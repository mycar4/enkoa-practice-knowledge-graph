# -*- coding: utf-8 -*-
"""
🧮 [미술 실기 입시 도우미] 학생부 환산점수 계산기 회귀 테스트
================================================================================
- 성적 입력 -> 학교별 환산등급 계산 -> 대학 추천 핵심기능의 정밀 계산 5개교
  (중앙대·가천대·홍익대세종·서경대·상명대) 각각에 대해, 원문 모집요강에서
  직접 확인한 반영교과/환산표/공식으로 손계산한 기대값과 서비스 계산 결과가
  일치하는지 확인한다. 모델 호출 없음, 무료·즉시 실행.
================================================================================
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.art_admission_service import ArtAdmissionService  # noqa: E402

_GRADES = [
    {"subject_group": "국어", "grade": 4, "credit": 4},
    {"subject_group": "영어", "grade": 3, "credit": 4},
    {"subject_group": "사회", "grade": 5, "credit": 4},
    {"subject_group": "수학", "grade": 6, "credit": 4},
    {"subject_group": "과학", "grade": 4, "credit": 4},
]

# (university, department, 손계산 기대 percentage) - 전부 원문 [표]를 그대로 대입해
# 사람이 직접 계산한 값. 소수점은 round(x, 2) 기준으로 비교한다.
EXPECTED_CASES = [
    # 가천대: 국어/영어만, conv[4]=98.5, conv[3]=99 -> (98.5*4+99*4)/8 = 98.75
    ("가천대학교", "회화전공", 98.75),
    # 중앙대: 국어/영어/사회(공간연출전공), conv[4]=8.80,conv[3]=9.20,conv[5]=8.20 (max=10)
    # -> (8.80+9.20+8.20)/3 = 8.7333 -> 87.33%
    ("중앙대학교", "공간연출전공", 87.33),
    # 서경대: 4개 교과군(국영수사) 각 25%, 단일 과목이라 그룹평균=자기 자신
    # conv: 4->97, 3->98, 6->95, 5->96 -> (97+98+95+96)/4 = 96.5
    ("서경대학교", "공연예술학부 무대기술전공(무대,조명)", 96.5),
    # 상명대: 전 과목 풀링, conv[4]=94,conv[3]=96,conv[5]=90,conv[6]=80,conv[4]=94(과학)
    # -> (94+96+90+80+94)/5 = 90.8
    ("상명대학교", "미술학부 조형예술전공", 90.8),
    # 홍익대 세종: 국어/영어 고정 + 택1(수사과 중 동점이면 유리한 쪽=과학)
    # conv: 국어4->95,영어3->97,과학4->95 -> (95+97+95)/3 = 95.6667 -> 95.67%
    ("홍익대학교", "조형대학(디자인컨버전스학부/영상·애니메이션학부/게임그래픽디자인전공)", 95.67),
]


def test_priority_schools_exact_calc_matches_hand_computed():
    svc = ArtAdmissionService()
    try:
        for university, department, expected_pct in EXPECTED_CASES:
            result = svc.calculate_school_record_score(university, department, _GRADES)
            assert result.get("available") is True, f"{university} {department}: available=False - {result.get('reason')}"
            assert result.get("data_tier") == "OFFICIAL_RULE", f"{university} {department}: 정밀 계산이 아닌 결과가 나옴"
            pct = result.get("percentage")
            assert pct is not None, f"{university} {department}: percentage 계산 실패"
            assert abs(pct - expected_pct) < 0.05, (
                f"{university} {department}: 손계산 {expected_pct} vs 서비스 계산 {pct} 불일치"
            )
        print(f"✅ test_priority_schools_exact_calc_matches_hand_computed passed! ({len(EXPECTED_CASES)}개교 전수 일치)")
    finally:
        svc.close()


def test_hongik_sejong_choice_subject_picks_more_advantageous_on_tie():
    """홍익대 세종 '택1(수학/사회/과학)'은 이수단위가 동률이면 원문 규정대로
    '유리한 교과'(환산점수가 더 높은 쪽)를 선택해야 한다 - 임의로 첫 번째 후보를
    고르면 안 된다는 걸 이번 세션에서 실제로 잡은 버그의 회귀 케이스."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 4, "credit": 4},
            {"subject_group": "영어", "grade": 3, "credit": 4},
            {"subject_group": "사회", "grade": 5, "credit": 4},  # conv=93
            {"subject_group": "수학", "grade": 6, "credit": 4},  # conv=90
            {"subject_group": "과학", "grade": 4, "credit": 4},  # conv=95 (가장 유리)
        ]
        result = svc.calculate_school_record_score(
            "홍익대학교", "조형대학(디자인컨버전스학부/영상·애니메이션학부/게임그래픽디자인전공)", grades,
        )
        assert result["chosen_choice_subject"] == "과학", (
            f"이수단위 동률 시 더 유리한 '과학'을 선택해야 하는데 '{result['chosen_choice_subject']}'가 선택됨"
        )
        print("✅ test_hongik_sejong_choice_subject_picks_more_advantageous_on_tie passed!")
    finally:
        svc.close()


def test_hongik_sejong_liberal_arts_common_and_career_split_scaled():
    """홍익대 세종 캠퍼스자율전공(자연·예능)/교과우수자전형은 공통·일반선택 평균과
    진로선택 평균을 각각 0.9배해 더한 뒤 이수학점 합에 따른 배율을 곱하는 5번째
    계산 모드(common_and_career_split_scaled)를 쓴다. 손계산:
    공통 4과목(국영수과 각 1등급=100점, credit10) 평균=100 -> ×0.9=90
    진로선택 1과목(A=10점, credit10) 평균=10 -> ×0.9=9
    총 이수학점=50(cap 100 이내) -> 배율=50/1000+0.9=0.95
    raw_score=(90+9)×0.95=94.05, max_score=99.0 -> percentage=95.0"""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 1, "credit": 10},
            {"subject_group": "영어", "grade": 1, "credit": 10},
            {"subject_group": "수학", "grade": 1, "credit": 10},
            {"subject_group": "과학", "grade": 1, "credit": 10},
            {"subject_group": "수학", "career_elective": True, "achievement": "A", "credit": 10},
        ]
        result = svc.calculate_school_record_score("홍익대학교", "캠퍼스자율전공(자연·예능)", grades)
        assert result.get("available") is True, result.get("reason")
        assert abs(result["raw_score"] - 94.05) < 0.01, result["raw_score"]
        assert abs(result["percentage"] - 95.0) < 0.01, result["percentage"]
        print("✅ test_hongik_sejong_liberal_arts_common_and_career_split_scaled passed!")
    finally:
        svc.close()


def test_sangmyung_accepts_art_track_subjects():
    """상명대는 '석차등급 있는 전 교과목'을 반영해 국영수사과 화이트리스트가 없다 -
    예술고 학생부의 드로잉/평면조형/미술전공실기 같은 예술계열 전문교과도 석차등급이
    있으면 계산에 포함돼야 한다(실측 사례로 발견한 gap의 회귀 케이스)."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "예술", "grade": 5, "credit": 6},
            {"subject_group": "예술", "grade": 4, "credit": 2},
            {"subject_group": "예술", "grade": 3, "credit": 4},
        ]
        result = svc.calculate_school_record_score("상명대학교", "미술학부 조형예술전공", grades)
        assert result.get("available") is True, result.get("reason")
        assert abs(result["percentage"] - 92.67) < 0.01, result["percentage"]
        print("✅ test_sangmyung_accepts_art_track_subjects passed!")
    finally:
        svc.close()


def test_korean_history_subject_alias_matches_official_rule_per_school():
    """실측 사례로 발견: '한국사'는 학교마다 취급이 완전히 다르다.
    - 홍익세종 미술우수자전형: 원문에 "사회 교과는 한국사, 사회를 반영함"이라고
      명시돼 있어 한국사가 사회로 합산돼야 한다 (subject_aliases 적용 확인)
    - 서경대: 반영교과 표에서 한국사 칸이 비어있어(국영수사만 25%씩) 한국사를
      넣어도 결과가 안 바뀌어야 한다 (아예 반영되지 않음)"""
    svc = ArtAdmissionService()
    try:
        base = [
            {"subject_group": "국어", "grade": 3, "credit": 4},
            {"subject_group": "영어", "grade": 3, "credit": 4},
        ]
        with_history = base + [{"subject_group": "한국사", "grade": 1, "credit": 4}]

        r_without = svc.calculate_school_record_score(
            "서경대학교", "공연예술학부 무대기술전공(무대,조명)", base,
        )
        r_with = svc.calculate_school_record_score(
            "서경대학교", "공연예술학부 무대기술전공(무대,조명)", with_history,
        )
        assert r_without["percentage"] == r_with["percentage"], (
            "서경대는 한국사 칸이 반영교과 표에 없는데, 한국사를 넣었더니 결과가 바뀜"
        )

        hongik_dept = "조형대학(디자인컨버전스학부/영상·애니메이션학부/게임그래픽디자인전공)"
        social_only = [{"subject_group": "사회", "grade": 1, "credit": 4}, {"subject_group": "국어", "grade": 3, "credit": 4}, {"subject_group": "영어", "grade": 3, "credit": 4}]
        history_instead = [{"subject_group": "한국사", "grade": 1, "credit": 4}, {"subject_group": "국어", "grade": 3, "credit": 4}, {"subject_group": "영어", "grade": 3, "credit": 4}]
        r_social = svc.calculate_school_record_score("홍익대학교", hongik_dept, social_only)
        r_history = svc.calculate_school_record_score("홍익대학교", hongik_dept, history_instead)
        assert r_social["percentage"] == r_history["percentage"], (
            "홍익세종은 한국사를 사회로 합산해야 하는데, 한국사로 넣었을 때 사회로 넣었을 때와 결과가 다름"
        )
        print("✅ test_korean_history_subject_alias_matches_official_rule_per_school passed!")
    finally:
        svc.close()


def test_non_priority_school_returns_unavailable_not_fake_number():
    """정밀 반영교과 규정을 원문으로 확보하지 못한 학교(예: 경기대)는 있지도 않은
    환산표를 지어내지 말고 반드시 available=False로 명시해야 한다."""
    svc = ArtAdmissionService()
    try:
        result = svc.calculate_school_record_score("경기대학교", "입체조형학과", _GRADES)
        assert result.get("available") is False, "정밀 규정이 없는 학교인데 available=True가 나옴 (값을 지어냈을 위험)"
        assert "percentage" not in result or result.get("percentage") is None
        print("✅ test_non_priority_school_returns_unavailable_not_fake_number passed!")
    finally:
        svc.close()


def test_recommend_universities_ranks_exact_before_approximate():
    svc = ArtAdmissionService()
    try:
        results = svc.recommend_universities(_GRADES)
        assert len(results) > 0
        precisions = [r["calc_precision"] for r in results]
        first_approx_idx = next((i for i, p in enumerate(precisions) if p == "approximate"), len(precisions))
        last_exact_idx = max((i for i, p in enumerate(precisions) if p == "exact"), default=-1)
        assert last_exact_idx < first_approx_idx, "exact 계산 결과가 approximate보다 뒤에 나오면 안 됨 (정밀 계산 우선 정렬 위반)"
        print(f"✅ test_recommend_universities_ranks_exact_before_approximate passed! (총 {len(results)}건)")
    finally:
        svc.close()


if __name__ == "__main__":
    test_priority_schools_exact_calc_matches_hand_computed()
    test_hongik_sejong_choice_subject_picks_more_advantageous_on_tie()
    test_hongik_sejong_liberal_arts_common_and_career_split_scaled()
    test_sangmyung_accepts_art_track_subjects()
    test_korean_history_subject_alias_matches_official_rule_per_school()
    test_non_priority_school_returns_unavailable_not_fake_number()
    test_recommend_universities_ranks_exact_before_approximate()
    print("🎉 ALL SCHOOL RECORD CALC TESTS PASSED!")
