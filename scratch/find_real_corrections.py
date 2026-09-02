# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

corps = [
    ("00126380", "삼성전자"),
    ("00164779", "SK하이닉스"),
    ("00164742", "현대자동차"),
    ("00258801", "카카오"),
    ("00401731", "셀트리온")
]

print("="*80)
print("🔍 실제 OpenDART [기재정정] 정기보고서/주요공시 샘플 탐색")
print("="*80)

for corp_code, name in corps:
    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={api_key}&corp_code={corp_code}&bgn_de=20210101&end_de=20241231&page_count=100"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    filings = data.get("list", [])
    corrected = [f for f in filings if "[기재정정]" in f.get("report_nm", "")]
    print(f"🏢 {name} ({corp_code}) - [기재정정] 건수: {len(corrected)}건")
    for c in corrected[:3]:
        print(f"   • [{c.get('rcept_no')}] ({c.get('rcept_dt')}) {c.get('report_nm')}")
