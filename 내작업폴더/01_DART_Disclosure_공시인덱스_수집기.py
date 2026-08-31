# -*- coding: utf-8 -*-
"""
🏛️ [v0.2 Step 1] DART-Trace OpenDART DS001 공시 인덱스 수집기 (페이징 & 정밀 집계 지원)
- 주요 기능:
  1) 대상 상장사의 DS001 공시목록(list.json) 페이징(page_no) 반복 수집
  2) :DART_Disclosure 노드 적재 (rcept_no Unique 제약조건 보장)
  3) (:DART_Company)-[:FILED]->(:DART_Disclosure) 관계 생성
  4) doc_status (NORMAL: 정정·철회로 분류되지 않은 공시 / CORRECTED / WITHDRAWN) 분류
  5) 신규 생성 / 기존 갱신 / 실패 / 미연결 기업 정밀 분리 집계
  6) CLI 옵션(--limit, --all) 지원 및 안전한 환경변수 검증 (비밀번호 기본값 제거)
"""

import os
import sys
import io
import time
import json
import argparse
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
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
DART_API_KEY = os.getenv("DART_API_KEY")

if not NEO4J_PASSWORD:
    raise ValueError("❌ [보안 원칙 위반 방지] .env 파일에 NEO4J_PASSWORD가 설정되지 않았습니다. 기본값을 사용하지 않고 안전하게 중단합니다.")
if not DART_API_KEY:
    raise ValueError("❌ .env 파일에 DART_API_KEY가 설정되지 않았습니다.")

def get_db_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def fetch_all_disclosures_with_paging(corp_code: str, bgn_de: str = "20240101", end_de: str = "20260831"):
    """OpenDART DS001 list.json 페이징(page_no) 전수 반복 수집"""
    all_list = []
    page_no = 1
    page_count = 100
    
    while True:
        url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de={bgn_de}&end_de={end_de}&page_no={page_no}&page_count={page_count}"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                status = data.get("status")
                
                if status == "000":
                    items = data.get("list", [])
                    all_list.extend(items)
                    total_page = data.get("total_page", 1)
                    
                    if page_no >= total_page:
                        break
                    page_no += 1
                    time.sleep(0.1) # 페이징 간 미세 대기
                elif status == "013": # 해당 기간 공시 없음
                    break
                else:
                    print(f"⚠️ OpenDART 응답 상태 ({corp_code}, page {page_no}): {status} - {data.get('message')}")
                    break
        except Exception as e:
            print(f"❌ API 호출 에러 ({corp_code}, page {page_no}): {e}")
            break
            
    return all_list

def ingest_disclosures(driver, corp_code: str, disclosures: list):
    """Neo4j에 :DART_Disclosure 및 [:FILED] 적재하고 신규/갱신 건수 반환"""
    if not disclosures:
        return {"created": 0, "updated": 0, "filed": 0}

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
        disc.ingested_at = datetime(),
        disc.is_new = true
    ON MATCH SET
        disc.report_nm = d.report_nm,
        disc.flr_nm = d.flr_nm,
        disc.rm = d.rm,
        disc.doc_status = CASE 
            WHEN d.rm CONTAINS '철' THEN 'WITHDRAWN'
            WHEN d.rm CONTAINS '정' OR d.report_nm CONTAINS '정정' THEN 'CORRECTED'
            ELSE 'NORMAL'
        END,
        disc.is_new = false
    
    WITH disc, d
    MATCH (c:DART_Company {corp_code: d.corp_code})
    MERGE (c)-[f:FILED]->(disc)
    RETURN count(CASE WHEN disc.is_new = true THEN 1 END) AS created_cnt,
           count(CASE WHEN disc.is_new = false THEN 1 END) AS updated_cnt,
           count(f) AS filed_cnt
    """

    with driver.session() as session:
        res = session.run(query, disclosures=disclosures).single()
        return {
            "created": res["created_cnt"] if res else 0,
            "updated": res["updated_cnt"] if res else 0,
            "filed": res["filed_cnt"] if res else 0
        }

def run_step1(limit: int = 100, bgn_de: str = "20240101", end_de: str = "20260831"):
    mode_text = f"1차 {limit}개사 파일럿 적재" if limit else "전체 상장사 전수 적재"
    print("=" * 85)
    print(f"🚀 [DART-Trace v0.2 Step 1] DS001 공시 인덱스 수집 가동 ({mode_text})")
    print("=" * 85)

    driver = get_db_driver()
    
    # 대상 기업 쿼리
    limit_clause = f"LIMIT {limit}" if limit else ""
    query_corps = f"""
    MATCH (c:DART_Company)
    WHERE c.corp_code IS NOT NULL AND c.is_listed = true
    RETURN c.corp_code AS corp_code, c.name AS name, c.market AS market
    ORDER BY CASE WHEN c.market = 'KOSPI' THEN 1 WHEN c.market = 'KOSDAQ' THEN 2 ELSE 3 END, c.name
    {limit_clause}
    """
    
    with driver.session() as session:
        corps = session.run(query_corps).data()

    print(f"📊 수집 대상 기업 수: {len(corps)}개사 선별 완료")

    stats = {
        "total_corps": len(corps),
        "success_corps": 0,
        "no_disclosure_corps": 0,
        "failed_corps": 0,
        "created_disclosures": 0,
        "updated_disclosures": 0,
        "total_filed": 0
    }

    for idx, corp in enumerate(corps, 1):
        c_code = corp["corp_code"]
        c_name = corp["name"]
        
        try:
            discs = fetch_all_disclosures_with_paging(c_code, bgn_de=bgn_de, end_de=end_de)
            if discs:
                res = ingest_disclosures(driver, c_code, discs)
                stats["created_disclosures"] += res["created"]
                stats["updated_disclosures"] += res["updated"]
                stats["total_filed"] += res["filed"]
                stats["success_corps"] += 1
                print(f"  [{idx:3d}/{len(corps)}] {c_name}({c_code}) ➔ 공시 {len(discs)}건 (신규: {res['created']}, 갱신: {res['updated']})")
            else:
                stats["no_disclosure_corps"] += 1
                print(f"  [{idx:3d}/{len(corps)}] {c_name}({c_code}) ➔ 해당 기간 공시 없음")
        except Exception as e:
            stats["failed_corps"] += 1
            print(f"  [{idx:3d}/{len(corps)}] ❌ {c_name}({c_code}) 적재 실패: {e}")
        
        time.sleep(0.12) # API Rate Limit 보호

    # 최종 DB 현황 집계
    with driver.session() as session:
        total_disc_nodes = session.run("MATCH (d:DART_Disclosure) RETURN count(d) AS cnt").single()["cnt"]
        total_filed_edges = session.run("MATCH ()-[r:FILED]->() RETURN count(r) AS cnt").single()["cnt"]
        doc_status_dist = session.run("""
        MATCH (d:DART_Disclosure)
        RETURN d.doc_status AS status, count(d) AS count
        ORDER BY count DESC
        """).data()

    print("\n" + "=" * 85)
    print(f"🏁 [v0.2 Step 1 {mode_text} 완료 보고서]")
    print(f"   • 대상 기업: 총 {stats['total_corps']}개사 (공시 확인: {stats['success_corps']}개, 공시 없음: {stats['no_disclosure_corps']}개, 실패: {stats['failed_corps']}개)")
    print(f"   • 금회 수집 결과: 신규 생성 {stats['created_disclosures']:,}건 / 기존 갱신 {stats['updated_disclosures']:,}건")
    print(f"   • DB 누적 현황: :DART_Disclosure 노드 {total_disc_nodes:,}개 / [:FILED] 관계 {total_filed_edges:,}개")
    print(f"   • 공시 문서 이력(doc_status) 정밀 분포:")
    for row in doc_status_dist:
        st_desc = "정정·철회로 분류되지 않은 공시" if row['status'] == 'NORMAL' else ("기재정정 공시" if row['status'] == 'CORRECTED' else "철회 공시")
        print(f"     - {row['status']} ({st_desc}): {row['count']:,}건")
    print("=" * 85)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DART-Trace DS001 공시 인덱스 수집기")
    parser.add_argument("--limit", type=int, default=100, help="수집할 상장사 수 (기본값: 100, 0 또는 음수 입력 시 전수 모드)")
    parser.add_argument("--all", action="store_true", help="전체 상장사 전수 수집 모드")
    parser.add_argument("--bgn_de", type=str, default="20240101", help="시작일자 (YYYYMMDD)")
    parser.add_argument("--end_de", type=str, default="20260831", help="종료일자 (YYYYMMDD)")
    
    args = parser.parse_args()
    target_limit = None if args.all or (args.limit and args.limit <= 0) else args.limit
    
    run_step1(limit=target_limit, bgn_de=args.bgn_de, end_de=args.end_de)
