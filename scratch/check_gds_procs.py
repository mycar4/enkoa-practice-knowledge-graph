# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    procs = s.run("SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'gds' RETURN name").data()
    print(f"사용 가능한 GDS 프로시저 수: {len(procs)}개")
    for p in procs[:15]:
        print(f"  • {p['name']}")
