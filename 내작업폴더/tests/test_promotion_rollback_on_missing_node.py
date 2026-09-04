# -*- coding: utf-8 -*-
"""
🧪 [DART-Trace] 대상 노드 결손 시 단일 트랜잭션 전체 롤백(Zero Pollution) 단정 테스트
================================================================================
- 19건 중 단 1건이라도 대상 DART_Company 노드가 결손되면:
  1) 트랜잭션 내부 사전 검증에서 즉시 ValueError 발생
  2) 전체 트랜잭션이 원자적으로 롤백 (Zero Write)
  3) 정상 노드 간의 관계조차 단 1건도 생성되지 않음을 실측 검증
================================================================================
"""

import os
import sys
from pathlib import Path
from neo4j import GraphDatabase, WRITE_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

sys.path.insert(0, str(BASE_DIR))
from execute_economic_stake_promotion import execute_promotion_batch_tx


def test_transaction_rollback_when_target_node_missing():
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    
    # 1. 테스트 실행 전 DB 상태 실측
    with driver.session() as s:
        pre_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        pre_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        pre_holds = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]

    # 2. 고의 결손 배치를 구성 (1건은 정상 노드, 1건은 실존하지 않는 가상 코드 '99999999')
    poisoned_batch = [
        {
            "holder_code": "00357607",  # 정상: (주)케이피티유
            "target_code": "00117027",  # 정상: (주)알루코
            "relationship_key": "rel-test-valid-rollback-check",
            "candidate_id": "cand-test-valid",
            "rcept_no": "20230810000694",
            "xml_sha256": "dummy",
            "shares_count": 100,
            "stake_ratio": 1.0,
            "reporting_obligation_date": "2023-08-04",
            "temporal_context": "TEST",
            "fact_type": "TEST",
            "temporal_definition": "TEST",
            "table_parser_index": 17,
            "all_tr_index": 2,
            "data_row_index": 0,
            "standard_xpath": "//TABLE[18]//TR[3]",
            "row_raw_parser_xpath": "//TABLE[17]//TR[0]",
            "xml_hash_verified": True,
            "row_inner_hash": "dummy",
            "promoted_at": "2026-09-04T00:00:00Z",
            "promotion_engine": "TEST_ENGINE"
        },
        {
            "holder_code": "00357607",  # 정상
            "target_code": "99999999",  # 고의 결손: 실존하지 않는 기업코드
            "relationship_key": "rel-test-poison-missing-node",
            "candidate_id": "cand-test-poison",
            "rcept_no": "20230810000694",
            "xml_sha256": "dummy",
            "shares_count": 200,
            "stake_ratio": 2.0,
            "reporting_obligation_date": "2023-08-04",
            "temporal_context": "TEST",
            "fact_type": "TEST",
            "temporal_definition": "TEST",
            "table_parser_index": 17,
            "all_tr_index": 2,
            "data_row_index": 0,
            "standard_xpath": "//TABLE[18]//TR[3]",
            "row_raw_parser_xpath": "//TABLE[17]//TR[0]",
            "xml_hash_verified": True,
            "row_inner_hash": "dummy",
            "promoted_at": "2026-09-04T00:00:00Z",
            "promotion_engine": "TEST_ENGINE"
        }
    ]

    # 3. execute_write 실행 시 반드시 ValueError 발생 단정
    error_caught = False
    try:
        with driver.session(default_access_mode=WRITE_ACCESS) as session:
            session.execute_write(execute_promotion_batch_tx, poisoned_batch)
    except ValueError as e:
        error_caught = True
        assert "필수 DART_Company 노드 결손 발견" in str(e)
        assert "99999999" in str(e)
        print(f"\n✅ [단정 1 통과] 트랜잭션 내부에서 결손 노드 99999999 감지 및 ValueError 발생 성공! ({e})")

    assert error_caught, "❌ ValueError가 발생하지 않았습니다! 결손 노드가 차단되지 않음!"

    # 4. 실행 후 DB 상태 재실측: 정상 노드 건조차 단 1건도 생성되지 않고 롤백되었음을 실측 검증
    with driver.session() as s:
        post_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        post_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        post_holds = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]

    assert post_nodes == pre_nodes, f"노드 오염 발생: Δ={post_nodes - pre_nodes}"
    assert post_rels == pre_rels, f"관계 생성 발생(부분 적재 오염!): Δ={post_rels - pre_rels}"
    assert post_holds == pre_holds, f"HOLDS_ECONOMIC_STAKE 관계 오염 발생: post={post_holds}, pre={pre_holds}"
    print(f"✅ [단정 2 통과] 전체 롤백 입증 완료! (노드 Δ=0, 관계 Δ=0, HOLDS_ECONOMIC_STAKE={post_holds}건 불변)")

    driver.close()


if __name__ == "__main__":
    test_transaction_rollback_when_target_node_missing()
