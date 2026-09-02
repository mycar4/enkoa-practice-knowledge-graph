# -*- coding: utf-8 -*-
"""
🧹 [마스터 정합화] 이름으로 생성된 임시 PERSON_/CORP_ 노드를 공식 DART_Company(corp_code)로 완전 단일화
"""
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    print("="*95)
    print("🧹 [임시 중복 주주 노드 ➔ 공식 DART_Company 단일화 정리]")
    print("="*95)
    
    # 1. 삼성물산 임시 노드 관계를 공식 삼성물산(00149655 또는 00126229)으로 이관 및 임시 노드 삭제
    s.run("""
    MATCH (dummy) WHERE dummy.global_person_id IN ['PERSON_삼성물산', 'CORP_삼성물산', 'CORP_삼성물산㈜']
    MATCH (official:DART_Company) WHERE official.corp_code IN ['00149655', '00126229'] AND official.name = '삼성물산'
    MATCH (dummy)-[r:OWNS_STAKE]->(target)
    MERGE (official)-[r2:OWNS_STAKE {source_edge_key: r.source_edge_key}]->(target)
    SET r2 = properties(r),
        r2.source_holder_key = official.corp_code
    DETACH DELETE dummy
    """)
    
    # 2. 현대모비스 임시 노드 관계를 공식 현대모비스(00164788)로 이관 및 임시 노드 삭제
    s.run("""
    MATCH (dummy) WHERE dummy.global_person_id IN ['PERSON_현대모비스', 'CORP_현대모비스']
    MATCH (official:DART_Company {corp_code: '00164788'})
    MATCH (dummy)-[r:OWNS_STAKE]->(target)
    MERGE (official)-[r2:OWNS_STAKE {source_edge_key: r.source_edge_key}]->(target)
    SET r2 = properties(r),
        r2.source_holder_key = official.corp_code
    DETACH DELETE dummy
    """)
    
    # 3. SK스퀘어 임시 노드 관계를 공식 SK스퀘어(01596425)로 이관 및 임시 노드 삭제
    s.run("""
    MATCH (dummy) WHERE dummy.global_person_id IN ['PERSON_SK스퀘어', 'CORP_SK스퀘어']
    MATCH (official:DART_Company {corp_code: '01596425'})
    MATCH (dummy)-[r:OWNS_STAKE]->(target)
    MERGE (official)-[r2:OWNS_STAKE {source_edge_key: r.source_edge_key}]->(target)
    SET r2 = properties(r),
        r2.source_holder_key = official.corp_code
    DETACH DELETE dummy
    """)
    
    print("✅ 임시 노드 단일화 및 공식 DART_Company 매핑 완료!")
