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
    MATCH (c:DART_Company)
    WHERE c.name IN ['삼성물산', 'SK스퀘어', 'SK', '카카오', '삼성전자', 'SK하이닉스']
    RETURN c.name AS name, c.corp_code AS corp_code, c.stock_code AS stock_code, labels(c) AS labels
    """).data()
    print("DART_Company 노드 조회 결과:")
    for r in res:
        print(f"  • {r['name']}: corp_code={r['corp_code']}, stock_code={r['stock_code']}")
