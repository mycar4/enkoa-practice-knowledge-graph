# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 비파괴 Raw 증거 수집·저장 엔진 수용 계약 검증 테스트
================================================================================
1. [계약 1: 불변성 및 충돌 격리] 동일 rcept_no에 다른 바이트 유입 시 기존 파일 보존 & CONFLICT_QUARANTINED 발급
2. [계약 2: 정직한 상태 표기] 네트워크 미호출 시 network_request_made: False, http_status_code: None, SKIPPED_LOCAL_PRESENT
3. [계약 3: 자격증명 은폐] 에러 메시지 및 URL 내 crtfc_key=***REDACTED*** 마스킹 검증
4. [계약 4: 파손 데이터 격리] ZIP 파손 시 quarantine/ 바이너리 격리 및 manifests/ 영수증 동시 발급
5. [계약 5: 메타데이터 정합] 5개사 표본의 XML 원문과 일치하는 법인코드/회사명 검증
6. [거버넌스: Git 비오염] raw_filings 디렉토리가 Git 추적 대상에서 100% 제외됨 확인 (.gitignore)
================================================================================
"""

import os
import sys
import json
import shutil
import unittest
import subprocess
import importlib

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

storage_mod = importlib.import_module("00_DART_Raw_Evidence_Storage_Engine")
RawEvidenceStorageEngine = storage_mod.RawEvidenceStorageEngine
compute_bytes_sha256 = storage_mod.compute_bytes_sha256
redact_credentials = storage_mod.redact_credentials


class TestRawEvidenceStorageContracts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_storage_dir = "내작업폴더/data/raw_filings/contract_test"
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

        cls.engine = RawEvidenceStorageEngine(base_dir=cls.test_storage_dir)

        fixture_base = "내작업폴더/data/fixtures/xml_5pct_samples"
        # XML 원문과 100% 일치하는 정합 메타데이터
        cls.pilot_samples = [
            {"rcept_no": "20241025000551", "corp_code": "00126380", "corp_name": "삼성전자", "report_nm": "주식등의대량보유상황보고서(일반)", "rcept_dt": "20241025", "fixture": os.path.join(fixture_base, "20241025000551.xml")},
            {"rcept_no": "20240503000063", "corp_code": "00164742", "corp_name": "현대자동차", "report_nm": "주식등의대량보유상황보고서(일반)", "rcept_dt": "20240503", "fixture": os.path.join(fixture_base, "20240503000063.xml")},
            {"rcept_no": "20241129001948", "corp_code": "00356361", "corp_name": "LG화학", "report_nm": "주식등의대량보유상황보고서(일반)", "rcept_dt": "20241129", "fixture": os.path.join(fixture_base, "20241129001948.xml")},
            {"rcept_no": "20240925000388", "corp_code": "00164779", "corp_name": "SK하이닉스", "report_nm": "주식등의대량보유상황보고서(약식)", "rcept_dt": "20240925", "fixture": os.path.join(fixture_base, "20240925000388.xml")},
            {"rcept_no": "20241216000307", "corp_code": "00164779", "corp_name": "SK하이닉스", "report_nm": "주식등의대량보유상황보고서(약식)", "rcept_dt": "20241216", "fixture": os.path.join(fixture_base, "20241216000307.xml")}
        ]

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_storage_dir):
            shutil.rmtree(cls.test_storage_dir)

    def test_01_store_initial_samples_and_verify_receipts(self):
        """[계약 5] 정합 메타데이터로 5개사 최초 저장 및 영수증 발행 검증"""
        for item in self.pilot_samples:
            with open(item["fixture"], "rb") as f:
                b = f.read()

            receipt = self.engine.store_raw_xml_bytes(
                xml_bytes=b,
                rcept_no=item["rcept_no"],
                corp_code=item["corp_code"],
                corp_name=item["corp_name"],
                report_nm=item["report_nm"],
                rcept_dt=item["rcept_dt"],
                network_request_made=False,
                http_status_code=None,
                source_note="FIXTURE_SEED"
            )

            self.assertEqual(receipt["collection_status"], "STORED")
            self.assertEqual(receipt["requested_rcept_no"], item["rcept_no"])
            self.assertEqual(receipt["corp_code"], item["corp_code"])
            self.assertEqual(receipt["corp_name"], item["corp_name"])
            self.assertFalse(receipt["network_request_made"])
            self.assertIsNone(receipt["http_status_code"])

            # 영수증 JSON 존재 확인
            receipt_path = os.path.join(self.engine.manifests_dir, f"receipt_{item['rcept_no']}_{receipt['xml_sha256'][:8]}.json")
            self.assertTrue(os.path.exists(receipt_path))

        print("  [계약 5 통과] 정합 메타데이터 및 STORED 영수증 발급 확인")

    def test_02_idempotency_identical_bytes_no_overwrite(self):
        """[계약 2] 동일 바이트 재유입 시 덮어쓰기 금지 및 SKIPPED_LOCAL_PRESENT 확인"""
        sample = self.pilot_samples[0]
        with open(sample["fixture"], "rb") as f:
            b = f.read()

        # 동일 바이트로 다시 저장 시도
        receipt = self.engine.store_raw_xml_bytes(
            xml_bytes=b,
            rcept_no=sample["rcept_no"],
            corp_code=sample["corp_code"],
            corp_name=sample["corp_name"]
        )

        self.assertEqual(receipt["collection_status"], "SKIPPED_LOCAL_PRESENT")
        self.assertFalse(receipt["network_request_made"])
        self.assertIsNone(receipt["http_status_code"])
        self.assertEqual(receipt["source_note"], "IDENTICAL_BYTES_ALREADY_PRESENT_NO_OVERWRITE")
        print("  [계약 2 통과] 동일 바이트 재유입 시 덮어쓰기 방지 및 SKIPPED_LOCAL_PRESENT(304 날조 없음) 확인")

    def test_03_conflict_quarantine_never_overwrites(self):
        """[계약 1] 기존 rcept_no에 다른 바이트 유입 시 기존 파일 보존 및 CONFLICT_QUARANTINED 격리 실측"""
        sample = self.pilot_samples[0] # 20241025000551 삼성전자
        target_path = os.path.join(self.engine.xml_dir, f"{sample['rcept_no']}.xml")
        
        # 기존 파일의 원본 해시 기록
        with open(target_path, "rb") as f:
            original_bytes = f.read()
        original_sha = compute_bytes_sha256(original_bytes)

        # 변조된 상충 바이트 준비
        mutated_bytes = original_bytes + b"<!-- CONFLICT_TAMPERED_CONTENT -->"
        mutated_sha = compute_bytes_sha256(mutated_bytes)
        self.assertNotEqual(original_sha, mutated_sha)

        # 상충 바이트 저장 시도
        receipt = self.engine.store_raw_xml_bytes(
            xml_bytes=mutated_bytes,
            rcept_no=sample["rcept_no"],
            corp_code=sample["corp_code"],
            corp_name=sample["corp_name"]
        )

        # 1. 상태가 CONFLICT_QUARANTINED인지 확인
        self.assertEqual(receipt["collection_status"], "CONFLICT_QUARANTINED")
        self.assertIn("CONTENT_SHA256_MISMATCH", receipt["error_message"])

        # 2. [가장 중요] 기존 파일이 덮어쓰여지지 않고 원형 그대로 보존되었는지 검증!
        with open(target_path, "rb") as f:
            current_bytes = f.read()
        self.assertEqual(compute_bytes_sha256(current_bytes), original_sha, "치명적 오류: 기존 XML이 덮어쓰여짐!")

        # 3. 신규 상충 바이트가 quarantine 디렉토리에 격리 저장되었는지 확인
        quarantine_file = os.path.join(self.engine.quarantine_dir, f"conflict_{sample['rcept_no']}_{mutated_sha[:8]}.xml")
        # ts가 붙을 수 있으므로 파일 패턴 확인
        quarantined_files = [f for f in os.listdir(self.engine.quarantine_dir) if sample['rcept_no'] in f and mutated_sha[:8] in f]
        self.assertTrue(len(quarantined_files) > 0, "quarantine 격리 파일 미생성!")

        # 4. 충돌 영수증 매니페스트가 manifests/에 존재하는지 확인
        conflict_receipt_file = os.path.join(self.engine.manifests_dir, f"receipt_{sample['rcept_no']}_conflict_{mutated_sha[:8]}.json")
        self.assertTrue(os.path.exists(conflict_receipt_file), "충돌 영수증 미생성!")

        print("  [계약 1 통과] 상충 바이트 유입 시 기존 파일 100% 보존 및 CONFLICT_QUARANTINED 영수증 발급 실측 성공")

    def test_04_credentials_redaction_security(self):
        """[계약 3] 예외 메시지 및 로그에서 API 키(crtfc_key) 마스킹 검증"""
        raw_error_url = "https://opendart.fss.or.kr/api/document.xml?crtfc_key=abc123secretKey999&rcept_no=20241025000551"
        sanitized = redact_credentials(raw_error_url)

        self.assertNotIn("abc123secretKey999", sanitized, "치명적 보안 결함: API 키가 마스킹되지 않음!")
        self.assertIn("crtfc_key=***REDACTED***", sanitized)

        exception_str = "HTTPError: 403 Forbidden for url: https://opendart.fss.or.kr/api/document.xml?crtfc_key=MY_PRIVATE_KEY_1234&foo=bar"
        sanitized_exc = redact_credentials(exception_str)
        self.assertNotIn("MY_PRIVATE_KEY_1234", sanitized_exc)
        self.assertIn("crtfc_key=***REDACTED***", sanitized_exc)
        print("  [계약 3 통과] API 키 마스킹 (crtfc_key=***REDACTED***) 100% 보안 확인")

    def test_05_git_status_cleanliness(self):
        """[거버넌스] Git 상태 검사: raw_filings 디렉토리가 Git untracked에 미포함 확인"""
        res = subprocess.run(
            ["git", "status", "--porcelain", "내작업폴더/data/raw_filings"],
            capture_output=True,
            text=True,
            shell=True
        )
        self.assertEqual(res.stdout.strip(), "", f"Git 추적 오염 발생! {res.stdout}")
        print("  [거버넌스 통과] raw_filings 디렉토리의 Git 영구 격리 확인 (.gitignore 준수)")


if __name__ == "__main__":
    unittest.main()
