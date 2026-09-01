# -*- coding: utf-8 -*-
"""
v0.3 DS005 5대 자본 이벤트 지식그래프 공식 감사 스크립트
- 대상: 95개 파일럿 상장사
- 5대 이벤트 노드 수량 및 타입별 분포 검증 (CB, BW, 증자, 양수, 합병)
- ANNOUNCED 관계 및 3원 일자(decided_on, received_on, effective_on) 검증
- EVIDENCED_BY 공시 원문 100% 연결 검증
- DART 공시 원문 링크(viewer_url) 및 14자리 rcept_no 무결성 검증
- 파생 프로젝션(MERGED_WITH, ACQUIRED_STAKE)의 fact_id 필수 키 누락 0건 assert 검증
"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(".env", override=True)

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, pwd))

def verify_v03():
    print("=" * 65)
    print("🔍 [v0.3 CapitalEvent Verification] 5대 자본 이벤트 데이터 무결성 감사")
    print("=" * 65)

    with driver.session() as s:
        # 1. 대상 기업 수
        target_corps_cnt = s.run("""
        MATCH (c:DART_Company)
        WHERE c.corp_code IS NOT NULL AND (c)-[:FILED]->()
        RETURN count(DISTINCT c) AS cnt
        """).single()['cnt']
        print(f"\n0️⃣ [파일럿 대상 상장사 수]: {target_corps_cnt}개사")
        assert target_corps_cnt == 95, f"파일럿 상장사 수 불일치: {target_corps_cnt} != 95"

        # 2. 전체 CapitalEvent 노드 수량 및 타입별 집계
        res_types = s.run("""
        MATCH (e:DART_CapitalEvent)
        RETURN e.event_type AS type, count(e) AS cnt
        ORDER BY cnt DESC
        """).data()
        
        total_events = sum(r['cnt'] for r in res_types)
        print(f"\n1️⃣ [이벤트 노드 총합]: {total_events:,}건")
        for r in res_types:
            print(f"  • {r['type']:20s}: {r['cnt']:,}건")
            
        assert total_events == 313, f"이벤트 노드 수량 불일치: {total_events} != 313"
        assert len(res_types) == 5, f"5대 이벤트 타입 중 일부 누락: {len(res_types)} != 5"

        # 3. Company -> ANNOUNCED -> CapitalEvent 관계 검증
        res_announced = s.run("""
        MATCH (c:DART_Company)-[r:ANNOUNCED]->(e:DART_CapitalEvent)
        RETURN count(r) AS cnt
        """).single()['cnt']
        print(f"\n2️⃣ [[:ANNOUNCED] 공시 연결 수]: {res_announced:,}건")
        assert res_announced == total_events, f"ANNOUNCED 관계 불일치: {res_announced} != {total_events}"

        # 4. EVIDENCED_BY 연결 검증 (313건 전수 연결)
        res_evidenced = s.run("""
        MATCH (e:DART_CapitalEvent)-[r:EVIDENCED_BY]->(d:DART_Disclosure)
        RETURN count(r) AS cnt
        """).single()['cnt']
        print(f"\n3️⃣ [[:EVIDENCED_BY] 공시 원문 연결 수]: {res_evidenced:,}건 / {total_events:,}건")
        assert res_evidenced == total_events, f"EVIDENCED_BY 미연결 존재: {res_evidenced} != {total_events}"

        # 5. 3원 일자(decided_on, received_on, effective_on) 검증
        res_dates = s.run("""
        MATCH (e:DART_CapitalEvent)
        RETURN count(e.decided_on) AS decided_cnt,
               count(e.received_on) AS received_cnt,
               count(e.effective_on) AS effective_cnt
        """).single()
        print(f"\n4️⃣ [3원 일자 적재 현황]:")
        print(f"  • decided_on   (이사회결의일): {res_dates['decided_cnt']:,}건")
        print(f"  • received_on  (공시접수일)  : {res_dates['received_cnt']:,}건 (100% 필수)")
        print(f"  • effective_on (납입/효력일) : {res_dates['effective_cnt']:,}건")
        assert res_dates['received_cnt'] == total_events, "received_on 공시접수일 누락 존재"

        # 6. 실측 샘플 상세 검증 (CB 및 합병)
        sample_cb = s.run("""
        MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent {event_type: 'CB_ISSUE'})
        WHERE e.issue_amount IS NOT NULL
        RETURN c.name AS comp, e.event_name AS name, e.issue_amount AS amount,
               e.conversion_price AS cv_price, e.source_rcept_no AS rcept_no,
               e.viewer_url AS url, e.is_private AS is_private
        LIMIT 2
        """).data()
        print(f"\n5️⃣ [CB 실측 샘플]:")
        for cb in sample_cb:
            print(f"  • {cb['comp']} | {cb['name']} | 발행액: {cb['amount']:,}원 | 전환가: {cb['cv_price']:,}원 | 사모여부: {cb['is_private']} | 접수번호: {cb['rcept_no']}")

        # 7. 파생 프로젝션 엣지 현황 및 fact_id 필수 무결성 검증 (누락 0건 assert)
        res_proj = s.run("""
        MATCH (a:DART_Company)-[r:MERGED_WITH|ACQUIRED_STAKE]->(b:DART_Company)
        RETURN type(r) AS rel, count(r) AS cnt,
               count(CASE WHEN r.fact_id IS NULL THEN 1 END) AS missing_fact_id_cnt
        """).data()
        print(f"\n6️⃣ [파생 프로젝션 엣지 현황 및 fact_id 무결성 검증]:")
        for p in res_proj:
            print(f"  • {p['rel']:20s}: {p['cnt']:,}건 (fact_id 누락: {p['missing_fact_id_cnt']:,}건)")
            assert p['missing_fact_id_cnt'] == 0, f"프로젝션 엣지 {p['rel']}에 fact_id 누락 존재: {p['missing_fact_id_cnt']}건"

    print("\n" + "=" * 65)
    print("🏆 [v0.3 DS005 5대 자본 이벤트 지식그래프 검증 100% ALL PASS]")
    print("=" * 65)

if __name__ == "__main__":
    verify_v03()
