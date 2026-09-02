# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    res = s.run("""
    MATCH (n) WHERE n.name IN ['계', '합계', '소계', '총계']
    DETACH DELETE n
    RETURN count(n) AS cnt
    """).single()["cnt"]
    print(f"🧹 합계/소계 요약 노드 정리 완료: {res}개 삭제")
