# -*- coding: utf-8 -*-
"""
📥 [OpenDART API] 전체 고유번호(CORPCODE.xml) 다운로드 및 전체 상장사(4,023개) 마스터 일괄 적재
"""
import os, sys, io, zipfile, urllib.request
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

DART_API_KEY = os.getenv("DART_API_KEY", "")
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

print("="*95)
print("📥 [1. OpenDART API 공식 고유번호 ZIP 다운로드 및 CORPCODE.xml 추출]")
print("="*95)

url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(req, timeout=30) as resp:
    zip_bytes = resp.read()
    
with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    zf.extractall("내작업폴더/data")
    print("✅ `내작업폴더/data/CORPCODE.xml` 추출 완료!")

xml_path = "내작업폴더/data/CORPCODE.xml"
tree = ET.parse(xml_path)
root = tree.getroot()

listed_companies = []
for item in root.findall("list"):
    stock_code = (item.findtext("stock_code") or "").strip()
    if stock_code: # 상장사만 필터
        listed_companies.append({
            "corp_code": item.findtext("corp_code").strip(),
            "name": item.findtext("corp_name").strip(),
            "stock_code": stock_code,
            "market": "Y"
        })

print(f"📊 공인 상장사 {len(listed_companies):,}개사 추출 완료!")

print("\n" + "="*95)
print("🏢 [2. Neo4j Aura 신규 DB에 4,000+ 상장사 마스터 Batch 적재]")
print("="*95)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), max_connection_lifetime=120)

BATCH_SIZE = 1000
with driver.session() as s:
    for i in range(0, len(listed_companies), BATCH_SIZE):
        batch = listed_companies[i:i+BATCH_SIZE]
        s.run("""
        UNWIND $batch AS it
        MERGE (c:DART_Company {corp_code: it.corp_code})
        ON CREATE SET c.name = it.name,
                      c.stock_code = it.stock_code,
                      c.market = it.market,
                      c.is_listed = true,
                      c.created_at = datetime()
        """, batch=batch)
        print(f"  • {i+len(batch):,} / {len(listed_companies):,} 개사 적재 완료...")
        
    final_count = s.run("MATCH (c:DART_Company) RETURN count(c) AS cnt").single()["cnt"]
    print(f"\n🎉 [적재 완수] Neo4j Aura에 공인 상장사 마스터 노드 {final_count:,}개 100% 적재 완료!")
