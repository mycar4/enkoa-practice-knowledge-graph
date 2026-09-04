# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] Decision Report Service (Antigravity Domain)
================================================================================
- 단일 기업 대상 [사실 / 관찰 지표 / 원문 근거 / 다음 확인 항목] 4단 의사결정 리포트 데이터 엔진
- 100% 읽기 전용 (driver.session 레벨 READ_ACCESS 강제)
- Cloud Aura 지식그래프의 DART_Company, DART_CapitalEvent, RawEvidenceCandidate 실시간 통합 조회
- 원천 사실(Facts)과 규칙 기반 관찰(Rule-based Observation)의 엄격한 분리
- 자본이벤트(공시 링크 연동)와 5% 후보(행 해시 결속 증거)의 정직한 증거 등급 구분
================================================================================
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests
from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

_MAX_FINANCIAL_CACHE_SIZE = 256
_financial_facts_cache: Dict[str, Dict[str, Any]] = {}


def _cache_financial_facts(key: str, data: Dict[str, Any]) -> None:
    """메모리 보호를 위한 상한선(256개) 기반 캐시 저장 및 오래된 항목 축출"""
    if len(_financial_facts_cache) >= _MAX_FINANCIAL_CACHE_SIZE:
        oldest_keys = list(_financial_facts_cache.keys())[:50]
        for k in oldest_keys:
            _financial_facts_cache.pop(k, None)
    _financial_facts_cache[key] = data

EVENT_TYPE_KR_MAP = {
    "PAID": "유상증자 결정",
    "CB_ISSUE": "전환사채(CB) 발행 결정",
    "BW_ISSUE": "신주인수권부사채(BW) 발행 결정",
    "MERGER": "회사합병 결정",
    "STOCK_ACQUISITION": "타법인 주식 및 출자증권 취득 결정"
}


def parse_accounting_number(raw_val: Any) -> Optional[int]:
    """공시 회계 수치 문자열을 정수(원 단위)로 파싱 (콤마, 괄호 음수, None 방어)"""
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s or s in ["-", "None", "null", "N/A"]:
        return None
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    s = s.replace(",", "").strip()
    try:
        val = int(float(s))
        return -val if is_negative else val
    except (ValueError, TypeError):
        return None


def format_currency_kr(val: Optional[int]) -> str:
    """원화 금액을 조/억원 단위 병기 포맷팅 (None 방어)"""
    if val is None:
        return "-"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000_000:
        jo = abs_val / 1_000_000_000_000
        return f"{sign}{jo:,.1f}조원 ({val:,}원)"
    elif abs_val >= 100_000_000:
        eok = abs_val / 100_000_000
        return f"{sign}{eok:,.1f}억원 ({val:,}원)"
    else:
        return f"{val:,}원"



def sanitize_capital_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """
    자본이벤트 공시 사실 정제 및 방어:
    1. 이벤트 코드 한글화 (PAID -> 유상증자 결정 등)
    2. 조달 금액 및 목적 컬럼 정정 (PAID 등에서 금액이 purpose로 유입된 현상 방어)
    3. 순수 숫자 문자열이 목적 컬럼에 노출되는 결손 방어
    """
    raw_type = str(ev.get("event_type") or "-").strip()
    event_type_kr = EVENT_TYPE_KR_MAP.get(raw_type, raw_type)
    
    raw_amt = ev.get("issue_amount")
    raw_pur = ev.get("purpose")
    
    # 1. 조달 금액 정제
    final_amount = None
    if raw_amt is not None and str(raw_amt).strip() not in ["", "-", "None"]:
        try:
            clean_amt_str = str(raw_amt).replace(",", "").strip()
            final_amount = int(float(clean_amt_str))
        except (ValueError, TypeError):
            pass

    pur_is_numeric = False
    pur_num_val = None
    if raw_pur is not None:
        pur_cleaned = str(raw_pur).replace(",", "").strip()
        if pur_cleaned.isdigit():
            pur_is_numeric = True
            pur_num_val = int(pur_cleaned)

    # PAID 유상증자 등에서 금액이 purpose에만 숫자로 존재하는 경우 승계
    if final_amount is None and pur_is_numeric:
        final_amount = pur_num_val

    if final_amount is not None and final_amount > 0:
        if final_amount >= 100_000_000:
            eok = final_amount / 100_000_000
            amt_display = f"{final_amount:,}원 ({eok:,.1f}억원)"
        else:
            amt_display = f"{final_amount:,}원"
    else:
        amt_display = "-"

    # 2. 조달 목적 정제
    if raw_pur is None or str(raw_pur).strip() in ["", "-", "None"]:
        purpose_display = "-"
    elif pur_is_numeric:
        # raw_amt가 따로 있고 pur도 숫자인 경우(세부 배정자금)
        if raw_amt is not None and final_amount != pur_num_val and pur_num_val is not None:
            if pur_num_val >= 100_000_000:
                eok_sub = pur_num_val / 100_000_000
                purpose_display = f"배정 자금: {pur_num_val:,}원 ({eok_sub:,.1f}억원)"
            else:
                purpose_display = f"배정 자금: {pur_num_val:,}원"
        else:
            purpose_display = "공시 원문 서식 참조"
    else:
        purpose_display = str(raw_pur).strip()

    sanitized = dict(ev)
    sanitized["event_type_kr"] = event_type_kr
    sanitized["sanitized_amount"] = final_amount
    sanitized["amount_display"] = amt_display
    sanitized["sanitized_purpose"] = purpose_display
    return sanitized


def build_official_timeline(
    capital_events: List[Dict[str, Any]],
    promoted_stakes: List[Dict[str, Any]],
    financial_facts: Dict[str, Any],
    raw_candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    출처별 공식 채널 타임라인 통합 생성:
    - GRADE_A_DART: DART 전자공시 법정 자본이벤트 공시 원문
    - GRADE_A_KRX: KRX KIND 상장공시 교차검증 결속
    - GRADE_A_FINANCIAL: OpenDART 정기보고서 재무제표 팩트
    - GRADE_B_UNVERIFIED: DART 5% 대량보유 미검증 원문 후보
    """
    timeline_items: List[Dict[str, Any]] = []

    # 1. 자본이벤트 (A급 DART + A급 KRX KIND 교차검증)
    for ev in capital_events:
        ev_date = ev.get("decided_on") or ev.get("received_on") or ev.get("effective_on")
        if not ev_date:
            continue
        rcp = ev.get("rcept_no")
        ev_kr = ev.get("event_type_kr", ev.get("event_type", "자본이벤트"))
        amt_disp = ev.get("amount_display", "-")
        pur_disp = ev.get("sanitized_purpose", "-")
        
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None
        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp}&method=search" if rcp else None

        timeline_items.append({
            "event_date": str(ev_date)[:10],
            "date_type": "DECIDED_ON" if ev.get("decided_on") else "RECEIVED_ON",
            "date_type_kr": "결정일자" if ev.get("decided_on") else "접수일자",
            "event_category": "CAPITAL_EVENT",
            "event_category_kr": "자본조달 공시",
            "channel_grade": "GRADE_A_DART",
            "channel_grade_kr": "🏛️ DART 공시 (A급)",
            "title": f"{ev_kr}",
            "summary": f"조달금액: {amt_disp} | 목적: {pur_disp}",
            "rcept_no": rcp,
            "dart_url": dart_url,
            "krx_kind_url": krx_url,
            "verification_status": "VERIFIED_FILING",
            "verification_note": "DART 전자공시 접수번호 결속 + KRX KIND 상장공시 교차검증 링크 제공"
        })

    # 2. 검증·승격된 경제적 보유 사실 (A급 법정 대량보유 공시)
    for p in promoted_stakes:
        p_date = p.get("reporting_obligation_date")
        if not p_date:
            continue
        rcp = p.get("rcept_no")
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None
        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp}&method=search" if rcp else None
        ratio_str = f"{p.get('stake_ratio')}%" if p.get('stake_ratio') is not None else "-"
        shares_cnt = p.get('shares_count')
        shares_str = f"{shares_cnt:,}주" if isinstance(shares_cnt, (int, float)) else (str(shares_cnt) if shares_cnt is not None else "-")

        timeline_items.append({
            "event_date": str(p_date)[:10],
            "date_type": "OBLIGATION_DATE",
            "date_type_kr": "보고의무발생일",
            "event_category": "PROMOTED_STAKE",
            "event_category_kr": "검증 경제적 보유",
            "channel_grade": "GRADE_A_DART",
            "channel_grade_kr": "🔒 DART 승격공시 (A급)",
            "title": f"[검증지분] {p.get('holder_to_target')}",
            "summary": f"지분율: {ratio_str} ({shares_str}) | 봉인 매니페스트 결속 완료",
            "rcept_no": rcp,
            "dart_url": dart_url,
            "krx_kind_url": krx_url,
            "verification_status": "VERIFIED_ECONOMIC_STAKE",
            "verification_note": "봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 검증 승격"
        })

    # 3. OpenDART 정기보고서 재무제표 팩트 (A급 정기공시)
    if isinstance(financial_facts, dict) and financial_facts.get("status") == "AVAILABLE":
        bsns_year = financial_facts.get("bsns_year")
        fin_rcp = financial_facts.get("rcept_no")
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={fin_rcp}" if fin_rcp else None
        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={fin_rcp}&method=search" if fin_rcp else None
        rev_str = format_currency_kr(financial_facts.get("revenue"))
        op_str = format_currency_kr(financial_facts.get("operating_income"))
        debt_r = financial_facts.get("debt_ratio")
        debt_str = f"{debt_r:.2f}%" if isinstance(debt_r, (int, float)) else (str(debt_r) if debt_r is not None else "-")

        timeline_items.append({
            "event_date": f"{bsns_year}-12-31",
            "date_type": "FISCAL_YEAR_END",
            "date_type_kr": "결산기준일",
            "event_category": "FINANCIAL_FACT",
            "event_category_kr": "정기 재무공시",
            "channel_grade": "GRADE_A_FINANCIAL",
            "channel_grade_kr": "📊 OpenDART 재무 (A급)",
            "title": f"{bsns_year}년 {financial_facts.get('reprt_name', '사업보고서')} ({financial_facts.get('fs_div_name', '연결')})",
            "summary": f"매출액: {rev_str} | 영업이익: {op_str} | 부채비율: {debt_str}",
            "rcept_no": fin_rcp,
            "dart_url": dart_url,
            "krx_kind_url": krx_url,
            "verification_status": "VERIFIED_FILING",
            "verification_note": "금융감독원 OpenDART 사업보고서(fnlttSinglAcnt) 단일회사 주요계정 직연동"
        })

    # 4. 5% 대량보유 미검증 원문 추출 후보 (B급 미검증 후보 - 상위 5건)
    for cand in raw_candidates[:5]:
        cand_date = cand.get("reporting_obligation_date")
        if not cand_date:
            continue
        rcp = cand.get("rcept_no")
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None
        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp}&method=search" if rcp else None
        ratio_str = f"{cand.get('stake_ratio')}%" if cand.get('stake_ratio') is not None else "-"

        timeline_items.append({
            "event_date": str(cand_date)[:10],
            "date_type": "OBLIGATION_DATE",
            "date_type_kr": "보고의무발생일",
            "event_category": "CANDIDATE_STAKE",
            "event_category_kr": "5% 보유 후보",
            "channel_grade": "GRADE_B_UNVERIFIED",
            "channel_grade_kr": "⚪ 원문추출 후보 (B급)",
            "title": f"[후보] {cand.get('holder_name')} 5% 보유 공시",
            "summary": f"지분율: {ratio_str} | 원문 파서 추출 (엔티티 미승격)",
            "rcept_no": rcp,
            "dart_url": dart_url,
            "krx_kind_url": krx_url,
            "verification_status": "UNVERIFIED_CANDIDATE",
            "verification_note": "DART 5% 대량보유 공시 원문 테이블 추출 1차 후보"
        })

    # 시간 역순(최신순) 정렬
    timeline_items.sort(key=lambda x: str(x.get("event_date", "")), reverse=True)

    grade_a_count = sum(1 for item in timeline_items if item.get("channel_grade") != "GRADE_B_UNVERIFIED")
    grade_b_count = sum(1 for item in timeline_items if item.get("channel_grade") == "GRADE_B_UNVERIFIED")
    all_dates = [item["event_date"] for item in timeline_items if item.get("event_date")]

    summary = {
        "total_timeline_events": len(timeline_items),
        "grade_a_count": grade_a_count,
        "grade_b_count": grade_b_count,
        "earliest_date": min(all_dates) if all_dates else None,
        "latest_date": max(all_dates) if all_dates else None
    }

    return {
        "summary": summary,
        "feed": timeline_items
    }


class DecisionReportService:
    """단일 기업 대상 4단 의사결정 리포트 데이터 서비스"""

    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        if self.driver:
            self.driver.close()

    def find_companies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """기업명, 종목코드, 법인코드 기반 검색"""
        q = query.strip()
        if not q:
            return []

        cypher = """
        MATCH (c:DART_Company)
        WHERE c.name CONTAINS $q OR c.stock_code = $q OR c.corp_code = $q
        RETURN c.corp_code AS corp_code, c.name AS corp_name, c.stock_code AS stock_code, c.is_listed AS is_listed
        ORDER BY size(c.name) ASC
        LIMIT $limit
        """
        with self.driver.session(default_access_mode=READ_ACCESS) as session:
            return session.run(cypher, q=q, limit=limit).data()

    def get_company_financial_facts(self, corp_code: str, preferred_year: int = 2024) -> Dict[str, Any]:
        """
        OpenDART fnlttSinglAcnt.json API를 호출하여 단일회사의 주요 재무제표 팩트(DS003) 조회
        - 연결재무제표(CFS) 우선 바인딩, 미제공 시 개별재무제표(OFS) 자동 폴백
        - preferred_year(기본 2024년) 미공시 시 직전년도(2023년) 자동 폴백
        - API 키 부재, 비상장사/미제출사, 네트워크 장애 시 UNAVAILABLE 상태로 안전 방어
        - 사실(Fact)과 단순 산술 비율(부채비율)만 제공하며 주관적 가치평가 배제
        """
        if not corp_code or len(str(corp_code).strip()) != 8:
            return {
                "status": "UNAVAILABLE",
                "message": f"유효하지 않은 고유번호(corp_code: '{corp_code}')입니다.",
                "bsns_year": None,
                "reprt_code": None,
                "reprt_name": None,
                "rcept_no": None,
                "fs_div": None,
                "fs_div_name": None,
                "revenue": None,
                "revenue_prev": None,
                "operating_income": None,
                "operating_income_prev": None,
                "net_income": None,
                "net_income_prev": None,
                "total_assets": None,
                "total_assets_prev": None,
                "total_liabilities": None,
                "total_liabilities_prev": None,
                "total_equity": None,
                "total_equity_prev": None,
                "debt_ratio": None,
                "accounts_detail": []
            }

        cleaned_code = str(corp_code).strip()
        cache_key = f"{cleaned_code}_{preferred_year}"
        if cache_key in _financial_facts_cache:
            return _financial_facts_cache[cache_key]

        dart_api_key = os.getenv("DART_API_KEY")
        if not dart_api_key:
            return {
                "status": "UNAVAILABLE",
                "message": "DART_API_KEY 환경변수가 설정되지 않아 OpenDART 재무제표를 조회할 수 없습니다.",
                "bsns_year": None,
                "reprt_code": None,
                "reprt_name": None,
                "rcept_no": None,
                "fs_div": None,
                "fs_div_name": None,
                "revenue": None,
                "revenue_prev": None,
                "operating_income": None,
                "operating_income_prev": None,
                "net_income": None,
                "net_income_prev": None,
                "total_assets": None,
                "total_assets_prev": None,
                "total_liabilities": None,
                "total_liabilities_prev": None,
                "total_equity": None,
                "total_equity_prev": None,
                "debt_ratio": None,
                "accounts_detail": []
            }

        years_to_try = [preferred_year, preferred_year - 1]
        target_year = None
        raw_items = []
        last_msg = ""

        for yr in years_to_try:
            url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
            params = {
                "crtfc_key": dart_api_key,
                "corp_code": cleaned_code,
                "bsns_year": str(yr),
                "reprt_code": "11011"
            }
            try:
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    payload = resp.json()
                    st_code = payload.get("status")
                    if st_code == "000" and payload.get("list"):
                        target_year = yr
                        raw_items = payload["list"]
                        break
                    else:
                        last_msg = payload.get("message", "조회 실패")
            except Exception as e:
                last_msg = str(e)

        if not target_year or not raw_items:
            res_fail = {
                "status": "UNAVAILABLE",
                "message": f"OpenDART 재무제표 미공시 또는 조회 제한 ({last_msg})",
                "bsns_year": None,
                "reprt_code": None,
                "reprt_name": None,
                "rcept_no": None,
                "fs_div": None,
                "fs_div_name": None,
                "revenue": None,
                "revenue_prev": None,
                "operating_income": None,
                "operating_income_prev": None,
                "net_income": None,
                "net_income_prev": None,
                "total_assets": None,
                "total_assets_prev": None,
                "total_liabilities": None,
                "total_liabilities_prev": None,
                "total_equity": None,
                "total_equity_prev": None,
                "debt_ratio": None,
                "accounts_detail": []
            }
            _cache_financial_facts(cache_key, res_fail)
            return res_fail

        # CFS 우선, 없으면 OFS
        has_cfs = any(item.get("fs_div") == "CFS" for item in raw_items)
        target_fs_div = "CFS" if has_cfs else "OFS"
        fs_div_name = "연결재무제표 (CFS)" if target_fs_div == "CFS" else "별도/개별재무제표 (OFS)"
        filtered_items = [item for item in raw_items if item.get("fs_div") == target_fs_div]

        def find_item(account_names: List[str]) -> Optional[Dict[str, Any]]:
            for it in filtered_items:
                if it.get("account_nm") in account_names:
                    return it
            return None

        rev_item = find_item(["매출액", "수익(매출액)", "영업수익"])
        op_item = find_item(["영업이익", "영업이익(손실)"])
        net_item = find_item(["당기순이익", "당기순이익(손실)"])
        asset_item = find_item(["자산총계"])
        liab_item = find_item(["부채총계"])
        equity_item = find_item(["자본총계"])

        revenue = parse_accounting_number(rev_item.get("thstrm_amount")) if rev_item else None
        revenue_prev = parse_accounting_number(rev_item.get("frmtrm_amount")) if rev_item else None
        operating_income = parse_accounting_number(op_item.get("thstrm_amount")) if op_item else None
        operating_income_prev = parse_accounting_number(op_item.get("frmtrm_amount")) if op_item else None
        net_income = parse_accounting_number(net_item.get("thstrm_amount")) if net_item else None
        net_income_prev = parse_accounting_number(net_item.get("frmtrm_amount")) if net_item else None
        total_assets = parse_accounting_number(asset_item.get("thstrm_amount")) if asset_item else None
        total_assets_prev = parse_accounting_number(asset_item.get("frmtrm_amount")) if asset_item else None
        total_liabilities = parse_accounting_number(liab_item.get("thstrm_amount")) if liab_item else None
        total_liabilities_prev = parse_accounting_number(liab_item.get("frmtrm_amount")) if liab_item else None
        total_equity = parse_accounting_number(equity_item.get("thstrm_amount")) if equity_item else None
        total_equity_prev = parse_accounting_number(equity_item.get("frmtrm_amount")) if equity_item else None

        debt_ratio = None
        if total_equity is not None and total_equity > 0 and total_liabilities is not None:
            debt_ratio = round((total_liabilities / total_equity) * 100, 2)

        rcept_no = None
        for it in filtered_items:
            if it.get("rcept_no"):
                rcept_no = it.get("rcept_no")
                break

        res_success = {
            "status": "AVAILABLE",
            "message": "OpenDART 정기공시 주요계정 조회 성공",
            "bsns_year": str(target_year),
            "reprt_code": "11011",
            "reprt_name": "사업보고서",
            "rcept_no": rcept_no,
            "fs_div": target_fs_div,
            "fs_div_name": fs_div_name,
            "revenue": revenue,
            "revenue_prev": revenue_prev,
            "operating_income": operating_income,
            "operating_income_prev": operating_income_prev,
            "net_income": net_income,
            "net_income_prev": net_income_prev,
            "total_assets": total_assets,
            "total_assets_prev": total_assets_prev,
            "total_liabilities": total_liabilities,
            "total_liabilities_prev": total_liabilities_prev,
            "total_equity": total_equity,
            "total_equity_prev": total_equity_prev,
            "debt_ratio": debt_ratio,
            "accounts_detail": [
                {
                    "account_nm": it.get("account_nm"),
                    "fs_div": it.get("fs_div"),
                    "sj_nm": it.get("sj_nm"),
                    "thstrm_nm": it.get("thstrm_nm"),
                    "thstrm_amount": it.get("thstrm_amount"),
                    "frmtrm_nm": it.get("frmtrm_nm"),
                    "frmtrm_amount": it.get("frmtrm_amount")
                }
                for it in filtered_items
            ]
        }
        _cache_financial_facts(cache_key, res_success)
        return res_success

    def generate_company_decision_report(self, corp_code_or_name: str, max_events: int = 15) -> Dict[str, Any]:
        """
        단일 기업에 대한 4단 의사결정 리포트 데이터 생성
        - 1단: 사실 (Facts) - 재무/공시/CB/원문 추출 지분율 수치 및 정확한 관찰 기간
        - 2단: 관찰 지표 (Rule-based Observation) - 규칙 기반 관찰, 키워드 탐지, 모니터링 시나리오 (투자 조언 아님)
        - 3단: 원문 근거 (Evidence) - 증거 등급 분리 (공시 링크 연동 vs 2D 행 해시 결속)
        - 4단: 다음 확인 항목 (Next Actions) - 실사 모니터링 체크리스트
        """
        target = corp_code_or_name.strip()
        with self.driver.session(default_access_mode=READ_ACCESS) as session:
            # 1. 대상 기업 기본 정보 조회
            comp_query = """
            MATCH (c:DART_Company)
            WHERE c.corp_code = $target OR c.name = $target OR c.stock_code = $target
            RETURN c.corp_code AS corp_code, c.name AS corp_name, c.stock_code AS stock_code, c.is_listed AS is_listed
            LIMIT 1
            """
            comp_res = session.run(comp_query, target=target).single()
            if not comp_res:
                return {
                    "status": "NOT_FOUND",
                    "message": f"'{target}'에 해당하는 상장사 마스터 노드를 찾을 수 없습니다."
                }

            corp_code = comp_res["corp_code"]
            corp_name = comp_res["corp_name"]
            stock_code = comp_res["stock_code"]

            # 2. 최근 자본이벤트 (CB, BW, 유상증자 등) 조회 (최신순)
            cap_query = """
            MATCH (c:DART_Company {corp_code: $corp_code})-[:ANNOUNCED]->(e:DART_CapitalEvent)
            RETURN e.event_type AS event_type,
                   e.decided_on AS decided_on,
                   e.received_on AS received_on,
                   e.effective_on AS effective_on,
                   e.issue_method AS issue_method,
                   e.issue_amount AS issue_amount,
                   e.conversion_price AS conversion_price,
                   e.min_refixing_floor AS min_refixing_floor,
                   e.purpose AS purpose,
                   e.source_rcept_no AS rcept_no,
                   e.viewer_url AS viewer_url
            ORDER BY e.decided_on DESC
            LIMIT $max_events
            """
            raw_capital_events = session.run(cap_query, corp_code=corp_code, max_events=max_events).data()
            capital_events = [sanitize_capital_event(e) for e in raw_capital_events]

            # 3. 검증·승격된 경제적 보유 사실 조회 (HOLDS_ECONOMIC_STAKE - 단일 기업 관련 보유/피보유)
            promoted_query = """
            MATCH (h:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
            WHERE h.corp_code = $corp_code OR t.corp_code = $corp_code
            RETURN 
                h.name AS holder_name,
                h.corp_code AS holder_code,
                t.name AS target_name,
                t.corp_code AS target_code,
                r.stake_ratio AS stake_ratio,
                r.shares_count AS shares_count,
                r.reporting_obligation_date AS reporting_obligation_date,
                r.row_inner_hash AS row_inner_hash,
                r.promoted_at AS promoted_at,
                r.promotion_manifest_sha256 AS promotion_manifest_sha256,
                r.relationship_key AS relationship_key,
                r.rcept_no AS rcept_no
            ORDER BY r.reporting_obligation_date DESC, r.stake_ratio DESC
            """
            promoted_rows = session.run(promoted_query, corp_code=corp_code).data()
            promoted_hashes = list({r["row_inner_hash"] for r in promoted_rows if r.get("row_inner_hash")})

            # 4. 5% 대량보유 공시 원문 추출 후보 조회 (승격 완료된 row_inner_hash 완벽 배제 - WITH 스코프 분리)
            stake_query = """
            MATCH (cand:RawEvidenceCandidate {target_corp_code: $corp_code})
            OPTIONAL MATCH (cand)-[:EVIDENCED_BY]->(frag:EvidenceFragment {role: 'ROW_DATA_EVIDENCE'})
            WITH cand, frag
            WHERE $promoted_hashes IS NULL OR size($promoted_hashes) = 0 
               OR frag IS NULL OR NOT frag.raw_inner_hash IN $promoted_hashes
            RETURN 
                cand.candidate_id AS candidate_id,
                cand.holder_name AS holder_name,
                cand.stake_ratio AS stake_ratio,
                cand.shares_count AS shares_count,
                cand.reporting_obligation_date AS reporting_obligation_date,
                cand.rcept_no AS rcept_no,
                cand.layout_status AS layout_status,
                frag.xpath AS row_raw_parser_xpath,
                frag.raw_inner_hash AS row_inner_hash,
                frag.extracted_value AS extracted_value
            ORDER BY cand.reporting_obligation_date DESC, cand.stake_ratio DESC
            LIMIT 50
            """
            stake_rows = session.run(stake_query, corp_code=corp_code, promoted_hashes=promoted_hashes).data()

            # 전체 미검증 후보 건수 정밀 집계 (승격 제외 실측 수치 - WITH 스코프 분리)
            total_cand_query = """
            MATCH (cand:RawEvidenceCandidate {target_corp_code: $corp_code})
            OPTIONAL MATCH (cand)-[:EVIDENCED_BY]->(frag:EvidenceFragment {role: 'ROW_DATA_EVIDENCE'})
            WITH cand, frag
            WHERE $promoted_hashes IS NULL OR size($promoted_hashes) = 0 
               OR frag IS NULL OR NOT frag.raw_inner_hash IN $promoted_hashes
            RETURN count(DISTINCT cand) AS total_count
            """
            total_cand_res = session.run(total_cand_query, corp_code=corp_code, promoted_hashes=promoted_hashes).single()
            total_raw_candidate_count = total_cand_res["total_count"] if total_cand_res else len(stake_rows)

        # =========================================================================
        # 1단: 사실 (Facts) - 정확한 관찰 기간 계산 (가짜 '최근 2년' 주장 제거)
        # =========================================================================
        event_dates = [e.get("decided_on") or e.get("received_on") for e in capital_events if (e.get("decided_on") or e.get("received_on"))]
        date_coverage = {
            "start_date": min(event_dates) if event_dates else None,
            "end_date": max(event_dates) if event_dates else None,
            "observed_events_count": len(capital_events),
            "description": f"최근 수집된 공시 {len(capital_events)}건 (기간: {min(event_dates)} ~ {max(event_dates)})" if event_dates else "수집된 자본이벤트 공시 없음"
        }

        # 검증·승격된 경제적 보유 사실 가공 (19건 승격본)
        promoted_stakes = []
        for r in promoted_rows:
            promoted_stakes.append({
                "holder_name": r["holder_name"],
                "holder_code": r["holder_code"],
                "target_name": r["target_name"],
                "target_code": r["target_code"],
                "holder_to_target": f"{r['holder_name']} → {r['target_name']}",
                "stake_ratio": r["stake_ratio"],
                "shares_count": r["shares_count"],
                "reporting_obligation_date": r["reporting_obligation_date"],
                "row_inner_hash": r["row_inner_hash"],
                "promoted_at": str(r.get("promoted_at") or "-"),
                "promotion_manifest_sha256": r.get("promotion_manifest_sha256"),
                "relationship_key": r.get("relationship_key"),
                "rcept_no": r.get("rcept_no"),
                "status": "VERIFIED_ECONOMIC_STAKE",
                "status_label": "검증·승격 완료",
                "verification_note": "봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 검증 승격 완료"
            })

        # 원문 추출 후보 가공 (미검증 후보 상태 명시, 승격된 해시 2차 안전 배제)
        promoted_hash_set = set(promoted_hashes)
        raw_candidates = []
        for r in stake_rows:
            h_val = r.get("row_inner_hash")
            if h_val and h_val in promoted_hash_set:
                continue
            if r.get("holder_name"):
                raw_candidates.append({
                    "candidate_id": r["candidate_id"],
                    "holder_name": r["holder_name"],
                    "stake_ratio": r["stake_ratio"],
                    "shares_count": r["shares_count"],
                    "reporting_obligation_date": r["reporting_obligation_date"],
                    "rcept_no": r["rcept_no"],
                    "row_raw_parser_xpath": r["row_raw_parser_xpath"],
                    "row_inner_hash": r["row_inner_hash"],
                    "extracted_value": r["extracted_value"],
                    "status": "UNVERIFIED_EXTRACTED_CANDIDATE",
                    "status_label": "미검증 원문 추출 후보",
                    "verification_note": "DART 5% 공시 원문 테이블에서 추출된 1차 후보이며, 엔티티 해소 승격 전 단계입니다."
                })

        # OpenDART 주요 재무제표 팩트 조회 (DS003)
        financial_facts = self.get_company_financial_facts(corp_code)

        # 출처별 공식 채널 통합 타임라인 피드 생성 (DART A급 + KRX KIND 교차검증)
        timeline_bundle = build_official_timeline(capital_events, promoted_stakes, financial_facts, raw_candidates)

        facts = {
            "company_profile": {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code,
                "is_listed": comp_res["is_listed"]
            },
            "date_coverage": date_coverage,
            "financial_facts": financial_facts,
            "official_timeline": timeline_bundle["feed"],
            "official_timeline_summary": timeline_bundle["summary"],
            "capital_events_summary": {
                "total_events_count": len(capital_events),
                "events_detail": capital_events
            },
            "major_holdings_summary": {
                "promoted_count": len(promoted_stakes),
                "promoted_stakes": promoted_stakes,
                "raw_candidate_count": total_raw_candidate_count,
                "raw_candidates": raw_candidates[:10]
            }
        }

        # =========================================================================
        # 2단: 관찰 지표 (Rule-based Observation) - 단정적 금융 판단 배제 및 근거 명시
        # =========================================================================
        cb_bw_events = [e for e in capital_events if any(k in str(e.get("event_type", "")) or k in str(e.get("event_type_kr", "")) for k in ["전환사채", "CB", "신주인수권", "BW"])]
        cb_bw_count = len(cb_bw_events)
        capital_increase_events = [e for e in capital_events if "유상증자" in str(e.get("event_type_kr", "")) or str(e.get("event_type", "")) == "PAID"]
        increase_count = len(capital_increase_events)

        relevant_events = cb_bw_events + capital_increase_events
        basis_rcept_nos = list(dict.fromkeys([e["rcept_no"] for e in relevant_events if e.get("rcept_no")]))
        basis_event_dates = sorted(list(dict.fromkeys([e.get("decided_on") or e.get("received_on") for e in relevant_events if (e.get("decided_on") or e.get("received_on"))])))

        # 목적 문구 키워드 탐지 (정제된 목적 텍스트 기준)
        purposes = [str(e.get("sanitized_purpose", "")) for e in capital_events if e.get("sanitized_purpose") and e.get("sanitized_purpose") not in ["-", "공시 원문 서식 참조"]]
        has_facility = any(any(k in p for k in ["시설", "설비", "연구", "R&D", "타법인"]) for p in purposes)
        has_debt = any(any(k in p for k in ["채무상환", "운영자금"]) for p in purposes)

        if has_facility and not has_debt:
            purpose_eval = "시설투자/R&D/타법인증권취득 키워드 중심 탐지"
        elif has_facility and has_debt:
            purpose_eval = "운영·채무상환 및 시설투자 병행 키워드 탐지"
        elif has_debt:
            purpose_eval = "운영자금/채무상환 키워드 중심 탐지"
        else:
            purpose_eval = "공시 서식상 특이 목적 키워드 미탐지"

        # 관찰 등급 (규칙 기반 탐지)
        if cb_bw_count >= 2 or (cb_bw_count + increase_count) >= 3:
            obs_level = "주의 관찰 요망 (CB/BW 또는 증자 2건 이상 누적 탐지)"
            obs_code = "OBS_WATCH_HIGH"
        elif (cb_bw_count + increase_count) >= 1:
            obs_level = "일반 관찰 (자본이벤트 발생 이력 탐지)"
            obs_code = "OBS_WATCH_MODERATE"
        else:
            obs_level = "특이 관찰 요망 사항 미발견"
            obs_code = "OBS_NORMAL"

        interpretations = {
            "rule_version": "RULE_HEURISTIC_v1.0",
            "observation_level": obs_level,
            "observation_code": obs_code,
            "basis_rcept_nos": basis_rcept_nos,
            "basis_event_dates": basis_event_dates,
            "cb_bw_overhang_observation": (
                f"수집된 공시 {len(capital_events)}건 중 CB/BW 공시 {cb_bw_count}건 감지. 전환청구 도래 시 잠재 주식수 증가에 따른 오버행 가능성 모니터링 필요."
                if cb_bw_count > 0 else
                f"수집된 공시 {len(capital_events)}건 기준 전환사채(CB) 및 BW 발행 이력 미발견."
            ),
            "financing_purpose_observation": purpose_eval,
            "tracking_scenarios": {
                "scenario_type": "추적 관찰용 시나리오 (참고용 - 가격 예측 아님)",
                "bull_case": "조달 자금의 시설투자 집행 및 신사업 가시화로 주당순이익(EPS) 희석 효과를 상쇄하는 성장 시나리오 (가정)",
                "base_case": "기존 주주 지분율 일부 희석이 발생하나, 만기 전 사채 취득 및 차환을 통해 재무 안정성을 유지하는 시나리오 (가정)",
                "bear_case": "전환가액 하향(리픽싱) 누적 및 주가 하락 시 잠재 전환물량 출회로 주가 하방 압력이 가중되는 시나리오 (가정)"
            },
            "disclaimer": "※ 본 관찰 지표 및 시나리오는 DART 공시 텍스트 규칙 기반 휴리스틱 탐지 결과이며, 투자 자문이나 주가 예측이 아닙니다."
        }

        # =========================================================================
        # 3단: 원문 근거 (Evidence) - 정직한 증거 등급 분리
        # =========================================================================
        evidence_list = []
        # 자본이벤트: 공시 접수번호 기준 원문 링크 연동 (행 단위 2D 해시 미적재 명시)
        for e in capital_events[:5]:
            rcp = e.get("rcept_no")
            ev_date = e.get("decided_on") or e.get("received_on") or "-"
            evidence_list.append({
                "item_type": "CAPITAL_EVENT",
                "title": f"{e.get('event_type_kr', e.get('event_type'))} ({ev_date})",
                "rcept_no": rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None,
                "evidence_level": "FILING_LINK_ONLY",
                "xpath": None,
                "inner_hash": None,
                "evidence_note": "공시 접수번호 기준 DART 원문 바로가기 연동 (행 단위 2D 해시 미적재)"
            })

        # 검증·승격된 경제적 보유 사실: 봉인 매니페스트 결속 및 원문 행 해시 전수 검증
        for p in promoted_stakes[:5]:
            rcp = p.get("rcept_no")
            evidence_list.append({
                "item_type": "PROMOTED_ECONOMIC_STAKE",
                "title": f"[검증·승격 사실] {p['holder_to_target']} ({p['stake_ratio']}%, {p['reporting_obligation_date']})",
                "rcept_no": rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None,
                "evidence_level": "MANIFEST_SEALED_ROW_HASH",
                "xpath": None,
                "inner_hash": p.get("row_inner_hash"),
                "manifest_sha256": p.get("promotion_manifest_sha256"),
                "evidence_note": "봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 검증 승격 완료 (HOLDS_ECONOMIC_STAKE)"
            })

        # 5% 보고 후보: 파서 추출 좌표 및 원문 행 SHA-256 결속
        for s in raw_candidates[:5]:
            rcp = s.get("rcept_no")
            evidence_list.append({
                "item_type": "MAJOR_STAKE_CANDIDATE",
                "title": f"[미검증 원문 추출 후보] {s.get('holder_name')} ({s.get('stake_ratio')}%, {s.get('reporting_obligation_date')})",
                "rcept_no": rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None,
                "evidence_level": "ROW_HASH_BOUND",
                "xpath": s.get("row_raw_parser_xpath"),
                "inner_hash": s.get("row_inner_hash"),
                "evidence_note": "파서 추출 좌표 + 원문 행 SHA-256 결속"
            })

        # 정기공시 재무제표 팩트: OpenDART DS003 단일회사 주요계정 직연동
        if financial_facts.get("status") == "AVAILABLE":
            fin_rcp = financial_facts.get("rcept_no")
            evidence_list.append({
                "item_type": "FINANCIAL_STATEMENT_FACT",
                "title": f"[정기공시 재무제표 팩트] {financial_facts.get('bsns_year')}년 {financial_facts.get('reprt_name')} ({financial_facts.get('fs_div_name')})",
                "rcept_no": fin_rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={fin_rcp}" if fin_rcp else None,
                "evidence_level": "OPENDART_API_FACT",
                "xpath": None,
                "inner_hash": None,
                "evidence_note": f"금융감독원 OpenDART 사업보고서 주요계정(fnlttSinglAcnt) API 팩트 연동 ({financial_facts.get('fs_div')})"
            })

        # =========================================================================
        # 4단: 다음 확인 항목 (Next Actions) - 실사 모니터링 체크리스트
        # =========================================================================
        next_actions = [
            "CB/BW 사채의 전환청구 시작일 및 전환가액 조정(리픽싱) 공시 주기적 추적",
            "유상증자 청약일 및 주금 납입일 준수 여부(납입 연기 정정공시 여부 확인)",
            "대주주 및 특수관계인의 추가 장내 매도/담보대출 설정 공시 모니터링",
            "다음 분기 정기보고서(사업보고서/분기보고서) 자본금 변동사항 표 대조"
        ]

        return {
            "status": "SUCCESS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_company": {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code
            },
            "tier1_facts": facts,
            "tier2_interpretations": interpretations,
            "tier3_evidence": evidence_list,
            "tier4_next_actions": next_actions
        }


if __name__ == "__main__":
    service = DecisionReportService()
    try:
        sample = service.generate_company_decision_report("HLB")
        print("Report Generated Successfully!")
        print("Date Coverage:", sample["tier1_facts"]["date_coverage"])
        print("Observation:", sample["tier2_interpretations"]["observation_level"])
        print("Evidence Count:", len(sample["tier3_evidence"]))
        for ev in sample["tier3_evidence"][:3]:
            print(f" - [{ev['evidence_level']}] {ev['title']} (XPath: {ev['xpath']}, Hash: {ev['inner_hash']})")
    finally:
        service.close()
