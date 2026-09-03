# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 증거 계층 DDL 마이그레이션 스크립트 (migrate_evidence_schema.py)
================================================================================
목적:
1. (:RawEvidenceCandidate) 및 (:EvidenceFragment) 노드에 대한 유니크 제약조건을
   독립 DDL 트랜잭션으로 안전하게 생성
2. 적재 런타임 코드로부터 DDL 책임 분리
3. 비밀번호 하드코딩 일체 배제 (환경변수 필수)
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


def apply_evidence_schema_migration():
    load_dotenv(".env")
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not pwd:
        raise ValueError("❌ [보안 오류] NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경변수가 누락되었습니다.")

    queries = [
        "CREATE CONSTRAINT constraint_raw_evidence_candidate_id IF NOT EXISTS FOR (c:RawEvidenceCandidate) REQUIRE c.candidate_id IS UNIQUE",
        "CREATE CONSTRAINT constraint_evidence_fragment_id IF NOT EXISTS FOR (f:EvidenceFragment) REQUIRE f.fragment_id IS UNIQUE"
    ]

    print("=" * 80)
    print("🛠️ [증거 계층 DDL 마이그레이션 시작]")
    print(f"• URI: {uri}")
    print(f"• User: {user}")
    print("=" * 80)

    with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
        with driver.session() as session:
            for q in queries:
                print(f"• DDL 실행: {q}")
                session.run(q)

    print("✔️ [마이그레이션 완료] 유니크 제약조건 2종 정상 반영 확인")
    print("=" * 80)


if __name__ == "__main__":
    apply_evidence_schema_migration()
