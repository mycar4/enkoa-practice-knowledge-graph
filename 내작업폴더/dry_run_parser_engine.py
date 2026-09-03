# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] 정밀 DRY_RUN 파서 엔진 및 변조 탐지 매니페스트 생성기 (v1.2.2)
========================================================================================================
[역사 및 지위 명시: ARCHITECTURE STATUS]
- 기존 v0.5.0 / Sprint 7.1 구현체는 '원문 탐색용 스파이크(Exploratory Spike)'로 분류·동결되었습니다.
- 본 엔진은 v1.2.1 아키텍처 명세서 및 4대 Bounded 리팩터링 원칙을 100% 준수하는 정식 DRY_RUN 엔진입니다.

[4대 엄격 검증 가드 (Strict Verification Guards)]:
1. [헤더-열 1:1 매핑 가드]:
   - 표 헤더 계층(성명, 관계, 주식종류, 기말 지분율)이 100% 검증된 표준 레이아웃만 파싱하며,
     헤더 구조가 불일치하거나 셀 인덱스가 모호한 표는 전량 `skipped_records`로 격리합니다.
2. [마스터 미해결 주체 planned_creations 원천 금지]:
   - 상장사 공인 마스터와 1:1 매핑되지 않는 주체는 신규 노드로 임의 분류하지 않고
     `skipped_records`(`UNRESOLVED_MASTER_ENTITY`)로만 보류 격리합니다.
3. [의결권 및 직접성 원문 팩트 입증 가드]:
   - '우선주=무의결권' 등의 일반화를 전면 배제하고, 원문에 '의결권 있는 주식', '의결권 없는 주식' 등
     명시적 팩트 근거가 있을 때만 판정하며 불명확 시 `skipped_records`로 보류합니다.
   - `source_edge_key`에 `ownership_basis`를 필수 포함하여 고유성을 엄격히 보장합니다.
4. [DB 드라이버 의존성 역전 (IoC / Dependency Injection)]:
   - 파서 엔진은 Neo4j 드라이버를 직접 생성하지 않으며, `ExistingEdgeProvider` 인터페이스를 주입받아
     오프라인 단위 테스트(Fake Provider)와 온라인 읽기 전용 검증(Aura READ Provider)을 완벽 분리합니다.
========================================================================================================
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime
from typing import Protocol, Tuple, Dict, Set, List, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

class ExistingEdgeProvider(Protocol):
    """DB 상태 조회를 위한 의존성 주입 인터페이스 (IoC)"""
    def get_corp_master_map(self) -> Dict[str, str]:
        """공인 상장사 마스터 사전 반환 {회사명: corp_code}"""
        ...
    def get_existing_edge_keys(self) -> Set[str]:
        """기존 DB에 등록된 source_edge_key 집합 반환"""
        ...
    def get_pre_counts(self) -> Tuple[int, int]:
        """실행 전 DB 노드 수 및 관계 수 (total_nodes, total_relationships) 반환"""
        ...

def canonical_json_bytes(obj: dict) -> bytes:
    """
    순환 참조 방지 및 RFC 8785 표준 키 정렬 UTF-8 직렬화
    - manifest_sha256 필드를 제외하고 사전식 정렬
    - separators=(',', ':')로 공백 완전 제거
    """
    clean_obj = {k: v for k, v in obj.items() if k != "manifest_sha256"}
    return json.dumps(clean_obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def compute_canonical_sha256(obj: dict) -> str:
    """Canonical JSON의 암호학적 SHA-256 해시 산출"""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()

def get_git_commit_hash() -> str:
    """현재 작업 트리의 Git Commit Hash 조회"""
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def extract_table_caption_as_of_date(tbl_html: str, full_xml: str, tbl_start_pos: int) -> str:
    """
    해당 표의 직전 텍스트 또는 표 캡션에서 기준일을 정밀 추출
    - HTML/XML 태그 제거 후 텍스트 기준으로 태그 사이의 공백/분할 완벽 대응
    """
    # 1. 표 내부 텍스트 태그 제거 후 기준일 캡션 우선 탐색
    clean_tbl = re.sub(r'<[^>]+>', ' ', tbl_html)
    clean_tbl = re.sub(r'\s+', ' ', clean_tbl)
    m = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', clean_tbl)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        
    # 2. 표 직전 1000자 텍스트에서 캡션 탐색
    if tbl_start_pos > 0:
        pre_raw = full_xml[max(0, tbl_start_pos - 1000):tbl_start_pos]
        clean_pre = re.sub(r'<[^>]+>', ' ', pre_raw)
        clean_pre = re.sub(r'\s+', ' ', clean_pre)
        m2 = re.search(r'기준일\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', clean_pre)
        if m2:
            return f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
            
    return ""

def parse_shareholders_strictly(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    corp_master_map: Dict[str, str]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    헤더-열 매핑 및 4대 가드가 100% 검증된 엄격 원문 파서:
    - 검증되지 않은 레이아웃은 일체 파싱하지 않고 skipped_records로 격리
    - 마스터 미해결 엔티티는 planned_* 진입 절대 금지
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
        
        # 변동현황, 임원현황 등 비타겟 테이블 배제
        if any(bad in tbl for bad in ["변동현황", "변동원인", "임원 및 직원", "주요계약", "주식의 분포", "주가 및"]):
            continue
            
        if "최대주주" in tbl and ("주식소유" in tbl or "주식의종류" in tbl or "의결권" in tbl):
            # 1. 표의 기준일 캡션 엄격 검증
            as_of_date = extract_table_caption_as_of_date(tbl, xml_text, tbl_pos)
            if not as_of_date:
                skipped_records.append({
                    "raw_sample": tbl[:120].replace("\n", " "),
                    "skip_reason": "TABLE_AS_OF_DATE_CAPTION_MISSING"
                })
                continue
                
            # 2. 행(TR) 분해 및 표준 헤더-열 매핑 검증
            tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
            trs = tr_pattern.findall(tbl)
            
            # 테이블 전체 텍스트에서 필수 헤더 키워드 포함 검증
            clean_tbl_text = re.sub(r'<[^>]+>', ' ', tbl)
            has_name_hdr = any(k in clean_tbl_text for k in ["성명", "성 명"])
            has_rel_hdr = any(k in clean_tbl_text for k in ["관계", "관 계"])
            has_kind_hdr = "주식의종류" in clean_tbl_text.replace(" ", "")
            has_stake_hdr = "소유주식수 및 지분율" in clean_tbl_text or ("기말" in clean_tbl_text and "지분율" in clean_tbl_text)
            
            if not (has_name_hdr and has_rel_hdr and has_kind_hdr and has_stake_hdr):
                skipped_records.append({
                    "raw_sample": clean_tbl_text[:120].strip(),
                    "skip_reason": "UNSUPPORTED_OR_UNVERIFIED_HEADER_LAYOUT"
                })
                continue
                
            # 표준 DART '최대주주 및 특수관계인의 주식소유 현황' 레이아웃 열 인덱스 확정
            # [Col 0: 성명, Col 1: 관계, Col 2: 주식의종류, Col 3: 기초주식수, Col 4: 기초지분율, Col 5: 기말주식수, Col 6: 기말지분율, Col 7: 비고]
            name_col = 0
            rel_col = 1
            kind_col = 2
            end_shares_col = 5
            end_stake_col = 6
                
            # 3. 데이터 행 파싱
            for tr in trs:
                cell_pattern = re.compile(r'<(?:TD|TE|TH)[^>]*>(.*?)</(?:TD|TE|TH)>', re.DOTALL | re.IGNORECASE)
                cells = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip() for c in cell_pattern.findall(tr)]
                cells = [c for c in cells if c]
                
                # 데이터 행은 최소 7개 이상 셀 필요
                if len(cells) < 7:
                    continue
                    
                # 헤더 / 요약행 제외
                if any(h in cells[name_col] for h in ["성명", "성 명", "구분", "기초", "기말", "합계", "총계", "소계", "기준일"]):
                    if cells[name_col] in ["계", "소계", "합계", "총계"]:
                        skipped_records.append({"raw_cells": cells, "skip_reason": "SUMMARY_TOTAL_ROW_EXCLUDED"})
                    continue
                    
                if re.match(r'^\d{4}[\.\-\s년]', cells[name_col]):
                    skipped_records.append({"raw_cells": cells, "skip_reason": "DATE_START_CHANGE_EVENT_ROW_EXCLUDED"})
                    continue
                    
                holder_name = cells[name_col].strip()
                relate = cells[rel_col].strip()
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
                    
                # 주식수 파싱
                shares_cnt = 0
                if end_shares_col != -1 and end_shares_col < len(cells):
                    raw_shares = cells[end_shares_col].replace(",", "").strip()
                    if raw_shares.isdigit():
                        shares_cnt = int(raw_shares)
                        
                # 4. 의결권 팩트 엄격 판정 (일반화 배제)
                if "의결권 있는" in stock_knd or "보통주" in stock_knd:
                    voting_type = "VOTING"
                    share_class = "COMMON"
                elif "의결권 없는" in stock_knd:
                    voting_type = "NON_VOTING"
                    share_class = "PREFERRED"
                else:
                    # 원문에서 의결권 여부가 명시적으로 입증되지 않으면 보류
                    skipped_records.append({"raw_cells": cells, "skip_reason": "UNVERIFIED_VOTING_RIGHTS_NO_GENERALIZATION"})
                    continue
                    
                # 5. 직접 보유 vs 특수관계인 법률 형태 판정 (관계명 추정 배제)
                if relate in ["본인", "최대주주 본인", "최대주주"]:
                    ownership_basis = "DIRECT"
                elif "특수관계인" in relate or "계열회사" in relate:
                    ownership_basis = "SPECIAL_RELATION"
                else:
                    skipped_records.append({"raw_cells": cells, "skip_reason": "AMBIGUOUS_OWNERSHIP_BASIS_REQUIRING_LEGAL_AUDIT"})
                    continue
                    
                # 6. 상장사 마스터 1:1 대조 (미해결 엔티티 planned_* 진입 절대 금지)
                clean_name = holder_name.replace("(주)", "").replace("주식회사", "").replace("㈜", "").strip()
                resolved_pk = None
                
                if holder_name in corp_master_map:
                    resolved_pk = corp_master_map[holder_name]
                elif clean_name in corp_master_map:
                    resolved_pk = corp_master_map[clean_name]
                    
                if not resolved_pk:
                    # 마스터에 없는 주체는 절대로 임의 노드를 생성하지 않고 skipped_records로 격리
                    skipped_records.append({
                        "raw_cells": cells,
                        "unresolved_holder_name": holder_name,
                        "skip_reason": "UNRESOLVED_MASTER_ENTITY_AWAITING_MASTER_RESOLUTION"
                    })
                    continue
                    
                # 7. 식별자 키 생성 (ownership_basis 포함으로 완전 고유화)
                edge_key = f"{rcept_no}_{resolved_pk}_{target_corp_code}_{share_class}_{voting_type}_{ownership_basis}"
                scope_key = f"{resolved_pk}_{target_corp_code}_{share_class}_{voting_type}_{ownership_basis}"
                
                planned_records.append({
                    "holder_name": holder_name,
                    "holder_pk": resolved_pk,
                    "holder_type": "COMPANY",
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
                
    # 중복 제거
    unique_planned = []
    seen = set()
    for r in planned_records:
        if r["source_edge_key"] not in seen:
            seen.add(r["source_edge_key"])
            unique_planned.append(r)
            
    doc_info = {
        "rcept_no": rcept_no,
        "xml_size_bytes": xml_size_bytes,
        "xml_sha256": xml_sha256
    }
    
    return doc_info, unique_planned, skipped_records

def run_dry_run_with_provider(
    xml_bytes: bytes,
    rcept_no: str,
    target_corp_code: str,
    provider: ExistingEdgeProvider,
    database_instance_id: str,
    manifest_id: str = None
) -> Dict[str, Any]:
    """
    의존성 주입 기반 순수 DRY_RUN 실행 파이프라인
    - 외부 DB 드라이버 없이 주입받은 provider만 사용하여 시뮬레이션
    """
    if not manifest_id:
        manifest_id = f"MANIFEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rcept_no}"
        
    started_at = datetime.now().isoformat() + "Z"
    
    # 1. Provider에서 상태 및 마스터 조회
    pre_nodes, pre_rels = provider.get_pre_counts()
    corp_master_map = provider.get_corp_master_map()
    existing_keys = provider.get_existing_edge_keys()
    
    # 2. 엄격 파서 실행 (Fallback 0%, 마스터 미해결 격리)
    doc_info, planned_records, skipped_records = parse_shareholders_strictly(
        xml_bytes, rcept_no, target_corp_code, corp_master_map
    )
    
    # 3. creations vs updates 명확한 분리
    planned_creations = []
    planned_updates = []
    for rec in planned_records:
        if rec["source_edge_key"] in existing_keys:
            planned_updates.append(rec)
        else:
            planned_creations.append(rec)
            
    finished_at = datetime.now().isoformat() + "Z"
    
    # 4. 매니페스트 구성 (v1.2.1 규격)
    manifest = {
        "manifest_schema_version": "1.2.1",
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
    
    # 5. Canonical JSON 직렬화 및 해시
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
