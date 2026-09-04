# -*- coding: utf-8 -*-
"""
단일 기업 4단 의사결정 리포트 서비스 & 데이터 계약 정밀 회귀 테스트
================================================================================
- 1단: 공시 사실 원천 수치 및 실제 관찰 기간(date_coverage) 정확성
- 2단: 규칙 기반 관찰 지표(rule_version, basis_rcept_nos, disclaimer) 정직성
- 3단: 증거 등급 분리 (FILING_LINK_ONLY vs ROW_HASH_BOUND) 정확성
- 4단: 5% 후보의 미검증 상태(UNVERIFIED_EXTRACTED_CANDIDATE) 및 승격 지분 0건 유지
================================================================================
"""

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.decision_report_service import DecisionReportService


def test_decision_report_data_contract_rigorous():
    service = DecisionReportService()
    try:
        report = service.generate_company_decision_report("HLB")
        
        # 1. 기본 상태 및 기업 마스터 검증
        assert report["status"] == "SUCCESS", f"Expected SUCCESS, got {report.get('status')}"
        assert "target_company" in report
        assert report["target_company"]["corp_code"] == "00199252"
        assert report["target_company"]["corp_name"] == "HLB"
        
        # 2. [Tier 1: 사실] 관찰 기간 및 미가공 수치 검증
        facts = report["tier1_facts"]
        assert "date_coverage" in facts
        cov = facts["date_coverage"]
        assert cov["start_date"] is not None, "Date coverage start_date must not be None"
        assert cov["end_date"] is not None, "Date coverage end_date must not be None"
        assert cov["observed_events_count"] >= 1
        assert "2년" not in cov["description"], "Should not hardcode '2년' without actual date filter"
        
        # 지분 현황: 미검증 후보 상태 및 승격 지분 0건 확인
        holdings = facts["major_holdings_summary"]
        assert holdings["promoted_count"] == 0, "Promoted stakes must be 0 before execution approval"
        assert len(holdings["promoted_stakes"]) == 0
        assert holdings["raw_candidate_count"] > 0
        for cand in holdings["raw_candidates"]:
            assert cand["status"] == "UNVERIFIED_EXTRACTED_CANDIDATE", f"Invalid status: {cand['status']}"
            assert cand["status_label"] == "미검증 원문 추출 후보"
            assert cand["holder_name"] is not None
            assert cand["rcept_no"] is not None
        
        # 3. [Tier 2: 관찰 지표] 규칙 기반 정직한 지표 및 시나리오 검증
        interp = report["tier2_interpretations"]
        assert interp["rule_version"] == "RULE_HEURISTIC_v1.0"
        assert interp["observation_code"] in ["OBS_WATCH_HIGH", "OBS_WATCH_MODERATE", "OBS_NORMAL"]
        assert isinstance(interp["basis_rcept_nos"], list)
        assert len(interp["basis_rcept_nos"]) > 0, "Should have basis rcept_nos for observed capital events"
        assert isinstance(interp["basis_event_dates"], list)
        assert "disclaimer" in interp
        assert "투자 자문이나 주가 예측이 아닙니다" in interp["disclaimer"]
        
        # 시나리오 검증
        scenarios = interp["tracking_scenarios"]
        assert scenarios["scenario_type"] == "추적 관찰용 시나리오 (참고용 - 가격 예측 아님)"
        assert "bull_case" in scenarios
        assert "base_case" in scenarios
        assert "bear_case" in scenarios
        
        # 4. [Tier 3: 원문 근거] 정직한 증거 등급 분리 검증
        evidence = report["tier3_evidence"]
        assert isinstance(evidence, list)
        assert len(evidence) > 0
        
        cap_ev_found = False
        stake_ev_found = False
        
        for ev in evidence:
            assert "evidence_level" in ev
            if ev["evidence_level"] == "FILING_LINK_ONLY":
                # 자본이벤트는 공시 링크만 존재해야 하며, 가짜 XPath나 해시가 없어야 함
                cap_ev_found = True
                assert ev["xpath"] is None, "FILING_LINK_ONLY must have xpath=None"
                assert ev["inner_hash"] is None, "FILING_LINK_ONLY must have inner_hash=None"
                assert "행 단위 2D 해시 미적재" in ev["evidence_note"]
            elif ev["evidence_level"] == "ROW_HASH_BOUND":
                # 5% 공시 후보는 파서 추출 좌표와 원문 행 해시가 존재해야 함
                stake_ev_found = True
                assert ev["xpath"] is not None, "ROW_HASH_BOUND must have parser xpath"
                assert ev["inner_hash"] is not None, "ROW_HASH_BOUND must have real inner_hash"
                assert "[미검증 원문 추출 후보]" in ev["title"]
                assert "파서 추출 좌표 + 원문 행 SHA-256 결속" == ev["evidence_note"]
        
        assert cap_ev_found, "Must contain at least one FILING_LINK_ONLY capital event evidence"
        assert stake_ev_found, "Must contain at least one ROW_HASH_BOUND stake candidate evidence"
        
        # 5. [Tier 4: 다음 확인 항목] 실사 체크리스트 검증
        actions = report["tier4_next_actions"]
        assert isinstance(actions, list)
        assert len(actions) >= 4
        
        print("✅ test_decision_report_data_contract_rigorous passed perfectly!")
    finally:
        service.close()


def test_company_search_find_companies():
    service = DecisionReportService()
    try:
        results = service.find_companies("HLB")
        assert isinstance(results, list)
        assert len(results) > 0
        assert any(r["corp_code"] == "00199252" for r in results)
        print("✅ test_company_search_find_companies passed!")
    finally:
        service.close()


def test_promoted_company_contract_aluko():
    service = DecisionReportService()
    try:
        report = service.generate_company_decision_report("00117027")  # 알루코
        assert report["status"] == "SUCCESS"
        assert report["target_company"]["corp_name"] == "알루코"

        holdings = report["tier1_facts"]["major_holdings_summary"]
        assert holdings["promoted_count"] == 1, f"Expected 1 promoted stake for Aluko, got {holdings['promoted_count']}"
        
        promoted = holdings["promoted_stakes"][0]
        assert promoted["holder_name"] == "케이피티유"
        assert promoted["target_name"] == "알루코"
        assert promoted["holder_to_target"] == "케이피티유 → 알루코"
        assert promoted["stake_ratio"] == 19.21
        assert promoted["shares_count"] == 18502826
        assert promoted["reporting_obligation_date"] == "2023-08-04"
        assert promoted["row_inner_hash"].startswith("def7b651")
        assert promoted["status"] == "VERIFIED_ECONOMIC_STAKE"
        assert promoted["status_label"] == "검증·승격 완료"

        # 미검증 후보와 분리 확인
        assert "raw_candidates" in holdings
        
        # 증거 분리 확인
        evidence = report["tier3_evidence"]
        promoted_ev = [ev for ev in evidence if ev.get("item_type") == "PROMOTED_ECONOMIC_STAKE"]
        assert len(promoted_ev) >= 1
        assert "HOLDS_ECONOMIC_STAKE" in promoted_ev[0]["evidence_note"]
        print("✅ test_promoted_company_contract_aluko passed!")
    finally:
        service.close()


if __name__ == "__main__":
    test_decision_report_data_contract_rigorous()
    test_company_search_find_companies()
    test_promoted_company_contract_aluko()
    print("🎉 ALL RIGOROUS MENU 2 TESTS PASSED!")
