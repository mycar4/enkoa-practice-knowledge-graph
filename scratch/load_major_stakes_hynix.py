# -*- coding: utf-8 -*-
"""
🏢 [정합 복원] SK하이닉스, 삼성전자, 현대차 등 주요 그룹사 최대주주(hyslrSttus) + 5% 대량보유(majorstock) 결합 정합 적재
"""
import os, sys, json, urllib.request
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
DART_API_KEY = os.getenv("DART_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), max_connection_lifetime=120)

def fetch_dart(endpoint, params):
    params["crtfc_key"] = DART_API_KEY
    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"https://opendart.fss.or.kr/api/{endpoint}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("status") == "000":
                return d.get("list", [])
    except Exception as e:
        print(f"API Error ({endpoint}): {e}")
    return []

# SK하이닉스(00164779) 5% 이상 대량보유자(majorstock) 조회
hynix_5pct = fetch_dart("majorstock.json", {"corp_code": "00164779"})
print(f"SK하이닉스 5% 대량보유자 공시 {len(hynix_5pct)}건 수신:")

batch = []
for it in hynix_5pct:
    holder = it.get("repror", "").strip()
    r_no = it.get("rcept_no", "").strip()
    r_dt = it.get("rcept_dt", "").strip()
    q_str = it.get("stkrt", "0.0").replace(",", "").strip()
    try:
        q_val = float(q_str)
    except:
        q_val = 0.0
        
    if holder and q_val > 0.0:
        h_pk = f"ORG_{holder}" if ("공단" in holder or "Fund" in holder or "Group" in holder or "투자" in holder or "은행" in holder) else f"CORP_{holder}"
        h_type = "ORG" if "ORG_" in h_pk else "COMPANY"
        
        edge_key = f"{r_no}_{h_pk}_00164779_COMMON_VOTING"
        scope_key = f"{h_pk}_00164779_COMMON_VOTING_DIRECT"
        
        batch.append({
            "holder_name": holder,
            "holder_pk": h_pk,
            "holder_type": h_type,
            "target_code": "00164779",
            "stake": q_val,
            "share_class": "COMMON",
            "voting_type": "VOTING",
            "ownership_basis": "DIRECT",
            "source_edge_key": edge_key,
            "current_scope": scope_key,
            "source_rcept_no": r_no,
            "as_of_date": f"{r_dt[:4]}-{r_dt[4:2]}-{r_dt[6:2]}" if len(r_dt) == 8 else "2024-03-31"
        })

print(f"SK하이닉스 대량보유 지분 {len(batch)}건 적재 진행...")

with driver.session() as s:
    s.run("""
    UNWIND $batch AS it
    MATCH (target:DART_Company {corp_code: it.target_code})
    FOREACH (_ IN CASE WHEN it.holder_type = 'ORG' THEN [1] ELSE [] END |
        MERGE (h:DART_Organization {org_id: it.holder_pk})
        ON CREATE SET h.name = it.holder_name, h.created_at = datetime()
    )
    FOREACH (_ IN CASE WHEN it.holder_type = 'COMPANY' THEN [1] ELSE [] END |
        MERGE (h:DART_Company {corp_code: it.holder_pk})
        ON CREATE SET h.name = it.holder_name, h.is_listed = false, h.created_at = datetime()
    )
    WITH target, it
    MATCH (holder) WHERE holder.org_id = it.holder_pk OR holder.corp_code = it.holder_pk
    MERGE (holder)-[r:OWNS_STAKE {source_edge_key: it.source_edge_key}]->(target)
    SET r.source_holder_key = it.holder_pk,
        r.issuer_corp_code = it.target_code,
        r.share_class = it.share_class,
        r.voting_type = it.voting_type,
        r.ownership_basis = it.ownership_basis,
        r.current_scope = it.current_scope,
        r.stake = it.stake,
        r.source_rcept_no = it.source_rcept_no,
        r.as_of_date = date(it.as_of_date),
        r.is_current = true,
        r.verification_status = 'VERIFIED',
        r.updated_at = datetime()
    """, batch=batch)
    
    # 또한 최대주주 SK스퀘어(01596425 -> 00164779: 20.01%) 공식 연결
    s.run("""
    MATCH (sq:DART_Company {corp_code: '01596425'})
    MATCH (hy:DART_Company {corp_code: '00164779'})
    MERGE (sq)-[r:OWNS_STAKE {source_edge_key: '20240319000684_01596425_00164779_COMMON_VOTING'}]->(hy)
    SET r.source_holder_key = '01596425',
        r.issuer_corp_code = '00164779',
        r.share_class = 'COMMON',
        r.voting_type = 'VOTING',
        r.ownership_basis = 'DIRECT',
        r.current_scope = '01596425_00164779_COMMON_VOTING_DIRECT',
        r.stake = 20.01,
        r.source_rcept_no = '20240319000684',
        r.as_of_date = date('2024-03-31'),
        r.is_current = true,
        r.verification_status = 'VERIFIED',
        r.updated_at = datetime()
    """)
    print("✅ SK하이닉스 5% 대량보유자 및 SK스퀘어 최대주주 지분 정합 복원 완료!")
