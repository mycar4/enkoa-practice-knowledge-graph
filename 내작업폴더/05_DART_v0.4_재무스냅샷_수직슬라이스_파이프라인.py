# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4 Sprint 1] 재무 스냅샷 수직 슬라이스 & 6대 제약조건 실전 검증 파이프라인
========================================================================================
[엔터프라이즈 정합 및 안정성 강화 규격]
1. [6대 DDL] Aura 클라우드 6종 UNIQUE 제약조건 및 인덱스 배포
2. [선행 검증] DB 내 상장사 노드 사전 존재 여부 확인 (미존재 시 즉시 RuntimeError)
3. [원천 일자 파싱] OpenDART 응답의 thstrm_dt(결산일) 및 rcept_no(접수일)에서 정규식 동적 추출
4. [엄격 멱등성] 동일 입력 재실행 후 노드/관계 카운트 엄격 단일 인스턴스 검증 (AssertionError)
5. [사실 증거 질의] Cypher (:DART_Company)-[:HAS_FINANCIALS]->(:DART_FinancialSnapshot)-[:EVIDENCED_BY]->(:DART_Disclosure)
6. [UUID 동시성 격리 픽스처 & 자동 Teardown] 실행별 고유 UUID 기반 픽스처로 동시 실행 충돌 방지 및 100% 삭제
========================================================================================
"""

import os
import sys
import re
import json
import uuid
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://2fa50db4.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "2fa50db4")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")

if not DART_API_KEY:
    raise ValueError("❌ DART_API_KEY가 환경변수에 설정되어 있지 않습니다.")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def step1_apply_6_constraints():
    """[Step 1] 6종 UNIQUE 제약조건 및 성능 인덱스 DDL 배포"""
    print("\n" + "="*80)
    print("🔒 [Step 1] Neo4j Aura 클라우드에 6종 UNIQUE 제약조건 DDL 배포")
    print("="*80)
    
    ddls = [
        # 6종 UNIQUE Constraints
        "CREATE CONSTRAINT company_corp_code_unique IF NOT EXISTS FOR (c:DART_Company) REQUIRE c.corp_code IS UNIQUE",
        "CREATE CONSTRAINT person_global_id_unique IF NOT EXISTS FOR (p:DART_Person) REQUIRE p.global_person_id IS UNIQUE",
        "CREATE CONSTRAINT disclosure_rcept_no_unique IF NOT EXISTS FOR (d:DART_Disclosure) REQUIRE d.rcept_no IS UNIQUE",
        "CREATE CONSTRAINT capital_event_id_unique IF NOT EXISTS FOR (e:DART_CapitalEvent) REQUIRE e.event_id IS UNIQUE",
        "CREATE CONSTRAINT financial_snapshot_id_unique IF NOT EXISTS FOR (f:DART_FinancialSnapshot) REQUIRE f.snapshot_id IS UNIQUE",
        "CREATE CONSTRAINT securities_filing_id_unique IF NOT EXISTS FOR (s:DART_SecuritiesFiling) REQUIRE s.filing_id IS UNIQUE",
        
        # Performance Indexes
        "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:DART_Company) ON (c.name)",
        "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:DART_Person) ON (p.name)",
        "CREATE INDEX capital_event_type_idx IF NOT EXISTS FOR (e:DART_CapitalEvent) ON (e.event_type)",
        "CREATE INDEX financial_period_key_idx IF NOT EXISTS FOR (f:DART_FinancialSnapshot) ON (f.period_key)",
        "CREATE INDEX financial_as_of_date_idx IF NOT EXISTS FOR (f:DART_FinancialSnapshot) ON (f.as_of_date)"
    ]
    
    with driver.session() as s:
        for ddl in ddls:
            s.run(ddl)
            print(f"  ✅ DDL 안착 완료: {ddl.split('FOR')[0].strip()} FOR {ddl.split('FOR')[1].strip()}")
    print("🎉 6종 UNIQUE 제약조건 및 인덱스 100% 배포 완료!")

def step2_ingest_financial_snapshot(corp_code="00126380", bsns_year="2023", reprt_code="11011"):
    """[Step 2] OpenDART 실시간 재무제표 API 수집 및 지식그래프 동적 적재"""
    print("\n" + "="*80)
    print(f"📊 [Step 2] OpenDART DS003 실시간 재무제표 수집 (법인코드: {corp_code}, {bsns_year}년 사업보고서)")
    print("="*80)
    
    # 1. 선행 검증: 상장사 노드 DB 존재 확인 (Silent Failure 방지)
    with driver.session() as s:
        comp_record = s.run("""
        MATCH (c:DART_Company {corp_code: $corp_code})
        RETURN c.name AS name, c.stock_code AS stock_code
        """, corp_code=corp_code).single()
        
    if not comp_record:
        raise RuntimeError(f"❌ 상장사 노드 부재: corp_code='{corp_code}'가 DB에 존재하지 않습니다. 선행 마스터 적재가 필요합니다.")
        
    corp_name = comp_record["name"]
    stock_code = comp_record["stock_code"]
    print(f"🏢 선행 대상 상장사 식별 완료: {corp_name} (종목코드: {stock_code}, 법인코드: {corp_code})")
    
    # 2. OpenDART API 호출
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bsns_year={bsns_year}&reprt_code={reprt_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    status = data.get("status")
    message = data.get("message")
    
    if status != "000":
        raise RuntimeError(f"❌ OpenDART API 호출 실패: status={status}, message={message}")
        
    items = data.get("list", [])
    if not items:
        raise ValueError(f"❌ OpenDART 재무제표 데이터가 비어있습니다. (corp_code={corp_code}, bsns_year={bsns_year})")
        
    print(f"📦 OpenDART 원천 API 정상 수신 완료 (계정 항목 수: {len(items)}개)")
    
    # 연결재무제표(CFS) 우선 선택, 부재 시 개별(OFS)
    cfs_items = [x for x in items if x.get("fs_div") == "CFS"]
    fs_div = "CFS" if cfs_items else "OFS"
    target_items = cfs_items if cfs_items else items
    
    # 3. 원천 필드에서 결산일(as_of_date) 및 접수번호(rcept_no) 동적 파싱
    raw_thstrm_dt = target_items[0].get("thstrm_dt", "")
    date_match = re.search(r'(\d{4})[.\-/](\d{2})[.\-/](\d{2})', raw_thstrm_dt)
    if date_match:
        as_of_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    else:
        as_of_date = f"{bsns_year}-12-31" # 정규식 매칭 실패 시 안전 기본일자
        
    rcept_no = target_items[0].get("rcept_no")
    if not rcept_no:
        raise ValueError("❌ API 응답에서 공시접수번호(rcept_no)를 추출할 수 없습니다.")
    rcept_dt = rcept_no[:8] # OpenDART 14자리 표준 접수번호(rcept_no) 앞 8자리에서 접수일자(YYYYMMDD) 파생
    
    # 4. 계정명 엄격 매칭 함수 (정확 일치)
    def get_exact_amount(exact_names):
        for it in target_items:
            acc_name = it.get("account_nm", "").strip()
            if acc_name in exact_names:
                val_str = it.get("thstrm_amount", "0").replace(",", "").strip()
                try:
                    return int(val_str)
                except ValueError:
                    return 0
        return 0
    
    total_assets = get_exact_amount(["자산총계"])
    total_liabilities = get_exact_amount(["부채총계"])
    total_equity = get_exact_amount(["자본총계"])
    capital_stock = get_exact_amount(["자본금"])
    revenue = get_exact_amount(["매출액", "수익(매출액)"])
    operating_income = get_exact_amount(["영업이익", "영업이익(손실)"])
    net_income = get_exact_amount(["당기순이익", "당기순이익(손실)"])
    
    # 재무비율 계산 (0 또는 음수 분모 시 None 안전 처리)
    debt_ratio = round((total_liabilities / total_equity) * 100, 2) if total_equity > 0 else None
    capital_impairment_ratio = 0.0 if total_equity >= capital_stock else round(((capital_stock - total_equity) / capital_stock) * 100, 2)
    
    snapshot_id = f"{corp_code}_{as_of_date}_{reprt_code}_{fs_div}_{rcept_no}"
    period_key = f"{corp_code}_{as_of_date}_{reprt_code}_{fs_div}"
    
    print(f"📊 [원천 추출 일자] 결산 기준일(thstrm_dt): {as_of_date} | 접수번호 파생 접수일(rcept_no[:8]): {rcept_dt}")
    print(f"📊 [지표 실측값] 자산: {total_assets:,}원 | 부채: {total_liabilities:,}원 | 자본: {total_equity:,}원")
    print(f"📊 [비율 산출값] 부채비율: {debt_ratio}% | 자본잠식률: {capital_impairment_ratio}%")
    print(f"🔑 snapshot_id: {snapshot_id}")
    print(f"🔑 period_key : {period_key}")
    
    # 5. 동적 Cypher MERGE 적재 및 실행 요약 검증
    with driver.session() as s:
        result = s.run("""
        MATCH (comp:DART_Company {corp_code: $corp_code})
        
        MERGE (disc:DART_Disclosure {rcept_no: $rcept_no})
        ON CREATE SET disc.report_nm = '사업보고서 (' + substring($as_of_date, 0, 4) + '.12)',
                      disc.rcept_dt = $rcept_dt,
                      disc.flr_nm = comp.name,
                      disc.doc_status = 'NORMAL',
                      disc.is_latest = true
        
        MERGE (comp)-[:FILED]->(disc)
        
        MERGE (f:DART_FinancialSnapshot {snapshot_id: $snapshot_id})
        SET f.period_key = $period_key,
            f.corp_code = $corp_code,
            f.as_of_date = date($as_of_date),
            f.reprt_code = $reprt_code,
            f.fs_div = $fs_div,
            f.currency = 'KRW',
            f.unit = 'KRW',
            f.total_assets = $total_assets,
            f.total_liabilities = $total_liabilities,
            f.total_equity = $total_equity,
            f.capital_stock = $capital_stock,
            f.revenue = $revenue,
            f.operating_income = $operating_income,
            f.net_income = $net_income,
            f.debt_ratio = $debt_ratio,
            f.capital_impairment_ratio = $capital_impairment_ratio,
            f.is_latest = true,
            f.source_rcept_no = $rcept_no,
            f.formula_version = 'v1.0',
            f.updated_at = datetime()
            
        MERGE (comp)-[:HAS_FINANCIALS]->(f)
        MERGE (f)-[r:EVIDENCED_BY]->(disc)
        SET r.match_status = 'EXACT',
            r.link_basis = 'SAME_RCEPT_NO',
            r.verified_at = datetime()
        """, corp_code=corp_code, rcept_no=rcept_no, rcept_dt=rcept_dt, snapshot_id=snapshot_id,
           period_key=period_key, as_of_date=as_of_date, reprt_code=reprt_code, fs_div=fs_div,
           total_assets=total_assets, total_liabilities=total_liabilities, total_equity=total_equity,
           capital_stock=capital_stock, revenue=revenue, operating_income=operating_income,
           net_income=net_income, debt_ratio=debt_ratio, capital_impairment_ratio=capital_impairment_ratio)
           
        summary = result.consume()
        print(f"⚡ Cypher 실행 요약: 속성 설정 {summary.counters.properties_set}개, 노드 생성 {summary.counters.nodes_created}개, 관계 생성 {summary.counters.relationships_created}개")
           
    print("✅ 실제 재무 스냅샷 노드 및 공시 원문 증거 관계(:EVIDENCED_BY) 적재 완료!")
    return snapshot_id, period_key, rcept_no

def step3_verify_idempotency(snapshot_id):
    """[Step 3] 동일 입력 재실행 후 멱등성(중복 0건) 엄격 검증 (실패 시 AssertionError)"""
    print("\n" + "="*80)
    print("🔁 [Step 3] MERGE 멱등성(Idempotency) 엄격 검증 (단일 인스턴스 보장)")
    print("="*80)
    
    with driver.session() as s:
        cnt_res = s.run("""
        MATCH (f:DART_FinancialSnapshot {snapshot_id: $sid})
        RETURN count(f) AS node_count
        """, sid=snapshot_id).single()
        
        rel_res = s.run("""
        MATCH (f:DART_FinancialSnapshot {snapshot_id: $sid})-[r:EVIDENCED_BY]->(d:DART_Disclosure)
        RETURN count(r) AS rel_count
        """, sid=snapshot_id).single()
        
    node_count = cnt_res["node_count"]
    rel_count = rel_res["rel_count"]
    
    print(f"  • snapshot_id '{snapshot_id}' 노드 개수: {node_count}개")
    print(f"  • [:EVIDENCED_BY] 관계 개수: {rel_count}건")
    
    assert node_count == 1, f"❌ 멱등성 위반: 스냅샷 노드가 1개가 아닌 {node_count}개 존재합니다."
    assert rel_count == 1, f"❌ 멱등성 위반: 증거 관계가 1건이 아닌 {rel_count}건 존재합니다."
    
    print("🎉 [멱등성 검증 100% 통과] 다회 실행 시에도 완벽한 단일 인스턴스 불변 유지 확인!")

def step4_query_evidence_path(corp_code="00126380"):
    """[Step 4] Cypher 사실 증거 경로 질의 (실패 시 AssertionError)"""
    print("\n" + "="*80)
    print("🔍 [Step 4] Cypher 사실 증거 경로 역추적 질의")
    print("="*80)
    
    with driver.session() as s:
        records = s.run("""
        MATCH (c:DART_Company {corp_code: $corp_code})-[h:HAS_FINANCIALS]->(f:DART_FinancialSnapshot)-[e:EVIDENCED_BY]->(d:DART_Disclosure)
        WHERE f.is_latest = true
        RETURN c.name AS company_name,
               f.as_of_date AS as_of_date,
               f.total_assets AS assets,
               f.debt_ratio AS debt_ratio,
               f.is_latest AS is_latest,
               e.match_status AS match_status,
               e.link_basis AS link_basis,
               d.report_nm AS report_nm,
               d.rcept_no AS rcept_no
        """, corp_code=corp_code).data()
        
    assert len(records) > 0, f"❌ 증거 경로 조회 실패: {corp_code}에 대한 유효 경로가 0건입니다."
    
    for r in records:
        print(f"  🏢 상장사: {r['company_name']}")
        print(f"  📊 결산 기준일: {r['as_of_date']} | 자산총계: {r['assets']:,}원 | 부채비율: {r['debt_ratio']}%")
        print(f"  🔒 증거 속성: match_status={r['match_status']}, link_basis={r['link_basis']}")
        print(f"  📑 근거 공시 원문: [{r['rcept_no']}] {r['report_nm']}")
        print(f"  ✨ 최신 유효 여부(is_latest): {r['is_latest']}")
        
    print("🎉 사실 증거 경로 100% 정상 질의 확인 완료!")

def step5_verify_restatement_isolated_fixture():
    """[Step 5] 정정 공시(:RESTATES) 검증: 고유 UUID 격리 픽스처 테스트 후 자동 Teardown"""
    print("\n" + "="*80)
    print("🔄 [Step 5] 정정 공시(:RESTATES) 체인 고유 UUID 격리 픽스처 검증 & 자동 Teardown")
    print("="*80)
    
    # 🎯 동시성 충돌 방지를 위한 고유 UUID 프리픽스 생성
    run_uuid = uuid.uuid4().hex[:8]
    test_prefix = f"TEST_FIXTURE_{run_uuid}_"
    
    orig_test_rcept = f"{test_prefix}ORIG_001"
    corr_test_rcept = f"{test_prefix}CORR_002"
    
    orig_sid = f"{test_prefix}CORP_2023-12-31_11011_CFS_{orig_test_rcept}"
    corr_sid = f"{test_prefix}CORP_2023-12-31_11011_CFS_{corr_test_rcept}"
    period_key = f"{test_prefix}CORP_2023-12-31_11011_CFS"
    
    print(f"🔑 이번 실행 격리 UUID: {run_uuid} (프리픽스: {test_prefix})")
    
    try:
        with driver.session() as s:
            # 1. 원본 테스트 스냅샷 생성
            s.run("""
            CREATE (orig_d:DART_Disclosure {rcept_no: $orig_rcept, is_latest: true, doc_status: 'NORMAL'})
            CREATE (orig_f:DART_FinancialSnapshot {snapshot_id: $orig_sid, period_key: $period_key, is_latest: true})
            CREATE (orig_f)-[:EVIDENCED_BY {match_status: 'EXACT', link_basis: 'SAME_RCEPT_NO'}]->(orig_d)
            """, orig_rcept=orig_test_rcept, orig_sid=orig_sid, period_key=period_key)
            
            # 2. 정정 공시 접수 및 :RESTATES 불변 체인 전이
            s.run("""
            CREATE (corr_d:DART_Disclosure {rcept_no: $corr_rcept, is_latest: true, doc_status: 'CORRECTED', restatement_of: $orig_rcept})
            CREATE (corr_f:DART_FinancialSnapshot {snapshot_id: $corr_sid, period_key: $period_key, is_latest: true, restatement_of: $orig_sid})
            CREATE (corr_f)-[:EVIDENCED_BY {match_status: 'EXACT', link_basis: 'SAME_RCEPT_NO'}]->(corr_d)
            
            WITH corr_d, corr_f
            MATCH (orig_d:DART_Disclosure {rcept_no: $orig_rcept})
            MATCH (orig_f:DART_FinancialSnapshot {snapshot_id: $orig_sid})
            SET orig_d.is_latest = false,
                orig_f.is_latest = false
            CREATE (corr_d)-[:RESTATES {corrected_at: date('2024-04-15')}]->(orig_d)
            CREATE (corr_f)-[:RESTATES {corrected_at: date('2024-04-15')}]->(orig_f)
            """, orig_rcept=orig_test_rcept, corr_rcept=corr_test_rcept,
               orig_sid=orig_sid, corr_sid=corr_sid, period_key=period_key)
            
            # 3. 정정 체인 무결성 검증
            chain = s.run("""
            MATCH (corr_f:DART_FinancialSnapshot {snapshot_id: $corr_sid})-[r:RESTATES]->(orig_f:DART_FinancialSnapshot {snapshot_id: $orig_sid})
            RETURN corr_f.is_latest AS new_latest,
                   orig_f.is_latest AS old_latest,
                   r.corrected_at AS corrected_at
            """, corr_sid=corr_sid, orig_sid=orig_sid).single()
            
            assert chain is not None, "❌ 정정 체인(:RESTATES) 관계가 조회되지 않습니다."
            assert chain["new_latest"] is True, f"❌ 신규 정정본 is_latest=True 여야 합니다. (실제: {chain['new_latest']})"
            assert chain["old_latest"] is False, f"❌ 과거 원본 is_latest=False 여야 합니다. (실제: {chain['old_latest']})"
            
            print("  • 격리 픽스처 내 정정 체인(:RESTATES) 및 is_latest 플래그 전이 검증 완벽 일치!")
            print(f"     [신규 정정본: is_latest={chain['new_latest']}] ──[:RESTATES {chain['corrected_at']}]──> [과거 원본: is_latest={chain['old_latest']}]")
            
    finally:
        # 🧹 4. Teardown: 고유 UUID 픽스처만 100% 정밀 자동 삭제 (다른 동시 실행 픽스처 보존 및 운영 DB 무결성 100%)
        with driver.session() as s:
            s.run("""
            MATCH (d:DART_Disclosure) WHERE d.rcept_no STARTS WITH $prefix DETACH DELETE d
            """, prefix=test_prefix)
            s.run("""
            MATCH (f:DART_FinancialSnapshot) WHERE f.snapshot_id STARTS WITH $prefix DETACH DELETE f
            """, prefix=test_prefix)
        print(f"  🧹 [Teardown 완료] 고유 UUID 픽스처({run_uuid}) 정밀 삭제 완료 (운영 Aura DB 무결성 100% 보존).")

def main():
    print("="*90)
    print("🚀 [DART-Trace v0.4 Sprint 1] 엔터프라이즈 재무 스냅샷 수직 슬라이스 실전 검증 가동")
    print("="*90)
    
    # 1. 6종 제약조건 배포
    step1_apply_6_constraints()
    
    # 2. 1차 실시간 OpenDART API 수집 & 적재
    sid, pkey, rcp = step2_ingest_financial_snapshot()
    
    # 3. 2차 실시간 OpenDART API 수집 & 멱등성 엄격 검증 (Assertion)
    step2_ingest_financial_snapshot()
    step3_verify_idempotency(sid)
    
    # 4. Cypher 사실 증거 경로 역추적 검증
    step4_query_evidence_path()
    
    # 5. 정정 공시 UUID 격리 픽스처 검증 & 자동 Teardown
    step5_verify_restatement_isolated_fixture()
    
    print("\n" + "="*90)
    print("🏆 [DART-Trace v0.4 Sprint 1] 엔터프라이즈 정합 기준 5대 수직 슬라이스 전 항목 100% 검증 통과!")
    print("="*90)

if __name__ == "__main__":
    main()
