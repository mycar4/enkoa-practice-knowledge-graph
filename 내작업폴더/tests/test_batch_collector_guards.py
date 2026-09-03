# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 배치 제어기 4대 운영 가드 모의 검증 테스트
================================================================================
네트워크 호출 0건 (Mock 기반 정밀 단위 검증)
1. [가드 1-A] Content-Length 헤더 30MB 초과 시 413 거부 실측
2. [가드 1-B] 스트리밍 청크 누적 30MB 초과 시 413 조기 차단 실측
3. [가드 2] 429 ➔ 503 ➔ 200 지수 백오프 3회 시퀀스 재시도 성공 실측
4. [가드 3] 연속 5건 실패 시 서킷 브레이커 즉시 발동 및 잔여 작업 100% 차단
5. [가드 4 & 5] 영수증 전수 감사 및 모든 일치 조건(5대 항목) 성공 판정 실측
6. [가드 5-반증] 메타데이터/해시 불일치 시 BATCH_AUDIT_REJECTED 엄격 거부 실측
================================================================================
"""

import os
import io
import sys
import json
import shutil
import zipfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
import importlib

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
MockDartTransport = storage_mod.MockDartTransport
RealDartHttpTransport = storage_mod.RealDartHttpTransport

batch_mod = importlib.import_module("00_DART_Batch_Collector_1500")
BatchCollector1500 = batch_mod.BatchCollector1500
run_batch_deep_closure_audit = batch_mod.run_batch_deep_closure_audit


def create_zip_bytes(filename_inside: str, content_inside: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename_inside, content_inside)
    return buf.getvalue()


class TestBatchCollectorGuards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_base_dir = "내작업폴더/data/raw_filings/batch_guards_test"
        if os.path.exists(cls.test_base_dir):
            shutil.rmtree(cls.test_base_dir)

        # 삼성전자 XML fixture 준비
        fixture_path = "내작업폴더/data/fixtures/xml_5pct_samples/20241025000551.xml"
        with open(fixture_path, "rb") as f:
            cls.sample_xml_bytes = f.read()

        cls.sample_zip = create_zip_bytes("document.xml", cls.sample_xml_bytes)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_base_dir):
            shutil.rmtree(cls.test_base_dir)

    def test_01_content_length_exceeded_guard(self):
        """[가드 1-A] Content-Length 헤더 30MB 초과 시 413 즉시 거부 실측"""
        transport = RealDartHttpTransport(api_key="test_api_key", max_payload_bytes=30 * 1024 * 1024)

        # Mock HTTP 응답: Content-Length = 35MB
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Length": "36700160"}  # 35MB

        with patch("urllib.request.urlopen", return_value=mock_resp):
            status, data, err = transport.fetch("20241025000551")

        self.assertEqual(status, 413)
        self.assertEqual(data, b"")
        self.assertIn("PAYLOAD_EXCEEDED_MAX_LIMIT_30MB: Content-Length=36700160", err)
        print("  [가드 1-A 통과] Content-Length 35MB 초과 시 413 즉시 차단 실측 성공")

    def test_02_stream_chunk_exceeded_guard(self):
        """[가드 1-B] 헤더 없이 청크 스트리밍 중 30MB 상한 도달 시 413 조기 차단 실측"""
        # 테스트를 위해 상한을 50KB로 낮추어 실측
        transport = RealDartHttpTransport(api_key="test_api_key", max_payload_bytes=50 * 1024)

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {}  # Content-Length 없음
        # 64KB 청크 반환 (50KB 상한 초과 유발)
        mock_resp.read.side_effect = [b"A" * (64 * 1024), b""]

        with patch("urllib.request.urlopen", return_value=mock_resp):
            status, data, err = transport.fetch("20241025000551")

        self.assertEqual(status, 413)
        self.assertEqual(data, b"")
        self.assertIn("PAYLOAD_EXCEEDED_MAX_LIMIT_30MB: stream exceeded 51200", err)
        print("  [가드 1-B 통과] 스트림 누적 바이트 상한 초과 시 413 조기 차단 실측 성공")

    def test_03_retry_sequence_429_503_200(self):
        """[가드 2] 429 ➔ 503 ➔ 200 3회 시퀀스 재시도 및 최종 성공 실측"""
        transport = RealDartHttpTransport(
            api_key="test_api_key",
            max_retries=3,
            retry_backoff_base=0.001  # 테스트 속도를 위해 1ms 백오프
        )

        # 3회 호출 모의: 1차 429, 2차 503, 3차 200 OK
        err_429 = HTTPError("http://dummy", 429, "Too Many Requests", {}, None)
        err_503 = HTTPError("http://dummy", 503, "Service Unavailable", {}, None)

        mock_resp_200 = MagicMock()
        mock_resp_200.__enter__.return_value = mock_resp_200
        mock_resp_200.getcode.return_value = 200
        mock_resp_200.headers = {"Content-Length": str(len(self.sample_zip))}
        mock_resp_200.read.side_effect = [self.sample_zip, b""]

        with patch("urllib.request.urlopen", side_effect=[err_429, err_503, mock_resp_200]) as mock_urlopen:
            status, data, err = transport.fetch("20241025000551")

        self.assertEqual(status, 200)
        self.assertEqual(data, self.sample_zip)
        self.assertIsNone(err)
        self.assertEqual(mock_urlopen.call_count, 3, "정확히 3회 시도 후 성공해야 함!")
        print("  [가드 2 통과] 429 ➔ 503 ➔ 200 지수 백오프 시퀀스 재시도 성공 실측 완료")

    def test_04_circuit_breaker_emergency_abort_on_5_failures(self):
        """[가드 3] 연속 5건 실패 시 서킷 브레이커 즉시 발동 및 잔여 작업 비상 중단 검증"""
        run_dir_base = os.path.join(self.test_base_dir, "test_circuit_breaker")
        mock_transport = MockDartTransport()

        # 10개 대상 중 앞 5개는 500 에러, 뒤 5개는 정상
        targets = []
        for i in range(1, 11):
            rcpt = f"2024010100000{i}"
            targets.append({
                "rcept_no": rcpt,
                "expected_corp_code": "00126380",
                "expected_corp_name": "테스트"
            })
            if i <= 5:
                mock_transport.set_response(rcpt, 500, b"", "Internal Server Error")
            else:
                mock_transport.set_response(rcpt, 200, self.sample_zip)

        collector = BatchCollector1500(
            base_runs_dir=run_dir_base,
            max_consecutive_failures=5,
            rate_limit_delay_sec=0.0,
            transport=mock_transport
        )

        run_id, run_dir, manifest_sha = collector.init_run(targets, run_id_prefix="cb_test")
        summary = collector.execute_batch(run_id, run_dir, manifest_sha, targets)

        self.assertTrue(summary["circuit_breaker_tripped"], "서킷 브레이커 미발동!")
        self.assertEqual(summary["processed_count"], 5, "5건 실패 후 즉시 중단되지 않고 추가 실행됨!")
        self.assertIn("CIRCUIT_BREAKER_TRIGGERED", summary["abort_reason"])

        # 체크포인트 파일 확인
        chk_path = os.path.join(run_dir, "checkpoint.json")
        self.assertTrue(os.path.exists(chk_path))
        with open(chk_path, "r", encoding="utf-8") as cf:
            chk = json.load(cf)
        self.assertTrue(chk["circuit_breaker_tripped"])
        self.assertEqual(chk["processed_count"], 5)

        # 6~10번째 대상은 네트워크 호출 자체가 0건이어야 함
        called_targets = mock_transport.call_history
        self.assertEqual(len(called_targets), 5)
        for i in range(6, 11):
            self.assertNotIn(f"2024010100000{i}", called_targets, "중단 이후 항목이 호출됨!")

        print("  [가드 3 통과] 연속 5건 실패 시 서킷 브레이커 즉시 발동 및 잔여 5건 호출 100% 차단 확인")

    def test_05_lineage_and_deep_closure_audit_success(self):
        """[가드 4 & 5] 영수증 전수 열람 및 5대 일치 조건 충족 시 BATCH_VERIFIED_SUCCESS 실측"""
        run_dir_base = os.path.join(self.test_base_dir, "test_deep_audit_success")
        mock_transport = MockDartTransport()

        targets = [
            {"rcept_no": "20241025000551", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"},
            {"rcept_no": "20241025000552", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"}
        ]
        for t in targets:
            mock_transport.set_response(t["rcept_no"], 200, self.sample_zip)

        collector = BatchCollector1500(base_runs_dir=run_dir_base, rate_limit_delay_sec=0.0, transport=mock_transport)
        run_id, run_dir, manifest_sha = collector.init_run(targets, run_id_prefix="audit_ok_test")
        collector.execute_batch(run_id, run_dir, manifest_sha, targets)

        # 심층 감사 실행
        closure_report = run_batch_deep_closure_audit(run_dir)

        self.assertEqual(closure_report["run_id"], run_id)
        self.assertEqual(closure_report["total_targets"], 2)
        self.assertEqual(closure_report["total_receipts_audited"], 2)
        self.assertTrue(closure_report["all_run_ids_matched"])
        self.assertTrue(closure_report["all_manifest_shas_matched"])
        self.assertTrue(closure_report["all_rcept_nos_matched"])
        self.assertTrue(closure_report["all_xml_hashes_matched"])
        self.assertTrue(closure_report["all_corp_codes_matched"])
        self.assertEqual(closure_report["audit_verdict"], "BATCH_VERIFIED_SUCCESS")

        print("  [가드 4 & 5 통과] 영수증 전수 열람 및 5대 조건 전수 일치 시 BATCH_VERIFIED_SUCCESS 확인")

    def test_06_deep_closure_audit_strictly_rejects_on_mismatch(self):
        """[가드 5-반증] 법인코드 불일치 시 BATCH_AUDIT_REJECTED로 엄격 거부 실측"""
        run_dir_base = os.path.join(self.test_base_dir, "test_deep_audit_reject")
        mock_transport = MockDartTransport()

        # 삼성전자 XML(00126380)을 반환하지만, 기대 법인코드가 99999999로 불일치하는 경우
        targets = [
            {"rcept_no": "20241025000551", "expected_corp_code": "99999999", "expected_corp_name": "가짜회사"}
        ]
        mock_transport.set_response("20241025000551", 200, self.sample_zip)

        collector = BatchCollector1500(base_runs_dir=run_dir_base, rate_limit_delay_sec=0.0, transport=mock_transport)
        run_id, run_dir, manifest_sha = collector.init_run(targets, run_id_prefix="reject_test")
        collector.execute_batch(run_id, run_dir, manifest_sha, targets)

        # 심층 감사 실행
        closure_report = run_batch_deep_closure_audit(run_dir)

        self.assertFalse(closure_report["all_corp_codes_matched"], "법인코드 불일치가 감지되어야 함!")
        self.assertEqual(closure_report["audit_verdict"], "BATCH_AUDIT_REJECTED", "불일치 시 승인되면 안 됨!")
        print("  [가드 5-반증 통과] 법인코드 불일치 시 BATCH_AUDIT_REJECTED로 엄격 거부 확인")

    def test_07_source_manifest_lineage_and_resume_mode(self):
        """[재개 및 혈통] 원천 매니페스트 해시 결속 및 --resume 체크포인트 재개 실측"""
        run_dir_base = os.path.join(self.test_base_dir, "test_resume")
        mock_transport = MockDartTransport()

        # 1. 원천 매니페스트 생성
        source_manifest_file = os.path.join(self.test_base_dir, "dummy_source_manifest.json")
        targets = [
            {"rcept_no": f"2024102500055{i}", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"}
            for i in range(1, 6)
        ]
        with open(source_manifest_file, "w", encoding="utf-8") as sf:
            json.dump({"targets": targets}, sf)

        for t in targets:
            mock_transport.set_response(t["rcept_no"], 200, self.sample_zip)

        collector = BatchCollector1500(base_runs_dir=run_dir_base, rate_limit_delay_sec=0.0, transport=mock_transport)

        # 2. 원천 매니페스트 기반 초기화
        run_id, run_dir, in_sha = collector.init_run(source_manifest_path=source_manifest_file, run_id_prefix="resume_test")

        # 3. 1차 실행: 앞 2개만 실행 후 중단 시뮬레이션
        partial_targets = targets[:2]
        collector.execute_batch(run_id, run_dir, in_sha, partial_targets, resume=False)
        self.assertEqual(len(mock_transport.call_history), 2)

        # 4. 2차 실행: 전체 5개 대상을 resume=True로 가동
        # 앞 2개는 건너뛰고, 뒤 3개만 새로 수집되어야 함!
        resumed_summary = collector.execute_batch(run_id, run_dir, in_sha, targets, resume=True)

        self.assertEqual(resumed_summary["processed_count"], 5)
        self.assertEqual(resumed_summary["completed_count"], 5)
        # 네트워크 호출은 총 5회여야 함 (앞 2회 + 뒤 3회, 중복 0건!)
        self.assertEqual(len(mock_transport.call_history), 5, "재개 시 이미 수집된 건은 호출되지 않아야 함!")

        # 5. 심층 집계 감사 검증 (원천 매니페스트 해시 일치 확인)
        closure_report = run_batch_deep_closure_audit(run_dir)
        self.assertTrue(closure_report["source_manifest_verified"], "원천 매니페스트 해시 일치 실패!")
        self.assertEqual(closure_report["audit_verdict"], "BATCH_VERIFIED_SUCCESS")

        print("  [재개 및 혈통 통과] 원천 매니페스트 해시 결속 및 checkpoint 기반 재개(0건 중복 호출) 실측 완수")


if __name__ == "__main__":
    unittest.main()
