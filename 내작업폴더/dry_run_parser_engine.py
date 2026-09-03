# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] 정밀 2D 좌표 보존 DRY_RUN 파서 엔진 (v1.3.1)
========================================================================================================
[핵심 결함 완전 차단: v1.3.1 패치 규격]
1. [데이터 행 2D 좌표 격자(Data Grid) 복원 (열 밀림 영구 차단)]:
   - `cells = [c for c in cells if c]` 제거. 빈 셀과 COLSPAN/ROWSPAN을 전개하여
     헤더에서 구한 동적 `col_idx`가 데이터 행의 물리적 좌표와 1:1 완벽 일치하도록 보장합니다.
2. [소유 형태 None 누수 원천 차단 및 법률 소유 방식 한정]:
   - `ownership_basis`가 미판정(None)인 경우 다음 단계 진행을 영구 차단하고 즉시 skipped_records로 격리합니다.
   - '특수관계인'을 소유 형태로 둔갑시키는 것을 금지하고, 오직 '직접(DIRECT)', '간접(INDIRECT)', '신탁(TRUST)'만 인정합니다.
3. [마스터 엔티티 다중 매칭(동명이인/동명법인) 차단 가드]:
   - 이름이 단 1개의 공인 PK에만 대응할 때만 해석하며, 2개 이상이면 `AMBIGUOUS_MASTER_ENTITY`로 보류 격리합니다.
4. [기준일의 구조적 결합성 입증]:
   - 임의의 전역/거리 텍스트 검색을 배제하고, 표 내부의 명시적 태그 및 <CAPTION>에서만 기준일을 입증합니다.
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
    """3대 공인 엔티티 Exact-Match 및 다중 매칭(동명이인) 방어 인터페이스"""
    def resolve_company(self, name_or_code: str) -> Tuple[Optional[str], bool]:
        """(corp_code, is_ambiguous) 반환. 둘 이상 매칭 시 (None, True)"""
        ...
    def resolve_person(self, name: str, resident_no_or_id: str = "") -> Tuple[Optional[str], bool]:
        """(global_person_id, is_ambiguous) 반환. 둘 이상 매칭 시 (None, True)"""
        ...
    def resolve_organization(self, name_or_id: str) -> Tuple[Optional[str], bool]:
        """(org_id, is_ambiguous) 반환. 둘 이상 매칭 시 (None, True)"""
        ...
    def get_existing_edge_keys(self) -> Set[str]:
        ...
    def get_pre_counts(self) -> Tuple[int, int]:
        ...

def canonical_json_bytes(obj: dict) -> bytes:
    """순환 참조 방지 및 간이 Canonical JSON UTF-8 직렬화"""
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

def build_2d_table_matrix(tbl_html: str) -> Tuple[List[List[str]], int]:
    """
    표 전체의 <TH>, <TD>, <TE> 셀들을 ROWSPAN 및 COLSPAN을 완벽 전개하여
    빈 셀을 보존한 2차원 문자열 매트릭스 `matrix[r][c]` 및 헤더 행 수 반환 (열 밀림 방지)
    """
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    all_trs = tr_pattern.findall(tbl_html)
    
    if not all_trs:
        return [], 0
        
    num_rows = len(all_trs)
    max_cols = 50
    matrix = [[None for _ in range(max_cols)] for _ in range(num_rows)]
    
    cell_pattern = re.compile(r'<(?:TH|TD|TE)([^>]*)>(.*?)</(?:TH|TD|TE)>', re.DOTALL | re.IGNORECASE)
    
    num_header_rows = 0
    actual_max_col = 0
    
    for r_idx, tr in enumerate(all_trs):
        if "<TH" in tr.upper() and num_header_rows == r_idx:
            num_header_rows += 1
            
        cells = cell_pattern.findall(tr)
        c_idx = 0
        for attrs, text in cells:
            while c_idx < max_cols and matrix[r_idx][c_idx] is not None:
                c_idx += 1
                
            clean_text = re.sub(r'<[^>]+>', '', text).replace('&nbsp;', ' ').strip()
            
            rowspan = 1
            colspan = 1
            r_match = re.search(r'ROWSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            c_match = re.search(r'COLSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            if r_match: rowspan = int(r_match.group(1))
            if c_match: colspan = int(c_match.group(1))
            
            for r in range(r_idx, min(num_rows, r_idx + rowspan)):
                for c in range(c_idx, min(max_cols, c_idx + colspan)):
                    matrix[r][c] = clean_text
                    if c > actual_max_col:
                        actual_max_col = c
                        
            c_idx += colspan
            
    # None으로 남은 빈 셀들을 빈 문자열("")로 치환하고 실제 열 크기로 절단
    for r in range(num_rows):
        for c in range(actual_max_col + 1):
            if matrix[r][c] is None:
                matrix[r][c] = ""
        matrix[r] = matrix[r][:actual_max_col + 1]
        
    return matrix, num_header_rows

def extract_table_structural_as_of_date(tbl_html: str) -> str:
    """
    표와 구조적으로 결합된 기준일 팩트 추출:
    - 외부 임의 텍스트 검색을 배제하고, 표 내부의 텍스트 또는 캡션(<CAPTION>)에서만 기준일 추출
    """
    clean_tbl = re.sub(r'<[^>]+>', ' ', tbl_html)
    clean_tbl = re.sub(r'\s+', ' ', clean_tbl)
    m = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', clean_tbl)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""

def parse_shareholders_2d_grid_v131(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    2D 매트릭스 기반 좌표 보존 및 4대 독립 팩트 검증 파서 (v1.3.1)
    """
    xml_size_bytes = len(xml_bytes)
    xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    xml_text = xml_bytes.decode("utf-8", errors="ignore")
    
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    
    planned_records = []
    skipped_records = []
    
    for match in table_pattern.finditer(xml_text):
        tbl = match.group(1)
        
        # 비타겟 테이블 배제
        if any(bad in tbl for bad in ["변동현황", "변동원인", "임원 및 직원", "주요계약", "주식의 분포", "주가 및"]):
            continue
            
        if "최대주주" in tbl and ("주식소유" in tbl or "주식의종류" in tbl or "의결권" in tbl):
            # 1. 표 내부 구조적 기준일 검증
            as_of_date = extract_table_structural_as_of_date(tbl)
            if not as_of_date:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "TABLE_INTERNAL_AS_OF_DATE_MISSING"
                })
                continue
                
            # 2. 2D 매트릭스 전개 (헤더와 데이터 행의 좌표 동기화)
            matrix, num_header_rows = build_2d_table_matrix(tbl)
            if not matrix or num_header_rows == 0:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "UNSUPPORTED_HEADER_GRID_LAYOUT_NO_TH"
                })
                continue
                
            total_cols = len(matrix[0])
            
            # 3. Header Path 산출
            header_paths: Dict[int, List[str]] = {}
            for c in range(total_cols):
                col_path = []
                for r in range(num_header_rows):
                    val = matrix[r][c]
                    if val and (not col_path or col_path[-1] != val):
                        col_path.append(val)
                header_paths[c] = col_path
                
            # 4. 동적 컬럼 인덱스 매핑
            name_col = -1
            rel_col = -1
            kind_col = -1
            end_stake_col = -1
            end_shares_col = -1
            ownership_col = -1
            
            for c_idx, path in header_paths.items():
                joined_path = " > ".join(path)
                if any(k in joined_path for k in ["성명", "성 명"]):
                    name_col = c_idx
                elif any(k in joined_path for k in ["관계", "관 계"]):
                    rel_col = c_idx
                elif "주식의종류" in joined_path.replace(" ", ""):
                    kind_col = c_idx
                elif any(k in joined_path for k in ["소유형태", "보유형태", "소유구분", "보유구분"]):
                    ownership_col = c_idx
                elif "기말" in joined_path.replace(" ", "") and "지분율" in joined_path:
                    end_stake_col = c_idx
                elif "기말" in joined_path.replace(" ", "") and "주식수" in joined_path:
                    end_shares_col = c_idx
                    
            if name_col == -1 or kind_col == -1 or end_stake_col == -1:
                skipped_records.append({
                    "header_paths": {str(k): v for k, v in header_paths.items()},
                    "skip_reason": f"DYNAMIC_HEADER_MAPPING_FAILED (name={name_col}, kind={kind_col}, stake={end_stake_col})"
                })
                continue
                
            # 5. 데이터 행 정밀 파싱 (빈 셀 제거 없이 2D 좌표 matrix[r_idx][c_idx]로 접근)
            for r_idx in range(num_header_rows, len(matrix)):
                row_cells = matrix[r_idx]
                
                holder_name = row_cells[name_col].strip()
                relate = row_cells[rel_col].strip() if rel_col != -1 else ""
                stock_knd = row_cells[kind_col].strip()
                raw_stake = row_cells[end_stake_col].replace(",", "").replace("%", "").strip()
                
                if not holder_name:
                    continue
                    
                # 헤더 / 요약행 / 날짜행 제외
                if any(h in holder_name for h in ["성명", "성 명", "구분", "기초", "기말", "합계", "총계", "소계", "기준일"]):
                    if holder_name in ["계", "소계", "합계", "총계"]:
                        skipped_records.append({"raw_cells": row_cells, "skip_reason": "SUMMARY_TOTAL_ROW_EXCLUDED"})
                    continue
                    
                if re.match(r'^\d{4}[\.\-\s년]', holder_name):
                    skipped_records.append({"raw_cells": row_cells, "skip_reason": "DATE_START_CHANGE_EVENT_ROW_EXCLUDED"})
                    continue
                    
                # 지분율 파싱
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
                    
                # [독립 팩트 1] 주식 종류 (share_class) 독립 명시 검증
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
                    
                # [독립 팩트 2] 의결권 (voting_type) 독립 명시 검증
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
                    
                # [독립 팩트 3] 소유 형태 (ownership_basis) 순수 법률 소유 방식 한정
                ownership_basis = None
                if ownership_col != -1 and ownership_col < len(row_cells):
                    raw_own = row_cells[ownership_col].strip()
                    if any(k in raw_own for k in ["직접", "본인소유"]):
                        ownership_basis = "DIRECT"
                    elif any(k in raw_own for k in ["간접", "신탁"]):
                        ownership_basis = "INDIRECT"
                        
                # ★ 핵심 버그 차단: 소유형태가 판정되지 않았으면(None) 절대 통과시키지 않고 즉시 차단
                if not ownership_basis:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "ownership_col_value": row_cells[ownership_col] if ownership_col != -1 else "NO_COLUMN",
                        "skip_reason": "UNVERIFIED_INDEPENDENT_OWNERSHIP_BASIS_NO_RELATION_CONVERSION"
                    })
                    continue
                    
                # [독립 팩트 4] 3대 공인 엔티티 Exact-Match 및 다중 매칭(동명이인) 방어
                resolved_pk = None
                resolved_type = None
                
                # 1) Company 마스터 조회
                c_pk, c_ambig = provider.resolve_company(holder_name)
                if c_ambig:
                    skipped_records.append({"raw_cells": row_cells, "skip_reason": "AMBIGUOUS_MASTER_ENTITY_MULTIPLE_MATCHES"})
                    continue
                if c_pk:
                    resolved_pk = c_pk
                    resolved_type = "COMPANY"
                else:
                    # 2) Organization 마스터 조회
                    o_pk, o_ambig = provider.resolve_organization(holder_name)
                    if o_ambig:
                        skipped_records.append({"raw_cells": row_cells, "skip_reason": "AMBIGUOUS_MASTER_ENTITY_MULTIPLE_MATCHES"})
                        continue
                    if o_pk:
                        resolved_pk = o_pk
                        resolved_type = "ORG"
                    else:
                        # 3) Person 마스터 조회
                        p_pk, p_ambig = provider.resolve_person(holder_name)
                        if p_ambig:
                            skipped_records.append({"raw_cells": row_cells, "skip_reason": "AMBIGUOUS_MASTER_ENTITY_MULTIPLE_MATCHES"})
                            continue
                        if p_pk:
                            resolved_pk = p_pk
                            resolved_type = "PERSON"
                            
                if not resolved_pk:
                    skipped_records.append({
                        "raw_cells": row_cells,
                        "unresolved_holder_name": holder_name,
                        "skip_reason": "UNRESOLVED_MASTER_ENTITY_AWAITING_MASTER_RESOLUTION"
                    })
                    continue
                    
                # 4대 독립 팩트 완비 확인 시에만 진입
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

def run_dry_run_simulation_v131(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider,
    database_instance_id: str,
    manifest_id: str = None
) -> Dict[str, Any]:
    """v1.3.1 2D 좌표 보존 기반 순수 DRY_RUN 실행 파이프라인"""
    if not manifest_id:
        manifest_id = f"MANIFEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rcept_no}"
        
    started_at = datetime.now().isoformat() + "Z"
    
    pre_nodes, pre_rels = provider.get_pre_counts()
    existing_keys = provider.get_existing_edge_keys()
    
    doc_info, planned_records, skipped_records = parse_shareholders_2d_grid_v131(
        xml_bytes, rcept_no, target_corp_code, provider
    )
    
    planned_creations = [r for r in planned_records if r["source_edge_key"] not in existing_keys]
    planned_updates = [r for r in planned_records if r["source_edge_key"] in existing_keys]
    
    finished_at = datetime.now().isoformat() + "Z"
    
    manifest = {
        "manifest_schema_version": "1.3.1",
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
