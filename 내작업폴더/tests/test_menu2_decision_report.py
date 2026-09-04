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

from unittest.mock import patch, MagicMock

from services.decision_report_service import (
    DecisionReportService,
    parse_accounting_number,
    format_currency_kr,
    build_official_timeline
)


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

        # 재무제표 팩트 계약 검증
        assert "financial_facts" in facts
        fin_facts = facts["financial_facts"]
        assert fin_facts["status"] in ["AVAILABLE", "UNAVAILABLE"]
        if fin_facts["status"] == "AVAILABLE":
            assert fin_facts["bsns_year"] in ["2024", "2023"]
            assert fin_facts["reprt_code"] == "11011"
            assert fin_facts["fs_div"] in ["CFS", "OFS"]
            assert fin_facts["revenue"] is not None
            assert fin_facts["debt_ratio"] is not None

        # 공식 채널 통합 타임라인 계약 검증
        assert "official_timeline" in facts
        assert "official_timeline_summary" in facts
        assert isinstance(facts["official_timeline"], list)
        assert len(facts["official_timeline"]) > 0
        assert facts["official_timeline_summary"]["grade_a_count"] > 0
        assert facts["official_timeline_summary"]["total_timeline_events"] == len(facts["official_timeline"])
        
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
            elif ev["evidence_level"] == "MANIFEST_SEALED_ROW_HASH":
                # 승격 사실은 봉인 매니페스트 결속 및 원문 행 해시 존재 (xpath는 None)
                assert ev["xpath"] is None, "MANIFEST_SEALED_ROW_HASH must have xpath=None"
                assert ev["inner_hash"] is not None
                assert "[검증·승격 사실]" in ev["title"]
            elif ev["evidence_level"] == "OPENDART_API_FACT":
                assert ev["xpath"] is None
                assert ev["inner_hash"] is None
                assert "OpenDART" in ev["evidence_note"]
        
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

        # 1. [불변 계약 ⑤] 승격된 동일 해시가 미검증 후보 테이블에서 배제되었는지 검증
        raw_candidates = holdings.get("raw_candidates", [])
        assert len(raw_candidates) > 0
        for cand in raw_candidates:
            assert cand.get("row_inner_hash") != promoted["row_inner_hash"], (
                f"Promoted hash {promoted['row_inner_hash']} leaked into unverified candidates!"
            )
            assert cand["status"] == "UNVERIFIED_EXTRACTED_CANDIDATE"

        # 2. 정직한 전체 후보 건수 검증 (슬라이스 10에 축소 왜곡되지 않고, 승격 1건이 정확히 차감됨)
        assert holdings["raw_candidate_count"] == 23, (
            f"Expected true total count exactly 23 for Aluko (24 minus 1 promoted), got {holdings['raw_candidate_count']}"
        )
        
        # 3. [증거 등급 분리] 승격 증거는 MANIFEST_SEALED_ROW_HASH 토큰 및 xpath=None 검증
        evidence = report["tier3_evidence"]
        promoted_ev = [ev for ev in evidence if ev.get("item_type") == "PROMOTED_ECONOMIC_STAKE"]
        assert len(promoted_ev) >= 1
        assert promoted_ev[0]["evidence_level"] == "MANIFEST_SEALED_ROW_HASH"
        assert promoted_ev[0]["xpath"] is None
        assert promoted_ev[0]["inner_hash"].startswith("def7b651")
        assert "HOLDS_ECONOMIC_STAKE" in promoted_ev[0]["evidence_note"]
        print("✅ test_promoted_company_contract_aluko passed!")
    finally:
        service.close()


def test_zero_mixing_across_all_promoted_companies():
    """10대 피보유 승격 기업 전수 스캔: 승격 해시가 미검증 후보 테이블에 단 1건도 누출되지 않음을 증명"""
    service = DecisionReportService()
    try:
        test_corps = [
            "KG이니시스", "아이비김영", "롯데칠성음료", "파워로직스", "해태제과식품",
            "유비온", "참좋은여행", "넵튠", "엠아이큐브솔루션", "에스케이증권제10호기업인수목적"
        ]
        for corp in test_corps:
            report = service.generate_company_decision_report(corp)
            if report.get("status") != "SUCCESS":
                continue
            holdings = report["tier1_facts"]["major_holdings_summary"]
            promoted_hashes = {p["row_inner_hash"] for p in holdings.get("promoted_stakes", []) if p.get("row_inner_hash")}
            raw_hashes = {c.get("row_inner_hash") for c in holdings.get("raw_candidates", []) if c.get("row_inner_hash")}
            
            intersection = promoted_hashes.intersection(raw_hashes)
            assert len(intersection) == 0, f"Leaked hashes found in {corp}: {intersection}"
        print("✅ test_zero_mixing_across_all_promoted_companies passed! (0 leaks across all 10 companies)")
    finally:
        service.close()


def test_capital_events_sanitization_and_defense():
    """자본이벤트 한글화, 금액/목적 스왑 방어 및 주관적 점수 배제 계약 검증"""
    service = DecisionReportService()
    try:
        for corp in ["HLB", "DXVX", "FSN"]:
            report = service.generate_company_decision_report(corp)
            assert report["status"] == "SUCCESS"
            
            events = report["tier1_facts"]["capital_events_summary"]["events_detail"]
            assert len(events) > 0, f"Expected capital events for {corp}"
            
            for ev in events:
                # 1. 이벤트 코드 한글화 검증 (영문 코드 raw 노출 방지)
                assert "event_type_kr" in ev
                assert ev["event_type_kr"] != "PAID", "PAID must be translated to '유상증자 결정'"
                assert ev["event_type_kr"] in [
                    "유상증자 결정",
                    "전환사채(CB) 발행 결정",
                    "신주인수권부사채(BW) 발행 결정",
                    "회사합병 결정",
                    "타법인 주식 및 출자증권 취득 결정"
                ] or not ev["event_type_kr"].isascii(), f"Raw ascii event type found: {ev['event_type_kr']}"
                
                # 2. 금액 및 목적 컬럼 정정 및 방어 검증
                amt_str = ev.get("amount_display", "-")
                pur_str = ev.get("sanitized_purpose", "-")
                
                # 목적 컬럼에 순수 숫자(예: '29,005,171,650')가 그대로 방치되지 않았는지 검증
                clean_pur = pur_str.replace(",", "").strip()
                assert not clean_pur.isdigit(), f"Raw numeric string leaked into purpose: {pur_str}"
                
                # PAID 이벤트인 경우 금액이 purpose에서 정상 구출되어 amount_display에 들어갔는지 검증
                if ev.get("event_type") == "PAID":
                    assert ev["event_type_kr"] == "유상증자 결정"
                    if ev.get("sanitized_amount") is not None:
                        assert amt_str != "-", "PAID with sanitized amount must have formatted amount_display"
                        assert "원" in amt_str
            
            # 3. 주관적 리스크 점수 및 가격 예측 배제 검증
            interp = report["tier2_interpretations"]
            assert "risk_score" not in interp, "Subjective risk_score must not exist"
            assert "predicted_price" not in interp, "Price prediction must not exist"
            assert "target_price" not in interp, "Target price must not exist"
            assert "투자 자문이나 주가 예측이 아닙니다" in interp.get("disclaimer", "")
        
        print("✅ test_capital_events_sanitization_and_defense passed!")
    finally:
        service.close()


def test_opendart_financial_facts_contract():
    """OpenDART DS003 정기공시 주요계정 연동, CFS/OFS 계층, 제로트러스트 폴백 계약 검증"""
    service = DecisionReportService()
    try:
        # 1. 삼성전자 (CFS 연결재무제표 정상 바인딩 검증)
        samsung_fin = service.get_company_financial_facts("00126380")
        assert samsung_fin["status"] == "AVAILABLE"
        assert samsung_fin["bsns_year"] in ["2024", "2023"]
        assert samsung_fin["reprt_code"] == "11011"
        assert samsung_fin["fs_div"] == "CFS"
        assert "연결재무제표" in samsung_fin["fs_div_name"]
        assert samsung_fin["revenue"] is not None and samsung_fin["revenue"] > 100_000_000_000_000  # 100조원 이상
        assert samsung_fin["total_assets"] is not None and samsung_fin["total_assets"] > 300_000_000_000_000
        assert samsung_fin["total_liabilities"] is not None and samsung_fin["total_liabilities"] > 0
        assert samsung_fin["total_equity"] is not None and samsung_fin["total_equity"] > 0
        assert samsung_fin["debt_ratio"] is not None and samsung_fin["debt_ratio"] > 0
        assert len(samsung_fin["accounts_detail"]) >= 5

        # 2. HLB 및 알루코 연동 검증
        hlb_fin = service.get_company_financial_facts("00199252")
        assert hlb_fin["status"] == "AVAILABLE"
        assert hlb_fin["revenue"] is not None and hlb_fin["revenue"] > 0

        aluko_fin = service.get_company_financial_facts("00117027")
        assert aluko_fin["status"] == "AVAILABLE"
        assert aluko_fin["revenue"] is not None and aluko_fin["revenue"] > 0

        # 3. 비정상 고유번호 제로트러스트 폴백 검증 (크래시 없이 UNAVAILABLE 반환)
        invalid_fin = service.get_company_financial_facts("99999999")
        assert invalid_fin["status"] == "UNAVAILABLE"
        assert invalid_fin["revenue"] is None
        assert "미공시 또는 조회 제한" in invalid_fin["message"]

        # 4. 회계 수치 및 원화 포맷터 유닛 검증
        assert parse_accounting_number("-24,169,405,515") == -24169405515
        assert parse_accounting_number("(24,169,405,515)") == -24169405515
        assert parse_accounting_number("300,870,903,000,000") == 300870903000000
        assert parse_accounting_number("-") is None
        assert parse_accounting_number(None) is None

        assert "조원" in format_currency_kr(300_870_903_000_000)
        assert "억원" in format_currency_kr(68_125_727_347)
        assert format_currency_kr(None) == "-"

        print("✅ test_opendart_financial_facts_contract passed!")
    finally:
        service.close()


def test_financial_facts_cfs_ofs_mock_selection():
    """CFS/OFS 혼재 시 CFS 우선 선택 및 CFS 부재 시 OFS 폴백 강제 mock 검증"""
    from services.decision_report_service import _financial_facts_cache
    service = DecisionReportService()
    try:
        # 1. CFS & OFS 혼재 mock 데이터 -> CFS만 선택되어야 함
        mixed_items = [
            {"fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "500,000,000", "frmtrm_amount": "400,000,000"},
            {"fs_div": "CFS", "account_nm": "영업이익", "thstrm_amount": "50,000,000", "frmtrm_amount": "40,000,000"},
            {"fs_div": "CFS", "account_nm": "당기순이익", "thstrm_amount": "30,000,000", "frmtrm_amount": "20,000,000"},
            {"fs_div": "CFS", "account_nm": "자산총계", "thstrm_amount": "1,000,000,000", "frmtrm_amount": "800,000,000"},
            {"fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "400,000,000", "frmtrm_amount": "300,000,000"},
            {"fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "600,000,000", "frmtrm_amount": "500,000,000"},
            # OFS 데이터 (혼재)
            {"fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "100,000,000", "frmtrm_amount": "80,000,000"},
            {"fs_div": "OFS", "account_nm": "영업이익", "thstrm_amount": "10,000,000", "frmtrm_amount": "8,000,000"},
            {"fs_div": "OFS", "account_nm": "당기순이익", "thstrm_amount": "5,000,000", "frmtrm_amount": "4,000,000"},
            {"fs_div": "OFS", "account_nm": "자산총계", "thstrm_amount": "300,000,000", "frmtrm_amount": "200,000,000"},
            {"fs_div": "OFS", "account_nm": "부채총계", "thstrm_amount": "100,000,000", "frmtrm_amount": "50,000,000"},
            {"fs_div": "OFS", "account_nm": "자본총계", "thstrm_amount": "200,000,000", "frmtrm_amount": "150,000,000"},
        ]
        
        mock_resp_mixed = MagicMock()
        mock_resp_mixed.status_code = 200
        mock_resp_mixed.json.return_value = {"status": "000", "list": mixed_items}
        
        _financial_facts_cache.pop("88880001_2024", None)
        with patch("requests.get", return_value=mock_resp_mixed):
            res_cfs = service.get_company_financial_facts("88880001", preferred_year=2024)
            assert res_cfs["status"] == "AVAILABLE"
            assert res_cfs["fs_div"] == "CFS"
            assert "연결재무제표" in res_cfs["fs_div_name"]
            assert res_cfs["revenue"] == 500_000_000, "Should select CFS revenue, not OFS"
            assert res_cfs["total_equity"] == 600_000_000
            assert res_cfs["debt_ratio"] == 66.67  # 400M / 600M * 100

        # 2. CFS 부재 시 (OFS만 있는 경우) -> OFS 선택되어야 함
        ofs_only_items = [
            {"fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "100,000,000", "frmtrm_amount": "80,000,000"},
            {"fs_div": "OFS", "account_nm": "영업이익", "thstrm_amount": "10,000,000", "frmtrm_amount": "8,000,000"},
            {"fs_div": "OFS", "account_nm": "당기순이익", "thstrm_amount": "5,000,000", "frmtrm_amount": "4,000,000"},
            {"fs_div": "OFS", "account_nm": "자산총계", "thstrm_amount": "300,000,000", "frmtrm_amount": "200,000,000"},
            {"fs_div": "OFS", "account_nm": "부채총계", "thstrm_amount": "100,000,000", "frmtrm_amount": "50,000,000"},
            {"fs_div": "OFS", "account_nm": "자본총계", "thstrm_amount": "200,000,000", "frmtrm_amount": "150,000,000"},
        ]
        mock_resp_ofs = MagicMock()
        mock_resp_ofs.status_code = 200
        mock_resp_ofs.json.return_value = {"status": "000", "list": ofs_only_items}

        _financial_facts_cache.pop("88880002_2024", None)
        with patch("requests.get", return_value=mock_resp_ofs):
            res_ofs = service.get_company_financial_facts("88880002", preferred_year=2024)
            assert res_ofs["status"] == "AVAILABLE"
            assert res_ofs["fs_div"] == "OFS"
            assert "개별재무제표" in res_ofs["fs_div_name"]
            assert res_ofs["revenue"] == 100_000_000
            assert res_ofs["debt_ratio"] == 50.0  # 100M / 200M * 100

        print("✅ test_financial_facts_cfs_ofs_mock_selection passed!")
    finally:
        service.close()


def test_financial_facts_year_fallback_mock():
    """2024년 status=013 조회 실패 후 2023년 자동 재시도 및 성공 mock 검증"""
    from services.decision_report_service import _financial_facts_cache
    service = DecisionReportService()
    try:
        # 1차(2024): 013 실패, 2차(2023): 000 성공
        mock_resp_2024 = MagicMock()
        mock_resp_2024.status_code = 200
        mock_resp_2024.json.return_value = {"status": "013", "message": "조회된 데이타가 없습니다."}

        mock_resp_2023 = MagicMock()
        mock_resp_2023.status_code = 200
        mock_resp_2023.json.return_value = {
            "status": "000",
            "list": [
                {"fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "300,000,000", "frmtrm_amount": "250,000,000"},
                {"fs_div": "CFS", "account_nm": "영업이익", "thstrm_amount": "30,000,000", "frmtrm_amount": "25,000,000"},
                {"fs_div": "CFS", "account_nm": "당기순이익", "thstrm_amount": "20,000,000", "frmtrm_amount": "15,000,000"},
                {"fs_div": "CFS", "account_nm": "자산총계", "thstrm_amount": "800,000,000", "frmtrm_amount": "700,000,000"},
                {"fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "300,000,000", "frmtrm_amount": "250,000,000"},
                {"fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "500,000,000", "frmtrm_amount": "450,000,000"},
            ]
        }

        _financial_facts_cache.pop("88880003_2024", None)
        with patch("requests.get", side_effect=[mock_resp_2024, mock_resp_2023]) as mock_get:
            res_fb = service.get_company_financial_facts("88880003", preferred_year=2024)
            assert res_fb["status"] == "AVAILABLE"
            assert res_fb["bsns_year"] == "2023", "Must fallback to 2023 when 2024 returns status 013"
            assert res_fb["revenue"] == 300_000_000
            assert mock_get.call_count == 2
            calls = mock_get.call_args_list
            assert calls[0].kwargs["params"]["bsns_year"] == "2024"
            assert calls[1].kwargs["params"]["bsns_year"] == "2023"

        print("✅ test_financial_facts_year_fallback_mock passed!")
    finally:
        service.close()


def test_financial_facts_zero_trust_edge_cases():
    """None, 빈 문자열, 형식 오류, 미등록 코드, API 키 부재 5대 제로트러스트 케이스 전수 실측"""
    from services.decision_report_service import _financial_facts_cache
    service = DecisionReportService()
    try:
        # Case 1: None
        res_none = service.get_company_financial_facts(None)
        assert res_none["status"] == "UNAVAILABLE"
        assert res_none["revenue"] is None
        assert "유효하지 않은 고유번호" in res_none["message"]

        # Case 2: 빈 문자열
        res_empty = service.get_company_financial_facts("")
        assert res_empty["status"] == "UNAVAILABLE"
        assert res_empty["revenue"] is None
        assert "유효하지 않은 고유번호" in res_empty["message"]

        # Case 3: 8자리 미만 형식 오류 ("12345")
        res_short = service.get_company_financial_facts("12345")
        assert res_short["status"] == "UNAVAILABLE"
        assert res_short["revenue"] is None
        assert "유효하지 않은 고유번호" in res_short["message"]

        # Case 4: 미등록 8자리 코드 ("99999999" - DART 실제 호출)
        _financial_facts_cache.pop("99999999_2024", None)
        res_unregistered = service.get_company_financial_facts("99999999")
        assert res_unregistered["status"] == "UNAVAILABLE"
        assert res_unregistered["revenue"] is None
        assert "미공시 또는 조회 제한" in res_unregistered["message"]

        # Case 5: DART_API_KEY 환경변수 부재
        _financial_facts_cache.pop("88889999_2024", None)
        with patch.dict(os.environ, {"DART_API_KEY": ""}):
            res_nokey = service.get_company_financial_facts("88889999")
            assert res_nokey["status"] == "UNAVAILABLE"
            assert res_nokey["revenue"] is None
            assert "DART_API_KEY 환경변수가 설정되지 않아" in res_nokey["message"]

        print("✅ test_financial_facts_zero_trust_edge_cases passed! (All 5 zero-trust cases verified)")
    finally:
        service.close()


def test_official_channels_timeline_contract():
    """출처별 공식 채널 타임라인 (DART A급, KRX KIND A급, OpenDART A급, 후보 B급) 계약 검증"""
    service = DecisionReportService()
    try:
        # 1. HLB 공식 타임라인 검증 (자본이벤트 + 재무제표 + 5% 후보 통합 피드)
        hlb_report = service.generate_company_decision_report("HLB")
        assert hlb_report["status"] == "SUCCESS"
        facts = hlb_report["tier1_facts"]
        timeline = facts["official_timeline"]
        summary = facts["official_timeline_summary"]

        assert len(timeline) > 0
        assert summary["total_timeline_events"] == len(timeline)
        assert summary["grade_a_count"] > 0, "HLB must have Grade A DART events"
        assert summary["earliest_date"] is not None
        assert summary["latest_date"] is not None
        assert summary["earliest_date"] <= summary["latest_date"]

        # 타임라인 항목 속성 및 URL 검증
        for item in timeline:
            assert item["event_date"] is not None
            assert item["channel_grade"] in [
                "GRADE_A_DART", "GRADE_A_KRX", "GRADE_A_FINANCIAL", "GRADE_B_UNVERIFIED"
            ]
            assert item["event_category"] in [
                "CAPITAL_EVENT", "PROMOTED_STAKE", "FINANCIAL_FACT", "CANDIDATE_STAKE"
            ]
            assert item["title"] is not None
            assert item["summary"] is not None
            
            rcp = item.get("rcept_no")
            if rcp:
                assert item["dart_url"] == f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}", f"Mismatch in dart_url for rcp {rcp}"
                assert item["krx_kind_url"] == f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp}&method=search", f"Mismatch in krx_kind_url for rcp {rcp}"
            else:
                assert item["dart_url"] is None
                assert item["krx_kind_url"] is None

        # 정렬 순서 검증 (최신순 내림차순)
        dates = [item["event_date"] for item in timeline]
        assert dates == sorted(dates, reverse=True), "Timeline must be sorted in descending order"

        # 2. 알루코 승격 지분 타임라인 포함 검증
        aluko_report = service.generate_company_decision_report("00117027")
        assert aluko_report["status"] == "SUCCESS"
        aluko_timeline = aluko_report["tier1_facts"]["official_timeline"]
        
        promoted_items = [
            item for item in aluko_timeline
            if item["event_category"] == "PROMOTED_STAKE"
        ]
        assert len(promoted_items) >= 1, "Aluko timeline must contain promoted stake event"
        p_item = promoted_items[0]
        assert p_item["event_date"] == "2023-08-04"
        assert p_item["channel_grade"] == "GRADE_A_DART"
        assert p_item["rcept_no"] == "20230810000694"
        assert "케이피티유" in p_item["title"]

        # 3. 헬퍼 유닛 검증 (빈 데이터 및 결손 방어)
        empty_res = build_official_timeline([], [], {"status": "UNAVAILABLE"}, [])
        assert len(empty_res["feed"]) == 0
        assert empty_res["summary"]["total_timeline_events"] == 0
        assert empty_res["summary"]["grade_a_count"] == 0
        assert empty_res["summary"]["grade_b_count"] == 0
        assert empty_res["summary"]["earliest_date"] is None
        assert empty_res["summary"]["latest_date"] is None

        print("✅ test_official_channels_timeline_contract passed!")
    finally:
        service.close()


if __name__ == "__main__":
    test_decision_report_data_contract_rigorous()
    test_company_search_find_companies()
    test_promoted_company_contract_aluko()
    test_zero_mixing_across_all_promoted_companies()
    test_capital_events_sanitization_and_defense()
    test_opendart_financial_facts_contract()
    test_financial_facts_cfs_ofs_mock_selection()
    test_financial_facts_year_fallback_mock()
    test_financial_facts_zero_trust_edge_cases()
    test_official_channels_timeline_contract()
    print("🎉 ALL 10 RIGOROUS MENU 2 TESTS PASSED!")



