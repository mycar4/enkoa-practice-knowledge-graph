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
from services.art_admission_service import ArtAdmissionService

_EVENT_COLOR = {"원서접수": "#2563eb", "실기고사": "#dc2626", "합격발표": "#16a34a"}
_SCHOOL_ABBR_LEN = 6  # 셀 안에 다 안 들어가니 학교명 앞부분만 표시


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
            tags = ""
            for e in sorted(by_date.get(date_str, []), key=lambda x: x["event_type"]):
                color = _EVENT_COLOR.get(e["event_type"], "#666")
                school_short = e["school"].split(" ")[0][:_SCHOOL_ABBR_LEN]
                tags += (
                    f"<div style='background:{color}; color:#fff; border-radius:3px; padding:1px 3px; "
                    f"margin-top:2px; font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' "
                    f"title='{e['school']} - {e['detail']}'>{school_short} {e['event_type']}</div>"
                )
            html.append(f"<td style='{cell_style}'><span style='{day_num_style}'>{day}</span>{tags}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "".join(html)


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
             "📝 기출문제", "🚦 데이터 정합성", "💬 질의응답"],
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

                by_univ = {t["university"]: t for t in all_tracks}
                for u in filtered_universities:
                    t = by_univ.get(u["university"], {})
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
                        st.markdown(f"**{u['university']}** ({u.get('campus') or '캠퍼스 미상'}) {dday_badge}", unsafe_allow_html=True)
                        st.caption(f"학과: {', '.join(u['departments'])}")
                        if tier_badge:
                            st.markdown(tier_badge, unsafe_allow_html=True)
                        st.markdown("---")

        elif page == "🔍 학교 상세":
            names = [u["university"] for u in universities]
            if not names:
                st.info("아직 적재된 학교 데이터가 없습니다.")
            else:
                selected = st.selectbox("학교 선택", names)
                detail = svc.get_university_detail(selected)

                st.markdown("### 🔒 공식 모집요강 사실")
                st.caption("아래 내용은 전부 공식 모집요강 원문에서 추출되었으며, 출처 링크가 함께 표시됩니다.")
                track_full_by_name = {t["track_name"]: t for t in svc.list_all_tracks_full() if t["university"] == selected}
                for t in detail["official_tracks"]:
                    full = track_full_by_name.get(t["track_name"], {})
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
                            <span style='font-size:12px;color:#666;'>출처 신뢰도: {full.get('source_tier', '-')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        if t.get("source_url"):
                            st.link_button("📑 공식 출처 원문 바로가기", t["source_url"], key=f"src_{t['track_name']}")

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
                        ("exam_date_raw", "실기고사일"), ("result_date", "발표일"), ("source_tier", "출처신뢰도"),
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
                # 원서접수 기간은 시작~끝 매일 표시 (달력에서는 막대가 아니라 날짜별 태그이므로 기간 전체를 펼쳐야 함)
                expanded_events = []
                for e in events:
                    if e["event_type"] == "원서접수":
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
                selected_month_label = st.selectbox("월 선택", month_labels, index=default_idx)
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
            names = ["전체"] + [u["university"] for u in universities]
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
                            st.link_button("📑 출처 원문 바로가기", p["source_url"], key=f"topic_{p['university']}_{p.get('year')}_{p['topic_text'][:20]}")

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

        else:  # 💬 질의응답
            st.markdown("### 💬 규칙기반 질의응답 (LLM 미사용, 그래프 사실만으로 답변)")
            st.caption("학교명을 포함하거나 '일정 충돌', '호환' 같은 키워드로 질문하세요. 모든 답변은 적재된 official_facts에서만 나오며, 근거 출처가 함께 표시됩니다.")
            query = st.text_input("질문 입력", placeholder="예: 한예종 알려줘 / 일정 충돌 있어? / 중앙대학교 호환되는 학교 있어?")
            if query:
                result = svc.answer_question(query)
                st.markdown(f"**[의도 분류: {result['intent']}]**")
                st.markdown(result["answer"].replace("\n", "  \n"))
                if result.get("source_url"):
                    st.link_button("📑 근거 원문 바로가기", result["source_url"])

    finally:
        svc.close()
