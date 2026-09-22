# -*- coding: utf-8 -*-
"""
🪵 [항목⑤+⑧] 대화 턴 로깅 - Supabase(franchise와 같은 프로젝트를 공유하되, 이 서비스
전용 테이블 art_admission_qa_logs만 씀) + 로컬 파일 폴백.

지금까지 이 서비스는 "확인하지 못했습니다" 응답이나 자기검증 경고가 어디에도 기록되지
않았다 - 그래서 오늘 발견된 실제 버그들(컨텍스트 희석, N+1 쿼리로 인한 504 등)이 전부
"사용자가 우연히 발견 -> 채팅으로 제보"로만 찾아졌다. 이 로그가 있으면 실제로 어떤
질문/유형이 얼마나 자주 실패하는지, 그리고 대화가 몇 턴이나 이어지는지 실측 데이터로
알 수 있다.

원문 발췌(context_tracks/tool_trace 등)는 저장하지 않는다 - Neo4j가 이미 원본이라
중복 저장할 이유가 없고, 용량도 10~50배 커진다. 질문 원문 + 답변 + 라우팅/자기검증
메타데이터만 남긴다.

기록은 항상 별도 스레드에서 비동기로 보낸다 - Supabase 응답을 기다리지 않으므로
API 응답 지연에 전혀 영향을 주지 않는다. Supabase 설정(URL/KEY)이 없거나 요청이
실패하면 로컬 파일(logs/art_admission_qa_gaps.jsonl, gitignore 처리)로 자동
폴백한다 - 로깅 실패가 절대 실제 응답을 막지 않는다.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_SUPABASE_URL = os.getenv("ART_ADMISSION_SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("ART_ADMISSION_SUPABASE_SERVICE_KEY", "")
_SUPABASE_TABLE = "art_admission_qa_logs"

_LOG_PATH = Path(os.getenv(
    "ART_ADMISSION_GAP_LOG_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "logs" / "art_admission_qa_gaps.jsonl"),
))

_GIVE_UP_MARKERS = ("확인하지 못했습니다", "찾지 못했습니다", "찾을 수 없습니다")


def _write_local_fallback(entry: Dict[str, Any]) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 로깅 자체가 실패해도(디스크 권한 등) 절대 응답을 막지 않는다.


def _send_to_supabase(entry: Dict[str, Any], debug_entry: Dict[str, Any]) -> None:
    try:
        import requests
        resp = requests.post(
            f"{_SUPABASE_URL}/rest/v1/{_SUPABASE_TABLE}",
            headers={
                "apikey": _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=entry, timeout=5,
        )
        if resp.status_code >= 300:
            _write_local_fallback({**debug_entry, "_supabase_error": f"{resp.status_code}: {resp.text[:300]}"})
    except Exception as e:
        _write_local_fallback({**debug_entry, "_supabase_error": str(e)})


def log_turn(query: str, endpoint: str, result: Dict[str, Any], session_id: Optional[str] = None) -> None:
    """매 턴을 비동기로 기록한다. Supabase 설정이 없으면 로컬 파일에만 남긴다."""
    try:
        answer = result.get("answer") or ""
        warnings = result.get("self_check_warnings") or []
        routing = result.get("routing") or {}
        entry = {
            "session_id": session_id or "unknown",
            "endpoint": endpoint,
            "query": query,
            "answer": answer,
            "route": routing.get("route"),
            "routing_method": routing.get("method"),
            "self_check_warnings": warnings,
            "gave_up": any(m in answer for m in _GIVE_UP_MARKERS),
            "error": bool(result.get("error")),
            "model": result.get("model"),
        }
    except Exception:
        return

    if _SUPABASE_URL and _SUPABASE_KEY:
        debug_entry = {**entry, "ts": datetime.now(timezone.utc).isoformat()}
        threading.Thread(target=_send_to_supabase, args=(entry, debug_entry), daemon=True).start()
    else:
        _write_local_fallback({**entry, "ts": datetime.now(timezone.utc).isoformat()})


# 이전 이름(항목⑧ 1단계, 실패만 기록) 호출부와의 하위 호환 - log_turn으로 위임한다.
def log_if_gap(query: str, endpoint: str, result: Dict[str, Any]) -> None:
    log_turn(query, endpoint, result)
