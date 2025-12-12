# -*- coding: utf-8-sig -*-
"""
Auth router: register, login, whoami.
Using JWT (HS256) via a shared secret from .env (AUTH_SECRET).
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import firebase_admin
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from backend.src.app.services.firebase_client import get_firestore_client
from backend.src.app.services.firestore_store import create_user, get_user

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


class FirebaseLoginIn(BaseModel):
    id_token: str = Field(min_length=10)


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
    if get_user(data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    password_hash = pwd_context.hash(data.password)
    create_user(data.username, password_hash)
    token = create_access_token(data.username, TOKEN_EXPIRE_MIN)
    return TokenOut(access_token=token, username=data.username)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn) -> TokenOut:
    """Login and return JWT."""
    user = get_user(data.username)
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


def _ensure_firebase_initialized() -> None:
    """Ensure firebase_admin default app exists before verifying tokens."""
    try:
        firebase_admin.get_app()
    except ValueError:
        # 初始化 Firestore（同時會建立 firebase_admin app）
        get_firestore_client()


@router.post("/firebase-login", response_model=TokenOut)
def firebase_login(data: FirebaseLoginIn) -> TokenOut:
    """Verify Firebase ID token + issue our JWT for downstream APIs."""
    _ensure_firebase_initialized()
    try:
        decoded = firebase_auth.verify_id_token(data.id_token)
    except Exception as exc:  # Firebase 會拋出多種例外，統一回傳 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
        ) from exc

    uid = decoded.get("uid")
    email = decoded.get("email")
    if not uid and not email:
        raise HTTPException(status_code=400, detail="Firebase token missing uid/email")
    username = (email or uid or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Firebase token missing username")

    user = get_user(username)
    if not user:
        # 以 Firebase 使用者 UID 建立一組獨立密碼雜湊，避免未來一般登入被誤用
        password_hash = pwd_context.hash(f"firebase:{uid or email}")
        create_user(username, password_hash)

    token = create_access_token(username, TOKEN_EXPIRE_MIN)
    return TokenOut(access_token=token, username=username)
