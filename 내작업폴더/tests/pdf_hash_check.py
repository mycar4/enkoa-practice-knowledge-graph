# -*- coding: utf-8 -*-
"""
[② PDF 해시 검사] raw json에 기록된 pdf_sha256이 지금 로컬 PDF와 여전히
일치하는지 확인한다. 대학이 모집요강을 정정공고로 조용히 고쳐도 우리
파일명/경로는 그대로라 지금까지는 알아챌 방법이 없었다 - 이 스크립트가
그 간극을 메운다.

일치하지 않으면(=수집 시점 이후 PDF가 바뀌었으면) 그 학교의 반영비율·실기
과제·일정 등을 재검증 대상으로 표시만 한다. 자동으로 아무것도 고치지
않는다(원문을 다시 봐야 정확한 값을 알 수 있으므로).

사용법:
    python 내작업폴더/tests/pdf_hash_check.py
"""
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "내작업폴더" / "data" / "art_admission" / "raw"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    changed = []
    missing = []
    no_hash = []

    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[경고] {path.name} 파싱 실패: {e}")
            continue
        records = data if isinstance(data, list) else [data]
        seen_files = set()
        for rec in records:
            for ds in rec.get("official_facts", {}).get("data_sources", []):
                lf = ds.get("local_file")
                if not lf or lf in seen_files:
                    continue
                seen_files.add(lf)
                recorded = ds.get("pdf_sha256")
                pdf_path = REPO_ROOT / lf
                if not pdf_path.exists():
                    missing.append((path.name, lf))
                    continue
                if not recorded:
                    no_hash.append((path.name, lf))
                    continue
                actual = sha256_of(pdf_path)
                if actual != recorded:
                    changed.append((rec.get("university"), path.name, lf, recorded, actual))

    if changed:
        print(f"⚠ 원문 PDF가 수집 시점 이후 바뀐 것으로 보이는 항목 {len(changed)}건 - 재검증 필요:")
        for uni, fname, lf, old, new in changed:
            print(f"  - [{uni}] {fname}: {lf}")
            print(f"      기록된 해시: {old}")
            print(f"      현재 해시:   {new}")
    if missing:
        print(f"\n[정보] 로컬에 PDF가 없는 항목 {len(missing)}건 (해시 검사 불가):")
        for fname, lf in missing:
            print(f"  - {fname}: {lf}")
    if no_hash:
        print(f"\n[정보] 아직 pdf_sha256이 없는 항목 {len(no_hash)}건 - "
              f"내작업폴더/tools/compute_pdf_hashes.py 실행 필요:")
        for fname, lf in no_hash:
            print(f"  - {fname}: {lf}")

    if not changed and not missing and not no_hash:
        print("✅ 전체 PDF 해시 일치 - 수집 시점 이후 원문이 바뀐 것으로 보이는 항목 없음.")

    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
