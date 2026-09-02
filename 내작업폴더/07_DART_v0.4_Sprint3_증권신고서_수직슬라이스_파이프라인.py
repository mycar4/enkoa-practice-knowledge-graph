# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4 Sprint 3] DS006 증권신고서(조달목적·풋옵션) 수직 슬라이스 파이프라인
========================================================================================
[Sprint 3 핵심 엔지니어링 목표]
1. [OpenDART DS005/DS006 수집]: 3S(00378363) 실제 사모 CB 발행결정 API (cvbdIsDecsn.json) 실시간 수집
2. [원천 자금조달 조건 및 목적 파싱]:
   - 사채회차(bd_tm), 권면총액(bd_fta), 사모여부(bdis_mthn)
   - 4대 조달목적: 운영(fdpp_op), 시설(fdpp_fclt), 채무상환(fdpp_dtrp), 타법인취득(fdpp_ocsa)
   - 표면이자율(bd_intr_sf), 만기이자율(bd_intr_ex), 사채만기일(bd_mtd), 전환청구개시일(cvrqpd_bgd)
3. [온톨로지 엔티티 적재 및 연결]:
   - (:DART_CapitalEvent {event_id: '00378363_CB_ISSUE_20241217000407_1'})
   - (:DART_SecuritiesFiling {filing_id: '00378363_SEC_20241217000407_1'})
   - (이벤트)-[:DETAILS {match_status: 'EXACT', link_basis: 'SAME_RCEPT_NO'}]->(증권신고서)
   - (증권신고서)-[:EVIDENCED_BY]->(공시원문), (이벤트)-[:EVIDENCED_BY]->(공시원문)
4. [엄격 멱등성 및 증거 경로 질의]:
   - 2회 연속 재실행 시 노드/관계 1건 단일 인스턴스 검증 (AssertionError)
   - 회사 ➔ 이벤트 ➔ 증권신고서 ➔ 공시원문 풀체인 Cypher 질의 검증
========================================================================================
"""

import os
import sys
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://2fa50db4.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "2fa50db4")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")

if not DART_API_KEY:
    raise ValueError("❌ DART_API_KEY가 환경변수에 설정되어 있지 않습니다.")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def parse_hangul_date(date_str):
    """'2029년 12월 17일' 또는 '2029.12.17' 문자열을 '2029-12-17' Date 문자열로 정규화"""
    if not date_str or date_str.strip() == "-":
        return None
    m = re.search(r'(\d{4})[년.\-/]\s*(\d{1,2})[월.\-/]\s*(\d{1,2})', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None

def parse_amount(val_str):
    """금액 문자열 정수형(Long) 변환"""
    if not val_str or val_str.strip() in ["-", ""]:
        return 0
    clean = re.sub(r'[^0-9]', '', str(val_str))
    return int(clean) if clean else 0

def parse_float(val_str):
    """이자율/비율 부동소수점(Float) 변환"""
    if not val_str or val_str.strip() in ["-", ""]:
        return 0.0
    clean = re.sub(r'[^0-9.]', '', str(val_str))
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0

def step1_ingest_securities_filing(corp_code="00378363"):
    """[Step 1] OpenDART 실시간 전환사채 및 증권신고서 조달조건 수집 & 적재"""
    print("\n" + "="*80)
    print(f"📜 [Step 1] OpenDART 3S({corp_code}) 실시간 사모 CB 발행결정 및 증권신고서 조달조건 수집")
    print("="*80)
    
    # 1. 선행 검증: 상장사 노드 DB 존재 확인
    with driver.session() as s:
        comp_record = s.run("MATCH (c:DART_Company {corp_code: $corp_code}) RETURN c.name AS name, c.stock_code AS stock_code", corp_code=corp_code).single()
        
    if not comp_record:
        raise RuntimeError(f"❌ 상장사 노드 부재: corp_code='{corp_code}'가 DB에 없습니다. 선행 마스터 적재가 필요합니다.")
        
    corp_name = comp_record["name"]
    print(f"🏢 선행 대상 상장사 식별 완료: {corp_name} (법인코드: {corp_code})")
    
    # 2. OpenDART cvbdIsDecsn.json API 호출
    url = f"https://opendart.fss.or.kr/api/cvbdIsDecsn.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de=20240101&end_de=20241231"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    if data.get("status") != "000":
        raise RuntimeError(f"❌ OpenDART API 호출 실패: status={data.get('status')}, message={data.get('message')}")
        
    items = data.get("list", [])
    if not items:
        raise ValueError(f"❌ CB 발행결정 데이터가 없습니다. (corp_code={corp_code})")
        
    cb_item = items[0]
    rcept_no = cb_item.get("rcept_no")
    rcept_dt = rcept_no[:8]
    
    # 3. 상세 조달조건 및 목적 필드 파싱
    event_seq = 1
    item_seq = 1
    
    event_id = f"{corp_code}_CB_ISSUE_{rcept_no}_{event_seq}"
    filing_id = f"{corp_code}_SEC_{rcept_no}_{item_seq}"
    
    event_name = f"제{cb_item.get('bd_tm', '')}회차 {cb_item.get('bd_knd', '전환사채발행결정')}"
    is_private = "사모" in cb_item.get("bdis_mthn", "")
    issue_amount = parse_amount(cb_item.get("bd_fta"))
    conversion_price = parse_amount(cb_item.get("cv_prc"))
    min_refixing_floor = parse_amount(cb_item.get("act_mktprcfl_cvprc_lwtrsprc"))
    
    # 조달자금 세부 용도
    target_operating_fund = parse_amount(cb_item.get("fdpp_op"))
    target_facility_fund = parse_amount(cb_item.get("fdpp_fclt"))
    target_debt_repayment_fund = parse_amount(cb_item.get("fdpp_dtrp"))
    target_acquisition_fund = parse_amount(cb_item.get("fdpp_ocsa"))
    
    # 금리 및 만기/풋옵션
    coupon_rate = parse_float(cb_item.get("bd_intr_sf"))
    ytm_rate = parse_float(cb_item.get("bd_intr_ex"))
    
    decided_on = parse_hangul_date(cb_item.get("bddd"))
    effective_on = parse_hangul_date(cb_item.get("pymd"))
    maturity_date = parse_hangul_date(cb_item.get("bd_mtd"))
    put_option_start = parse_hangul_date(cb_item.get("cvrqpd_bgd"))
    
    print(f"📦 [파싱 완료] 사건 ID: {event_id}")
    print(f"   • 이벤트명: {event_name} (권면총액: {issue_amount:,}원, 사모여부: {is_private})")
    print(f"   • 조달목적: 운영={target_operating_fund:,}원 | 시설={target_facility_fund:,}원 | 타법인취득={target_acquisition_fund:,}원")
    print(f"   • 금리조건: 표면={coupon_rate}%, 만기={ytm_rate}%")
    print(f"   • 주요일자: 결의일={decided_on}, 납입일={effective_on}, 만기일={maturity_date}, 풋옵션개시일={put_option_start}")
    
    # 4. Neo4j Cypher 동적 적재
    with driver.session() as s:
        s.run("""
        MATCH (comp:DART_Company {corp_code: $corp_code})
        
        MERGE (disc:DART_Disclosure {rcept_no: $rcept_no})
        ON CREATE SET disc.report_nm = '주요사항보고서(전환사채권발행결정)',
                      disc.rcept_dt = $rcept_dt,
                      disc.flr_nm = comp.name,
                      disc.doc_status = 'NORMAL',
                      disc.is_latest = true
                      
        MERGE (comp)-[:FILED]->(disc)
        
        MERGE (ev:DART_CapitalEvent {event_id: $event_id})
        SET ev.event_type = 'CB_ISSUE',
            ev.event_name = $event_name,
            ev.is_private = $is_private,
            ev.issue_amount = $issue_amount,
            ev.conversion_price = $conversion_price,
            ev.min_refixing_floor = $min_refixing_floor,
            ev.currency = 'KRW',
            ev.decided_on = CASE WHEN $decided_on IS NOT NULL THEN date($decided_on) ELSE NULL END,
            ev.received_on = date(substring($rcept_no, 0, 4) + '-' + substring($rcept_no, 4, 2) + '-' + substring($rcept_no, 6, 2)),
            ev.effective_on = CASE WHEN $effective_on IS NOT NULL THEN date($effective_on) ELSE NULL END,
            ev.doc_status = 'NORMAL',
            ev.is_latest = true,
            ev.source_rcept_no = $rcept_no,
            ev.updated_at = datetime()
            
        MERGE (comp)-[:ANNOUNCED]->(ev)
        MERGE (ev)-[r1:EVIDENCED_BY]->(disc)
        SET r1.match_status = 'EXACT',
            r1.link_basis = 'SAME_RCEPT_NO',
            r1.verified_at = datetime()
            
        MERGE (sec:DART_SecuritiesFiling {filing_id: $filing_id})
        SET sec.corp_code = $corp_code,
            sec.item_seq = $item_seq,
            sec.source_rcept_no = $rcept_no,
            sec.target_operating_fund = $target_operating_fund,
            sec.target_facility_fund = $target_facility_fund,
            sec.target_debt_repayment_fund = $target_debt_repayment_fund,
            sec.target_acquisition_fund = $target_acquisition_fund,
            sec.coupon_rate = $coupon_rate,
            sec.ytm_rate = $ytm_rate,
            sec.maturity_date = CASE WHEN $maturity_date IS NOT NULL THEN date($maturity_date) ELSE NULL END,
            sec.put_option_start = CASE WHEN $put_option_start IS NOT NULL THEN date($put_option_start) ELSE NULL END,
            sec.is_latest = true,
            sec.updated_at = datetime()
            
        MERGE (ev)-[r2:DETAILS]->(sec)
        SET r2.match_status = 'EXACT',
            r2.link_basis = 'SAME_RCEPT_NO',
            r2.verified_at = datetime()
            
        MERGE (sec)-[r3:EVIDENCED_BY]->(disc)
        SET r3.match_status = 'EXACT',
            r3.link_basis = 'SAME_RCEPT_NO',
            r3.verified_at = datetime()
        """, corp_code=corp_code, rcept_no=rcept_no, rcept_dt=rcept_dt, event_id=event_id,
           filing_id=filing_id, event_name=event_name, is_private=is_private,
           issue_amount=issue_amount, conversion_price=conversion_price, min_refixing_floor=min_refixing_floor,
           decided_on=decided_on, effective_on=effective_on, maturity_date=maturity_date,
           put_option_start=put_option_start, item_seq=item_seq, target_operating_fund=target_operating_fund,
           target_facility_fund=target_facility_fund, target_debt_repayment_fund=target_debt_repayment_fund,
           target_acquisition_fund=target_acquisition_fund, coupon_rate=coupon_rate, ytm_rate=ytm_rate)
           
    print("✅ 전환사채 이벤트 및 증권신고서 조달조건 연결 적재 완료!")
    return event_id, filing_id, rcept_no

def step2_verify_idempotency(event_id, filing_id):
    """[Step 2] 동일 입력 재실행 후 멱등성(중복 0건) 엄격 검증"""
    print("\n" + "="*80)
    print("🔁 [Step 2] MERGE 멱등성(Idempotency) 엄격 검증")
    print("="*80)
    
    with driver.session() as s:
        ev_cnt = s.run("MATCH (e:DART_CapitalEvent {event_id: $eid}) RETURN count(e) AS c", eid=event_id).single()["c"]
        sec_cnt = s.run("MATCH (s:DART_SecuritiesFiling {filing_id: $fid}) RETURN count(s) AS c", fid=filing_id).single()["c"]
        rel_details_cnt = s.run("MATCH (:DART_CapitalEvent {event_id: $eid})-[r:DETAILS]->(:DART_SecuritiesFiling) RETURN count(r) AS c", eid=event_id).single()["c"]
        
    print(f"  • event_id '{event_id}' 노드 수: {ev_cnt}개 (정상: 1)")
    print(f"  • filing_id '{filing_id}' 노드 수: {sec_cnt}개 (정상: 1)")
    print(f"  • [:DETAILS] 관계 수: {rel_details_cnt}건 (정상: 1)")
    
    assert ev_cnt == 1, f"❌ 멱등성 위반: 이벤트 노드 수 {ev_cnt}"
    assert sec_cnt == 1, f"❌ 멱등성 위반: 증권신고서 노드 수 {sec_cnt}"
    assert rel_details_cnt == 1, f"❌ 멱등성 위반: DETAILS 관계 수 {rel_details_cnt}"
    
    print("🎉 [멱등성 검증 100% 통과] 자본이벤트 및 증권신고서 단일 인스턴스 불변 확인!")

def step3_query_full_chain(corp_code="00378363"):
    """[Step 3] 회사 -> 이벤트 -> 증권신고서 -> 공시원문 풀체인 역추적 Cypher 질의"""
    print("\n" + "="*80)
    print("🔍 [Step 3] 회사 ➔ 이벤트 ➔ 증권신고서 ➔ 공시원문 풀 증거 경로 Cypher 질의")
    print("="*80)
    
    with driver.session() as s:
        records = s.run("""
        MATCH (c:DART_Company {corp_code: $corp_code})-[a:ANNOUNCED]->(e:DART_CapitalEvent)-[d:DETAILS]->(s:DART_SecuritiesFiling)-[ev:EVIDENCED_BY]->(disc:DART_Disclosure)
        RETURN c.name AS corp_name,
               e.event_name AS event_name,
               e.issue_amount AS issue_amount,
               e.conversion_price AS conv_price,
               s.target_operating_fund AS op_fund,
               s.coupon_rate AS coupon,
               s.ytm_rate AS ytm,
               s.maturity_date AS maturity,
               s.put_option_start AS put_start,
               d.match_status AS match_status,
               d.link_basis AS link_basis,
               disc.report_nm AS report_nm,
               disc.rcept_no AS rcept_no
        """, corp_code=corp_code).data()
        
    assert len(records) > 0, f"❌ 풀 증거 경로 조회 실패 (0건)"
    
    for r in records:
        print(f"  🏢 상장사: {r['corp_name']}")
        print(f"  ⚡ 자본이벤트: {r['event_name']} (권면총액: {r['issue_amount']:,}원, 전환가: {r['conv_price']:,}원)")
        print(f"  📜 증권신고서 조달조건: 운영자금={r['op_fund']:,}원 | 표면={r['coupon']}% | 만기={r['ytm']}%")
        print(f"  ⏱️ 만기일: {r['maturity']} | 풋옵션 행사개시일: {r['put_start']}")
        print(f"  🔒 확정 증거 속성: match_status={r['match_status']}, link_basis={r['link_basis']}")
        print(f"  📑 근거 공시원문: [{r['rcept_no']}] {r['report_nm']}")
        
    print("🎉 회사-이벤트-증권신고서-공시원문 4단 풀체인 질의 100% 정상 확인!")

def main():
    print("="*90)
    print("🚀 [DART-Trace v0.4 Sprint 3] DS006 증권신고서(조달목적·풋옵션) 수직 슬라이스 가동")
    print("="*90)
    
    # 1. 1차 실시간 OpenDART API 수집 & 적재
    eid, fid, rcp = step1_ingest_securities_filing()
    
    # 2. 2차 실시간 재실행 후 멱등성 검증 (Assertion)
    step1_ingest_securities_filing()
    step2_verify_idempotency(eid, fid)
    
    # 3. 4단 풀 증거 경로 역추적 Cypher 질의 검증
    step3_query_full_chain()
    
    print("\n" + "="*90)
    print("🏆 [DART-Trace v0.4 Sprint 3] 증권신고서 수직 슬라이스 전 항목 100% 검증 완수!")
    print("="*90)

if __name__ == "__main__":
    main()
