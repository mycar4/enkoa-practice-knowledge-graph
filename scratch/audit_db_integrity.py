# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    # 1. 제약조건 목록
    constraints = s.run("SHOW CONSTRAINTS").data()
    print("Aura DB 현재 제약조건 목록:")
    for c in constraints:
        print(f"  • {c.get('name')}: {c.get('type')} on {c.get('labelsOrTypes')} ({c.get('properties')})")
        
    # 2. 식별자가 없는 비정상 노드 확인 (corp_code 없는 DART_Company 등)
    invalid_companies = s.run("MATCH (c:DART_Company) WHERE c.corp_code IS NULL RETURN c.name AS name").data()
    print(f"\ncorp_code 없는 비정상 DART_Company 노드 수: {len(invalid_companies)}개")
    for ic in invalid_companies:
        print(f"  ⚠️ {ic['name']}")
