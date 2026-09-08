# -*- coding: utf-8 -*-
"""
🎯 [미술 실기 입시 도우미] RAG 품질 회귀 평가 (day59~64 RAGAS/가드레일 개념의 경량 자체 구현)
================================================================================
- day59에서 정식으로 배울 RAGAS(Context Precision/Recall, Faithfulness)를 그대로
  쓰려 했으나, 설치된 ragas==0.4.3이 langchain_community의 이미 제거된
  서브모듈(langchain_community.chat_models.vertexai)을 하드 임포트하다가 깨진다
  (langchain_community가 "sunset" 공지된 노후 패키지라 생긴 업스트림 비호환).
  억지로 버전을 낮춰 다른 의존성(day35~42의 langchain-neo4j 등)을 깨뜨리는 대신,
  같은 목적(자동 품질 채점을 배포 파이프라인에 고정)을 달성하는 경량 자체 채점기로
  대체한다 - RAGAS 정식판은 day59 실습에서 별도 가상환경으로 다시 검증한다.

- 두 층으로 나눈다:
  1) 결정적 회귀(모델 호출 없음, 무료·즉시): 이번 세션에서 실제로 두 번 터진
     "재료만 겹치는데 실기종목 일치로 오판" 버그를 고정 케이스로 박아둔다.
  2) LLM-as-Judge Faithfulness(day60 개념, gpt-4o-mini 소액 호출): Q&A 답변이
     실제로 준 context 밖의 사실을 지어냈는지 채점한다. 케이스 수를 일부러
     최소로 유지해 배포마다 드는 비용을 몇 원 단위로 묶어둔다.
================================================================================
"""

import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.art_admission_service import ArtAdmissionService  # noqa: E402
from services.art_admission_llm import _call_llm  # noqa: E402

# (topic_keywords, 반드시 exact로 나와야 하는 학교, 절대 exact로 나오면 안 되는 학교)
# 각 튜플이 이번 세션에서 실제로 터졌던 버그(재료만 겹침 vs 실기유형 자체 일치 혼동)의
# 회귀 케이스다.
EXACT_MATCH_REGRESSION_CASES = [
    ("기초디자인", {"가천대학교", "명지대학교"}, {"가천대학교(회화전공)"}),  # 회화전공(자유표현)이 섞이면 실패
    ("소묘", {"중앙대학교", "동국대학교", "한국예술종합학교"}, set()),
    ("인체수채화", {"경희대학교", "상명대학교"}, {"동국대학교"}),  # 수채화만 겹치는 동국대가 섞이면 실패
]


def test_exact_match_never_includes_material_only_overlaps():
    """day37 온톨로지 시그니처 판정을 배포마다 자동 재검증한다. 사람이 매번 손으로
    Playwright/파이썬 스크립트를 새로 짜서 확인했던 것(이번 세션에 3번 반복)을
    고정 회귀로 박아 이제 배포 전에 자동으로 걸리게 한다."""
    svc = ArtAdmissionService()
    try:
        for keyword, must_include, must_exclude in EXACT_MATCH_REGRESSION_CASES:
            rows = svc.search_tracks_by_prep(topic_keywords=[keyword], material_query="", document_only=False)
            exact_universities = {r["university"] for r in rows if r["match_status"] == "exact"}
            missing = {u for u in must_include if u not in exact_universities}
            assert not missing, f"'{keyword}': exact에 있어야 할 대학이 빠짐 - {missing}"
            # must_exclude는 "학교(학과)" 표기가 섞인 항목이라 학교명만으로는 못 걸러서
            # 재료만 겹치는 개별 트랙이 exact로 승격됐는지 department까지 대조한다.
            for label in must_exclude:
                if "(" in label:
                    uni, dept = label.rstrip(")").split("(")
                    bad = [r for r in rows if r["university"] == uni and r["department"] == dept and r["match_status"] == "exact"]
                    assert not bad, f"'{keyword}': 재료만 겹치는 '{label}'이 exact로 잘못 승격됨"
        print(f"✅ test_exact_match_never_includes_material_only_overlaps passed! ({len(EXACT_MATCH_REGRESSION_CASES)}개 키워드 케이스 전수 통과)")
    finally:
        svc.close()


def test_qa_search_and_agent_search_agree():
    """대학찾기(search_tracks_by_prep)와 입시질문(build_llm_context의 exam_type_keyword_match)
    두 경로의 판정이 항상 일치하는지 확인한다 - 이번 세션에서 실제로 두 경로가 어긋나서
    (조사 파싱 버그, substring 오탐지 버그) 두 번 잡았던 문제의 재발 방지."""
    svc = ArtAdmissionService()
    try:
        topics = svc.list_exam_topic_keywords()
        assert topics, "실기유형 키워드 목록이 비어있음 - 데이터 문제"
        for kw in topics:
            search_set = {
                (r["university"], r["department"])
                for r in svc.search_tracks_by_prep(topic_keywords=[kw], material_query="", document_only=False)
                if r["match_status"] == "exact"
            }
            ctx, _ = svc.build_llm_context(f"{kw} 준비 중인데 어디서 볼 수 있어?")
            qa_set = {(t["university"], t["department"]) for t in ctx if t["exam_type_keyword_match"]}
            assert search_set == qa_set, f"'{kw}' 판정 불일치 - 대학찾기={search_set}, Q&A={qa_set}"
        print(f"✅ test_qa_search_and_agent_search_agree passed! ({len(topics)}개 키워드 전수 일치)")
    finally:
        svc.close()


_FAITHFULNESS_JUDGE_PROMPT = """당신은 RAG 답변 품질 채점기입니다(day60 LLM-as-Judge 개념).
"context"(JSON, 사실로 확인된 데이터)와 "answer"(생성된 답변)를 비교해서, answer에 등장하는
구체적 사실(학교명·숫자·날짜)이 전부 context 안에 실제로 있는 값인지 판정하십시오.
context에 없는 사실을 하나라도 지어냈으면 grounded=false, 전부 context 그대로면 grounded=true.
반드시 JSON만 답하십시오: {"grounded": true 또는 false, "reason": "한 줄 이유"}"""


def _judge_faithfulness(context: list, answer: str) -> dict:
    user_prompt = f"context:\n{json.dumps(context, ensure_ascii=False)}\n\nanswer:\n{answer}"
    raw = _call_llm(_FAITHFULNESS_JUDGE_PROMPT, user_prompt, "gpt-4o-mini", temperature=0.0)
    cleaned = raw.strip().strip("`")
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:]
    return json.loads(cleaned)


def test_qa_answer_faithfulness_llm_judge():
    """day60 LLM-as-Judge 개념의 최소 구현. 실제 /qa 파이프라인과 동일한 함수
    (build_llm_context + answer_with_llm)를 고정 질문 2건에 돌리고, 답변이
    준 context 밖 사실을 지어내지 않았는지 별도 LLM 채점기로 확인한다.
    비용: gpt-4o-mini 호출이 질문당 2회(답변 생성+채점) - 요청당 몇 원 수준."""
    from services.art_admission_llm import answer_with_llm

    svc = ArtAdmissionService()
    try:
        fixed_questions = ["소묘 준비 중인데 어느 학교 전형에서 볼 수 있어?", "인체수채화 준비 중인데 어디서 볼 수 있어?"]
        for q in fixed_questions:
            context_tracks, context_estimates = svc.build_llm_context(q)
            result = answer_with_llm(context_tracks, context_estimates, q, model_id="gpt-4o-mini")
            verdict = _judge_faithfulness(context_tracks, result["answer"])
            assert verdict.get("grounded") is True, f"'{q}' 답변이 근거 없는 사실을 포함함 - {verdict.get('reason')}"
        print(f"✅ test_qa_answer_faithfulness_llm_judge passed! ({len(fixed_questions)}개 질문 전부 grounded=true)")
    finally:
        svc.close()


if __name__ == "__main__":
    test_exact_match_never_includes_material_only_overlaps()
    test_qa_search_and_agent_search_agree()
    test_qa_answer_faithfulness_llm_judge()
    print("🎉 ALL ART ADMISSION RAG EVAL TESTS PASSED!")
