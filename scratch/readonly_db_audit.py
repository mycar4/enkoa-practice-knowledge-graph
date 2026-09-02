# -*- coding: utf-8 -*-
"""
🔍 [DART-Trace 읽기 전용 데이터베이스 감사 스크립트 (Read-Only DB Audit)]
- 목적: 운영 DB에 어떠한 쓰기/삭제도 발생시키지 않고, 현재 노드/관계/식별자/라벨 상태를 정밀 진단
"""

import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

print("="*90)
print("🔍 [읽기 전용 감사] Neo4j Aura DB 엔티티 및 식별자 현황 정밀 진단")
print("="*90)

with driver.session() as s:
    # 1. 라벨별 전체 노드 수
    labels_res = s.run("""
    MATCH (n)
    UNWIND labels(n) AS lbl
    RETURN lbl, count(n) AS cnt
    ORDER BY cnt DESC
    """).data()
    print("📊 [1. 라벨별 전체 노드 수]")
    for r in labels_res:
        print(f"  • {r['lbl']:<30}: {r['cnt']:>8,d}개")
        
    # 2. 관계 유형별 전체 수
    rels_res = s.run("""
    MATCH ()-[r]->()
    RETURN type(r) AS rel_type, count(r) AS cnt
    ORDER BY cnt DESC
    """).data()
    print("\n📊 [2. 관계 유형별 전체 건수]")
    for r in rels_res:
        print(f"  • {r['rel_type']:<30}: {r['cnt']:>8,d}건")
        
    # 3. DART_Company의 corp_code 존재 현황 (Null vs Non-Null)
    comp_audit = s.run("""
    MATCH (c:DART_Company)
    RETURN count(c) AS total_companies,
           count(c.corp_code) AS has_corp_code,
           count(c) - count(c.corp_code) AS missing_corp_code
    """).single()
    print("\n📊 [3. DART_Company 식별자(corp_code) 무결성]")
    print(f"  • 전체 DART_Company 노드 수: {comp_audit['total_companies']:,}개")
    print(f"  • corp_code 정상 보유 노드: {comp_audit['has_corp_code']:,}개")
    print(f"  • corp_code 누락 노드    : {comp_audit['missing_corp_code']:,}개")
    
    # 4. DART_Organization의 org_id 존재 현황
    org_audit = s.run("""
    MATCH (o:DART_Organization)
    RETURN count(o) AS total_orgs,
           count(o.org_id) AS has_org_id,
           count(o) - count(o.org_id) AS missing_org_id
    """).single()
    print("\n📊 [4. DART_Organization 식별자(org_id) 무결성]")
    print(f"  • 전체 DART_Organization 노드: {org_audit['total_orgs']:,}개")
    print(f"  • org_id 정상 보유 노드     : {org_audit['has_org_id']:,}개")
    print(f"  • org_id 누락 노드         : {org_audit['missing_org_id']:,}개")
    
    # 5. DART_Person의 global_person_id 존재 현황
    person_audit = s.run("""
    MATCH (p:DART_Person)
    RETURN count(p) AS total_persons,
           count(p.global_person_id) AS has_global_id,
           count(p) - count(p.global_person_id) AS missing_global_id
    """).single()
    print("\n📊 [5. DART_Person 식별자(global_person_id) 무결성]")
    print(f"  • 전체 DART_Person 노드: {person_audit['total_persons']:,}개")
    print(f"  • global_person_id 정상 보유: {person_audit['has_global_id']:,}개")
    print(f"  • global_person_id 누락     : {person_audit['missing_global_id']:,}개")
    
    # 6. OWNS_STAKE 관계의 is_current 플래그 및 source_rcept_no 보유 현황
    stake_audit = s.run("""
    MATCH ()-[r:OWNS_STAKE]->()
    RETURN count(r) AS total_stakes,
           count(r.stake) AS has_stake,
           count(CASE WHEN r.is_current = true THEN 1 END) AS current_true,
           count(CASE WHEN r.is_current = false THEN 1 END) AS current_false,
           count(CASE WHEN r.is_current IS NULL THEN 1 END) AS current_null,
           count(r.source_rcept_no) AS has_rcept_no
    """).single()
    print("\n📊 [6. OWNS_STAKE 지분 관계 속성 현황]")
    print(f"  • 전체 지분 관계 수   : {stake_audit['total_stakes']:,}건")
    print(f"  • stake 지분율 보유   : {stake_audit['has_stake']:,}건")
    print(f"  • is_current: true    : {stake_audit['current_true']:,}건")
    print(f"  • is_current: false   : {stake_audit['current_false']:,}건")
    print(f"  • is_current: NULL    : {stake_audit['current_null']:,}건")
    print(f"  • source_rcept_no 보유: {stake_audit['has_rcept_no']:,}건")

print("\n" + "="*90)
print("✅ [읽기 전용 감사 완료] DB 변경 0건, 현황 진단 완수")
print("="*90)
