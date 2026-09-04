# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 경제적 보유 관계(:HOLDS_ECONOMIC_STAKE) 실제 승격 실행기 v3.0 (자동 하네스)
================================================================================
[자동 하네스 6대 엄격 계약]
1. 봉인 매니페스트 SHA-256 결속 검증 (하드코딩 기대값과 대조)
2. 19개 후보·증거 파편·XML 원문 해시 전수 사전 재대조 (DB 직접 질의)
3. 법인명 정규화 규칙(법인격 표기 제거) 및 원문명/마스터명/코드 전수 기록
4. 단일 원자적 트랜잭션(Atomic Write) 및 트랜잭션 내부 즉시 감사(In-Tx Assertion)
   - 트랜잭션 내부 감사 실패 시 즉시 예외 발생 -> 자동 전체 롤백(Zero Pollution)
5. 생성 관계에 promotion_manifest_sha256 및 promotion_run_id 필수 기록
6. 사후 감사 및 실행 영수증(Receipt) 발급
================================================================================
"""

import os
import sys
import io
import re
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from neo4j import GraphDatabase, WRITE_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

EXPECTED_MANIFEST_NAME = "promotion_dryrun_20260904_061552.json"
EXPECTED_MANIFEST_SHA256 = "1c4fceb788874b5e4f928d44aa9954423c89188f2f325c758eb8e6b4742e8ac1"
EXPECTED_CANDIDATE_COUNT = 19


def normalize_corp_name(name: str) -> str:
    """
    법인명 정규화 함수 (CORP_CODE_AND_LEGAL_AFFIX_NORMALIZED_MATCH_V1)
    - 법인격 표기 제거: (주), ㈜, [주], 주식회사, (유), 유한회사, (합), 합자회사, 합명회사 등
    - 특수문자, 괄호, 공백 제거 후 대문자화
    """
    if not name:
        return ""
    n = re.sub(r'\((주|유|무|합|사단|재단)\)|㈜|\[주\]|주식회사|유한회사|합자회사|합명회사', '', name)
    n = re.sub(r'[\s\(\)\[\]\.\-_,]', '', n)
    return n.upper().strip()


def pre_audit_candidate_batch(session, planned_rels: List[Dict[str, Any]], manifest_sha256: str, run_id: str) -> List[Dict[str, Any]]:
    """
    적재 전 DB 직접 질의를 통한 19개 후보·증거 파편·XML 원문 해시 전수 사전 재검증 및 파라미터 빌드
    1건이라도 불일치 또는 결손 시 즉시 AssertionError 발생
    """
    print("  🔍 [사전 재검증] DB 직접 질의를 통한 19건 후보·파편·XML 해시·법인명 정규화 전수 검증 시작...")
    promoted_at_str = datetime.now(timezone.utc).isoformat()
    verified_batch = []

    for idx, item in enumerate(planned_rels, 1):
        cid = item["candidate_id"]
        h_code = item.get("source_holding_company", {}).get("corp_code") or item.get("source_node", {}).get("corp_code")
        t_code = item.get("target_investee_company", {}).get("corp_code") or item.get("target_node", {}).get("corp_code")
        facts = item.get("holding_facts", item.get("properties", {}))
        bindings = item.get("evidence_bindings", {})
        temp_meta = item.get("temporal_semantics", {})
        rel_key = item.get("relationship_key") or f"rel-holds-{h_code}-{t_code}-{item['rcept_no']}"

        # DB 직접 질의: 후보, 파편, 회사 노드 실시간 대조
        query = """
        MATCH (c:RawEvidenceCandidate {candidate_id: $cid})
        OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment {role: 'ROW_DATA_EVIDENCE'})
        OPTIONAL MATCH (h:DART_Company {corp_code: $h_code})
        OPTIONAL MATCH (t:DART_Company {corp_code: $t_code})
        RETURN c.rcept_no AS rcept_no,
               c.xml_sha256 AS xml_sha256,
               c.holder_name AS holder_raw_name,
               c.target_corp_code AS target_corp_code,
               c.target_corp_name AS target_corp_name,
               c.shares_count AS cand_shares,
               c.stake_ratio AS cand_stake,
               c.reporting_obligation_date AS cand_date,
               h.name AS h_master_name,
               t.name AS t_master_name,
               collect(f.raw_inner_hash) AS frag_hashes
        """
        row = session.run(query, cid=cid, h_code=h_code, t_code=t_code).single()
        if not row or not row["rcept_no"]:
            raise AssertionError(f"❌ [사전 검증 실패] 후보 노드 결손: candidate_id={cid}")

        # 1) 대상 회사 및 보유 회사 노드 존재 검증
        if not row["h_master_name"]:
            raise AssertionError(f"❌ [사전 검증 실패] 보유회사 DART_Company 결손: corp_code={h_code}")
        if not row["t_master_name"]:
            raise AssertionError(f"❌ [사전 검증 실패] 대상회사 DART_Company 결손: corp_code={t_code}")

        # 2) XML 해시 재대조 (매니페스트 값 vs DB 실제값)
        if row["xml_sha256"] != item["xml_sha256"]:
            raise AssertionError(f"❌ [사전 검증 실패] XML SHA256 불일치: DB={row['xml_sha256']} vs Man={item['xml_sha256']}")

        # 3) ROW_DATA_EVIDENCE 파편 해시 재대조
        frag_hashes = row["frag_hashes"]
        if len(frag_hashes) != 1:
            raise AssertionError(f"❌ [사전 검증 실패] ROW_DATA_EVIDENCE 파편 수 비정상: {len(frag_hashes)}개 (기대값: 1개)")
        if frag_hashes[0] != bindings.get("row_inner_hash"):
            raise AssertionError(f"❌ [사전 검증 실패] 행 내부 해시 불일치: DB={frag_hashes[0]} vs Man={bindings.get('row_inner_hash')}")

        # 4) 수치 및 날짜 정합성 검증
        manifest_shares = int(facts.get("shares_count"))
        manifest_stake = float(facts.get("stake_ratio"))
        if row["cand_shares"] != manifest_shares:
            raise AssertionError(f"❌ [사전 검증 실패] 보유주식수 불일치: DB={row['cand_shares']} vs Man={manifest_shares}")
        if abs(float(row["cand_stake"]) - manifest_stake) > 1e-4:
            raise AssertionError(f"❌ [사전 검증 실패] 지분율 불일치: DB={row['cand_stake']} vs Man={manifest_stake}")
        if row["cand_date"] != facts.get("reporting_obligation_date"):
            raise AssertionError(f"❌ [사전 검증 실패] 보고의무발생일 불일치: DB={row['cand_date']} vs Man={facts.get('reporting_obligation_date')}")

        # 5) 법인명 정규화 매칭 검증
        raw_holder = row["holder_raw_name"]
        raw_target = row["target_corp_name"]
        h_master = row["h_master_name"]
        t_master = row["t_master_name"]

        h_norm_raw = normalize_corp_name(raw_holder)
        h_norm_master = normalize_corp_name(h_master)
        t_norm_raw = normalize_corp_name(raw_target)
        t_norm_master = normalize_corp_name(t_master)

        if h_norm_raw != h_norm_master:
            raise AssertionError(f"❌ [사전 검증 실패] 보유자 정규화 불일치: '{raw_holder}'({h_norm_raw}) != '{h_master}'({h_norm_master})")
        if t_norm_raw != t_norm_master:
            raise AssertionError(f"❌ [사전 검증 실패] 대상회사 정규화 불일치: '{raw_target}'({t_norm_raw}) != '{t_master}'({t_norm_master})")

        verified_batch.append({
            "holder_code": h_code,
            "target_code": t_code,
            "relationship_key": rel_key,
            "candidate_id": cid,
            "rcept_no": item["rcept_no"],
            "xml_sha256": item["xml_sha256"],
            "shares_count": manifest_shares,
            "stake_ratio": manifest_stake,
            "reporting_obligation_date": facts.get("reporting_obligation_date"),
            "temporal_context": temp_meta.get("temporal_context", "HISTORICAL_DISCLOSURE_FACT_2023"),
            "fact_type": temp_meta.get("fact_type", "HISTORICAL_REPORTED_ECONOMIC_STAKE"),
            "temporal_definition": temp_meta.get("temporal_definition", "2023년 공시 보고의무발생일 기준 과거 사실 (현재 2026년 지분 아님)"),
            "table_parser_index": bindings.get("table_parser_index"),
            "all_tr_index": bindings.get("all_tr_index"),
            "data_row_index": bindings.get("data_row_index"),
            "standard_xpath": bindings.get("standard_xpath"),
            "row_raw_parser_xpath": bindings.get("row_raw_parser_xpath", ""),
            "xml_hash_verified": True,  # DB 직접 실측 검증 완료
            "row_inner_hash": bindings.get("row_inner_hash", ""),
            "source_raw_name": raw_holder,
            "source_master_name": h_master,
            "target_raw_name": raw_target,
            "target_master_name": t_master,
            "name_resolution_rule": "CORP_CODE_AND_LEGAL_AFFIX_NORMALIZED_MATCH_V1",
            "promotion_manifest_sha256": manifest_sha256,
            "promotion_run_id": run_id,
            "promoted_at": promoted_at_str,
            "promotion_engine": "PROMOTION_HARNESS_V3.0"
        })

    print(f"  ✅ [사전 재검증 완료] 19/19건 전수 합격 (XML 해시, 파편 해시, 법인명 정규화 일치)")
    return verified_batch


def execute_promotion_batch_tx(tx, batch: List[Dict[str, Any]], run_id: str = "default_run") -> List[Dict[str, Any]]:
    """
    단일 원자적 트랜잭션 내에서:
    1) 필수 DART_Company 노드 전수 사전 존재 검증 (결손 시 예외 -> 즉시 롤백)
    2) 19건 일괄 MERGE 및 신규생성/기존존재(CREATED/ALREADY_EXISTS) 회계 추적
    3) 트랜잭션 내부 즉시 감사 (In-Transaction Assertion):
       - 생성/매칭된 run_id 관계 건수가 정확히 len(batch)인지 검증
       - OWNS_STAKE 관계가 0건인지 검증
       - 검증 불만족 시 트랜잭션 내에서 즉시 예외 발생 -> 원자적 전체 롤백
    """
    # 1. 19건 전체의 보유회사 및 대상회사 노드 사전 존재성 엄격 검증
    all_req_codes = list({item["holder_code"] for item in batch} | {item["target_code"] for item in batch})
    check_cypher = """
    UNWIND $req_codes AS code
    OPTIONAL MATCH (c:DART_Company {corp_code: code})
    RETURN code, (c IS NOT NULL) AS exists
    """
    check_results = tx.run(check_cypher, req_codes=all_req_codes).data()
    missing_codes = [r["code"] for r in check_results if not r["exists"]]
    
    if missing_codes:
        raise ValueError(f"❌ [트랜잭션 롤백] 필수 DART_Company 노드 결손 발견: {missing_codes}")

    # 2. 단일 원자적 트랜잭션 일괄 MERGE 실행
    cypher = """
    UNWIND $batch AS item
    MATCH (h:DART_Company {corp_code: item.holder_code})
    MATCH (t:DART_Company {corp_code: item.target_code})
    
    OPTIONAL MATCH (h)-[existing:HOLDS_ECONOMIC_STAKE {relationship_key: item.relationship_key}]->(t)
    WITH item, h, t, (CASE WHEN existing IS NULL THEN 'CREATED' ELSE 'ALREADY_EXISTS' END) AS action_status

    MERGE (h)-[r:HOLDS_ECONOMIC_STAKE {relationship_key: item.relationship_key}]->(t)
    ON CREATE SET
        r.candidate_id = item.candidate_id,
        r.rcept_no = item.rcept_no,
        r.xml_sha256 = item.xml_sha256,
        r.shares_count = item.shares_count,
        r.stake_ratio = item.stake_ratio,
        r.reporting_obligation_date = item.reporting_obligation_date,
        r.temporal_context = item.temporal_context,
        r.fact_type = item.fact_type,
        r.temporal_definition = item.temporal_definition,
        r.table_parser_index = item.table_parser_index,
        r.all_tr_index = item.all_tr_index,
        r.data_row_index = item.data_row_index,
        r.standard_xpath = item.standard_xpath,
        r.row_raw_parser_xpath = item.row_raw_parser_xpath,
        r.xml_hash_verified = item.xml_hash_verified,
        r.row_inner_hash = item.row_inner_hash,
        r.source_raw_name = item.source_raw_name,
        r.source_master_name = item.source_master_name,
        r.target_raw_name = item.target_raw_name,
        r.target_master_name = item.target_master_name,
        r.name_resolution_rule = item.name_resolution_rule,
        r.promotion_manifest_sha256 = item.promotion_manifest_sha256,
        r.promotion_run_id = item.promotion_run_id,
        r.promoted_at = item.promoted_at,
        r.promotion_engine = item.promotion_engine
    ON MATCH SET
        r.last_verified_run_id = item.promotion_run_id,
        r.last_verified_at = item.promoted_at
    RETURN item.candidate_id AS cid, item.relationship_key AS rel_key, action_status AS action
    """
    result = tx.run(cypher, batch=batch)
    data = result.data()
    
    if len(data) != len(batch):
        raise RuntimeError(f"❌ [트랜잭션 롤백] MERGE 결과 건수({len(data)})가 요청 배치 건수({len(batch)})와 불일치합니다!")

    # 3. 트랜잭션 내부 즉시 감사 (In-Transaction Audit)
    # 커밋 이전에 트랜잭션 안에서 직접 실측하여 위반 시 예외 발생 -> 트랜잭션 자동 롤백
    audit_cypher = """
    MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->()
    WHERE r.promotion_run_id = $run_id OR r.last_verified_run_id = $run_id
    RETURN count(r) AS tagged_holds
    """
    audit_res = tx.run(audit_cypher, run_id=run_id).single()
    if not audit_res or audit_res["tagged_holds"] != len(batch):
        raise RuntimeError(f"❌ [트랜잭션 롤백] 트랜잭션 내 관계 생성/재검증 검증 실패: {audit_res['tagged_holds']} != {len(batch)}")

    owns_check = tx.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()
    if owns_check and owns_check["c"] > 0:
        raise RuntimeError(f"❌ [트랜잭션 롤백] OWNS_STAKE 격리 위반 발견: {owns_check['c']}건 존재!")

    return data


def execute_promotion_to_aura():
    print("=" * 95)
    print("🚀 [DART-Trace] Phase 2: HOLDS_ECONOMIC_STAKE 자동 하네스 승격 실행기 v3.0")
    print("=" * 95)

    # 1. 봉인 매니페스트 로드 및 SHA-256 결속 검증
    manifest_dir = BASE_DIR / "data" / "resolution_manifests"
    target_dryrun_path = manifest_dir / EXPECTED_MANIFEST_NAME
    if not target_dryrun_path.exists():
        raise FileNotFoundError(f"❌ 봉인 매니페스트를 찾을 수 없습니다: {target_dryrun_path}")

    raw_manifest_bytes = target_dryrun_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw_manifest_bytes).hexdigest()
    
    print(f"  📂 봉인 매니페스트: {target_dryrun_path.name}")
    print(f"  🔒 매니페스트 SHA-256: {actual_sha256}")
    
    if actual_sha256 != EXPECTED_MANIFEST_SHA256:
        raise ValueError(f"❌ [무결성 위반] 매니페스트 해시 불일치!\n기대값: {EXPECTED_MANIFEST_SHA256}\n실제값: {actual_sha256}")

    dryrun_data = json.loads(raw_manifest_bytes.decode("utf-8"))
    planned_rels = dryrun_data.get("proposed_holds_economic_stake") or dryrun_data.get("planned_relationships", [])
    print(f"  📋 적재 예정 지분 관계: {len(planned_rels)}건 (봉인 검증 100% 통과)")
    
    if len(planned_rels) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError(f"❌ 적재 대상 건수 불일치: {len(planned_rels)}건 (기대값: {EXPECTED_CANDIDATE_COUNT}건)")

    run_id = f"promrun_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    print(f"  🆔 실행 고유 ID (run_id): {run_id}")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    try:
        # 2. 실행 전 DB 상태 실측 및 후보·파편·XML 전수 사전 재검증
        with driver.session() as session:
            pre_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            pre_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            pre_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            pre_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            print(f"  [적재 전 DB] 전체 노드: {pre_nodes:,}개 | 전체 관계: {pre_rels:,}건 (HOLDS: {pre_holds}건, OWNS: {pre_owns}건)")

            # 사전 전수 재검증 실행 (DB 직접 조회 & 해시 & 정규화 대조)
            batch_params = pre_audit_candidate_batch(session, planned_rels, actual_sha256, run_id)

        # 3. 단일 원자적 트랜잭션(execute_write) 일괄 실행 + 트랜잭션 내부 즉시 감사
        print("  ⚡ 단일 원자적 트랜잭션(Single Atomic Transaction)으로 19건 일괄 적재 시작...")
        with driver.session(default_access_mode=WRITE_ACCESS) as session:
            tx_results = session.execute_write(execute_promotion_batch_tx, batch_params, run_id)

        # 4. 3분할 회계 집계 (created / already_existing / rejected)
        created_count = sum(1 for r in tx_results if r["action"] == "CREATED")
        already_existing_count = sum(1 for r in tx_results if r["action"] == "ALREADY_EXISTS")
        rejected_count = len(batch_params) - len(tx_results)

        print(f"  📊 실행 회계: 신규 생성(CREATED)={created_count}건 | 기존 존재(ALREADY_EXISTS)={already_existing_count}건 | 거부/실패(REJECTED)={rejected_count}건")

        # 5. 실행 후 DB 상태 실측 및 사후 독립 감사
        with driver.session() as session:
            post_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            post_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            post_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            post_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            
            # DB에 영구 기록된 manifest SHA 및 run_id 관계 건수 실측
            stored_holds = session.run("""
                MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->()
                WHERE r.promotion_manifest_sha256 = $m_sha
                RETURN count(r) AS c
            """, m_sha=actual_sha256).single()["c"]

            print(f"  [적재 후 DB] 전체 노드: {post_nodes:,}개 | 전체 관계: {post_rels:,}건 (HOLDS: {post_holds}건, OWNS: {post_owns}건)")
            print(f"  🔒 DB 내 봉인 매니페스트 결속 관계 수: {stored_holds}건")

        delta_nodes = post_nodes - pre_nodes
        delta_rels = post_rels - pre_rels

        # 사후 독립 감사 단정
        assert delta_nodes == 0, f"❌ 노드 수 변동 오류 (오염 발생): Δ={delta_nodes}"
        assert delta_rels == created_count, f"❌ 관계 증가수 불일치: Δ={delta_rels} (기대값: CREATED={created_count})"
        assert post_owns == 0, "❌ OWNS_STAKE 격리 위반: 0건 유지 실패!"
        assert (created_count + already_existing_count) == len(planned_rels), f"❌ 미처리 관계 존재: {rejected_count}건"
        assert post_holds >= len(planned_rels), f"❌ 전체 HOLDS_ECONOMIC_STAKE 누적 수량 오류: {post_holds}"
        assert stored_holds >= len(planned_rels), f"❌ 매니페스트 결속 관계 수량 오류: {stored_holds}"

        # 6. 실행 영수증 발급
        receipt_file = manifest_dir / f"promotion_execution_receipt_{run_id}.json"
        receipt_data = {
            "status": "PROMOTION_SUCCESS",
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "applied_manifest": target_dryrun_path.name,
            "manifest_sha256": actual_sha256,
            "promotion_engine": "PROMOTION_HARNESS_V3.0",
            "accounting": {
                "total_requested": len(planned_rels),
                "created": created_count,
                "already_existing": already_existing_count,
                "rejected": rejected_count
            },
            "name_resolution_rule": {
                "rule_name": "CORP_CODE_AND_LEGAL_AFFIX_NORMALIZED_MATCH_V1",
                "definition": "법인격 표기 제거 후 괄호/공백 정규화 대조 및 DART 8자리 고유코드 일치 검증",
                "all_19_resolved": True
            },
            "temporal_semantics": {
                "temporal_context": "HISTORICAL_DISCLOSURE_FACT_2023",
                "fact_type": "HISTORICAL_REPORTED_ECONOMIC_STAKE",
                "definition": "2023년 공시 보고의무발생일 기준 과거 공시 사실 (2026년 현재 지분 아님)"
            },
            "pre_db_state": {"nodes": pre_nodes, "relationships": pre_rels, "owns_stake": pre_owns, "holds_economic_stake": pre_holds},
            "post_db_state": {"nodes": post_nodes, "relationships": post_rels, "owns_stake": post_owns, "holds_economic_stake": post_holds},
            "db_delta": {"delta_nodes": delta_nodes, "delta_relationships": delta_rels},
            "verified_invariances": {
                "zero_node_pollution": (delta_nodes == 0),
                "exact_relationship_increase_matches_created": (delta_rels == created_count),
                "zero_owns_stake_isolation": (post_owns == 0),
                "manifest_sha256_persisted": True,
                "run_id_persisted": True,
                "idempotent_safe": True
            },
            "tx_execution_details": tx_results
        }
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(receipt_data, f, ensure_ascii=False, indent=2)

        print(f"  🧾 승격 실행 영수증 발급 완료: {receipt_file.name}")
        print("=" * 95)
        print(f"🎯 [Phase 2 적재 성공] 신규 생성: {created_count}건 / 누적: {post_holds}건 | OWNS_STAKE: {post_owns}건 안전 격리")
        print(f"  🔒 DB 결속 매니페스트 SHA-256: {actual_sha256}")
        print(f"  🆔 실행 고유 run_id: {run_id}")
        print("  ⏰ 시간적 의미: 2023년 보고의무발생일 기준 과거 공시 사실 (2026년 현재 지분 아님)")
        print("=" * 95)
        return receipt_data

    finally:
        driver.close()


if __name__ == "__main__":
    execute_promotion_to_aura()
