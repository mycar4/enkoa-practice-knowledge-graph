# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 조회 서비스 (100% 읽기 전용)
================================================================================
- Admission_* 라벨만 조회한다. DART_* 데이터와는 절대 섞이지 않는다.
- 공식 사실(전형/일정/실기규정/기출주제)과 추정치(컷라인/후기)는 반환 시에도
  항상 별도 키로 분리해서 내려준다 - 화면에서 절대 같은 카드에 섞어 그리지 말 것.
================================================================================
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")


class ArtAdmissionService:
    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        if self.driver:
            self.driver.close()

    def list_universities(self) -> List[Dict[str, Any]]:
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            return s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)
                RETURN u.name AS university, u.campus AS campus, collect(DISTINCT d.name) AS departments
                ORDER BY university
            """).data()

    def get_university_detail(self, university: str) -> Dict[str, Any]:
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            tracks = s.run("""
                MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                OPTIONAL MATCH (e)-[:HAD_PAST_TOPIC]->(p:Admission_PastTopic)
                OPTIONAL MATCH (t)-[:HAS_SCHEDULE]->(sch:Admission_Schedule)
                WITH d, t, e, sch, collect(DISTINCT {year: p.year, topic_text: p.topic_text, source: p.source, source_url: p.source_url}) AS past_topics
                RETURN d.name AS department, t.name AS track_name, t.quota AS quota, t.ratio AS ratio,
                       t.is_staged AS is_staged, t.source_url AS source_url, t.source_page AS source_page,
                       e.name AS exam_type_name, e.allowed_materials AS allowed_materials,
                       e.paper_size AS paper_size, e.time_limit_minutes AS time_limit_minutes,
                       sch.application_start AS application_start, sch.application_end AS application_end,
                       sch.exam_date AS exam_date, sch.result_date AS result_date,
                       past_topics
            """, university=university).data()

            estimates = s.run("""
                MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                OPTIONAL MATCH (t)-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                OPTIONAL MATCH (t)-[:HAS_INTERVIEW_SUMMARY]->(iv:Admission_InterviewSummary)
                WITH t, c, collect(DISTINCT {title: iv.title, url: iv.url, channel: iv.channel, summary: iv.summary}) AS interviews
                RETURN t.name AS track_name, c.cutoff_grade_estimate AS cutoff_grade_estimate,
                       c.source_url AS cutoff_source_url, interviews
            """, university=university).data()

        return {"official_tracks": tracks, "estimates_by_track": estimates}

    def compare_tracks(self, track_keys: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """track_keys: [{"university": ..., "track_name": ...}, ...] 여러 학교 전형을 나란히 비교."""
        results = []
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            for key in track_keys:
                row = s.run("""
                    MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track {name: $track_name})
                    OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                    OPTIONAL MATCH (t)-[:HAS_SCHEDULE]->(sch:Admission_Schedule)
                    RETURN u.name AS university, t.name AS track_name, t.ratio AS ratio,
                           e.name AS exam_type_name, e.allowed_materials AS allowed_materials,
                           e.paper_size AS paper_size, e.time_limit_minutes AS time_limit_minutes,
                           sch.exam_date AS exam_date, sch.result_date AS result_date
                """, university=key["university"], track_name=key["track_name"]).data()
                results.extend(row)
        return results
