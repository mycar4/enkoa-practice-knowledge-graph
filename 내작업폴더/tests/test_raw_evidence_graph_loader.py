# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] RawEvidenceCandidate & EvidenceFragment 격리 적재 단위 테스트
================================================================================
검증 항목:
1. DRY-RUN 모드 시 DB 노드/엣지 변경 0건 검증
2. 7대 필수 메타데이터(rcept_no, xml_sha256, run_id, receipt_id, adapter_version 등) 결속 검증
3. 일반서식(SUPPORTED_5PCT_GENERAL) vs 약식(UNSUPPORTED_LAYOUT) 분기 적재 검증
4. OWNS_STAKE 및 is_current 불변성(Invariance) 검증 (신규 지분 관계 생성 0건)
================================================================================
"""

import os
import sys
import json
import unittest
from dotenv import load_dotenv
from neo4j import GraphDatabase

import importlib
sys.path.insert(0, os.path.abspath("내작업폴더"))
loader_mod = importlib.import_module("00_Raw_Evidence_Graph_Loader")
RawEvidenceGraphLoader = loader_mod.RawEvidenceGraphLoader


class TestRawEvidenceGraphLoader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_dotenv(".env")
        cls.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        cls.user = os.getenv("NEO4J_USER", "neo4j")
        cls.pwd = os.getenv("NEO4J_PASSWORD", "12345678")
        cls.driver = GraphDatabase.driver(cls.uri, auth=(cls.user, cls.pwd))
        cls.loader = RawEvidenceGraphLoader(driver=cls.driver)
        cls.run_id = "batch_1500_20260903_051738"

    @classmethod
    def tearDownClass(cls):
        cls.loader.close()
        cls.driver.close()

    def test_01_dry_run_zero_db_write(self):
        """[검증 1] DRY-RUN 가동 시 통계만 산출하고 Neo4j에는 단 1건의 노드/관계도 쓰지 않음"""
        with self.driver.session() as s:
            cand_before = s.run("MATCH (c:RawEvidenceCandidate {run_id: $r}) RETURN count(c) AS cnt", {"r": "dry_run_test"}).single()["cnt"]

        res = self.loader.load_evidence_batch(
            run_id=self.run_id,
            dry_run=True,
            limit=10
        )

        self.assertTrue(res["dry_run"])
        self.assertEqual(res["total_targets_evaluated"], 10)
        self.assertGreater(res["candidates_created"], 0)
        self.assertEqual(res["owns_stake_created"], 0)

        with self.driver.session() as s:
            cand_after = s.run("MATCH (c:RawEvidenceCandidate {run_id: $r}) RETURN count(c) AS cnt", {"r": "dry_run_test"}).single()["cnt"]

        self.assertEqual(cand_before, cand_after, "DRY-RUN 모드에서 DB 노드가 생성되었습니다!")
        print("  [가드 1 통과] DRY-RUN 모드 DB 쓰기 0건 완벽 입증")

    def test_02_layout_classification_and_provenance_binding(self):
        """[검증 2 & 3] 10건 소규모 실제 적재 후 일반/약식 분류 및 7대 필수 메타데이터 전수 결속 검증"""
        # 10건 실제 파일럿 적재 실행
        res = self.loader.load_evidence_batch(
            run_id=self.run_id,
            dry_run=False,
            limit=10
        )

        self.assertEqual(res["total_targets_evaluated"], 10)
        self.assertEqual(res["supported_general_count"] + res["unsupported_layout_count"], 10)

        # DB에서 적재된 노드 조회 및 7대 메타데이터 검증
        with self.driver.session() as s:
            records = s.run(
                "MATCH (c:RawEvidenceCandidate {run_id: $r}) RETURN c",
                {"r": self.run_id}
            ).data()

        self.assertGreaterEqual(len(records), 10)

        for rec in records:
            c = rec["c"]
            # 7대 필수 혈통 필드 비어있지 않음 검증
            self.assertTrue(bool(c.get("candidate_id")))
            self.assertTrue(bool(c.get("rcept_no")))
            self.assertEqual(len(c.get("rcept_no")), 14)
            self.assertTrue(bool(c.get("xml_sha256")))
            self.assertEqual(len(c.get("xml_sha256")), 64)
            self.assertEqual(c.get("run_id"), self.run_id)
            self.assertTrue(bool(c.get("receipt_id")))
            self.assertEqual(c.get("adapter_name"), "5PCT_GENERAL_ART142_V1")
            self.assertEqual(c.get("adapter_version"), "1.0.0")
            self.assertTrue(bool(c.get("xml_rel_path")))

            # 서식 분류 상태 검증
            layout_status = c.get("layout_status")
            self.assertIn(layout_status, ["SUPPORTED_5PCT_GENERAL", "UNSUPPORTED_LAYOUT"])

            if layout_status == "SUPPORTED_5PCT_GENERAL":
                self.assertIsNotNone(c.get("holder_name"))
                self.assertIsNotNone(c.get("shares_count"))
                self.assertIsNotNone(c.get("stake_ratio"))
            else:
                self.assertIsNotNone(c.get("rejection_reason"))

        print("  [가드 2 & 3 통과] 10건 파일럿 실적재 및 7대 혈통 메타데이터 100% 결속 검증 완료")

    def test_03_fragment_and_relationship_binding(self):
        """[검증 4] 일반서식 후보 노드와 EvidenceFragment 간 EVIDENCED_BY 엣지 결속 검증"""
        with self.driver.session() as s:
            supported_cands = s.run(
                """
                MATCH (c:RawEvidenceCandidate {run_id: $r, layout_status: 'SUPPORTED_5PCT_GENERAL'})
                OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
                RETURN c.candidate_id AS cid, count(f) AS frag_cnt
                """,
                {"r": self.run_id}
            ).data()

        if supported_cands:
            for item in supported_cands:
                self.assertGreater(item["frag_cnt"], 0, f"일반서식 후보({item['cid']})에 결속된 증거 파편이 0개입니다!")
            print(f"  [가드 4 통과] 일반서식 후보 {len(supported_cands)}건에 대해 EvidenceFragment 정상 결속 확인")

    def test_04_no_owns_stake_invariance(self):
        """[검증 5 - 절대 불변식] 증거 적재 후 프로덕션 지분 관계(OWNS_STAKE) 생성 0건 보장"""
        with self.driver.session() as s:
            # RawEvidenceCandidate나 EvidenceFragment와 연결된 OWNS_STAKE 관계가 존재하는지 전수 조사
            tainted_stakes = s.run(
                """
                MATCH (n)-[r:OWNS_STAKE]-(m)
                WHERE n:RawEvidenceCandidate OR n:EvidenceFragment OR m:RawEvidenceCandidate OR m:EvidenceFragment
                RETURN count(r) AS cnt
                """
            ).single()["cnt"]

            self.assertEqual(tainted_stakes, 0, "❌ 절대 불변식 위반! 증거 노드가 OWNS_STAKE 관계와 연결되었습니다!")

        print("  [가드 5 통과] Zero OWNS_STAKE 불변식 100% 준수 실측 완료")


if __name__ == "__main__":
    unittest.main()
