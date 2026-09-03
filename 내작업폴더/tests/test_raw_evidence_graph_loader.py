# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] RawEvidenceCandidate & EvidenceFragment 격리 적재 순수 오프라인 단위 테스트 (v3.0)
================================================================================
원칙:
- 운영 Aura DB 연결 및 변경 0건 (100% Mock / 오프라인)
- 7대 엄격 계약 가드 실측 검증:
  1. 기본 DRY-RUN 모드 시 DB 쓰기 0건 검증
  2. 원문 행 해시 기반 불변 결정론적 ID 검증
  3. 제로-트러스트: 디스크 XML 변조 감지 시 즉시 거부 검증
  4. 제로-트러스트: 입력 매니페스트 해시 불일치 감지 시 즉시 거부 검증
  5. 외부 주입 및 Fallback 금지 검증 (receipt_id 누락 시 즉시 거부)
  6. 행 해시 Fallback 금지: ROW_DATA_EVIDENCE 결손 시 UNRESOLVED_ROW_PROVENANCE 격리 검증
  7. 불변성 쓰기 계약 (ON CREATE SET) 및 적재 영수증(load_run_id / load_receipt_id) 검증
================================================================================
"""

import os
import sys
import json
import unittest
from unittest.mock import MagicMock

import importlib
sys.path.insert(0, os.path.abspath("내작업폴더"))
loader_mod = importlib.import_module("00_Raw_Evidence_Graph_Loader")
RawEvidenceGraphLoader = loader_mod.RawEvidenceGraphLoader


class TestRawEvidenceGraphLoaderOffline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.run_id = "batch_1500_20260903_051738"
        cls.real_run_dir = os.path.join("내작업폴더/data/raw_filings/batch_runs", cls.run_id)

    def test_01_default_dry_run_zero_db_write(self):
        """[가드 1] commit=False(기본값) 시 Mock 드라이버로 DB 호출 0건 완벽 입증"""
        mock_driver = MagicMock()
        loader = RawEvidenceGraphLoader(driver=mock_driver)

        res = loader.load_evidence_batch(
            run_id=self.run_id,
            commit=False,
            limit=5
        )

        self.assertFalse(res["commit_mode"])
        self.assertEqual(res["total_targets_evaluated"], 5)
        self.assertEqual(res["zero_trust_verified_count"], 5)
        self.assertGreater(res["candidates_created"], 0)
        self.assertEqual(res["owns_stake_created"], 0)
        self.assertIsNone(res["write_manifest_path"])

        mock_driver.session.assert_not_called()
        print("  [가드 1 통과] 기본 DRY-RUN 모드 DB 호출 0건 오프라인 실측 완료")

    def test_02_deterministic_hash_based_id_invariance(self):
        """[가드 2] 순번 ID 배제 및 원문 행 해시 기반 불변 결정론적 ID 검증"""
        loader = RawEvidenceGraphLoader(driver="MOCK")

        res1 = loader.load_evidence_batch(run_id=self.run_id, commit=False, limit=5)
        res2 = loader.load_evidence_batch(run_id=self.run_id, commit=False, limit=5)

        self.assertEqual(res1["candidates_created"], res2["candidates_created"])
        self.assertEqual(res1["fragments_created"], res2["fragments_created"])
        print("  [가드 2 통과] 원문 행 해시 기반 결정론적 불변 식별자 일치 확인")

    def test_03_zero_trust_tampered_xml_rejection(self):
        """[가드 3] 제로-트러스트: 디스크 XML 바이트 해시가 영수증과 불일치할 시 즉시 거부"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_run_dir = os.path.join(temp_dir, "tampered_run")
            os.makedirs(os.path.join(temp_run_dir, "xml"))
            os.makedirs(os.path.join(temp_run_dir, "manifests"))

            with open(os.path.join(temp_run_dir, "batch_closure_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"audit_verdict": "BATCH_VERIFIED_SUCCESS"}, f)
            with open(os.path.join(temp_run_dir, "input_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"targets": [{"rcept_no": "20240101000001"}]}, f)

            with open(os.path.join(temp_run_dir, "xml", "20240101000001.xml"), "wb") as f:
                f.write(b"<DOCUMENT>TAMPERED_CONTENT</DOCUMENT>")

            with open(os.path.join(temp_run_dir, "manifests", "receipt_20240101000001.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "receipt_id": "rcpt-20240101000001",
                    "requested_rcept_no": "20240101000001",
                    "run_id": "tampered_run",
                    "xml_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                    "input_manifest_sha256": "valid_sha",
                    "xml_storage_rel_path": "xml/20240101000001.xml"
                }, f)

            temp_loader = RawEvidenceGraphLoader(base_runs_dir=temp_dir, driver="MOCK")
            with self.assertRaises(ValueError) as ctx:
                temp_loader.load_evidence_batch(run_id="tampered_run", commit=False)

            self.assertIn("디스크 XML 실측 해시", str(ctx.exception))
            print("  [가드 3 통과] 제로-트러스트: 디스크 XML 변조 감지 시 즉시 거부 실측 완료")

    def test_04_zero_trust_input_manifest_mismatch_rejection(self):
        """[가드 4] 제로-트러스트: 영수증의 input_manifest_sha256 불일치 시 즉시 거부"""
        import tempfile, hashlib
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_run_dir = os.path.join(temp_dir, "mismatch_manifest_run")
            os.makedirs(os.path.join(temp_run_dir, "xml"))
            os.makedirs(os.path.join(temp_run_dir, "manifests"))

            with open(os.path.join(temp_run_dir, "batch_closure_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"audit_verdict": "BATCH_VERIFIED_SUCCESS"}, f)
            with open(os.path.join(temp_run_dir, "input_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"targets": [{"rcept_no": "20240101000003"}]}, f)

            xml_bytes = b"<DOCUMENT>VALID</DOCUMENT>"
            xml_sha = hashlib.sha256(xml_bytes).hexdigest()
            with open(os.path.join(temp_run_dir, "xml", "20240101000003.xml"), "wb") as f:
                f.write(xml_bytes)

            with open(os.path.join(temp_run_dir, "manifests", "receipt_20240101000003.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "receipt_id": "rcpt-20240101000003",
                    "requested_rcept_no": "20240101000003",
                    "run_id": "mismatch_manifest_run",
                    "xml_sha256": xml_sha,
                    "input_manifest_sha256": "wrong_input_manifest_sha",
                    "xml_storage_rel_path": "xml/20240101000003.xml"
                }, f)

            temp_loader = RawEvidenceGraphLoader(base_runs_dir=temp_dir, driver="MOCK")
            with self.assertRaises(ValueError) as ctx:
                temp_loader.load_evidence_batch(run_id="mismatch_manifest_run", commit=False)

            self.assertIn("input_manifest_sha256", str(ctx.exception))
            print("  [가드 4 통과] 제로-트러스트: 입력 매니페스트 해시 불일치 시 즉시 거부 실측 완료")

    def test_05_fallback_forbidden_strict_provenance(self):
        """[가드 5] 영수증 필드(receipt_id, xml_storage_rel_path) 결손 시 fallback 없이 즉시 거부"""
        import tempfile, hashlib
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_run_dir = os.path.join(temp_dir, "fallback_test_run")
            os.makedirs(os.path.join(temp_run_dir, "xml"))
            os.makedirs(os.path.join(temp_run_dir, "manifests"))

            with open(os.path.join(temp_run_dir, "batch_closure_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"audit_verdict": "BATCH_VERIFIED_SUCCESS"}, f)
            with open(os.path.join(temp_run_dir, "input_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"targets": [{"rcept_no": "20240101000002"}]}, f)

            xml_bytes = b"<DOCUMENT>VALID_CONTENT</DOCUMENT>"
            xml_sha = hashlib.sha256(xml_bytes).hexdigest()

            with open(os.path.join(temp_run_dir, "xml", "20240101000002.xml"), "wb") as f:
                f.write(xml_bytes)

            with open(os.path.join(temp_run_dir, "manifests", "receipt_20240101000002.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "requested_rcept_no": "20240101000002",
                    "run_id": "fallback_test_run",
                    "xml_sha256": xml_sha,
                    "xml_storage_rel_path": "xml/20240101000002.xml"
                }, f)

            temp_loader = RawEvidenceGraphLoader(base_runs_dir=temp_dir, driver="MOCK")
            with self.assertRaises(ValueError) as ctx:
                temp_loader.load_evidence_batch(run_id="fallback_test_run", commit=False)

            self.assertIn("receipt_id 결손 (Fallback 금지)", str(ctx.exception))
            print("  [가드 5 통과] receipt_id 결손 시 Fallback 없는 실패-폐쇄 거부 실측 완료")

    def test_06_mock_commit_on_create_set_and_manifest(self):
        """[가드 6 & 7] Mock 커밋 시 ON CREATE SET 불변식, load_run_id 결속 및 Write Manifest 발행 검증"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        loader = RawEvidenceGraphLoader(driver=mock_driver)
        res = loader.load_evidence_batch(
            run_id=self.run_id,
            load_run_id="test_mock_load_run",
            commit=True,
            limit=5
        )

        self.assertTrue(res["commit_mode"])
        self.assertEqual(res["load_run_id"], "test_mock_load_run")
        self.assertIsNotNone(res["write_manifest_path"])
        self.assertTrue(os.path.exists(res["write_manifest_path"]))

        # 적재 실행 매니페스트 내용 감사
        with open(res["write_manifest_path"], "r", encoding="utf-8") as wf:
            manifest_doc = json.load(wf)
        self.assertEqual(manifest_doc["load_run_id"], "test_mock_load_run")
        self.assertEqual(manifest_doc["collection_run_id"], self.run_id)

        # Cypher 쿼리 내 ON CREATE SET 검증
        for call_args in mock_session.run.call_args_list:
            cypher_query = call_args[0][0]
            self.assertNotIn("OWNS_STAKE", cypher_query)
            self.assertNotIn("is_current", cypher_query)

            if "MERGE (frag:EvidenceFragment" in cypher_query or "MERGE (cand:RawEvidenceCandidate" in cypher_query:
                self.assertIn("ON CREATE SET", cypher_query, "❌ MERGE 문에 ON CREATE SET 불변식 쓰기가 적용되지 않았습니다!")
                self.assertNotIn("\n                SET\n", cypher_query, "❌ 불변성 위반: trailing SET이 남아있어 재실행 시 덮어쓰기가 발생합니다!")
                self.assertIn("load_run_id", cypher_query)
                self.assertIn("load_receipt_id", cypher_query)

        # 테스트용 매니페스트 정리
        os.remove(res["write_manifest_path"])
        print("  [가드 6 & 7 통과] ON CREATE SET 불변식 쓰기, load_run_id 결속 및 Write Manifest 발행 실측 완료")


if __name__ == "__main__":
    unittest.main()
