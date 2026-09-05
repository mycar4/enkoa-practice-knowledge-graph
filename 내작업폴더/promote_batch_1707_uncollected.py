# -*- coding: utf-8 -*-
"""
[DART-Trace] 오늘 신규 로딩분(batch_1707_uncollected) 전용 범용 해소·승격 실행기
================================================================================
- dry_run_resolution_engine.py의 Rule 1~5 판정 로직(범용, 재사용)을 그대로 사용하되,
  candidate_id ASC LIMIT 500 대신 load_run_id로 오늘 신규 3,212건만 필터링한다.
- PASS 판정 건만 dry_run_economic_stake_promotion.py와 동일한 3/3 행 증거 재대조를 거쳐
  execute_economic_stake_promotion.py의 execute_promotion_batch_tx(완전 범용, 하드코딩 없음)로
  단일 원자적 트랜잭션 승격한다.
- 기본은 DRY-RUN(승격 후보 산출 + 매니페스트 저장까지만). --commit 시에만 실제 Aura 기록.
================================================================================
"""

import os
import sys
import re
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List
from neo4j import GraphDatabase, READ_ACCESS, WRITE_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dry_run_resolution_engine import evaluate_single_candidate, normalize_corp_name  # noqa: E402
from execute_economic_stake_promotion import execute_promotion_batch_tx  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent           # 내작업폴더
REPO_ROOT = BASE_DIR.parent
ENV_PATH = REPO_ROOT / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

TARGET_LOAD_RUN_ID = "load_batch_1707_uncollected_20260905_021604_20260905_023122"


def validate_row_evidence_values(cand_holder: str, cand_shares: Any, cand_stake: Any, extracted_val: str) -> Dict[str, Any]:
    """dry_run_economic_stake_promotion.py와 동일한 3/3 행 증거 재대조 로직"""
    norm_cand_holder = normalize_corp_name(cand_holder)
    pattern = re.compile(r"holder=(?P<holder>.*?),\s*shares=(?P<shares>\d+),\s*stake=(?P<stake>[\d.]+)%?")
    m = pattern.search(extracted_val or "")
    if not m:
        return {"passed": False, "holder_match": False, "shares_match": False, "stake_match": False,
                "error": "ROW_DATA_EVIDENCE 정규식 파싱 실패"}

    ex_holder = m.group("holder").strip()
    norm_ex_holder = normalize_corp_name(ex_holder)
    ex_shares = int(m.group("shares"))
    ex_stake = float(m.group("stake"))

    try:
        cand_shares_int = int(cand_shares) if cand_shares is not None else -1
        cand_stake_float = float(cand_stake) if cand_stake is not None else -1.0
    except (ValueError, TypeError):
        cand_shares_int = -1
        cand_stake_float = -1.0

    holder_match = (norm_cand_holder == norm_ex_holder)
    shares_match = (ex_shares == cand_shares_int)
    stake_match = abs(ex_stake - cand_stake_float) < 1e-4

    return {
        "passed": holder_match and shares_match and stake_match,
        "holder_match": holder_match, "shares_match": shares_match, "stake_match": stake_match,
        "parsed_evidence": {"extracted_holder": ex_holder, "extracted_shares": ex_shares, "extracted_stake": ex_stake}
    }


def resolve_exact_xml_coordinates(xml_rel_path: str, target_hash: str, raw_parser_xpath: str) -> Dict[str, Any]:
    """xml_rel_path(후보 노드에 실제 기록된 경로)를 그대로 사용 - 하드코딩 디렉토리 없음"""
    # xml_rel_path 저장 관례가 두 가지 혼재(저장소 루트 기준 vs 내작업폴더 기준) - 둘 다 시도
    candidate_paths = [BASE_DIR / xml_rel_path, REPO_ROOT / xml_rel_path]
    xml_file = next((p for p in candidate_paths if p.exists()), candidate_paths[0])
    if xml_file.exists():
        content = xml_file.read_text(encoding="utf-8", errors="ignore")
        table_pattern = re.compile(r"<TABLE[^>]*>(.*?)</TABLE>", re.DOTALL | re.IGNORECASE)
        tables = table_pattern.findall(content)
        for t_idx, tbl in enumerate(tables):
            tr_pattern = re.compile(r"<TR[^>]*>(.*?)</TR>", re.DOTALL | re.IGNORECASE)
            all_trs = tr_pattern.findall(tbl)
            for r_idx, tr in enumerate(all_trs):
                clean_tr = re.sub(r"\s+", " ", tr).strip()
                h = hashlib.sha256(clean_tr.encode("utf-8")).hexdigest()
                if h == target_hash:
                    return {
                        "table_parser_index": t_idx, "all_tr_index": r_idx, "data_row_index": r_idx,
                        "standard_xpath": f"//TABLE[{t_idx + 1}]//TR[{r_idx + 1}]",
                        "raw_parser_xpath": raw_parser_xpath, "xml_hash_verified": True
                    }
    m = re.search(r"//TABLE\[(\d+)\]//TR\[(\d+)\]", raw_parser_xpath or "")
    if m:
        t_idx, r_idx = int(m.group(1)), int(m.group(2))
        return {"table_parser_index": t_idx, "all_tr_index": r_idx, "data_row_index": r_idx,
                "standard_xpath": raw_parser_xpath, "raw_parser_xpath": raw_parser_xpath, "xml_hash_verified": False}
    return {"table_parser_index": None, "all_tr_index": None, "data_row_index": None,
            "standard_xpath": raw_parser_xpath, "raw_parser_xpath": raw_parser_xpath, "xml_hash_verified": False}


def run_resolution(session) -> Dict[str, Any]:
    company_rows = session.run("MATCH (c:DART_Company) RETURN c.corp_code AS code, c.name AS name").data()
    corp_code_set = {r["code"] for r in company_rows if r.get("code")}
    code_to_master_name = {r["code"]: r["name"] for r in company_rows if r.get("code")}
    name_to_corps: Dict[str, set] = {}
    for r in company_rows:
        n = (r["name"] or "").strip()
        if n:
            name_to_corps.setdefault(n, set()).add(r["code"])
            norm = normalize_corp_name(n)
            if norm and norm != n:
                name_to_corps.setdefault(norm, set()).add(r["code"])

    query = """
    MATCH (c:RawEvidenceCandidate {load_run_id: $lrid})
    OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
    WITH c, collect({role: f.role, xpath: f.xpath, raw_inner_hash: f.raw_inner_hash, extracted_value: f.extracted_value}) AS frags
    RETURN c, frags
    """
    rows = session.run(query, lrid=TARGET_LOAD_RUN_ID).data()
    print(f"  [대상 로드] load_run_id={TARGET_LOAD_RUN_ID} -> {len(rows):,}건")

    results = []
    verdict_counts = {"PASS": 0, "REJECT": 0, "AMBIGUOUS": 0}
    for row in rows:
        cand = row["c"]
        frags = [f for f in row["frags"] if f.get("role")]
        eval_res = evaluate_single_candidate(cand, frags, corp_code_set, name_to_corps, code_to_master_name)
        eval_res["_xml_rel_path"] = cand.get("xml_rel_path")
        verdict_counts[eval_res["verdict"]] += 1
        results.append(eval_res)

    print(f"  [해소 판정] PASS={verdict_counts['PASS']} AMBIGUOUS={verdict_counts['AMBIGUOUS']} REJECT={verdict_counts['REJECT']}")
    return {"results": results, "verdict_counts": verdict_counts}


def build_promotion_proposals(session, pass_evals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pass_cids = [e["candidate_id"] for e in pass_evals]
    frag_query = """
    MATCH (c:RawEvidenceCandidate) WHERE c.candidate_id IN $cids
    OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
    RETURN c.candidate_id AS cid, f.role AS role, f.xpath AS xpath, f.raw_inner_hash AS hash, f.extracted_value AS val
    """
    frag_records = session.run(frag_query, cids=pass_cids).data()
    frags_by_cid: Dict[str, List[Dict[str, Any]]] = {}
    for fr in frag_records:
        frags_by_cid.setdefault(fr["cid"], []).append(fr)

    proposed = []
    rejected_from_pass = []
    for idx, cand in enumerate(pass_evals, 1):
        cid = cand["candidate_id"]
        frags = frags_by_cid.get(cid, [])
        row_frags = [f for f in frags if f["role"] == "ROW_DATA_EVIDENCE"]
        tc_frags = [f for f in frags if f["role"] == "TARGET_COMPANY"]
        rep_frags = [f for f in frags if f["role"] == "REPORTER"]
        date_frags = [f for f in frags if f["role"] == "REPORTING_OBLIGATION_DATE"]

        if not row_frags:
            rejected_from_pass.append({"candidate_id": cid, "reason": "ROW_DATA_EVIDENCE 파편 부재"})
            continue

        row_f = row_frags[0]
        val_check = validate_row_evidence_values(cand["holder_name"], cand["shares_count"], cand["stake_ratio"], row_f.get("val", ""))
        if not val_check["passed"]:
            rejected_from_pass.append({"candidate_id": cid, "reason": f"행 증거 3대 수치 불일치: {val_check}"})
            continue

        h_code = cand["resolved_master_corp_code"]
        t_code = cand["target_corp_code"]
        rcept_no = cand["rcept_no"]
        if not h_code:
            rejected_from_pass.append({"candidate_id": cid, "reason": "보유자 마스터 미해소(h_code 없음)"})
            continue

        xpath_info = resolve_exact_xml_coordinates(cand["_xml_rel_path"], row_f["hash"], row_f["xpath"])
        row_hash_short = row_f["hash"][:16]
        rel_key = f"rel-holds-{h_code}-{t_code}-{rcept_no}-{row_hash_short}"

        proposed.append({
            "sequence": idx,
            "candidate_id": cid,
            "holder_code": h_code,
            "target_code": t_code,
            "relationship_key": rel_key,
            "rcept_no": rcept_no,
            "xml_sha256": cand["xml_sha256"],
            "shares_count": cand["shares_count"],
            "stake_ratio": cand["stake_ratio"],
            "reporting_obligation_date": cand["reporting_obligation_date"],
            "temporal_context": "HISTORICAL_DISCLOSURE_FACT",
            "fact_type": "HISTORICAL_REPORTED_ECONOMIC_STAKE",
            "temporal_definition": f"{cand['reporting_obligation_date']} 공시 보고의무발생일 기준 원문 결속 사실 (현재 지분 아님)",
            "table_parser_index": xpath_info["table_parser_index"],
            "all_tr_index": xpath_info["all_tr_index"],
            "data_row_index": xpath_info["data_row_index"],
            "standard_xpath": xpath_info["standard_xpath"],
            "row_raw_parser_xpath": xpath_info["raw_parser_xpath"],
            "xml_hash_verified": xpath_info["xml_hash_verified"],
            "row_inner_hash": row_f["hash"],
            "source_raw_name": cand["holder_name"],
            "source_master_name": cand.get("master_corp_name") or cand["holder_name"],
            "target_raw_name": cand["target_corp_name"],
            "target_master_name": cand.get("master_corp_name"),
            "name_resolution_rule": "CORP_CODE_AND_LEGAL_AFFIX_NORMALIZED_MATCH_V1",
        })
    return proposed, rejected_from_pass


def main():
    commit = "--commit" in sys.argv
    print("=" * 90)
    print(f"[batch_1707_uncollected 해소 및 승격] {'COMMIT 모드' if commit else 'DRY-RUN 모드'}")
    print("=" * 90)

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(default_access_mode=READ_ACCESS) as session:
            pre_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            pre_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            print(f"  [DB 기준선] OWNS_STAKE={pre_owns} HOLDS_ECONOMIC_STAKE={pre_holds}")

            resolution = run_resolution(session)
            pass_evals = [e for e in resolution["results"] if e["verdict"] == "PASS"]

            proposed, rejected_from_pass = build_promotion_proposals(session, pass_evals)
            print(f"  [행 증거 재대조] PASS 판정 {len(pass_evals)}건 중 최종 승격 후보 {len(proposed)}건 (재검증 탈락 {len(rejected_from_pass)}건)")

        # 매니페스트 저장
        manifest_dir = BASE_DIR / "data" / "resolution_manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        manifest_path = manifest_dir / f"promotion_dryrun_1707batch_{ts}.json"
        manifest_payload = {
            "engine_version": "PROMOTION_CONTRACT_1707BATCH_V1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_load_run_id": TARGET_LOAD_RUN_ID,
            "verdict_summary": resolution["verdict_counts"],
            "total_proposed_relationships": len(proposed),
            "rejected_from_pass_after_row_check": rejected_from_pass,
            "proposed_holds_economic_stake": proposed,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, ensure_ascii=False, indent=2)
        print(f"  [매니페스트 저장] {manifest_path.name}")

        if not commit:
            print("\nDRY-RUN 완료 (DB 쓰기 0건). --commit 플래그로 재실행 시 실제 승격됩니다.")
            return

        if not proposed:
            print("승격할 후보가 0건입니다. 종료합니다.")
            return

        run_id = f"promrun_1707batch_{ts}_{uuid.uuid4().hex[:8]}"
        batch_params = []
        for p in proposed:
            item = dict(p)
            item["candidate_id"] = p["candidate_id"]
            item["promotion_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            item["promotion_run_id"] = run_id
            item["promoted_at"] = datetime.now(timezone.utc).isoformat()
            item["promotion_engine"] = "PROMOTION_HARNESS_1707BATCH_V1"
            batch_params.append(item)

        with driver.session(default_access_mode=WRITE_ACCESS) as session:
            tx_results = session.execute_write(execute_promotion_batch_tx, batch_params, run_id)

        created = sum(1 for r in tx_results if r["action"] == "CREATED")
        already = sum(1 for r in tx_results if r["action"] == "ALREADY_EXISTS")
        print(f"  [커밋 완료] CREATED={created} ALREADY_EXISTS={already}")

        with driver.session(default_access_mode=READ_ACCESS) as session:
            post_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            post_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
        print(f"  [DB 사후] OWNS_STAKE={post_owns} HOLDS_ECONOMIC_STAKE={post_holds} (Δ={post_holds - pre_holds})")
        assert post_owns == 0, "OWNS_STAKE 격리 위반!"
        print("=" * 90)
        print(f"[성공] 신규 승격 {created}건, HOLDS_ECONOMIC_STAKE 누적 {post_holds}건")
        print("=" * 90)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
