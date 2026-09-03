# -*- coding: utf-8 -*-
r"""
🏛️ [DART-Trace] 비파괴 Raw 증거 수집·저장 엔진 (Raw Evidence Storage Engine v3)
================================================================================
[7대 핵심 방어벽 및 무결성 수용 계약]
1. 14자리 접수번호 검증 (^\d{14}$) 및 경로 순회(Path Traversal) 원천 차단
2. 원자적 파일 쓰기 (Atomic Write: tempfile + os.replace)로 부분 쓰기/파손 방지
3. ZIP 보안 검증: .xml 단일 메인 파일 검증, 50MB 해제 상한(Zip Bomb 방지), 최소 웰폼드 확인
4. 덮어쓰기 금지 (Immutability): 기존 파일과 다른 바이트 유입 시 CONFLICT_QUARANTINED 격리
5. 정직한 상태 분리: network_request_made(bool), http_status_code(null or int), SKIPPED_LOCAL_PRESENT
6. 실행별 고유 영수증 영구 보존: receipt_{rcept_no}_{ts}_{receipt_id[:8]}.json
7. XML 내부 메타데이터(COMPANY-NAME AREGCIK, DOCUMENT-NAME) 자체 추출 및 결속
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
import tempfile
import uuid
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
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


def validate_rcept_no(rcept_no: str) -> bool:
    """14자리 공시 접수번호 형식 검증 (Path Traversal 방지)"""
    if not isinstance(rcept_no, str):
        return False
    return bool(re.match(r'^\d{14}$', rcept_no.strip()))


def _normalize_long_path(p: str) -> str:
    """Windows MAX_PATH(260자) 제한 방어를 위한 extended-length 경로 정규화"""
    abs_p = os.path.abspath(p)
    if os.name == 'nt' and not abs_p.startswith('\\\\?\\'):
        return '\\\\?\\' + abs_p
    return abs_p


def atomic_write_bytes(target_path: str, data: bytes) -> None:
    """임시 파일 생성 후 os.replace()를 통한 원자적(Atomic) 파일 쓰기 (Windows 260자 경로 제한 방어)"""
    abs_target = os.path.abspath(target_path)
    dir_name = os.path.dirname(abs_target)
    os.makedirs(dir_name, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dir_name, delete=False) as tf:
        temp_path = tf.name
        tf.write(data)

    src = _normalize_long_path(temp_path)
    dst = _normalize_long_path(abs_target)
    os.replace(src, dst)


def extract_xml_metadata(xml_bytes: bytes) -> Dict[str, str]:
    """XML 원문 내부에서 발행회사 고유번호, 회사명, 공시서식명 자체 추출"""
    text = xml_bytes.decode('utf-8', errors='ignore')
    
    # 1. 대상회사 고유번호 및 회사명 추출
    comp_m = re.search(r'<COMPANY-NAME[^>]*AREGCIK=["\'](\d{8})["\'][^>]*>(.*?)</COMPANY-NAME>', text, re.IGNORECASE)
    corp_code = comp_m.group(1).strip() if comp_m else ""
    corp_name = re.sub(r'\s+', ' ', comp_m.group(2)).strip() if comp_m else ""
    
    # 대체 태그 탐색
    if not corp_name:
        alt_m = re.search(r'<TE[^>]*ACODE=["\']CRP_NM["\'][^>]*>(.*?)</TE>', text, re.IGNORECASE)
        if alt_m:
            corp_name = re.sub(r'\s+', ' ', alt_m.group(1)).strip()

    # 2. 공시문서명 추출
    doc_m = re.search(r'<DOCUMENT-NAME[^>]*>(.*?)</DOCUMENT-NAME>', text, re.IGNORECASE)
    doc_title = re.sub(r'\s+', ' ', doc_m.group(1)).strip() if doc_m else ""

    return {
        "extracted_corp_code": corp_code,
        "extracted_corp_name": corp_name,
        "extracted_doc_title": doc_title
    }


def inspect_and_extract_zip(
    zip_bytes: bytes,
    max_uncompressed_bytes: int = 50 * 1024 * 1024
) -> Tuple[bytes, str]:
    """
    ZIP 바이너리 보안 검증 및 XML 원문 안전 추출:
    - Zip Bomb 방지: 총 압축 해제 크기 상한(50MB) 검증
    - 확장자 검증: .xml 파일이 '정확히 1개'여야 함 (0개 또는 복수 개 거부)
    - ElementTree 파싱 실측: DART 비표준 unescaped & 정규화 후 Well-formed XML 여부 엄격 검증
    """
    if len(zip_bytes) == 0:
        raise ValueError("EMPTY_ZIP_BYTES")

    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        raise ValueError(f"CORRUPTED_ZIP_FORMAT: {str(e)}")

    with z:
        namelist = z.namelist()
        if not namelist:
            raise ValueError("NO_FILES_IN_ZIP")

        # 압축 해제 크기 합산 검증 (Zip Bomb 방어)
        total_uncompressed = sum(info.file_size for info in z.infolist())
        if total_uncompressed > max_uncompressed_bytes:
            raise ValueError(f"ZIP_BOMB_DETECTED: uncompressed size {total_uncompressed} exceeds limit {max_uncompressed_bytes}")

        # .xml 파일 탐색 및 정확히 1개 존재 검증
        xml_files = [name for name in namelist if name.lower().endswith(".xml")]
        if len(xml_files) == 0:
            raise ValueError(f"NO_XML_FILE_IN_ZIP: files={namelist[:5]}")
        if len(xml_files) > 1:
            raise ValueError(f"MULTIPLE_XML_FILES_IN_ZIP: expected exactly 1, found {len(xml_files)}: {xml_files}")

        main_xml_name = xml_files[0]
        xml_bytes = z.read(main_xml_name)

    # ElementTree 파싱 실측 검증 (DART 특화 unescaped & 정규화 후 Well-formed XML 보장)
    try:
        clean_xml = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', xml_bytes.decode('utf-8', errors='ignore'))
        root = ET.fromstring(clean_xml)
        if root is None or not root.tag:
            raise ValueError("EMPTY_ROOT_TAG")
    except Exception as e:
        raise ValueError(f"MALFORMED_XML_PARSE_ERROR: {str(e)}")

    return xml_bytes, main_xml_name


# =====================================================================
# 전송 어댑터 인터페이스 및 구현체 (네트워크 주입 가능 구조)
# =====================================================================
class BaseTransportAdapter:
    """공시 원문 전송 계층 추상 인터페이스"""
    def fetch(self, rcept_no: str) -> Tuple[int, bytes, Optional[str]]:
        """(http_status_code, response_bytes, error_message) 반환"""
        raise NotImplementedError


class RealDartHttpTransport(BaseTransportAdapter):
    """실제 금융감독원 OpenDART HTTP 통신 어댑터 (30MB 크기 제한 및 지수 백오프 탑재)"""
    def __init__(
        self,
        api_key: str,
        max_payload_bytes: int = 30 * 1024 * 1024,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
        timeout_sec: float = 30.0
    ):
        self.api_key = api_key
        self.max_payload_bytes = max_payload_bytes
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.timeout_sec = timeout_sec

    def fetch(self, rcept_no: str) -> Tuple[int, bytes, Optional[str]]:
        if not self.api_key:
            return 401, b"", "DART_API_KEY_MISSING"

        url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={self.api_key}&rcept_no={rcept_no}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace Raw Collector v3)"})

        last_error = None
        status_code = 500

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    status_code = resp.getcode()

                    # 1. Content-Length 헤더 사전 검증
                    cl_header = resp.headers.get("Content-Length")
                    if cl_header and cl_header.isdigit() and int(cl_header) > self.max_payload_bytes:
                        return 413, b"", f"PAYLOAD_EXCEEDED_MAX_LIMIT_30MB: Content-Length={cl_header}"

                    # 2. 스트리밍 누적 읽기 및 30MB 상한 가드
                    chunks = []
                    total_bytes = 0
                    chunk_size = 64 * 1024
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > self.max_payload_bytes:
                            return 413, b"", f"PAYLOAD_EXCEEDED_MAX_LIMIT_30MB: stream exceeded {self.max_payload_bytes}"
                        chunks.append(chunk)

                    zip_bytes = b"".join(chunks)
                    return status_code, zip_bytes, None

            except Exception as e:
                safe_err = redact_credentials(str(e))
                status_code = getattr(e, "code", 500) if hasattr(e, "code") else 500
                last_error = safe_err

                # 재시도 대상: 429(Rate Limit) 또는 일시적 5xx 서버 오류
                if status_code in [429, 500, 502, 503, 504] and attempt < self.max_retries:
                    backoff = self.retry_backoff_base * (2 ** attempt)
                    time.sleep(backoff)
                    continue
                else:
                    break

        return status_code, b"", last_error


class MockDartTransport(BaseTransportAdapter):
    """테스트용 가짜 전송 어댑터 (네트워크 호출 0건 보장)"""
    def __init__(self, responses: Optional[Dict[str, Tuple[int, bytes, Optional[str]]]] = None):
        self.responses = responses or {}
        self.call_history: List[str] = []

    def set_response(self, rcept_no: str, status_code: int, zip_bytes: bytes, error_message: Optional[str] = None):
        self.responses[rcept_no] = (status_code, zip_bytes, error_message)

    def fetch(self, rcept_no: str) -> Tuple[int, bytes, Optional[str]]:
        self.call_history.append(rcept_no)
        if rcept_no in self.responses:
            return self.responses[rcept_no]
        return 404, b"", f"Mock 404: rcept_no {rcept_no} not registered"


# =====================================================================
# 비파괴 원문 저장 엔진 메인
# =====================================================================
class RawEvidenceStorageEngine:
    """비파괴 공시 원문 저장 및 영수증 매니페스트 발급 엔진"""

    def __init__(
        self,
        base_dir: str = "내작업폴더/data/raw_filings",
        transport: Optional[BaseTransportAdapter] = None,
        api_key: Optional[str] = None,
        rate_limit_delay_sec: float = 0.2
    ):
        self.base_dir = base_dir
        self.rate_limit_delay_sec = rate_limit_delay_sec

        # 전송 어댑터 설정 (기본값: RealDartHttpTransport)
        effective_key = api_key or os.getenv("DART_API_KEY", "")
        self.transport = transport or RealDartHttpTransport(api_key=effective_key)

        # 하위 격리 디렉토리 설정
        self.xml_dir = os.path.join(self.base_dir, "xml")
        self.manifests_dir = os.path.join(self.base_dir, "manifests")
        self.quarantine_dir = os.path.join(self.base_dir, "quarantine")
        self.logs_dir = os.path.join(self.base_dir, "logs")

        for d in [self.xml_dir, self.manifests_dir, self.quarantine_dir, self.logs_dir]:
            os.makedirs(d, exist_ok=True)

    def _get_daily_log_path(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        return os.path.join(self.logs_dir, f"collection_audit_{today_str}.jsonl")

    def _append_audit_log(self, receipt: Dict[str, Any]) -> None:
        log_path = self._get_daily_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    def _write_receipt_file(self, rcept_no: str, receipt: Dict[str, Any], suffix: str = "") -> str:
        """실행별 고유 영수증 JSON 파일 영구 저장 (UUID 및 나노초로 동일 초 충돌 100% 방지)"""
        ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        nano_part = str(time.time_ns())[-6:]
        uid_short = uuid.uuid4().hex[:8]
        fn = f"receipt_{rcept_no}_{ts_compact}_{nano_part}_{uid_short}{suffix}.json"
        target_receipt_path = os.path.join(self.manifests_dir, fn)
        atomic_write_bytes(target_receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2).encode('utf-8'))
        return target_receipt_path

    def find_cached_xml(self, rcept_no: str) -> Optional[Tuple[bytes, str]]:
        """로컬 캐시된 XML이 존재하고 유효할 경우 (bytes, sha256) 반환"""
        if not validate_rcept_no(rcept_no):
            return None
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
        caller_corp_code: str = "",
        caller_corp_name: str = "",
        caller_report_nm: str = "",
        rcept_dt: str = "",
        network_request_made: bool = False,
        http_status_code: Optional[int] = None,
        source_note: str = "DIRECT_BYTE_INJECTION",
        run_id: str = "",
        input_manifest_sha256: str = ""
    ) -> Dict[str, Any]:
        """
        원문 XML 바이트를 비파괴 불변 원칙 및 배타적 생성(xb)으로 저장
        """
        # 1. 14자리 접수번호 검증
        if not validate_rcept_no(rcept_no):
            return {
                "receipt_id": f"rcpt-invalid-{int(time.time())}",
                "requested_rcept_no": rcept_no,
                "run_id": run_id,
                "input_manifest_sha256": input_manifest_sha256,
                "collection_status": "REJECTED_INVALID_RCEPT_NO_FORMAT",
                "network_request_made": False,
                "http_status_code": None,
                "error_message": f"rcept_no must be exactly 14 digits: '{rcept_no}'",
                "source_note": None
            }

        now_utc = datetime.now(timezone.utc).isoformat()
        new_sha256 = compute_bytes_sha256(xml_bytes)
        target_xml_path = os.path.join(self.xml_dir, f"{rcept_no}.xml")
        rel_xml_path = os.path.relpath(target_xml_path, start=os.getcwd()).replace("\\", "/")

        # XML 내부 메타데이터 자체 추출
        extracted_meta = extract_xml_metadata(xml_bytes)

        # 2. 기존 파일 존재 여부 및 SHA-256 충돌 검사 (절대 덮어쓰기 금지)
        if os.path.exists(target_xml_path):
            with open(target_xml_path, "rb") as ef:
                existing_bytes = ef.read()
            existing_sha256 = compute_bytes_sha256(existing_bytes)

            if existing_sha256 == new_sha256:
                # 동일 바이트 재유입: 덮어쓰지 않고 캐시 안내 영수증 발행
                receipt = {
                    "receipt_id": f"rcpt-skip-{rcept_no}-{new_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "run_id": run_id,
                    "input_manifest_sha256": input_manifest_sha256,
                    "caller_corp_code": caller_corp_code,
                    "caller_corp_name": caller_corp_name,
                    "caller_report_nm": caller_report_nm,
                    "extracted_metadata": extracted_meta,
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
                self._write_receipt_file(rcept_no, receipt, suffix="_skipped")
                self._append_audit_log(receipt)
                return receipt
            else:
                # 상충 바이트 유입: 기존 파일 보존! 신규 바이트는 quarantine 격리
                ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                conflict_abs_path = os.path.join(self.quarantine_dir, f"conflict_{rcept_no}_{new_sha256[:8]}_{ts_compact}_{uuid.uuid4().hex[:6]}.xml")
                atomic_write_bytes(conflict_abs_path, xml_bytes)

                rel_conflict_path = os.path.relpath(conflict_abs_path, start=os.getcwd()).replace("\\", "/")
                receipt = {
                    "receipt_id": f"rcpt-conflict-{rcept_no}-{new_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "run_id": run_id,
                    "input_manifest_sha256": input_manifest_sha256,
                    "caller_corp_code": caller_corp_code,
                    "caller_corp_name": caller_corp_name,
                    "caller_report_nm": caller_report_nm,
                    "extracted_metadata": extracted_meta,
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
                self._write_receipt_file(rcept_no, receipt, suffix=f"_conflict_{new_sha256[:8]}")
                self._append_audit_log(receipt)
                return receipt

        # 3. 신규 파일 배타적 원자적 생성 (Exclusive Atomic Creation)
        try:
            with open(target_xml_path, "xb") as ef:
                ef.write(xml_bytes)
        except FileExistsError:
            # 동시 실행으로 이미 생성됨 -> 기존 바이트 재확인
            with open(target_xml_path, "rb") as ef:
                concurrent_bytes = ef.read()
            concurrent_sha256 = compute_bytes_sha256(concurrent_bytes)
            if concurrent_sha256 == new_sha256:
                receipt = {
                    "receipt_id": f"rcpt-concurrent-skip-{rcept_no}-{new_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "run_id": run_id,
                    "input_manifest_sha256": input_manifest_sha256,
                    "caller_corp_code": caller_corp_code,
                    "caller_corp_name": caller_corp_name,
                    "caller_report_nm": caller_report_nm,
                    "extracted_metadata": extracted_meta,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_xml_path,
                    "xml_size_bytes": len(concurrent_bytes),
                    "xml_sha256": concurrent_sha256,
                    "collection_status": "SKIPPED_LOCAL_PRESENT",
                    "network_request_made": network_request_made,
                    "http_status_code": http_status_code,
                    "error_message": None,
                    "source_note": "CONCURRENT_CREATION_DETECTED_IDENTICAL"
                }
                self._write_receipt_file(rcept_no, receipt, suffix="_skipped")
                self._append_audit_log(receipt)
                return receipt
            else:
                # 상충 바이트: 격리
                ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                conflict_abs_path = os.path.join(self.quarantine_dir, f"conflict_{rcept_no}_{new_sha256[:8]}_{ts_compact}_{uuid.uuid4().hex[:6]}.xml")
                atomic_write_bytes(conflict_abs_path, xml_bytes)
                rel_conflict_path = os.path.relpath(conflict_abs_path, start=os.getcwd()).replace("\\", "/")
                receipt = {
                    "receipt_id": f"rcpt-conflict-{rcept_no}-{new_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "run_id": run_id,
                    "input_manifest_sha256": input_manifest_sha256,
                    "caller_corp_code": caller_corp_code,
                    "caller_corp_name": caller_corp_name,
                    "caller_report_nm": caller_report_nm,
                    "extracted_metadata": extracted_meta,
                    "rcept_dt": rcept_dt,
                    "collection_timestamp_utc": now_utc,
                    "xml_storage_rel_path": rel_conflict_path,
                    "xml_size_bytes": len(xml_bytes),
                    "xml_sha256": new_sha256,
                    "existing_xml_sha256": concurrent_sha256,
                    "collection_status": "CONFLICT_QUARANTINED",
                    "network_request_made": network_request_made,
                    "http_status_code": http_status_code,
                    "error_message": f"CONCURRENT_CONTENT_SHA256_MISMATCH: existing={concurrent_sha256[:10]}... new={new_sha256[:10]}...",
                    "source_note": "CONCURRENT_QUARANTINED_NEVER_OVERWRITE"
                }
                self._write_receipt_file(rcept_no, receipt, suffix=f"_conflict_{new_sha256[:8]}")
                self._append_audit_log(receipt)
                return receipt

        receipt_id = f"rcpt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{rcept_no}-{new_sha256[:8]}"
        receipt = {
            "receipt_id": receipt_id,
            "requested_rcept_no": rcept_no,
            "run_id": run_id,
            "input_manifest_sha256": input_manifest_sha256,
            "caller_corp_code": caller_corp_code,
            "caller_corp_name": caller_corp_name,
            "caller_report_nm": caller_report_nm,
            "extracted_metadata": extracted_meta,
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
        self._write_receipt_file(rcept_no, receipt)
        self._append_audit_log(receipt)
        return receipt

    def fetch_and_store(
        self,
        rcept_no: str,
        caller_corp_code: str = "",
        caller_corp_name: str = "",
        caller_report_nm: str = "",
        rcept_dt: str = "",
        force_refresh: bool = False,
        run_id: str = "",
        input_manifest_sha256: str = ""
    ) -> Dict[str, Any]:
        """
        전송 어댑터를 통해 원문 수집 및 비파괴 저장 (멱등성 보장)
        """
        # 1. 14자리 접수번호 검증
        if not validate_rcept_no(rcept_no):
            return {
                "receipt_id": f"rcpt-invalid-{int(time.time())}",
                "requested_rcept_no": rcept_no,
                "run_id": run_id,
                "input_manifest_sha256": input_manifest_sha256,
                "collection_status": "REJECTED_INVALID_RCEPT_NO_FORMAT",
                "network_request_made": False,
                "http_status_code": None,
                "error_message": f"rcept_no must be exactly 14 digits: '{rcept_no}'",
                "source_note": None
            }

        now_utc = datetime.now(timezone.utc).isoformat()
        rel_xml_path = os.path.relpath(os.path.join(self.xml_dir, f"{rcept_no}.xml"), start=os.getcwd()).replace("\\", "/")

        # 2. 멱등성 검사 (로컬 캐시 존재 시 네트워크 호출 스킵)
        if not force_refresh:
            cached = self.find_cached_xml(rcept_no)
            if cached:
                cached_bytes, cached_sha256 = cached
                extracted_meta = extract_xml_metadata(cached_bytes)
                receipt = {
                    "receipt_id": f"rcpt-local-{rcept_no}-{cached_sha256[:8]}",
                    "requested_rcept_no": rcept_no,
                    "run_id": run_id,
                    "input_manifest_sha256": input_manifest_sha256,
                    "caller_corp_code": caller_corp_code,
                    "caller_corp_name": caller_corp_name,
                    "caller_report_nm": caller_report_nm,
                    "extracted_metadata": extracted_meta,
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
                self._write_receipt_file(rcept_no, receipt, suffix="_cache_hit")
                self._append_audit_log(receipt)
                return receipt

        # 3. 전송 계층을 통한 다운로드 실행
        status_code, zip_bytes, transport_err = self.transport.fetch(rcept_no)

        if transport_err or status_code != 200:
            safe_err = redact_credentials(transport_err or f"HTTP_{status_code}")
            receipt = {
                "receipt_id": f"rcpt-err-{rcept_no}",
                "requested_rcept_no": rcept_no,
                "run_id": run_id,
                "input_manifest_sha256": input_manifest_sha256,
                "caller_corp_code": caller_corp_code,
                "caller_corp_name": caller_corp_name,
                "caller_report_nm": caller_report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": None,
                "xml_size_bytes": 0,
                "xml_sha256": None,
                "collection_status": "FAILED_DOWNLOAD",
                "network_request_made": True,
                "http_status_code": status_code,
                "error_message": safe_err,
                "source_note": None
            }
            self._write_receipt_file(rcept_no, receipt, suffix="_failed")
            self._append_audit_log(receipt)
            return receipt

        # 4. ZIP 보안 검증 및 XML 추출
        try:
            xml_bytes, xml_name = inspect_and_extract_zip(zip_bytes)
        except Exception as ze:
            ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            quarantine_path = os.path.join(self.quarantine_dir, f"{rcept_no}_corrupted_{ts_compact}.bin")
            atomic_write_bytes(quarantine_path, zip_bytes)

            receipt = {
                "receipt_id": f"rcpt-corrupt-{rcept_no}-{ts_compact}",
                "requested_rcept_no": rcept_no,
                "run_id": run_id,
                "input_manifest_sha256": input_manifest_sha256,
                "caller_corp_code": caller_corp_code,
                "caller_corp_name": caller_corp_name,
                "caller_report_nm": caller_report_nm,
                "rcept_dt": rcept_dt,
                "collection_timestamp_utc": now_utc,
                "xml_storage_rel_path": os.path.relpath(quarantine_path, start=os.getcwd()).replace("\\", "/"),
                "xml_size_bytes": len(zip_bytes),
                "xml_sha256": compute_bytes_sha256(zip_bytes),
                "collection_status": "CORRUPTED_XML",
                "network_request_made": True,
                "http_status_code": status_code,
                "error_message": redact_credentials(f"INSPECT_ZIP_FAILED: {str(ze)}"),
                "source_note": "QUARANTINED"
            }
            self._write_receipt_file(rcept_no, receipt, suffix="_corrupted")
            self._append_audit_log(receipt)
            return receipt

        # 5. 정상 XML 저장 (원자적 쓰기 & 불변성 계약)
        receipt = self.store_raw_xml_bytes(
            xml_bytes=xml_bytes,
            rcept_no=rcept_no,
            caller_corp_code=caller_corp_code,
            caller_corp_name=caller_corp_name,
            caller_report_nm=caller_report_nm,
            rcept_dt=rcept_dt,
            network_request_made=True,
            http_status_code=status_code,
            source_note="TRANSPORT_DOWNLOAD",
            run_id=run_id,
            input_manifest_sha256=input_manifest_sha256
        )

        if self.rate_limit_delay_sec > 0:
            time.sleep(self.rate_limit_delay_sec)

        return receipt
