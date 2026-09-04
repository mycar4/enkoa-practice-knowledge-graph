# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] Menu 2: 단일 기업 4단 의사결정 리포트 UI (Antigravity Domain)
================================================================================
- 토스 / 블룸버그 스타일의 다크·화이트 반응형 4단 카드 대시보드
- services/decision_report_service.py를 순수 데이터 소스로 사용
- 1단: 사실 (Facts) - 재무/공시/CB/원문 추출 지분율 수치 및 정확한 관찰 기간
- 2단: 관찰 지표 (Rule-based Observation) - 단정적 금융 판단 배제, 규칙 버전 및 근거 공시 명시
- 3단: 원문 근거 (Evidence) - 증거 등급 분리 (공시 링크 연동 vs 2D 행 해시 결속)
- 4단: 다음 확인 항목 (Next Actions) - 투자자 실사 모니터링 체크리스트
================================================================================
"""

import os
import json
import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional

from services.decision_report_service import DecisionReportService, format_currency_kr


def get_observation_badge(obs_code: str, obs_level: str) -> str:
    """규칙 기반 관찰 등급에 따른 토스/블룸버그 스타일 뱃지 HTML 생성"""
    if obs_code == "OBS_WATCH_HIGH":
        return f"<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 13px;'>🔍 관찰 등급: {obs_level}</span>"
    elif obs_code == "OBS_WATCH_MODERATE":
        return f"<span style='background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 13px;'>🔍 관찰 등급: {obs_level}</span>"
    else:
        return f"<span style='background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 13px;'>🔍 관찰 등급: {obs_level}</span>"


def render_menu2_decision_report(driver=None, theme_mode: str = "🌙 다크 모드 (Dark)"):
    """4단 의사결정 리포트 메인 렌더러"""
    is_dark = "다크" in theme_mode

    # 스타일 토큰 (토스 증권 + 블룸버그 터미널 융합 스타일)
    bg_card = "rgba(30, 41, 59, 0.7)" if is_dark else "#ffffff"
    border_card = "rgba(255, 255, 255, 0.1)" if is_dark else "#e2e8f0"
    text_primary = "#f8fafc" if is_dark else "#0f172a"
    text_secondary = "#94a3b8" if is_dark else "#64748b"
    accent_blue = "#38bdf8"
    accent_green = "#10b981"
    accent_amber = "#f59e0b"
    accent_red = "#ef4444"

    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
            <span style="font-size: 32px;">📋</span>
            <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: {text_primary};">
                단일 기업 4단 의사결정 리포트
            </h1>
            <span style="background: linear-gradient(135deg, #0284c7, #0369a1); color: white; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">
                DART-Trace v1.0
            </span>
        </div>
        <p style="margin: 0; font-size: 14px; color: {text_secondary}; line-height: 1.6;">
            객관적 공시 사실(<b>Facts</b>)과 규칙 기반 관찰 지표(<b>Rule-based Observation</b>)를 엄격히 분리하고, 
            원문 증거 등급(<b>Evidence</b>) 및 투자자 실사 체크리스트(<b>Next Actions</b>)를 제공합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. 기업 검색 및 프리셋 바
    service = DecisionReportService()

    if "selected_report_corp" not in st.session_state:
        st.session_state.selected_report_corp = "HLB"

    search_col1, search_col2 = st.columns([2, 5])
    with search_col1:
        search_input = st.text_input(
            "🔍 기업명 / 종목코드 / 법인코드 검색",
            value="",
            placeholder="예: HLB, 028300, 00199252",
            key="report_company_search_input"
        )
    with search_col2:
        st.caption("⚡ 주요 자본이벤트 분석 대표 기업 숏컷:")
        preset_cols1 = st.columns(5)
        presets1 = [
            ("HLB (코스닥 028300)", "HLB"),
            ("DXVX (코스닥 180400)", "DXVX"),
            ("FSN (코스닥 214270)", "FSN"),
            ("삼성전자 (코스피 005930)", "삼성전자"),
            ("파인메딕스 (코넥스)", "파인메딕스")
        ]
        for idx, (label, code_or_name) in enumerate(presets1):
            with preset_cols1[idx]:
                if st.button(label.split()[0], key=f"btn_preset_{code_or_name}", use_container_width=True):
                    st.session_state.selected_report_corp = code_or_name
                    st.session_state.report_company_search_input = ""
                    st.rerun()

        st.caption("🔒 검증 경제적 보유 사실 예시:")
        preset_cols2 = st.columns(3)
        presets2 = [
            ("알루코 (승격 1건)", "알루코"),
            ("씨티씨바이오 (승격 2건)", "씨티씨바이오"),
            ("롯데지주 (승격 2건)", "롯데지주")
        ]
        for idx, (label, code_or_name) in enumerate(presets2):
            with preset_cols2[idx]:
                if st.button(label.split()[0], key=f"btn_promoted_preset_{code_or_name}", use_container_width=True):
                    st.session_state.selected_report_corp = code_or_name
                    st.session_state.report_company_search_input = ""
                    st.rerun()

    target_to_load = st.session_state.selected_report_corp
    if search_input.strip():
        matches = service.find_companies(search_input.strip(), limit=5)
        if matches:
            match_labels = [f"{m['corp_name']} ({m.get('stock_code') or '비상장'} | {m['corp_code']})" for m in matches]
            selected_match = st.selectbox("🎯 검색 결과 선택", match_labels, index=0, key="report_search_select")
            idx = match_labels.index(selected_match)
            target_to_load = matches[idx]["corp_code"]
        else:
            st.warning(f"'{search_input}'에 일치하는 기업 마스터 노드가 없습니다.")

    # 2. 4단 리포트 데이터 로드
    with st.spinner(f"🏛️ '{target_to_load}' 지식그래프 4단 의사결정 리포트 산출 중..."):
        try:
            report = service.generate_company_decision_report(target_to_load)
        except Exception as e:
            st.error(f"❌ 리포트 생성 중 오류 발생: {e}")
            service.close()
            return

    service.close()

    if report.get("status") == "NOT_FOUND":
        st.error(report.get("message", "기업을 찾을 수 없습니다."))
        return

    company_info = report["target_company"]
    corp_name = company_info.get("corp_name", "")
    corp_code = company_info.get("corp_code", "")
    stock_code = company_info.get("stock_code") or "비상장"
    facts = report["tier1_facts"]
    date_coverage = facts.get("date_coverage", {})
    interpretations = report["tier2_interpretations"]
    evidence_list = report["tier3_evidence"]
    next_actions = report["tier4_next_actions"]

    # 3. 기업 프로필 및 상태 배너 (Toss 헤더 룩)
    obs_code = interpretations.get("observation_code", "OBS_NORMAL")
    obs_level = interpretations.get("observation_level", "일반 관찰")

    st.markdown(f"""
    <div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <h2 style="margin: 0; font-size: 26px; font-weight: 800; color: {text_primary};">{corp_name}</h2>
                    <span style="background: rgba(56, 189, 248, 0.15); color: {accent_blue}; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px; font-size: 13px; font-family: monospace; font-weight: 600;">{stock_code}</span>
                    <span style="background: rgba(148, 163, 184, 0.15); color: {text_secondary}; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-family: monospace;">법인코드: {corp_code}</span>
                </div>
                <div style="margin-top: 6px; font-size: 13px; color: {text_secondary};">
                    📅 <b>공시 관찰 범위</b>: {date_coverage.get('description', '관찰 기간 집계 중')}
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                {get_observation_badge(obs_code, obs_level)}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── [1단: 사실 (Facts)] ──
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <span style="background: {accent_blue}; color: black; font-weight: 900; font-size: 12px; padding: 2px 8px; border-radius: 4px;">TIER 1</span>
        <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: {text_primary};">📊 공시 사실 원천 수치 (Facts)</h3>
        <span style="font-size: 12px; color: {text_secondary};">※ 금융감독원 DART 공시 원문 100% 미가공 사실 수치</span>
    </div>
    """, unsafe_allow_html=True)

    cap_events = facts.get("capital_events_summary", {}).get("events_detail", [])
    total_events_cnt = len(cap_events)
    cb_bw_cnt = sum(1 for e in cap_events if any(k in str(e.get("event_type", "")) or k in str(e.get("event_type_kr", "")) for k in ["전환사채", "CB", "신주인수권", "BW"]))
    increase_cnt = sum(1 for e in cap_events if "유상증자" in str(e.get("event_type_kr", "")) or str(e.get("event_type", "")) == "PAID")
    holdings_summary = facts.get("major_holdings_summary", {})
    promoted_stakes = holdings_summary.get("promoted_stakes", [])
    promoted_cnt = len(promoted_stakes)
    raw_candidates = holdings_summary.get("raw_candidates", [])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("수집된 자본이벤트", f"{total_events_cnt}건", help=date_coverage.get("description"))
    with kpi2:
        st.metric("전환사채(CB)·BW 발행", f"{cb_bw_cnt}건", help="CB/BW 발행 결정 공시")
    with kpi3:
        st.metric("검증 경제적 보유 사실", f"{promoted_cnt}건", help="봉인 매니페스트 SHA-256 결속 승격본 (당사 기준 보유 및 피보유 포함)")
    with kpi4:
        total_raw_cand_cnt = holdings_summary.get("raw_candidate_count", len(raw_candidates))
        st.metric("5% 공시 피보유 후보", f"{total_raw_cand_cnt}건", help=f"당사 대상 5% 대량보유 공시 원문 추출본 (미검증 후보 전체 {total_raw_cand_cnt}건 중 상위 10건 표기)")

    # 1-1. 최근 자본이벤트 타임라인
    st.markdown(f"**⚡ 최근 자본이벤트 타임라인 (DART DS005 연동)**")
    if cap_events:
        events_df_data = []
        for ev in cap_events:
            c_price = ev.get("conversion_price")
            c_price_str = f"{int(c_price):,}원" if (c_price and isinstance(c_price, (int, float))) else (str(c_price) if c_price else "-")
            floor = ev.get("min_refixing_floor")
            floor_str = f"{int(floor):,}원" if (floor and isinstance(floor, (int, float))) else (str(floor) if floor else "-")
            
            events_df_data.append({
                "결정일자": str(ev.get("decided_on") or ev.get("received_on") or "-"),
                "이벤트 구분": ev.get("event_type_kr") or ev.get("event_type", "-"),
                "조달 금액": ev.get("amount_display") or "-",
                "전환/발행가": c_price_str,
                "최저 리픽싱가": floor_str,
                "조달 목적": ev.get("sanitized_purpose") or "-"
            })
        st.dataframe(pd.DataFrame(events_df_data), use_container_width=True, height=200)
    else:
        st.info(f"'{corp_name}'에 대해 수집된 자본이벤트(CB·BW·유상증자) 공시가 없습니다.")

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 1-2. 검증·승격된 경제적 보유 사실 (HOLDS_ECONOMIC_STAKE) - 전용 카드
    st.markdown(f"""
    <div style="background: {bg_card}; border: 1px solid rgba(16, 185, 129, 0.35); border-left: 5px solid {accent_green}; border-radius: 12px; padding: 14px 18px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">🔒</span>
                <h4 style="margin: 0; font-size: 15px; font-weight: 700; color: {text_primary};">검증·승격된 경제적 보유 사실 (HOLDS_ECONOMIC_STAKE)</h4>
                <span style="background: rgba(16, 185, 129, 0.15); color: {accent_green}; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 700;">{promoted_cnt}건 검증 승격</span>
            </div>
            <span style="font-size: 12px; color: {text_secondary};">※ 봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 감사 통과본</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if promoted_stakes:
        promoted_df_data = []
        for p in promoted_stakes:
            amt_shares = p.get("shares_count")
            shares_str = f"{int(amt_shares):,}주" if (amt_shares and isinstance(amt_shares, (int, float))) else (str(amt_shares) if amt_shares is not None else "-")
            ratio = p.get("stake_ratio")
            ratio_str = f"{float(ratio):.2f}%" if ratio is not None else "-"
            h_raw = p.get("row_inner_hash")
            hash_display = f"{h_raw[:16]}..." if h_raw else "-"
            promoted_df_data.append({
                "보유사 → 대상회사": p.get("holder_to_target", "-"),
                "지분율": ratio_str,
                "보유주식수": shares_str,
                "보고의무발생일": str(p.get("reporting_obligation_date") or "-"),
                "원문 행 해시": hash_display,
                "최초 승격일": str(p.get("promoted_at") or "-")[:19]
            })
        st.dataframe(pd.DataFrame(promoted_df_data), use_container_width=True, height=160)
        st.caption("🛡️ 위 내역은 DART 대량보유 공시 보고의무발생일 기준 과거 경제적 지분 보유 사실이며, 지배력·경영권 단정이나 현재 지분이 아닙니다.")
    else:
        st.info(f"'{corp_name}'에 대해 검증·승격된 경제적 보유 사실(HOLDS_ECONOMIC_STAKE)이 없습니다.")

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 1-3. 5% 대량보유 공시 원문 추출 후보 (미검증 후보) - 전용 카드
    st.markdown(f"**👥 5% 대량보유 공시 원문 추출 후보 (미검증 후보)**")
    if raw_candidates:
        holdings_df_data = []
        for h in raw_candidates:
            ratio = h.get("stake_ratio")
            ratio_str = f"{float(ratio):.2f}%" if ratio is not None else "-"
            shares = h.get("shares_count")
            shares_str = f"{int(shares):,}주" if (shares and isinstance(shares, (int, float))) else (str(shares) if shares else "-")
            
            holdings_df_data.append({
                "보고자 / 보유자": h.get("holder_name", "-"),
                "지분율": ratio_str,
                "보유주식수": shares_str,
                "보고의무발생일": str(h.get("reporting_obligation_date") or "-"),
                "검증 상태": "⚪ 미검증 1차 후보"
            })
        st.dataframe(pd.DataFrame(holdings_df_data), use_container_width=True, height=200)
        st.caption("🛡️ 위 지분 데이터는 DART 원문 테이블에서 추출된 1차 후보이며, 엔티티 해소 검증 전 단계입니다.")
    else:
        st.info("수집된 5% 이상 대량보유 공시 원문 후보가 없습니다.")

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 1-4. 🏛️ 주요 재무제표 팩트 (OpenDART DS003 단일회사 주요계정 연동)
    fin_facts = facts.get("financial_facts", {})
    fin_status = fin_facts.get("status")

    if fin_status == "AVAILABLE":
        bsns_yr = fin_facts.get("bsns_year", "2024")
        fs_nm = fin_facts.get("fs_div_name", "연결재무제표")
        rep_nm = fin_facts.get("reprt_name", "사업보고서")
        debt_ratio_val = fin_facts.get("debt_ratio")
        debt_ratio_str = f"{debt_ratio_val:.2f}%" if debt_ratio_val is not None else "-"
        fin_rcp = fin_facts.get("rcept_no")

        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid rgba(56, 189, 248, 0.35); border-left: 5px solid {accent_blue}; border-radius: 12px; padding: 14px 18px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">🏛️</span>
                    <h4 style="margin: 0; font-size: 15px; font-weight: 700; color: {text_primary};">주요 재무제표 팩트 (OpenDART DS003 단일회사 주요계정)</h4>
                    <span style="background: rgba(56, 189, 248, 0.15); color: {accent_blue}; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 700;">
                        {bsns_yr}년 {rep_nm} ({fs_nm})
                    </span>
                </div>
                <span style="font-size: 12px; color: {text_secondary};">※ 금융감독원 OpenDART 공시 원문 단일계정 직연동 사실</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fin_col1, fin_col2, fin_col3, fin_col4 = st.columns(4)
        with fin_col1:
            rev_curr = fin_facts.get("revenue")
            st.metric("매출액 (당기)", format_currency_kr(rev_curr), help="OpenDART 정기보고서 손익계산서 매출액")
        with fin_col2:
            op_curr = fin_facts.get("operating_income")
            st.metric("영업이익 (당기)", format_currency_kr(op_curr), help="OpenDART 정기보고서 손익계산서 영업이익(손실)")
        with fin_col3:
            net_curr = fin_facts.get("net_income")
            st.metric("당기순이익 (당기)", format_currency_kr(net_curr), help="OpenDART 정기보고서 손익계산서 당기순이익(손실)")
        with fin_col4:
            st.metric("부채비율", debt_ratio_str, help="부채총계 / 자본총계 × 100 (회계적 단순 산술비율, 주관적 리스크 판정 아님)")

        fin_table_data = [
            {
                "주요 계정과목": "자산총계",
                "당기 금액": format_currency_kr(fin_facts.get("total_assets")),
                "전기 금액": format_currency_kr(fin_facts.get("total_assets_prev")),
                "비고": "재무상태표 (BS)"
            },
            {
                "주요 계정과목": "부채총계",
                "당기 금액": format_currency_kr(fin_facts.get("total_liabilities")),
                "전기 금액": format_currency_kr(fin_facts.get("total_liabilities_prev")),
                "비고": "재무상태표 (BS)"
            },
            {
                "주요 계정과목": "자본총계",
                "당기 금액": format_currency_kr(fin_facts.get("total_equity")),
                "전기 금액": format_currency_kr(fin_facts.get("total_equity_prev")),
                "비고": "재무상태표 (BS)"
            },
            {
                "주요 계정과목": "매출액",
                "당기 금액": format_currency_kr(fin_facts.get("revenue")),
                "전기 금액": format_currency_kr(fin_facts.get("revenue_prev")),
                "비고": "손익계산서 (IS)"
            },
            {
                "주요 계정과목": "영업이익",
                "당기 금액": format_currency_kr(fin_facts.get("operating_income")),
                "전기 금액": format_currency_kr(fin_facts.get("operating_income_prev")),
                "비고": "손익계산서 (IS)"
            },
            {
                "주요 계정과목": "당기순이익",
                "당기 금액": format_currency_kr(fin_facts.get("net_income")),
                "전기 금액": format_currency_kr(fin_facts.get("net_income_prev")),
                "비고": "손익계산서 (IS)"
            }
        ]
        st.dataframe(pd.DataFrame(fin_table_data), use_container_width=True, height=220)

        c_sub1, c_sub2 = st.columns([4, 1])
        with c_sub1:
            st.caption("🛡️ 위 재무제표 수치는 금융감독원 OpenDART 사업보고서(DS003) 공시 원문 팩트이며, 주관적 가치평가나 목표주가 산출이 아닙니다.")
        with c_sub2:
            if fin_rcp:
                st.link_button("📑 사업보고서 원문", f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={fin_rcp}", use_container_width=True)
    else:
        st.info(f"🏛️ 주요 재무제표 팩트: {fin_facts.get('message', 'OpenDART 재무제표 데이터 미공시 또는 조회 제한')}")

    st.markdown("---")

    # ── [2단: 관찰 지표 (Rule-based Observation)] ──
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <span style="background: {accent_amber}; color: black; font-weight: 900; font-size: 12px; padding: 2px 8px; border-radius: 4px;">TIER 2</span>
        <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: {text_primary};">🧠 규칙 기반 관찰 지표 (Rule-based Observation)</h3>
        <span style="font-size: 12px; color: {text_secondary};">※ 규칙 버전: <code>{interpretations.get('rule_version', 'v1.0')}</code> | 근거 공시: {len(interpretations.get('basis_rcept_nos', []))}건</span>
    </div>
    """, unsafe_allow_html=True)

    inter_col1, inter_col2 = st.columns(2)
    with inter_col1:
        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 12px; padding: 18px; height: 100%;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                <h4 style="margin: 0; font-size: 16px; color: {text_primary};">📉 전환사채(CB)·BW 공시 관찰 지표</h4>
                {get_observation_badge(obs_code, obs_level)}
            </div>
            <p style="margin: 0; font-size: 14px; color: {text_secondary}; line-height: 1.6;">
                {interpretations.get('cb_bw_overhang_observation', '')}
            </p>
            <div style="margin-top: 8px; font-size: 12px; color: {accent_blue};">
                • 관련 공시 접수번호: <code>{', '.join(interpretations.get('basis_rcept_nos', [])[:3]) or '미해당'}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with inter_col2:
        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 12px; padding: 18px; height: 100%;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                <h4 style="margin: 0; font-size: 16px; color: {text_primary};">🎯 공시 목적 문구 키워드 탐지</h4>
                <span style="background: rgba(56, 189, 248, 0.15); color: {accent_blue}; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;">
                    {interpretations.get('financing_purpose_observation', '탐지 중')}
                </span>
            </div>
            <p style="margin: 0; font-size: 14px; color: {text_secondary}; line-height: 1.6;">
                공시 서식상의 자금 사용 목적 텍스트를 파싱하여 시설·R&D·타법인증권취득 또는 운영·채무상환성 키워드 매칭 결과를 제공합니다.
            </p>
            <div style="margin-top: 8px; font-size: 12px; color: {text_secondary};">
                • 이벤트 일자: <code>{', '.join([str(d) for d in interpretations.get('basis_event_dates', [])[:3]]) or '미해당'}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 모니터링 시나리오 (참고용 명시)
    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
    scenarios = interpretations.get("tracking_scenarios", {})
    sc_col1, sc_col2, sc_col3 = st.columns(3)
    with sc_col1:
        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid rgba(16, 185, 129, 0.3); border-top: 4px solid {accent_green}; border-radius: 12px; padding: 16px; height: 100%;">
            <h5 style="margin: 0 0 8px 0; color: {accent_green}; font-size: 14px; font-weight: 700;">🟢 Bull Case (추적 시나리오)</h5>
            <p style="margin: 0; font-size: 13px; color: {text_secondary}; line-height: 1.6;">
                {scenarios.get('bull_case', '-')}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with sc_col2:
        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid rgba(56, 189, 248, 0.3); border-top: 4px solid {accent_blue}; border-radius: 12px; padding: 16px; height: 100%;">
            <h5 style="margin: 0 0 8px 0; color: {accent_blue}; font-size: 14px; font-weight: 700;">🔵 Base Case (추적 시나리오)</h5>
            <p style="margin: 0; font-size: 13px; color: {text_secondary}; line-height: 1.6;">
                {scenarios.get('base_case', '-')}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with sc_col3:
        st.markdown(f"""
        <div style="background: {bg_card}; border: 1px solid rgba(239, 68, 68, 0.3); border-top: 4px solid {accent_red}; border-radius: 12px; padding: 16px; height: 100%;">
            <h5 style="margin: 0 0 8px 0; color: {accent_red}; font-size: 14px; font-weight: 700;">🔴 Bear Case (추적 시나리오)</h5>
            <p style="margin: 0; font-size: 13px; color: {text_secondary}; line-height: 1.6;">
                {scenarios.get('bear_case', '-')}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.caption(f"📢 {interpretations.get('disclaimer', '')}")
    st.markdown("---")

    # ── [3단: 원문 근거 (Evidence)] ──
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: space-between; margin: 24px 0 12px 0; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="background: {accent_green}; color: black; font-weight: 900; font-size: 12px; padding: 2px 8px; border-radius: 4px;">TIER 3</span>
            <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: {text_primary};">🔍 금감원 공시 원문 증거 & 감사 추적 (Evidence)</h3>
        </div>
        <span style="font-size: 12px; color: {text_secondary};">※ 행 단위 결속 증거 vs 공시 단위 링크 분리 표기</span>
    </div>
    """, unsafe_allow_html=True)

    if evidence_list:
        for idx, ev in enumerate(evidence_list):
            rcp = ev.get("rcept_no")
            viewer_url = ev.get("dart_viewer_url")
            xpath = ev.get("xpath")
            h_hash = ev.get("inner_hash")
            ev_level = ev.get("evidence_level")
            ev_note = ev.get("evidence_note", "")

            is_promoted = (ev_level == "MANIFEST_SEALED_ROW_HASH" or ev.get("item_type") == "PROMOTED_ECONOMIC_STAKE")
            is_hash_bound = (ev_level == "ROW_HASH_BOUND")
            is_opendart_fact = (ev_level == "OPENDART_API_FACT" or ev.get("item_type") == "FINANCIAL_STATEMENT_FACT")

            if is_promoted:
                badge_color = "#10b981"
                badge_text = "🔒 봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 검증"
            elif is_hash_bound:
                badge_color = "#38bdf8"
                badge_text = "⚪ 파서 추출 좌표 + 원문 행 SHA-256 결속 (미검증 후보)"
            elif is_opendart_fact:
                badge_color = "#a855f7"
                badge_text = "🏛️ OpenDART 정기공시 재무제표 팩트 직연동"
            else:
                badge_color = "#64748b"
                badge_text = "🔗 공시 원문 링크 연동"

            with st.container():
                st.markdown(f"""
                <div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="background: {badge_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">{badge_text}</span>
                            <span style="font-size: 14px; font-weight: 600; color: {text_primary};">{ev.get('title')}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span style="font-family: monospace; font-size: 12px; color: {accent_blue};">접수번호: {rcp or '-'}</span>
                            {f"<span style='background: rgba(16, 185, 129, 0.15); color: {accent_green}; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-family: monospace;'>SHA-256: {h_hash[:16]}...</span>" if h_hash else "<span style='color: #94a3b8; font-size: 11px;'>행 단위 해시 미적재</span>"}
                        </div>
                    </div>
                    <div style="margin-top: 8px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: {text_secondary};">
                        <span>📍 {f"파서 추출 좌표: <code style='color: {accent_amber};'>{xpath}</code> (원문 행 SHA-256 결속)" if xpath else ev_note}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if viewer_url:
                    c_btn1, c_btn2, _ = st.columns([2, 3, 5])
                    with c_btn1:
                        st.link_button(f"📑 DART 원문 바로가기", viewer_url, use_container_width=True)
                    with c_btn2:
                        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp}&method=search" if rcp else None
                        if krx_url:
                            st.link_button(f"🏛️ KRX 상장공시 교차검증", krx_url, use_container_width=True)
    else:
        st.info("연결된 공시 원문 증거가 없습니다.")

    st.markdown("---")

    # ── [4단: 다음 확인 항목 (Next Actions)] ──
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <span style="background: #a855f7; color: white; font-weight: 900; font-size: 12px; padding: 2px 8px; border-radius: 4px;">TIER 4</span>
        <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: {text_primary};">⚡ 투자자 실사 체크리스트 (Next Actions)</h3>
        <span style="font-size: 12px; color: {text_secondary};">※ 후속 공시 일정 및 잠재 위험 모니터링 행동 항목</span>
    </div>
    """, unsafe_allow_html=True)

    act_col1, act_col2 = st.columns(2)
    for idx, action in enumerate(next_actions):
        target_col = act_col1 if idx % 2 == 0 else act_col2
        with target_col:
            st.checkbox(f"**Action {idx+1}**: {action}", key=f"chk_action_{corp_code}_{idx}", value=False)

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 5. 크로스 네비게이션 액션 버튼 (메뉴 4 및 메뉴 6 연결)
    st.markdown(f"""
    <div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 12px; padding: 16px 20px; margin-top: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <h4 style="margin: 0 0 4px 0; font-size: 15px; color: {text_primary};">🔗 DART-Trace 심층 분석 바로가기</h4>
                <p style="margin: 0; font-size: 13px; color: {text_secondary};">현재 보고 계신 <b>{corp_name}</b>의 원문 증거와 자본이벤트를 다른 전문 메뉴에서 심층 탐색하세요.</p>
            </div>
            <div style="display: flex; gap: 12px;">
                <span style="font-size: 13px; color: {accent_blue};">👉 좌측 사이드바 <b>메뉴 4 (DS005 자본이벤트)</b> 또는 <b>메뉴 6 (5% 공시 원문 증거 감사기)</b>를 선택하세요.</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_menu2_decision_report()
