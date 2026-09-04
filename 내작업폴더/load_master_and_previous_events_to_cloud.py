# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 3,988개 상장사 마스터 및 5대 자본이벤트(313건) 클라우드 병합 파이프라인
================================================================================
본 스크립트는 기존 15,000건 공시 원문 증거(2.4만개 후보, 5.1만개 파편)를 보존하면서,
1. 대한민국 전체 3,988개 상장사 마스터(:DART_Company)
2. 5대 핵심 자본이벤트(:DART_CapitalEvent 313건)
를 클라우드 Neo4j Aura 운영 DB에 안전하게 추가 병합합니다.
================================================================================
"""

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_URI or not NEO4J_PASSWORD:
    raise ValueError("❌ [환경 오류] .env에 NEO4J_URI 및 NEO4J_PASSWORD가 설정되지 않았습니다.")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def normalize_date_str(val):
    if not val or val in ['-', '해당사항없음', '']:
        return None
    val_clean = re.sub(r'[^\d]', '', str(val))
    if len(val_clean) == 8:
        return f"{val_clean[:4]}-{val_clean[4:6]}-{val_clean[6:8]}"
    return None


def parse_num(val, is_float=False):
    if not val or val in ['-', '해당사항없음', '']:
        return None
    c_str = str(val).replace(',', '').strip()
    try:
        return float(c_str) if is_float else int(float(c_str))
    except:
        return None


def step1_load_3988_master_companies():
    print("\n" + "="*80)
    print("🏢 [Step 1] 대한민국 전체 3,988개 상장사 마스터(:DART_Company) 클라우드 적재")
    print("="*80)

    xml_path = "내작업폴더/data/CORPCODE.xml"
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f"CORPCODE.xml 부재: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()
    companies = []
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        if stock_code:
            companies.append({
                "corp_code": item.findtext("corp_code").strip(),
                "name": item.findtext("corp_name").strip(),
                "stock_code": stock_code,
                "is_listed": True
            })

    print(f"  📂 CORPCODE.xml 파싱 완료: 총 {len(companies):,}개 상장사")

    # 1,000개씩 분할 적재
    batch_size = 1000
    with driver.session() as s:
        for i in range(0, len(companies), batch_size):
            chunk = companies[i:i + batch_size]
            s.run("""
            UNWIND $batch AS it
            MERGE (c:DART_Company {corp_code: it.corp_code})
            ON CREATE SET c.name = it.name,
                          c.stock_code = it.stock_code,
                          c.is_listed = it.is_listed,
                          c.created_at = datetime()
            ON MATCH SET c.name = it.name,
                         c.stock_code = it.stock_code,
                         c.is_listed = it.is_listed
            """, batch=chunk)

        cnt = s.run("MATCH (c:DART_Company) RETURN count(c) as c").single()["c"]
        print(f"  ✅ [DART_Company] 클라우드 Aura 적재 완료: 총 {cnt:,}개사")


def step2_load_313_capital_events():
    print("\n" + "="*80)
    print("⚡ [Step 2] 5대 핵심 자본이벤트(CB·BW·증자·합병 313건) 클라우드 적재")
    print("="*80)

    events_dir = "내작업폴더/data/dart_raw_filings/capital_events"
    if not os.path.exists(events_dir):
        print("  ⚠️ 자본이벤트 디렉토리 부재, 건너뜁니다.")
        return

    json_files = [f for f in os.listdir(events_dir) if f.endswith(".json")]
    print(f"  📂 로컬 아카이브 발견: 총 {len(json_files):,}개 자본이벤트 파일")

    events = []
    for fn in json_files:
        fp = os.path.join(events_dir, fn)
        with open(fp, "r", encoding="utf-8") as f:
            it = json.load(f)

        rcept_no = it.get("rcept_no", "").strip()
        corp_code = it.get("corp_code", "").strip()
        corp_name = it.get("corp_name", "").strip()
        if not rcept_no or not corp_code:
            continue

        # 파일명에서 event_type 추론 (예: 00108612_CB_ISSUE_...)
        parts = fn.split("_")
        event_type = "CAPITAL_EVENT"
        if len(parts) >= 3:
            event_type = f"{parts[1]}_{parts[2]}" if parts[2] in ["ISSUE", "ACQUISITION"] else parts[1]

        event_id = fn.replace(".json", "")
        decided_on = normalize_date_str(it.get("bddd"))
        received_on = f"{rcept_no[:4]}-{rcept_no[4:6]}-{rcept_no[6:8]}" if len(rcept_no) >= 8 else None
        
        effective_on = None
        if "CB" in event_type or "BW" in event_type or "PAID" in event_type:
            effective_on = normalize_date_str(it.get("pymd"))
        elif "ACQUISITION" in event_type:
            effective_on = normalize_date_str(it.get("py_dd"))
        elif "MERGER" in event_type:
            effective_on = normalize_date_str(it.get("mgsc_mgdt"))

        issue_method = it.get("bdis_mthn") or it.get("ic_mth") or it.get("mg_mth") or "-"
        is_private = True if ("사모" in str(issue_method) or "제3자" in str(issue_method)) else False
        issue_amount = parse_num(it.get("bd_fta") or it.get("acq_amt") or it.get("rbsnfdtl_cpt"))
        conversion_price = parse_num(it.get("cv_prc") or it.get("ex_prc") or it.get("nstk_prc"))
        min_refixing_floor = parse_num(it.get("act_mktprcfl_cvprc_lwtrsprc"))
        target_corp_name = it.get("tgcmp_cmpnm") or it.get("mgptncmp_cmpnm") or None
        if target_corp_name:
            target_corp_name = target_corp_name.replace("(주)", "").replace("주식회사", "").strip()

        merger_ratio = it.get("mg_rt")
        purpose = it.get("mg_pp") or it.get("acq_pp") or it.get("fdpp_op") or None

        events.append({
            "event_id": event_id,
            "event_type": event_type,
            "corp_code": corp_code,
            "corp_name": corp_name,
            "rcept_no": rcept_no,
            "decided_on": decided_on,
            "received_on": received_on,
            "effective_on": effective_on,
            "issue_method": str(issue_method),
            "is_private": is_private,
            "issue_amount": issue_amount,
            "conversion_price": conversion_price,
            "min_refixing_floor": min_refixing_floor,
            "target_corp_name": target_corp_name,
            "merger_ratio": str(merger_ratio) if merger_ratio else None,
            "purpose": str(purpose) if purpose else None,
            "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        })

    # 제약조건 생성
    with driver.session() as s:
        s.run("CREATE CONSTRAINT dart_capital_event_id_unique IF NOT EXISTS FOR (e:DART_CapitalEvent) REQUIRE e.event_id IS UNIQUE")

    # 적재
    with driver.session() as s:
        s.run("""
        UNWIND $batch AS it
        MERGE (comp:DART_Company {corp_code: it.corp_code})
        ON CREATE SET comp.name = it.corp_name
        
        MERGE (e:DART_CapitalEvent {event_id: it.event_id})
        SET e.event_type = it.event_type,
            e.corp_code = it.corp_code,
            e.corp_name = it.corp_name,
            e.source_rcept_no = it.rcept_no,
            e.viewer_url = it.viewer_url,
            e.issue_method = it.issue_method,
            e.is_private = it.is_private,
            e.issue_amount = it.issue_amount,
            e.conversion_price = it.conversion_price,
            e.min_refixing_floor = it.min_refixing_floor,
            e.target_corp_name = it.target_corp_name,
            e.merger_ratio = it.merger_ratio,
            e.purpose = it.purpose,
            e.updated_at = datetime()

        WITH comp, e, it
        FOREACH (_ IN CASE WHEN it.decided_on IS NOT NULL THEN [1] ELSE [] END |
            SET e.decided_on = date(it.decided_on)
        )
        FOREACH (_ IN CASE WHEN it.received_on IS NOT NULL THEN [1] ELSE [] END |
            SET e.received_on = date(it.received_on)
        )
        FOREACH (_ IN CASE WHEN it.effective_on IS NOT NULL THEN [1] ELSE [] END |
            SET e.effective_on = date(it.effective_on)
        )

        MERGE (comp)-[r1:ANNOUNCED]->(e)
        SET r1.received_on = date(it.received_on)
        """, batch=events)

        cnt = s.run("MATCH (e:DART_CapitalEvent) RETURN count(e) as c").single()["c"]
        rels = s.run("MATCH ()-[r:ANNOUNCED]->() RETURN count(r) as c").single()["c"]
        print(f"  ✅ [DART_CapitalEvent] 클라우드 Aura 적재 완료: {cnt:,}개 이벤트 ({rels:,}건 ANNOUNCED 연결)")


def main():
    print("\n" + "█"*80)
    print("🚀 [DART-Trace] 3,988개 상장사 마스터 및 5대 자본이벤트 클라우드 병합 시작")
    print("█"*80)

    step1_load_3988_master_companies()
    step2_load_313_capital_events()

    # 최종 상태 검증
    print("\n" + "="*80)
    print("📊 [클라우드 Neo4j Aura 최종 상태]")
    print("="*80)
    with driver.session() as s:
        labels = s.run("CALL db.labels()").values()
        for l in labels:
            lbl = l[0]
            cnt = s.run(f"MATCH (n:`{lbl}`) RETURN count(n) as c").single()["c"]
            print(f"  - :{lbl:25} {cnt:>8,}개")
        rels = s.run("CALL db.relationshipTypes()").values()
        for r in rels:
            rt = r[0]
            cnt = s.run(f"MATCH ()-[rel:`{rt}`]->() RETURN count(rel) as c").single()["c"]
            print(f"  - [:{rt:23}] {cnt:>8,}건")
    driver.close()
    print("\n🏆 [성공] 3,988개 상장사 마스터 및 자본이벤트 클라우드 병합 완료!")


if __name__ == "__main__":
    main()
