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
    ):
        fn()
        print(f"PASS: {fn.__name__}")
    print("\n컨텍스트 보존 회귀 테스트 전체 통과")
