# -*- coding: utf-8 -*-
"""
🪵 [항목⑧ 실패 로깅 1단계] "확인하지 못했습니다"류 답변이나 자기검증 경고가 뜬 질문을
로컬 파일(JSONL)에 남긴다.

지금까지 이 서비스는 "확인하지 못했습니다" 응답이나 자기검증 경고가 어디에도 기록되지
않았다 - 그래서 오늘 발견된 실제 버그들(컨텍스트 희석, N+1 쿼리로 인한 504 등)이 전부
"사용자가 우연히 발견 -> 채팅으로 제보"로만 찾아졌다. 이 로그를 켜두면 실제로 어떤
질문/유형이 얼마나 자주 실패하는지 실측 데이터로 알 수 있다.

대화내용 전체를 DB에 저장할지(항목⑤)는 아직 결정되지 않았고, 그 결정에는 개인정보
보존정책까지 같이 정해야 하는 더 큰 논의가 필요하다 - 그 결정을 기다리지 않고 먼저
켤 수 있는 가장 가벼운 형태로 시작한다: 학생 개인정보(성적 등)를 구조화해서 담지 않고
질문 원문 + 실패 신호만 로컬 파일에 남긴다. 나중에 DB로 옮기기로 결정되면 이 파일을
그대로 적재하면 된다.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_LOG_PATH = Path(os.getenv(
    "ART_ADMISSION_GAP_LOG_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "logs" / "art_admission_qa_gaps.jsonl"),
))

_GIVE_UP_MARKERS = ("확인하지 못했습니다", "찾지 못했습니다", "찾을 수 없습니다")


def log_if_gap(query: str, endpoint: str, result: Dict[str, Any]) -> None:
    """답변에 문제 신호(포기 문구/자기검증 경고/에러)가 있으면 한 줄(JSON) 기록한다.
    로깅 자체가 실패해도(디스크 권한 등) 절대 실제 응답을 막지 않는다 - 예외를 전부
    조용히 삼킨다."""
    try:
        answer = result.get("answer") or ""
        warnings = result.get("self_check_warnings") or []
        gave_up = any(m in answer for m in _GIVE_UP_MARKERS)
        is_gap = bool(warnings) or bool(result.get("error")) or gave_up
        if not is_gap:
            return
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "query": query,
            "route": (result.get("routing") or {}).get("route"),
            "self_check_warnings": warnings,
            "error": bool(result.get("error")),
            "gave_up": gave_up,
        }
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
