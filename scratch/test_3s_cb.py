# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

url = f"https://opendart.fss.or.kr/api/cvbdIsDecsn.json?crtfc_key={api_key}&corp_code=00378363&bgn_de=20240101&end_de=20241231"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

for it in data.get("list", []):
    for k, v in it.items():
        if v:
            print(f"  {k}: {v}")
