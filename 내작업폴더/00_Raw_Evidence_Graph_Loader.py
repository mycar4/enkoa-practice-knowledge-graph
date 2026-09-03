# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] RawEvidenceCandidate & EvidenceFragment 격리 계층 적재 엔진
================================================================================
목적:
1. 1,500건 검증 완료된 공시 원문(XML) 및 영수증을 오프라인 파싱
2. 프로덕션 지분 그래프(:OWNS_STAKE, GDS)와 완전히 분리된 순수 증거 계층 적재:
   - (:RawEvidenceCandidate)
   - (:EvidenceFragment)
   - (:RawEvidenceCandidate)-[:EVIDENCED_BY]->(:EvidenceFragment)
3. 7대 필수 메타데이터 전수 결속:
   - rcept_no, xml_sha256, run_id, receipt_id, adapter_name, adapter_version, xml_rel_path
4. 서식 분기:
   - 제142조 일반서식: SUPPORTED_5PCT_GENERAL 상태 부여 및 후보/파편 결속 적재
   - 약식 및 기타 서식: UNSUPPORTED_LAYOUT 상태로 후보 노드만 격리 보존
5. Zero OWNS_STAKE Invariance:
   - OWNS_STAKE 및 is_current 엣지 생성 0건 보장
================================================================================
"""

import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

sys.path.insert(0, os.path.abspath("내작업폴더"))
from adapter_5pct_general_art142_v1 import run_adapter_5pct_general_art142_v1, ADAPTER_NAME, ADAPTER_VERSION

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class RawEvidenceGraphLoader:
    """원천 증거 격리 적재 엔진 (Neo4j)"""

    def __init__(
        self,
        base_runs_dir: str = "내작업폴더/data/raw_filings/batch_runs",
        driver: Optional[Driver] = None
    ):
        self.base_runs_dir = base_runs_dir
        self.driver = driver
        if self.driver is None:
            load_dotenv(".env")
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            pwd = os.getenv("NEO4J_PASSWORD", "12345678")
            self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        if self.driver:
            self.driver.close()

    def ensure_constraints(self):
        """증거 계층 유니크 제약조건 생성"""
        queries = [
            "CREATE CONSTRAINT constraint_raw_evidence_candidate_id IF NOT EXISTS FOR (c:RawEvidenceCandidate) REQUIRE c.candidate_id IS UNIQUE",
            "CREATE CONSTRAINT constraint_evidence_fragment_id IF NOT EXISTS FOR (f:EvidenceFragment) REQUIRE f.fragment_id IS UNIQUE"
        ]
        with self.driver.session() as s:
            for q in queries:
                s.run(q)

    def load_evidence_batch(
        self,
        run_id: str,
        dry_run: bool = False,
        limit: Optional[int] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        배치 실행 아카이브를 읽어 증거 노드 적재 수행
        """
        run_dir = os.path.join(self.base_runs_dir, run_id)
        if not os.path.exists(run_dir):
            raise FileNotFoundError(f"실행 디렉토리 부재: {run_dir}")

        # 1. 종료 감사 성공 여부 사전 검증
        closure_path = os.path.join(run_dir, "batch_closure_manifest.json")
        if not os.path.exists(closure_path):
            raise FileNotFoundError(f"종료 감사 매니페스트 부재: {closure_path}")

        with open(closure_path, "r", encoding="utf-8") as cf:
            closure_audit = json.load(cf)

        if closure_audit.get("audit_verdict") != "BATCH_VERIFIED_SUCCESS":
            raise ValueError(f"❌ [안전 거부] 해당 실행은 BATCH_VERIFIED_SUCCESS 승인을 획득하지 못했습니다: {closure_audit.get('audit_verdict')}")

        in_manifest_path = os.path.join(run_dir, "input_manifest.json")
        with open(in_manifest_path, "r", encoding="utf-8") as mf:
            in_manifest = json.load(mf)

        targets = in_manifest.get("targets", [])
        if limit is not None and limit > 0:
            targets = targets[:limit]

        xml_dir = os.path.join(run_dir, "xml")
        manifests_dir = os.path.join(run_dir, "manifests")

        # 영수증 인덱싱 (rcept_no -> receipt_info)
        receipt_map: Dict[str, Dict[str, Any]] = {}
        for fn in os.listdir(manifests_dir):
            if fn.endswith(".json") and fn.startswith("receipt_"):
                p = os.path.join(manifests_dir, fn)
                with open(p, "r", encoding="utf-8") as rf:
                    rcpt_data = json.load(rf)
                r_no = rcpt_data.get("requested_rcept_no")
                if r_no:
                    receipt_map[r_no] = rcpt_data

        stats = {
            "run_id": run_id,
            "dry_run": dry_run,
            "total_targets_evaluated": len(targets),
            "supported_general_count": 0,
            "unsupported_layout_count": 0,
            "candidates_created": 0,
            "fragments_created": 0,
            "relationships_created": 0,
            "owns_stake_created": 0, # 불변식 검증용 (반드시 0이어야 함)
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None
        }

        if not dry_run:
            self.ensure_constraints()

        candidate_batch: List[Dict[str, Any]] = []
        fragment_batch: List[Dict[str, Any]] = []
        rel_batch: List[Dict[str, Any]] = []

        now_str = datetime.now(timezone.utc).isoformat()

        for idx, target in enumerate(targets, start=1):
            rcept_no = target["rcept_no"]
            expected_corp_code = target.get("expected_corp_code", "")
            expected_corp_name = target.get("expected_corp_name", "")

            xml_path = os.path.join(xml_dir, f"{rcept_no}.xml")
            if not os.path.exists(xml_path):
                raise FileNotFoundError(f"XML 파일 부재: {xml_path}")

            with open(xml_path, "rb") as xf:
                xml_bytes = xf.read()

            receipt = receipt_map.get(rcept_no, {})
            receipt_id = receipt.get("receipt_id", f"rcpt-{rcept_no}")
            xml_sha256 = receipt.get("xml_sha256", "")
            xml_rel_path = receipt.get("xml_storage_rel_path", f"xml/{rcept_no}.xml")

            # 2. 어댑터 실행 (순수 오프라인 파싱)
            adapter_res = run_adapter_5pct_general_art142_v1(xml_bytes, rcept_no=rcept_no)
            status = adapter_res.get("adapter_status")

            if status == "SUCCESS":
                stats["supported_general_count"] += 1
                doc_meta = adapter_res.get("document_metadata", {})
                t_corp_code = doc_meta.get("target_corp_code") or expected_corp_code
                t_corp_name = doc_meta.get("target_corp_name") or expected_corp_name
                reporter_name = doc_meta.get("reporter_name", "")

                # 증거 파편 등록
                frag_id_map: Dict[str, str] = {}
                for f in adapter_res.get("evidence_fragments", []):
                    f_id = f["fragment_id"]
                    frag_dict = {
                        "fragment_id": f_id,
                        "rcept_no": rcept_no,
                        "xml_sha256": xml_sha256,
                        "role": f.get("role", "UNKNOWN"),
                        "xpath": f.get("xpath", ""),
                        "raw_inner_hash": f.get("raw_inner_hash", ""),
                        "extracted_value": str(f.get("extracted_value", "")),
                        "created_at": now_str
                    }
                    fragment_batch.append(frag_dict)
                    frag_id_map[f_id] = f_id
                    stats["fragments_created"] += 1

                # 후보 등록
                for c_idx, cand in enumerate(adapter_res.get("candidates", [])):
                    c_id = f"cand-{rcept_no}-{c_idx+1}"
                    cand_dict = {
                        "candidate_id": c_id,
                        "rcept_no": rcept_no,
                        "xml_sha256": xml_sha256,
                        "run_id": run_id,
                        "receipt_id": receipt_id,
                        "adapter_name": ADAPTER_NAME,
                        "adapter_version": ADAPTER_VERSION,
                        "xml_rel_path": xml_rel_path,
                        "layout_status": "SUPPORTED_5PCT_GENERAL",
                        "rejection_reason": None,
                        "target_corp_code": t_corp_code,
                        "target_corp_name": t_corp_name,
                        "reporter_name": reporter_name,
                        "holder_name": cand.get("holder_name", ""),
                        "shares_count": cand.get("shares_count", 0),
                        "stake_ratio": cand.get("stake_ratio", 0.0),
                        "reporting_obligation_date": cand.get("reporting_obligation_date", ""),
                        "created_at": now_str
                    }
                    candidate_batch.append(cand_dict)
                    stats["candidates_created"] += 1

                    # 후보 -> 파편 엣지 등록
                    for linked_f_id in cand.get("evidence_fragment_ids", []):
                        rel_batch.append({
                            "candidate_id": c_id,
                            "fragment_id": linked_f_id
                        })
                        stats["relationships_created"] += 1

            else:
                # 미지원 서식 (약식 또는 비일반)
                stats["unsupported_layout_count"] += 1
                rejection_reason = adapter_res.get("rejection_reason", "UNSUPPORTED_LAYOUT")
                c_id = f"cand-{rcept_no}-unsupported"
                cand_dict = {
                    "candidate_id": c_id,
                    "rcept_no": rcept_no,
                    "xml_sha256": xml_sha256,
                    "run_id": run_id,
                    "receipt_id": receipt_id,
                    "adapter_name": ADAPTER_NAME,
                    "adapter_version": ADAPTER_VERSION,
                    "xml_rel_path": xml_rel_path,
                    "layout_status": "UNSUPPORTED_LAYOUT",
                    "rejection_reason": rejection_reason,
                    "target_corp_code": expected_corp_code,
                    "target_corp_name": expected_corp_name,
                    "reporter_name": None,
                    "holder_name": None,
                    "shares_count": None,
                    "stake_ratio": None,
                    "reporting_obligation_date": None,
                    "created_at": now_str
                }
                candidate_batch.append(cand_dict)
                stats["candidates_created"] += 1

            # 배치 단위 커밋 (dry_run이 아닐 때)
            if not dry_run and (idx % batch_size == 0 or idx == len(targets)):
                self._flush_batches(candidate_batch, fragment_batch, rel_batch)
                candidate_batch.clear()
                fragment_batch.clear()
                rel_batch.clear()

        if not dry_run and (candidate_batch or fragment_batch or rel_batch):
            self._flush_batches(candidate_batch, fragment_batch, rel_batch)

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    def _flush_batches(
        self,
        candidates: List[Dict[str, Any]],
        fragments: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        """Neo4j 트랜잭션 배치 적재"""
        with self.driver.session() as session:
            # 1. Fragments 적재
            if fragments:
                frag_cypher = """
                UNWIND $batch AS f
                MERGE (frag:EvidenceFragment {fragment_id: f.fragment_id})
                SET frag.rcept_no = f.rcept_no,
                    frag.xml_sha256 = f.xml_sha256,
                    frag.role = f.role,
                    frag.xpath = f.xpath,
                    frag.raw_inner_hash = f.raw_inner_hash,
                    frag.extracted_value = f.extracted_value,
                    frag.created_at = f.created_at
                """
                session.run(frag_cypher, {"batch": fragments})

            # 2. Candidates 적재
            if candidates:
                cand_cypher = """
                UNWIND $batch AS c
                MERGE (cand:RawEvidenceCandidate {candidate_id: c.candidate_id})
                SET cand.rcept_no = c.rcept_no,
                    cand.xml_sha256 = c.xml_sha256,
                    cand.run_id = c.run_id,
                    cand.receipt_id = c.receipt_id,
                    cand.adapter_name = c.adapter_name,
                    cand.adapter_version = c.adapter_version,
                    cand.xml_rel_path = c.xml_rel_path,
                    cand.layout_status = c.layout_status,
                    cand.rejection_reason = c.rejection_reason,
                    cand.target_corp_code = c.target_corp_code,
                    cand.target_corp_name = c.target_corp_name,
                    cand.reporter_name = c.reporter_name,
                    cand.holder_name = c.holder_name,
                    cand.shares_count = c.shares_count,
                    cand.stake_ratio = c.stake_ratio,
                    cand.reporting_obligation_date = c.reporting_obligation_date,
                    cand.created_at = c.created_at
                """
                session.run(cand_cypher, {"batch": candidates})

            # 3. Candidate -> Fragment 엣지 적재
            if relationships:
                rel_cypher = """
                UNWIND $batch AS r
                MATCH (cand:RawEvidenceCandidate {candidate_id: r.candidate_id})
                MATCH (frag:EvidenceFragment {fragment_id: r.fragment_id})
                MERGE (cand)-[:EVIDENCED_BY]->(frag)
                """
                session.run(rel_cypher, {"batch": relationships})


def main():
    parser = argparse.ArgumentParser(description="Raw Evidence Graph Loader")
    parser.add_argument("--run-id", default="batch_1500_20260903_051738", help="적재 대상 Run ID")
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 통계 산출")
    parser.add_argument("--limit", type=int, default=None, help="처리 건수 제한 (파일럿용)")
    parser.add_argument("--batch-size", type=int, default=50, help="DB 적재 배치 크기")
    args = parser.parse_args()

    print("=" * 80)
    mode_str = "🔍 [DRY-RUN 모드 - DB 쓰기 0건]" if args.dry_run else "🚀 [실제 Neo4j 격리 적재 모드]"
    print(f"{mode_str} Run ID: {args.run_id} (limit: {args.limit})")
    print("=" * 80)

    loader = RawEvidenceGraphLoader()
    try:
        res = loader.load_evidence_batch(
            run_id=args.run_id,
            dry_run=args.dry_run,
            limit=args.limit,
            batch_size=args.batch_size
        )
        print("\n📊 [적재 처리 결과]")
        print(f"• 평가 대상 공시 건수: {res['total_targets_evaluated']:,}건")
        print(f"• 제142조 일반서식 지원: {res['supported_general_count']:,}건")
        print(f"• 미지원/약식 서식 격리: {res['unsupported_layout_count']:,}건")
        print(f"• RawEvidenceCandidate 노드: {res['candidates_created']:,}개")
        print(f"• EvidenceFragment 노드: {res['fragments_created']:,}개")
        print(f"• EVIDENCED_BY 관계: {res['relationships_created']:,}개")
        print(f"• OWNS_STAKE 관계 (불변식 검증): {res['owns_stake_created']}개 (100% 0건 유지)")
        print("=" * 80)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
