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

        page = st.radio("📌 메뉴", ["🏫 학교/학과 목록", "🔍 학교 상세", "⚖️ 전형 비교"], horizontal=True)
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

        else:  # 전형 비교
            st.info("여러 학교의 전형을 나란히 비교하는 기능입니다. 데이터가 2개교 이상 적재되면 선택 UI가 활성화됩니다.")

    finally:
        svc.close()
