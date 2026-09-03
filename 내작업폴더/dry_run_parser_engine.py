# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] 무결성 2D 그리드 DRY_RUN 파서 엔진 (v1.3.2)
========================================================================================================
[핵심 결함 완전 차단: v1.3.2 패치 규격]
1. [소유형태 TRUST 분리 및 모호성 배제]:
   - '신탁'을 INDIRECT로 왜곡하지 않고 'TRUST'로 명확히 분리하며, 모호한 문구는 100% skipped_records 격리.
2. [기준일 진정한 구조적 결합 (Strict Caption/Header Binding)]:
   - 표 본문 전체 검색 전면 폐지. 오직 <CAPTION> 태그 내부 또는 표 첫 행 <TH> 단독 제목 셀의 기준일만 인정.
3. [3대 엔티티 타입 교차 다의성(Cross-Type Ambiguity) 완전 배제]:
   - Company 우선순위 편향 전면 폐지. Company, Organization, Person 3대 타입 후보를 모두 수집(Union)하여
     전체 통틀어 정확히 단 1개의 PK만 일치할 때만 승격. 둘 이상 매칭 시 AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE 격리.
4. [데이터 행의 병합 셀(ROWSPAN/COLSPAN) 임의 채우기 금지]:
   - 데이터 행에 ROWSPAN > 1 또는 COLSPAN > 1 셀이 존재할 경우 일반 행으로 왜곡하지 않고
     UNSUPPORTED_MERGED_DATA_ROW로 안전 격리.
========================================================================================================
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime
from typing import Protocol, Tuple, Dict, Set, List, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

class MasterEntityProvider(Protocol):
    """3대 공인 엔티티 Exact-Match 및 다중 매칭 방어 인터페이스"""
    def resolve_all_types(self, name_or_code: str) -> List[Tuple[str, str]]:
        """
        주어진 이름에 매칭되는 모든 (PK, ENTITY_TYPE) 튜플 목록 반환
        예: [('01596425', 'COMPANY')] or [('P1', 'PERSON'), ('C1', 'COMPANY')]
        """
        ...
    def get_existing_edge_keys(self) -> Set[str]:
        ...
    def get_pre_counts(self) -> Tuple[int, int]:
        ...

def canonical_json_bytes(obj: dict) -> bytes:
    clean_obj = {k: v for k, v in obj.items() if k != "manifest_sha256"}
    return json.dumps(clean_obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def compute_canonical_sha256(obj: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()

def get_git_commit_hash() -> str:
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def extract_strict_structural_as_of_date(tbl_html: str) -> str:
    """
    엄격 구조적 기준일 팩트 추출:
    - 표 본문 텍스트 전체 검색 전면 폐지!
    - 1) <CAPTION>...</CAPTION> 내부의 기준일
    - 2) 표 첫 번째 행(<TR>) 단독 <TH> 제목 셀 내부의 기준일
    위 두 위치에 명속된 날짜만 인정하며, 그 외 본문 셀/비고/각주 날짜는 일체 불인정.
    """
    # 1. <CAPTION> 태그 내부 검사
    cap_match = re.search(r'<CAPTION[^>]*>(.*?)</CAPTION>', tbl_html, re.DOTALL | re.IGNORECASE)
    if cap_match:
        cap_clean = re.sub(r'<[^>]+>', ' ', cap_match.group(1))
        m = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', cap_clean)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 2. 첫 번째 행 단독 <TH> 제목 셀 검사
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    trs = tr_pattern.findall(tbl_html)
    if trs:
        first_tr = trs[0]
        th_pattern = re.compile(r'<TH[^>]*>(.*?)</TH>', re.DOTALL | re.IGNORECASE)
        ths = th_pattern.findall(first_tr)
        if len(ths) == 1:
            th_clean = re.sub(r'<[^>]+>', ' ', ths[0])
            m = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', th_clean)
            if m:
                return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return ""

def parse_header_paths_2d(header_trs: List[str]) -> Tuple[Dict[int, List[str]], int]:
    """헤더 <TH>의 ROWSPAN/COLSPAN을 2D 매트릭스로 전개하여 Header Path 산출"""
    num_header_rows = len(header_trs)
    max_cols = 50
    grid = [[None for _ in range(max_cols)] for _ in range(num_header_rows)]
    
    th_pattern = re.compile(r'<TH([^>]*)>(.*?)</TH>', re.DOTALL | re.IGNORECASE)
    actual_max_col = 0
    
    for r_idx, tr in enumerate(header_trs):
        th_matches = th_pattern.findall(tr)
        c_idx = 0
        for attrs, text in th_matches:
            while c_idx < max_cols and grid[r_idx][c_idx] is not None:
                c_idx += 1
                
            clean_text = re.sub(r'<[^>]+>', '', text).replace('&nbsp;', ' ').strip()
            rowspan = 1
            colspan = 1
            r_m = re.search(r'ROWSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            c_m = re.search(r'COLSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            if r_m: rowspan = int(r_m.group(1))
            if c_m: colspan = int(c_m.group(1))
            
            for r in range(r_idx, min(num_header_rows, r_idx + rowspan)):
                for c in range(c_idx, min(max_cols, c_idx + colspan)):
                    grid[r][c] = clean_text
                    if c > actual_max_col:
                        actual_max_col = c
            c_idx += colspan
            
    header_paths: Dict[int, List[str]] = {}
    for c in range(actual_max_col + 1):
        col_path = []
        for r in range(num_header_rows):
            val = grid[r][c]
            if val and (not col_path or col_path[-1] != val):
                col_path.append(val)
        header_paths[c] = col_path
        
    return header_paths, actual_max_col + 1

def parse_shareholders_strict_v132(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    v1.3.2 엄격 원문 팩트 파서:
    - 엄격 구조적 기준일 결속
    - 데이터 행 병합 셀(ROWSPAN/COLSPAN) 임의 채우기 금지
    - 소유형태 TRUST 분리 및 모호성 차단
    - 3대 엔티티 교차 다의성(Cross-Type Ambiguity) 완전 배제
    """
    xml_size_bytes = len(xml_bytes)
    xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    xml_text = xml_bytes.decode("utf-8", errors="ignore")
    
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    
    planned_records = []
    skipped_records = []
    
    for match in table_pattern.finditer(xml_text):
        tbl = match.group(1)
        
        if any(bad in tbl for bad in ["변동현황", "변동원인", "임원 및 직원", "주요계약", "주식의 분포", "주가 및"]):
            continue
            
        if "최대주주" in tbl and ("주식소유" in tbl or "주식의종류" in tbl or "의결권" in tbl):
            # 1. 엄격 구조적 기준일 검증 (<CAPTION> 또는 1행 단독 <TH>)
            as_of_date = extract_strict_structural_as_of_date(tbl)
            if not as_of_date:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "TABLE_STRICT_CAPTION_OR_HEADER_AS_OF_DATE_MISSING"
                })
                continue
                
            # 2. 헤더 TR 분리
            tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
            all_trs = tr_pattern.findall(tbl)
            
            header_trs = []
            data_trs = []
            is_header = True
            for tr in all_trs:
                # 단독 기준일 행은 헤더 매트릭스에서 제외
                if "기준일" in tr and len(re.findall(r'<TH', tr, re.IGNORECASE)) == 1:
                    continue
                if is_header and "<TH" in tr.upper():
                    header_trs.append(tr)
                else:
                    is_header = False
                    data_trs.append(tr)
                    
            if not header_trs or not data_trs:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "UNSUPPORTED_TABLE_NO_HEADER_OR_DATA_ROWS"
                })
                continue
                
            # 3. 2D 헤더 매트릭스 전개
            header_paths, total_cols = parse_header_paths_2d(header_trs)
            
            # 4. 동적 컬럼 인덱스 매핑
            name_col = -1
            rel_col = -1
            kind_col = -1
            end_stake_col = -1
            end_shares_col = -1
            ownership_col = -1
            
            for c_idx, path in header_paths.items():
                joined = " > ".join(path)
                if any(k in joined for k in ["성명", "성 명"]):
                    name_col = c_idx
                elif any(k in joined for k in ["관계", "관 계"]):
                    rel_col = c_idx
                elif "주식의종류" in joined.replace(" ", ""):
                    kind_col = c_idx
                elif any(k in joined for k in ["소유형태", "보유형태", "소유구분", "보유구분"]):
                    ownership_col = c_idx
                elif "기말" in joined.replace(" ", "") and "지분율" in joined:
                    end_stake_col = c_idx
                elif "기말" in joined.replace(" ", "") and "주식수" in joined:
                    end_shares_col = c_idx
                    
            if name_col == -1 or kind_col == -1 or end_stake_col == -1:
                skipped_records.append({
                    "header_paths": {str(k): v for k, v in header_paths.items()},
                    "skip_reason": f"DYNAMIC_HEADER_MAPPING_FAILED (name={name_col}, kind={kind_col}, stake={end_stake_col})"
                })
                continue
                
            # 5. 데이터 행 정밀 검증
            cell_pattern = re.compile(r'<(?:TD|TE|TH)([^>]*)>(.*?)</(?:TD|TE|TH)>', re.DOTALL | re.IGNORECASE)
            
            for d_idx, tr in enumerate(data_trs):
                raw_cells = cell_pattern.findall(tr)
                
                # ★ 핵심 가드 4: 데이터 행의 병합 셀(ROWSPAN/COLSPAN) 임의 채우기 금지
                has_rowspan = any(re.search(r'ROWSPAN\s*=\s*["\']?([2-9]|\d{2,})["\']?', attrs, re.IGNORECASE) for attrs, _ in raw_cells)
                has_colspan = any(re.search(r'COLSPAN\s*=\s*["\']?([2-9]|\d{2,})["\']?', attrs, re.IGNORECASE) for attrs, _ in raw_cells)
                if has_rowspan or has_colspan:
                    skipped_records.append({
                        "row_index": d_idx,
                        "raw_tr": tr[:140].replace("\n", " "),
                        "skip_reason": "UNSUPPORTED_MERGED_DATA_ROW (ROWSPAN/COLSPAN present in data row)"
                    })
                    continue
                    
                # 빈 셀 보존 텍스트 리스트
                row_cells = [re.sub(r'<[^>]+>', '', t).replace('&nbsp;', ' ').strip() for _, t in raw_cells]
                
                # 열 수 불일치 행 안전 격리
                if len(row_cells) != total_cols:
                    skipped_records.append({
                        "row_index": d_idx,
                        "row_len": len(row_cells),
                        "expected_cols": total_cols,
                        "skip_reason": "UNSUPPORTED_DATA_ROW_COLUMN_COUNT_MISMATCH"
                    })
                    continue
                    
                holder_name = row_cells[name_col]
                relate = row_cells[rel_col] if rel_col != -1 else ""
                stock_knd = row_cells[kind_col]
                raw_stake = row_cells[end_stake_col].replace(",", "").replace("%", "").strip()
                
                if not holder_name:
                    continue
                    
                # 요약 / 날짜 행 격리
                if any(h in holder_name for h in ["성명", "성 명", "구분", "기초", "기말", "합계", "총계", "소계", "기준일"]):
                    if holder_name in ["계", "소계", "합계", "총계"]:
                        skipped_records.append({"raw_cells": row_cells, "skip_reason": "SUMMARY_TOTAL_ROW_EXCLUDED"})
                    continue
                    
                if re.match(r'^\d{4}[\.\-\s년]', holder_name):
                    skipped_records.append({"raw_cells": row_cells, "skip_reason": "DATE_START_CHANGE_EVENT_ROW_EXCLUDED"})
                    continue
                    
                # 지분율 검증
                try:
                    stake_val = float(raw_stake)
                except ValueError:
                    skipped_records.append({"raw_cells": row_cells, "skip_reason": "INVALID_OR_NON_NUMERIC_STAKE_RATIO"})
                    continue
                    
                if stake_val <= 0.0:
                    skipped_records.append({"raw_cells": row_cells, "skip_reason": "ZERO_STAKE_RATIO_EXCLUDED"})
                    continue
                    
                shares_cnt = 0
                if end_shares_col != -1:
                    raw_s = row_cells[end_shares_col].replace(",", "").strip()
                    if raw_s.isdigit(): shares_cnt = int(raw_s)
                    
                # [독립 팩트 1] 주식 종류 독립 명시
                share_class = None
                if "보통주" in stock_knd:
                    share_class = "COMMON"
                elif "우선주" in stock_knd or "2우B" in stock_knd or "3우B" in stock_knd:
                    share_class = "PREFERRED"
                else:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "stock_knd_raw": stock_knd,
                        "skip_reason": "UNVERIFIED_INDEPENDENT_SHARE_CLASS_NO_INFERENCE"
                    })
                    continue
                    
                # [독립 팩트 2] 의결권 독립 명시
                voting_type = None
                if "의결권 있는" in stock_knd:
                    voting_type = "VOTING"
                elif "의결권 없는" in stock_knd:
                    voting_type = "NON_VOTING"
                else:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "stock_knd_raw": stock_knd,
                        "skip_reason": "UNVERIFIED_INDEPENDENT_VOTING_RIGHTS_NO_INFERENCE"
                    })
                    continue
                    
                # [독립 팩트 3] 소유 형태 TRUST 분리 및 모호성 원천 차단
                ownership_basis = None
                if ownership_col != -1:
                    raw_own = row_cells[ownership_col].strip()
                    if any(k in raw_own for k in ["직접", "본인소유"]):
                        ownership_basis = "DIRECT"
                    elif any(k in raw_own for k in ["간접"]):
                        ownership_basis = "INDIRECT"
                    elif any(k in raw_own for k in ["신탁"]):
                        ownership_basis = "TRUST"
                        
                if not ownership_basis:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "ownership_col_value": row_cells[ownership_col] if ownership_col != -1 else "NO_COLUMN",
                        "skip_reason": "UNVERIFIED_INDEPENDENT_OWNERSHIP_BASIS_NO_RELATION_CONVERSION"
                    })
                    continue
                    
                # [독립 팩트 4] 3대 엔티티 교차 다의성(Cross-Type Ambiguity) 완전 배제
                all_candidates = provider.resolve_all_types(holder_name)
                
                # 후보가 0개인 경우
                if len(all_candidates) == 0:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "unresolved_holder_name": holder_name,
                        "skip_reason": "UNRESOLVED_MASTER_ENTITY_AWAITING_MASTER_RESOLUTION"
                    })
                    continue
                    
                # 후보가 2개 이상인 경우 (동명이인 또는 Company/Person/Org 간 교차 다의성)
                if len(all_candidates) > 1:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "holder_name": holder_name,
                        "candidate_matches": [f"{pk}({t})" for pk, t in all_candidates],
                        "skip_reason": "AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE_MULTIPLE_MATCHES"
                    })
                    continue
                    
                # 정확히 단 1개의 후보만 매칭된 경우
                resolved_pk, resolved_type = all_candidates[0]
                
                edge_key = f"{rcept_no}_{resolved_pk}_{target_corp_code}_{share_class}_{voting_type}_{ownership_basis}"
                scope_key = f"{resolved_pk}_{target_corp_code}_{share_class}_{voting_type}_{ownership_basis}"
                
                planned_records.append({
                    "holder_name": holder_name,
                    "holder_pk": resolved_pk,
                    "holder_type": resolved_type,
                    "target_code": target_corp_code,
                    "stake": stake_val,
                    "shares_count": shares_cnt,
                    "position": relate,
                    "stock_knd_raw": stock_knd,
                    "share_class": share_class,
                    "voting_type": voting_type,
                    "ownership_basis": ownership_basis,
                    "source_edge_key": edge_key,
                    "current_scope": scope_key,
                    "source_rcept_no": rcept_no,
                    "as_of_date": as_of_date
                })
                
    doc_info = {
        "rcept_no": rcept_no,
        "xml_size_bytes": xml_size_bytes,
        "xml_sha256": xml_sha256
    }
    return doc_info, planned_records, skipped_records

def run_dry_run_simulation_v132(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider,
    database_instance_id: str,
    manifest_id: str = None
) -> Dict[str, Any]:
    """v1.3.2 엄격 가드 기반 순수 DRY_RUN 시뮬레이션"""
    if not manifest_id:
        manifest_id = f"MANIFEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rcept_no}"
        
    started_at = datetime.now().isoformat() + "Z"
    
    pre_nodes, pre_rels = provider.get_pre_counts()
    existing_keys = provider.get_existing_edge_keys()
    
    doc_info, planned_records, skipped_records = parse_shareholders_strict_v132(
        xml_bytes, rcept_no, target_corp_code, provider
    )
    
    planned_creations = [r for r in planned_records if r["source_edge_key"] not in existing_keys]
    planned_updates = [r for r in planned_records if r["source_edge_key"] in existing_keys]
    
    finished_at = datetime.now().isoformat() + "Z"
    
    manifest = {
        "manifest_schema_version": "1.3.2",
        "manifest_id": manifest_id,
        "status": "DRY_RUN",
        "git_commit": get_git_commit_hash(),
        "database_instance_id": database_instance_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "input_documents": [doc_info],
        "pre_execution_state": {
            "total_nodes": pre_nodes,
            "total_relationships": pre_rels
        },
        "planned_creations": planned_creations,
        "planned_updates": planned_updates,
        "skipped_records": skipped_records,
        "post_execution_state_expected": {
            "total_nodes": pre_nodes,
            "total_relationships": pre_rels
        }
    }
    
    c_bytes = canonical_json_bytes(manifest)
    manifest_sha256 = compute_canonical_sha256(manifest)
    
    return {
        "manifest": manifest,
        "manifest_bytes": c_bytes,
        "manifest_sha256": manifest_sha256,
        "planned_creations_count": len(planned_creations),
        "planned_updates_count": len(planned_updates),
        "skipped_records_count": len(skipped_records)
    }
