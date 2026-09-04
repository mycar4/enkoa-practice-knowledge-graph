# -*- coding: utf-8 -*-
"""
🧪 [DART-Trace] 엔티티 해소 무결성 검증 단위 테스트 (Value Binding Integrity Test)
================================================================================
- 변조된 회사명, 위조된 파편 값, 비정상 달력 날짜 등이 반드시 REJECT되는지 엄격 검증
================================================================================
"""

import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dry_run_resolution_engine import evaluate_single_candidate


def get_base_valid_candidate_and_frags():
    """모든 규칙을 100% 만족하는 기준 정상 PASS 후보 및 파편 데이터셋"""
    candidate = {
        "candidate_id": "cand-test-valid-001",
        "rcept_no": "20241231000001",
        "target_corp_code": "00117027",
        "target_corp_name": "(주)알루코",
        "holder_name": "(주)케이피티유",
        "reporter_name": "(주)케이피티유",
        "stake_ratio": 19.21,
        "shares_count": 18502826,
        "reporting_obligation_date": "2024-05-10",
        "layout_status": "SUPPORTED_5PCT_GENERAL",
        "xml_sha256": "e0a5abe39ea00c84aa9842ff793f9330d975c6a786fcadfb8d8f18fb6b57cdf2"
    }

    fragments = [
        {
            "role": "TARGET_COMPANY",
            "xpath": "//COMPANY-NAME",
            "raw_inner_hash": "hash-target-company-001",
            "extracted_value": "name=(주)알루코, code=00117027"
        },
        {
            "role": "REPORTER",
            "xpath": "//TE[@ACODE='RPT_RSP_NM']",
            "raw_inner_hash": "hash-reporter-001",
            "extracted_value": "(주)케이피티유"
        },
        {
            "role": "REPORTING_OBLIGATION_DATE",
            "xpath": "//TU[@AUNIT='RPT_RSP_DT']",
            "raw_inner_hash": "hash-date-001",
            "extracted_value": "2024-05-10"
        },
        {
            "role": "ROW_DATA_EVIDENCE",
            "xpath": "//TABLE[1]//TR[1]",
            "raw_inner_hash": "hash-row-001",
            "extracted_value": "holder=(주)케이피티유, shares=18502826, stake=19.21%"
        }
    ]

    corp_code_set = {"00117027", "00357607"}
    name_to_corps = {
        "(주)알루코": {"00117027"},
        "알루코": {"00117027"},
        "(주)케이피티유": {"00357607"},
        "케이피티유": {"00357607"}
    }
    code_to_master_name = {
        "00117027": "알루코",
        "00357607": "케이피티유"
    }

    return candidate, fragments, corp_code_set, name_to_corps, code_to_master_name


def test_clean_candidate_passes():
    """정상 후보 및 파편은 반드시 PASS 판정을 받아야 함"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "PASS", f"예상 PASS 실패: {res}"
    assert len(res["failure_reasons"]) == 0
    print("✅ Test 1 통과: 무결한 기준 후보 PASS 확인")


def test_rule1_tampered_company_name_rejection():
    """Rule 1: 후보 대상회사명이 마스터 회사명과 다를 경우 반드시 REJECT"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    # 변조: 대상회사명을 엉뚱한 이름으로 위조
    cand["target_corp_name"] = "변조된가짜바이오"
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "REJECT", f"변조된 회사명이 거부되지 않음: {res['verdict']}"
    assert any("대상회사명 마스터 불일치" in r for r in res["failure_reasons"])
    print("✅ Test 2 통과: 변조된 대상회사명 REJECT 차단 확인")


def test_rule4_tampered_reporter_fragment_rejection():
    """Rule 4: 보고자 증거 파편 값이 후보 보고자와 다를 경우 반드시 REJECT"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    # 변조: 보고자 파편 추출값을 위조
    frags[1]["extracted_value"] = "위조된_보고자성명"
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "REJECT", f"위조된 보고자 파편이 거부되지 않음: {res['verdict']}"
    assert any("REPORTER 파편 값 불일치" in r for r in res["failure_reasons"])
    print("✅ Test 3 통과: 위조된 보고자 파편 값 REJECT 차단 확인")


def test_rule4_tampered_row_holder_fragment_rejection():
    """Rule 4: 행 증거 파편의 보유자명이 후보 보유자와 다를 경우 반드시 REJECT"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    # 변조: 행 증거 파편에 기재된 보유자명을 다른 회사로 위조
    frags[3]["extracted_value"] = "holder=(주)엉뚱한다른회사, shares=18502826, stake=19.21%"
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "REJECT", f"위조된 보유자 행 증거가 거부되지 않음: {res['verdict']}"
    assert any("ROW_DATA_EVIDENCE 보유자 값 불일치" in r for r in res["failure_reasons"])
    print("✅ Test 4 통과: 위조된 행 증거 보유자 값 REJECT 차단 확인")


def test_rule5_invalid_calendar_date_rejection():
    """Rule 5: 달력상 존재하지 않는 날짜(예: 2월 30일)는 반드시 REJECT"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    # 변조: 존재하지 않는 2월 30일 설정
    cand["reporting_obligation_date"] = "2024-02-30"
    frags[2]["extracted_value"] = "2024-02-30"
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "REJECT", f"비실존 달력 날짜가 거부되지 않음: {res['verdict']}"
    assert any("비실존 달력 일자" in r for r in res["failure_reasons"])
    print("✅ Test 5 통과: 비실존 달력 날짜(2024-02-30) REJECT 차단 확인")


def test_rule5_date_fragment_mismatch_rejection():
    """Rule 5: 후보의 날짜와 날짜 파편의 값이 다르면 반드시 REJECT"""
    cand, frags, cset, n2c, c2m = get_base_valid_candidate_and_frags()
    # 변조: 후보 날짜는 5월 10일인데 파편은 5월 11일
    cand["reporting_obligation_date"] = "2024-05-10"
    frags[2]["extracted_value"] = "2024-05-11"
    res = evaluate_single_candidate(cand, frags, cset, n2c, c2m)
    assert res["verdict"] == "REJECT", f"날짜 불일치 후보가 거부되지 않음: {res['verdict']}"
    assert any("후보-파편 날짜 값 불일치" in r for r in res["failure_reasons"])
    print("✅ Test 6 통과: 후보-파편 간 날짜 불일치 REJECT 차단 확인")


if __name__ == "__main__":
    print("=" * 70)
    print("🏛️ [DART-Trace] 엔티티 해소 변조 증거값 REJECT 단정 테스트")
    print("=" * 70)
    test_clean_candidate_passes()
    test_rule1_tampered_company_name_rejection()
    test_rule4_tampered_reporter_fragment_rejection()
    test_rule4_tampered_row_holder_fragment_rejection()
    test_rule5_invalid_calendar_date_rejection()
    test_rule5_date_fragment_mismatch_rejection()
    print("=" * 70)
    print("🎯 모든 변조 증거 REJECT 단정 테스트 6/6 전수 통과!")
    print("=" * 70)
