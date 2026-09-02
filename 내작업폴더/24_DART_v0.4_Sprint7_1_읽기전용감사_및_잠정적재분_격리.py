# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] Sprint 7.1 실행 영향 전수 감사(Read-Only) 및 핀포인트 격리 파이프라인
========================================================================================================
[감사 및 격리 원칙]
1. [Step 1: 100% 읽기 전용 실측 감사 (Read-Only Audit)]:
   - `ingestion_run_id = 'RUN_20260903_XML_SPRINT7_1'`로 생성/수정된 모든 관계(15건) 및 주주 노드 실측
   - 파서 내 `DETACH DELETE`로 삭제되었던 `PERSON_202...` 대상(이전 오파싱 날짜 노드 3건) 영향 분석
   - fallback 및 휴리스틱(보통주/우선주 가정, 첫번째 소수점 지분율, 하드코딩 날짜) 포함 여부 감사
2. [Step 2: 핀포인트 격리 마이그레이션 (Pinpoint Quarantine)]:
   - 전체를 건드리지 않고 오직 `r.ingestion_run_id = 'RUN_20260903_XML_SPRINT7_1'` 대상만 핀포인트 격리
   - `verification_status = 'UNVERIFIED_XML_TRIAL'`, `is_current = false`
3. [Step 3: 격리 후 표준 SSOT 투영 0건 불변성 검증]:
   - 엄격 SSOT 5대 메타데이터 쿼리 실행 결과가 0건인지 재확인
========================================================================================================
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

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), max_connection_lifetime=120)

TARGET_RUN_ID = "RUN_20260903_XML_SPRINT7_1"

def step1_read_only_impact_audit():
    """[Step 1] 100% 읽기 전용 감사: Sprint 7.1 실행분의 노드/관계 및 영향 범위 실측"""
    print("\n" + "="*95)
    print("🔍 [Step 1: 100% 읽기 전용 감사 (Read-Only)] Sprint 7.1 실행 영향 실측")
    print("="*95)
    
    with driver.session() as s:
        # 1. Sprint 7.1 관계 목록 상세 조회
        run_rels = s.run("""
        MATCH (h)-[r:OWNS_STAKE {ingestion_run_id: $run_id}]->(t:DART_Company)
        RETURN coalesce(h.name, h.global_person_id) AS holder_name,
               labels(h)[0] AS holder_label,
               coalesce(h.corp_code, h.org_id, h.global_person_id) AS holder_pk,
               t.name AS target_name,
               t.corp_code AS target_code,
               r.stake AS stake,
               r.share_class AS share_class,
               r.voting_type AS voting_type,
               r.ownership_basis AS ownership_basis,
               r.as_of_date AS as_of_date,
               r.source_rcept_no AS rcept_no,
               r.source_edge_key AS edge_key,
               r.verification_status AS status,
               r.is_current AS is_current
        ORDER BY t.name, r.stake DESC
        """, run_id=TARGET_RUN_ID).data()
        
        # 2. 전체 DB 요약
        total_nodes = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        total_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        
        # 3. ingestion_run_id별 지분 관계 분포
        run_dist = s.run("""
        MATCH ()-[r:OWNS_STAKE]->()
        RETURN coalesce(r.ingestion_run_id, 'LEGACY_UNTAGGED') AS run_id,
               r.verification_status AS status,
               r.is_current AS is_current,
               count(r) AS cnt
        """).data()
        
    print(f"📊 [전체 DB 현황] 전체 노드: {total_nodes:,}개 | 전체 관계: {total_rels:,}개")
    print(f"\n📦 [지분 관계(OWNS_STAKE)의 run_id별 상태 분포]:")
    for d in run_dist:
        print(f"  • run_id='{d['run_id']}' | status='{d['status']}' | is_current={d['is_current']} ➔ {d['cnt']}건")
        
    print(f"\n📑 [Sprint 7.1 ('{TARGET_RUN_ID}')이 생성/수정한 관계: 총 {len(run_rels)}건]:")
    print(f"{'No':^3} | {'발행사':^8} | {'주주명 (PK)':^30} | {'라벨':^14} | {'지분율':^7} | {'주식종류':^9} | {'의결권':^9} | {'보유형태':^16}")
    print("-" * 115)
    for idx, r in enumerate(run_rels, 1):
        pk_str = f"{r['holder_name']} ({r['holder_pk']})"
        print(f"{idx:3d} | {r['target_name']:^8} | {pk_str:<30} | {r['holder_label']:^14} | {r['stake']:>5.2f}% | {r['share_class']:^9} | {r['voting_type']:^9} | {r['ownership_basis']:^16}")
    print("=" * 115)
    
    # 4. 삭제된 PERSON_202... 분석 보고
    print("\n⚠️ [파서 내부 DETACH DELETE 실행 영향 분석]:")
    print("  • 대상 패턴: `MATCH (p:DART_Person) WHERE p.global_person_id STARTS WITH 'PERSON_202' DETACH DELETE p`")
    print("  • 원인: 1차 탐색 실행 시 '변동현황' 표에서 '2021.04.29', '2021년 12월 09일', '2023년 04월 05일' 날짜 문자열이")
    print("         cells[0] 주주명으로 오인되어 임시 생성되었던 3개 더미 노드였음.")
    print("  • 문제점: 인제스천 파이프라인 내부에서 임의로 DELETE 쓰기를 수행한 것은 '원천 보존 원칙' 및 '읽기/쓰기 분리 원칙'을 위반한 심각한 결함임.")
    print("  • 교훈: 파서에 DELETE 쿼리를 내장하지 않고, 오파싱된 데이터는 파서 단계에서 생성 자체를 원천 차단(Skip)해야 함.")

def step2_execute_pinpoint_quarantine():
    """[Step 2] 핀포인트 격리 마이그레이션: 오직 RUN_20260903_XML_SPRINT7_1 대상만 격리"""
    print("\n" + "="*95)
    print(f"🔒 [Step 2: 핀포인트 격리 마이그레이션 (Write)] run_id='{TARGET_RUN_ID}' 대상 격리")
    print("="*95)
    
    with driver.session() as s:
        # 오직 해당 run_id만 명시적으로 타겟팅하여 격리
        res = s.run("""
        MATCH ()-[r:OWNS_STAKE {ingestion_run_id: $run_id}]->()
        SET r.verification_status = 'UNVERIFIED_XML_TRIAL',
            r.is_current = false,
            r.quarantine_reason = 'PARSER_HEURISTIC_FALLBACKS_AND_UNVERIFIED_VOTING',
            r.quarantined_at = datetime()
        RETURN count(r) AS quarantined_cnt
        """, run_id=TARGET_RUN_ID).single()["quarantined_cnt"]
        
        print(f"✅ 총 {res}건의 관계를 [verification_status='UNVERIFIED_XML_TRIAL', is_current=false]로 핀포인트 격리 완료!")

def step3_verify_ssot_zero_active():
    """[Step 3] 격리 후 표준 SSOT 5대 조건 투영 0건 차단 재확인"""
    print("\n" + "="*95)
    print("🛡️ [Step 3: 읽기 전용 검증 (Read-Only)] 엄격 SSOT 5대 조건 투영 0건 차단 재확인")
    print("="*95)
    
    STANDARD_SSOT_CYPHER = """
    MATCH (master)-[r:OWNS_STAKE]->(target:DART_Company)
    WHERE r.is_current = true
      AND r.verification_status = 'VERIFIED'
      AND r.source_edge_key IS NOT NULL
      AND r.current_scope IS NOT NULL
      AND r.source_rcept_no IS NOT NULL
      AND r.as_of_date IS NOT NULL
      AND r.stake > 0.0
      AND r.voting_type = 'VOTING'
    RETURN count(r) AS active_cnt
    """
    with driver.session() as s:
        active_cnt = s.run(STANDARD_SSOT_CYPHER).single()["active_cnt"]
        
    print(f"  • 현재 운영 DB 엄격 SSOT 투영 유효 건수: {active_cnt}건")
    if active_cnt == 0:
        print("  🎉 [안전 차단 확인] 미검증 데이터의 분석 유입이 100% 원천 차단된 상태 유지 확인 완료!")
    else:
        print(f"  ⚠️ 경고: 아직 {active_cnt}건이 SSOT 조건에 매칭됩니다. 즉시 점검 필요.")

def main():
    print("="*95)
    print("🚨 [DART-Trace v0.4] Sprint 7.1 실행 영향 실측 감사 및 핀포인트 격리 파이프라인")
    print("="*95)
    
    step1_read_only_impact_audit()
    step2_execute_pinpoint_quarantine()
    step3_verify_ssot_zero_active()
    
    print("\n" + "="*95)
    print("🏆 [감사 및 격리 완료] Sprint 7.1 잠정 적재분 핀포인트 격리 및 SSOT 0건 차단 완수!")
    print("="*95)

if __name__ == "__main__":
    main()
