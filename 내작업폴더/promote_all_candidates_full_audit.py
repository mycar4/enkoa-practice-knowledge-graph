# -*- coding: utf-8 -*-
"""
[DART-Trace] 전체 RawEvidenceCandidate(27,208건) 대상 범용 해소·승격 전수 감사
================================================================================
promote_batch_1707_uncollected.py와 동일한 로직이나, load_run_id 필터 없이
DB에 존재하는 모든 RawEvidenceCandidate를 대상으로 한다(이미 승격된 건 포함 -
승격 로직은 MERGE 기반이라 기존 건은 ALREADY_EXISTS로 안전하게 처리됨).
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
from promote_batch_1707_uncollected import (  # noqa: E402
    validate_row_evidence_values,
    resolve_exact_xml_coordinates,
    build_promotion_proposals,
)

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
ENV_PATH = REPO_ROOT / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")


def run_resolution_all(session) -> Dict[str, Any]:
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

    print("  [전체 후보 로딩 중 - 시간이 걸릴 수 있습니다]")
    query = """
    MATCH (c:RawEvidenceCandidate)
    OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
    WITH c, collect({role: f.role, xpath: f.xpath, raw_inner_hash: f.raw_inner_hash, extracted_value: f.extracted_value}) AS frags
    RETURN c, frags
    """
    rows = session.run(query).data()
    print(f"  [대상 로드] 전체 -> {len(rows):,}건")

    results = []
    verdict_counts = {"PASS": 0, "REJECT": 0, "AMBIGUOUS": 0}
    for row in rows:
        cand = row["c"]
        frags = [f for f in row["frags"] if f.get("role")]
        eval_res = evaluate_single_candidate(cand, frags, corp_code_set, name_to_corps, code_to_master_name)
        eval_res["_xml_rel_path"] = cand.get("xml_rel_path")
        verdict_counts[eval_res["verdict"]] += 1
        results.append(eval_res)
        if len(results) % 5000 == 0:
            print(f"    ...{len(results):,}/{len(rows):,}건 판정 완료")

    print(f"  [해소 판정] PASS={verdict_counts['PASS']} AMBIGUOUS={verdict_counts['AMBIGUOUS']} REJECT={verdict_counts['REJECT']}")
    return {"results": results, "verdict_counts": verdict_counts}


def main():
    commit = "--commit" in sys.argv
    print("=" * 90)
    print(f"[전체 RawEvidenceCandidate 전수 감사] {'COMMIT 모드' if commit else 'DRY-RUN 모드'}")
    print("=" * 90)

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(default_access_mode=READ_ACCESS) as session:
            pre_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            pre_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            print(f"  [DB 기준선] OWNS_STAKE={pre_owns} HOLDS_ECONOMIC_STAKE={pre_holds}")

            resolution = run_resolution_all(session)
            pass_evals = [e for e in resolution["results"] if e["verdict"] == "PASS"]

            proposed, rejected_from_pass = build_promotion_proposals(session, pass_evals)
            print(f"  [행 증거 재대조] PASS 판정 {len(pass_evals)}건 중 최종 승격 후보 {len(proposed)}건 (재검증 탈락 {len(rejected_from_pass)}건)")

        manifest_dir = BASE_DIR / "data" / "resolution_manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        manifest_path = manifest_dir / f"promotion_dryrun_fullaudit_{ts}.json"
        manifest_payload = {
            "engine_version": "PROMOTION_CONTRACT_FULLAUDIT_V1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        # 대량 배치이므로 500건 단위로 분할 커밋 (단일 트랜잭션 크기 안전선)
        # 청크별로 고유 run_id를 발급해야 함 - execute_promotion_batch_tx의 트랜잭션 내부 감사는
        # "이 run_id로 태깅된 관계 수 == 이번 배치 건수"를 검증하므로, run_id를 재사용하면
        # 이전 청크의 누적치와 충돌해 예외가 발생한다(청크1 성공 후 청크2에서 실제로 발생했던 버그).
        chunk_size = 500
        total_created, total_already = 0, 0
        for i in range(0, len(proposed), chunk_size):
            chunk_run_id = f"promrun_fullaudit_{ts}_{uuid.uuid4().hex[:8]}"
            chunk = []
            for p in proposed[i:i + chunk_size]:
                item = dict(p)
                item["promotion_manifest_sha256"] = manifest_sha
                item["promotion_run_id"] = chunk_run_id
                item["promoted_at"] = datetime.now(timezone.utc).isoformat()
                item["promotion_engine"] = "PROMOTION_HARNESS_FULLAUDIT_V1"
                chunk.append(item)
            with driver.session(default_access_mode=WRITE_ACCESS) as session:
                tx_results = session.execute_write(execute_promotion_batch_tx, chunk, chunk_run_id)
            c = sum(1 for r in tx_results if r["action"] == "CREATED")
            a = sum(1 for r in tx_results if r["action"] == "ALREADY_EXISTS")
            total_created += c
            total_already += a
            print(f"  [배치 {i//chunk_size + 1}] CREATED={c} ALREADY_EXISTS={a} (누적 CREATED={total_created})")

        with driver.session(default_access_mode=READ_ACCESS) as session:
            post_owns = session.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            post_holds = session.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
        print(f"  [DB 사후] OWNS_STAKE={post_owns} HOLDS_ECONOMIC_STAKE={post_holds} (Δ={post_holds - pre_holds})")
        assert post_owns == 0, "OWNS_STAKE 격리 위반!"
        print("=" * 90)
        print(f"[성공] 신규 승격 {total_created}건 (기존 존재 {total_already}건), HOLDS_ECONOMIC_STAKE 누적 {post_holds}건")
        print("=" * 90)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
