# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PWD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PWD))

with driver.session() as s:
    q = """
    MATCH (c:DART_Company {name: '삼성전자'})<-[r:OWNS_STAKE]-(holder)
    RETURN holder.name AS holder, r.stake AS stake
    ORDER BY r.stake DESC
    """
    records = s.run(q).data()
    print(f"🎯 [Aura 클라우드 실시간 쿼리 성공: 삼성전자 주요 주주]")
    for r in records:
        print(f"  • {r['holder']}: {r['stake']}%")
