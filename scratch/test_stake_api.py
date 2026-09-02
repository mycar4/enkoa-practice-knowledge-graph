# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

url = f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={api_key}&corp_code=00126380"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

items = data.get("list", [])
if items:
    for k, v in items[0].items():
        print(f"  {k}: {v}")
