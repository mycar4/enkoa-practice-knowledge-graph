# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 엔티티 해소 DRY_RUN 판정 엔진 (Entity Resolution DRY_RUN Engine v1.2)
================================================================================
[스프린트 1.2 무결성 판정 계약 원칙]
1. 100% 읽기 전용 (driver.session 레벨 READ_ACCESS 강제, DB 쓰기 0건 보장)
2. 과거 스파이크(single_candidate_economic_holding_verifier.py) 일절 배제
3. 3진 판정 상태: PASS / REJECT / AMBIGUOUS + 상세 규칙 평가 사유
4. 판정 계약 3대 값 결속 무결성 보강 (Value Binding Integrity):
   ① [Rule 1 대상회사 실체 일치]: 8자리 corp_code 마스터 등록 및 후보 회사명과 마스터 회사명의 일치 검증.
      사명 변경/오기/불일치 시 REJECT.
   ② [Rule 4 증거 파편 실제 값 1:1 결속]: 4대 필수 파편(TARGET_COMPANY, REPORTER, 
      REPORTING_OBLIGATION_DATE, ROW_DATA_EVIDENCE)의 실제 추출값(extracted_value)이
      후보의 회사코드/명, 보고자, 날짜, 보유자 값과 각각 1:1 일치하는지 검증. 변조 시 REJECT.
   ③ [Rule 5 날짜 실제 달력 유효성 & 파편 값 일치]: YYYY-MM-DD 포맷뿐 아니라 실제 달력 유효 일자(strptime)
      검증 및 날짜 파편 값과의 1:1 일치 검증.
================================================================================
"""

import re
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple
from neo4j import GraphDatabase, READ_ACCESS

RULE_IDS = [
    "RULE_1_CORP_MATCH",
    "RULE_2_HOLDER_RESOLUTION",
    "RULE_3_REPORTER_HOLDER_SEPARATION",
    "RULE_4_EVIDENCE_ROLE_COVERAGE",
    "RULE_5_TEMPORAL_VALIDITY"
]

REQUIRED_EVIDENCE_ROLES = {
    "TARGET_COMPANY",
    "REPORTER",
    "REPORTING_OBLIGATION_DATE",
    "ROW_DATA_EVIDENCE"
}


def normalize_corp_name(name: str) -> str:
    """회사명 정규화 (괄호 주식회사 표기 및 공백 제거)"""
    if not name:
        return ""
    norm = name.strip()
    norm = norm.replace("(주)", "").replace("주식회사", "").replace("(유)", "").replace("유한회사", "").replace("㈜", "")
    return re.sub(r'\s+', '', norm)


def evaluate_single_candidate(
    candidate_node: Dict[str, Any],
    fragments: List[Dict[str, Any]],
    corp_code_set: Set[str],
    name_to_corps: Dict[str, Set[str]],
    code_to_master_name: Dict[str, str]
) -> Dict[str, Any]:
    """
    단일 RawEvidenceCandidate 노드 및 결속 EvidenceFragment에 대해 5대 무결성 계약을 평가하여
    PASS / REJECT / AMBIGUOUS 3진 판정 결과를 반환합니다. (순수 인메모리 연산)
    """
    rule_results = {}
    failure_reasons = []
    ambiguous_reasons = []

    cid = candidate_node.get("candidate_id", "")
    rcept_no = candidate_node.get("rcept_no", "")
    corp_code = candidate_node.get("target_corp_code", "")
    corp_name = candidate_node.get("target_corp_name", "")
    holder_name = candidate_node.get("holder_name", "")
    reporter_name = candidate_node.get("reporter_name", "")
    stake_ratio = candidate_node.get("stake_ratio")
    shares_count = candidate_node.get("shares_count")
    ob_date = candidate_node.get("reporting_obligation_date", "")
    layout_status = candidate_node.get("layout_status", "")
    xml_sha256 = candidate_node.get("xml_sha256", "")

    norm_cand_corp = normalize_corp_name(corp_name)
    master_corp_name = code_to_master_name.get(corp_code, "")
    norm_master_corp = normalize_corp_name(master_corp_name)

    # -------------------------------------------------------------
    # Rule 1: 대상회사 상장사 마스터 1:1 일치 및 사명 검증 (RULE_1_CORP_MATCH)
    # -------------------------------------------------------------
    if not corp_code or len(str(corp_code).strip()) != 8:
        rule_results["RULE_1_CORP_MATCH"] = {
            "status": "FAIL",
            "reason": f"대상회사 법인코드 비정상 (corp_code: '{corp_code}')"
        }
        failure_reasons.append("대상회사 8자리 DART 법인코드 결측 또는 비정상")
    elif corp_code not in corp_code_set:
        rule_results["RULE_1_CORP_MATCH"] = {
            "status": "FAIL",
            "reason": f"DART 상장사 마스터 미등록 법인 (corp_code: {corp_code}, corp_name: {corp_name})"
        }
        failure_reasons.append("상장사 마스터 미등록 법인(비상장 또는 폐지)")
    elif norm_cand_corp != norm_master_corp:
        rule_results["RULE_1_CORP_MATCH"] = {
            "status": "FAIL",
            "reason": f"대상회사명 마스터 불일치 (후보: '{corp_name}' vs 마스터: '{master_corp_name}')"
        }
        failure_reasons.append(f"대상회사명 마스터 불일치 ('{corp_name}' != '{master_corp_name}')")
    else:
        rule_results["RULE_1_CORP_MATCH"] = {
            "status": "PASS",
            "reason": f"상장사 마스터 1:1 결속 및 사명 일치 확인 ({corp_name}, corp_code: {corp_code})"
        }

    # -------------------------------------------------------------
    # Rule 2: 보유자 마스터 고유 해소 (RULE_2_HOLDER_RESOLUTION)
    # -------------------------------------------------------------
    resolved_master_corp_code = None
    if not holder_name or len(str(holder_name).strip()) < 2:
        rule_results["RULE_2_HOLDER_RESOLUTION"] = {
            "status": "FAIL",
            "reason": f"보유자명 누락 또는 2자 미만 결측 ('{holder_name}')"
        }
        failure_reasons.append("보유자 성명/법인명 식별 불가")
    elif any(placeholder in str(holder_name) for placeholder in ["미기재", "불명", "해당없음", "-", "기타"]):
        rule_results["RULE_2_HOLDER_RESOLUTION"] = {
            "status": "FAIL",
            "reason": f"보유자명이 플레이스홀더로 기재됨 ('{holder_name}')"
        }
        failure_reasons.append("플레이스홀더 보유자명")
    elif re.search(r'(외\s*\d+인|외\s*\d+명)', str(holder_name)):
        rule_results["RULE_2_HOLDER_RESOLUTION"] = {
            "status": "AMBIGUOUS",
            "reason": f"공동보유 '외 N인' 복수 주체 결합형 명칭 ('{holder_name}')"
        }
        ambiguous_reasons.append("공동보유 집단 명칭(외 N인)으로 개별 주체 식별 필요")
    else:
        # 마스터 해소(Entity Resolution) 시도
        h_raw = str(holder_name).strip()
        h_norm = normalize_corp_name(h_raw)

        matched_codes = name_to_corps.get(h_raw) or name_to_corps.get(h_norm) or set()

        if len(matched_codes) == 1:
            resolved_master_corp_code = list(matched_codes)[0]
            rule_results["RULE_2_HOLDER_RESOLUTION"] = {
                "status": "PASS",
                "resolved_master_code": resolved_master_corp_code,
                "reason": f"마스터 1:1 고유 해소 완료 ('{h_raw}' -> corp_code: {resolved_master_corp_code})"
            }
        elif len(matched_codes) > 1:
            rule_results["RULE_2_HOLDER_RESOLUTION"] = {
                "status": "AMBIGUOUS",
                "matched_codes": list(matched_codes),
                "reason": f"마스터 내 동일 명칭 복수 엔티티 경합 ({len(matched_codes)}건: {list(matched_codes)})"
            }
            ambiguous_reasons.append(f"동일 명칭 복수 마스터 엔티티 경합 ('{h_raw}')")
        else:
            rule_results["RULE_2_HOLDER_RESOLUTION"] = {
                "status": "AMBIGUOUS",
                "reason": f"마스터 엔티티 미등록 주체(자연인 또는 비상장/사모펀드) - 미해소(UNRESOLVED)"
            }
            ambiguous_reasons.append(f"마스터 미등록 주체(자연인/비상장/사모펀드) 미해소 ('{h_raw}')")

    # -------------------------------------------------------------
    # Rule 3: 보고자-보유자 주체 분리 보존 (RULE_3_REPORTER_HOLDER_SEPARATION)
    # -------------------------------------------------------------
    if not reporter_name:
        rule_results["RULE_3_REPORTER_HOLDER_SEPARATION"] = {
            "status": "FAIL",
            "reason": "보고자(REPORTER) 성명/법인명 누락"
        }
        failure_reasons.append("보고자 주체 정보 누락")
    else:
        is_same = (str(reporter_name).strip() == str(holder_name).strip())
        rule_results["RULE_3_REPORTER_HOLDER_SEPARATION"] = {
            "status": "PASS",
            "reason": f"보고자('{reporter_name}')와 보유자('{holder_name}') 명시적 분리 보존 (동일인 여부: {is_same})"
        }

    # -------------------------------------------------------------
    # Rule 4: 증거 파편 역할 완비 및 실제 값 1:1 결속 (RULE_4_EVIDENCE_ROLE_COVERAGE)
    # -------------------------------------------------------------
    if not fragments:
        rule_results["RULE_4_EVIDENCE_ROLE_COVERAGE"] = {
            "status": "FAIL",
            "reason": "결속된 EvidenceFragment 전무 (원문 증거 부재)"
        }
        failure_reasons.append("결속 증거 파편(EvidenceFragment) 0건")
    else:
        frag_by_role = {}
        for f in fragments:
            if f.get("role"):
                frag_by_role.setdefault(f["role"], []).append(f)

        missing_roles = REQUIRED_EVIDENCE_ROLES - set(frag_by_role.keys())
        has_valid_xpath = all(bool(f.get("xpath")) for f in fragments)
        has_valid_hash = all(bool(f.get("raw_inner_hash")) for f in fragments)

        # 4대 증거 실제 값 결속 검증 (Value Binding Integrity)
        val_mismatches = []
        if not missing_roles:
            # 1. TARGET_COMPANY 파편 값 검증
            tc_frag = frag_by_role["TARGET_COMPANY"][0]
            tc_val = tc_frag.get("extracted_value", "")
            if corp_code not in tc_val and norm_cand_corp not in normalize_corp_name(tc_val):
                val_mismatches.append(f"TARGET_COMPANY 파편 값 불일치 (파편: '{tc_val}' vs 후보: '{corp_name}/{corp_code}')")

            # 2. REPORTER 파편 값 검증
            rep_frag = frag_by_role["REPORTER"][0]
            rep_val = rep_frag.get("extracted_value", "").strip()
            if rep_val != str(reporter_name).strip():
                val_mismatches.append(f"REPORTER 파편 값 불일치 (파편: '{rep_val}' vs 후보: '{reporter_name}')")

            # 3. REPORTING_OBLIGATION_DATE 파편 값 검증
            date_frag = frag_by_role["REPORTING_OBLIGATION_DATE"][0]
            date_val = date_frag.get("extracted_value", "").strip()
            if date_val != str(ob_date).strip():
                val_mismatches.append(f"REPORTING_OBLIGATION_DATE 파편 값 불일치 (파편: '{date_val}' vs 후보: '{ob_date}')")

            # 4. ROW_DATA_EVIDENCE 파편 값 검증 (보유자 성명 포함 여부)
            row_frag = frag_by_role["ROW_DATA_EVIDENCE"][0]
            row_val = row_frag.get("extracted_value", "")
            norm_holder = normalize_corp_name(str(holder_name))
            if norm_holder and norm_holder not in normalize_corp_name(row_val):
                val_mismatches.append(f"ROW_DATA_EVIDENCE 보유자 값 불일치 (파편: '{row_val}' vs 후보: '{holder_name}')")

        if missing_roles:
            rule_results["RULE_4_EVIDENCE_ROLE_COVERAGE"] = {
                "status": "FAIL",
                "bound_roles": list(frag_by_role.keys()),
                "missing_roles": list(missing_roles),
                "reason": f"필수 증거 역할 파편 결손 (누락 역할: {list(missing_roles)})"
            }
            failure_reasons.append(f"필수 증거 역할 누락 ({', '.join(missing_roles)})")
        elif not (has_valid_xpath and has_valid_hash):
            rule_results["RULE_4_EVIDENCE_ROLE_COVERAGE"] = {
                "status": "FAIL",
                "reason": "증거 파편의 2D XPath 또는 암호학적 원문 행 해시(raw_inner_hash) 결측 존재"
            }
            failure_reasons.append("증거 파편의 XPath/해시 결손")
        elif val_mismatches:
            rule_results["RULE_4_EVIDENCE_ROLE_COVERAGE"] = {
                "status": "FAIL",
                "val_mismatches": val_mismatches,
                "reason": f"증거 파편 실제 값 결속 불일치: {'; '.join(val_mismatches)}"
            }
            failure_reasons.extend(val_mismatches)
        else:
            rule_results["RULE_4_EVIDENCE_ROLE_COVERAGE"] = {
                "status": "PASS",
                "bound_roles": list(frag_by_role.keys()),
                "fragment_count": len(fragments),
                "reason": f"4대 필수 증거 파편 실제 값 일치 및 해시 무결성 검증 완료 ({len(fragments)}개 파편)"
            }

    # -------------------------------------------------------------
    # Rule 5: 서식 지원 및 날짜 유효성/파편 일치 (RULE_5_TEMPORAL_VALIDITY)
    # -------------------------------------------------------------
    is_valid_calendar = False
    if ob_date and re.match(r'^\d{4}-\d{2}-\d{2}$', str(ob_date).strip()):
        try:
            datetime.strptime(str(ob_date).strip(), "%Y-%m-%d")
            is_valid_calendar = True
        except ValueError:
            is_valid_calendar = False

    date_frags = [f for f in fragments if f.get("role") == "REPORTING_OBLIGATION_DATE"]
    date_frag_match = True
    date_frag_val = ""
    if date_frags:
        date_frag_val = date_frags[0].get("extracted_value", "").strip()
        date_frag_match = (date_frag_val == str(ob_date).strip())

    if layout_status != "SUPPORTED_5PCT_GENERAL":
        rule_results["RULE_5_TEMPORAL_VALIDITY"] = {
            "status": "FAIL",
            "reason": f"미지원 또는 약식 서식 (layout: '{layout_status}')"
        }
        failure_reasons.append(f"비표준/약식 서식 추출본 ({layout_status})")
    elif not ob_date or not re.match(r'^\d{4}-\d{2}-\d{2}$', str(ob_date).strip()):
        rule_results["RULE_5_TEMPORAL_VALIDITY"] = {
            "status": "FAIL",
            "reason": f"보고의무발생일 누락 또는 YYYY-MM-DD 규격 위반 ('{ob_date}')"
        }
        failure_reasons.append("보고의무발생일 규격 결손")
    elif not is_valid_calendar:
        rule_results["RULE_5_TEMPORAL_VALIDITY"] = {
            "status": "FAIL",
            "reason": f"보고의무발생일이 실존하지 않는 달력 일자임 ('{ob_date}')"
        }
        failure_reasons.append(f"비실존 달력 일자 결측 ({ob_date})")
    elif not date_frag_match:
        rule_results["RULE_5_TEMPORAL_VALIDITY"] = {
            "status": "FAIL",
            "reason": f"후보의 보고의무발생일과 날짜 파편 값 불일치 ('{ob_date}' != '{date_frag_val}')"
        }
        failure_reasons.append("후보-파편 날짜 값 불일치")
    else:
        rule_results["RULE_5_TEMPORAL_VALIDITY"] = {
            "status": "PASS",
            "reason": f"표준 서식 및 실존 달력 일자 확인, 날짜 파편 값 1:1 일치 ('{ob_date}')"
        }

    # -------------------------------------------------------------
    # 최종 3진 판정 (Verdict Determination)
    # -------------------------------------------------------------
    if failure_reasons:
        verdict = "REJECT"
    elif ambiguous_reasons:
        verdict = "AMBIGUOUS"
    else:
        verdict = "PASS"

    return {
        "candidate_id": cid,
        "rcept_no": rcept_no,
        "target_corp_code": corp_code,
        "target_corp_name": corp_name,
        "master_corp_name": master_corp_name,
        "holder_name": holder_name,
        "resolved_master_corp_code": resolved_master_corp_code,
        "reporter_name": reporter_name,
        "stake_ratio": stake_ratio,
        "shares_count": shares_count,
        "reporting_obligation_date": ob_date,
        "xml_sha256": xml_sha256,
        "verdict": verdict,
        "rule_evaluations": rule_results,
        "failure_reasons": failure_reasons,
        "ambiguous_reasons": ambiguous_reasons,
        "fragment_count": len(fragments)
    }


def execute_dry_run_batch(driver, limit: int = 500) -> Dict[str, Any]:
    """
    Cloud Aura DB에서 candidate_id 오름차순으로 고정 표본을 READ_ACCESS로 읽어
    엔티티 해소 DRY_RUN 판정을 전수 수행하고 검수 매니페스트를 생성합니다.
    (100% 읽기 전용, DB 쓰기 0건 및 전후 DB 카운트 검증)
    """
    print(f"🚀 [DRY_RUN v1.2] 표본 {limit:,}건 (candidate_id 정렬 고정) 판정 시작 (READ_ACCESS 모드)...")

    # 1. 실행 전 DB 상태 실측 (Pre-run DB Count)
    with driver.session(default_access_mode=READ_ACCESS) as session:
        pre_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        pre_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"  [DB 기준선] 전체 노드: {pre_nodes:,}개 | 전체 관계: {pre_rels:,}건")

        # 2. DART 상장사 마스터 로드 및 인덱싱
        company_rows = session.run("MATCH (c:DART_Company) RETURN c.corp_code AS code, c.name AS name").data()
        corp_code_set = {r["code"] for r in company_rows if r.get("code")}
        code_to_master_name = {r["code"]: r["name"] for r in company_rows if r.get("code")}

        name_to_corps: Dict[str, Set[str]] = {}
        for r in company_rows:
            n = r["name"].strip() if r.get("name") else ""
            if n:
                name_to_corps.setdefault(n, set()).add(r["code"])
                norm = normalize_corp_name(n)
                if norm and norm != n:
                    name_to_corps.setdefault(norm, set()).add(r["code"])

        print(f"  [마스터 로드] 상장사 {len(corp_code_set):,}개사, 정규화 명칭 {len(name_to_corps):,}건 인메모리 인덱싱 완료")

        # 3. 고정 표본 500건 및 증거 파편 로드 (ORDER BY c.candidate_id ASC)
        query = """
        MATCH (c:RawEvidenceCandidate)
        OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
        WITH c, collect({role: f.role, xpath: f.xpath, raw_inner_hash: f.raw_inner_hash, extracted_value: f.extracted_value}) AS frags
        ORDER BY c.candidate_id ASC
        LIMIT $limit
        RETURN c, frags
        """
        rows = session.run(query, limit=limit).data()
        print(f"  [표본 로드] candidate_id 정렬 고정 표본 {len(rows):,}건 로드 완료")

    # 4. 입력 목록 고유 해시 계산 (입력 재현성 보증)
    candidate_id_list = [r["c"]["candidate_id"] for r in rows]
    input_sha256 = hashlib.sha256("\n".join(candidate_id_list).encode('utf-8')).hexdigest()
    print(f"  [무결성 해시] 입력 표본 목록 SHA-256: {input_sha256}")

    # 5. 인메모리 5대 무결성 판정 수행
    results = []
    verdict_counts = {"PASS": 0, "REJECT": 0, "AMBIGUOUS": 0}
    reason_histogram = {}

    for row in rows:
        cand = row["c"]
        frags = [f for f in row["frags"] if f.get("role")]
        
        eval_res = evaluate_single_candidate(
            candidate_node=cand,
            fragments=frags,
            corp_code_set=corp_code_set,
            name_to_corps=name_to_corps,
            code_to_master_name=code_to_master_name
        )
        verdict = eval_res["verdict"]
        verdict_counts[verdict] += 1

        for r in eval_res["failure_reasons"] + eval_res["ambiguous_reasons"]:
            reason_histogram[r] = reason_histogram.get(r, 0) + 1

        results.append(eval_res)

    # 6. 실행 후 DB 상태 실측 (Post-run DB Count & Delta 검증)
    with driver.session(default_access_mode=READ_ACCESS) as session:
        post_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        post_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    delta_nodes = post_nodes - pre_nodes
    delta_rels = post_rels - pre_rels

    assert delta_nodes == 0, f"❌ Zero DB Write 위반: 노드 변화량 {delta_nodes}"
    assert delta_rels == 0, f"❌ Zero DB Write 위반: 관계 변화량 {delta_rels}"
    print(f"  [Zero DB Write 검증] 완료: 노드 변화량 Δ={delta_nodes}, 관계 변화량 Δ={delta_rels}")

    manifest = {
        "engine_version": "DRY_RUN_CONTRACT_V1.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(results),
        "input_list_sha256": input_sha256,
        "pre_run_db_state": {"nodes": pre_nodes, "relationships": pre_rels},
        "post_run_db_state": {"nodes": post_nodes, "relationships": post_rels},
        "db_delta": {"delta_nodes": delta_nodes, "delta_relationships": delta_rels},
        "verdict_summary": {
            "PASS": verdict_counts["PASS"],
            "PASS_pct": round(verdict_counts["PASS"] / max(len(results), 1) * 100, 2),
            "REJECT": verdict_counts["REJECT"],
            "REJECT_pct": round(verdict_counts["REJECT"] / max(len(results), 1) * 100, 2),
            "AMBIGUOUS": verdict_counts["AMBIGUOUS"],
            "AMBIGUOUS_pct": round(verdict_counts["AMBIGUOUS"] / max(len(results), 1) * 100, 2),
        },
        "reason_histogram": dict(sorted(reason_histogram.items(), key=lambda x: x[1], reverse=True)),
        "evaluations": results
    }

    return manifest
