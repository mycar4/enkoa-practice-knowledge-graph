# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 검증용 FO(Front Office) 연동 API
================================================================================
- "새 제품 개발"이 아니라 이미 검증된 art_admission_service.py/art_admission_llm.py
  함수를 그대로 HTTP로 감싼 것뿐이다. 새 비즈니스 로직은 여기 없다.
- 노출 범위는 딱 4개 - 학교/전형 조회, 호환학교 매칭(6장 조합 추천 아님, 그대로
  있던 기능), RAG 질의응답, 서류첨삭. 학생관리/PDF리포트/결제/관리자는 의도적으로
  아예 안 만들었다 - "Validation FO" 범위 밖.
- 프리미엄(gated) 모델은 외부 공개 API에서 비용/오남용 위험이 있어 노출하지
  않는다 - 항상 gpt-4o-mini(무료키만 있으면 쓸 수 있는 저비용 모델)로 고정.
- 실행: uv run uvicorn 내작업폴더.api_art_admission:app --reload --port 8000
  (배포 시에는 별도 호스팅 - Streamlit Cloud는 FastAPI를 못 띄운다)
================================================================================
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from services.art_admission_service import ArtAdmissionService  # noqa: E402
from services.art_admission_llm import answer_with_llm, review_document, chat_about_review  # noqa: E402

DEFAULT_MODEL = "gpt-4o-mini"  # 공개 API는 항상 이 모델만 쓴다 - gated 모델 노출 안 함

app = FastAPI(
    title="Art Admission Validation API",
    description="검증용 FO 연동을 위한 최소 API - 새 비즈니스 로직 없음, 기존 엔진 그대로 노출",
    version="0.1.2",
)

# 새 브랜드 도메인(예: artready.kr)에서 호출할 것이므로 CORS를 열어야 한다.
# 실제 도메인이 정해지면 "*" 대신 그 도메인만 넣는 걸 강력히 권장한다 -
# 지금은 검증 단계라 열어두되, 운영 전환 시 반드시 좁혀야 함.
_ALLOWED_ORIGINS = os.getenv("FO_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_service() -> ArtAdmissionService:
    return ArtAdmissionService()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universities")
def list_universities():
    """01 PROFILE / 02 MATCH 화면용 - 등록된 학교/학과 목록."""
    svc = get_service()
    try:
        return svc.list_universities()
    finally:
        svc.close()


@app.get("/universities/{university}")
def university_detail(university: str, campus: Optional[str] = None):
    svc = get_service()
    try:
        detail = svc.get_university_detail(university, campus=campus)
        if not detail:
            raise HTTPException(status_code=404, detail="해당 학교 데이터를 찾을 수 없습니다.")
        return detail
    finally:
        svc.close()


class PrepSearchRequest(BaseModel):
    topic_keywords: Optional[List[str]] = None
    material_query: str = ""
    document_only: bool = False


@app.get("/prep-topics")
def prep_topics():
    """"큰 주제" 선택지 - FO의 실기종목 선택 UI에 그대로 넣을 값."""
    svc = get_service()
    try:
        return svc.list_exam_topic_keywords()
    finally:
        svc.close()


@app.get("/stats")
def stats():
    """홈 화면 통계용 - 고유 대학 수와 전형(트랙) 수를 분리해서 반환한다.
    캠퍼스가 여러 개인 대학(홍익대 등)을 두 번 세지 않도록 university 집합은
    이름으로만 dedup한다. 새 비즈니스 로직 없음 - list_all_tracks_full() 결과를
    그냥 집계만 한다."""
    svc = get_service()
    try:
        tracks = svc.list_all_tracks_full()
        universities = {t["university"] for t in tracks}
        years = sorted({t.get("admission_year") for t in tracks if t.get("admission_year")})
        return {
            "university_count": len(universities),
            "track_count": len(tracks),
            "admission_years": years,
        }
    finally:
        svc.close()


class CompareRequest(BaseModel):
    selections: List[dict]  # [{"university": ..., "department": ...}, ...]


@app.post("/compare-tracks")
def compare_tracks_endpoint(req: CompareRequest):
    """대학 찾기 결과에서 2~6개 전형을 선택했을 때 나란히 비교표를 만든다.
    기존 Streamlit '전형 비교' 탭이 쓰던 get_comparison_table() 그대로 재사용."""
    svc = get_service()
    try:
        return svc.get_comparison_table(req.selections)
    finally:
        svc.close()


@app.post("/simulate-multi-apply")
def simulate_multi_apply_endpoint(req: CompareRequest):
    """선택한 조합 안에서만 일정(실기고사일) 충돌을 검사한다. 기존 '동시지원
    시뮬레이터' 탭이 쓰던 simulate_multi_apply() 그대로 재사용 - 새 로직 없음."""
    svc = get_service()
    try:
        return svc.simulate_multi_apply(req.selections)
    finally:
        svc.close()


@app.get("/calendar-events")
def calendar_events_endpoint():
    """전체 전형의 원서접수/실기고사/발표/등록 일정. FO에서 선택된 학교만
    클라이언트 쪽에서 골라 타임라인으로 그린다. 기존 '일정 캘린더' 탭이 쓰던
    get_calendar_events() 그대로 재사용."""
    svc = get_service()
    try:
        return svc.get_calendar_events()
    finally:
        svc.close()


@app.get("/past-topics")
def past_topics_endpoint(university: Optional[str] = None):
    """Evidence Drawer에서 기출문제가 있으면 같이 보여주기 위한 조회.
    기존 '기출문제' 탭이 쓰던 get_past_topics() 그대로 재사용."""
    svc = get_service()
    try:
        return svc.get_past_topics(university=university)
    finally:
        svc.close()


@app.post("/prep-search")
def prep_search(req: PrepSearchRequest):
    """03 RESULT 화면 - 학생이 선택한 실기종목/재료로 호환 학교 찾기.
    기존 "준비한 실기로 학교 찾기" 탭과 동일 로직, 새 비즈니스 로직 없음."""
    svc = get_service()
    try:
        return svc.search_tracks_by_prep(
            topic_keywords=req.topic_keywords, material_query=req.material_query,
            document_only=req.document_only,
        )
    finally:
        svc.close()


class QARequest(BaseModel):
    query: str


@app.post("/qa")
def qa(req: QARequest):
    """04 EVIDENCE 화면 - 기존 질의응답 탭의 AI 답변 파이프라인 그대로.
    항상 gpt-4o-mini만 쓴다(공개 API에서 프리미엄 모델 비용 노출 방지)."""
    svc = get_service()
    try:
        context_tracks, context_estimates = svc.build_llm_context(req.query)
        try:
            context_raw = svc.hybrid_search(req.query, top_k=5)
        except Exception:
            context_raw = []
        anchor_names = [t["university"] for t in context_tracks]
        exclude_names = anchor_names + [t["department"] for t in context_tracks]
        try:
            context_graph_related = svc.get_graph_related_context(
                req.query, anchor_names=anchor_names, exclude_names=exclude_names, top_n=5,
            )
        except Exception:
            context_graph_related = []
        try:
            context_compatible = svc.get_compatible_tracks_for_query(req.query)
        except Exception:
            context_compatible = []

        result = answer_with_llm(
            context_tracks, context_estimates, req.query,
            model_id=DEFAULT_MODEL, context_raw_excerpts=context_raw,
            context_graph_related=context_graph_related,
            context_compatible_tracks=context_compatible,
        )
        return {
            **result,
            "context_tracks": context_tracks,
            "context_compatible_tracks": context_compatible,
            "context_graph_related": context_graph_related,
            "context_raw_excerpts": context_raw,
        }
    finally:
        svc.close()


class ReviewRequest(BaseModel):
    text: str
    doc_type: str = "자기소개서"
    university: Optional[str] = None


@app.post("/review-document")
def review_document_endpoint(req: ReviewRequest):
    """서류첨삭 메뉴 그대로. 학교를 지정하면 해당 학교 서류 규정 원문을 근거로 반영."""
    svc = get_service()
    try:
        graph_hint = []
        try:
            graph_hint = svc.detect_entities_in_text(req.text)
        except Exception:
            pass
        doc_rules = []
        if req.university:
            try:
                doc_rules = svc.get_document_rule_excerpts(req.university, req.doc_type)
            except Exception:
                pass
        result = review_document(
            req.text, model_id=DEFAULT_MODEL, doc_type=req.doc_type,
            graph_hint=graph_hint, university=req.university, context_doc_rules=doc_rules,
        )
        # rules_found는 LLM 판단이 아니라 실제로 발췌를 찾았는지(doc_rules 존재 여부) 그대로
        # 반영한 결정론적 값 - 화면이 이 값만 보고 안내 배너를 그리게 해서, LLM이 자체적으로
        # "규정을 확인/확인못함" 문구를 잘못 말해도 화면 표시와 어긋나지 않게 한다.
        return {**result, "doc_rules": doc_rules, "graph_hint": graph_hint, "rules_found": bool(doc_rules)}
    finally:
        svc.close()


class ReviewChatRequest(BaseModel):
    doc_text: str
    doc_type: str = "자기소개서"
    history: List[dict]


@app.post("/review-chat")
def review_chat_endpoint(req: ReviewChatRequest):
    """첨삭 후 이어지는 대화. history는 최초 첨삭(assistant)부터 이후 주고받은
    턴을 [{'role': 'user'|'assistant', 'content': ...}] 그대로 담아 보낸다."""
    return chat_about_review(req.doc_text, req.doc_type, req.history, model_id=DEFAULT_MODEL)
