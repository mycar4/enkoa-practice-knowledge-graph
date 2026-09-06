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
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# 사용자가 흔히 쓰는 약칭 -> 실제 university 노드명. 여기 없는 학교는 정식명으로만 인식된다.
_UNIVERSITY_ALIASES = {
    "한예종": "한국예술종합학교",
    "중앙대": "중앙대학교",
    "가천대": "가천대학교",
}


def _resolve_university_mentions(query: str, universities: List[str]) -> List[str]:
    """질의문 안에서 언급된 university 정식명 목록을 찾는다 (정식명 부분일치 + 약칭 테이블)."""
    found = []
    for full_name in universities:
        if full_name in query:
            found.append(full_name)
    for alias, full_name in _UNIVERSITY_ALIASES.items():
        if alias in query and full_name in universities and full_name not in found:
            found.append(full_name)
    return found


def _extract_dates(text: Optional[str]) -> List[str]:
    """자유텍스트 일정 필드(예: '1단계: 2025-09-27, 2단계: 2025-11-01')에서
    실제 ISO 날짜만 정규식으로 뽑아낸다 - 지어내지 않고 원문에 박힌 날짜 그대로."""
    if not text:
        return []
    return sorted(set(_DATE_RE.findall(text)))

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
                       t.admission_year AS admission_year,
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

    def list_all_tracks_full(self) -> List[Dict[str, Any]]:
        """전형 비교/충돌감지/호환매칭의 공통 원천 데이터. 전부 official_facts에서만 가져온다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                OPTIONAL MATCH (t)-[:HAS_SCHEDULE]->(sch:Admission_Schedule)
                RETURN u.name AS university, d.name AS department, t.name AS track_name,
                       t.quota AS quota, t.ratio AS ratio, t.source_url AS source_url,
                       t.admission_year AS admission_year,
                       e.name AS exam_type_name, e.allowed_materials AS allowed_materials,
                       e.paper_size AS paper_size, e.time_limit_minutes AS time_limit_minutes,
                       sch.application_start AS application_start, sch.application_end AS application_end,
                       sch.exam_date AS exam_date_raw, sch.result_date AS result_date
            """).data()
        for r in rows:
            r["exam_dates"] = _extract_dates(r.get("exam_date_raw"))
        return rows

    def detect_schedule_conflicts(self) -> List[Dict[str, Any]]:
        """실기고사일이 겹치는 전형 쌍을 전부 찾는다. 날짜는 exam_date 원문에서
        정규식으로 뽑은 것만 쓰고, 추정으로 보정하지 않는다.
        admission_year가 다른 전형끼리는 애초에 비교 대상이 아니다(서로 다른
        입시 연도를 겹침으로 오판하는 사고를 구조적으로 차단)."""
        tracks = self.list_all_tracks_full()
        conflicts = []
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                a, b = tracks[i], tracks[j]
                if a["university"] == b["university"]:
                    continue
                if a.get("admission_year") != b.get("admission_year"):
                    continue
                shared = sorted(set(a["exam_dates"]) & set(b["exam_dates"]))
                if shared:
                    conflicts.append({
                        "date": shared,
                        "admission_year": a.get("admission_year"),
                        "school_a": {"university": a["university"], "department": a["department"],
                                     "track_name": a["track_name"], "source_url": a["source_url"]},
                        "school_b": {"university": b["university"], "department": b["department"],
                                     "track_name": b["track_name"], "source_url": b["source_url"]},
                    })
        return conflicts

    def find_compatible_tracks(self, university: str, department: str) -> List[Dict[str, Any]]:
        """기준 전형과 실기 유형(키워드)·허용재료가 겹치는 다른 학교 전형을 찾는다.
        키워드 매칭은 exam_type_name에 포함된 단어 교집합만 본다 - 유사도 추정 없음."""
        tracks = self.list_all_tracks_full()
        base = next((t for t in tracks if t["university"] == university and t["department"] == department), None)
        if not base or not base.get("exam_type_name"):
            return []

        base_keywords = set(re.findall(r"[가-힣]{2,}", base["exam_type_name"]))
        base_materials = set(base.get("allowed_materials") or [])

        results = []
        for t in tracks:
            if t["university"] == university:
                continue
            if not t.get("exam_type_name"):
                continue
            kw = set(re.findall(r"[가-힣]{2,}", t["exam_type_name"]))
            shared_kw = base_keywords & kw
            shared_materials = base_materials & set(t.get("allowed_materials") or [])
            if shared_kw or shared_materials:
                results.append({
                    "university": t["university"], "department": t["department"], "track_name": t["track_name"],
                    "admission_year": t.get("admission_year"),
                    "exam_type_name": t["exam_type_name"], "shared_keywords": sorted(shared_kw),
                    "shared_materials": sorted(shared_materials), "source_url": t["source_url"],
                })
        return results

    def answer_question(self, query: str) -> Dict[str, Any]:
        """규칙기반 질의응답 - LLM 없이 그래프 사실만으로 답한다(할루시네이션 원천 차단).
        DART-Trace의 evidence-chat과 동일한 설계: 의도를 키워드로 분류 후 정확한
        Cypher 결과만 돌려주고, 답변에 근거(source_url)를 항상 포함한다."""
        q = query.strip()
        tracks = self.list_all_tracks_full()
        universities = sorted({t["university"] for t in tracks})
        mentioned = _resolve_university_mentions(q, universities)

        # "일정"/"비교"/"스케줄" 등은 특정 학교를 콕 집지 않은 일반 질의일 때만 일정 의도로 본다
        # (학교명이 있으면 SCHOOL_FACT가 우선이어야 하므로 mentioned 여부로 분기)
        is_conflict_intent = any(k in q for k in ["충돌", "겹치", "동시", "겹침"])
        is_schedule_list_intent = (not mentioned) and any(k in q for k in ["일정", "스케줄", "날짜"])
        is_compat_intent = any(k in q for k in ["호환", "비슷", "추천"])

        # 의도 1: 일정 충돌/전체비교 질의 (학교명 언급 여부와 무관하게 최우선 처리)
        if is_conflict_intent or is_schedule_list_intent:
            conflicts = self.detect_schedule_conflicts()
            lines = [f"- [{t.get('admission_year') or '학년도 미상'}] {t['university']} {t['department']}: {', '.join(t['exam_dates']) or '일정 정보 없음'}" for t in tracks]
            answer = "적재된 전형별 실기고사일 (학년도 다르면 서로 비교 대상 아님):\n" + "\n".join(lines)
            if conflicts:
                clines = [
                    f"- {c['date']}: {c['school_a']['university']} {c['school_a']['department']} ↔ "
                    f"{c['school_b']['university']} {c['school_b']['department']}"
                    for c in conflicts
                ]
                answer += "\n\n⚠️ 겹치는 날짜:\n" + "\n".join(clines)
            else:
                answer += "\n\n현재 겹치는 날짜는 없습니다."
            return {"intent": "SCHEDULE_CONFLICT", "answer": answer, "source_url": None}

        # 의도 2: 호환/추천 질의 (학교명이 언급되어야 기준을 잡을 수 있음)
        if is_compat_intent:
            if not mentioned:
                return {"intent": "COMPATIBILITY", "answer": "어느 학교를 기준으로 비교할지 학교명을 함께 말씀해주세요.", "source_url": None}
            university = mentioned[0]
            track = next((t for t in tracks if t["university"] == university), None)
            matches = self.find_compatible_tracks(university, track["department"])
            if not matches:
                return {"intent": "COMPATIBILITY", "answer": f"{university} {track['department']}과 실기유형/재료가 겹치는 다른 전형을 찾지 못했습니다 (적재된 데이터 범위 내).", "source_url": None}
            lines = [f"- {m['university']} {m['department']}: 공통 키워드 {m['shared_keywords']}, 공통 재료 {m['shared_materials']}" for m in matches]
            return {"intent": "COMPATIBILITY", "answer": "\n".join(lines), "source_url": None}

        # 의도 3: 학교/학과 특정 언급 - 상세 사실 그대로 반환 (다른 의도 키워드가 없을 때만)
        if mentioned:
            t = next(t for t in tracks if t["university"] == mentioned[0])
            return {
                "intent": "SCHOOL_FACT",
                "answer": (
                    f"[{t['university']} {t['department']} - {t['track_name']}] ({t.get('admission_year') or '학년도 미상'}학년도 공식 사실)\n"
                    f"모집인원: {t.get('quota') or '정보없음'}명 | 반영비율: {t.get('ratio') or '정보없음'}\n"
                    f"실기종목: {t.get('exam_type_name') or '정보없음'} | 규격: {t.get('paper_size') or '정보없음'} | "
                    f"시험시간: {t.get('time_limit_minutes') or '정보없음'}분\n"
                    f"원서접수: {t.get('application_start') or '-'}~{t.get('application_end') or '-'} | "
                    f"실기고사일: {', '.join(t['exam_dates']) or (t.get('exam_date_raw') or '-')} | "
                    f"발표: {t.get('result_date') or '-'}\n"
                    f"출처: {t.get('source_url') or '없음'}"
                ),
                "source_url": t.get("source_url"),
            }

        return {"intent": "UNKNOWN", "answer": "질문을 이해하지 못했습니다. 학교명을 포함하거나 '일정 충돌', '호환' 같은 키워드를 사용해보세요.", "source_url": None}
