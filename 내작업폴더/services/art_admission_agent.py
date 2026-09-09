# -*- coding: utf-8 -*-
"""
🤖 [미술 실기 입시 도우미] LangGraph 에이전트 오케스트레이션 계층 (day50~56)
================================================================================
기존에는 "실기 검색"·"전형 비교"·"일정 충돌 확인"이 서로 다른 화면(profile.html→
results.html)과 서로 다른 REST 엔드포인트(/prep-search, /compare-tracks,
/simulate-multi-apply, /calendar-events)로 쪼개져 있었고, "언제 뭘 부를지"를
프론트 JS가 하드코딩된 순서로 호출했다(results.html의 Promise.all).

이 모듈은 그 4개 서비스 함수를 그대로 LangChain "tool"로 감싸고, 사용자의 자연어
질문 하나를 보고 어떤 도구를 어떤 순서로 부를지 LLM이 스스로 판단하게 한다.
새 비즈니스 로직이 아니라 - 기존 함수 재사용 + 조립 방식만 바뀐 것이다.

절대 원칙(§1)은 여기서도 동일하게 지킨다: 도구가 반환한 그래프 사실 밖의 숫자/학교/
날짜를 에이전트가 지어내지 못하게 시스템 프롬프트에 못박고, art_admission_llm의
Self-RAG 자기검증(그라운딩 체크)·코드 레벨 가드레일을 최종 답변에도 그대로 적용한다.
================================================================================
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from services.art_admission_llm import _strip_banned_phrases, _self_check_grounding, answer_with_llm

AGENT_MODEL = "gpt-4o-mini"  # 공개 API 원칙과 동일하게 항상 이 모델만 쓴다.

# day54 Adaptive RAG(질의 라우팅) 개념: 모든 질문을 LLM 에이전트 도구선택에 맡기지
# 않는다. ART:READY의 실제 질문 유형은 몇 가지로 다 나열 가능하다(대학 하나 전체
# 조회 / 실기종목으로 검색 / 여러 전형 비교·일정충돌). 의도가 명확한 두 경우는
# 규칙으로 즉시 기존 /qa 파이프라인(build_llm_context+answer_with_llm, 그래프
# 쿼리 + LLM 호출 1번)으로 보내고, "비교/충돌/여러 학교 동시 언급"처럼 도구를
# 여러 개 순서대로 조합해야 하는 진짜 복합 질의만 LangGraph 에이전트로 넘긴다.
# 이렇게 하면 (1) 단순 질의에서 "LLM이 엉뚱한 도구를 고르는" 이번 세션의 버그
# 유형 자체가 구조적으로 안 생기고, (2) LLM 왕복 횟수가 줄어 더 빠르고 싸다.
_COMPOUND_SIGNAL_WORDS = ["비교", "겹치", "충돌", "동시", "같이 지원", "함께 지원", "캘린더", "일정표"]


def _is_compound_query(query: str, all_universities: List[str]) -> bool:
    if any(w in query for w in _COMPOUND_SIGNAL_WORDS):
        return True
    from services.art_admission_service import resolve_university_mentions_detailed
    detail = resolve_university_mentions_detailed(query, all_universities)
    return len(detail["universities"]) >= 2

_SYSTEM_PROMPT = """당신은 "미술 실기 입시 도우미"의 에이전트입니다. 학생·학원장·학부모의
질문 하나에 대해, 아래 도구들을 필요한 만큼 여러 번, 필요한 순서로 호출해서 답하십시오.

특정 대학 하나만 언급하고 실기종목/재료를 특정하지 않은 질문(예: "가천대 실기는 뭐야?")
이면 반드시 get_university_info를 먼저 쓰십시오. search_tracks는 실기종목·재료 키워드가
있어야만 결과가 나오는 도구라, 키워드 없이 부르면 항상 0건이 나옵니다 - 그 0건을
"데이터가 없다"고 오해하지 말고, 대학 전체를 물었다면 get_university_info를 쓰십시오.

도구가 반환한 JSON 안에 있는 사실(학교/학과/실기유형/재료/일정/충돌여부)만 사용하고,
그 안에 없는 학교·숫자·날짜는 절대 새로 만들어내지 마십시오. 도구 호출로 확인이 안 되면
"현재 적재된 공식 모집요강 데이터에서 확인하지 못했습니다. 최종 지원 전 해당 대학 입학처
공지를 확인하세요."라고 답하십시오.

재료(연필 등)만 겹치는 결과를 "실기종목 일치"나 "호환 전형"이라고 부르지 마십시오 -
match_status가 "exact"인 것만 그렇게 부르고, "partial"인 것은 "재료·규격만 겹치고
실기유형은 다릅니다"라고 명확히 구분하십시오.

여러 전형을 비교해야 하는 질문(예: "A랑 B 비교해줘", "일정 안 겹치는지 확인해줘")이면
동일한 학교를 두 번 찾지 말고 search_tracks는 한 번만 호출해 필요한 후보를 전부 확보한
뒤, compare_tracks와 check_schedule_conflicts를 순서대로 호출해 실기고사 충돌 여부까지
확인한 뒤 답하십시오. 일정 정보가 없으면 "일정 정보가 적재되지 않았습니다. 공식
모집요강을 재확인하세요."라고 명시하십시오.

실기고사일이 겹치면 정확히 "실기고사일이 겹칩니다. 동시 지원 가능 여부와 준비 일정을
확인하세요."라는 취지로만 안내하고, "한 곳만 지원해야 한다"거나 "동시에 지원할 수
없다"처럼 지원 가능 여부 자체를 당신이 단정하지 마십시오 - 그건 대학 입학처 규정을
직접 확인해야 아는 것입니다.

간결하고 친절한 한국어로 답하고, "RAG 검증됨"/"실측 검증" 같은 확정적 신뢰 문구는
쓰지 마십시오."""


def _get_service():
    from services.art_admission_service import ArtAdmissionService
    return ArtAdmissionService()


def _all_universities() -> List[str]:
    """Self-RAG 그라운딩 체크용 전체 대학 목록. 실패해도 그라운딩 체크가 그냥
    스킵되게(빈 리스트) 하고, 에이전트 답변 자체는 절대 막지 않는다."""
    svc = _get_service()
    try:
        return sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        return []
    finally:
        svc.close()


@tool
def get_university_info(university: str, campus: str = "") -> str:
    """특정 대학 하나에 대해 실기유형을 특정하지 않고 전반적으로 물을 때 쓴다
    (예: "가천대 실기는 뭐야?", "중앙대 전형 알려줘"). search_tracks는 실기종목/재료
    키워드가 있어야만 결과가 나오므로, 그런 키워드 없이 대학 하나만 언급된 질문에는
    이 도구를 써야 한다. 그 대학의 모든 학과·전형·실기유형을 전부 반환한다."""
    svc = _get_service()
    try:
        detail = svc.get_university_detail(university, campus=campus or None)
        tracks = [{
            "department": t.get("department"), "track_name": t.get("track_name"),
            "exam_type_name": t.get("exam_type_name"), "allowed_materials": t.get("allowed_materials"),
            "quota": t.get("quota"), "exam_dates": t.get("exam_dates"), "source_url": t.get("source_url"),
        } for t in detail.get("official_tracks", [])]
        return json.dumps({"university": university, "count": len(tracks), "tracks": tracks}, ensure_ascii=False)
    finally:
        svc.close()


@tool
def search_tracks(topic_keywords: List[str] = [], material_query: str = "", document_only: bool = False) -> str:
    """학생이 준비 중인 실기 종목(topic_keywords, 예: ["소묘"], ["기초디자인"])이나 재료
    (material_query, 예: "연필")로 지원 가능한 대학 전형을 찾는다. 결과의 match_status가
    "exact"면 실기유형 자체가 일치, "partial"이면 재료·규격만 겹침(실기유형은 다름),
    "document"면 서류전형이다. 서류전형만 보고 싶으면 document_only=true."""
    svc = _get_service()
    try:
        rows = svc.search_tracks_by_prep(
            topic_keywords=topic_keywords, material_query=material_query, document_only=document_only,
        )
        trimmed = [{
            "university": r["university"], "campus": r.get("campus"), "department": r["department"],
            "track_name": r.get("track_name"), "exam_type_name": r.get("exam_type_name"),
            "match_status": r["match_status"], "exact_match_reasons": r.get("exact_match_reasons"),
            "partial_match_reasons": r.get("partial_match_reasons"), "warnings": r.get("warnings"),
            "quota": r.get("quota"), "exam_dates": r.get("exam_dates"), "source_url": r.get("source_url"),
        } for r in rows[:20]]  # 토큰 절약: 최대 20건만 도구 응답에 담는다
        return json.dumps({"count": len(rows), "results": trimmed}, ensure_ascii=False)
    finally:
        svc.close()


@tool
def compare_tracks(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들(university, campus, department 조합 2~6개)을 나란히 비교하는 표를
    만든다. selections 예: [{"university":"가천대학교","campus":"글로벌(성남)","department":"시각디자인전공"}, ...]"""
    svc = _get_service()
    try:
        rows = svc.get_comparison_table(selections)
        return json.dumps({"count": len(rows), "tracks": rows}, ensure_ascii=False, default=str)
    finally:
        svc.close()


@tool
def check_schedule_conflicts(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들의 실기고사일이 서로 겹치는지 확인한다(수시 최대 6장 제한도 함께
    검사). selections 형식은 compare_tracks와 동일."""
    svc = _get_service()
    try:
        result = svc.simulate_multi_apply(selections)
        return json.dumps(result, ensure_ascii=False, default=str)
    finally:
        svc.close()


@tool
def get_calendar(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들의 원서접수·실기고사·합격발표 일정을 시간순으로 정리한다.
    selections 형식은 compare_tracks와 동일 (빈 리스트면 전체 일정)."""
    svc = _get_service()
    try:
        all_events = svc.get_calendar_events()
        if not selections:
            return json.dumps({"events": all_events[:30]}, ensure_ascii=False, default=str)
        labels = {f"{s['university']} {s['department']}" for s in selections}
        filtered = [e for e in all_events if e.get("school") in labels]
        return json.dumps({"events": filtered}, ensure_ascii=False, default=str)
    finally:
        svc.close()


TOOLS = [get_university_info, search_tracks, compare_tracks, check_schedule_conflicts, get_calendar]


def run_qa_pipeline(svc, query: str, model_id: str = AGENT_MODEL) -> Dict[str, Any]:
    """기존 /qa 엔드포인트와 완전히 같은 파이프라인(그래프 조회 + LLM 답변 생성 1회).
    도구를 여러 개 조합할 필요 없는 단순 질의(대학 하나 전체 조회, 실기종목 검색)에
    쓴다 - LLM이 "어떤 도구를 쓸지" 고민할 필요 자체가 없어서 더 빠르고 저렴하고,
    도구 선택 실수(이번 세션의 get_university_info 누락 버그류)가 원천적으로 안 생긴다."""
    context_tracks, context_estimates = svc.build_llm_context(query)
    try:
        context_raw = svc.hybrid_search(query, top_k=5)
    except Exception:
        context_raw = []
    anchor_names = [t["university"] for t in context_tracks]
    exclude_names = anchor_names + [t["department"] for t in context_tracks]
    try:
        context_graph_related = svc.get_graph_related_context(
            query, anchor_names=anchor_names, exclude_names=exclude_names, top_n=5,
        )
    except Exception:
        context_graph_related = []
    try:
        context_compatible = svc.get_compatible_tracks_for_query(query)
    except Exception:
        context_compatible = []
    try:
        all_universities = sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        all_universities = []

    result = answer_with_llm(
        context_tracks, context_estimates, query, model_id=model_id,
        context_raw_excerpts=context_raw, context_graph_related=context_graph_related,
        context_compatible_tracks=context_compatible, all_universities=all_universities,
    )
    result["context_tracks"] = context_tracks
    result["context_compatible_tracks"] = context_compatible
    result["context_graph_related"] = context_graph_related
    result["context_raw_excerpts"] = context_raw
    return result


def route_and_answer(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """day54 질의 라우팅 진입점. /agent-chat이 이 함수를 호출한다 - 단순 질의는
    기존 /qa 파이프라인으로, 복합 질의(비교·일정충돌·여러 학교 동시 언급)만
    LangGraph 에이전트로 보낸다."""
    svc = _get_service()
    try:
        all_universities = sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        all_universities = []
    finally:
        svc.close()

    if _is_compound_query(query, all_universities):
        return run_agent(query, history)

    svc = _get_service()
    try:
        result = run_qa_pipeline(svc, query)
    finally:
        svc.close()
    # 프론트(qa.html)의 트레이스 패널과 형식을 맞추되, "도구 선택 없이 즉시 처리했다"는
    # 걸 투명하게 보여준다 - 라우팅 자체도 숨기지 않는다.
    result["tool_trace"] = [{
        "tool": "qa_pipeline",
        "args": {"query": query},
        "result_preview": f"단순 질의로 판단 - 도구 선택 없이 그래프 조회 {len(result.get('context_tracks', []))}건으로 즉시 답변",
    }]
    return result


def run_agent(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """질문 하나를 에이전트에게 넘겨, 필요한 도구를 스스로 호출하게 하고 최종 답변과
    "실제로 어떤 도구를 어떤 인자로 불렀는지" 트레이스를 함께 반환한다. 트레이스는
    기존 qa.html의 "그래프 추적 패널"을 대체한다 - 이번엔 진짜 함수 호출 로그라서
    더 투명하다."""
    llm = ChatOpenAI(model=AGENT_MODEL, temperature=0)
    agent = create_react_agent(llm, TOOLS, prompt=_SYSTEM_PROMPT)

    messages = list(history or [])
    messages.append({"role": "user", "content": query})

    result = agent.invoke({"messages": messages})
    out_messages = result["messages"]

    tool_trace = []
    grounded_universities = set()
    for m in out_messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                tool_trace.append({"tool": tc["name"], "args": tc["args"]})
        if isinstance(m, ToolMessage):
            content = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
            # Self-RAG 그라운딩용: 이 도구 호출이 실제로 반환한 학교명을 전부 모아둔다
            # (트레이스 패널에 보여줄 미리보기는 300자로 자르지만, 그라운딩 판정은
            # 잘리지 않은 전체 내용으로 해야 한다 - 안 그러면 뒷부분에 있는 학교가
            # 누락돼서 정상 답변까지 "환각 의심"으로 오탐할 수 있다).
            try:
                parsed = json.loads(content)
                for row in parsed.get("results", []) or parsed.get("tracks", []) or []:
                    if isinstance(row, dict) and row.get("university"):
                        grounded_universities.add(row["university"])
                if parsed.get("university"):
                    grounded_universities.add(parsed["university"])
                for c in parsed.get("conflicts", []) or []:
                    pass  # 충돌 항목은 "대학 학과" 합쳐진 문자열이라 이름 추출은 생략
            except Exception:
                pass
            if tool_trace and "result_preview" not in tool_trace[-1]:
                tool_trace[-1]["result_preview"] = content[:300]

    final_answer = out_messages[-1].content if out_messages else ""
    if not isinstance(final_answer, str):
        final_answer = json.dumps(final_answer, ensure_ascii=False)

    # Self-RAG류 자기검증(day53~54): /qa와 동일한 원칙 - 답변에 등장하는 학교명이
    # 실제로 이번 도구 호출 결과 안에 있었는지 코드로 재검사한다.
    # 2026-09-09 오탐 수정: 사용자의 질문 원문(query)이나 이전 대화(history)에 이미
    # 등장한 학교명은 grounded로 취급한다 - "이 결과로 질문하기" 기능이 성적 추천의
    # 실제 계산 결과(허구가 아님)를 질문 앞에 붙여 보내는데, 에이전트가 그 학교명을
    # 그대로 답변에서 언급하면 "이번 도구 호출 결과에는 없다"는 이유로 오탐이 났다.
    all_universities = _all_universities()
    query_text = query + " " + " ".join(str(m.get("content", "")) for m in (history or []))
    for name in all_universities:
        if name in query_text:
            grounded_universities.add(name)
    grounding_issues = [
        f"'{name}'가 답변에 등장하지만 이번 도구 호출 결과에는 없었습니다(환각 의심)"
        for name in all_universities if name in final_answer and name not in grounded_universities
    ]

    # 에이전트 답변에도 동일한 코드 레벨 가드레일을 적용한다(§ 절대원칙 - 화면마다
    # 따로 지키는 게 아니라 답변 생성 공통 경로 전체에 걸쳐야 한다).
    final_answer, banned_hit = _strip_banned_phrases(final_answer)

    result_payload = {
        "answer": final_answer,
        "model": AGENT_MODEL,
        "tool_trace": tool_trace,
    }
    if grounding_issues or banned_hit:
        result_payload["self_check_warnings"] = grounding_issues + [f"금지 문구 제거됨: {p}" for p in banned_hit]
    return result_payload
