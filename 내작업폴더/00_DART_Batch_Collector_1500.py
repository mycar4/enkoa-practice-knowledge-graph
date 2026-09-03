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
        targets: List[Dict[str, str]],
        run_id_prefix: str = "batch_1500",
        list_source_name: str = "KOSPI_KOSDAQ_MIDCAP_MASTER"
    ) -> Tuple[str, str, str]:
        """
        배치 런 초기화:
        - 실행 디렉토리 생성
        - 사전 input_manifest.json 영구 고정 및 SHA-256 계산
        - 반환: (run_id, run_dir, input_manifest_sha256)
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"{run_id_prefix}_{ts}"
        run_dir = os.path.join(self.base_runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        input_manifest_path = os.path.join(run_dir, "input_manifest.json")
        manifest_data = {
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
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
        targets: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        배치 순차 실행:
        - 서킷 브레이커(연속 5건 실패 시 즉시 중단)
        - 실시간 checkpoint.json 갱신
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

        processed_results: List[Dict[str, Any]] = []

        print(f"🚀 [배치 시작] Run ID: {run_id}")
        print(f"   • 대상 건수: {len(targets)}건 (순차 제어)")
        print(f"   • 연속 실패 중단 기준: {self.max_consecutive_failures}회")

        for idx, target in enumerate(targets, start=1):
            rcept_no = target["rcept_no"]
            expected_corp_code = target.get("expected_corp_code", "")
            expected_corp_name = target.get("expected_corp_name", "")

            # 서킷 브레이커 검사
            if consecutive_failures >= self.max_consecutive_failures:
                circuit_breaker_tripped = True
                abort_reason = f"CIRCUIT_BREAKER_TRIGGERED: consecutive_failures={consecutive_failures} reached limit {self.max_consecutive_failures}"
                print(f"\n🚨 [비상 중단] {abort_reason}")
                break

            # 개별 수집 및 영수증 결속 발행
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

    # 최종 엄격 판정 (5대 조건 전수 충족 필수)
    is_strictly_verified = (
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
