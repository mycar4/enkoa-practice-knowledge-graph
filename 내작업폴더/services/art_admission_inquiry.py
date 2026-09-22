# -*- coding: utf-8 -*-
"""
1:1 상담신청 게시판 - 회원가입 없이 운영하기 위해 국내 커뮤니티 게시판의 표준
패턴("글 작성 시 비밀번호 설정 -> 열람 시 입력")을 그대로 쓴다. 목록에는 제목/
작성자(마스킹)/날짜/답변상태만 노출하고, 질문·답변 본문은 비밀번호가 맞아야만
보여준다.

art_admission_gap_log.py와 같은 Supabase 프로젝트(franchise와 공유)의 별도
테이블(art_admission_inquiries)을 쓴다. 로그와 달리 이건 "쓰고 바로 읽어야"
하므로(제출 직후 목록에 나와야 함) 비동기 폴백이 아니라 동기 호출이다 -
Supabase가 죽으면 그냥 에러를 그대로 올린다(사용자에게 "잠시 후 다시
시도하세요"로 보여줌).
"""
import hashlib
import os
import secrets
from typing import Any, Dict, List, Optional

import requests

_SUPABASE_URL = os.getenv("ART_ADMISSION_SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("ART_ADMISSION_SUPABASE_SERVICE_KEY", "")
_TABLE = "art_admission_inquiries"


class InquiryConfigError(Exception):
    """Supabase 설정(URL/KEY)이 없을 때 - 로그와 달리 이 기능은 폴백이 없다."""


def _headers(prefer: str = "return=representation") -> Dict[str, str]:
    if not (_SUPABASE_URL and _SUPABASE_KEY):
        raise InquiryConfigError("ART_ADMISSION_SUPABASE_URL/SERVICE_KEY가 설정되지 않았습니다.")
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _mask_name(name: str) -> str:
    """게시판 목록용 이름 마스킹: 2글자면 가운데, 3글자 이상이면 가운데만 남기고 별표."""
    name = (name or "").strip()
    if len(name) <= 1:
        return name
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def create_inquiry(
    name: str, contact: str, title: str, question_content: str,
    password: str, session_id: Optional[str] = None,
) -> Dict[str, Any]:
    salt = secrets.token_hex(8)
    row = {
        "name": name, "contact": contact, "title": title,
        "question_content": question_content,
        "password_salt": salt, "password_hash": _hash_password(password, salt),
        "session_id": session_id,
    }
    resp = requests.post(
        f"{_SUPABASE_URL}/rest/v1/{_TABLE}", headers=_headers(), json=row, timeout=10,
    )
    resp.raise_for_status()
    created = resp.json()[0]
    return {"id": created["id"], "created_at": created["created_at"]}


def list_inquiries_public() -> List[Dict[str, Any]]:
    """목록용 - 본문/비밀번호/연락처는 절대 포함하지 않는다."""
    resp = requests.get(
        f"{_SUPABASE_URL}/rest/v1/{_TABLE}"
        "?select=id,name,title,status,created_at,answered_at&order=created_at.desc&limit=200",
        headers=_headers(), timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    for r in rows:
        r["name"] = _mask_name(r.get("name", ""))
    return rows


def view_inquiry(inquiry_id: int, password: str) -> Optional[Dict[str, Any]]:
    """비밀번호가 맞으면 본문+답변을 반환, 틀리거나 없으면 None."""
    resp = requests.get(
        f"{_SUPABASE_URL}/rest/v1/{_TABLE}?id=eq.{inquiry_id}&select=*",
        headers=_headers(), timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return None
    row = rows[0]
    if _hash_password(password, row["password_salt"]) != row["password_hash"]:
        return None
    return {
        "id": row["id"], "title": row["title"], "question_content": row["question_content"],
        "answer_content": row.get("answer_content"), "status": row["status"],
        "created_at": row["created_at"], "answered_at": row.get("answered_at"),
    }



# 관리자(답변 작성) 쪽은 이 Python API를 거치지 않는다 - franchise BO가 이미
# art_admission_qa_logs를 읽을 때 쓰던 것과 같은 패턴(TypeScript에서 Supabase REST를
# 직접 호출)으로 art_admission_inquiries도 조회/답변한다. BO는 별도 로그인 세션으로
# 이미 보호되므로 비밀번호 체크 없이 전체 행에 접근한다.
