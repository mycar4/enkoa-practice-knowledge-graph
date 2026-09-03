# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 5개 공시(발행회사 4개사) 파일럿 읽기 전용 종료 감사 러너
================================================================================
목적:
1. 입력 기준의 expected_corp_code를 기준으로 각 XML 추출 법인코드와 엄격 대조 (metadata_match 검증)
2. 범위 명시: 5개 공시 문서 / 4개 발행회사 (삼성전자, 현대자동차, LG화학, SK하이닉스 2건)
3. 입력 매니페스트·XML 원문·영수증의 SHA-256 해시 결속
4. 보존 성격 명확화: 로컬 디렉토리 격리 보존 (.gitignore 적용 로컬 스토리지)
5. 최종 종료 감사 보고서(pilot_closure_audit_report.json) 발행
================================================================================
"""

import os
import sys
import json
import hashlib
import importlib
from datetime import datetime, timezone
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
extract_xml_metadata = storage_mod.extract_xml_metadata
compute_bytes_sha256 = storage_mod.compute_bytes_sha256


def file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# 4대 발행회사 5개 공시 문서의 엄격 기대 기준
EXPECTED_AUDIT_BENCHMARK: List[Dict[str, str]] = [
    {
        "rcept_no": "20241025000551",
        "expected_corp_code": "00126380",
        "expected_corp_name": "삼성전자",
        "issuer_group": "삼성",
        "doc_type": "5PCT_GENERAL"
    },
    {
        "rcept_no": "20240503000063",
        "expected_corp_code": "00164742",
        "expected_corp_name": "현대자동차",
        "issuer_group": "현대차",
        "doc_type": "5PCT_GENERAL"
    },
    {
        "rcept_no": "20241129001948",
        "expected_corp_code": "00356361",
        "expected_corp_name": "LG화학",
        "issuer_group": "LG",
        "doc_type": "5PCT_GENERAL"
    },
    {
        "rcept_no": "20240925000388",
        "expected_corp_code": "00164779",
        "expected_corp_name": "에스케이하이닉스",
        "issuer_group": "SK",
        "doc_type": "5PCT_SIMPLIFIED"
    },
    {
        "rcept_no": "20241216000307",
        "expected_corp_code": "00164779",
        "expected_corp_name": "에스케이하이닉스",
        "issuer_group": "SK",
        "doc_type": "5PCT_SIMPLIFIED"
    }
]


def run_closure_audit(run_id: str = "pilot_run_20260903_033015") -> Dict[str, Any]:
    archive_dir = f"내작업폴더/data/raw_filings/pilot_live_archive/{run_id}"
    if not os.path.exists(archive_dir):
        raise FileNotFoundError(f"아카이브 디렉토리 없음: {archive_dir}")

    xml_dir = os.path.join(archive_dir, "xml")
    manifests_dir = os.path.join(archive_dir, "manifests")
    input_manifest_path = os.path.join(archive_dir, "input_manifest.json")

    print("=" * 80)
    print(f"🔍 [종료 감사 시작] Run ID: {run_id}")
    print(f"   • 대상 범위: 5개 공시 문서 / 4개 발행회사 (SK하이닉스 2건 포함)")
    print(f"   • 아카이브 경로: {archive_dir} (로컬 디스크 격리 보존)")
    print("=" * 80)

    # 1. 입력 매니페스트 해시 결속
    input_manifest_hash = file_sha256(input_manifest_path)
    print(f"1. input_manifest.json SHA-256: {input_manifest_hash}")

    # 2. 각 문서별 엄격 메타데이터 대조 및 해시 감사
    audit_rows: List[Dict[str, Any]] = []
    all_matched = True
    distinct_issuers = set()

    for idx, bench in enumerate(EXPECTED_AUDIT_BENCHMARK, start=1):
        rcept_no = bench["rcept_no"]
        xml_path = os.path.join(xml_dir, f"{rcept_no}.xml")

        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML 원문 부재: {xml_path}")

        with open(xml_path, "rb") as xf:
            xml_bytes = xf.read()

        xml_hash = compute_bytes_sha256(xml_bytes)
        meta = extract_xml_metadata(xml_bytes)

        extracted_code = meta.get("extracted_corp_code", "")
        extracted_name = meta.get("extracted_corp_name", "")

        # 엄격 대조: 법인코드는 8자리 정확 일치 필수
        code_match = (extracted_code == bench["expected_corp_code"])
        name_match = (bench["expected_corp_name"] in extracted_name)
        overall_match = code_match and name_match

        if not overall_match:
            all_matched = False

        distinct_issuers.add(extracted_code)

        # 관련 영수증 매니페스트 탐색 및 해시 결속
        related_receipts = [
            f for f in os.listdir(manifests_dir) if rcept_no in f and f.endswith(".json")
        ]
        receipt_hashes = {
            fn: file_sha256(os.path.join(manifests_dir, fn))
            for fn in sorted(related_receipts)
        }

        row = {
            "index": idx,
            "rcept_no": rcept_no,
            "issuer_group": bench["issuer_group"],
            "expected_corp_code": bench["expected_corp_code"],
            "extracted_corp_code": extracted_code,
            "corp_code_match": code_match,
            "expected_corp_name": bench["expected_corp_name"],
            "extracted_corp_name": extracted_name,
            "corp_name_match": name_match,
            "metadata_match": overall_match,
            "xml_size_bytes": len(xml_bytes),
            "xml_sha256": xml_hash,
            "receipt_count": len(related_receipts),
            "receipt_hashes": receipt_hashes
        }
        audit_rows.append(row)

        print(f"[{idx}/5] {rcept_no} ({bench['issuer_group']}) 감사:")
        print(f"    • 법인코드 일치 여부: {code_match} (기대={bench['expected_corp_code']}, 실측={extracted_code})")
        print(f"    • 회사명 정합 여부: {name_match} (기대={bench['expected_corp_name']}, 실측={extracted_name})")
        print(f"    • 원문 XML SHA-256: {xml_hash}")
        print(f"    • 보존된 영수증 수: {len(related_receipts)}건")
        print("-" * 60)

    # 3. 종료 감사 보고서 작성
    closure_report_path = os.path.join(archive_dir, "pilot_closure_audit_report.json")
    closure_data = {
        "audit_run_id": run_id,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_definition": "5_DOCUMENTS_4_ISSUER_CORPORATIONS",
        "total_documents_audited": len(audit_rows),
        "distinct_issuers_count": len(distinct_issuers),
        "distinct_issuer_codes": sorted(list(distinct_issuers)),
        "storage_classification": "LOCAL_DISK_RETENTION_GIT_IGNORED",
        "input_manifest_sha256": input_manifest_hash,
        "all_metadata_matched": all_matched,
        "audit_verdict": "PILOT_PASSED_READY_FOR_BATCH_PLANNING" if all_matched else "PILOT_METADATA_MISMATCH",
        "document_audits": audit_rows
    }

    with open(closure_report_path, "w", encoding="utf-8") as f:
        json.dump(closure_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("🏆 [종료 감사 판정 결과]")
    print(f"   • 대상: {closure_data['total_documents_audited']}개 공시 문서 / {closure_data['distinct_issuers_count']}개 발행회사")
    print(f"   • 법인코드/회사명 전수 일치 여부: {all_matched}")
    print(f"   • 스토리지 분류: {closure_data['storage_classification']}")
    print(f"   • 감사 판정: {closure_data['audit_verdict']}")
    print(f"   • 결과 파일 저장: {closure_report_path}")
    print("=" * 80)

    return closure_data


if __name__ == "__main__":
    res = run_closure_audit()
    if not res["all_metadata_matched"]:
        sys.exit(1)
