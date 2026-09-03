# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 대량 공시 수집 배치 제어 엔진 및 심층 집계 감사기
================================================================================
4대 운영 제어 및 데이터 거버넌스 구현:
1. HTTP 30MB 압축 페이로드 상한 검사 및 소켓 타임아웃 30초 강제
2. 지수 백오프(최대 3회) 및 서킷 브레이커(연속 5건 실패 시 즉시 비상 중단)
3. 완전 혈통 결속: input_manifest.json ➔ 영수증 ➔ batch_closure_manifest.json
4. 영수증 내부 JSON 값(rcept_no, xml_sha256, 법인코드) 전수 심층 대조 감사
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import importlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
RawEvidenceStorageEngine = storage_mod.RawEvidenceStorageEngine
compute_bytes_sha256 = storage_mod.compute_bytes_sha256
atomic_write_bytes = storage_mod.atomic_write_bytes


def compute_file_sha256(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class BatchCollector1500:
    """1,500건 대량 공시 원문 수집 배치 제어기"""

    def __init__(
        self,
        base_runs_dir: str = "내작업폴더/data/raw_filings/batch_runs",
        max_consecutive_failures: int = 5,
        rate_limit_delay_sec: float = 0.2,
        transport=None
    ):
        self.base_runs_dir = base_runs_dir
        self.max_consecutive_failures = max_consecutive_failures
        self.rate_limit_delay_sec = rate_limit_delay_sec
        self.transport = transport

    def init_run(
        self,
        targets: Optional[List[Dict[str, str]]] = None,
        source_manifest_path: Optional[str] = None,
        run_id_prefix: str = "batch_1500",
        list_source_name: str = "KOSPI_KOSDAQ_MIDCAP_MASTER",
        expected_target_count: Optional[int] = None
    ) -> Tuple[str, str, str]:
        """
        배치 런 초기화 (실패-폐쇄 Fail-Closed 강제):
        - source_manifest_path 지정 시 파일 존재, JSON 파싱, 고유성 검증 필수
        - targets 비어있거나 0건이면 즉시 예외 발생
        - targets 내 14자리 숫자 rcept_no 고유성 전수 검증
        - expected_target_count 지정 시 건수 엄격 일치 강제
        - input_manifest.json 생성 후 (run_id, run_dir, input_manifest_sha256) 반환
        """
        if source_manifest_path is not None:
            if not os.path.exists(source_manifest_path):
                raise FileNotFoundError(f"❌ [실패-폐쇄] 원천 매니페스트 파일이 존재하지 않습니다: {source_manifest_path}")
            try:
                with open(source_manifest_path, "r", encoding="utf-8") as sf:
                    src_data = json.load(sf)
            except Exception as e:
                raise ValueError(f"❌ [실패-폐쇄] 원천 매니페스트 JSON 파싱 실패: {e}")

            if targets is None:
                targets = src_data.get("targets", [])

        if not targets:
            raise ValueError("❌ [실패-폐쇄] 수집 대상(targets)이 0건이거나 비어있습니다. 실행을 생성할 수 없습니다.")

        # 접수번호 14자리 및 고유성 전수 검증
        rcept_nos = [t.get("rcept_no", "").strip() for t in targets]
        if any(not r or len(r) != 14 or not r.isdigit() for r in rcept_nos):
            raise ValueError("❌ [실패-폐쇄] targets 내에 14자리 숫자가 아닌 비정상 rcept_no가 포함되어 있습니다.")
        if len(set(rcept_nos)) != len(targets):
            raise ValueError(f"❌ [실패-폐쇄] targets 내에 중복된 rcept_no가 존재합니다! (전체: {len(targets)}, 고유: {len(set(rcept_nos))})")

        # 대상 건수 검증 (지정된 경우)
        if expected_target_count is not None and len(targets) != expected_target_count:
            raise ValueError(f"❌ [실패-폐쇄] 대상 건수 불일치: 기대={expected_target_count}건, 실제={len(targets)}건")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"{run_id_prefix}_{ts}"
        run_dir = os.path.join(self.base_runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        source_manifest_sha = None
        source_manifest_rel = None
        if source_manifest_path and os.path.exists(source_manifest_path):
            source_manifest_sha = compute_file_sha256(source_manifest_path)
            source_manifest_rel = os.path.relpath(source_manifest_path, start=os.getcwd()).replace("\\", "/")

        input_manifest_path = os.path.join(run_dir, "input_manifest.json")
        manifest_data = {
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_manifest_path": source_manifest_rel,
            "source_manifest_sha256": source_manifest_sha,
            "list_source_name": list_source_name,
            "total_target_count": len(targets),
            "max_consecutive_failures_limit": self.max_consecutive_failures,
            "rate_limit_delay_sec": self.rate_limit_delay_sec,
            "storage_tier": "LOCAL_DISK_RETENTION_GIT_IGNORED",
            "targets": targets
        }
        atomic_write_bytes(input_manifest_path, json.dumps(manifest_data, ensure_ascii=False, indent=2).encode('utf-8'))
        manifest_sha = compute_file_sha256(input_manifest_path)

        return run_id, run_dir, manifest_sha

    def execute_batch(
        self,
        run_id: str,
        run_dir: str,
        input_manifest_sha256: str,
        targets: List[Dict[str, str]],
        resume: bool = False
    ) -> Dict[str, Any]:
        """
        배치 순차 실행:
        - resume=True 시 checkpoint.json 및 로컬 xml/ 상태를 읽어 이미 완료된 rcept_no를 안전하게 건너뜀
        - 서킷 브레이커(연속 5건 실패 시 즉시 중단)
        - 실시간 checkpoint.json 갱신 (completed_rcept_nos 목록 포함)
        - 개별 영수증에 run_id 및 input_manifest_sha256 전수 결속
        """
        engine = RawEvidenceStorageEngine(
            base_dir=run_dir,
            transport=self.transport,
            rate_limit_delay_sec=self.rate_limit_delay_sec
        )

        checkpoint_path = os.path.join(run_dir, "checkpoint.json")
        consecutive_failures = 0
        circuit_breaker_tripped = False
        abort_reason = None

        completed_rcept_nos = set()
        if resume and os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as cf:
                    chk_info = json.load(cf)
                completed_rcept_nos = set(chk_info.get("completed_rcept_nos", []))
                print(f"🔄 [체크포인트 재개 감지] 기존 완료 목록 {len(completed_rcept_nos)}건 건너뜀 준비")
            except Exception as e:
                print(f"⚠️ 체크포인트 읽기 실패: {e}")

        # 로컬 xml/ 에 실존하는 파일도 완료 목록에 통합
        xml_dir = os.path.join(run_dir, "xml")
        if os.path.exists(xml_dir):
            for fn in os.listdir(xml_dir):
                if fn.endswith(".xml"):
                    completed_rcept_nos.add(fn[:-4])

        processed_results: List[Dict[str, Any]] = []

        print(f"🚀 [배치 가동] Run ID: {run_id}")
        print(f"   • 대상 건수: {len(targets)}건 (재개 모드: {resume}, 기완료: {len(completed_rcept_nos)}건)")
        print(f"   • 연속 실패 중단 기준: {self.max_consecutive_failures}회")

        for idx, target in enumerate(targets, start=1):
            rcept_no = target["rcept_no"]
            expected_corp_code = target.get("expected_corp_code", "")
            expected_corp_name = target.get("expected_corp_name", "")

            # 1. 재개 모드 건너뛰기
            if resume and rcept_no in completed_rcept_nos:
                processed_results.append({
                    "index": idx,
                    "rcept_no": rcept_no,
                    "expected_corp_code": expected_corp_code,
                    "expected_corp_name": expected_corp_name,
                    "collection_status": "SKIPPED_LOCAL_PRESENT",
                    "resumed_skip": True
                })
                consecutive_failures = 0
                continue

            # 2. 서킷 브레이커 검사
            if consecutive_failures >= self.max_consecutive_failures:
                circuit_breaker_tripped = True
                abort_reason = f"CIRCUIT_BREAKER_TRIGGERED: consecutive_failures={consecutive_failures} reached limit {self.max_consecutive_failures}"
                print(f"\n🚨 [비상 중단] {abort_reason}")
                break

            # 3. 개별 수집 및 영수증 결속 발행
            receipt = engine.fetch_and_store(
                rcept_no=rcept_no,
                caller_corp_code=expected_corp_code,
                caller_corp_name=expected_corp_name,
                force_refresh=False,
                run_id=run_id,
                input_manifest_sha256=input_manifest_sha256
            )

            status = receipt.get("collection_status")
            if status in ["STORED", "SKIPPED_LOCAL_PRESENT"]:
                consecutive_failures = 0  # 성공 시 리셋
                completed_rcept_nos.add(rcept_no)
            else:
                consecutive_failures += 1
                print(f"   ⚠️ 실패/격리 감지 ({rcept_no}): {status}, 연속 실패: {consecutive_failures}회")

            res_item = {
                "index": idx,
                "rcept_no": rcept_no,
                "expected_corp_code": expected_corp_code,
                "expected_corp_name": expected_corp_name,
                "collection_status": status,
                "xml_sha256": receipt.get("xml_sha256"),
                "network_request_made": receipt.get("network_request_made"),
                "receipt_id": receipt.get("receipt_id")
            }
            processed_results.append(res_item)

            # 실시간 체크포인트 원자적 갱신
            checkpoint_data = {
                "run_id": run_id,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "processed_count": len(processed_results),
                "total_target_count": len(targets),
                "completed_count": len(completed_rcept_nos),
                "completed_rcept_nos": sorted(list(completed_rcept_nos)),
                "current_consecutive_failures": consecutive_failures,
                "circuit_breaker_tripped": circuit_breaker_tripped,
                "last_processed_rcept_no": rcept_no
            }
            atomic_write_bytes(checkpoint_path, json.dumps(checkpoint_data, ensure_ascii=False, indent=2).encode('utf-8'))

        # 루프 탈출 후 최종 체크포인트 기록 (서킷 브레이커 상태 반영)
        final_checkpoint_data = {
            "run_id": run_id,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "processed_count": len(processed_results),
            "total_target_count": len(targets),
            "completed_count": len(completed_rcept_nos),
            "completed_rcept_nos": sorted(list(completed_rcept_nos)),
            "current_consecutive_failures": consecutive_failures,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "abort_reason": abort_reason,
            "last_processed_rcept_no": processed_results[-1]["rcept_no"] if processed_results else None
        }
        atomic_write_bytes(checkpoint_path, json.dumps(final_checkpoint_data, ensure_ascii=False, indent=2).encode('utf-8'))

        # 배치 실행 결과 요약
        batch_run_summary = {
            "run_id": run_id,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_target_count": len(targets),
            "processed_count": len(processed_results),
            "completed_count": len(completed_rcept_nos),
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "abort_reason": abort_reason,
            "consecutive_failures_at_end": consecutive_failures
        }

        return batch_run_summary


def run_batch_deep_closure_audit(run_dir: str) -> Dict[str, Any]:
    """
    배치 종료 심층 집계 감사:
    - input_manifest.json 읽기
    - 대상 1,500개 각각에 대해 manifests/ 디렉토리의 모든 영수증 JSON을 전수 열람 및 감사
    - 필수 5대 판정 기준:
      1. run_id 전수 일치
      2. input_manifest_sha256 전수 일치
      3. requested_rcept_no 전수 일치
      4. 디스크 XML SHA-256 vs 영수증 xml_sha256 전수 일치
      5. XML 추출 extracted_corp_code vs expected_corp_code 전수 일치
    - BATCH_VERIFIED_SUCCESS 판정은 위 5대 조건 및 failed=0, quarantined=0, missing=0을 100% 충족할 때만 부여
    - batch_closure_manifest.json 최종 발행
    """
    input_manifest_path = os.path.join(run_dir, "input_manifest.json")
    if not os.path.exists(input_manifest_path):
        raise FileNotFoundError(f"input_manifest 부재: {input_manifest_path}")

    with open(input_manifest_path, "r", encoding="utf-8") as f:
        in_manifest = json.load(f)

    run_id = in_manifest["run_id"]
    in_manifest_sha = compute_file_sha256(input_manifest_path)
    targets = in_manifest["targets"]

    xml_dir = os.path.join(run_dir, "xml")
    manifests_dir = os.path.join(run_dir, "manifests")

    audited_rows = []
    stored_count = 0
    skipped_count = 0
    quarantined_count = 0
    failed_count = 0
    missing_receipt_count = 0
    metadata_match_count = 0

    all_run_ids_matched = True
    all_manifest_shas_matched = True
    all_rcept_nos_matched = True
    all_xml_hashes_matched = True
    all_corp_codes_matched = True

    all_receipt_files = os.listdir(manifests_dir) if os.path.exists(manifests_dir) else []

    for target in targets:
        rcept_no = target["rcept_no"]
        expected_code = target.get("expected_corp_code", "")
        expected_name = target.get("expected_corp_name", "")

        # 해당 접수번호의 모든 영수증 탐색 (1건 이상 필수)
        matching_receipts = sorted([f for f in all_receipt_files if rcept_no in f and f.endswith(".json")])
        if not matching_receipts:
            missing_receipt_count += 1
            all_rcept_nos_matched = False
            audited_rows.append({
                "rcept_no": rcept_no,
                "audit_verdict": "MISSING_RECEIPT",
                "receipts_audited_count": 0,
                "all_receipts_valid": False
            })
            continue

        target_all_valid = True
        receipts_detail = []

        for r_fn in matching_receipts:
            receipt_path = os.path.join(manifests_dir, r_fn)
            with open(receipt_path, "r", encoding="utf-8") as rf:
                receipt = json.load(rf)

            status = receipt.get("collection_status")
            if status == "STORED":
                stored_count += 1
            elif status == "SKIPPED_LOCAL_PRESENT":
                skipped_count += 1
            elif "QUARANTINED" in str(status) or "CORRUPTED" in str(status):
                quarantined_count += 1
                target_all_valid = False
            else:
                failed_count += 1
                target_all_valid = False

            # 1. run_id 대조
            r_run_id = receipt.get("run_id")
            run_id_match = (r_run_id == run_id)
            if not run_id_match:
                all_run_ids_matched = False
                target_all_valid = False

            # 2. input_manifest_sha256 대조
            r_manifest_sha = receipt.get("input_manifest_sha256")
            manifest_sha_match = (r_manifest_sha == in_manifest_sha)
            if not manifest_sha_match:
                all_manifest_shas_matched = False
                target_all_valid = False

            # 3. requested_rcept_no 대조
            r_rcept_no = receipt.get("requested_rcept_no")
            rcept_no_match = (r_rcept_no == rcept_no)
            if not rcept_no_match:
                all_rcept_nos_matched = False
                target_all_valid = False

            # 4. XML 파일 해시 대조 (STORED/SKIPPED인 경우 필수)
            xml_hash_match = False
            if status in ["STORED", "SKIPPED_LOCAL_PRESENT"]:
                disk_xml_path = os.path.join(xml_dir, f"{rcept_no}.xml")
                if os.path.exists(disk_xml_path):
                    actual_xml_hash = compute_file_sha256(disk_xml_path)
                    xml_hash_match = (actual_xml_hash == receipt.get("xml_sha256"))
                if not xml_hash_match:
                    all_xml_hashes_matched = False
                    target_all_valid = False

            # 5. 법인코드 대조
            extracted_meta = receipt.get("extracted_metadata", {})
            extracted_code = extracted_meta.get("extracted_corp_code", "")
            code_match = (extracted_code == expected_code) if expected_code else True
            if not code_match:
                all_corp_codes_matched = False
                target_all_valid = False

            receipts_detail.append({
                "receipt_file": r_fn,
                "collection_status": status,
                "run_id_match": run_id_match,
                "manifest_sha_match": manifest_sha_match,
                "rcept_no_match": rcept_no_match,
                "xml_hash_match": xml_hash_match,
                "corp_code_match": code_match
            })

        if target_all_valid:
            metadata_match_count += 1

        audited_rows.append({
            "rcept_no": rcept_no,
            "expected_corp_code": expected_code,
            "expected_corp_name": expected_name,
            "receipts_audited_count": len(matching_receipts),
            "target_all_valid": target_all_valid,
            "receipts": receipts_detail
        })

    # 원천 입력 매니페스트 해시 결속 검증 (실패-폐쇄: 누락/None/부재 시 무조건 False)
    source_manifest_path = in_manifest.get("source_manifest_path")
    source_manifest_sha = in_manifest.get("source_manifest_sha256")
    source_manifest_verified = False
    if source_manifest_path and source_manifest_sha:
        if os.path.exists(source_manifest_path):
            current_src_sha = compute_file_sha256(source_manifest_path)
            source_manifest_verified = (current_src_sha == source_manifest_sha)

    # 타겟 수 0건이거나 source_manifest 결속 실패 시 무조건 승인 거부
    has_valid_targets = len(targets) > 0

    # 최종 엄격 판정 (실패-폐쇄: 0건 수집 또는 원천 결속 누락 시 무조건 BATCH_AUDIT_REJECTED)
    is_strictly_verified = (
        has_valid_targets and
        source_manifest_verified and
        failed_count == 0 and
        quarantined_count == 0 and
        missing_receipt_count == 0 and
        all_run_ids_matched and
        all_manifest_shas_matched and
        all_rcept_nos_matched and
        all_xml_hashes_matched and
        all_corp_codes_matched
    )

    closure_manifest_path = os.path.join(run_dir, "batch_closure_manifest.json")
    closure_data = {
        "run_id": run_id,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_manifest_sha256": in_manifest_sha,
        "source_manifest_path": source_manifest_path,
        "source_manifest_sha256": source_manifest_sha,
        "source_manifest_verified": source_manifest_verified,
        "total_targets": len(targets),
        "total_receipts_audited": len(all_receipt_files),
        "stored_count": stored_count,
        "skipped_count": skipped_count,
        "quarantined_count": quarantined_count,
        "failed_count": failed_count,
        "missing_receipt_count": missing_receipt_count,
        "all_run_ids_matched": all_run_ids_matched,
        "all_manifest_shas_matched": all_manifest_shas_matched,
        "all_rcept_nos_matched": all_rcept_nos_matched,
        "all_xml_hashes_matched": all_xml_hashes_matched,
        "all_corp_codes_matched": all_corp_codes_matched,
        "metadata_match_count": metadata_match_count,
        "metadata_match_rate_pct": round((metadata_match_count / max(1, len(targets))) * 100, 2),
        "audit_verdict": "BATCH_VERIFIED_SUCCESS" if is_strictly_verified else "BATCH_AUDIT_REJECTED",
        "detailed_target_audits": audited_rows
    }
    atomic_write_bytes(closure_manifest_path, json.dumps(closure_data, ensure_ascii=False, indent=2).encode('utf-8'))

    return closure_data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DART-Trace 1,500건 배치 수집 제어기")
    parser.add_argument("--source-manifest", type=str, default="내작업폴더/data/raw_filings/input_manifest_1500.json", help="고정 입력 매니페스트 경로")
    parser.add_argument("--resume", action="store_true", help="중단된 런 체크포인트에서 이어서 재개")
    parser.add_argument("--run-id", type=str, default=None, help="재개할 기존 run_id (미지정 시 가장 최근 런 디렉토리)")
    parser.add_argument("--delay", type=float, default=0.2, help="API 호출 간 딜레이(초)")
    parser.add_argument("--max-failures", type=int, default=5, help="서킷 브레이커 연속 실패 상한")
    args = parser.parse_args()

    base_runs_dir = "내작업폴더/data/raw_filings/batch_runs"
    collector = BatchCollector1500(
        base_runs_dir=base_runs_dir,
        max_consecutive_failures=args.max_failures,
        rate_limit_delay_sec=args.delay
    )

    if args.resume:
        if args.run_id:
            run_id = args.run_id
            run_dir = os.path.join(base_runs_dir, run_id)
        else:
            all_runs = sorted([d for d in os.listdir(base_runs_dir) if os.path.isdir(os.path.join(base_runs_dir, d))])
            if not all_runs:
                raise FileNotFoundError("재개할 기존 런 디렉토리가 없습니다.")
            run_id = all_runs[-1]
            run_dir = os.path.join(base_runs_dir, run_id)

        in_manifest_path = os.path.join(run_dir, "input_manifest.json")
        if not os.path.exists(in_manifest_path):
            raise FileNotFoundError(f"재개할 런의 input_manifest.json 부재: {in_manifest_path}")

        in_manifest_sha = compute_file_sha256(in_manifest_path)
        with open(in_manifest_path, "r", encoding="utf-8") as f:
            manifest_info = json.load(f)
        targets = manifest_info.get("targets", [])
        print(f"🔄 [--resume 재개 모드] Run ID: {run_id}, 잔여 대상 처리 시작")
    else:
        expected_cnt = 1500 if "1500" in str(args.source_manifest) else None
        run_id, run_dir, in_manifest_sha = collector.init_run(
            source_manifest_path=args.source_manifest,
            run_id_prefix="batch_1500",
            expected_target_count=expected_cnt
        )
        with open(os.path.join(run_dir, "input_manifest.json"), "r", encoding="utf-8") as f:
            manifest_info = json.load(f)
        targets = manifest_info.get("targets", [])

    summary = collector.execute_batch(run_id, run_dir, in_manifest_sha, targets, resume=args.resume)
    print("\n🔍 배치 종료 후 심층 집계 감사 자동 실행...")
    audit_res = run_batch_deep_closure_audit(run_dir)
    print(f"📊 최종 심층 감사 판정: {audit_res['audit_verdict']}")


if __name__ == "__main__":
    main()
