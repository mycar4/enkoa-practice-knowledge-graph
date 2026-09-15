# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 학과 교육과정 데이터 로더
================================================================================
- pilot_15_universities.json / remaining_40_universities.json 같은 커리큘럼
  수집 산출물(department_curriculum/*.json)을 읽어 Neo4j Admission_Department
  노드에 반영한다. 00_Art_Admission_Graph_Loader.py(전형 원문)와는 완전히
  분리된 별도 경로다 - 메인 로더 재실행이 태그/커리큘럼을 덮어쓰지 않도록
  services/art_admission_service.py의 set_department_curriculum()/
  set_department_tag()를 그대로 쓴다(2026-09-14 태그 설계와 동일한 이유).
- university/campus/department 이름이 Neo4j에 이미 있는 Admission_Department
  노드와 정확히 일치해야 반영된다 - 일치하지 않는 항목은 조용히 건너뛰지 않고
  "불일치"로 보고해서, 오탈자나 학과명 변경을 놓치지 않게 한다.
- curriculum_subjects가 비어있는 항목(아직 수집 안 된 학과)은 건너뛴다 -
  빈 커리큘럼으로 덮어써서 이미 있던 데이터를 지우는 사고를 막기 위함.
- 기본 DRY-RUN(매칭 결과만 출력), --commit 시에만 실제 적재.
================================================================================
"""

import os
import sys
import json
import glob
import argparse
from pathlib import Path

from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(REPO_ROOT / ".env")

from services.art_admission_service import ArtAdmissionService  # noqa: E402

CURRICULUM_DIR = BASE_DIR / "data" / "department_curriculum"

uri = os.getenv("ART_ADMISSION_NEO4J_URI") or os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user_env = os.getenv("ART_ADMISSION_NEO4J_USER") or os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("ART_ADMISSION_NEO4J_PASSWORD") or os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")


def department_exists(driver, university, department, campus):
    with driver.session(default_access_mode=READ_ACCESS) as s:
        row = s.run("""
            MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department {name: $department})
            WHERE $campus IS NULL OR u.campus = $campus
            RETURN d.name AS name
        """, university=university, department=department, campus=campus).data()
    return bool(row)


def existing_tag(driver, university, department, campus):
    with driver.session(default_access_mode=READ_ACCESS) as s:
        row = s.run("""
            MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department {name: $department})
            WHERE $campus IS NULL OR u.campus = $campus
            RETURN d.standard_tag AS tag
        """, university=university, department=department, campus=campus).single()
    return row["tag"] if row else None


def main():
    parser = argparse.ArgumentParser(description="학과 교육과정 데이터 Neo4j 반영기")
    parser.add_argument("file", nargs="?", default=None,
                         help="반영할 커리큘럼 JSON 파일 (기본: data/department_curriculum/*.json 전체)")
    parser.add_argument("--commit", action="store_true", help="실제 적재 (미지정 시 매칭 확인만 하는 DRY-RUN)")
    parser.add_argument("--skip-tag", action="store_true", help="suggested_tag 자동 적용을 건너뛰고 커리큘럼만 반영")
    parser.add_argument("--force-tag", action="store_true",
                         help="이미 태그가 있는 학과도 suggested_tag로 덮어쓴다(기본은 태그가 없는 학과에만 적용 - "
                              "관리자가 수동으로 검토·수정한 태그를 이 로더 재실행이 조용히 되돌리는 사고를 막기 위함)")
    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = sorted(glob.glob(str(CURRICULUM_DIR / "*.json")))

    if not files:
        print(f"반영할 커리큘럼 JSON 파일이 없습니다: {CURRICULUM_DIR}")
        return

    driver = GraphDatabase.driver(uri, auth=(user_env, pwd))
    svc = ArtAdmissionService()
    standard_tags = set(svc.list_standard_department_tags())

    matched, unmatched, skipped_empty = [], [], []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data if isinstance(data, list) else [data]
        for rec in records:
            if not rec.get("curriculum_subjects"):
                skipped_empty.append(rec)
                continue
            if department_exists(driver, rec["university"], rec["department"], rec.get("campus")):
                matched.append(rec)
            else:
                unmatched.append(rec)

    print(f"입력 파일: {len(files)}개 / 커리큘럼 있는 항목: {len(matched) + len(unmatched)}건 "
          f"(빈 항목 {len(skipped_empty)}건은 건너뜀)")
    print(f"  Neo4j 학과와 매칭: {len(matched)}건 / 불일치: {len(unmatched)}건")
    for r in unmatched:
        print(f"    ⚠️ 불일치: {r['university']}({r.get('campus')}) {r['department']}")

    if not args.commit:
        print("\nDRY-RUN 완료 (DB 쓰기 0건). --commit 플래그로 재실행 시 실제 적재됩니다.")
        return

    tagged = 0
    for r in matched:
        svc.set_department_curriculum(
            r["university"], r["department"],
            department_intro=r.get("department_intro") or "",
            curriculum_subjects=r["curriculum_subjects"],
            campus=r.get("campus"),
            source_note=r.get("source_url"),
        )
        if not args.skip_tag:
            tag = r.get("suggested_tag")
            if tag in standard_tags:
                if args.force_tag or not existing_tag(driver, r["university"], r["department"], r.get("campus")):
                    svc.set_department_tag(r["university"], r["department"], tag, campus=r.get("campus"))
                    tagged += 1
    print(f"[커밋 완료] 커리큘럼 {len(matched)}건 반영, 태그 {tagged}건 적용")
    print("다음 단계: python 04_Department_Embedding_Indexer.py --commit 로 임베딩을 갱신하세요.")


if __name__ == "__main__":
    main()
