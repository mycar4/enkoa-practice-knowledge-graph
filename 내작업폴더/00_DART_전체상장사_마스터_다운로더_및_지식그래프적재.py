# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 대한민국 전체 상장사(2,700개+) 마스터 전수 다운로드 & Neo4j 지식그래프 적재
====================================================================================
1. OpenDART API (corpCode.xml) 고유번호 마스터 ZIP 파일 실시간 다운로드
2. 압축 해제 후 유효 상장사(stock_code 보유 기업) 2,700개 전수 파싱
3. Neo4j에 (:DART_Company {name, stock_code, corp_code})로 MERGE 대량 고속 적재
====================================================================================
"""

import os
import sys
import zipfile
import io
import xml.etree.ElementTree as ET
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

def fetch_and_load_all_listed_corps():
    print("="*80)
    print("🚀 [DART-Trace] 대한민국 전체 상장사(코스피/코스닥/코넥스) 2,700개+ 전수 적재 가동")
    print("="*80)
    
    if not DART_API_KEY:
        print("❌ DART_API_KEY가 설정되지 않았습니다.")
        return
        
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"
    print(f"📡 1. OpenDART 기업 고유번호 마스터 ZIP 다운로드 중...")
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        zip_bytes = resp.read()
        
    print(f"📦 2. ZIP 파일 압축 해제 및 XML 파싱 중 (데이터 크기: {len(zip_bytes)//1024} KB)...")
    listed_corps = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        with z.open("CORPCODE.xml") as xml_file:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for list_elem in root.findall("list"):
                corp_code = list_elem.findtext("corp_code", "").strip()
                corp_name = list_elem.findtext("corp_name", "").strip()
                stock_code = list_elem.findtext("stock_code", "").strip()
                modify_date = list_elem.findtext("modify_date", "").strip()
                
                # 상장회사만 필터링 (종목코드 6자리가 존재하는 기업)
                if stock_code and len(stock_code) == 6:
                    listed_corps.append({
                        "name": corp_name,
                        "corp_code": corp_code,
                        "stock_code": stock_code,
                        "modify_date": modify_date
                    })
                    
    print(f"✅ 대한민국 유효 전체 상장사 총 {len(listed_corps)}개사 추출 완료!")
    for c in listed_corps[:5]:
        print(f"  • [{c['stock_code']}] {c['name']} (고유코드: {c['corp_code']})")

    # 3. Neo4j 대량 고속 적재 (배치 크기: 500개씩)
    print(f"\n📥 3. Neo4j 지식그래프에 전체 상장사 노드 고속 MERGE 적재 중...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    batch_size = 500
    total_loaded = 0
    with driver.session() as s:
        for i in range(0, len(listed_corps), batch_size):
            batch = listed_corps[i:i+batch_size]
            s.run("""
            UNWIND $batch AS c
            MERGE (comp:DART_Company {name: c.name})
            SET comp.stock_code = c.stock_code,
                comp.corp_code = c.corp_code,
                comp.is_listed = true,
                comp.updated_at = datetime()
            """, batch=batch)
            total_loaded += len(batch)
            print(f"  ⚡ {total_loaded}/{len(listed_corps)} 개사 적재 진행 중...")
            
    print("\n" + "="*80)
    print(f"🎉 대한민국 전체 {total_loaded}개 상장사가 Neo4j 지식그래프에 완벽 적재되었습니다!")
    print("="*80)

if __name__ == "__main__":
    fetch_and_load_all_listed_corps()
