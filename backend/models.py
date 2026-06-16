"""backend/models.py — Model database: User, Paper, SearchHistory."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

    history = relationship("SearchHistory", back_populates="user", cascade="all, delete")


class Paper(Base):
    __tablename__ = "papers"
    id        = Column(Integer, primary_key=True, index=True)
    title     = Column(String, index=True, nullable=False)
    category  = Column(String, default="Lainnya")
    n_chunks  = Column(Integer, default=0)


class SearchHistory(Base):
    __tablename__ = "search_history"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    query         = Column(Text)
    citation_text = Column(Text)
    best_paper    = Column(String)
    created_at    = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="history")
