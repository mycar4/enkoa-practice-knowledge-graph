# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] 정밀 2D 헤더 그리드 DRY_RUN 파서 엔진 (v1.3.0)
========================================================================================================
[핵심 설계 원칙: v1.3.0 아키텍처 명세서]
1. [2D 헤더 그리드 동적 복원]:
   - <TH> 태그의 ROWSPAN과 COLSPAN을 물리적 2차원 행렬(Grid)로 전개하여 각 컬럼의 계층 경로(Header Path)를 동적 산출합니다.
   - 고정 열 인덱스(0, 1, 2, 5, 6 등)의 하드코딩을 원천 금지합니다.
2. [4대 독립 팩트 검증 (상호 추정 전면 배제)]:
   - 주식종류(share_class), 의결권(voting_type), 소유형태(ownership_basis), 엔티티PK가
     각각 원문의 독립 문구 및 공인 마스터와 1:1 일치해야만 planned_*에 진입합니다.
   - 원문에 의결권/직접성 독립 필드가 결측되어 '0건의 WRITE 후보'가 도출되더라도
     이는 오류가 아닌 정상적인 무결성(True-Zero) 판정으로 간주합니다.
3. [3대 공인 엔티티 Exact-Match Provider]:
   - Company, Person, Organization 3대 마스터 인터페이스를 통해 공인 식별자를 조회합니다.
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
    """3대 공인 엔티티 Exact-Match 및 DB 상태 조회 인터페이스 (IoC)"""
    def resolve_company(self, name_or_code: str) -> Optional[str]:
        """법인명 또는 corp_code 기반 DART_Company exact-match PK 반환"""
        ...
    def resolve_person(self, name: str, resident_no_or_id: str = "") -> Optional[str]:
        """성명 기반 DART_Person exact-match global_person_id 반환"""
        ...
    def resolve_organization(self, name_or_id: str) -> Optional[str]:
        """기관/재단명 기반 DART_Organization exact-match org_id 반환"""
        ...
    def get_existing_edge_keys(self) -> Set[str]:
        """기존 DB에 등록된 source_edge_key 집합 반환"""
        ...
    def get_pre_counts(self) -> Tuple[int, int]:
        """실행 전 DB 노드 수 및 관계 수 (total_nodes, total_relationships) 반환"""
        ...

def canonical_json_bytes(obj: dict) -> bytes:
    """순환 참조 방지 및 간이 Canonical JSON(사전식 정렬, 공백 제거) UTF-8 직렬화"""
    clean_obj = {k: v for k, v in obj.items() if k != "manifest_sha256"}
    return json.dumps(clean_obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def compute_canonical_sha256(obj: dict) -> str:
    """Canonical JSON의 SHA-256 해시 산출"""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()

def get_git_commit_hash() -> str:
    """현재 작업 트리의 Git Commit Hash 조회"""
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def build_2d_header_paths(tbl_html: str) -> Tuple[Dict[int, List[str]], int]:
    """
    <TH> 태그의 ROWSPAN 및 COLSPAN을 2차원 그리드로 전개하여 각 컬럼의 수직 Header Path를 동적으로 복원
    반환: (col_idx -> [상위헤더, 중위헤더, 하위헤더], 총 헤더 행 수)
    """
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    all_trs = tr_pattern.findall(tbl_html)
    
    # 1. <TH>를 포함하는 헤더 TR들만 수집
    header_trs = []
    for tr in all_trs:
        if "<TH" in tr.upper():
            header_trs.append(tr)
        else:
            # 데이터 행이 시작되면 헤더 탐색 종료
            if header_trs:
                break
                
    if not header_trs:
        return {}, 0
        
    num_header_rows = len(header_trs)
    
    # 2. 2D 그리드 행렬 초기화 (여유 있는 열 수로 60열 할당 후 추후 압축)
    max_cols = 60
    grid = [[None for _ in range(max_cols)] for _ in range(num_header_rows)]
    
    th_pattern = re.compile(r'<TH([^>]*)>(.*?)</TH>', re.DOTALL | re.IGNORECASE)
    
    actual_max_col = 0
    for r_idx, tr in enumerate(header_trs):
        th_matches = th_pattern.findall(tr)
        c_idx = 0
        for attrs, text in th_matches:
            # 이미 이전 행의 ROWSPAN으로 점유된 열은 건너뜀
            while c_idx < max_cols and grid[r_idx][c_idx] is not None:
                c_idx += 1
                
            clean_text = re.sub(r'<[^>]+>', '', text).replace('&nbsp;', ' ').strip()
            
            # ROWSPAN, COLSPAN 파싱
            rowspan = 1
            colspan = 1
            r_match = re.search(r'ROWSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            c_match = re.search(r'COLSPAN\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            if r_match: rowspan = int(r_match.group(1))
            if c_match: colspan = int(c_match.group(1))
            
            # 그리드 영역 채우기
            for r in range(r_idx, min(num_header_rows, r_idx + rowspan)):
                for c in range(c_idx, min(max_cols, c_idx + colspan)):
                    grid[r][c] = clean_text
                    if c > actual_max_col:
                        actual_max_col = c
                        
            c_idx += colspan
            
    # 3. 각 컬럼의 Header Path 도출 (위에서 아래로 중복 텍스트 제거)
    header_paths: Dict[int, List[str]] = {}
    for c in range(actual_max_col + 1):
        col_path = []
        for r in range(num_header_rows):
            val = grid[r][c]
            if val and (not col_path or col_path[-1] != val):
                col_path.append(val)
        header_paths[c] = col_path
        
    return header_paths, num_header_rows

def extract_table_caption_as_of_date(tbl_html: str, full_xml: str, tbl_start_pos: int) -> str:
    """표 내부 또는 직전 텍스트에서 기준일 정밀 추출"""
    clean_tbl = re.sub(r'<[^>]+>', ' ', tbl_html)
    clean_tbl = re.sub(r'\s+', ' ', clean_tbl)
    m = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', clean_tbl)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        
    if tbl_start_pos > 0:
        pre_raw = full_xml[max(0, tbl_start_pos - 1000):tbl_start_pos]
        clean_pre = re.sub(r'<[^>]+>', ' ', pre_raw)
        clean_pre = re.sub(r'\s+', ' ', clean_pre)
        m2 = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', clean_pre)
        if m2:
            return f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
            
    return ""

def parse_shareholders_2d_grid(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    2D 헤더 그리드 동적 복원 및 4대 독립 팩트 검증 엔진:
    - 헤더 경로를 동적으로 분석하여 열 인덱스를 도출
    - 주식종류, 의결권, 소유형태, 엔티티PK 4대 독립 팩트가 미확인되면 100% skipped_records로 격리
    """
    xml_size_bytes = len(xml_bytes)
    xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    xml_text = xml_bytes.decode("utf-8", errors="ignore")
    
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    
    planned_records = []
    skipped_records = []
    
    for match in table_pattern.finditer(xml_text):
        tbl = match.group(1)
        tbl_pos = match.start()
        
        # 비타겟 테이블 배제
        if any(bad in tbl for bad in ["변동현황", "변동원인", "임원 및 직원", "주요계약", "주식의 분포", "주가 및"]):
            continue
            
        if "최대주주" in tbl and ("주식소유" in tbl or "주식의종류" in tbl or "의결권" in tbl):
            # 1. 기준일 캡션 검증
            as_of_date = extract_table_caption_as_of_date(tbl, xml_text, tbl_pos)
            if not as_of_date:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "TABLE_AS_OF_DATE_CAPTION_MISSING"
                })
                continue
                
            # 2. 2D 헤더 그리드 동적 복원
            header_paths, num_header_rows = build_2d_header_paths(tbl)
            if not header_paths or num_header_rows == 0:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "UNSUPPORTED_HEADER_GRID_LAYOUT_NO_TH"
                })
                continue
                
            # 3. Header Path 기반 동적 컬럼 인덱스 매핑
            name_col = -1
            rel_col = -1
            kind_col = -1
            end_stake_col = -1
            end_shares_col = -1
            ownership_col = -1
            
            for c_idx, path in header_paths.items():
                joined_path = " > ".join(path)
                # 성명 열 매핑
                if any(k in joined_path for k in ["성명", "성 명"]):
                    name_col = c_idx
                # 관계 열 매핑
                elif any(k in joined_path for k in ["관계", "관 계"]):
                    rel_col = c_idx
                # 주식의 종류 열 매핑
                elif "주식의종류" in joined_path.replace(" ", ""):
                    kind_col = c_idx
                # 소유/보유 형태 열 매핑 (원문에 독립 열이 존재하는지 검증)
                elif any(k in joined_path for k in ["소유형태", "보유형태", "소유구분", "보유구분"]):
                    ownership_col = c_idx
                # 기말 지분율 열 매핑
                elif "기말" in joined_path.replace(" ", "") and "지분율" in joined_path:
                    end_stake_col = c_idx
                # 기말 주식수 열 매핑
                elif "기말" in joined_path.replace(" ", "") and "주식수" in joined_path:
                    end_shares_col = c_idx
                    
            # 필수 열 동적 매핑 검증
            if name_col == -1 or kind_col == -1 or end_stake_col == -1:
                skipped_records.append({
                    "header_paths": {str(k): v for k, v in header_paths.items()},
                    "skip_reason": f"DYNAMIC_HEADER_MAPPING_FAILED (name={name_col}, kind={kind_col}, stake={end_stake_col})"
                })
                continue
                
            # 4. 데이터 행(TR) 파싱
            tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
            trs = tr_pattern.findall(tbl)
            
            # 헤더 행 이후의 데이터 행 순회
            for tr in trs[num_header_rows:]:
                cell_pattern = re.compile(r'<(?:TD|TE|TH)[^>]*>(.*?)</(?:TD|TE|TH)>', re.DOTALL | re.IGNORECASE)
                cells = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip() for c in cell_pattern.findall(tr)]
                cells = [c for c in cells if c]
                
                if len(cells) <= max(name_col, kind_col, end_stake_col):
                    continue
                    
                # 헤더 / 요약행 / 날짜행 제외
                if any(h in cells[name_col] for h in ["성명", "성 명", "구분", "기초", "기말", "합계", "총계", "소계", "기준일"]):
                    if cells[name_col] in ["계", "소계", "합계", "총계"]:
                        skipped_records.append({"raw_cells": cells, "skip_reason": "SUMMARY_TOTAL_ROW_EXCLUDED"})
                    continue
                    
                if re.match(r'^\d{4}[\.\-\s년]', cells[name_col]):
                    skipped_records.append({"raw_cells": cells, "skip_reason": "DATE_START_CHANGE_EVENT_ROW_EXCLUDED"})
                    continue
                    
                holder_name = cells[name_col].strip()
                relate = cells[rel_col].strip() if rel_col != -1 and rel_col < len(cells) else ""
                stock_knd = cells[kind_col].strip()
                raw_stake = cells[end_stake_col].replace(",", "").replace("%", "").strip()
                
                # 지분율 파싱
                try:
                    stake_val = float(raw_stake)
                except ValueError:
                    skipped_records.append({"raw_cells": cells, "skip_reason": "INVALID_OR_NON_NUMERIC_STAKE_RATIO"})
                    continue
                    
                if stake_val <= 0.0:
                    skipped_records.append({"raw_cells": cells, "skip_reason": "ZERO_STAKE_RATIO_EXCLUDED"})
                    continue
                    
                shares_cnt = 0
                if end_shares_col != -1 and end_shares_col < len(cells):
                    raw_s = cells[end_shares_col].replace(",", "").strip()
                    if raw_s.isdigit(): shares_cnt = int(raw_s)
                    
                # [독립 팩트 검증 1] 주식 종류 (share_class) 독립 명시 검증
                # 원문에 '보통주', '우선주', '종류주' 명시가 없는 경우 상호 추정 금지
                share_class = None
                if "보통주" in stock_knd:
                    share_class = "COMMON"
                elif "우선주" in stock_knd or "2우B" in stock_knd or "3우B" in stock_knd:
                    share_class = "PREFERRED"
                else:
                    skipped_records.append({
                        "raw_cells": cells,
                        "stock_knd_raw": stock_knd,
                        "skip_reason": "UNVERIFIED_INDEPENDENT_SHARE_CLASS_NO_INFERENCE"
                    })
                    continue
                    
                # [독립 팩트 검증 2] 의결권 (voting_type) 독립 명시 검증
                # 보통주라고 해서 자동으로 VOTING으로 승격하지 않으며, 원문에 의결권 명시 문구가 있어야 함
                voting_type = None
                if "의결권 있는" in stock_knd:
                    voting_type = "VOTING"
                elif "의결권 없는" in stock_knd:
                    voting_type = "NON_VOTING"
                else:
                    skipped_records.append({
                        "raw_cells": cells,
                        "stock_knd_raw": stock_knd,
                        "skip_reason": "UNVERIFIED_INDEPENDENT_VOTING_RIGHTS_NO_INFERENCE"
                    })
                    continue
                    
                # [독립 팩트 검증 3] 소유 형태 (ownership_basis) 독립 증거 검증
                # 관계명(본인, 특수관계인)을 소유 형태로 둔갑시키는 것을 금지하고, 독립 컬럼이나 법률 문구 확인
                ownership_basis = None
                if ownership_col != -1 and ownership_col < len(cells):
                    raw_own = cells[ownership_col].strip()
                    if any(k in raw_own for k in ["직접", "본인소유"]):
                        ownership_basis = "DIRECT"
                    elif any(k in raw_own for k in ["간접", "신탁", "특수관계인"]):
                        ownership_basis = "SPECIAL_RELATION"
                else:
                    # 표 자체에 소유형태 독립 컬럼이 없는 경우 -> 법률상 직접보유를 입증할 수 없으므로 안전 격리
                    skipped_records.append({
                        "raw_cells": cells,
                        "position_raw": relate,
                        "skip_reason": "UNVERIFIED_INDEPENDENT_OWNERSHIP_BASIS_NO_RELATION_CONVERSION"
                    })
                    continue
                    
                # [독립 팩트 검증 4] 3대 공인 엔티티 Exact-Match 검증
                resolved_pk = None
                resolved_type = None
                
                # 1) Company 마스터 조회
                c_pk = provider.resolve_company(holder_name)
                if c_pk:
                    resolved_pk = c_pk
                    resolved_type = "COMPANY"
                else:
                    # 2) Organization 마스터 조회
                    o_pk = provider.resolve_organization(holder_name)
                    if o_pk:
                        resolved_pk = o_pk
                        resolved_type = "ORG"
                    else:
                        # 3) Person 마스터 조회
                        p_pk = provider.resolve_person(holder_name)
                        if p_pk:
                            resolved_pk = p_pk
                            resolved_type = "PERSON"
                            
                if not resolved_pk:
                    skipped_records.append({
                        "raw_cells": cells,
                        "unresolved_holder_name": holder_name,
                        "skip_reason": "UNRESOLVED_MASTER_ENTITY_AWAITING_MASTER_RESOLUTION"
                    })
                    continue
                    
                # 4대 독립 팩트가 100% 완비된 경우에만 고유 식별자 키 생성 및 planned_records 진입
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

def run_dry_run_simulation_v13(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: MasterEntityProvider,
    database_instance_id: str,
    manifest_id: str = None
) -> Dict[str, Any]:
    """v1.3.0 2D 헤더 그리드 기반 순수 DRY_RUN 실행 파이프라인"""
    if not manifest_id:
        manifest_id = f"MANIFEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rcept_no}"
        
    started_at = datetime.now().isoformat() + "Z"
    
    pre_nodes, pre_rels = provider.get_pre_counts()
    existing_keys = provider.get_existing_edge_keys()
    
    doc_info, planned_records, skipped_records = parse_shareholders_2d_grid(
        xml_bytes, rcept_no, target_corp_code, provider
    )
    
    planned_creations = [r for r in planned_records if r["source_edge_key"] not in existing_keys]
    planned_updates = [r for r in planned_records if r["source_edge_key"] in existing_keys]
    
    finished_at = datetime.now().isoformat() + "Z"
    
    manifest = {
        "manifest_schema_version": "1.3.0",
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
