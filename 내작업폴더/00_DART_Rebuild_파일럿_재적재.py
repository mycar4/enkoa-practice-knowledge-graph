# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] DART 파일럿 데이터 재적재 (Rebuild Pipeline)

⚠️ [주의 및 거버넌스 원칙]
1. 본 스크립트는 '백업 복원(Restore)'이 아니라, DART 100개사 파일럿 데이터를 처음부터 '새로 재적재(Rebuild)'하는 파이프라인입니다.
2. 실행 시 기존 DB의 DART 노드를 초기화하므로, 검수 완료된 DB 스냅샷 상태와 수치 차이가 발생할 수 있습니다.
3. 임의 자동 실행을 금지하며, 개발/테스트 초기화 목적에만 제한적으로 사용합니다.
"""

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(".env", override=True)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

if not NEO4J_PASSWORD:
    print("❌ 오류: .env 파일에 NEO4J_PASSWORD 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

print("================================================================================")
print("⚙️ [DART-Trace] 100개사 파일럿 데이터 재적재(Rebuild) 파이프라인 가동")
print("================================================================================")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# 1. 인덱스 제약조건 선행 확인 및 비-DART 잔여물 청소
with driver.session() as s:
    print("🧹 1단계: 비-DART 교안 노드 청소 및 인덱스 제약조건 선행 점검...")
    s.run("MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'DART_') DETACH DELETE n")
    s.run("CREATE CONSTRAINT dart_company_corp_code_unique IF NOT EXISTS FOR (c:DART_Company) REQUIRE c.corp_code IS UNIQUE")
    s.run("CREATE CONSTRAINT dart_disclosure_rcept_no_unique IF NOT EXISTS FOR (d:DART_Disclosure) REQUIRE d.rcept_no IS UNIQUE")
    print("✅ 인덱스 제약조건 점검 완료!")

# 2. 베이스라인 100개 대기업 지배구조 네트워크 적재
print("\n📥 2단계: 베이스라인 100대 기업 지배구조 네트워크 적재 실행...")
subprocess.run([sys.executable, "내작업폴더/00_DART_Trace_100개_확장_대규모_지식그래프_적재.py"], check=True)

# 3. 전체 3,988개 상장사 마스터 적재
print("\n📥 3단계: 대한민국 3,988개 전체 상장사 마스터 적재 실행...")
subprocess.run([sys.executable, "내작업폴더/00_DART_전체상장사_마스터_다운로더_및_지식그래프적재.py"], check=True)

# 4. v0.2 Step 1 공시 인덱스 수집기 실행 (1차 파일럿 100개사)
print("\n📥 4단계: v0.2 Step 1 DS001 공시 인덱스 수집기 실행...")
subprocess.run([sys.executable, "내작업폴더/01_DART_Disclosure_공시인덱스_수집기.py"], check=True)

# 5. v0.2 Step 2 지분공시 및 타법인출자 통합 파이프라인 실행 (1차 파일럿 100개사)
print("\n📥 5단계: v0.2 Step 2 DS004 지분공시 + DS002 타법인출자 통합 파이프라인 실행...")
subprocess.run([sys.executable, "내작업폴더/02_DART_P1_지분공시_및_타법인출자_통합파이프라인.py"], check=True)

# 6. 재적재 결과 집계
with driver.session() as s:
    comp_cnt = s.run("MATCH (c:DART_Company) RETURN count(c) AS c").single()['c']
    disc_cnt = s.run("MATCH (d:DART_Disclosure) RETURN count(d) AS c").single()['c']
    owns_cnt = s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()['c']
    inv_cnt = s.run("MATCH ()-[r:INVESTED_IN]->() RETURN count(r) AS c").single()['c']
    non_dart = s.run("MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS c").single()['c']

print("\n================================================================================")
print("📊 [DART-Trace] 100개사 파일럿 재적재(Rebuild) 완료 현황")
print(f"   • 상장사 노드 (:DART_Company): {comp_cnt:,}개")
print(f"   • 공시 인덱스 노드 (:DART_Disclosure): {disc_cnt:,}건")
print(f"   • 지분 소유 관계 (:OWNS_STAKE): {owns_cnt:,}건")
print(f"   • 타법인 출자 관계 (:INVESTED_IN): {inv_cnt:,}건")
print(f"   • 비-DART 노드 잔여: {non_dart}개")
print("================================================================================")
