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
    MATCH (h)-[r:OWNS_STAKE]->(c:DART_Company)
    WHERE r.is_current = true
    RETURN labels(h)[0] AS holder_label,
           count(r) AS stake_count,
           avg(r.stake) AS avg_stake
    """).data()
    print("Aura 클라우드 현재 is_current=true 지분 관계 통계:")
    for r in res:
        print(f"  • {r['holder_label']}: {r['stake_count']}건 (평균 지분율: {r['avg_stake']:.2f}%)")
