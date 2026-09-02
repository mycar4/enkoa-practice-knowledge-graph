# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    apocs = s.run("SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc' RETURN name").data()
    print(f"사용 가능한 APOC 프로시저 수: {len(apocs)}개")
    for a in apocs[:10]:
        print(f"  • {a['name']}")
