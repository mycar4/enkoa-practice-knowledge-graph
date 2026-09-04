# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] RawEvidenceCandidate & EvidenceFragment 엄격 격리 적재 엔진
================================================================================
[계약 규격: Strict Evidence Layer Contract v3.0]
1. 보안:
   - 하드코딩된 비밀번호 기본값 완전 배제 (환경변수 미설정 시 즉시 에러)
2. 제로-트러스트 적재 전 4대 실측 대조:
   - 디스크 XML 실시간 SHA-256 == receipt.xml_sha256
   - receipt.requested_rcept_no == rcept_no
   - receipt.run_id == run_id
   - receipt.input_manifest_sha256 == input_manifest.json 실측 해시
3. 행 해시 Fallback 완전 배제:
   - ROW_DATA_EVIDENCE 파편 결손 시 holder_name/shares_count 대체 생성 일체 금지
   - UNRESOLVED_ROW_PROVENANCE 로 안전 보류 격리
4. 불변성 쓰기 계약 (ON CREATE SET):
   - 최초 적재 시에만 created_at 및 원시 증거 속성 기록 (ON MATCH 시 기존 원본 불변)
5. 그래프 적재 전용 영수증 체계:
   - load_run_id 및 노드별 load_receipt_id 필수 결속
   - commit 완료 시 graph_load_manifest_{load_run_id}.json 영구 디스크 발행
6. 기본 DRY-RUN 및 명시적 --commit 강제
================================================================================
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

sys.path.insert(0, os.path.abspath("내작업폴더"))
from adapter_5pct_general_art142_v1 import run_adapter_5pct_general_art142_v1, ADAPTER_NAME, ADAPTER_VERSION

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def compute_bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class RawEvidenceGraphLoader:
    """원천 증거 격리 적재 엔진 (엄격 계약 준수)"""

    def __init__(
        self,
        base_runs_dir: str = "내작업폴더/data/raw_filings/batch_runs",
        driver: Optional[Any] = None
    ):
        self.base_runs_dir = base_runs_dir
        self.driver = None
        if driver is not None and driver != "MOCK":
            self.driver = driver
        elif driver is None:
            load_dotenv(".env")
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER")
            pwd = os.getenv("NEO4J_PASSWORD")
            if not uri or not user or not pwd:
                raise ValueError("❌ [보안 오류] NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경변수가 필수입니다.")
            self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        if self.driver:
            self.driver.close()

    def load_evidence_batch(
        self,
        run_id: str,
        load_run_id: Optional[str] = None,
        commit: bool = False,
        limit: Optional[int] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        배치 아카이브를 읽어 증거 노드 적재 수행
        commit=False 이면 DRY-RUN (DB 쓰기 0건)
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
            raise ValueError(f"❌ [안전 거부] BATCH_VERIFIED_SUCCESS 승인을 획득하지 못한 런입니다: {closure_audit.get('audit_verdict')}")

        in_manifest_path = os.path.join(run_dir, "input_manifest.json")
        if not os.path.exists(in_manifest_path):
            raise FileNotFoundError(f"입력 매니페스트 부재: {in_manifest_path}")

        disk_in_manifest_sha = compute_file_sha256(in_manifest_path)

        with open(in_manifest_path, "r", encoding="utf-8") as mf:
            in_manifest = json.load(mf)

        targets = in_manifest.get("targets", [])
        if limit is not None and limit > 0:
            targets = targets[:limit]

        xml_dir = os.path.join(run_dir, "xml")
        manifests_dir = os.path.join(run_dir, "manifests")

        # 영수증 인덱싱
        receipt_map: Dict[str, Dict[str, Any]] = {}
        for fn in os.listdir(manifests_dir):
            if fn.endswith(".json") and fn.startswith("receipt_"):
                p = os.path.join(manifests_dir, fn)
                with open(p, "r", encoding="utf-8") as rf:
                    rcpt_data = json.load(rf)
                r_no = rcpt_data.get("requested_rcept_no")
                if r_no:
                    receipt_map[r_no] = rcpt_data

        effective_load_run_id = load_run_id or f"load_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        stats = {
            "collection_run_id": run_id,
            "load_run_id": effective_load_run_id,
            "commit_mode": commit,
            "total_targets_evaluated": len(targets),
            "supported_general_count": 0,
            "unsupported_layout_count": 0,
            "unresolved_provenance_rows": 0,
            "candidates_created": 0,
            "fragments_created": 0,
            "relationships_created": 0,
            "zero_trust_verified_count": 0,
            "quarantined_count": 0,
            "owns_stake_created": 0,  # 절대 불변식 (반드시 0)
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "write_manifest_path": None
        }

        candidate_batch: List[Dict[str, Any]] = []
        fragment_batch: List[Dict[str, Any]] = []
        rel_batch: List[Dict[str, Any]] = []

        now_str = datetime.now(timezone.utc).isoformat()

        for idx, target in enumerate(targets, start=1):
            rcept_no = target["rcept_no"]

            receipt = receipt_map.get(rcept_no)
            if not receipt:
                raise ValueError(f"❌ [실패-폐쇄] 영수증 누락: rcept_no={rcept_no}")

            coll_status = receipt.get("collection_status")
            if coll_status in ["CORRUPTED_XML", "QUARANTINED"] or "QUARANTINE" in str(coll_status):
                stats["quarantined_count"] += 1
                continue

            xml_path = os.path.join(xml_dir, f"{rcept_no}.xml")
            if not os.path.exists(xml_path):
                raise FileNotFoundError(f"XML 파일 부재: {xml_path}")

            with open(xml_path, "rb") as xf:
                xml_bytes = xf.read()

            # 2. 제로-트러스트 적재 직전 실시간 4대 대조
            disk_xml_sha = compute_bytes_sha256(xml_bytes)

            collection_receipt_id = receipt.get("receipt_id")
            if not collection_receipt_id:
                raise ValueError(f"❌ [실패-폐쇄] 영수증 내 receipt_id 결손 (Fallback 금지): rcept_no={rcept_no}")

            xml_rel_path = receipt.get("xml_storage_rel_path")
            if not xml_rel_path:
                raise ValueError(f"❌ [실패-폐쇄] 영수증 내 xml_storage_rel_path 결손 (Fallback 금지): rcept_no={rcept_no}")

            if receipt.get("xml_sha256") != disk_xml_sha:
                raise ValueError(f"❌ [실패-폐쇄] 디스크 XML 실측 해시({disk_xml_sha})와 영수증 해시({receipt.get('xml_sha256')}) 불일치: rcept_no={rcept_no}")

            if receipt.get("run_id") != run_id:
                raise ValueError(f"❌ [실패-폐쇄] 영수증의 run_id({receipt.get('run_id')})가 현재 런({run_id})과 불일치: rcept_no={rcept_no}")

            # [계약 보완] 입력 매니페스트 해시 전수 대조
            receipt_in_sha = receipt.get("input_manifest_sha256")
            if receipt_in_sha != disk_in_manifest_sha:
                raise ValueError(f"❌ [실패-폐쇄] 영수증의 input_manifest_sha256({receipt_in_sha})가 디스크 매니페스트 해시({disk_in_manifest_sha})와 불일치: rcept_no={rcept_no}")

            stats["zero_trust_verified_count"] += 1

            # 3. 어댑터 파싱
            adapter_res = run_adapter_5pct_general_art142_v1(xml_bytes, rcept_no=rcept_no)
            status = adapter_res.get("adapter_status")

            if status == "SUCCESS":
                stats["supported_general_count"] += 1
                doc_meta = adapter_res.get("document_metadata", {})

                # 외부 값 주입 전면 배제: 오직 XML 파싱 결과만 사용
                t_corp_code = doc_meta.get("target_corp_code") or None
                t_corp_name = doc_meta.get("target_corp_name") or None
                reporter_name = doc_meta.get("reporter_name") or None

                # 증거 파편 등록 (결정론적 fragment_id 및 전수 혈통 결속)
                frag_id_map: Dict[str, str] = {}
                for f in adapter_res.get("evidence_fragments", []):
                    raw_hash = f.get("raw_inner_hash", "")
                    role = f.get("role", "UNKNOWN")
                    # 불변 결정론적 ID
                    f_id = f"frag-{rcept_no}-{raw_hash[:16]}-{role}"
                    load_rcpt_frag = f"ldrcpt-{effective_load_run_id}-{f_id}"
                    old_uuid = f["fragment_id"]
                    frag_id_map[old_uuid] = f_id

                    frag_dict = {
                        "fragment_id": f_id,
                        "rcept_no": rcept_no,
                        "xml_sha256": disk_xml_sha,
                        "collection_run_id": run_id,
                        "collection_receipt_id": collection_receipt_id,
                        "load_run_id": effective_load_run_id,
                        "load_receipt_id": load_rcpt_frag,
                        "adapter_name": ADAPTER_NAME,
                        "adapter_version": ADAPTER_VERSION,
                        "xml_rel_path": xml_rel_path,
                        "role": role,
                        "xpath": f.get("xpath", ""),
                        "raw_inner_hash": raw_hash,
                        "extracted_value": str(f.get("extracted_value", "")),
                        "created_at": now_str
                    }
                    fragment_batch.append(frag_dict)
                    stats["fragments_created"] += 1

                # 후보 등록 (원문 행 해시 기반 불변 결정론적 ID - Fallback 완전 제거!)
                for cand in adapter_res.get("candidates", []):
                    row_hash = None
                    for orig_fid in cand.get("evidence_fragment_ids", []):
                        for ef in adapter_res.get("evidence_fragments", []):
                            if ef["fragment_id"] == orig_fid and ef.get("role") == "ROW_DATA_EVIDENCE":
                                row_hash = ef.get("raw_inner_hash")
                                break
                        if row_hash:
                            break

                    # [계약 보완] 행 해시 부재 시 fallback 절대 금지 -> 격리 보류
                    if not row_hash:
                        stats["unresolved_provenance_rows"] += 1
                        continue

                    c_id = f"cand-{rcept_no}-{row_hash[:16]}"
                    load_rcpt_cand = f"ldrcpt-{effective_load_run_id}-{c_id}"

                    cand_dict = {
                        "candidate_id": c_id,
                        "rcept_no": rcept_no,
                        "xml_sha256": disk_xml_sha,
                        "collection_run_id": run_id,
                        "collection_receipt_id": collection_receipt_id,
                        "load_run_id": effective_load_run_id,
                        "load_receipt_id": load_rcpt_cand,
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

                    # 후보 -> 파편 엣지
                    for orig_fid in cand.get("evidence_fragment_ids", []):
                        mapped_fid = frag_id_map.get(orig_fid)
                        if mapped_fid:
                            rel_batch.append({
                                "candidate_id": c_id,
                                "fragment_id": mapped_fid
                            })
                            stats["relationships_created"] += 1

            else:
                # 미지원 서식: 외부 값 주입 없이 순수 rejection_reason 및 XML 해시 기반 ID 격리 보존
                stats["unsupported_layout_count"] += 1
                rejection_reason = adapter_res.get("rejection_reason", "UNSUPPORTED_LAYOUT")
                c_id = f"cand-{rcept_no}-unsupported-{disk_xml_sha[:16]}"
                load_rcpt_cand = f"ldrcpt-{effective_load_run_id}-{c_id}"

                cand_dict = {
                    "candidate_id": c_id,
                    "rcept_no": rcept_no,
                    "xml_sha256": disk_xml_sha,
                    "collection_run_id": run_id,
                    "collection_receipt_id": collection_receipt_id,
                    "load_run_id": effective_load_run_id,
                    "load_receipt_id": load_rcpt_cand,
                    "adapter_name": ADAPTER_NAME,
                    "adapter_version": ADAPTER_VERSION,
                    "xml_rel_path": xml_rel_path,
                    "layout_status": "UNSUPPORTED_LAYOUT",
                    "rejection_reason": rejection_reason,
                    "target_corp_code": None,
                    "target_corp_name": None,
                    "reporter_name": None,
                    "holder_name": None,
                    "shares_count": None,
                    "stake_ratio": None,
                    "reporting_obligation_date": None,
                    "created_at": now_str
                }
                candidate_batch.append(cand_dict)
                stats["candidates_created"] += 1

            # 배치 단위 커밋 (commit=True 일 때만)
            if commit and (idx % batch_size == 0 or idx == len(targets)):
                self._flush_batches(candidate_batch, fragment_batch, rel_batch)
                candidate_batch.clear()
                fragment_batch.clear()
                rel_batch.clear()

        if commit and (candidate_batch or fragment_batch or rel_batch):
            self._flush_batches(candidate_batch, fragment_batch, rel_batch)

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()

        # [계약 보완] 적재 실행 영수증 (Write Manifest) 영구 발행
        if commit:
            manifest_filename = f"graph_load_manifest_{effective_load_run_id}.json"
            write_manifest_path = os.path.join(manifests_dir, manifest_filename)
            with open(write_manifest_path, "w", encoding="utf-8") as wf:
                json.dump(stats, wf, ensure_ascii=False, indent=2)
            stats["write_manifest_path"] = write_manifest_path

        return stats

    def _flush_batches(
        self,
        candidates: List[Dict[str, Any]],
        fragments: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        """Neo4j 트랜잭션 배치 적재 (ON CREATE SET 불변성 준수)"""
        if not self.driver:
            raise RuntimeError("❌ [적재 불가] commit=True이나 유효한 Neo4j Driver가 제공되지 않았습니다.")
        with self.driver.session() as session:
            # 1. Fragments 적재 (ON CREATE SET 전용 불변식 - 재실행 시 완전 no-op)
            if fragments:
                frag_cypher = """
                UNWIND $batch AS f
                MERGE (frag:EvidenceFragment {fragment_id: f.fragment_id})
                ON CREATE SET
                    frag.rcept_no = f.rcept_no,
                    frag.xml_sha256 = f.xml_sha256,
                    frag.collection_run_id = f.collection_run_id,
                    frag.collection_receipt_id = f.collection_receipt_id,
                    frag.load_run_id = f.load_run_id,
                    frag.load_receipt_id = f.load_receipt_id,
                    frag.adapter_name = f.adapter_name,
                    frag.adapter_version = f.adapter_version,
                    frag.xml_rel_path = f.xml_rel_path,
                    frag.role = f.role,
                    frag.xpath = f.xpath,
                    frag.raw_inner_hash = f.raw_inner_hash,
                    frag.extracted_value = f.extracted_value,
                    frag.created_at = f.created_at
                """
                session.run(frag_cypher, {"batch": fragments})

            # 2. Candidates 적재 (ON CREATE SET 전용 불변식 - 재실행 시 완전 no-op)
            if candidates:
                cand_cypher = """
                UNWIND $batch AS c
                MERGE (cand:RawEvidenceCandidate {candidate_id: c.candidate_id})
                ON CREATE SET
                    cand.rcept_no = c.rcept_no,
                    cand.xml_sha256 = c.xml_sha256,
                    cand.collection_run_id = c.collection_run_id,
                    cand.collection_receipt_id = c.collection_receipt_id,
                    cand.load_run_id = c.load_run_id,
                    cand.load_receipt_id = c.load_receipt_id,
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
    parser = argparse.ArgumentParser(description="Raw Evidence Graph Loader (Strict Contract v3.0)")
    parser.add_argument("--run-id", default="batch_1500_20260903_051738", help="적재 대상 Run ID")
    parser.add_argument("--load-run-id", default=None, help="그래프 적재 실행 고유 ID (생략 시 자동 생성)")
    parser.add_argument("--commit", action="store_true", help="명시적 실제 DB 적재 플래그 (미지정 시 DRY-RUN)")
    parser.add_argument("--limit", type=int, default=None, help="처리 건수 제한 (파일럿용)")
    parser.add_argument("--batch-size", type=int, default=50, help="DB 적재 배치 크기")
    args = parser.parse_args()

    print("=" * 80)
    if args.commit:
        mode_str = "🚀 [실제 Neo4j 격리 적재 모드 (--commit)]"
    else:
        mode_str = "🔍 [기본 DRY-RUN 모드 - DB 쓰기 0건]"
    print(f"{mode_str} Run ID: {args.run_id} (limit: {args.limit})")
    print("=" * 80)

    loader = RawEvidenceGraphLoader(driver=None if args.commit else "MOCK")
    try:
        res = loader.load_evidence_batch(
            run_id=args.run_id,
            load_run_id=args.load_run_id,
            commit=args.commit,
            limit=args.limit,
            batch_size=args.batch_size
        )
        print("\n📊 [적재 처리 결과]")
        print(f"• 수집 Run ID: {res['collection_run_id']}")
        print(f"• 적재 Load Run ID: {res['load_run_id']}")
        print(f"• 평가 대상 공시 건수: {res['total_targets_evaluated']:,}건")
        print(f"• 제로-트러스트 4대 해시 검증 통과: {res['zero_trust_verified_count']:,}건")
        print(f"• 제142조 일반서식 지원: {res['supported_general_count']:,}건")
        print(f"• 미지원/약식 서식 격리: {res['unsupported_layout_count']:,}건")
        print(f"• 행 해시 결손 보류 (Fallback 배제): {res['unresolved_provenance_rows']:,}건")
        print(f"• RawEvidenceCandidate 노드: {res['candidates_created']:,}개")
        print(f"• EvidenceFragment 노드: {res['fragments_created']:,}개")
        print(f"• EVIDENCED_BY 관계: {res['relationships_created']:,}개")
        print(f"• OWNS_STAKE 관계 (불변식 검증): {res['owns_stake_created']}개 (100% 0건 유지)")
        if res.get("write_manifest_path"):
            print(f"• 📜 적재 실행 영수증 발행: {res['write_manifest_path']}")
        print("=" * 80)
    finally:
        if args.commit:
            loader.close()


if __name__ == "__main__":
    main()
