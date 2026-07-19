"""
backend/api.py — REST API (FastAPI): Auth + Papers + Recommend.
Jalankan:  python -m uvicorn backend.api:app --reload --port 8000
Docs   :  http://localhost:8000/docs
"""
import os
import re
import json
import logging

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend import rag_engine, models, auth
from backend.database import Base, engine, get_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sitasiai")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Citation Recommender API", version="1.0")
# CORS dibatasi ke origin frontend (set CORS_ORIGINS di .env; pisah koma)
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins,
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


# ── Schemas ──────────────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class RecommendReq(BaseModel):
    paragraph: str
    top_k: int = 5
    use_hyde: bool = True
    use_cot: bool = True
    external: bool = False

class AskReq(BaseModel):
    question: str
    top_k: int = 5


# ── Rate limit sederhana (sliding window per user) ───────────────────────────
# Endpoint LLM itu mahal (6–8 panggilan API berbayar per request) — batasi per user.
import time as _time
from collections import defaultdict, deque

RATE_LIMIT_N   = int(os.getenv("RATE_LIMIT_N", "10"))      # maks request...
RATE_LIMIT_WIN = int(os.getenv("RATE_LIMIT_WIN", "60"))    # ...per detik window
_hits: dict = defaultdict(deque)


def _client_key(request: Request) -> str:
    """Kunci rate-limit per-IP. Di belakang reverse proxy (nginx senopati.its),
    IP asli ada di X-Forwarded-For (ambil hop pertama)."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(key: str):
    now = _time.time()
    q = _hits[key]
    while q and now - q[0] > RATE_LIMIT_WIN:
        q.popleft()
    if len(q) >= RATE_LIMIT_N:
        raise HTTPException(status_code=429,
                            detail=f"Terlalu banyak permintaan — maks {RATE_LIMIT_N} per "
                                   f"{RATE_LIMIT_WIN} detik. Coba lagi sebentar.")
    q.append(now)


# ── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _startup():
    rag_engine.init()


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Auth ─────────────────────────────────────────────────────────────────────
@app.post("/auth/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    user = models.User(name=req.name, email=req.email,
                       hashed_password=auth.hash_password(req.password))
    db.add(user); db.commit(); db.refresh(user)
    token = auth.create_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/auth/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user or not auth.verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    token = auth.create_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/auth/me")
def me(user: models.User = Depends(auth.get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


# ── Papers / Library ─────────────────────────────────────────────────────────
@app.get("/papers")
def list_papers(q: str = "", category: str = "", limit: int = 50, offset: int = 0,
                db: Session = Depends(get_db)):
    """Library: langsung ke basis data vektor (163k, Postgres) bila tersedia;
    fallback ke tabel korpus 100-paper (SQLite)."""
    try:
        from backend import vectordb
        if vectordb.available():
            res = vectordb.list_papers(q=q, limit=min(limit, 100), offset=offset)
            return {"source": "database", "total": res["total"], "papers": res["papers"]}
    except Exception:
        log.exception("list_papers via vectordb gagal; fallback korpus")
    query = db.query(models.Paper)
    if q:
        query = query.filter(models.Paper.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Paper.category == category)
    papers = query.order_by(models.Paper.title).all()
    return {"source": "korpus", "total": len(papers),
            "papers": [{"title": p.title, "year": "", "authors": p.category,
                        "cited_by": p.n_chunks, "doi": ""} for p in papers]}


@app.get("/papers/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.query(models.Paper.category).distinct().all()
    return sorted([r[0] for r in rows])


# ── Recommend (butuh login) ──────────────────────────────────────────────────
def _run_llm_endpoint(name, fn, request: Request):
    """Rate-limit per-IP + logging seragam untuk endpoint yang memanggil LLM."""
    key = _client_key(request)
    check_rate_limit(key)
    try:
        return fn()
    except HTTPException:
        raise
    except Exception:
        log.exception("endpoint %s gagal (ip=%s)", name, key)
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal. Coba lagi.")


@app.post("/recommend")
def recommend(req: RecommendReq, request: Request, db: Session = Depends(get_db),
              user: models.User = Depends(auth.get_current_user)):
    res = _run_llm_endpoint("/recommend", lambda: rag_engine.recommend(
        req.paragraph, top_k=req.top_k, use_hyde=True, use_cot=True), request)
    if user.id:                             # anonim (AUTH_DISABLED) → tanpa history
        db.add(models.SearchHistory(user_id=user.id, query=req.paragraph[:1000],
                                   citation_text=res.get("citation_text",""),
                                   best_paper=res.get("best_reference_paper","")))
        db.commit()
    return res


@app.post("/recommend-external")
def recommend_external(req: RecommendReq, request: Request, db: Session = Depends(get_db),
                       user: models.User = Depends(auth.get_current_user)):
    """Rekomendasi sitasi dari sumber EKSTERNAL (Semantic Scholar live)."""
    res = _run_llm_endpoint("/recommend-external", lambda: rag_engine.recommend_external(
        req.paragraph, top_k=req.top_k), request)
    if user.id:                             # anonim (AUTH_DISABLED) → tanpa history
        db.add(models.SearchHistory(user_id=user.id, query=req.paragraph[:1000],
                                   citation_text=res.get("citation_text",""),
                                   best_paper=res.get("best_reference_paper","")))
        db.commit()
    return res


@app.post("/cite-abstract")
def cite_abstract(req: RecommendReq, request: Request, db: Session = Depends(get_db),
                  user: models.User = Depends(auth.get_current_user)):
    """Auto-sitasi abstrak: sisipkan (Penulis, Tahun) per kalimat + daftar referensi."""
    res = _run_llm_endpoint("/cite-abstract", lambda: rag_engine.cite_abstract(
        req.paragraph, top_k=req.top_k, prefer_external=req.external), request)
    if user.id:
        db.add(models.SearchHistory(user_id=user.id, query=req.paragraph[:1000],
                                   citation_text=res.get("cited_abstract", "")[:2000], best_paper=""))
        db.commit()
    return res


@app.post("/ask")
def ask(req: AskReq, request: Request, user: models.User = Depends(auth.get_current_user)):
    return _run_llm_endpoint("/ask", lambda: rag_engine.answer_question(
        req.question, top_k=req.top_k), request)


@app.post("/ask-external")
def ask_external(req: AskReq, request: Request, user: models.User = Depends(auth.get_current_user)):
    """Pertanyaan/topik pendek → cari paper dari sumber eksternal + jawaban singkat."""
    return _run_llm_endpoint("/ask-external", lambda: rag_engine.ask_external(
        req.question, top_k=req.top_k), request)


@app.get("/history")
def history(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    rows = (db.query(models.SearchHistory)
            .filter(models.SearchHistory.user_id == user.id)
            .order_by(models.SearchHistory.created_at.desc()).limit(20).all())
    return [{"query": r.query, "citation_text": r.citation_text,
             "best_paper": r.best_paper, "created_at": str(r.created_at)} for r in rows]


# ── Riwayat chat ANONIM (tanpa login) — disimpan per-ID browser di server ────────
_ANON_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")   # format ID aman (cegah injeksi/abuse)
ANON_MAX_BYTES = 600_000                          # batas ukuran blob per-ID

class AnonHistoryReq(BaseModel):
    data: list                                     # daftar sesi chat


@app.get("/anon-history/{anon_id}")
def get_anon_history(anon_id: str, db: Session = Depends(get_db)):
    if not _ANON_RE.match(anon_id):
        raise HTTPException(400, "anon_id tidak valid")
    row = db.query(models.AnonChat).filter(models.AnonChat.anon_id == anon_id).first()
    if not row:
        return {"data": [], "updated_at": None}
    try:
        data = json.loads(row.data or "[]")
    except Exception:
        data = []
    return {"data": data, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@app.put("/anon-history/{anon_id}")
def put_anon_history(anon_id: str, req: AnonHistoryReq, db: Session = Depends(get_db)):
    if not _ANON_RE.match(anon_id):
        raise HTTPException(400, "anon_id tidak valid")
    blob = json.dumps(req.data[:50], ensure_ascii=False)   # maks 50 sesi
    if len(blob.encode("utf-8")) > ANON_MAX_BYTES:
        raise HTTPException(413, "riwayat terlalu besar")
    row = db.query(models.AnonChat).filter(models.AnonChat.anon_id == anon_id).first()
    if row:
        row.data = blob
    else:
        db.add(models.AnonChat(anon_id=anon_id, data=blob))
    db.commit()
    return {"ok": True}
