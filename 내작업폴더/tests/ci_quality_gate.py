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
    test_self_check_grounding_does_not_flag_names_from_query_context,
)
from tests.test_art_admission_context_preservation import (  # noqa: E402
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
    test_not_applicable_schools_get_no_score_not_approximate_guess,
    test_recommend_sorts_by_raw_grade_not_schools_own_generous_curve,
    test_prior_year_comparison_tier_drives_primary_sort,
    test_gender_restriction_flags_womens_universities,
    test_school_record_impact_score_matches_hand_computed,
    test_prior_year_result_batch2_image_based_schools,
    test_non_priority_school_returns_unavailable_not_fake_number,
    test_recommend_universities_ranks_exact_before_approximate,
)

def test_art_admission_agent_module_imports_cleanly():
    """2026-09-23 실측 발견: 이 게이트는 art_admission_agent.py를 어디서도 import하지
    않았다 - 그날 고친 거의 모든 코드가 이 파일에 있었는데도, 모듈 최상단 f-string
    안에 이스케이프 안 된 중괄호({track1: ...})가 들어가 NameError로 즉시 임포트가
    깨지는 문법 수준 버그를 로컬 재현 테스트에서야 겨우 잡았다(게이트는 "통과"라고
    나왔었음) - 하마터면 API 전체가 못 뜨는 채로 배포될 뻔했다. 최소한의 임포트
    스모크 테스트를 게이트에 영구히 추가해 이 사각지대를 없앤다."""
    import importlib
    import services.art_admission_agent as agent_module
    importlib.reload(agent_module)
    assert callable(agent_module.route_and_answer)


if __name__ == "__main__":
    test_art_admission_agent_module_imports_cleanly()
    test_exact_match_never_includes_material_only_overlaps()
    test_qa_search_and_agent_search_agree()
    test_self_check_grounding_does_not_flag_names_from_query_context()
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
    # day48(리랭킹·컨텍스트 압축) 학습 적용: 좁히기가 근거를 버리지 않는지 검증
    test_topic_narrowing_keeps_every_matched_track()
    test_narrowing_never_invents_tracks()
    test_narrowing_actually_reduces_payload()
    test_school_specific_query_is_not_narrowed_away()
    test_practical_exam_date_rule_exists_in_prompts()
    test_aggregate_count_uses_full_registry_not_sample()
    test_gratitude_short_circuit_matches_only_pure_thanks()
    test_grounding_extraction_known_tool_shapes()
    test_duplicate_track_name_disambiguation_rule_exists_in_prompts()
    test_text2cypher_excludes_document_only_tracks_from_practical_ranking()
    test_text2cypher_excludes_portfolio_and_non_practical_markers()
    test_document_track_category_recognizes_non_practical_marker()
    test_dead_jev_compound_query_function_removed()
    test_route_classifier_falls_back_on_low_confidence_or_thin_margin()
    test_self_check_numeric_claims_flags_dates_and_quotas_not_in_context()
    test_recommend_universities_topic_filter_is_track_level_not_department_level()
    test_university_detail_returns_empty_official_tracks_for_unknown_university()
    test_self_check_practical_date_contradiction_catches_self_contradiction()
    test_force_fix_practical_date_wording_survives_llm_dodging_disclaimer()
    print("🎉 CI QUALITY GATE PASSED (무료 회귀 테스트 41건)")
