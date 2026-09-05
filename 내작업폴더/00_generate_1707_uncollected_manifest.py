# -*- coding: utf-8 -*-
"""
[DART-Trace] 미수집 상장사 1,707개사 대상 회사별 majorstock.json 매니페스트 생성기
================================================================================
- 날짜 구간 전체를 훑는 방식(list.json) 대신, 회사(corp_code)를 지정해
  OpenDART majorstock.json(대량보유상황보고서 목록)을 개별 호출한다.
- scratch/list_uncollected_listed_companies.json (1,707개사)을 입력으로 받는다.
- 회사당 1회 호출, status='013'(데이터 없음)은 정상 케이스로 건너뛴다.
- 기존 input_manifest_15000.json과 rcept_no가 겹치면 제외한다(중복 재수집 방지).
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Any, List
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
DART_API_KEY = os.getenv("DART_API_KEY", "")

INPUT_PATH = "내작업폴더/scratch/list_uncollected_listed_companies.json"
PREV_MANIFEST_PATH = "내작업폴더/data/raw_filings/input_manifest_15000.json"
OUT_DIR = "내작업폴더/data/raw_filings"
OUT_PATH = os.path.join(OUT_DIR, "input_manifest_1707_uncollected.json")


def compute_file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_prev_rcept_nos() -> set:
    if not os.path.exists(PREV_MANIFEST_PATH):
        return set()
    with open(PREV_MANIFEST_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    return set(t["rcept_no"] for t in d.get("targets", []))


def fetch_majorstock(corp_code: str) -> List[Dict[str, Any]]:
    url = f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace 1707 Manifest Builder)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    status = data.get("status")
    if status == "000":
        return data.get("list", [])
    if status == "013":
        return []
    raise RuntimeError(f"API 오류 status={status} msg={data.get('message')}")


def main():
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY가 .env에 설정되지 않았습니다.")

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        uncollected = json.load(f)
    corp_items = list(uncollected.items())
    print(f"대상 기업 수: {len(corp_items):,}개사")

    prev_rcept_nos = load_prev_rcept_nos()
    print(f"기존 15000 매니페스트 rcept_no 수 (중복 배제 기준): {len(prev_rcept_nos):,}건")

    targets: List[Dict[str, Any]] = []
    seen_rcept_nos = set()
    no_data_count = 0
    error_corp_codes: List[str] = []

    for idx, (corp_code, info) in enumerate(corp_items, 1):
        corp_name = info.get("corp_name", "") if isinstance(info, dict) else str(info)
        try:
            items = fetch_majorstock(corp_code)
        except Exception as e:
            error_corp_codes.append(corp_code)
            print(f"  [{idx}/{len(corp_items)}] {corp_name}({corp_code}) 오류: {e}")
            time.sleep(0.3)
            continue

        if not items:
            no_data_count += 1
        else:
            for it in items:
                rcept_no = it.get("rcept_no", "").strip()
                if not rcept_no or rcept_no in seen_rcept_nos or rcept_no in prev_rcept_nos:
                    continue
                seen_rcept_nos.add(rcept_no)
                targets.append({
                    "target_index": len(targets) + 1,
                    "rcept_no": rcept_no,
                    "expected_corp_code": it.get("corp_code", corp_code).strip(),
                    "expected_corp_name": it.get("corp_name", corp_name).strip(),
                    "report_nm": it.get("report_tp", ""),
                    "format_type": it.get("report_tp", "기타"),
                    "rcept_dt": it.get("rcept_dt", ""),
                    "holder_name": it.get("repror", "")
                })

        if idx % 100 == 0 or idx == len(corp_items):
            print(f"  [{idx:5d}/{len(corp_items)}] 누적 신규 공시 {len(targets):,}건 | 데이터없음 {no_data_count:,}개사 | 오류 {len(error_corp_codes)}건")

        time.sleep(0.12)

    rcept_nos = [t["rcept_no"] for t in targets]
    if len(rcept_nos) != len(set(rcept_nos)):
        raise ValueError("무결성 위반: targets 내 중복 rcept_no 발생")

    distinct_issuers = sorted(set(t["expected_corp_code"] for t in targets))

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest_payload = {
        "manifest_type": "DART_TRACE_1707_UNCOLLECTED_BATCH_INPUT_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_api": "OpenDART majorstock.json (corp_code 지정 호출)",
        "input_company_list": INPUT_PATH,
        "input_company_count": len(corp_items),
        "companies_with_no_data": no_data_count,
        "companies_with_error": len(error_corp_codes),
        "error_corp_codes": error_corp_codes,
        "total_target_count": len(targets),
        "distinct_issuers_count": len(distinct_issuers),
        "targets": targets
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, ensure_ascii=False, indent=2)

    manifest_sha = compute_file_sha256(OUT_PATH)

    print("\n" + "=" * 80)
    print("[1707개사 매니페스트 생성 완료]")
    print(f"  파일 경로: {OUT_PATH}")
    print(f"  대상 기업 수: {len(corp_items):,}개사")
    print(f"  신규 공시 대상: {len(targets):,}건")
    print(f"  데이터 없음: {no_data_count:,}개사")
    print(f"  오류: {len(error_corp_codes):,}건")
    print(f"  고유 발행회사 수(공시 있는): {len(distinct_issuers):,}개사")
    print(f"  SHA-256: {manifest_sha}")
    print("=" * 80)


if __name__ == "__main__":
    main()
