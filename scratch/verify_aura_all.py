# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    total_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    total_corps = s.run("MATCH (c:DART_Company) RETURN count(c) AS c").single()["c"]
    kospi_cnt = s.run("MATCH (c:DART_Company {market: 'KOSPI'}) RETURN count(c) AS c").single()["c"]
    kosdaq_cnt = s.run("MATCH (c:DART_Company {market: 'KOSDAQ'}) RETURN count(c) AS c").single()["c"]
    total_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    
    print("="*80)
    print("🏛️ [Neo4j Aura 클라우드] 대한민국 전체 상장사 베이스라인 구축 현황")
    print("="*80)
    print(f"• 클라우드 총 노드 수: {total_nodes:,}개")
    print(f"• 전체 상장사(:DART_Company): {total_corps:,}개사")
    print(f"   - 🏢 코스피(KOSPI): {kospi_cnt:,}개사")
    print(f"   - 🚀 코스닥(KOSDAQ): {kosdaq_cnt:,}개사")
    print(f"• 누적 연결 관계 수: {total_rels:,}건")
    print("="*80)
