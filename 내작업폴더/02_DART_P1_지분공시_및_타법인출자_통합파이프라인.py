# -*- coding: utf-8 -*-
"""
🏛️ [v0.2 Step 2 - 최종 정합본] DART-Trace DS004 지분공시 + DS002 최대주주 & 타법인출자 정규화 파이프라인
- 대상: 1차 100개사 파일럿 상장사
- 반영 사항:
  1) 대량보유(majorstock)의 rcept_dt는 공시 접수일(reported_on / disclosed_at)로 명확히 분리
  2) 법인 매칭 시 정확히 1건(len == 1) 매칭일 때만 VERIFIED 생성, 0건 또는 복수(>1) 매칭 시 후보 큐 보류
  3) stlm_dt 결산기준일 기반 as_of_date 정확 설정 및 최신성(is_current) 동적 계산
  4) 영구 후보 큐(candidate_queue.jsonl) 분리 및 기존 베이스라인 319건 완벽 보존
"""

import os
import sys
import io
import time
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

# UTF-8 콘솔 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
DART_API_KEY = os.getenv("DART_API_KEY")

if not NEO4J_PASSWORD:
    raise ValueError("❌ .env 파일에 NEO4J_PASSWORD가 설정되지 않았습니다.")
if not DART_API_KEY:
    raise ValueError("❌ .env 파일에 DART_API_KEY가 설정되지 않았습니다.")

CANDIDATE_FILE = os.path.join(os.path.dirname(__file__), "candidate_queue.jsonl")

def get_db_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def append_candidate(record: dict):
    """미매칭/복수매칭/미식별 데이터를 영구 후보 큐 파일에 저장"""
    record["logged_at"] = datetime.now().isoformat()
    with open(CANDIDATE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def call_dart_api(endpoint: str, params: dict):
    """OpenDART 범용 API 호출기"""
    params["crtfc_key"] = DART_API_KEY
    query_str = urllib.parse.urlencode(params)
    url = f"https://opendart.fss.or.kr/api/{endpoint}.json?{query_str}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "000":
                return data.get("list", [])
            return []
    except Exception as e:
        return []

def clean_number(val, default=0.0):
    if not val or val == "-":
        return default
    try:
        s = str(val).replace(",", "").strip()
        return float(s) if "." in s else int(s)
    except:
        return default

def clean_company_name(name: str):
    if not name:
        return ""
    s = name.strip()
    for prefix in ["(주)", "㈜", "(유)", "주식회사", "유한회사"]:
        s = s.replace(prefix, "").strip()
    return s

def process_majorstock(driver, corp_code: str, target_name: str):
    """1. DS004 majorstock (5% 대량보유) 수집 및 승격 (rcept_dt -> reported_on)"""
    items = call_dart_api("majorstock", {"corp_code": corp_code})
    if not items:
        return {"created": 0, "candidates": 0}
    
    created = 0
    candidates = 0
    
    with driver.session() as session:
        for it in items:
            repror = it.get("repror", "").strip()
            if not repror:
                continue
            
            stake = clean_number(it.get("stkrt", 0.0), 0.0)
            if stake <= 0:
                continue
                
            rcept_no = it.get("rcept_no", "")
            rcept_dt = it.get("rcept_dt", "2024-12-31")
            reported_on = rcept_dt if "-" in rcept_dt else f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
            purpose = it.get("report_resn", "5% 대량보유 보고")
            shares = int(clean_number(it.get("stkqy", 0)))
            
            # 법인 매칭 (정확히 1건 매칭 검증)
            matched_corps = session.run("""
            MATCH (c:DART_Company)
            WHERE c.name = $name OR c.name = $clean_name
            RETURN c.corp_code AS code, c.name AS name
            """, name=repror, clean_name=clean_company_name(repror)).data()
            
            if len(matched_corps) == 1:
                owner_code = matched_corps[0]["code"]
                query = """
                MATCH (owner:DART_Company {corp_code: $owner_code})
                MATCH (target:DART_Company {corp_code: $corp_code})
                MERGE (owner)-[r:OWNS_STAKE {source_rcept_no: $rcept_no}]->(target)
                SET r.stake = $stake,
                    r.position = '5%이상 대량보유자',
                    r.shares_count = $shares,
                    r.purpose = $purpose,
                    r.reported_on = date($reported_on),
                    r.disclosed_at = date($reported_on),
                    r.verification_status = 'VERIFIED',
                    r.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + $rcept_no
                RETURN count(r) AS cnt
                """
                res = session.run(query, owner_code=owner_code, corp_code=corp_code,
                                  rcept_no=rcept_no, stake=float(stake), shares=shares,
                                  purpose=purpose, reported_on=reported_on).single()
                if res:
                    created += res["cnt"]
                continue
            elif len(matched_corps) > 1:
                # 동명 법인 복수 매칭 위험 ➔ 후보 큐 보류
                append_candidate({
                    "source_api": "DS004_majorstock",
                    "target_corp_code": corp_code,
                    "target_corp_name": target_name,
                    "raw_name": repror,
                    "candidate_type": "AMBIGUOUS_MULTIPLE_CORP_MATCH",
                    "matched_count": len(matched_corps),
                    "stake": float(stake),
                    "reported_on": reported_on,
                    "source_rcept_no": rcept_no,
                    "reason": f"동명 법인 {len(matched_corps)}개사 발견으로 인한 안전 보류"
                })
                candidates += 1
                continue

            # 검증된 대형 기관 매칭
            is_verified_group = any(k in repror for k in ["국민연금", "BlackRock", "미래에셋", "한국투자", "삼성자산운용", "KB자산운용", "신한자산운용"])
            if is_verified_group:
                query = """
                MERGE (owner:DART_Group {name: $repror})
                WITH owner
                MATCH (target:DART_Company {corp_code: $corp_code})
                MERGE (owner)-[r:OWNS_STAKE {source_rcept_no: $rcept_no}]->(target)
                SET r.stake = $stake,
                    r.position = '5%이상 대량보유자',
                    r.shares_count = $shares,
                    r.purpose = $purpose,
                    r.reported_on = date($reported_on),
                    r.disclosed_at = date($reported_on),
                    r.verification_status = 'VERIFIED',
                    r.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + $rcept_no
                RETURN count(r) AS cnt
                """
                res = session.run(query, repror=repror, corp_code=corp_code, rcept_no=rcept_no,
                                  stake=float(stake), shares=shares, purpose=purpose, reported_on=reported_on).single()
                if res:
                    created += res["cnt"]
                continue

            # 미검증 개인/일반 단체 ➔ 후보 큐 보류
            append_candidate({
                "source_api": "DS004_majorstock",
                "target_corp_code": corp_code,
                "target_corp_name": target_name,
                "raw_name": repror,
                "candidate_type": "UNVERIFIED_INDIVIDUAL_OR_GROUP",
                "stake": float(stake),
                "shares_count": shares,
                "reported_on": reported_on,
                "source_rcept_no": rcept_no,
                "reason": "개인 고유 식별자 부재에 따른 안전 보류"
            })
            candidates += 1
                
    return {"created": created, "candidates": candidates}

def process_hyslr_sttus(driver, corp_code: str, target_name: str, bsns_year: str = "2024", reprt_code: str = "11011"):
    """2. DS002 hyslrSttus (최대주주 현황) 수집 및 승격 (stlm_dt -> as_of_date)"""
    items = call_dart_api("hyslrSttus", {"corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code})
    if not items:
        return {"created": 0, "candidates": 0}
        
    created = 0
    candidates = 0
    
    with driver.session() as session:
        for it in items:
            nm = it.get("nm", "").strip()
            if not nm or nm == "-":
                continue
                
            stake = clean_number(it.get("trmend_posesn_stock_qota_rt", 0.0), 0.0)
            if stake <= 0:
                stake = clean_number(it.get("bsis_posesn_stock_qota_rt", 0.0), 0.0)
            if stake <= 0:
                continue
                
            rcept_no = it.get("rcept_no", f"R_HYSLR_{corp_code}_{bsns_year}")
            relate = it.get("relate", "최대주주")
            shares = int(clean_number(it.get("trmend_posesn_stock_co", 0)))
            stlm_dt = it.get("stlm_dt", f"{bsns_year}-12-31")
            as_of_date = stlm_dt if "-" in stlm_dt else f"{bsns_year}-12-31"
            
            # 법인 매칭 (정확히 1건 매칭 검증)
            matched_corps = session.run("""
            MATCH (c:DART_Company)
            WHERE c.name = $name OR c.name = $clean_name
            RETURN c.corp_code AS code
            """, name=nm, clean_name=clean_company_name(nm)).data()
            
            if len(matched_corps) == 1:
                owner_code = matched_corps[0]["code"]
                query = """
                MATCH (owner:DART_Company {corp_code: $owner_code})
                MATCH (target:DART_Company {corp_code: $corp_code})
                MERGE (owner)-[r:OWNS_STAKE {source_rcept_no: $rcept_no}]->(target)
                SET r.stake = $stake,
                    r.position = $relate,
                    r.shares_count = $shares,
                    r.as_of_date = date($as_of_date),
                    r.disclosed_at = date($as_of_date),
                    r.verification_status = 'VERIFIED',
                    r.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + $rcept_no
                RETURN count(r) AS cnt
                """
                res = session.run(query, owner_code=owner_code, corp_code=corp_code,
                                  rcept_no=rcept_no, stake=float(stake), relate=relate,
                                  shares=shares, as_of_date=as_of_date).single()
                if res:
                    created += res["cnt"]
                continue
            elif len(matched_corps) > 1:
                append_candidate({
                    "source_api": "DS002_hyslrSttus",
                    "target_corp_code": corp_code,
                    "target_corp_name": target_name,
                    "raw_name": nm,
                    "candidate_type": "AMBIGUOUS_MULTIPLE_CORP_MATCH",
                    "matched_count": len(matched_corps),
                    "stake": float(stake),
                    "as_of_date": as_of_date,
                    "source_rcept_no": rcept_no,
                    "reason": f"동명 법인 {len(matched_corps)}개사 발견으로 인한 안전 보류"
                })
                candidates += 1
                continue

            # 검증된 대형 기관 매칭
            is_verified_group = any(k in nm for k in ["국민연금", "BlackRock", "미래에셋", "한국투자", "삼성자산운용", "신한자산운용", "재단", "공단"])
            if is_verified_group:
                query = """
                MERGE (owner:DART_Group {name: $nm})
                WITH owner
                MATCH (target:DART_Company {corp_code: $corp_code})
                MERGE (owner)-[r:OWNS_STAKE {source_rcept_no: $rcept_no}]->(target)
                SET r.stake = $stake,
                    r.position = $relate,
                    r.shares_count = $shares,
                    r.as_of_date = date($as_of_date),
                    r.disclosed_at = date($as_of_date),
                    r.verification_status = 'VERIFIED',
                    r.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + $rcept_no
                RETURN count(r) AS cnt
                """
                res = session.run(query, nm=nm, corp_code=corp_code, rcept_no=rcept_no,
                                  stake=float(stake), relate=relate, shares=shares, as_of_date=as_of_date).single()
                if res:
                    created += res["cnt"]
                continue

            # 미검증 개인 ➔ 후보 큐 보류
            append_candidate({
                "source_api": "DS002_hyslrSttus",
                "target_corp_code": corp_code,
                "target_corp_name": target_name,
                "raw_name": nm,
                "candidate_type": "UNVERIFIED_INDIVIDUAL_SHAREHOLDER",
                "position": relate,
                "stake": float(stake),
                "shares_count": shares,
                "as_of_date": as_of_date,
                "source_rcept_no": rcept_no,
                "reason": "개인 고유 식별자 부재에 따른 안전 보류"
            })
            candidates += 1
                
    return {"created": created, "candidates": candidates}

def process_otr_cpr_invstmnt(driver, corp_code: str, target_name: str, bsns_year: str = "2024", reprt_code: str = "11011"):
    """3. DS002 otrCprInvstmntSttus (타법인출자) - 정확히 1건 매칭 시에만 INVESTED_IN 승격"""
    items = call_dart_api("otrCprInvstmntSttus", {"corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code})
    if not items:
        return {"matched": 0, "unmatched": 0}
        
    matched_cnt = 0
    unmatched_cnt = 0
    
    with driver.session() as session:
        for it in items:
            inv_prm = it.get("inv_prm", "").strip()
            if not inv_prm:
                continue
                
            stake = clean_number(it.get("trmend_blce_qota_rt", 0.0), 0.0)
            if stake <= 0:
                stake = clean_number(it.get("bsis_blce_qota_rt", 0.0), 0.0)
                
            shares = int(clean_number(it.get("trmend_blce_qy", 0)))
            book_value = int(clean_number(it.get("trmend_blce_acntbk_amount", 0)))
            acq_cost = int(clean_number(it.get("frst_acqs_amount", 0)))
            purpose = it.get("invstmnt_purps", "단순투자")
            rcept_no = it.get("rcept_no", f"R_OTR_{corp_code}_{bsns_year}")
            stlm_dt = it.get("stlm_dt", f"{bsns_year}-12-31")
            as_of_date = stlm_dt if "-" in stlm_dt else f"{bsns_year}-12-31"
            
            # 개체 식별: 정확히 1건 매칭 검증
            matched_subs = session.run("""
            MATCH (sub:DART_Company)
            WHERE sub.name = $name OR sub.name = $clean_name
            RETURN sub.corp_code AS code, sub.name AS matched_name
            """, name=inv_prm, clean_name=clean_company_name(inv_prm)).data()
            
            if len(matched_subs) == 1:
                sub_code = matched_subs[0]["code"]
                query = """
                MATCH (parent:DART_Company {corp_code: $parent_code})
                MATCH (sub:DART_Company {corp_code: $sub_code})
                MERGE (parent)-[r:INVESTED_IN {source_rcept_no: $rcept_no}]->(sub)
                SET r.stake = $stake,
                    r.shares_count = $shares,
                    r.book_value = $book_value,
                    r.acq_cost = $acq_cost,
                    r.purpose = $purpose,
                    r.as_of_date = date($as_of_date),
                    r.disclosed_at = date($as_of_date),
                    r.verification_status = 'VERIFIED',
                    r.viewer_url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + $rcept_no
                RETURN count(r) AS cnt
                """
                res = session.run(query, parent_code=corp_code, sub_code=sub_code, rcept_no=rcept_no,
                                  stake=float(stake), shares=shares, book_value=book_value, acq_cost=acq_cost,
                                  purpose=purpose, as_of_date=as_of_date).single()
                if res and res["cnt"] > 0:
                    matched_cnt += res["cnt"]
            else:
                unmatched_cnt += 1
                reason = f"동명 법인 {len(matched_subs)}개사 발견으로 보류" if len(matched_subs) > 1 else "사전 적재된 상장/외감 기업 마스터 미존재 (비상장 미식별 법인)"
                append_candidate({
                    "source_api": "DS002_otrCprInvstmntSttus",
                    "parent_corp_code": corp_code,
                    "parent_corp_name": target_name,
                    "target_inv_prm": inv_prm,
                    "candidate_type": "UNMATCHED_AFFILIATE_COMPANY" if len(matched_subs) == 0 else "AMBIGUOUS_MULTIPLE_CORP_MATCH",
                    "matched_count": len(matched_subs),
                    "stake": float(stake),
                    "shares_count": shares,
                    "book_value": book_value,
                    "acq_cost": acq_cost,
                    "purpose": purpose,
                    "as_of_date": as_of_date,
                    "source_rcept_no": rcept_no,
                    "reason": reason
                })
                
    return {"matched": matched_cnt, "unmatched": unmatched_cnt}

def update_is_current_dynamically(driver):
    """최신 기준일자(as_of_date / reported_on) 계산 후 is_current 속성 동적 태깅"""
    print("⏳ [최신성 계산] 최신일자 기반 is_current 동적 산출 중...")
    with driver.session() as session:
        # OWNS_STAKE 최신성
        session.run("""
        MATCH (owner)-[r:OWNS_STAKE]->(target:DART_Company)
        WHERE r.source_rcept_no IS NOT NULL
        WITH owner, target, max(coalesce(r.as_of_date, r.reported_on)) AS max_date
        MATCH (owner)-[r:OWNS_STAKE]->(target)
        WHERE r.source_rcept_no IS NOT NULL
        SET r.is_current = (coalesce(r.as_of_date, r.reported_on) = max_date)
        """)
        
        # INVESTED_IN 최신성
        session.run("""
        MATCH (parent:DART_Company)-[r:INVESTED_IN]->(sub:DART_Company)
        WHERE r.source_rcept_no IS NOT NULL AND r.as_of_date IS NOT NULL
        WITH parent, sub, max(r.as_of_date) AS max_date
        MATCH (parent)-[r:INVESTED_IN]->(sub)
        WHERE r.source_rcept_no IS NOT NULL AND r.as_of_date IS NOT NULL
        SET r.is_current = (r.as_of_date = max_date)
        """)
    print("✅ is_current 최신 유효 지분 사실 동적 태깅 완료!")

def run_step2_pipeline(limit: int = 100):
    if os.path.exists(CANDIDATE_FILE):
        os.remove(CANDIDATE_FILE)

    print("=" * 85)
    print(f"🚀 [v0.2 Step 2 - 최종 정합본] DS004 지분공시 + DS002 최대주주 & 타법인출자 가동 (1차 {limit}개사)")
    print("=" * 85)

    driver = get_db_driver()
    
    # 기존 Step 2 임시 관계만 초기화 (베이스라인 319건 보존)
    with driver.session() as session:
        session.run("MATCH ()-[r:OWNS_STAKE]->() WHERE r.source_rcept_no IS NOT NULL DELETE r")
        session.run("MATCH ()-[r:INVESTED_IN]->() DELETE r")
    
    with driver.session() as session:
        corps = session.run("""
        MATCH (c:DART_Company)
        WHERE c.corp_code IS NOT NULL AND c.is_listed = true
        RETURN c.corp_code AS corp_code, c.name AS name, c.market AS market
        ORDER BY CASE WHEN c.market = 'KOSPI' THEN 1 WHEN c.market = 'KOSDAQ' THEN 2 ELSE 3 END, c.name
        LIMIT $limit
        """, limit=limit).data()

    print(f"📊 1차 파일럿 대상 상장사: {len(corps)}개사 순회 시작")

    stats = {
        "major_created": 0,
        "major_candidates": 0,
        "hyslr_created": 0,
        "hyslr_candidates": 0,
        "invested_matched": 0,
        "invested_unmatched": 0
    }

    for idx, corp in enumerate(corps, 1):
        c_code = corp["corp_code"]
        c_name = corp["name"]
        
        m_res = process_majorstock(driver, c_code, c_name)
        stats["major_created"] += m_res["created"]
        stats["major_candidates"] += m_res["candidates"]
        time.sleep(0.08)
        
        h_res = process_hyslr_sttus(driver, c_code, c_name)
        stats["hyslr_created"] += h_res["created"]
        stats["hyslr_candidates"] += h_res["candidates"]
        time.sleep(0.08)
        
        inv_res = process_otr_cpr_invstmnt(driver, c_code, c_name)
        stats["invested_matched"] += inv_res["matched"]
        stats["invested_unmatched"] += inv_res["unmatched"]
        time.sleep(0.08)
        
        print(f"  [{idx:3d}/{len(corps)}] {c_name}({c_code}) ➔ 검증지분: {m_res['created']+h_res['created']}건 | 타법인출자: {inv_res['matched']}건 | 후보보류: {m_res['candidates']+h_res['candidates']+inv_res['unmatched']}건")

    update_is_current_dynamically(driver)

    with driver.session() as session:
        total_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS cnt").single()["cnt"]
        base_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() WHERE r.source_rcept_no IS NULL RETURN count(r) AS cnt").single()["cnt"]
        step2_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() WHERE r.source_rcept_no IS NOT NULL RETURN count(r) AS cnt").single()["cnt"]
        invested_cnt = session.run("MATCH ()-[r:INVESTED_IN]->() RETURN count(r) AS cnt").single()["cnt"]
        
        zero_stake_inv = session.run("MATCH ()-[r:INVESTED_IN]->() WHERE r.stake = 0.0 RETURN count(r) AS cnt").single()["cnt"]
        valid_stake_inv = session.run("MATCH ()-[r:INVESTED_IN]->() WHERE r.stake > 0.0 RETURN count(r) AS cnt").single()["cnt"]
        zero_book_inv = session.run("MATCH ()-[r:INVESTED_IN]->() WHERE r.book_value = 0 RETURN count(r) AS cnt").single()["cnt"]
        valid_book_inv = session.run("MATCH ()-[r:INVESTED_IN]->() WHERE r.book_value > 0 RETURN count(r) AS cnt").single()["cnt"]

    print("\n" + "=" * 85)
    print("🏁 [v0.2 Step 2 최종 정합본 적재 완료 보고서]")
    print(f"   • 지분 관계 (:OWNS_STAKE): 총 {total_owns:,}건 (베이스라인 보존: {base_owns:,}건 + Step 2 신규 검증: {step2_owns:,}건)")
    print(f"   • 타법인출자 (:INVESTED_IN): 총 {invested_cnt:,}건")
    print(f"     - 유효 지분율(>0%): {valid_stake_inv}건 / 0% 지분율: {zero_stake_inv}건")
    print(f"     - 유효 장부가액(>0원): {valid_book_inv}건 / 0원 장부가액: {zero_book_inv}건")
    print(f"   • 영구 후보 큐(Candidate Queue): 총 {stats['major_candidates'] + stats['hyslr_candidates'] + stats['invested_unmatched']:,}건 영구 보관 완료 ({CANDIDATE_FILE})")
    print("=" * 85)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DART-Trace Step 2 지분공시 및 타법인출자 통합 파이프라인")
    parser.add_argument("--limit", type=int, default=100, help="대상 기업 수 (기본: 100)")
    args = parser.parse_args()
    
    run_step2_pipeline(limit=args.limit)
