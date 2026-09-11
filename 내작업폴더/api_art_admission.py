# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 검증용 FO(Front Office) 연동 API
================================================================================
- "새 제품 개발"이 아니라 이미 검증된 art_admission_service.py/art_admission_llm.py
  함수를 그대로 HTTP로 감싼 것뿐이다. 새 비즈니스 로직은 여기 없다.
- 노출 범위는 학교/전형 조회, 호환학교 매칭, 무충돌 6장 조합 자동 추천
  (/recommend-combo), 학생부 뒤집기 시뮬레이터(/simulate-reversal), RAG
  질의응답, 서류첨삭. 학생관리/PDF리포트/결제/관리자는 의도적으로
  아예 안 만들었다 - "Validation FO" 범위 밖.
- 서류첨삭(review-document/review-chat)에 한해 AI 모델을 고를 수 있다. 기본
  모델(gpt-4o-mini 등 gated=False)은 누구나 바로 쓸 수 있고, 고급 모델
  (gated=True)은 art_admission_llm.MODEL_PASSWORD와 일치하는 비밀번호를
  같이 보내야 실제로 그 모델이 쓰인다 - 비용이 큰 모델을 실수/장난으로 못
  고르게 막는 용도일 뿐 보안 목적은 아니다(art_admission_app.py Streamlit
  버전과 동일한 정책). 비밀번호가 없거나 틀리면 조용히 기본 모델로 대체하고
  이유(gate_note)를 응답에 실어 보낸다 - 에러로 막지 않는다.
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

from services.art_admission_service import ArtAdmissionService, get_shared_service  # noqa: E402
from services.art_admission_llm import (  # noqa: E402
    review_document, chat_about_review, get_available_models, MODEL_PASSWORD,
)

DEFAULT_MODEL = "gpt-4o-mini"  # 모델을 못 고르는 나머지 엔드포인트(질의응답 등)는 항상 이 모델


def _resolve_review_model(model_id: Optional[str], model_password: Optional[str]) -> tuple[str, Optional[str]]:
    """서류첨삭 전용 모델 선택 + 비밀번호 게이트. gated 모델인데 비밀번호가
    안 맞으면 에러로 막지 않고 조용히 기본 모델로 대체한 뒤, 화면에 보여줄
    사유(gate_note)를 같이 돌려준다 - art_admission_app.py(Streamlit)의
    "비밀번호 안 맞으면 그냥 기본값" 정책과 동일하게 맞춘다."""
    models = get_available_models()
    info = next((m for m in models if m["id"] == model_id), None)
    if info is None:
        return DEFAULT_MODEL, None
    if not info["available"]:
        return DEFAULT_MODEL, f"'{info['label']}'는 API 키가 설정되어 있지 않아 사용할 수 없습니다. 기본 모델로 답변합니다."
    if info["gated"] and model_password != MODEL_PASSWORD:
        return DEFAULT_MODEL, f"'{info['label']}'는 비밀번호가 필요합니다. 비밀번호가 없거나 일치하지 않아 기본 모델로 답변합니다."
    return info["id"], None

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
    # 2026-09-09: 요청마다 새 드라이버를 만들지 않고 프로세스 생애주기 동안 하나만
    # 만들어 재사용한다(입시 질문 응답 지연의 실제 원인 - 자세한 이유는
    # art_admission_service.get_shared_service() 주석 참고). 그래서 이 함수를
    # 호출하는 곳들은 더 이상 finally에서 svc.close()를 부르지 않는다 - 공유
    # 인스턴스를 매 요청마다 닫아버리면 다음 요청이 죽은 드라이버를 쓰게 된다.
    return get_shared_service()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universities")
def list_universities():
    """01 PROFILE / 02 MATCH 화면용 - 등록된 학교/학과 목록."""
    svc = get_service()
    return svc.list_universities()


@app.get("/universities/{university}")
def university_detail(university: str, campus: Optional[str] = None):
    svc = get_service()
    detail = svc.get_university_detail(university, campus=campus)
    if not detail:
        raise HTTPException(status_code=404, detail="해당 학교 데이터를 찾을 수 없습니다.")
    return detail


class PrepSearchRequest(BaseModel):
    topic_keywords: Optional[List[str]] = None
    material_query: str = ""
    document_only: bool = False
    holistic_only: bool = False
    academic_record_only: bool = False


@app.get("/prep-topics")
def prep_topics():
    """"큰 주제" 선택지 - FO의 실기종목 선택 UI에 그대로 넣을 값."""
    svc = get_service()
    return svc.list_exam_topic_keywords()


@app.get("/stats")
def stats():
    """홈 화면 통계용 - 고유 대학 수와 전형(트랙) 수를 분리해서 반환한다.
    캠퍼스가 여러 개인 대학(홍익대 등)을 두 번 세지 않도록 university 집합은
    이름으로만 dedup한다. 새 비즈니스 로직 없음 - list_all_tracks_full() 결과를
    그냥 집계만 한다."""
    svc = get_service()
    tracks = svc.list_all_tracks_full()
    universities = {t["university"] for t in tracks}
    years = sorted({t.get("admission_year") for t in tracks if t.get("admission_year")})
    return {
        "university_count": len(universities),
        "track_count": len(tracks),
        "admission_years": years,
    }


@app.get("/school-record-coverage")
def school_record_coverage():
    """grades.html 안내 문구용 - 정밀 계산 가능한 학교가 몇 개교인지 실시간으로
    센다. 예전엔 특정 5개교를 문구에 직접 적어뒀는데 19개교로 늘어난 뒤에도
    문구가 갱신되지 않았던 사고가 있었다(사용자 실측 제보) - 화면이 매번
    실제 데이터를 세어 스스로 최신 상태를 반영하게 한다."""
    svc = get_service()
    return svc.get_school_record_coverage()


class CompareRequest(BaseModel):
    selections: List[dict]  # [{"university": ..., "department": ...}, ...]


@app.post("/compare-tracks")
def compare_tracks_endpoint(req: CompareRequest):
    """대학 찾기 결과에서 2~6개 전형을 선택했을 때 나란히 비교표를 만든다.
    기존 Streamlit '전형 비교' 탭이 쓰던 get_comparison_table() 그대로 재사용."""
    svc = get_service()
    return svc.get_comparison_table(req.selections)


@app.post("/simulate-multi-apply")
def simulate_multi_apply_endpoint(req: CompareRequest):
    """선택한 조합 안에서만 일정(실기고사일) 충돌을 검사한다. 기존 '동시지원
    시뮬레이터' 탭이 쓰던 simulate_multi_apply() 그대로 재사용 - 새 로직 없음."""
    svc = get_service()
    return svc.simulate_multi_apply(req.selections)


@app.get("/calendar-events")
def calendar_events_endpoint():
    """전체 전형의 원서접수/실기고사/발표/등록 일정. FO에서 선택된 학교만
    클라이언트 쪽에서 골라 타임라인으로 그린다. 기존 '일정 캘린더' 탭이 쓰던
    get_calendar_events() 그대로 재사용."""
    svc = get_service()
    return svc.get_calendar_events()


@app.get("/past-topics")
def past_topics_endpoint(university: Optional[str] = None):
    """Evidence Drawer에서 기출문제가 있으면 같이 보여주기 위한 조회.
    기존 '기출문제' 탭이 쓰던 get_past_topics() 그대로 재사용."""
    svc = get_service()
    return svc.get_past_topics(university=university)


@app.post("/prep-search")
def prep_search(req: PrepSearchRequest):
    """03 RESULT 화면 - 학생이 선택한 실기종목/재료로 호환 학교 찾기.
    기존 "준비한 실기로 학교 찾기" 탭과 동일 로직, 새 비즈니스 로직 없음."""
    svc = get_service()
    return svc.search_tracks_by_prep(
        topic_keywords=req.topic_keywords, material_query=req.material_query,
        document_only=req.document_only, holistic_only=req.holistic_only,
        academic_record_only=req.academic_record_only,
    )


class SchoolRecordRequest(BaseModel):
    university: str
    department: str
    grades: List[dict]  # [{"subject_group": "국어", "grade": 4, "credit": 4}, ...]
    campus: Optional[str] = None
    track_name: Optional[str] = None


@app.post("/calculate-school-record")
def calculate_school_record_endpoint(req: SchoolRecordRequest):
    """학생 성적 -> 특정 학교·학과 실제 학생부 반영 규정 그대로 환산.
    원문 반영교과/환산표를 확보한 학교(school_record_coverage 참고 - 학교 수는
    계속 늘어나므로 여기 특정 개수를 적지 않는다)만 정밀 계산이 가능하고,
    그 외 학교는 available=False로 명시한다."""
    svc = get_service()
    return svc.calculate_school_record_score(
        req.university, req.department, req.grades, campus=req.campus, track_name=req.track_name,
    )


class RecommendUniversitiesRequest(BaseModel):
    grades: List[dict]
    topic_keywords: Optional[List[str]] = None
    material_query: str = ""


@app.post("/recommend-universities")
def recommend_universities_endpoint(req: RecommendUniversitiesRequest):
    """성적 기반 대학/학과 추천. calc_precision은 3가지: 정밀 계산 가능한 학교는
    "exact", 반영교과는 확인됐지만 세부 공식이 아직 없는 학교는 "approximate",
    실기 100%나 학생부종합 정성평가라 애초에 학생부 등급 환산 자체가 없는 전형은
    "not_applicable"(school_record_percentage=None) - FO는 반드시 이 3가지를
    다르게 표시해야 하며, not_applicable은 점수 없이 사유(reason_summary)만
    보여줘야 한다(근사치조차 매기면 안 됨 - 실제로 반영되지 않는 성적을
    반영되는 것처럼 보여주는 셈이라 오해를 부른다)."""
    svc = get_service()
    return svc.recommend_universities(
        req.grades, topic_keywords=req.topic_keywords, material_query=req.material_query,
    )


class RecommendComboRequest(BaseModel):
    grades: List[dict]
    topic_keywords: Optional[List[str]] = None
    material_query: str = ""
    max_count: int = 6


@app.post("/recommend-combo")
def recommend_combo_endpoint(req: RecommendComboRequest):
    """수시 최대 지원 장수(기본 6) 안에서 실기고사 날짜가 겹치지 않는 조합을
    자동으로 골라준다. recommend_universities()의 적합도 순서를 그대로 신뢰해
    그리디로 채우고, 충돌로 건너뛴 후보도 함께 보여준다(왜 빠졌는지 투명하게)."""
    svc = get_service()
    return svc.recommend_conflict_free_combo(
        req.grades, topic_keywords=req.topic_keywords, material_query=req.material_query,
        max_count=req.max_count,
    )


@app.post("/simulate-reversal")
def simulate_reversal_endpoint(req: SchoolRecordRequest):
    """"학생부가 약해도 실기 비중이 크면 뒤집을 수 있는가"를 반영비율 공식만으로
    계산한다. 실제 합격선은 공개되지 않으므로 추정하지 않고, 실기 0점~만점일 때
    총점이 움직이는 산술적 범위(하한/상한)만 정직하게 보여준다."""
    svc = get_service()
    return svc.simulate_practical_reversal(
        req.university, req.department, req.grades, campus=req.campus, track_name=req.track_name,
    )


class QARequest(BaseModel):
    query: str


@app.post("/qa")
def qa(req: QARequest):
    """04 EVIDENCE 화면 - 기존 질의응답 탭의 AI 답변 파이프라인 그대로.
    항상 gpt-4o-mini만 쓴다(공개 API에서 프리미엄 모델 비용 노출 방지)."""
    from services.art_admission_agent import run_qa_pipeline
    svc = get_service()
    return run_qa_pipeline(svc, req.query, model_id=DEFAULT_MODEL)


class AgentChatRequest(BaseModel):
    query: str
    history: List[dict] = []


@app.post("/agent-chat")
def agent_chat_endpoint(req: AgentChatRequest):
    """day54 질의 라우팅 + day50~56 LangGraph 에이전트. 의도가 명확한 단순 질의
    (대학 하나 전체 조회, 실기종목 검색)는 기존 /qa 파이프라인으로 즉시 처리하고,
    비교·일정충돌처럼 도구 여러 개를 순서대로 조합해야 하는 복합 질의만 에이전트로
    넘긴다 - 모든 질문을 에이전트 도구선택에 맡기지 않는다(day54 Adaptive RAG)."""
    from services.art_admission_agent import route_and_answer
    try:
        return route_and_answer(req.query, req.history)
    except Exception as e:
        return {
            "answer": f"⚠️ 에이전트 답변 생성 실패: {e}",
            "model": "gpt-4o-mini",
            "tool_trace": [],
            "error": True,
        }


@app.get("/review-models")
def review_models_endpoint():
    """서류첨삭 화면의 "AI 모델 선택" 드롭다운용 - id/label/gated/available만
    노출한다(실제 API 키는 절대 포함 안 됨). gated=True인 모델은 FO가 비밀번호
    입력창을 같이 보여줘야 한다."""
    return get_available_models()


class ReviewRequest(BaseModel):
    text: str
    doc_type: str = "자기소개서"
    university: Optional[str] = None
    model_id: str = DEFAULT_MODEL
    model_password: Optional[str] = None


@app.post("/review-document")
def review_document_endpoint(req: ReviewRequest):
    """서류첨삭 메뉴 그대로. 학교를 지정하면 해당 학교 서류 규정 원문을 근거로 반영."""
    svc = get_service()
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
    resolved_model, gate_note = _resolve_review_model(req.model_id, req.model_password)
    result = review_document(
        req.text, model_id=resolved_model, doc_type=req.doc_type,
        graph_hint=graph_hint, university=req.university, context_doc_rules=doc_rules,
    )
    if gate_note:
        result["gate_note"] = gate_note
    # rules_found는 LLM 판단이 아니라 실제로 발췌를 찾았는지(doc_rules 존재 여부) 그대로
    # 반영한 결정론적 값 - 화면이 이 값만 보고 안내 배너를 그리게 해서, LLM이 자체적으로
    # "규정을 확인/확인못함" 문구를 잘못 말해도 화면 표시와 어긋나지 않게 한다.
    return {**result, "doc_rules": doc_rules, "graph_hint": graph_hint, "rules_found": bool(doc_rules)}


class ReviewChatRequest(BaseModel):
    doc_text: str
    doc_type: str = "자기소개서"
    history: List[dict]
    model_id: str = DEFAULT_MODEL
    model_password: Optional[str] = None


@app.post("/review-chat")
def review_chat_endpoint(req: ReviewChatRequest):
    """첨삭 후 이어지는 대화. history는 최초 첨삭(assistant)부터 이후 주고받은
    턴을 [{'role': 'user'|'assistant', 'content': ...}] 그대로 담아 보낸다."""
    resolved_model, gate_note = _resolve_review_model(req.model_id, req.model_password)
    result = chat_about_review(req.doc_text, req.doc_type, req.history, model_id=resolved_model)
    if gate_note:
        result["gate_note"] = gate_note
    return result
