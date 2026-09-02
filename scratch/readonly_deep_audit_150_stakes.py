# -*- coding: utf-8 -*-
"""
🔍 [100% 읽기 전용 정밀 감사] OWNS_STAKE 전체 150건 속성 및 가정값 잔존 현황 진단
"""
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    print("="*95)
    print("🔍 [1. OWNS_STAKE 전체 150건 상태 및 속성 전수 감사]")
    print("="*95)
    
    # 1. is_current 상태별 분포
    curr_dist = s.run("""
    MATCH ()-[r:OWNS_STAKE]->()
    RETURN r.is_current AS is_current, count(r) AS cnt
    """).data()
    print("📊 [is_current 상태 분포]:", curr_dist)
    
    # 2. metadata_status 분포
    meta_dist = s.run("""
    MATCH ()-[r:OWNS_STAKE]->()
    RETURN r.metadata_status AS meta_status, count(r) AS cnt
    """).data()
    print("📊 [metadata_status 분포]:", meta_dist)
    
    # 3. source_rcept_no = 'DISCLOSURE_FACT' 잔존 여부
    fake_rcept = s.run("""
    MATCH ()-[r:OWNS_STAKE]->()
    WHERE r.source_rcept_no = 'DISCLOSURE_FACT'
    RETURN count(r) AS cnt
    """).single()["cnt"]
    print(f"📊 [가정값 source_rcept_no='DISCLOSURE_FACT' 건수]: {fake_rcept}건")
    
    # 4. is_current = true 인 모든 11건 관계의 전수 속성 덤프
    print("\n" + "="*95)
    print("📋 [is_current = true 유효 관계 11건 전수 속성 덤프]")
    print("="*95)
    
    rows = s.run("""
    MATCH (h)-[r:OWNS_STAKE]->(t)
    WHERE r.is_current = true
    RETURN coalesce(h.name, h.corp_code, h.org_id) AS holder,
           t.name AS target,
           t.corp_code AS target_code,
           r.stake AS stake,
           r.source_rcept_no AS rcept_no,
           r.share_class AS share_class,
           r.voting_type AS voting_type,
           r.ownership_basis AS ownership_basis,
           r.metadata_status AS metadata_status,
           r.as_of_date AS as_of_date,
           r.reported_on AS reported_on,
           r.updated_at AS updated_at
    ORDER BY t.name, stake DESC
    """).data()
    
    for idx, r in enumerate(rows, 1):
        print(f"[{idx:2d}] {r['holder']} ➔ {r['target']} ({r['stake']}%)")
        print(f"     • 공시번호: {r['rcept_no']} | 주식종류: {r['share_class']} | 의결권: {r['voting_type']} | 직접/간접: {r['ownership_basis']}")
        print(f"     • 메타상태: {r['metadata_status']} | 기준일: {r['as_of_date']} | 보고일: {r['reported_on']} | 수정시각: {r['updated_at']}\n")
