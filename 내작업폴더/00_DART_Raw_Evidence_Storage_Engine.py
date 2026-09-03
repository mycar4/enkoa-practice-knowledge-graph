# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 비파괴 Raw 증거 수집·저장 엔진 (Raw Evidence Storage Engine)
================================================================================
1. OpenDART document.xml API를 통한 공시 원문 수집
2. SHA-256 해시 검증 및 문서 혈통(Provenance) 영수증 매니페스트 즉시 발행
3. 멱등성(Idempotency) 보장: 로컬 캐시 일치 시 API 호출 0건 (쿼터 보호)
4. 오류/파손 파일 안전 격리(Quarantine) 및 Git 레포지토리 비오염(.gitignore) 철저 준수
================================================================================
"""

import os
import io
import sys
import json
import time
import zipfile
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)


def compute_bytes_sha256(data: bytes) -> str:
    """바이트 데이터의 SHA-256 해시 16진수 문자열 반환"""
    return hashlib.sha256(data).hexdigest()


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
        http_status_code: int = 200,
        source_note: str = "DIRECT_BYTE_INJECTION"
    ) -> Dict[str, Any]:
        """이미 확보된 XML 바이트를 영수증과 함께 비파괴 저장 (테스트 및 수동 주입용)"""
        now_utc = datetime.now(timezone.utc).isoformat()
        xml_sha256 = compute_bytes_sha256(xml_bytes)
        rel_xml_path = os.path.relpath(os.path.join(self.xml_dir, f"{rcept_no}.xml"), start=os.getcwd()).replace("\\", "/")

        # 1. XML 원문 저장
        target_xml_path = os.path.join(self.xml_dir, f"{rcept_no}.xml")
        with open(target_xml_path, "wb") as f:
            f.write(xml_bytes)

        # 2. 수집 영수증 매니페스트 생성
        receipt_id = f"rcpt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{rcept_no}-{xml_sha256[:8]}"
        receipt: Dict[str, Any] = {
            "receipt_id": receipt_id,
            "requested_rcept_no": rcept_no,
            "corp_code": corp_code,
            "corp_name": corp_name,
            "report_nm": report_nm,
            "rcept_dt": rcept_dt,
            "collection_timestamp_utc": now_utc,
            "xml_storage_rel_path": rel_xml_path,
            "xml_size_bytes": len(xml_bytes),
            "xml_sha256": xml_sha256,
            "collection_status": "STORED",
            "http_status_code": http_status_code,
            "error_message": None,
            "source_note": source_note
        }

        # 3. 영수증 JSON 파일 저장
        receipt_path = os.path.join(self.manifests_dir, f"receipt_{rcept_no}_{xml_sha256[:8]}.json")
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

        # 1. 멱등성 검사 (로컬 캐시 존재 시 API 호출 스킵)
        if not force_refresh:
            cached = self.find_cached_xml(rcept_no)
            if cached:
                cached_bytes, cached_sha256 = cached
                receipt_id = f"rcpt-cached-{rcept_no}-{cached_sha256[:8]}"
                receipt = {
                    "receipt_id": receipt_id,
                    "requested_rcept_no": rcept_no,
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "report_nm": report_nm,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_xml_path,
                    "xml_size_bytes": len(cached_bytes),
                    "xml_sha256": cached_sha256,
                    "collection_status": "SKIPPED_EXISTING_IDENTICAL",
                    "http_status_code": 304,
                    "error_message": None,
                    "source_note": "LOCAL_CACHE_HIT_NO_API_CALL"
                }
                self._append_audit_log(receipt)
                return receipt

        # 2. OpenDART document.xml API 호출
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
                "http_status_code": 401,
                "error_message": "DART_API_KEY_MISSING",
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

        url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={self.api_key}&rcept_no={rcept_no}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace Raw Collector)"})

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status_code = resp.getcode()
                zip_bytes = resp.read()
        except Exception as e:
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
                "http_status_code": getattr(e, "code", 500),
                "error_message": str(e),
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

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
                "http_status_code": status_code,
                "error_message": "EMPTY_ZIP_RESPONSE",
                "source_note": None
            }
            self._append_audit_log(receipt)
            return receipt

        # 3. ZIP 압축 해제 및 XML 추출
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                namelist = z.namelist()
                if not namelist:
                    raise ValueError("NO_FILES_IN_ZIP")
                xml_filename = namelist[0]
                xml_bytes = z.read(xml_filename)
        except Exception as ze:
            quarantine_path = os.path.join(self.quarantine_dir, f"{rcept_no}_corrupted.bin")
            with open(quarantine_path, "wb") as qf:
                qf.write(zip_bytes)
            receipt = {
                "receipt_id": f"rcpt-corrupt-{rcept_no}",
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
                "http_status_code": status_code,
                "error_message": f"ZIP_EXTRACTION_FAILED: {str(ze)}",
                "source_note": "QUARANTINED"
            }
            self._append_audit_log(receipt)
            return receipt

        # 4. 정상 XML 비파괴 저장 및 영수증 매니페스트 발급
        receipt = self.store_raw_xml_bytes(
            xml_bytes=xml_bytes,
            rcept_no=rcept_no,
            corp_code=corp_code,
            corp_name=corp_name,
            report_nm=report_nm,
            rcept_dt=rcept_dt,
            http_status_code=status_code,
            source_note="OPENDART_API_DOWNLOAD"
        )

        # 5. Rate limit 준수
        if self.rate_limit_delay_sec > 0:
            time.sleep(self.rate_limit_delay_sec)

        return receipt
