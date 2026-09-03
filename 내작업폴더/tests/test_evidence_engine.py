# -*- coding: utf-8 -*-
"""
🧪 [Unit Test] 다층 증거 온톨로지 엔진 단위 테스트 (test_evidence_engine.py)
- 오프라인/비파괴(Zero DB Write)
- 실존 5% 공시 XML 기반 RawHoldingFact, EvidenceFragment, EvidenceBundle 검증
- 계약서(Promotion Contract) 3단계 승격 등급 및 상태 전이 실측
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("내작업폴더"))

from evidence_loader_engine import (
    RawHoldingFact,
    EvidenceFragment,
    EvidenceBundle,
    extract_evidence_from_5pct_xml
)

class TestEvidenceLoaderEngine(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.samsung_xml_path = "scratch/xml_5pct_samples/20241025000551.xml"
        cls.nps_xml_path = "scratch/xml_5pct_samples/20240925000388.xml"

    def test_01_general_5pct_evidence_extraction(self):
        """[일반보고] 삼성물산 ➔ 삼성전자 5% 공시: 팩트 추출, 해시 결속, 상태 전이 검증"""
        if not os.path.exists(self.samsung_xml_path):
            self.skipTest("삼성물산 5% XML 캐시 파일 부재")
            
        with open(self.samsung_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        facts, fragments, bundles = extract_evidence_from_5pct_xml(
            xml_bytes=xml_bytes,
            rcept_no="20241025000551",
            target_corp_code="00126380"
        )
        
        self.assertGreater(len(facts), 0, "RawHoldingFact 추출 실패")
        self.assertGreater(len(fragments), 0, "EvidenceFragment 추출 실패")
        self.assertGreater(len(bundles), 0, "EvidenceBundle 추출 실패")
        
        # 1. 삼성물산 Fact 검증
        ss_fact = next((f for f in facts if "삼성물산" in f.holder_raw_name), None)
        self.assertIsNotNone(ss_fact)
        self.assertEqual(ss_fact.shares_count, 298818100)
        self.assertEqual(ss_fact.stake_ratio, 5.01)
        self.assertEqual(ss_fact.source_report_tp, "5PCT_GENERAL")
        
        # 2. 기준일 Fragment 검증
        date_frag = next((fr for fr in fragments if fr.evidence_role == "AS_OF_DATE"), None)
        self.assertIsNotNone(date_frag)
        self.assertEqual(date_frag.extracted_value, "2024-10-22")
        self.assertEqual(len(date_frag.raw_inner_hash), 64, "SHA-256 해시 규격 불일치")
        
        # 3. 소유형태 Fragment 검증 (제142조 제1호 자기계산 보유)
        ss_owner_frag = next((fr for fr in fragments if fr.evidence_role == "OWNERSHIP_BASIS" and "ARTICLE_142_ITEM_1" in fr.extracted_value), None)
        self.assertIsNotNone(ss_owner_frag)
        
        # 4. 삼성물산 Bundle 검증
        ss_bundle = next((b for b in bundles if "삼성물산" in b.holder_key), None)
        self.assertIsNotNone(ss_bundle)
        self.assertEqual(ss_bundle.as_of_date, "2024-10-22")
        self.assertEqual(ss_bundle.bundle_status, "PARTIALLY_EVIDENCED")
        self.assertIn("VERIFIED_ECONOMIC_HOLDING", ss_bundle.eligible_tiers)
        # 계약서 준수: 개별 의결권 증거(분자)가 결속되지 않았으므로 Tier 2/3로 무단 승격되지 않음!
        self.assertNotIn("VERIFIED_VOTING_HOLDING", ss_bundle.eligible_tiers)
        print(f"\n  [Pass] 일반보고(삼성물산) Bundle 상태: {ss_bundle.bundle_status}, Tiers: {ss_bundle.eligible_tiers}")

    def test_02_simplified_5pct_evidence_extraction(self):
        """[약식보고] 국민연금공단 ➔ SK하이닉스 5% 공시: 소유형태 미기재 정상 처리 검증"""
        if not os.path.exists(self.nps_xml_path):
            self.skipTest("국민연금 5% XML 캐시 파일 부재")
            
        with open(self.nps_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        facts, fragments, bundles = extract_evidence_from_5pct_xml(
            xml_bytes=xml_bytes,
            rcept_no="20240925000388",
            target_corp_code="00164779"
        )
        
        self.assertGreater(len(facts), 0, "약식보고 팩트 추출 실패")
        nps_fact = next((f for f in facts if "국민연금" in f.holder_raw_name), None)
        self.assertIsNotNone(nps_fact)
        self.assertEqual(nps_fact.shares_count, 53477083)
        self.assertEqual(nps_fact.stake_ratio, 7.35)
        self.assertEqual(nps_fact.source_report_tp, "5PCT_SIMPLIFIED")
        
        nps_bundle = next((b for b in bundles if "국민연금" in b.holder_key), None)
        self.assertIsNotNone(nps_bundle)
        self.assertFalse(nps_bundle.evidence_mask["OWNERSHIP"], "약식보고는 소유형태 미기재 정상 상태여야 함")
        self.assertIn("VERIFIED_ECONOMIC_HOLDING", nps_bundle.eligible_tiers)
        print(f"  [Pass] 약식보고(국민연금) Bundle 상태: {nps_bundle.bundle_status}, Tiers: {nps_bundle.eligible_tiers}")

    def test_03_mobis_and_lg_general_5pct(self):
        """[일반보고] 현대모비스(현대차) & ㈜LG(LG화학): Fact, Fragment, Tier 1 승격 검증"""
        for r_no, c_code, expected_holder in [
            ("20240503000063", "00164742", "현대모비스"),
            ("20241129001948", "00356361", "LG")
        ]:
            xml_path = f"scratch/xml_5pct_samples/{r_no}.xml"
            if not os.path.exists(xml_path):
                continue
            with open(xml_path, "rb") as f:
                xml_bytes = f.read()
            facts, fragments, bundles = extract_evidence_from_5pct_xml(xml_bytes, r_no, c_code)
            self.assertGreater(len(facts), 0, f"{expected_holder} 팩트 추출 실패")
            target_fact = next((f for f in facts if expected_holder in f.holder_raw_name), None)
            self.assertIsNotNone(target_fact, f"{expected_holder} 팩트 검색 실패")
            target_bundle = next((b for b in bundles if expected_holder in b.holder_key), None)
            self.assertIsNotNone(target_bundle)
            self.assertIn("VERIFIED_ECONOMIC_HOLDING", target_bundle.eligible_tiers)
            print(f"  [Pass] 일반보고({expected_holder}) Fact: {target_fact.shares_count:,}주 ({target_fact.stake_ratio}%), Tiers: {target_bundle.eligible_tiers}")

if __name__ == "__main__":
    unittest.main()
