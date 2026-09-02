# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    try:
        ver = s.run("RETURN gds.version() AS ver").single()["ver"]
        print(f"✅ GDS 버전: {ver}")
    except Exception as e:
        print(f"⚠️ GDS 직접 호출 결과: {e}")
