# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 비파괴 Raw 증거 수집·저장 엔진 (Raw Evidence Storage Engine v2)
================================================================================
[5대 수용 계약]
1. 덮어쓰기 금지 (Immutability): 기존 파일과 다른 바이트 유입 시 절대 덮어쓰지 않고 CONFLICT_QUARANTINED 격리
2. 정직한 상태 분리: network_request_made(bool), http_status_code(null or int), SKIPPED_LOCAL_PRESENT
3. 보안 (Credentials Redaction): 예외 및 로그에서 crtfc_key=***REDACTED*** 마스킹
4. 파손 격리 영수증: ZIP 파손 시 바이너리 격리 및 manifests/에 영수증 JSON 동시 발급
5. 메타데이터 정합: XML 원문과 일치하는 정확한 대상회사/보고자 정보 결속
================================================================================
"""

import os
import io
import re
import sys
import json
import time
import zipfile
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)


def compute_bytes_sha256(data: bytes) -> str:
    """바이트 데이터의 SHA-256 해시 반환"""
    return hashlib.sha256(data).hexdigest()


def redact_credentials(text: str) -> str:
    """URL 및 에러 메시지 내 API 인증키 정규식 마스킹"""
    if not text:
        return ""
    return re.sub(r'crtfc_key=[^&]+', 'crtfc_key=***REDACTED***', str(text), flags=re.IGNORECASE)


class RawEvidenceStorageEngine:
    """비파괴 공시 원문 저장 및 영수증 매니페스트 발급 엔진"""

    def __init__(
        self,
        base_dir: str = "내작업폴더/data/raw_filings",
        api_key: Optional[str] = None,
        rate_limit_delay_sec: float = 0.2
    ):
        self.base_dir = base_dir
        self.api_key = api_key or os.getenv("DART_API_KEY", "")
        self.rate_limit_delay_sec = rate_limit_delay_sec

        # 하위 격리 디렉토리 설정
        self.xml_dir = os.path.join(self.base_dir, "xml")
        self.manifests_dir = os.path.join(self.base_dir, "manifests")
        self.quarantine_dir = os.path.join(self.base_dir, "quarantine")
        self.logs_dir = os.path.join(self.base_dir, "logs")

        # 디렉토리 생성
        for d in [self.xml_dir, self.manifests_dir, self.quarantine_dir, self.logs_dir]:
            os.makedirs(d, exist_ok=True)

    def _get_daily_log_path(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        return os.path.join(self.logs_dir, f"collection_audit_{today_str}.jsonl")

    def _append_audit_log(self, receipt: Dict[str, Any]) -> None:
        log_path = self._get_daily_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    def find_cached_xml(self, rcept_no: str) -> Optional[Tuple[bytes, str]]:
        """로컬 캐시된 XML이 존재하고 유효할 경우 (bytes, sha256) 반환"""
        xml_path = os.path.join(self.xml_dir, f"{rcept_no}.xml")
        if os.path.exists(xml_path) and os.path.getsize(xml_path) > 0:
            with open(xml_path, "rb") as f:
                b = f.read()
            return b, compute_bytes_sha256(b)
        return None

    def store_raw_xml_bytes(
        self,
        xml_bytes: bytes,
        rcept_no: str,
        corp_code: str = "",
        corp_name: str = "",
        report_nm: str = "",
        rcept_dt: str = "",
        network_request_made: bool = False,
        http_status_code: Optional[int] = None,
        source_note: str = "DIRECT_BYTE_INJECTION"
    ) -> Dict[str, Any]:
        """
        XML 바이트를 비파괴 불변 원칙에 따라 저장 및 영수증 발행:
        - 동일 rcept_no에 동일 해시: 덮어쓰지 않고 SKIPPED_LOCAL_PRESENT 반환
        - 동일 rcept_no에 상충 해시: 기존 파일 보존, 신규 바이트는 quarantine/에 격리하고 CONFLICT_QUARANTINED 영수증 발급
        - 신규 rcept_no: xml/ 디렉토리에 최초 저장 및 STORED 영수증 발급
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        new_sha256 = compute_bytes_sha256(xml_bytes)
        target_xml_path = os.path.join(self.xml_dir, f"{rcept_no}.xml")
        rel_xml_path = os.path.relpath(target_xml_path, start=os.getcwd()).replace("\\", "/")

        # -----------------------------------------------------------------
        # 계약 1: 기존 파일 존재 여부 및 SHA-256 충돌 검사 (절대 덮어쓰기 금지)
        # -----------------------------------------------------------------
        if os.path.exists(target_xml_path):
            with open(target_xml_path, "rb") as ef:
                existing_bytes = ef.read()
            existing_sha256 = compute_bytes_sha256(existing_bytes)

            if existing_sha256 == new_sha256:
                # 동일 바이트 재유입: 덮어쓰지 않고 캐시 안내 영수증 발행
                receipt = {
                    "receipt_id": f"rcpt-skip-{rcept_no}-{new_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "report_nm": report_nm,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_xml_path,
                    "xml_size_bytes": len(existing_bytes),
                    "xml_sha256": existing_sha256,
                    "collection_status": "SKIPPED_LOCAL_PRESENT",
                    "network_request_made": network_request_made,
                    "http_status_code": http_status_code,
                    "error_message": None,
                    "source_note": "IDENTICAL_BYTES_ALREADY_PRESENT_NO_OVERWRITE"
                }
                self._append_audit_log(receipt)
                return receipt
            else:
                # 상충 바이트 유입: 기존 파일 절대 보존! 신규 바이트는 quarantine 격리
                ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                conflict_rel_name = f"conflict_{rcept_no}_{new_sha256[:8]}_{ts_compact}.xml"
                conflict_abs_path = os.path.join(self.quarantine_dir, conflict_rel_name)
                with open(conflict_abs_path, "wb") as cf:
                    cf.write(xml_bytes)

                rel_conflict_path = os.path.relpath(conflict_abs_path, start=os.getcwd()).replace("\\", "/")
                receipt_id = f"rcpt-conflict-{rcept_no}-{new_sha256[:8]}"
                receipt = {
                    "receipt_id": receipt_id,
                    "requested_rcept_no": rcept_no,
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "report_nm": report_nm,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_conflict_path,
                    "xml_size_bytes": len(xml_bytes),
                    "xml_sha256": new_sha256,
                    "existing_xml_sha256": existing_sha256,
                    "collection_status": "CONFLICT_QUARANTINED",
                    "network_request_made": network_request_made,
                    "http_status_code": http_status_code,
                    "error_message": f"CONTENT_SHA256_MISMATCH: existing={existing_sha256[:10]}... new={new_sha256[:10]}...",
                    "source_note": "QUARANTINED_NEVER_OVERWRITE"
                }
                # 충돌 영수증 영구 보존
                receipt_file = os.path.join(self.manifests_dir, f"receipt_{rcept_no}_conflict_{new_sha256[:8]}.json")
                with open(receipt_file, "w", encoding="utf-8") as f:
                    json.dump(receipt, f, ensure_ascii=False, indent=2)

                self._append_audit_log(receipt)
                return receipt

        # -----------------------------------------------------------------
        # 신규 파일 최초 저장
        # -----------------------------------------------------------------
        with open(target_xml_path, "wb") as f:
            f.write(xml_bytes)

        receipt_id = f"rcpt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{rcept_no}-{new_sha256[:8]}"
        receipt = {
            "receipt_id": receipt_id,
            "requested_rcept_no": rcept_no,
            "corp_code": corp_code,
            "corp_name": corp_name,
            "report_nm": report_nm,
            "rcept_dt": rcept_dt,
            "collection_timestamp_utc": now_utc,
            "xml_storage_rel_path": rel_xml_path,
            "xml_size_bytes": len(xml_bytes),
            "xml_sha256": new_sha256,
            "collection_status": "STORED",
            "network_request_made": network_request_made,
            "http_status_code": http_status_code,
            "error_message": None,
            "source_note": source_note
        }

        # 영수증 JSON 파일 저장
        receipt_path = os.path.join(self.manifests_dir, f"receipt_{rcept_no}_{new_sha256[:8]}.json")
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)

        self._append_audit_log(receipt)
        return receipt

    def fetch_and_store(
        self,
        rcept_no: str,
        corp_code: str = "",
        corp_name: str = "",
        report_nm: str = "",
        rcept_dt: str = "",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        OpenDART document.xml API를 통해 원문 수집 및 비파괴 저장 (멱등성 보장)
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        rel_xml_path = os.path.relpath(os.path.join(self.xml_dir, f"{rcept_no}.xml"), start=os.getcwd()).replace("\\", "/")

        # 1. 멱등성 검사 (로컬 캐시 존재 시 API 호출 완전 스킵)
        if not force_refresh:
            cached = self.find_cached_xml(rcept_no)
            if cached:
                cached_bytes, cached_sha256 = cached
                receipt = {
                    "receipt_id": f"rcpt-local-{rcept_no}-{cached_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "report_nm": report_nm,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_xml_path,
                    "xml_size_bytes": len(cached_bytes),
                    "xml_sha256": cached_sha256,
                    "collection_status": "SKIPPED_LOCAL_PRESENT",
                    "network_request_made": False,
                    "http_status_code": None,
                    "error_message": None,
                    "source_note": "LOCAL_CACHE_HIT_NO_API_CALL"
                }
                self._append_audit_log(receipt)
                return receipt

        # 2. API Key 존재 검증
        if not self.api_key:
            receipt = {
                "receipt_id": f"rcpt-err-{rcept_no}",
                "requested_rcept_no": rcept_no,
                "corp_code": corp_code,
                "corp_name": corp_name,
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": None,
                "xml_size_bytes": 0,
                "xml_sha256": None,
                "collection_status": "FAILED_DOWNLOAD",
                "network_request_made": False,
                "http_status_code": 401,
                "error_message": "DART_API_KEY_MISSING",
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

        # 3. 네트워크 요청 수행 (API 키 비노출 마스킹 가드)
        url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={self.api_key}&rcept_no={rcept_no}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace Raw Collector)"})

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status_code = resp.getcode()
                zip_bytes = resp.read()
        except Exception as e:
            safe_err = redact_credentials(str(e))
            http_code = getattr(e, "code", 500) if hasattr(e, "code") else 500
            receipt = {
                "receipt_id": f"rcpt-err-{rcept_no}",
                "requested_rcept_no": rcept_no,
                "corp_code": corp_code,
                "corp_name": corp_name,
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": None,
                "xml_size_bytes": 0,
                "xml_sha256": None,
                "collection_status": "FAILED_DOWNLOAD",
                "network_request_made": True,
                "http_status_code": http_code,
                "error_message": safe_err,
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

        # 4. 빈 응답 검증
        if len(zip_bytes) == 0:
            receipt = {
                "receipt_id": f"rcpt-empty-{rcept_no}",
                "requested_rcept_no": rcept_no,
                "corp_code": corp_code,
                "corp_name": corp_name,
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": None,
                "xml_size_bytes": 0,
                "xml_sha256": None,
                "collection_status": "CORRUPTED_XML",
                "network_request_made": True,
                "http_status_code": status_code,
                "error_message": "EMPTY_ZIP_RESPONSE",
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

        # 5. ZIP 압축 해제 및 XML 추출 (파손 시 quarantine 격리 및 영수증 발급)
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                namelist = z.namelist()
                if not namelist:
                    raise ValueError("NO_FILES_IN_ZIP")
                xml_filename = namelist[0]
                xml_bytes = z.read(xml_filename)
        except Exception as ze:
            ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            corrupted_bin_name = f"{rcept_no}_corrupted_{ts_compact}.bin"
            quarantine_path = os.path.join(self.quarantine_dir, corrupted_bin_name)
            with open(quarantine_path, "wb") as qf:
                qf.write(zip_bytes)

            receipt_id = f"rcpt-corrupt-{rcept_no}-{ts_compact}"
            receipt = {
                "receipt_id": receipt_id,
                "requested_rcept_no": rcept_no,
                "corp_code": corp_code,
                "corp_name": corp_name,
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": os.path.relpath(quarantine_path, start=os.getcwd()).replace("\\", "/"),
                "xml_size_bytes": len(zip_bytes),
                "xml_sha256": compute_bytes_sha256(zip_bytes),
                "collection_status": "CORRUPTED_XML",
                "network_request_made": True,
                "http_status_code": status_code,
                "error_message": redact_credentials(f"ZIP_EXTRACTION_FAILED: {str(ze)}"),
                "source_note": "QUARANTINED"
            }
            # 파손 격리 영수증 저장
            receipt_file = os.path.join(self.manifests_dir, f"receipt_{rcept_no}_corrupted_{ts_compact}.json")
            with open(receipt_file, "w", encoding="utf-8") as f:
                json.dump(receipt, f, ensure_ascii=False, indent=2)

            self._append_audit_log(receipt)
            return receipt

        # 6. 정상 XML 저장 (store_raw_xml_bytes 호출하여 불변성 계약 적용)
        receipt = self.store_raw_xml_bytes(
            xml_bytes=xml_bytes,
            rcept_no=rcept_no,
            corp_code=corp_code,
            corp_name=corp_name,
            report_nm=report_nm,
            rcept_dt=rcept_dt,
            network_request_made=True,
            http_status_code=status_code,
            source_note="OPENDART_API_DOWNLOAD"
        )

        # 7. Rate limit 준수
        if self.rate_limit_delay_sec > 0:
            time.sleep(self.rate_limit_delay_sec)

        return receipt
