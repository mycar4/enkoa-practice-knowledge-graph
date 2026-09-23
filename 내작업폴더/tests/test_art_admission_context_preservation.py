# -*- coding: utf-8 -*-
"""
[컨텍스트 좁히기 근거 보존 회귀 테스트] - day48(리랭킹·컨텍스트 압축) 학습 결과 적용

왜 이 파일이 필요한가:
  LLM에 넣기 전 컨텍스트를 좁히는(=압축하는) 단계는 비용 최적화가 아니라 **동작 조건**이다.
  299건을 통째로 넣으면 LLM 호출 자체가 실패한다(2026-09-23 실장애).
  그런데 좁히기는 동시에 **오답 유발 지점**이기도 하다 - 근거를 잘라내면 LLM은
  "그 사실은 없다"고 합리적으로(그러나 틀리게) 추론한다.

  day48 교재 제작 중 실측한 사례:
      압축 전(1,361토큰): "3절 켄트지는 실기고사 당일 지급되는 재료" (정답)
      압축 후(  183토큰): "3절 켄트지는 지급되지 않습니다"           (오답)
      -> 토큰 86.6% 절감에 성공했지만 답이 뒤집혔다.

  오늘 우리 서비스에서 실제로 난 같은 유형의 사고:
      - "색인된 대학 총 몇 곳" -> 표본 6곳만 보고 "6곳"이라 답함 (실제 55곳)
      - "홍대 실기 날짜"       -> 실기시험이 없는 전형의 면접일을 실기일로 답함

  이 테스트들은 그 회귀를 **배포 전에** 잡는다. LLM을 호출하지 않으므로 비용이 없고
  결정적이다(ci_quality_gate 편입 조건).
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.art_admission_agent import (  # noqa: E402
    narrow_context, is_pure_gratitude_message, extract_grounding_from_tool_result,
)
from services.art_admission_service import ArtAdmissionService  # noqa: E402

_SERVICE = None


def _svc() -> ArtAdmissionService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ArtAdmissionService()
    return _SERVICE


def test_topic_narrowing_keeps_every_matched_track():
    """실기유형 질의에서 좁히기가 '일치하는 전형'을 하나도 버리지 않아야 한다.

    회귀 대상 사고(2026-09-23): "소묘로 지원 가능한 학교"를 물었는데 원문검색 기반
    재좁히기가 의미상 비슷한 엉뚱한 4~5개 학교로 컨텍스트를 좁혀버려, 정작 소묘
    전형이 있는 중앙대/한예종 등이 통째로 사라졌다.
    """
    svc = _svc()
    query = "소묘로 지원 가능한 학교 알려줘"
    tracks, estimates = svc.build_llm_context(query)
    topics = sorted(set(svc.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)

    matched_before = {
        (t["university"], t["department"], t.get("track_name"))
        for t in tracks if t.get("exam_type_keyword_match")
    }
    assert matched_before, "테스트 전제 실패: '소묘' 일치 전형이 0건이면 검증이 무의미하다"

    # 원문검색이 엉뚱한 학교를 물고 온 최악의 상황을 일부러 만든다
    noise_universities = sorted({t["university"] for t in tracks})[:2]
    context_raw = [{"university": u, "text": "무관한 원문"} for u in noise_universities]

    narrowed, _ = narrow_context(
        query, tracks, estimates,
        mentioned=[], context_raw=context_raw, canonical_topics=topics,
    )
    matched_after = {
        (t["university"], t["department"], t.get("track_name"))
        for t in narrowed if t.get("exam_type_keyword_match")
    }

    lost = matched_before - matched_after
    assert not lost, (
        f"좁히기가 일치 전형 {len(lost)}건을 버렸습니다(근거 유실 → 오답 위험): "
        f"{sorted(lost)[:5]}"
    )


def test_narrowing_never_invents_tracks():
    """좁히기 결과는 반드시 입력의 부분집합이어야 한다(없던 전형 생성 금지).

    day48 불변식 '압축은 원문에 없는 것을 만들지 않는다'의 서비스 버전이다.
    """
    svc = _svc()
    query = "수채화 준비하는데 어디 지원할 수 있어?"
    tracks, estimates = svc.build_llm_context(query)
    topics = sorted(set(svc.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)

    before = {(t["university"], t["department"], t.get("track_name")) for t in tracks}
    narrowed, narrowed_est = narrow_context(
        query, tracks, estimates, mentioned=[], context_raw=[], canonical_topics=topics,
    )
    after = {(t["university"], t["department"], t.get("track_name")) for t in narrowed}

    assert after <= before, f"입력에 없던 전형이 생성됨: {sorted(after - before)[:5]}"
    assert len(narrowed) <= len(tracks), "좁히기 후 건수가 늘어남"
    assert len(narrowed_est) <= len(estimates), "추정치 건수가 늘어남"


def test_narrowing_actually_reduces_payload():
    """좁히기가 실제로 페이로드를 줄여야 한다(안 줄이면 LLM 호출이 실패한다).

    회귀 대상 사고(2026-09-23): 재좁히기를 '건너뛰기'로 고쳤더니 299건 전체가
    그대로 LLM에 실려 프로덕션에서 반복적으로 호출 실패가 났다.
    """
    svc = _svc()
    query = "기초디자인으로 지원 가능한 학교 알려줘"
    tracks, estimates = svc.build_llm_context(query)
    topics = sorted(set(svc.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)

    narrowed, _ = narrow_context(
        query, tracks, estimates, mentioned=[], context_raw=[], canonical_topics=topics,
    )
    assert len(narrowed) < len(tracks), (
        f"좁히기가 전혀 일어나지 않았습니다({len(tracks)}건 그대로). "
        "전체 전형이 LLM 페이로드에 실려 호출 실패 위험이 있습니다."
    )
    # 전형 하나도 안 남기면 근거 0건이 되어 '정보 없음'만 답하게 된다
    assert narrowed, "좁히기 결과가 0건입니다(근거 전멸)"


def test_school_specific_query_is_not_narrowed_away():
    """학교를 콕 집어 물으면 그 학교 전형이 좁히기로 사라지면 안 된다."""
    svc = _svc()
    query = "홍익대학교 전형 알려줘"
    tracks, estimates = svc.build_llm_context(query)
    topics = sorted(set(svc.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)

    hongik_before = [t for t in tracks if t["university"] == "홍익대학교"]
    assert hongik_before, "테스트 전제 실패: 홍익대 전형이 컨텍스트에 없음"

    narrowed, _ = narrow_context(
        query, tracks, estimates,
        mentioned=["홍익대학교"], context_raw=[], canonical_topics=topics,
    )
    hongik_after = [t for t in narrowed if t["university"] == "홍익대학교"]
    assert len(hongik_after) == len(hongik_before), (
        f"학교 지정 질의인데 해당 학교 전형이 {len(hongik_before)}건 -> "
        f"{len(hongik_after)}건으로 줄었습니다"
    )


def test_practical_exam_date_rule_exists_in_prompts():
    """'실기 날짜' 질문에 면접일을 실기일로 답하지 않도록 하는 규칙이 살아있어야 한다.

    회귀 대상 사고(2026-09-23): 홍익대 미술우수자전형은 실기시험이 없고
    미술활동보고서 서류평가+면접뿐인데, 그 면접일을 "실기 날짜"라고 안내했다.
    수험생이 실기 준비 일정을 잘못 잡을 수 있는 위험한 오답이었다.
    """
    from services.art_admission_agent import _SYSTEM_PROMPT
    from services.art_admission_llm import _QA_SYSTEM_PROMPT

    for name, prompt in (("run_agent", _SYSTEM_PROMPT), ("qa_pipeline", _QA_SYSTEM_PROMPT)):
        assert "exam_type_name" in prompt, f"{name} 프롬프트에 exam_type_name 확인 규칙이 없음"
        assert "면접" in prompt and "실기" in prompt, (
            f"{name} 프롬프트에 실기/면접 구분 규칙이 없습니다 - "
            "면접일을 실기일로 답하는 사고가 재발할 수 있습니다"
        )


def test_aggregate_count_uses_full_registry_not_sample():
    """'색인된 대학 몇 곳' 질의는 표본이 아니라 전체 등록 수로 답해야 한다.

    회귀 대상 사고(2026-09-23): 컨텍스트에 우연히 들어온 5~6개 대학만 세어
    "총 6곳"이라고 답했다(실제 55곳). 좁혀진 컨텍스트를 전체로 착각한 전형적 사고다.
    """
    from services.art_admission_agent import route_and_answer

    svc = _svc()
    actual_total = len({u["university"] for u in svc.list_universities()})
    result = route_and_answer("2027학년도 기준 지금 색인된 대학이 총 몇 곳이야?")

    assert result["routing"]["method"] == "deterministic_university_count", (
        f"대학 수 질의가 결정론적 경로를 타지 않았습니다: {result['routing']}"
    )
    assert str(actual_total) in result["answer"], (
        f"실제 등록 대학 수({actual_total})가 답변에 없습니다: {result['answer'][:120]}"
    )


def test_gratitude_short_circuit_matches_only_pure_thanks():
    """순수 감사 인사만 도구/LLM 없이 즉시 답해야 하고, 진짜 질문은 절대 걸러선 안 된다.

    회귀 대상 사고(2026-09-23, GPT/Antigravity QC 양쪽에서 독립 발견): "고맙다
    도움 많이 됐어"가 SIMPLE_GRAPH로 흘러들어가 키워드 없는 기본 컨텍스트(예:
    경기대학교 트랙들)를 붙잡고 무관한 "출처:"를 인용했다. 반대로 이 패턴이
    너무 넓으면 "고맙다는데 그럼 소묘는 어디서 봐?"처럼 감사+질문이 섞인 문장을
    질문 없이 그냥 인사로 처리해버리는 새 사고를 만들 수 있다 - 양방향을 검증한다.
    """
    pure_gratitude = [
        "고맙다 도움 많이 됐어", "감사합니다", "정말 고마워요!",
        "고마워요 ㅎㅎ", "thanks", "Thank you!",
    ]
    for q in pure_gratitude:
        assert is_pure_gratitude_message(q), f"순수 감사 인사를 놓쳤습니다: {q!r}"

    mixed_with_question = [
        "고맙다 근데 하나만 더 물어볼게 중앙대 실기 날짜",
        "감사합니다 그런데 홍익대는요?",
        "고마운데 소묘로 지원 가능한 학교도 알려줄 수 있어?",
    ]
    for q in mixed_with_question:
        assert not is_pure_gratitude_message(q), (
            f"질문이 섞인 문장을 순수 인사로 오판했습니다(실제 질문이 묵살됨): {q!r}"
        )

    unrelated_questions = [
        "중앙대학교 실기 준비물이 뭐야?",
        "국어 3등급인데 어디 지원 가능해?",
    ]
    for q in unrelated_questions:
        assert not is_pure_gratitude_message(q), f"무관한 질문을 감사 인사로 오판했습니다: {q!r}"


def test_grounding_extraction_known_tool_shapes():
    """도구별 반환 JSON 모양에서 그라운딩(대학명/전형)이 빠짐없이 뽑혀야 한다.

    오늘 하루 실측으로 확인된 3개 도구의 실제 반환 모양을 그대로 재현해서 검증한다.
    새 도구를 추가하거나 반환 키를 바꿀 때 이 테스트에 그 모양을 추가하면,
    같은 유형의 그라운딩 누락/오탐 사고를 배포 전에 잡는다.
    """
    all_universities = ["중앙대학교", "홍익대학교", "숭실대학교"]

    # 1) get_university_info: {"university":..., "tracks":[...]} - 각 track 행에는
    #    university 키가 없다(상위에만 있음). 이걸 놓쳐서 이 도구를 쓴 답변마다
    #    "근거를 못 찾았다" 패널이 잘못 떴다(Antigravity QC 실측 발견).
    parsed = {
        "university": "중앙대학교",
        "count": 1,
        "tracks": [{"department": "공간연출전공", "track_name": "실기형", "source_url": "https://x"}],
    }
    result = extract_grounding_from_tool_result(parsed, all_universities)
    assert "중앙대학교" in result["universities"]
    assert len(result["tracks"]) == 1, "get_university_info의 tracks 키가 그라운딩에 반영되지 않았습니다"
    assert result["tracks"][0]["university"] == "중앙대학교"

    # 2) get_calendar: events[].school은 university 키가 아니라 "학교+학과" 합친 라벨.
    parsed = {"events": [{"school": "홍익대학교 미술대학", "date": "2026-11-28"}]}
    result = extract_grounding_from_tool_result(parsed, all_universities)
    assert "홍익대학교" in result["universities"], "get_calendar의 school 라벨에서 대학명을 못 뽑았습니다"

    # 3) text2cypher_query: RETURN 별칭이 매번 달라 고정 키가 없다 - rows 전체를
    #    평문으로 펼쳐 실제 대학명 문자열이 등장하는지로 판정해야 한다.
    parsed = {
        "generated_cypher": "MATCH (u:Admission_University) RETURN u.name AS uni",
        "rows": [{"uni": "숭실대학교"}, {"uni": "홍익대학교"}],
        "count": 2,
    }
    result = extract_grounding_from_tool_result(parsed, all_universities)
    assert result["universities"] == {"숭실대학교", "홍익대학교"}, (
        "text2cypher 가변 키에서 대학명을 못 뽑았습니다(환각 의심 오탐 재발 위험)"
    )
    assert result["text2cypher_evidence"] is not None
    assert result["text2cypher_evidence"]["count"] == 2

    # 4) error가 있는 text2cypher 결과는 근거로 인정하면 안 된다(실패한 쿼리).
    parsed_error = {"generated_cypher": "INVALID", "error": "스키마에 없는 라벨"}
    result = extract_grounding_from_tool_result(parsed_error, all_universities)
    assert result["text2cypher_evidence"] is None, "실패한 쿼리를 근거로 잘못 인정했습니다"

    # 5) find_compatible_exam_tracks: "compatible" 키는 그라운딩과 별도로
    #    context_compatible_tracks에도 원본 그대로 쌓여야 한다(과잉주장 자기검증용).
    parsed = {"compatible": [{"university": "중앙대학교", "shared_keywords": ["소묘"]}]}
    result = extract_grounding_from_tool_result(parsed, all_universities)
    assert "중앙대학교" in result["universities"]
    assert len(result["compatible"]) == 1 and result["compatible"][0]["shared_keywords"] == ["소묘"]


def test_duplicate_track_name_disambiguation_rule_exists_in_prompts():
    """같은 대학·같은 전형명이 단과대학별로 날짜가 다를 때 구분하라는 규칙이 살아있어야 한다.

    회귀 대상 사고(2026-09-23): 홍익대학교 "미술우수자전형"이 미술대학/조형대학에
    각각 다른 날짜로 존재하는데, 연속 질문에 답변마다 다른 날짜가 나와 마치
    시스템이 오락가락하는 것처럼 보였다.
    """
    from services.art_admission_agent import _SYSTEM_PROMPT
    from services.art_admission_llm import _QA_SYSTEM_PROMPT

    for name, prompt in (("run_agent", _SYSTEM_PROMPT), ("qa_pipeline", _QA_SYSTEM_PROMPT)):
        assert "단과대학" in prompt or "department" in prompt.lower(), (
            f"{name} 프롬프트에 동명 전형 구분(단과대학별 분리) 규칙이 없습니다"
        )


def test_text2cypher_excludes_document_only_tracks_from_practical_ranking():
    """text2cypher 생성 규칙에 '실기전형' 질문에서 서류전형을 제외하라는 규칙이 있어야 한다.

    회귀 대상 사고(2026-09-23): "정원이 제일 적은 실기전형은?" 질문에 실기 자체가
    없는 학생부종합 전형을 "실기전형"으로 집계해 잘못 답했다.
    """
    from services.art_admission_agent import _CYPHER_GEN_PROMPT

    assert "실기 없음" in _CYPHER_GEN_PROMPT or "학생부" in _CYPHER_GEN_PROMPT, (
        "Cypher 생성 프롬프트에 서류전형 제외 규칙이 없습니다 - "
        "'실기전형' 집계 질문에 서류전형이 섞여 들어올 수 있습니다"
    )


def test_text2cypher_excludes_portfolio_and_non_practical_markers():
    """'실기전형' 랭킹에서 포트폴리오·구술면접·비실기 전형도 제외해야 한다.

    회귀 대상 사고(2026-09-23 GPT QC 재검수): "정원이 제일 적은 실기전형은?" 질문에
    국민대 "미술·조형 특기자전형"(exam_type_name="포트폴리오 기반 구술면접" - 현장
    실기시험 없이 서류+면접으로만 평가)이 실기전형으로 잘못 집계됐다. "학생부"로
    시작하지 않아 기존 규칙(실기 없음/해당 없음/학생부 시작)만으로는 안 걸러졌다.
    """
    from services.art_admission_agent import _CYPHER_GEN_PROMPT

    for marker in ("포트폴리오", "비실기"):
        assert marker in _CYPHER_GEN_PROMPT, (
            f"Cypher 생성 프롬프트에 '{marker}' 제외 규칙이 없습니다 - "
            "현장 실기시험이 없는 전형이 '실기전형' 집계에 섞여 들어올 수 있습니다"
        )


def test_document_track_category_recognizes_non_practical_marker():
    """exam_type_name이 '비실기 (학생부 100%)'인 트랙은 academic_record로 분류돼
    성적 추천에서 실기종목 필터링 시 제외돼야 한다.

    회귀 대상 사고(2026-09-23 GPT QC 재검수): 목원대 미술교육과 "교과전형"
    (exam_type_name="비실기 (학생부 100%)")이 "소묘 준비 중" 학생의 성적 추천
    목록에 그대로 섞여 나왔다. 이 exam_type_name에는 기존 분류 마커
    ("학생부교과"/"학생부종합"/"포트폴리오"/"미술활동보고서"/"서류평가") 중
    무엇도 없어 분류를 통과해버렸다(is_doc=False로 오판정).
    """
    from services.art_admission_service import ArtAdmissionService

    assert ArtAdmissionService._document_track_category("비실기 (학생부 100%)") == "academic_record", (
        "'비실기' 표기 전형이 실기 없는 전형으로 분류되지 않았습니다 - "
        "실기종목 기반 추천/검색에서 걸러지지 않고 섞여 나올 수 있습니다"
    )
    # 진짜 실기전형까지 잘못 걸러지면 안 된다(과잉 필터링 회귀 방지)
    assert ArtAdmissionService._document_track_category(
        "소묘(정물,인체)/수채화(인물)/수묵담채화(정물)/모델인물두상/기초디자인 중 택1"
    ) is None, "진짜 실기전형이 비실기로 잘못 분류됐습니다"


def test_dead_jev_compound_query_function_removed():
    """죽은 코드 정리 회귀: Noul 기반 _is_compound_query가 다시 생기지 않아야 한다.

    회귀 배경(2026-09-23 리포트 검토): 외부 리포트가 이 함수(art_admission_agent.py
    구버전 L95-120)를 "5대 핵심 관문 중 하나"로 보고했지만, 실제로는 day54 Jev
    Choice 라우터(_classify_route) 도입 이후 이 함수를 호출하는 곳이 코드 어디에도
    없었다(폴백 경로도 키워드 전용 _is_compound_query_keyword를 씀). 죽은 코드가
    "살아있는 관문"으로 잘못 보고될 만큼 헷갈리는 상태였으므로 삭제했다 - 다시
    추가된다면 같은 혼동이 재발한다는 뜻이므로 이 테스트가 잡는다.
    """
    import services.art_admission_agent as agent_module

    assert not hasattr(agent_module, "_is_compound_query"), (
        "_is_compound_query(Noul 버전, 미사용 죽은 코드)가 다시 추가됐습니다 - "
        "실제로 호출하는 곳이 없으면 키워드 폴백(_is_compound_query_keyword)만 남기고 정리하십시오"
    )


def test_route_classifier_falls_back_on_low_confidence_or_thin_margin():
    """Jev Choice 라우팅이 동전 던지기 수준으로 애매하면 키워드 폴백으로 넘어가야 한다.

    회귀 대상(2026-09-23 리포트 검토에서 확인된 실제 갭): _classify_route가
    confidence/probabilities를 반환값에 담기만 하고 실제로는 한 번도 검사하지
    않았다. "COMPLEX_TOOL 0.51 vs SIMPLE_GRAPH 0.48"처럼 1·2위 확률차가 0.03밖에
    안 나는 판정까지 그대로 채택돼, 같은 종류의 질문이 턴마다 다른 경로로 갈리는
    사고로 이어졌다. Jev Choice를 실제로 부르지 않고 TypeSafeClient.system_one만
    가짜 응답으로 교체해서(무료) 가드 로직만 검증한다.
    """
    from unittest.mock import patch, MagicMock
    from services.art_admission_agent import _classify_route

    def _fake_response(choice, confidence, probabilities):
        answer = MagicMock(choice=choice, confidence=confidence, probabilities=probabilities)
        resp = MagicMock()
        resp.answers = {"route": answer}
        return resp

    # 1) 신뢰도 낮음(0.27) + 확률차 얇음(0.03) -> Jev 판정을 버리고 키워드 폴백으로
    with patch(
        "typesafe_sdk.TypeSafeClient.system_one",
        return_value=_fake_response("COMPLEX_TOOL", 0.27, {"COMPLEX_TOOL": 0.51, "SIMPLE_GRAPH": 0.48, "DOCUMENT_WRITING_HELP": 0.01}),
    ):
        result = _classify_route("수채화로 지원 가능한 학교 알려줘", ["중앙대학교"])
    assert result["method"] == "keyword_fallback_low_confidence", (
        f"애매한 Jev 판정을 그대로 채택했습니다(가드 미작동): {result}"
    )

    # 2) 신뢰도 높음(0.94) + 확률차 큼 -> Jev 판정을 그대로 신뢰해야 한다(과잉 폴백 방지)
    with patch(
        "typesafe_sdk.TypeSafeClient.system_one",
        return_value=_fake_response("SIMPLE_GRAPH", 0.94, {"SIMPLE_GRAPH": 0.95, "COMPLEX_TOOL": 0.04, "DOCUMENT_WRITING_HELP": 0.01}),
    ):
        result = _classify_route("중앙대학교 실기 준비물이 뭐야?", ["중앙대학교"])
    assert result["method"] == "jev_choice", (
        f"신뢰도 높은 판정까지 불필요하게 폴백시켰습니다(과잉 가드): {result}"
    )
    assert result["route"] == "SIMPLE_GRAPH"


def test_self_check_numeric_claims_flags_dates_and_quotas_not_in_context():
    """답변에 등장하는 날짜/정원이 조회 근거 어디에도 없으면 환각 의심으로 잡아야 한다.

    회귀 배경(2026-09-23 리포트 검토 개선4 - 팩트 왜곡 검증 확대): 기존
    _self_check_compat_claim은 '호환/유사' 주장에만 좁게 걸려 있었다. 정원/일정도
    답변에 그대로 노출되는 구체적 사실이라 같은 위험(근거 없는 값을 단정)이
    있는데 검증 대상이 아니었다.
    """
    from services.art_admission_llm import _self_check_numeric_claims

    context_tracks = [{
        "university": "중앙대학교", "quota": 5,
        "exam_dates": ["2026-10-11"], "application_start": "2026-09-08",
    }]

    # 근거에 없는 날짜/정원을 답변이 확언하면 잡아야 한다
    bad_answer = "중앙대학교 공간연출전공은 정원 12명이며 실기고사는 2026-11-30입니다."
    issues = _self_check_numeric_claims(bad_answer, context_tracks, [])
    assert any("2026-11-30" in i for i in issues), f"근거에 없는 날짜를 못 잡았습니다: {issues}"
    assert any("12명" in i for i in issues), f"근거에 없는 정원을 못 잡았습니다: {issues}"

    # 근거와 일치하는 값은 오탐하면 안 된다
    good_answer = "중앙대학교 공간연출전공은 정원 5명이며 실기고사는 2026-10-11입니다."
    assert _self_check_numeric_claims(good_answer, context_tracks, []) == [], (
        "근거와 일치하는 값을 잘못 환각 의심으로 잡았습니다(과잉탐지)"
    )

    # 원문 발췌(context_raw_excerpts)에 등장하는 날짜는 정당한 근거이므로 오탐하면 안 된다
    raw_only_answer = "관련 공지에 따르면 2026-12-01에 추가 안내가 있을 예정입니다."
    excerpts = [{"text": "...2026-12-01 추가 공지 예정..."}]
    assert _self_check_numeric_claims(raw_only_answer, context_tracks, excerpts) == [], (
        "원문 발췌에만 있는 정당한 날짜를 환각 의심으로 오탐했습니다"
    )


def test_recommend_universities_topic_filter_is_track_level_not_department_level():
    """실기종목 필터는 '학과'가 아니라 '전형(트랙)' 단위로 걸려야 한다.

    회귀 대상(2026-09-23 GPT QC 재검수, 어제 fix로 안 잡힌 재발): 목원대학교
    미술교육과는 트랙이 두 개다 - "실기교과전형"(소묘 실제로 요구, exact match)과
    "교과전형"(exam_type_name="비실기 (학생부 100%)", 실기 없음). recommend_universities()의
    topic_keywords 필터가 (university, campus, department) 3개 키로만 걸러서,
    같은 학과 안에 하나라도 일치하는 트랙이 있으면 그 학과의 다른(실기 없는) 트랙까지
    같이 통과시켰다 - "소묘 준비 중"인 학생 추천에 실기가 아예 없는 전형이 섞여
    나온 근본 원인. track_name까지 키에 넣어야 트랙 단위로 정확히 걸러진다.
    """
    svc = _svc()
    grades = [{"subject_group": "국어", "grade": 4, "credit": 4}]
    results = svc.recommend_universities(grades, topic_keywords=["소묘"])
    mokwon_academic_record = [
        r for r in results
        if r["university"] == "목원대학교" and r["department"] == "미술교육과"
        and (r.get("exam_type_name") or "").strip() == "비실기 (학생부 100%)"
    ]
    assert not mokwon_academic_record, (
        f"실기 없는 목원대 교과전형이 '소묘' 필터를 통과했습니다: {mokwon_academic_record}"
    )
    # 같은 학과의 실제 실기전형(실기교과전형)까지 잘못 걸러지면 안 된다(과잉 필터링 회귀 방지)
    mokwon_practical = [
        r for r in results
        if r["university"] == "목원대학교" and r["department"] == "미술교육과"
        and "소묘" in (r.get("exam_type_name") or "")
    ]
    assert mokwon_practical, "목원대 미술교육과의 진짜 소묘 실기전형까지 걸러졌습니다(과잉 필터링)"


def test_university_detail_returns_empty_official_tracks_for_unknown_university():
    """존재하지 않는 대학을 조회하면 official_tracks가 비어 있어야 한다(API의 404
    판정 근거).

    회귀 대상(2026-09-23 GPT QC 재검수): api_art_admission.py의 university_detail()이
    `if not detail`로 404를 판정했는데, get_university_detail()은 학교를 못 찾아도
    official_tracks/estimates_by_track이 빈 리스트인 채로 다른 키(region, college_type)를
    가진 non-empty dict를 반환하므로 "if not detail"이 항상 False가 되어 404 분기가
    한 번도 실행되지 않았다(존재하지 않는 대학도 HTTP 200 + 빈 목록으로 응답).
    API 레이어는 official_tracks 유무로 404를 판정하도록 고쳤다 - 이 테스트는 그
    판정 근거가 되는 서비스 레벨 반환값 자체를 검증한다.
    """
    svc = _svc()
    detail = svc.get_university_detail("존재안하는대학교12345")
    assert detail.get("official_tracks") == [], (
        f"존재하지 않는 대학인데 official_tracks가 비어있지 않습니다: {detail.get('official_tracks')}"
    )
    # 실존 대학은 official_tracks가 채워져야 한다(대조군 - 404 조건이 정상 대학까지
    # 걸러버리는 과잉탐지 방지)
    real = svc.get_university_detail("홍익대학교")
    assert real.get("official_tracks"), "실존 대학인데 official_tracks가 비어있습니다"


def test_self_check_practical_date_contradiction_catches_self_contradiction():
    """'실기 날짜'와 '실기시험 없음'이 같은 답변에 함께 있으면 자기모순으로 잡아야 한다.

    회귀 대상(2026-09-23 GPT QC 재검수): "홍익대학교 미술우수자전형 실기 날짜
    알려줘" 질문에 "실기시험: 없음 (서류평가 및 면접)"이라고 정직하게 밝히면서도
    섹션 제목은 여전히 "실기 날짜는 다음과 같습니다"였다. 프롬프트 규칙을 이미
    명시했는데도 절반만 지키는 패턴이 반복돼 결정론적 검증을 추가했다.
    """
    from services.art_admission_llm import _self_check_practical_date_contradiction

    contradictory = (
        "홍익대학교 미술우수자전형의 실기 날짜는 다음과 같습니다:\n"
        "- 미술대학: 2026-12-05~06\n"
        "실기시험: 없음 (서류평가 및 면접)"
    )
    issues = _self_check_practical_date_contradiction(contradictory)
    assert issues, "'실기 날짜'와 '실기시험 없음'이 공존하는 자기모순을 못 잡았습니다"

    # 실기시험이 실제로 있는 전형에 "실기 날짜"를 쓰는 건 정상이므로 오탐하면 안 된다
    normal = "중앙대학교 공간연출전공의 실기 날짜는 2026-10-11입니다."
    assert _self_check_practical_date_contradiction(normal) == [], (
        "정상적인 '실기 날짜' 답변을 잘못 자기모순으로 오탐했습니다"
    )

    # "실기 날짜"라는 표현 자체가 없으면 당연히 체크 대상이 아니다
    unrelated = "이 전형은 면접일이 2026-11-07입니다."
    assert _self_check_practical_date_contradiction(unrelated) == []


def test_force_fix_practical_date_wording_survives_llm_dodging_disclaimer():
    """LLM 재시도가 'disclaimer만 지우고 헤더는 안 고치는' 식으로 자기검증을
    회피해도, 그라운딩 근거를 직접 보고 코드가 정정 문구를 강제로 붙여야 한다.

    회귀 대상(2026-09-23 GPT QC 재검수 후속): 자기모순 self-check가 재시도를
    걸었더니, LLM이 "실기시험: 없음" disclaimer만 지우고 "실기 날짜"라는 잘못된
    제목은 그대로 둔 채 재응답했다 - 재시도 전보다 더 위험해졌다(경고 없이
    면접일을 실기 날짜로 단정). 텍스트 자기모순만 보는 self-check로는 이 회피를
    못 막으므로, context_tracks의 exam_type_name을 직접 봐서 실기시험이 있는
    전형이 하나도 없는데 '실기 날짜' 표현이 남아있으면 LLM 출력과 무관하게
    코드가 정정 문구를 강제로 덧붙인다.
    """
    from services.art_admission_llm import _force_fix_practical_date_wording

    dodged_answer = (
        "홍익대학교 미술우수자전형의 실기 날짜는 다음과 같습니다:\n"
        "- 미술대학: 2026-12-05~06\n"
        "- 조형대학: 2026-11-28~29"
    )
    non_practical_tracks = [
        {"university": "홍익대학교", "department": "미술대학", "exam_type_name": "미술활동보고서 서류평가 및 심층 면접평가"},
        {"university": "홍익대학교", "department": "조형대학", "exam_type_name": "미술활동보고서 서류평가 및 심층 면접평가"},
    ]
    fixed = _force_fix_practical_date_wording(dodged_answer, non_practical_tracks)
    assert "정정" in fixed and "면접" in fixed, (
        f"실기시험이 없는데 '실기 날짜'만 남은 답변에 강제 정정 문구가 안 붙었습니다: {fixed!r}"
    )

    # 실제로 실기시험이 있는 전형이면 절대 정정 문구를 붙이면 안 된다(과잉탐지 방지)
    practical_tracks = [{"university": "중앙대학교", "department": "공간연출전공", "exam_type_name": "소묘(공간구성과 묘사)"}]
    normal_answer = "중앙대학교 공간연출전공의 실기 날짜는 2026-10-11입니다."
    assert _force_fix_practical_date_wording(normal_answer, practical_tracks) == normal_answer, (
        "실기시험이 실제로 있는데 정정 문구를 잘못 붙였습니다(과잉탐지)"
    )

    # exam_type_name 정보 자체가 없으면(판정 근거 부족) 손대지 않아야 한다
    unknown_tracks = [{"university": "OO대학교", "department": "OO학과"}]
    assert _force_fix_practical_date_wording(normal_answer, unknown_tracks) == normal_answer

    # 2026-09-23 프로덕션 재검증에서 실제로 재현된 케이스: context_tracks에 같은
    # 대학의 무관한 다른(실기 있는) 전형이 섞여 있으면, "전체 중 하나라도 실기가
    # 있으면 통과"로 판정해선 안 되고 답변이 실제로 언급한 그 전형(track_name)만
    # 봐야 한다. track_name이 있는 fixture로 이 시나리오를 재현한다.
    mixed_tracks = [
        {"university": "홍익대학교", "department": "미술대학", "track_name": "미술우수자전형",
         "exam_type_name": "미술활동보고서 서류평가 및 심층 면접평가"},
        {"university": "홍익대학교", "department": "회화과", "track_name": "실기우수자전형",
         "exam_type_name": "인물소묘"},  # 같은 대학의 무관한 다른 전형(진짜 실기 있음)
    ]
    mixed_answer = "홍익대학교 미술우수자전형의 실기 날짜는 다음과 같습니다: 2026-12-05~06"
    fixed_mixed = _force_fix_practical_date_wording(mixed_answer, mixed_tracks)
    assert "정정" in fixed_mixed, (
        "같은 대학의 무관한 실기전형이 섞여 있다는 이유로 정정을 건너뛰었습니다 - "
        f"답변이 실제로 언급한 전형(미술우수자전형) 기준으로 판정해야 합니다: {fixed_mixed!r}"
    )


def test_run_agent_compat_search_does_not_raise_unboundlocalerror():
    """[유료 - gpt-4o-mini 실호출, ci_quality_gate 비편입] find_compatible_exam_tracks
    경로를 실제로 태우는 질문이 예외 없이 끝까지 답해야 한다.

    회귀 대상 사고(2026-09-23 실장애): run_agent()의 중첩 함수 _invoke()가
    grounded_universities를 |=(augmented assignment)로 갱신하면서도 nonlocal
    선언이 없어, 도구가 하나라도 호출되면 "local variable 'grounded_universities'
    referenced before assignment"로 매번 터졌다. 공통 예외 처리기가 이를 삼켜
    HTTP 200 + "AI 서비스 고도화 작업 중" 문구로 위장해서, qa.html에서는 실제
    호환학교 검색 질문이 전부 조용히 실패하고 있었다(실기 호환학교 검색에서 재현).
    """
    from services.art_admission_agent import run_agent

    result = run_agent("한국예술종합학교 무대미술과와 같은 실기로 지원 가능한 학교는?")
    assert not result.get("error"), f"run_agent가 error를 반환했습니다: {result}"
    assert result.get("answer"), "run_agent가 빈 답변을 반환했습니다"
    tool_names = {t.get("tool") for t in result.get("tool_trace", [])}
    assert "find_compatible_exam_tracks" in tool_names, (
        f"find_compatible_exam_tracks가 호출되지 않았습니다(라우팅이 바뀌었을 수 있음): {tool_names}"
    )


def test_pii_scan_runs_without_university_specified():
    """[유료 - Jev 실호출, ci_quality_gate 비편입] university/doc_rules가 없어도
    (예: /review-chat처럼 학교를 안 지정한 호출) 개인식별정보 스캔 자체는
    수행돼야 한다.

    회귀 대상(2026-09-24 GPT QC 재검수): run_document_fact_checks()가 "이 학교
    발췌에 '블라인드'라는 단어가 실제로 있을 때만" PII를 검사해서, university를
    안 지정한 호출(doc_rules=[])에서는 fact_checks.checks가 항상 빈 배열이었다
    - 실명/학교명이 그대로 있어도 아무 경고 없이 통과됐다. university 지정
    여부와 무관하게 PII 검사 자체는 항상 돌고, 학교 규정이 확인 안 됐을 때는
    "예방적 권고" 톤으로만 낮추도록 수정했다.
    """
    svc = _svc()
    text_with_pii = "저는 대원고등학교를 졸업한 지원자이고, 지도교사 이수진 선생님의 도움을 받았습니다."
    result = svc.run_document_fact_checks(text_with_pii, doc_rules=[])
    blind_checks = [c for c in result["checks"] if c.get("type") == "blind_review"]
    assert blind_checks, "university 미지정 상태에서 PII 검사 자체가 스킵됐습니다(빈 checks)"
    assert blind_checks[0]["passed"] is False, "실명/학교명이 있는데 통과(passed=True) 처리됐습니다"
    assert blind_checks[0]["suspects"], "개인식별정보가 감지됐는데 suspects가 비어있습니다"

    # 개인식별정보가 전혀 없는 정상 텍스트는 오탐하면 안 된다(과잉탐지 방지)
    clean_text = "저는 미술 실기를 준비하며 소묘와 수채화를 꾸준히 연습해왔습니다."
    clean_result = svc.run_document_fact_checks(clean_text, doc_rules=[])
    clean_blind_checks = [c for c in clean_result["checks"] if c.get("type") == "blind_review"]
    assert not clean_blind_checks, f"개인식별정보가 없는데 blind_review 경고가 붙었습니다(과잉탐지): {clean_blind_checks}"


if __name__ == "__main__":
    for fn in (
        test_topic_narrowing_keeps_every_matched_track,
        test_narrowing_never_invents_tracks,
        test_narrowing_actually_reduces_payload,
        test_school_specific_query_is_not_narrowed_away,
        test_practical_exam_date_rule_exists_in_prompts,
        test_aggregate_count_uses_full_registry_not_sample,
        test_gratitude_short_circuit_matches_only_pure_thanks,
        test_grounding_extraction_known_tool_shapes,
        test_duplicate_track_name_disambiguation_rule_exists_in_prompts,
        test_text2cypher_excludes_document_only_tracks_from_practical_ranking,
        test_text2cypher_excludes_portfolio_and_non_practical_markers,
        test_document_track_category_recognizes_non_practical_marker,
        test_dead_jev_compound_query_function_removed,
        test_route_classifier_falls_back_on_low_confidence_or_thin_margin,
        test_self_check_numeric_claims_flags_dates_and_quotas_not_in_context,
        test_recommend_universities_topic_filter_is_track_level_not_department_level,
        test_university_detail_returns_empty_official_tracks_for_unknown_university,
        test_self_check_practical_date_contradiction_catches_self_contradiction,
        test_force_fix_practical_date_wording_survives_llm_dodging_disclaimer,
    ):
        fn()
        print(f"PASS: {fn.__name__}")
    print("\n컨텍스트 보존 회귀 테스트 전체 통과")
