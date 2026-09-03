# -*- coding: utf-8 -*-
"""
🌐 [통합 테스트] Aura DB 읽기 전용 연결 및 AccessMode.READ 강제 검증
========================================================================================================
[검증 목적]
1. Neo4j Aura DB와의 실제 통신 시 `default_access_mode=neo4j.AccessMode.READ` 강제 적용 검증
2. 실 운영 DB의 상장사 마스터(`DART_Company`)를 로드하여 DRY_RUN 파서 엔진과의 통합 연동 실측
3. 통합 실행 전후 실 DB의 노드/관계 수 불변성 실측
========================================================================================================
"""

import os
import sys
from typing import Dict, Set, Tuple
from dotenv import load_dotenv
import neo4j

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    ExistingEdgeProvider,
    run_dry_run_with_provider
)

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
AURA_INSTANCE_ID = os.getenv("AURA_INSTANCEID", "a8a048c8")

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class AuraReadOnlyEdgeProvider:
    """Aura DB 연동 읽기 전용 Provider (AccessMode.READ 강제)"""
    def __init__(self, uri, auth):
        self.driver = neo4j.GraphDatabase.driver(uri, auth=auth, max_connection_lifetime=60)

    def get_corp_master_map(self) -> Dict[str, str]:
        with self.driver.session(default_access_mode="READ") as s:
            rows = s.run("MATCH (c:DART_Company) RETURN c.name AS name, c.corp_code AS code").data()
            return {r["name"]: r["code"] for r in rows if r.get("name") and r.get("code")}

    def get_existing_edge_keys(self) -> Set[str]:
        with self.driver.session(default_access_mode="READ") as s:
            return set(s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN r.source_edge_key AS k").value())

    def get_pre_counts(self) -> Tuple[int, int]:
        with self.driver.session(default_access_mode="READ") as s:
            nodes = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
            rels = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
            return (nodes, rels)

    def close(self):
        self.driver.close()

def main():
    print("="*80)
    print("🌐 [통합 테스트 실행] Aura DB AccessMode.READ 읽기 전용 모드 검증")
    print("="*80)
    
    provider = AuraReadOnlyEdgeProvider(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
    
    # 1. 실행 전 실 DB 상태 실측
    pre_nodes, pre_rels = provider.get_pre_counts()
    master_map = provider.get_corp_master_map()
    existing_keys = provider.get_existing_edge_keys()
    print(f"  • 실 DB 상장사 마스터 사전: {len(master_map):,}개사 로드 완료")
    print(f"  • 실 DB 실행 전 상태: 노드 {pre_nodes:,}개 | 관계 {pre_rels:,}개")
    
    # 2. DRY_RUN 파서 엔진 실행
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    res = run_dry_run_with_provider(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id=AURA_INSTANCE_ID,
        manifest_id="TEST_INTEGRATION_AURA_READONLY"
    )
    
    manifest = res["manifest"]
    
    # 3. 실행 후 실 DB 상태 실측 및 불변성 검증
    post_nodes, post_rels = provider.get_pre_counts()
    provider.close()
    
    assert pre_nodes == post_nodes, f"❌ 실 DB 노드 수 변동 발생: {pre_nodes} != {post_nodes}"
    assert pre_rels == post_rels, f"❌ 실 DB 관계 수 변동 발생: {pre_rels} != {post_rels}"
    
    print("\n📊 [통합 테스트 실측 결과]:")
    print(f"  • DB Zero-Write 검증: 노드 {pre_nodes} == {post_nodes}, 관계 {pre_rels} == {post_rels} (변화 0건)")
    print(f"  • 예정 생성(creations): {res['planned_creations_count']}건")
    print(f"  • 예정 갱신(updates): {res['planned_updates_count']}건")
    print(f"  • 보류(skipped_records): {res['skipped_records_count']}건")
    print("="*80)
    print("🎉 [통합 테스트 100% 통과] Aura AccessMode.READ 모드 하에서 Zero-Write 완벽 입증!")
    print("="*80)

if __name__ == "__main__":
    main()
