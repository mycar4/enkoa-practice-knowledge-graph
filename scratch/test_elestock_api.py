# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

url = f"https://opendart.fss.or.kr/api/elestock.json?crtfc_key={api_key}&corp_code=00126380"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

items = data.get("list", [])
print(f"삼성전자 임원/주요주주 소유보고 건수: {len(items)}건")
for it in items[:5]:
    print(f"  • {it.get('repror')} ({it.get('isu_exctv_rgist_at')}) | 주식: {it.get('sp_stock_lmp_cnt')}주 | 지분: {it.get('sp_stock_lmp_rate')}% | 접수번호: {it.get('rcept_no')} ({it.get('rcept_dt')})")
