# -*- coding: utf-8 -*-
import os, sys, io, zipfile, re, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={api_key}&rcept_no=20241226000456"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    zip_bytes = resp.read()

with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
    xml = z.read("20241226000456.xml").decode("utf-8", errors="ignore")

idx = xml.find("정정사유")
if idx != -1:
    clean_text = re.sub(r'<[^>]+>', ' ', xml[idx-100:idx+600])
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    print(f"정정사유 주변 본문 텍스트:\n{clean_text}")
