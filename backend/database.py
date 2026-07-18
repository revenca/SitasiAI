"""backend/database.py — Setup SQLAlchemy (SQLite default, Postgres bila DATABASE_URL di-set)."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT     = Path(__file__).resolve().parent.parent
SQLITE_URL = f"sqlite:///{ROOT / 'app.db'}"
# DATABASE_URL Postgres → dipakai untuk tabel relasional (users/history/papers).
# Bila kosong → SQLite lokal (app.db). Normalisasi ke driver psycopg2 untuk SQLAlchemy.
DB_URL = os.getenv("DATABASE_URL", "").strip() or SQLITE_URL
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


def _make_engine(url):
    ca = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=ca, pool_pre_ping=True)


engine = _make_engine(DB_URL)
# Uji koneksi sekali; bila Postgres tak terjangkau → fallback SQLite agar backend tetap hidup.
if not DB_URL.startswith("sqlite"):
    try:
        with engine.connect():
            pass
    except Exception as e:
        print(f"[database] Postgres tak terjangkau ({type(e).__name__}); fallback ke SQLite. "
              "Tabel vektor akan pakai FAISS (bukan pgvector).")
        DB_URL = SQLITE_URL
        engine = _make_engine(DB_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
