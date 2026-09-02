import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env")
load_dotenv("내작업폴더/.env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
with driver.session() as s:
    graphs = [r["graphName"] for r in s.run("CALL gds.graph.list() YIELD graphName RETURN graphName")]
    for g in graphs:
        s.run(f'CALL gds.graph.drop("{g}") YIELD graphName')
        print(f"🧹 메모리에서 정리 완료: {g}")
    print("✅ 모든 GDS 인메모리 투영이 깨끗하게 정리되었습니다!")
