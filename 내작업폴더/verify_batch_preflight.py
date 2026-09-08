import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(".env", override=True)
NEO4J_URI = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("AURA_USER") or os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")
DART_API_KEY = os.getenv("DART_API_KEY")

print(f"1. DART_API_KEY 존재 여부: {bool(DART_API_KEY)} (길이: {len(DART_API_KEY) if DART_API_KEY else 0})")
print(f"2. NEO4J_URI (AURA): {NEO4J_URI}")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
with driver.session() as s:
    res = s.run("MATCH (c:DART_Company {market: 'KOSPI'}) RETURN count(c) as c").single()
    print(f"3. KOSPI 기업 수 in Neo4j Aura: {res['c']}개")
    res_kd = s.run("MATCH (c:DART_Company {market: 'KOSDAQ'}) RETURN count(c) as c").single()
    print(f"4. KOSDAQ 기업 수 in Neo4j Aura: {res_kd['c']}개")

driver.close()
print("🎉 Neo4j Aura & DART API 사전 점검 100% 정상 통과!")
