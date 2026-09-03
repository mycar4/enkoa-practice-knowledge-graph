# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 5PCT_GENERAL_ART142_V1 명시적 어댑터 (Explicit Adapter)
================================================================================
[어댑터 계약 규격]
1. 대상 서식: ACODE="00636" (주식등의 대량보유상황보고서 일반서식)
2. 문서 혈통 삼위일체:
   - 요청 rcept_no
   - 원문 XML SHA-256
   - 실행 매니페스트 (Execution Manifest)
3. 2D 동적 헤더 매핑:
   - '성명(명칭)', '합계 > 주수', '합계 > 비율' 컬럼 동적 탐색 (하드코딩 배제!)
   - 헤더 누락 시 즉시 UNSUPPORTED_LAYOUT_MISSING_REQUIRED_HEADERS로 안전 거부
4. 데이터 행 감사:
   - 외부 행 인덱스 주입 없이 자체 판정
   - 요약행/부적격행 개별 격리 (문서 전체 억지 해석 금지)
5. Zero DB Write: RawEvidenceCandidate 및 증거 조각 매니페스트만 산출
================================================================================
"""

import os
import sys
import re
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.abspath("내작업폴더"))
from dry_run_parser_engine import parse_header_paths_2d

ADAPTER_NAME = "5PCT_GENERAL_ART142_V1"
ADAPTER_VERSION = "1.0.0"

def clean_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def compute_sha256(text_or_bytes: Any) -> str:
    if isinstance(text_or_bytes, str):
        return hashlib.sha256(text_or_bytes.encode('utf-8')).hexdigest()
    return hashlib.sha256(text_or_bytes).hexdigest()

def run_adapter_5pct_general_art142_v1(
    xml_bytes: bytes,
    rcept_no: Optional[str] = None,
    user_supplied_filename: Optional[str] = None
) -> Dict[str, Any]:
    """5PCT_GENERAL_ART142_V1 어댑터 실행 진입점 (순수 비파괴 오프라인)"""
    run_timestamp = datetime.now(timezone.utc).isoformat()
    xml_sha256 = compute_sha256(xml_bytes)
    xml_text = xml_bytes.decode('utf-8', errors='ignore')
    
    manifest: Dict[str, Any] = {
        "adapter_name": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "execution_timestamp": run_timestamp,
        "provenance": {
            "requested_rcept_no": rcept_no,
            "user_supplied_filename": user_supplied_filename,
            "xml_size_bytes": len(xml_bytes),
            "xml_sha256": xml_sha256
        },
        "adapter_status": "RUNNING",
        "rejection_reason": None,
        "document_metadata": {},
        "header_mapping": {},
        "candidates_count": 0,
        "quarantined_rows_count": 0,
        "candidates": [],
        "quarantined_rows": [],
        "evidence_fragments": []
    }
    
    # -------------------------------------------------------------
    # 1. 서식 사전 검증 (Document Pre-check)
    # -------------------------------------------------------------
    doc_name_m = re.search(r'<DOCUMENT-NAME[^>]*ACODE=["\']([^"\']+)["\'][^>]*>(.*?)</DOCUMENT-NAME>', xml_text, re.IGNORECASE)
    if not doc_name_m:
        doc_name_m = re.search(r'<DOCUMENT-NAME[^>]*>(.*?)</DOCUMENT-NAME>', xml_text, re.IGNORECASE)
        
    doc_acode = doc_name_m.group(1).strip() if (doc_name_m and len(doc_name_m.groups()) > 1) else ""
    doc_title = clean_whitespace(doc_name_m.group(2) if len(doc_name_m.groups()) > 1 else doc_name_m.group(1)) if doc_name_m else ""
    
    is_5pct_general = (doc_acode == "00636") or ("대량보유상황보고서" in doc_title and "일반" in doc_title)
    if not is_5pct_general:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_NOT_5PCT_GENERAL"
        return manifest
        
    manifest["document_metadata"]["document_title"] = doc_title
    manifest["document_metadata"]["document_acode"] = doc_acode
    
    # -------------------------------------------------------------
    # 2. 문서 레벨 주체 및 날짜 증거 추출
    # -------------------------------------------------------------
    # 2-1. 발행회사
    comp_m = re.search(r'<COMPANY-NAME[^>]*AREGCIK=["\'](\d{8})["\'][^>]*>(.*?)</COMPANY-NAME>', xml_text, re.IGNORECASE)
    if not comp_m:
        comp_m = re.search(r'<TE[^>]*ACODE=["\']CRP_NM["\'][^>]*>(.*?)</TE>', xml_text, re.IGNORECASE)
        
    target_corp_code = comp_m.group(1).strip() if (comp_m and comp_m.group(1).isdigit()) else ""
    target_corp_name = clean_whitespace(comp_m.group(2) if len(comp_m.groups()) > 1 else comp_m.group(1)) if comp_m else ""
    
    if not target_corp_name:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_TARGET_COMPANY_MISSING"
        return manifest
        
    frag_target_comp = {
        "fragment_id": str(uuid.uuid4()),
        "role": "TARGET_COMPANY",
        "xpath": "//COMPANY-NAME | //TE[@ACODE='CRP_NM']",
        "raw_inner_html": clean_whitespace(comp_m.group(0)),
        "raw_inner_hash": compute_sha256(clean_whitespace(comp_m.group(0))),
        "extracted_value": f"name={target_corp_name}, code={target_corp_code}"
    }
    manifest["evidence_fragments"].append(frag_target_comp)
    manifest["document_metadata"]["target_corp_name"] = target_corp_name
    manifest["document_metadata"]["target_corp_code"] = target_corp_code

    # 2-2. 보고자 (Reporter)
    rep_m = re.search(r'<TE[^>]*ACODE=["\']RPT_RSP_NM["\'][^>]*>(.*?)</TE>', xml_text, re.IGNORECASE)
    reporter_name = clean_whitespace(rep_m.group(1)) if rep_m else ""
    if not reporter_name:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_REPORTER_MISSING"
        return manifest
        
    frag_reporter = {
        "fragment_id": str(uuid.uuid4()),
        "role": "REPORTER",
        "xpath": "//TE[@ACODE='RPT_RSP_NM']",
        "raw_inner_html": clean_whitespace(rep_m.group(0)),
        "raw_inner_hash": compute_sha256(clean_whitespace(rep_m.group(0))),
        "extracted_value": reporter_name
    }
    manifest["evidence_fragments"].append(frag_reporter)
    manifest["document_metadata"]["reporter_name"] = reporter_name

    # 2-3. 보고의무발생일 (Reporting Obligation Date)
    duty_date_m = re.search(r'<TU[^>]*AUNIT=["\']RPT_RSP_DT["\'][^>]*AUNITVALUE=["\'](\d{8})["\'][^>]*>(.*?)</TU>', xml_text, re.IGNORECASE)
    reporting_obligation_date = ""
    if duty_date_m:
        raw_d = duty_date_m.group(1)
        reporting_obligation_date = f"{raw_d[:4]}-{raw_d[4:6]}-{raw_d[6:8]}"
        frag_duty_date = {
            "fragment_id": str(uuid.uuid4()),
            "role": "REPORTING_OBLIGATION_DATE",
            "xpath": "//TU[@AUNIT='RPT_RSP_DT']",
            "raw_inner_html": clean_whitespace(duty_date_m.group(0)),
            "raw_inner_hash": compute_sha256(clean_whitespace(duty_date_m.group(0))),
            "extracted_value": reporting_obligation_date
        }
        manifest["evidence_fragments"].append(frag_duty_date)
    else:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_REPORTING_OBLIGATION_DATE_MISSING"
        return manifest
        
    manifest["document_metadata"]["reporting_obligation_date"] = reporting_obligation_date

    # -------------------------------------------------------------
    # 3. 제142조 표 탐색 및 동적 2D 헤더 매핑
    # -------------------------------------------------------------
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(xml_text)
    
    target_table_idx = None
    target_table_html = None
    
    for idx, tbl in enumerate(tables):
        clean_tbl = clean_whitespace(re.sub(r'<[^>]+>', ' ', tbl))
        if "제142조" in clean_tbl and any(k in clean_tbl for k in ["제1호", "제2호", "보고자", "특별관계자"]):
            target_table_idx = idx
            target_table_html = tbl
            break
            
    if target_table_idx is None:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_TABLE_142_NOT_FOUND"
        return manifest
        
    manifest["document_metadata"]["table_index"] = target_table_idx
    manifest["document_metadata"]["table_inner_hash"] = compute_sha256(clean_whitespace(target_table_html))

    # 2D 헤더 경로 동적 매핑
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    all_trs = tr_pattern.findall(target_table_html)
    
    # 헤더 행 추출 (TH 태그를 포함하는 행들)
    header_trs = [tr for tr in all_trs if "<TH" in tr.upper()]
    if len(header_trs) < 2:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_HEADER_ROWS_INSUFFICIENT"
        return manifest
        
    try:
        header_paths, total_cols = parse_header_paths_2d(header_trs, max_cols=60)
    except Exception as e:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = f"UNSUPPORTED_LAYOUT_HEADER_PARSE_ERROR_{str(e)}"
        return manifest
        
    formatted_headers = {col: " > ".join(path) for col, path in header_paths.items()}
    manifest["header_mapping"] = formatted_headers

    # 3대 필수 헤더 경로 동적 탐색 (하드코딩 인덱스 전면 배제!)
    holder_col_idx = None
    shares_col_idx = None
    stake_col_idx = None
    relation_col_idx = None
    article_item_cols: Dict[str, int] = {} # 예: {"제1호": 3, "제2호": 4}

    for col, path in header_paths.items():
        joined_path = " > ".join(path)
        clean_path_no_space = joined_path.replace(" ", "")
        
        # 1) 성명(명칭) 열
        if any(k in clean_path_no_space for k in ["성명", "성명(명칭)", "명칭"]) and not any(bad in clean_path_no_space for bad in ["합계", "주수", "비율", "생년월일", "사업자등록번호"]):
            holder_col_idx = col
            
        # 2) 주식수 합계 열
        if ("합계" in clean_path_no_space) and any(k in clean_path_no_space for k in ["주수", "주식수", "수량"]):
            shares_col_idx = col
            
        # 3) 지분율 합계 열
        if ("합계" in clean_path_no_space) and any(k in clean_path_no_space for k in ["비율", "지분율", "보유비율"]):
            stake_col_idx = col
            
        # 4) 관계 열
        if "관계" in clean_path_no_space and not any(bad in clean_path_no_space for bad in ["소유", "합계", "주수"]):
            relation_col_idx = col
            
        # 5) 제142조 조항 열
        for item_num in ["제1호", "제2호", "제3호", "제4호", "제5호", "제6호", "제7호"]:
            if item_num in clean_path_no_space:
                article_item_cols[item_num] = col

    # 3대 필수 헤더 중 하나라도 결측 시 즉시 안전 거부!
    if holder_col_idx is None or shares_col_idx is None or stake_col_idx is None:
        manifest["adapter_status"] = "REJECTED"
        manifest["rejection_reason"] = "UNSUPPORTED_LAYOUT_MISSING_REQUIRED_HEADERS"
        manifest["missing_headers_detail"] = {
            "holder_col_found": holder_col_idx is not None,
            "shares_col_found": shares_col_idx is not None,
            "stake_col_found": stake_col_idx is not None
        }
        return manifest

    manifest["document_metadata"]["matched_columns"] = {
        "holder_col_idx": holder_col_idx,
        "shares_col_idx": shares_col_idx,
        "stake_col_idx": stake_col_idx,
        "relation_col_idx": relation_col_idx,
        "article_item_cols": article_item_cols
    }

    # -------------------------------------------------------------
    # 4. 데이터 행 순회 및 검증 (Row-Level Audit)
    # -------------------------------------------------------------
    data_trs = [tr for tr in all_trs if tr not in header_trs]
    
    for r_idx, tr in enumerate(data_trs):
        raw_cells = re.findall(r'<(?:TD|TE|TH|TU)[^>]*>(.*?)</(?:TD|TE|TH|TU)>', tr, re.DOTALL | re.IGNORECASE)
        cells = [clean_whitespace(re.sub(r'<[^>]+>', '', c)) for c in raw_cells]
        
        # 기본 셀 수 검증
        req_max_idx = max(holder_col_idx, shares_col_idx, stake_col_idx)
        if len(cells) <= req_max_idx:
            manifest["quarantined_rows"].append({
                "data_row_index": r_idx,
                "reason": f"ROW_CELLS_INSUFFICIENT_{len(cells)}_REQUIRED_{req_max_idx+1}",
                "raw_preview": clean_whitespace(tr)[:100]
            })
            continue
            
        # 요약/헤더 행 건너뛰기
        raw_holder = cells[holder_col_idx]
        if not raw_holder or raw_holder in ["보고자", "특별관계자", "-", "소계", "합계", "총계"]:
            # 만약 0열에 이름이 있고 holder_col_idx에 빈 문자열인 경우 등 방어
            if relation_col_idx is not None and cells[relation_col_idx] in ["보고자", "특별관계자"] and not raw_holder:
                pass
            manifest["quarantined_rows"].append({
                "data_row_index": r_idx,
                "reason": f"SKIPPED_SUMMARY_OR_NON_HOLDER_ROW_{raw_holder}",
                "raw_preview": clean_whitespace(tr)[:100]
            })
            continue

        # 수치 추출 (동적 결속된 열에서만 정확히 추출!)
        shares_str = cells[shares_col_idx].replace(",", "").strip()
        stake_str = cells[stake_col_idx].replace("%", "").strip()
        
        if not shares_str.isdigit():
            manifest["quarantined_rows"].append({
                "data_row_index": r_idx,
                "reason": f"METRIC_SHARES_NOT_DIGIT_{shares_str}",
                "raw_preview": clean_whitespace(tr)[:100]
            })
            continue
            
        try:
            stake_val = float(stake_str)
            shares_cnt = int(shares_str)
        except Exception as e:
            manifest["quarantined_rows"].append({
                "data_row_index": r_idx,
                "reason": f"METRIC_PARSE_FLOAT_FAILED_{stake_str}",
                "raw_preview": clean_whitespace(tr)[:100]
            })
            continue
            
        if shares_cnt <= 0 and stake_val <= 0.0:
            manifest["quarantined_rows"].append({
                "data_row_index": r_idx,
                "reason": "ZERO_HOLDING_ROW",
                "raw_preview": clean_whitespace(tr)[:100]
            })
            continue

        # 소유형태 원문 표기 보존 (수치 추론 일체 배제! 제142조 각 호 열의 원문 셀값 배열 전수 보관)
        article_142_raw_entries = []
        for item_name, col_i in sorted(article_item_cols.items()):
            if col_i < len(cells):
                cell_item_val = cells[col_i].strip()
                article_142_raw_entries.append({
                    "item_name": item_name,
                    "col_idx": col_i,
                    "header_path": manifest["header_mapping"].get(col_i, f"제142조 > {item_name}"),
                    "raw_cell_value": cell_item_val
                })

        # 증거 파편 생성 및 결속
        candidate_id = str(uuid.uuid4())
        tr_clean_inner = clean_whitespace(tr)
        
        frag_row = {
            "fragment_id": str(uuid.uuid4()),
            "role": "ROW_DATA_EVIDENCE",
            "xpath": f"//TABLE[{target_table_idx}]//TR[{r_idx}]",
            "raw_inner_html": tr_clean_inner,
            "raw_inner_hash": compute_sha256(tr_clean_inner),
            "extracted_value": f"holder={raw_holder}, shares={shares_cnt}, stake={stake_val}%"
        }
        manifest["evidence_fragments"].append(frag_row)
        
        candidate_record = {
            "candidate_id": candidate_id,
            "status": "RAW_EVIDENCE_CANDIDATE",
            "reporter_name": reporter_name,
            "holder_name": raw_holder,
            "target_corp_name": target_corp_name,
            "target_corp_code": target_corp_code,
            "reporting_obligation_date": reporting_obligation_date,
            "shares_count": shares_cnt,
            "stake_ratio": stake_val,
            "article_142_raw_entries": article_142_raw_entries,
            "evidence_fragment_ids": [
                frag_target_comp["fragment_id"],
                frag_reporter["fragment_id"],
                frag_duty_date["fragment_id"],
                frag_row["fragment_id"]
            ]
        }
        manifest["candidates"].append(candidate_record)

    manifest["candidates_count"] = len(manifest["candidates"])
    manifest["quarantined_rows_count"] = len(manifest["quarantined_rows"])
    manifest["adapter_status"] = "SUCCESS" if manifest["candidates_count"] > 0 else "ZERO_CANDIDATES_PROCESSED"
    
    return manifest
