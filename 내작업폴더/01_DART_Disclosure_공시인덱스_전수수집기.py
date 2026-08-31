# -*- coding: utf-8 -*-
"""
🏛️ [v0.2 Step 1] DART-Trace OpenDART DS001 공시 인덱스 전수 수집기
- 역할:
  1) 대상 기업(주요 상장사 및 지분 추적 대상사)의 DS001 공시목록(list.json) 수집
  2) :DART_Disclosure 노드 적재 (rcept_no Unique 제약조건 보장)
  3) (:DART_Company)-[:FILED]->(:DART_Disclosure) 관계 생성
  4) doc_status (NORMAL / CORRECTED / WITHDRAWN) 및 DART 원문 뷰어 링크(viewer_url) 자동 태깅
"""

import os
import sys
import io
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

# UTF-8 콘솔 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")
DART_API_KEY = os.getenv("DART_API_KEY", "")

def get_db_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def fetch_disclosures_for_company(corp_code: str, bgn_de: str = "20240101", end_de: str = "20260831"):
    """OpenDART DS001 공시검색 API (list.json) 호출"""
    if not DART_API_KEY:
        print("❌ DART_API_KEY가 없습니다.")
        return []
    
    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de={bgn_de}&end_de={end_de}&page_count=100"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "000":
                return data.get("list", [])
            elif data.get("status") == "013": # 공시 없음
                return []
            else:
                print(f"⚠️ OpenDART 응답 상태 ({corp_code}): {data.get('status')} - {data.get('message')}")
                return []
    except Exception as e:
        print(f"❌ API 호출 에러 ({corp_code}): {e}")
        return []

def ingest_disclosures(driver, corp_code: str, disclosures: list):
    """Neo4j에 :DART_Disclosure 및 [:FILED] 적재"""
    if not disclosures:
        return 0

    query = """
    UNWIND $disclosures AS d
    MERGE (disc:DART_Disclosure {rcept_no: d.rcept_no})
    ON CREATE SET
        disc.report_nm = d.report_nm,
        disc.rcept_dt = d.rcept_dt,
        disc.received_on = date(substring(d.rcept_dt, 0, 4) + '-' + substring(d.rcept_dt, 4, 2) + '-' + substring(d.rcept_dt, 6, 2)),
        disc.corp_code = d.corp_code,
        disc.corp_name = d.corp_name,
        disc.flr_nm = d.flr_nm,
        disc.rm = d.rm,
        disc.doc_status = CASE 
            WHEN d.rm CONTAINS '철' THEN 'WITHDRAWN'
            WHEN d.rm CONTAINS '정' OR d.report_nm CONTAINS '정정' THEN 'CORRECTED'
            ELSE 'NORMAL'
        END,
        disc.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + d.rcept_no,
        disc.ingested_at = datetime()
    ON MATCH SET
        disc.report_nm = d.report_nm,
        disc.flr_nm = d.flr_nm,
        disc.rm = d.rm,
        disc.doc_status = CASE 
            WHEN d.rm CONTAINS '철' THEN 'WITHDRAWN'
            WHEN d.rm CONTAINS '정' OR d.report_nm CONTAINS '정정' THEN 'CORRECTED'
            ELSE 'NORMAL'
        END
    
    WITH disc, d
    MATCH (c:DART_Company {corp_code: d.corp_code})
    MERGE (c)-[:FILED]->(disc)
    RETURN count(disc) AS cnt
    """

    with driver.session() as session:
        result = session.run(query, disclosures=disclosures).single()
        return result["cnt"] if result else 0

def run_step1_pipeline():
    print("=" * 80)
    print("🚀 [DART-Trace v0.2 Step 1] DS001 공시 인덱스 수집 및 :DART_Disclosure 적재 시작")
    print("=" * 80)

    driver = get_db_driver()
    
    # 1. 대상 기업 목록 추출 (코스피/코스닥 주요 상장사 및 지분 네트워크 대상 기업)
    with driver.session() as session:
        corps = session.run("""
        MATCH (c:DART_Company)
        WHERE c.corp_code IS NOT NULL AND c.is_listed = true
        RETURN c.corp_code AS corp_code, c.name AS name, c.market AS market
        ORDER BY CASE WHEN c.market = 'KOSPI' THEN 1 WHEN c.market = 'KOSDAQ' THEN 2 ELSE 3 END, c.name
        LIMIT 100
        """).data()

    print(f"📊 1. 1차 인덱싱 대상 대표 상장사: {len(corps)}개사 선별 완료")

    total_disclosures = 0
    success_corps = 0

    for idx, corp in enumerate(corps, 1):
        c_code = corp["corp_code"]
        c_name = corp["name"]
        
        discs = fetch_disclosures_for_company(c_code, bgn_de="20240101", end_de="20260831")
        if discs:
            ingested_cnt = ingest_disclosures(driver, c_code, discs)
            total_disclosures += ingested_cnt
            success_corps += 1
            print(f"  [{idx:3d}/{len(corps)}] {c_name}({c_code}) ➔ 공시 {len(discs)}건 적재 완료 (누적: {total_disclosures}건)")
        else:
            print(f"  [{idx:3d}/{len(corps)}] {c_name}({c_code}) ➔ 해당 기간 공시 없음")
        
        time.sleep(0.15) # API Rate Limit 안정성 확보

    # 2. 결과 검증 집계
    with driver.session() as session:
        total_disc_nodes = session.run("MATCH (d:DART_Disclosure) RETURN count(d) AS cnt").single()["cnt"]
        total_filed_edges = session.run("MATCH ()-[r:FILED]->() RETURN count(r) AS cnt").single()["cnt"]
        doc_status_dist = session.run("""
        MATCH (d:DART_Disclosure)
        RETURN d.doc_status AS status, count(d) AS count
        ORDER BY count DESC
        """).data()

    print("\n" + "=" * 80)
    print(f"🎉 [v0.2 Step 1 완료] 총 {total_disc_nodes:,}개 :DART_Disclosure 노드 & {total_filed_edges:,}개 [:FILED] 관계 적재 완료!")
    print(f"📈 공시 문서 상태(doc_status) 분포:")
    for row in doc_status_dist:
        print(f"   • {row['status']}: {row['count']:,}건")
    print("=" * 80)

if __name__ == "__main__":
    run_step1_pipeline()
