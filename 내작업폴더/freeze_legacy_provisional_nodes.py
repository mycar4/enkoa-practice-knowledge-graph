# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 잠정 시험 적재 노드 공식 동결 스크립트 (freeze_legacy_provisional_nodes.py)
================================================================================
목적:
1. 정규 격리 적재 이전에 시험 생성된 순번 기반 ID 노드(cand-*-1, cand-*-2 등 19개)를
   삭제하지 않고 'LEGACY_PROVISIONAL_TEST_LOAD' 상태로 명시 동결
2. 향후 정규 적재 데이터와 엄격히 분리되도록 load_run_id='legacy_provisional_test' 부여
================================================================================
"""

import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def freeze_legacy_provisional_nodes():
    load_dotenv(".env")
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not pwd:
        raise ValueError("❌ [보안 오류] NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경변수가 누락되었습니다.")

    print("=" * 80)
    print("❄️ [잠정 시험 적재 노드 공식 동결 시작]")
    print("=" * 80)

    cypher = """
    MATCH (c:RawEvidenceCandidate)
    WHERE c.candidate_id =~ 'cand-\\d{14}-\\d+'
    SET c.legacy_status = 'LEGACY_PROVISIONAL_TEST_LOAD',
        c.load_run_id = 'legacy_provisional_test'
    RETURN count(c) AS frozen_count, collect(c.candidate_id) AS frozen_cids
    """

    with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
        with driver.session() as session:
            record = session.run(cypher).single()
            frozen_cnt = record["frozen_count"]
            frozen_cids = record["frozen_cids"]

    print(f"✔️ 동결 처리된 잠정 시험 노드 수: {frozen_cnt}개")
    for cid in frozen_cids:
        print(f"   ❄️ 동결: {cid}")
    print("=" * 80)


if __name__ == "__main__":
    freeze_legacy_provisional_nodes()
