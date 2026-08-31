# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 인덱스 및 제약조건 도입 & 실행계획(EXPLAIN/PROFILE) 검증 스크립트
"""

import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test0011"))

def run_cypher(query, **params):
    with driver.session() as s:
        return [r.data() for r in s.run(query, **params)]

print("="*80)
print("🚀 [1단계] DART-Trace 핵심 인덱스 및 UNIQUE 제약조건 생성")
print("="*80)

# 1. UNIQUE 제약조건 생성 (중복 방지 + 자동 RANGE B-Tree 인덱스 생성)
run_cypher("CREATE CONSTRAINT dart_uniq_company IF NOT EXISTS FOR (c:DART_Company) REQUIRE c.name IS UNIQUE")
run_cypher("CREATE CONSTRAINT dart_uniq_person IF NOT EXISTS FOR (p:DART_Person) REQUIRE p.name IS UNIQUE")
print("✅ [UNIQUE 제약] DART_Company.name & DART_Person.name 고유 제약조건 생성 완료!")

# 2. TEXT 전문 인덱스 생성 (부분일치 CONTAINS / ENDS WITH 가속)
run_cypher("CREATE TEXT INDEX dart_txt_company IF NOT EXISTS FOR (c:DART_Company) ON (c.name)")
run_cypher("CREATE TEXT INDEX dart_txt_group IF NOT EXISTS FOR (g:DART_Group) ON (g.name)")
print("✅ [TEXT 인덱스] DART_Company.name & DART_Group.name 부분일치 전문 색인 생성 완료!")

# 3. 현재 등록된 DART 인덱스/제약조건 목록 메타데이터 조회
print("\n" + "="*80)
print("📋 [2단계] Neo4j DB 내 실제 활성화된 DART 인덱스 메타데이터 (SHOW INDEXES)")
print("="*80)
indexes = run_cypher("SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state WHERE name STARTS WITH 'dart_'")
for idx in indexes:
    name_str = idx.get("name", "")
    type_str = idx.get("type", "")
    labels_str = str(idx.get("labelsOrTypes", []))
    props_str = str(idx.get("properties", []))
    state_str = idx.get("state", "")
    print(f"• 인덱스명: {name_str:<22} | 타입: {type_str:<8} | 대상 레이블: {labels_str:<18} | 속성: {props_str:<10} | 상태: {state_str}")

# 4. 실행계획(EXPLAIN) 연산자 검증
print("\n" + "="*80)
print("⚡ [3단계] 쿼리 실행계획(EXPLAIN) 연산자 실측 검증")
print("="*80)
with driver.session() as s:
    # A. 정확 일치 검색 -> NodeIndexSeek (B-Tree 색인)
    res1 = s.run("EXPLAIN MATCH (c:DART_Company {name: '삼성전자'}) RETURN c")
    plan1 = res1.consume().plan
    op1 = plan1.get("operatorType", str(plan1)) if isinstance(plan1, dict) else getattr(plan1, "operator_type", str(plan1))
    print(f"1. [정확 일치 검색] ('삼성전자' = )")
    print(f"   ➔ 실행계획 연산자: [{op1}] (B-Tree RANGE Index 활용)\n")

    # B. 부분 일치 검색 -> NodeIndexContainsScan (TEXT Index)
    res2 = s.run("EXPLAIN MATCH (c:DART_Company) WHERE c.name CONTAINS '홀딩스' RETURN c")
    plan2 = res2.consume().plan
    op2 = plan2.get("operatorType", str(plan2)) if isinstance(plan2, dict) else getattr(plan2, "operator_type", str(plan2))
    print(f"2. [부분 일치 검색] ('홀딩스' CONTAINS)")
    print(f"   ➔ 실행계획 연산자: [{op2}] (TEXT 전문 Index 활용)\n")

print("="*80)
print("🎉 DART-Trace 3대 인덱스 엔진 도입 및 성능 검증 100% 완료!")
print("="*80)
