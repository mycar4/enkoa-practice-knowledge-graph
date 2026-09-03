# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] VERIFIED_ECONOMIC_HOLDING 승격 계약 순수 오프라인 단위 테스트
================================================================================
원칙:
- 운영 DB 연결 0건 (100% Mock / 오프라인)
- 5대 핵심 무결성 가드 실측 검증:
  1. 대상회사 고유 법인코드(corp_code) 8자리 완비 검증
  2. 보유자(HOLDER) 식별자 유일성 검증
  3. 보고자(REPORTER)와 보유자(HOLDER)의 독립 분리 및 불일치 시에도 보존 검증
  4. 주수·비율의 행 해시(raw_inner_hash) 1:1 결속 검증
  5. 보고의무발생일 != 공시접수일 날짜 의미 분리 검증
  6. 산출물 온톨로지에서 OWNS_STAKE 배제 및 HOLDS_ECONOMIC_STAKE 매핑 검증
================================================================================
"""

import unittest
from unittest.mock import MagicMock, patch

import importlib
import sys
import os
sys.path.insert(0, os.path.abspath("내작업폴더"))
verifier_mod = importlib.import_module("single_candidate_economic_holding_verifier")
verify_single_candidate = verifier_mod.verify_single_candidate


class TestEconomicHoldingVerifierOffline(unittest.TestCase):

    @patch("neo4j.GraphDatabase.driver")
    def test_01_successful_economic_holding_promotion_contract(self, mock_driver_fn):
        """[가드 1-6] 5대 요건 전수 충족 시 VERIFIED_ECONOMIC_HOLDING 승격 스펙 생성 검증"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver_fn.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock Candidate
        mock_cand_record = MagicMock()
        mock_cand_record.data.return_value = {
            "candidate_id": "cand-20241231000388-abcb57e77f16f345",
            "rcept_no": "20241231000388",
            "corp_name": "주식회사 파인메딕스",
            "corp_code": "01455410",
            "reporter_name": "전성우",
            "holder_name": "오희숙",
            "shares": 94100,
            "ratio": 1.67,
            "ob_date": "2024-12-26",
            "layout_status": "SUPPORTED_5PCT_GENERAL",
            "legacy_status": None,
            "rejection_reason": None,
            "xml_sha256": "be4b4650cca8eda6e47b2983972ad9ac09cb7800451cbe1146260960f2a2da26",
            "xml_rel_path": "xml/20241231000388.xml",
            "col_run": "batch_1500_20260903_051738",
            "col_rcpt": "rcpt-20260903051741-20241231000388-be4b4650",
            "load_run": "load_full_1500_20260903_055400",
            "load_rcpt": "ldrcpt-load_full_1500_20260903_055400-cand-20241231000388-abcb57e77f16f345",
            "created_at": "2026-09-03T05:54:01.000Z"
        }

        # Mock Fragments
        mock_frag_records = [
            MagicMock(data=lambda: {
                "frag_id": "frag-20241231000388-target-corp",
                "role": "TARGET_COMPANY",
                "extracted_value": "name=주식회사 파인메딕스, code=01455410",
                "xpath": "/DOCUMENT/BODY/TABLE[1]",
                "raw_inner_hash": "target_hash_1234567890",
                "xml_sha256": "be4b4650...",
                "created_at": "2026-09-03T05:54:01.000Z"
            }),
            MagicMock(data=lambda: {
                "frag_id": "frag-20241231000388-reporter",
                "role": "REPORTER",
                "extracted_value": "전성우",
                "xpath": "/DOCUMENT/BODY/TABLE[2]",
                "raw_inner_hash": "reporter_hash_12345678",
                "xml_sha256": "be4b4650...",
                "created_at": "2026-09-03T05:54:01.000Z"
            }),
            MagicMock(data=lambda: {
                "frag_id": "frag-20241231000388-row-data",
                "role": "ROW_DATA_EVIDENCE",
                "extracted_value": "holder=오희숙, shares=94100, stake=1.67%",
                "xpath": "/DOCUMENT/BODY/TABLE[3]/TR[2]",
                "raw_inner_hash": "abcb57e77f16f34599c43d4c10b3dd348f2e810f1df8565246343edb8ab849e5",
                "xml_sha256": "be4b4650...",
                "created_at": "2026-09-03T05:54:01.000Z"
            }),
            MagicMock(data=lambda: {
                "frag_id": "frag-20241231000388-ob-date",
                "role": "REPORTING_OBLIGATION_DATE",
                "extracted_value": "2024-12-26",
                "xpath": "/DOCUMENT/BODY/TABLE[4]",
                "raw_inner_hash": "ob_date_hash_123456789",
                "xml_sha256": "be4b4650...",
                "created_at": "2026-09-03T05:54:01.000Z"
            })
        ]

        mock_session.run.side_effect = [
            MagicMock(single=lambda: mock_cand_record),
            mock_frag_records
        ]

        res = verify_single_candidate("cand-20241231000388-abcb57e77f16f345")

        self.assertEqual(res["dry_run_verdict"], "PROMOTION_READY")
        self.assertEqual(res["checklist"]["1_target_company_identifier"]["status"], "PASS")
        self.assertEqual(res["checklist"]["2_holder_master_resolution"]["status"], "PASS")
        self.assertEqual(res["checklist"]["3_reporter_holder_separation"]["status"], "PASS")
        self.assertFalse(res["checklist"]["3_reporter_holder_separation"]["is_same_person"])
        self.assertEqual(res["checklist"]["4_metrics_and_row_hash_binding"]["status"], "PASS")
        self.assertTrue(res["checklist"]["4_metrics_and_row_hash_binding"]["candidate_id_hash_matched"])
        self.assertEqual(res["checklist"]["5_temporal_semantics_separation"]["status"], "PASS")
        self.assertFalse(res["checklist"]["5_temporal_semantics_separation"]["is_obligation_same_as_filing"])

        # 산출물 검증
        fact = res["promoted_fact"]
        self.assertEqual(fact["fact_type"], "VERIFIED_ECONOMIC_HOLDING")
        self.assertEqual(fact["target_company"]["corp_code"], "01455410")
        self.assertEqual(fact["holder"]["name"], "오희숙")
        self.assertEqual(fact["reporter_provenance"]["reporter_name"], "전성우")
        self.assertEqual(fact["economic_holding_metric"]["shares_count"], 94100)
        self.assertEqual(fact["temporal_semantics"]["reporting_obligation_date"], "2024-12-26")
        self.assertEqual(fact["graph_ontology_mapping"]["relationship_type"], ":HOLDS_ECONOMIC_STAKE")
        self.assertEqual(fact["graph_ontology_mapping"]["strictly_forbidden_relationship"], ":OWNS_STAKE")
        print("  [가드 통과] VERIFIED_ECONOMIC_HOLDING 5대 승격 계약 오프라인 실측 완수")


if __name__ == "__main__":
    unittest.main()
