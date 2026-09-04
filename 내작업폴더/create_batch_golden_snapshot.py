# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] 1,500건 배치 무결성 스냅샷 패키징 및 보조 디스크(D:) 격리 백업 러너
================================================================================
목적:
1. batch_1500_20260903_051738 폴더 전수(XML 1,500개 + 영수증 1,500개 + 감사보고서)를
   단일 ZIP 아카이브로 결정론적 패키징
2. ZIP 파일의 SHA-256 체크섬 및 전수 파일 목록 매니페스트 생성
3. 보조 물리 디스크(D:\DART_Raw_Backup)로 안전 복사
4. 복사 대상 위치에서 SHA-256 해시 재검증 및 읽기 전용(Read-Only) 속성 부여
================================================================================
"""

import os
import sys
import json
import zipfile
import hashlib
import shutil
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def compute_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_snapshot_and_backup(run_id: str = "batch_15000_20260904_001355"):
    run_dir = os.path.join("내작업폴더/data/raw_filings/batch_runs", run_id)
    if not os.path.exists(run_dir):
        raise FileNotFoundError(f"실행 디렉토리 부재: {run_dir}")

    print("=" * 80)
    print(f"📦 [1단계: 무결성 스냅샷 ZIP 생성] 대상: {run_dir}")
    print("=" * 80)

    backup_local_dir = "내작업폴더/data/raw_filings/backups"
    os.makedirs(backup_local_dir, exist_ok=True)

    zip_filename = f"{run_id}_SNAPSHOT.zip"
    zip_path = os.path.join(backup_local_dir, zip_filename)
    sha_path = os.path.join(backup_local_dir, f"{zip_filename}.sha256")
    manifest_path = os.path.join(backup_local_dir, f"{run_id}_SNAPSHOT_manifest.json")

    file_entries = []
    xml_count = 0
    receipt_count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(run_dir):
            for file in sorted(files):
                abs_f = os.path.join(root, file)
                rel_f = os.path.relpath(abs_f, run_dir).replace("\\", "/")
                file_sha = compute_file_sha256(abs_f)
                file_size = os.path.getsize(abs_f)

                if rel_f.startswith("xml/") and rel_f.endswith(".xml"):
                    xml_count += 1
                elif rel_f.startswith("manifests/") and rel_f.endswith(".json"):
                    receipt_count += 1

                file_entries.append({
                    "rel_path": rel_f,
                    "size_bytes": file_size,
                    "sha256": file_sha
                })
                z.write(abs_f, rel_f)

    zip_sha256 = compute_file_sha256(zip_path)
    zip_size = os.path.getsize(zip_path)

    # .sha256 파일 기록
    with open(sha_path, "w", encoding="utf-8") as sf:
        sf.write(f"{zip_sha256} *{zip_filename}\n")

    # 매니페스트 기록
    snapshot_manifest = {
        "snapshot_id": f"{run_id}_SNAPSHOT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": run_id,
        "zip_filename": zip_filename,
        "zip_size_bytes": zip_size,
        "zip_sha256": zip_sha256,
        "total_files_packaged": len(file_entries),
        "xml_files_count": xml_count,
        "receipt_files_count": receipt_count,
        "files": file_entries
    }
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(snapshot_manifest, mf, ensure_ascii=False, indent=2)

    print(f"✔️ ZIP 패키징 완료: {zip_path} ({zip_size / (1024*1024):.2f} MB)")
    print(f"✔️ 포함 파일 수: 총 {len(file_entries):,}개 (XML: {xml_count}개, 영수증: {receipt_count}개)")
    print(f"✔️ ZIP SHA-256: {zip_sha256}")

    # 2단계: 보조 디스크(D:) 복사 및 재검증
    secondary_target_dir = r"D:\DART_Raw_Backup"
    if os.path.exists("D:\\"):
        print("\n" + "=" * 80)
        print(f"💾 [2단계: 보조 물리 디스크(D:) 복사 및 무결성 재검증]")
        print("=" * 80)

        dest_run_dir = os.path.join(secondary_target_dir, run_id)
        os.makedirs(dest_run_dir, exist_ok=True)

        dest_zip = os.path.join(dest_run_dir, zip_filename)
        dest_sha = os.path.join(dest_run_dir, f"{zip_filename}.sha256")
        dest_manifest = os.path.join(dest_run_dir, f"{run_id}_SNAPSHOT_manifest.json")

        print(f"• 대상 경로: {dest_run_dir}")
        shutil.copy2(zip_path, dest_zip)
        shutil.copy2(sha_path, dest_sha)
        shutil.copy2(manifest_path, dest_manifest)

        # 3단계: 복사본 SHA-256 재검증
        print("• 대상 위치에서 SHA-256 해시 실측 재검증 중...")
        recomputed_dest_sha = compute_file_sha256(dest_zip)
        print(f"• 복사본 실측 SHA-256: {recomputed_dest_sha}")

        if recomputed_dest_sha != zip_sha256:
            raise ValueError(f"❌ 복사본 해시 불일치! 원본: {zip_sha256}, 복사본: {recomputed_dest_sha}")

        print("  ✔️ 원본과 D: 복사본 해시 100% 일치 확인!")

        # 읽기 전용 속성 부여
        import stat
        for p in [dest_zip, dest_sha, dest_manifest]:
            os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        print("  🔒 복사된 3개 파일에 읽기 전용(Read-Only) 불변 보호 속성 설정 완료")

        print("\n" + "=" * 80)
        print("🎉 [스냅샷 & 2차 물리 디스크(D:) 백업 전 과정 완결]")
        print(f"   • 로컬 스냅샷: {zip_path}")
        print(f"   • 2차 백업: {dest_zip}")
        print(f"   • SHA-256: {zip_sha256}")
        print("=" * 80)
    else:
        print("\n⚠️ D:\\ 드라이브를 찾을 수 없습니다. 로컬 스냅샷만 완료되었습니다.")

    return snapshot_manifest


if __name__ == "__main__":
    target_rid = sys.argv[1] if len(sys.argv) > 1 else "batch_15000_20260904_001355"
    create_snapshot_and_backup(target_rid)
