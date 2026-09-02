# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={api_key}&corp_code=00258801&bgn_de=20241101&end_de=20241231&page_count=100"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

for f in data.get("list", []):
    if "분기보고서" in f.get("report_nm", ""):
        print(f"[{f.get('rcept_no')}] ({f.get('rcept_dt')}) {f.get('report_nm')}")
