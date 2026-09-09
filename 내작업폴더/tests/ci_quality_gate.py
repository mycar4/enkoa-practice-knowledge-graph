# -*- coding: utf-8 -*-
"""GitHub Actions 배포 게이트 전용 진입점. test_art_admission_rag_eval.py의 전체 3개
테스트 중, 무료·결정적인 두 개만 골라 배포 직전에 돌린다(비용 드는 LLM-as-Judge
테스트는 로컬/수동 실행용으로 남겨둔다 - 배포마다 API 비용이 나가지 않게).
실행: python 내작업폴더/tests/ci_quality_gate.py (리포 루트에서)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_art_admission_rag_eval import (  # noqa: E402
    test_exact_match_never_includes_material_only_overlaps,
    test_qa_search_and_agent_search_agree,
)
from tests.test_art_admission_school_record_calc import (  # noqa: E402
    test_priority_schools_exact_calc_matches_hand_computed,
    test_hongik_sejong_choice_subject_picks_more_advantageous_on_tie,
    test_hongik_sejong_liberal_arts_common_and_career_split_scaled,
    test_sangmyung_accepts_art_track_subjects,
    test_korean_history_subject_alias_matches_official_rule_per_school,
    test_estimated_grade_equivalent_matches_raw_grade_not_inflated_score,
    test_breakdown_and_reason_summary_and_fit_label_present,
    test_original_15_batch2_schools_use_generalized_modes_not_hardcoding,
    test_batch3_schools_hongik_seoul_chugye_karts,
    test_batch4_remaining_15_schools_use_generalized_modes_not_hardcoding,
    test_non_priority_school_returns_unavailable_not_fake_number,
    test_recommend_universities_ranks_exact_before_approximate,
)

if __name__ == "__main__":
    test_exact_match_never_includes_material_only_overlaps()
    test_qa_search_and_agent_search_agree()
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
    test_non_priority_school_returns_unavailable_not_fake_number()
    test_recommend_universities_ranks_exact_before_approximate()
    print("🎉 CI QUALITY GATE PASSED (무료 회귀 테스트 14건)")
