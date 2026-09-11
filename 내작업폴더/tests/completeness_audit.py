# -*- coding: utf-8 -*-
"""
[완결성 감사] 이미 수집한 raw JSON이 원문 PDF의 "모든 미술 실기 계열 학과"를
빠짐없이 담고 있는지 자동으로 점검한다.

배경: 2026-09-11, 사용자가 국립공주대학교 미술교육과(사범대학 소속, 학생부교과
일반전형)가 누락된 걸 발견했다. 원인은 "미대를 찾아서 수집"하는 방식이라
디자인학부 계열(예술대학 소속)만 눈에 띄고, 같은 학교의 다른 단과대학(사범대학
등)에 흩어진 미술 관련 학과는 놓치기 쉬웠기 때문이다.

v1(학과명에 "디자인/미술" 등 키워드가 있으면 후보)은 오탐이 너무 많았다 -
"디자인컨버전스학과"(천안공과대학 공학계 프로그램), "금속재료공학전공"(신소재
공학부, 재료공학이지 금속공예가 아님)처럼 이름만 비슷한 공학 계열이 대거
섞여 나왔다. 사용자 제안대로, 학과명이 아니라 "그 학과의 실기고사 과목이
실제 미술 실기 과목인지"를 기준으로 바꿨다: 원문에서 실기 과목명(소묘·수채화·
기초디자인·조소 등)이 등장하는 페이지에 같이 나오는 학과명만 후보로 채택한다.
이 방법은 이번 34개교 재검증뿐 아니라 앞으로 새 학교를 추가할 때도 "이 학과가
정말 미술 실기 전형이 있는가"를 원문 근거로 걸러내는 재사용 가능한 절차다.

주의: 이건 사람이 확인해야 할 "후보 리스트"를 만드는 도구지, 자동으로 데이터를
추가하지 않는다(원문 페이지를 직접 봐야 반영비율·전형명·모집인원이 정확함 -
Zero-Mixing 원칙과 동일한 이유로 여기서도 지어내지 않는다). 실기 과목명이
언급된 페이지에 우연히 같이 실린 무관한 학과(예: 같은 표에 나열된 음악/체육
학과)가 섞여 나올 수 있으므로 반드시 사람이 최종 확인해야 한다.

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

# 미술 실기고사에서 실제로 쓰이는 과목/과제명 - 학과 이름이 아니라 "시험 내용"
# 기준이라 공학계 "디자인" 학과(디자인컨버전스학과 등)는 여기 안 걸린다.
# "인물"·"정물"·"조소" 단독처럼 너무 흔한 한글 단어는 무관한 문맥(지원자격
# 설명, 인물평가 등)에서도 걸려 오탐을 늘리므로 빼고, 실기고사 표에서만
# 쓰이는 구체적인 복합 과목명 위주로 좁혔다.
EXAM_SUBJECT_KEYWORDS = [
    "인물수채화", "인물소묘", "정물소묘", "정물수채화", "인체소묘", "인체수채화",
    "수묵담채화", "문인화", "발상과 표현", "발상과표현", "기초디자인",
    "입체조형", "평면조형", "매체미술", "자유표현", "상황표현", "칸만화",
    "기초조형", "점토조형", "물레성형", "공예디자인", "기초소묘", "사고의전환",
    "기초수채화", "인물화", "두상소묘", "석고소묘", "정물화", "풍경소묘",
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


# 페이지 전체를 기준으로 하면(모집단위 전체를 한 표에 나열하는 학교가 많아서)
# 실기 과목명 하나 때문에 그 페이지의 무관한 학과 수십 개가 다 같이 딸려
# 나온다(실측: 페이지 단위로 했더니 792건, 대부분 공학계/인문계 오탐). 학과명
# 앞뒤 이 글자 수 안에 실기 과목명이 있어야만 "그 학과 얘기"로 인정한다.
PROXIMITY_WINDOW = 120


def extract_dept_candidates(pdf_path):
    """실기 과목명(EXAM_SUBJECT_KEYWORDS)이 근처(PROXIMITY_WINDOW자 이내)에
    같이 나오는 학과명만 후보로 뽑는다. 학과명 자체의 키워드가 아니라 "실제로
    그 학과 항목 옆에 미술 실기 과목이 언급되는가"가 채택 기준이라, 이름만
    비슷한 공학계 학과(디자인컨버전스학과 등)는 자연스럽게 걸러진다."""
    doc = fitz.open(pdf_path)
    candidates = set()
    for page in doc:
        text = page.get_text()
        subject_positions = [m.start() for kw in EXAM_SUBJECT_KEYWORDS for m in re.finditer(re.escape(kw), text)]
        if not subject_positions:
            continue
        for m in DEPT_SUFFIX_RE.finditer(text):
            token = m.group(0).strip()
            if len(token) < 3:
                continue
            if any(noise in token for noise in NOISE_SUBSTRINGS):
                continue
            dept_start, dept_end = m.start(), m.end()
            near = any(
                (dept_start - PROXIMITY_WINDOW) <= pos <= (dept_end + PROXIMITY_WINDOW)
                for pos in subject_positions
            )
            if near:
                candidates.add(token)
    doc.close()
    return candidates


_SUFFIX_RE = re.compile(r"(학과|학부|전공학과|전공)$")
_SPLIT_RE = re.compile(r"[/·,()]|\s*등\s*$")


def _stem(token):
    """접미사(학과/학부/전공)를 떼고 비교한다 - "동양화전공"과 "동양화"처럼
    접미사만 다른 표기를 같은 걸로 인식하기 위함."""
    return _SUFFIX_RE.sub("", token).strip()


def _sub_tokens(name):
    """"미술대학(동양화/회화/판화/조소/디자인학부 등)"처럼 여러 학과를 괄호·
    슬래시로 묶어 저장한 department 문자열을 개별 조각으로 쪼갠다 - 안 쪼개면
    원문의 "동양화전공"이 이 병합 문자열과 매칭이 안 돼 매번 오탐으로 잡힌다."""
    parts = [p.strip() for p in _SPLIT_RE.split(name) if p and p.strip()]
    return parts or [name]


def is_covered(candidate, covered_names):
    """느슨한 포함 관계로 확인 - 원문 학과명과 raw json의 department 표기가
    완전히 똑같지 않은 경우가 흔하다(예: "미술교육과" vs "미술교육"),
    접미사를 뗀 뒤 양방향 부분일치로 체크. covered_names 쪽은 병합 표기를
    조각내서 각 조각과도 비교한다."""
    cand_stem = _stem(candidate)
    for name in covered_names:
        if not name:
            continue
        if candidate in name or name in candidate:
            return True
        for part in _sub_tokens(name):
            part_stem = _stem(part)
            if not part_stem or not cand_stem:
                continue
            if cand_stem in part_stem or part_stem in cand_stem:
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
            if not is_covered(cand, covered_names):
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
