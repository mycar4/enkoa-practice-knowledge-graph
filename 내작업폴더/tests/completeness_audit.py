# -*- coding: utf-8 -*-
"""
[완결성 감사] 이미 수집한 raw JSON이 원문 PDF의 "모든 미술/디자인 계열 학과"를
빠짐없이 담고 있는지 자동으로 점검한다.

배경: 2026-09-11, 사용자가 국립공주대학교 미술교육과(사범대학 소속, 학생부교과
일반전형)가 누락된 걸 발견했다. 원인은 "미대를 찾아서 수집"하는 방식이라
디자인학부 계열(예술대학 소속)만 눈에 띄고, 같은 학교의 다른 단과대학(사범대학
등)에 흩어진 미술 관련 학과는 놓치기 쉬웠기 때문이다. 이 스크립트는 "빠짐없이
봤는지"를 사람의 기억에 의존하지 않고, 이미 로컬에 있는 38개교 원문 PDF
전체에서 학과명 패턴을 싹 훑어 raw JSON에 없는 미술 계열 학과 후보를 뽑아낸다.

주의: 이건 사람이 확인해야 할 "후보 리스트"를 만드는 도구지, 자동으로 데이터를
추가하지 않는다(원문 페이지를 직접 봐야 실기 유무·반영비율·전형명이 정확함 -
Zero-Mixing 원칙과 동일한 이유로 여기서도 지어내지 않는다). 오탐(목차, 전년도
비교표, 다른 캠퍼스 언급 등)이 섞여 나올 수 있으므로 반드시 사람이 걸러야 한다.

사용법:
    python 내작업폴더/tests/completeness_audit.py
    python 내작업폴더/tests/completeness_audit.py --university 국립공주대학교
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    print("pymupdf가 필요합니다: uv add pymupdf")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "내작업폴더" / "data" / "art_admission" / "raw"

# 학과/학부/전공 이름으로 흔히 쓰이는 접미사. 이 앞의 한글/영문/괄호/가운뎃점
# 조각을 학과명 후보로 뽑는다(너무 짧은 조각은 노이즈라 2자 이상만 인정).
DEPT_SUFFIX_RE = re.compile(r"[가-힣A-Za-z0-9·\(\)/&,\.]{2,25}(?:학과|학부|전공학과|전공)")

# 미술/디자인/조형 계열임을 시사하는 키워드 - 이 중 하나라도 포함되면 후보로 채택.
# "체육", "음악" 등 예체능계 다른 분야는 별도 관심사가 아니므로 넣지 않는다.
ART_KEYWORDS = [
    "미술", "디자인", "조형", "공예", "회화", "조소", "서양화", "동양화", "판화",
    "시각디자인", "산업디자인", "패션디자인", "패션", "텍스타일", "도예", "도자",
    "금속", "애니메이션", "만화", "웹툰", "무대미술", "무대", "의상디자인", "의상",
    "공간디자인", "공간연출", "실내디자인", "환경디자인", "영상디자인", "일러스트",
    "조형예술", "예술학과", "미술교육", "미술학",
]

# 학과명 후보에 섞여 나오지만 실제로는 학과가 아닌 흔한 오탐 패턴
NOISE_SUBSTRINGS = ["자율전공학부", "특성화고교졸업자전형", "농어촌학생전형"]


def load_covered_departments():
    """raw json 전체에서 university -> {이미 확보한 department/track 이름들} 매핑."""
    covered = {}
    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [경고] {path.name} 파싱 실패: {e}")
            continue
        records = data if isinstance(data, list) else [data]
        for rec in records:
            uni = rec.get("university")
            dept = rec.get("department") or ""
            track = rec.get("track_name") or ""
            if not uni:
                continue
            covered.setdefault(uni, set()).add(dept)
            covered.setdefault(uni, set()).add(track)
    return covered


def local_pdf_paths_for_university(university):
    """이 대학의 raw json이 참조하는 local_file 경로들을 전부 모은다(같은 학교라도
    파일이 여러 개일 수 있음 - 캠퍼스별로 다른 PDF를 쓰는 경우도 있어 중복 제거."""
    paths = set()
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        records = data if isinstance(data, list) else [data]
        for rec in records:
            if rec.get("university") != university:
                continue
            for ds in rec.get("official_facts", {}).get("data_sources", []):
                lf = ds.get("local_file")
                if lf:
                    paths.add(lf)
    return paths


def extract_dept_candidates(pdf_path):
    """PDF 전체 텍스트에서 학과명 후보를 뽑는다. 페이지를 특정하지 않고 문서
    전체를 훑는다 - 모집인원표가 어느 페이지에 있는지 학교마다 다르기 때문."""
    doc = fitz.open(pdf_path)
    candidates = set()
    for page in doc:
        text = page.get_text()
        for m in DEPT_SUFFIX_RE.finditer(text):
            token = m.group(0).strip()
            if len(token) < 3:
                continue
            if any(noise in token for noise in NOISE_SUBSTRINGS):
                continue
            candidates.add(token)
    doc.close()
    return candidates


def is_art_related(name):
    return any(kw in name for kw in ART_KEYWORDS)


def is_covered(candidate, covered_names):
    """느슨한 포함 관계로 확인 - 원문 학과명과 raw json의 department 표기가
    완전히 똑같지 않은 경우가 흔하다(예: "미술교육과" vs "미술교육"),
    양방향 부분일치로 체크."""
    for name in covered_names:
        if not name:
            continue
        if candidate in name or name in candidate:
            return True
    return False


def audit_university(university, covered_departments):
    pdf_paths = local_pdf_paths_for_university(university)
    if not pdf_paths:
        return None
    covered_names = covered_departments.get(university, set())
    missing = set()
    for rel_path in pdf_paths:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            print(f"  [경고] {university}: PDF 파일 없음 - {rel_path}")
            continue
        try:
            candidates = extract_dept_candidates(full_path)
        except Exception as e:
            print(f"  [경고] {university}: {rel_path} 텍스트 추출 실패 - {e}")
            continue
        for cand in candidates:
            if is_art_related(cand) and not is_covered(cand, covered_names):
                missing.add(cand)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--university", help="이 대학 하나만 감사(생략하면 raw json에 있는 전체 대학)")
    args = parser.parse_args()

    covered = load_covered_departments()
    universities = [args.university] if args.university else sorted(covered.keys())

    print(f"=== 완결성 감사: {len(universities)}개 대학 ===\n")
    total_missing = 0
    for uni in universities:
        missing = audit_university(uni, covered)
        if missing is None:
            continue
        if missing:
            total_missing += len(missing)
            print(f"[{uni}] 누락 의심 {len(missing)}건:")
            for m in sorted(missing):
                print(f"  - {m}")
            print()

    print("=" * 60)
    if total_missing == 0:
        print("누락 의심 학과 없음 (원문에 등장하는 미술/디자인 계열 학과명 패턴 기준).")
    else:
        print(f"총 {total_missing}건의 누락 의심 학과 발견. 각 항목은 원문 PDF를 직접 열어")
        print("실제 실기 여부·반영비율·전형명을 확인한 뒤 raw json에 추가해야 한다.")
        print("(이 리스트는 후보일 뿐이며 목차·전년도 비교표 등 오탐이 섞여 있을 수 있음)")


if __name__ == "__main__":
    main()
