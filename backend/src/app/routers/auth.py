# -*- coding: utf-8-sig -*-
"""
Auth router: register, login, whoami.
Using JWT (HS256) via a shared secret from .env (AUTH_SECRET).
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from backend.src.app.services.file_store import ensure_dirs, load_users, save_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()

ALGORITHM = "HS256"
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")
TOKEN_EXPIRE_MIN = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))  # 1 day


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


def create_access_token(username: str, expires_minutes: int) -> str:
    """Create JWT token."""
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode = {"sub": username, "exp": expire}
    return jwt.encode(to_encode, AUTH_SECRET, algorithm=ALGORITHM)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    """Extract username from JWT."""
    token = creds.credentials
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise JWTError("missing sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return username


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn) -> TokenOut:
    """Register a new user (unique username)."""
    users = load_users()
    if data.username in users:
        raise HTTPException(status_code=400, detail="Username already exists")

    ensure_dirs(data.username)
    password_hash = pwd_context.hash(data.password)
    save_user(data.username, password_hash)
    token = create_access_token(data.username, TOKEN_EXPIRE_MIN)
    return TokenOut(access_token=token, username=data.username)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn) -> TokenOut:
    """Login and return JWT."""
    users = load_users()
    user = users.get(data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(data.username, TOKEN_EXPIRE_MIN)
    return TokenOut(access_token=token, username=data.username)


@router.get("/me")
def me(username: str = Depends(get_current_user)) -> dict:
    """Return current username."""
    return {"username": username}
