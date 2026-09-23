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
import traceback
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import threading  # noqa: E402

from services.art_admission_service import ArtAdmissionService, get_shared_service  # noqa: E402
from services.art_admission_llm import (  # noqa: E402
    review_document, chat_about_review, get_available_models, MODEL_PASSWORD, warm_up_reranker,
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


@app.on_event("startup")
def _warm_up_on_startup():
    # 2026-09-13: 배포 직후 서버가 막 재시작된 상태에서 실제 사용자가 던진 첫
    # /qa 질문이 크로스인코더 리랭커 모델 로딩 비용(약 15초)을 그대로 떠안는
    # 문제가 실측으로 확인됐다("세종대학교 수시 제출서류는 어떻게 제출해야
    # 해?" 질문이 22초 걸림 - 1차 호출 17.5초 vs 같은 프로세스 2차 호출 3.2초).
    # 배포 스크립트가 재시작 직후 /health로 헬스체크하므로 여기서 동기로
    # 모델을 로딩하면 그 헬스체크가 늦어질 수 있어, 별도 스레드에서 백그라운드로
    # 미리 로딩해둔다 - 첫 실제 사용자 질문이 도착할 즈음엔 이미 준비돼 있다.
    threading.Thread(target=warm_up_reranker, daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universities")
def list_universities():
    """01 PROFILE / 02 MATCH 화면용 - 등록된 학교/학과 목록."""
    svc = get_service()
    return svc.list_universities()


@app.get("/tracks/by-department")
def tracks_by_department(q: str):
    """["대학찾기"/"대학지도" 학과 검색] 학과명 부분일치로 등록된 전형을 전부 찾는다."""
    svc = get_service()
    return svc.search_tracks_by_department(q)


@app.get("/tracks/by-tag")
def tracks_by_tag(tag: str):
    """[표준 계열 태그로 찾기] 대학지도(kg.html)의 태그 필터에서 "이 계열로 검색하기"를
    누르면 여기로 와서, 같은 태그의 학과 전형을 전부 모아 보여준다."""
    svc = get_service()
    return svc.search_tracks_by_tag(tag)


@app.get("/department-curriculum")
def department_curriculum(university: str, department: str, campus: Optional[str] = None):
    """[교육과정 원문 보기] 학과 소개 + 실제 반영 교과목 목록. 아직 수집 안 된
    학과는 빈 값(200)으로 응답한다 - 데이터가 없다는 것도 유효한 답이라 404로
    취급하지 않는다."""
    svc = get_service()
    return svc.get_department_curriculum(university, department, campus=campus)


@app.get("/similar-departments")
def similar_departments(university: str, department: str, campus: Optional[str] = None, top_k: int = 5):
    """["학과명으로 찾기" 결과 보강] 찾은 학과와 같은 표준 계열 태그 안에서만 임베딩
    유사도 top-K를 반환한다. 태그나 임베딩이 아직 없는 학과는 빈 목록을 반환한다
    (에러가 아니라 "아직 비교 데이터가 없다"는 정상 상태)."""
    svc = get_service()
    return svc.find_similar_departments(university, department, campus=campus, top_k=top_k)


class SimilarDepartmentsBatchRequest(BaseModel):
    items: List[dict]  # [{"university": ..., "department": ..., "campus": ...}, ...]
    top_k: int = 5


@app.post("/similar-departments/batch")
def similar_departments_batch(req: SimilarDepartmentsBatchRequest):
    """2026-09-18: results.html이 유니크 학과 개수만큼(최대 200개 이상) /similar-departments를
    동시에(Promise.all) 호출하는 바람에, 서버(nginx, HTTP/1.1)의 호스트당 동시연결 6개
    제한에 걸려 같은 화면의 다른 요청(/prep-topics 등)까지 순서가 밀리며 체감 속도가
    느려지는 문제를 실측으로 확인했다. 요청 개수를 1개로 합쳐 이 병목을 없앤다.
    응답 키는 "대학::캠퍼스::학과" 형식(campus 없으면 빈 문자열)."""
    svc = get_service()
    return svc.find_similar_departments_batch(req.items, top_k=req.top_k)


@app.get("/universities/{university}")
def university_detail(university: str, campus: Optional[str] = None):
    svc = get_service()
    detail = svc.get_university_detail(university, campus=campus)
    # 2026-09-23 GPT QC 재검수로 발견: get_university_detail()은 학교를 못 찾아도
    # 항상 {"official_tracks": [], "estimates_by_track": [], "region":..., "college_type":...}
    # 형태의 비어있지 않은 dict를 반환한다 - "if not detail"은 dict 자체가 키를 갖고
    # 있어 항상 False라 이 404 분기가 한 번도 실행될 수 없었다(존재하지 않는
    # 학교명을 조회해도 HTTP 200 + 빈 목록이 나감). 실제로 데이터가 있는지는
    # official_tracks가 채워졌는지로 판정해야 한다.
    if not detail.get("official_tracks"):
        raise HTTPException(status_code=404, detail="해당 학교 데이터를 찾을 수 없습니다.")
    return detail


@app.get("/kg-graph")
def kg_graph(university: Optional[str] = None):
    """[④ 인터랙티브 KG 뷰어] 대학-학과-전형 구조를 vis.js용 {nodes, edges}로 반환.
    학생 성적까지 반영하려면 /kg-graph/scored(POST)를 쓴다."""
    svc = get_service()
    return svc.get_kg_graph(university=university)


class KgGraphRequest(BaseModel):
    university: Optional[str] = None
    topic_keyword: Optional[str] = None
    track_type: Optional[str] = None
    admission_type: Optional[str] = None
    grades: Optional[List[dict]] = None


@app.post("/kg-graph/scored")
def kg_graph_scored(req: KgGraphRequest):
    """[④ KG 뷰어] university 지정 시 학교별 보기, topic_keyword 지정 시 실기종목별
    보기(예: "소묘"), track_type 지정 시 전형종류별 보기(예: "학교장추천"),
    admission_type 지정 시 전형 유형별 보기(예: "학생부교과전형"). grades를 같이
    보내면 전형 노드에 학생부 환산 결과를 툴팁으로 얹는다 - 계산은 기존
    recommend_universities()를 그대로 재사용한다."""
    svc = get_service()
    if req.track_type:
        return svc.get_kg_graph_by_track_type(req.track_type, grades=req.grades)
    if req.topic_keyword:
        return svc.get_kg_graph_by_topic(req.topic_keyword, grades=req.grades)
    if req.admission_type:
        return svc.get_kg_graph_by_admission_type(req.admission_type, grades=req.grades)
    return svc.get_kg_graph(university=req.university, grades=req.grades)


@app.get("/kg-topics")
def kg_topics():
    """[④ KG 뷰어] "실기종목별 보기" 드롭다운용 - 서술형 문구를 걸러낸 명사형 과목명만."""
    svc = get_service()
    return svc.list_kg_topic_keywords()


@app.get("/kg-track-types")
def kg_track_types():
    """[④ KG 뷰어] "전형종류별 보기" 드롭다운용 - 지금 데이터에 실제 존재하는 특별전형 종류만."""
    svc = get_service()
    return svc.list_track_type_categories()


@app.get("/kg-admission-types")
def kg_admission_types():
    """[④ KG 뷰어] "전형 유형별 보기" 드롭다운용 - 실기/실적위주·서류·학생부종합·학생부교과."""
    svc = get_service()
    return svc.list_admission_type_categories()


@app.get("/entity-graph")
def entity_graph(min_weight: int = 2):
    """[④ KG 뷰어 - 2층 비정형 의미망] 2026-09-18: 이 그래프(LLM이 원문에서 뽑은
    개체+동시출현+커뮤니티)는 이미 계산까지 다 돼 있었는데 FO로 나가는 API가
    없었다(사용자 발견 - Streamlit 내부 QC 도구에만 있었음). 그 문을 연다."""
    svc = get_service()
    return svc.get_kg_entity_graph(min_weight=min_weight)


@app.get("/kg-graph/combined")
def kg_graph_combined(university: str, min_weight: int = 2):
    """[④ KG 뷰어 - 1층(공식 팩트)+2층(비정형 의미망) 연계 보기] 대학 하나로 범위를
    좁혀서 두 계층을 한 화면에 그린다. 둘을 잇는 실제 그래프 관계는 DB에 없으므로
    (실측 확인 - Department-Entity 직접 관계 0건), 이름이 일치하는 학과/대학만
    점선으로 이어서 "1층에서 말하는 이 학과가 원문에서는 어떻게 언급되는지"를
    보여준다."""
    svc = get_service()
    return svc.get_combined_kg_graph(university, min_weight=min_weight)


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


@app.get("/department-tags")
def department_tags():
    """[표준 계열 태그 목록] profile.html "계열로 찾기"/kg.html 태그 필터가 공유하는
    10개 카테고리 - 한 곳(list_standard_department_tags)에서만 관리해 화면마다
    다른 목록이 나오지 않게 한다."""
    svc = get_service()
    return svc.list_standard_department_tags()


# 2026-09-24 [공통코드 관리 화면 1단계 - department_tag]: 배포 없이 태그를
# 추가/변경할 수 있게 Neo4j(:CommonCode)로 옮기고 관리 화면(admin-common-codes.html)을
# 붙인다. 학생 대상 공개 API가 전부인 이 서비스에 정식 로그인 체계가 없으므로,
# review 모델 선택의 MODEL_PASSWORD와 동일한 패턴(간단한 공유 비밀번호)으로
# 쓰기 3종(POST/PUT/DELETE)만 막는다 - 실수/장난으로 못 건드리게 하는 용도이지
# 강한 보안 목적은 아니다.
_COMMON_CODE_ADMIN_PASSWORD = "20260924"


def _require_common_code_admin(password: Optional[str]):
    if password != _COMMON_CODE_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="관리자 비밀번호가 올바르지 않습니다.")


@app.get("/common-codes")
def list_common_codes_endpoint(category: str):
    svc = get_service()
    return svc.list_common_codes(category)


class CommonCodeCreateRequest(BaseModel):
    category: str
    code: str
    label: str
    sort_order: Optional[int] = None
    admin_password: str


@app.post("/common-codes")
def create_common_code_endpoint(req: CommonCodeCreateRequest):
    _require_common_code_admin(req.admin_password)
    svc = get_service()
    try:
        return svc.create_common_code(req.category, req.code, req.label, sort_order=req.sort_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class CommonCodeUpdateRequest(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    admin_password: str


@app.put("/common-codes/{category}/{code}")
def update_common_code_endpoint(category: str, code: str, req: CommonCodeUpdateRequest):
    _require_common_code_admin(req.admin_password)
    svc = get_service()
    try:
        return svc.update_common_code(category, code, label=req.label, sort_order=req.sort_order, active=req.active)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/common-codes/{category}/{code}")
def delete_common_code_endpoint(category: str, code: str, admin_password: str):
    _require_common_code_admin(admin_password)
    svc = get_service()
    try:
        svc.delete_common_code(category, code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}


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
    # 2026-09-14: 나이스 html 업로드에서 인식한 출결/봉사시간 - 지금은 중앙대(출결)
    # 처럼 원문 감점표를 school_record_rule에 넣어둔 학교에만 실제로 반영된다
    # (rule에 attendance_bands/service_bands가 없는 대다수 학교는 그냥 무시됨).
    unexcused_absence_days: Optional[int] = None
    service_hours: Optional[float] = None


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
        unexcused_absence_days=req.unexcused_absence_days, service_hours=req.service_hours,
    )


class RecommendComboRequest(BaseModel):
    grades: List[dict]
    topic_keywords: Optional[List[str]] = None
    material_query: str = ""
    max_count: int = 6
    unexcused_absence_days: Optional[int] = None
    service_hours: Optional[float] = None


@app.post("/recommend-combo")
def recommend_combo_endpoint(req: RecommendComboRequest):
    """수시 최대 지원 장수(기본 6) 안에서 실기고사 날짜가 겹치지 않는 조합을
    자동으로 골라준다. recommend_universities()의 적합도 순서를 그대로 신뢰해
    그리디로 채우고, 충돌로 건너뛴 후보도 함께 보여준다(왜 빠졌는지 투명하게)."""
    svc = get_service()
    return svc.recommend_conflict_free_combo(
        req.grades, topic_keywords=req.topic_keywords, material_query=req.material_query,
        max_count=req.max_count,
        unexcused_absence_days=req.unexcused_absence_days, service_hours=req.service_hours,
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
    session_id: Optional[str] = None


# 2026-09-16: LLM 호출 예외(레이트리밋/지출한도/네트워크 오류 등)의 원문 메시지를
# 그대로 사용자에게 보여주면 "project_spend_limit_exceeded"처럼 내부 결제 상태나
# 심지어 OpenAI 대시보드 URL까지 그대로 노출된다(실측 발견 - 사용자 화면에 결제
# 한도 초과 메시지가 그대로 떴음). 원인이 뭐든 사용자에게는 서비스 운영 사정으로만
# 안내하고, 실제 원인은 서버 로그에만 남긴다.
# 2026-09-23 실장애 후속: "AI 서비스 고도화 작업이 진행 중"이라는 문구가 실제로는
# 순수 파이썬 버그(UnboundLocalError)였던 경우에도 그대로 나갔다 - "일부러 멈춘
# 기능"처럼 읽혀 원인 파악을 오히려 늦췄다(로그에도 traceback 없이 str(e) 한 줄뿐).
# 문구를 원인을 특정하지 않는 표현으로 바꾸고, 서버 로그에는 항상 전체 traceback과
# 요청 쿼리를 남긴다.
_LLM_FRIENDLY_ERROR = "일시적인 오류로 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."


@app.post("/qa")
def qa(req: QARequest):
    """04 EVIDENCE 화면 - 기존 질의응답 탭의 AI 답변 파이프라인 그대로.
    항상 gpt-4o-mini만 쓴다(공개 API에서 프리미엄 모델 비용 노출 방지)."""
    from services.art_admission_agent import run_qa_pipeline
    from services.art_admission_gap_log import log_turn
    svc = get_service()
    try:
        result = run_qa_pipeline(svc, req.query, model_id=DEFAULT_MODEL)
        log_turn(req.query, "/qa", result, session_id=req.session_id)
        return result
    except Exception:
        # 원인은 서버 로그에만 남긴다 - str(e) 한 줄이 아니라 전체 traceback +
        # 요청 쿼리를 남겨야 다음 장애 때 원인을 바로 찾을 수 있다(2026-09-23 실장애:
        # UnboundLocalError가 str(e)로는 "local variable... referenced before
        # assignment"만 보이고 어느 줄인지 안 나와 원인 특정이 늦어졌다).
        print(f"[/qa] 처리 실패 query={req.query!r}\n{traceback.format_exc()}")
        return {
            "answer": _LLM_FRIENDLY_ERROR,
            "model": DEFAULT_MODEL,
            "context_tracks": [],
            "grounded_tracks": [],
            "error": True,
        }


class AgentChatRequest(BaseModel):
    query: str
    history: List[dict] = []
    session_id: Optional[str] = None


@app.post("/agent-chat")
def agent_chat_endpoint(req: AgentChatRequest):
    """day54 질의 라우팅 + day50~56 LangGraph 에이전트. 의도가 명확한 단순 질의
    (대학 하나 전체 조회, 실기종목 검색)는 기존 /qa 파이프라인으로 즉시 처리하고,
    비교·일정충돌처럼 도구 여러 개를 순서대로 조합해야 하는 복합 질의만 에이전트로
    넘긴다 - 모든 질문을 에이전트 도구선택에 맡기지 않는다(day54 Adaptive RAG)."""
    from services.art_admission_agent import route_and_answer
    from services.art_admission_gap_log import log_turn
    try:
        result = route_and_answer(req.query, req.history)
        log_turn(req.query, "/agent-chat", result, session_id=req.session_id)
        return result
    except Exception:
        # 원인은 서버 로그에만 남긴다(위 /qa와 동일한 이유 - 전체 traceback + 쿼리).
        print(f"[/agent-chat] 처리 실패 query={req.query!r}\n{traceback.format_exc()}")
        return {
            "answer": _LLM_FRIENDLY_ERROR,
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


@app.get("/universities-by-doc-type")
def universities_by_doc_type(doc_type: str):
    """[서류첨삭 학교 선택 필터] 2026-09-18: "문서종류에 맞는 지원학교만 선택
    가능하게" 요청 반영 - 실제 원문에 그 서류명이 등장하는 학교만 골라준다.
    응답이 {"filtered": false}면 그 문서 종류는 필터링 근거가 없다는 뜻이므로
    (예: "기타 서류") FO는 전체 학교 목록을 그대로 보여줘야 한다."""
    svc = get_service()
    universities = svc.list_universities_with_document_type(doc_type)
    if universities is None:
        return {"filtered": False, "universities": []}
    return {"filtered": True, "universities": universities}


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
    # 2026-09-21: [팩트 기반 검증] fact_checks는 LLM 의견이 아니라 코드가 직접
    # 계산/스캔한 결과다(글자 수 len() 비교, 개인식별정보 정규식 스캔) - LLM이
    # 이 값을 지어내거나 뒤집을 수 없고, 화면도 이 값을 AI 답변 문구로 대체하면
    # 안 된다. doc_rules가 비어 있으면 애초에 검사 근거가 없으므로 checks도 비게
    # 된다(거짓으로 통과 처리하지 않음).
    fact_checks = svc.run_document_fact_checks(req.text, doc_rules)
    # rules_found는 LLM 판단이 아니라 실제로 발췌를 찾았는지(doc_rules 존재 여부) 그대로
    # 반영한 결정론적 값 - 화면이 이 값만 보고 안내 배너를 그리게 해서, LLM이 자체적으로
    # "규정을 확인/확인못함" 문구를 잘못 말해도 화면 표시와 어긋나지 않게 한다.
    return {
        **result, "doc_rules": doc_rules, "graph_hint": graph_hint,
        "rules_found": bool(doc_rules), "fact_checks": fact_checks,
    }


class ReviewChatRequest(BaseModel):
    doc_text: str
    doc_type: str = "자기소개서"
    university: Optional[str] = None
    history: List[dict]
    model_id: str = DEFAULT_MODEL
    model_password: Optional[str] = None


@app.post("/review-chat")
def review_chat_endpoint(req: ReviewChatRequest):
    """첨삭 후 이어지는 대화. history는 최초 첨삭(assistant)부터 이후 주고받은
    턴을 [{'role': 'user'|'assistant', 'content': ...}] 그대로 담아 보낸다.
    university가 있으면 최초 첨삭(review-document)과 동일한 학교 규정 발췌를
    다시 조회해서 넣어준다 - 안 그러면 이어지는 대화에서 모델이 "규정을 확인할
    수 없다"고 답해 최초 첨삭과 모순된다(2026-09-21 발견)."""
    svc = get_service()
    doc_rules = []
    if req.university:
        try:
            doc_rules = svc.get_document_rule_excerpts(req.university, req.doc_type)
        except Exception:
            pass
    resolved_model, gate_note = _resolve_review_model(req.model_id, req.model_password)
    result = chat_about_review(
        req.doc_text, req.doc_type, req.history, model_id=resolved_model,
        university=req.university, context_doc_rules=doc_rules,
    )
    if gate_note:
        result["gate_note"] = gate_note
    # 2026-09-23 GPT QC 발견: /review-document는 fact_checks(PII 블라인드 검사 포함)를
    # 돌리는데 /review-chat은 아예 빠져 있어서, 대화가 이어지며 사용자가 "다시 써줘"로
    # 새 텍스트를 붙여도 이 엔드포인트에서는 검사 자체가 한 번도 안 됐다. 최초 첨삭과
    # 동일한 검사를 여기서도 돌린다 - 이어지는 대화 중 가장 최근 사용자 메시지(재작성
    # 요청에 새로 붙인 글일 가능성이 높음)와 원본 doc_text를 합쳐서 스캔한다.
    latest_user_text = next(
        (m.get("content", "") for m in reversed(req.history) if m.get("role") == "user"), ""
    )
    result["fact_checks"] = svc.run_document_fact_checks(
        f"{req.doc_text}\n{latest_user_text}", doc_rules,
    )
    return result


# 2026-09-23 [1:1 상담신청 게시판] 회원가입 없이 운영 - 글 작성 시 비밀번호를
# 직접 정하고, 열람 시 그 비밀번호를 입력하는 국내 표준 "1:1 문의" 게시판 패턴.
# 목록(/inquiries)은 본문 없이 제목/마스킹된 이름/날짜/답변상태만 준다.
class InquiryCreateRequest(BaseModel):
    name: str
    contact: str
    title: str
    question_content: str
    password: str
    session_id: Optional[str] = None


class InquiryViewRequest(BaseModel):
    password: str


@app.post("/inquiries")
def create_inquiry_endpoint(req: InquiryCreateRequest):
    from services.art_admission_inquiry import create_inquiry, InquiryConfigError
    if not req.name.strip() or not req.contact.strip() or not req.title.strip() or not req.question_content.strip():
        raise HTTPException(status_code=400, detail="이름/연락처/제목/문의내용은 비워둘 수 없습니다.")
    if not req.password or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="비밀번호는 4자 이상이어야 합니다.")
    try:
        return create_inquiry(
            req.name, req.contact, req.title, req.question_content,
            req.password, session_id=req.session_id,
        )
    except InquiryConfigError:
        raise HTTPException(status_code=503, detail="상담신청 기능이 아직 설정되지 않았습니다.")
    except Exception:
        raise HTTPException(status_code=502, detail="문의 접수에 실패했습니다. 잠시 후 다시 시도하세요.")


@app.get("/inquiries")
def list_inquiries_endpoint():
    from services.art_admission_inquiry import list_inquiries_public, InquiryConfigError
    try:
        return list_inquiries_public()
    except InquiryConfigError:
        raise HTTPException(status_code=503, detail="상담신청 기능이 아직 설정되지 않았습니다.")
    except Exception:
        raise HTTPException(status_code=502, detail="목록을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")


@app.post("/inquiries/{inquiry_id}/view")
def view_inquiry_endpoint(inquiry_id: int, req: InquiryViewRequest):
    from services.art_admission_inquiry import view_inquiry, InquiryConfigError
    try:
        result = view_inquiry(inquiry_id, req.password)
    except InquiryConfigError:
        raise HTTPException(status_code=503, detail="상담신청 기능이 아직 설정되지 않았습니다.")
    except Exception:
        raise HTTPException(status_code=502, detail="조회에 실패했습니다. 잠시 후 다시 시도하세요.")
    if result is None:
        raise HTTPException(status_code=403, detail="비밀번호가 일치하지 않습니다.")
    return result
