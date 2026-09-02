# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    s.run("MATCH (d:DART_Disclosure {rcept_no: '20240415000888'}) DETACH DELETE d")
    s.run("MATCH (f:DART_FinancialSnapshot) WHERE f.snapshot_id CONTAINS '20240415000888' DETACH DELETE f")
    s.run("MATCH (d:DART_Disclosure {rcept_no: '20240312000736'}) SET d.is_latest = true")
    s.run("MATCH (f:DART_FinancialSnapshot {snapshot_id: '00126380_2023-12-31_11011_CFS_20240312000736'}) SET f.is_latest = true")
    print("Aura 클라우드 테스트 임시 데이터 100% 정화 및 원상 복구 완료!")
