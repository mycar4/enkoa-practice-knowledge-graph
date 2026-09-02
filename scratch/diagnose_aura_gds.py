# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

print("="*80)
print("🔍 Neo4j Aura 인스턴스 GDS(Graph Data Science) 실행 가능 여부 정밀 진단")
print("="*80)

# 1. CALL gds.version() 테스트
with driver.session() as s:
    try:
        ver = s.run("CALL gds.version() YIELD version RETURN version").single()["version"]
        print(f"✅ CALL gds.version() 성공: version = '{ver}'")
    except Exception as e:
        print(f"❌ CALL gds.version() 실패: {e}")

# 2. gds.graph.project 테스트
with driver.session() as s:
    try:
        res = s.run("""
        CALL gds.graph.project(
            'test_proj',
            'DART_Company',
            'OWNS_STAKE'
        )
        YIELD graphName, nodeCount
        RETURN graphName, nodeCount
        """).single()
        print(f"✅ gds.graph.project 성공: {res}")
    except Exception as e:
        print(f"❌ gds.graph.project 실패: {e}")
