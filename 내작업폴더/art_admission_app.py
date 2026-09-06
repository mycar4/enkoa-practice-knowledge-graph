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

sys.path.insert(0, os.path.abspath("내작업폴더"))

import streamlit as st
from services.art_admission_service import ArtAdmissionService


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

        page = st.radio("📌 메뉴", ["🏫 학교/학과 목록", "🔍 학교 상세", "⚖️ 전형 비교", "💬 질의응답"], horizontal=True)
        st.markdown("---")

        if page == "🏫 학교/학과 목록":
            st.subheader(f"등록된 학교 ({len(universities)}개)")
            if not universities:
                st.info("아직 적재된 데이터가 없습니다. 크롤링 결과가 준비되면 `00_Art_Admission_Graph_Loader.py`로 적재 후 여기에 표시됩니다.")
            else:
                for u in universities:
                    with st.container():
                        st.markdown(f"**{u['university']}** ({u.get('campus') or '캠퍼스 미상'})")
                        st.caption(f"학과: {', '.join(u['departments'])}")
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
                for t in detail["official_tracks"]:
                    with st.container():
                        st.markdown(f"""
                        <div style='background: rgba(22,163,74,0.08); border: 1px solid rgba(22,163,74,0.3); border-radius: 8px; padding: 14px; margin-bottom: 10px;'>
                            <b>{t['department']} — {t['track_name']}</b><br/>
                            모집인원: {t.get('quota') or '-'}명 | 반영비율: {t.get('ratio') or '-'}<br/>
                            실기종목: {t.get('exam_type_name') or '-'} | 허용재료: {', '.join(t.get('allowed_materials') or []) or '-'}
                            | 규격: {t.get('paper_size') or '-'} | 시험시간: {t.get('time_limit_minutes') or '-'}분<br/>
                            원서접수: {t.get('application_start') or '-'} ~ {t.get('application_end') or '-'}
                            | 실기고사일: {t.get('exam_date') or '-'} | 발표일: {t.get('result_date') or '-'}
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
            st.markdown("### 🚨 실기고사일 충돌 자동 감지")
            st.caption("적재된 전형들의 실기고사일(공식 사실)만 비교합니다. 날짜는 원문 요강에서 정규식으로 그대로 추출한 값이며 추정하지 않습니다.")
            conflicts = svc.detect_schedule_conflicts()
            if not conflicts:
                st.success("현재 적재된 전형 중 실기고사일이 겹치는 조합이 없습니다.")
            else:
                for c in conflicts:
                    st.warning(
                        f"**{', '.join(c['date'])}** 에 겹침: "
                        f"{c['school_a']['university']} {c['school_a']['department']} ↔ "
                        f"{c['school_b']['university']} {c['school_b']['department']}"
                    )

            st.markdown("---")
            st.markdown("### 🔗 실기유형 호환 매칭")
            st.caption("실기종목명·허용재료가 겹치는 다른 학교 전형을 찾습니다 (키워드/재료 완전일치 기준, 유사도 추정 아님).")
            all_tracks = svc.list_all_tracks_full()
            options = [f"{t['university']} - {t['department']}" for t in all_tracks]
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
                            <b>{m['university']} {m['department']}</b> ({m['track_name']})<br/>
                            공통 실기유형 키워드: {', '.join(m['shared_keywords']) or '-'} | 공통 허용재료: {', '.join(m['shared_materials']) or '-'}
                        </div>
                        """, unsafe_allow_html=True)

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
