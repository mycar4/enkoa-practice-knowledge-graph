# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 고정 매니페스트 원천 결속 및 체크포인트 재개 모의시험
================================================================================
목적:
1. input_manifest_1500.json (SHA-256: c5434afd...) 원천 파일의 혈통 결속 검증
2. 프로세스 중단 후 --resume 재개 시 기존 완료 파일(0건 중복 호출) 건너뛰기 검증
3. 심층 집계 감사에서 source_manifest_verified=True 및 BATCH_VERIFIED_SUCCESS 실측
================================================================================
"""

import os
import io
import sys
import json
import shutil
import zipfile
import importlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
MockDartTransport = storage_mod.MockDartTransport

batch_mod = importlib.import_module("00_DART_Batch_Collector_1500")
BatchCollector1500 = batch_mod.BatchCollector1500
run_batch_deep_closure_audit = batch_mod.run_batch_deep_closure_audit
compute_file_sha256 = batch_mod.compute_file_sha256


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


def run_lineage_and_resume_simulation():
    source_manifest_path = "내작업폴더/data/raw_filings/input_manifest_1500.json"
    if not os.path.exists(source_manifest_path):
        raise FileNotFoundError(f"원천 매니페스트 부재: {source_manifest_path}")

    expected_frozen_sha = compute_file_sha256(source_manifest_path)
    print("=" * 80)
    print("📋 [1,500건 고정 목록 혈통 결속 & 재개 모의시험 시작]")
    print(f"• 원천 파일: {source_manifest_path}")
    print(f"• 고정 SHA-256: {expected_frozen_sha}")
    print("=" * 80)

    with open(source_manifest_path, "r", encoding="utf-8") as f:
        full_manifest = json.load(f)

    # 모의시험 대상: 앞 10건 선별
    test_slice = full_manifest["targets"][:10]

    mock_transport = MockDartTransport()
    for t in test_slice:
        r_no = t["rcept_no"]
        c_code = t["expected_corp_code"]
        c_name = t["expected_corp_name"]
        mock_transport.set_response(r_no, 200, make_mock_zip(r_no, c_code, c_name))

    sim_base_dir = "내작업폴더/data/raw_filings/sim_resume_runs"
    collector = BatchCollector1500(
        base_runs_dir=sim_base_dir,
        max_consecutive_failures=5,
        rate_limit_delay_sec=0.0,
        transport=mock_transport
    )

    # 1. 런 초기화: source_manifest_path 직접 전달
    run_id, run_dir, in_sha = collector.init_run(
        targets=test_slice,
        source_manifest_path=source_manifest_path,
        run_id_prefix="sim_resume_1500"
    )
    print(f"\n[Step 1 초기화] Run ID: {run_id}")
    print(f"• 실행 디렉토리: {run_dir}")
    print(f"• 생성된 input_manifest.json SHA: {in_sha}")

    # input_manifest.json 내용 확인
    with open(os.path.join(run_dir, "input_manifest.json"), "r", encoding="utf-8") as rf:
        saved_in_manifest = json.load(rf)

    assert saved_in_manifest["source_manifest_sha256"] == expected_frozen_sha, "원천 SHA 불일치!"
    print("  ✔️ input_manifest.json에 원천 1,500건 매니페스트 SHA-256 영구 결속 확인")

    # 2. 1차 실행: 앞 4건만 처리 후 중단 시뮬레이션
    print("\n[Step 2 1차 가동] 10건 중 앞 4건 처리 후 중단 시뮬레이션")
    collector.execute_batch(run_id, run_dir, in_sha, test_slice[:4], resume=False)
    print(f"  ✔️ 1차 완료: 네트워크 호출 {len(mock_transport.call_history)}회")
    assert len(mock_transport.call_history) == 4

    # 3. 2차 실행: 전체 10건을 대상으로 resume=True 가동
    print("\n[Step 3 2차 재개] 전체 10건 대상 --resume 재개 가동")
    resumed_summary = collector.execute_batch(run_id, run_dir, in_sha, test_slice, resume=True)
    print(f"  ✔️ 재개 완료: 누적 완료 건수 {resumed_summary['completed_count']}/10건")
    print(f"  ✔️ 총 네트워크 호출 횟수: {len(mock_transport.call_history)}회 (기존 4건 재호출 0건!)")
    assert len(mock_transport.call_history) == 10, "재개 시 중복 호출이 발생했습니다!"

    # 4. 심층 집계 감사 검증
    print("\n[Step 4 심층 집계 감사] 원천 혈통 및 5대 조건 전수 검증")
    closure_report = run_batch_deep_closure_audit(run_dir)

    print("=" * 80)
    print(f"• 전체 대상: {closure_report['total_targets']}건")
    print(f"• 열람 영수증 수: {closure_report['total_receipts_audited']}개")
    print(f"• 원천 매니페스트 경로: {closure_report['source_manifest_path']}")
    print(f"• 원천 매니페스트 SHA: {closure_report['source_manifest_sha256']}")
    print(f"• 원천 매니페스트 해시 검증: {closure_report['source_manifest_verified']}")
    print(f"• 5대 조건 일치: run_id={closure_report['all_run_ids_matched']}, manifest_sha={closure_report['all_manifest_shas_matched']}, rcept_no={closure_report['all_rcept_nos_matched']}, xml_hash={closure_report['all_xml_hashes_matched']}, corp_code={closure_report['all_corp_codes_matched']}")
    print(f"• 최종 감사 판정: {closure_report['audit_verdict']}")
    print("=" * 80)

    assert closure_report["source_manifest_verified"] is True
    assert closure_report["audit_verdict"] == "BATCH_VERIFIED_SUCCESS"

    # 아티팩트 정리
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        print(f"🧹 시뮬레이션 임시 폴더 안전 삭제: {run_dir}")

    print("\n🎉 [1,500건 고정 매니페스트 원천 결속 및 재개 모의시험 100% 합격!]")


if __name__ == "__main__":
    run_lineage_and_resume_simulation()
