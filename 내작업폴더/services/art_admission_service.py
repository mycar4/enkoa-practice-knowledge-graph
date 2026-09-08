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
    "경희대": "경희대학교",
    "동국대": "동국대학교",
    "명지대": "명지대학교",
    "삼육대": "삼육대학교",
    "상명대": "상명대학교",
    "서경대": "서경대학교",
    "용인대": "용인대학교",
    "계원예대": "계원예술대학교",
    "계원": "계원예술대학교",
    "추계예대": "추계예술대학교",
    "추계": "추계예술대학교",
    "홍대": "홍익대학교",
    "홍익대": "홍익대학교",
    "서울과기대": "서울과학기술대학교",
    "서울과학기술대": "서울과학기술대학교",
    "서울예대": "서울예술대학교",
}


def _auto_short_forms(full_name: str) -> List[str]:
    """별칭 표에 없는 학교도 놓치지 않도록, "OO대학교"/"OO대"에서 "학교"/"대학교" 접미사를
    떼서 자동으로 짧은 형태 후보를 만든다(day39 엔티티 해소: 사전에 없다고 바로 포기하지
    않고, 규칙으로 한 번 더 정규화를 시도한 뒤에야 miss 처리한다)."""
    forms = [full_name]
    for suffix in ("대학교", "대학"):
        if full_name.endswith(suffix):
            forms.append(full_name[: -len(suffix)])
    return forms


def resolve_university_mentions_detailed(query: str, universities: List[str]) -> Dict[str, Any]:
    """day39 엔티티 해소 방식 그대로: 질의문에서 학교명을 (miss/exact/ambiguous)로 가른다.
    - exact: 정식명·별칭·자동단축형 중 하나가 유일한 학교에만 걸림
    - ambiguous: 같은 짧은 표현이 서로 다른 학교 여러 곳에 동시에 걸림 (예: 짧은 표현이
      두 학교의 자동단축형과 동시에 겹치는 경우) - 이때는 아무거나 골라잡지 않고 후보를
      전부 보여줘서, 상위 호출자(에이전트/Q&A)가 사용자에게 "어느 학교요?"라고 되물을 수
      있게 한다.
    - miss: 아무 후보도 안 걸림."""
    # 후보 표현 -> 그 표현이 가리킬 수 있는 학교(들) 매핑을 먼저 만든다.
    surface_to_universities: Dict[str, set] = {}
    for full_name in universities:
        for form in _auto_short_forms(full_name):
            surface_to_universities.setdefault(form, set()).add(full_name)
    for alias, full_name in _UNIVERSITY_ALIASES.items():
        if full_name in universities:
            surface_to_universities.setdefault(alias, set()).add(full_name)

    matched: Dict[str, set] = {}
    for surface, cand_universities in surface_to_universities.items():
        if surface and surface in query:
            for u in cand_universities:
                matched.setdefault(u, set()).add(surface)

    exact = sorted(u for u, surfaces in matched.items())
    # 같은 표현이 정말로 여러 학교에 동시에 매칭된 경우만 ambiguous로 별도 표시.
    ambiguous_surfaces = {s: us for s, us in surface_to_universities.items() if s in query and len(us) > 1}

    return {
        "status": "miss" if not exact else ("ambiguous" if ambiguous_surfaces else "exact"),
        "universities": exact,
        "ambiguous_surfaces": {s: sorted(us) for s, us in ambiguous_surfaces.items()},
    }


def _resolve_university_mentions(query: str, universities: List[str]) -> List[str]:
    """질의문 안에서 언급된 university 정식명 목록을 찾는다 (정식명·별칭·자동단축형 부분일치).
    기존 호출부와의 호환을 위해 List[str]만 반환 - 애매함/미스 정보가 필요하면
    resolve_university_mentions_detailed()를 쓴다."""
    return resolve_university_mentions_detailed(query, universities)["universities"]


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
            for t in tracks:
                t["source_tier"] = _classify_source(t.get("source_url"))
                t["exam_dates"] = _extract_dates(t.get("exam_date"))

            estimates = s.run("""
                MATCH (u:Admission_University {name: $university})-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($campus IS NULL OR u.campus = $campus)
                OPTIONAL MATCH (t)-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                OPTIONAL MATCH (t)-[:HAS_INTERVIEW_SUMMARY]->(iv:Admission_InterviewSummary)
                WITH d, t, c, collect(DISTINCT {title: iv.title, url: iv.url, channel: iv.channel, summary: iv.summary}) AS interviews
                RETURN d.name AS department, t.name AS track_name, c.cutoff_grade_estimate AS cutoff_grade_estimate,
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

    @staticmethod
    def _match_selected_track(tracks: List[Dict[str, Any]], sel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """비교/일정/근거 화면이 공유하는 전형 식별 로직. track_name(전형명, 예: "실기우수자전형")은
        같은 대학 안 여러 학과가 그대로 공유하는 카테고리 이름이라 식별자로 쓰면 안 되고 - 실제로
        이 버그 때문에 Evidence 패널이 엉뚱한 학과 근거를 보여준 적이 있다 - university+campus+department
        조합만 이 데이터셋 전체(31건)에서 유일함이 확인됐다. campus는 selections에 없을 수도 있으므로
        (구버전 클라이언트 호환) 넘어온 경우에만 비교한다."""
        for t in tracks:
            if t["university"] != sel.get("university") or t["department"] != sel.get("department"):
                continue
            if sel.get("campus") and t.get("campus") != sel.get("campus"):
                continue
            return t
        return None

    def simulate_multi_apply(self, selections: List[Dict[str, str]]) -> Dict[str, Any]:
        """selections: [{"university":..., "campus":..., "department":...}, ...] (최대 6개, 수시 6장 제한).
        선택한 조합 안에서만 일정 충돌을 검사한다."""
        tracks = self.list_all_tracks_full()
        chosen = []
        for sel in selections:
            t = self._match_selected_track(tracks, sel)
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
        """selections: [{"university":..., "campus":..., "department":...}, ...]
        전형 나란히 비교표용 원천 데이터. 전부 official_facts 그대로, 가공/추정 없음."""
        tracks = self.list_all_tracks_full()
        results = []
        for sel in selections:
            t = self._match_selected_track(tracks, sel)
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

    def get_entity_graph_view(self, min_weight: int = 1) -> Dict[str, Any]:
        """LLM 구조화 추출(원문검증+신뢰도필터 통과분만)로 만든 Admission_Entity +
        CO_OCCURS_WITH 그래프를 pyvis 시각화용 노드/엣지로 변환한다. PageRank/
        Louvain 커뮤니티 + LLM이 붙인 커뮤니티 라벨을 함께 담는다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            node_rows = s.run("""
                MATCH (e:Admission_Entity)
                RETURN e.name AS name, e.type AS type, e.pagerank AS pagerank,
                       e.community AS community, e.community_label AS community_label,
                       e.llm_discovered AS llm_discovered
            """).data()
            edge_rows = s.run("""
                MATCH (a:Admission_Entity)-[r:CO_OCCURS_WITH]-(b:Admission_Entity)
                WHERE a.name < b.name AND r.weight >= $min_weight
                RETURN a.name AS a, b.name AS b, r.weight AS weight
            """, min_weight=min_weight).data()

        nodes = [{
            "id": r["name"], "label": r["name"],
            "kind": f"entity_{r['type']}" if not r.get("llm_discovered") else "entity_llm_new",
            "title": (f"{r['name']} ({r['type']}) pagerank={r.get('pagerank') or 0:.4f} "
                      f"community={r.get('community')} [{r.get('community_label') or ''}]"
                      + (" 🆕 LLM 신규발견" if r.get("llm_discovered") else "")),
        } for r in node_rows]
        edges = [{"from": r["a"], "to": r["b"], "weight": r["weight"]} for r in edge_rows]
        return {"nodes": nodes, "edges": edges}

    def get_architecture_overview(self) -> Dict[str, Any]:
        """'지식그래프가 실제로 뭐고 어떻게 만들어졌는지'를 보여주는 메타 그래프.
        노드/엣지 개수는 전부 지금 이 순간 DB에서 직접 센 실측치다 - 어떤 값도
        하드코딩하지 않는다. 세 계층(구조화 사실 / PDF 원문 청크 / LLM 개체그래프)이
        어느 스크립트로 만들어졌는지까지 엣지 라벨에 명시한다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            counts = s.run("""
                RETURN
                  count { (:Admission_University) } AS university,
                  count { (:Admission_Department) } AS department,
                  count { (t:Admission_Track) WHERE t.is_superseded IS NULL OR t.is_superseded = false } AS track,
                  count { (:Admission_ExamType) } AS exam_type,
                  count { (:Admission_CutoffEstimate) } AS cutoff_estimate,
                  count { (:Admission_PastTopic) } AS past_topic,
                  count { (:Admission_TextChunk) } AS text_chunk,
                  count { (:Admission_Entity) } AS entity,
                  count { (:Admission_Entity {llm_discovered: true}) } AS entity_llm_discovered,
                  count { ()-[:MENTIONS]->() } AS mentions,
                  count { ()-[:CO_OCCURS_WITH]-() } AS cooccurs
            """).single().data()
            community_count = s.run(
                "MATCH (e:Admission_Entity) WHERE e.community IS NOT NULL RETURN count(DISTINCT e.community) AS c"
            ).single()["c"]
        counts["cooccurs"] = counts["cooccurs"] // 2  # 무방향 관계라 MATCH가 양방향으로 2번씩 셈
        counts["community"] = community_count

        nodes = [
            {"id": "university", "label": f"University\n({counts['university']}개)", "kind": "university"},
            {"id": "department", "label": f"Department\n({counts['department']}개)", "kind": "department"},
            {"id": "track", "label": f"Track\n({counts['track']}개, 활성)", "kind": "track"},
            {"id": "exam_type", "label": f"ExamType\n({counts['exam_type']}개)", "kind": "exam_type"},
            {"id": "past_topic", "label": f"PastTopic\n({counts['past_topic']}건)", "kind": "past_topic"},
            {"id": "cutoff", "label": f"CutoffEstimate\n({counts['cutoff_estimate']}건, 추정치)", "kind": "estimate"},
            {"id": "pdf", "label": "PDF 원문", "kind": "entity_material"},
            {"id": "textchunk", "label": f"TextChunk\n({counts['text_chunk']}건, 임베딩)", "kind": "entity_llm_new"},
            {"id": "entity", "label": f"Entity\n({counts['entity']}개, LLM추출 {counts['entity_llm_discovered']}개)", "kind": "entity_llm_new"},
            {"id": "community", "label": f"커뮤니티\n({counts['community']}개, PageRank/Louvain)", "kind": "entity_llm_new"},
        ]
        edges = [
            {"from": "university", "to": "department", "title": "00_Art_Admission_Graph_Loader.py (구조화 추출, LLM 관여 없음)"},
            {"from": "department", "to": "track", "title": "00_Art_Admission_Graph_Loader.py"},
            {"from": "track", "to": "exam_type", "title": "00_Art_Admission_Graph_Loader.py"},
            {"from": "exam_type", "to": "past_topic", "title": "HAD_PAST_TOPIC (원문 그대로 발췌)"},
            {"from": "track", "to": "cutoff", "title": "ESTIMATED_CUTOFF (작년 입시결과 기반 추정치, 공식 아님)"},
            {"from": "pdf", "to": "textchunk", "title": "01_Art_Admission_Vector_Indexer.py (청크화+임베딩, text-embedding-3-small)"},
            {"from": "textchunk", "to": "entity", "title": "MENTIONS - 02_Art_Admission_Entity_Linker.py (LLM 구조화 추출+원문검증+신뢰도필터)"},
            {"from": "entity", "to": "community", "title": "CO_OCCURS_WITH 위 PageRank/Louvain (networkx 로컬 계산) + LLM 커뮤니티 라벨"},
        ]
        return {"nodes": nodes, "edges": edges, "counts": counts}

    def _all_entities(self) -> List[Dict[str, Any]]:
        """Admission_Entity 전체를 이름/타입/커뮤니티/PageRank와 함께 가져온다.
        403건 규모라 매번 전체 조회해도 비용이 작다 - 캐싱은 하지 않는다
        (개체 링커를 재실행하면 바로 최신값을 봐야 하므로)."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            return s.run("""
                MATCH (e:Admission_Entity)
                RETURN e.name AS name, e.type AS type, e.pagerank AS pagerank,
                       e.community AS community, e.community_label AS community_label
            """).data()

    def get_graph_related_context(self, query: str, anchor_names: Optional[List[str]] = None,
                                   exclude_names: Optional[List[str]] = None,
                                   top_n: int = 5) -> List[Dict[str, Any]]:
        """GraphRAG 연동: 질문에 언급된 개체를 찾아 그 개체가 속한 커뮤니티
        (동시출현 기반 자동 군집)에서, PageRank가 높은 다른 학교/학과를 "관련 사례"로
        뽑아온다. 여기 나온 학교에 대한 세부 사실(날짜/점수 등)은 이 함수가 보장하지
        않는다 - 어디까지나 "같이 자주 언급되는 계열"이라는 구조적 힌트일 뿐이므로,
        LLM 프롬프트에서도 반드시 참고용으로만 쓰고 사실 근거로 쓰지 말라고 못박는다.

        anchor_names: build_llm_context 등에서 이미 약칭("중앙대"→"중앙대학교")까지
        해소한 정식 university/department명. 이걸 안 받고 질문 원문 문자열에 개체명이
        그대로 있는지만 보면, 사용자가 약칭을 쓸 때(예: "중앙대") 개체명("중앙대학교")이
        원문에 없어서 매칭이 통째로 실패한다 - 실제로 겪은 버그라 정식명은 anchor_names로
        직접 받고, 질문 원문 부분일치는 보조 수단으로만 쓴다."""
        exclude = set(exclude_names or [])
        anchors = set(anchor_names or [])
        entities = self._all_entities()
        matched = [e for e in entities if e["name"] and (e["name"] in anchors or e["name"] in query)]
        if not matched:
            return []
        matched_names = {e["name"] for e in matched}
        communities = {e["community"] for e in matched if e.get("community") not in (None, -1)}
        if not communities:
            return []

        related = [
            e for e in entities
            if e.get("community") in communities
            and e["name"] not in matched_names
            and e["name"] not in exclude
            and e["type"] in ("university", "department")
        ]
        related.sort(key=lambda e: -(e.get("pagerank") or 0))
        return [
            {"name": e["name"], "type": e["type"], "community_label": e.get("community_label") or ""}
            for e in related[:top_n]
        ]

    def detect_entities_in_text(self, text: str, top_n: int = 8) -> List[Dict[str, Any]]:
        """GraphRAG 연동(서류 첨삭용): 사용자가 붙여넣은 자소서/활동보고서 문장에서
        어떤 학교/학과/실기종목 개체가 언급됐는지 이름매칭으로 찾고, 그 개체가 속한
        커뮤니티 라벨(예: '회화 계열 실기')을 함께 반환한다. 첨삭 자체의 사실판정에는
        쓰지 않고, 어떤 계열 글인지 감을 잡아 첨삭 톤을 맞추는 참고 정보로만 쓴다."""
        entities = self._all_entities()
        matched = [e for e in entities if e["name"] and len(e["name"]) >= 2 and e["name"] in text]
        matched.sort(key=lambda e: -(e.get("pagerank") or 0))
        return [
            {"name": e["name"], "type": e["type"], "community_label": e.get("community_label") or ""}
            for e in matched[:top_n]
        ]

    def get_entity_mismatch_candidates(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """사전(구조화 데이터)에 없다가 LLM 구조화 추출이 새로 찾아낸 개체를 노출한다
        (day36 교안_02가 목표했던 지점: 규칙/사전 기반으로는 놓치는 걸 LLM이 잡아냄).
        원문검증+신뢰도필터를 이미 통과한 것들만 여기 올라온다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (c:Admission_TextChunk)-[:MENTIONS]->(e:Admission_Entity {llm_discovered: true})
                WITH e, count(DISTINCT c) AS chunk_count
                RETURN e.name AS name, e.type AS type, e.pagerank AS pagerank, chunk_count
                ORDER BY chunk_count DESC LIMIT $top_n
            """, top_n=top_n).data()
        return rows

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

    # 실기유형 문구에 흔히 끼어드는 일반 행정 용어 - "무엇으로 준비했는지"(소묘/연필/수채화 등)와
    # 무관해서 겹쳐도 실기 준비 과정이 같다는 신호가 아니므로 키워드 매칭에서 제외한다.
    _GENERIC_EXAM_KEYWORDS = {
        "실기", "면접", "서류", "평가", "심사", "질의응답", "전형", "발표", "제출",
        "작성", "참고자료", "단계", "선발", "제시", "이미지", "사진", "당일",
        # 실기종목명이 완결된 문장형으로 적힌 학교(예: 명지대 "문제 주제의 해석과
        # 표현 (입체적 첨가 형식 제외 모든 재료 허용)")에서 나오는 조사/연결어/
        # 상투어 - "큰 주제" 선택지에서 이런 문법 부스러기까지 뜨는 걸 막는다.
        "또는", "주제는", "주제의", "시험당일", "모든", "형식", "재료", "제외",
        "문제", "첨가", "허용", "해석과", "표현", "함께", "이내", "방향", "선택",
        "있는", "대한", "내외", "정물과",
        # "특기"는 실기 종목명이 아니라 "지정대사 연기 및 특기(장기자랑)"처럼
        # 시험 절차의 한 항목을 가리키는 일반 단어인데, 우연히 용인대·서울예대
        # 실기유형 원문에 그대로 등장해서 "큰 주제" 선택지에 잘못 노출됐었다.
        "특기",
    }

    @staticmethod
    def _exam_keywords(text: str) -> set:
        return set(re.findall(r"[가-힣]{2,}", text or "")) - ArtAdmissionService._GENERIC_EXAM_KEYWORDS

    @staticmethod
    def _material_keywords(materials: List[str]) -> set:
        """재료 문자열은 학교마다 표기가 제각각이라("소묘용 연필" vs "연필") 완전일치로는
        거의 안 겹친다 - 재료명 안의 단어 단위로 쪼개서 겹치는지 본다."""
        kws = set()
        for m in materials or []:
            kws |= set(re.findall(r"[가-힣]{2,}", m))
        return kws

    def find_compatible_tracks(self, university: str, department: str) -> List[Dict[str, Any]]:
        """기준 전형과 실기 유형(키워드)·허용재료(키워드)가 겹치는 다른 학교 전형을 찾는다.
        즉 '소묘/연필로 준비한 과정'이 통하는 다른 학교를 찾는 게 목적이므로, 재료명도
        전체 문자열이 아니라 단어 단위로 비교한다 - 유사도 추정(임베딩)은 쓰지 않는다."""
        tracks = self.list_all_tracks_full()
        base = next((t for t in tracks if t["university"] == university and t["department"] == department), None)
        if not base or not base.get("exam_type_name"):
            return []

        base_keywords = self._exam_keywords(base["exam_type_name"])
        base_material_kw = self._material_keywords(base.get("allowed_materials"))

        results = []
        for t in tracks:
            if t["university"] == university:
                continue
            if not t.get("exam_type_name"):
                continue
            shared_kw = base_keywords & self._exam_keywords(t["exam_type_name"])
            shared_materials = base_material_kw & self._material_keywords(t.get("allowed_materials"))
            if shared_kw or shared_materials:
                results.append({
                    "university": t["university"], "department": t["department"], "track_name": t["track_name"],
                    "admission_year": t.get("admission_year"),
                    "exam_type_name": t["exam_type_name"], "shared_keywords": sorted(shared_kw),
                    "shared_materials": sorted(shared_materials), "source_url": t["source_url"],
                })
        results.sort(key=lambda m: -(len(m["shared_keywords"]) + len(m["shared_materials"])))
        return results

    # 실기 유형/재료 문구에 이 단어가 있으면 실기시험이 아니라 서류로 평가받는
    # 전형이다 - 실측 데이터에 실제로 있는 표현("미술활동보고서 서류평가...",
    # "포트폴리오... 서류평가...")만 근거로 판정한다. 임의 카테고리 추정 아님.
    _DOCUMENT_BASED_MARKERS = ("서류평가", "미술활동보고서")

    def list_tracks_with_estimates(self) -> List[Dict[str, Any]]:
        """실기 역탐색용 원천 데이터 - 트랙마다 exam_type/재료/일정/컷라인 추정치를
        한 번의 쿼리로 합쳐서 가져온다 (N+1 방지). FO 결과 카드에 필요한 필드를
        전부 여기서 채운다 - quota/ratio/time_limit_minutes/원서접수·실기고사·발표일까지."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE t.is_superseded IS NULL OR t.is_superseded = false
                OPTIONAL MATCH (t)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
                OPTIONAL MATCH (t)-[:HAS_SCHEDULE]->(sch:Admission_Schedule)
                OPTIONAL MATCH (t)-[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                RETURN u.name AS university, u.campus AS campus, d.name AS department,
                       t.name AS track_name, t.admission_year AS admission_year,
                       t.quota AS quota, t.ratio AS ratio, t.source_url AS source_url,
                       e.name AS exam_type_name, e.allowed_materials AS allowed_materials,
                       e.paper_size AS paper_size, e.time_limit_minutes AS time_limit_minutes,
                       sch.application_start AS application_start, sch.application_end AS application_end,
                       sch.exam_date AS exam_date_raw, sch.result_date AS result_date,
                       c.cutoff_grade_estimate AS cutoff_grade_estimate, c.source_url AS cutoff_source_url
            """).data()
        for r in rows:
            r["exam_dates"] = _extract_dates(r.get("exam_date_raw"))
            r["source_tier"] = _classify_source(r.get("source_url"))
        return rows

    def list_exam_topic_keywords(self, min_schools: int = 2) -> List[str]:
        """'큰 주제' 선택지 - exam_type_name(실기종목명)에서만 뽑은 키워드.
        재료명(색연필/가위/고착제 등 200개+ 세부 항목)과 섞이지 않게 분리해서,
        UI 멀티셀렉트가 소묘/수채화/한국화/기초디자인처럼 굵직한 실기 종목
        위주로만 나오게 한다. 카테고리를 수작업으로 만든 게 아니라, 이미 데이터
        모델에 있는 exam_type vs material 구분을 그대로 활용한 것.
        min_schools: 이 개수 미만으로만 등장하는 단어(특정 학교 지정작품 제목 -
        예: '돈키호테'/'브레히트' 같은 서울예대 연극 지정작품명 - 는 '실기 종목'이
        아니라 그 학교만의 세부 사항이므로 큰 주제 목록에서 제외)."""
        rows = self.list_tracks_with_estimates()
        counts: Dict[str, int] = {}
        for r in rows:
            exam_name = r.get("exam_type_name") or ""
            if any(marker in exam_name for marker in self._DOCUMENT_BASED_MARKERS):
                continue  # 서류전형 표시어("서류평가"/"면접평가" 등)는 실기 종목이 아니므로 제외
            for kw in self._exam_keywords(exam_name):
                counts[kw] = counts.get(kw, 0) + 1
        return sorted(kw for kw, cnt in counts.items() if cnt >= min_schools)

    def list_available_prep_keywords(self) -> List[str]:
        """(레거시) exam_type+재료 전체 키워드 - 새 UI는 주제/재료를 분리해서
        list_exam_topic_keywords()를 쓰지만, 다른 곳에서 필요할 수 있어 남겨둔다."""
        rows = self.list_tracks_with_estimates()
        kws: set = set()
        for r in rows:
            kws |= self._exam_keywords(r.get("exam_type_name") or "")
            kws |= self._material_keywords(r.get("allowed_materials"))
        return sorted(kws)

    def search_tracks_by_prep(self, topic_keywords: Optional[List[str]] = None,
                               material_query: str = "", document_only: bool = False) -> List[Dict[str, Any]]:
        """수험생이 고른 '큰 주제'(실기종목 키워드)와 자유 검색한 재료 문구로
        겹치는 학교/학과를 찾는다. 재료는 200개+ 세부 항목이 있어 선택지 나열
        대신 부분일치 검색으로 처리한다 - 예를 들어 "연필"로 검색하면
        "소묘용 연필", "4B연필" 등을 전부 잡는다.
        document_only=True면 실기 없이 서류(미술활동보고서 등)로 평가받는
        전형만 따로 보여준다.

        match_status 3단계로 반드시 분리한다 - 재료만 겹치는 걸 "실기종목 일치"
        라고 부르면 안 된다는 게 이 함수의 핵심 불변조건이다:
          - "exact"    : 선택한 실기종목 키워드가 전형의 실기유형과 실제로 겹침
          - "partial"  : 재료/규격만 겹치거나 일부 키워드만 겹침 (준비 내용 확인 필요)
          - "document" : 실기 없이 서류로 평가 (document_only일 때만)
        """
        topic_set = set(topic_keywords or [])
        material_query = (material_query or "").strip()
        rows = self.list_tracks_with_estimates()
        results = []
        for r in rows:
            exam_name = r.get("exam_type_name") or ""
            is_doc = any(marker in exam_name for marker in self._DOCUMENT_BASED_MARKERS)
            if document_only:
                if not is_doc:
                    continue
                results.append({
                    **r, "matched_keywords": [], "is_document_based": True,
                    "match_status": "document", "exact_match_reasons": [],
                    "partial_match_reasons": [], "warnings": [],
                })
                continue
            if is_doc:
                continue  # 서류전형은 재료/실기 키워드 비교 대상이 아니므로 일반 검색에서는 제외

            exam_kw = self._exam_keywords(exam_name)
            matched_topics = topic_set & exam_kw if topic_set else set()
            matched_materials = set()
            if material_query:
                for m in (r.get("allowed_materials") or []):
                    if material_query in m:
                        matched_materials.add(m)

            matched = matched_topics | matched_materials
            if not matched:
                continue

            if matched_topics:
                match_status = "exact"
                exact_reasons = sorted(matched_topics)
                partial_reasons = sorted(matched_materials)
                warnings: List[str] = []
            else:
                match_status = "partial"
                exact_reasons = []
                partial_reasons = sorted(matched_materials)
                warnings = ["실기유형이 아니라 재료·규격만 겹치는 결과입니다. 실제 준비 내용을 공식 모집요강에서 반드시 확인하세요."]

            results.append({
                **r, "matched_keywords": sorted(matched), "is_document_based": False,
                "match_status": match_status, "exact_match_reasons": exact_reasons,
                "partial_match_reasons": partial_reasons, "warnings": warnings,
            })

        # exact를 항상 앞에, 그 안에서는 겹치는 키워드가 많은 순
        results.sort(key=lambda r: (r["match_status"] != "exact", -len(r["matched_keywords"])))
        return results

    def get_compatible_tracks_for_query(self, query: str) -> List[Dict[str, Any]]:
        """AI 답변(LLM) 경로용 호환학교 조회. 규칙기반 answer_question의 호환 분기와
        같은 학교/학과 해석을 쓰지만, "호환/지원가능" 같은 의도 키워드가 있어야만
        도는 게 아니라 학교(+가능하면 학과)가 인식되기만 하면 항상 계산해서 LLM에게
        참고자료로 준다 - 사용자가 자연어로 아무리 다르게 물어도(예: "동일한 실기로
        지원 가능한 학교") AI 답변이 실제 매칭 데이터를 보고 답하게 하기 위함."""
        q = query.strip()
        tracks = self.list_all_tracks_full()
        universities = sorted({t["university"] for t in tracks})
        mentioned = _resolve_university_mentions(q, universities)
        if not mentioned:
            return []
        university = mentioned[0]
        univ_tracks = [t for t in tracks if t["university"] == university]
        dept_track = next((t for t in univ_tracks if t["department"] and t["department"] in q), None)
        track = dept_track or (univ_tracks[0] if len(univ_tracks) == 1 else None)
        if not track:
            return []
        return self.find_compatible_tracks(university, track["department"])

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
        is_compat_intent = any(k in q for k in [
            "호환", "비슷", "추천", "동일한 실기", "같은 실기", "동일 실기",
            "지원가능", "지원 가능", "지원할 수 있는", "같이 준비",
        ])

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
            univ_tracks = [t for t in tracks if t["university"] == university]
            # 질문에 학과명이 같이 언급되면 그 학과를 기준으로 삼는다 - 안 그러면 그 학교의
            # 아무 트랙이나(목록의 첫 번째) 기준이 돼서, 여러 학과가 있는 학교는 사용자가
            # 물어본 학과와 무관한 결과가 나올 수 있다 (실제로 겪은 버그).
            dept_track = next((t for t in univ_tracks if t["department"] and t["department"] in q), None)
            if dept_track:
                track = dept_track
            elif len(univ_tracks) > 1:
                dept_list = ", ".join(sorted({t["department"] for t in univ_tracks}))
                return {
                    "intent": "COMPATIBILITY",
                    "answer": f"{university}에는 학과가 여러 개 있습니다({dept_list}). 어느 학과 기준인지 학과명을 함께 말씀해주세요.",
                    "source_url": None,
                }
            else:
                track = univ_tracks[0]
            matches = self.find_compatible_tracks(university, track["department"])
            if not matches:
                return {"intent": "COMPATIBILITY", "answer": f"{university} {track['department']}과(와) 실기유형/재료가 겹치는 다른 전형을 찾지 못했습니다 (적재된 데이터 범위 내).", "source_url": None}
            lines = [
                f"[기준: {university} {track['department']} - {track.get('exam_type_name')}]",
                "",
            ] + [
                f"- {m['university']} {m['department']} ({m.get('exam_type_name')}): "
                f"공통 실기 키워드 {m['shared_keywords'] or '-'}, 공통 재료 키워드 {m['shared_materials'] or '-'}"
                for m in matches
            ]
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

        # 질의 문장 자체에 등장하는 실기유형 키워드(예: "소묘")를 뽑아, 각 트랙의
        # exam_type_name과 실제로 겹치는지 미리 계산해 LLM에게 넘긴다. 이게 없으면
        # LLM이 재료(연필 등)만 보고 스스로 "비슷한 실기"라고 짐작해버리는 문제가 있었다.
        # search_tracks_by_prep과 완전히 같은 판정(topic_set & exam_kw 완전일치)을
        # 쓰기 위해, 질의 문장에서 실제 실기종목 키워드를 뽑아낸다. 단순 substring
        # 검사(kw in query)는 "수채화"가 "인체수채화"의 부분 문자열이라 서로 다른
        # 종목을 같은 것으로 오탐지했었다(상명대 "인체수채화" 질문에 동국대 "수채화"
        # 전형이 잘못 섞여 나옴) - 그래서 데이터에 실제 존재하는 실기종목 키워드
        # 전체를 대상으로, 긴 키워드부터 먼저 매칭해 겹치는 문자를 "소비"하는
        # 최장일치 방식으로 질의에서 실기종목 키워드를 뽑는다. 조사가 붙은 경우
        # ("소묘로")도 "소묘"가 그 안의 substring이므로 여전히 잡힌다.
        canonical_topics = sorted(set(self.list_exam_topic_keywords(min_schools=1)), key=len, reverse=True)
        consumed = [False] * len(query)
        query_topic_kw: set = set()
        for kw in canonical_topics:
            start = 0
            while True:
                idx = query.find(kw, start)
                if idx == -1:
                    break
                if not any(consumed[idx:idx + len(kw)]):
                    query_topic_kw.add(kw)
                    for i in range(idx, idx + len(kw)):
                        consumed[i] = True
                start = idx + 1

        context_tracks = [{
            "university": t["university"], "department": t["department"], "track_name": t["track_name"],
            "admission_year": t.get("admission_year"), "quota": t.get("quota"), "ratio": t.get("ratio"),
            "exam_type_name": t.get("exam_type_name"), "allowed_materials": t.get("allowed_materials"),
            "paper_size": t.get("paper_size"), "time_limit_minutes": t.get("time_limit_minutes"),
            "application_start": t.get("application_start"), "application_end": t.get("application_end"),
            "exam_dates": t.get("exam_dates"), "result_date": t.get("result_date"),
            "source_url": t.get("source_url"),
            "exam_type_keyword_match": bool(query_topic_kw & self._exam_keywords(t.get("exam_type_name") or "")),
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
        from services.art_admission_llm import embed_text, rerank_chunks, cross_encoder_rerank
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

        # day48: 전용 크로스인코더가 있으면 그걸 먼저 쓴다(빠르고·결정적이고·LLM 호출비 없음).
        # 모델을 못 받았거나 실패하면 기존 LLM 재순위화로 자동 폴백 - 검색 자체는 절대 안 죽는다.
        ce_result = cross_encoder_rerank(query, candidates, top_k=top_k)
        if ce_result is not None:
            return ce_result
        try:
            return rerank_chunks(query, candidates, model_id=rerank_model_id, top_k=top_k)
        except Exception:
            return candidates[:top_k]

    _DOC_RULE_KEYWORDS: Dict[str, List[str]] = {
        "자기소개서": ["자기소개서", "블라인드", "분량", "글자", "표절", "대필", "유의사항"],
        "미술활동보고서": ["미술활동보고서", "블라인드", "분량", "글자", "표절", "대필", "유의사항"],
        "포트폴리오 설명글": ["포트폴리오", "블라인드", "분량", "글자", "유의사항"],
        "기타 서류": ["블라인드", "분량", "글자", "표절", "대필", "유의사항"],
    }

    def get_document_rule_excerpts(self, university: str, doc_type: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """서류 첨삭 학교별 규정 반영: 학교마다 서류 규정(블라인드 평가, 분량/글자 제한,
        표절·대필 금지 등)이 실제로 다르므로, 이미 색인된 PDF 원문에서 해당 학교·문서종류
        관련 키워드가 들어간 청크를 직접 찾아온다. 임의로 규정을 만들지 않고, 못 찾으면
        빈 리스트를 반환한다 - 그 경우 첨삭은 일반 글쓰기 관점으로만 진행되며 UI에서도
        '이 학교 규정 원문을 못 찾음'을 명시해야 한다."""
        if not university:
            return []
        keywords = self._DOC_RULE_KEYWORDS.get(doc_type, self._DOC_RULE_KEYWORDS["기타 서류"])
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (c:Admission_TextChunk {university: $university})
                WHERE any(kw IN $keywords WHERE c.text CONTAINS kw)
                RETURN c.university AS university, c.chunk_index AS chunk_index, c.text AS text,
                       c.page_start AS page_start, c.page_end AS page_end,
                       c.admission_year AS admission_year, c.source_file AS source_file
                LIMIT $top_k
            """, university=university, keywords=keywords, top_k=top_k * 3).data()
        # 목차 페이지(점선 leader "....." 같은 표기가 많은 페이지)는 실제 규정 문장이
        # 아니므로 걸러낸다 - 실측해보니 키워드 매칭에 이런 노이즈가 자주 걸림.
        real_rows = [r for r in rows if r["text"].count("..") < 10]
        return (real_rows or rows)[:top_k]
