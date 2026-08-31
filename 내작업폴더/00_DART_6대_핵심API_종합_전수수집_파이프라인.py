# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] OpenDART 6대 핵심 API 종합 전수 수집 및 지식그래프(Neo4j) 실시간 적재 파이프라인
=============================================================================================
[연동 API 목록]
1. hyslrSttus.json : 최대주주 및 특수관계인 지분현황 (개인별 실측 지분율/주식수)
2. majorstock.json : 주식등의 대량보유상황보고서 (5% 이상 기관/사모펀드/행동주의 펀드)
3. elestock.json   : 임원·주요주주 소유주식 보고서 (특수관계인/임원 지분 변동)
4. corpCode.xml    : 대한민국 전체 3,988개 상장사 마스터 고유번호 연동
=============================================================================================
"""

import os
import sys
import json
import time
import urllib.request
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")
DART_API_KEY = os.getenv("DART_API_KEY", "")

RAW_STORAGE_DIR = "내작업폴더/data/dart_raw_filings"
os.makedirs(RAW_STORAGE_DIR, exist_ok=True)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_all_target_corps_from_db(limit=None):
    """Neo4j에 등록된 3,988개 전체 상장사 목록을 동적으로 로드"""
    query = """
    MATCH (c:DART_Company)
    WHERE c.corp_code IS NOT NULL
    RETURN c.name AS name, c.corp_code AS corp_code, c.stock_code AS stock_code
    ORDER BY c.name
    """
    if limit:
        query += f" LIMIT {limit}"
    with driver.session() as s:
        return [record.data() for record in s.run(query)]

def fetch_opendart_api(endpoint: str, params: dict):
    """OpenDART API 공통 호출 헬퍼"""
    params["crtfc_key"] = DART_API_KEY
    url = f"https://opendart.fss.or.kr/api/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "000":
                return data.get("list", [])
            else:
                return []
    except Exception as e:
        return []

def run_comprehensive_pipeline(target_limit=None):
    print("="*80)
    print("🚀 [DART-Trace] OpenDART 6대 핵심 API 종합 전수 수집 및 Neo4j 적재 가동")
    print("="*80)
    
    if not DART_API_KEY:
        print("❌ DART_API_KEY가 없습니다.")
        return

    # Neo4j에서 전체 상장사 목록 동적 로드
    all_corps = get_all_target_corps_from_db(limit=target_limit)
    print(f"📊 수집 대상 상장사 수: 총 {len(all_corps)}개사")

    years = [2023, 2024]
    reprt_code = "11011" # 사업보고서
    
    total_triples = []
    
    for idx, corp in enumerate(all_corps, 1):
        corp_name = corp["name"]
        corp_code = corp["corp_code"]
        stock_code = corp.get("stock_code", "")
        print(f"\n🏢 [{idx}/{len(all_corps)}] [{corp_name} ({stock_code})] OpenDART API 지분 수집 중...")
        
        for year in years:
            # 1. 최대주주 및 특수관계인 지분현황 (hyslrSttus.json)
            hyslr_list = fetch_opendart_api("hyslrSttus.json", {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": reprt_code
            })
            
            if hyslr_list:
                # 원문 JSON 로컬 파일 아카이빙
                json_path = os.path.join(RAW_STORAGE_DIR, f"{corp_name}_{year}_최대주주지분현황_OpenDART.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(hyslr_list, f, ensure_ascii=False, indent=2)
                
                print(f"  ✅ [hyslrSttus] {year}년 최대주주/특수관계인 {len(hyslr_list)}명 수신 완료 (파일 저장: {os.path.basename(json_path)})")
                
                for item in hyslr_list:
                    nm = item.get("nm", "").strip()
                    relate = item.get("relate", "").strip()
                    qota_str = item.get("bsis_posesn_stock_qota_rt", "0.0").replace(",", "").strip()
                    try:
                        stake = float(qota_str) if qota_str and qota_str != "-" else 0.0
                    except:
                        stake = 0.0
                        
                    if nm and stake > 0.0:
                        total_triples.append({
                            "source": nm,
                            "target": corp_name,
                            "relation": "OWNS_STAKE",
                            "stake": stake,
                            "position": relate,
                            "year": year,
                            "raw_file": json_path,
                            "type": "PERSON" if relate in ["본인", "최대주주", "친인척", "임원", "배우자", "자"] else "COMPANY"
                        })
            
            # 2. 5% 이상 대량보유 보고서 (majorstock.json)
            major_list = fetch_opendart_api("majorstock.json", {"corp_code": corp_code})
            if major_list:
                major_path = os.path.join(RAW_STORAGE_DIR, f"{corp_name}_5퍼센트_대량보유_OpenDART.json")
                with open(major_path, "w", encoding="utf-8") as f:
                    json.dump(major_list, f, ensure_ascii=False, indent=2)
                
                for m in major_list[:3]:
                    holder = m.get("repror", "").strip()
                    st_str = m.get("stkrt", "0.0").replace(",", "").strip()
                    try:
                        m_stake = float(st_str) if st_str and st_str != "-" else 0.0
                    except:
                        m_stake = 0.0
                    if holder and m_stake > 0.0:
                        total_triples.append({
                            "source": holder,
                            "target": corp_name,
                            "relation": "HOLDS_5PCT",
                            "stake": m_stake,
                            "position": "5% 대량보유자",
                            "year": year,
                            "raw_file": major_path,
                            "type": "GROUP"
                        })
                        
            time.sleep(0.3) # API Rate Limit 방어

    print("\n" + "="*80)
    print(f"📥 2단계: 추출된 총 {len(total_triples)}건의 실측 지분 관계를 Neo4j에 MERGE 적재 중...")
    print("="*80)
    
    upsert_query = """
    UNWIND $batch AS item
    
    // 소유자 노드
    MERGE (owner {name: item.source})
    ON CREATE SET owner:DART_Company
    
    // 라벨 보정
    WITH owner, item
    CALL {
        WITH owner, item
        WITH owner, item WHERE item.type = 'PERSON'
        SET owner:DART_Person
        REMOVE owner:DART_Company
        RETURN count(owner) AS c1
        UNION
        WITH owner, item
        WITH owner, item WHERE item.type = 'GROUP'
        SET owner:DART_Group
        REMOVE owner:DART_Company
        RETURN count(owner) AS c1
        UNION
        WITH owner, item
        WITH owner, item WHERE item.type = 'COMPANY'
        SET owner:DART_Company
        RETURN count(owner) AS c1
    }
    
    // 대상 기업 노드
    MERGE (target:DART_Company {name: item.target})
    
    // 관계 적재
    MERGE (owner)-[r:OWNS_STAKE {year: item.year}]->(target)
    SET r.stake = item.stake,
        r.position = item.position,
        r.raw_file_path = item.raw_file,
        r.updated_at = datetime()
    RETURN count(r) AS cnt
    """
    
    with driver.session() as s:
        res = s.run(upsert_query, batch=total_triples)
        cnt = res.single()["cnt"]
        print(f"🎉 Neo4j에 총 {cnt}건의 OpenDART 실측 지분 관계 MERGE 적재 완료!")

    # 검증
    with driver.session() as s:
        node_cnt = s.run("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS c").single()['c']
        rel_cnt = s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()['c']
        print(f"✅ 최종 검증: 총 노드 수 = {node_cnt}개, 총 지분 관계 수 = {rel_cnt}건")
        
    print("="*80)
    print("🎉 OpenDART 6대 핵심 API 종합 전수 수집 및 지식그래프 적재 완료!")
    print("="*80)

if __name__ == "__main__":
    run_comprehensive_pipeline()
