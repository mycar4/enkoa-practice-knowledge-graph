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
import os
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from neo4j import READ_ACCESS

from services.art_admission_llm import (
    _strip_banned_phrases, _self_check_grounding, _self_check_compat_claim, answer_with_llm,
)

AGENT_MODEL = "gpt-4o-mini"  # 공개 API 원칙과 동일하게 항상 이 모델만 쓴다.

# day54 Adaptive RAG(질의 라우팅) 개념: 모든 질문을 LLM 에이전트 도구선택에 맡기지
# 않는다. ART:READY의 실제 질문 유형은 몇 가지로 다 나열 가능하다(대학 하나 전체
# 조회 / 실기종목으로 검색 / 여러 전형 비교·일정충돌). 의도가 명확한 두 경우는
# 규칙으로 즉시 기존 /qa 파이프라인(build_llm_context+answer_with_llm, 그래프
# 쿼리 + LLM 호출 1번)으로 보내고, "비교/충돌/여러 학교 동시 언급"처럼 도구를
# 여러 개 순서대로 조합해야 하는 진짜 복합 질의만 LangGraph 에이전트로 넘긴다.
# 이렇게 하면 (1) 단순 질의에서 "LLM이 엉뚱한 도구를 고르는" 이번 세션의 버그
# 유형 자체가 구조적으로 안 생기고, (2) LLM 왕복 횟수가 줄어 더 빠르고 싸다.
_COMPOUND_SIGNAL_WORDS = [
    "비교", "겹치", "충돌", "동시", "같이 지원", "함께 지원", "캘린더", "일정표",
    # 2026-09-14: "내신 3등급에 기초디자인인데 어디 찔러야 해?" 같은 성적기반 추천
    # 질문이 단순 질의로 분류돼 run_qa_pipeline(도구 없음, RAG만)으로 가는 바람에
    # recommend_by_grades 도구를 아예 못 부르고 "신중히 지원하세요" 식 원론적 답변만
    # 나가던 문제(사용자 발견) - 이 신호어가 있으면 무조건 도구를 쓰는 run_agent로
    # 보내서 실제 계산 엔진을 태우게 한다.
    "등급", "내신", "찔러", "지원해야", "붙을", "합격 가능", "추천해",
    # 랭킹/집계 질문("경쟁률 제일 높은 학교는?")도 get_competition_rate_ranking
    # 도구가 있어야만 답할 수 있는데, 신호어가 없으면 qa_pipeline(도구 없음)으로
    # 새서 "확인하지 못했습니다"만 나온다(2026-09-14 사용자 테스트로 발견).
    "경쟁률", "제일", "가장 높은", "가장 낮은", "순위", "랭킹",
    # 2026-09-18: "중앙대 실기와 유사한 대학 찾아줘"가 단순 질의로 분류되면서
    # find_similar_departments 도구(임베딩 코사인 유사도 비교)를 아예 안 부르고
    # run_qa_pipeline(도구 없음, RAG만)으로 새는 문제(사용자 발견) - qa_pipeline은
    # 질문에서 인식된 학교(중앙대)의 원문 청크만 컨텍스트로 주기 때문에, 애초에
    # "비교할 다른 학교 데이터"가 컨텍스트에 없어서 "찾지 못했습니다"만 나온다.
    # 유사/비슷/닮은 학과·대학을 찾는 질문은 반드시 도구 경로로 보낸다.
    "유사", "비슷", "닮은", "같은 학과", "같은 계열",
    # 2026-09-22: "같은 실기로 지원 가능한 학교"류 질문은 find_compatible_exam_tracks
    # 도구가 있어야 정확히 답할 수 있는데, 이 신호어가 빠져 있으면(Jev 실패 시
    # 폴백되는 이 키워드 목록에) qa_pipeline으로 새서 get_compatible_tracks_for_query
    # 결과에 의존하게 된다 - 그 자체는 틀리지 않지만, 명시적으로 도구 경로를 태우는
    # 게 더 일관된 동작이라 방어적으로 추가한다.
    "실기", "호환",
    # 2026-09-21 day46 RAPTOR 도입: "전체 절차 요약해줘"/"총정리"/"한눈에" 같은
    # 개요성 질문은 summarize_admission_flow 도구가 있어야 답할 수 있는데,
    # 신호어가 없으면 도구 없는 run_qa_pipeline으로 새서 낱개 청크 몇 개만 붙여준
    # 파편적인 답이 나온다.
    "총정리", "한눈에", "전체 흐름", "전체 절차", "전체 개요", "요약해",
]


def _is_compound_query_keyword(query: str, all_universities: List[str]) -> bool:
    """원래 방식(신호어 목록) - Jev 실패 시 이 폴백으로 전환된다. 2026-09-14/18/21
    세 차례에 걸쳐 "이 표현이 목록에 없어서 도구 없는 경로로 샜다"는 실사용
    버그가 반복 발견됐다(성적추천/랭킹/유사학과/전체요약 각각 한 번씩) - 목록을
    무한히 늘리는 대신(대증요법) Jev로 근본 교체한다."""
    if any(w in query for w in _COMPOUND_SIGNAL_WORDS):
        return True
    from services.art_admission_service import resolve_university_mentions_detailed
    detail = resolve_university_mentions_detailed(query, all_universities)
    return len(detail["universities"]) >= 2


# 2026-09-22 day47 Jev 도입: 실측(6문항, 과거 버그 3건과 같은 카테고리의 새
# 표현으로 재구성) 결과 키워드 방식 2/6 -> Jev 6/6로 개선. "여러 대학 이름이
# 2개 이상 언급됨"은 판단이 아니라 명백한 사실이라 Jev를 거칠 필요가 없어
# 그대로 유지하고, "도구가 필요한 질문 유형인가"라는 애매한 판단만 Jev로 대체한다.
def _is_compound_query(query: str, all_universities: List[str]) -> bool:
    from services.art_admission_service import resolve_university_mentions_detailed
    detail = resolve_university_mentions_detailed(query, all_universities)
    if len(detail["universities"]) >= 2:
        return True
    try:
        from typesafe_sdk import Noul, TypeSafeClient
        import os
        client = TypeSafeClient(timeout=5.0)
        model = os.getenv("TYPESAFE_MODEL", "jev-1.13.0")
        resp = client.system_one(
            model=model, state=query,
            questions={
                "needs_tool": Noul(
                    instructions=(
                        "이 질문에 답하려면 다음 중 하나 이상의 '계산/비교/추천/랭킹/요약 "
                        "도구'가 필요한가요: 성적 기반 지원 추천, 여러 전형 비교나 일정 "
                        "충돌 확인, 경쟁률/순위 집계, 비슷한 학과 찾기, 전체 절차 요약. "
                        "특정 사실 하나만 묻는 단순 조회는 '아니오'입니다."
                    ),
                ),
            },
        )
        return resp.answers["needs_tool"].noul >= 0.5
    except Exception:
        return _is_compound_query_keyword(query, all_universities)

_SYSTEM_PROMPT = """당신은 "미술 실기 입시 도우미"의 에이전트입니다. 학생·학원장·학부모의
질문 하나에 대해, 아래 도구들을 필요한 만큼 여러 번, 필요한 순서로 호출해서 답하십시오.

특정 대학 하나만 언급하고 실기종목/재료를 특정하지 않은 질문(예: "가천대 실기는 뭐야?")
이면 반드시 get_university_info를 먼저 쓰십시오. search_tracks는 실기종목·재료 키워드가
있어야만 결과가 나오는 도구라, 키워드 없이 부르면 항상 0건이 나옵니다 - 그 0건을
"데이터가 없다"고 오해하지 말고, 대학 전체를 물었다면 get_university_info를 쓰십시오.

"OO대 실기랑 유사한/비슷한 학과(대학) 찾아줘"처럼 대학명만 있고 학과명이 없는 질문이면,
find_similar_departments의 department 인자를 절대 추측해서 만들어내지 마십시오 -
학과명 철자가 실제 DB와 한 글자라도 다르면 결과가 무조건 0건으로 나오고, 그걸 "유사한
곳이 없다"고 잘못 보고하게 됩니다(실측으로 발견한 버그). 먼저 get_university_info로 그
대학의 실제 학과명 목록을 확인한 뒤, 학과가 하나뿐이면 그 이름 그대로 find_similar_departments에
넣고, 여러 개면 "어느 학과 기준으로 비교할까요?"라고 되물으십시오.

"OO학과와 같은/호환되는 실기로 지원 가능한 학교"처럼 질문에 "실기"/"호환"이라는 말이
있으면 find_compatible_exam_tracks를 쓰십시오 - find_similar_departments는 커리큘럼
(수업 내용) 유사도만 비교할 뿐 실기 종목이 같다는 보장이 전혀 없습니다. 반대로 "성격이
비슷한 학과"/"계열이 비슷"처럼 학과 자체의 성격을 묻는 질문엔 find_similar_departments를
쓰십시오. 두 도구를 헷갈려서 엉뚱한 기준으로 답하면 안 됩니다.

반입금지 물품, 입실/고사 시작 시각, 특별 유의사항처럼 구조화 도구 어디에도 없는 세세한
원문 디테일을 물으면 search_document_details를 쓰십시오(university를 알면 반드시 채울 것).

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

check_schedule_conflicts는 "내가 실제 지원하려는 조합(최대 6장)이 서로 안 겹치는지"를
검증하는 도구입니다 - selections를 대학별로 나눠서 여러 번 호출하면 같은 대학 안의
충돌만 보이고 대학 사이의 충돌은 절대 확인되지 않습니다. "OO대학교와 OO대학교 사이에
날짜가 겹치는지"처럼 사용자가 지원하려는 특정 조합이 아니라 여러 학교를 그냥 통째로
비교하는 질문이면, check_schedule_conflicts는 아예 시도하지 말고 처음부터
text2cypher_query로 두 대학의 모든 실기고사일을 한 번에 대조하는 쿼리를 쓰십시오
(실측 발견: "중앙대랑 홍익대 실기고사일이 겹치는지"를 물었을 때 check_schedule_conflicts를
먼저 시도했다가 - 대학당 전형이 6개를 넘어 "over_limit" 오류가 나거나 대학별로
나눠 호출해서 두 대학 사이의 겹침을 놓치는 등 - 여러 번 실패하고 나서야 text2cypher로
돌아섰고, 그 과정에서 self-check 재시도가 소진돼 결국 "확인할 수 없습니다"로
포기하는 사고가 있었습니다. 이런 "여러 학교 비교" 질문에는 처음부터 text2cypher만
쓰면 이 시행착오 자체가 생기지 않습니다).

학생이 자기 내신 등급(또는 성취도)을 말하며 "어디 찔러야 해", "무슨 전형이 유리해",
"합격 가능성", "추천해줘"처럼 실제 지원 대상을 물으면 반드시 recommend_by_grades를
쓰십시오. 이건 이 서비스의 "성적 추천" 화면과 완전히 같은 계산 엔진이라, 실제 계산
없이 "실기 비중과 내신을 종합적으로 고려해 신중히 지원하십시오" 같은 원론적 조언만
하고 끝내는 것은 이 질문 유형에서는 오답입니다. 실기 종목을 같이 말했으면
topic_keywords/material_query에 채워 넣고, **실기 종목을 아직 안 말했어도 등급만으로
먼저 도구를 호출**하십시오(topic_keywords/material_query를 비워서 호출 - 전체
실기유형 대상 후보를 보여준 뒤 "실기 종목을 알려주시면 더 좁혀드릴게요"라고
덧붙이는 게, 아무것도 안 보여주고 실기 종목부터 되묻는 것보다 낫습니다 - 실측으로
확인된 문제: 등급만 준 질문에 도구를 아예 안 부르고 원론적 되묻기만 하던 버그).
학생이 등급을 말하지 않은 과목은 grades 배열에 넣지 말고, 말한 과목만으로 도구를
호출하십시오(모르는 과목 등급을 지어내지 않음).

실기고사일이 겹치면 정확히 "실기고사일이 겹칩니다. 동시 지원 가능 여부와 준비 일정을
확인하세요."라는 취지로만 안내하고, "한 곳만 지원해야 한다"거나 "동시에 지원할 수
없다"처럼 지원 가능 여부 자체를 당신이 단정하지 마십시오 - 그건 대학 입학처 규정을
직접 확인해야 아는 것입니다.

간결하고 친절한 한국어로 답하고, "RAG 검증됨"/"실측 검증" 같은 확정적 신뢰 문구는
쓰지 마십시오.

같은 대학 안에 같은 전형명(예: "미술우수자전형")이 서로 다른 단과대학/학부에 각각
따로 존재해서 모집인원·실기고사일이 다를 수 있습니다(실측 발견: 홍익대학교에
"미술대학"의 미술우수자전형과 "조형대학"의 미술우수자전형이 따로 있고 날짜가
다름 - 같은 대학에 대해 연속으로 물었는데 답변마다 다른 날짜가 나왔던 사고의
원인). 전형명만으로 날짜/인원을 답하지 말고, 반드시 어느 단과대학·학과의 전형인지
함께 명시하십시오. 여러 단과대학에 같은 이름의 전형이 있으면 전부 나열하고,
사용자가 특정하지 않았으면 "어느 학과 기준으로 답변드릴까요?"라고 되물으십시오.

"실기 날짜/실기고사일"을 물으면 도구가 반환한 exam_dates를 곧바로 실기 날짜로
단정하지 마십시오 - exam_type_name을 확인해서 "실기"/"소묘"/"수채화"/"기초디자인"/
"조소" 같은 실제 제작형 실기 종목이 없고 "서류평가"/"면접"/"구술"만 있다면 그
전형은 실기시험 자체가 없는 것이고, exam_dates는 면접일입니다(실측 발견: 홍익대
미술우수자전형은 미술활동보고서 서류평가+면접뿐인데 그 날짜를 "실기 날짜"라고
답해 학생에게 위험한 오해를 줄 뻔했습니다). 실기시험이 있는 전형만 "실기 날짜"라고
부르고, 없으면 "이 조건에서 실기시험이 있는 전형을 찾지 못했습니다 - 아래는 면접/
서류 전형 일정입니다"처럼 구분해서 답하십시오.

"전체 흐름/절차/일정을 요약해줘"류 질문에 summarize_admission_flow를 쓸 때, 질문에
"일정"이라는 말이 있거나 원서접수·실기고사·합격발표 같은 구체적 날짜가 필요해
보이면 summarize_admission_flow 하나만 부르고 끝내지 말고 get_university_info도
같이 호출해서 실제 날짜를 함께 답하십시오 - summarize_admission_flow는 원문 여러
개를 LLM이 압축한 개요라 개별 날짜가 다 안 담겨 있을 수 있는데도(실측 발견: 같은
"일정 요약" 질문 유형인데 한 대학은 두 도구를 다 불러 정확한 날짜가 나왔고, 다른
대학은 summarize_admission_flow만 불러 "정확한 날짜는 공식 홈페이지에서 확인하라"는
뭉뚱그린 답만 나왔음 - 구조화 데이터에 날짜가 이미 있는데도 안 쓴 것).

"정원이 제일 많은/적은", "모집인원 순위" 처럼 quota(정원) 기준으로 순위를 묻는
질문에는 get_competition_rate_ranking을 절대 쓰지 마십시오 - 그 도구는 오직
경쟁률(competition_rate)로만 정렬하며 quota 정렬 기능이 아예 없습니다(실측 발견:
topic_keywords로 실기종목을 좁혀서 불러도 여전히 경쟁률 순으로 정렬돼, 정원 18명인
전형을 "정원이 제일 많다"고 잘못 답한 사고가 재현됨 - 실제 1위는 정원 289명).
quota 기준 질문은 반드시 text2cypher_query로 "ORDER BY t.quota DESC LIMIT 1"
형태의 쿼리를 써서 답하십시오.

위 도구들 중 어느 것도 질문과 안 맞으면(예: "실기고사일이 겹치는 전형 조합이 있는
대학이 몇 곳이야?", "정원이 제일 많은 전형은 어디야?" 같은 임의의 집계·필터·랭킹
질문) "확인할 수 없습니다"로 포기하지 말고 text2cypher_query를 최후 수단으로
쓰십시오. 단, 다른 도구로 답이 되는 질문에는 절대 쓰지 마십시오(느리고 비쌈)."""


def _get_service():
    # 2026-09-09: "입시 질문이 왜 느리지" 실측 - 도구 호출마다 여기서 새
    # ArtAdmissionService()(=새 Neo4j 드라이버, 클라우드 TLS 핸드셰이크)를 만들고
    # 있었다. 복합 질의 하나에 도구가 3~4번 불리면 그만큼 연결 비용이 누적된다.
    # 프로세스 생애주기 동안 하나만 만들어 재사용하는 공유 인스턴스로 교체
    # (art_admission_service.get_shared_service() 참고, api_art_admission.py의
    # get_service()와 동일한 인스턴스를 공유한다).
    from services.art_admission_service import get_shared_service
    return get_shared_service()


def _all_universities() -> List[str]:
    """Self-RAG 그라운딩 체크용 전체 대학 목록. 실패해도 그라운딩 체크가 그냥
    스킵되게(빈 리스트) 하고, 에이전트 답변 자체는 절대 막지 않는다."""
    svc = _get_service()
    try:
        return sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        return []


@tool
def get_university_info(university: str, campus: str = "") -> str:
    """특정 대학 하나에 대해 실기유형을 특정하지 않고 전반적으로 물을 때 쓴다
    (예: "가천대 실기는 뭐야?", "중앙대 전형 알려줘"). search_tracks는 실기종목/재료
    키워드가 있어야만 결과가 나오므로, 그런 키워드 없이 대학 하나만 언급된 질문에는
    이 도구를 써야 한다. 그 대학의 모든 학과·전형·실기유형을 전부 반환한다."""
    svc = _get_service()
    detail = svc.get_university_detail(university, campus=campus or None)
    tracks = [{
        "department": t.get("department"), "track_name": t.get("track_name"),
        "exam_type_name": t.get("exam_type_name"), "allowed_materials": t.get("allowed_materials"),
        "quota": t.get("quota"), "exam_dates": t.get("exam_dates"), "source_url": t.get("source_url"),
        "competition_rate": t.get("competition_rate"), "competition_applicant_count": t.get("competition_applicant_count"),
        "past_topics": [p for p in (t.get("past_topics") or []) if p.get("topic_text")] or None,
    } for t in detail.get("official_tracks", [])]
    return json.dumps({"university": university, "count": len(tracks), "tracks": tracks}, ensure_ascii=False)


@tool
def find_similar_departments(university: str, department: str, campus: str = "", top_k: int = 5) -> str:
    """"OO학과랑 비슷한 학과 어디 있어?" 같은 질문에 쓴다. 학과명 표기가 학교마다
    달라도("애니메이션학과(4컷)" vs "만화애니메이션텍전공") 교육과정이 비슷하면 찾아준다 -
    관리자가 승인한 표준 계열 태그가 같은 학과들 중에서만 비교하므로(예: "회화·한국화"
    안에서만), 전혀 다른 계열끼리 우연히 비슷하게 나오는 오매칭을 막는다.

    university/department는 반드시 사용자 질문에 나온 "기준 학교/학과"만 넣으십시오
    (예: "중앙대 실기와 유사한 대학 찾아줘" -> university="중앙대학교"). 결과 후보로
    나올 만한 다른 대학 이름을 여기 넣지 마십시오 - 이 도구는 "university의 department와
    비슷한 곳"을 찾아 반환하는 것이지, university 자체를 비교 대상 후보로 넣는 게
    아닙니다(실측으로 발견한 버그: 중앙대를 물었는데 university="가천대학교"를 넣어
    엉뚱한 0건이 나옴). get_university_info로 학과명을 확인했다면 그때 조회한
    university 인자를 그대로 재사용하십시오.

    similarity_pct는 교육과정 텍스트 임베딩 간 코사인 유사도를 %로 바꾼 값이다 -
    이건 사람이 검증한 사실이 아니라 통계적 유사도이므로, 답변에서 "N% 유사"처럼
    수치 그대로 전달하되 "확실히 같다/증명됐다"처럼 단정하지 말 것. standard_tag가
    없어서 결과가 비어 있으면 "아직 이 학과는 계열 분류/커리큘럼 데이터가 없어
    비교할 수 없다"고 정직하게 답할 것(추측으로 채우지 말 것).

    2026-09-22 중요: 이 도구는 "커리큘럼(수업 내용)이 비슷한가"만 비교하고 실기
    종목·재료가 같다는 뜻이 절대 아니다. "같은/호환되는 실기로 지원 가능한 학교"처럼
    질문에 "실기"/"호환"이 있으면 이 도구 대신 반드시 find_compatible_exam_tracks를
    쓰십시오(실측 발견: 이 도구로 답했다가 실기유형이 전혀 다른 학교만 나온 경우 있음)."""
    svc = _get_service()
    rows = svc.find_similar_departments(university, department, campus=campus or None, top_k=top_k)
    trimmed = [{
        "university": r["university"], "campus": r.get("campus"), "department": r["department"],
        "standard_tag": r.get("standard_tag"), "similarity_pct": round((r.get("score") or 0) * 100, 1),
        "source_url": r.get("source_url"),
    } for r in rows]
    return json.dumps({"count": len(trimmed), "similar": trimmed}, ensure_ascii=False)


@tool
def find_compatible_exam_tracks(university: str, department: str, campus: str = "") -> str:
    """"OO대 OO학과와 같은/호환되는 실기로 지원 가능한 학교는?"처럼 실기 종목·재료가
    실제로 일치하는(또는 겹치는) 학교를 찾을 때 쓴다. find_similar_departments
    (커리큘럼/수업 내용 유사도)와는 완전히 다른 기준이다 - 질문에 "실기"/"호환"이
    있으면 이 도구를, "성격이 비슷한 학과"/"계열이 비슷"처럼 학과 자체의 성격을
    묻는 질문엔 find_similar_departments를 쓰십시오.

    결과의 shared_keywords가 있으면 실기유형(과제) 자체가 일치하는 것이고,
    shared_keywords는 비어있고 shared_materials만 있으면 재료·규격만 겹치는
    것(실기유형은 다름)이다 - 답변에서 이 둘을 절대 같은 말("호환"/"같은 실기")로
    섞어 쓰지 말고 명확히 구분해서 전달하십시오. 결과가 비어 있으면 "실기유형이
    실제로 일치하는 다른 학교를 찾지 못했습니다"라고 정직하게 답하십시오."""
    svc = _get_service()
    rows = svc.find_compatible_tracks(university, department)
    trimmed = [{
        "university": r["university"], "department": r.get("department"), "track_name": r.get("track_name"),
        "exam_type_name": r.get("exam_type_name"), "shared_keywords": r.get("shared_keywords"),
        "shared_materials": r.get("shared_materials"), "source_url": r.get("source_url"),
    } for r in rows[:15]]
    return json.dumps({"count": len(trimmed), "compatible": trimmed}, ensure_ascii=False)


@tool
def search_document_details(query: str, university: str = "") -> str:
    """구조화 필드(get_university_info 등)로는 안 잡히는 세세한 원문 디테일(반입금지
    물품, 입실/고사 시작 시각, 특별 유의사항, 지원자격 우대사항 등)을 학교 공식
    모집요강·안내문 원문에서 직접 검색한다. 다른 도구로 답이 안 나오는 세부질문에
    쓰고, university를 알면 반드시 채워서 검색을 그 학교로 좁히십시오(안 채우면
    관련 없는 다른 학교 내용이 섞여 나올 수 있음). 결과 text는 원문 발췌이며,
    거기 없는 내용은 지어내지 말고 "원문에서 확인하지 못했습니다"라고 답하십시오."""
    svc = _get_service()
    rows = svc.search_document_excerpts(query, top_k=5, universities=[university] if university else None)
    trimmed = [{
        "university": r.get("university"), "source_file": r.get("source_file"),
        "text": (r.get("text") or "")[:600], "page_start": r.get("page_start"), "page_end": r.get("page_end"),
    } for r in rows]
    return json.dumps({"count": len(trimmed), "excerpts": trimmed}, ensure_ascii=False)


@tool
def search_tracks(topic_keywords: List[str] = [], material_query: str = "", document_only: bool = False) -> str:
    """학생이 준비 중인 실기 종목(topic_keywords, 예: ["소묘"], ["기초디자인"])이나 재료
    (material_query, 예: "연필")로 지원 가능한 대학 전형을 찾는다. 결과의 match_status가
    "exact"면 실기유형 자체가 일치, "partial"이면 재료·규격만 겹침(실기유형은 다름),
    "document"면 서류전형이다. 서류전형만 보고 싶으면 document_only=true."""
    svc = _get_service()
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


@tool
def compare_tracks(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들(university, campus, department 조합 2~6개)을 나란히 비교하는 표를
    만든다. selections 예: [{"university":"가천대학교","campus":"글로벌(성남)","department":"시각디자인전공"}, ...]"""
    svc = _get_service()
    rows = svc.get_comparison_table(selections)
    return json.dumps({"count": len(rows), "tracks": rows}, ensure_ascii=False, default=str)


@tool
def check_schedule_conflicts(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들의 실기고사일이 서로 겹치는지 확인한다(수시 최대 6장 제한도 함께
    검사). selections 형식은 compare_tracks와 동일."""
    svc = _get_service()
    result = svc.simulate_multi_apply(selections)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_competition_rate_ranking(topic_keywords: List[str] = [], top_n: int = 10, order: str = "desc") -> str:
    """"경쟁률 제일 높은/낮은 학교는?" 같은 "경쟁률(competition_rate)" 랭킹 질문에만
    쓴다. 개별 학교 비교용 도구(get_university_info/search_tracks)는 조건에 맞는
    목록만 줄 뿐 "전체 중 1등"을 가려낼 수 없어서 이런 질문엔 항상 "확인하지
    못했습니다"만 나오던 문제(2026-09-14 사용자 발견)를 이 도구로 메운다. 2027학년도
    공식 발표 경쟁률(competition_rate)이 있는 전형만 대상으로 하며, 아직 학교가 발표
    안 한 전형은 순위에서 제외한다(0으로 지어내지 않음). order="asc"면 경쟁률 낮은
    순(안정 지원 후보 찾기용). competition_rate는 배수(예: 9.03은 "9.03:1", 9.03%가
    아님) - 답변에 %를 붙이지 말 것.
    주의: 이 도구는 오직 경쟁률로만 정렬합니다. "정원이 제일 많은/적은", "모집인원
    순위" 같은 quota(정원) 기준 랭킹 질문에는 이 도구를 절대 쓰지 마십시오 - 실측
    발견: 이 도구를 quota 질문에 잘못 써서 경쟁률 낮은 순 1위(정원 2명짜리 소규모
    학과)를 "정원이 제일 많다"고 답하는 완전히 틀린 사고가 있었습니다(실제 1위는
    정원 289명). quota 기준 랭킹은 이 도구에 없으므로 text2cypher_query로
    "ORDER BY t.quota DESC"를 써서 답하십시오."""
    svc = _get_service()
    tracks = svc.list_all_tracks_full()
    if topic_keywords:
        from services.art_admission_service import ArtAdmissionService
        tracks = [
            t for t in tracks
            if any(ArtAdmissionService._topic_keyword_matches(kw, t.get("exam_type_name") or "") for kw in topic_keywords)
        ]
    rated = [t for t in tracks if t.get("competition_rate") is not None]
    rated.sort(key=lambda t: t["competition_rate"], reverse=(order != "asc"))
    trimmed = [{
        "university": t["university"], "campus": t.get("campus"), "department": t["department"],
        "track_name": t.get("track_name"), "competition_rate": t["competition_rate"],
        "competition_applicant_count": t.get("competition_applicant_count"),
        "quota": t.get("quota"), "source_url": t.get("competition_rate_source_url") or t.get("source_url"),
    } for t in rated[:top_n]]
    return json.dumps({
        "count": len(trimmed), "total_with_official_rate": len(rated), "total_tracks_considered": len(tracks),
        "ranking": trimmed,
    }, ensure_ascii=False, default=str)


@tool
def get_calendar(selections: List[Dict[str, str]]) -> str:
    """선택한 전형들의 원서접수·실기고사·합격발표 일정을 시간순으로 정리한다.
    selections 형식은 compare_tracks와 동일 (빈 리스트면 전체 일정)."""
    svc = _get_service()
    all_events = svc.get_calendar_events()
    if not selections:
        return json.dumps({"events": all_events[:30]}, ensure_ascii=False, default=str)
    labels = {f"{s['university']} {s['department']}" for s in selections}
    filtered = [e for e in all_events if e.get("school") in labels]
    return json.dumps({"events": filtered}, ensure_ascii=False, default=str)


@tool
def recommend_by_grades(grades: List[Dict[str, Any]], topic_keywords: List[str] = [], material_query: str = "") -> str:
    """학생의 내신 성적과 준비 중인 실기 종목을 함께 주면, results.html/grades.html의
    "성적 추천" 화면과 완전히 같은 계산 엔진(recommend_conflict_free_combo)으로 실제
    지원할 만한 전형을 골라준다. "내신 3등급에 기초디자인인데 어디 찔러야 해?" 같은
    질문에는 반드시 이 도구를 써야 한다 - 문서 검색(search_tracks)만으로는 학생부
    환산 계산을 못 하므로 "신중히 지원하세요" 같은 원론적 답변만 나오게 된다(2026-09-14
    사용자 발견 - 화면에서는 되는데 챗봇에서만 안 되던 근본 원인).
    수시 최대 6장 제한 안에서 실기고사 날짜가 서로 안 겹치는 조합도 같이 짜준다.

    grades 형식(리스트, 과목마다 하나씩):
    - 일반/공통선택과목: {"subject_group": "국어", "grade": 3, "credit": 4}
      (subject_group은 "국어"/"수학"/"영어"/"사회"/"과학"/"한국사"/"예술 계열" 등 나이스
      교과 분류명, grade는 1~9 석차등급, credit은 이수단위 - 사용자가 "국어 3등급"처럼만
      말해도 credit은 3~4 정도로 합리적으로 채워 넣는다)
    - 진로선택과목(성취도 A/B/C만 있고 석차등급이 없는 과목): {"subject_group": "예술",
      "career_elective": true, "achievement": "A", "credit": 2}
    사용자가 등급을 일부만 말했으면(예: "국영수만 알려줬다") 아는 과목만 넣는다 -
    모르는 과목을 지어내 채우지 않는다. topic_keywords는 실기 종목(예: ["기초디자인"]),
    material_query는 준비한 재료(예: "수채화")."""
    svc = _get_service()
    result = svc.recommend_conflict_free_combo(grades, topic_keywords=topic_keywords, material_query=material_query)
    combo = [{
        "university": c["university"], "campus": c.get("campus"), "department": c["department"],
        "track_name": c.get("track_name"), "exam_type_name": c.get("exam_type_name"),
        "school_record_percentage": c.get("school_record_percentage"), "calc_precision": c.get("calc_precision"),
        "reason_summary": c.get("reason_summary"), "exam_dates": c.get("exam_dates"),
        "source_url": c.get("source_url"),
    } for c in result["combo"]]
    return json.dumps({
        "combo": combo, "count": result["count"],
        "total_candidates_considered": result["total_candidates_considered"],
    }, ensure_ascii=False, default=str)


# 2026-09-21 day42 Text2Cypher 도입: 위 8개 고정 도구는 "미리 예상한 질문 유형"만
# 답할 수 있다 - 실측으로 확인된 실패 사례("실기고사일이 2개 이상 겹치는 전형 조합이
# 있는 대학이 몇 곳이야?" 같은 임의 집계/필터 질문)는 어떤 고정 도구 설명과도 안 맞아서
# 에이전트가 도구를 아예 안 부르고 "확인할 수 없습니다"로 새버렸다(그래프에 필요한
# 데이터가 다 있는데도). 고정 도구를 무한정 추가하는 대신, 스키마를 아는 LLM이 그때그때
# 필요한 Cypher를 직접 짜게 하는 이 도구로 롱테일 질문을 받는다 - 단, 절대 원칙(§1)을
# 지키기 위해 읽기 전용만 허용하고, 생성된 쿼리를 실행 전에 코드로 검증한다.
_GRAPH_SCHEMA_DESC = """
(:Admission_University {name, campus})
(:Admission_Department {name, university, standard_tag, department_intro, curriculum_subjects})
(:Admission_Track {name, university, department, quota, ratio, is_staged, source_url, admission_year,
                    competition_applicant_count, competition_rate})
(:Admission_ExamType {name, university, department, track_name, allowed_materials, paper_size, time_limit_minutes})
(:Admission_Schedule {university, department, track_name, application_start, application_end,
                       exam_date, result_date, registration_start, registration_end})
(:Admission_SelectionStage {university, department, track_name, stage_number, description, ratio_desc, multiplier})
(:Admission_CutoffEstimate {university, department, track_name, cutoff_grade_estimate, data_tier, source_url})
(:Admission_YearlyResult {university, department, track_name, admission_year, competition_rate, grade_typical})

관계: (Univ)-[:HAS_DEPARTMENT]->(Dept)-[:HAS_TRACK]->(Track)-[:REQUIRES_EXAM]->(ExamType),
     (Track)-[:HAS_SCHEDULE]->(Schedule), (Track)-[:HAS_STAGE]->(SelectionStage),
     (Track)-[:ESTIMATED_CUTOFF]->(CutoffEstimate), (Track)-[:HAS_YEARLY_RESULT]->(YearlyResult)
"""

_CYPHER_GEN_PROMPT = f"""당신은 Neo4j Cypher 전문가입니다. 아래 그래프 스키마만 보고,
사용자 질문에 답하는 Cypher 쿼리를 정확히 하나만 작성하십시오.

스키마:
{_GRAPH_SCHEMA_DESC}

규칙(반드시 지킬 것):
1. MATCH/WHERE/WITH/RETURN/ORDER BY/LIMIT/집계함수(count, collect, avg 등)만 사용 - 절대
   CREATE/MERGE/DELETE/DETACH/SET/REMOVE/DROP/LOAD CSV/CALL apoc 같은 쓰기·관리 구문을 쓰지 마십시오.
2. 스키마에 없는 라벨/속성을 지어내지 마십시오.
3. LIMIT이 없으면 결과 끝에 반드시 LIMIT 50을 붙이십시오.
4. 설명 없이 Cypher 쿼리 코드만 출력하십시오(마크다운 코드블록도 쓰지 말 것).
5. "같은 대학/학교 안에서 서로 다른 두 전형(트랙)을 비교"해야 하는 질문(예: 일정 겹침,
   같은 날짜)은 반드시 같은 대학을 두 번 매치하는 자기 자신과의 JOIN이 필요합니다.
   한쪽 트랙만 보고 답하면 항상 틀립니다.
6. 질문이 "몇 곳/몇 개"처럼 개수를 묻더라도, count(...) 숫자 하나만 RETURN하지 말고
   실제로 해당하는 대학/학과/전형명과 근거가 되는 구체적 값(예: 겹치는 날짜)도 함께
   collect()로 RETURN해서, 사용자가 그 숫자를 직접 검증할 수 있게 하십시오(실측 발견:
   숫자만 반환하면 "그 N곳이 어디인지, 정말 맞는지" 사용자가 확인할 방법이 없어
   불신으로 이어졌습니다). 예시:
   MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->()-[:HAS_TRACK]->(t1:Admission_Track)-[:HAS_SCHEDULE]->(s1:Admission_Schedule),
         (u)-[:HAS_DEPARTMENT]->()-[:HAS_TRACK]->(t2:Admission_Track)-[:HAS_SCHEDULE]->(s2:Admission_Schedule)
   WHERE t1.name < t2.name AND s1.exam_date IS NOT NULL AND s1.exam_date = s2.exam_date
   RETURN u.name AS university, collect(DISTINCT {{track1: t1.name, track2: t2.name, exam_date: s1.exam_date}}) AS overlapping_tracks
   ORDER BY university LIMIT 50
7. 질문에 "실기전형"/"실기 전형"이라는 말이 있으면, 학생부교과·학생부종합처럼 실기
   자체가 없는 전형(서류·내신만으로 선발)을 결과에 절대 섞지 마십시오(실측 발견:
   "정원이 제일 적은 실기전형은?" 질문에 실기가 아예 없는 "학생부종합(농어촌학생)"
   전형을 실기전형이라며 잘못 답한 사고가 있었습니다). Admission_Track을
   REQUIRES_EXAM으로 Admission_ExamType과 반드시 JOIN하고, ExamType.name이
   "실기 없음"이나 "해당 없음"을 포함하거나 "학생부"로 시작하는 행은 WHERE 절에서
   제외하십시오. 예:
   MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d)-[:HAS_TRACK]->(t:Admission_Track)
         -[:REQUIRES_EXAM]->(e:Admission_ExamType)
   WHERE t.quota IS NOT NULL AND NOT e.name CONTAINS "실기 없음"
         AND NOT e.name CONTAINS "해당 없음" AND NOT e.name STARTS WITH "학생부"
         AND e.name <> "미지정" AND NOT e.name CONTAINS "미지정"
   RETURN u.name AS university, t.name AS track_name, t.quota AS quota, e.name AS exam_type_name
   ORDER BY quota ASC LIMIT 50

질문: __QUESTION__"""

_FORBIDDEN_CYPHER_PATTERN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|CALL\s+apoc\.(?!text|meta))\b",
    re.IGNORECASE,
)

# 2026-09-23 [항목② 구글문서 검토 후속]: "생성된 자유 Cypher를 검증 없이 그대로
# 실행한다"는 지적에 대해 - Neo4j READ_ACCESS 세션 자체가 서버 레벨에서 쓰기를
# 거부하므로(클라이언트 정규식과 무관하게 실제로 강제됨) 데이터 변조 위험은 원래도
# 없었지만, 진짜 AST 컴파일러를 만드는 대신 실질적 위험(스키마에 없는 라벨/관계로
# 헤매며 비싼 쿼리를 짜는 것, 여러 문장을 이어붙이는 것, 결과 폭주, 무한정 실행)을
# 코드로 막는 allowlist+제한을 추가한다.
_ALLOWED_LABELS = {
    "Admission_University", "Admission_Department", "Admission_Track", "Admission_ExamType",
    "Admission_Schedule", "Admission_SelectionStage", "Admission_CutoffEstimate", "Admission_YearlyResult",
}
_ALLOWED_REL_TYPES = {
    "HAS_DEPARTMENT", "HAS_TRACK", "REQUIRES_EXAM", "HAS_SCHEDULE", "HAS_STAGE",
    "ESTIMATED_CUTOFF", "HAS_YEARLY_RESULT",
}
_ALLOWED_SCHEMA_TOKENS = _ALLOWED_LABELS | _ALLOWED_REL_TYPES
# 스키마의 라벨/관계타입은 전부 대문자로 시작하는 명명 규칙이라(Admission_Xxx,
# HAS_XXX), ":Xxx" 형태의 라벨/관계 토큰만 골라내고 소문자로 시작하는 속성 맵 키
# ({name: $x} 등)는 자연히 걸러진다.
_LABEL_TOKEN_PATTERN = re.compile(r":([A-Z][A-Za-z0-9_]*)")
_MULTI_STATEMENT_PATTERN = re.compile(r";\s*\S")  # 세미콜론 뒤에 내용이 더 있으면 여러 문장
_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)
_MAX_ROW_LIMIT = 50
_CYPHER_TIMEOUT_SECONDS = 10.0


def _validate_cypher(cypher: str) -> Optional[str]:
    """생성된 Cypher가 실행해도 안전한지 검증한다. 문제가 있으면 사용자에게 보여줄
    에러 메시지를, 안전하면 None을 반환한다."""
    if _FORBIDDEN_CYPHER_PATTERN.search(cypher):
        return "안전상 읽기 전용 쿼리만 허용됩니다."
    if _MULTI_STATEMENT_PATTERN.search(cypher):
        return "한 번에 하나의 쿼리 문장만 허용됩니다."
    unknown = sorted({m for m in _LABEL_TOKEN_PATTERN.findall(cypher) if m not in _ALLOWED_SCHEMA_TOKENS})
    if unknown:
        return f"스키마에 없는 라벨/관계를 사용했습니다: {unknown}"
    limits = [int(n) for n in _LIMIT_PATTERN.findall(cypher)]
    if limits and max(limits) > _MAX_ROW_LIMIT:
        return f"LIMIT은 최대 {_MAX_ROW_LIMIT}까지만 허용됩니다."
    return None


def _generate_cypher(question: str) -> str:
    llm = ChatOpenAI(model=AGENT_MODEL, temperature=0)
    resp = llm.invoke(_CYPHER_GEN_PROMPT.replace("__QUESTION__", question))
    cypher = resp.content.strip()
    # 혹시 마크다운 코드블록으로 감싸 나오면 벗겨낸다.
    cypher = re.sub(r"^```(?:cypher)?\s*|\s*```$", "", cypher, flags=re.IGNORECASE).strip()
    if not _LIMIT_PATTERN.search(cypher):
        cypher = cypher.rstrip().rstrip(";") + f" LIMIT {_MAX_ROW_LIMIT}"
    return cypher


@tool
def text2cypher_query(question: str) -> str:
    """다른 도구 어디에도 안 맞는 구조화 데이터 질문(임의의 집계/필터/랭킹, 예: "실기고사일이
    2개 이상 겹치는 전형 조합이 있는 대학이 몇 곳이야?")에만 최후 수단으로 쓰십시오. 먼저
    다른 도구(get_university_info, search_tracks, compare_tracks, check_schedule_conflicts,
    get_calendar, recommend_by_grades, get_competition_rate_ranking, find_similar_departments,
    find_compatible_exam_tracks, search_document_details)로
    답할 수 있는지 반드시 먼저 확인하고, 그중 하나로 답이 되면 절대 이 도구를 쓰지 마십시오
    (이 도구는 매번 별도 LLM 호출로 Cypher를 새로 생성하므로 더 느리고 비쌉니다).
    이 도구가 반환한 JSON 행(rows) 안의 값만 사실로 쓰고, 없는 값은 절대 지어내지 마십시오."""
    cypher = _generate_cypher(question)
    error = _validate_cypher(cypher)
    if error:
        return json.dumps({"error": error, "generated_cypher": cypher}, ensure_ascii=False)
    svc = _get_service()
    try:
        from neo4j import Query
        with svc.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run(Query(cypher, timeout=_CYPHER_TIMEOUT_SECONDS)).data()
    except Exception as e:
        return json.dumps({"error": f"쿼리 실행 실패: {e}", "generated_cypher": cypher}, ensure_ascii=False)
    return json.dumps({"count": len(rows), "rows": rows[:_MAX_ROW_LIMIT], "generated_cypher": cypher}, ensure_ascii=False, default=str)


@tool
def summarize_admission_flow(university: str, topic: str = "") -> str:
    """"OO대 수시 절차/전체 흐름을 요약해줘", "미술활동보고서 절차 총정리해줘",
    "이 학과 전반적으로 어떤 분위기야/특징이야"처럼 개별 사실 하나가 아니라 여러
    절차·내용을 관통하는 "전체 흐름/개요/분위기"를 물을 때 쓴다. 특정 숫자·날짜
    하나만 묻는 질문(예: "논술고사 시험시간 몇 분이야?")에는 절대 쓰지 말고
    get_university_info나 text2cypher_query를 쓰십시오 - 이 도구가 주는 요약은
    LLM이 원문 여러 개를 압축한 것이라 개별 숫자가 다 안 담겨 있을 수 있습니다.
    topic을 비워두면 대학 전체 개요, topic을 주면(예: "미술활동보고서") 그 주제에
    가장 가까운 요약을 찾습니다. day46 RAPTOR 트리가 아직 없는 신규 학교(색인
    파이프라인 미실행분)를 물으면 빈 결과가 오므로, 그때는 이 도구 대신 다른
    도구로 답하십시오."""
    svc = _get_service()
    rows = svc.get_raptor_summary(university, query=topic, top_k=3)
    if not rows:
        return json.dumps({
            "error": f"{university}는 아직 전체 흐름 요약(RAPTOR)이 준비되지 않았습니다. "
                     "get_university_info 등 다른 도구로 개별 사실을 확인하십시오.",
        }, ensure_ascii=False)
    return json.dumps({
        "university": university,
        "note": "이 요약은 LLM이 원문 여러 건을 압축한 것입니다 - 정확한 숫자/날짜가 필요하면 다른 도구로 원문을 재확인하십시오.",
        "summaries": [{"level": r["level"], "text": r["text"]} for r in rows],
    }, ensure_ascii=False)


TOOLS = [get_university_info, find_similar_departments, find_compatible_exam_tracks, search_document_details, search_tracks, compare_tracks, check_schedule_conflicts, get_calendar, recommend_by_grades, get_competition_rate_ranking, text2cypher_query, summarize_admission_flow]


def run_qa_pipeline(
    svc, query: str, model_id: str = AGENT_MODEL,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """기존 /qa 엔드포인트와 완전히 같은 파이프라인(그래프 조회 + LLM 답변 생성 1회).
    도구를 여러 개 조합할 필요 없는 단순 질의(대학 하나 전체 조회, 실기종목 검색)에
    쓴다 - LLM이 "어떤 도구를 쓸지" 고민할 필요 자체가 없어서 더 빠르고 저렴하고,
    도구 선택 실수(이번 세션의 get_university_info 누락 버그류)가 원천적으로 안 생긴다."""
    context_tracks, context_estimates = svc.build_llm_context(query, history=history)

    # 2026-09-22 실측으로 발견한 버그 수정: 예전엔 anchor_names를 context_tracks에서
    # 등장하는 대학명으로 뽑았는데, build_llm_context가 질의에서 학교를 못 찾으면
    # subset을 "전체 55개교"로 채우므로(art_admission_service.py build_llm_context
    # 참고) anchor_names도 늘 55개교 전부가 돼버려 "질의에서 학교가 실제로 인식됐는지"
    # 를 전혀 구분하지 못했다(결과: 아래 두 로직이 사실상 죽어있었음 - "학교 인식 시
    # 그 학교로만 검색 좁히기"도, 뒤이은 "무관 컨텍스트 정리"도 이 조건이 항상
    # False(=전체 55개교가 anchor로 잡힘)라 실행되지 않았다). build_llm_context와
    # 완전히 같은 로직(resolve_university_mentions_with_negation)을 직접 써서
    # "질의 문장에 실제로 이름이 등장한 학교"만 anchor로 삼는다.
    from services.art_admission_service import resolve_university_mentions_with_negation
    try:
        all_universities = sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        all_universities = []
    mentioned = resolve_university_mentions_with_negation(query, all_universities)["included"]

    try:
        # 질의에서 학교가 실제로 인식됐으면 그 학교 청크로만 검색을 좁힌다 -
        # 그렇지 않으면 55개교 전체를 놓고 순위를 매겨서 다른 학교 내용에 밀려날 수 있다.
        context_raw = svc.search_document_excerpts(query, top_k=5, universities=sorted(set(mentioned)) or None)
    except Exception:
        context_raw = []

    # 2026-09-22 실측 발견: 질의에서 학교가 안 잡히면 context_tracks가 전체 55개교
    # 299건을 통째로 담는다 - 원문검색(context_raw)이 실제로 정답을 찾아와도
    # ("미술활동보고서 표절 기준이 뭐야?" - 검색은 홍익대 표절 기준표를 1위로 정확히
    # 찾음), gpt-4o-mini가 299건짜리 무관한 구조화 데이터에 묻혀 정작 그 5건짜리 원문
    # 발췌를 무시하고 "확인하지 못했습니다"로 답하는 현상을 재현 확인(self_check 재시도
    # 문제가 아니라 1차 생성 자체가 이렇게 나옴). 아래 주석(2026-09-22 이전)에 적힌
    # "학교명 없이 작성법을 묻는 질문"만 review.html로 우회시킨 이전 패치는 이 버그의
    # 한 증상만 피해갔을 뿐 근본 원인(무관한 대량 컨텍스트가 신호를 희석시킴)은 그대로
    # 남아 있었다 - 원문검색이 특정 학교를 찾아왔으면 그 학교로 context_tracks도 다시
    # 좁혀서, 원문검색이 실제로 찾아낸 학교와 무관한 나머지 학교 데이터가 신호를
    # 희석시키지 않게 한다.
    # 2026-09-23 실측 발견("소묘 학교 왔다갔다" 사고 재조사): 학교명 없이 실기유형
    # 키워드만으로 "그 실기로 볼 수 있는 학교 목록"을 묻는 질문(또는 그 후속질문)에서,
    # 바로 아래의 원문검색 기반 재좁히기가 질문 텍스트와 의미상 우연히 비슷한 엉뚱한
    # 4~5개 학교로 context_tracks를 잘못 좁혀버려 실기유형이 실제로 일치하는 나머지
    # 학교들이 통째로 사라지는 걸 확인했다(예: "소묘"에 대해 가천대/숙명여대/전남대만
    # 남고 정작 소묘 전형이 있는 중앙대/한예종 등은 빠짐). 이 재좁히기는 "원문 산문
    # 인용이 필요한 질문"을 위한 것이지, "구조화된 exam_type_keyword_match로 이미
    # 걸러지는 실기유형 목록형 질문"에는 오히려 해롭다 - 실기유형 키워드가(이번 질의든
    # 직전 대화 이력에서 이어받은 것이든) 있으면 재좁히기를 건너뛴다.
    try:
        canonical_topics = sorted(set(svc.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)
    except Exception:
        canonical_topics = []

    def _has_topic_kw(text: str) -> bool:
        return any(kw in text for kw in canonical_topics)

    has_topic_kw = _has_topic_kw(query) or any(
        _has_topic_kw(str(m.get("content", "")))
        for m in (history or []) if m.get("role") == "user"
    )

    if not mentioned and has_topic_kw:
        # 원문검색 재좁히기 대신, 이미 정확한 exam_type_keyword_match 플래그로 직접
        # 좁힌다 - "건너뛰기"만 하면 299건 전체가 그대로 LLM에 실려 페이로드가
        # 커지면서 실제로 타임아웃/호출 실패가 나는 걸 실측으로 확인했다(수정 직후
        # 프로덕션 재검증에서 "소묘로 시험 보는 학교 알려줘"가 반복적으로 LLM 호출
        # 실패 처리됨). 일치하는 항목만 추리면 정확도와 페이로드 크기를 동시에
        # 잡을 수 있다.
        matched = [t for t in context_tracks if t.get("exam_type_keyword_match")]
        if matched:
            context_tracks = matched
    elif not mentioned and context_raw:
        raw_universities = sorted({r["university"] for r in context_raw if r.get("university")})
        if raw_universities:
            context_tracks = [t for t in context_tracks if t["university"] in raw_universities]
            context_estimates = [e for e in context_estimates if e.get("university") in raw_universities]
    # 2026-09-21 사용자 지시로 끔: get_graph_related_context()가 만드는 "관련 학교"
    # 힌트는 원문 인용/출처 없이 동시출현 커뮤니티만으로 만드는데, 2026-09-17 감사에서
    # 라벨 붙은 24개 커뮤니티 중 20개가 내부 동시출현의 65~100%가 "1회성"(우연한
    # 동시 언급)으로 확인된 노이즈 위주 데이터다. 답변에 실제로 주입되는 컨텍스트라
    # 방치하면 사용자에게 근거 없는 "관련 학교" 힌트가 섞여 나갈 수 있어 원천 차단한다.
    # 이 기능이 하려던 "비슷한 학과 찾기"는 find_similar_departments(교육과정 임베딩 +
    # 관리자 승인 표준계열 태그, 94~98% 커버리지)가 이미 더 정확하게 대신하고 있다.
    context_graph_related: List[Dict[str, Any]] = []
    try:
        context_compatible = svc.get_compatible_tracks_for_query(query)
    except Exception:
        context_compatible = []

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


# 2026-09-22 실사용 발견: "미술활동보고서 어떻게 써야 하지?" 같이 학교명
# 없이 문서 작성법을 묻는 질문이 일반 QA 파이프라인으로 가면, 학교를 특정 못 해
# build_llm_context가 전체 대학 트랙(299건)을 통째로 컨텍스트에 넣고 결국
# "확인하지 못했습니다"로 끝난다 - 할루시네이션은 없었지만 "근거 299건"이라는
# 표시가 사용자에게 오히려 신뢰를 깎아먹었다. 이 질문 유형은 애초에 학교별
# 서류 규정을 원문에서 찾아 첨삭해주는 review.html(get_document_rule_excerpts
# 기반)이 훨씬 적합하므로, LLM 호출 자체를 생략하고 바로 안내한다.
_DOC_WRITING_HELP_SIGNALS = [
    "어떻게 써야", "작성 방법", "작성법", "쓰는 법", "어떻게 작성",
    "써야 하", "쓰는지", "작성할 때", "써야하나", "작성 시",
]
_DOC_TYPE_TRIGGER_WORDS = ["자기소개서", "미술활동보고서", "포트폴리오", "활동보고서"]

# 2026-09-23 실사용 발견: "재직사실확인서 제출 방법", "확인서 다운로드 경로", "팩스로
# 어떻게 보내" 같은 절차/행정 질문이 Jev에서 DOCUMENT_WRITING_HELP와 SIMPLE_GRAPH
# 사이 확률이 0.48:0.48로 사실상 동점이 나며 불안정하게 review.html로 새는 걸
# 확인했다 - 재현해보니 review.html의 좁은 키워드 검색(get_document_rule_excerpts,
# "블라인드/분량/글자/표절/대필" 등으로 한정)은 이런 절차 질문을 전혀 못 찾는 반면,
# 일반 원문검색은 정확한 답(팩스번호·다운로드 경로 포함)을 이미 찾아낼 수 있었다
# - 즉 review.html로 보내는 게 막다른 길이었다. 이런 절차성 신호어가 있으면
# DOCUMENT_WRITING_HELP를 아예 후보에서 제외해 Jev의 동점 판정에 흔들리지 않게 한다.
_DOC_PROCEDURAL_SIGNALS = [
    "제출 방법", "제출 경로", "제출처", "접수 방법", "접수처", "다운로드", "팩스", "FAX",
    "전송 방법", "전송처", "발급 방법",
    # 2026-09-23 GPT 고객경험 QC로 실측 발견: "미술활동보고서 몇 개까지 쓸 수 있어?"
    # (실제로는 교과활동 최대 7개/비교과 최대 8개/총 12개 이내라는 원문 수치가 이미
    # 색인돼 있어 SIMPLE_GRAPH로 바로 답할 수 있는데도) DOCUMENT_WRITING_HELP로
    # 오라우팅돼 review.html로 떠넘겨짐 - "개수/글자수 제한이 몇인지" 같은 정량적
    # 사실 질문도 "작성 규정"이 아니라 절차성 신호어로 취급한다.
    "몇 개까지", "몇 개 까지", "최대 몇", "몇 자까지", "몇 자 까지", "몇 건까지",
]


def _is_procedural_not_writing_help(query: str) -> bool:
    return any(w in query for w in _DOC_PROCEDURAL_SIGNALS)

# 2026-09-22: 도메인마다 다른 프런트가 이 함수를 호출할 수 있어(BO/CO/FO 각각
# 별도 배포) 하드코딩 대신 환경변수로 오버라이드 가능하게 하되, 기본값은 실제
# 운영 중인 FO 도메인으로 둔다.
# 2026-09-23 실사용 발견: 기본값이 Vercel 자동생성 URL(appartreadykr.vercel.app)로
# 박혀 있었다 - 실제 브랜드 도메인 www.artready.kr도 같은 배포를 정상 서빙하는 것을
# 확인(둘 다 HTTP 200)했으므로, 사용자에게 노출되는 링크는 브랜드 도메인으로 바꾼다.
_FO_BASE_URL = os.getenv("FO_PUBLIC_BASE_URL", "https://www.artready.kr")


def _is_document_writing_help_query_keyword(query: str) -> bool:
    """원래 방식(키워드 목록) - Jev 호출이 실패하면(키 없음/네트워크 오류/신생
    서비스 장애 등) 이 폴백으로 자동 전환된다."""
    return (
        any(w in query for w in _DOC_TYPE_TRIGGER_WORDS)
        and any(s in query for s in _DOC_WRITING_HELP_SIGNALS)
    )


# 2026-09-22 [day47 Jev 도입]: 위 키워드 방식은 "자기소개서 대필하면 걸리나요?",
# "미술활동보고서에 인적사항 넣으면 감점되나요?"처럼 목록에 없는 표현을 계속
# 놓쳤다(실측: 8문항 중 4문항 오탐/누락). TypeSafe AI의 Jev(Noul - 예/아니요
# 확률 판단)로 교체해서 실측 8/8 정확도로 개선 확인. 다만 Jev는 출시 1주일 된
# 신생 서비스라 가격/SLA가 아직 불명(2026-09-22 기준) - 실패해도 안전하게
# 키워드 방식으로 자동 폴백한다(예외 삼키고 조용히 대체, 사용자에게 영향 없음).
_JEV_TIMEOUT_SECONDS = 5.0


def _is_document_writing_help_query(query: str) -> bool:
    try:
        from typesafe_sdk import Noul, TypeSafeClient
        client = TypeSafeClient(timeout=_JEV_TIMEOUT_SECONDS)
        model = os.getenv("TYPESAFE_MODEL", "jev-1.13.0")
        resp = client.system_one(
            model=model, state=query,
            questions={
                "is_writing_help": Noul(
                    instructions=(
                        "이 질문이 '서류(자기소개서/미술활동보고서/포트폴리오 등) 작성 "
                        "방법이나 작성 규정(표절, 대필, 분량, 인적사항 노출, 실명 기재 등)'에 "
                        "관한 것인가요? 단순 사실 조회(전형/일정/마감일/절차 등)는 아니오입니다."
                    ),
                ),
            },
        )
        return resp.answers["is_writing_help"].noul >= 0.5
    except Exception:
        return _is_document_writing_help_query_keyword(query)


# 2026-09-23 [항목 ① Jev 라우터 통합]: 예전엔 route_and_answer가 Jev(Noul)를 최대
# 2번 순차 호출했다(서류작성법 판정 -> 아니면 복합질의 판정). 매번 최대 두 번의
# 왕복(각 최대 5초 타임아웃)이 누적될 수 있었고, 다이어그램(ART:READY 챗봇 아키텍처
# 검토 문서)이 제안한 "JEV ROUTER(3지선다)" 모양과도 안 맞았다(이진판단 2회로 3지선다를
# 흉내내고 있었음). Jev Choice(다지선다, 확률·신뢰도 함께 반환)로 한 번에 판정하도록
# 통합한다 - 왕복 1회로 줄어 지연시간이 줄고, 결과도 재사용 가능한 하나의 판정으로
# 남는다(§Evidence Package). 대학 2곳 이상 언급은 판단이 아니라 사실이므로 Jev를
# 거치지 않고 호출부에서 먼저 결정론적으로 처리한다(기존과 동일).
_ROUTE_CRITERIA = {
    "DOCUMENT_WRITING_HELP": (
        "서류(자기소개서/미술활동보고서/포트폴리오 등)를 지원자가 직접 '무슨 내용을 "
        "어떻게 써야 하는지' 묻는 질문이나, 그 내용에 대한 작성 규정(표절, 대필, 분량, "
        "인적사항 노출, 실명 기재 등)을 묻는 질문. 주의: '평가자 재직사실확인서 제출 "
        "방법', '서류 접수 경로/마감일', 'FAX 번호', '다운로드 경로'처럼 서류 자체의 "
        "글쓰기 내용이 아니라 제출·접수 절차/행정을 묻는 질문은 여기 해당하지 않는다 "
        "- 이런 질문은 SIMPLE_GRAPH나 COMPLEX_TOOL로 분류한다(실측 발견: 이런 절차성 "
        "질문이 여기로 잘못 분류돼 review.html로 보내졌는데, 정작 review.html의 좁은 "
        "키워드 검색은 이 내용을 못 찾아 안내가 막다른 길이 됐다 - 반면 일반 원문검색은 "
        "정확한 답을 이미 찾아낼 수 있었다)"
    ),
    "COMPLEX_TOOL": (
        "계산/비교/추천/랭킹/요약 도구가 필요한 질문: 성적 기반 지원 추천, 여러 전형 "
        "비교나 일정 충돌 확인, 경쟁률/순위 집계, 비슷한 학과나 호환되는 실기 찾기, "
        "전체 절차 요약, 또는 특정 학과·전형의 전반적인 분위기·특징·컨셉을 묻는 질문"
        "(예: '이 학과 전반적으로 어떤 느낌이야', '전형이 어떻게 굴러가'). 여기에는 "
        "직전 답변에 대한 되물음/항의성 후속질문도 포함된다 - 새 키워드 없이 "
        "'왜 그렇게 답했지', '아까랑 다르잖아', '뭔소리야', '또 빠졌네' 처럼 이전 "
        "답변 내용을 전제로 따지는 질문은 이번 문장만으로는 무엇을 찾아야 하는지 "
        "알 수 없어 대화 맥락을 실제로 참고해야 하므로 COMPLEX_TOOL로 분류한다"
        "(실측 발견: 이런 질문이 단순 키워드 재검색으로 처리되면서 같은 질문에 매번 "
        "다른 학교 목록이 나오는 사고가 있었다)"
    ),
    "SIMPLE_GRAPH": (
        "위 두 경우가 아닌 단순 사실 조회 - 특정 대학/학과/전형의 실기유형·재료·일정·"
        "정원 등을 하나만 직접 묻는 질문"
    ),
}


def _classify_route_keyword(query: str, all_universities: List[str]) -> str:
    """Jev Choice 실패 시 폴백 - 기존 순차 키워드 판정을 그대로 재사용한다."""
    if _is_document_writing_help_query_keyword(query):
        return "DOCUMENT_WRITING_HELP"
    if _is_compound_query_keyword(query, all_universities):
        return "COMPLEX_TOOL"
    return "SIMPLE_GRAPH"


def _classify_route(query: str, all_universities: List[str]) -> Dict[str, Any]:
    """반환값: {"route": "DOCUMENT_WRITING_HELP"|"COMPLEX_TOOL"|"SIMPLE_GRAPH",
    "method": "jev_choice"|"keyword_fallback", "model": str|None,
    "confidence": float|None, "probabilities": dict|None} - Evidence Package에
    그대로 기록할 수 있는 형태로 만든다."""
    try:
        from typesafe_sdk import Choice, TypeSafeClient
        client = TypeSafeClient(timeout=_JEV_TIMEOUT_SECONDS)
        model = os.getenv("TYPESAFE_MODEL", "jev-1.13.0")
        resp = client.system_one(
            model=model, state=query,
            questions={"route": Choice(
                instructions="이 질문을 아래 세 경로 중 가장 알맞은 곳으로 분류하십시오.",
                criteria=_ROUTE_CRITERIA,
            )},
        )
        answer = resp.answers["route"]
        return {
            "route": answer.choice, "method": "jev_choice", "model": model,
            "confidence": answer.confidence, "probabilities": answer.probabilities,
        }
    except Exception:
        return {
            "route": _classify_route_keyword(query, all_universities),
            "method": "keyword_fallback", "model": None, "confidence": None, "probabilities": None,
        }


def route_and_answer(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """day54 질의 라우팅 진입점, 2026-09-23 Jev Choice 라우터 통합. /agent-chat이 이
    함수를 호출한다 - 단순 질의는 기존 /qa 파이프라인으로, 복합 질의(비교·일정충돌·
    여러 학교 동시 언급)만 LangGraph 에이전트로, 서류작성법 질의는 review.html로 보낸다."""
    svc = _get_service()
    try:
        all_universities = sorted({u["university"] for u in svc.list_universities()})
    except Exception:
        all_universities = []

    # 2026-09-23 실사용 발견: "지금 색인된 대학이 총 몇 곳이야?" 같은 질문이 LLM/Jev
    # 경로(SIMPLE_GRAPH 또는 COMPLEX_TOOL, 라우팅 신뢰도가 0.5 안팎으로 갈릴 만큼
    # 애매함)를 타면서, 가끔 도구를 잘못 고르거나 컨텍스트가 흔들려 "정보 없음"으로
    # 답하는 걸 실측으로 확인(직전까지 "총 55곳"으로 정확히 답하던 것과 같은 질문).
    # 이건 판단이 필요 없는 정확한 숫자이므로 애초에 LLM을 거치지 않고 결정론적으로
    # 답한다 - 한 번 흔들리면 매번 흔들릴 수 있는 질문 유형이라 LLM 신뢰도 개선보다
    # 이쪽이 100% 안정적이고 무료다.
    # 오탐 방지: "정원 수"/"경쟁률" 등 대학 하나를 특정해 묻는 질문까지 이 결정론적
    # 답변으로 새지 않도록, (a) 색인/등록/적재 같은 "데이터베이스 규모"를 뜻하는
    # 단어가 있고 (b) 질문에 특정 대학명이 등장하지 않을 때만 적용한다.
    _UNIV_COUNT_PATTERN = re.compile(r"(색인|등록|적재)\s*된?\s*대학.{0,8}(몇\s*(곳|개)|개수|수(는|가|\?|$))")
    from services.art_admission_service import resolve_university_mentions_detailed
    detail = resolve_university_mentions_detailed(query, all_universities)
    if _UNIV_COUNT_PATTERN.search(query) and not detail["universities"]:
        return {
            "answer": f"현재 적재된 공식 모집요강 데이터에서 확인된 대학은 총 {len(all_universities)}곳입니다.",
            "context_tracks": [], "context_compatible_tracks": [],
            "context_graph_related": [], "context_raw_excerpts": [],
            "grounded_tracks": [], "grounded_tracks_total": 0,
            "routing": {"route": "SIMPLE_GRAPH", "method": "deterministic_university_count",
                        "model": None, "confidence": None, "probabilities": None},
            "tool_trace": [{
                "tool": "deterministic_university_count",
                "args": {"query": query},
                "result_preview": f"등록 대학 수 질문 감지 - LLM 호출 없이 실제 목록 길이({len(all_universities)})로 즉시 답변",
            }],
        }

    # 결정론적 규칙(Jev보다 먼저, 판단이 아니라 사실): 대학 2곳 이상이 질문에 실제로
    # 언급되면 항상 도구 조합(run_agent)이 필요하다(detail은 위에서 이미 계산됨).
    if len(detail["universities"]) >= 2:
        routing = {"route": "COMPLEX_TOOL", "method": "deterministic_multi_university",
                   "model": None, "confidence": None, "probabilities": None}
    else:
        routing = _classify_route(query, all_universities)

    if routing["route"] == "DOCUMENT_WRITING_HELP" and _is_procedural_not_writing_help(query):
        routing = {"route": "SIMPLE_GRAPH", "method": "deterministic_procedural_override",
                   "model": routing.get("model"), "confidence": routing.get("confidence"),
                   "probabilities": routing.get("probabilities")}

    if routing["route"] == "DOCUMENT_WRITING_HELP":
        review_url = f"{_FO_BASE_URL}/review.html"
        return {
            "answer": (
                "서류 작성 방법은 학교별로 글자 수·블라인드 처리·표절 금지 규정이 달라서, "
                "이 채팅창보다 서류별 규정을 직접 원문에서 찾아 첨삭해주는 전용 화면이 "
                f"더 정확합니다.\n\n[서류 첨삭 화면으로 이동하기]({review_url})"
            ),
            "context_tracks": [], "context_compatible_tracks": [],
            "context_graph_related": [], "context_raw_excerpts": [],
            "grounded_tracks": [], "grounded_tracks_total": 0,
            "routing": routing,
            "tool_trace": [{
                "tool": "redirect_to_document_review",
                "args": {"query": query},
                "result_preview": "서류 작성법 질문 감지 - LLM 호출 없이 서류첨삭 화면(review.html)으로 안내",
            }],
        }

    if routing["route"] == "COMPLEX_TOOL":
        result = run_agent(query, history)
        result["routing"] = routing
        return result

    # SIMPLE_GRAPH
    result = run_qa_pipeline(svc, query, history=history)

    # 프론트(qa.html)의 트레이스 패널과 형식을 맞추되, "도구 선택 없이 즉시 처리했다"는
    # 걸 투명하게 보여준다 - 라우팅 자체도 숨기지 않는다.
    result["tool_trace"] = [{
        "tool": "qa_pipeline",
        "args": {"query": query},
        "result_preview": f"단순 질의로 판단 - 도구 선택 없이 그래프 조회 {len(result.get('context_tracks', []))}건으로 즉시 답변",
    }]
    # run_agent()의 grounded_tracks와 같은 모양으로 맞춰서, qa.html이 경로(단순/복합
    # 질의)와 무관하게 같은 필드 하나로 "지식그래프 근거" 패널을 그릴 수 있게 한다.
    context_tracks = result.get("context_tracks") or []
    result["grounded_tracks"] = [
        {"university": t.get("university"), "department": t.get("department"),
         "track_name": t.get("track_name"), "source_url": t.get("source_url")}
        for t in context_tracks[:20]
    ]
    result["grounded_tracks_total"] = len(context_tracks)
    result["routing"] = routing
    return result


def run_agent(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """질문 하나를 에이전트에게 넘겨, 필요한 도구를 스스로 호출하게 하고 최종 답변과
    "실제로 어떤 도구를 어떤 인자로 불렀는지" 트레이스를 함께 반환한다. 트레이스는
    기존 qa.html의 "그래프 추적 패널"을 대체한다 - 이번엔 진짜 함수 호출 로그라서
    더 투명하다."""
    llm = ChatOpenAI(model=AGENT_MODEL, temperature=0)
    agent = create_react_agent(llm, TOOLS, prompt=_SYSTEM_PROMPT)

    tool_trace = []
    grounded_universities = set()
    # 2026-09-09: "입시 질문 답변이 정말 우리 지식그래프 근거인가"를 화면에서
    # 직접 보여달라는 요청 - 학교명만 모으던 grounded_universities와 별도로,
    # 실제 도구가 반환한 트랙(대학/학과/전형명/원문 링크)을 그대로 모아뒀다가
    # qa.html의 "지식그래프 근거" 패널에 그대로 노출한다(사람이 읽을 수 있는
    # 요약이 아니라 실제 반환 레코드라 설득력이 있다).
    grounded_tracks = []
    grounded_track_keys = set()
    # 2026-09-22: /qa 파이프라인의 _self_check_compat_claim(호환/유사 과잉주장·포기
    # 검사)을 에이전트 경로에도 동일하게 적용하려면 find_compatible_exam_tracks가
    # 반환한 shared_keywords/shared_materials 원본이 필요하다 - grounded_tracks는
    # 화면 표시용으로 필드를 잘라내므로 별도로 원본 그대로 모아둔다.
    context_compatible_tracks: List[Dict[str, Any]] = []
    # 2026-09-23 실사용 발견: text2cypher_query는 매번 질문에 맞춰 즉석에서 다른
    # Cypher를 생성하므로 행(row)의 키 구성이 매번 달라(university/department/
    # track_name 고정 모양이 아님) - 위 grounded_tracks 추출 로직이 이 모양을 인식할
    # 수 없어 "실기고사일이 2개 이상 겹치는 대학이 몇 곳이야?" 같은 질문이 실제로는
    # 그래프에 실시간 쿼리해서 정확히 답했는데도 "근거를 못 찾았다"는 오해를 주는
    # 패널이 뜨고, 답변도 숫자 하나("7곳입니다")뿐이라 사용자가 검증할 길이 없었다
    # (실측 제보: "7곳이 언제 겹치는건데? 정말 7곳이 전부야?"). grounded_tracks로
    # 억지로 맞추는 대신, 실행된 Cypher와 원본 결과 행을 그대로 별도 필드에 남겨서
    # 프론트가 "근거 없음" 대신 "이 쿼리로 직접 조회했다"는 진짜 근거를 보여주게 한다.
    text2cypher_evidence: List[Dict[str, Any]] = []
    # 2026-09-23 실사용 발견: get_calendar가 반환하는 "events"는 university 키가
    # 아니라 "school"(대학명+학과명을 합친 라벨) 키를 쓴다 - 아래 추출 루프가 이
    # 모양을 몰라서 캘린더 도구로 답한 경우 grounded_tracks/grounded_universities가
    # 전부 비어, "지식그래프 근거" 패널이 텅 비고(신뢰도 문제) 자기검증도 그 답변의
    # 학교명을 놓쳤다. all_universities를 _invoke 정의보다 먼저 계산해서 이벤트의
    # school 라벨과 대조할 수 있게 한다.
    all_universities = _all_universities()

    def _add_grounded_track(row: dict):
        key = (row.get("university"), row.get("department"), row.get("track_name"))
        if key in grounded_track_keys or len(grounded_tracks) >= 20:
            return
        grounded_track_keys.add(key)
        grounded_tracks.append({
            "university": row.get("university"), "department": row.get("department"),
            "track_name": row.get("track_name"), "source_url": row.get("source_url"),
        })

    def _invoke(messages) -> str:
        """도구 호출 루프 한 번(초기 또는 재시도)을 실행하고, 그 결과로 tool_trace/
        grounded_tracks/context_compatible_tracks(위 outer 변수들)를 누적한 뒤 최종
        답변 텍스트만 반환한다. 재시도 시에도 이전 호출의 근거가 사라지지 않도록
        outer 변수에 계속 append하는 구조다."""
        result = agent.invoke({"messages": messages})
        out_messages = result["messages"]
        for m in out_messages:
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    tool_trace.append({"tool": tc["name"], "args": tc["args"]})
                    # 2026-09-23 실사용 발견: check_schedule_conflicts/get_calendar/
                    # compare_tracks처럼 "selections" 인자로 학교를 지정해서 호출하는
                    # 도구는, 반환 결과(conflicts 등)가 university 키 없이 "a"/"b"처럼
                    # 합쳐진 문자열만 쓰는 경우가 있어 결과만 봐서는 그 학교가 답변에
                    # 나와도 "환각 의심"으로 오탐됐다(실측: "7곳 어디지?" 되물음에서
                    # check_schedule_conflicts(중앙대,동국대)를 실제로 호출했는데도
                    # 동국대학교가 환각 의심 경고로 뜸). 도구를 실제로 호출할 때 준 인자
                    # 자체가 이미 "이 학교를 진짜로 조회했다"는 증거이므로, 인자에 등장한
                    # 학교명도 바로 근거로 인정한다.
                    args_text = json.dumps(tc.get("args", {}), ensure_ascii=False)
                    for name in all_universities:
                        if name in args_text:
                            grounded_universities.add(name)
            if isinstance(m, ToolMessage):
                content = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
                # Self-RAG 그라운딩용: 이 도구 호출이 실제로 반환한 학교명을 전부 모아둔다
                # (트레이스 패널에 보여줄 미리보기는 300자로 자르지만, 그라운딩 판정은
                # 잘리지 않은 전체 내용으로 해야 한다 - 안 그러면 뒷부분에 있는 학교가
                # 누락돼서 정상 답변까지 "환각 의심"으로 오탐할 수 있다).
                try:
                    parsed = json.loads(content)
                    # recommend_by_grades는 "combo"(선택된 조합), get_competition_rate_ranking은
                    # "ranking" 키를 쓴다 - "results"/"tracks"만 보던 원래 코드는 이 두 도구가
                    # 반환한 학교를 전부 놓쳐서, 정상 답변까지 "환각 의심"으로 오탐했다
                    # (2026-09-14 사용자 실측 제보로 발견 - 스크린샷에서 recommend_by_grades가
                    # 호출됐고 답변의 학교들이 실제로 그 결과 안에 있었는데도 경고가 떴었음).
                    # find_similar_departments는 "similar" 키, find_compatible_exam_tracks는
                    # "compatible" 키, search_document_details는 "excerpts" 키를 쓴다 -
                    # 이 키들을 안 넣으면 해당 도구를 쓴 정상 답변마다 오탐이 재발한다.
                    for row in (parsed.get("results", []) or parsed.get("tracks", [])
                                or parsed.get("combo", []) or parsed.get("ranking", [])
                                or parsed.get("similar", []) or []):
                        if isinstance(row, dict) and row.get("university"):
                            grounded_universities.add(row["university"])
                            _add_grounded_track(row)
                    for row in parsed.get("compatible", []) or []:
                        if isinstance(row, dict) and row.get("university"):
                            grounded_universities.add(row["university"])
                            _add_grounded_track(row)
                            context_compatible_tracks.append(row)
                    for row in parsed.get("excerpts", []) or []:
                        if isinstance(row, dict) and row.get("university"):
                            grounded_universities.add(row["university"])
                    for row in parsed.get("events", []) or []:
                        school = row.get("school") if isinstance(row, dict) else None
                        if school:
                            matched = next((name for name in all_universities if name in school), None)
                            if matched:
                                grounded_universities.add(matched)
                    if parsed.get("university"):
                        grounded_universities.add(parsed["university"])
                        if parsed.get("official_tracks"):
                            for row in parsed["official_tracks"]:
                                if isinstance(row, dict):
                                    _add_grounded_track({**row, "university": parsed["university"]})
                    if "generated_cypher" in parsed and "error" not in parsed:
                        # 2026-09-23 실사용 발견: text2cypher_query 행은 매번 다른 RETURN
                        # 별칭을 쓰므로(university/u.name/school 등 무엇이든 가능) 고정 키로
                        # 못 찾는다. 대신 행 전체를 평문으로 펼쳐서 그 안에 실제 대학명
                        # 문자열이 등장하는지 대조한다 - 자기검증(_self_check)이 이 도구가
                        # 진짜로 찾아온 학교까지 "환각 의심"으로 오탐하는 걸 막는다(실측
                        # 제보: "7곳 어디지?" 되물음에 text2cypher가 정확히 답했는데도
                        # 답변에 나온 7개 대학 중 5개가 전부 환각 의심 경고로 뜸).
                        flat_text = json.dumps(parsed.get("rows", []), ensure_ascii=False)
                        for name in all_universities:
                            if name in flat_text:
                                grounded_universities.add(name)
                        text2cypher_evidence.append({
                            "generated_cypher": parsed.get("generated_cypher"),
                            "rows": parsed.get("rows", [])[:20],
                            "count": parsed.get("count"),
                        })
                except Exception:
                    pass
                if tool_trace and "result_preview" not in tool_trace[-1]:
                    tool_trace[-1]["result_preview"] = content[:300]

        final_answer = out_messages[-1].content if out_messages else ""
        if not isinstance(final_answer, str):
            final_answer = json.dumps(final_answer, ensure_ascii=False)
        return final_answer

    # 2026-09-23 실사용 발견: 채팅창(qa.html)이 같은 브라우저 세션 안에서 쌓인
    # history 전체를 매 요청마다 그대로 보낸다(서버엔 대화기록이 안 남고 브라우저
    # 메모리에만 있음) - 완전히 다른 새 질문("소묘 준비중, 내신 4등급인데 어디 지원
    # 가능해?")을 했는데도 훨씬 이전 턴의 도구 호출 인자(예: 중앙대학교 공간연출전공
    # 실기호환 검색)를 그대로 반복해서 답하는 현상이 실측 확인됨 - 에이전트가 긴
    # history를 few-shot 예시처럼 취급해 이전 턴의 구체적 값에 붙잡힌 것으로 추정.
    # 근본적으로는 "주제 전환 감지"가 맞는 해법이지만, 우선 안전하게 최근 2턴(4개
    # 메시지)으로만 잘라서 무관한 오래된 턴이 새 질문을 오염시킬 여지 자체를 줄인다.
    _MAX_HISTORY_MESSAGES = 4
    trimmed_history = (history or [])[-_MAX_HISTORY_MESSAGES:]
    messages = list(trimmed_history)
    messages.append({"role": "user", "content": query})
    final_answer = _invoke(messages)

    # Self-RAG류 자기검증(day53~54, 2026-09-22 compat_claim 추가): /qa와 동일한
    # 원칙 - 답변에 등장하는 학교명이 실제로 이번 도구 호출 결과 안에 있었는지,
    # "호환"/"유사" 주장이 실제 근거(shared_keywords)로 뒷받침되는지 코드로 재검사한다.
    # 2026-09-09 오탐 수정: 사용자의 질문 원문(query)이나 이전 대화(history)에 이미
    # 등장한 학교명은 grounded로 취급한다 - "이 결과로 질문하기" 기능이 성적 추천의
    # 실제 계산 결과(허구가 아님)를 질문 앞에 붙여 보내는데, 에이전트가 그 학교명을
    # 그대로 답변에서 언급하면 "이번 도구 호출 결과에는 없다"는 이유로 오탐이 났다.
    # (all_universities는 위에서 _invoke 정의 전에 이미 계산해둔 것을 재사용한다.)
    query_text = query + " " + " ".join(str(m.get("content", "")) for m in (history or []))
    for name in all_universities:
        if name in query_text:
            grounded_universities.add(name)

    def _self_check(answer: str) -> List[str]:
        grounding_issues = [
            f"'{name}'가 답변에 등장하지만 이번 도구 호출 결과에는 없었습니다(환각 의심)"
            for name in all_universities if name in answer and name not in grounded_universities
        ]
        return grounding_issues + _self_check_compat_claim(answer, context_compatible_tracks)

    self_check_warnings = _self_check(final_answer)
    # qa_pipeline과 동일하게 문제 발견 시 딱 한 번만 재시도한다(무한루프 방지 - 비용은
    # 최대 2배로만 늘어남). 도구 재호출이 필요할 수도 있으므로 agent.invoke를 처음부터
    # 다시 돈다(단일 LLM 재호출이 아니라 도구 루프 전체 재시도).
    if self_check_warnings:
        retry_messages = messages + [
            {"role": "assistant", "content": final_answer},
            {"role": "user", "content": (
                "[자기검증 실패 - 재작성 필요]\n이전 답변에서 다음 문제가 발견되었습니다:\n- "
                + "\n- ".join(self_check_warnings)
                + "\n위 문제를 고쳐서 규칙을 지키는 답변으로 다시 작성하십시오. 필요하면 도구를 다시 호출해도 됩니다."
            )},
        ]
        try:
            retried = _invoke(retry_messages)
            self_check_warnings = _self_check(retried)
            final_answer = retried
        except Exception:
            pass  # 재시도 실패하면 원래 답변 유지, 아래에서 경고만 표시

    # 에이전트 답변에도 동일한 코드 레벨 가드레일을 적용한다(§ 절대원칙 - 화면마다
    # 따로 지키는 게 아니라 답변 생성 공통 경로 전체에 걸쳐야 한다).
    final_answer, banned_hit = _strip_banned_phrases(final_answer)

    result_payload = {
        "answer": final_answer,
        "model": AGENT_MODEL,
        "tool_trace": tool_trace,
        "grounded_tracks": grounded_tracks,
        "grounded_tracks_total": len(grounded_tracks),
        "text2cypher_evidence": text2cypher_evidence,
    }
    if self_check_warnings or banned_hit:
        result_payload["self_check_warnings"] = self_check_warnings + [f"금지 문구 제거됨: {p}" for p in banned_hit]
    return result_payload
