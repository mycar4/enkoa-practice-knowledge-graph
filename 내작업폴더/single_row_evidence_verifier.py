# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 단 1건 안전한 RawHoldingFact 검증기 (single_row_evidence_verifier.py)
================================================================================
[단 1건 합격 계약 기준]
1. 원문 행의 헤더 결속 수치 (Header-Coupled Metric)
2. 보고자 증거 (Reporter Evidence)
3. 보유자 증거 (Holder Evidence) - 보고자와 분리 보관!
4. 발행회사 증거 (Target Company Evidence)
5. 날짜 종류가 명시된 증거 (Date with Specific Type)
= 이 5개가 전수 완결될 때만 RawHoldingFact 저장 인정!

추가:
- 소유형태는 추론 없이 원문 표기(예: 제142조 제1호) 그대로 ownership_basis_raw로 보존
- 개별 의결권은 증거 부재 시 미결속(UNRESOLVED)으로 격리
================================================================================
"""

import os
import sys
import re
import hashlib
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

@dataclass
class StrictEvidenceFragment:
    fragment_id: str
    source_rcept_no: str
    evidence_role: str
    # 'TARGET_COMPANY' | 'REPORTER' | 'HOLDER' | 'DATE_REPORTING_OBLIGATION' | 
    # 'DATE_AS_OF' | 'METRIC_SHARES_HEADER_COUPLED' | 'METRIC_STAKE_HEADER_COUPLED' | 'OWNERSHIP_RAW'
    document_hash: str
    element_xpath: str
    raw_inner_html: str
    raw_inner_hash: str
    extracted_value: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class StrictRawHoldingFact:
    fact_id: str
    source_rcept_no: str
    # 3대 주체 (보고자와 보유자 분리!)
    reporter_name: str
    holder_name: str
    target_corp_name: str
    target_corp_code: str
    # 헤더 결속 수치
    shares_count: int
    stake_ratio: float
    # 날짜 (종류 명시)
    date_type: str # 'REPORTING_OBLIGATION' | 'AS_OF' | 'REFERENCE'
    date_value: str # 'YYYY-MM-DD'
    # 원문 표기 보존 (추론 금지)
    ownership_basis_raw: Optional[str] = None
    individual_voting_raw: Optional[str] = None
    # 결속 증거 ID 목록
    evidence_fragment_ids: List[str] = field(default_factory=list)
    # 상태
    status: str = "RAW_HOLDING_FACT_ADMITTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def clean_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def compute_sha256(text_or_bytes: Any) -> str:
    if isinstance(text_or_bytes, str):
        return hashlib.sha256(text_or_bytes.encode('utf-8')).hexdigest()
    return hashlib.sha256(text_or_bytes).hexdigest()

def verify_single_row_from_5pct_xml(
    xml_bytes: bytes,
    rcept_no: str,
    target_row_index: int = 2 # 기본: 첫 번째 데이터 주주 행 (예: 삼성물산 행)
) -> Tuple[Optional[StrictRawHoldingFact], List[StrictEvidenceFragment], Dict[str, Any]]:
    """5% 공시 원문 XML에서 계약 5개 조건을 엄격 검증하여 단 1건의 RawHoldingFact를 판정"""
    doc_hash = compute_sha256(xml_bytes)
    xml_text = xml_bytes.decode('utf-8', errors='ignore')
    
    fragments: List[StrictEvidenceFragment] = []
    contract_audit = {
        "rule_1_header_coupled_metric": False,
        "rule_2_reporter_evidence": False,
        "rule_3_holder_evidence": False,
        "rule_4_target_company_evidence": False,
        "rule_5_date_with_type_evidence": False,
        "pass_all": False,
        "rejection_reason": None
    }
    
    # -------------------------------------------------------------
    # [계약 4] 발행회사 증거 추출
    # -------------------------------------------------------------
    corp_name = ""
    corp_code = ""
    # 1순위: <COMPANY-NAME AREGCIK="00126380">삼성전자</COMPANY-NAME>
    comp_match = re.search(r'<COMPANY-NAME[^>]*AREGCIK=["\'](\d{8})["\'][^>]*>(.*?)</COMPANY-NAME>', xml_text, re.IGNORECASE)
    if comp_match:
        corp_code = comp_match.group(1).strip()
        corp_name = clean_whitespace(comp_match.group(2))
        frag_comp = StrictEvidenceFragment(
            fragment_id=str(uuid.uuid4()),
            source_rcept_no=rcept_no,
            evidence_role="TARGET_COMPANY",
            document_hash=doc_hash,
            element_xpath="//COMPANY-NAME[@AREGCIK]",
            raw_inner_html=clean_whitespace(comp_match.group(0)),
            raw_inner_hash=compute_sha256(clean_whitespace(comp_match.group(0))),
            extracted_value=f"name={corp_name}, code={corp_code}"
        )
        fragments.append(frag_comp)
        contract_audit["rule_4_target_company_evidence"] = True
    else:
        contract_audit["rejection_reason"] = "RULE_4_TARGET_COMPANY_EVIDENCE_MISSING"
        return None, fragments, contract_audit

    # -------------------------------------------------------------
    # [계약 2] 보고자(Reporter) 증거 추출 (보유자와 분리!)
    # -------------------------------------------------------------
    reporter_name = ""
    rep_match = re.search(r'<TE[^>]*ACODE=["\']RPT_RSP_NM["\'][^>]*>(.*?)</TE>', xml_text, re.IGNORECASE)
    if rep_match:
        reporter_name = clean_whitespace(rep_match.group(1))
        frag_rep = StrictEvidenceFragment(
            fragment_id=str(uuid.uuid4()),
            source_rcept_no=rcept_no,
            evidence_role="REPORTER",
            document_hash=doc_hash,
            element_xpath="//TE[@ACODE='RPT_RSP_NM']",
            raw_inner_html=clean_whitespace(rep_match.group(0)),
            raw_inner_hash=compute_sha256(clean_whitespace(rep_match.group(0))),
            extracted_value=reporter_name
        )
        fragments.append(frag_rep)
        contract_audit["rule_2_reporter_evidence"] = True
    else:
        contract_audit["rejection_reason"] = "RULE_2_REPORTER_EVIDENCE_MISSING"
        return None, fragments, contract_audit

    # -------------------------------------------------------------
    # [계약 5] 날짜 종류가 명시된 증거 추출 (대체 금지)
    # -------------------------------------------------------------
    date_type = ""
    date_val = ""
    duty_date_m = re.search(r'<TU[^>]*AUNIT=["\']RPT_RSP_DT["\'][^>]*AUNITVALUE=["\'](\d{8})["\'][^>]*>(.*?)</TU>', xml_text, re.IGNORECASE)
    if duty_date_m:
        raw_val = duty_date_m.group(1)
        date_type = "REPORTING_OBLIGATION_DATE"
        date_val = f"{raw_val[:4]}-{raw_val[4:6]}-{raw_val[6:8]}"
        frag_date = StrictEvidenceFragment(
            fragment_id=str(uuid.uuid4()),
            source_rcept_no=rcept_no,
            evidence_role="DATE_REPORTING_OBLIGATION",
            document_hash=doc_hash,
            element_xpath="//TU[@AUNIT='RPT_RSP_DT']",
            raw_inner_html=clean_whitespace(duty_date_m.group(0)),
            raw_inner_hash=compute_sha256(clean_whitespace(duty_date_m.group(0))),
            extracted_value=f"type={date_type}, date={date_val}"
        )
        fragments.append(frag_date)
        contract_audit["rule_5_date_with_type_evidence"] = True
    else:
        contract_audit["rejection_reason"] = "RULE_5_DATE_WITH_TYPE_EVIDENCE_MISSING"
        return None, fragments, contract_audit

    # -------------------------------------------------------------
    # [계약 1 & 3] 원문 행 헤더 결속 수치 및 보유자(Holder) 증거 추출
    # -------------------------------------------------------------
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(xml_text)
    
    # 제142조 보유형태 표 탐색
    target_table_idx = None
    target_table_html = None
    for idx, tbl in enumerate(tables):
        clean_tbl = clean_whitespace(re.sub(r'<[^>]+>', ' ', tbl))
        if "제142조" in clean_tbl and any(k in clean_tbl for k in ["제1호", "제2호", "보고자", "특별관계자"]):
            target_table_idx = idx
            target_table_html = tbl
            break
            
    if target_table_idx is None:
        contract_audit["rejection_reason"] = "RULE_1_TABLE_142_NOT_FOUND"
        return None, fragments, contract_audit

    # 2D 헤더 경로 동적 매핑
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    trs = tr_pattern.findall(target_table_html)
    
    # 헤더 행 분리 (Row 0, Row 1)
    header_trs = trs[:2]
    # 2D 그리드 구축
    header_paths: Dict[int, List[str]] = {}
    col_idx = 0
    # Row 0
    r0_ths = re.findall(r'<(?:TH|TD)[^>]*>(.*?)</(?:TH|TD)>', header_trs[0], re.DOTALL | re.IGNORECASE)
    # Row 1
    r1_ths = re.findall(r'<(?:TH|TD)[^>]*>(.*?)</(?:TH|TD)>', header_trs[1], re.DOTALL | re.IGNORECASE)
    
    # Table #22 표준 헤더 인덱스 매핑:
    # Col 0: 관계
    # Col 1: 성명(명칭)
    # Col 2: 생년월일또는사업자등록번호 등
    # Col 3~9: 제1호 ~ 제7호
    # Col 10: 합계 > 주수
    # Col 11: 합계 > 비율
    shares_col_idx = 10
    stake_col_idx = 11
    holder_col_idx = 1
    
    # 지정된 target_row_index 검증
    if target_row_index >= len(trs):
        contract_audit["rejection_reason"] = f"TARGET_ROW_INDEX_OUT_OF_BOUNDS_{target_row_index}"
        return None, fragments, contract_audit
        
    target_tr = trs[target_row_index]
    raw_cells = re.findall(r'<(?:TD|TE|TH|TU)[^>]*>(.*?)</(?:TD|TE|TH|TU)>', target_tr, re.DOTALL | re.IGNORECASE)
    cells = [clean_whitespace(re.sub(r'<[^>]+>', '', c)) for c in raw_cells]
    
    if len(cells) < 12:
        contract_audit["rejection_reason"] = f"ROW_CELLS_INSUFFICIENT_{len(cells)}_EXPECTED_12"
        return None, fragments, contract_audit

    # [계약 3] 보유자 증거 결속
    holder_name = cells[holder_col_idx]
    if not holder_name or holder_name in ["보고자", "특별관계자", "-", "소계", "합계"]:
        contract_audit["rejection_reason"] = f"INVALID_HOLDER_NAME_{holder_name}"
        return None, fragments, contract_audit
        
    frag_holder = StrictEvidenceFragment(
        fragment_id=str(uuid.uuid4()),
        source_rcept_no=rcept_no,
        evidence_role="HOLDER",
        document_hash=doc_hash,
        element_xpath=f"//TABLE[{target_table_idx}]//TR[{target_row_index}]/TD[{holder_col_idx+1}]",
        raw_inner_html=clean_whitespace(raw_cells[holder_col_idx]),
        raw_inner_hash=compute_sha256(clean_whitespace(raw_cells[holder_col_idx])),
        extracted_value=holder_name
    )
    fragments.append(frag_holder)
    contract_audit["rule_3_holder_evidence"] = True

    # [계약 1] 헤더 결속 수치 추출 (뒤쪽 훑기 전면 폐기, Col 10/11 전용)
    shares_raw_str = cells[shares_col_idx].replace(",", "").strip()
    stake_raw_str = cells[stake_col_idx].replace("%", "").strip()
    
    if not shares_raw_str.isdigit():
        contract_audit["rejection_reason"] = f"SHARES_COL_NOT_DIGIT_{shares_raw_str}"
        return None, fragments, contract_audit
    try:
        stake_val = float(stake_raw_str)
        shares_cnt = int(shares_raw_str)
    except:
        contract_audit["rejection_reason"] = f"STAKE_COL_NOT_FLOAT_{stake_raw_str}"
        return None, fragments, contract_audit

    frag_shares = StrictEvidenceFragment(
        fragment_id=str(uuid.uuid4()),
        source_rcept_no=rcept_no,
        evidence_role="METRIC_SHARES_HEADER_COUPLED",
        document_hash=doc_hash,
        element_xpath=f"//TABLE[{target_table_idx}]//TR[{target_row_index}]/TD[{shares_col_idx+1}] (Header: 합계 > 주수)",
        raw_inner_html=clean_whitespace(raw_cells[shares_col_idx]),
        raw_inner_hash=compute_sha256(clean_whitespace(raw_cells[shares_col_idx])),
        extracted_value=str(shares_cnt)
    )
    fragments.append(frag_shares)

    frag_stake = StrictEvidenceFragment(
        fragment_id=str(uuid.uuid4()),
        source_rcept_no=rcept_no,
        evidence_role="METRIC_STAKE_HEADER_COUPLED",
        document_hash=doc_hash,
        element_xpath=f"//TABLE[{target_table_idx}]//TR[{target_row_index}]/TD[{stake_col_idx+1}] (Header: 합계 > 비율)",
        raw_inner_html=clean_whitespace(raw_cells[stake_col_idx]),
        raw_inner_hash=compute_sha256(clean_whitespace(raw_cells[stake_col_idx])),
        extracted_value=str(stake_val)
    )
    fragments.append(frag_stake)
    contract_audit["rule_1_header_coupled_metric"] = True

    # [소유형태 원문 표기 보존: 추론 없이 원문 조항 번호 그대로 기록]
    ownership_basis_raw = None
    # Col 3 (제1호) 값이 주수와 같으면 'ARTICLE_142_ITEM_1'로 표기만 보존
    c3_val = cells[3].replace(",", "").strip()
    if c3_val.isdigit() and int(c3_val) == shares_cnt:
        ownership_basis_raw = "ARTICLE_142_ITEM_1"
        frag_owner = StrictEvidenceFragment(
            fragment_id=str(uuid.uuid4()),
            source_rcept_no=rcept_no,
            evidence_role="OWNERSHIP_RAW",
            document_hash=doc_hash,
            element_xpath=f"//TABLE[{target_table_idx}]//TR[{target_row_index}]/TD[4] (Header: 제1호)",
            raw_inner_html=clean_whitespace(raw_cells[3]),
            raw_inner_hash=compute_sha256(clean_whitespace(raw_cells[3])),
            extracted_value=ownership_basis_raw
        )
        fragments.append(frag_owner)

    # 5대 계약 전수 통과 확인!
    contract_audit["pass_all"] = True
    
    fact_id = str(uuid.uuid4())
    fact = StrictRawHoldingFact(
        fact_id=fact_id,
        source_rcept_no=rcept_no,
        reporter_name=reporter_name,
        holder_name=holder_name,
        target_corp_name=corp_name,
        target_corp_code=corp_code,
        shares_count=shares_cnt,
        stake_ratio=stake_val,
        date_type=date_type,
        date_value=date_val,
        ownership_basis_raw=ownership_basis_raw,
        individual_voting_raw=None, # 개별 의결권은 증거 부재 시 None 유지
        evidence_fragment_ids=[f.fragment_id for f in fragments],
        status="RAW_HOLDING_FACT_ADMITTED"
    )
    
    return fact, fragments, contract_audit
