# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.3] OpenDART DS005 주요사항 5대 자본 이벤트 수집 & 지식그래프 적재 통합 파이프라인
==================================================================================================
[연동 5대 핵심 자본 이벤트 API]
1. cvbdIsDecsn.json           : 전환사채(CB) 발행결정 (사모/공모, 전환가액, 표면/만기이자율, 납입일)
2. bdwtIsDecsn.json           : 신주인수권부사채(BW) 발행결정 (행사가액, 사채총액, 납입일)
3. piicDecsn.json             : 유상증자결정 (신주발행가액, 증자방식, 시설/운영/타법인취득자금)
4. otcprStkInvscrAcqDecsn.json: 타법인 주식 및 출자증권 양수결정 (양수대상사, 양수금액, 대금지급일)
5. cmpMgDecsn.json            : 회사합병결정 (합병상대회사, 합병비율, 합병기일)
==================================================================================================
"""

import os
import sys
import re
import json
import time
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

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
DART_API_KEY = os.getenv("DART_API_KEY", "")

RAW_STORAGE_DIR = "내작업폴더/data/dart_raw_filings/capital_events"
os.makedirs(RAW_STORAGE_DIR, exist_ok=True)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def init_constraints():
    """v0.3 자본 이벤트 고유 제약조건 생성"""
    with driver.session() as s:
        s.run("""
        CREATE CONSTRAINT dart_capital_event_id_unique IF NOT EXISTS
        FOR (e:DART_CapitalEvent) REQUIRE e.event_id IS UNIQUE
        """)
        s.run("""
        CREATE INDEX dart_capital_event_type_idx IF NOT EXISTS
        FOR (e:DART_CapitalEvent) ON (e.event_type)
        """)
        s.run("""
        CREATE INDEX dart_capital_event_received_idx IF NOT EXISTS
        FOR (e:DART_CapitalEvent) ON (e.received_on)
        """)
    print("🔒 [v0.3 Schema] DART_CapitalEvent 고유 제약조건 및 색인 생성 완료.")

def normalize_date_str(val):
    """한글/슬래시/하이픈 일자 문자열을 YYYY-MM-DD로 정규화"""
    if not val or val in ['-', '해당사항없음', '']:
        return None
    val_clean = re.sub(r'[^\d]', '', str(val))
    if len(val_clean) == 8:
        return f"{val_clean[:4]}-{val_clean[4:6]}-{val_clean[6:8]}"
    return None

def parse_num(val, is_float=False):
    """금액/수치 문자열 정규화 (콤마 제거)"""
    if not val or val in ['-', '해당사항없음', '']:
        return None
    c_str = str(val).replace(',', '').strip()
    try:
        return float(c_str) if is_float else int(float(c_str))
    except:
        return None

def fetch_opendart_endpoint(endpoint_file: str, corp_code: str, bgn_de="20200101", end_de="20261231"):
    """OpenDART API 단일 엔드포인트 호출"""
    url = f"https://opendart.fss.or.kr/api/{endpoint_file}?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de={bgn_de}&end_de={end_de}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == '000' and data.get('list'):
                return data.get('list')
    except Exception as e:
        pass
    return []

def get_target_corps_from_db():
    """Neo4j에 등록된 상장사 corp_code 및 이름 목록 로드 (1차 파일럿 대상)"""
    with driver.session() as s:
        res = s.run("""
        MATCH (c:DART_Company)
        WHERE c.corp_code IS NOT NULL AND (c)-[:FILED]->()
        RETURN DISTINCT c.name AS name, c.corp_code AS corp_code
        ORDER BY c.name
        """)
        records = [r.data() for r in res]
        if not records:
            res = s.run("MATCH (c:DART_Company) WHERE c.corp_code IS NOT NULL RETURN c.name AS name, c.corp_code AS corp_code ORDER BY c.name")
            records = [r.data() for r in res]
        return records

def ingest_capital_events():
    """v0.3 5대 핵심 자본 이벤트 전수 수집 및 그래프 적재 파이프라인"""
    init_constraints()
    corps = get_target_corps_from_db()
    print(f"📊 [v0.3 Pipeline] 총 {len(corps)}개 대상 상장사의 DS005 5대 자본 이벤트 수집 시작...\n")

    endpoints = [
        ("CB_ISSUE", "cvbdIsDecsn.json", "전환사채발행결정"),
        ("BW_ISSUE", "bdwtIsDecsn.json", "신주인수권부사채발행결정"),
        ("PAID_INCREASE", "piicDecsn.json", "유상증자결정"),
        ("STOCK_ACQUISITION", "otcprStkInvscrInhDecsn.json", "타법인주식및출자증권양수결정"),
        ("MERGER", "cmpMgDecsn.json", "회사합병결정")
    ]

    total_stats = {ep[0]: 0 for ep in endpoints}
    total_projections = 0

    for idx, c in enumerate(corps, 1):
        corp_name = c['name']
        corp_code = c['corp_code']

        for event_type, ep_file, event_label in endpoints:
            items = fetch_opendart_endpoint(ep_file, corp_code)
            if not items:
                continue

            for seq, it in enumerate(items, 1):
                rcept_no = it.get('rcept_no', '').strip()
                if not rcept_no or len(rcept_no) < 14:
                    continue

                event_id = f"{corp_code}_{event_type}_{rcept_no}_{seq}"
                
                # 3원 일자 파싱
                decided_on = normalize_date_str(it.get('bddd'))
                received_on = f"{rcept_no[:4]}-{rcept_no[4:6]}-{rcept_no[6:8]}"
                
                effective_on = None
                if event_type in ['CB_ISSUE', 'BW_ISSUE', 'PAID_INCREASE']:
                    effective_on = normalize_date_str(it.get('pymd'))
                elif event_type == 'STOCK_ACQUISITION':
                    effective_on = normalize_date_str(it.get('py_dd'))
                elif event_type == 'MERGER':
                    effective_on = normalize_date_str(it.get('mgsc_mgdt'))

                # 주요 속성 추출
                issue_method = it.get('bdis_mthn') or it.get('ic_mth') or it.get('mg_mth') or '-'
                is_private = True if ('사모' in str(issue_method) or '제3자' in str(issue_method)) else False
                
                issue_amount = parse_num(it.get('bd_fta') or it.get('acq_amt') or it.get('rbsnfdtl_cpt'))
                conversion_price = parse_num(it.get('cv_prc') or it.get('ex_prc') or it.get('nstk_prc'))
                min_refixing_floor = parse_num(it.get('act_mktprcfl_cvprc_lwtrsprc'))
                
                target_corp_name = it.get('tgcmp_cmpnm') or it.get('mgptncmp_cmpnm') or None
                if target_corp_name:
                    target_corp_name = target_corp_name.replace('(주)', '').replace('주식회사', '').strip()

                merger_ratio = it.get('mg_rt')
                purpose = it.get('mg_pp') or it.get('acq_pp') or it.get('fdpp_op') or None

                # 로컬 원본 아카이빙
                json_path = os.path.join(RAW_STORAGE_DIR, f"{event_id}.json")
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(it, jf, ensure_ascii=False, indent=2)

                viewer_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

                # Neo4j 적재 트랜잭션
                with driver.session() as session:
                    session.run("""
                    MERGE (comp:DART_Company {corp_code: $corp_code})
                    ON CREATE SET comp.name = $corp_name
                    
                    MERGE (e:DART_CapitalEvent {event_id: $event_id})
                    SET e.event_type = $event_type,
                        e.event_name = $event_name,
                        e.corp_code = $corp_code,
                        e.corp_name = $corp_name,
                        e.source_rcept_no = $rcept_no,
                        e.viewer_url = $viewer_url,
                        e.issue_method = $issue_method,
                        e.is_private = $is_private,
                        e.issue_amount = $issue_amount,
                        e.conversion_price = $conversion_price,
                        e.min_refixing_floor = $min_refixing_floor,
                        e.target_corp_name = $target_corp_name,
                        e.merger_ratio = $merger_ratio,
                        e.purpose = $purpose,
                        e.updated_at = datetime()

                    WITH comp, e
                    FOREACH (_ IN CASE WHEN $decided_on IS NOT NULL THEN [1] ELSE [] END |
                        SET e.decided_on = date($decided_on)
                    )
                    FOREACH (_ IN CASE WHEN $received_on IS NOT NULL THEN [1] ELSE [] END |
                        SET e.received_on = date($received_on)
                    )
                    FOREACH (_ IN CASE WHEN $effective_on IS NOT NULL THEN [1] ELSE [] END |
                        SET e.effective_on = date($effective_on)
                    )

                    MERGE (comp)-[r1:ANNOUNCED]->(e)
                    SET r1.received_on = date($received_on)
                    WITH comp, e, r1
                    FOREACH (_ IN CASE WHEN $decided_on IS NOT NULL THEN [1] ELSE [] END |
                        SET r1.decided_on = date($decided_on)
                    )

                    WITH comp, e
                    MERGE (d:DART_Disclosure {rcept_no: $rcept_no})
                    ON CREATE SET d.report_nm = $event_name,
                                  d.rcept_dt = replace($received_on, '-', ''),
                                  d.received_on = date($received_on),
                                  d.viewer_url = $viewer_url,
                                  d.evidence_status = 'CAPITAL_EVENT_INDEXED'
                    MERGE (e)-[:EVIDENCED_BY]->(d)
                    """, {
                        'corp_code': corp_code,
                        'corp_name': corp_name,
                        'event_id': event_id,
                        'event_type': event_type,
                        'event_name': f"{corp_name} {event_label}",
                        'rcept_no': rcept_no,
                        'viewer_url': viewer_url,
                        'decided_on': decided_on,
                        'received_on': received_on,
                        'effective_on': effective_on,
                        'issue_method': issue_method,
                        'is_private': is_private,
                        'issue_amount': issue_amount,
                        'conversion_price': conversion_price,
                        'min_refixing_floor': min_refixing_floor,
                        'target_corp_name': target_corp_name,
                        'merger_ratio': merger_ratio,
                        'purpose': purpose
                    })

                    # 프로젝션 엣지 생성: 정확히 1건 매칭일 때만 관계 생성 (CONTAINS 자동 매칭 배제)
                    if target_corp_name and event_type == 'STOCK_ACQUISITION':
                        res_match = session.run("""
                        MATCH (a:DART_Company {corp_code: $corp_code})
                        WITH a
                        MATCH (b:DART_Company {name: $target_corp_name})
                        WITH a, collect(b) AS b_list
                        WHERE size(b_list) = 1
                        WITH a, b_list[0] AS b
                        MERGE (a)-[r:ACQUIRED_STAKE {derived_from_event_id: $event_id}]->(b)
                        SET r.fact_id = $event_id + '_ACQUIRED_STAKE_' + coalesce(b.corp_code, b.name),
                            r.source_rcept_no = $rcept_no,
                            r.amount = $issue_amount,
                            r.effective_on = date($effective_on),
                            r.projection_version = 'v0.3'
                        RETURN count(r) AS created_cnt
                        """, {
                            'corp_code': corp_code,
                            'target_corp_name': target_corp_name,
                            'event_id': event_id,
                            'rcept_no': rcept_no,
                            'issue_amount': issue_amount,
                            'effective_on': effective_on or received_on
                        }).single()
                        if res_match and res_match['created_cnt'] > 0:
                            total_projections += res_match['created_cnt']

                    elif target_corp_name and event_type == 'MERGER':
                        res_match = session.run("""
                        MATCH (a:DART_Company {corp_code: $corp_code})
                        WITH a
                        MATCH (b:DART_Company {name: $target_corp_name})
                        WITH a, collect(b) AS b_list
                        WHERE size(b_list) = 1
                        WITH a, b_list[0] AS b
                        MERGE (a)-[r:MERGED_WITH {derived_from_event_id: $event_id}]->(b)
                        SET r.fact_id = $event_id + '_MERGED_WITH_' + coalesce(b.corp_code, b.name),
                            r.source_rcept_no = $rcept_no,
                            r.merger_ratio = $merger_ratio,
                            r.effective_on = date($effective_on),
                            r.projection_version = 'v0.3'
                        RETURN count(r) AS created_cnt
                        """, {
                            'corp_code': corp_code,
                            'target_corp_name': target_corp_name,
                            'event_id': event_id,
                            'rcept_no': rcept_no,
                            'merger_ratio': merger_ratio,
                            'effective_on': effective_on or received_on
                        }).single()
                        if res_match and res_match['created_cnt'] > 0:
                            total_projections += res_match['created_cnt']

                total_stats[event_type] += 1

            time.sleep(0.05) # API Rate Limit 안정성 유지

        if idx % 10 == 0 or idx == len(corps):
            print(f"  [{idx}/{len(corps)}] {corp_name} 완료 (누적 이벤트: CB {total_stats['CB_ISSUE']}건, BW {total_stats['BW_ISSUE']}건, 증자 {total_stats['PAID_INCREASE']}건, 양수 {total_stats['STOCK_ACQUISITION']}건, 합병 {total_stats['MERGER']}건)")

    print("\n" + "=" * 60)
    print("🏆 [v0.3 DS005 5대 자본 이벤트 지식그래프 적재 완료 보고]")
    print("=" * 60)
    for k, v in total_stats.items():
        print(f"• {k:20s}: {v:,}건")
    print(f"• 총 CapitalEvent 노드: {sum(total_stats.values()):,}건")
    print(f"• 파생 프로젝션 엣지   : {total_projections:,}건")
    print("=" * 60)

if __name__ == "__main__":
    ingest_capital_events()
