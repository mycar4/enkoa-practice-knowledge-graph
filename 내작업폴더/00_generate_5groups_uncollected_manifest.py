# -*- coding: utf-8 -*-
"""
[DART-Trace] 5대 대기업집단(삼성/SK/현대차/LG/한화) 미수집 상장 계열사 22개사
majorstock.json 매니페스트 생성기
================================================================================
- 공정거래위원회 공식 "2026년 공시대상기업집단 계열회사 현황"(별첨5)을 기준으로
  5대 그룹의 상장 계열사를 전수 확인한 뒤, 이 중 RawEvidenceCandidate가
  단 1건도 없는(=한 번도 5% 대량보유 공시가 수집된 적 없는) 22개사만 추림
  (내작업폴더/data/ftc_group_data/5groups_uncollected_targets.json 산출 과정 참고).
- 00_generate_1707_uncollected_manifest.py와 동일한 회사 단위 majorstock.json
  개별 호출 방식(날짜 구간 훑기 방식 아님 - 중복수집 버그 재발 방지).
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

INPUT_PATH = "내작업폴더/data/ftc_group_data/list_5groups_uncollected.json"
PREV_MANIFEST_PATHS = [
    "내작업폴더/data/raw_filings/input_manifest_1500.json",
    "내작업폴더/data/raw_filings/input_manifest_15000.json",
    "내작업폴더/data/raw_filings/input_manifest_1707_uncollected.json",
]
OUT_DIR = "내작업폴더/data/raw_filings"
OUT_PATH = os.path.join(OUT_DIR, "input_manifest_5groups_uncollected.json")


def compute_file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_prev_rcept_nos() -> set:
    result = set()
    for p in PREV_MANIFEST_PATHS:
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        result.update(t["rcept_no"] for t in d.get("targets", []))
    return result


def fetch_majorstock(corp_code: str) -> List[Dict[str, Any]]:
    url = f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace 5Groups Manifest Builder)"})
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
    print(f"대상 기업 수: {len(corp_items):,}개사 (5대 대기업집단 FTC 공식 계열사 중 미수집분)")

    prev_rcept_nos = load_prev_rcept_nos()
    print(f"기존 3개 매니페스트(1500/15000/1707) rcept_no 수 (중복 배제 기준): {len(prev_rcept_nos):,}건")

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
            print(f"  [{idx}/{len(corp_items)}] {corp_name}({corp_code}) - 공시 없음(013)")
        else:
            new_this_corp = 0
            for it in items:
                rcept_no = it.get("rcept_no", "").strip()
                if not rcept_no or rcept_no in seen_rcept_nos or rcept_no in prev_rcept_nos:
                    continue
                seen_rcept_nos.add(rcept_no)
                new_this_corp += 1
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
            print(f"  [{idx}/{len(corp_items)}] {corp_name}({corp_code}) - 신규 공시 {new_this_corp}건 (원본 {len(items)}건)")

        time.sleep(0.15)

    rcept_nos = [t["rcept_no"] for t in targets]
    if len(rcept_nos) != len(set(rcept_nos)):
        raise ValueError("무결성 위반: targets 내 중복 rcept_no 발생")

    distinct_issuers = sorted(set(t["expected_corp_code"] for t in targets))

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest_payload = {
        "manifest_type": "DART_TRACE_5GROUPS_UNCOLLECTED_BATCH_INPUT_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_api": "OpenDART majorstock.json (corp_code 지정 호출)",
        "source_group_list": "공정거래위원회 2026년 공시대상기업집단 계열회사 현황(별첨5), 5대 그룹(삼성/SK/현대차/LG/한화) 상장 계열사 중 미수집분",
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
    print("[5대 대기업집단 미수집분 매니페스트 생성 완료]")
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
