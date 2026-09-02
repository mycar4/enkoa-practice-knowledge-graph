# -*- coding: utf-8 -*-
"""
지하철 데이터(Station, NEXT_TO) 및 송금 데이터(Account, TRANSFERRED)를 Neo4j에 즉시 적재
"""
import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")
AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")

driver = None
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ 로컬 Neo4j 연결")
except Exception:
    if AURA_URI and AURA_USER and AURA_PASSWORD:
        driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        driver.verify_connectivity()
        print("✅ Aura Cloud DB 연결")
    else:
        raise ConnectionError("DB 연결 실패")

def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

# 1. 지하철 데이터 로더 임포트
DATA_DIR = Path("day30_Cypher_심화/data") if Path("day30_Cypher_심화/data").exists() else Path("내작업폴더/day30_Cypher_심화/data")
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))
from load_subway import load

print("🚇 수도권 전철 데이터 적재 시작...")
run_cypher("MATCH (n:Station) DETACH DELETE n")
n_station, n_edge = load(run_cypher)
print(f"✅ 전철 데이터 적재 완료: 역 {n_station}개, 구간 {n_edge}개")

# 2. 송금 데이터 적재
print("💳 계좌 송금 데이터 적재 시작...")
run_cypher("MATCH (n:Account) DETACH DELETE n")
run_cypher("""
CREATE (a1:Account {id:'A', owner:'김철수', balance:1000}),
       (a2:Account {id:'B', owner:'이영희', balance:500}),
       (a3:Account {id:'C', owner:'박민수', balance:200}),
       (a4:Account {id:'D', owner:'최지우', balance:1500}),
       (a5:Account {id:'E', owner:'정하나', balance:800}),
       (a6:Account {id:'F', owner:'강동원', balance:300}),
       (a7:Account {id:'G', owner:'윤서아', balance:950}),
       (a8:Account {id:'H', owner:'임재범', balance:1200}),
       (a9:Account {id:'I', owner:'한소희', balance:600}),
       (a10:Account {id:'J', owner:'송중기', balance:450}),
       (a11:Account {id:'K', owner:'송혜교', balance:700})
CREATE (a1)-[:TRANSFERRED {amount:200, date:date('2026-03-01')}]->(a2),
       (a1)-[:TRANSFERRED {amount:300, date:date('2026-03-02')}]->(a3),
       (a2)-[:TRANSFERRED {amount:150, date:date('2026-03-03')}]->(a4),
       (a2)-[:TRANSFERRED {amount:100, date:date('2026-03-04')}]->(a5),
       (a3)-[:TRANSFERRED {amount:250, date:date('2026-03-05')}]->(a5),
       (a4)-[:TRANSFERRED {amount:400, date:date('2026-03-06')}]->(a6),
       (a5)-[:TRANSFERRED {amount:500, date:date('2026-03-07')}]->(a7),
       (a6)-[:TRANSFERRED {amount:100, date:date('2026-03-08')}]->(a8),
       (a7)-[:TRANSFERRED {amount:300, date:date('2026-03-09')}]->(a8),
       (a8)-[:TRANSFERRED {amount:450, date:date('2026-03-10')}]->(a9),
       (a9)-[:TRANSFERRED {amount:200, date:date('2026-03-11')}]->(a10),
       (a10)-[:TRANSFERRED {amount:150, date:date('2026-03-12')}]->(a11),
       (a1)-[:TRANSFERRED {amount:50,  date:date('2026-03-13')}]->(a6),
       (a3)-[:TRANSFERRED {amount:180, date:date('2026-03-14')}]->(a7)
""")
print("✅ 계좌 송금 데이터 적재 완료: 계좌 11개, 송금 14건")
