# -*- coding: utf-8 -*-
r"""
🏛️ [DART-Trace] 네트워크 독립 저장 엔진 완결 수용시험 (8대 방어벽 검증)
================================================================================
네트워크 통신 0건 보장 (MockDartTransport 가짜 전송 어댑터 기반)
1. [테스트 1] 14자리 공시 접수번호 형식 검증 (^\d{14}$ 이외의 경로 순회/변조 거부)
2. [테스트 2] 정상 ZIP 수신 ➔ XML 원자적 저장 및 내부 메타데이터(발행회사/서식명) 자체 추출 검증
3. [테스트 3] 파손 ZIP 수신 ➔ quarantine/ 격리 및 manifests/ 영수증 동시 발급 실측
4. [테스트 4] 비XML ZIP 수신 ➔ XML 부재 오류 탐지 및 quarantine/ 격리
5. [테스트 5] 대용량 압축(Zip Bomb) 시도 ➔ 용량 상한 초과 탐지 및 안전 차단
6. [테스트 6] 파일 쓰기 원자성(Atomic Write) 검증 (임시 파일 교체)
7. [테스트 7] 동일 rcept_no에 상충 바이트 유입 ➔ 기존 파일 100% 보존 및 CONFLICT_QUARANTINED 발급
8. [테스트 8] 멱등성 검증: 로컬 캐시 존재 시 Transport 호출 0건 (network_request_made: False)
================================================================================
"""

import os
import io
import sys
import json
import zipfile
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
MockDartTransport = storage_mod.MockDartTransport
compute_bytes_sha256 = storage_mod.compute_bytes_sha256
validate_rcept_no = storage_mod.validate_rcept_no
inspect_and_extract_zip = storage_mod.inspect_and_extract_zip
atomic_write_bytes = storage_mod.atomic_write_bytes


def create_zip_bytes(filename_inside: str, content_inside: bytes) -> bytes:
    """테스트용 인메모리 ZIP 바이트 생성 도우미"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename_inside, content_inside)
    return buf.getvalue()


class TestRawEvidenceStorageEngineContracts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_storage_dir = "내작업폴더/data/raw_filings/mock_contract_test"
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

        # 실제 fixture 로드 (삼성전자 20241025000551)
        fixture_path = "내작업폴더/data/fixtures/xml_5pct_samples/20241025000551.xml"
        with open(fixture_path, "rb") as f:
            cls.sample_xml_bytes = f.read()

        cls.sample_rcept_no = "20241025000551"

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

    def setUp(self):
        # 각 테스트마다 전용 격리 하위 디렉토리 생성
        self.sub_test_dir = os.path.join(self.test_storage_dir, self._testMethodName)
        os.makedirs(self.sub_test_dir, exist_ok=True)
        self.mock_transport = MockDartTransport()
        self.engine = RawEvidenceStorageEngine(base_dir=self.sub_test_dir, transport=self.mock_transport)

    # -----------------------------------------------------------------
    # 테스트 1: 14자리 공시 접수번호 형식 검증
    # -----------------------------------------------------------------
    def test_01_invalid_rcept_no_rejected(self):
        """14자리가 아닌 접수번호나 경로 순회 시도 거부 검증"""
        invalid_cases = [
            "12345",
            "../../etc/passwd",
            "20241025000551/foo",
            "20241025000551a",
            "202410250005511", # 15자리
            "              "
        ]
        for inv in invalid_cases:
            self.assertFalse(validate_rcept_no(inv), f"유효하지 않은 rcept_no가 통과됨: {inv}")
            receipt = self.engine.fetch_and_store(inv)
            self.assertEqual(receipt["collection_status"], "REJECTED_INVALID_RCEPT_NO_FORMAT")
            self.assertFalse(receipt["network_request_made"])

        print("  [테스트 1 통과] 14자리 외 접수번호 및 경로순회 공격 거부 100% 확인")

    # -----------------------------------------------------------------
    # 테스트 2: 정상 ZIP 수신 ➔ XML 원자적 저장 및 내부 메타데이터 자체 추출
    # -----------------------------------------------------------------
    def test_02_mock_normal_zip_stored_and_metadata_extracted(self):
        """정상 ZIP 수신 시 XML 저장 및 XML 내부 메타데이터(발행회사/서식명) 자체 추출 검증"""
        zip_bytes = create_zip_bytes("document.xml", self.sample_xml_bytes)
        self.mock_transport.set_response(self.sample_rcept_no, 200, zip_bytes)

        receipt = self.engine.fetch_and_store(self.sample_rcept_no)

        self.assertEqual(receipt["collection_status"], "STORED")
        self.assertTrue(receipt["network_request_made"])
        self.assertEqual(receipt["http_status_code"], 200)
        self.assertEqual(receipt["xml_sha256"], compute_bytes_sha256(self.sample_xml_bytes))

        # [핵심 검증] XML 내부 메타데이터 자체 추출 확인
        meta = receipt.get("extracted_metadata", {})
        self.assertEqual(meta.get("extracted_corp_code"), "00126380")
        self.assertEqual(meta.get("extracted_corp_name"), "삼성전자")
        self.assertIn("대량보유상황보고서", meta.get("extracted_doc_title", ""))

        # 디스크 파일 존재 확인
        xml_file = os.path.join(self.engine.xml_dir, f"{self.sample_rcept_no}.xml")
        self.assertTrue(os.path.exists(xml_file))

        print("  [테스트 2 통과] 정상 ZIP 수신 ➔ 원자적 저장 및 내부 메타데이터 자체 추출 확인")

    # -----------------------------------------------------------------
    # 테스트 3: 파손 ZIP 수신 ➔ quarantine/ 격리 및 manifests/ 영수증 동시 발급
    # -----------------------------------------------------------------
    def test_03_mock_corrupted_zip_quarantined_with_receipt(self):
        """파손 ZIP 유입 시 엔진의 정상 경로를 통한 quarantine/ 바이너리 격리 및 영수증 발급 검증"""
        corrupted_bytes = b"BROKEN_ZIP_HEADER_NOT_A_REAL_ZIP_FILE"
        broken_rcept = "20240909000123"
        self.mock_transport.set_response(broken_rcept, 200, corrupted_bytes)

        receipt = self.engine.fetch_and_store(broken_rcept)

        self.assertEqual(receipt["collection_status"], "CORRUPTED_XML")
        self.assertTrue(receipt["network_request_made"])
        self.assertIn("INSPECT_ZIP_FAILED", receipt["error_message"])

        # quarantine/ 에 바이너리 파일 저장 확인
        q_files = [f for f in os.listdir(self.engine.quarantine_dir) if broken_rcept in f and f.endswith(".bin")]
        self.assertTrue(len(q_files) > 0, "quarantine 디렉토리에 파손 파일 미생성!")

        # manifests/ 에 격리 영수증 JSON 생성 확인
        m_files = [f for f in os.listdir(self.engine.manifests_dir) if broken_rcept in f and "corrupted" in f]
        self.assertTrue(len(m_files) > 0, "manifests 디렉토리에 격리 영수증 JSON 미생성!")

        print("  [테스트 3 통과] 파손 ZIP 유입 시 quarantine 바이너리 격리 및 영수증 동시 발급 실측 성공")

    # -----------------------------------------------------------------
    # 테스트 4: 비XML ZIP 수신 ➔ XML 부재 오류 탐지 및 quarantine/ 격리
    # -----------------------------------------------------------------
    def test_04_mock_non_xml_zip_quarantined(self):
        """ZIP 내부에 .xml 파일이 전혀 없는 경우 격리 처리 검증"""
        non_xml_zip = create_zip_bytes("readme.txt", b"This is plain text, not XML.")
        bad_rcept = "20240808000456"
        self.mock_transport.set_response(bad_rcept, 200, non_xml_zip)

        receipt = self.engine.fetch_and_store(bad_rcept)

        self.assertEqual(receipt["collection_status"], "CORRUPTED_XML")
        self.assertIn("NO_XML_FILE_IN_ZIP", receipt["error_message"])

        q_files = [f for f in os.listdir(self.engine.quarantine_dir) if bad_rcept in f]
        self.assertTrue(len(q_files) > 0)
        print("  [테스트 4 통과] 비XML ZIP 수신 시 안전 격리 및 에러 영수증 발급 확인")

    # -----------------------------------------------------------------
    # 테스트 5: 대용량 압축(Zip Bomb) 시도 ➔ 용량 상한 초과 탐지 및 안전 차단
    # -----------------------------------------------------------------
    def test_05_mock_zip_bomb_oversized_rejected(self):
        """압축 해제 크기 상한(50MB) 초과 시 Zip Bomb 탐지 검증"""
        # inspect_and_extract_zip 직접 호출로 1KB 상한 초과 시뮬레이션
        large_content = b"A" * 2048 # 2KB
        large_zip = create_zip_bytes("big.xml", large_content)

        with self.assertRaises(ValueError) as ctx:
            inspect_and_extract_zip(large_zip, max_uncompressed_bytes=1024) # 1KB 상한

        self.assertIn("ZIP_BOMB_DETECTED", str(ctx.exception))
        print("  [테스트 5 통과] Zip Bomb(압축 해제 상한 초과) 원천 차단 검증 완료")

    # -----------------------------------------------------------------
    # 테스트 6: 파일 쓰기 원자성(Atomic Write) 검증
    # -----------------------------------------------------------------
    def test_06_atomic_write_integrity(self):
        """임시 파일 생성 후 os.replace()를 통한 원자적 교체 검증"""
        test_file = os.path.join(self.sub_test_dir, "test_atomic.dat")
        data1 = b"INITIAL_CONTENT"
        atomic_write_bytes(test_file, data1)
        with open(test_file, "rb") as f:
            self.assertEqual(f.read(), data1)

        data2 = b"NEW_ATOMIC_CONTENT"
        atomic_write_bytes(test_file, data2)
        with open(test_file, "rb") as f:
            self.assertEqual(f.read(), data2)

        print("  [테스트 6 통과] 원자적(Atomic) 파일 쓰기 무결성 확인")

    # -----------------------------------------------------------------
    # 테스트 7: 동일 rcept_no에 상충 바이트 유입 ➔ 기존 파일 보존 및 CONFLICT_QUARANTINED
    # -----------------------------------------------------------------
    def test_07_conflict_quarantine_never_overwrites(self):
        """기존 rcept_no에 다른 바이트 유입 시 기존 파일 100% 보존 및 CONFLICT_QUARANTINED 실측"""
        # 1. 초기 파일 저장
        zip_bytes = create_zip_bytes("document.xml", self.sample_xml_bytes)
        self.mock_transport.set_response(self.sample_rcept_no, 200, zip_bytes)
        rcpt1 = self.engine.fetch_and_store(self.sample_rcept_no)
        self.assertEqual(rcpt1["collection_status"], "STORED")

        # 기존 파일 원본 해시
        target_path = os.path.join(self.engine.xml_dir, f"{self.sample_rcept_no}.xml")
        with open(target_path, "rb") as f:
            orig_bytes = f.read()
        orig_sha = compute_bytes_sha256(orig_bytes)

        # 2. 변조된 상충 바이트 주입
        tampered_bytes = self.sample_xml_bytes + b"<!-- CONFLICT -->"
        rcpt_conflict = self.engine.store_raw_xml_bytes(tampered_bytes, self.sample_rcept_no)

        self.assertEqual(rcpt_conflict["collection_status"], "CONFLICT_QUARANTINED")

        # [핵심 검증] 기존 파일이 덮어쓰여지지 않고 원형 그대로 보존되었는가!
        with open(target_path, "rb") as f:
            current_bytes = f.read()
        self.assertEqual(compute_bytes_sha256(current_bytes), orig_sha, "기존 XML이 덮어쓰여져 훼손됨!")

        # quarantine/ 에 격리 파일 생성 확인
        q_conflicts = [f for f in os.listdir(self.engine.quarantine_dir) if "conflict" in f and self.sample_rcept_no in f]
        self.assertTrue(len(q_conflicts) > 0)

        print("  [테스트 7 통과] 상충 바이트 시 기존 파일 100% 불변 보존 및 CONFLICT_QUARANTINED 확인")

    # -----------------------------------------------------------------
    # 테스트 8: 멱등성 검증: 로컬 캐시 존재 시 Transport 호출 0건
    # -----------------------------------------------------------------
    def test_08_idempotency_skip_local(self):
        """로컬 캐시가 이미 존재할 경우 Transport.fetch() 호출이 0건임을 검증"""
        # 1회차 수집
        zip_bytes = create_zip_bytes("document.xml", self.sample_xml_bytes)
        self.mock_transport.set_response(self.sample_rcept_no, 200, zip_bytes)
        self.engine.fetch_and_store(self.sample_rcept_no)
        self.assertEqual(len(self.mock_transport.call_history), 1)

        # 2회차 호출: 캐시 존재로 네트워크 호출 스킵되어야 함
        rcpt2 = self.engine.fetch_and_store(self.sample_rcept_no)
        self.assertEqual(rcpt2["collection_status"], "SKIPPED_LOCAL_PRESENT")
        self.assertFalse(rcpt2["network_request_made"])
        self.assertIsNone(rcpt2["http_status_code"])

        # Transport 호출 횟수가 여전히 1이어야 함 (2회차는 0건 추가)
        self.assertEqual(len(self.mock_transport.call_history), 1, "캐시가 있는데 전송 계층이 추가 호출됨!")

        print("  [테스트 8 통과] 멱등성 검증: 로컬 캐시 존재 시 네트워크 호출 정확히 0건 확인")


if __name__ == "__main__":
    unittest.main()
