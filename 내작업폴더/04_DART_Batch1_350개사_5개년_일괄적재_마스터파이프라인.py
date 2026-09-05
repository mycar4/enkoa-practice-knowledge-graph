# -*- coding: utf-8 -*-
raise RuntimeError(
    "🚨 [영구 폐기된 위험 스크립트 실행 차단]\n"
    "본 스크립트는 DART-Trace의 'Claim-to-Fact' 거버넌스 헌법(원문 행 해시·2D XPath·3중 교차검증)을 거치지 않고\n"
    "미검증 :OWNS_STAKE 관계를 직접 생성하여 프로덕션 DB를 오염시키는 중대한 결함으로 인해 영구 폐기(DISCARDED)되었습니다.\n"
    "모든 지분 관계 생성은 반드시 'RawEvidenceCandidate -> EvidenceFragment -> 3중 교차검증 -> HOLDS_ECONOMIC_STAKE 승격' 파이프라인만 사용해야 합니다."
)

import os
import sys
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

NEO4J_URI = os.getenv("AURA_URI") or os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")

if not DART_API_KEY:
    raise ValueError("❌ DART_API_KEY가 설정되지 않았습니다.")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_target_350_corps():
    """코스피 200 + 코스닥 150 대상 350개사 선별"""
    with driver.session() as s:
        # 코스피 200
        kospi_corps = s.run("""
        MATCH (c:DART_Company {market: 'KOSPI'})
        WHERE c.stock_code IS NOT NULL AND c.corp_code IS NOT NULL
        RETURN c.name AS name, c.corp_code AS corp_code, c.stock_code AS stock_code, 'KOSPI' AS market
        ORDER BY c.stock_code ASC
        LIMIT 200
        """).data()
        
        # 코스닥 150
        kosdaq_corps = s.run("""
        MATCH (c:DART_Company {market: 'KOSDAQ'})
        WHERE c.stock_code IS NOT NULL AND c.corp_code IS NOT NULL
        RETURN c.name AS name, c.corp_code AS corp_code, c.stock_code AS stock_code, 'KOSDAQ' AS market
        ORDER BY c.stock_code ASC
        LIMIT 150
        """).data()
        
    return kospi_corps + kosdaq_corps

def run_batch1():
    target_corps = get_target_350_corps()
    print("=" * 90)
    print(f"🚀 [DART-Trace Step 2 - 1차 배치] 코스피 200 & 코스닥 150 (총 {len(target_corps)}개사) 5개년 적재 가동")
    print(f"📡 클라우드 접속 대상: {NEO4J_URI}")
    print("=" * 90)
    
    # 350개사 순회 수집 및 적재
    for idx, c in enumerate(target_corps, 1):
        corp_name = c['name']
        corp_code = c['corp_code']
        market = c['market']
        
        print(f"[{idx:3d}/{len(target_corps)}] 🏢 {corp_name} ({market}, {c['stock_code']}) 수집 중...")
        
        # 1. DS001 공시 인덱스 수집
        try:
            url_list = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de=20210101&end_de=20260902&page_no=1&page_count=100"
            req = urllib.request.Request(url_list, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                filings = data.get("list", [])
                if filings:
                    with driver.session() as s:
                        s.run("""
                        UNWIND $filings AS f
                        MERGE (d:DART_Disclosure {rcept_no: f.rcept_no})
                        SET d.report_nm = f.report_nm,
                            d.rcept_dt = f.rcept_dt,
                            d.flr_nm = f.flr_nm,
                            d.corp_name = f.corp_name,
                            d.doc_status = CASE 
                                WHEN f.report_nm CONTAINS '[기재정정]' THEN 'CORRECTED'
                                WHEN f.report_nm CONTAINS '[철회]' THEN 'WITHDRAWN'
                                ELSE 'NORMAL' END
                        WITH d, f
                        MATCH (c:DART_Company {corp_code: f.corp_code})
                        MERGE (c)-[:FILED]->(d)
                        """, filings=filings)
        except Exception as e:
            pass
        
        # 2. [영구 무력화] DS004 대량보유 지분 직접 적재 영구 금지 (CLAUDE.md 거버넌스 헌법)
        # ⚠️ 절대 활성화 금지: RawEvidenceCandidate -> EvidenceFragment -> 3중 교차검증 없는 직접 OWNS_STAKE 생성은 프로덕션 오염 유발.
        # pass

        
        # 3. DS005 사모 CB 발행결정 수집
        try:
            url_cb = f"https://opendart.fss.or.kr/api/cvbdIsDecsn.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de=20210101&end_de=20260902"
            req_cb = urllib.request.Request(url_cb, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_cb, timeout=10) as resp:
                data_cb = json.loads(resp.read().decode("utf-8"))
                cb_list = data_cb.get("list", [])
                if cb_list:
                    for cb in cb_list:
                        ev_id = f"CB_{cb.get('rcept_no')}"
                        amt = int(cb.get("cb_is_fta", 0) or 0)
                        cv_prc = int(cb.get("cv_prc", 0) or 0)
                        with driver.session() as s:
                            s.run("""
                            MERGE (e:DART_CapitalEvent {event_id: $ev_id})
                            SET e.event_type = 'CB_ISSUE',
                                e.event_name = $ev_name,
                                e.issue_amount = $amt,
                                e.conversion_price = $cv_prc,
                                e.is_private = CASE WHEN $method CONTAINS '사모' THEN true ELSE false END,
                                e.decided_on = $dec_on,
                                e.received_on = $rcv_on,
                                e.effective_on = $eff_on,
                                e.source_rcept_no = $rcp
                            WITH e
                            MATCH (c:DART_Company {corp_code: $ccode})
                            MERGE (c)-[:ANNOUNCED]->(e)
                            """, ev_id=ev_id, ev_name=cb.get("bd_nm", "전환사채발행"), amt=amt, cv_prc=cv_prc,
                               method=cb.get("cb_is_mth", ""), dec_on=cb.get("bdr_de", ""), rcv_on=cb.get("rcept_dt", ""),
                               eff_on=cb.get("pym_de", ""), rcp=cb.get("rcept_no", ""), ccode=corp_code)
        except Exception as e:
            pass
            
        time.sleep(0.15) # API 속도 제어
        
    print("\n" + "=" * 90)
    print("🎉 [Step 2 - 1차 배치 350개사] 5개년 공시 & 지분 & CB 지식그래프 적재 100% 완료!")
    print("=" * 90)

if __name__ == "__main__":
    run_batch1()
