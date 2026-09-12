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
import json
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


def _weighted_avg(items: List[tuple]) -> Optional[float]:
    """items: [(환산점수, 이수단위), ...]. 이수단위 합이 0이면 계산 불가(None)."""
    total_credit = sum(c for _, c in items)
    if total_credit == 0:
        return None
    return sum(s * c for s, c in items) / total_credit


def _raw_grade_avg(items_with_grade: List[tuple]) -> Optional[float]:
    """(이수단위, 원 석차등급) 쌍의 이수단위 가중평균 - 학교 고유 배점표를 거치지 않은
    '원 석차등급' 그대로의 평균이다. 학교 배점표는 상위 등급 구간을 압축해두는
    경우가 흔해서(예: 가천대 1~6등급이 100~97.5점으로 거의 차이가 없음), 배점
    기준 백분율을 일반 곡선에 역산하면 실제보다 훨씬 좋아 보이는 등급이 나온다
    (실측: 4~6등급대 학생이 배점 기준 97%로 나오는데 원 등급 평균은 4.96 -
    타 입시업체 '내등급' 4.92와 거의 일치). 그래서 참고용 등급은 반드시 이
    원 석차등급 평균을 써야 하고, 배점표를 거친 값을 역산하면 안 된다."""
    pairs = [(g, c) for c, g in items_with_grade if g is not None]
    if not pairs:
        return None
    total_credit = sum(c for _, c in pairs)
    if total_credit == 0:
        return None
    return round(sum(g * c for g, c in pairs) / total_credit, 2)


def _calc_school_record_raw_score(rule: Dict[str, Any], grades: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """school_record_rule(원문 모집요강에서 그대로 옮긴 반영교과/환산표/공식)에 따라
    학생 성적을 그 학교 공식 그대로 환산한다. 등급 곡선을 임의로 지어내지 않고,
    JSON에 원문 그대로 박아둔 conversion_table/formula만 사용한다.

    grades 항목 형태: {"subject_group": "국어", "grade": 4, "credit": 4} (일반/공통선택과목)
                     또는 {"subject_group": "국어", "career_elective": True, "achievement": "A", "credit": 2} (진로선택과목)
    """
    if not rule:
        return None
    mode = rule.get("mode")
    conv = {str(k): v for k, v in (rule.get("conversion_table") or {}).items()}
    max_score = max(conv.values()) if conv else None

    # 예: 홍익대 세종은 원문에 "사회 교과는 한국사, 사회(역사/도덕포함)를 반영함"이라고
    # 명시돼 있어 한국사를 사회로 합산해야 하지만, 서경대는 반영교과 표에서 한국사
    # 칸이 아예 비어있어 반영하지 않는다 - 이렇게 학교마다 갈리는 걸 학생 입력값을
    # 억지로 통일시키지 않고, 확인된 학교에만 subject_aliases로 치환 규정을 박아둔다.
    aliases = rule.get("subject_aliases") or {}
    if aliases:
        grades = [
            {**g, "subject_group": aliases.get(g.get("subject_group"), g.get("subject_group"))}
            for g in grades
        ]

    def _score_for_grade(g):
        return conv.get(str(g)) if g is not None else None

    if mode == "simple_weighted_average":
        # top_n + credit_weighted:false 조합으로 "전체 반영교과 중 석차등급 상위 N과목을
        # 이수단위 적용 없이 단순평균"하는 학교(예: 동국대 - 국어/수학/사회/과학/영어/
        # 한국사 중 상위 10과목, 이수단위 미적용)까지 코드 수정 없이 흡수한다.
        subjects = set(rule.get("subjects") or [])
        top_n = rule.get("top_n")
        credit_weighted = rule.get("credit_weighted", True)
        # average_by_semester: 계원예대처럼 "학기별 이수단위 가중평균 -> 그 학기평균들의
        # 단순평균"(2단계 평균)을 쓰는 학교용. 학기 이수단위 총량이 학기마다 다르면
        # 전체를 한 번에 이수단위 가중평균 내는 것과 결과가 달라지므로, 원문 계산식이
        # 명시적으로 학기 단위 평균을 요구할 때만 켠다(학생 입력에 "semester" 키 필요).
        average_by_semester = rule.get("average_by_semester", False)
        candidates = []
        for g in grades:
            if g.get("career_elective"):
                continue  # 이 모드는 진로선택과목 미반영 (원문 규정 그대로)
            if subjects and g.get("subject_group") not in subjects:
                continue
            s = _score_for_grade(g.get("grade"))
            if s is None:
                continue
            candidates.append(g)
        candidates = sorted(candidates, key=lambda g: -_score_for_grade(g.get("grade")))
        if top_n:
            candidates = candidates[:top_n]

        pool = []
        raw_pool = []
        details = []
        for g in candidates:
            s = _score_for_grade(g.get("grade"))
            credit = g.get("credit") or 1
            weight = credit if credit_weighted else 1
            pool.append((s, weight))
            raw_pool.append((weight, g.get("grade")))
            details.append({"subject_group": g.get("subject_group"), "grade": g.get("grade"), "credit": credit, "score": s, "semester": g.get("semester")})

        if not pool:
            return None

        if average_by_semester:
            by_sem: Dict[Any, List[tuple]] = {}
            for g in candidates:
                sem = g.get("semester") or "미상"
                credit = g.get("credit") or 1
                weight = credit if credit_weighted else 1
                by_sem.setdefault(sem, []).append((_score_for_grade(g.get("grade")), weight))
            sem_avgs = [v for v in (_weighted_avg(items) for items in by_sem.values()) if v is not None]
            avg = sum(sem_avgs) / len(sem_avgs) if sem_avgs else None
        else:
            avg = _weighted_avg(pool)
        if avg is None:
            return None
        return {"raw_score": avg, "max_score": max_score, "matched_subject_count": len(pool), "raw_grade_average": _raw_grade_avg(raw_pool), "breakdown": details}

    if mode == "year_weighted_band_lookup":
        # 한국예술종합학교 방식: 과목별 석차등급을 9~1점 등급점수로 바꾼 뒤
        # (1) 학기별 이수단위 가중평균 -> (2) 학년별 단순평균(학기 평균들의 평균, 이수단위
        # 미적용) -> (3) 학년별 반영비율(year_weights)로 가중합 -> (4) 그 결과값을
        # 0~100점 구간표(score_band_table)에서 조회, 총 4단계 집계라 기존
        # conversion_table 방식(과목별 점수 -> 단일 가중평균)으로는 표현이 안 돼서
        # 새 모드로 분리했다(여전히 학교명 분기 없이 파라미터만으로 재사용 가능).
        grade_points = {str(k): v for k, v in (rule.get("grade_point_table") or {}).items()}
        year_weights = {str(k): v for k, v in (rule.get("year_weights") or {}).items()}
        bands = rule.get("score_band_table") or []

        by_year_sem: Dict[tuple, List[tuple]] = {}
        raw_pool = []
        for g in grades:
            year = str(g.get("year")) if g.get("year") is not None else None
            if year not in year_weights or not year_weights[year]:
                continue  # 반영비율 0인 학년(예: 8월 지원 졸업예정자의 3학년)은 원문대로 제외
            pt = grade_points.get(str(g.get("grade"))) if g.get("grade") is not None else None
            if pt is None:
                continue
            credit = g.get("credit") or 1
            sem = g.get("semester")
            by_year_sem.setdefault((year, sem), []).append((pt, credit))
            raw_pool.append((credit, g.get("grade")))

        if not by_year_sem:
            return None

        year_semester_avgs: Dict[str, List[float]] = {}
        for (year, _sem), items in by_year_sem.items():
            avg = _weighted_avg(items)
            if avg is not None:
                year_semester_avgs.setdefault(year, []).append(avg)

        year_scores = {y: sum(v) / len(v) for y, v in year_semester_avgs.items() if v}
        if not year_scores:
            return None
        total_weight = sum(year_weights[y] for y in year_scores)
        if total_weight == 0:
            return None
        # 실제로 성적이 있는 학년의 반영비율 합으로 정규화 - 원문 규정은 모든 학년 성적이
        # 다 있는 걸 전제로 하지만(그 경우 정규화해도 값이 그대로임), 일부 학년 성적이
        # 없는 예외적 입력에서 총합이 100%에 못 미쳐 부당하게 낮은 점수가 나오는 걸 방지.
        weighted_grade_point = sum(year_scores[y] * year_weights[y] for y in year_scores) / total_weight

        matched_score = None
        for band in bands:
            lo, hi = band.get("min"), band.get("max")
            if lo is not None and hi is not None and lo <= weighted_grade_point <= hi:
                matched_score = band.get("score")
                break
        if matched_score is None:
            return None
        return {
            "raw_score": matched_score,
            "max_score": 100,
            "matched_subject_count": sum(len(items) for items in by_year_sem.values()),
            "raw_grade_average": _raw_grade_avg(raw_pool),
            "breakdown": [{"year": y, "year_grade_point": round(s, 2)} for y, s in year_scores.items()] + [{"weighted_grade_point": round(weighted_grade_point, 2)}],
        }

    if mode == "choose_max_credit_subject":
        fixed = set(rule.get("fixed_subjects") or [])
        choice_group = rule.get("subject_choice_group") or []
        # selection_method: "credit"(기본, 이수단위 합 최대 교과 선택 - 동률이면 유리한 쪽)
        # 또는 "score"(성신여대처럼 이수단위 비교 없이 무조건 "성적이 상위인 교과영역"을
        # 실제로 계산해보고 고르는 학교용 - 매번 전체 후보를 계산해서 비교).
        selection_method = rule.get("selection_method", "credit")
        career_elective_included = rule.get("career_elective_included", False)
        ce_conv = {str(k): v for k, v in (rule.get("career_elective_conversion_table") or {}).items()}
        ce_max_per_subject = rule.get("career_elective_max_count_per_subject")

        def _pool_for(choice_subject):
            active = fixed | ({choice_subject} if choice_subject else set())
            common_pool = [
                (_score_for_grade(g.get("grade")), g.get("credit") or 1)
                for g in grades
                if not g.get("career_elective") and g.get("subject_group") in active and _score_for_grade(g.get("grade")) is not None
            ]
            career_pool = []
            if career_elective_included and ce_conv:
                for sg in active:
                    cands = [
                        g for g in grades
                        if g.get("career_elective") and g.get("subject_group") == sg and ce_conv.get(str(g.get("achievement"))) is not None
                    ]
                    cands = sorted(cands, key=lambda g: -ce_conv[str(g.get("achievement"))])
                    if ce_max_per_subject:
                        cands = cands[:ce_max_per_subject]
                    career_pool.extend((ce_conv[str(g.get("achievement"))], g.get("credit") or 1) for g in cands)
            return common_pool + career_pool

        if selection_method == "score":
            candidates = choice_group
        else:
            credit_by_subject: Dict[str, int] = {}
            for g in grades:
                sg = g.get("subject_group")
                if sg in choice_group and not g.get("career_elective"):
                    credit_by_subject[sg] = credit_by_subject.get(sg, 0) + (g.get("credit") or 1)
            if not credit_by_subject:
                candidates = []
            else:
                max_credit = max(credit_by_subject.values())
                candidates = [s for s, c in credit_by_subject.items() if c == max_credit]

        if not candidates:
            pool = _pool_for(None)
            chosen = None
        elif len(candidates) == 1:
            chosen = candidates[0]
            pool = _pool_for(chosen)
        else:
            # 이수학점(단위) 합이 동률이거나(선택방식=credit), 애초에 "성적이 상위인 쪽을
            # 반영"하는 규정(선택방식=score)이면 각 후보를 실제로 계산해보고 결과가 더
            # 높은 쪽을 선택한다 (임의로 하나를 고르지 않는다).
            best_chosen, best_pool, best_avg = None, [], None
            for cand in candidates:
                cand_pool = _pool_for(cand)
                cand_avg = _weighted_avg(cand_pool) if cand_pool else None
                if cand_avg is not None and (best_avg is None or cand_avg > best_avg):
                    best_chosen, best_pool, best_avg = cand, cand_pool, cand_avg
            chosen, pool = best_chosen, best_pool

        avg = _weighted_avg(pool) if pool else None
        if avg is None:
            return None
        active_final = fixed | ({chosen} if chosen else set())
        raw_pool = [
            (g.get("credit") or 1, g.get("grade"))
            for g in grades
            if not g.get("career_elective") and g.get("subject_group") in active_final and _score_for_grade(g.get("grade")) is not None
        ]
        details = [
            {"subject_group": g.get("subject_group"), "grade": g.get("grade"), "credit": g.get("credit") or 1, "score": _score_for_grade(g.get("grade"))}
            for g in grades
            if not g.get("career_elective") and g.get("subject_group") in active_final and _score_for_grade(g.get("grade")) is not None
        ]
        return {"raw_score": avg, "max_score": max_score, "matched_subject_count": len(pool), "chosen_choice_subject": chosen, "raw_grade_average": _raw_grade_avg(raw_pool), "breakdown": details}

    if mode == "subject_group_weighted":
        groups = rule.get("subject_groups") or {}
        # choice_groups: 동덕여대처럼 "필수 국어·영어 + (수학/사회/과학 중 성적이 좋은
        # 1개 교과)"를 균등(1/3씩) 반영하는 학교용 - 고정 그룹(subject_groups)과 별개로,
        # 옵션 여러 개 중 실제로 계산해서 평균이 가장 높은 과목 하나만 그 비중으로 반영한다.
        choice_groups = rule.get("choice_groups") or []
        top_n = rule.get("top_n_per_group")
        total = 0.0
        matched = 0
        missing_groups = []
        raw_total = 0.0
        raw_weight_used = 0.0
        details = []

        def _group_items(subject):
            items = [
                (_score_for_grade(g.get("grade")), g.get("credit") or 1, g.get("grade"))
                for g in grades
                if not g.get("career_elective") and g.get("subject_group") == subject and _score_for_grade(g.get("grade")) is not None
            ]
            if top_n:
                items = sorted(items, key=lambda x: -x[0])[:top_n]
            return items

        def _apply_group(subject, weight_pct, items):
            nonlocal total, matched, raw_total, raw_weight_used
            if not items:
                # 원문 규정대로: 반영과목이 전혀 없는 교과영역은 0점 처리(제외가 아님)
                missing_groups.append(subject)
                return
            group_avg = _weighted_avg([(s, c) for s, c, _ in items])
            total += (group_avg or 0) * weight_pct / 100.0
            matched += len(items)
            group_raw_avg = _raw_grade_avg([(c, g) for _, c, g in items])
            if group_raw_avg is not None:
                raw_total += group_raw_avg * weight_pct
                raw_weight_used += weight_pct
            for s, c, g in items:
                details.append({"subject_group": subject, "grade": g, "credit": c, "score": s, "group_weight_pct": weight_pct})

        for subject, weight_pct in groups.items():
            _apply_group(subject, weight_pct, _group_items(subject))

        for cg in choice_groups:
            options = cg.get("options") or []
            weight_pct = cg.get("weight_pct", 0)
            best_subject, best_items, best_avg = None, [], None
            for option in options:
                items = _group_items(option)
                if not items:
                    continue
                avg = _weighted_avg([(s, c) for s, c, _ in items])
                if avg is not None and (best_avg is None or avg > best_avg):
                    best_subject, best_items, best_avg = option, items, avg
            if best_subject is None:
                missing_groups.append("choice(" + "/".join(options) + ")")
                continue
            _apply_group(best_subject, weight_pct, best_items)

        # top_k_groups: 수원대처럼 "국어/수학/영어/사회(또는과학) 4개 후보 중 점수가
        # 높은 2개 교과만 50%씩 반영"하는 학교용 - choice_groups(옵션 중 1개만 선택)와
        # 달리 옵션 여러 개 중 상위 K개를 골라 각각 동일 비중으로 반영한다.
        top_k = rule.get("top_k_groups")
        if top_k:
            options = top_k.get("options") or []
            k = top_k.get("k", 1)
            weight_pct_each = top_k.get("weight_pct_each", 0)
            scored = []
            for option in options:
                items = _group_items(option)
                if not items:
                    continue
                avg = _weighted_avg([(s, c) for s, c, _ in items])
                if avg is not None:
                    scored.append((avg, option, items))
            scored.sort(key=lambda x: -x[0])
            for _avg, option, items in scored[:k]:
                _apply_group(option, weight_pct_each, items)

        if matched == 0:
            return None
        raw_grade_average = round(raw_total / raw_weight_used, 2) if raw_weight_used else None
        return {"raw_score": total, "max_score": max_score, "matched_subject_count": matched, "missing_subject_groups": missing_groups, "raw_grade_average": raw_grade_average, "breakdown": details}

    if mode == "all_subjects_plus_career_elective":
        # subjects가 비어있으면(기본값) 상명대처럼 전 교과목 반영, subjects를 채우면
        # 명지대(예체능계열: 국어·영어만 + 진로선택 전부 반영 + 이수학점 가산점)처럼
        # 특정 교과로 제한된 "전체 반영" 학교도 코드 분기 없이 흡수한다.
        subjects = set(rule.get("subjects") or [])
        credit_bonus_factor = rule.get("credit_bonus_factor")  # 예: 명지대 0.05
        pool = []
        raw_pool = []
        details = []
        ce_conv = {str(k): v for k, v in (rule.get("career_elective_conversion_table") or {}).items()}
        ce_items = []
        ce_details = []
        for g in grades:
            if subjects and g.get("subject_group") not in subjects:
                continue
            if g.get("career_elective"):
                s = ce_conv.get(str(g.get("achievement")))
                if s is not None:
                    credit = g.get("credit") or 1
                    ce_items.append((s, credit))
                    ce_details.append({"subject_group": g.get("subject_group"), "achievement": g.get("achievement"), "credit": credit, "score": s})
            else:
                s = _score_for_grade(g.get("grade"))
                if s is not None:
                    credit = g.get("credit") or 1
                    pool.append((s, credit))
                    raw_pool.append((credit, g.get("grade")))  # 진로선택(성취도)은 원 석차등급이 없어 참고등급 계산엔 제외
                    details.append({"subject_group": g.get("subject_group"), "grade": g.get("grade"), "credit": credit, "score": s})
        max_ce = rule.get("career_elective_max_count")
        if max_ce is not None:
            paired = sorted(zip(ce_items, ce_details), key=lambda x: -x[0][0])[:max_ce]
            ce_items = [p[0] for p in paired]
            ce_details = [p[1] for p in paired]
        pool.extend(ce_items)
        details.extend(ce_details)
        if not pool:
            return None
        total_credit = sum(c for _, c in pool)
        numerator = sum(s * c for s, c in pool)
        if credit_bonus_factor:
            # 명지대: 분자에 "반영교과 내 모든 이수과목 이수학점 합 × 0.05"를 가산점으로 더함
            numerator += total_credit * credit_bonus_factor
        avg = numerator / total_credit if total_credit else None
        if avg is None:
            return None
        # 가산점(credit_bonus_factor)은 이수학점 분포와 무관하게 평균에 상수로 더해지므로
        # (Σsc + 합×f)/합 = weighted_avg(s) + f, 이론상 만점도 그만큼 올라간다.
        effective_max = (max_score + credit_bonus_factor) if credit_bonus_factor and max_score else max_score
        return {"raw_score": avg, "max_score": effective_max, "matched_subject_count": len(pool), "raw_grade_average": _raw_grade_avg(raw_pool), "breakdown": details}

    if mode == "common_and_career_split_scaled":
        # 공통·일반선택과목 평균과 진로선택과목 평균을 각각 가중치로 합산하는 학교들의
        # 공통 패턴. 학교마다 다른 부분(가중치 자체, 이수학점에 따른 배율 적용 여부,
        # 진로선택 상위 N과목 제한, 진로선택 자체가 없을 때 공통 가중치를 올려주는지)을
        # 전부 rule 파라미터로 빼뒀다 - 새 학교가 이 패턴과 조금만 다르다고 코드를 새로
        # 분기하지 않고, 파라미터 조합으로 흡수하기 위함:
        #   - common_weight/career_weight: 기본 0.9/0.9 (홍익세종). 경희대처럼 0.8/0.2인
        #     학교도 있음(반영비율 자체가 다름, 0.9/0.9 더블카운팅이 아니라 진짜 8:2 분할)
        #   - use_credit_scale: 홍익세종은 이수학점 합에 따른 추가 배율(학점합/1000+0.9)이
        #     있지만(True, 기본값), 경희대처럼 그런 배율 자체가 없는 학교는 False
        #   - common_weight_if_no_career: 경희대는 "진로선택 성취평가등급이 1개도 없으면
        #     공통·일반선택만 100% 반영"이라 이 경우 가중치가 0.8->1.0으로 올라간다
        #   - career_elective_max_count: 상위 N개 진로선택과목만 반영(경희대=3, 홍익세종=제한없음)
        subjects = set(rule.get("subjects") or [])
        credit_cap = rule.get("credit_cap", 100)
        use_credit_scale = rule.get("use_credit_scale", True)
        common_weight = rule.get("common_weight", 0.9)
        career_weight = rule.get("career_weight", 0.9)
        common_weight_if_no_career = rule.get("common_weight_if_no_career", common_weight)
        career_max_count = rule.get("career_elective_max_count")
        ce_conv = {str(k): v for k, v in (rule.get("career_elective_conversion_table") or {}).items()}

        common_pool = [
            (_score_for_grade(g.get("grade")), g.get("credit") or 1)
            for g in grades
            if not g.get("career_elective") and (not subjects or g.get("subject_group") in subjects) and _score_for_grade(g.get("grade")) is not None
        ]
        career_candidates = [
            g for g in grades
            if g.get("career_elective") and (not subjects or g.get("subject_group") in subjects) and ce_conv.get(str(g.get("achievement"))) is not None
        ]
        career_candidates = sorted(career_candidates, key=lambda g: -ce_conv[str(g.get("achievement"))])
        if career_max_count is not None:
            career_candidates = career_candidates[:career_max_count]
        career_pool = [(ce_conv[str(g.get("achievement"))], g.get("credit") or 1) for g in career_candidates]
        if not common_pool and not career_pool:
            return None

        common_avg = _weighted_avg(common_pool) or 0
        career_avg = _weighted_avg(career_pool) or 0
        effective_common_weight = common_weight if career_pool else common_weight_if_no_career
        total_credit = sum(c for _, c in common_pool) + sum(c for _, c in career_pool)
        scale = (min(total_credit, credit_cap) / 1000 + 0.9) if use_credit_scale else 1.0
        raw_score = (common_avg * effective_common_weight + (career_avg * career_weight if career_pool else 0)) * scale

        common_max = max(conv.values()) if conv else 0
        career_max = max(ce_conv.values()) if ce_conv else 0
        theoretical_scale = (credit_cap / 1000 + 0.9) if use_credit_scale else 1.0
        theoretical_max = (common_max * common_weight + career_max * career_weight) * theoretical_scale
        raw_grade_pool = [
            (g.get("credit") or 1, g.get("grade"))
            for g in grades
            if not g.get("career_elective") and (not subjects or g.get("subject_group") in subjects) and _score_for_grade(g.get("grade")) is not None
        ]
        details = [
            {"subject_group": g.get("subject_group"), "grade": g.get("grade"), "credit": g.get("credit") or 1, "score": _score_for_grade(g.get("grade"))}
            for g in grades
            if not g.get("career_elective") and (not subjects or g.get("subject_group") in subjects) and _score_for_grade(g.get("grade")) is not None
        ] + [
            {"subject_group": g.get("subject_group"), "achievement": g.get("achievement"), "credit": g.get("credit") or 1, "score": ce_conv.get(str(g.get("achievement")))}
            for g in career_candidates
        ]
        return {
            "raw_score": raw_score, "max_score": round(theoretical_max, 4),
            "matched_subject_count": len(common_pool) + len(career_pool),
            "raw_grade_average": _raw_grade_avg(raw_grade_pool),
            "breakdown": details,
        }

    if mode == "subject_group_band_lookup":
        # 인천대 방식: 교과군별로 먼저 원 석차등급을 이수단위 가중평균 낸 뒤(예: 국어 2.07),
        # 그 "평균값"을 학교 고유 구간표(band_table, 예: 2.00~2.24 -> 347점)에서 조회해
        # 교과군 점수를 구하고, 교과군 비중(subject_groups)만큼 곱해 합산한다.
        # subject_group_weighted와 다른 점: 그 모드는 "과목별로 먼저 환산 -> 평균"인데
        # 반해, 이 모드는 "원 등급을 먼저 평균 -> 그 평균을 한 번만 환산"한다 - 순서가
        # 바뀌면 결과가 달라지는 비선형 구간표라 별도 모드로 분리했다(2027 인천대
        # 모집요강 39·53·54쪽 산출예시로 검증한 방식).
        subject_groups = rule.get("subject_groups") or {}
        bands = sorted(rule.get("band_table") or [], key=lambda b: b["min"])
        no_course_grade = rule.get("no_course_grade", 9)  # 반영과목이 없으면 최저등급(9등급) 반영

        def _band_score(raw_avg: float) -> Optional[float]:
            for b in bands:
                if b["min"] <= raw_avg <= b["max"]:
                    return b["score"]
            return None

        total = 0.0
        matched = 0
        details = []
        raw_avgs_weighted = []
        for subject, weight_pct in subject_groups.items():
            items = [
                (g.get("grade"), g.get("credit") or 1)
                for g in grades
                if not g.get("career_elective") and g.get("subject_group") == subject and g.get("grade") is not None
            ]
            if items:
                raw_avg = _raw_grade_avg([(c, g) for g, c in items])
                matched += len(items)
            else:
                raw_avg = float(no_course_grade)  # 원문 규정: 반영과목이 하나도 없는 교과군은 최저등급 처리
            score = _band_score(raw_avg) if raw_avg is not None else None
            if score is None:
                continue
            total += score * weight_pct / 100.0
            raw_avgs_weighted.append((raw_avg, weight_pct))
            details.append({"subject_group": subject, "raw_grade_average": raw_avg, "score": score, "group_weight_pct": weight_pct})
        if matched == 0:
            return None
        band_max = max((b["score"] for b in bands), default=None)
        raw_grade_average = _weighted_avg(raw_avgs_weighted) if raw_avgs_weighted else None
        return {
            "raw_score": total, "max_score": band_max, "matched_subject_count": matched,
            "raw_grade_average": round(raw_grade_average, 2) if raw_grade_average is not None else None,
            "breakdown": details,
        }

    if mode == "top_n_per_year_simple_average":
        # 용인대 방식: 학년(1~3)마다 반영교과 중 성적이 좋은 상위 N과목만 골라(전체
        # 학년 통틀어 최대 N x 3과목), 이수단위 가중치 없이 그 환산점수들을 단순평균한다
        # (다른 모드는 전부 이수단위 가중평균인데 이 학교만 단순평균 - 원문 46~47쪽 확인).
        # grades 항목에 "year": 1|2|3 이 있어야 학년별로 묶을 수 있다.
        subjects = set(rule.get("subjects") or [])
        top_n = rule.get("top_n_per_year", 3)
        by_year: Dict[Any, List[Dict[str, Any]]] = {}
        for g in grades:
            if g.get("career_elective"):
                continue
            if subjects and g.get("subject_group") not in subjects:
                continue
            s = _score_for_grade(g.get("grade"))
            if s is None:
                continue
            by_year.setdefault(g.get("year"), []).append({**g, "score": s})
        pool = []
        details = []
        for _year, items in by_year.items():
            items = sorted(items, key=lambda g: -g["score"])[:top_n]
            pool.extend(items)
        if not pool:
            return None
        avg = sum(g["score"] for g in pool) / len(pool)
        raw_pool = [(1, g.get("grade")) for g in pool]  # 단순평균이므로 이수단위 대신 가중치 1로 통일
        for g in pool:
            details.append({"subject_group": g.get("subject_group"), "grade": g.get("grade"), "year": g.get("year"), "score": g["score"]})
        return {
            "raw_score": avg, "max_score": max_score, "matched_subject_count": len(pool),
            "raw_grade_average": _raw_grade_avg(raw_pool), "breakdown": details,
        }

    return None


# 정밀 환산 규정이 없는 학교(대다수)에서 쓰는 근사 곡선. 학교별 반영교과를 모르므로
# 입력받은 전 과목을 그냥 이수단위 가중평균한다 - "정밀 계산"이 아니라 "근사 추정"이라고
# 반드시 라벨링해서 내려보내야 하는 이유가 이것 (calc_precision: "approximate").
_GENERIC_GRADE_CURVE = {1: 100, 2: 90, 3: 80, 4: 70, 5: 60, 6: 50, 7: 40, 8: 20, 9: 0}


def _describe_reflected_subjects(rule: Dict[str, Any]) -> str:
    """학교별 반영교과를 한 줄 설명으로 - 카드에 "왜 추천됐는지" 보여주기 위한
    결정론적 템플릿(LLM 호출 없음). rule에 실제 들어있는 필드만 조합하므로
    지어내는 내용이 없다."""
    mode = rule.get("mode")
    if mode == "simple_weighted_average":
        subs = rule.get("subjects") or []
        return "·".join(subs) + " 반영" if subs else "일부 교과만 반영"
    if mode == "choose_max_credit_subject":
        fixed = "·".join(rule.get("fixed_subjects") or [])
        choice = "/".join(rule.get("subject_choice_group") or [])
        return f"{fixed} + 택1({choice}, 이수단위 많은 교과 자동선택)" if fixed else "택1 교과 반영"
    if mode == "subject_group_weighted":
        groups = rule.get("subject_groups") or {}
        return "·".join(groups.keys()) + " 4개 교과군 균등 반영" if groups else "교과군별 반영"
    if mode == "all_subjects_plus_career_elective":
        return "특정 교과 제한 없이 석차등급 있는 전 교과목 반영"
    if mode == "common_and_career_split_scaled":
        subs = rule.get("subjects") or []
        return "·".join(subs) + " + 진로선택과목 반영" if subs else "전 교과목 반영"
    if mode == "subject_group_band_lookup":
        groups = rule.get("subject_groups") or {}
        return "·".join(groups.keys()) + " 교과군별 반영(구간표 조회)" if groups else "교과군별 구간표 반영"
    if mode == "top_n_per_year_simple_average":
        subs = rule.get("subjects") or []
        top_n = rule.get("top_n_per_year", 3)
        return (f"{'·'.join(subs)} 중 학년별 상위 {top_n}과목 단순평균" if subs else f"학년별 상위 {top_n}과목 단순평균")
    return "학교 고유 반영 방식"


def _build_reason_summary(rule: Dict[str, Any], practical_ratio_pct: Optional[float],
                           school_record_ratio_pct: Optional[float], ratio_text: Optional[str] = None) -> str:
    """카드에 노출할 "추천 이유" 한 줄 - 반영교과 + 실기/학생부 비중을 조합한
    결정론적 문장이다. 절대 "합격 가능성"을 언급하지 않고, 반영 구조상의
    유불리(학생부 영향이 크다/작다)만 설명한다."""
    subj_desc = _describe_reflected_subjects(rule)
    if practical_ratio_pct is not None and school_record_ratio_pct is not None:
        if practical_ratio_pct >= school_record_ratio_pct * 2:
            ratio_desc = f"실기 {practical_ratio_pct}% · 학생부 {school_record_ratio_pct}%로 실기 비중이 커서 학생부 영향은 상대적으로 제한적입니다."
        elif school_record_ratio_pct > practical_ratio_pct:
            ratio_desc = f"실기 {practical_ratio_pct}% · 학생부 {school_record_ratio_pct}%로 학생부 비중이 낮지 않아 내신 영향이 큽니다."
        else:
            ratio_desc = f"실기 {practical_ratio_pct}% · 학생부 {school_record_ratio_pct}%로 실기와 학생부가 비슷한 비중입니다."
    elif school_record_ratio_pct == 100:
        ratio_desc = "실기 없이 학생부교과 100%로 선발하는 전형입니다."
    elif ratio_text:
        # 단계별 전형처럼 단일 실기%/학생부%로 못 쪼개는 경우, 원문 반영비율 설명을 그대로 인용한다.
        ratio_desc = f"반영비율(원문): {ratio_text}"
    else:
        ratio_desc = "반영비율 정보가 확인되지 않았습니다."
    return f"{subj_desc}. {ratio_desc}"


def _approximate_school_record_score(grades: List[Dict[str, Any]]) -> Optional[float]:
    pool = [
        (_GENERIC_GRADE_CURVE[g["grade"]], g.get("credit") or 1)
        for g in grades
        if not g.get("career_elective") and g.get("grade") in _GENERIC_GRADE_CURVE
    ]
    if not pool:
        return None
    avg = _weighted_avg(pool)
    return round(avg, 2) if avg is not None else None


def _school_record_impact_score(rule: Optional[Dict[str, Any]], school_record_ratio_pct: Optional[float]) -> Optional[float]:
    """"내신 실질영향" 지표(사용자 확정 설계). 등급 하나 차이가 실제로 몇 점 깎이는지를
    보되, 등급 구간별로 관대함이 다른 학교(예: 동국대 1~5등급은 완만하다가 6등급부터
    급락)가 흔해서, 모든 학교에 같은 "6등급"을 대입해 학교 간 비교가 가능하게 한다
    (student 개인 등급이 아니라 학교 고유 배점표만 보는 지표라 학생 성적과 무관하게
    학교마다 고정값). 값 = (1등급 환산점수 - 6등급 환산점수) / 만점 × (학생부 반영비율/100).
    반영비율까지 곱하는 이유: 등급 격차가 커도 반영비율이 낮으면 총점에 미치는 실제
    영향은 작기 때문 - "환산표 기울기"와 "총점 기여도"를 함께 봐야 '실질' 영향이 된다.
    conversion_table이 없는 모드(예: 한국예종의 구간표 방식)나 subjects/그룹형 모드에서
    1·6등급 값이 없으면 비교 불가(None)로 정직하게 반환한다 - 지어내지 않는다."""
    if not rule or school_record_ratio_pct is None:
        return None
    conv = {str(k): v for k, v in (rule.get("conversion_table") or {}).items()}
    s1, s6 = conv.get("1"), conv.get("6")
    if s1 is None or s6 is None:
        return None
    max_score = max(conv.values()) if conv else None
    if not max_score:
        return None
    return round((s1 - s6) / max_score * (school_record_ratio_pct / 100), 4)


def _prior_year_tier(student_grade: Optional[float], pyr: Optional[Dict[str, Any]]) -> str:
    """전년도 등록자 학생부 성적과 이 학생의 원 석차등급(estimated_grade_equivalent)을
    비교해 4단계 버킷으로 나눈다 - 순위나 합격 확률이 아니라 "전년도 등록자 대비 어디쯤"
    인지만 보여준다. typical/floor 두 값 다 있으면 3단계, typical만 있으면(학교 원문이
    범위가 아니라 단일 평균값만 제공한 경우) 2단계로 갈린다. 학교마다 typical/floor가
    정확히 무엇을 의미하는지(50%컷/평균/1단계합격자 등)는 pyr["grade_stat_type"]에 그대로
    남겨두고 이 함수는 대소 비교만 한다 - 절대 "합격 가능성"으로 해석하면 안 된다."""
    if student_grade is None or not pyr:
        return "NO_DATA"
    typical = pyr.get("school_record_grade_typical")
    floor = pyr.get("school_record_grade_floor")
    if typical is None:
        return "NO_DATA"
    if student_grade <= typical:
        return "REGISTRANT_TOP"
    if floor is not None:
        return "REGISTRANT_MID" if student_grade <= floor else "REGISTRANT_BELOW"
    return "REGISTRANT_BELOW"


# 2026-09-09 실측으로 발견한 사고: 처음엔 "환산 백분율을 표준 9등급 곡선에 역산"하는
# 방식(_percentage_to_grade_equivalent, 삭제됨)을 썼는데, 타 입시업체 실측 데이터
# (내등급 4.92)와 비교해보니 완전히 다른 값(1.29)이 나왔다. 원인: 학교 공식 배점표가
# 상위 등급 구간을 압축해두는 경우가 흔해서(가천대 1~6등급이 100~97.5점, 겨우 2.5점
# 차이) 배점 기준 백분율은 원 등급이 4~6등급이어도 97%까지 나올 수 있는데, 이걸
# "일반적인" 9등급 곡선에 거꾸로 대입하면 실제보다 훨씬 좋은 등급으로 둔갑한다.
# 그래서 참고용 등급은 위 각 계산 모드가 함께 반환하는 raw_grade_average(배점표를
# 거치지 않은 원 석차등급의 이수단위 가중평균)를 그대로 쓴다 - 타사 수치와 실측 일치.

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

    def _kg_score_lookup(self, grades: Optional[List[Dict[str, Any]]]) -> Dict[tuple, Dict[str, Any]]:
        """[④ KG 뷰어] 학생이 입력한 성적이 있으면 recommend_universities()가 이미
        계산해주는 전형별 환산 결과를 (대학,캠퍼스,학과,전형명) 키로 재사용한다 -
        새 계산 로직을 만들지 않고 기존 엔진 결과를 그래프 노드에 얹기만 한다."""
        if not grades:
            return {}
        ranked = self.recommend_universities(grades)
        return {
            (r["university"], r.get("campus"), r["department"], r.get("track_name")): r
            for r in ranked
        }

    @staticmethod
    def _kg_track_title(score: Optional[Dict[str, Any]]) -> Optional[str]:
        """전형 노드에 마우스를 올렸을 때 보여줄 학생부 환산 요약 - 없으면 None(툴팁 생략)."""
        if not score:
            return None
        if score.get("calc_precision") == "not_applicable":
            return "이 전형은 학생부 성적을 반영하지 않습니다."
        pct = score.get("school_record_percentage")
        if pct is None:
            return None
        grade_eq = score.get("estimated_grade_equivalent")
        precision_note = "정밀 계산" if score.get("calc_precision") == "exact" else "근사 추정"
        grade_note = f" (원 석차등급 약 {grade_eq}등급)" if grade_eq is not None else ""
        return f"학생부 환산 {pct}점{grade_note} - {precision_note}"

    def get_kg_graph(self, university: Optional[str] = None,
                      grades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """[④ 인터랙티브 KG 뷰어] 대학-학과-전형 구조를 vis.js가 바로 그릴 수 있는
        {nodes, edges} 형태로 내보낸다. 새 비즈니스 로직이 아니라 이미 Neo4j에 있는
        관계를 그대로 노출하는 것뿐이다. university를 주면 그 학교(모든 캠퍼스)만
        반환해서 전체 그래프가 너무 커서 안 보이는 문제를 피한다. grades를 주면
        전형 노드에 학생부 환산 결과를 툴팁으로 얹는다(계산 로직은 recommend_universities
        재사용, 여기서 새로 계산하지 않음)."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                WHERE (t.is_superseded IS NULL OR t.is_superseded = false)
                  AND ($university IS NULL OR u.name = $university)
                RETURN u.name AS university, u.campus AS campus, d.name AS department,
                       t.name AS track_name, t.quota AS quota
                ORDER BY university, campus, department, track_name
            """, university=university).data()

        score_lookup = self._kg_score_lookup(grades)
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, str]] = []
        for r in rows:
            uni_label = r["university"] + (f" ({r['campus']}캠퍼스)" if r.get("campus") else "")
            uni_id = f"u::{uni_label}"
            dept_id = f"d::{uni_label}::{r['department']}"
            track_id = f"t::{dept_id}::{r['track_name']}"

            if uni_id not in nodes:
                nodes[uni_id] = {"id": uni_id, "label": uni_label, "group": "university"}
            if dept_id not in nodes:
                nodes[dept_id] = {"id": dept_id, "label": r["department"], "group": "department"}
                edges.append({"from": uni_id, "to": dept_id})
            if track_id not in nodes:
                quota = r.get("quota")
                track_label = r["track_name"] + (f" ({quota}명)" if quota else "")
                score = score_lookup.get((r["university"], r.get("campus"), r["department"], r["track_name"]))
                nodes[track_id] = {
                    "id": track_id, "label": track_label, "group": "track",
                    "title": self._kg_track_title(score),
                }
                edges.append({"from": dept_id, "to": track_id})

        return {"nodes": list(nodes.values()), "edges": edges}

    # [④ KG 뷰어 - 실기종목별 보기 전용] list_exam_topic_keywords()가 쓰는
    # _exam_keywords()는 "2글자 이상 한글이면 다 키워드"라 "문장을"/"사물의"/
    # "사진이미지를"처럼 조사가 붙은 서술형 문구까지 실기종목으로 잘못 뽑혔다
    # (사용자가 KG 뷰어 드롭다운에서 직접 확인). search_tracks_by_prep 등 다른
    # 화면의 매칭 로직까지 건드리면 영향 범위가 커지므로, KG 뷰어 전용으로
    # completeness_audit.py에서 이미 검증한 "실기 과목명다운 어미로 끝나는
    # 조각만 채택" 방식을 그대로 재사용한다 - 소묘/수채화/한국화/발상과표현처럼
    # 명사형 과목명만 남고, 서술형 문구는 자동으로 걸러진다.
    _KG_TOPIC_STOP_FRAGMENTS = {
        "고사", "당일", "제시", "제공", "사진", "이미지", "경우", "조건", "주제",
        "선택", "가능", "방법", "형식", "포함", "해당", "없음", "실기", "이하",
        "기준", "기재", "별도", "확인", "반영", "전용", "동일", "추정", "원문",
        "단계", "구술", "면접", "서류", "평가", "질의응답", "학생부", "정성평가",
    }
    _KG_TOPIC_SUFFIXES = ("화", "묘", "조", "형", "성형", "조형", "디자인", "표현", "만화", "서예", "그라피")
    _KG_TOPIC_SPLITTER = re.compile(r"택\s*\d|또는|중\s*택|위주|[·,/+()\[\]:;\-]")

    @classmethod
    def _kg_topic_fragments(cls, exam_name: str) -> set:
        fragments = set()
        for part in cls._KG_TOPIC_SPLITTER.split(exam_name or ""):
            p = part.strip()
            if not p or not (2 <= len(p) <= 10) or not re.fullmatch(r"[가-힣\s]+", p):
                continue
            p_nospace = p.replace(" ", "")
            if p_nospace in cls._KG_TOPIC_STOP_FRAGMENTS or not p_nospace.endswith(cls._KG_TOPIC_SUFFIXES):
                continue
            fragments.add(p_nospace)
        return fragments

    def list_kg_topic_keywords(self, min_schools: int = 2) -> List[str]:
        """[④ KG 뷰어 전용] "실기종목별 보기" 드롭다운에 넣을 명사형 과목명 목록.
        min_schools 미만으로만 등장하는 특정 학교 고유 표현은 큰 주제가 아니므로 뺀다."""
        rows = self.list_tracks_with_estimates()
        counts: Dict[str, int] = {}
        for r in rows:
            for kw in self._kg_topic_fragments(r.get("exam_type_name") or ""):
                counts[kw] = counts.get(kw, 0) + 1
        return sorted(kw for kw, cnt in counts.items() if cnt >= min_schools)

    def get_kg_graph_by_topic(self, topic_keyword: str,
                               grades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """[④ KG 뷰어 - 실기종목별 보기] 학교가 아니라 실기종목("소묘", "발상과표현" 등)을
        루트로 두고, 그 종목을 쓰는 대학/학과/전형을 모아 보여준다."""
        rows = self.list_tracks_with_estimates()
        score_lookup = self._kg_score_lookup(grades)
        topic_id = f"topic::{topic_keyword}"
        nodes: Dict[str, Dict[str, Any]] = {topic_id: {"id": topic_id, "label": topic_keyword, "group": "topic"}}
        edges: List[Dict[str, str]] = []
        for r in rows:
            exam_name = r.get("exam_type_name") or ""
            if topic_keyword not in self._kg_topic_fragments(exam_name):
                continue
            uni_label = r["university"] + (f" ({r['campus']}캠퍼스)" if r.get("campus") else "")
            uni_id = f"u::{uni_label}"
            dept_id = f"d::{uni_label}::{r['department']}"
            track_id = f"t::{dept_id}::{r.get('track_name')}"

            if uni_id not in nodes:
                nodes[uni_id] = {"id": uni_id, "label": uni_label, "group": "university"}
                edges.append({"from": topic_id, "to": uni_id})
            if dept_id not in nodes:
                nodes[dept_id] = {"id": dept_id, "label": r["department"], "group": "department"}
                edges.append({"from": uni_id, "to": dept_id})
            if track_id not in nodes:
                quota = r.get("quota")
                track_label = (r.get("track_name") or "") + (f" ({quota}명)" if quota else "")
                score = score_lookup.get((r["university"], r.get("campus"), r["department"], r.get("track_name")))
                nodes[track_id] = {
                    "id": track_id, "label": track_label, "group": "track",
                    "title": self._kg_track_title(score),
                }
                edges.append({"from": dept_id, "to": track_id})

        return {"nodes": list(nodes.values()), "edges": edges}

    # [④ KG 뷰어 - 전형종류별 보기] results.html의 specialAdmissionTags()가 쓰는
    # SPECIAL_ADMISSION_PATTERNS를 그대로 이식 - 학교마다 표기가 제각각인
    # "학교장추천"/"농어촌학생"류 특별전형을 공통 키워드로 묶는 판정을 화면
    # 두 곳(카드 필터 칩, KG 뷰어)에서 어긋나지 않게 유지한다.
    _TRACK_TYPE_PATTERNS = [
        ("학교장추천", re.compile(r"학교장추천")),
        ("농어촌학생", re.compile(r"농어촌(학생|출신)")),
        ("특수교육대상자", re.compile(r"특수교육대상자")),
        ("특성화고", re.compile(r"특성화고(교)?(졸업자|출신)?")),
        ("기회균형·사회통합", re.compile(r"기회균형|사회통합|고른기회|기초생활수급자")),
        ("지역인재", re.compile(r"지역인재")),
        ("가톨릭지도자추천", re.compile(r"가톨릭지도자")),
        ("재림교회목회자추천", re.compile(r"재림교회")),
        ("예체능인재", re.compile(r"예체능인재")),
        ("특기자", re.compile(r"특기자")),
    ]

    def list_track_type_categories(self) -> List[str]:
        """[④ KG 뷰어 전용] 지금 데이터에 실제로 존재하는 특별전형 종류만 드롭다운에 노출."""
        rows = self.list_all_tracks_full()
        present = set()
        for r in rows:
            name = r.get("track_name") or ""
            for key, pattern in self._TRACK_TYPE_PATTERNS:
                if pattern.search(name):
                    present.add(key)
        return sorted(present)

    def get_kg_graph_by_track_type(self, track_type: str,
                                    grades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """[④ KG 뷰어 - 전형종류별 보기] "학교장추천"/"농어촌학생" 같은 특별전형 종류를
        루트로 두고, 그 종류에 해당하는 대학/학과/전형을 모아 보여준다."""
        pattern = next((p for key, p in self._TRACK_TYPE_PATTERNS if key == track_type), None)
        if pattern is None:
            return {"nodes": [], "edges": []}
        rows = self.list_all_tracks_full()
        score_lookup = self._kg_score_lookup(grades)
        root_id = f"tracktype::{track_type}"
        nodes: Dict[str, Dict[str, Any]] = {root_id: {"id": root_id, "label": track_type, "group": "tracktype"}}
        edges: List[Dict[str, str]] = []
        for r in rows:
            track_name = r.get("track_name") or ""
            if not pattern.search(track_name):
                continue
            uni_label = r["university"] + (f" ({r['campus']}캠퍼스)" if r.get("campus") else "")
            uni_id = f"u::{uni_label}"
            dept_id = f"d::{uni_label}::{r['department']}"
            track_id = f"t::{dept_id}::{track_name}"

            if uni_id not in nodes:
                nodes[uni_id] = {"id": uni_id, "label": uni_label, "group": "university"}
                edges.append({"from": root_id, "to": uni_id})
            if dept_id not in nodes:
                nodes[dept_id] = {"id": dept_id, "label": r["department"], "group": "department"}
                edges.append({"from": uni_id, "to": dept_id})
            if track_id not in nodes:
                quota = r.get("quota")
                track_label = track_name + (f" ({quota}명)" if quota else "")
                score = score_lookup.get((r["university"], r.get("campus"), r["department"], track_name))
                nodes[track_id] = {
                    "id": track_id, "label": track_label, "group": "track",
                    "title": self._kg_track_title(score),
                }
                edges.append({"from": dept_id, "to": track_id})

        return {"nodes": list(nodes.values()), "edges": edges}

    # [④ KG 뷰어 - 전형 유형별 보기] results.html의 "전형 유형으로 좁히기" 셀렉트와
    # 동일한 축(실기/실적위주 · 서류전형(실기없음) · 학생부종합전형 · 학생부교과전형).
    # 위 "전형종류별 보기"(학교장추천 등 track_name 기반 특별전형)와는 완전히 다른
    # 분류 기준이므로 헷갈리지 않게 라벨을 명확히 구분한다.
    _ADMISSION_TYPE_LABELS = {
        "practical": "실기/실적위주전형",
        "portfolio": "서류전형(실기 없음)",
        "holistic": "학생부종합전형",
        "academic_record": "학생부교과전형",
    }

    def list_admission_type_categories(self) -> List[str]:
        """[④ KG 뷰어 전용] 지금 데이터에 실제로 존재하는 전형 유형 라벨만 노출."""
        rows = self.list_tracks_with_estimates()
        present = set()
        for r in rows:
            category = self._document_track_category(r.get("exam_type_name")) or "practical"
            present.add(self._ADMISSION_TYPE_LABELS[category])
        order = list(self._ADMISSION_TYPE_LABELS.values())
        return [label for label in order if label in present]

    def get_kg_graph_by_admission_type(self, admission_type_label: str,
                                        grades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """[④ KG 뷰어 - 전형 유형별 보기] "학생부교과전형"처럼 준비 방법이 근본적으로
        다른 유형(실기 유무·정성/정량 평가)을 루트로 두고 해당 대학/학과/전형을 모은다."""
        category = next((k for k, v in self._ADMISSION_TYPE_LABELS.items() if v == admission_type_label), None)
        if category is None:
            return {"nodes": [], "edges": []}
        rows = self.list_tracks_with_estimates()
        score_lookup = self._kg_score_lookup(grades)
        root_id = f"admissiontype::{admission_type_label}"
        nodes: Dict[str, Dict[str, Any]] = {root_id: {"id": root_id, "label": admission_type_label, "group": "admissiontype"}}
        edges: List[Dict[str, str]] = []
        for r in rows:
            row_category = self._document_track_category(r.get("exam_type_name")) or "practical"
            if row_category != category:
                continue
            uni_label = r["university"] + (f" ({r['campus']}캠퍼스)" if r.get("campus") else "")
            uni_id = f"u::{uni_label}"
            dept_id = f"d::{uni_label}::{r['department']}"
            track_id = f"t::{dept_id}::{r.get('track_name')}"

            if uni_id not in nodes:
                nodes[uni_id] = {"id": uni_id, "label": uni_label, "group": "university"}
                edges.append({"from": root_id, "to": uni_id})
            if dept_id not in nodes:
                nodes[dept_id] = {"id": dept_id, "label": r["department"], "group": "department"}
                edges.append({"from": uni_id, "to": dept_id})
            if track_id not in nodes:
                quota = r.get("quota")
                track_label = (r.get("track_name") or "") + (f" ({quota}명)" if quota else "")
                score = score_lookup.get((r["university"], r.get("campus"), r["department"], r.get("track_name")))
                nodes[track_id] = {
                    "id": track_id, "label": track_label, "group": "track",
                    "title": self._kg_track_title(score),
                }
                edges.append({"from": dept_id, "to": track_id})

        return {"nodes": list(nodes.values()), "edges": edges}

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
            _CATEGORY_LABELS = {
                "portfolio": "서류전형(실기 없음)",
                "holistic": "학생부종합전형",
                "academic_record": "학생부교과전형",
                None: "실기/실적위주전형",
            }
            for t in tracks:
                t["source_tier"] = _classify_source(t.get("source_url"))
                t["exam_dates"] = _extract_dates(t.get("exam_date"))
                # FO 카드 상단 태그용 - search_tracks_by_prep/build_llm_context와 동일한
                # _document_track_category() 판정을 그대로 재사용해서 판정이 세 곳에서
                # 어긋나지 않게 한다(오늘 build_llm_context 쪽에서 이 판정이 빠져 실기
                # 키워드 QA 매칭이 잘못됐던 것과 같은 종류의 불일치를 막기 위함).
                doc_category = self._document_track_category(t.get("exam_type_name"))
                t["track_category"] = doc_category or "practical"
                t["track_category_label"] = _CATEGORY_LABELS[doc_category]

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
                       t.practical_ratio_pct AS practical_ratio_pct,
                       t.school_record_ratio_pct AS school_record_ratio_pct,
                       t.csat_minimum_required AS csat_minimum_required,
                       t.school_record_rule_json AS school_record_rule_json,
                       t.school_record_status AS school_record_status,
                       t.school_record_status_note AS school_record_status_note,
                       t.gender_restriction AS gender_restriction,
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
            raw_rule = r.pop("school_record_rule_json", None)
            r["school_record_rule"] = json.loads(raw_rule) if raw_rule else None
        return rows

    def get_school_record_coverage(self) -> Dict[str, Any]:
        """grades.html 안내 문구용 - 특정 5개교를 하드코딩해서 적던 문구가 실제로는
        19개교로 늘어난 뒤에도 갱신 안 돼서 오래된 정보를 보여준 사고(2026-09-09
        사용자 실측 제보)가 있었다. 대학명을 다시 하드코딩하는 대신, 매번 실제
        데이터에서 개수를 세어 화면이 항상 최신 상태를 스스로 반영하게 한다."""
        tracks = self.list_all_tracks_full()
        exact_universities = {t["university"] for t in tracks if t.get("school_record_rule")}
        na_universities = {t["university"] for t in tracks if t.get("school_record_status") == "not_applicable"}
        all_universities = {t["university"] for t in tracks}
        return {
            "exact_school_count": len(exact_universities),
            "not_applicable_school_count": len(na_universities),
            "total_school_count": len(all_universities),
        }

    def _get_prior_year_results_by_track(self) -> Dict[tuple, Dict[str, Any]]:
        """전년도 등록자 성적 추정치(Admission_CutoffEstimate) 전용 조회 - list_all_tracks_full()과
        의도적으로 분리된 별도 쿼리다. list_all_tracks_full()은 official_facts만 반환한다고
        문서화돼 있는데(Zero-Mixing), 이 추정치는 대학 자체 CDN에 공개된 '전년도 입시결과'
        문서에서 뽑은 값이라 official_facts가 아니라 estimates 계열이다. 호출부(recommend_
        universities)에서 반드시 별도 키(prior_year_result)로 붙여서 절대 같은 카드에서
        공식 사실과 섞어 표시하지 않게 한다."""
        with self.driver.session(default_access_mode=READ_ACCESS) as s:
            rows = s.run("""
                MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)-[:HAS_TRACK]->(t:Admission_Track)
                      -[:ESTIMATED_CUTOFF]->(c:Admission_CutoffEstimate)
                WHERE c.prior_year_admission_year IS NOT NULL
                RETURN u.name AS university, u.campus AS campus, d.name AS department, t.name AS track_name,
                       c.prior_year_admission_year AS admission_year,
                       c.prior_year_competition_rate AS competition_rate,
                       c.prior_year_grade_typical AS school_record_grade_typical,
                       c.prior_year_grade_floor AS school_record_grade_floor,
                       c.prior_year_grade_stat_type AS grade_stat_type,
                       c.prior_year_fill_rate_pct AS fill_rate_pct,
                       c.prior_year_methodology_note AS methodology_note,
                       c.prior_year_source_url AS source_url,
                       c.prior_year_source_page AS source_page
            """).data()
        return {(r["university"], r.get("campus"), r["department"], r["track_name"]): r for r in rows}

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
    def _match_selected_track(tracks: List[Dict[str, Any]], sel: Dict[str, Any],
                               prefer_rule: bool = False) -> Optional[Dict[str, Any]]:
        """비교/일정/근거/성적계산 화면이 공유하는 전형 식별 로직.

        2026-09-09 사고: university+campus+department 조합이 "이 데이터셋 전체에서
        유일하다"는 예전 가정이 깨졌다 - 상명대 미술학부 조형예술전공처럼 같은 학과에
        실기전형과 학생부종합전형이 별도 트랙으로 공존하는 실제 사례가 생겼다(실기 없이
        학생부종합만 별도 카테고리로 추가하면서 노출됨). 그래서 sel에 track_name이
        오면 반드시 그것까지 일치하는 트랙을 우선 반환한다(비교/일정/근거 패널처럼
        "정확히 이 카드" 식별이 중요한 곳은 호출부가 반드시 track_name을 넘겨야 함).
        track_name이 없는 구버전 호출(성적 계산처럼 애초에 track_name 개념이 없던
        API)에서 후보가 여러 개면, prefer_rule=True인 경우 학생부 반영 규정
        (school_record_rule)이 있는 트랙을 우선한다 - "성적 계산"이라는 함수 목적상
        계산 가능한 트랙을 고르는 게 자연스러운 기본값이기 때문이다. 그래도 후보가
        여럿이면 마지막엔 그냥 첫 번째를 반환한다(기존 동작 유지)."""
        candidates = [
            t for t in tracks
            if t["university"] == sel.get("university") and t["department"] == sel.get("department")
            and (not sel.get("campus") or t.get("campus") == sel.get("campus"))
        ]
        if not candidates:
            return None
        track_name = sel.get("track_name")
        if track_name:
            exact = next((t for t in candidates if t.get("track_name") == track_name), None)
            if exact:
                return exact
        if prefer_rule:
            with_rule = next((t for t in candidates if t.get("school_record_rule")), None)
            if with_rule:
                return with_rule
        return candidates[0]

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
        # 홍익대 세종 자율전공(자연·예능)처럼 실기 자체가 없는 전형의 exam_type_name을
        # "해당 없음(학생부교과 100%, 실기 없음 - ...)"으로 서술했더니, "없음"이 우연히
        # 다른 학교 원문에도 등장해 실기종목 키워드로 잘못 잡혔다(전수조사로 발견).
        "없음", "해당",
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

    # 2026-09-09: "서류전형(실기 없음)만 보기"에 학생부종합전형(상명대 등)까지
    # 섞여서 나온다는 피드백 - 준비 방법이 완전히 다른 두 유형(미술 실적/포트폴리오
    # 제출이 핵심인 서류전형 vs 학생부+자소서를 종합평가하는 학생부종합전형)을
    # 하나로 묶으면 안 된다. 역시 실측 데이터에 실제로 등장하는 표현만 근거로
    # 판정한다 - 임의 카테고리 추정이 아니다.
    _ART_PORTFOLIO_MARKERS = ("미술활동보고서", "포트폴리오")
    _HOLISTIC_REVIEW_MARKERS = ("학생부종합",)
    # 2026-09-10: "학생부교과(교과우수자전형)"은 학생부종합과 다르다 - 정성평가가
    # 아니라 학생부 성적을 100% 정량 반영하는 전형이라, "실기 없는 전형" 안에서도
    # 준비 방법이 또 다르다(사용자 지적으로 별도 카테고리로 분리). 실측 데이터에
    # 실제 등장하는 표현("학생부교과 100%")만 근거로 판정한다.
    _ACADEMIC_RECORD_MARKERS = ("학생부교과",)

    @staticmethod
    def _document_track_category(exam_type_name: Optional[str]) -> Optional[str]:
        """실기 없는 전형을 준비 방법이 다른 세 갈래로 나눈다:
        "portfolio"(미술 실적/포트폴리오 제출), "holistic"(학생부종합 - 학생부+
        자소서 등 정성 종합평가), "academic_record"(학생부교과 - 학생부 성적
        100% 정량 반영, 정성평가 아님). 어느 표시어도 없이 "서류평가"만 있는
        경우는 과거 동작과 호환되게 portfolio로 취급한다(기존에 이런 케이스가
        전부 그렇게 분류돼 있었음)."""
        name = exam_type_name or ""
        if any(m in name for m in ArtAdmissionService._ART_PORTFOLIO_MARKERS):
            return "portfolio"
        if any(m in name for m in ArtAdmissionService._HOLISTIC_REVIEW_MARKERS):
            return "holistic"
        if any(m in name for m in ArtAdmissionService._ACADEMIC_RECORD_MARKERS):
            return "academic_record"
        if any(m in name for m in ArtAdmissionService._DOCUMENT_BASED_MARKERS):
            return "portfolio"
        return None

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
                               material_query: str = "", document_only: bool = False,
                               holistic_only: bool = False, academic_record_only: bool = False) -> List[Dict[str, Any]]:
        """수험생이 고른 '큰 주제'(실기종목 키워드)와 자유 검색한 재료 문구로
        겹치는 학교/학과를 찾는다. 재료는 200개+ 세부 항목이 있어 선택지 나열
        대신 부분일치 검색으로 처리한다 - 예를 들어 "연필"로 검색하면
        "소묘용 연필", "4B연필" 등을 전부 잡는다.
        document_only=True면 실기 없이 미술 실적/포트폴리오 제출로 평가받는
        전형만, holistic_only=True면 학생부종합(서류+면접, 실기·포트폴리오
        제출 없음) 전형만, academic_record_only=True면 학생부교과(학생부 성적
        100% 정량 반영, 정성평가 아님) 전형만 따로 보여준다 - 준비 방법이
        완전히 달라 같은 필터로 묶지 않는다(사용자 피드백).

        match_status로 반드시 분리한다 - 재료만 겹치는 걸 "실기종목 일치"
        라고 부르면 안 된다는 게 이 함수의 핵심 불변조건이다:
          - "exact"           : 선택한 실기종목 키워드가 전형의 실기유형과 실제로 겹침
          - "partial"         : 재료/규격만 겹치거나 일부 키워드만 겹침 (준비 내용 확인 필요)
          - "document"        : 실기 없이 미술 실적/포트폴리오로 평가 (document_only일 때만)
          - "holistic_review" : 실기·포트폴리오 없이 학생부종합으로 평가 (holistic_only일 때만)
          - "academic_record" : 실기 없이 학생부교과 100% 정량 반영으로 평가 (academic_record_only일 때만)
        """
        topic_set = set(topic_keywords or [])
        material_query = (material_query or "").strip()
        rows = self.list_tracks_with_estimates()
        results = []
        for r in rows:
            exam_name = r.get("exam_type_name") or ""
            doc_category = self._document_track_category(exam_name)
            is_doc = doc_category is not None
            if document_only:
                if doc_category != "portfolio":
                    continue
                results.append({
                    **r, "matched_keywords": [], "is_document_based": True,
                    "match_status": "document", "exact_match_reasons": [],
                    "partial_match_reasons": [], "warnings": [],
                })
                continue
            if holistic_only:
                if doc_category != "holistic":
                    continue
                results.append({
                    **r, "matched_keywords": [], "is_document_based": False, "is_holistic_review": True,
                    "match_status": "holistic_review", "exact_match_reasons": [],
                    "partial_match_reasons": [], "warnings": [],
                })
                continue
            if academic_record_only:
                if doc_category != "academic_record":
                    continue
                results.append({
                    **r, "matched_keywords": [], "is_document_based": False, "is_holistic_review": False,
                    "is_academic_record": True, "match_status": "academic_record",
                    "exact_match_reasons": [], "partial_match_reasons": [], "warnings": [],
                })
                continue
            if is_doc:
                continue  # 서류/학생부종합 전형은 재료/실기 키워드 비교 대상이 아니므로 일반 검색에서는 제외

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
            # search_tracks_by_prep과 동일하게, 서류/학생부종합/학생부교과 전형(is_doc)은
            # 실기 키워드 비교 대상이 아니므로 여기서도 제외한다 - 국민대 "포트폴리오 기반
            # 구술면접"(디자인학과·공예학과)처럼 exam_type_name에 우연히 실기 키워드
            # 문자열이 섞여 들어간 서류전형이 잘못 "실기유형 일치"로 잡히는 걸 막는다.
            "exam_type_keyword_match": (
                self._document_track_category(t.get("exam_type_name")) is None
                and bool(query_topic_kw & self._exam_keywords(t.get("exam_type_name") or ""))
            ),
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

    def calculate_school_record_score(self, university: str, department: str, grades: List[Dict[str, Any]],
                                       campus: Optional[str] = None, track_name: Optional[str] = None) -> Dict[str, Any]:
        """학생 성적(grades)을 특정 학교·학과의 실제 학생부 반영 규정(school_record_rule)
        그대로 환산한다. 원문에서 확인된 학교(school_record_coverage 참고)만
        정밀 계산이 가능하고, 나머지는 아직 반영교과/환산표를 확보 못 했으므로
        available=False로 명시한다 (없는 규정을 지어내지 않는다).
        track_name을 안 넘긴 호출(기존 grades.html 흐름)에서 같은 학과에 트랙이
        여러 개면(예: 상명대 미술학부 조형예술전공의 실기전형/학생부종합전형)
        _match_selected_track가 prefer_rule=True로 계산 가능한 쪽을 우선 고른다 -
        "성적 계산"이라는 이 함수의 목적상 자연스러운 기본값."""
        tracks = self.list_all_tracks_full()
        track = self._match_selected_track(
            tracks, {"university": university, "campus": campus, "department": department, "track_name": track_name},
            prefer_rule=True,
        )
        if not track:
            return {"available": False, "reason": f"'{university} {department}' 전형을 찾을 수 없습니다."}

        rule = track.get("school_record_rule")
        if track.get("school_record_status") == "not_applicable":
            return {
                "available": False,
                "not_applicable": True,
                "reason": track.get("school_record_status_note") or "이 전형은 학생부 성적을 반영하지 않습니다.",
                "university": university, "department": department,
                "practical_ratio_pct": track.get("practical_ratio_pct"),
                "school_record_ratio_pct": track.get("school_record_ratio_pct"),
            }
        if not rule:
            return {
                "available": False,
                "reason": "이 학교는 아직 학생부 반영 세부 규정(반영교과·석차등급 환산표)이 원문으로 확인되지 않아 "
                          "정밀 계산을 제공하지 않습니다. 실기/학생부 반영 비율만 참고하세요.",
                "university": university, "department": department,
                "practical_ratio_pct": track.get("practical_ratio_pct"),
                "school_record_ratio_pct": track.get("school_record_ratio_pct"),
            }

        calc = _calc_school_record_raw_score(rule, grades)
        if calc is None:
            return {
                "available": False,
                "reason": "입력하신 과목 중 이 학교의 반영교과에 해당하는(석차등급이 있는) 과목이 없습니다.",
                "university": university, "department": department,
            }

        raw_score, max_score = calc["raw_score"], calc.get("max_score")
        percentage = round(raw_score / max_score * 100, 2) if max_score else None
        return {
            "available": True,
            "university": university, "campus": track.get("campus"), "department": department,
            "track_name": track.get("track_name"),
            "raw_score": round(raw_score, 4),
            "max_score": max_score,
            "percentage": percentage,
            "estimated_grade_equivalent": calc.get("raw_grade_average"),
            "matched_subject_count": calc.get("matched_subject_count"),
            "missing_subject_groups": calc.get("missing_subject_groups"),
            "chosen_choice_subject": calc.get("chosen_choice_subject"),
            "practical_ratio_pct": track.get("practical_ratio_pct"),
            "school_record_ratio_pct": track.get("school_record_ratio_pct"),
            "csat_minimum_required": track.get("csat_minimum_required"),
            "formula_note": rule.get("formula_note"),
            "rule_source_page": rule.get("rule_source_page"),
            "source_url": track.get("source_url"),
            "data_tier": "OFFICIAL_RULE",
            "breakdown": calc.get("breakdown"),
        }

    def recommend_universities(self, grades: List[Dict[str, Any]],
                                topic_keywords: Optional[List[str]] = None,
                                material_query: str = "") -> List[Dict[str, Any]]:
        """성적 기반 대학/학과 추천. 학생부 반영 규정을 원문으로 확보한 5개교는
        calc_precision="exact"로 실제 환산점수를, 나머지는 "approximate"로 비율 기반
        근사치를 매겨 항상 구분해서 내려준다 - "합격 가능성"을 단정하지 않고, 학생부
        축의 상대적 유불리 정보만 제공한다 (실기 원점수는 알 수 없으므로 총점 확정 불가)."""
        tracks = self.list_all_tracks_full()
        prior_year_by_track = self._get_prior_year_results_by_track()

        if topic_keywords or material_query:
            prep_matches = self.search_tracks_by_prep(topic_keywords=topic_keywords, material_query=material_query or "")
            allowed_keys = {(r["university"], r.get("campus"), r["department"]) for r in prep_matches}
            tracks = [t for t in tracks if (t["university"], t.get("campus"), t["department"]) in allowed_keys]

        results = []
        for t in tracks:
            entry = {
                "university": t["university"], "campus": t.get("campus"), "department": t["department"],
                "track_name": t.get("track_name"),
                "practical_ratio_pct": t.get("practical_ratio_pct"),
                "school_record_ratio_pct": t.get("school_record_ratio_pct"),
                "csat_minimum_required": t.get("csat_minimum_required"),
                "gender_restriction": t.get("gender_restriction"),
                "source_url": t.get("source_url"),
                "exam_type_name": t.get("exam_type_name"),
                # 2026-09-09: 대학찾기 카드에는 있는데 성적추천 카드에는 빠져있던
                # 모집인원/재료/규격/일정 정보 - "이 정보가 중요하니 대학찾기와
                # 동일하게 나와야 한다"는 피드백 반영. list_all_tracks_full()이
                # 이미 만들어둔 값을 그대로 옮기기만 한다(새 쿼리 없음).
                "quota": t.get("quota"), "admission_year": t.get("admission_year"),
                "allowed_materials": t.get("allowed_materials"), "paper_size": t.get("paper_size"),
                "application_start": t.get("application_start"), "application_end": t.get("application_end"),
                "exam_dates": t.get("exam_dates"), "result_date": t.get("result_date"),
            }
            doc_category = self._document_track_category(t.get("exam_type_name"))
            entry["is_document_based"] = doc_category == "portfolio"
            entry["is_holistic_review"] = doc_category == "holistic"
            entry["is_academic_record"] = doc_category == "academic_record"
            rule = t.get("school_record_rule")
            if t.get("school_record_status") == "not_applicable":
                # 실기 100% 또는 학생부종합 정성평가라 애초에 "학생부 등급→점수 환산" 자체가
                # 존재하지 않는 전형이다. 이런 학교까지 비율 기반 근사치를 매기면 실제로는
                # 반영되지도 않는 성적을 반영되는 것처럼 보여주는 셈이라, approximate조차
                # 계산하지 않고 명시적으로 "해당 없음"만 반환한다(원문에서 직접 확인된 사실 -
                # RULE_INCOMPLETE와 다름, 나중에 규정이 "발견될" 여지가 없는 경우다).
                entry["calc_precision"] = "not_applicable"
                entry["school_record_percentage"] = None
                entry["data_tier"] = "NOT_APPLICABLE"
                entry["estimated_grade_equivalent"] = None
                entry["reason_summary"] = t.get("school_record_status_note") or "이 전형은 학생부 성적을 반영하지 않습니다."
            elif rule:
                calc = _calc_school_record_raw_score(rule, grades)
                if calc and calc.get("max_score"):
                    pct = round(calc["raw_score"] / calc["max_score"] * 100, 2)
                    entry["calc_precision"] = "exact"
                    entry["raw_score"] = round(calc["raw_score"], 4)
                    entry["max_score"] = calc["max_score"]
                    entry["school_record_percentage"] = pct
                    entry["formula_note"] = rule.get("formula_note")
                    entry["data_tier"] = "OFFICIAL_RULE"
                    entry["estimated_grade_equivalent"] = calc.get("raw_grade_average")
                    entry["reason_summary"] = _build_reason_summary(
                        rule, t.get("practical_ratio_pct"), t.get("school_record_ratio_pct"), t.get("ratio"),
                    )
                else:
                    entry["calc_precision"] = "exact"
                    entry["school_record_percentage"] = None
                    entry["note"] = "입력한 과목 중 이 학교의 반영 대상 과목이 없어 계산할 수 없습니다."
                    entry["data_tier"] = "OFFICIAL_RULE"
                    entry["estimated_grade_equivalent"] = None
                    entry["reason_summary"] = None
            else:
                entry["calc_precision"] = "approximate"
                entry["school_record_percentage"] = _approximate_school_record_score(grades)
                entry["data_tier"] = "APPROXIMATE_NOT_OFFICIAL"
                # 반영교과를 모르는 학교라 별도 배점표가 없다 - 입력한 전 과목(진로선택
                # 제외)의 원 석차등급 이수단위 가중평균을 그대로 참고등급으로 쓴다.
                entry["estimated_grade_equivalent"] = _raw_grade_avg([
                    (g.get("credit") or 1, g.get("grade")) for g in grades if not g.get("career_elective")
                ])
                entry["reason_summary"] = "반영교과·환산표가 원문으로 확인되지 않아 실기/학생부 반영 비율만으로 근사 추정한 결과입니다."

            # 전년도 등록자 성적 비교(estimates 계열 - official_facts와 분리된 별도 키로만
            # 붙인다. Zero-Mixing: 이 값은 "공식 반영 규정"이 아니라 대학 자체 CDN에 공개된
            # "전년도 입시결과" 문서에서 뽑은 참고 자료다).
            pyr = prior_year_by_track.get((t["university"], t.get("campus"), t["department"], t.get("track_name")))
            entry["prior_year_result"] = pyr
            entry["prior_year_tier"] = _prior_year_tier(entry.get("estimated_grade_equivalent"), pyr)
            entry["school_record_impact_score"] = _school_record_impact_score(rule, t.get("school_record_ratio_pct"))

            results.append(entry)

        # GOOD_FIT/CHECK 판정(사용자 확정 기준): "배점표 기준 환산 점수가 높다"가 아니라
        # "이 학생의 원 석차등급이 전년도 등록자보다 좋은가"로 판정한다 - 즉 prior_year_tier
        # 그대로 반영한다(다른 상대비교식을 별도로 만들지 않는다). 학교 간에 서로 비교해서
        # "이 학생이 상대적으로 어디서 잘 나오는지"를 보는 게 아니라, 그 학교 자체의 전년도
        # 등록자 기준으로 판단해야 의미가 있다(반영교과가 학교마다 달라 학교 간 원등급
        # 비교는 애초에 절대적 우열이 아니라 참고용일 뿐임).
        # REGISTRANT_TOP(전년도 등록자 평균보다 좋음) -> GOOD_FIT
        # REGISTRANT_MID/BELOW -> CHECK
        # NO_DATA(비교자료 없음) -> 판정 불가(None) - 자료가 없는데 판정을 매기면 안 됨
        for e in results:
            if e["calc_precision"] != "exact":
                e["fit_label"] = None
            elif e["prior_year_tier"] == "REGISTRANT_TOP":
                e["fit_label"] = "GOOD_FIT"
            elif e["prior_year_tier"] in ("REGISTRANT_MID", "REGISTRANT_BELOW"):
                e["fit_label"] = "CHECK"
            else:
                e["fit_label"] = None

        # 정렬 기준(사용자 설계 확정안 - 임의 가중치로 합친 "종합점수"는 만들지 않는다):
        # ① 기본 정렬 - 전년도 등록자 성적 대비 위치(4단계 버킷: REGISTRANT_TOP/MID/
        #    BELOW/NO_DATA). 같은 버킷 안에서만 아래 순서로 2차 정렬:
        #    1) 실기유형 일치 - topic_keywords/material_query가 주어지면 이미 그 필터링
        #       단계에서 걸러지므로 여기서는 별도 키가 필요 없다.
        #    2) 내신 실질영향이 낮은 학교 우선 (school_record_impact_score 오름차순 -
        #       값이 작을수록 등급 하나 차이의 총점 영향이 작다는 뜻).
        #    3) 실기비중이 높은 학교 우선 (practical_ratio_pct 내림차순).
        #    경쟁률·모집인원은 참고정보로만 노출하고 정렬에는 넣지 않는다(경쟁률이 낮다고
        #    합격이 쉬운 게 아니라는 게 사용자가 명시한 이유). 마지막 타이브레이커로만
        #    원 석차등급 오름차순을 남겨 정렬을 안정적으로 만든다(위 3개 기준이 전부
        #    동률/None인 극히 드문 경우에만 영향을 준다).
        # 정밀 계산(exact) -> 근사 추정(approximate) -> 해당 없음(not_applicable) 순서는
        # 그대로 유지 - not_applicable은 점수 자체가 없는 게 정상이므로 맨 뒤로 보내되
        # 목록에서 빼지는 않는다.
        _precision_rank = {"exact": 0, "approximate": 1, "not_applicable": 2}
        _tier_rank = {"REGISTRANT_TOP": 0, "REGISTRANT_MID": 1, "REGISTRANT_BELOW": 2, "NO_DATA": 3}
        results.sort(key=lambda e: (
            _precision_rank.get(e["calc_precision"], 3),
            _tier_rank.get(e["prior_year_tier"], 3),
            e["school_record_impact_score"] if e["school_record_impact_score"] is not None else float("inf"),
            -(e["practical_ratio_pct"] if e["practical_ratio_pct"] is not None else -1),
            e["estimated_grade_equivalent"] if e["estimated_grade_equivalent"] is not None else 99,
        ))
        return results

    def recommend_conflict_free_combo(self, grades: List[Dict[str, Any]],
                                       topic_keywords: Optional[List[str]] = None,
                                       material_query: str = "",
                                       max_count: int = 6) -> Dict[str, Any]:
        """수시 최대 지원 장수(max_count, 기본 6) 안에서 실기고사 날짜가 서로
        겹치지 않는 조합을 자동으로 골라준다. recommend_universities()가 이미
        만들어둔 적합도 순서(전년도 등록자 대비 위치 -> 내신영향 -> 실기비중)를
        그대로 신뢰해서, 그 순서대로 훑으며 지금까지 고른 학교들과 실기일이
        하나도 안 겹치면 담고, 겹치면 건너뛴다(그리디). 학교마다 반영교과가
        달라 학교 간 절대 서열을 매길 수 없으므로 "최적"은 이 적합도 순서
        기준이며, 최소 충돌·최대 개수를 보장하는 완전탐색은 하지 않는다
        (후보 수가 많지 않아 그리디로도 실용적인 조합이 나옴)."""
        ranked = self.recommend_universities(grades, topic_keywords=topic_keywords, material_query=material_query)
        chosen: List[Dict[str, Any]] = []
        skipped_due_to_conflict: List[Dict[str, Any]] = []
        for cand in ranked:
            if len(chosen) >= max_count:
                break
            cand_dates = set(cand.get("exam_dates") or [])
            conflict = None
            if cand_dates:
                for c in chosen:
                    if cand.get("admission_year") != c.get("admission_year"):
                        continue
                    shared = cand_dates & set(c.get("exam_dates") or [])
                    if shared:
                        conflict = {"with_university": c["university"], "with_department": c["department"], "date": sorted(shared)}
                        break
            if conflict:
                skipped_due_to_conflict.append({
                    "university": cand["university"], "campus": cand.get("campus"), "department": cand["department"],
                    "track_name": cand.get("track_name"), "conflict": conflict,
                })
                continue
            chosen.append(cand)
        return {
            "combo": chosen,
            "count": len(chosen),
            "max_count": max_count,
            "skipped_due_to_conflict": skipped_due_to_conflict[:20],
            "total_candidates_considered": len(ranked),
        }

    def simulate_practical_reversal(self, university: str, department: str, grades: List[Dict[str, Any]],
                                     campus: Optional[str] = None, track_name: Optional[str] = None) -> Dict[str, Any]:
        """"학생부가 약해도 실기 비중이 크면 뒤집을 수 있는가"에 답하기 위한 계산.
        실제 합격선(총점 커트라인)은 공식적으로 공개되지 않으므로 이를 추정하거나
        지어내지 않는다(Zero-Mixing) - 대신 반영비율 공식만으로 확정할 수 있는
        산술적 사실만 보여준다: 지금 학생부 환산 결과로 이미 확보한 총점 비중과,
        실기에서 0점~만점을 받았을 때 총점이 어디부터 어디까지 움직일 수 있는지의
        범위(하한·상한)다. "합격 가능성"이 아니라 "실기가 만회해줄 수 있는 폭"만
        정직하게 알려준다."""
        calc = self.calculate_school_record_score(university, department, grades, campus=campus, track_name=track_name)
        if not calc.get("available"):
            return {**calc, "reversal_available": False}

        school_weight = calc.get("school_record_ratio_pct")
        practical_weight = calc.get("practical_ratio_pct")
        if school_weight is None or practical_weight is None or calc.get("percentage") is None:
            return {
                **calc, "reversal_available": False,
                "reversal_reason": "이 전형의 학생부/실기 반영비율(%)이 확인되지 않아 뒤집기 시뮬레이션을 제공할 수 없습니다.",
            }

        my_school_contribution = round(calc["percentage"] * school_weight / 100, 2)
        composite_min = my_school_contribution
        composite_max = round(my_school_contribution + practical_weight, 2)
        return {
            **calc,
            "reversal_available": True,
            "school_weight_pct": school_weight,
            "practical_weight_pct": practical_weight,
            "my_school_contribution_pct": my_school_contribution,
            "composite_min_pct": composite_min,
            "composite_max_pct": composite_max,
            "practical_swing_pct": practical_weight,
            "reversal_note": (
                f"학생부 반영 결과, 총점(100% 기준) 중 이미 확보한 부분은 {my_school_contribution}%p입니다. "
                f"이 전형은 실기 비중이 {practical_weight}%라서, 실기 점수에 따라 최종 총점은 "
                f"최소 {composite_min}%p(실기 0점 가정)부터 최대 {composite_max}%p(실기 만점 가정)까지 움직일 수 있습니다. "
                "이는 반영비율만으로 계산한 산술적 범위이며 실제 합격선(다른 지원자들과의 상대 경쟁)을 의미하지 않습니다."
            ),
        }


# 2026-09-09 "입시 질문이 왜 이렇게 느리지" 실측으로 발견한 원인: API 엔드포인트마다,
# 그리고 에이전트의 도구 호출마다 매번 ArtAdmissionService()를 새로 만들고 있었다 -
# Neo4j Aura(클라우드, 리전 간 네트워크)로 매번 새 TLS 연결+인증 핸드셰이크를 하는
# 셈이라, 복합 질의 하나에 도구가 3~4번 불리면 그때마다 수백ms씩 연결 비용이
# 누적됐다. neo4j 드라이버는 원래 애플리케이션당 1개만 만들어 계속 재사용하도록
# 설계돼 있고(세션은 메서드 호출마다 만드는 게 정상, 드라이버 자체는 아님) 내부
# 커넥션 풀이 동시 요청도 안전하게 처리하므로, 요청/도구 호출마다 새로 만들 이유가
# 없다 - 프로세스 생애주기 동안 하나만 만들어 재사용한다.
_shared_service: Optional["ArtAdmissionService"] = None


def get_shared_service() -> "ArtAdmissionService":
    global _shared_service
    if _shared_service is None:
        _shared_service = ArtAdmissionService()
    return _shared_service
