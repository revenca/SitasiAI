"""
backend/vectordb.py — Basis data vektor PostgreSQL + pgvector (opsional).

Bila DATABASE_URL menunjuk ke Postgres DAN tabel `documents` sudah ada, modul ini dipakai
sebagai basis data vektor (menggantikan FAISS). Jika Postgres tidak tersedia / belum
di-migrasi, available() = False → rag_engine otomatis fallback ke FAISS. Jadi aman:
tanpa Postgres, sistem tetap jalan seperti biasa.

Env:
    DATABASE_URL=postgresql://user:pass@host:5432/sitasiai
"""
import os
import numpy as np

try:
    import psycopg2
    from psycopg2.extras import execute_values
    from pgvector.psycopg2 import register_vector
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

PG_URL = os.getenv("DATABASE_URL", "") or os.getenv("PG_URL", "")
if PG_URL and not PG_URL.startswith(("postgres://", "postgresql://")):
    PG_URL = ""                       # hanya aktif untuk URL Postgres

_conn = None
_checked = False


def _connect():
    global _conn, _checked
    if _conn is not None:
        return _conn
    if _checked or not (_HAS_PG and PG_URL):
        return None
    _checked = True
    try:
        c = psycopg2.connect(PG_URL)
        with c.cursor() as cur:                   # ekstensi vector harus ada SEBELUM register
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.commit()
        register_vector(c)
        _conn = c
        return c
    except Exception as e:                        # koneksi gagal → fallback FAISS
        print(f"[vectordb] Postgres tidak terhubung ({e}); pakai FAISS.")
        return None


def available() -> bool:
    """True bila Postgres terhubung dan tabel documents siap dipakai."""
    c = _connect()
    if c is None:
        return False
    try:
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('public.documents')")
            return cur.fetchone()[0] is not None
    except Exception:
        return False


def count(source: str = None) -> int:
    c = _connect()
    if c is None:
        return 0
    with c.cursor() as cur:
        if source:
            cur.execute("SELECT count(*) FROM documents WHERE source=%s", (source,))
        else:
            cur.execute("SELECT count(*) FROM documents")
        return cur.fetchone()[0]


def search(query_emb, top_k: int = 5, source: str = None) -> list:
    """Top-k paper terdekat (cosine) via pgvector. Format kandidat sama dgn rag_engine."""
    c = _connect()
    if c is None:
        return []
    vec = np.asarray(query_emb, dtype=np.float32)
    with c.cursor() as cur:
        if source:
            cur.execute(
                "SELECT paper_title, abstract, authors, year, citation, doi, cited_by, source, "
                "1 - (embedding <=> %s) AS score FROM documents WHERE source=%s "
                "ORDER BY embedding <=> %s LIMIT %s", (vec, source, vec, top_k))
        else:
            cur.execute(
                "SELECT paper_title, abstract, authors, year, citation, doi, cited_by, source, "
                "1 - (embedding <=> %s) AS score FROM documents "
                "ORDER BY embedding <=> %s LIMIT %s", (vec, vec, top_k))
        rows = cur.fetchall()
    out = []
    for title, abstract, authors, year, citation, doi, cited_by, src, score in rows:
        out.append({"paper_title": title, "chunk_text": abstract or "",
                    "authors": authors or "", "year": year or "", "citation": citation or "",
                    "doi": doi or "", "cited_by": cited_by or 0, "source": src,
                    "score": float(score)})
    return out


def list_papers(q: str = "", limit: int = 50, offset: int = 0) -> dict:
    """Daftar/cari paper di basis data (untuk halaman Library).
    Return {total, papers:[{title,year,authors,cited_by,doi}]}."""
    c = _connect()
    if c is None:
        return {"total": 0, "papers": []}
    like = f"%{q}%"
    with c.cursor() as cur:
        if q:
            cur.execute("SELECT count(*) FROM documents WHERE paper_title ILIKE %s", (like,))
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT paper_title, year, authors, cited_by, doi FROM documents "
                "WHERE paper_title ILIKE %s ORDER BY cited_by DESC NULLS LAST LIMIT %s OFFSET %s",
                (like, limit, offset))
        else:
            cur.execute("SELECT count(*) FROM documents")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT paper_title, year, authors, cited_by, doi FROM documents "
                "ORDER BY cited_by DESC NULLS LAST LIMIT %s OFFSET %s", (limit, offset))
        rows = cur.fetchall()
    return {"total": total,
            "papers": [{"title": t, "year": y or "", "authors": a or "",
                        "cited_by": cb or 0, "doi": d or ""} for t, y, a, cb, d in rows]}


# ── Untuk migrasi (dipakai backend/migrate_to_pgvector.py) ────────────────────
def ensure_schema(dim: int = 768):
    c = _connect()
    if c is None:
        raise RuntimeError("Postgres tidak terhubung — set DATABASE_URL ke postgresql://...")
    with c.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                paper_title TEXT NOT NULL,
                abstract    TEXT,
                authors     TEXT,
                year        TEXT,
                citation    TEXT,
                doi         TEXT,
                cited_by    INTEGER DEFAULT 0,
                source      TEXT,
                embedding   vector({dim})
            )
        """)
    c.commit()


def create_index():
    """Index HNSW cosine — dibuat SETELAH bulk insert (jauh lebih cepat)."""
    c = _connect()
    with c.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS documents_emb_hnsw "
                    "ON documents USING hnsw (embedding vector_cosine_ops)")
    c.commit()


def truncate(source: str = None):
    c = _connect()
    with c.cursor() as cur:
        if source:
            cur.execute("DELETE FROM documents WHERE source=%s", (source,))
        else:
            cur.execute("TRUNCATE documents RESTART IDENTITY")
    c.commit()


def bulk_insert(records: list):
    """records: list dict(paper_title, abstract, authors, year, citation, doi, cited_by,
    source, embedding=np.ndarray)."""
    c = _connect()
    with c.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO documents (paper_title, abstract, authors, year, citation, doi, "
            "cited_by, source, embedding) VALUES %s",
            [(r["paper_title"], r["abstract"], r["authors"], r["year"], r["citation"],
              r["doi"], r["cited_by"], r["source"], r["embedding"]) for r in records])
    c.commit()
