# -*- coding: utf-8 -*-
"""
[② PDF 해시 필드] raw json의 각 data_sources 항목에 원문 PDF의 SHA-256을 채운다.

목적: 지금 raw json에 적힌 반영비율·실기과제·일정 등은 특정 시점의 PDF 내용을
근거로 기록된 것이다. 대학이 모집요강을 정정공고로 조용히 수정해도(실제로 흔한
일 - 오탈자 정정, 일정 변경 등) 우리 쪽 파일명/local_file 경로는 그대로라서
이런 변경을 감지할 방법이 없었다. `pdf_sha256`을 기록해두면, 나중에
`tests/pdf_hash_check.py`로 "지금 이 PDF의 해시가 우리가 수집했을 때와 같은지"를
기계적으로 확인할 수 있다 - 달라졌다면 원문이 바뀐 것이므로 재검증 대상이 된다.

이 스크립트는 raw json을 직접 덮어쓴다. 실행 전후로 `git diff`를 확인할 것.

사용법:
    python 내작업폴더/tools/compute_pdf_hashes.py            # 전체 파일
    python 내작업폴더/tools/compute_pdf_hashes.py --check    # 쓰지 않고 누락/변경만 보고
"""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="파일을 고치지 않고 누락/변경만 보고")
    args = parser.parse_args()

    updated_files = 0
    updated_entries = 0
    missing_pdfs = []
    changed_hashes = []

    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[경고] {path.name} 파싱 실패: {e}")
            continue
        records = data if isinstance(data, list) else [data]
        file_changed = False

        for rec in records:
            for ds in rec.get("official_facts", {}).get("data_sources", []):
                lf = ds.get("local_file")
                if not lf:
                    continue
                pdf_path = REPO_ROOT / lf
                if not pdf_path.exists():
                    missing_pdfs.append((path.name, lf))
                    continue
                new_hash = sha256_of(pdf_path)
                old_hash = ds.get("pdf_sha256")
                if old_hash and old_hash != new_hash:
                    changed_hashes.append((path.name, lf, old_hash, new_hash))
                if old_hash != new_hash:
                    if not args.check:
                        ds["pdf_sha256"] = new_hash
                        file_changed = True
                    updated_entries += 1

        if file_changed and not args.check:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            updated_files += 1

    mode = "점검만 (--check)" if args.check else "실제 반영"
    print(f"=== PDF 해시 {mode} 완료 ===")
    print(f"갱신된 data_sources 항목: {updated_entries}건 / 갱신된 파일: {updated_files}개")
    if missing_pdfs:
        print(f"\n[경고] 로컬에 PDF가 없어 해시를 못 만든 항목 {len(missing_pdfs)}건:")
        for fname, lf in missing_pdfs:
            print(f"  - {fname}: {lf}")
    if changed_hashes:
        print(f"\n[알림] 이미 기록된 해시와 달라진 항목 {len(changed_hashes)}건 (원문이 바뀌었을 수 있음 - 재검증 권장):")
        for fname, lf, old, new in changed_hashes:
            print(f"  - {fname}: {lf}\n      이전: {old}\n      현재: {new}")


if __name__ == "__main__":
    main()
