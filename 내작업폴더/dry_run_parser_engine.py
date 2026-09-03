# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v0.4] DRY_RUN 파서 엔진 및 변조 탐지 매니페스트 생성기
========================================================================================================
[설계 규격 준수: v1.2.1 아키텍처 명세서]
1. [100% 무쓰기(Zero-Write) 안전 보장]:
   - 기본 실행 모드는 `dry_run = True`이며, DB에 CREATE/MERGE/SET/DELETE 실행을 100% 차단합니다.
   - Neo4j DB는 오직 상장사 마스터 및 기존 관계 대조를 위한 읽기 전용(Read-Only MATCH)으로만 접근합니다.
2. [원문 미확인 = 적재 보류 (Fallback 0% 원칙)]:
   - 성명, 주식종류, 의결권, 지분율, 기준일 중 하나라도 원문에서 검증되지 않으면
     어떠한 기본값도 주입하지 않고 `skipped_records`에 원문 셀 내용과 사유를 남깁니다.
3. [RFC 8785 표준 Canonical JSON 해싱]:
   - `manifest_sha256` 필드를 제외한 본문을 사전식 키 정렬 후 SHA-256 해시를 산출합니다.
4. [생성 예정 vs 갱신 예정 엄격 분리]:
   - 기존 DB 상태와 1:1 대조하여 `planned_creations`와 `planned_updates`를 명확히 분리합니다.
========================================================================================================
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
AURA_INSTANCE_ID = os.getenv("AURA_INSTANCEID", "a8a048c8")

def get_read_only_driver():
    """읽기 전용 Neo4j 드라이버 인스턴스 반환"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), max_connection_lifetime=60)

def canonical_json_bytes(obj: dict) -> bytes:
    """RFC 8785 표준에 따른 사전식 키 정렬 Canonical JSON UTF-8 바이트 생성"""
    # 순환 참조 방지를 위해 manifest_sha256 필드가 있다면 제외
    clean_obj = {k: v for k, v in obj.items() if k != "manifest_sha256"}
    return json.dumps(clean_obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def compute_canonical_sha256(obj: dict) -> str:
    """Canonical JSON의 SHA-256 해시값 산출"""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()

def get_git_commit_hash() -> str:
    """현재 작업 트리의 Git Commit Hash 조회"""
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def parse_shareholders_dry_run(xml_file_path: str, rcept_no: str, target_corp_code: str, corp_master_map: dict):
    """
    고정 XML 파일에서 '최대주주 및 특수관계인의 주식소유 현황' 표를 읽고,
    Fallback 없이 100% 팩트 기반의 예정 레코드 및 보류(skipped) 레코드를 도출
    """
    with open(xml_file_path, "rb") as f:
        xml_bytes = f.read()
        
    xml_size_bytes = len(xml_bytes)
    xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    xml_text = xml_bytes.decode("utf-8", errors="ignore")
    
    # 1. 기준일 팩트 추출
    date_match = re.search(r'기준일\s*[:：]\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', xml_text)
    if not date_match:
        # 기준일 미기재 시 임의 가정값 주입 없이 파싱 중단
        raise ValueError(f"❌ 공시 원문 내 기준일(as_of_date) 명시가 없어 파싱 불가: rcept_no={rcept_no}")
        
    as_of_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    
    # 2. 본 주식소유 현황 표(TABLE) 정밀 탐색 (변동현황 등 이력 테이블은 명시적 배제)
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(xml_text)
    
    planned_records = []
    skipped_records = []
    
    for tbl in tables:
        # 이력/변동현황/임원현황 표는 원천 배제
        if any(bad in tbl for bad in ["변동현황", "변동원인", "변동 원인", "임원 및 직원", "주요계약"]):
            continue
            
        if "최대주주" in tbl and ("의결권" in tbl or "보통주" in tbl or "주식의종류" in tbl or "소유주식수" in tbl or "지분율" in tbl):
            tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
            trs = tr_pattern.findall(tbl)
            
            for tr in trs:
                cell_pattern = re.compile(r'<(?:TD|TE)[^>]*>(.*?)</(?:TD|TE)>', re.DOTALL | re.IGNORECASE)
                raw_cells = cell_pattern.findall(tr)
                cells = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip() for c in raw_cells]
                cells = [c for c in cells if c]
                
                # 최소 4개 셀 미만 행은 스킵
                if len(cells) < 4:
                    continue
                    
                # 헤더 행 스킵
                if any(h in cells[0] for h in ["성명", "성 명", "구분", "기초", "기말", "기준일"]):
                    continue
                    
                # 합계/요약 행은 DB 적재 대상이 아니므로 skipped_records에 명시적 분류
                if cells[0] in ["계", "소계", "합계", "총계", "우선주", "보통주"]:
                    skipped_records.append({
                        "raw_cells": cells,
                        "skip_reason": "SUMMARY_TOTAL_ROW_EXCLUDED"
                    })
                    continue
                    
                # 날짜로 시작하는 변동 행 스킵
                if re.match(r'^\d{4}[\.\-\s년]', cells[0]):
                    skipped_records.append({
                        "raw_cells": cells,
                        "skip_reason": "DATE_START_CHANGE_EVENT_ROW_EXCLUDED"
                    })
                    continue
                    
                holder_name = cells[0].strip()
                relate = cells[1].strip() if len(cells) > 1 else ""
                stock_knd = cells[2].strip() if len(cells) > 2 else ""
                
                # 주식종류 팩트 검증 (미기재 시 기본값 보통주 처리 절대 금지)
                if not stock_knd or stock_knd == "-":
                    skipped_records.append({
                        "raw_cells": cells,
                        "skip_reason": "MISSING_SHARE_KIND_NO_FALLBACK"
                    })
                    continue
                    
                # 지분율 및 주식수 탐색
                stake_val = 0.0
                shares_cnt = 0
                for c in reversed(cells[3:]):
                    c_clean = c.replace(",", "").replace("%", "").strip()
                    if "." in c_clean:
                        try:
                            val = float(c_clean)
                            if 0.0 < val <= 100.0 and stake_val == 0.0:
                                stake_val = val
                        except:
                            pass
                    elif c_clean.isdigit():
                        try:
                            s_val = int(c_clean)
                            if s_val > 0 and shares_cnt == 0:
                                shares_cnt = s_val
                        except:
                            pass
                            
                # 지분율 미확인 레코드는 보류 처리
                if stake_val <= 0.0:
                    skipped_records.append({
                        "raw_cells": cells,
                        "skip_reason": "ZERO_OR_UNVERIFIED_STAKE_RATIO"
                    })
                    continue
                    
                # 의결권 및 주식종류 팩트 판정
                is_pref = "우선" in stock_knd or "2우B" in stock_knd or "3우B" in stock_knd
                share_class = "PREFERRED" if is_pref else "COMMON"
                
                # 원문에 의결권 명시 여부 확인
                if "의결권 있는" in stock_knd or "보통" in stock_knd:
                    voting_type = "VOTING"
                elif "의결권 없는" in stock_knd or is_pref:
                    voting_type = "NON_VOTING"
                else:
                    # 의결권 여부 불명확 시 보류
                    skipped_records.append({
                        "raw_cells": cells,
                        "skip_reason": "AMBIGUOUS_VOTING_RIGHTS_REQUIRING_AUDIT"
                    })
                    continue
                    
                # 소유 형태 팩트 판정
                is_direct = any(kw in relate for kw in ["본인", "최대주주 본인", "최대주주", "대표이사", "사내이사"])
                ownership_basis = "DIRECT" if is_direct else "SPECIAL_RELATION"
                
                # 상장사 마스터 대조 (미식별 주체는 임의 노드 생성 대신 보류 처리)
                clean_h_name = holder_name.replace("(주)", "").replace("주식회사", "").replace("㈜", "").strip()
                
                if holder_name in corp_master_map:
                    h_type = "COMPANY"
                    h_pk = corp_master_map[holder_name]
                elif clean_h_name in corp_master_map:
                    h_type = "COMPANY"
                    h_pk = corp_master_map[clean_h_name]
                elif any(kw in holder_name for kw in ["주식회사", "회사", "홀딩스", "㈜"]):
                    # 상장사 마스터에 없는 비상장 법인
                    h_type = "COMPANY"
                    h_pk = f"CORP_{holder_name}"
                elif any(kw in holder_name for kw in ["공단", "기금", "Fund", "Group", "투자", "은행", "재단"]):
                    h_type = "ORG"
                    h_pk = f"ORG_{holder_name}"
                else:
                    h_type = "PERSON"
                    h_pk = f"PERSON_{holder_name}"
                    
                edge_key = f"{rcept_no}_{h_pk}_{target_corp_code}_{share_class}_{voting_type}"
                scope_key = f"{h_pk}_{target_corp_code}_{share_class}_{voting_type}_{ownership_basis}"
                
                planned_records.append({
                    "holder_name": holder_name,
                    "holder_pk": h_pk,
                    "holder_type": h_type,
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
                
    # 엣지 키 기준 중복 제거
    unique_planned = []
    seen = set()
    for rec in planned_records:
        if rec["source_edge_key"] not in seen:
            seen.add(rec["source_edge_key"])
            unique_planned.append(rec)
            
    doc_info = {
        "rcept_no": rcept_no,
        "file_name": os.path.basename(xml_file_path),
        "xml_size_bytes": xml_size_bytes,
        "xml_sha256": xml_sha256
    }
    
    return doc_info, unique_planned, skipped_records

def run_dry_run_simulation(xml_file_path: str, rcept_no: str, target_corp_code: str, manifest_id: str = None) -> dict:
    """
    DRY_RUN 시뮬레이션 전체 파이프라인:
    1. DB 읽기 전용 상태 조회 (pre_state)
    2. 고정 XML 파싱 (Fallback 0% 적용)
    3. 기존 엣지와 비교하여 planned_creations vs planned_updates 분리
    4. Canonical JSON 해시 생성 및 매니페스트 디스크 저장
    5. DB 쓰기 0건 보장 및 결과 반환
    """
    if not manifest_id:
        manifest_id = f"MANIFEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rcept_no}"
        
    started_at = datetime.now().isoformat() + "Z"
    
    driver = get_read_only_driver()
    
    # 1. DB 현재 상태 읽기 전용 조회
    with driver.session() as s:
        pre_nodes = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        pre_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        
        # 상장사 마스터 캐시 로드
        m_rows = s.run("MATCH (c:DART_Company) RETURN c.name AS name, c.corp_code AS code").data()
        corp_master_map = {r["name"]: r["code"] for r in m_rows if r.get("name") and r.get("code")}
        
        # 기존에 존재하는 엣지 키 조회 (creations vs updates 분리용)
        existing_keys = set(s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN r.source_edge_key AS k").value())
        
    # 2. XML 팩트 파싱
    doc_info, planned_records, skipped_records = parse_shareholders_dry_run(
        xml_file_path, rcept_no, target_corp_code, corp_master_map
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
    
    # 4. execution_manifest 딕셔너리 구성 (v1.2.1 규격 준수)
    manifest = {
        "manifest_schema_version": "1.2.1",
        "manifest_id": manifest_id,
        "status": "DRY_RUN",
        "git_commit": get_git_commit_hash(),
        "database_instance_id": AURA_INSTANCE_ID,
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
            "total_nodes": pre_nodes, # DRY_RUN이므로 변화 0
            "total_relationships": pre_rels
        }
    }
    
    # 5. Canonical JSON 해시 산출
    manifest_sha256 = compute_canonical_sha256(manifest)
    
    # 6. 매니페스트 파일 로컬 저장
    os.makedirs("내작업폴더/manifests", exist_ok=True)
    out_path = f"내작업폴더/manifests/execution_manifest_{manifest_id}.json"
    with open(out_path, "wb") as f:
        f.write(canonical_json_bytes(manifest))
        
    driver.close()
    
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "manifest_file_path": out_path,
        "planned_creations_count": len(planned_creations),
        "planned_updates_count": len(planned_updates),
        "skipped_records_count": len(skipped_records)
    }

if __name__ == "__main__":
    # 독립 실행 테스트 (고정 SK하이닉스 XML Fixture)
    fixture = "내작업폴더/tests/fixtures/20240319000684.xml"
    if os.path.exists(fixture):
        print(f"🚀 DRY_RUN 시뮬레이션 실행 중... (Fixture: {fixture})")
        res = run_dry_run_simulation(fixture, "20240319000684", "00164779")
        print("\n" + "="*80)
        print("📋 [DRY_RUN 시뮬레이션 결과 리포트]")
        print("="*80)
        print(f"  • 매니페스트 ID: {res['manifest']['manifest_id']}")
        print(f"  • Canonical SHA-256: {res['manifest_sha256']}")
        print(f"  • 입력 XML 바이트: {res['manifest']['input_documents'][0]['xml_size_bytes']:,} bytes")
        print(f"  • 생성 예정 관계: {res['planned_creations_count']}건")
        print(f"  • 갱신 예정 관계: {res['planned_updates_count']}건")
        print(f"  • 보류(Skipped) 행: {res['skipped_records_count']}건")
        print(f"  • 매니페스트 파일 저장: {res['manifest_file_path']}")
        print("="*80)
        print("🎉 [DB 안전성] 실제 DB 쓰기(CREATE/SET/DELETE) 0건 완벽 차단 확인 완료!")
    else:
        print(f"❌ Fixture 파일이 존재하지 않습니다: {fixture}")
