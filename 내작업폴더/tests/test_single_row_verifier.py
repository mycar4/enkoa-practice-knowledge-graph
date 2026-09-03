# -*- coding: utf-8 -*-
"""
🧪 [Unit Test] 단 1건 안전한 RawHoldingFact 검증기 단위 테스트
- 오프라인/비파괴 (Zero DB Write)
- 5대 합격 계약 조건 전수 검증
- 보고자 != 보유자 분리 검증
- 원문 표기 보존(추론 금지) 검증
- 부적격 행 격리(Quarantine) 검증
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("내작업폴더"))

from single_row_evidence_verifier import (
    StrictRawHoldingFact,
    StrictEvidenceFragment,
    verify_single_row_from_5pct_xml
)

class TestSingleRowEvidenceVerifier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.samsung_xml_path = "scratch/xml_5pct_samples/20241025000551.xml"
        if not os.path.exists(cls.samsung_xml_path):
            raise FileNotFoundError(f"Fixture XML not found: {cls.samsung_xml_path}")
        with open(cls.samsung_xml_path, "rb") as f:
            cls.samsung_xml_bytes = f.read()

    def test_01_admit_single_row_fact_samsung_cnt(self):
        """[단 1건 합격] 삼성물산 행: 5대 계약 전수 통과 및 RawHoldingFact 인정 검증"""
        fact, fragments, audit = verify_single_row_from_5pct_xml(
            xml_bytes=self.samsung_xml_bytes,
            rcept_no="20241025000551",
            target_row_index=2 # 삼성물산주식회사 행
        )
        
        # 1. 5대 계약 감사 통과 확인
        self.assertTrue(audit["pass_all"], f"5대 계약 불합격: {audit['rejection_reason']}")
        self.assertTrue(audit["rule_1_header_coupled_metric"])
        self.assertTrue(audit["rule_2_reporter_evidence"])
        self.assertTrue(audit["rule_3_holder_evidence"])
        self.assertTrue(audit["rule_4_target_company_evidence"])
        self.assertTrue(audit["rule_5_date_with_type_evidence"])
        
        # 2. Fact 값 검증
        self.assertIsNotNone(fact)
        self.assertEqual(fact.reporter_name, "삼성물산주식회사")
        self.assertEqual(fact.holder_name, "삼성물산주식회사")
        self.assertEqual(fact.target_corp_name, "삼성전자")
        self.assertEqual(fact.target_corp_code, "00126380")
        self.assertEqual(fact.shares_count, 298818100)
        self.assertEqual(fact.stake_ratio, 5.01)
        self.assertEqual(fact.date_type, "REPORTING_OBLIGATION_DATE")
        self.assertEqual(fact.date_value, "2024-10-22")
        
        # 3. 추론 금지 원칙 검증: 제142조 제1호 원문 표기 그대로 보존
        self.assertEqual(fact.ownership_basis_raw, "ARTICLE_142_ITEM_1")
        # 4. 개별 의결권 미결속 검증: 분모 총수와 혼동하지 않고 None 유지
        self.assertIsNone(fact.individual_voting_raw)
        
        # 5. 증거 파편 결속 수 검증 (Comp, Rep, Date, Holder, Shares, Stake, Owner)
        self.assertEqual(len(fragments), 7)
        print(f"\n  [Pass] 단 1건 RawHoldingFact 승인: {fact.holder_name} -> {fact.target_corp_name} {fact.shares_count:,}주 ({fact.stake_ratio}%)")
        print(f"         증거 파편 수: {len(fragments)}개 (전수 inner HTML 해시 결속 완료)")

    def test_02_separate_reporter_and_holder(self):
        """[보고자 != 보유자 분리] 삼성생명보험 행: 보고자와 보유자의 엄격한 분리 보존 검증"""
        fact, fragments, audit = verify_single_row_from_5pct_xml(
            xml_bytes=self.samsung_xml_bytes,
            rcept_no="20241025000551",
            target_row_index=3 # 특별관계자 삼성생명보험 행
        )
        
        self.assertTrue(audit["pass_all"])
        self.assertIsNotNone(fact)
        # 보고자는 삼성물산이지만, 보유자는 삼성생명보험이어야 함!
        self.assertEqual(fact.reporter_name, "삼성물산주식회사")
        self.assertEqual(fact.holder_name, "삼성생명보험")
        self.assertEqual(fact.shares_count, 513938710)
        self.assertEqual(fact.stake_ratio, 8.61)
        self.assertNotEqual(fact.reporter_name, fact.holder_name, "보고자와 보유자가 분리되지 않고 오염됨!")
        print(f"  [Pass] 주체 분리 검증 성공: 보고자({fact.reporter_name}) != 보유자({fact.holder_name})")

    def test_03_quarantine_on_invalid_row(self):
        """[부적격 행 격리] 헤더 행 또는 잘못된 인덱스 요청 시 안전하게 None 반환 및 보류 사유 기록"""
        fact, fragments, audit = verify_single_row_from_5pct_xml(
            xml_bytes=self.samsung_xml_bytes,
            rcept_no="20241025000551",
            target_row_index=0 # 헤더 행
        )
        
        self.assertFalse(audit["pass_all"])
        self.assertIsNone(fact, "부적격 헤더 행이 Fact로 오인 승인됨!")
        self.assertIsNotNone(audit["rejection_reason"])
        print(f"  [Pass] 부적격 행 격리 성공: 사유={audit['rejection_reason']}")

if __name__ == "__main__":
    unittest.main()
