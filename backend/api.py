"""
backend/api.py — REST API (FastAPI): Auth + Papers + Recommend.
Jalankan:  python -m uvicorn backend.api:app --reload --port 8000
Docs   :  http://localhost:8000/docs
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend import rag_engine, models, auth
from backend.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Citation Recommender API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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

class AskReq(BaseModel):
    question: str
    top_k: int = 5


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


# ── Papers ───────────────────────────────────────────────────────────────────
@app.get("/papers")
def list_papers(q: str = "", category: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Paper)
    if q:
        query = query.filter(models.Paper.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Paper.category == category)
    papers = query.order_by(models.Paper.title).all()
    return [{"id": p.id, "title": p.title, "category": p.category, "n_chunks": p.n_chunks}
            for p in papers]


@app.get("/papers/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.query(models.Paper.category).distinct().all()
    return sorted([r[0] for r in rows])


# ── Recommend (butuh login) ──────────────────────────────────────────────────
@app.post("/recommend")
def recommend(req: RecommendReq, db: Session = Depends(get_db),
              user: models.User = Depends(auth.get_current_user)):
    res = rag_engine.recommend(req.paragraph, top_k=req.top_k,
                               use_hyde=req.use_hyde, use_cot=req.use_cot)
    # simpan history
    db.add(models.SearchHistory(user_id=user.id, query=req.paragraph[:1000],
                               citation_text=res.get("citation_text",""),
                               best_paper=res.get("best_reference_paper","")))
    db.commit()
    return res


@app.post("/ask")
def ask(req: AskReq, user: models.User = Depends(auth.get_current_user)):
    return rag_engine.answer_question(req.question, top_k=req.top_k)


@app.get("/history")
def history(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    rows = (db.query(models.SearchHistory)
            .filter(models.SearchHistory.user_id == user.id)
            .order_by(models.SearchHistory.created_at.desc()).limit(20).all())
    return [{"query": r.query, "citation_text": r.citation_text,
             "best_paper": r.best_paper, "created_at": str(r.created_at)} for r in rows]
