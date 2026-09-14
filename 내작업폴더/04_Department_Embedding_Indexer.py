# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 학과 임베딩 색인기
================================================================================
- 표준 계열 태그(standard_tag)가 붙어 있고 교육과정 원문(department_intro +
  curriculum_subjects, set_department_curriculum()으로 저장)이 있는 학과만
  대상으로 임베딩을 만든다. 둘 다 없으면 "유사 학과 추천"의 전제(같은 태그
  안에서만 비교)가 성립하지 않으므로 건너뛴다.
- "타이포그래피1"(국민대) vs "Typography(1)"(홍익대)처럼 표기가 달라도 의미가
  비슷하면 벡터 거리가 가까워지는 것이 이 색인의 목적 - Subject 노드로 쪼개
  문자열을 정확히 매칭하는 방식은 표기 불일치 때문에 채택하지 않았다
  (2026-09-14 검토 결론).
- 기본 DRY-RUN(대상 학과 목록만 출력), --commit 시에만 실제 임베딩 호출 + 적재.
================================================================================
"""

import os
import sys
import argparse
from pathlib import Path

from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(REPO_ROOT / ".env")

from services.art_admission_llm import embed_text, EMBEDDING_DIM  # noqa: E402

uri = os.getenv("ART_ADMISSION_NEO4J_URI") or os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("ART_ADMISSION_NEO4J_USER") or os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("ART_ADMISSION_NEO4J_PASSWORD") or os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")


def ensure_vector_index(driver):
    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        s.run(f"""
            CREATE VECTOR INDEX admission_department_embedding IF NOT EXISTS
            FOR (d:Admission_Department) ON (d.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {EMBEDDING_DIM},
                `vector.similarity_function`: 'cosine'
            }}}}
        """)


def fetch_targets(driver, university=None):
    with driver.session(default_access_mode=READ_ACCESS) as s:
        rows = s.run("""
            MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)
            WHERE d.standard_tag IS NOT NULL
              AND d.department_intro IS NOT NULL
              AND d.curriculum_subjects IS NOT NULL
              AND ($university IS NULL OR u.name = $university)
            RETURN u.name AS university, u.campus AS campus, d.name AS department,
                   d.standard_tag AS tag, d.department_intro AS intro,
                   d.curriculum_subjects AS subjects
        """, university=university).data()
    return rows


def build_doc_text(row):
    subjects = row["subjects"] or []
    return f"{row['department']}\n{row['intro']}\n반영 교육과정: {', '.join(subjects)}"


def main():
    parser = argparse.ArgumentParser(description="미술 실기 입시 학과 임베딩 색인기")
    parser.add_argument("--commit", action="store_true", help="실제 임베딩 호출 + Neo4j 적재 (미지정 시 DRY-RUN)")
    parser.add_argument("--university", default=None, help="특정 대학만 재색인 (기본: 전체)")
    args = parser.parse_args()

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        rows = fetch_targets(driver, args.university)
        print(f"임베딩 대상: {len(rows)}개 학과 (standard_tag + 교육과정 원문 둘 다 있는 경우만)")
        for r in rows:
            print(f"  - {r['university']}({r.get('campus') or '-'}) {r['department']} [{r['tag']}]")

        if not args.commit:
            print("\nDRY-RUN 완료 (임베딩 호출/DB 쓰기 0건). --commit 플래그로 재실행 시 실제 색인됩니다.")
            if rows:
                print(f"\n[미리보기: {rows[0]['university']} {rows[0]['department']} 임베딩 입력 텍스트]")
                print(build_doc_text(rows[0])[:300])
            return

        ensure_vector_index(driver)
        for r in rows:
            vec = embed_text(build_doc_text(r))
            with driver.session(default_access_mode=WRITE_ACCESS) as s:
                s.run("""
                    MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department {name: $department})
                    WHERE u.campus = $campus OR ($campus IS NULL AND u.campus IS NULL)
                    SET d.embedding = $embedding
                """, university=r["university"], campus=r.get("campus"),
                     department=r["department"], embedding=vec)
            print(f"[커밋 완료] {r['university']} {r['department']} 임베딩 저장")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
