# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] Neo4j 적재기
================================================================================
- DART-Trace(지배구조)와 완전히 분리된 신규 도메인. 기존 Aura 인스턴스를
  공유하되, 전부 `Admission_` 접두 라벨만 사용해 기존 DART_* 데이터와
  절대 섞이지 않는다.
- Antigravity가 크롤링한 JSON(내작업폴더/data/art_admission/raw/*.json,
  ART_ADMISSION_CRAWL_BRIEF.md의 스키마)을 입력으로 받는다.
- DART-Trace와 동일한 원칙: official_facts(공식 모집요강 원문)와
  estimates(추정치/후기)는 절대 같은 노드/관계에 섞지 않고 완전히 분리된
  관계 타입(REQUIRES_EXAM 등 vs ESTIMATED_CUTOFF/HAS_INTERVIEW_SUMMARY)으로
  적재한다.
- 기본 DRY-RUN, --commit 명시 시에만 실제 적재.
================================================================================
"""

import os
import sys
import json
import glob
import argparse
from pathlib import Path
from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env")

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

RAW_DIR = BASE_DIR / "data" / "art_admission" / "raw"


def validate_record(rec: dict, filename: str) -> list:
    """필수 필드 존재 여부만 최소 검증 (값의 진위는 검수 담당이 별도 확인)."""
    errors = []
    for field in ["university", "department", "track_name", "official_facts"]:
        if field not in rec:
            errors.append(f"{filename}: 필수 필드 '{field}' 누락")
    of = rec.get("official_facts", {})
    if "source_url" not in of or not of.get("source_url"):
        errors.append(f"{filename}: official_facts.source_url 누락 (출처 없는 데이터는 적재 거부)")
    if not of.get("admission_year"):
        errors.append(
            f"{filename}: official_facts.admission_year 누락 - 몇 학년도 모집요강인지 명시 필수 "
            f"(서로 다른 학년도 문서를 섞어 비교하는 사고를 막기 위한 필수값)"
        )
    return errors


def load_one_record_tx(tx, rec: dict):
    university = rec["university"]
    campus = rec.get("campus", "")
    department = rec["department"]
    track_name = rec["track_name"]
    of = rec["official_facts"]
    est = rec.get("estimates", {})

    tx.run("""
        MERGE (u:Admission_University {name: $university, campus: $campus})
        MERGE (d:Admission_Department {name: $department, university: $university})
        MERGE (u)-[:HAS_DEPARTMENT]->(d)
        MERGE (t:Admission_Track {name: $track_name, university: $university, department: $department})
        MERGE (d)-[:HAS_TRACK]->(t)
        SET t.quota = $quota,
            t.ratio = $ratio,
            t.is_staged = $is_staged,
            t.source_url = $source_url,
            t.source_page = $source_page,
            t.admission_year = $admission_year

        MERGE (e:Admission_ExamType {name: $exam_type_name, track_name: $track_name, university: $university})
        MERGE (t)-[:REQUIRES_EXAM]->(e)
        SET e.allowed_materials = $allowed_materials,
            e.paper_size = $paper_size,
            e.time_limit_minutes = $time_limit_minutes

        MERGE (s:Admission_Schedule {track_name: $track_name, university: $university})
        MERGE (t)-[:HAS_SCHEDULE]->(s)
        SET s.application_start = $app_start,
            s.application_end = $app_end,
            s.exam_date = $exam_date,
            s.result_date = $result_date
    """, university=university, campus=campus, department=department, track_name=track_name,
         quota=of.get("quota"), ratio=of.get("ratio"), is_staged=of.get("is_staged"),
         source_url=of.get("source_url"), source_page=of.get("source_page"),
         admission_year=of.get("admission_year"),
         exam_type_name=of.get("exam_type_name", "미지정"),
         allowed_materials=of.get("allowed_materials", []),
         paper_size=of.get("paper_size"), time_limit_minutes=of.get("time_limit_minutes"),
         app_start=(of.get("application_period") or {}).get("start"),
         app_end=(of.get("application_period") or {}).get("end"),
         exam_date=of.get("exam_date"), result_date=of.get("result_date"))

    for topic in of.get("past_topics", []) or []:
        tx.run("""
            MATCH (e:Admission_ExamType {name: $exam_type_name, track_name: $track_name, university: $university})
            MERGE (p:Admission_PastTopic {university: $university, track_name: $track_name, year: $year, topic_text: $topic_text})
            MERGE (e)-[:HAD_PAST_TOPIC]->(p)
            SET p.source = $source, p.source_url = $source_url
        """, university=university, track_name=track_name, exam_type_name=of.get("exam_type_name", "미지정"),
             year=topic.get("year"), topic_text=topic.get("topic_text"),
             source=topic.get("source"), source_url=topic.get("source_url"))

    # 추정치/후기 - official_facts와 완전히 분리된 관계 타입으로만 연결 (Zero-Mixing)
    if est.get("cutoff_grade_estimate") is not None:
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university})
            MERGE (c:Admission_CutoffEstimate {track_name: $track_name, university: $university})
            MERGE (t)-[:ESTIMATED_CUTOFF]->(c)
            SET c.cutoff_grade_estimate = $cutoff, c.source_url = $source_url, c.data_tier = 'ESTIMATE_NOT_OFFICIAL'
        """, university=university, track_name=track_name,
             cutoff=est.get("cutoff_grade_estimate"), source_url=est.get("cutoff_source_url"))

    for interview in est.get("interview_summaries", []) or []:
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university})
            MERGE (i:Admission_InterviewSummary {university: $university, track_name: $track_name, url: $url})
            MERGE (t)-[:HAS_INTERVIEW_SUMMARY]->(i)
            SET i.title = $title, i.channel = $channel, i.summary = $summary, i.data_tier = 'ESTIMATE_NOT_OFFICIAL'
        """, university=university, track_name=track_name,
             url=interview.get("url"), title=interview.get("title"),
             channel=interview.get("channel"), summary=interview.get("summary"))


def main():
    parser = argparse.ArgumentParser(description="미술 실기 입시 데이터 Neo4j 적재기")
    parser.add_argument("--commit", action="store_true", help="실제 적재 (미지정 시 검증만 하는 DRY-RUN)")
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"입력 폴더가 없습니다: {RAW_DIR}")
        return

    files = sorted(glob.glob(str(RAW_DIR / "*.json")))
    if not files:
        print(f"적재할 JSON 파일이 없습니다: {RAW_DIR}")
        return

    all_errors = []
    records = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        recs = data if isinstance(data, list) else [data]
        for rec in recs:
            errs = validate_record(rec, os.path.basename(fp))
            all_errors.extend(errs)
            if not errs:
                records.append(rec)

    print(f"입력 파일: {len(files)}개 / 레코드: {len(records) + len(all_errors)}건 / 검증통과: {len(records)}건 / 거부: {len(all_errors)}건")
    for e in all_errors:
        print(f"  ⚠️ {e}")

    if not args.commit:
        print("\nDRY-RUN 완료 (DB 쓰기 0건). --commit 플래그로 재실행 시 실제 적재됩니다.")
        return

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(default_access_mode=WRITE_ACCESS) as session:
            for rec in records:
                session.execute_write(load_one_record_tx, rec)
        with driver.session(default_access_mode=READ_ACCESS) as session:
            u_cnt = session.run("MATCH (n:Admission_University) RETURN count(n) AS c").single()["c"]
            t_cnt = session.run("MATCH (n:Admission_Track) RETURN count(n) AS c").single()["c"]
        print(f"[커밋 완료] Admission_University={u_cnt}, Admission_Track={t_cnt}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
