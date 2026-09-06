# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace API] 공용 의존성
================================================================================
- Neo4j 드라이버는 프로세스 전체에서 단 하나만 생성해 재사용한다(READ_ACCESS 강제).
- get_current_user: Authorization: Bearer <JWT> 헤더를 검증해 로그인 사용자를 반환.
  포트폴리오처럼 로그인이 필요한 라우터에서만 Depends로 사용한다.
================================================================================
"""

import os
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 내작업폴더
REPO_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(REPO_ROOT, ".env"))

_security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
    user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    return driver


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_security)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")

    from services.auth_service import decode_access_token, get_user_by_id

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")

    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")
    return user
