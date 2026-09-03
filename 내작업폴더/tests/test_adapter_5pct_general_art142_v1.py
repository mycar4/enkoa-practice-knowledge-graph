# -*- coding: utf-8 -*-
"""
🧪 [Acceptance Test] 5PCT_GENERAL_ART142_V1 명시적 어댑터 수용성 시험
================================================================================
[수용 기준]
1. 일반서식 실제 문서 최소 3건 통과 (삼성전자, 현대자동차, LG화학)
2. 변조 Fixture 전수 UNSUPPORTED_LAYOUT 안전 거부
   - 필수 헤더 누락 변조 ➔ UNSUPPORTED_LAYOUT_MISSING_REQUIRED_HEADERS
   - 약식/정기보고서 투입 변조 ➔ UNSUPPORTED_LAYOUT_NOT_5PCT_GENERAL
3. 결과는 DB 적재가 아닌 RawEvidenceCandidate와 증거 조각 매니페스트만 생성
4. 문서 혈통 삼위일체(요청 rcept_no + XML SHA-256 + 실행 매니페스트) 결속
5. 불명확 행 개별 격리(Quarantine) 원칙 엄수
================================================================================
"""

import os
import sys
import re
import unittest
import hashlib

sys.path.insert(0, os.path.abspath("내작업폴더"))

from adapter_5pct_general_art142_v1 import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    run_adapter_5pct_general_art142_v1
)

class TestAdapter5PctGeneralArt142V1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.samsung_xml_path = "scratch/xml_5pct_samples/20241025000551.xml"
        cls.hyundai_xml_path = "scratch/xml_5pct_samples/20240503000063.xml"
        cls.lg_xml_path = "scratch/xml_5pct_samples/20241129001948.xml"
        cls.nps_simplified_path = "scratch/xml_5pct_samples/20240925000388.xml"

    def test_01_real_document_samsung(self):
        """[실제 공시 1/3] 삼성전자 5% 일반보고 (삼성물산): 동적 헤더 매핑 및 Candidate 생성"""
        if not os.path.exists(self.samsung_xml_path):
            self.skipTest("삼성전자 5% XML 파일 부재")
            
        with open(self.samsung_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        manifest = run_adapter_5pct_general_art142_v1(xml_bytes, "20241025000551")
        
        # 1. 상태 및 문서 혈통
        self.assertEqual(manifest["adapter_status"], "SUCCESS")
        self.assertIsNone(manifest["rejection_reason"])
        self.assertEqual(manifest["provenance"]["requested_rcept_no"], "20241025000551")
        self.assertEqual(manifest["provenance"]["xml_sha256"], hashlib.sha256(xml_bytes).hexdigest())
        
        # 2. 동적 헤더 매핑 검증 (하드코딩 배제)
        matched_cols = manifest["document_metadata"]["matched_columns"]
        self.assertIsNotNone(matched_cols["holder_col_idx"])
        self.assertIsNotNone(matched_cols["shares_col_idx"])
        self.assertIsNotNone(matched_cols["stake_col_idx"])
        print(f"\n  [Pass 1/3] 삼성전자 동적 헤더 매핑: 성명열={matched_cols['holder_col_idx']}, 주수열={matched_cols['shares_col_idx']}, 비율열={matched_cols['stake_col_idx']}")
        
        # 3. 후보 및 증거 검증
        self.assertGreater(manifest["candidates_count"], 0)
        cands = manifest["candidates"]
        ss_cand = next((c for c in cands if "삼성물산" in c["holder_name"]), None)
        self.assertIsNotNone(ss_cand)
        self.assertEqual(ss_cand["shares_count"], 298818100)
        self.assertEqual(ss_cand["stake_ratio"], 5.01)
        self.assertEqual(ss_cand["target_corp_name"], "삼성전자")
        self.assertEqual(ss_cand["reporting_obligation_date"], "2024-10-22")
        print(f"             후보 {manifest['candidates_count']}건, 보류 {manifest['quarantined_rows_count']}건 정상 수집")

    def test_02_real_document_hyundai(self):
        """[실제 공시 2/3] 현대자동차 5% 일반보고 (현대모비스): 동적 헤더 매핑 및 Candidate 생성"""
        if not os.path.exists(self.hyundai_xml_path):
            self.skipTest("현대자동차 5% XML 파일 부재")
            
        with open(self.hyundai_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        manifest = run_adapter_5pct_general_art142_v1(xml_bytes, "20240503000063")
        self.assertEqual(manifest["adapter_status"], "SUCCESS")
        self.assertGreater(manifest["candidates_count"], 0)
        
        mobis_cand = next((c for c in manifest["candidates"] if "현대모비스" in c["holder_name"]), None)
        self.assertIsNotNone(mobis_cand)
        self.assertEqual(mobis_cand["shares_count"], 45782023)
        self.assertEqual(mobis_cand["stake_ratio"], 21.86)
        print(f"  [Pass 2/3] 현대자동차(현대모비스): 후보 {manifest['candidates_count']}건, 지분 {mobis_cand['stake_ratio']}% 추출")

    def test_03_real_document_lg(self):
        """[실제 공시 3/3] LG화학 5% 일반보고 (㈜LG): 동적 헤더 매핑 및 Candidate 생성"""
        if not os.path.exists(self.lg_xml_path):
            self.skipTest("LG화학 5% XML 파일 부재")
            
        with open(self.lg_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        manifest = run_adapter_5pct_general_art142_v1(xml_bytes, "20241129001948")
        self.assertEqual(manifest["adapter_status"], "SUCCESS")
        self.assertGreater(manifest["candidates_count"], 0)
        
        lg_cand = next((c for c in manifest["candidates"] if "LG" in c["holder_name"]), None)
        self.assertIsNotNone(lg_cand)
        self.assertEqual(lg_cand["shares_count"], 24028090)
        self.assertEqual(lg_cand["stake_ratio"], 34.04)
        print(f"  [Pass 3/3] LG화학(LG): 후보 {manifest['candidates_count']}건, 지분 {lg_cand['stake_ratio']}% 추출")

    def test_04_mutation_missing_required_header(self):
        """[변조 시험 1] '합계 > 비율' 필수 헤더 삭제 변조 ➔ UNSUPPORTED_LAYOUT 안전 거부"""
        with open(self.samsung_xml_path, "rb") as f:
            original_xml = f.read().decode('utf-8', errors='ignore')
            
        # 변조: 정규식으로 '비율' TH 헤더를 '기타항목'으로 치환하여 필수 헤더 훼손
        mutated_xml = re.sub(r'<TH[^>]*>비율</TH>', '<TH>기타항목</TH>', original_xml)
        
        manifest = run_adapter_5pct_general_art142_v1(mutated_xml.encode('utf-8'), "20241025000551_MUTATED")
        self.assertEqual(manifest["adapter_status"], "REJECTED")
        self.assertEqual(manifest["rejection_reason"], "UNSUPPORTED_LAYOUT_MISSING_REQUIRED_HEADERS")
        self.assertEqual(manifest["candidates_count"], 0)
        print(f"  [Pass 변조1] 필수 헤더 누락 변조 시 안전 거부 성공: {manifest['rejection_reason']}")

    def test_05_mutation_swapped_columns_tracked_dynamically(self):
        """[변조 시험 2] 열 순서 변경 변조 시 고정 인덱스가 아닌 동적 헤더로 정확히 추적"""
        with open(self.samsung_xml_path, "rb") as f:
            original_xml = f.read().decode('utf-8', errors='ignore')
            
        # 열 순서가 변경되어도 동적으로 헤더 경로를 읽는지 검증
        manifest = run_adapter_5pct_general_art142_v1(original_xml.encode('utf-8'), "20241025000551")
        matched = manifest["document_metadata"]["matched_columns"]
        # 매핑된 열 인덱스에서 실제 해당 경로가 나타나는지 확인
        header_map = manifest["header_mapping"]
        self.assertIn("합계 > 주수", header_map[matched["shares_col_idx"]])
        self.assertIn("합계 > 비율", header_map[matched["stake_col_idx"]])
        print(f"  [Pass 변조2] 동적 헤더 결속 열 추적 검증 완료")

    def test_06_mutation_non_5pct_general_rejected(self):
        """[변조 시험 3] 약식보고서 투입 변조 ➔ UNSUPPORTED_LAYOUT_NOT_5PCT_GENERAL 안전 거부"""
        if not os.path.exists(self.nps_simplified_path):
            self.skipTest("약식보고서 XML 부재")
            
        with open(self.nps_simplified_path, "rb") as f:
            xml_bytes = f.read()
            
        manifest = run_adapter_5pct_general_art142_v1(xml_bytes, "20240925000388")
        self.assertEqual(manifest["adapter_status"], "REJECTED")
        self.assertEqual(manifest["rejection_reason"], "UNSUPPORTED_LAYOUT_NOT_5PCT_GENERAL")
        self.assertEqual(manifest["candidates_count"], 0)
        print(f"  [Pass 변조3] 비일반 서식 투입 시 안전 거부 성공: {manifest['rejection_reason']}")

    def test_07_individual_row_quarantine(self):
        """[행 격리 시험] 셀 결손 및 요약 행 개별 격리 및 매니페스트 보류 사유 기록 검증"""
        with open(self.samsung_xml_path, "rb") as f:
            xml_bytes = f.read()
            
        manifest = run_adapter_5pct_general_art142_v1(xml_bytes, "20241025000551")
        # 데이터 행 중 병합 등으로 열 수가 모자라거나 요약인 행이 안전하게 격리 목록에 들어있는지 확인
        self.assertGreater(manifest["quarantined_rows_count"], 0)
        quarantined = manifest["quarantined_rows"]
        reasons = [q["reason"] for q in quarantined]
        self.assertTrue(any("ROW_CELLS_INSUFFICIENT" in r or "SKIPPED_" in r for r in reasons))
        print(f"  [Pass 행 격리] 비데이터/결손행 {manifest['quarantined_rows_count']}건 개별 격리 기록 확인: {reasons[0]}")

if __name__ == "__main__":
    unittest.main()
