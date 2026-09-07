# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] Streamlit 화면
================================================================================
- DART-Trace와 완전히 분리된 신규 서비스. app_dart_trace_dashboard.py 최상단의
  "서비스 선택" 스위치에서 진입한다 (DART-Trace 메뉴 로직에는 전혀 관여하지 않음).
- 핵심 원칙(DART-Trace와 동일): [공식 모집요강 사실] vs [추정치/후기]를
  화면에서 절대 같은 카드/표에 섞지 않는다. 항상 별도 섹션, 별도 색상.
================================================================================
"""

import sys
import os
import calendar
import datetime
from collections import defaultdict

sys.path.insert(0, os.path.abspath("내작업폴더"))

import streamlit as st
import pandas as pd
import plotly.express as px
from pyvis.network import Network
from services.art_admission_service import ArtAdmissionService
from services.art_admission_llm import get_available_models, answer_with_llm, review_document, chat_about_review, MODEL_PASSWORD


def _select_model_with_gate(models: list, key_prefix: str):
    """모델 선택 드롭다운 + gated 모델이면 비밀번호 입력을 요구한다.
    비밀번호가 한 번 맞으면 세션 내내(다른 탭 포함) 다시 안 물어본다.
    반환값: (선택된 모델 dict, 실제 사용 가능 여부: bool)."""
    labels = [f"{m['label']}" + ("" if m["available"] else " (API 키 없음)") for m in models]
    idx = st.selectbox("AI 모델 선택", range(len(models)), format_func=lambda i: labels[i], key=f"{key_prefix}_model_select")
    model = models[idx]

    if not model["gated"]:
        return model, model["available"]

    if st.session_state.get("model_gate_unlocked"):
        return model, model["available"]

    pw = st.text_input("🔒 비밀번호", type="password", key=f"{key_prefix}_model_pw")
    if pw:
        if pw == MODEL_PASSWORD:
            st.session_state.model_gate_unlocked = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return model, False

_EVENT_COLOR = {"원서접수": "#2563eb", "실기고사": "#dc2626", "합격발표": "#16a34a", "등록": "#9333ea"}
_SCHOOL_ABBR_LEN = 9  # 셀 안에 다 안 들어가니 학교명(+캠퍼스) 앞부분만 표시, 나머지는 ellipsis+툴팁


def _render_month_calendar(events: list, year: int, month: int, today: datetime.date) -> str:
    """익숙한 달(月) 그리드 형태의 달력 HTML을 만든다. 일요일 시작, 각 날짜 칸에
    해당일 이벤트(학교명+종류)를 색깔 태그로 표시한다."""
    by_date = defaultdict(list)
    for e in events:
        by_date[e["start"]].append(e)

    cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
    weeks = cal.monthdayscalendar(year, month)

    weekday_labels = ["일", "월", "화", "수", "목", "금", "토"]
    html = ["<table style='width:100%; border-collapse:collapse; table-layout:fixed;'>"]
    html.append("<tr>" + "".join(
        f"<th style='padding:4px; font-size:12px; color:#666; border-bottom:1px solid #ddd;'>{w}</th>"
        for w in weekday_labels
    ) + "</tr>")

    for week in weeks:
        html.append("<tr>")
        for day in week:
            if day == 0:
                html.append("<td style='border:1px solid #eee; height:90px; background:#fafafa;'></td>")
                continue
            date_obj = datetime.date(year, month, day)
            date_str = date_obj.isoformat()
            is_today = date_obj == today
            cell_style = "border:1px solid #eee; height:90px; vertical-align:top; padding:4px; font-size:11px;"
            if is_today:
                cell_style += "background:rgba(220,38,38,0.08); border:2px solid #dc2626;"
            day_num_style = "font-weight:bold; color:#dc2626;" if is_today else "font-weight:bold;"
            # 같은 대학·같은 이벤트유형(예: 가천대 4개 학과 원서접수)은 태그 하나로 묶는다.
            grouped = defaultdict(list)
            for e in by_date.get(date_str, []):
                univ = e["school"].split(" ")[0]
                grouped[(univ, e["event_type"])].append(e)

            tags = ""
            for (univ, event_type), es in sorted(grouped.items(), key=lambda kv: kv[0][1]):
                color = _EVENT_COLOR.get(event_type, "#666")
                school_short = univ[:_SCHOOL_ABBR_LEN]
                count_suffix = f" ({len(es)})" if len(es) > 1 else ""
                tooltip = "; ".join(f"{e['school']} - {e['detail']}" for e in es)
                tags += (
                    f"<div style='background:{color}; color:#fff; border-radius:3px; padding:1px 3px; "
                    f"margin-top:2px; font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' "
                    f"title='{tooltip}'>{school_short} {event_type}{count_suffix}</div>"
                )
            html.append(f"<td style='{cell_style}'><span style='{day_num_style}'>{day}</span>{tags}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "".join(html)


_GRAPH_NODE_COLOR = {
    "university": "#1d4ed8",
    "department": "#0891b2",
    "track": "#16a34a",
    "exam_type": "#d97706",
    "past_topic": "#7c3aed",
    "estimate": "#6b7280",
    "entity_university": "#1d4ed8",
    "entity_department": "#0891b2",
    "entity_exam_type": "#d97706",
    "entity_material": "#be123c",
    "entity_llm_new": "#16a34a",
    "entity_other": "#16a34a",
}
_GRAPH_NODE_SHAPE = {
    "university": "box",
    "department": "box",
    "track": "ellipse",
    "exam_type": "diamond",
    "past_topic": "dot",
    "estimate": "dot",
    "entity_university": "box",
    "entity_department": "box",
    "entity_exam_type": "diamond",
    "entity_material": "triangle",
    "entity_llm_new": "star",
    "entity_other": "star",
}


def _render_graph_html(nodes: list, edges: list) -> str:
    """지식그래프를 pyvis로 인터랙티브 네트워크 HTML로 만든다. 공식 사실 계열
    (university/department/track/exam_type/past_topic)은 파란~보라 계열,
    추정치(estimate)는 회색으로 완전히 다른 색을 써서 Zero-Mixing을 시각적으로도 지킨다."""
    net = Network(height="600px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    net.barnes_hut(gravity=-3000, spring_length=120)
    for n in nodes:
        net.add_node(
            n["id"], label=n["label"], title=n.get("title", n["label"]),
            color=_GRAPH_NODE_COLOR.get(n["kind"], "#94a3b8"),
            shape=_GRAPH_NODE_SHAPE.get(n["kind"], "dot"),
        )
    for e in edges:
        net.add_edge(e["from"], e["to"])
    return net.generate_html(notebook=False)


def render_art_admission_app():
    st.markdown("""
    <div style='text-align: center; padding: 10px 0;'>
        <span style='font-size: 40px;'>🎨</span>
        <h2 style='margin: 5px 0 0 0;'>미술 실기 입시 도우미</h2>
        <p style='font-size: 13px; color: #64748b;'>공식 모집요강 사실과 웹 추정치를 분리해서 보여주는 입시 정보 도구</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    svc = ArtAdmissionService()
    try:
        universities = svc.list_universities()

        page = st.radio(
            "📌 메뉴",
            ["🏫 학교/학과 목록", "🔍 학교 상세", "⚖️ 전형 비교", "📅 일정 캘린더", "🎯 동시지원 시뮬레이터",
             "📝 기출문제", "🚦 데이터 정합성", "💬 질의응답", "🖊️ 서류 AI 첨삭", "🕸️ 지식그래프 보기"],
            horizontal=True,
        )
        st.markdown("---")

        if page == "🏫 학교/학과 목록":
            st.subheader(f"등록된 학교 ({len(universities)}개)")
            if not universities:
                st.info("아직 적재된 데이터가 없습니다. 크롤링 결과가 준비되면 `00_Art_Admission_Graph_Loader.py`로 적재 후 여기에 표시됩니다.")
            else:
                material_kw = st.text_input("🔎 허용재료/규격/실기종목 키워드 검색 (예: 연필, 켄트지)", placeholder="비워두면 전체 표시")
                all_tracks = svc.list_all_tracks_full()
                filtered_universities = universities
                if material_kw.strip():
                    matched = svc.search_by_material(material_kw)
                    matched_names = {t["university"] for t in matched}
                    filtered_universities = [u for u in universities if u["university"] in matched_names]
                    st.caption(f"'{material_kw}' 검색 결과: {len(filtered_universities)}개 학교")

                by_univ_campus = {(t["university"], t.get("campus")): t for t in all_tracks}
                for u in filtered_universities:
                    t = by_univ_campus.get((u["university"], u.get("campus")), {})
                    dday = t.get("application_end_dday")
                    if dday is None:
                        dday_badge = ""
                    elif dday < 0:
                        dday_badge = "<span style='background:#6b7280;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;'>접수마감</span>"
                    elif dday == 0:
                        dday_badge = "<span style='background:#dc2626;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;'>D-DAY</span>"
                    else:
                        dday_badge = f"<span style='background:#dc2626;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;'>접수마감 D-{dday}</span>"
                    tier_badge = f"<span style='font-size:12px;color:#666;'>{t.get('source_tier', '')}</span>" if t else ""
                    with st.container():
                        st.markdown(f"**{u['display_name']}** {dday_badge}", unsafe_allow_html=True)
                        st.caption(f"학과: {', '.join(u['departments'])}")
                        if tier_badge:
                            st.markdown(tier_badge, unsafe_allow_html=True)
                        st.markdown("---")

        elif page == "🔍 학교 상세":
            display_to_key = {u["display_name"]: (u["university"], u.get("campus")) for u in universities}
            names = list(display_to_key.keys())
            if not names:
                st.info("아직 적재된 학교 데이터가 없습니다.")
            else:
                selected_display = st.selectbox("학교 선택", names)
                selected, selected_campus = display_to_key[selected_display]
                detail = svc.get_university_detail(selected, campus=selected_campus)

                st.markdown("### 🔒 공식 모집요강 사실")
                st.caption("아래 내용은 전부 공식 모집요강 원문에서 추출되었으며, 출처 링크가 함께 표시됩니다.")
                track_full_by_key = {
                    (t["department"], t["track_name"]): t for t in svc.list_all_tracks_full()
                    if t["university"] == selected and t.get("campus") == selected_campus
                }
                for t in detail["official_tracks"]:
                    full = track_full_by_key.get((t["department"], t["track_name"]), {})
                    dday = full.get("application_end_dday")
                    if dday is None:
                        dday_badge = ""
                    elif dday < 0:
                        dday_badge = "<span style='background:#6b7280;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;margin-left:6px;'>접수마감</span>"
                    else:
                        dday_badge = f"<span style='background:#dc2626;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;margin-left:6px;'>접수마감 D-{dday}</span>"
                    with st.container():
                        st.markdown(f"""
                        <div style='background: rgba(22,163,74,0.08); border: 1px solid rgba(22,163,74,0.3); border-radius: 8px; padding: 14px; margin-bottom: 10px;'>
                            <b>{t['department']} — {t['track_name']}</b>
                            <span style='background:#166534;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;margin-left:6px;'>{t.get('admission_year') or '학년도 미상'}학년도</span>{dday_badge}<br/>
                            모집인원: {t.get('quota') or '-'}명 | 반영비율: {t.get('ratio') or '-'}<br/>
                            실기종목: {t.get('exam_type_name') or '-'} | 허용재료: {', '.join(t.get('allowed_materials') or []) or '-'}
                            | 규격: {t.get('paper_size') or '-'} | 시험시간: {t.get('time_limit_minutes') or '-'}분<br/>
                            원서접수: {t.get('application_start') or '-'} ~ {t.get('application_end') or '-'}
                            | 실기고사일: {t.get('exam_date') or '-'} | 발표일: {t.get('result_date') or '-'}<br/>
                            등록(등록금납부): {t.get('registration_start') or '-'} ~ {t.get('registration_end') or '-'}<br/>
                            <span style='font-size:12px;color:#666;'>출처 신뢰도: {full.get('source_tier', '-')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        if t.get("source_url"):
                            st.link_button("📑 공식 출처 원문 바로가기", t["source_url"], key=f"src_{selected}_{t['department']}_{t['track_name']}")

                st.markdown("### ⚪ 추정치 / 후기 (비공식, 참고용)")
                st.caption("아래 내용은 공식 모집요강이 아닌 웹 검색·유튜브·입시업체 자료 기반 추정치입니다. 위 공식 사실과 절대 혼동하지 마세요.")
                for e in detail["estimates_by_track"]:
                    if e.get("cutoff_grade_estimate") is None and not any(iv.get("title") for iv in e.get("interviews", [])):
                        continue
                    st.markdown(f"""
                    <div style='background: rgba(100,116,139,0.08); border: 1px solid rgba(100,116,139,0.3); border-radius: 8px; padding: 14px; margin-bottom: 10px;'>
                        <b>{e['track_name']}</b><br/>
                        추정 합격 컷라인: {e.get('cutoff_grade_estimate') or '정보 없음'}
                    </div>
                    """, unsafe_allow_html=True)

        elif page == "⚖️ 전형 비교":
            st.markdown("### 📊 전형 나란히 비교표")
            st.caption("여러 학교 전형을 표 하나로 나란히 놓고 비교합니다. 전부 official_facts 원문 값 그대로입니다.")
            all_tracks_cmp = svc.list_all_tracks_full()
            cmp_options = [f"{t['university']} - {t['department']}" for t in all_tracks_cmp]
            cmp_labels = st.multiselect("비교할 전형 선택 (2개 이상 권장)", cmp_options, key="cmp_multiselect")
            if cmp_labels:
                selections = []
                for label in cmp_labels:
                    idx = cmp_options.index(label)
                    t = all_tracks_cmp[idx]
                    selections.append({"university": t["university"], "department": t["department"]})
                rows = svc.get_comparison_table(selections)
                if rows:
                    # 항목별로 행을 쌓아서 만듦 (학교가 열, 항목이 행)
                    cols = {f"{r['university']}\n{r['department']}": r for r in rows}
                    field_labels = [
                        ("admission_year", "학년도"), ("quota", "모집인원"), ("ratio", "반영비율"),
                        ("exam_type_name", "실기종목"), ("paper_size", "규격"), ("time_limit_minutes", "시험시간(분)"),
                        ("application_start", "원서접수 시작"), ("application_end", "원서접수 마감"),
                        ("exam_date_raw", "실기고사일"), ("result_date", "발표일"),
                        ("registration_start", "등록 시작"), ("registration_end", "등록 마감"),
                        ("source_tier", "출처신뢰도"),
                    ]
                    table_data = {}
                    for col_name, r in cols.items():
                        table_data[col_name] = [r.get(key) for key, _ in field_labels]
                    df = pd.DataFrame(table_data, index=[label for _, label in field_labels])
                    st.dataframe(df, use_container_width=True)
                    for r in rows:
                        if r.get("source_url"):
                            st.link_button(f"📑 {r['university']} 출처", r["source_url"], key=f"cmp_src_{r['university']}_{r['department']}")

            st.markdown("---")
            st.markdown("### 🚨 실기고사일 충돌 자동 감지")
            st.caption("적재된 전형들의 실기고사일(공식 사실)만 비교합니다. 날짜는 원문 요강에서 정규식으로 그대로 추출한 값이며 추정하지 않습니다.")
            conflicts = svc.detect_schedule_conflicts()
            if not conflicts:
                st.success("현재 적재된 전형 중 실기고사일이 겹치는 조합이 없습니다.")
            else:
                for c in conflicts:
                    st.warning(
                        f"**{c.get('admission_year') or '학년도 미상'}학년도 {', '.join(c['date'])}** 에 겹침: "
                        f"{c['school_a']['university']} {c['school_a']['department']} ↔ "
                        f"{c['school_b']['university']} {c['school_b']['department']}"
                    )

            st.markdown("---")
            st.markdown("### 🔗 실기유형 호환 매칭")
            st.caption("실기종목명·허용재료가 겹치는 다른 학교 전형을 찾습니다 (키워드/재료 완전일치 기준, 유사도 추정 아님).")
            all_tracks = svc.list_all_tracks_full()
            options = [f"{t['university']} - {t['department']} ({t.get('admission_year') or '학년도 미상'}학년도)" for t in all_tracks]
            if options:
                selected_label = st.selectbox("기준 전형 선택", options)
                idx = options.index(selected_label)
                base = all_tracks[idx]
                matches = svc.find_compatible_tracks(base["university"], base["department"])
                if not matches:
                    st.info("호환되는 다른 전형을 찾지 못했습니다 (적재된 데이터 범위 내).")
                else:
                    for m in matches:
                        st.markdown(f"""
                        <div style='background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.3); border-radius: 8px; padding: 12px; margin-bottom: 8px;'>
                            <b>{m['university']} {m['department']}</b> ({m['track_name']}, {m.get('admission_year') or '학년도 미상'}학년도)<br/>
                            공통 실기유형 키워드: {', '.join(m['shared_keywords']) or '-'} | 공통 허용재료: {', '.join(m['shared_materials']) or '-'}
                        </div>
                        """, unsafe_allow_html=True)

        elif page == "📅 일정 캘린더":
            st.markdown("### 📅 전체 학교 일정 캘린더 (한눈에 보기)")
            st.caption("원서접수 시작일·실기고사일·합격발표일을 달력 위에 그대로 표시합니다. 오늘 날짜 칸은 빨간 테두리로 강조됩니다.")
            events = svc.get_calendar_events()
            if not events:
                st.info("적재된 일정이 없습니다.")
            else:
                # 원서접수/등록 기간은 시작~끝 매일 표시 (달력에서는 막대가 아니라 날짜별 태그이므로 기간 전체를 펼쳐야 함)
                expanded_events = []
                for e in events:
                    if e["event_type"] in ("원서접수", "등록"):
                        start = datetime.date.fromisoformat(e["start"])
                        end = datetime.date.fromisoformat(e["end"])
                        d = start
                        while d <= end:
                            expanded_events.append({**e, "start": d.isoformat()})
                            d += datetime.timedelta(days=1)
                    else:
                        expanded_events.append(e)

                today = datetime.date.today()
                all_dates = [datetime.date.fromisoformat(e["start"]) for e in expanded_events]
                months = sorted({(d.year, d.month) for d in all_dates})
                month_labels = [f"{y}년 {m}월" for y, m in months]
                default_idx = 0
                for i, (y, m) in enumerate(months):
                    if (y, m) == (today.year, today.month):
                        default_idx = i
                        break

                if st.session_state.get("cal_month_select") not in month_labels:
                    st.session_state.cal_month_select = month_labels[default_idx]
                current_idx = month_labels.index(st.session_state.cal_month_select)

                col_prev, col_sel, col_next = st.columns([1, 3, 1])
                with col_prev:
                    if st.button("◀ 이전달", use_container_width=True, disabled=current_idx <= 0):
                        st.session_state.cal_month_select = month_labels[current_idx - 1]
                        st.rerun()
                with col_next:
                    if st.button("다음달 ▶", use_container_width=True, disabled=current_idx >= len(months) - 1):
                        st.session_state.cal_month_select = month_labels[current_idx + 1]
                        st.rerun()
                with col_sel:
                    selected_month_label = st.selectbox("월 선택", month_labels, key="cal_month_select")
                sel_year, sel_month = months[month_labels.index(selected_month_label)]

                legend = " ".join(
                    f"<span style='background:{color};color:#fff;border-radius:3px;padding:2px 6px;font-size:12px;margin-right:6px;'>{name}</span>"
                    for name, color in _EVENT_COLOR.items()
                )
                st.markdown(legend, unsafe_allow_html=True)
                st.markdown(_render_month_calendar(expanded_events, sel_year, sel_month, today), unsafe_allow_html=True)
                st.caption(f"기준일(오늘): {today.isoformat()} | 태그에 마우스를 올리면 학교명·전형 상세가 표시됩니다.")

        elif page == "🎯 동시지원 시뮬레이터":
            st.markdown("### 🎯 다중 학교 동시지원 시뮬레이터")
            st.caption("수시는 최대 6개교까지 지원 가능합니다. 선택한 조합 안에서만 일정 충돌을 검사합니다 (학년도 다른 전형은 비교 대상에서 자동 제외).")
            all_tracks = svc.list_all_tracks_full()
            options = [f"{t['university']} - {t['department']}" for t in all_tracks]
            if not options:
                st.info("아직 적재된 전형이 없습니다.")
            else:
                selected_labels = st.multiselect("지원 희망 전형 선택 (최대 6개)", options)
                if selected_labels:
                    selections = []
                    for label in selected_labels:
                        idx = options.index(label)
                        t = all_tracks[idx]
                        selections.append({"university": t["university"], "department": t["department"]})
                    result = svc.simulate_multi_apply(selections)
                    if result["conflicts"] or result["over_limit"]:
                        st.error(f"**판정: {result['verdict']}**")
                    else:
                        st.success(f"**판정: {result['verdict']}**")
                    st.caption(f"선택 {len(selected_labels)}개교 (최대 6개교)")
                    for c in result["conflicts"]:
                        st.warning(f"{', '.join(c['date'])} 겹침: {c['a']} ↔ {c['b']}")

        elif page == "📝 기출문제":
            st.markdown("### 📝 실기고사 기출문제 (원문 그대로, 출처 포함)")
            st.caption("모두 공식 모집요강 원문에서 발췌한 내용입니다.")
            names = ["전체"] + sorted({u["university"] for u in universities})
            selected_school = st.selectbox("학교 선택", names)
            topics = svc.get_past_topics(university=None if selected_school == "전체" else selected_school)
            if not topics:
                st.info("적재된 기출문제가 없습니다.")
            else:
                for p in topics:
                    with st.container():
                        st.markdown(f"""
                        <div style='background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.3); border-radius: 8px; padding: 14px; margin-bottom: 10px;'>
                            <b>{p['university']} {p['department']} - {p['track_name']}</b>
                            <span style='background:#4338ca;color:#fff;border-radius:4px;padding:2px 6px;font-size:12px;margin-left:6px;'>{p.get('year') or '-'}학년도</span><br/>
                            <span style='font-size:12px;color:#666;'>실기종목: {p.get('exam_type_name') or '-'} | 출처유형: {p.get('source') or '-'}</span><br/>
                            {p.get('topic_text') or ''}
                        </div>
                        """, unsafe_allow_html=True)
                        if p.get("source_url"):
                            st.link_button("📑 출처 원문 바로가기", p["source_url"], key=f"topic_{p['university']}_{p['department']}_{p['track_name']}_{p.get('year')}_{p['topic_text'][:20]}")

        elif page == "🚦 데이터 정합성":
            st.markdown("### 🚦 데이터 정합성 자가진단")
            st.caption("2026-09-07 '학년도 뒤섞임' 사고 재발 방지를 위한 자동 점검입니다. 사람이 매번 원문을 재대조하지 않아도 이 화면이 이상 징후를 자동으로 잡아냅니다.")
            issues = svc.check_data_integrity()
            if not issues:
                st.success("이상 없음 - 전체 전형이 admission_year·source_url을 모두 갖추고 있고, 학년도도 서로 일치합니다.")
            else:
                critical = [i for i in issues if i["level"] == "CRITICAL"]
                warning = [i for i in issues if i["level"] == "WARNING"]
                info = [i for i in issues if i["level"] == "INFO"]
                if critical:
                    st.error(f"🔴 CRITICAL {len(critical)}건")
                    for i in critical:
                        st.markdown(f"- **{i['track']}**: {i['issue']}")
                if warning:
                    st.warning(f"🟡 WARNING {len(warning)}건")
                    for i in warning:
                        st.markdown(f"- **{i['track']}**: {i['issue']}")
                if info:
                    st.info(f"ℹ️ INFO {len(info)}건 (정상 참고사항)")
                    for i in info:
                        st.markdown(f"- **{i['track']}**: {i['issue']}")

        elif page == "💬 질의응답":
            st.markdown("### 💬 질의응답")
            st.caption("학교명을 포함하거나 '일정 충돌', '호환' 같은 키워드로 질문하세요. 규칙기반 답변은 항상 그래프 사실만으로 나오고, AI 답변은 그 같은 사실만 근거로 자연어로 다시 풀어줍니다 (없는 값은 지어내지 않도록 프롬프트로 제한).")
            query = st.text_input("질문 입력", placeholder="예: 한예종 알려줘 / 일정 충돌 있어? / 중앙대학교 호환되는 학교 있어?")

            selected_model, model_usable = _select_model_with_gate(get_available_models(), key_prefix="qa")

            if query:
                result = svc.answer_question(query)
                st.markdown("#### 🔒 규칙기반 답변 (LLM 미사용)")
                st.markdown(f"**[의도 분류: {result['intent']}]**")
                st.markdown(result["answer"].replace("\n", "  \n"))
                if result.get("source_url"):
                    st.link_button("📑 근거 원문 바로가기", result["source_url"], key="qa_rule_src")

                st.markdown("---")
                st.markdown("#### 🤖 AI 답변")
                if not selected_model["available"]:
                    st.warning(f"'{selected_model['label']}'는 API 키가 설정되어 있지 않아 사용할 수 없습니다. 위 규칙기반 답변을 참고해주세요.")
                elif not model_usable:
                    st.info("비밀번호를 입력하면 이 모델로 답변을 생성합니다.")
                else:
                    with st.spinner("AI가 그래프 사실 + 원문 검색(하이브리드+재순위화) + 개체 그래프 연관 정보를 보고 답변을 작성 중입니다..."):
                        context_tracks, context_estimates = svc.build_llm_context(query)
                        try:
                            context_raw = svc.hybrid_search(query, top_k=5)
                        except Exception:
                            context_raw = []  # 벡터/풀텍스트 인덱스가 아직 없거나 임베딩 실패 시 구조화 사실만으로 답변
                        anchor_names = [t["university"] for t in context_tracks]
                        exclude_names = anchor_names + [t["department"] for t in context_tracks]
                        try:
                            context_graph_related = svc.get_graph_related_context(
                                query, anchor_names=anchor_names, exclude_names=exclude_names, top_n=5,
                            )
                        except Exception:
                            context_graph_related = []
                        try:
                            context_compatible = svc.get_compatible_tracks_for_query(query)
                        except Exception:
                            context_compatible = []
                        llm_result = answer_with_llm(
                            context_tracks, context_estimates, query,
                            model_id=selected_model["id"], context_raw_excerpts=context_raw,
                            context_graph_related=context_graph_related,
                            context_compatible_tracks=context_compatible,
                        )
                    st.markdown(llm_result["answer"].replace("\n", "  \n"))
                    if llm_result.get("grounded_on"):
                        st.caption(f"근거로 사용: {', '.join(llm_result['grounded_on'])}")
                    if context_graph_related:
                        related_str = ", ".join(f"{r['name']}({r['community_label']})" if r["community_label"] else r["name"] for r in context_graph_related)
                        st.caption(f"🕸️ 그래프 연관 정보(참고용, 사실 근거 아님): {related_str}")
                    if context_compatible:
                        with st.expander(f"🎯 실기유형/재료 키워드 호환학교 {len(context_compatible)}건 (구조화 데이터, 근거로 사용됨)"):
                            for m in context_compatible:
                                st.markdown(
                                    f"- **{m['university']} {m['department']}** ({m.get('exam_type_name')}): "
                                    f"공통 실기 키워드 {m['shared_keywords'] or '-'}, 공통 재료 키워드 {m['shared_materials'] or '-'}"
                                )
                    if context_raw:
                        with st.expander(f"🔎 원문 검색 결과 {len(context_raw)}건 (하이브리드 검색 + AI 재순위화, 참고용)"):
                            for r in context_raw:
                                rerank = r.get("rerank_score")
                                score_label = f"재순위화 점수 {rerank}/10" if rerank is not None else f"융합점수 {r.get('fusion_score', 0):.2f}"
                                st.markdown(
                                    f"**{r['university']}** ({r.get('admission_year') or '?'}학년도, "
                                    f"p.{r.get('page_start')}-{r.get('page_end')}, {score_label})"
                                )
                                st.caption(r["text"][:400] + ("..." if len(r["text"]) > 400 else ""))

        elif page == "🖊️ 서류 AI 첨삭":
            st.markdown("### 🖊️ 서류/자소서 AI 첨삭")
            st.markdown(
                "<div style='background:rgba(100,116,139,0.1); border:1px solid rgba(100,116,139,0.3); "
                "border-radius:8px; padding:10px; font-size:13px;'>"
                "⚪ <b>AI 추정 의견입니다 - 공식 평가/합격 가능성 판정이 아닙니다.</b> "
                "홍익대 미술활동보고서, 계원예대 포트폴리오 설명 등 실기 없이 서류로 평가받는 전형을 "
                "준비할 때 글쓰기 관점의 참고용 피드백만 제공합니다."
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            univ_labels = ["학교 미선택 (일반 첨삭)"] + [u["display_name"] for u in universities]
            univ_choice = st.selectbox(
                "지원 학교 선택 (학교마다 분량 제한·블라인드 평가·표절 금지 등 서류 규정이 다릅니다)",
                univ_labels,
            )
            selected_university = None
            if univ_choice != "학교 미선택 (일반 첨삭)":
                display_to_univ = {u["display_name"]: u["university"] for u in universities}
                selected_university = display_to_univ[univ_choice]

            doc_type = st.selectbox("문서 종류", ["자기소개서", "미술활동보고서", "포트폴리오 설명글", "기타 서류"])

            selected_model2, model2_usable = _select_model_with_gate(get_available_models(), key_prefix="review")

            uploaded = st.file_uploader("문서 파일 첨부 (.txt, .pdf)", type=["txt", "pdf"])
            pasted_text = st.text_area("또는 텍스트를 직접 붙여넣으세요", height=200)

            doc_text = ""
            if uploaded is not None:
                if uploaded.name.lower().endswith(".pdf"):
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(uploaded)
                        doc_text = "\n".join((p.extract_text() or "") for p in reader.pages)
                    except Exception as e:
                        st.error(f"PDF 텍스트 추출 실패: {e}")
                else:
                    doc_text = uploaded.read().decode("utf-8", errors="ignore")
            elif pasted_text.strip():
                doc_text = pasted_text

            if st.button("AI 첨삭 받기", disabled=not doc_text.strip()):
                if not selected_model2["available"]:
                    st.warning(f"'{selected_model2['label']}'는 API 키가 설정되어 있지 않아 사용할 수 없습니다. 다른 모델을 선택해주세요.")
                elif not model2_usable:
                    st.warning("이 모델은 비밀번호를 맞춰야 사용할 수 있습니다.")
                else:
                    with st.spinner("AI가 개체 그래프 + 학교별 서류 규정 원문을 확인하며 첨삭 중입니다..."):
                        try:
                            graph_hint = svc.detect_entities_in_text(doc_text)
                        except Exception:
                            graph_hint = []
                        doc_rules = []
                        if selected_university:
                            try:
                                doc_rules = svc.get_document_rule_excerpts(selected_university, doc_type)
                            except Exception:
                                doc_rules = []
                        review = review_document(
                            doc_text, model_id=selected_model2["id"], doc_type=doc_type, graph_hint=graph_hint,
                            university=selected_university, context_doc_rules=doc_rules,
                        )
                    if review.get("error"):
                        st.error(review["feedback"])
                    else:
                        # 새로 첨삭을 받으면 이전 대화는 초기화하고 새 대화를 시작한다.
                        st.session_state.review_doc_text = doc_text
                        st.session_state.review_doc_type = doc_type
                        st.session_state.review_model_id = selected_model2["id"]
                        st.session_state.review_history = [{"role": "assistant", "content": review["feedback"]}]
                        if graph_hint:
                            labels = sorted({h["community_label"] for h in graph_hint if h.get("community_label")})
                            st.caption(f"🕸️ 감지된 계열(참고용): {', '.join(labels) if labels else '(라벨 없음)'} "
                                       f"— 언급 개체: {', '.join(h['name'] for h in graph_hint)}")
                        if selected_university:
                            if doc_rules:
                                st.caption(f"📄 {selected_university}의 서류 규정 원문 {len(doc_rules)}건을 근거로 첨삭에 반영했습니다.")
                            else:
                                st.caption(f"⚠️ {selected_university}의 서류 규정 원문을 색인에서 찾지 못해 일반 글쓰기 관점으로만 첨삭했습니다.")

            # 첫 첨삭 이후에는 이 대화 스레드가 계속 화면에 남아 이어서 물어볼 수 있다.
            if st.session_state.get("review_history"):
                st.markdown("---")
                st.markdown("#### 💬 AI와 대화로 첨삭 보완하기")
                for turn in st.session_state.review_history:
                    with st.chat_message("assistant" if turn["role"] == "assistant" else "user"):
                        st.markdown(turn["content"].replace("\n", "  \n"))

                followup = st.chat_input("첨삭에 대해 궁금한 점이나 수정한 글을 입력하세요")
                if followup:
                    st.session_state.review_history.append({"role": "user", "content": followup})
                    with st.chat_message("user"):
                        st.markdown(followup)
                    with st.chat_message("assistant"):
                        with st.spinner("AI가 답변 중입니다..."):
                            chat_result = chat_about_review(
                                st.session_state.review_doc_text,
                                st.session_state.review_doc_type,
                                st.session_state.review_history,
                                model_id=st.session_state.review_model_id,
                            )
                        st.markdown(chat_result["reply" if not chat_result.get("error") else "reply"].replace("\n", "  \n"))
                    st.session_state.review_history.append({"role": "assistant", "content": chat_result["reply"]})

                if st.button("🔄 새 대화 시작 (기존 첨삭 지우기)"):
                    st.session_state.review_history = []
                    st.rerun()

        else:  # 🕸️ 지식그래프 보기
            st.markdown("### 🕸️ 지식그래프 보기")
            view = st.radio("보기 종류", ["구조 그래프 (공식사실/추정치)", "LLM 개체 추출 그래프 (구조화 추출+PageRank/커뮤니티)"], horizontal=True)

            if view == "구조 그래프 (공식사실/추정치)":
                st.caption(
                    "University → Department → Track → ExamType → PastTopic (공식 사실, 파랑~보라 계열)과 "
                    "Track → CutoffEstimate (추정치, 회색)를 색으로 분리해서 보여줍니다. "
                    "점/노드를 드래그하거나 확대해서 관계를 직접 확인할 수 있습니다."
                )
                display_to_key_g = {u["display_name"]: (u["university"], u.get("campus")) for u in universities}
                scope_labels = ["전체"] + list(display_to_key_g.keys())
                scope = st.selectbox("범위 선택", scope_labels)

                if scope == "전체":
                    graph = svc.get_graph_view()
                else:
                    g_univ, g_campus = display_to_key_g[scope]
                    graph = svc.get_graph_view(university=g_univ, campus=g_campus)

                if not graph["nodes"]:
                    st.info("표시할 그래프 데이터가 없습니다.")
                else:
                    st.caption(f"노드 {len(graph['nodes'])}개 · 관계 {len(graph['edges'])}개")
                    html = _render_graph_html(graph["nodes"], graph["edges"])
                    st.components.v1.html(html, height=620, scrolling=True)

            else:  # LLM 개체 추출 그래프
                st.markdown(
                    "<div style='background:rgba(37,99,235,0.08); border:1px solid rgba(37,99,235,0.3); "
                    "border-radius:8px; padding:10px; font-size:13px;'>"
                    "🔵 <b>LLM 구조화 추출로 만든 그래프입니다.</b> 문자열이 겹친다고 무조건 연결하지 않고, "
                    "① LLM이 문맥을 보고 개체를 뽑고 → ② 뽑힌 표현이 실제 원문에 그대로 있는지 검증하고 "
                    "→ ③ 신뢰도 0.5 미만은 버리는 3단계를 거칩니다. 🆕 표시는 학교 모집요강에는 없던, "
                    "LLM이 원문에서 새로 찾아낸 개체(사전 매칭만으로는 놓쳤을 것들)입니다."
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.caption("점 크기·PageRank가 높을수록 다른 개체와 자주 같은 문서 조각(청크)에 동시 등장한 개체입니다. 색 = 커뮤니티(자동 군집, LLM이 붙인 한글 라벨 포함).")

                min_weight = st.slider("동시출현 최소 횟수(엣지 필터)", 1, 10, 1)
                egraph = svc.get_entity_graph_view(min_weight=min_weight)
                if not egraph["nodes"]:
                    st.info("개체 추출 그래프가 아직 없습니다. 내작업폴더/02_Art_Admission_Entity_Linker.py --commit 을 먼저 실행하세요.")
                else:
                    st.caption(f"개체 {len(egraph['nodes'])}개 · 동시출현 관계 {len(egraph['edges'])}개")
                    html = _render_graph_html(egraph["nodes"], egraph["edges"])
                    st.components.v1.html(html, height=620, scrolling=True)

                st.markdown("#### 🆕 사전에 없던, LLM이 새로 찾아낸 개체 Top 10")
                st.caption("모집요강 구조화 데이터(대학/학과/실기종목/재료)에는 없지만, PDF 원문에서 LLM이 문맥으로 찾아낸 개체입니다.")
                mismatches = svc.get_entity_mismatch_candidates(top_n=10)
                if mismatches:
                    df_mismatch = pd.DataFrame(mismatches)
                    st.dataframe(df_mismatch, use_container_width=True)
                else:
                    st.info("데이터 없음 - 개체 추출기를 먼저 실행하세요.")

    finally:
        svc.close()
