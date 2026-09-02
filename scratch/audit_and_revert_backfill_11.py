# -*- coding: utf-8 -*-
"""
🔍 [감사 및 정합화] Sprint 6.4 백필 11건 관계 전수 감사 및 임의 가정값 원복/정밀 분리
"""
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    print("="*90)
    print("🔍 [1. 백필된 OWNS_STAKE 관계 11건 전수 속성 실측 감사]")
    print("="*90)
    
    rows = s.run("""
    MATCH (h)-[r:OWNS_STAKE]->(t:DART_Company)
    WHERE r.is_current = true
    RETURN coalesce(h.name, h.corp_code, h.org_id) AS holder,
           t.name AS target,
           properties(r) AS props
    """).data()
    
    print(f"총 {len(rows)}건 유효 지분 관계 발견:\n")
    for idx, r in enumerate(rows, 1):
        print(f"[{idx}] {r['holder']} ➔ {r['target']}")
        print(f"    속성: {r['props']}\n")
        
    # 2. 임의 가정값(DISCLOSURE_FACT 등) 및 임의 생성된 source_edge_key / current_scope 원복
    # 원천 공시에서 검증되지 않은 백필 속성을 제거하고 metadata_status = 'LEGACY_UNVERIFIED' 로 안전 격리
    print("="*90)
    print("🔄 [2. 임의 가정값 제거 및 원천 미검증 속성 롤백/격리]")
    print("="*90)
    
    res = s.run("""
    MATCH (h)-[r:OWNS_STAKE]->(t:DART_Company)
    WHERE r.is_current = true
    SET r.metadata_status = 'UNVERIFIED_LEGACY'
    REMOVE r.source_edge_key,
           r.current_scope
    RETURN count(r) AS cleaned_cnt
    """).single()["cleaned_cnt"]
    
    print(f"✅ {res}건의 관계에서 임의 가정값(`source_edge_key`, `current_scope`)을 완전히 제거하고 `metadata_status='UNVERIFIED_LEGACY'`로 격리 완료.")
