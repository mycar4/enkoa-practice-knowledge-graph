# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 대한민국 전체 상장사 코스닥(KOSDAQ) / 코스피(KOSPI) 시장 분류 전수 태깅
=====================================================================================
1. KRX 상장법인 마스터에서 회사명, 시장구분(코스피/코스닥/코넥스), 종목코드 추출
2. Neo4j의 DART_Company 노드에 `market` ('KOSDAQ', 'KOSPI', 'KONEX') 및 `corp_cls` ('K', 'Y', 'N') 전수 SET
=====================================================================================
"""

import os
import sys
import re
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

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def tag_markets():
    print("="*80)
    print("🚀 [DART-Trace] KRX 시장분류(코스닥/코스피/코넥스) 전수 다운로드 및 태깅 시작")
    print("="*80)
    
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("euc-kr", errors="ignore")
        
    # 정규식으로 tr 태그 단위 파싱
    tr_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL)
    td_pattern = re.compile(r'<td.*?>(.*?)</td>', re.DOTALL)
    
    items = []
    for tr in tr_pattern.findall(html):
        tds = td_pattern.findall(tr)
        if len(tds) >= 3:
            raw_name = re.sub(r'<.*?>', '', tds[0]).strip()
            raw_market = re.sub(r'<.*?>', '', tds[1]).strip()
            raw_code = re.sub(r'<.*?>', '', tds[2]).strip()
            
            if len(raw_code) == 6:
                market_type = "KOSDAQ" if "코스닥" in raw_market else ("KOSPI" if "유가" in raw_market else ("KONEX" if "코넥스" in raw_market else "OTHER"))
                corp_cls = "K" if market_type == "KOSDAQ" else ("Y" if market_type == "KOSPI" else ("N" if market_type == "KONEX" else "E"))
                
                items.append({
                    "name": raw_name,
                    "stock_code": raw_code,
                    "market": market_type,
                    "corp_cls": corp_cls
                })
                
    print(f"📊 KRX 공식 상장법인 총 {len(items)}개사 분류 파싱 완료!")
    kosdaq_count = sum(1 for x in items if x['market'] == 'KOSDAQ')
    kospi_count = sum(1 for x in items if x['market'] == 'KOSPI')
    konex_count = sum(1 for x in items if x['market'] == 'KONEX')
    print(f"  • 코스닥(KOSDAQ): {kosdaq_count}개사")
    print(f"  • 코스피(KOSPI): {kospi_count}개사")
    print(f"  • 코넥스(KONEX): {konex_count}개사")
    
    # Neo4j 일괄 업데이트
    print("\n📥 Neo4j DART_Company 노드에 시장분류(market, corp_cls) 태깅 중...")
    with driver.session() as s:
        s.run("""
        UNWIND $batch AS it
        MATCH (c:DART_Company)
        WHERE c.stock_code = it.stock_code OR c.name = it.name
        SET c.market = it.market,
            c.corp_cls = it.corp_cls,
            c.is_listed = true
        """, batch=items)
        
        # 검증
        kq_db = s.run("MATCH (c:DART_Company) WHERE c.market = 'KOSDAQ' OR c.corp_cls = 'K' RETURN count(c) AS cnt").single()['cnt']
        kp_db = s.run("MATCH (c:DART_Company) WHERE c.market = 'KOSPI' OR c.corp_cls = 'Y' RETURN count(c) AS cnt").single()['cnt']
        print(f"\n✅ Neo4j 검증 완료:")
        print(f"  🎉 코스닥(KOSDAQ) 노드 수: {kq_db}개사")
        print(f"  🎉 코스피(KOSPI) 노드 수: {kp_db}개사")
        
    print("="*80)
    print("🎉 전수 시장분류 태깅 100% 완료!")
    print("="*80)

if __name__ == "__main__":
    tag_markets()
