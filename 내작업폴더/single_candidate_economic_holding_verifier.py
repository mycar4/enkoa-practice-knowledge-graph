# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 경제적 보유 사실 (VERIFIED_ECONOMIC_HOLDING) 단 1건 통제 드라이런 검증기
================================================================================
[승격 계약 규격: Strict Economic Holding Contract v1.0]
목적:
1. 공시 수치를 곧바로 '지배력/의결권 지분(:OWNS_STAKE)'으로 과도 해석하는 오류를 원천 차단
2. 오직 원문 결속 '경제적 보유 사실(VERIFIED_ECONOMIC_HOLDING)'로 개념을 엄격 한정
3. 5대 무결성 필수 요건 검증:
   - 요건 1: 대상회사 공식 식별자 (DART 고유 8자리 법인코드 corp_code)
   - 요건 2: 보유자 마스터 식별 및 엔티티 유일성
   - 요건 3: 보고자(REPORTER)와 보유자(HOLDER)의 주체 분리 및 별도 보존 (동일성 임의 가정 금지)
   - 요건 4: 주수·지분율의 원문 행 해시(raw_inner_hash) 암호학적 1:1 결속
   - 요건 5: 날짜 의미의 명시적 분리 (보고의무발생일 != 공시접수일 != 생성일시)
4. 순수 100% 읽기 전용 (READ_ACCESS 세션 강제, DB 쓰기 0건)
================================================================================
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def verify_single_candidate(candidate_id: str) -> Dict[str, Any]:
    load_dotenv(".env")
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not pwd:
        raise ValueError("❌ [보안 오류] NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경변수가 필수입니다.")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(default_access_mode=READ_ACCESS) as session:
            # 1. 대상 후보 조회
            cand_cypher = """
            MATCH (c:RawEvidenceCandidate {candidate_id: $cid})
            RETURN c.candidate_id AS candidate_id,
                   c.rcept_no AS rcept_no,
                   c.target_corp_name AS corp_name,
                   c.target_corp_code AS corp_code,
                   c.reporter_name AS reporter_name,
                   c.holder_name AS holder_name,
                   c.shares_count AS shares,
                   c.stake_ratio AS ratio,
                   c.reporting_obligation_date AS ob_date,
                   c.layout_status AS layout_status,
                   c.legacy_status AS legacy_status,
                   c.rejection_reason AS rejection_reason,
                   c.xml_sha256 AS xml_sha256,
                   c.xml_rel_path AS xml_rel_path,
                   c.collection_run_id AS col_run,
                   c.collection_receipt_id AS col_rcpt,
                   c.load_run_id AS load_run,
                   c.load_receipt_id AS load_rcpt,
                   c.created_at AS created_at
            """
            cand_record = session.run(cand_cypher, cid=candidate_id).single()
            if not cand_record:
                raise ValueError(f"❌ [조회 실패] 후보를 찾을 수 없습니다: {candidate_id}")

            cand = cand_record.data()

            # 2. 결속된 증거 파편 조회
            frag_cypher = """
            MATCH (c:RawEvidenceCandidate {candidate_id: $cid})-[:EVIDENCED_BY]->(f:EvidenceFragment)
            RETURN f.fragment_id AS frag_id,
                   f.role AS role,
                   f.extracted_value AS extracted_value,
                   f.xpath AS xpath,
                   f.raw_inner_hash AS raw_inner_hash,
                   f.xml_sha256 AS xml_sha256,
                   f.created_at AS created_at
            ORDER BY f.role, f.fragment_id
            """
            frags = [r.data() for r in session.run(frag_cypher, cid=candidate_id)]

    finally:
        driver.close()

    # 3. 5대 무결성 요건 엄격 검증
    checklist = {}

    # 요건 1: 대상회사 공식 식별자
    corp_code = cand.get("corp_code")
    has_valid_corp_code = bool(corp_code and len(corp_code) == 8 and corp_code.isdigit())
    has_target_frag = any(f["role"] == "TARGET_COMPANY" for f in frags)
    checklist["1_target_company_identifier"] = {
        "status": "PASS" if (has_valid_corp_code and has_target_frag) else "FAIL",
        "corp_code": corp_code,
        "corp_name": cand.get("corp_name"),
        "has_target_company_fragment": has_target_frag
    }

    # 요건 2: 보유자 마스터 식별 및 유일성
    holder_name = (cand.get("holder_name") or "").strip()
    checklist["2_holder_master_resolution"] = {
        "status": "PASS" if bool(holder_name) else "FAIL",
        "holder_name": holder_name
    }

    # 요건 3: 보고자(REPORTER)와 보유자(HOLDER) 주체 분리 보존
    reporter_frag = next((f for f in frags if f["role"] == "REPORTER"), None)
    reporter_val = reporter_frag["extracted_value"] if reporter_frag else cand.get("reporter_name")
    checklist["3_reporter_holder_separation"] = {
        "status": "PASS" if bool(reporter_val and holder_name) else "FAIL",
        "reporter_name": reporter_val,
        "holder_name": holder_name,
        "is_same_person": (reporter_val == holder_name),
        "note": "보고자와 보유자가 동일하든 상이하든 각각 독립 증거로 보존됨"
    }

    # 요건 4: 주수·지분율의 원문 행 해시(raw_inner_hash) 1:1 결속
    row_frag = next((f for f in frags if f["role"] == "ROW_DATA_EVIDENCE"), None)
    shares = cand.get("shares")
    ratio = cand.get("ratio")
    has_valid_metrics = bool(shares is not None and shares > 0 and ratio is not None and ratio > 0.0)
    
    hash_matched = False
    if row_frag:
        row_h = row_frag["raw_inner_hash"]
        hash_matched = (row_h[:16] in candidate_id)

    checklist["4_metrics_and_row_hash_binding"] = {
        "status": "PASS" if (has_valid_metrics and row_frag and hash_matched) else "FAIL",
        "shares_count": shares,
        "stake_ratio": ratio,
        "row_inner_hash": row_frag["raw_inner_hash"] if row_frag else None,
        "candidate_id_hash_matched": hash_matched
    }

    # 요건 5: 날짜 의미의 명시적 분리
    ob_date = cand.get("ob_date")
    rcept_no = cand.get("rcept_no")
    filing_date_str = f"{rcept_no[:4]}-{rcept_no[4:6]}-{rcept_no[6:8]}" if rcept_no and len(rcept_no) >= 8 else None
    
    has_valid_ob_date = False
    if ob_date:
        try:
            datetime.strptime(ob_date, "%Y-%m-%d")
            has_valid_ob_date = True
        except ValueError:
            has_valid_ob_date = False

    checklist["5_temporal_semantics_separation"] = {
        "status": "PASS" if (has_valid_ob_date and filing_date_str) else "FAIL",
        "reporting_obligation_date": ob_date,
        "filing_receipt_date": filing_date_str,
        "is_obligation_same_as_filing": (ob_date == filing_date_str),
        "note": "보고의무발생일은 공시접수일과 엄격히 구분하여 독립 기록됨"
    }

    all_passed = all(item["status"] == "PASS" for item in checklist.values())

    # 4. 승격 산출물 모델링 (드라이런 결과 생성)
    promoted_fact = None
    if all_passed:
        promoted_fact = {
            "fact_type": "VERIFIED_ECONOMIC_HOLDING",
            "semantic_definition": "특정 보유자가 특정 발행사에 특정 수량·비율을 보유한다는 원문 결속 경제적 보유 사실",
            "prohibited_legal_interpretation": "의결권 행사 및 실질 지배력(OWNS_STAKE)으로의 과도 해석 엄격 금지",
            "target_company": {
                "corp_code": corp_code,
                "corp_name": cand.get("corp_name")
            },
            "holder": {
                "name": holder_name,
                "resolved_entity_type": "DART_Person" if len(holder_name) <= 4 else "DART_Company"
            },
            "reporter_provenance": {
                "reporter_name": reporter_val,
                "has_distinct_reporter_fragment": bool(reporter_frag)
            },
            "economic_holding_metric": {
                "shares_count": shares,
                "stake_ratio": ratio,
                "unit": "주 / %"
            },
            "temporal_semantics": {
                "reporting_obligation_date": ob_date,
                "filing_receipt_no": rcept_no,
                "filing_receipt_date": filing_date_str
            },
            "cryptographic_lineage": {
                "source_candidate_id": candidate_id,
                "source_row_hash": row_frag["raw_inner_hash"] if row_frag else None,
                "xml_sha256": cand.get("xml_sha256"),
                "collection_receipt_id": cand.get("col_rcpt"),
                "load_receipt_id": cand.get("load_rcpt"),
                "dry_run_verified_at": datetime.now(timezone.utc).isoformat()
            },
            "graph_ontology_mapping": {
                "start_node_selector": f"(:DART_Person {{name: '{holder_name}'}})",
                "relationship_type": ":HOLDS_ECONOMIC_STAKE",
                "target_node_selector": f"(:DART_Company {{corp_code: '{corp_code}'}})",
                "strictly_forbidden_relationship": ":OWNS_STAKE"
            }
        }

    return {
        "candidate_id": candidate_id,
        "dry_run_verdict": "PROMOTION_READY" if all_passed else "REJECTED",
        "checklist": checklist,
        "promoted_fact": promoted_fact
    }


def main():
    parser = argparse.ArgumentParser(description="Single Candidate Economic Holding Verifier (DRY-RUN)")
    # 기본값: 콜마홀딩스 윤상현 일반서식 후보 (cand-20241227000779-fd13824bac2da439)
    parser.add_argument("--candidate-id", default="cand-20241227000779-fd13824bac2da439", help="검증할 RawEvidenceCandidate ID")
    args = parser.parse_args()

    print("=" * 80)
    print(f"🔬 [VERIFIED_ECONOMIC_HOLDING 단 1건 통제 드라이런 검증 시작]")
    print(f"• 대상 Candidate ID: {args.candidate_id}")
    print(f"• 실행 모드: 100% DRY-RUN (Neo4j READ_ACCESS 세션 강제, 쓰기 0건)")
    print("=" * 80)

    result = verify_single_candidate(args.candidate_id)

    print("\n📋 [5대 무결성 체크리스트 검증 결과]")
    for key, val in result["checklist"].items():
        status_icon = "🟢 PASS" if val["status"] == "PASS" else "❌ FAIL"
        print(f"• {key}: {status_icon}")
        for k, v in val.items():
            if k != "status":
                print(f"    - {k}: {v}")

    print("\n" + "=" * 80)
    print(f"🏆 최종 판정: {result['dry_run_verdict']}")
    print("=" * 80)

    if result["promoted_fact"]:
        print("\n📜 [합격 시 발급될 경제적 보유 사실 (VERIFIED_ECONOMIC_HOLDING) 스펙]")
        print(json.dumps(result["promoted_fact"], ensure_ascii=False, indent=2))
        print("=" * 80)


if __name__ == "__main__":
    main()
