# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 실제 OpenDART API 문서 단 1건 수동 스모크 검증
================================================================================
⚠️ 주의: 본 테스트는 기본 unittest discover 시 실행되지 않으며, 
명시적인 환경변수 RUN_DART_LIVE_TESTS=1 이 지정될 때만 단독 수동 실행됩니다.
수집된 XML 원문과 영수증 매니페스트는 검수용으로 영구 보존(tearDown 삭제 없음)됩니다.
================================================================================
"""

import os
import sys
import unittest
import importlib

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
RawEvidenceStorageEngine = storage_mod.RawEvidenceStorageEngine
compute_bytes_sha256 = storage_mod.compute_bytes_sha256


@unittest.skipUnless(
    os.getenv("RUN_DART_LIVE_TESTS") == "1",
    "실제 DART API 호출은 RUN_DART_LIVE_TESTS=1 환경변수 지정 시에만 수동 실행됩니다."
)
class TestRealApiSingleFetch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 영구 보존용 스모크 아카이브 디렉토리 (자동 삭제 안 함)
        cls.smoke_archive_dir = "내작업폴더/data/raw_filings/smoke_live_archive"
        os.makedirs(cls.smoke_archive_dir, exist_ok=True)
        cls.engine = RawEvidenceStorageEngine(base_dir=cls.smoke_archive_dir)

    def test_01_real_network_fetch_and_metadata_audit(self):
        """[실측 스모크] 실제 OpenDART API 1건 수집 ➔ XML 내부 메타데이터 대조 검증 및 영구 보존"""
        # 검증 대상: 삼성전자 5% 일반보고서 (2024.10.25 접수)
        target_rcept_no = "20241025000551"

        receipt = self.engine.fetch_and_store(
            rcept_no=target_rcept_no,
            force_refresh=False
        )

        # 1. 상태 및 네트워크 검증
        self.assertIn(receipt["collection_status"], ["STORED", "SKIPPED_LOCAL_PRESENT"])
        self.assertGreater(receipt["xml_size_bytes"], 1000)
        self.assertIsNotNone(receipt["xml_sha256"])

        # 2. [가장 중요] XML 내부에서 자체 추출된 메타데이터 검증
        meta = receipt.get("extracted_metadata", {})
        self.assertEqual(meta.get("extracted_corp_code"), "00126380", f"법인코드 불일치: {meta}")
        self.assertEqual(meta.get("extracted_corp_name"), "삼성전자", f"회사명 불일치: {meta}")
        self.assertIn("대량보유상황보고서", meta.get("extracted_doc_title", ""))

        # 3. 디스크 파일 존재 확인 (영구 보존됨)
        xml_file = os.path.join(self.engine.xml_dir, f"{target_rcept_no}.xml")
        self.assertTrue(os.path.exists(xml_file), f"XML 파일 미생성: {xml_file}")

        # 4. 동일 문서 2회차 호출 시 멱등성 검증
        receipt2 = self.engine.fetch_and_store(rcept_no=target_rcept_no, force_refresh=False)
        self.assertEqual(receipt2["collection_status"], "SKIPPED_LOCAL_PRESENT")
        self.assertFalse(receipt2["network_request_made"])
        self.assertIsNone(receipt2["http_status_code"])

        print(f"\n  [실제 API 스모크 통과] rcept_no={target_rcept_no}")
        print(f"    • 추출된 법인코드: {meta.get('extracted_corp_code')}")
        print(f"    • 추출된 회사명: {meta.get('extracted_corp_name')}")
        print(f"    • 공시 서식명: {meta.get('extracted_doc_title')}")
        print(f"    • 원문 크기: {receipt['xml_size_bytes']:,} bytes")
        print(f"    • 원문 SHA-256: {receipt['xml_sha256']}")
        print(f"    • 영구 보존 위치: {xml_file}")


if __name__ == "__main__":
    unittest.main()
