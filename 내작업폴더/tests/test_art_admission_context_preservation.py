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

from services.art_admission_agent import narrow_context  # noqa: E402
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


if __name__ == "__main__":
    for fn in (
        test_topic_narrowing_keeps_every_matched_track,
        test_narrowing_never_invents_tracks,
        test_narrowing_actually_reduces_payload,
        test_school_specific_query_is_not_narrowed_away,
        test_practical_exam_date_rule_exists_in_prompts,
        test_aggregate_count_uses_full_registry_not_sample,
    ):
        fn()
        print(f"PASS: {fn.__name__}")
    print("\n컨텍스트 보존 회귀 테스트 전체 통과")
