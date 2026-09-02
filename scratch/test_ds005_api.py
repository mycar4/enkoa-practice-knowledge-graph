# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("NEO4J_PASSWORD", "1234")

driver = GraphDatabase.driver(uri, auth=(user, pwd))

# 10개 상장사 샘플 가져오기
with driver.session() as s:
    res = s.run("MATCH (c:DART_Company) WHERE c.corp_code IS NOT NULL RETURN c.name AS name, c.corp_code AS corp_code LIMIT 20")
    corps = [r.data() for r in res]

bgn_de = "20200101"
end_de = "20241231"

endpoints = {
    "CB (전환사채)": "cvbdIsDecsn.json",
    "BW (신주인수권)": "bdwtIsDecsn.json",
    "증자 (유상증자)": "piicDecsn.json",
    "타법인주식양수": "otcprStkInvscrAcqDecsn.json",
    "회사합병": "cmpMgDecsn.json"
}

print(f"Loaded {len(corps)} companies for testing DS005...")

total_events_found = 0
for c in corps:
    name = c['name']
    code = c['corp_code']
    for ep_name, ep_file in endpoints.items():
        url = f"https://opendart.fss.or.kr/api/{ep_file}?crtfc_key={api_key}&corp_code={code}&bgn_de={bgn_de}&end_de={end_de}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == '000' and data.get('list'):
                    cnt = len(data['list'])
                    total_events_found += cnt
                    print(f"🎯 [발견] {name}({code}) - {ep_name}: {cnt}건")
                    print(f"   필드 목록: {list(data['list'][0].keys())}")
                    print(f"   샘플 레코드: {json.dumps(data['list'][0], ensure_ascii=False)[:250]}")
        except Exception as e:
            pass

print(f"\n총 발견된 자본 이벤트 건수: {total_events_found}건")
