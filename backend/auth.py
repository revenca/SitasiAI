"""backend/auth.py — Password hashing (bcrypt) + JWT token."""
import os
import bcrypt
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models

SECRET    = os.getenv("JWT_SECRET", "thesis-citation-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: int, email: str) -> str:
    payload = {"sub": str(user_id), "email": email,
               "exp": datetime.utcnow() + timedelta(days=TOKEN_TTL_DAYS)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    cred_err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token tidak valid", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        uid = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise cred_err
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user:
        raise cred_err
    return user
