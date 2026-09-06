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
import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

# 학교 자체 공식 도메인(신뢰도 상) 목록 - 여기 없는 나머지(주로 CDN 미러)는
# "제3자 미러"로 분류한다. 오늘(2026-09-07) 사고: CDN 미러는 최신 연도가
# 없을 수 있어 학년도 확인을 대학 자체 사이트로 다시 해야 했음.
_OFFICIAL_DOMAINS = {
    "karts.ac.kr": "한국예술종합학교",
    "admission.cau.ac.kr": "중앙대학교",
    "admission.gachon.ac.kr": "가천대학교",
}


def _classify_source(url: Optional[str]) -> str:
    if not url:
        return "출처 없음"
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "판정 불가"
    for domain in _OFFICIAL_DOMAINS:
        if domain in host:
            return "🟢 대학 자체 공식 사이트"
    if "negagea.net" in host:
        return "🟡 제3자 CDN 미러 (최신 연도 누락 위험 - 학년도 재확인 필수)"
    return "⚪ 기타 출처"


def _days_until(date_str: Optional[str]) -> Optional[int]:
    """오늘(시스템 실제 날짜) 기준 D-day. 과거면 음수(마감 지남)."""
    if not date_str:
        return None
    m = _DATE_RE.search(date_str)
    if not m:
        return None
    try:
        target = datetime.date.fromisoformat(m.group(0))
    except ValueError:
        return None
    return (target - datetime.date.today()).days

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# 사용자가 흔히 쓰는 약칭 -> 실제 university 노드명. 여기 없는 학교는 정식명으로만 인식된다.
_UNIVERSITY_ALIASES = {
    "한예종": "한국예술종합학교",
    "중앙대": "중앙대학교",
    "가천대": "가천대학교",
    "서경대": "서경대학교",
    "용인대": "용인대학교",
    "계원예대": "계원예술대학교",
    "계원": "계원예술대학교",
    "추계예대": "추계예술대학교",
    "추계": "추계예술대학교",
    "홍대": "홍익대학교",
    "홍익대": "홍익대학교",
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
        """대학명이 같아도 캠퍼스가 다르면(예: 홍익대 서울/세종) 별개 University 노드로
        적재되어 있으므로, 여기서 각 행마다 화면 표시용 display_name을 만들어준다 -
        같은 이름이 2개 이상이면 자동으로 '대학명 (캠퍼스캠퍼스)'로 구분한다.
        새 학교가 여러 캠퍼스로 추가돼도 코드 수정 없이 자동으로 같은 방식으로 처리된다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE t.is_superseded IS NULL OR t.is_superseded = false
                RETURN u.name AS university, u.campus AS campus, collect(DISTINCT d.name) AS departments
                ORDER BY university, campus
            """).data()

        name_counts: Dict[str, int] = {}
        for r in rows:
            name_counts[r["university"]] = name_counts.get(r["university"], 0) + 1
        for r in rows:
            if name_counts[r["university"]] > 1 and r.get("campus"):
                r["display_name"] = f"{r['university']} ({r['campus']}캠퍼스)"
            else:
                r["display_name"] = r["university"]
        return rows

    def get_university_detail(self, university: str, campus: Optional[str] = None) -> Dict[str, Any]:
        """campus를 주면 같은 이름의 다른 캠퍼스 데이터가 섞이지 않도록 그 캠퍼스로만
        걸러서 조회한다 (예: 홍익대 서울 선택 시 세종 데이터가 같이 나오지 않게)."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            tracks = s.run("""
                MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($campus IS NULL OR u.campus = $campus)
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
                       sch.registration_start AS registration_start, sch.registration_end AS registration_end,
                       past_topics
            """, university=university, campus=campus).data()

            estimates = s.run("""
                MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($campus IS NULL OR u.campus = $campus)
                OPTIONAL MATCH (t)-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                OPTIONAL MATCH (t)-[:HAS_INTERVIEW_SUMMARY]->(iv:Admission_InterviewSummary)
                WITH t, c, collect(DISTINCT {title: iv.title, url: iv.url, channel: iv.channel, summary: iv.summary}) AS interviews
                RETURN t.name AS track_name, c.cutoff_grade_estimate AS cutoff_grade_estimate,
                       c.source_url AS cutoff_source_url, interviews
            """, university=university, campus=campus).data()

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
                WHERE t.is_superseded IS NULL OR t.is_superseded = false
                OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                OPTIONAL MATCH (t)-[:HAS_SCHEDULE]->(sch:Admission_Schedule)
                RETURN u.name AS university, u.campus AS campus, d.name AS department, t.name AS track_name,
                       t.quota AS quota, t.ratio AS ratio, t.source_url AS source_url,
                       t.admission_year AS admission_year,
                       e.name AS exam_type_name, e.allowed_materials AS allowed_materials,
                       e.paper_size AS paper_size, e.time_limit_minutes AS time_limit_minutes,
                       sch.application_start AS application_start, sch.application_end AS application_end,
                       sch.exam_date AS exam_date_raw, sch.result_date AS result_date,
                       sch.registration_start AS registration_start, sch.registration_end AS registration_end
            """).data()
        for r in rows:
            r["exam_dates"] = _extract_dates(r.get("exam_date_raw"))
            r["source_tier"] = _classify_source(r.get("source_url"))
            r["application_end_dday"] = _days_until(r.get("application_end"))
            r["exam_date_dday"] = _days_until(r.get("exam_date_raw"))
        return rows

    def check_data_integrity(self) -> List[Dict[str, Any]]:
        """오늘(2026-09-07) 겪은 '학년도 뒤섞임' 사고의 재발을 사람이 아니라
        시스템이 자동으로 잡아내게 하는 자가진단. 전부 official_facts 필드만
        기계적으로 검사하며, 추정하지 않는다."""
        tracks = self.list_all_tracks_full()
        issues = []

        year_counts: Dict[Any, int] = {}
        for t in tracks:
            year_counts[t.get("admission_year")] = year_counts.get(t.get("admission_year"), 0) + 1
        majority_year = max(year_counts, key=year_counts.get) if year_counts else None

        for t in tracks:
            label = f"{t['university']} {t['department']}"
            if not t.get("admission_year"):
                issues.append({"level": "CRITICAL", "track": label, "issue": "admission_year 누락"})
            elif len(year_counts) > 1 and t.get("admission_year") != majority_year:
                issues.append({
                    "level": "WARNING", "track": label,
                    "issue": f"다수({majority_year}학년도)와 다른 학년도({t.get('admission_year')}) - 최신 회차인지 재확인 필요",
                })
            if not t.get("source_url"):
                issues.append({"level": "CRITICAL", "track": label, "issue": "source_url 누락"})

            # 원서접수만 지난 건 정상(실기고사가 아직 안 끝났으면 진행 중인 회차).
            # 전체 일정(원서접수·실기고사·발표)이 '전부' 과거면 그때만 완전히
            # 끝난 회차로 판단한다 - 그래야 오늘 같은 오탐(false positive)이 안 남.
            all_dates = list(t.get("exam_dates") or [])
            if t.get("result_date"):
                all_dates += _extract_dates(t["result_date"])
            all_ddays = [d for d in (_days_until(x) for x in all_dates) if d is not None]
            if t.get("application_end_dday") is not None and t["application_end_dday"] < 0:
                if all_ddays and max(all_ddays) < 0:
                    issues.append({
                        "level": "CRITICAL", "track": label,
                        "issue": f"원서접수·실기고사·발표일이 전부 지남(최신 실기고사일 기준 {abs(max(all_ddays))}일 전) - 완전히 끝난 회차 데이터일 가능성, 최신 요강 재확인 필요",
                    })
                elif not all_ddays:
                    issues.append({
                        "level": "WARNING", "track": label,
                        "issue": "원서접수는 마감됐는데 실기고사일을 확인할 수 없음 - exam_date 필드 점검 필요",
                    })
                else:
                    issues.append({
                        "level": "INFO", "track": label,
                        "issue": "원서접수 기간 종료 (실기고사는 아직 진행 전 - 정상적인 현재 회차)",
                    })
            if "negagea.net" in (t.get("source_url") or ""):
                issues.append({
                    "level": "INFO", "track": label,
                    "issue": "제3자 CDN 미러 출처 - 최신 학년도 여부를 대학 자체 사이트에서 한 번 더 확인 권장",
                })

        return issues

    def simulate_multi_apply(self, selections: List[Dict[str, str]]) -> Dict[str, Any]:
        """selections: [{"university":..., "department":...}, ...] (최대 6개, 수시 6장 제한).
        선택한 조합 안에서만 일정 충돌을 검사한다."""
        tracks = self.list_all_tracks_full()
        chosen = []
        for sel in selections:
            t = next((t for t in tracks if t["university"] == sel["university"] and t["department"] == sel["department"]), None)
            if t:
                chosen.append(t)

        conflicts = []
        for i in range(len(chosen)):
            for j in range(i + 1, len(chosen)):
                a, b = chosen[i], chosen[j]
                if a.get("admission_year") != b.get("admission_year"):
                    continue
                shared = sorted(set(a["exam_dates"]) & set(b["exam_dates"]))
                if shared:
                    conflicts.append({"date": shared, "a": f"{a['university']} {a['department']}", "b": f"{b['university']} {b['department']}"})

        return {
            "count": len(chosen),
            "over_limit": len(selections) > 6,
            "conflicts": conflicts,
            "verdict": "지원 가능 (일정 충돌 없음)" if not conflicts and len(selections) <= 6 else
                       ("6개교 초과 - 수시는 최대 6장까지만 지원 가능합니다" if len(selections) > 6 else "일정 충돌 있음 - 아래 목록 확인"),
        }

    def get_past_topics(self, university: Optional[str] = None) -> List[Dict[str, Any]]:
        """기출문제 원문(Admission_PastTopic)을 그대로 반환. 전부 공식 출처 링크 포함."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            query = """
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                          -[:REQUIRES_EXAM]->(e:Admission_ExamType)-[:HAD_PAST_TOPIC]->(p:Admission_PastTopic)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($university IS NULL OR u.name = $university)
                RETURN u.name AS university, d.name AS department, t.name AS track_name,
                       e.name AS exam_type_name, p.year AS year, p.topic_text AS topic_text,
                       p.source AS source, p.source_url AS source_url
                ORDER BY university, year DESC
            """
            return s.run(query, university=university).data()

    def get_comparison_table(self, selections: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """selections: [{"university":..., "department":...}, ...]
        전형 나란히 비교표용 원천 데이터. 전부 official_facts 그대로, 가공/추정 없음."""
        tracks = self.list_all_tracks_full()
        results = []
        for sel in selections:
            t = next((t for t in tracks if t["university"] == sel["university"] and t["department"] == sel["department"]), None)
            if t:
                results.append(t)
        return results

    def get_graph_view(self, university: Optional[str] = None, campus: Optional[str] = None) -> Dict[str, Any]:
        """지식그래프 구조를 노드/엣지 목록으로 반환한다 (시각화 전용, 화면 표시용 가공 없이
        그래프 형태 그대로). 공식 사실 계열(University->Department->Track->ExamType->PastTopic)과
        추정치 계열(Track->CutoffEstimate/InterviewSummary)을 색으로 분리해서 Zero-Mixing을
        그래프에서도 시각적으로 지킨다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($university IS NULL OR u.name = $university)
                  AND ($campus IS NULL OR u.campus = $campus)
                OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                OPTIONAL MATCH (e)-[:HAD_PAST_TOPIC]->(p:Admission_PastTopic)
                OPTIONAL MATCH (t)-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                RETURN u.name AS university, u.campus AS campus, d.name AS department,
                       t.name AS track_name, t.admission_year AS admission_year,
                       e.name AS exam_type_name,
                       collect(DISTINCT p.topic_text) AS past_topics,
                       c.cutoff_grade_estimate AS cutoff_grade_estimate
            """, university=university, campus=campus).data()

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, str]] = []

        def add_node(node_id: str, label: str, kind: str, title: str = ""):
            if node_id not in nodes:
                nodes[node_id] = {"id": node_id, "label": label, "kind": kind, "title": title or label}

        def add_edge(a: str, b: str):
            edges.append({"from": a, "to": b})

        for r in rows:
            u_id = f"U::{r['university']}::{r.get('campus')}"
            d_id = f"D::{r['university']}::{r.get('campus')}::{r['department']}"
            t_id = f"T::{r['university']}::{r['department']}::{r['track_name']}"
            add_node(u_id, r["university"], "university")
            add_node(d_id, r["department"], "department")
            add_node(t_id, f"{r['track_name']} ({r.get('admission_year') or '?'})", "track")
            add_edge(u_id, d_id)
            add_edge(d_id, t_id)

            if r.get("exam_type_name"):
                e_id = f"E::{t_id}::{r['exam_type_name']}"
                topics = [x for x in (r.get("past_topics") or []) if x]
                add_node(e_id, r["exam_type_name"], "exam_type", title="\n".join(topics[:3]) or r["exam_type_name"])
                add_edge(t_id, e_id)
                if topics:
                    p_id = f"P::{e_id}"
                    add_node(p_id, f"기출 {len(topics)}건", "past_topic", title="\n".join(topics))
                    add_edge(e_id, p_id)

            if r.get("cutoff_grade_estimate") is not None:
                c_id = f"C::{t_id}"
                add_node(c_id, f"추정컷 {r['cutoff_grade_estimate']}등급", "estimate")
                add_edge(t_id, c_id)

        return {"nodes": list(nodes.values()), "edges": edges}

    def get_calendar_events(self) -> List[Dict[str, Any]]:
        """전체 전형의 원서접수 기간·실기고사일·발표일을 타임라인 이벤트로 변환.
        exam_date는 여러 날짜가 섞여있을 수 있어 하루짜리 이벤트로 각각 쪼갠다."""
        tracks = self.list_all_tracks_full()

        # 같은 대학명이 캠퍼스별로 여러 개면(예: 홍익대 서울/세종) 캘린더 태그에도
        # 캠퍼스를 붙여 구분한다 - 학교 목록 display_name과 같은 규칙.
        campuses_by_univ: Dict[str, set] = {}
        for t in tracks:
            campuses_by_univ.setdefault(t["university"], set()).add(t.get("campus"))

        events = []
        for t in tracks:
            univ_label = t["university"]
            if len(campuses_by_univ.get(t["university"], set())) > 1 and t.get("campus"):
                univ_label = f"{t['university']}({t['campus']}캠퍼스)"
            label = f"{univ_label} {t['department']}"
            if t.get("application_start") and t.get("application_end"):
                events.append({
                    "school": label, "event_type": "원서접수", "detail": "원서접수 기간",
                    "start": t["application_start"], "end": t["application_end"],
                    "admission_year": t.get("admission_year"),
                })
            for d in t.get("exam_dates") or []:
                events.append({
                    "school": label, "event_type": "실기고사", "detail": "실기고사일",
                    "start": d, "end": d, "admission_year": t.get("admission_year"),
                })
            for d in _extract_dates(t.get("result_date")):
                events.append({
                    "school": label, "event_type": "합격발표", "detail": "합격자 발표",
                    "start": d, "end": d, "admission_year": t.get("admission_year"),
                })
            if t.get("registration_start") and t.get("registration_end"):
                events.append({
                    "school": label, "event_type": "등록", "detail": "등록금 납부 기간",
                    "start": t["registration_start"], "end": t["registration_end"],
                    "admission_year": t.get("admission_year"),
                })
        return events

    def search_by_material(self, keyword: str) -> List[Dict[str, Any]]:
        """허용재료·실기규격에 키워드가 포함된 전형을 찾는다 (완전 텍스트 매칭, 추정 없음)."""
        tracks = self.list_all_tracks_full()
        kw = keyword.strip()
        if not kw:
            return []
        results = []
        for t in tracks:
            materials = t.get("allowed_materials") or []
            if any(kw in m for m in materials) or kw in (t.get("paper_size") or "") or kw in (t.get("exam_type_name") or ""):
                results.append(t)
        return results

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

    def build_llm_context(self, query: str):
        """LLM 그라운딩용 컨텍스트를 만든다. 질의에서 학교명이 인식되면 그 학교의
        모든 학과/트랙만, 인식되지 않으면 적재된 전체 트랙(현재 규모상 소량)을 넘긴다.
        LLM에게는 이 반환값만 사실로 주어지며, 그 밖의 어떤 것도 지어내지 못하게 한다."""
        tracks = self.list_all_tracks_full()
        universities = sorted({t["university"] for t in tracks})
        mentioned = _resolve_university_mentions(query, universities)
        subset = [t for t in tracks if t["university"] in mentioned] if mentioned else tracks

        context_tracks = [{
            "university": t["university"], "department": t["department"], "track_name": t["track_name"],
            "admission_year": t.get("admission_year"), "quota": t.get("quota"), "ratio": t.get("ratio"),
            "exam_type_name": t.get("exam_type_name"), "allowed_materials": t.get("allowed_materials"),
            "paper_size": t.get("paper_size"), "time_limit_minutes": t.get("time_limit_minutes"),
            "application_start": t.get("application_start"), "application_end": t.get("application_end"),
            "exam_dates": t.get("exam_dates"), "result_date": t.get("result_date"),
            "source_url": t.get("source_url"),
        } for t in subset]

        context_estimates = []
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            for t in subset:
                rows = s.run("""
                    MATCH (tr:Admission_Track {name: $tn, university: $u, department: $d})-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                    RETURN c.cutoff_grade_estimate AS cutoff_grade_estimate, c.source_url AS source_url
                """, tn=t["track_name"], u=t["university"], d=t["department"]).data()
                for r in rows:
                    context_estimates.append({"university": t["university"], "department": t["department"], **r})

        return context_tracks, context_estimates

    def vector_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """PDF 원문 청크(Admission_TextChunk)에 대한 순수 벡터 유사도 검색. hybrid_search가
        기본값이지만, 벡터 인덱스만 단독으로 확인하고 싶을 때 쓴다."""
        from services.art_admission_llm import embed_text
        query_vec = embed_text(query)
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                CALL db.index.vector.queryNodes('admission_chunk_embedding', $top_k, $vec)
                YIELD node, score
                RETURN node.university AS university, node.chunk_index AS chunk_index, node.text AS text,
                       node.page_start AS page_start, node.page_end AS page_end,
                       node.admission_year AS admission_year, node.source_file AS source_file,
                       score
                ORDER BY score DESC
            """, top_k=top_k, vec=query_vec).data()
        return rows

    def hybrid_search(self, query: str, top_k: int = 5, candidate_pool: int = 15,
                       rerank_model_id: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
        """벡터 유사도 검색 + 키워드(풀텍스트) 검색을 합쳐서 후보를 늘리고(재현율↑),
        LLM 재순위화로 정말 관련 있는 것만 추려낸다(정확도↑). 벡터 단독은 뜻은 비슷한데
        핵심 고유명사/숫자가 다른 문장을 헷갈릴 수 있고, 키워드 단독은 표현이 다르면
        놓치므로 둘을 합친다."""
        from services.art_admission_llm import embed_text, rerank_chunks
        query_vec = embed_text(query)

        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            vec_rows = s.run("""
                CALL db.index.vector.queryNodes('admission_chunk_embedding', $pool, $vec)
                YIELD node, score
                RETURN node.university AS university, node.chunk_index AS chunk_index, node.text AS text,
                       node.page_start AS page_start, node.page_end AS page_end,
                       node.admission_year AS admission_year, score AS vec_score
            """, pool=candidate_pool, vec=query_vec).data()

            kw_rows = s.run("""
                CALL db.index.fulltext.queryNodes('admission_chunk_fulltext', $q) YIELD node, score
                RETURN node.university AS university, node.chunk_index AS chunk_index, node.text AS text,
                       node.page_start AS page_start, node.page_end AS page_end,
                       node.admission_year AS admission_year, score AS kw_score
                LIMIT $pool
            """, q=query, pool=candidate_pool).data()

        max_vec = max((r["vec_score"] for r in vec_rows), default=1.0) or 1.0
        max_kw = max((r["kw_score"] for r in kw_rows), default=1.0) or 1.0

        merged: Dict[tuple, Dict[str, Any]] = {}
        for r in vec_rows:
            key = (r["university"], r["chunk_index"])
            merged[key] = {**r, "vec_score_norm": r["vec_score"] / max_vec, "kw_score_norm": 0.0}
        for r in kw_rows:
            key = (r["university"], r["chunk_index"])
            if key in merged:
                merged[key]["kw_score_norm"] = r["kw_score"] / max_kw
            else:
                merged[key] = {**r, "vec_score_norm": 0.0, "kw_score_norm": r["kw_score"] / max_kw}

        candidates = list(merged.values())
        for c in candidates:
            c["fusion_score"] = 0.7 * c["vec_score_norm"] + 0.3 * c["kw_score_norm"]
        candidates.sort(key=lambda c: c["fusion_score"], reverse=True)
        candidates = candidates[:candidate_pool]

        try:
            return rerank_chunks(query, candidates, model_id=rerank_model_id, top_k=top_k)
        except Exception:
            return candidates[:top_k]
