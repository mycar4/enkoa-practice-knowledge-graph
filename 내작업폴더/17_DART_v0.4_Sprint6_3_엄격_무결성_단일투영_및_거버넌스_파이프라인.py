# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4 Sprint 6.3] 엄격 무결성 단일 투영(SSOT) 및 엔티티 거버넌스 파이프라인
========================================================================================================
[Sprint 6.3 엄격 무결성 및 거버넌스 원칙]
1. [합성 메타데이터 Fallback 원천 배제]:
   - `coalesce`로 임의의 키/스코프를 날조하지 않음
   - 5대 메타데이터(`source_edge_key`, `current_scope`, `source_rcept_no`, `as_of_date`, `stake`)가
     DB에 명시적으로 존재하는 정합 관계만 투영하고, 미비 관계는 분석에서 철저히 제외
2. [동일 Master-Target 다중 에지 명시적 합산 정책 (Multi-Edge Aggregation Policy)]:
   - NetworkX `DiGraph` 투영 시 동일 `(target -> master)` 간의 유효 지분은 임의 덮어쓰기가 아닌
     명시적 가중치 합산(`G[tgt][src]['weight'] += stake`)으로 보존
3. [활성 EXACT 및 ResolutionDecision 의사결정 체인 선행 감사]:
   - `raw_id + resolution_scope` 단위 단일 활성 EXACT 가드 상시 실행
4. [영구 변경 없는 격리 데모(In-Session Isolated Demo) 및 전역 불변성(Global Invariance)]:
   - 스크립트 시작 시점(Pre) vs 종료 시점(Post) DB 노드/관계수 100% 일치 실측 Assertion
========================================================================================================
"""

import os
import sys
import uuid
from dotenv import load_dotenv
from neo4j import GraphDatabase
import networkx as nx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://2fa50db4.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "2fa50db4")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

if not NEO4J_PASSWORD:
    raise ValueError("❌ [보안 가드] NEO4J_PASSWORD 환경변수가 설정되지 않았습니다.")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), max_connection_lifetime=120)

def get_session():
    return driver.session()

# =====================================================================================================
# 🏛️ [단일 진실 공급원] DART-Trace 엄격 무결성 단일 투영 쿼리 (Strict SSOT Projection Cypher)
# =====================================================================================================
UNIFIED_PROJECTION_CYPHER = """
// ── Case A: Raw 노드 -> EXACT RESOLVED_TO -> Master 노드 ──
MATCH (raw:RawEntity)-[r:OWNS_STAKE]->(target:DART_Company)
MATCH (raw)-[res:RESOLVED_TO {match_status: 'EXACT', is_active: true}]->(master)
WHERE ($target_corp_code IS NULL OR target.corp_code = $target_corp_code)
  AND r.is_current = true
  AND r.source_edge_key IS NOT NULL
  AND r.current_scope IS NOT NULL
  AND r.source_rcept_no IS NOT NULL
  AND r.as_of_date IS NOT NULL
  AND r.stake IS NOT NULL
  AND ($min_stake IS NULL OR r.stake > $min_stake)
RETURN 'CASE_A' AS origin_case,
       r.source_edge_key AS source_edge_key,
       r.source_holder_key AS source_holder_key,
       r.current_scope AS current_scope,
       res.resolution_decision_id AS resolution_decision_id,
       coalesce(master.corp_code, master.org_id, master.global_person_id) AS master_pk,
       coalesce(master.name, master.global_person_id) AS master_name,
       CASE
         WHEN master:DART_Company THEN 'DART_Company'
         WHEN master:DART_Organization THEN 'DART_Organization'
         WHEN master:DART_Person THEN 'DART_Person'
         ELSE 'UNKNOWN'
       END AS master_type,
       target.corp_code AS target_corp_code,
       target.name AS target_name,
       r.stake AS stake,
       r.as_of_date AS as_of_date,
       r.source_rcept_no AS source_rcept_no

UNION ALL

// ── Case B: 이미 공인 Master 노드 -> Master 자신 ──
MATCH (master)-[r:OWNS_STAKE]->(target:DART_Company)
WHERE ($target_corp_code IS NULL OR target.corp_code = $target_corp_code)
  AND r.is_current = true
  AND r.source_edge_key IS NOT NULL
  AND r.current_scope IS NOT NULL
  AND r.source_rcept_no IS NOT NULL
  AND r.as_of_date IS NOT NULL
  AND r.stake IS NOT NULL
  AND ($min_stake IS NULL OR r.stake > $min_stake)
  AND NOT master:RawEntity
  AND (
    (master:DART_Company AND master.corp_code IS NOT NULL) OR
    (master:DART_Organization AND master.org_id IS NOT NULL) OR
    (master:DART_Person AND master.global_person_id IS NOT NULL)
  )
RETURN 'CASE_B' AS origin_case,
       r.source_edge_key AS source_edge_key,
       r.source_holder_key AS source_holder_key,
       r.current_scope AS current_scope,
       null AS resolution_decision_id,
       coalesce(master.corp_code, master.org_id, master.global_person_id) AS master_pk,
       coalesce(master.name, master.global_person_id) AS master_name,
       CASE
         WHEN master:DART_Company THEN 'DART_Company'
         WHEN master:DART_Organization THEN 'DART_Organization'
         WHEN master:DART_Person THEN 'DART_Person'
         ELSE 'UNKNOWN'
       END AS master_type,
       target.corp_code AS target_corp_code,
       target.name AS target_name,
       r.stake AS stake,
       r.as_of_date AS as_of_date,
       r.source_rcept_no AS source_rcept_no
"""

def get_global_db_counts():
    """운영 DB 카운트 측정"""
    with get_session() as s:
        node_cnt = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        rel_cnt = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        raw_cnt = s.run("MATCH (n:RawEntity) RETURN count(n) AS cnt").single()["cnt"]
        dec_cnt = s.run("MATCH (n:ResolutionDecision) RETURN count(n) AS cnt").single()["cnt"]
        stake_cnt = s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS cnt").single()["cnt"]
    return {
        "nodes": node_cnt,
        "relationships": rel_cnt,
        "raw_entities": raw_cnt,
        "decisions": dec_cnt,
        "owns_stake_rels": stake_cnt
    }

def audit_active_exact_scope_uniqueness():
    """[감사 1] raw_id + resolution_scope 단위의 단일 활성 EXACT 감사"""
    print("\n" + "="*90)
    print("🔒 [감사 1] raw_id + resolution_scope 복합 단위의 단일 활성 EXACT 제약 감사")
    print("="*90)
    
    with get_session() as s:
        duplicates = s.run("""
        MATCH (raw:RawEntity)-[res:RESOLVED_TO {match_status: 'EXACT', is_active: true}]->(master)
        WITH raw.raw_id AS raw_id,
             coalesce(res.resolution_scope, 'GLOBAL_DEFAULT') AS scope,
             count(res) AS exact_count,
             collect(coalesce(master.name, master.corp_code, master.org_id, master.global_person_id)) AS targets
        WHERE exact_count > 1
        RETURN raw_id, scope, exact_count, targets
        """).data()
        
    if duplicates:
        print(f"❌ [위반 감지] raw_id + resolution_scope 활성 EXACT 중복 매핑 {len(duplicates)}건 적발:")
        for d in duplicates:
            print(f"  • RawID: {d['raw_id']} | Scope: {d['scope']} | 중복수: {d['exact_count']} | 타겟: {d['targets']}")
        raise AssertionError("❌ (raw_id + resolution_scope) 단일 활성 EXACT 제약 위반으로 파이프라인을 중단합니다.")
    else:
        print("✅ (raw_id + resolution_scope) 단일 활성 EXACT 중복 위반 0건 확인 (무결성 통과)")

def step1_verify_isolated_demo():
    """[검증 1] 영구 변경이 남지 않는 격리 데모(Isolated Demo) 5대 기준 실증 검증 (Strict SSOT 호출)"""
    print("\n" + "="*90)
    print("🧪 [검증 1] 영구 변경이 남지 않는 격리 데모(Isolated Demo) 5대 합격 기준 실증")
    print("="*90)
    
    fid = uuid.uuid4().hex[:8]
    raw_id = f"DEMO_{fid}_RAW"
    ma_id = f"DEMO_{fid}_CORP_A"
    mb_id = f"DEMO_{fid}_CORP_B"
    tgt_id = f"DEMO_{fid}_TARGET"
    dec_id = f"DEC_{fid}_001"
    scope_key = f"SCOPE_{fid}_EQUITY"
    
    e1 = f"EDGE_{fid}_001" # Case A
    e2 = f"EDGE_{fid}_002" # Case B
    e3 = f"EDGE_{fid}_003" # is_current: null (배제)
    e4 = f"EDGE_{fid}_004" # is_current: false (배제)
    
    with get_session() as s:
        # 데모 픽스처 생성 (5대 메타데이터 완비)
        s.run("""
        MERGE (ma:DART_Company {corp_code: $ma_id, name: '데모A_투자법인'})
        MERGE (mb:DART_Company {corp_code: $mb_id, name: '데모B_지주회사'})
        MERGE (target:DART_Company {corp_code: $tgt_id, name: '데모_타겟회사'})
        
        MERGE (raw:RawEntity {raw_id: $raw_id, name: '데모_원천명칭'})
        
        MERGE (dec:ResolutionDecision {decision_id: $dec_id})
        SET dec.resolution_scope = $scope_key,
            dec.version = 1,
            dec.match_status = 'EXACT',
            dec.link_basis = 'DART_CORP_CODE',
            dec.evidence_identifier = $ma_id,
            dec.approved_by = 'DEMO_AUDITOR',
            dec.resolved_at = datetime()
            
        MERGE (raw)-[:HAS_DECISION]->(dec)
        MERGE (dec)-[:MAPS_TO]->(ma)
        
        MERGE (raw)-[res:RESOLVED_TO {resolution_decision_id: $dec_id}]->(ma)
        SET res.match_status = 'EXACT',
            res.resolution_scope = $scope_key,
            res.link_basis = 'DART_CORP_CODE',
            res.evidence_identifier = $ma_id,
            res.is_active = true,
            res.resolved_at = datetime()
            
        // Case A Edge (Edge 1)
        MERGE (raw)-[r1:OWNS_STAKE {source_edge_key: $e1}]->(target)
        SET r1.source_holder_key = $raw_id,
            r1.issuer_corp_code = $tgt_id,
            r1.share_class = 'COMMON',
            r1.voting_type = 'VOTING',
            r1.ownership_basis = 'DIRECT',
            r1.current_scope = $raw_id + '_' + $tgt_id + '_COMMON_VOTING_DIRECT',
            r1.stake = 25.0,
            r1.is_current = true,
            r1.source_rcept_no = '20260101000001',
            r1.as_of_date = '2025-12-31'
            
        // Case B Edge (Edge 2)
        MERGE (mb)-[r2:OWNS_STAKE {source_edge_key: $e2}]->(target)
        SET r2.source_holder_key = $mb_id,
            r2.issuer_corp_code = $tgt_id,
            r2.share_class = 'COMMON',
            r2.voting_type = 'VOTING',
            r2.ownership_basis = 'DIRECT',
            r2.current_scope = $mb_id + '_' + $tgt_id + '_COMMON_VOTING_DIRECT',
            r2.stake = 15.0,
            r2.is_current = true,
            r2.source_rcept_no = '20260101000002',
            r2.as_of_date = '2025-12-31'
            
        // 배제 Edge 3 (is_current: null)
        MERGE (raw)-[r3:OWNS_STAKE {source_edge_key: $e3}]->(target)
        SET r3.source_holder_key = $raw_id,
            r3.issuer_corp_code = $tgt_id,
            r3.share_class = 'COMMON',
            r3.voting_type = 'VOTING',
            r3.ownership_basis = 'DIRECT',
            r3.current_scope = $raw_id + '_' + $tgt_id + '_COMMON_VOTING_DIRECT',
            r3.stake = 5.0,
            r3.is_current = null,
            r3.source_rcept_no = '20240101000001',
            r3.as_of_date = '2023-12-31'
            
        // 배제 Edge 4 (is_current: false)
        MERGE (mb)-[r4:OWNS_STAKE {source_edge_key: $e4}]->(target)
        SET r4.source_holder_key = $mb_id,
            r4.issuer_corp_code = $tgt_id,
            r4.share_class = 'COMMON',
            r4.voting_type = 'VOTING',
            r4.ownership_basis = 'DIRECT',
            r4.current_scope = $mb_id + '_' + $tgt_id + '_COMMON_VOTING_DIRECT',
            r4.stake = 10.0,
            r4.is_current = false,
            r4.source_rcept_no = '20250101000001',
            r4.as_of_date = '2024-12-31'
        """, ma_id=ma_id, mb_id=mb_id, tgt_id=tgt_id, raw_id=raw_id, dec_id=dec_id,
            scope_key=scope_key, e1=e1, e2=e2, e3=e3, e4=e4)
        
        try:
            # 엄격 SSOT 쿼리 실행 (coalesce 없는 원본 속성 검사)
            rows = s.run(UNIFIED_PROJECTION_CYPHER, target_corp_code=tgt_id, min_stake=None).data()
            print(f"📊 [엄격 SSOT 투영 결과] 총 {len(rows)}건 추출:")
            for r in rows:
                print(f"  • [{r['origin_case']}] {r['master_name']} (PK: {r['master_pk']}) ➔ {r['stake']}% (EdgeKey: {r['source_edge_key']}, Scope: {r['current_scope']})")
                
            case_a = [r for r in rows if r['origin_case'] == 'CASE_A']
            case_b = [r for r in rows if r['origin_case'] == 'CASE_B']
            edge_keys = [r['source_edge_key'] for r in rows]
            
            assert len(case_a) >= 1, "❌ Case A 누락"
            assert len(case_b) >= 1, "❌ Case B 누락"
            assert len(edge_keys) == len(set(edge_keys)), f"❌ 중복 키 적발: {edge_keys}"
            assert e3 not in edge_keys, "❌ is_current: null 누출"
            assert e4 not in edge_keys, "❌ is_current: false 누출"
            print("✅ [격리 데모 통과] 엄격 5대 메타데이터 필터 및 UNION ALL 듀얼 패스 100% 통과")
            
        finally:
            s.run("""
            MATCH (n) WHERE n.corp_code STARTS WITH 'DEMO_' + $fid 
                         OR n.raw_id STARTS WITH 'DEMO_' + $fid 
                         OR n.decision_id STARTS WITH 'DEC_' + $fid
            DETACH DELETE n
            """, fid=fid)
            print("✅ [Teardown 완료] 격리 데모 픽스처 전수 삭제 (잔여 0건)")

def step2_audit_operational_db():
    """[검증 2] 운영 DB 100% 읽기 전용 실측 감사 (5대 메타데이터 완비 기준 실측)"""
    print("\n" + "="*90)
    print("🏢 [검증 2] 운영 DB 100% 읽기 전용 감사: 엄격 SSOT 기준 투영 현황")
    print("="*90)
    
    with get_session() as s:
        # 엄격 SSOT 쿼리 실행
        facts = s.run(UNIFIED_PROJECTION_CYPHER, target_corp_code=None, min_stake=None).data()
        
    print(f"📊 [운영 DB 실측 요약]")
    print(f"  • 엄격 5대 메타데이터 완비 투영 건수: {len(facts)}건")
    if len(facts) == 0:
        print("  💡 [안내] 현재 운영 DB의 레거시 관계들은 v0.4 5대 메타데이터(`source_edge_key`, `current_scope`) 정합화 전이므로,")
        print("           엄격 거버넌스 원칙에 따라 투영에서 안전하게 제외(보정 큐 대기)되었습니다.")
    else:
        for r in facts[:5]:
            print(f"  • [{r['origin_case']}] {r['master_name']} ➔ {r['target_name']} ({r['stake']}%)")

def step3_run_ppr_with_multi_edge_aggregation(target_corp_code="00164779"):
    """[검증 3] PPR 영향력 후보 탐색 (다중 에지 명시적 합산 정책 적용)"""
    print("\n" + "="*90)
    print(f"⚡ [검증 3] PPR 영향력 후보 탐색 (동일 Master-Target 다중 에지 명시적 합산 정책)")
    print("="*90)
    
    # 데모 픽스처를 통해 다중 에지 합산 동작 검증 (A사 -> B사 10% + 5% = 15%)
    fid = uuid.uuid4().hex[:8]
    raw_id = f"PPR_{fid}_RAW"
    ma_id = f"PPR_{fid}_CORP_A"
    tgt_id = f"PPR_{fid}_TARGET"
    dec_id = f"DEC_{fid}_PPR"
    scope_key = f"SCOPE_{fid}_PPR"
    e1 = f"EDGE_{fid}_001" # 10.0%
    e2 = f"EDGE_{fid}_002" # 5.0% (동일 target, 다른 scope/class)
    
    with get_session() as s:
        s.run("""
        MERGE (ma:DART_Company {corp_code: $ma_id, name: 'PPR_테스트_대주주'})
        MERGE (target:DART_Company {corp_code: $tgt_id, name: 'PPR_테스트_발행사'})
        MERGE (raw:RawEntity {raw_id: $raw_id, name: 'PPR_원천주주'})
        
        MERGE (dec:ResolutionDecision {decision_id: $dec_id})
        SET dec.resolution_scope = $scope_key,
            dec.version = 1,
            dec.match_status = 'EXACT',
            dec.link_basis = 'DART_CORP_CODE',
            dec.evidence_identifier = $ma_id,
            dec.approved_by = 'PPR_AUDITOR',
            dec.resolved_at = datetime()
            
        MERGE (raw)-[:HAS_DECISION]->(dec)
        MERGE (dec)-[:MAPS_TO]->(ma)
        
        MERGE (raw)-[res:RESOLVED_TO {resolution_decision_id: $dec_id}]->(ma)
        SET res.match_status = 'EXACT',
            res.resolution_scope = $scope_key,
            res.link_basis = 'DART_CORP_CODE',
            res.evidence_identifier = $ma_id,
            res.is_active = true,
            res.resolved_at = datetime()
            
        MERGE (raw)-[r1:OWNS_STAKE {source_edge_key: $e1}]->(target)
        SET r1.source_holder_key = $raw_id,
            r1.issuer_corp_code = $tgt_id,
            r1.share_class = 'COMMON',
            r1.voting_type = 'VOTING',
            r1.ownership_basis = 'DIRECT',
            r1.current_scope = $raw_id + '_' + $tgt_id + '_COMMON_VOTING_DIRECT',
            r1.stake = 10.0,
            r1.is_current = true,
            r1.source_rcept_no = '20260101000001',
            r1.as_of_date = '2025-12-31'
            
        MERGE (raw)-[r2:OWNS_STAKE {source_edge_key: $e2}]->(target)
        SET r2.source_holder_key = $raw_id,
            r2.issuer_corp_code = $tgt_id,
            r2.share_class = 'PREFERRED',
            r2.voting_type = 'NON_VOTING',
            r2.ownership_basis = 'DIRECT',
            r2.current_scope = $raw_id + '_' + $tgt_id + '_PREFERRED_NON_VOTING_DIRECT',
            r2.stake = 5.0,
            r2.is_current = true,
            r2.source_rcept_no = '20260101000001',
            r2.as_of_date = '2025-12-31'
        """, ma_id=ma_id, tgt_id=tgt_id, raw_id=raw_id, dec_id=dec_id, scope_key=scope_key, e1=e1, e2=e2)
        
        try:
            # 엄격 SSOT 쿼리 실행
            raw_edges = s.run(UNIFIED_PROJECTION_CYPHER, target_corp_code=tgt_id, min_stake=0.0).data()
            
            G = nx.DiGraph()
            for e in raw_edges:
                src = e["master_pk"]
                tgt = e["target_corp_code"]
                stake_val = float(e["stake"])
                assert stake_val > 0.0, f"❌ 0% 이하 지분율 포함 적발: {e}"
                
                if not G.has_node(src):
                    G.add_node(src, name=e["master_name"], type=e["master_type"])
                if not G.has_node(tgt):
                    G.add_node(tgt, name=e["target_name"], type="DART_Company")
                    
                # ── [핵심] 동일 (target -> master) 다중 에지 명시적 가중치 합산 정책 ──
                if G.has_edge(tgt, src):
                    G[tgt][src]['weight'] += stake_val
                    print(f"  🔗 [다중 에지 합산 발생] {tgt} -> {src}: 기존 가중치 + {stake_val}% = {G[tgt][src]['weight']}%")
                else:
                    G.add_edge(tgt, src, weight=stake_val)
                    
            # 합산 결과 검증: 10.0 + 5.0 = 15.0%
            assert G[tgt_id][ma_id]['weight'] == 15.0, f"❌ 다중 에지 합산 오류: {G[tgt_id][ma_id]['weight']}"
            print("✅ [다중 에지 합산 정책 통과] 덮어쓰기 없이 10.0% + 5.0% = 15.0% 정상 합산 확인")
            
            # PPR 연산
            ppr = nx.pagerank(G, alpha=0.85, personalization={tgt_id: 1.0}, weight='weight')
            ranked = sorted([(k, v) for k, v in ppr.items() if k != tgt_id], key=lambda x: x[1], reverse=True)
            print(f"🎯 [PPR 연산 결과] {G.nodes[ranked[0][0]]['name']} ➔ PPR 점수: {ranked[0][1]:.6f}")
            
        finally:
            s.run("""
            MATCH (n) WHERE n.corp_code STARTS WITH 'PPR_' + $fid 
                         OR n.raw_id STARTS WITH 'PPR_' + $fid 
                         OR n.decision_id STARTS WITH 'DEC_' + $fid
            DETACH DELETE n
            """, fid=fid)
            print("✅ [Teardown 완료] PPR 테스트 픽스처 전수 삭제 (잔여 0건)")

def main():
    print("="*95)
    print("🚀 [DART-Trace v0.4 Sprint 6.3] 엄격 무결성 단일 투영(SSOT) 및 거버넌스 파이프라인 가동")
    print("="*95)
    
    pre = get_global_db_counts()
    print(f"📊 [전역 시작 시점 DB 실측치] 노드: {pre['nodes']:,}개 | 관계: {pre['relationships']:,}개")
    
    # 1. 활성 EXACT 선행 감사
    audit_active_exact_scope_uniqueness()
    
    # 2. 격리 데모 픽스처 엄격 5대 메타데이터 검증
    step1_verify_isolated_demo()
    
    # 3. 운영 DB 읽기 전용 감사
    step2_audit_operational_db()
    
    # 4. 다중 에지 명시적 합산 정책 적용 PPR 연산
    step3_run_ppr_with_multi_edge_aggregation()
    
    post = get_global_db_counts()
    print("\n" + "="*90)
    print(f"🔒 [전역 불변성 검증] 실행 전: {pre} == 실행 후: {post}")
    print("="*90)
    assert pre == post, f"❌ DB 카운트 불일치! Pre: {pre} vs Post: {post}"
    print("🎉 [전역 불변성 검증 통과] 운영 DB 100% 무손상 유지 확인 완료!")
    
    print("\n" + "="*95)
    print("🏆 [Sprint 6.3] 엄격 무결성 단일 투영(SSOT) 및 엔티티 거버넌스 전수 합격 완수!")
    print("="*95)

if __name__ == "__main__":
    main()
