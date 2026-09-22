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
import re
import sys
import json
import glob
import argparse
from datetime import datetime, timezone
from pathlib import Path
from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS
from dotenv import load_dotenv

_YEAR_LABEL_RE = re.compile(r"(20\d{2})\s*학년도")
_YEAR_TOKEN_RE = re.compile(r"20\d{2}")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env")

# 2026-09-13: art-admission 전용 Neo4j 인스턴스 - DART-Trace가 쓰는 AURA_*와 분리됨
uri = os.getenv("ART_ADMISSION_NEO4J_URI") or os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("ART_ADMISSION_NEO4J_USER") or os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("ART_ADMISSION_NEO4J_PASSWORD") or os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

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

    admission_year = of.get("admission_year")

    # source_url / document_name 안에 "YYYY학년도"가 박혀 있는데 admission_year와 다르면
    # 무조건 거부한다. 이건 "구 문서의 연도 라벨만 바꿔치기"하는 조작을 잡기 위한 장치다 —
    # 실제 신규 원문을 재수집하지 않고 값만 세탁하면 필연적으로 source_url/파일명에
    # 예전 학년도가 그대로 남기 때문에, 이 불일치 자체가 조작의 물증이 된다.
    candidates = []
    src = of.get("source_url")
    if src:
        candidates.append(("source_url", src))
    for ds in (of.get("data_sources") or []):
        if isinstance(ds, dict) and ds.get("document_name"):
            candidates.append(("data_sources.document_name", ds["document_name"]))

    for field_label, text in candidates:
        for m in _YEAR_LABEL_RE.finditer(text):
            found_year = int(m.group(1))
            if found_year != admission_year:
                errors.append(
                    f"{filename}: official_facts.{field_label}에 '{found_year}학년도'가 명시되어 "
                    f"있는데 admission_year={admission_year}과(와) 불일치 - "
                    f"연도 라벨만 바꿔치기하고 실제 원문은 재수집하지 않은 조작으로 간주하여 적재 거부. "
                    f"반드시 해당 학년도의 진짜 원문 PDF를 재다운로드하여 재추출할 것."
                )

    return errors


def load_one_record_tx(tx, rec: dict, batch_id: str):
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
            t.admission_year = $admission_year,
            t.csat_minimum_required = $csat_minimum_required,
            t.csat_minimum_rule = $csat_minimum_rule,
            t.school_record_ratio_pct = $school_record_ratio_pct,
            t.practical_ratio_pct = $practical_ratio_pct,
            t.document_ratio_pct = $document_ratio_pct,
            t.interview_ratio_pct = $interview_ratio_pct,
            t.school_record_rule_json = $school_record_rule_json,
            t.school_record_status = $school_record_status,
            t.school_record_status_note = $school_record_status_note,
            t.gender_restriction = $gender_restriction,
            t.stage_ratio_label = $stage_ratio_label,
            t.stage_practical_ratio_pct = $stage_practical_ratio_pct,
            t.stage_school_record_ratio_pct = $stage_school_record_ratio_pct,
            t.competition_applicant_count = $competition_applicant_count,
            t.competition_rate = $competition_rate,
            t.competition_rate_announced_at = $competition_rate_announced_at,
            t.competition_rate_source_url = $competition_rate_source_url,
            t.last_loaded_batch_id = $batch_id,
            t.is_superseded = false,
            t.retrieved_at = $retrieved_at,
            t.published_at = $published_at,
            t.valid_from = $valid_from,
            t.valid_to = $valid_to,
            t.verification_status = coalesce($verification_status, t.verification_status, 'unverified')

        MERGE (e:Admission_ExamType {name: $exam_type_name, track_name: $track_name, university: $university, department: $department})
        MERGE (t)-[:REQUIRES_EXAM]->(e)
        SET e.allowed_materials = $allowed_materials,
            e.paper_size = $paper_size,
            e.time_limit_minutes = $time_limit_minutes

        MERGE (s:Admission_Schedule {track_name: $track_name, university: $university, department: $department})
        MERGE (t)-[:HAS_SCHEDULE]->(s)
        SET s.application_start = $app_start,
            s.application_end = $app_end,
            s.exam_date = $exam_date,
            s.result_date = $result_date,
            s.registration_start = $reg_start,
            s.registration_end = $reg_end
    """, university=university, campus=campus, department=department, track_name=track_name,
         quota=of.get("quota"), ratio=of.get("ratio"), is_staged=of.get("is_staged"),
         source_url=of.get("source_url"), source_page=of.get("source_page"),
         admission_year=of.get("admission_year"),
         csat_minimum_required=of.get("csat_minimum_required"),
         csat_minimum_rule=of.get("csat_minimum_rule"),
         school_record_ratio_pct=of.get("school_record_ratio_pct"),
         practical_ratio_pct=of.get("practical_ratio_pct"),
         document_ratio_pct=of.get("document_ratio_pct"),
         interview_ratio_pct=of.get("interview_ratio_pct"),
         school_record_rule_json=(
             json.dumps(of["school_record_rule"], ensure_ascii=False)
             if of.get("school_record_rule") else None
         ),
         school_record_status=of.get("school_record_status"),
         school_record_status_note=of.get("school_record_status_note"),
         gender_restriction=of.get("gender_restriction"),
         stage_ratio_label=of.get("stage_ratio_label"),
         stage_practical_ratio_pct=of.get("stage_practical_ratio_pct"),
         stage_school_record_ratio_pct=of.get("stage_school_record_ratio_pct"),
         competition_applicant_count=of.get("competition_applicant_count"),
         competition_rate=of.get("competition_rate"),
         competition_rate_announced_at=of.get("competition_rate_announced_at"),
         competition_rate_source_url=of.get("competition_rate_source_url"),
         batch_id=batch_id,
         # 2026-09-23 [항목③ 소스 시간·버전 필드]: retrieved_at은 이 레코드가 실제로
         # Neo4j에 적재된 시각을 매 실행마다 갱신해서 자동으로 채운다(항상 신뢰 가능 -
         # 입력 JSON에 의존하지 않음). published_at/valid_from/valid_to/verification_status는
         # 아직 수집 브리프(ART_ADMISSION_CRAWL_BRIEF.md)가 요구하지 않는 선택 필드라
         # 과거 57개교 데이터엔 대부분 없다(null로 적재됨) - 앞으로 수집분부터 채워
         # 넣을 수 있게 배관만 먼저 깔아둔다. 전체 소급 채움은 별도 작업.
         retrieved_at=datetime.now(timezone.utc).isoformat(),
         published_at=of.get("published_at"),
         valid_from=of.get("valid_from"),
         valid_to=of.get("valid_to"),
         verification_status=of.get("verification_status"),
         exam_type_name=of.get("exam_type_name", "미지정"),
         allowed_materials=of.get("allowed_materials", []),
         paper_size=of.get("paper_size"), time_limit_minutes=of.get("time_limit_minutes"),
         app_start=(of.get("application_period") or {}).get("start"),
         app_end=(of.get("application_period") or {}).get("end"),
         exam_date=of.get("exam_date"), result_date=of.get("result_date"),
         reg_start=(of.get("registration_period") or {}).get("start"),
         reg_end=(of.get("registration_period") or {}).get("end"))

    # day37 온톨로지 확장: 단계형 전형(예: 이화 1단계 서류100%→2단계 서류80%+면접20%)을
    # 표현하는 별도 노드. 기존 Track -[:HAS_SCHEDULE]-> Schedule 패턴과 동일하게,
    # Track 안에 flat 필드로 욱여넣지 않고 독립 노드로 분리한다 - 단계 수가 학교마다
    # 다르고(1~2단계), 나중에 단계를 더 세분화해도 Track 스키마 자체는 안 바뀐다.
    for idx, stage in enumerate(of.get("stages", []) or [], start=1):
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university, department: $department})
            MERGE (st:Admission_SelectionStage {track_name: $track_name, university: $university, department: $department, stage_number: $stage_number})
            MERGE (t)-[:HAS_STAGE]->(st)
            SET st.description = $description, st.ratio_desc = $ratio_desc, st.multiplier = $multiplier
        """, university=university, department=department, track_name=track_name,
             stage_number=idx, description=stage.get("description"),
             ratio_desc=stage.get("ratio_desc"), multiplier=stage.get("multiplier"))

    for topic in of.get("past_topics", []) or []:
        tx.run("""
            MATCH (e:Admission_ExamType {name: $exam_type_name, track_name: $track_name, university: $university, department: $department})
            MERGE (p:Admission_PastTopic {university: $university, department: $department, track_name: $track_name, year: $year, topic_text: $topic_text})
            MERGE (e)-[:HAD_PAST_TOPIC]->(p)
            SET p.source = $source, p.source_url = $source_url
        """, university=university, department=department, track_name=track_name, exam_type_name=of.get("exam_type_name", "미지정"),
             year=topic.get("year"), topic_text=topic.get("topic_text"),
             source=topic.get("source"), source_url=topic.get("source_url"))

    # 추정치/후기 - official_facts와 완전히 분리된 관계 타입으로만 연결 (Zero-Mixing)
    if est.get("cutoff_grade_estimate") is not None:
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university, department: $department})
            MERGE (c:Admission_CutoffEstimate {track_name: $track_name, university: $university, department: $department})
            MERGE (t)-[:ESTIMATED_CUTOFF]->(c)
            SET c.cutoff_grade_estimate = $cutoff, c.source_url = $source_url, c.data_tier = 'ESTIMATE_NOT_OFFICIAL'
        """, university=university, department=department, track_name=track_name,
             cutoff=est.get("cutoff_grade_estimate"), source_url=est.get("cutoff_source_url"))

    # 2026-09-14: 전년도 입결을 Track 하위 단일 노드(Admission_CutoffEstimate)의
    # flat 필드로 욱여넣던 구조는 MERGE 키에 연도가 없어서, 다음 학년도 갱신 때
    # 새 연도 값이 이전 연도 값을 그냥 덮어써 버린다 - "최근 3개년 추이" 같은
    # 시계열 조회가 원천적으로 불가능했다. Admission_YearlyResult를 연도까지
    # 포함한 키로 분리해서, 매년 새 노드가 "추가"되게 한다(과거 연도 보존).
    # 지금은 raw JSON에 연도가 1개뿐이라 당장 시계열이 생기진 않지만, 내년
    # 갱신부터는 자동으로 2개년 이상이 쌓인다(스키마를 미리 준비해두는 것).
    pyr = est.get("prior_year_result") or {}
    if pyr and pyr.get("admission_year") is not None:
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university, department: $department})
            MERGE (yr:Admission_YearlyResult {track_name: $track_name, university: $university, department: $department, admission_year: $pyr_year})
            MERGE (t)-[:HAS_YEARLY_RESULT]->(yr)
            SET yr.competition_rate = $pyr_competition_rate,
                yr.grade_typical = $pyr_grade_typical,
                yr.grade_floor = $pyr_grade_floor,
                yr.grade_stat_type = $pyr_grade_stat_type,
                yr.fill_rate_pct = $pyr_fill_rate_pct,
                yr.methodology_note = $pyr_methodology_note,
                yr.source_url = $pyr_source_url,
                yr.source_page = $pyr_source_page,
                yr.data_tier = 'ESTIMATE_NOT_OFFICIAL'
        """, university=university, department=department, track_name=track_name,
             pyr_year=pyr.get("admission_year"),
             pyr_competition_rate=pyr.get("competition_rate"),
             pyr_grade_typical=pyr.get("school_record_grade_typical"),
             pyr_grade_floor=pyr.get("school_record_grade_floor"),
             pyr_grade_stat_type=pyr.get("grade_stat_type"),
             pyr_fill_rate_pct=pyr.get("fill_rate_pct"),
             pyr_methodology_note=pyr.get("methodology_note"),
             pyr_source_url=pyr.get("source_url"),
             pyr_source_page=pyr.get("source_page"))

    for interview in est.get("interview_summaries", []) or []:
        tx.run("""
            MATCH (t:Admission_Track {name: $track_name, university: $university, department: $department})
            MERGE (i:Admission_InterviewSummary {university: $university, department: $department, track_name: $track_name, url: $url})
            MERGE (t)-[:HAS_INTERVIEW_SUMMARY]->(i)
            SET i.title = $title, i.channel = $channel, i.summary = $summary, i.data_tier = 'ESTIMATE_NOT_OFFICIAL'
        """, university=university, department=department, track_name=track_name,
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

    batch_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 2026-09-15: is_superseded 도입 - Admission_Track의 MERGE 키에는 admission_year가
    # 없어서 "같은 전형명"에 새 연도가 들어오면 그냥 덮어써진다(문제 없음). 하지만
    # 학교가 전형명을 바꾸거나 폐지하면 옛 전형명의 Track 노드는 아무도 안 건드려서
    # 옛 연도 값을 단 채로 영원히 남아있고, 조회 API는 지금 유효한 전형인 것처럼
    # 그대로 보여준다. 이번 배치가 대학별로 가장 최신으로 확인한 admission_year보다
    # 낮은 연도를 달고, 이번 배치에서 건드리지도 않은 Track만 골라 is_superseded로
    # 표시해서 조회에서 걸러낼 수 있게 한다(삭제는 하지 않음 - 과거 이력 보존).
    uni_max_year = {}
    for rec in records:
        y = rec["official_facts"].get("admission_year")
        if not y:
            continue
        key = (rec["university"], rec.get("campus"))
        uni_max_year[key] = max(uni_max_year.get(key, 0), y)

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(default_access_mode=WRITE_ACCESS) as session:
            for rec in records:
                session.execute_write(load_one_record_tx, rec, batch_id)
            for (university, campus), max_year in uni_max_year.items():
                session.run("""
                    MATCH (u:Admission_University {name: $university, campus: $campus})
                          -[:HAS_DEPARTMENT]->(:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                    WHERE t.last_loaded_batch_id <> $batch_id AND t.admission_year < $max_year
                    SET t.is_superseded = true
                """, university=university, campus=campus, batch_id=batch_id, max_year=max_year)
        with driver.session(default_access_mode=READ_ACCESS) as session:
            u_cnt = session.run("MATCH (n:Admission_University) RETURN count(n) AS c").single()["c"]
            t_cnt = session.run("MATCH (n:Admission_Track) RETURN count(n) AS c").single()["c"]
            superseded_cnt = session.run("MATCH (n:Admission_Track {is_superseded: true}) RETURN count(n) AS c").single()["c"]
        print(f"[커밋 완료] Admission_University={u_cnt}, Admission_Track={t_cnt} (구버전 is_superseded={superseded_cnt}), batch_id={batch_id}")
        print(f"  이번 배치가 건드린 Track 조회: MATCH (t:Admission_Track {{last_loaded_batch_id: '{batch_id}'}}) RETURN t")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
