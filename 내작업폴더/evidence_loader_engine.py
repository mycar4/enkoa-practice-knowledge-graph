# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 다층 증거 온톨로지 엔진 (Evidence Loader Engine)
================================================================================
[계약 규격 준수: Promotion Contract v1.0]
1. RawHoldingFact       : 보고자, 대상회사, 주식수, 지분율의 원천 사실 보존
2. EvidenceFragment     : 각 사실의 XML 경로, 정규화 inner HTML, SHA-256 해시 결속
3. EvidenceBundle       : 한 공시 문서 내 증거 결속 상태 머신 (COLLECTING / PARTIALLY_EVIDENCED / CONFLICTED / RESOLVED)
4. 3단계 승격 정책      : Tier 1(Economic) -> Tier 2(Voting) -> Tier 3(Ownership)
================================================================================
"""

import os
import sys
import re
import json
import hashlib
import uuid
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict

# ----------------------------------------------------------------------
# 1. 데이터 모델 (Data Classes)
# ----------------------------------------------------------------------

@dataclass
class RawHoldingFact:
    fact_id: str
    holder_raw_name: str
    target_corp_code: str
    shares_count: int
    stake_ratio: float
    share_class_raw: Optional[str] = None
    source_report_tp: str = "UNKNOWN" # 'PERIODIC' | '5PCT_GENERAL' | '5PCT_SIMPLIFIED'
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class EvidenceFragment:
    fragment_id: str
    source_rcept_no: str
    evidence_role: str # 'ECONOMIC_FACT' | 'AS_OF_DATE' | 'VOTING_RIGHT' | 'OWNERSHIP_BASIS'
    document_hash: str # 원문 XML 전체 해시
    element_xpath: str # 예: '//TABLE[22]//TR[2]'
    raw_inner_html: str # 정규화된 inner HTML
    raw_inner_hash: str # sha256(raw_inner_html)
    extracted_value: str # 파싱된 값 (예: '2024-10-22', '298,818,100')
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class EvidenceBundle:
    bundle_id: str
    rcept_no: str
    holder_key: str
    target_corp_code: str
    bundle_status: str # 'COLLECTING' | 'PARTIALLY_EVIDENCED' | 'CONFLICTED' | 'RESOLVED'
    fact_ids: List[str] = field(default_factory=list)
    fragment_ids: List[str] = field(default_factory=list)
    evidence_mask: Dict[str, bool] = field(default_factory=lambda: {
        "ECONOMIC": False,
        "AS_OF_DATE": False,
        "VOTING": False,
        "OWNERSHIP": False
    })
    as_of_date: Optional[str] = None
    ownership_basis_resolved: Optional[str] = None
    voting_resolved: Optional[str] = None
    eligible_tiers: List[str] = field(default_factory=list)
    conflict_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ----------------------------------------------------------------------
# 2. 유틸리티 함수
# ----------------------------------------------------------------------

def clean_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def compute_sha256(text_or_bytes: Any) -> str:
    if isinstance(text_or_bytes, str):
        return hashlib.sha256(text_or_bytes.encode('utf-8')).hexdigest()
    return hashlib.sha256(text_or_bytes).hexdigest()

# ----------------------------------------------------------------------
# 3. 5% 대량보유공시 증거 추출기
# ----------------------------------------------------------------------

def extract_evidence_from_5pct_xml(xml_bytes: bytes, rcept_no: str, target_corp_code: str) -> Tuple[List[RawHoldingFact], List[EvidenceFragment], List[EvidenceBundle]]:
    """5% 공시 원문 XML로부터 계약 규격에 맞춘 Fact, Fragment, Bundle 추출"""
    doc_hash = compute_sha256(xml_bytes)
    xml_text = xml_bytes.decode('utf-8', errors='ignore')
    
    facts: List[RawHoldingFact] = []
    fragments: List[EvidenceFragment] = []
    bundles: List[EvidenceBundle] = []
    
    # 1. 기준일 (보고의무발생일 / 작성기준일) 추출
    duty_date = ""
    frag_date = None
    date_tu_match = re.search(r'<TU[^>]*AUNIT=["\']RPT_RSP_DT["\'][^>]*AUNITVALUE=["\'](\d{8})["\'][^>]*>(.*?)</TU>', xml_text, re.IGNORECASE)
    if date_tu_match:
        raw_val = date_tu_match.group(1) # YYYYMMDD
        duty_date = f"{raw_val[:4]}-{raw_val[4:6]}-{raw_val[6:8]}"
        frag_date = EvidenceFragment(
            fragment_id=str(uuid.uuid4()),
            source_rcept_no=rcept_no,
            evidence_role="AS_OF_DATE",
            document_hash=doc_hash,
            element_xpath="//TABLE-GROUP[@ACLASS='RPT_RSP_DT']//TU[@AUNIT='RPT_RSP_DT']",
            raw_inner_html=clean_whitespace(date_tu_match.group(0)),
            raw_inner_hash=compute_sha256(clean_whitespace(date_tu_match.group(0))),
            extracted_value=duty_date
        )
        fragments.append(frag_date)
    else:
        # 정규식 백업
        date_m = re.search(r'보고의무\s*발생일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', xml_text)
        if date_m:
            duty_date = f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}"
            frag_date = EvidenceFragment(
                fragment_id=str(uuid.uuid4()),
                source_rcept_no=rcept_no,
                evidence_role="AS_OF_DATE",
                document_hash=doc_hash,
                element_xpath="//P[contains(., '보고의무발생일')]",
                raw_inner_html=clean_whitespace(date_m.group(0)),
                raw_inner_hash=compute_sha256(clean_whitespace(date_m.group(0))),
                extracted_value=duty_date
            )
            fragments.append(frag_date)

    # 2. 보고서 유형 판정 (DOCUMENT-NAME 기준: 일반 ACODE=00636 vs 약식 ACODE=00637)
    doc_name_m = re.search(r'<DOCUMENT-NAME[^>]*>(.*?)</DOCUMENT-NAME>', xml_text, re.IGNORECASE)
    doc_name = doc_name_m.group(1) if doc_name_m else ""
    report_tp = "5PCT_SIMPLIFIED" if "약식" in doc_name or "00637" in xml_text else "5PCT_GENERAL"

    # 3. 테이블 순회
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(xml_text)
    
    for t_idx, tbl in enumerate(tables):
        clean_tbl = clean_whitespace(re.sub(r'<[^>]+>', ' ', tbl))
        
        # [Case A: 일반보고 제142조 보유형태 표] (예: 삼성물산 Table #22)
        if "제142조" in clean_tbl and any(k in clean_tbl for k in ["제1호", "제2호", "보고자", "특별관계자"]):
            trs = re.findall(r'<TR[^>]*>(.*?)</TR>', tbl, re.DOTALL | re.IGNORECASE)
            for r_idx, tr in enumerate(trs):
                raw_cells = re.findall(r'<(?:TD|TE|TH|TU)[^>]*>(.*?)</(?:TD|TE|TH|TU)>', tr, re.DOTALL | re.IGNORECASE)
                cells = [clean_whitespace(re.sub(r'<[^>]+>', '', c)) for c in raw_cells]
                
                # 헤더행 건너뛰기
                if not cells or any(h in cells[0] for h in ["관계", "제1호", "성명", "명칭", "생년월일", "합계", "소계"]):
                    continue
                if len(cells) < 3:
                    continue
                    
                # 주주명 추출 (보고자/특별관계자 라벨 구분)
                if cells[0] in ["보고자", "특별관계자"]:
                    holder_name = cells[1] if len(cells) > 1 else ""
                else:
                    holder_name = cells[0]
                    
                if not holder_name or holder_name in ["보고자", "특별관계자", "-", "소계", "합계"]:
                    continue
                    
                # 주식수 및 지분율 탐색
                stake_val = 0.0
                shares_cnt = 0
                for c in reversed(cells):
                    c_clean = c.replace(",", "").replace("%", "").strip()
                    if "." in c_clean and stake_val == 0.0:
                        try:
                            val = float(c_clean)
                            if 0.0 <= val <= 100.0:
                                stake_val = val
                        except:
                            pass
                    elif c_clean.isdigit() and shares_cnt == 0:
                        try:
                            shares_cnt = int(c_clean)
                        except:
                            pass
                            
                if shares_cnt > 0 or stake_val > 0.0:
                    fact_id = str(uuid.uuid4())
                    raw_fact = RawHoldingFact(
                        fact_id=fact_id,
                        holder_raw_name=holder_name,
                        target_corp_code=target_corp_code,
                        shares_count=shares_cnt,
                        stake_ratio=stake_val,
                        share_class_raw="의결권있는주식(합산)",
                        source_report_tp=report_tp
                    )
                    facts.append(raw_fact)
                    
                    tr_clean_inner = clean_whitespace(tr)
                    frag_fact = EvidenceFragment(
                        fragment_id=str(uuid.uuid4()),
                        source_rcept_no=rcept_no,
                        evidence_role="ECONOMIC_FACT",
                        document_hash=doc_hash,
                        element_xpath=f"//TABLE[{t_idx}]//TR[{r_idx}]",
                        raw_inner_html=tr_clean_inner,
                        raw_inner_hash=compute_sha256(tr_clean_inner),
                        extracted_value=f"shares={shares_cnt}, stake={stake_val}%"
                    )
                    fragments.append(frag_fact)
                    
                    # 소유형태 파편 결속 (제1호 vs 제2호)
                    ownership_type = "UNRESOLVED"
                    # 제1호 컬럼 위치 탐색
                    for col_val in cells[2:6]:
                        c_num = col_val.replace(",", "").strip()
                        if c_num.isdigit() and int(c_num) == shares_cnt:
                            ownership_type = "ARTICLE_142_ITEM_1_DIRECT_EQUIVALENT"
                            break
                    
                    frag_owner = EvidenceFragment(
                        fragment_id=str(uuid.uuid4()),
                        source_rcept_no=rcept_no,
                        evidence_role="OWNERSHIP_BASIS",
                        document_hash=doc_hash,
                        element_xpath=f"//TABLE[{t_idx}]//TR[{r_idx}]",
                        raw_inner_html=tr_clean_inner,
                        raw_inner_hash=compute_sha256(tr_clean_inner),
                        extracted_value=ownership_type
                    )
                    fragments.append(frag_owner)
                    
                    bundle = evaluate_evidence_bundle(
                        rcept_no=rcept_no,
                        holder_name=holder_name,
                        target_corp_code=target_corp_code,
                        fact=raw_fact,
                        frag_fact=frag_fact,
                        frag_date=frag_date if duty_date else None,
                        frag_owner=frag_owner,
                        frag_voting=None
                    )
                    bundles.append(bundle)

        # [Case B: 약식보고 보유주식등의 내역 표] (예: 국민연금 Table #13)
        elif report_tp == "5PCT_SIMPLIFIED" and "보유주식등의 내역" in clean_tbl:
            trs = re.findall(r'<TR[^>]*>(.*?)</TR>', tbl, re.DOTALL | re.IGNORECASE)
            for r_idx, tr in enumerate(trs):
                raw_cells = re.findall(r'<(?:TD|TE|TH|TU)[^>]*>(.*?)</(?:TD|TE|TH|TU)>', tr, re.DOTALL | re.IGNORECASE)
                cells = [clean_whitespace(re.sub(r'<[^>]+>', '', c)) for c in raw_cells]
                
                # 헤더행 건너뛰기
                clean_c0 = cells[0].replace(" ", "")
                if not cells or clean_c0 in ["관계", "주권", "의결권", "합계", "소계", "총계", "연번", "구분"]:
                    continue
                if len(cells) < 3:
                    continue
                    
                if cells[0] in ["보고자", "특별관계자"]:
                    holder_name = cells[1] if len(cells) > 1 else ""
                else:
                    holder_name = cells[0]
                    
                if not holder_name or holder_name in ["보고자", "특별관계자", "-", "소계", "합계"]:
                    continue
                    
                stake_val = 0.0
                shares_cnt = 0
                for c in reversed(cells):
                    c_clean = c.replace(",", "").replace("%", "").strip()
                    if "." in c_clean and stake_val == 0.0:
                        try:
                            val = float(c_clean)
                            if 0.0 <= val <= 100.0:
                                stake_val = val
                        except:
                            pass
                    elif c_clean.isdigit() and shares_cnt == 0:
                        try:
                            shares_cnt = int(c_clean)
                        except:
                            pass
                            
                if shares_cnt > 0 or stake_val > 0.0:
                    fact_id = str(uuid.uuid4())
                    raw_fact = RawHoldingFact(
                        fact_id=fact_id,
                        holder_raw_name=holder_name,
                        target_corp_code=target_corp_code,
                        shares_count=shares_cnt,
                        stake_ratio=stake_val,
                        share_class_raw="의결권있는주식",
                        source_report_tp=report_tp
                    )
                    facts.append(raw_fact)
                    
                    tr_clean_inner = clean_whitespace(tr)
                    frag_fact = EvidenceFragment(
                        fragment_id=str(uuid.uuid4()),
                        source_rcept_no=rcept_no,
                        evidence_role="ECONOMIC_FACT",
                        document_hash=doc_hash,
                        element_xpath=f"//TABLE[{t_idx}]//TR[{r_idx}]",
                        raw_inner_html=tr_clean_inner,
                        raw_inner_hash=compute_sha256(tr_clean_inner),
                        extracted_value=f"shares={shares_cnt}, stake={stake_val}%"
                    )
                    fragments.append(frag_fact)
                    
                    bundle = evaluate_evidence_bundle(
                        rcept_no=rcept_no,
                        holder_name=holder_name,
                        target_corp_code=target_corp_code,
                        fact=raw_fact,
                        frag_fact=frag_fact,
                        frag_date=frag_date if duty_date else None,
                        frag_owner=None,
                        frag_voting=None
                    )
                    bundles.append(bundle)

    return facts, fragments, bundles

# ----------------------------------------------------------------------
# 4. EvidenceBundle 상태 전이 및 3단계 승격 판정기
# ----------------------------------------------------------------------

def evaluate_evidence_bundle(
    rcept_no: str,
    holder_name: str,
    target_corp_code: str,
    fact: RawHoldingFact,
    frag_fact: EvidenceFragment,
    frag_date: Optional[EvidenceFragment] = None,
    frag_owner: Optional[EvidenceFragment] = None,
    frag_voting: Optional[EvidenceFragment] = None
) -> EvidenceBundle:
    """계약서(Promotion Contract) 규격에 따른 상태 전이 및 승격 등급 부여"""
    bundle_id = str(uuid.uuid4())
    fact_ids = [fact.fact_id]
    fragment_ids = [frag_fact.fragment_id]
    
    evidence_mask = {
        "ECONOMIC": bool(fact.shares_count > 0 or fact.stake_ratio > 0.0),
        "AS_OF_DATE": False,
        "VOTING": False,
        "OWNERSHIP": False
    }
    
    as_of_date_val = None
    if frag_date:
        evidence_mask["AS_OF_DATE"] = True
        fragment_ids.append(frag_date.fragment_id)
        as_of_date_val = frag_date.extracted_value
        
    ownership_val = None
    if frag_owner and frag_owner.extracted_value != "UNRESOLVED":
        evidence_mask["OWNERSHIP"] = True
        fragment_ids.append(frag_owner.fragment_id)
        ownership_val = frag_owner.extracted_value
        
    voting_val = None
    if frag_voting:
        evidence_mask["VOTING"] = True
        fragment_ids.append(frag_voting.fragment_id)
        voting_val = frag_voting.extracted_value
        
    # 상태 머신 전이
    # 1. Tier 1 판정: ECONOMIC + AS_OF_DATE 충족 시
    eligible_tiers = []
    if evidence_mask["ECONOMIC"] and evidence_mask["AS_OF_DATE"]:
        eligible_tiers.append("VERIFIED_ECONOMIC_HOLDING")
        
    # 2. Tier 2 판정: Tier 1 + VOTING 개별 의결권 충족 시
    if "VERIFIED_ECONOMIC_HOLDING" in eligible_tiers and evidence_mask["VOTING"]:
        eligible_tiers.append("VERIFIED_VOTING_HOLDING")
        
    # 3. Tier 3 판정: Tier 2 + OWNERSHIP 충족 시
    if "VERIFIED_VOTING_HOLDING" in eligible_tiers and evidence_mask["OWNERSHIP"]:
        eligible_tiers.append("VERIFIED_OWNERSHIP_BASIS")
        
    # 최종 Bundle 상태
    if len(eligible_tiers) == 3:
        bundle_status = "RESOLVED"
    elif len(eligible_tiers) >= 1:
        bundle_status = "PARTIALLY_EVIDENCED"
    else:
        bundle_status = "COLLECTING"
        
    return EvidenceBundle(
        bundle_id=bundle_id,
        rcept_no=rcept_no,
        holder_key=holder_name,
        target_corp_code=target_corp_code,
        bundle_status=bundle_status,
        fact_ids=fact_ids,
        fragment_ids=fragment_ids,
        evidence_mask=evidence_mask,
        as_of_date=as_of_date_val,
        ownership_basis_resolved=ownership_val,
        voting_resolved=voting_val,
        eligible_tiers=eligible_tiers
    )
