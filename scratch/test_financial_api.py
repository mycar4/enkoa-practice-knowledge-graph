# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")
url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?crtfc_key={api_key}&corp_code=00126380&bsns_year=2023&reprt_code=11011"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print("Status:", data.get("status"))
print("Message:", data.get("message"))
items = data.get("list", [])
print("Item count:", len(items))
for it in items[:15]:
    print(f"[{it.get('fs_div')}] {it.get('account_nm')}: {it.get('thstrm_amount')} (account_id: {it.get('account_id')}, rcept_no: {it.get('rcept_no')})")
