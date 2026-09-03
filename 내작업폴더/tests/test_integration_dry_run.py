# -*- coding: utf-8 -*-
"""
🌐 [v1.3.1 통합 테스트] Aura DB 3대 엔티티 Provider 및 READ 모드 검증
========================================================================================================
[검증 목적]
1. Neo4j Aura DB와의 실제 통신 시 `default_access_mode="READ"` 강제 적용 검증
2. 실 운영 DB의 3대 엔티티(Company, Person, Organization)를 로드하여 다중 매칭(동명이인) 방어 실측
3. 통합 실행 전후 실 DB의 노드/관계 수 불변성 실측 (Zero-Write Guard)
4. 실 공시(SK하이닉스) 입력 시 '0건 WRITE 후보 (True-Zero 무결성)' 실측
========================================================================================================
"""

import os
import sys
from typing import Dict, Set, Tuple, Optional, List
from collections import defaultdict
from dotenv import load_dotenv
import neo4j

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    MasterEntityProvider,
    run_dry_run_simulation_v131
)

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
AURA_INSTANCE_ID = os.getenv("AURA_INSTANCEID", "a8a048c8")

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class Aura3EntityAmbiguityManager:
    """Aura DB 연동 3대 엔티티 다중 매칭 방어 Provider (AccessMode.READ 강제)"""
    def __init__(self, uri, auth):
        self.driver = neo4j.GraphDatabase.driver(uri, auth=auth, max_connection_lifetime=60)
        self._load_master_caches()

    def _load_master_caches(self):
        with self.driver.session(default_access_mode="READ") as s:
            # Company 로드 (이름 -> list of corp_code)
            self.companies = defaultdict(list)
            c_rows = s.run("MATCH (c:DART_Company) RETURN c.name AS name, c.corp_code AS code").data()
            for r in c_rows:
                if r.get("name") and r.get("code"):
                    self.companies[r["name"]].append(r["code"])
                    clean = r["name"].replace("(주)", "").replace("주식회사", "").replace("㈜", "").strip()
                    if clean != r["name"]:
                        self.companies[clean].append(r["code"])
                        
            # Person 로드 (이름 -> list of global_person_id)
            self.persons = defaultdict(list)
            p_rows = s.run("MATCH (p:DART_Person) RETURN p.name AS name, p.global_person_id AS id").data()
            for r in p_rows:
                if r.get("name") and r.get("id"):
                    self.persons[r["name"]].append(r["id"])
                    
            # Organization 로드 (이름 -> list of org_id)
            self.orgs = defaultdict(list)
            o_rows = s.run("MATCH (o:DART_Organization) RETURN o.name AS name, o.org_id AS id").data()
            for r in o_rows:
                if r.get("name") and r.get("id"):
                    self.orgs[r["name"]].append(r["id"])

    def resolve_company(self, name_or_code: str) -> Tuple[Optional[str], bool]:
        pks = list(set(self.companies.get(name_or_code, [])))
        if len(pks) > 1: return (None, True)
        if len(pks) == 1: return (pks[0], False)
        return (None, False)

    def resolve_person(self, name: str, resident_no_or_id: str = "") -> Tuple[Optional[str], bool]:
        pks = list(set(self.persons.get(name, [])))
        if len(pks) > 1: return (None, True)
        if len(pks) == 1: return (pks[0], False)
        return (None, False)

    def resolve_organization(self, name_or_id: str) -> Tuple[Optional[str], bool]:
        pks = list(set(self.orgs.get(name_or_id, [])))
        if len(pks) > 1: return (None, True)
        if len(pks) == 1: return (pks[0], False)
        return (None, False)

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
    print("🌐 [v1.3.1 통합 테스트 실행] Aura DB 3대 엔티티 다중 매칭 방어 & READ 모드 검증")
    print("="*80)
    
    provider = Aura3EntityAmbiguityManager(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
    
    # 1. 실행 전 실 DB 상태 실측
    pre_nodes, pre_rels = provider.get_pre_counts()
    print(f"  • 실 DB 3대 마스터 사전 캐시:")
    print(f"    - Company: {len(provider.companies):,}개 이름 매핑")
    print(f"    - Person: {len(provider.persons):,}개 이름 매핑")
    print(f"    - Organization: {len(provider.orgs):,}개 이름 매핑")
    print(f"  • 실 DB 실행 전 상태: 노드 {pre_nodes:,}개 | 관계 {pre_rels:,}개")
    
    # 2. DRY_RUN 파서 엔진 v1.3.1 실행
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    res = run_dry_run_simulation_v131(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id=AURA_INSTANCE_ID,
        manifest_id="TEST_INTEGRATION_V131_AURA"
    )
    
    manifest = res["manifest"]
    
    # 3. 실행 후 실 DB 상태 실측 및 불변성 검증
    post_nodes, post_rels = provider.get_pre_counts()
    provider.close()
    
    assert pre_nodes == post_nodes, f"❌ 실 DB 노드 수 변동 발생: {pre_nodes} != {post_nodes}"
    assert pre_rels == post_rels, f"❌ 실 DB 관계 수 변동 발생: {pre_rels} != {post_rels}"
    
    # 4. True-Zero 후보 검증 (실 공시 표에 소유형태 독립 컬럼 부재로 0건 WRITE 후보 도출)
    assert res["planned_creations_count"] == 0, f"❌ True-Zero 원칙 위반: {res['planned_creations_count']}건"
    assert res["planned_updates_count"] == 0, f"❌ True-Zero 원칙 위반: {res['planned_updates_count']}건"
    assert res["skipped_records_count"] > 0, "❌ 격리 기록 누락"
    
    print("\n📊 [통합 테스트 실측 결과 (v1.3.1 True-Zero 무결성 입증)]:")
    print(f"  • DB Zero-Write 검증: 노드 {pre_nodes} == {post_nodes}, 관계 {pre_rels} == {post_rels} (변화 0건)")
    print(f"  • 예정 생성(creations): {res['planned_creations_count']}건 (독립 소유형태 컬럼 결측으로 0건 정상 도출)")
    print(f"  • 예정 갱신(updates): {res['planned_updates_count']}건")
    print(f"  • 안전 보류(skipped_records): {res['skipped_records_count']}건 (100% 안전 격리 완료)")
    print("="*80)
    print("🎉 [통합 테스트 100% 통과] Aura AccessMode.READ 모드 하에서 True-Zero 무결성 완벽 입증!")
    print("="*80)

if __name__ == "__main__":
    main()
