# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from neo4j import GraphDatabase
import sys

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("NEO4J_PASSWORD", "1234")

driver = GraphDatabase.driver(uri, auth=(user, pwd))

with driver.session() as s:
    res = s.run("MATCH (c:DART_Company) WHERE c.corp_code IS NOT NULL RETURN c.name AS name, c.corp_code AS corp_code LIMIT 30")
    corps = [r.data() for r in res]

bgn_de = "20200101"
end_de = "20241231"

endpoints = {
    "CB": "cvbdIsDecsn.json",
    "BW": "bdwtIsDecsn.json",
    "증자": "piicDecsn.json",
    "타법인주식양수": "otcprStkInvscrAcqDecsn.json",
    "회사합병": "cmpMgDecsn.json"
}

found_samples = {}

for c in corps:
    name = c['name']
    code = c['corp_code']
    for ep_key, ep_file in endpoints.items():
        if ep_key in found_samples:
            continue
        url = f"https://opendart.fss.or.kr/api/{ep_file}?crtfc_key={api_key}&corp_code={code}&bgn_de={bgn_de}&end_de={end_de}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == '000' and data.get('list'):
                    found_samples[ep_key] = (name, data['list'][0])
                    print(f"\n=======================================================")
                    print(f"📌 [API: {ep_key}] 기업: {name}, 필드 개수: {len(data['list'][0])}")
                    print(f"=======================================================")
                    for k, v in data['list'][0].items():
                        print(f"  • {k}: {v}")
        except Exception:
            pass

print(f"\n발견된 이벤트 타입 샘플 개수: {len(found_samples)}")
