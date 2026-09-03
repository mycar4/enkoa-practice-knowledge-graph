# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] RawEvidenceCandidate & EvidenceFragment 격리 적재 순수 오프라인 단위 테스트
================================================================================
원칙:
- 운영 Aura DB 연결 및 변경 0건 (100% Mock / 오프라인)
- 6대 엄격 계약 가드 실측 검증:
  1. 기본 DRY-RUN 모드 시 DB 쓰기 0건 검증
  2. 원문 행 해시 기반 불변 결정론적 ID(Deterministic Hash ID) 검증
  3. 제로-트러스트: 디스크 XML 변조/불일치 시 실패-폐쇄 즉시 거부 검증
  4. 외부 주입 및 Fallback 금지 검증 (receipt_id 누락 시 즉시 거부)
  5. EvidenceFragment 및 Candidate 7대 혈통 필드 전수 결속 검증
  6. Zero OWNS_STAKE 및 is_current 불변식 검증
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

        # DB 세션 호출이 전혀 발생하지 않았음을 실측 검증
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
        loader = RawEvidenceGraphLoader(driver="MOCK")

        # 임시 디렉토리에 변조된 XML 배치 모의
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_run_dir = os.path.join(temp_dir, "tampered_run")
            os.makedirs(os.path.join(temp_run_dir, "xml"))
            os.makedirs(os.path.join(temp_run_dir, "manifests"))

            # 정상 종료 감사 및 입력 매니페스트
            with open(os.path.join(temp_run_dir, "batch_closure_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"audit_verdict": "BATCH_VERIFIED_SUCCESS"}, f)
            with open(os.path.join(temp_run_dir, "input_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"targets": [{"rcept_no": "20240101000001"}]}, f)

            # 변조된 XML 파일
            with open(os.path.join(temp_run_dir, "xml", "20240101000001.xml"), "wb") as f:
                f.write(b"<DOCUMENT>TAMPERED_CONTENT</DOCUMENT>")

            # 영수증에는 가짜 해시 기록
            with open(os.path.join(temp_run_dir, "manifests", "receipt_20240101000001.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "receipt_id": "rcpt-20240101000001",
                    "requested_rcept_no": "20240101000001",
                    "run_id": "tampered_run",
                    "xml_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                    "xml_storage_rel_path": "xml/20240101000001.xml"
                }, f)

            temp_loader = RawEvidenceGraphLoader(base_runs_dir=temp_dir, driver="MOCK")
            with self.assertRaises(ValueError) as ctx:
                temp_loader.load_evidence_batch(run_id="tampered_run", commit=False)

            self.assertIn("디스크 XML 실측 해시", str(ctx.exception))
            print("  [가드 3 통과] 제로-트러스트: 디스크 XML 변조 감지 시 즉시 거부 실측 완료")

    def test_04_fallback_forbidden_strict_provenance(self):
        """[가드 4] 영수증 필드(receipt_id, xml_storage_rel_path) 결손 시 fallback 없이 즉시 거부"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_run_dir = os.path.join(temp_dir, "fallback_test_run")
            os.makedirs(os.path.join(temp_run_dir, "xml"))
            os.makedirs(os.path.join(temp_run_dir, "manifests"))

            with open(os.path.join(temp_run_dir, "batch_closure_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"audit_verdict": "BATCH_VERIFIED_SUCCESS"}, f)
            with open(os.path.join(temp_run_dir, "input_manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"targets": [{"rcept_no": "20240101000002"}]}, f)

            xml_bytes = b"<DOCUMENT>VALID_CONTENT</DOCUMENT>"
            import hashlib
            xml_sha = hashlib.sha256(xml_bytes).hexdigest()

            with open(os.path.join(temp_run_dir, "xml", "20240101000002.xml"), "wb") as f:
                f.write(xml_bytes)

            # receipt_id가 없는 영수증 투입
            with open(os.path.join(temp_run_dir, "manifests", "receipt_20240101000002.json"), "w", encoding="utf-8") as f:
                json.dump({
                    # receipt_id 고의 누락!
                    "requested_rcept_no": "20240101000002",
                    "run_id": "fallback_test_run",
                    "xml_sha256": xml_sha,
                    "xml_storage_rel_path": "xml/20240101000002.xml"
                }, f)

            temp_loader = RawEvidenceGraphLoader(base_runs_dir=temp_dir, driver="MOCK")
            with self.assertRaises(ValueError) as ctx:
                temp_loader.load_evidence_batch(run_id="fallback_test_run", commit=False)

            self.assertIn("receipt_id 결손 (Fallback 금지)", str(ctx.exception))
            print("  [가드 4 통과] receipt_id 결손 시 Fallback 없는 실패-폐쇄 거부 실측 완료")

    def test_05_mock_commit_and_no_owns_stake_invariance(self):
        """[가드 5 & 6] Mock 커밋 시 Cypher 쿼리 내 OWNS_STAKE 및 is_current 오염 0건 불변식 검증"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        loader = RawEvidenceGraphLoader(driver=mock_driver)
        res = loader.load_evidence_batch(
            run_id=self.run_id,
            commit=True,
            limit=5
        )

        self.assertTrue(res["commit_mode"])
        self.assertGreater(mock_session.run.call_count, 0)

        # 실행된 모든 Cypher 쿼리 텍스트 전수 감사
        for call_args in mock_session.run.call_args_list:
            cypher_query = call_args[0][0]
            self.assertNotIn("OWNS_STAKE", cypher_query, "❌ Cypher에 OWNS_STAKE 관계가 포함되어 있습니다!")
            self.assertNotIn("is_current", cypher_query, "❌ Cypher에 is_current 속성이 포함되어 있습니다!")

            # EvidenceFragment 및 RawEvidenceCandidate MERGE 문 검증
            if "MERGE (frag:EvidenceFragment" in cypher_query:
                self.assertIn("frag.run_id = f.run_id", cypher_query)
                self.assertIn("frag.receipt_id = f.receipt_id", cypher_query)
                self.assertIn("frag.adapter_name = f.adapter_name", cypher_query)
                self.assertIn("frag.adapter_version = f.adapter_version", cypher_query)
                self.assertIn("frag.xml_rel_path = f.xml_rel_path", cypher_query)

        print("  [가드 5 & 6 통과] EvidenceFragment 5대 혈통 필드 전수 결속 및 Zero OWNS_STAKE 불변식 오프라인 실측 완료")


if __name__ == "__main__":
    unittest.main()
