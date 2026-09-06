# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace API] 사용자 인증 서비스
================================================================================
- 이메일+비밀번호(bcrypt 해시) 기반 심플 인증. 외부 OAuth 연동 없이 자체 완결.
- portfolio_service.py와 동일한 SQLite 파일(users 테이블)을 사용한다.
- JWT(HS256) 액세스 토큰 발급/검증. 시크릿은 .env의 JWT_SECRET_KEY
  (미설정 시 개발 편의를 위한 기본값 사용 - 운영 배포 전 반드시 교체 필요).
================================================================================
"""

import os
import datetime
from typing import Optional, Dict, Any

import bcrypt
from jose import jwt, JWTError
from dotenv import load_dotenv

from services.portfolio_service import _get_conn

BASE_DIR_ENV = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR_ENV, ".env"))

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dart-trace-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 7일


def hash_password(password: str) -> str:
    # passlib 1.7.4는 bcrypt>=4.1과 내부 API 비호환(__about__ 제거)으로 스퓨리어스
    # "72 bytes" 에러를 내므로, bcrypt 라이브러리를 직접 사용한다.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def register_user(email: str, password: str) -> Dict[str, Any]:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("유효한 이메일 주소를 입력해주세요.")
    if len(password) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")

    conn = _get_conn()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise ValueError("이미 가입된 이메일입니다.")
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, hash_password(password), datetime.datetime.now().isoformat())
        )
        conn.commit()
        return {"id": cur.lastrowid, "email": email}
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    email = email.strip().lower()
    conn = _get_conn()
    try:
        row = conn.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "email": row["email"]}
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
