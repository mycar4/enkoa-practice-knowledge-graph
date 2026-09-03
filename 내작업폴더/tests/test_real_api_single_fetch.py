# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 실제 OpenDART API 문서 단 1건 수집 실측 검증
================================================================================
1. [실측 1] 실제 OpenDART document.xml 1건 다운로드 ➔ ZIP 압축 해제 ➔ XML 저장 ➔ STORED 영수증 발급
2. [실측 2] 동일 1건 재호출 시 네트워크 요청 스킵(network_request_made: False, 쿼터 소진 0) 검증
3. [실측 3] 수신된 XML SHA-256 해시 무결성 검증
4. [실측 4] 유효하지 않은 rcept_no 호출 시 FAILED_DOWNLOAD 처리 및 API 키 비노출(마스킹) 검증
================================================================================
"""

import os
import sys
import shutil
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


class TestRealApiSingleFetch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 단 1건 실측 전용 격리 디렉토리
        cls.test_storage_dir = "내작업폴더/data/raw_filings/single_api_test"
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

        cls.engine = RawEvidenceStorageEngine(base_dir=cls.test_storage_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

    def test_01_real_network_fetch_single_document(self):
        """[실측 1] 실제 OpenDART API 호출로 1건(삼성전자 5% 일반) 수집 및 STORED 영수증 검증"""
        # 검증 대상: 삼성전자 5% 일반보고서 (2024.10.25 접수)
        target_rcept_no = "20241025000551"
        target_corp_code = "00126380"
        target_corp_name = "삼성전자"

        receipt = self.engine.fetch_and_store(
            rcept_no=target_rcept_no,
            corp_code=target_corp_code,
            corp_name=target_corp_name,
            report_nm="주식등의대량보유상황보고서(일반)",
            rcept_dt="20241025",
            force_refresh=False
        )

        # 1. 수집 결과 검증
        self.assertEqual(receipt["collection_status"], "STORED", f"수집 실패: {receipt}")
        self.assertTrue(receipt["network_request_made"])
        self.assertEqual(receipt["http_status_code"], 200)
        self.assertGreater(receipt["xml_size_bytes"], 1000)
        self.assertIsNotNone(receipt["xml_sha256"])

        # 2. 실제 디스크 파일 존재 검증
        xml_file = os.path.join(self.engine.xml_dir, f"{target_rcept_no}.xml")
        self.assertTrue(os.path.exists(xml_file), f"XML 파일 미생성: {xml_file}")

        receipt_file = os.path.join(self.engine.manifests_dir, f"receipt_{target_rcept_no}_{receipt['xml_sha256'][:8]}.json")
        self.assertTrue(os.path.exists(receipt_file), f"영수증 파일 미생성: {receipt_file}")

        # 3. 디스크에 저장된 바이트의 해시와 영수증 해시 일치 검증
        with open(xml_file, "rb") as f:
            actual_bytes = f.read()
        self.assertEqual(compute_bytes_sha256(actual_bytes), receipt["xml_sha256"])

        print(f"  [실측 1 통과] 실제 API 수집 성공: rcept_no={target_rcept_no}, 크기={receipt['xml_size_bytes']:,} bytes, 해시={receipt['xml_sha256'][:10]}...")

    def test_02_real_idempotency_skip_network(self):
        """[실측 2] 동일 1건 재호출 시 네트워크 요청 0건 및 SKIPPED_LOCAL_PRESENT 검증"""
        target_rcept_no = "20241025000551"

        # force_refresh=False로 재호출
        receipt = self.engine.fetch_and_store(
            rcept_no=target_rcept_no,
            corp_code="00126380",
            corp_name="삼성전자"
        )

        self.assertEqual(receipt["collection_status"], "SKIPPED_LOCAL_PRESENT")
        self.assertFalse(receipt["network_request_made"], "오류: 캐시가 있는데 네트워크 요청이 실행됨!")
        self.assertIsNone(receipt["http_status_code"], "오류: 네트워크 미요청인데 HTTP 코드가 존재함!")
        self.assertEqual(receipt["source_note"], "LOCAL_CACHE_HIT_NO_API_CALL")

        print("  [실측 2 통과] 재실행 시 실제 네트워크 호출 0건 확인 (API 쿼터 소진 0건)")

    def test_03_invalid_rcept_no_api_key_redacted(self):
        """[실측 3] 비정상 rcept_no 호출 실패 시 에러 영수증 발급 및 API 키 비노출(마스킹) 검증"""
        invalid_rcept_no = "00000000000000"

        receipt = self.engine.fetch_and_store(
            rcept_no=invalid_rcept_no,
            corp_code="00000000",
            corp_name="가상회사"
        )

        self.assertIn(receipt["collection_status"], ["FAILED_DOWNLOAD", "CORRUPTED_XML"])
        self.assertTrue(receipt["network_request_made"])
        
        # [핵심 보안 검증] error_message에 API 키가 노출되지 않았는지 확인
        if receipt["error_message"]:
            self.assertNotIn(self.engine.api_key, receipt["error_message"], "치명적 보안 결함: 에러에 실제 API 키 노출!")
            if "crtfc_key=" in receipt["error_message"]:
                self.assertIn("crtfc_key=***REDACTED***", receipt["error_message"])

        print(f"  [실측 3 통과] 실패 시 안전 영수증 발급 및 API 키 비노출 확인: {receipt['collection_status']}")


if __name__ == "__main__":
    unittest.main()
