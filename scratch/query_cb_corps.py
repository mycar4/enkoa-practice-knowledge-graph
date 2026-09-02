# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    records = s.run("""
    MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
    RETURN c.name AS name, c.corp_code AS corp_code, e.event_name AS event_name, e.source_rcept_no AS rcept_no
    LIMIT 10
    """).data()

print("Aura 클라우드에 적재된 CB/자본이벤트 기업 샘플:")
for r in records:
    print(f"  • {r['name']} ({r['corp_code']}): {r['event_name']} (접수번호: {r['rcept_no']})")
