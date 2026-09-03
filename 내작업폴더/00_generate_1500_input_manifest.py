# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] OpenDART 실 API 기반 1,500건 5% 대량보유상황보고서 입력 매니페스트 생성기
================================================================================
목적:
- OpenDART DS001 공시목록(list.json) API (pblntf_ty=D, 지분공시)를 페이징 호출
- '주식등의 대량보유상황보고서'(일반/약식) 서식을 대상으로 정확히 1,500건 추출
- rcept_no 및 expected_corp_code, expected_corp_name 영구 고정
- 내작업폴더/data/raw_filings/input_manifest_1500.json 생성 및 SHA-256 결속
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
DART_API_KEY = os.getenv("DART_API_KEY", "")


def compute_file_sha256(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate_1500_manifest(target_count: int = 1500) -> Dict[str, Any]:
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY가 설정되지 않았습니다.")

    print("=" * 80)
    print(f"📋 [OpenDART 목록 원천 수집] 5% 대량보유상황보고서 {target_count}건 선별 시작")
    print("=" * 80)

    # 3개월 단위 기간 목록 (OpenDART 1회 조회 상한: 3개월)
    # 2024년 4분기부터 역순 탐색
    periods = [
        ("20241001", "20241231"),
        ("20240701", "20240930"),
        ("20240401", "20240630"),
        ("20240101", "20240331")
    ]

    collected_targets: List[Dict[str, Any]] = []
    seen_rcept_nos = set()

    for bgn_de, end_de in periods:
        if len(collected_targets) >= target_count:
            break

        print(f"\n🔍 기간 조회: {bgn_de} ~ {end_de} (pblntf_ty=D)")
        page_no = 1

        while len(collected_targets) < target_count:
            url = (
                f"https://opendart.fss.or.kr/api/list.json?"
                f"crtfc_key={DART_API_KEY}&bgn_de={bgn_de}&end_de={end_de}&pblntf_ty=D&page_no={page_no}&page_count=100"
            )

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace Manifest Builder)"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))

                status = raw_data.get("status")
                if status != "000":
                    print(f"   ⚠️ API 응답 상태 ({status}): {raw_data.get('message')}")
                    break

                items = raw_data.get("list", [])
                if not items:
                    break

                for it in items:
                    rcept_no = it.get("rcept_no", "").strip()
                    report_nm = it.get("report_nm", "").strip()
                    corp_code = it.get("corp_code", "").strip()
                    corp_name = it.get("corp_name", "").strip()
                    rcept_dt = it.get("rcept_dt", "").strip()

                    # 5% 대량보유상황보고서 필터링 (일반/약식)
                    if "대량보유상황보고서" in report_nm and rcept_no not in seen_rcept_nos:
                        seen_rcept_nos.add(rcept_no)
                        collected_targets.append({
                            "target_index": len(collected_targets) + 1,
                            "rcept_no": rcept_no,
                            "expected_corp_code": corp_code,
                            "expected_corp_name": corp_name,
                            "report_nm": report_nm,
                            "rcept_dt": rcept_dt
                        })

                        if len(collected_targets) >= target_count:
                            break

                total_page = raw_data.get("total_page", 1)
                print(f"   • Page {page_no}/{total_page} 파싱 완료 (누적 5% 보고서: {len(collected_targets)}/{target_count}건)")

                if page_no >= total_page:
                    break
                page_no += 1
                time.sleep(0.15)  # API Rate Limit 준수

            except Exception as e:
                print(f"   ❌ API 호출 에러 (Page {page_no}): {e}")
                time.sleep(1.0)
                break

    if len(collected_targets) < target_count:
        print(f"⚠️ 목표 건수({target_count}) 미달: 총 {len(collected_targets)}건 수집됨")

    out_dir = "내작업폴더/data/raw_filings"
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "input_manifest_1500.json")

    manifest_payload = {
        "manifest_type": "DART_TRACE_1500_BATCH_INPUT_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_api": "OpenDART list.json (pblntf_ty=D)",
        "document_type_filter": "주식등의 대량보유상황보고서(일반/약식)",
        "total_target_count": len(collected_targets),
        "distinct_issuers_count": len(set(t["expected_corp_code"] for t in collected_targets)),
        "targets": collected_targets
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, ensure_ascii=False, indent=2)

    manifest_sha = compute_file_sha256(manifest_path)

    print("\n" + "=" * 80)
    print("🎉 [1,500건 입력 매니페스트 고정 완료]")
    print(f"   • 파일 경로: {manifest_path}")
    print(f"   • 수집된 5% 공시 건수: {len(collected_targets):,}건")
    print(f"   • 포함된 고유 발행회사 수: {manifest_payload['distinct_issuers_count']:,}개사")
    print(f"   • input_manifest_1500.json SHA-256: {manifest_sha}")
    print("=" * 80)

    return manifest_payload


if __name__ == "__main__":
    generate_1500_manifest(target_count=1500)
