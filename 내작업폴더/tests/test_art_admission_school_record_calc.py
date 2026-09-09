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


def test_estimated_grade_equivalent_matches_raw_grade_not_inflated_score():
    """2026-09-09 실측 사고: 처음엔 학교 배점표 기준 백분율(가천대 97.1%)을 일반
    9등급 곡선에 역산해서 "참고용 환산등급"을 만들었는데, 타 입시업체 실측 데이터
    (내등급 4.92)와 비교해보니 완전히 다른 값(1.29)이 나왔다. 가천대 배점표는
    1~6등급이 100~97.5점으로 거의 압축돼 있어 원 등급 4~6등급도 배점 기준으론
    97%가 나오는데, 이걸 다시 등급으로 되돌리면 실제보다 훨씬 좋아 보이게 된다.
    참고등급은 배점표를 거치지 않은 '원 석차등급 가중평균'이어야 하고, 이 값이
    타사 실측치(4.92)와 거의 일치해야 한다 - 이번 세션에서 실제 확인한 회귀 케이스."""
    svc = ArtAdmissionService()
    try:
        # 실제 학생(은수) 국어/영어 5개 학기 성적 - 가천대 회화전공은 국영만 반영
        grades = [
            {"subject_group": "국어", "grade": 5, "credit": 3},
            {"subject_group": "영어", "grade": 6, "credit": 3},
            {"subject_group": "국어", "grade": 4, "credit": 3},
            {"subject_group": "영어", "grade": 5, "credit": 3},
            {"subject_group": "국어", "grade": 5, "credit": 3},
            {"subject_group": "영어", "grade": 7, "credit": 2},
            {"subject_group": "국어", "grade": 4, "credit": 3},
            {"subject_group": "영어", "grade": 5, "credit": 2},
            {"subject_group": "국어", "grade": 4, "credit": 2},
            {"subject_group": "영어", "grade": 5, "credit": 2},
        ]
        result = svc.calculate_school_record_score("가천대학교", "회화전공", grades)
        assert result["available"] is True
        assert abs(result["percentage"] - 97.1) < 0.05, "배점표 기준 환산 백분율 자체는 그대로 97.1%여야 함"
        # 원 석차등급 가중평균은 손계산: 국어(62/14=4.4286), 영어(67/12=5.5833),
        # 두 교과를 이수단위 합산 가중평균하면 (62+67)/(14+12)=4.9615 -> 4.96
        assert abs(result["estimated_grade_equivalent"] - 4.96) < 0.05, (
            f"참고등급이 원 석차등급 평균(≈4.96, 타사 실측 4.92와 일치)이 아니라 "
            f"배점표 역산값({result['estimated_grade_equivalent']})으로 나옴 - 회귀 발생"
        )
        print("✅ test_estimated_grade_equivalent_matches_raw_grade_not_inflated_score passed!")
    finally:
        svc.close()


def test_breakdown_and_reason_summary_and_fit_label_present():
    """UI 요청사항: (1) 계산 상세보기 팝업에 실제 대입값을 보여줘야 하므로
    calculate_school_record_score가 breakdown(과목별 등급/이수단위/환산점수)을
    반환해야 한다. (2) recommend_universities는 추천 이유(reason_summary)를 정밀
    계산된 항목에 부여해야 한다. (3) GOOD_FIT/CHECK 판정(fit_label)은 사용자
    확정 기준대로 "배점표 환산 점수가 높다"가 아니라 "이 학생의 원 석차등급이
    전년도 등록자보다 좋은가"(prior_year_tier)로만 정해져야 하며, 전년도 비교
    자료가 없는 학교(NO_DATA)는 판정 자체가 없어야 한다(자료 없이 임의 판정하면
    안 됨)."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 5, "credit": 3},
            {"subject_group": "영어", "grade": 6, "credit": 3},
        ]
        detail = svc.calculate_school_record_score("가천대학교", "회화전공", grades)
        assert detail["available"] is True
        assert isinstance(detail.get("breakdown"), list) and len(detail["breakdown"]) == 2
        for item in detail["breakdown"]:
            assert "subject_group" in item and "credit" in item and "score" in item

        recs = svc.recommend_universities(grades)
        exact_with_pct = [r for r in recs if r["calc_precision"] == "exact" and r["school_record_percentage"] is not None]
        assert exact_with_pct, "정밀 계산 결과가 하나도 없음"
        assert all(r.get("reason_summary") for r in exact_with_pct), "정밀 계산 항목엔 추천 이유가 있어야 함"

        # fit_label <-> prior_year_tier 매핑이 정확히 일치하는지 전수 검사 (구조적 검증).
        expected_map = {"REGISTRANT_TOP": "GOOD_FIT", "REGISTRANT_MID": "CHECK", "REGISTRANT_BELOW": "CHECK", "NO_DATA": None}
        for r in exact_with_pct:
            assert r["fit_label"] == expected_map[r["prior_year_tier"]], (
                f"{r['university']} {r['department']}: fit_label={r['fit_label']} "
                f"but prior_year_tier={r['prior_year_tier']}"
            )

        # 가천대 회화전공(전년도 typical=4.92, floor=6.19)은 이 학생 원등급 5.5로
        # REGISTRANT_MID(전년도 평균~최저 사이) -> CHECK가 나와야 한다(GOOD_FIT 아님).
        gachon = next(r for r in exact_with_pct if r["university"] == "가천대학교" and r["department"] == "회화전공")
        assert gachon["prior_year_tier"] == "REGISTRANT_MID", gachon["prior_year_tier"]
        assert gachon["fit_label"] == "CHECK", gachon["fit_label"]

        no_data_entries = [r for r in exact_with_pct if r["prior_year_tier"] == "NO_DATA"]
        assert no_data_entries, "NO_DATA 항목이 하나도 없음 - 테스트 전제 성립 안 함"
        assert all(r["fit_label"] is None for r in no_data_entries), "전년도 비교자료가 없는데 fit_label이 매겨짐(임의 판정 위험)"
        print("✅ test_breakdown_and_reason_summary_and_fit_label_present passed!")
    finally:
        svc.close()


def test_original_15_batch2_schools_use_generalized_modes_not_hardcoding():
    """30개교 확장 원칙 검증: 경희대(공통0.8+진로0.2 분할, 크레딧스케일 없음)·
    동국대(상위10과목 단순평균, 이수단위 미반영)·명지대(국영만+진로선택+이수학점
    가산점 0.05)·서울과기대(국영사한국사 단순 이수단위가중평균)는 전부 새로운
    if-university 분기 없이, 기존 5개 모드에 파라미터(common_weight/career_weight/
    use_credit_scale/top_n/credit_weighted/credit_bonus_factor/subjects)만 추가해서
    처리된다. 손계산 값과 일치하는지 확인."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 4, "credit": 3},
            {"subject_group": "영어", "grade": 5, "credit": 3},
            {"subject_group": "수학", "grade": 4, "credit": 3},
            {"subject_group": "사회", "grade": 3, "credit": 3},
            {"subject_group": "과학", "grade": 2, "credit": 3},
            {"subject_group": "한국사", "grade": 2, "credit": 1},
        ]
        cases = [
            ("경희대학교", "회화전공", 92.0),
            ("동국대학교", "한국화전공", 99.12),
            ("명지대학교", "비주얼커뮤니케이션디자인전공", 92.0),
            ("서울과학기술대학교", "조형예술학과", 97.2),
        ]
        for uni, dept, expected_pct in cases:
            r = svc.calculate_school_record_score(uni, dept, grades)
            assert r.get("available") is True, f"{uni} {dept}: {r.get('reason')}"
            assert abs(r["percentage"] - expected_pct) < 0.05, f"{uni} {dept}: {r['percentage']} != {expected_pct}"

        # 삼육대 아트앤디자인학과는 "서류 20%"가 정성평가(학생부+인성검사 종합)라
        # 애초에 정량 공식이 없다 - 규정 미확인이 아니라 규정 자체가 존재하지 않는
        # 케이스이므로 available=False가 맞다(허위로 계산값을 만들면 안 됨).
        syu = svc.calculate_school_record_score("삼육대학교", "아트앤디자인학과", grades)
        assert syu.get("available") is False
        print("✅ test_original_15_batch2_schools_use_generalized_modes_not_hardcoding passed!")
    finally:
        svc.close()


def test_batch3_schools_hongik_seoul_chugye_karts():
    """계속 확장: 홍익대 서울캠퍼스(choose_max_credit_subject, 세종캠퍼스와 동일한
    학교 공통 환산표를 공유 - Ⅰ.학교생활기록부 반영 방법 챕터가 두 캠퍼스에 공통
    적용됨을 검증), 추계예술대(simple_weighted_average, 국어·영어만, 이수단위
    가중평균), 한국예술종합학교 무대미술과(신규 모드 year_weighted_band_lookup:
    학기별 가중평균->학년별 단순평균->학년별 반영비율 가중합->32단계 구간표 조회)
    까지 전부 기존 5개 모드(+1개 새 모드)에 파라미터만 추가해 처리됨을 확인한다."""
    svc = ArtAdmissionService()
    try:
        r = svc.calculate_school_record_score("홍익대학교", "미술대학(동양화/회화/판화/조소/디자인학부 등)", _GRADES)
        assert r.get("available") is True, r.get("reason")
        assert abs(r["percentage"] - 95.67) < 0.05, f"홍익대 서울: {r['percentage']} != 95.67"

        r = svc.calculate_school_record_score("추계예술대학교", "미술창작학부(1학년말 동양화/서양화(현대미술 포함)/판화미디어전공 선택)", _GRADES)
        assert r.get("available") is True, r.get("reason")
        assert abs(r["percentage"] - 92.5) < 0.05, f"추계예술대: {r['percentage']} != 92.5"

        karts_grades = []
        for sem in [1, 2]:
            karts_grades.append({"year": 1, "semester": sem, "subject_group": "국어", "grade": 2, "credit": 4})
            karts_grades.append({"year": 1, "semester": sem, "subject_group": "영어", "grade": 2, "credit": 4})
            karts_grades.append({"year": 2, "semester": sem, "subject_group": "국어", "grade": 3, "credit": 4})
            karts_grades.append({"year": 2, "semester": sem, "subject_group": "영어", "grade": 3, "credit": 4})
        r = svc.calculate_school_record_score("한국예술종합학교", "무대미술과", karts_grades)
        assert r.get("available") is True, r.get("reason")
        # 손계산: 1학년 평균등급점수=8(2등급), 2학년=7(3등급) -> 8*0.4+7*0.6=7.4 -> 구간표 7.26~7.50 -> 85.00점
        assert abs(r["percentage"] - 85.0) < 0.05, f"한예종 무대미술과: {r['percentage']} != 85.0"
        print("✅ test_batch3_schools_hongik_seoul_chugye_karts passed!")
    finally:
        svc.close()


def test_batch4_remaining_15_schools_use_generalized_modes_not_hardcoding():
    """원본 15개교 완료 후 나머지 대학 확장: 숙명여대(진로선택 없으면 공통 100%
    반영되는 common_and_career_split_scaled), 동덕여대(균등 1/3 반영 + 선택교과
    1개, subject_group_weighted의 choice_groups 신규 파라미터), 수원대(4개 후보
    교과 중 상위 2개만 50%씩 반영, subject_group_weighted의 top_k_groups 신규
    파라미터), 단국대·한성대·인하대(simple_weighted_average 국영사 조합),
    경기대(9개 교과 common_and_career_split_scaled) - 전부 학교명 분기 없이
    기존 3개 모드에 새 파라미터(choice_groups/top_k_groups)만 추가해 처리된다."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 3, "credit": 4},
            {"subject_group": "영어", "grade": 4, "credit": 4},
            {"subject_group": "수학", "grade": 5, "credit": 4},
            {"subject_group": "사회", "grade": 2, "credit": 4},
            {"subject_group": "한국사", "grade": 2, "credit": 3},
        ]
        cases = [
            ("숙명여자대학교", "회화과(한국화)", 82.0),
            ("동덕여자대학교", "회화전공", 94.67),
            ("수원대학교", "조형예술학부", 97.0),
            ("단국대학교", "도예과", 98.0),
            ("한성대학교", "예술학부(동양화전공)", 95.62),
            ("인하대학교", "조형예술학과", 96.0),
            ("경기대학교", "입체조형학과", 95.84),
            ("성신여자대학교", "동양화과", 97.67),
        ]
        for uni, dept, expected_pct in cases:
            r = svc.calculate_school_record_score(uni, dept, grades)
            assert r.get("available") is True, f"{uni} {dept}: {r.get('reason')}"
            assert abs(r["percentage"] - expected_pct) < 0.05, f"{uni} {dept}: {r['percentage']} != {expected_pct}"
        print("✅ test_batch4_remaining_15_schools_use_generalized_modes_not_hardcoding passed!")
    finally:
        svc.close()


def test_prior_year_result_batch2_image_based_schools():
    """이미지(스캔) PDF라 자동 텍스트 추출이 안 되는 4개교(서울과기대·성신여대·
    경희대·경기대)는 pymupdf로 페이지를 렌더링한 뒤 직접 읽어(비전) 옮긴 값이다 -
    OCR 도구가 아니라 육안 대조이므로 정확한 값이 DB에 그대로 들어갔는지 회귀
    테스트로 고정해둔다. 경희대는 학생부 등급 자료 자체가 원문에 없어 competition_rate만
    있고 typical/floor는 반드시 None이어야 한다(지어내면 안 됨)."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 3, "credit": 4},
            {"subject_group": "영어", "grade": 4, "credit": 4},
        ]
        results = svc.recommend_universities(grades)

        def pyr_of(uni, dept):
            r = next(x for x in results if x["university"] == uni and x["department"] == dept)
            return r["prior_year_result"]

        seoultech = pyr_of("서울과학기술대학교", "조형예술학과")
        assert seoultech["school_record_grade_typical"] == 2.75
        assert seoultech["school_record_grade_floor"] is None

        sungshin = pyr_of("성신여자대학교", "동양화과")
        assert sungshin["competition_rate"] == 10.55
        assert sungshin["school_record_grade_typical"] == 4.31

        khu = pyr_of("경희대학교", "회화전공")
        assert khu["competition_rate"] == 51.4
        assert khu["school_record_grade_typical"] is None, "경희대는 학생부 등급 자료가 없는데 값이 들어감(지어냈을 위험)"
        assert khu["school_record_grade_floor"] is None

        gyeonggi = pyr_of("경기대학교", "Fine Arts학부")
        assert gyeonggi["school_record_grade_typical"] == 5.083
        assert gyeonggi["school_record_grade_floor"] == 5.707
        print("✅ test_prior_year_result_batch2_image_based_schools passed!")
    finally:
        svc.close()


def test_gender_restriction_flags_womens_universities():
    """사용자 요청('남/여 구분' = 여대 필터링): 여자대학교는 남학생이 지원 자체를
    할 수 없으므로 FO에서 걸러낼 수 있어야 한다. gender_restriction 필드가
    데이터에 없으면 이 필터 자체가 불가능하므로, 확인된 6개 여대(덕성·동덕·
    서울여대·성신·숙명·이화) 전 트랙에 "female_only"가 정확히 붙어있는지,
    그 외 대학(공학 - 남녀공학)에는 붙어있지 않은지 확인한다."""
    svc = ArtAdmissionService()
    try:
        grades = [{"subject_group": "국어", "grade": 3, "credit": 4}, {"subject_group": "영어", "grade": 4, "credit": 4}]
        results = svc.recommend_universities(grades)
        expected_female_only = {"덕성여자대학교", "동덕여자대학교", "서울여자대학교", "성신여자대학교", "숙명여자대학교", "이화여자대학교"}
        female_only_unis = set(r["university"] for r in results if r.get("gender_restriction") == "female_only")
        assert female_only_unis == expected_female_only, female_only_unis

        # 공학(남녀공학) 대학은 gender_restriction이 없어야 함(허위 표시 금지)
        coed = next(r for r in results if r["university"] == "중앙대학교")
        assert coed.get("gender_restriction") is None
        print("✅ test_gender_restriction_flags_womens_universities passed!")
    finally:
        svc.close()


def test_school_record_impact_score_matches_hand_computed():
    """'내신 실질영향' 지표(사용자 확정 공식) = (1등급 환산점수-6등급 환산점수)/만점
    × 학생부반영비율. 동국대 한국화전공(conv: 1등급=10점,6등급=8.7점,만점10, 학생부
    반영비율30%)로 손계산: (10-8.7)/10 × 0.3 = 0.039. 6등급을 공통 기준점으로 삼는
    이유는 학교마다 등급 구간별 관대함이 다른데(동국대는 1~5등급은 완만하다가 6등급부터
    급락) 모든 학교에 같은 등급을 대입해야 학교 간 비교가 가능하기 때문이다."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 3, "credit": 4},
            {"subject_group": "영어", "grade": 4, "credit": 4},
        ]
        results = svc.recommend_universities(grades)
        dongguk = next(r for r in results if r["university"] == "동국대학교" and r["department"] == "한국화전공")
        assert abs(dongguk["school_record_impact_score"] - 0.039) < 1e-6, dongguk["school_record_impact_score"]
        print("✅ test_school_record_impact_score_matches_hand_computed passed!")
    finally:
        svc.close()


def test_non_priority_school_returns_unavailable_not_fake_number():
    """학생부 반영 자체가 정성평가(서류종합전형)라 정량 공식이 존재하지 않는 학교
    (이화여대 디자인학부 예체능서류전형 - 원문 확인 결과 100% 학생부종합 정성평가)는
    있지도 않은 환산표를 지어내지 말고 반드시 available=False로 명시해야 한다."""
    svc = ArtAdmissionService()
    try:
        result = svc.calculate_school_record_score("이화여자대학교", "디자인학부", _GRADES)
        assert result.get("available") is False, "정밀 규정이 없는 학교인데 available=True가 나옴 (값을 지어냈을 위험)"
        assert "percentage" not in result or result.get("percentage") is None
        print("✅ test_non_priority_school_returns_unavailable_not_fake_number passed!")
    finally:
        svc.close()


def test_not_applicable_schools_get_no_score_not_approximate_guess():
    """실기 100%나 학생부종합 정성평가라 애초에 '학생부 등급→점수 환산' 자체가
    존재하지 않는 전형(계원예대·삼육대·덕성여대·서울여대·건국대·한양에리카·
    서울예대·이화여대·상명대(학생부종합), 총 9개교 21개 트랙)은 RULE_INCOMPLETE
    (규정을 아직 못 찾은 경우, 비율 기반 근사치라도 의미가 있음)와 다르다 -
    근사치조차 매기면 실제로는
    반영되지도 않는 성적을 반영되는 것처럼 보여주는 셈이므로, calculate_school_record_score
    단건 조회와 recommend_universities 목록 양쪽 모두에서 school_record_percentage가
    반드시 None이어야 하고 calc_precision="not_applicable"로 명확히 구분되어야 한다."""
    svc = ArtAdmissionService()
    try:
        single = svc.calculate_school_record_score("삼육대학교", "아트앤디자인학과", _GRADES)
        assert single.get("available") is False
        assert single.get("not_applicable") is True, "not_applicable 플래그가 없으면 FO가 RULE_INCOMPLETE와 구분 못 함"
        assert single.get("reason"), "사유 없이 그냥 계산 불가라고만 하면 안 됨"

        results = svc.recommend_universities(_GRADES)
        na_entries = [r for r in results if r["university"] == "삼육대학교"]
        assert na_entries, "recommend_universities 목록에서 아예 빠지면 안 됨(트랙 존재 자체는 계속 보여줘야 함)"
        for e in na_entries:
            assert e["calc_precision"] == "not_applicable"
            assert e["school_record_percentage"] is None, "학생부 미반영 전형인데 근사치라도 점수가 나오면 안 됨(오해 유발)"
            assert e.get("reason_summary"), "사유가 없으면 사용자가 왜 점수가 없는지 알 수 없음"

        na_count = sum(1 for r in results if r["calc_precision"] == "not_applicable")
        assert na_count == 21, f"확인된 학생부 미반영 트랙 수(21)와 다름: {na_count}"

        # 정렬 순서: exact -> approximate -> not_applicable (점수 없는 항목이 앞으로 오면 안 됨)
        precisions_in_order = [r["calc_precision"] for r in results]
        first_na_idx = precisions_in_order.index("not_applicable")
        assert all(p != "exact" for p in precisions_in_order[first_na_idx:]), "not_applicable 뒤에 exact가 나오면 정렬이 깨진 것"
        print("✅ test_not_applicable_schools_get_no_score_not_approximate_guess passed!")
    finally:
        svc.close()


def test_recommend_sorts_by_raw_grade_not_schools_own_generous_curve():
    """사용자 피드백 1차: 학교마다 등급→점수 환산표의 관대함이 달라서(어떤 학교는 상위
    등급을 널찍하게 압축, 어떤 학교는 촘촘하게 벌림) school_record_percentage로 학교 간
    순위를 매기면 "환산표가 후한 학교"가 실제 성적 경쟁력과 무관하게 항상 위로 올라오는
    착시가 생긴다(실측: 가천대 98.75%/원등급3.5가 서울과기대 98.2%/원등급2.8보다 원래
    순위가 위였음 - 원등급은 서울과기대가 더 좋은데도 뒤집힘). 이후 사용자 피드백 2차로
    정렬 기준이 다시 한번 바뀌어(전년도 등록자 비교 -> 내신 실질영향 -> 실기비중, 원
    석차등급은 최종 타이브레이커로만 남음) 이 테스트는 "NO_DATA 구간(전년도 비교자료도
    없고 내신영향/실기비중도 동률인 좁은 부분집합)에서 school_record_percentage가
    아니라 다른 기준으로 정렬된다"는 최소 불변식만 검증한다."""
    svc = ArtAdmissionService()
    try:
        grades = [
            {"subject_group": "국어", "grade": 3, "credit": 4},
            {"subject_group": "영어", "grade": 4, "credit": 4},
            {"subject_group": "수학", "grade": 5, "credit": 4},
            {"subject_group": "사회", "grade": 2, "credit": 4},
            {"subject_group": "과학", "grade": 6, "credit": 4},
            {"subject_group": "한국사", "grade": 2, "credit": 3},
        ]
        results = svc.recommend_universities(grades)
        exact = [r for r in results if r["calc_precision"] == "exact" and r["estimated_grade_equivalent"] is not None]
        assert exact, "정밀 계산 결과가 하나도 없음"

        # exact 전체가 (tier, 내신실질영향 오름차순, 실기비중 내림차순, 원등급 오름차순)
        # 기준으로 정확히 정렬돼 있는지 재계산해서 대조한다 - percentage 기준이 아님을
        # 구조적으로 검증(특정 두 학교 하드코딩 비교가 아니라 전체 리스트 재계산 대조).
        _tier_rank = {"REGISTRANT_TOP": 0, "REGISTRANT_MID": 1, "REGISTRANT_BELOW": 2, "NO_DATA": 3}
        expected_keys = [
            (
                _tier_rank.get(r["prior_year_tier"], 3),
                r["school_record_impact_score"] if r["school_record_impact_score"] is not None else float("inf"),
                -(r["practical_ratio_pct"] if r["practical_ratio_pct"] is not None else -1),
                r["estimated_grade_equivalent"],
            )
            for r in exact
        ]
        assert expected_keys == sorted(expected_keys), (
            "exact 그룹이 (전년도등록자tier, 내신실질영향, 실기비중, 원등급) 기준으로 "
            "정렬돼 있지 않음 - school_record_percentage 기준으로 되돌아갔을 위험"
        )
        print("✅ test_recommend_sorts_by_raw_grade_not_schools_own_generous_curve passed!")
    finally:
        svc.close()


def test_prior_year_comparison_tier_drives_primary_sort():
    """사용자 최종 설계안: 임의 가중치로 합친 종합점수 대신, 기본 정렬은 '전년도 등록자
    성적 대비 위치'(4단계 버킷: REGISTRANT_TOP/MID/BELOW/NO_DATA) - 이게 원 석차등급보다
    우선한다. 즉 원 석차등급이 더 안 좋아도 전년도 등록자 대비 더 높은 버킷에 있으면
    앞에 온다(반영교과가 다른 학교 간 비교이므로 원 석차등급 자체보다 "그 학교 기준으로
    작년 등록자보다 나은가"가 더 직접적인 신호). 대학 자체 CDN(negagea.net)에 공개된
    2026학년도 수시입시결과 문서에서 확인한 실측 데이터(가천대·동국대·중앙대 등)로
    검증한다."""
    svc = ArtAdmissionService()
    try:
        # 이 학생은 원 석차등급이 나쁜 편(6~8등급대)이라 대부분 학교에서
        # REGISTRANT_BELOW가 나오지만, 극소수 학교는 그래도 TOP/MID에 들 수 있다.
        grades = [
            {"subject_group": "국어", "grade": 6, "credit": 4},
            {"subject_group": "영어", "grade": 7, "credit": 4},
            {"subject_group": "수학", "grade": 8, "credit": 4},
            {"subject_group": "사회", "grade": 6, "credit": 4},
        ]
        results = svc.recommend_universities(grades)
        with_data = [r for r in results if r["prior_year_tier"] != "NO_DATA" and r["calc_precision"] == "exact"]
        assert with_data, "전년도 비교자료가 있는 exact 항목이 하나도 없음"

        tiers_in_order = [r["prior_year_tier"] for r in with_data]
        tier_rank = {"REGISTRANT_TOP": 0, "REGISTRANT_MID": 1, "REGISTRANT_BELOW": 2}
        ranks = [tier_rank[t] for t in tiers_in_order]
        assert ranks == sorted(ranks), "prior_year_tier 기준으로 정렬돼 있지 않음(TOP -> MID -> BELOW 순이어야 함)"

        # 가천대 조소전공(전년도 typical=5.6, floor=6.78)은 이 학생 원등급과 비교했을 때
        # MID에 들어야 한다(가천대 반영교과는 국어·영어만이라 계산: 국어6/영어7 각
        # credit4 -> 원등급 (6*4+7*4)/8 = 6.5, typical 5.6보다 나쁘고 floor 6.78보다 좋음).
        gachon_josso = next((r for r in results if r["university"] == "가천대학교" and r["department"] == "조소전공"), None)
        assert gachon_josso is not None
        assert gachon_josso["prior_year_tier"] == "REGISTRANT_MID", (
            f"가천대 조소전공 tier={gachon_josso['prior_year_tier']} (기대: REGISTRANT_MID, "
            f"원등급={gachon_josso['estimated_grade_equivalent']}, typical=5.6, floor=6.78)"
        )
        # prior_year_result가 official_facts와 분리된 별도 키로만 붙어있는지 확인 (Zero-Mixing)
        assert "prior_year_result" in gachon_josso
        assert gachon_josso["prior_year_result"]["grade_stat_type"]
        assert gachon_josso["prior_year_result"]["methodology_note"]
        print("✅ test_prior_year_comparison_tier_drives_primary_sort passed!")
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
    test_estimated_grade_equivalent_matches_raw_grade_not_inflated_score()
    test_breakdown_and_reason_summary_and_fit_label_present()
    test_original_15_batch2_schools_use_generalized_modes_not_hardcoding()
    test_batch3_schools_hongik_seoul_chugye_karts()
    test_batch4_remaining_15_schools_use_generalized_modes_not_hardcoding()
    test_not_applicable_schools_get_no_score_not_approximate_guess()
    test_recommend_sorts_by_raw_grade_not_schools_own_generous_curve()
    test_prior_year_comparison_tier_drives_primary_sort()
    test_gender_restriction_flags_womens_universities()
    test_school_record_impact_score_matches_hand_computed()
    test_prior_year_result_batch2_image_based_schools()
    test_non_priority_school_returns_unavailable_not_fake_number()
    test_recommend_universities_ranks_exact_before_approximate()
    print("🎉 ALL SCHOOL RECORD CALC TESTS PASSED!")
