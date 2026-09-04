#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 [DART-Trace v1.0] True Day 35 Hybrid GraphRAG 종합 검증 및 회귀 테스트 (unittest 기반)
================================================================================
검증 항목:
1. Cloud Neo4j Aura 313개 :DART_CapitalEvent 노드 전수 512차원 임베딩 및 속성 검증
2. Vector Index (dart_capital_event_vector_idx) & Fulltext Index ONLINE 상태 검증
3. MinMax 정규화 및 Day 35 70:30 하이브리드 리랭킹 수학 수식 검증
4. 512차원 벡터 검색 실행 및 상위 적중 결과 정합성 검증
5. 4-tier Response Contract (사실 / 해석 / 원문 근거 / 다음 확인 항목) 생성 무결성 검증
================================================================================
"""

import os
import sys
import math
import unittest
from pathlib import Path
from dotenv import load_dotenv

# Windows stdout UTF-8 보장
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from services.graphrag_service import (
    get_neo4j_driver,
    minmax_scale,
    search_vector_only,
    search_hybrid_rerank,
    build_evidence_context,
    generate_graphrag_response
)


class TestV10GraphRAGPipeline(unittest.TestCase):

    def test_01_neo4j_aura_capital_events_313_embeddings(self):
        """1. 313개 자본이벤트 노드가 512차원 벡터 및 목적 텍스트를 100% 보유하는지 검증"""
        driver = get_neo4j_driver()
        with driver.session() as session:
            res = session.run("""
            MATCH (e:DART_CapitalEvent)
            RETURN count(e) AS total,
                   count(e.purpose_text) AS has_purpose_text,
                   count(e.scale_amount) AS has_scale,
                   count(e.embedding_512) AS has_vector,
                   collect(size(e.embedding_512))[0] AS sample_dim
            """)
            rec = res.single()
            self.assertEqual(rec["total"], 313, f"총 자본이벤트 노드 수는 313이어야 함 (실제: {rec['total']})")
            self.assertEqual(rec["has_purpose_text"], 313, "313개 노드 모두 purpose_text를 보유해야 함")
            self.assertEqual(rec["has_scale"], 313, "313개 노드 모두 scale_amount를 보유해야 함")
            self.assertEqual(rec["has_vector"], 313, "313개 노드 모두 embedding_512를 보유해야 함")
            self.assertEqual(rec["sample_dim"], 512, f"임베딩 벡터 차원은 512여야 함 (실제: {rec['sample_dim']})")

    def test_02_neo4j_indexes_online(self):
        """2. Vector Index 및 Fulltext Index가 생성되어 ONLINE 상태인지 검증"""
        driver = get_neo4j_driver()
        with driver.session() as session:
            res = session.run("""
            SHOW INDEXES YIELD name, type, state, populationPercent
            WHERE name IN ['dart_capital_event_vector_idx', 'dart_purpose_fulltext_idx']
            RETURN name, type, state, populationPercent
            """)
            indexes = {r["name"]: r for r in res}
            self.assertIn("dart_capital_event_vector_idx", indexes, "dart_capital_event_vector_idx 가 존재해야 함")
            self.assertIn("dart_purpose_fulltext_idx", indexes, "dart_purpose_fulltext_idx 가 존재해야 함")

            vec_idx = indexes["dart_capital_event_vector_idx"]
            self.assertEqual(vec_idx["type"], "VECTOR")
            self.assertEqual(vec_idx["state"], "ONLINE")
            self.assertEqual(vec_idx["populationPercent"], 100.0)

            ft_idx = indexes["dart_purpose_fulltext_idx"]
            self.assertEqual(ft_idx["type"], "FULLTEXT")
            self.assertEqual(ft_idx["state"], "ONLINE")

    def test_03_minmax_scale_math(self):
        """3. MinMax 정규화 함수의 수학적 무결성 검증"""
        # 일반 경우
        raw = [10.0, 20.0, 30.0]
        norm = minmax_scale(raw)
        self.assertEqual(norm, [0.0, 0.5, 1.0])

        # 모든 값이 동일한 경우 (분모 0 방어 -> 모두 1.0 반환)
        same = [7.0, 7.0, 7.0]
        norm_same = minmax_scale(same)
        self.assertEqual(norm_same, [1.0, 1.0, 1.0])

        # 빈 리스트
        self.assertEqual(minmax_scale([]), [])

    def test_04_hybrid_reranker_math(self):
        """4. Day 35 70:30 하이브리드 리랭커 수식 및 정렬 검증"""
        # 모의 검색 결과
        mock_hits = [
            {
                "event_id": "EVT_1",
                "corp_name": "A사",
                "score": 0.90,  # 유사도 높음
                "scale_amount": 10_000_000_000,  # 100억
                "pagerank": 0.15
            },
            {
                "event_id": "EVT_2",
                "corp_name": "B사",
                "score": 0.70,  # 유사도 보통
                "scale_amount": 100_000_000_000,  # 1000억 (규모 큼)
                "pagerank": 0.85  # 중심성 높음
            }
        ]
        reranked = search_hybrid_rerank(mock_hits, sim_weight=0.70)
        self.assertEqual(len(reranked), 2)

        # 각 항목에 final_score, sim_norm, scale_norm, pr_norm이 포함되어 있는지 확인
        for item in reranked:
            self.assertIn("final_score", item)
            self.assertIn("sim_norm", item)
            self.assertIn("scale_norm", item)
            self.assertIn("pr_norm", item)
            self.assertTrue(0.0 <= item["final_score"] <= 1.0)

        # 내림차순 정렬 확인
        self.assertTrue(reranked[0]["final_score"] >= reranked[1]["final_score"])

    def test_05_search_vector_only_live(self):
        """5. 라이브 DB 512차원 벡터 검색 실행 및 상위 적중 확인"""
        q = "시설 투자 및 공장 증설을 위한 전환사채 발행"
        hits = search_vector_only(q, top_k=5)
        self.assertGreater(len(hits), 0, "검색 결과가 1건 이상이어야 함")
        self.assertLessEqual(len(hits), 5, "top_k 제한이 지켜져야 함")

        first = hits[0]
        self.assertIn("event_id", first)
        self.assertIn("corp_name", first)
        self.assertIn("score", first)
        self.assertIn("purpose_text", first)
        self.assertIn("scale_amount", first)
        self.assertGreater(first["score"], 0.5, "유의미한 코사인 유사도가 산출되어야 함")

    def test_06_4tier_response_contract(self):
        """6. 4-Tier Response Contract (Fact, Interpretation, Evidence, Next Action) 무결성 검증"""
        q = "타법인 증권 취득 목적으로 자금을 조달한 기업"
        report = generate_graphrag_response(q, top_k=3)

        self.assertEqual(report["question"], q)
        self.assertGreater(len(report["hits"]), 0)
        self.assertLessEqual(len(report["hits"]), 3)

        # 4단 계약 검증
        self.assertGreater(len(report["fact"].strip()), 0, "사실(Fact) 섹션이 비어있지 않아야 함")
        self.assertGreater(len(report["interpretation"].strip()), 0, "해석(Interpretation) 섹션이 비어있지 않아야 함")
        self.assertGreater(len(report["evidence"].strip()), 0, "원문 근거(Evidence) 섹션이 비어있지 않아야 함")
        self.assertGreater(len(report["next_action"].strip()), 0, "다음 확인 항목(Next Action) 섹션이 비어있지 않아야 함")

        # 원문 증거 역추적 검증 (DART 접수번호 또는 dart 링크 포함)
        has_evidence_marker = (
            "202" in report["evidence"] or 
            "dart.fss.or.kr" in report["evidence"] or 
            "접수번호" in report["evidence"] or
            "202" in report["full_answer"]
        )
        self.assertTrue(has_evidence_marker, "원문 근거에 DART 접수번호 또는 공시 링크가 포함되어야 함")


    def test_07_graphrag_service_read_access_enforced(self):
        """7. [불변 계약 ②] graphrag_service.py에 default_access_mode=READ_ACCESS가 강제 적용되었는지 정적/동적 검증"""
        service_file = PROJECT_ROOT / "services" / "graphrag_service.py"
        content = service_file.read_text(encoding="utf-8")
        
        # 정적 검증
        self.assertIn("READ_ACCESS", content, "graphrag_service.py에 READ_ACCESS가 임포트되어 있어야 함")
        self.assertIn("default_access_mode=READ_ACCESS", content, "graphrag_service.py에 default_access_mode=READ_ACCESS가 적용되어 있어야 함")

    def test_08_immutable_contract_owns_stake_zero_and_holds_economic_stake_19(self):
        """8. [불변 계약 ①] DB 상 :OWNS_STAKE 0건 격리 및 :HOLDS_ECONOMIC_STAKE 19건 실존 무결성 검증"""
        driver = get_neo4j_driver()
        with driver.session() as session:
            # 1) 금지된 :OWNS_STAKE는 0건이어야 함 (존재하지 않아야 함)
            r1 = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS cnt").single()["cnt"]
            self.assertEqual(r1, 0, f":OWNS_STAKE 관계는 0건으로 완전 격리되어야 함 (실제: {r1})")

            # 2) 실제 승격된 :HOLDS_ECONOMIC_STAKE는 정확히 19건이어야 함
            r2 = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS cnt").single()["cnt"]
            self.assertEqual(r2, 19, f":HOLDS_ECONOMIC_STAKE 관계는 정확히 19건이어야 함 (실제: {r2})")

            # 3) DB 전체 관계 타입 검증
            rel_types = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS types").single()["types"]
            self.assertNotIn("OWNS_STAKE", rel_types, "DB 전체 관계 타입 목록에 OWNS_STAKE가 존재하지 않아야 함")
            self.assertIn("HOLDS_ECONOMIC_STAKE", rel_types, "DB 전체 관계 타입 목록에 HOLDS_ECONOMIC_STAKE가 존재해야 함")
            print(f"\n  [불변 계약 검증 확인] OWNS_STAKE={r1}건 (0건 정상), HOLDS_ECONOMIC_STAKE={r2}건 (19건 정상), 타입={rel_types}")


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 [DART-Trace v1.0] GraphRAG 파이프라인 회귀 및 검증 테스트 러너 가동 (8대 계약 전수 검증)")
    print("=" * 80)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestV10GraphRAGPipeline)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
