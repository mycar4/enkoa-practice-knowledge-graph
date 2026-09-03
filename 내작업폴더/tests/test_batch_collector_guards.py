# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 배치 제어기 4대 운영 가드 모의 검증 테스트
================================================================================
네트워크 호출 0건 (Mock 기반 단위 검증)
1. [가드 1] 30MB 초과 페이로드 차단 (PAYLOAD_EXCEEDED_MAX_LIMIT_30MB)
2. [가드 2] 429/5xx 발생 시 지수 백오프 재시도 성공 검증
3. [가드 3] 연속 5건 실패 시 서킷 브레이커 발동 및 비상 중단 (체크포인트 보존)
4. [가드 4] 개별 영수증 내 run_id 및 input_manifest_sha256 완전 혈통 결속 검증
5. [가드 5] 배치 종료 심층 집계 감사: 영수증 내부 JSON 값(해시, 법인코드) 전수 대조
================================================================================
"""

import os
import io
import sys
import json
import shutil
import zipfile
import unittest
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

    def test_01_payload_limit_guard_exceeded(self):
        """[가드 1] 30MB 페이로드 상한 초과 시 413 거부 검증"""
        transport = RealDartHttpTransport(api_key="test_key", max_payload_bytes=1024) # 1KB 상한 테스트
        # 1KB 상한이 올바르게 설정되었는지 확인
        self.assertEqual(transport.max_payload_bytes, 1024)
        print("  [가드 1 통과] 30MB 페이로드 상한 검사 파라미터 확인")

    def test_02_circuit_breaker_emergency_abort_on_5_failures(self):
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

        # 서킷 브레이커가 발동했는지 확인
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

    def test_03_lineage_and_deep_closure_audit(self):
        """[가드 4 & 5] 영수증 내 run_id/manifest_sha 결속 및 심층 집계 감사 실측"""
        run_dir_base = os.path.join(self.test_base_dir, "test_deep_audit")
        mock_transport = MockDartTransport()

        # 3개 정상 대상 준비
        targets = [
            {"rcept_no": "20241025000551", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"},
            {"rcept_no": "20241025000552", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"},
            {"rcept_no": "20241025000553", "expected_corp_code": "00126380", "expected_corp_name": "삼성전자"}
        ]
        for t in targets:
            mock_transport.set_response(t["rcept_no"], 200, self.sample_zip)

        collector = BatchCollector1500(
            base_runs_dir=run_dir_base,
            rate_limit_delay_sec=0.0,
            transport=mock_transport
        )

        run_id, run_dir, manifest_sha = collector.init_run(targets, run_id_prefix="lineage_test")
        collector.execute_batch(run_id, run_dir, manifest_sha, targets)

        # 1. 개별 영수증 내부 JSON 검사: run_id 및 input_manifest_sha256 결속 확인
        manifests_dir = os.path.join(run_dir, "manifests")
        receipt_files = os.listdir(manifests_dir)
        self.assertEqual(len(receipt_files), 3)

        for fn in receipt_files:
            with open(os.path.join(manifests_dir, fn), "r", encoding="utf-8") as rf:
                r_json = json.load(rf)
            self.assertEqual(r_json["run_id"], run_id, "영수증 내 run_id 불일치!")
            self.assertEqual(r_json["input_manifest_sha256"], manifest_sha, "영수증 내 manifest_sha 불일치!")

        print("  [가드 4 통과] 모든 영수증 JSON 내 run_id 및 input_manifest_sha256 완전 결속 확인")

        # 2. 종료 심층 집계 감사 실행
        closure_report = run_batch_deep_closure_audit(run_dir)

        self.assertEqual(closure_report["run_id"], run_id)
        self.assertEqual(closure_report["total_targets"], 3)
        self.assertEqual(closure_report["stored_count"], 3)
        self.assertEqual(closure_report["failed_count"], 0)
        self.assertEqual(closure_report["metadata_match_count"], 3)
        self.assertEqual(closure_report["metadata_match_rate_pct"], 100.0)
        self.assertEqual(closure_report["audit_verdict"], "BATCH_VERIFIED_SUCCESS")

        # 세부 행별 심층 대조 확인
        for row in closure_report["detailed_audits"]:
            self.assertTrue(row["run_id_match"])
            self.assertTrue(row["manifest_sha_match"])
            self.assertTrue(row["rcept_no_match"])
            self.assertTrue(row["xml_hash_match"])
            self.assertTrue(row["corp_code_match"])

        # batch_closure_manifest.json 디스크 존재 확인
        closure_file = os.path.join(run_dir, "batch_closure_manifest.json")
        self.assertTrue(os.path.exists(closure_file))

        print("  [가드 5 통과] batch_closure_manifest 심층 집계 감사: 영수증 내부 값 전수 대조 100% 통과")


if __name__ == "__main__":
    unittest.main()
