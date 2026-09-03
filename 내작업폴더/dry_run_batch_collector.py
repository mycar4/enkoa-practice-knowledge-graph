# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 배치 제어기 Mock 기반 100% 드라이런(Dry-run) 검증 러너
================================================================================
목적:
- 내작업폴더/data/raw_filings/input_manifest_1500.json의 1,500건 목록을 직접 로드
- MockDartTransport를 주입하여 네트워크 호출 0건 상태로 배치 엔진 전 과정 모의 가동
- checkpoint.json 실시간 갱신, 영수증 1,500개 발행, batch_closure_manifest.json 심층 집계 감사 실측
- BATCH_VERIFIED_SUCCESS 판정 100% 실측 확인
================================================================================
"""

import os
import io
import sys
import json
import shutil
import zipfile
import importlib
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
MockDartTransport = storage_mod.MockDartTransport

batch_mod = importlib.import_module("00_DART_Batch_Collector_1500")
BatchCollector1500 = batch_mod.BatchCollector1500
run_batch_deep_closure_audit = batch_mod.run_batch_deep_closure_audit


def make_mock_zip(rcept_no: str, corp_code: str, corp_name: str) -> bytes:
    xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
  <COMPANY-NAME AREGCIK="{corp_code}">{corp_name}</COMPANY-NAME>
  <DOCUMENT-NAME>주식등의 대량보유상황보고서(일반)</DOCUMENT-NAME>
  <BODY>Mock Content for {rcept_no}</BODY>
</DOCUMENT>""".encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{rcept_no}.xml", xml_content)
    return buf.getvalue()


def run_1500_dry_run():
    manifest_path = "내작업폴더/data/raw_filings/input_manifest_1500.json"
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"1,500건 입력 매니페스트 부재: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    targets = manifest["targets"]
    print("=" * 80)
    print(f"🧪 [배치 드라이런 시작] 대상: {len(targets):,}건 (네트워크 호출 0건, Mock 기반)")
    print("=" * 80)

    # Mock 전송 계층 준비 (모든 타겟에 대해 유효한 XML 반환)
    mock_transport = MockDartTransport()
    for t in targets:
        r_no = t["rcept_no"]
        c_code = t["expected_corp_code"]
        c_name = t["expected_corp_name"]
        mock_transport.set_response(r_no, 200, make_mock_zip(r_no, c_code, c_name))

    dry_run_base_dir = "내작업폴더/data/raw_filings/batch_runs"
    collector = BatchCollector1500(
        base_runs_dir=dry_run_base_dir,
        max_consecutive_failures=5,
        rate_limit_delay_sec=0.0,
        transport=mock_transport
    )

    run_id, run_dir, in_manifest_sha = collector.init_run(targets, run_id_prefix="dryrun_1500")
    print(f"• Run ID: {run_id}")
    print(f"• Run Dir: {run_dir}")
    print(f"• Input Manifest SHA-256: {in_manifest_sha}")

    # 배치 실행
    summary = collector.execute_batch(run_id, run_dir, in_manifest_sha, targets)
    print(f"\n• 실행 완료 건수: {summary['processed_count']:,}/{summary['total_target_count']:,}")
    print(f"• 서킷 브레이커 발동 여부: {summary['circuit_breaker_tripped']}")

    # 심층 집계 감사 실행
    print("\n🔍 심층 집계 감사(run_batch_deep_closure_audit) 실행 중...")
    closure_report = run_batch_deep_closure_audit(run_dir)

    print("=" * 80)
    print("📊 [드라이런 최종 심층 감사 결과]")
    print(f"   • 전체 대상 건수: {closure_report['total_targets']:,}건")
    print(f"   • 전수 열람된 영수증 수: {closure_report['total_receipts_audited']:,}개")
    print(f"   • STORED 성공 건수: {closure_report['stored_count']:,}건")
    print(f"   • 실패/격리/누락 건수: {closure_report['failed_count']} / {closure_report['quarantined_count']} / {closure_report['missing_receipt_count']}")
    print(f"   • run_id 전수 일치: {closure_report['all_run_ids_matched']}")
    print(f"   • manifest_sha 전수 일치: {closure_report['all_manifest_shas_matched']}")
    print(f"   • rcept_no 전수 일치: {closure_report['all_rcept_nos_matched']}")
    print(f"   • XML 해시 전수 일치: {closure_report['all_xml_hashes_matched']}")
    print(f"   • 법인코드 전수 일치: {closure_report['all_corp_codes_matched']}")
    print(f"   • 메타데이터 정합율: {closure_report['metadata_match_rate_pct']}%")
    print(f"   • 최종 감사 판정: {closure_report['audit_verdict']}")
    print("=" * 80)

    # 드라이런 아티팩트 정리
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        print(f"🧹 드라이런 임시 아티팩트 안전 삭제 완료: {run_dir}")

    return closure_report


if __name__ == "__main__":
    rep = run_1500_dry_run()
    if rep["audit_verdict"] != "BATCH_VERIFIED_SUCCESS":
        sys.exit(1)
    print("\n🎉 [1,500건 배치 제어기 드라이런 100% 무결성 실측 완료!]")
