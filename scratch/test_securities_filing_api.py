# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
api_key = os.getenv("DART_API_KEY")

corps = [
    ("00258801", "카카오"),
    ("00401731", "셀트리온"),
    ("00161408", "HMM"),
    ("00164779", "SK하이닉스"),
    ("00356361", "에코프로비엠"),
    ("00878939", "HLB"),
    ("00593457", "씨젠")
]

for corp_code, name in corps:
    url = f"https://opendart.fss.or.kr/api/cvbdIsDecsn.json?crtfc_key={api_key}&corp_code={corp_code}&bgn_de=20200101&end_de=20241231"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    if data.get("status") == "000":
        items = data.get("list", [])
        print(f"🏢 {name} ({corp_code}) - CB 발행 건수: {len(items)}건")
        for it in items[:2]:
            print(f"   • 공시명: {it.get('bd_nm')} (접수번호: {it.get('rcept_no')})")
            print(f"   • 사채발행방법(사모/공모): {it.get('cb_is_mth')}")
            print(f"   • 시설: {it.get('fclt_fnd')} | 운영: {it.get('bpr_fnd')} | 채무상환: {it.get('dbt_rp_fnd')} | 타법인취득: {it.get('ocp_at_fnd')}")
            print(f"   • 표면이자율: {it.get('sfc_inr')} | 만기이자율: {it.get('exp_inr')} | 만기일: {it.get('exp_dt')}")
    else:
        print(f"🏢 {name} ({corp_code}) - 응답: {data.get('message')}")
