#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 [DART-Trace] 파이썬 터미널 실전 시나리오 인터랙티브 테스트 러너 (실측 기반)
================================================================================
브라우저를 띄우지 않고도 터미널에서 직접 5대 실전 시나리오를 실행할 수 있습니다.
================================================================================
"""

import sys
from pathlib import Path
from neo4j import READ_ACCESS

# Windows stdout UTF-8 보장
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.graphrag_service import (
    get_neo4j_driver,
    generate_graphrag_response,
    search_vector_only,
    search_hybrid_rerank
)
from services.decision_report_service import DecisionReportService


def run_scenario_1():
    print("\n" + "=" * 80)
    print("🔥 [시나리오 1] 512차원 자본이벤트 GraphRAG AI 분석기 실전 질의")
    print("=" * 80)
    q = "HLB의 대규모 전환사채(CB) 발행 목적과 잠재적 희석(Overhang) 리스크는?"
    print(f"질문: '{q}'\n분석 중... (512차원 벡터 검색 + 70:30 하이브리드 리랭킹)")
    
    report = generate_graphrag_response(q, top_k=3)
    
    print("\n[리랭킹 상위 공시]")
    for i, h in enumerate(report["hits"], 1):
        print(f"  {i}. {h['corp_name']} - {h['event_type']} (조달규모: {h.get('scale_amount', 0):,}원 | 최종점수: {h.get('final_score', 0):.4f})")
    
    print("\n" + "-" * 80)
    print("📄 [AI 4-Tier 의사결정 리포트]")
    print("-" * 80)
    print(f"### 1. 사실 (Fact)\n{report['fact']}\n")
    print(f"### 2. 해석 (Interpretation)\n{report['interpretation']}\n")
    print(f"### 3. 원문 근거 (Evidence)\n{report['evidence']}\n")
    print(f"### 4. 다음 확인 항목 (Next Action)\n{report['next_action']}\n")


def run_scenario_2():
    print("\n" + "=" * 80)
    print("🔍 [시나리오 2] Evidence Inspector: DART 15,000건 공시 2D XPath & 실측 지분율")
    print("=" * 80)
    driver = get_neo4j_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        # 1) 케이피티유 -> 알루코 승격 지분 실측 조회
        stake_res = session.run("""
        MATCH (h:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
        WHERE h.name CONTAINS '케이피티유' OR t.name CONTAINS '알루코'
        RETURN h.name AS holder,
               t.name AS target,
               r.stake_ratio AS ratio,
               r.shares_count AS shares,
               r.rcept_no AS rcept_no,
               r.reporting_obligation_date AS report_date
        LIMIT 1
        """)
        rec = stake_res.single()
        if rec:
            print(f"[실측 승격 지분] {rec['holder']} ➔ {rec['target']}:")
            print(f"  - 지분율: {rec['ratio']}%")
            print(f"  - 보유주식수: {rec['shares']:,}주")
            print(f"  - 보고의무발생일: {rec['report_date']} (접수번호: {rec['rcept_no']})")

        # 2) 2D XPath 원문 증거 조각 확인
        frag_res = session.run("""
        MATCH (cand:RawEvidenceCandidate)-[:EVIDENCED_BY]->(frag:EvidenceFragment)
        WHERE cand.holder_name CONTAINS '알루코' OR cand.holder_name CONTAINS '케이피티유'
        RETURN cand.holder_name AS holder_name,
               cand.rcept_no AS rcept_no,
               frag.xpath AS xpath,
               frag.extracted_value AS extracted_value,
               frag.raw_inner_hash AS row_hash
        LIMIT 2
        """)
        frags = [dict(r) for r in frag_res]
        if frags:
            print("\n[원문 2D XML XPath 증거 조각]:")
            for i, f in enumerate(frags, 1):
                hash_val = str(f.get('row_hash') or '')[:16]
                print(f"  [{i}] 주주명: {f['holder_name']} | DART 접수번호: {f['rcept_no']}")
                print(f"      표 좌표(XPath): {f['xpath']}")
                print(f"      추출 값: '{f['extracted_value']}' | 행 해시: {hash_val}...")


def run_scenario_3():
    print("\n" + "=" * 80)
    print("📊 [시나리오 3] 알루코 4단 의사결정 리포트 (XBRL 재무 팩트 및 타임라인)")
    print("=" * 80)
    service = DecisionReportService()
    try:
        report = service.generate_company_decision_report("알루코")
        t1 = report.get("tier1_facts", {})
        fin = t1.get("financial_facts", {})
        tl = t1.get("official_timeline", [])
        
        target = report.get("target_company", {})
        print(f"대상 기업: {target.get('corp_name', '알루코')} (종목코드: {target.get('stock_code', '-')})")
        if fin.get("status") == "AVAILABLE":
            print(f"[OpenDART XBRL 재무제표 팩트 ({fin.get('bsns_year')}년 {fin.get('reprt_name')} - {fin.get('fs_div_name')})]:")
            print(f"  - 자산총계: {fin.get('total_assets', 0):,}원")
            print(f"  - 부채총계: {fin.get('total_liabilities', 0):,}원")
            print(f"  - 자본총계: {fin.get('total_equity', 0):,}원")
            print(f"  - 매출액: {fin.get('revenue', 0):,}원")
            print(f"  - 영업이익: {fin.get('operating_income', 0):,}원")
        
        print(f"\n[통합 공식 채널 피드 (총 {len(tl)}건 중 상위 3건)]:")
        for item in tl[:3]:
            print(f"  • [{item.get('event_date')}] [{item.get('channel_grade')}] {item.get('title')} (접수번호: {item.get('rcept_no')})")
    finally:
        service.close()


def run_scenario_4():
    print("\n" + "=" * 80)
    print("🕸️ [시나리오 4] 현대자동차 그룹 계열사 지배구조 탐색")
    print("=" * 80)
    driver = get_neo4j_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        res = session.run("""
        MATCH (c:DART_Company)
        WHERE c.name CONTAINS '현대'
        RETURN c.name AS corp_name, c.stock_code AS stock_code
        LIMIT 5
        """)
        records = [dict(r) for r in res]
        print("현대 계열사 마스터 노드 탐색 결과:")
        for r in records:
            print(f"  - {r['corp_name']} (종목코드: {r.get('stock_code', '-')})")


def run_scenario_5():
    print("\n" + "=" * 80)
    print("⚡ [시나리오 5] 자본이벤트(BW_ISSUE / MERGER) 3원 일자 실측 필터링")
    print("=" * 80)
    driver = get_neo4j_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        res = session.run("""
        MATCH (e:DART_CapitalEvent)
        WHERE e.event_type IN ['BW_ISSUE', 'MERGER']
        RETURN e.corp_name AS corp_name,
               e.event_type AS event_type,
               e.decided_on AS decided_on,
               e.received_on AS received_on,
               e.effective_on AS effective_on,
               e.scale_amount AS scale_amount
        ORDER BY e.scale_amount DESC
        LIMIT 3
        """)
        records = [dict(r) for r in res]
        print(f"조달 규모 상위 BW/합병 공시 (3원 일자 분리 실측):")
        for i, r in enumerate(records, 1):
            print(f"  [{i}] {r['corp_name']} - {r['event_type']} (규모: {r.get('scale_amount', 0):,}원)")
            print(f"      결정일(decided): {r.get('decided_on')} | 접수일(received): {r.get('received_on')} | 효력일(effective): {r.get('effective_on')}")


if __name__ == "__main__":
    print("=" * 80)
    print("🌟 DART-Trace 실전 시나리오 파이썬 콘솔 러너 (실측 기반)")
    print("1: 시나리오 1 (자본이벤트 512차원 GraphRAG 4단 리포트)")
    print("2: 시나리오 2 (15,000건 공시 2D XPath & 실측 지분율 19.21%)")
    print("3: 시나리오 3 (알루코 재무제표 팩트 & 공식 타임라인)")
    print("4: 시나리오 4 (현대 계열사 지배구조 탐색)")
    print("5: 시나리오 5 (자본이벤트 3원 일자 필터링)")
    print("all: 전체 시나리오 1~5 일괄 실행")
    print("=" * 80)
    
    choice = sys.argv[1] if len(sys.argv) > 1 else "2"
        
    if choice == "1":
        run_scenario_1()
    elif choice == "2":
        run_scenario_2()
    elif choice == "3":
        run_scenario_3()
    elif choice == "4":
        run_scenario_4()
    elif choice == "5":
        run_scenario_5()
    elif choice == "all":
        run_scenario_2()
        run_scenario_3()
        run_scenario_4()
        run_scenario_5()
        run_scenario_1()
    else:
        run_scenario_2()
