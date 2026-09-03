# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 5개사 순차 실 API 파일럿 수집 및 무결성 검증 러너
================================================================================
규격 및 제한:
- 최대 5건 고정, 100% 순차 실행, force_refresh=False
- 저장 경로: 내작업폴더/data/raw_filings/pilot_live_archive/{run_id}/
- 사전 입력 매니페스트 고정 (input_manifest.json)
- DB 적재·어댑터 승격·GDS 실행 절대 금지 (Zero Write)
- 1차 수집 ➔ 2차 멱등성 검증 ➔ XML 해시 및 추출 식별자 읽기 전용 감사 리포트 출력
================================================================================
"""

import os
import sys
import json
import time
import importlib
from datetime import datetime, timezone
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
RawEvidenceStorageEngine = storage_mod.RawEvidenceStorageEngine
compute_bytes_sha256 = storage_mod.compute_bytes_sha256


# 1. 고정된 5개사 입력 매니페스트 정의
PILOT_INPUT_TARGETS: List[Dict[str, str]] = [
    {
        "target_index": 1,
        "rcept_no": "20241025000551",
        "expected_corp_name": "삼성전자",
        "description": "삼성물산의 삼성전자 대량보유상황보고서(일반)"
    },
    {
        "target_index": 2,
        "rcept_no": "20240503000063",
        "expected_corp_name": "현대자동차",
        "description": "현대모비스의 현대자동차 대량보유상황보고서(일반)"
    },
    {
        "target_index": 3,
        "rcept_no": "20241129001948",
        "expected_corp_name": "LG화학",
        "description": "㈜LG의 LG화학 대량보유상황보고서(일반)"
    },
    {
        "target_index": 4,
        "rcept_no": "20240925000388",
        "expected_corp_name": "SK하이닉스",
        "description": "국민연금공단의 SK하이닉스 대량보유상황보고서(약식)"
    },
    {
        "target_index": 5,
        "rcept_no": "20241216000307",
        "expected_corp_name": "SK하이닉스",
        "description": "The Capital Group의 SK하이닉스 대량보유상황보고서(약식)"
    }
]


def run_5_pilot():
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"pilot_run_{run_timestamp}"
    base_archive_dir = f"내작업폴더/data/raw_filings/pilot_live_archive/{run_id}"

    os.makedirs(base_archive_dir, exist_ok=True)
    print(f"🚀 [파일럿 시작] Run ID: {run_id}")
    print(f"   • 저장 위치: {base_archive_dir}")
    print(f"   • 대상 건수: {len(PILOT_INPUT_TARGETS)}건 (순차 실행)")

    # 2. 시작 전 입력 매니페스트 파일 영구 고정 저장
    input_manifest_path = os.path.join(base_archive_dir, "input_manifest.json")
    input_manifest_data = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_targets": len(PILOT_INPUT_TARGETS),
        "execution_mode": "SEQUENTIAL_STRICT",
        "db_write_enabled": False,
        "targets": PILOT_INPUT_TARGETS
    }
    with open(input_manifest_path, "w", encoding="utf-8") as f:
        json.dump(input_manifest_data, f, ensure_ascii=False, indent=2)
    print(f"   • 입력 매니페스트 고정 완료: {input_manifest_path}\n")

    # 3. 비파괴 저장 엔진 인스턴스화
    engine = RawEvidenceStorageEngine(base_dir=base_archive_dir, rate_limit_delay_sec=0.25)

    # -------------------------------------------------------------
    # [1차 실행] 순차 실제 API 수집
    # -------------------------------------------------------------
    print("=" * 80)
    print("🌐 [1차 실행] OpenDART 실 API 순차 수집 진행")
    print("=" * 80)

    pass1_receipts: List[Dict[str, Any]] = []
    for item in PILOT_INPUT_TARGETS:
        rcept_no = item["rcept_no"]
        print(f"[{item['target_index']}/5] {rcept_no} ({item['expected_corp_name']}) 수집 요청 중...")

        receipt = engine.fetch_and_store(rcept_no=rcept_no, force_refresh=False)
        pass1_receipts.append(receipt)

        meta = receipt.get("extracted_metadata", {})
        print(f"    ➔ 상태: {receipt['collection_status']} (HTTP {receipt.get('http_status_code')})")
        print(f"    ➔ 크기: {receipt.get('xml_size_bytes', 0):,} bytes")
        print(f"    ➔ SHA-256: {receipt.get('xml_sha256')}")
        print(f"    ➔ XML 추출 회사코드: {meta.get('extracted_corp_code')}")
        print(f"    ➔ XML 추출 회사명: {meta.get('extracted_corp_name')}")
        print(f"    ➔ XML 추출 서식명: {meta.get('extracted_doc_title')}")
        print("-" * 60)

    # -------------------------------------------------------------
    # [2차 실행] 동일 5건 즉시 멱등성(Idempotency) 검증
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("🔁 [2차 실행] 멱등성 검증 (네트워크 호출 0건, 캐시 히트 실측)")
    print("=" * 80)

    pass2_receipts: List[Dict[str, Any]] = []
    for item in PILOT_INPUT_TARGETS:
        rcept_no = item["rcept_no"]
        receipt2 = engine.fetch_and_store(rcept_no=rcept_no, force_refresh=False)
        pass2_receipts.append(receipt2)
        print(f"[{item['target_index']}/5] {rcept_no} 재호출 ➔ 상태: {receipt2['collection_status']}, 네트워크 호출: {receipt2['network_request_made']}")

    # -------------------------------------------------------------
    # [결과 감사 리포트 생성]
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("📊 [파일럿 감사 리포트] 최종 검증 결과 요약")
    print("=" * 80)

    xml_files_on_disk = os.listdir(engine.xml_dir)
    manifest_files_on_disk = os.listdir(engine.manifests_dir)
    quarantine_files_on_disk = os.listdir(engine.quarantine_dir)

    print(f"1. 수집된 XML 원문 개수: {len(xml_files_on_disk)}개 (정상: 5개)")
    print(f"2. 발급된 영수증 매니페스트: {len(manifest_files_on_disk)}개 (1차 5개 + 2차 캐시히트 5개 = 10개)")
    print(f"3. 격리된 파손 파일 개수: {len(quarantine_files_on_disk)}개 (정상: 0개)")

    all_stored_ok = all(r["collection_status"] == "STORED" for r in pass1_receipts)
    all_skipped_ok = all(r["collection_status"] == "SKIPPED_LOCAL_PRESENT" and not r["network_request_made"] for r in pass2_receipts)

    print(f"4. 1차 수집 전수 STORED 성공 여부: {all_stored_ok}")
    print(f"5. 2차 멱등성 전수 SKIPPED_LOCAL_PRESENT 성공 여부: {all_skipped_ok}")

    # 실행 요약 매니페스트 저장
    summary_manifest_path = os.path.join(base_archive_dir, "pilot_summary_report.json")
    summary_data = {
        "run_id": run_id,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_targets": 5,
        "pass1_all_stored": all_stored_ok,
        "pass2_all_idempotent": all_skipped_ok,
        "quarantine_count": len(quarantine_files_on_disk),
        "results": [
            {
                "rcept_no": p1["requested_rcept_no"],
                "pass1_status": p1["collection_status"],
                "pass1_size_bytes": p1["xml_size_bytes"],
                "pass1_sha256": p1["xml_sha256"],
                "extracted_corp_code": p1.get("extracted_metadata", {}).get("extracted_corp_code"),
                "extracted_corp_name": p1.get("extracted_metadata", {}).get("extracted_corp_name"),
                "extracted_doc_title": p1.get("extracted_metadata", {}).get("extracted_doc_title"),
                "pass2_status": p2["collection_status"],
                "pass2_network_made": p2["network_request_made"]
            }
            for p1, p2 in zip(pass1_receipts, pass2_receipts)
        ]
    }
    with open(summary_manifest_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"6. 종합 감사 리포트 저장: {summary_manifest_path}")

    return summary_data


if __name__ == "__main__":
    res = run_5_pilot()
    if not (res["pass1_all_stored"] and res["pass2_all_idempotent"]):
        sys.exit(1)
    print("\n🎉 [5개사 실 API 순차 파일럿 100% 무결성 검증 완수!]")
