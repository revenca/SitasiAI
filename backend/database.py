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

ROOT   = Path(__file__).resolve().parent.parent
# DATABASE_URL Postgres → dipakai untuk tabel relasional (users/history/papers).
# Bila kosong → SQLite lokal (app.db). Normalisasi ke driver psycopg2 untuk SQLAlchemy.
DB_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{ROOT / 'app.db'}"
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
