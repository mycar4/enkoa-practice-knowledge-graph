# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] OpenDART 실 API 기반 15,000건 5% 대량보유상황보고서 입력 매니페스트 생성기
================================================================================
목적:
- OpenDART DS001 공시목록(list.json) API (pblntf_ty=D, 지분공시)를 3개월 윈도우로 역순 페이징 호출
- '주식등의 대량보유상황보고서'(일반/약식) 서식을 대상으로 정확히 15,000건 추출
- 14자리 rcept_no 및 8자리 expected_corp_code, expected_corp_name 영구 고정
- 기존 1,500건 매니페스트(input_manifest_1500.json)와의 중복 교집합 분석
- 서식 분포(일반 vs 약식) 및 고유 발행사 수 통계 산출
- 내작업폴더/data/raw_filings/input_manifest_15000.json 생성 및 SHA-256 결속
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
from typing import List, Dict, Any, Tuple
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


def generate_quarter_periods(start_year: int = 2024, end_year: int = 2022) -> List[Tuple[str, str]]:
    """최근 분기부터 과거 분기로 3개월 단위 기간 목록 생성 (OpenDART 1회 조회 상한: 3개월)"""
    quarters = [
        ("1001", "1231"),
        ("0701", "0930"),
        ("0401", "0630"),
        ("0101", "0331"),
    ]
    periods = []
    for y in range(start_year, end_year - 1, -1):
        for q_start, q_end in quarters:
            periods.append((f"{y}{q_start}", f"{y}{q_end}"))
    return periods


def generate_15000_manifest(target_count: int = 15000) -> Dict[str, Any]:
    if not DART_API_KEY:
        raise ValueError("❌ [보안 오류] DART_API_KEY가 .env에 설정되지 않았습니다.")

    print("=" * 80)
    print(f"📋 [OpenDART 목록 원천 수집] 5% 대량보유상황보고서 {target_count:,}건 선별 시작")
    print(f"• 시작 일시(UTC): {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 2024년 4분기부터 과거 분기로 역순 탐색
    periods = generate_quarter_periods(start_year=2024, end_year=2022)

    collected_targets: List[Dict[str, Any]] = []
    seen_rcept_nos = set()
    format_distribution = {"일반": 0, "약식": 0, "기타": 0}

    # 기존 1,500건 매니페스트 로드하여 중복 비교용 준비
    prev_manifest_path = "내작업폴더/data/raw_filings/input_manifest_1500.json"
    prev_rcept_nos = set()
    if os.path.exists(prev_manifest_path):
        try:
            with open(prev_manifest_path, "r", encoding="utf-8") as pf:
                prev_data = json.load(pf)
                prev_rcept_nos = set(t["rcept_no"] for t in prev_data.get("targets", []))
            print(f"ℹ️ [기존 매니페스트 확인] input_manifest_1500.json 내 {len(prev_rcept_nos):,}건 로드 완료")
        except Exception as e:
            print(f"⚠️ 기존 매니페스트 로드 실패: {e}")

    for bgn_de, end_de in periods:
        if len(collected_targets) >= target_count:
            break

        print(f"\n🔍 기간 조회: {bgn_de} ~ {end_de} (pblntf_ty=D, 지분공시)")
        page_no = 1

        while len(collected_targets) < target_count:
            url = (
                f"https://opendart.fss.or.kr/api/list.json?"
                f"crtfc_key={DART_API_KEY}&bgn_de={bgn_de}&end_de={end_de}&pblntf_ty=D&page_no={page_no}&page_count=100"
            )

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DART-Trace 15K Manifest Builder)"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))

                status = raw_data.get("status")
                if status != "000":
                    msg = raw_data.get("message", "")
                    if status == "013":  # 데이터 부재
                        print(f"   ℹ️ 해당 기간 데이터 없음 ({bgn_de}~{end_de})")
                    else:
                        print(f"   ⚠️ API 응답 상태 ({status}): {msg}")
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

                        fmt_type = "기타"
                        if "(일반)" in report_nm or "일반" in report_nm:
                            fmt_type = "일반"
                            format_distribution["일반"] += 1
                        elif "(약식)" in report_nm or "약식" in report_nm:
                            fmt_type = "약식"
                            format_distribution["약식"] += 1
                        else:
                            format_distribution["기타"] += 1

                        collected_targets.append({
                            "target_index": len(collected_targets) + 1,
                            "rcept_no": rcept_no,
                            "expected_corp_code": corp_code,
                            "expected_corp_name": corp_name,
                            "report_nm": report_nm,
                            "format_type": fmt_type,
                            "rcept_dt": rcept_dt
                        })

                        if len(collected_targets) >= target_count:
                            break

                total_page = raw_data.get("total_page", 1)
                if page_no % 10 == 0 or page_no == total_page or len(collected_targets) >= target_count:
                    print(f"   • Page {page_no:3d}/{total_page:3d} (누적 5% 보고서: {len(collected_targets):,}/{target_count:,}건 | 일반: {format_distribution['일반']:,}, 약식: {format_distribution['약식']:,})")

                if page_no >= total_page:
                    break
                page_no += 1
                time.sleep(0.12)  # OpenDART Rate Limit 준수

            except Exception as e:
                print(f"   ❌ API 호출 에러 (Page {page_no}): {e}")
                time.sleep(1.0)
                break

    if len(collected_targets) < target_count:
        print(f"\n⚠️ 목표 건수({target_count:,}) 미달: 총 {len(collected_targets):,}건 수집됨")

    # 엄격 무결성 사전 검증
    rcept_nos = [t["rcept_no"] for t in collected_targets]
    if len(rcept_nos) != len(set(rcept_nos)):
        raise ValueError(f"❌ [무결성 위반] targets 내 중복 rcept_no 발생! (전체: {len(rcept_nos)}, 고유: {len(set(rcept_nos))})")

    corp_codes = [t["expected_corp_code"] for t in collected_targets]
    distinct_issuers = sorted(list(set(corp_codes)))

    overlap_with_prev_1500 = len(seen_rcept_nos.intersection(prev_rcept_nos))

    out_dir = "내작업폴더/data/raw_filings"
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "input_manifest_15000.json")

    manifest_payload = {
        "manifest_type": "DART_TRACE_15000_BATCH_INPUT_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_api": "OpenDART list.json (pblntf_ty=D)",
        "document_type_filter": "주식등의 대량보유상황보고서(일반/약식)",
        "total_target_count": len(collected_targets),
        "distinct_issuers_count": len(distinct_issuers),
        "format_distribution": format_distribution,
        "overlap_with_input_manifest_1500": overlap_with_prev_1500,
        "new_targets_count": len(collected_targets) - overlap_with_prev_1500,
        "targets": collected_targets
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, ensure_ascii=False, indent=2)

    manifest_sha = compute_file_sha256(manifest_path)

    print("\n" + "=" * 80)
    print("🎉 [15,000건 입력 매니페스트 고정 완료]")
    print(f"   • 파일 경로: {manifest_path}")
    print(f"   • 총 수집된 5% 공시 대상: {len(collected_targets):,}건")
    print(f"   • 포함된 고유 발행회사 수: {len(distinct_issuers):,}개사")
    print(f"   • 서식 분포: 일반서식 {format_distribution['일반']:,}건, 약식서식 {format_distribution['약식']:,}건")
    print(f"   • 기존 1,500건 매니페스트와의 중복 수: {overlap_with_prev_1500:,}건 (동일 공시)")
    print(f"   • 순수 신규 공시 대상: {manifest_payload['new_targets_count']:,}건")
    print(f"   • input_manifest_15000.json SHA-256: {manifest_sha}")
    print("=" * 80)

    return manifest_payload


if __name__ == "__main__":
    generate_15000_manifest(target_count=15000)
