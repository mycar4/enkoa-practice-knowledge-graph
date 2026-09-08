import os, sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv('.env')
api_key = os.getenv('DART_API_KEY')
corp_code = '00126380' # 삼성전자

url = f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={api_key}&corp_code={corp_code}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print("majorstock.json status:", data.get('status'), data.get('message'))
    print("list sample:", data.get('list')[:2] if data.get('list') else None)
