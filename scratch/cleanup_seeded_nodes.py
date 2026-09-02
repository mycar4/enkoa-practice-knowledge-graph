# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    # 운영 DB에 임시 시딩되었던 BlackRock Raw 및 Decision 노드 정리
    res = s.run("""
    MATCH (n) WHERE n.raw_id STARTS WITH 'RAW_' OR n.decision_id STARTS WITH 'DEC_' OR n.raw_id STARTS WITH 'TOY_'
    DETACH DELETE n
    RETURN count(n) AS deleted_cnt
    """).single()["deleted_cnt"]
    print(f"🧹 운영 DB 잔여 시딩 노드 정리 완료: {res}개 삭제")
