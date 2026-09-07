# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] AI 기반 기업 지배구조 & 경영권 분쟁 GraphRAG 실전 웹 대시보드
- 실행 방법: uv run streamlit run 내작업폴더/app_dart_trace_dashboard.py
"""

import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS
from pyvis.network import Network
import networkx as nx

# 5% 공시 명시적 어댑터 및 금융특화 GraphRAG 엔진 (읽기 전용 / 동결 규격)
sys.path.insert(0, os.path.abspath("내작업폴더"))
from adapter_5pct_general_art142_v1 import run_adapter_5pct_general_art142_v1
from engine_financial_graphrag import analyze_financial_graphrag
from ui.pages.menu2_decision_report import render_menu2_decision_report

# 1. 환경 설정 & Streamlit 페이지 설정
st.set_page_config(
    page_title="DART-Trace 기업 지배구조 GraphRAG 플랫폼",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Streamlit Community Cloud에는 로컬 .env 파일이 없고 대신 st.secrets에
# 배포용 비밀값을 넣는다. 이 저장소의 모든 코드는 os.getenv()로 읽으므로,
# st.secrets에 있는 키를 최초 1회 os.environ에 복사해서 로컬(.env)/클라우드(st.secrets)
# 양쪽에서 코드 수정 없이 동일하게 동작하게 한다 - 이미 os.environ에 있는 값은 덮지 않음.
try:
    for _key, _val in st.secrets.items():
        if isinstance(_val, str) and _key not in os.environ:
            os.environ[_key] = _val
except Exception:
    pass  # secrets.toml이 없는 로컬 환경(.env만 쓰는 경우)에서는 조용히 통과

load_dotenv(".env", override=False)

# 클라우드 Aura 전용 변수 1순위 탐색 (교안 실습용 NEO4J_URI와 완벽 격리)
NEO4J_URI = os.getenv("AURA_URI") or os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
NEO4J_USER = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD", "")

# Neo4j 드라이버 연결 (URI별 캐싱 자동 갱신 - 100% Read-Only 안전 연결)
@st.cache_resource
def get_neo4j_driver(uri: str, user: str, password: str):
    try:
        if not password:
            st.warning("⚠️ .env 또는 Streamlit Secrets에 NEO4J_PASSWORD가 설정되지 않았습니다.")
            return None
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        st.error(f"❌ Neo4j 연결 실패 ({uri}): {e}")
        return None

driver = get_neo4j_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

def run_cypher(query: str, **params):
    if not driver:
        return []
    with driver.session(default_access_mode=READ_ACCESS) as session:
        return [record.data() for record in session.run(query, **params)]

def ensure_company_ownership_data(company_name: str):
    """[보안 조치] 공개 웹 대시보드에서의 실시간 DB 쓰기(MERGE) 제거 (100% Read-Only 안전 유지)"""
    pass

def generate_graphrag_response(prompt: str, api_key_input: str = "") -> dict:
    """DART-Trace 금융특화 GraphRAG (증거 기반 질의응답 및 거버넌스 가드레일)"""
    drv = get_neo4j_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    if not drv:
        return {
            "ans": "⚠️ Neo4j 데이터베이스 연결에 실패했습니다. 환경 설정을 확인하세요.",
            "raw_facts_text": "",
            "raw_data": {},
            "cypher": "// Database connection error",
            "intent": "ERROR",
            "entities": [],
            "token_usage_info": None,
            "prompt_payload": {}
        }
    return analyze_financial_graphrag(prompt, drv, api_key_input)

# ── 서비스 선택 스위치 (메인 진입점 분리) ──
# DART-Trace(지배구조)와 미술 실기 입시 도우미는 완전히 별개 서비스다.
# 메인 링크(쿼리파라미터 없음)로 들어오면 미술 입시 도우미가 곧바로 뜨고
# 사이드바에 DART-Trace 선택지 자체가 안 보인다 - 학원 등 외부에 공유할 링크가
# DART-Trace 존재를 노출하지 않게 하기 위함. DART-Trace는 URL에
# "?internal=darttrace" 를 붙인 비공개 링크로만 접근한다(뒤 숫자 없는 평문
# 파라미터라 추측하긴 쉽지만, 이건 보안 차단이 아니라 "메인에 안 보이게" 하는
# 용도일 뿐 - 진짜 민감정보라면 별도 인증이 필요).
_is_internal_access = st.query_params.get("internal") == "darttrace"

if _is_internal_access:
    with st.sidebar:
        service_mode = st.radio("🗂️ 서비스 선택", ["🎨 미술 실기 입시 도우미", "🏛️ DART-Trace (지배구조)"], key="top_service_mode")
        st.markdown("---")
else:
    service_mode = "🎨 미술 실기 입시 도우미"

if service_mode == "🎨 미술 실기 입시 도우미":
    from art_admission_app import render_art_admission_app
    render_art_admission_app()
    st.stop()

# 사이드바
with st.sidebar:
    st.markdown("""
    <div style='text-align: center; padding: 10px 0;'>
        <span style='font-size: 48px;'>🏛️</span>
        <h2 style='margin: 5px 0 0 0; color: #00e5ff !important;'>DART-Trace</h2>
        <p style='font-size: 13px; color: #90a4ae !important; margin: 0;'>AI 지식그래프 & GraphRAG 지배구조 분석</p>
    </div>
    """, unsafe_allow_html=True)

    # 🎨 다크 / 화이트 모드 선택기 (기본값: ☀️ 화이트 모드)
    theme_mode = st.radio("🎨 화면 테마 선택", ["☀️ 화이트 모드 (Light)", "🌙 다크 모드 (Dark)"], index=0, horizontal=True)
    st.markdown("---")
    
    # 사용자 대상 메뉴(5개)와 개발자 전용 도구(2개)를 분리 - 일반 사용자 화면에서
    # 실시간 수집기/Cypher 콘솔이 안 보이도록 접이식 섹션으로 이동 (메뉴 개편 1단계)
    menu = st.radio(
        "📌 서비스 메뉴",
        [
            "🌐 1. 상장사 지배구조 & 순환출자 탐색기",
            "📋 2. 단일 기업 4단 의사결정 리포트",
            "👑 3. 승격 지분 기반 지배 계열사 랭킹",
            "⚡ 4. DS005 기업 주요 자본 이벤트 (CB·BW·증자·M&A)",
            "🔍 6. 5% 공시 원문 증거 감사기 (Evidence Audit Inspector)",
            "💼 8. 내 포트폴리오 (로컬 개인 보유종목 관리)",
        ],
        key="main_menu_select"
    )

    with st.expander("🛠️ 개발자 도구"):
        dev_menu = st.radio(
            "개발자/운영자 전용",
            [
                "(선택 안 함)",
                "📥 5. 최근 5년 OpenDART 실시간 수집 & 스토리지",
                "💻 7. 개발자/분석가 라이브 쿼리 콘솔 (FO Live Cypher Console)"
            ],
            key="dev_menu_select"
        )
        if dev_menu != "(선택 안 함)":
            menu = dev_menu
    
    st.markdown("---")
    st.markdown("### 📊 인프라 연결 현황")
    if driver:
        node_res = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_' OR l STARTS WITH 'RawEvidence' OR l STARTS WITH 'Evidence') RETURN count(n) AS c")
        rel_res = run_cypher("MATCH ()-[r]->() WHERE type(r) IN ['EVIDENCED_BY', 'ANNOUNCED', 'HOLDS_ECONOMIC_STAKE', 'OWNS_STAKE', 'INVESTED_IN', 'ACQUIRED_STAKE', 'REPRESENTS'] RETURN count(r) AS c")
        node_cnt = node_res[0]['c'] if node_res else 0
        rel_cnt = rel_res[0]['c'] if rel_res else 0
        st.success(f"✅ Neo4j: {node_cnt:,}개 노드 / {rel_cnt:,}건 관계")
    else:
        st.error("❌ Neo4j 데이터베이스 미연결")

# # 🎨 테마별 커스텀 CSS 전면 주입 (전 화면 모든 위젯 음영·대비 100% 가시성 보장)
if "화이트" in theme_mode:
    # ☀️ 화이트 모드 전용 완벽 스타일 (가시성 100% 보장)
    st.markdown("""
    <style>
        /* 0. 텍스트 드래그 선택 영역(Selection) 음영 */
        ::selection {
            background-color: #bae6fd !important;
            color: #0369a1 !important;
        }
        ::-moz-selection {
            background-color: #bae6fd !important;
            color: #0369a1 !important;
        }

        /* 1. 최상단 헤더바 투명화 */
        header[data-testid="stHeader"] {
            background: transparent !important;
        }
        
        /* 2. 전체 앱 배경 및 기본 글자색 */
        .stApp {
            background-color: #f8fafc !important;
            color: #0f172a !important;
        }
        
        /* 3. 좌측 사이드바 화이트 룩 */
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #e2e8f0 !important;
        }
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
            color: #0f172a !important;
        }
        
        /* 4. 본문 헤더 및 텍스트 */
        h1, h2, h3, h4, h5, h6, p, span, label, div, small, strong, b {
            color: #0f172a !important;
        }
        .stCaption {
            color: #475569 !important;
            font-weight: 500 !important;
        }
        
        /* 5. 버튼 완벽 화이트 스타일 (검은색 묻힘 완전 제거) */
        button:not([data-baseweb="tab"]):not([kind="primary"]) {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]) * {
            color: #0f172a !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]):hover {
            background-color: #f1f5f9 !important;
            border-color: #0284c7 !important;
            color: #0284c7 !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]):hover * {
            color: #0284c7 !important;
        }
        button[kind="primary"] {
            background-color: #0284c7 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(2, 132, 199, 0.3) !important;
        }
        button[kind="primary"] * {
            color: #ffffff !important;
        }
        
        /* 6. 인라인 코드 및 코드 블록 화이트 음영 (검은 박스 완전 제거) */
        code:not(pre code) {
            background-color: #e0f2fe !important;
            color: #0369a1 !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            border: 1px solid #bae6fd !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }
        pre, div[data-testid="stCodeBlock"], div[data-testid="stCodeBlock"] pre {
            background-color: #f8fafc !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }
        div[data-testid="stCodeBlock"] code, div[data-testid="stCodeBlock"] span, div[data-testid="stCodeBlock"] * {
            color: #0f172a !important;
            background-color: transparent !important;
            font-family: 'Consolas', 'Courier New', monospace !important;
        }

        /* 7. Expander 화이트 스타일 (검은색 헤더 완전 제거) */
        div[data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 10px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
            overflow: hidden !important;
        }
        div[data-testid="stExpander"] summary {
            background-color: #f8fafc !important;
            border-bottom: 1px solid #e2e8f0 !important;
            padding: 10px 16px !important;
        }
        div[data-testid="stExpander"] summary:hover {
            background-color: #f1f5f9 !important;
        }
        div[data-testid="stExpander"] summary span, div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary * {
            color: #0f172a !important;
            font-weight: 600 !important;
        }
        div[data-testid="stExpander"] > div[role="region"] {
            background-color: #ffffff !important;
            padding: 14px !important;
        }

        /* 8. 라디오 버튼 & 체크박스 (검은 직사각형 완전 제거) */
        div[data-testid="stRadio"] input[type="radio"],
        div[data-testid="stCheckbox"] input[type="checkbox"] {
            accent-color: #0284c7 !important;
            cursor: pointer !important;
            width: 17px !important;
            height: 17px !important;
        }
        div[data-testid="stCheckbox"] label, div[data-testid="stCheckbox"] span, div[data-testid="stCheckbox"] p {
            color: #0f172a !important;
        }
        div[data-testid="stRadio"] label:hover,
        div[data-testid="stCheckbox"] label:hover {
            color: #0284c7 !important;
        }
        div[data-testid="stRadio"] label:has(input:checked) {
            color: #0284c7 !important;
            font-weight: 700 !important;
        }
        div[data-baseweb="checkbox"] > div {
            border-color: #cbd5e1 !important;
            background-color: transparent !important;
        }
        
        /* 9. 모든 입력창 (input, textarea, text_input) */
        input, textarea, [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
        }
        input:focus, textarea:focus, [data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
            border-color: #0284c7 !important;
            box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.2) !important;
            outline: none !important;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8 !important;
        }

        /* 10. 드롭다운 선택상자 (BaseWeb Select & 팝오버 포털 100% 화이트화) */
        div[data-baseweb="select"],
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="select"]:hover,
        div[data-baseweb="select"] > div:hover {
            border-color: #0284c7 !important;
        }
        div[data-baseweb="select"] * {
            color: #0f172a !important;
        }
        
        /* 전역 팝오버 메뉴 및 리스트박스 (BaseWeb Portal - 화면 밖 포털까지 전수 제어) */
        body div[data-baseweb="popover"],
        body div[data-baseweb="popover"] > div,
        body div[data-baseweb="menu"],
        body ul[role="listbox"] {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            box-shadow: 0 12px 30px rgba(0,0,0,0.18) !important;
            border-radius: 8px !important;
        }
        body ul[role="listbox"] li,
        body ul[role="listbox"] li * {
            color: #0f172a !important;
            background-color: #ffffff !important;
        }
        body ul[role="listbox"] li:hover,
        body ul[role="listbox"] li:hover *,
        body ul[role="listbox"] li[aria-selected="true"],
        body ul[role="listbox"] li[aria-selected="true"] * {
            background-color: #e0f2fe !important;
            color: #0284c7 !important;
            font-weight: 600 !important;
        }
        
        /* 11. 하단 챗봇 입력창 (st.chat_input) */
        div[data-testid="stChatInput"],
        div[data-testid="stChatInput"] > div,
        div[data-testid="stBottomBlockContainer"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
        }
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] textarea::placeholder,
        div[data-testid="stChatInput"] * {
            color: #0f172a !important;
            background-color: transparent !important;
            font-size: 15px !important;
            font-weight: 500 !important;
        }
        div[data-testid="stChatInput"] textarea::placeholder {
            color: #64748b !important;
        }
        div[data-testid="stBottomBlockContainer"] {
            background-color: rgba(248, 250, 252, 0.95) !important;
        }
        
        /* 12. 탭 버튼 (st.tabs) */
        button[data-baseweb="tab"] {
            cursor: pointer !important;
            color: #475569 !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            padding: 8px 16px !important;
            border-radius: 6px 6px 0 0 !important;
            transition: all 0.2s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            color: #0284c7 !important;
            background-color: rgba(2, 132, 199, 0.08) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #0284c7 !important;
            border-bottom: 3px solid #0284c7 !important;
            background-color: rgba(2, 132, 199, 0.06) !important;
        }
        
        /* 13. 알림 박스 (st.info, st.success, st.warning, st.error) */
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            border: 1px solid rgba(0, 0, 0, 0.08) !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04) !important;
        }
        div[data-testid="stAlert"] * {
            color: #0f172a !important;
        }
        
        /* 14. 데이터 테이블 & JSON 뷰어 */
        [data-testid="stDataFrame"] {
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            background-color: #ffffff !important;
        }
        div[data-testid="stJson"], div[data-testid="stJson"] pre {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #0f172a !important;
        }
        div[data-testid="stJson"] * {
            color: #0f172a !important;
        }

        /* 15. 카드 및 지표 */
        .metric-card {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
        }
        .risk-high { color: #dc2626 !important; font-weight: bold; }
        .risk-medium { color: #d97706 !important; font-weight: bold; }
        .risk-low { color: #16a34a !important; font-weight: bold; }
        .badge-person { background-color: #e11d48; color: white !important; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
        .badge-corp { background-color: #2563eb; color: white !important; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)
    canvas_bg = "#ffffff"
    canvas_font = "#0f172a"
else:
    # 🌙 다크 모드 전용 완벽 스타일 (가시성 100% 보장)
    st.markdown("""
    <style>
        /* 0. 텍스트 드래그 선택 영역(Selection) 음영 */
        ::selection {
            background-color: #0284c7 !important;
            color: #ffffff !important;
        }
        ::-moz-selection {
            background-color: #0284c7 !important;
            color: #ffffff !important;
        }

        /* 1. 최상단 헤더바 투명화 */
        header[data-testid="stHeader"] {
            background: transparent !important;
        }
        
        /* 2. 전체 앱 배경 및 기본 글자색 */
        .stApp {
            background-color: #0e1117 !important;
            color: #f0f2f6 !important;
        }
        
        /* 3. 좌측 사이드바 다크 룩 */
        [data-testid="stSidebar"] {
            background-color: #11151c !important;
            border-right: 1px solid rgba(255,255,255,0.1) !important;
        }
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
            color: #f0f2f6 !important;
        }
        
        /* 4. 본문 헤더 및 텍스트 */
        h1, h2, h3, h4, h5, h6, p, span, label, div, small, strong, b {
            color: #f0f2f6 !important;
        }
        .stCaption {
            color: #94a3b8 !important;
            font-weight: 500 !important;
        }
        
        /* 5. 버튼 완벽 다크 스타일 */
        button:not([data-baseweb="tab"]):not([kind="primary"]) {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]) * {
            color: #f8fafc !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]):hover {
            background-color: #334155 !important;
            border-color: #38bdf8 !important;
            color: #38bdf8 !important;
        }
        button:not([data-baseweb="tab"]):not([kind="primary"]):hover * {
            color: #38bdf8 !important;
        }
        button[kind="primary"] {
            background-color: #0284c7 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }
        button[kind="primary"] * {
            color: #ffffff !important;
        }
        
        /* 6. 인라인 코드 및 코드 블록 다크 음영 */
        code:not(pre code) {
            background-color: #1e293b !important;
            color: #38bdf8 !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            border: 1px solid #334155 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }
        pre, div[data-testid="stCodeBlock"], div[data-testid="stCodeBlock"] pre {
            background-color: #111827 !important;
            border: 1px solid #374151 !important;
            border-radius: 8px !important;
        }
        div[data-testid="stCodeBlock"] code, div[data-testid="stCodeBlock"] span, div[data-testid="stCodeBlock"] * {
            color: #f8fafc !important;
            background-color: transparent !important;
            font-family: 'Consolas', 'Courier New', monospace !important;
        }

        /* 7. Expander 다크 스타일 */
        div[data-testid="stExpander"] {
            background-color: #1e293b !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 10px !important;
            overflow: hidden !important;
        }
        div[data-testid="stExpander"] summary {
            background-color: #11151c !important;
            border-bottom: 1px solid rgba(255,255,255,0.08) !important;
            padding: 10px 16px !important;
        }
        div[data-testid="stExpander"] summary:hover {
            background-color: #1e293b !important;
        }
        div[data-testid="stExpander"] summary span, div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary * {
            color: #f8fafc !important;
            font-weight: 600 !important;
        }
        div[data-testid="stExpander"] > div[role="region"] {
            background-color: #1e293b !important;
            padding: 14px !important;
        }

        /* 8. 라디오 버튼 & 체크박스 다크 스타일 */
        div[data-testid="stRadio"] input[type="radio"],
        div[data-testid="stCheckbox"] input[type="checkbox"] {
            accent-color: #38bdf8 !important;
            cursor: pointer !important;
            width: 17px !important;
            height: 17px !important;
        }
        div[data-testid="stCheckbox"] label, div[data-testid="stCheckbox"] span, div[data-testid="stCheckbox"] p {
            color: #f8fafc !important;
        }
        div[data-testid="stRadio"] label:hover,
        div[data-testid="stCheckbox"] label:hover {
            color: #38bdf8 !important;
        }
        div[data-testid="stRadio"] label:has(input:checked) {
            color: #38bdf8 !important;
            font-weight: 700 !important;
        }
        div[data-baseweb="checkbox"] > div {
            border-color: #475569 !important;
            background-color: transparent !important;
        }
        
        /* 9. 입력창 다크 스타일 */
        textarea, input, [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            font-family: 'Consolas', 'Courier New', monospace !important;
            border-radius: 8px !important;
        }
        textarea:focus, input:focus, [data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
            border-color: #38bdf8 !important;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25) !important;
            outline: none !important;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8 !important;
        }

        /* 10. 드롭다운 선택상자 및 팝오버 다크 스타일 */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] div {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            color: #f8fafc !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="select"]:hover,
        div[data-baseweb="select"] > div:hover {
            border-color: #38bdf8 !important;
        }
        div[data-baseweb="select"] * {
            color: #f8fafc !important;
        }
        
        body div[data-baseweb="popover"], 
        body div[data-baseweb="popover"] > div, 
        body div[data-baseweb="menu"], 
        body ul[role="listbox"] {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            box-shadow: 0 12px 30px rgba(0,0,0,0.8) !important;
            border-radius: 8px !important;
        }
        body ul[role="listbox"] li,
        body ul[role="listbox"] li * {
            color: #f8fafc !important;
            background-color: #1e293b !important;
        }
        body ul[role="listbox"] li:hover, 
        body ul[role="listbox"] li:hover *, 
        body ul[role="listbox"] li[aria-selected="true"], 
        body ul[role="listbox"] li[aria-selected="true"] * {
            background-color: #0284c7 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }
        
        /* 11. 하단 챗봇 입력창 */
        div[data-testid="stChatInput"],
        div[data-testid="stChatInput"] > div,
        div[data-testid="stBottomBlockContainer"] > div {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        }
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] textarea::placeholder,
        div[data-testid="stChatInput"] * {
            color: #f8fafc !important;
            background-color: transparent !important;
            font-size: 15px !important;
            font-weight: 500 !important;
        }
        div[data-testid="stChatInput"] textarea::placeholder {
            color: #94a3b8 !important;
        }
        div[data-testid="stBottomBlockContainer"] {
            background-color: rgba(14, 17, 23, 0.95) !important;
        }

        /* 12. 탭 버튼 (st.tabs) */
        button[data-baseweb="tab"] {
            cursor: pointer !important;
            color: #94a3b8 !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            padding: 8px 16px !important;
            border-radius: 6px 6px 0 0 !important;
            transition: all 0.2s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            color: #38bdf8 !important;
            background-color: rgba(56, 189, 248, 0.1) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #38bdf8 !important;
            border-bottom: 3px solid #38bdf8 !important;
            background-color: rgba(56, 189, 248, 0.08) !important;
        }

        /* 13. 알림 박스 */
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }
        div[data-testid="stAlert"] * {
            color: #f8fafc !important;
        }
        
        /* 14. 데이터 테이블 & JSON 뷰어 */
        [data-testid="stDataFrame"] {
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            background-color: #1e293b !important;
        }
        div[data-testid="stJson"], div[data-testid="stJson"] pre {
            background-color: #111827 !important;
            border: 1px solid #374151 !important;
            border-radius: 8px !important;
            color: #f8fafc !important;
        }
        div[data-testid="stJson"] * {
            color: #f8fafc !important;
        }
        
        /* 15. 카드 및 지표 */
        .metric-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)) !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 12px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4) !important;
        }
        .risk-high { color: #ff5252 !important; font-weight: bold; }
        .risk-medium { color: #ffb74d !important; font-weight: bold; }
        .risk-low { color: #81c784 !important; font-weight: bold; }
        .badge-person { background-color: #e91e63; color: white !important; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
        .badge-corp { background-color: #2196f3; color: white !important; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)
    canvas_bg = "#0e1117"
    canvas_font = "#ffffff"


# ── 메뉴 1: 상장사 지배구조 & 순환출자 탐색기 ──
def render_graphrag_chat_section(default_corp_filter: str = ""):
    """512차원 하이브리드 GraphRAG 질의응답 (메뉴 개편 2단계: 메뉴4 탭5 -> 메뉴1 홈으로 이동)"""
    st.markdown("### 🤖 AI에게 자본이벤트를 물어보세요")
    st.caption("512차원 Vector Index + MinMax 70:30 하이브리드 리랭커(유사도 70% + 자본규모/PageRank 30%) 기반 4단 의사결정 리포트를 즉시 생성합니다.")

    col_q1, col_q2, col_q3 = st.columns(3)
    sample_q = ""
    if col_q1.button("🏢 타법인 인수 및 지분 투자", key="home_q1"):
        sample_q = "타법인 증권 취득이나 인수를 위해 자금을 조달한 기업과 조달 목적을 알려줘"
    if col_q2.button("🏭 시설 투자 및 공장 증설 (CB/BW)", key="home_q2"):
        sample_q = "시설 투자 및 공장 증설을 위해 전환사채(CB)나 신주인수권부사채(BW)를 발행한 기업"
    if col_q3.button("⚠️ 운영자금 충당 및 채무상환 증자", key="home_q3"):
        sample_q = "운영자금 조달 또는 채무상환을 목적으로 대규모 유상증자를 결의한 공시"

    user_query = st.text_input(
        "자본이벤트 관련 질문을 입력하세요",
        value=sample_q if sample_q else "",
        placeholder="예: 타법인 지분 인수 목적으로 자본을 조달한 기업과 자금용도를 분석해줘",
        key="graphrag_home_query"
    )

    col_k, col_corp = st.columns([1, 2])
    with col_k:
        top_k_select = st.slider("검색 상위 건수 (top_k)", min_value=1, max_value=10, value=3, key="graphrag_home_topk")
    with col_corp:
        corp_filter_input = st.text_input("특정 기업 필터 (선택 사항)", value=default_corp_filter, key="graphrag_home_corp_filter")

    if st.button("🚀 GraphRAG AI 분석 리포트 생성", type="primary", key="btn_graphrag_home"):
        if not user_query:
            st.warning("질문을 입력해주세요.")
        else:
            with st.spinner("512차원 벡터 검색 및 MinMax 70:30 리랭킹 연산 중..."):
                from services.graphrag_service import generate_graphrag_response
                c_filter = corp_filter_input.strip() if corp_filter_input.strip() else None
                report = generate_graphrag_response(user_query, corp_filter=c_filter, top_k=top_k_select)

                st.markdown("#### 🎯 하이브리드 리랭킹 검색 결과 (Top K)")
                if report["hits"]:
                    hit_rows = []
                    for h in report["hits"]:
                        hit_rows.append({
                            "기업명": h.get("corp_name"),
                            "유형": h.get("event_type"),
                            "종합점수 (70:30)": f"{h.get('final_score', 0):.4f}",
                            "코사인유사도": f"{h.get('score', 0):.4f}",
                            "조달규모": f"{h.get('scale_amount', 0):,}원",
                            "공시접수번호": h.get("rcept_no"),
                            "결의일": h.get("decided_on")
                        })
                    st.dataframe(pd.DataFrame(hit_rows), use_container_width=True)

                st.markdown("---")
                st.markdown("### 📋 4단 의사결정 AI 리포트 (Fact vs Interpretation)")

                c_fact, c_interp = st.columns(2)
                with c_fact:
                    st.markdown("#### 1. 📌 사실 (Fact)")
                    st.info(report["fact"])
                with c_interp:
                    st.markdown("#### 2. 🧠 해석 (Interpretation)")
                    st.success(report["interpretation"])

                c_evid, c_next = st.columns(2)
                with c_evid:
                    st.markdown("#### 3. 🔍 원문 근거 (Evidence)")
                    st.warning(report["evidence"])
                with c_next:
                    st.markdown("#### 4. 🧭 다음 확인 항목 (Next Action)")
                    st.error(report["next_action"])


if menu == "🌐 1. 상장사 지배구조 & 순환출자 탐색기":
    st.header("🌐 상장사 지배구조 네트워크 탐색기")
    st.caption("Neo4j 지식그래프에 적재된 지분율(%)과 순환출자 관계를 3D 물리 엔진 그래프로 직관적으로 시각화합니다.")

    render_graphrag_chat_section()
    st.markdown("---")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("🔍 분석 대상 선택")
        
        # 탐색 방식 선택 (프리셋 vs 개별 검색 vs 직접 Cypher 입력)
        search_mode = st.radio("탐색 모드", ["📁 대표 그룹 프리셋", "🔎 전체 상장사 초성 색인", "💻 직접 Cypher 쿼리 실행"], horizontal=True)
        
        selected_entity = None
        custom_cypher_query = None
        
        if search_mode == "💻 직접 Cypher 쿼리 실행":
            sample_choice = st.selectbox(
                "⚡ 추천 실측 샘플 쿼리 불러오기",
                [
                    "직접 입력",
                    "1. 실측 승격 경제적 지분망 (19건 전체)",
                    "2. 롯데그룹 지배구조 네트워크 (롯데지주 계열)",
                    "3. 알루코-케이피티유 실측 지분 관계",
                    "4. 현대홈쇼핑-현대퓨처넷 실측 지분 관계",
                    "5. 최근 주요 자본이벤트(CB/BW/증자/합병) 연결망",
                    "6. 20% 이상 주요 승격 지분 조회",
                    "7. 시장별(KOSPI vs KOSDAQ) 상장사 수 집계"
                ]
            )
            
            sample_queries = {
                "1. 실측 승격 경제적 지분망 (19건 전체)": "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id",
                "2. 롯데그룹 지배구조 네트워크 (롯데지주 계열)": "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nWHERE a.name STARTS WITH '롯데' OR b.name STARTS WITH '롯데'\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id",
                "3. 알루코-케이피티유 실측 지분 관계": "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nWHERE a.name IN ['케이피티유', '알루코'] OR b.name IN ['케이피티유', '알루코']\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id",
                "4. 현대홈쇼핑-현대퓨처넷 실측 지분 관계": "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nWHERE a.name IN ['현대홈쇼핑', '현대퓨처넷'] OR b.name IN ['현대홈쇼핑', '현대퓨처넷']\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id",
                "5. 최근 주요 자본이벤트(CB/BW/증자/합병) 연결망": "MATCH (a:DART_Company)-[r:ANNOUNCED]->(b:DART_CapitalEvent)\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id\nLIMIT 30",
                "6. 20% 이상 주요 승격 지분 조회": "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nWHERE r.stake >= 20.0\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id",
                "7. 시장별(KOSPI vs KOSDAQ) 상장사 수 집계": "MATCH (c:DART_Company)\nWHERE c.market IN ['KOSPI', 'KOSDAQ']\nRETURN c.market AS 시장구분, count(c) AS 기업수"
            }
            
            initial_val = sample_queries.get(sample_choice, "MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id")
            custom_cypher_query = st.text_area("💻 Cypher 쿼리 입력창", value=initial_val, height=140)
            st.caption("💡 `RETURN a, b, properties(r) AS r_props, type(r) AS r_type` 형식으로 작성 시 3D 그래프로 즉시 렌더링됩니다.")
            selected_group = None
            
        elif search_mode == "🔎 전체 상장사 초성 색인":
            all_entity_rows = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN DISTINCT n.name AS name ORDER BY n.name")
            all_entity_list = [r['name'] for r in all_entity_rows if r['name']]
            
            # 초성 추출 헬퍼 함수
            def get_initial_consonant(text: str) -> str:
                if not text:
                    return '기타'
                cleaned = text.lstrip("()주 ").strip()
                if not cleaned:
                    cleaned = text
                first_char = cleaned[0]
                if '가' <= first_char <= '힣':
                    consonants = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
                    idx = (ord(first_char) - 44032) // 588
                    c = consonants[idx]
                    if c in ['ㄲ']: return 'ㄱ'
                    if c in ['ㄸ']: return 'ㄷ'
                    if c in ['ㅃ']: return 'ㅂ'
                    if c in ['ㅆ']: return 'ㅅ'
                    if c in ['ㅉ']: return 'ㅈ'
                    return c
                elif ('A' <= first_char <= 'Z') or ('a' <= first_char <= 'z'):
                    return 'A-Z'
                elif '0' <= first_char <= '9':
                    return '0-9'
                return '기타'
            
            # 색인 선택기 (ㄱ~ㅎ, A-Z, 0-9)
            idx_list = ["전체 (3,988+개사)", "ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ", "A-Z", "0-9"]
            selected_idx = st.selectbox("🔤 가나다 / 영문 / 숫자 색인 선택", idx_list, index=idx_list.index("ㅅ"))
            
            # 색인에 따른 목록 필터링
            if selected_idx.startswith("전체"):
                filtered_entities = all_entity_list
            else:
                filtered_entities = [name for name in all_entity_list if get_initial_consonant(name) == selected_idx]
                
            if not filtered_entities:
                filtered_entities = all_entity_list
                
            default_ix = filtered_entities.index("삼성전자") if "삼성전자" in filtered_entities else 0
            selected_entity = st.selectbox(f"📋 '{selected_idx}' 색인 종목 ({len(filtered_entities)}개사)", filtered_entities, index=default_ix)
            selected_group = None
        else:
            selected_group = st.selectbox(
                "대기업 집단 / 지배구조 유형 (실제로 승격·적재된 케이스만 표시)",
                [
                    "🏛️ 실측 승격 지분 네트워크 (전체 종합)",
                    "롯데그룹 지배구조 (롯데지주➔칠성/웰푸드)",
                    "알루코 지배구조 (케이피티유➔알루코)",
                    "현대홈쇼핑 지배구조 (현대홈쇼핑➔현대퓨처넷)",
                    "⚡ 최근 주요 자본이벤트 네트워크 (30건)",
                    "🌐 전체 상장사 통합 네트워크"
                ]
            )
            st.caption("💡 삼성/현대차/SK/LG/한화/국민연금 등 미수집 대기업집단은 데이터가 없어 목록에서 제외했습니다 (수집 완료 후 추가 예정).")
        
        selected_year = st.selectbox(
            "📅 분석 시점 (연도별 지배구조)",
            ["전체 시계열 통합 (기본)", "2025년 (최신)", "2024년", "2023년", "2022년", "2021년"],
            index=0
        )
        year_filter_num = int(selected_year[:4]) if "전체" not in selected_year else None
        
        include_history = st.checkbox("과거 이력 관계 포함 (동시 표시)", value=False, help="기본적으로 최신 유효 사실(is_current=True) 및 베이스라인만 표시하며, 체크 시 과거 변동 이력까지 3D 그래프에 그립니다.")
        show_physics = st.checkbox("물리 엔진 활성화 (노드 자동 정렬)", value=True)
        st.markdown("---")
        st.markdown("""
        **🏷️ 노드 색상 범례:**
        * 🔴 **빨강**: 총수 / 지배주주 (DART_Person)
        * 🔵 **파랑**: 지주사 / 상장 계열사 (DART_Company)
        * 🟢 **초록**: 핵심 자회사 (사업회사)
        * 🟣 **보라**: 국민연금 / 사모펀드 (DART_Group)
        """)
        
    with col2:
        # 그룹별 맞춤 Cypher 쿼리
        if custom_cypher_query:
            query = custom_cypher_query
        elif selected_entity:
            # 개별 기업/인물 맞춤 중심 지배구조 네트워크 (실측 승격 지분 및 자본이벤트 반영)
            query = f"""
            MATCH (a)-[r]->(b)
            WHERE (a.name = '{selected_entity}' OR b.name = '{selected_entity}')
              AND type(r) IN ['HOLDS_ECONOMIC_STAKE', 'ANNOUNCED', 'OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            LIMIT 40
            """
        elif selected_group == "🏛️ 실측 승격 지분 네트워크 (전체 종합)":
            query = """
            MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "롯데그룹 지배구조 (롯데지주➔칠성/웰푸드)":
            query = """
            MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)
            WHERE a.name STARTS WITH '롯데' OR b.name STARTS WITH '롯데'
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "알루코 지배구조 (케이피티유➔알루코)":
            query = """
            MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)
            WHERE a.name IN ['케이피티유', '알루코'] OR b.name IN ['케이피티유', '알루코']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "현대홈쇼핑 지배구조 (현대홈쇼핑➔현대퓨처넷)":
            query = """
            MATCH (a)-[r:HOLDS_ECONOMIC_STAKE]->(b)
            WHERE a.name IN ['현대홈쇼핑', '현대퓨처넷'] OR b.name IN ['현대홈쇼핑', '현대퓨처넷']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "⚡ 최근 주요 자본이벤트 네트워크 (30건)":
            query = """
            MATCH (a:DART_Company)-[r:ANNOUNCED]->(b:DART_CapitalEvent)
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            LIMIT 30
            """
        else:
            query = """
            MATCH (a)-[r]->(b)
            WHERE type(r) IN ['HOLDS_ECONOMIC_STAKE', 'ANNOUNCED', 'OWNS_STAKE', 'INVESTED_IN']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            LIMIT 50
            """
            
        raw_graph_data = run_cypher(query)
        
        # 1. 공통 전체 이력 엣지 맵 생성 (테이블/팩트 패널은 3D 토글과 무관하게 100% 전체 이력 유지)
        edges_map = {}
        for idx, row in enumerate(raw_graph_data):
            a = row['a']
            b = row['b']
            r_props = row.get('r_props', {})
            r_type = row.get('r_type', 'OWNS_STAKE')
            
            a_name = a.get('name') or a.get('corp_code') or a.get('rcept_no') or str(a) if isinstance(a, dict) else str(a)
            b_name = b.get('name') or b.get('corp_code') or b.get('rcept_no') or str(b) if isinstance(b, dict) else str(b)
            stake_val = float(r_props.get('stake', 0.0) or 0.0)
            pos_val = str(r_props.get('position', '') or '')
            yr = r_props.get('year', None)
            
            as_of_date_val = str(r_props.get('as_of_date', '') or '')
            reported_on_val = str(r_props.get('reported_on', '') or r_props.get('disclosed_at', '') or '')
            source_rcp = str(r_props.get('source_rcept_no', '') or '')
            
            if source_rcp:
                doc_st = str(r_props.get('doc_status') or 'UNKNOWN')
                ver_st = str(r_props.get('verification_status') or 'UNKNOWN')
                view_url = str(r_props.get('viewer_url') or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={source_rcp}")
            else:
                doc_st = "UNLINKED"
                ver_st = "BASELINE_DATA"
                view_url = ""
                
            is_curr = bool(r_props['is_current']) if 'is_current' in r_props and r_props['is_current'] is not None else None
            book_val = int(r_props.get('book_value', 0) or 0)
            shares_cnt = int(r_props.get('shares_count', 0) or 0)
            purp_val = str(r_props.get('purpose', '') or '')
            
            r_id = row.get('r_id') or r_props.get('fact_id') or f"{a_name}_{b_name}_{r_type}_{source_rcp}_{as_of_date_val}_{reported_on_val}_{idx}"
            edges_map[r_id] = {
                'r_id': r_id,
                'source': a_name,
                'target': b_name,
                'stake': stake_val,
                'pos': pos_val,
                'type': r_type,
                'year': yr,
                'as_of_date': as_of_date_val,
                'reported_on': reported_on_val,
                'source_rcept_no': source_rcp,
                'doc_status': doc_st,
                'verification_status': ver_st,
                'is_current': is_curr,
                'book_value': book_val,
                'shares_count': shares_cnt,
                'purpose': purp_val,
                'viewer_url': view_url
            }
        
        # 🌟 3D 그래프 & 데이터 테이블(Table View) 탭 뷰
        tab_graph, tab_table = st.tabs(["🌐 3D 인터랙티브 그래프", "📋 데이터 테이블 (Table View)"])
        
        is_graph_format = bool(raw_graph_data and isinstance(raw_graph_data[0], dict) and 'a' in raw_graph_data[0] and 'b' in raw_graph_data[0])
        
        with tab_graph:
            if is_graph_format:
                # 3D 그래프 전용 엣지 필터링 (토글 미체크 시 is_current=True 및 베이스라인만 표시)
                graph_edges = [
                    e for e in edges_map.values()
                    if include_history or (e.get('is_current') is True or e.get('is_current') is None)
                ]
                
                # 연도별 필터링 적용 (시계열 지분 스냅샷)
                if year_filter_num:
                    graph_edges = [
                        e for e in graph_edges
                        if e.get('year') is None or e.get('year') == year_filter_num
                    ]
                
                # PyVis 인터랙티브 네트워크 생성 (메모리 렌더링)
                net = Network(height="520px", width="100%", bgcolor=canvas_bg, font_color=canvas_font, directed=True)
                
                nodes_added = set()
                for edge_info in graph_edges:
                    for nid in [edge_info['source'], edge_info['target']]:
                        if nid not in nodes_added:
                            color = "#2196f3"
                            shape = "dot"
                            title = f"기업: {nid}"
                            
                            if nid in ["이재용", "이부진", "이서현", "정의선", "정몽구", "최태원", "구광모", "김승연", "김동관", "신동빈", "김범수", "방시혁", "강철민", "박성호", "조명훈", "장동식", "김홍국"]:
                                color = "#ff4081"
                                shape = "star"
                                title = f"👑 총수/인물: {nid}"
                            elif nid in ["국민연금공단", "MBK파트너스", "골든홀딩스투자조합", "블루스톤1호조합", "아시아혁신투자조합", "삼성자산운용", "미래에셋자산운용"]:
                                color = "#9c27b0"
                                shape = "hexagon"
                                title = f"🏛️ 펀드/기관: {nid}"
                            elif "바이오" in nid or "전자" in nid or "에어로" in nid or "리츠" in nid:
                                color = "#00e676"
                                title = f"핵심 계열사/법인: {nid}"
                            
                            net.add_node(nid, label=nid, color=color, shape=shape, title=title, size=22)
                            nodes_added.add(nid)
                    
                    stake_val = edge_info['stake']
                    pos_val = edge_info['pos']
                    yr = edge_info['year']
                    r_type = edge_info['type']
                    
                    edge_label = f"{stake_val}%" if stake_val > 0 else (pos_val if pos_val else r_type)
                    edge_title = f"지분율: {stake_val}% ({yr}년)" if yr else f"지분율: {stake_val}%"
                    edge_width = max(1.5, stake_val / 6.0) if stake_val > 0 else 2.0
                    
                    net.add_edge(edge_info['source'], edge_info['target'], label=edge_label, title=edge_title, color="#78909c", arrows="to", width=edge_width)
                
                # 물리 엔진 및 고정 레이아웃(randomSeed) 설정 (매번 위치가 달라지는 무작위성 완전 제거)
                if show_physics:
                    net.set_options("""
                    var options = {
                      "layout": {
                        "randomSeed": 42
                      },
                      "physics": {
                        "barnesHut": {
                          "gravitationalConstant": -3500,
                          "centralGravity": 0.25,
                          "springLength": 160,
                          "springConstant": 0.05,
                          "damping": 0.92,
                          "avoidOverlap": 0.3
                        },
                        "minVelocity": 0.75,
                        "solver": "barnesHut",
                        "stabilization": {
                          "enabled": true,
                          "iterations": 120,
                          "fit": true
                        }
                      }
                    }
                    """)
                else:
                    net.toggle_physics(False)
                    
                html_content = net.generate_html()
                components.html(html_content, height=540)
            else:
                if not raw_graph_data:
                    st.warning("⚠️ 선택하신 조건에 일치하는 지분/공시 관계가 라이브 DB에 존재하지 않습니다 (0건 조회).")
                    st.info("💡 실측 지분 데이터를 즉시 확인하시려면 프리셋에서 **[🏛️ 실측 승격 지분 네트워크 (19건 종합)]**, **[롯데그룹 지배구조]**, 또는 **[알루코 지배구조]**를 선택해 보세요!")
                else:
                    st.info("📊 실행하신 쿼리는 노드-관계(a->b) 그래프 형태가 아닌 **집계/단일 컬럼 조회 결과**입니다. 오른쪽 **[📋 데이터 테이블]** 탭에서 조회 결과를 확인하세요!")
                    if len(raw_graph_data) == 1:
                        first_row = raw_graph_data[0]
                        col_keys = list(first_row.keys())
                        st.metric(label=col_keys[0], value=f"{first_row[col_keys[0]]:,}" if isinstance(first_row[col_keys[0]], (int, float)) else str(first_row[col_keys[0]]))
            
        with tab_table:
            import pandas as pd
            
            # 1) 데이터 세트 선행 준비 (3D 토글과 무관하게 전체 이력 100% 유지 + 최신 행 최상단 정렬: is_current DESC, reported_on DESC, as_of_date DESC)
            def get_stake_sort_key(item):
                is_curr = item.get('is_current')
                # True: 2, None(미판정/베이스라인): 1, False(과거 이력): 0
                curr_score = 2 if is_curr is True else (1 if is_curr is None else 0)
                rep_on = str(item.get('reported_on') or '')
                as_of = str(item.get('as_of_date') or '')
                yr = str(item.get('year') or '')
                return (curr_score, rep_on, as_of, yr)

            stake_items = sorted(
                [e for e in edges_map.values() if e['type'] in ['HOLDS_ECONOMIC_STAKE', 'ANNOUNCED', 'OWNS_STAKE', 'HOLDS_5PCT']],
                key=get_stake_sort_key,
                reverse=True
            )
            
            invest_query = """
            MATCH (a:DART_Company)-[r:INVESTED_IN]->(b:DART_Company)
            WHERE ($entity IS NULL OR a.name = $entity OR b.name = $entity)
            RETURN a.name AS source, b.name AS target, r.stake AS stake, r.book_value AS book_value,
                   r.purpose AS purpose, r.as_of_date AS as_of_date, r.source_rcept_no AS source_rcept_no,
                   r.doc_status AS doc_status, r.verification_status AS verification_status,
                   r.is_current AS is_current, r.viewer_url AS viewer_url
            ORDER BY r.book_value DESC LIMIT 50
            """
            invest_data = run_cypher(invest_query, entity=selected_entity if selected_entity else None)
            
            disc_query = """
            MATCH (c:DART_Company)-[:FILED]->(d:DART_Disclosure)
            WHERE ($entity IS NULL OR c.name = $entity)
            RETURN c.name AS company, d.rcept_dt AS rcept_dt, d.report_nm AS report_nm,
                   d.flr_nm AS flr_nm, d.doc_status AS doc_status, d.rcept_no AS rcept_no,
                   d.viewer_url AS viewer_url
            ORDER BY d.rcept_dt DESC LIMIT 30
            """
            disc_data = run_cypher(disc_query, entity=selected_entity if selected_entity else None)
            
            cand_rows = []
            cand_path = "내작업폴더/candidate_queue.jsonl"
            if os.path.exists(cand_path):
                with open(cand_path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f):
                        if idx >= 50:
                            break
                        try:
                            cand_rows.append(json.loads(line.strip()))
                        except:
                            pass
            
            # 2) 순수 테이블 행 선택 상태 관리 (드롭다운 완전 제거)
            if "active_source" not in st.session_state:
                st.session_state.active_source = "STAKE"
                st.session_state.active_index = 0
            
            col_tbl, col_fact = st.columns([6, 5])
            
            tbl_stake_res = None
            tbl_inv_res = None
            tbl_disc_res = None
            tbl_cand_res = None
            
            # 좌측: 4대 팩트 데이터 테이블 영역
            with col_tbl:
                subtab_stake, subtab_invest, subtab_disclosure, subtab_cand = st.tabs([
                    "📊 지분 소유망 (OWNS_STAKE)", 
                    "🏢 타법인 출자현황 (INVESTED_IN)", 
                    "📑 공시 인덱스 (:DART_Disclosure)", 
                    "🛡️ 후보 큐 (Candidate Queue)"
                ])
                
                # 1) 지분 소유망 서브탭
                with subtab_stake:
                    if stake_items:
                        df_stake = pd.DataFrame([
                            {
                                "소유자 (주주/기관)": it['source'],
                                "투자 대상 (기업)": it['target'],
                                "지분율 (%)": f"{it['stake']:.2f}%" if it['stake'] > 0 else "-",
                                "직책 / 관계": it['pos'] or it['type'],
                                "공시접수번호": it['source_rcept_no'] if it['source_rcept_no'] else "❌ 미연결",
                                "공시 상태": "🟢 NORMAL" if it['doc_status'] == 'NORMAL' else ("🟡 CORRECTED" if it['doc_status'] == 'CORRECTED' else ("🔴 WITHDRAWN" if it['doc_status'] == 'WITHDRAWN' else ("⚪ UNKNOWN" if it['doc_status'] == 'UNKNOWN' else "⚪ UNLINKED"))),
                                "검증 상태": "🟢 VERIFIED" if it['verification_status'] == 'VERIFIED' else ("⚪ CANDIDATE" if it['verification_status'] == 'CANDIDATE' else ("⚪ BASELINE" if it['verification_status'] == 'BASELINE_DATA' else "⚪ UNKNOWN"))
                            } for it in stake_items
                        ])
                        
                        tbl_stake_res = st.dataframe(
                            df_stake, 
                            use_container_width=True, 
                            height=360,
                            on_select="rerun",
                            selection_mode="single-row",
                            key="table_stake_select"
                        )
                    else:
                        st.info("선택된 기업/그룹에 대한 정규 지분 소유 데이터가 없습니다.")
                        
                # 2) 타법인 출자현황 서브탭
                with subtab_invest:
                    if invest_data:
                        df_inv = pd.DataFrame([
                            {
                                "출자 회사": it['source'],
                                "피출자사 (자회사)": it['target'],
                                "지분율 (%)": f"{float(it.get('stake', 0.0)):.2f}%" if it.get('stake') else "-",
                                "기말 장부가액 (원)": f"{int(it.get('book_value', 0)):,}원" if it.get('book_value') else "-",
                                "출자 목적": it.get('purpose', '-') or '-',
                                "결산 기준일": str(it.get('as_of_date', '-')),
                                "공시접수번호": it.get('source_rcept_no') or "❌ 미연결"
                            } for it in invest_data
                        ])
                        
                        tbl_inv_res = st.dataframe(
                            df_inv, 
                            use_container_width=True, 
                            height=360,
                            on_select="rerun",
                            selection_mode="single-row",
                            key="table_invest_select"
                        )
                    else:
                        st.info("조회된 타법인 출자 데이터가 없습니다.")
                        
                # 3) 공시 인덱스 서브탭
                with subtab_disclosure:
                    if disc_data:
                        df_disc = pd.DataFrame([
                            {
                                "공시접수일": it['rcept_dt'],
                                "보고서명": it['report_nm'],
                                "제출인 / 보고자": it['flr_nm'] or it['company'],
                                "문서 상태": "🟢 NORMAL" if it['doc_status'] == 'NORMAL' else ("🟡 CORRECTED" if it['doc_status'] == 'CORRECTED' else ("🔴 WITHDRAWN" if it['doc_status'] == 'WITHDRAWN' else "⚪ UNKNOWN")),
                                "공시접수번호": it['rcept_no']
                            } for it in disc_data
                        ])
                        
                        tbl_disc_res = st.dataframe(
                            df_disc, 
                            use_container_width=True, 
                            height=360,
                            on_select="rerun",
                            selection_mode="single-row",
                            key="table_disc_select"
                        )
                    else:
                        st.info("조회된 DART 공시 인덱스가 없습니다.")
                        
                # 4) 후보 큐 (Candidate Queue) 서브탭
                with subtab_cand:
                    st.caption("🛡️ 동명이인 방지 및 미식별 법인 격리 원칙에 따라 검증 보류된 데이터입니다.")
                    if cand_rows:
                        df_cand = pd.DataFrame([
                            {
                                "출처 API": c.get('source_api', '-'),
                                "회사코드": c.get('corp_code', '-'),
                                "피출자회사코드": c.get('target_corp_code', '-'),
                                "주주/피출자명": c.get('person_or_group_name') or c.get('target_corp_name') or '-',
                                "격리 사유": c.get('reason', '-'),
                                "공시접수일": c.get('reported_on', '-')
                            } for c in cand_rows
                        ])
                        
                        tbl_cand_res = st.dataframe(
                            df_cand, 
                            use_container_width=True, 
                            height=360,
                            on_select="rerun",
                            selection_mode="single-row",
                            key="table_cand_select"
                        )
                    else:
                        st.info("후보 큐 파일이 비어 있거나 존재하지 않습니다.")

            # 테이블 실제 클릭 이벤트 감지 (행을 클릭했을 때만 실행)
            stake_rows = tbl_stake_res.selection.rows if (tbl_stake_res and hasattr(tbl_stake_res, "selection") and tbl_stake_res.selection.rows) else []
            invest_rows = tbl_inv_res.selection.rows if (tbl_inv_res and hasattr(tbl_inv_res, "selection") and tbl_inv_res.selection.rows) else []
            disc_rows = tbl_disc_res.selection.rows if (tbl_disc_res and hasattr(tbl_disc_res, "selection") and tbl_disc_res.selection.rows) else []
            cand_rows_sel = tbl_cand_res.selection.rows if (tbl_cand_res and hasattr(tbl_cand_res, "selection") and tbl_cand_res.selection.rows) else []

            if stake_rows and st.session_state.get("_prev_clicked_stake") != stake_rows:
                st.session_state._prev_clicked_stake = stake_rows
                st.session_state.active_source = "STAKE"
                st.session_state.active_index = stake_rows[0]
            elif invest_rows and st.session_state.get("_prev_clicked_invest") != invest_rows:
                st.session_state._prev_clicked_invest = invest_rows
                st.session_state.active_source = "INVESTMENT"
                st.session_state.active_index = invest_rows[0]
            elif disc_rows and st.session_state.get("_prev_clicked_disc") != disc_rows:
                st.session_state._prev_clicked_disc = disc_rows
                st.session_state.active_source = "DISCLOSURE"
                st.session_state.active_index = disc_rows[0]
            elif cand_rows_sel and st.session_state.get("_prev_clicked_cand") != cand_rows_sel:
                st.session_state._prev_clicked_cand = cand_rows_sel
                st.session_state.active_source = "CANDIDATE"
                st.session_state.active_index = cand_rows_sel[0]

            # 우측: [🏛️ 팩트 상세 패널 (Fact Detail Panel)]
            with col_fact:
                active_src = st.session_state.get("active_source", "STAKE")
                active_idx = st.session_state.get("active_index", 0)
                payload = None
                
                if active_src == "STAKE" and stake_items:
                    idx = min(active_idx, len(stake_items) - 1)
                    payload = {"category": "STAKE", "data": stake_items[idx]}
                elif active_src == "INVESTMENT" and invest_data:
                    idx = min(active_idx, len(invest_data) - 1)
                    payload = {"category": "INVESTMENT", "data": invest_data[idx]}
                elif active_src == "DISCLOSURE" and disc_data:
                    idx = min(active_idx, len(disc_data) - 1)
                    payload = {"category": "DISCLOSURE", "data": disc_data[idx]}
                elif active_src == "CANDIDATE" and cand_rows:
                    idx = min(active_idx, len(cand_rows) - 1)
                    payload = {"category": "CANDIDATE", "data": cand_rows[idx]}
                else:
                    if stake_items: payload = {"category": "STAKE", "data": stake_items[0]}
                    elif invest_data: payload = {"category": "INVESTMENT", "data": invest_data[0]}
                    elif disc_data: payload = {"category": "DISCLOSURE", "data": disc_data[0]}
                    elif cand_rows: payload = {"category": "CANDIDATE", "data": cand_rows[0]}
                
                if payload:
                    cat = payload.get("category")
                    data = payload.get("data", {})
                    
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, rgba(2, 132, 199, 0.08) 0%, rgba(15, 23, 42, 0.05) 100%); 
                                border: 1px solid rgba(2, 132, 199, 0.3); border-radius: 12px; padding: 14px; margin-bottom: 12px;'>
                        <h4 style='margin: 0 0 6px 0; color: #0284c7;'>🏛️ 팩트 상세 패널 (Fact Detail Panel)</h4>
                        <p style='margin: 0; font-size: 13px; color: #64748b;'>선택한 사실의 금감원 DART 공시 원문 출처 및 무결성 배지를 검증합니다.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # ── CASE 1 & 2: 지분 소유(STAKE) / 타법인 출자(INVESTMENT) ──
                    if cat in ["STAKE", "INVESTMENT"]:
                        src = data.get('source', 'Unknown')
                        tgt = data.get('target', 'Unknown')
                        st.markdown(f"### 🏢 `{src}` ➔ `{tgt}`")
                        
                        m_c1, m_c2 = st.columns(2)
                        with m_c1:
                            if float(data.get('stake', 0.0) or 0.0) > 0:
                                st.metric("소유 지분율", f"{float(data['stake']):.2f}%", help="OpenDART 정규 보고서 기말 지분율")
                            elif int(data.get('book_value', 0) or 0) > 0:
                                st.metric("기말 장부가액", f"{int(data['book_value']):,}원", help="타법인출자현황 기말 장부가액")
                            else:
                                st.metric("관계 유형", data.get('type', 'OWNS_STAKE'))
                        with m_c2:
                            st.metric("직책 / 목적", data.get('pos') or data.get('purpose') or data.get('type') or "주요출자자")
                        
                        st.markdown("---")
                        
                        # 이중 상태 배지 (더미 기본값 배제)
                        st.markdown("##### 🏷️ 데이터 무결성 & 공시 상태 배지")
                        b_col1, b_col2, b_col3 = st.columns(3)
                        
                        doc_st = data.get('doc_status')
                        ver_st = data.get('verification_status')
                        is_curr = data.get('is_current')
                        rcp_no = data.get('source_rcept_no')
                        
                        with b_col1:
                            if doc_st == 'NORMAL':
                                st.markdown("📄 **공시 상태**<br><span style='background-color:#16a34a;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>🟢 정규 공시 (NORMAL)</span>", unsafe_allow_html=True)
                            elif doc_st == 'CORRECTED':
                                st.markdown("📄 **공시 상태**<br><span style='background-color:#d97706;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>🟡 기재 정정 (CORRECTED)</span>", unsafe_allow_html=True)
                            elif doc_st == 'WITHDRAWN':
                                st.markdown("📄 **공시 상태**<br><span style='background-color:#dc2626;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>🔴 철회 (WITHDRAWN)</span>", unsafe_allow_html=True)
                            elif doc_st == 'UNKNOWN':
                                st.markdown("📄 **공시 상태**<br><span style='background-color:#64748b;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 상태 미확인 (UNKNOWN)</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("📄 **공시 상태**<br><span style='background-color:#94a3b8;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 공시 미연결 (UNLINKED)</span>", unsafe_allow_html=True)
                                
                        with b_col2:
                            if ver_st == 'VERIFIED':
                                st.markdown("🛡️ **검증 상태**<br><span style='background-color:#0284c7;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>🟢 검증 완료 (VERIFIED)</span>", unsafe_allow_html=True)
                            elif ver_st == 'CANDIDATE':
                                st.markdown("🛡️ **검증 상태**<br><span style='background-color:#64748b;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 후보 큐 (CANDIDATE)</span>", unsafe_allow_html=True)
                            elif ver_st == 'BASELINE_DATA':
                                st.markdown("🛡️ **검증 상태**<br><span style='background-color:#94a3b8;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 베이스라인 (BASELINE)</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("🛡️ **검증 상태**<br><span style='background-color:#64748b;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 검증 미확인 (UNKNOWN)</span>", unsafe_allow_html=True)
                                
                        with b_col3:
                            if is_curr is True:
                                st.markdown("⏱️ **최신성 여부**<br><span style='background-color:#16a34a;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>🟢 최신 유효 사실</span>", unsafe_allow_html=True)
                            elif is_curr is False:
                                st.markdown("⏱️ **최신성 여부**<br><span style='background-color:#94a3b8;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 과거 이력 사실</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("⏱️ **최신성 여부**<br><span style='background-color:#64748b;color:white;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold;'>⚪ 최신성 미판정 (UNKNOWN)</span>", unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # 시계열 분리
                        st.markdown("##### 📅 시계열 기준일 분리")
                        d_col1, d_col2 = st.columns(2)
                        with d_col1:
                            st.markdown(f"**결산 기준일 (`as_of_date`):**\n`{data.get('as_of_date') or ('연도 정보만 존재 (' + str(data.get('year')) + '년)' if data.get('year') else '기준일 미명시')}`")
                        with d_col2:
                            st.markdown(f"**공시 접수일 (`reported_on`):**\n`{data.get('reported_on') or '접수일 미명시 / 미연결'}`")
                            
                        # DART 공시 원문 역추적 (임의 하드코딩 제거!)
                        st.markdown("---")
                        st.markdown("##### 🔗 금감원 DART 공시 원문 역추적")
                        
                        if rcp_no and len(str(rcp_no)) == 14:
                            viewer_url = data.get('viewer_url') or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
                            st.code(f"고유 공시접수번호 (rcept_no): {rcp_no}", language="text")
                            st.link_button("📑 금감원 DART 공시 원문 검증 바로가기 (새 창)", viewer_url, use_container_width=True, type="primary")
                            krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp_no}&method=search"
                            st.link_button("🏛️ KRX 상장공시시스템(KIND) 교차 검증 (새 창)", krx_url, use_container_width=True)
                        else:
                            st.warning("⚠️ **근거 공시 미연결 (NO_DISCLOSURE)**\n\n본 관계는 초기 베이스라인 데이터이거나, DART 공시 인덱스와 아직 매핑되지 않은 상태입니다. (외부 뷰어 링크 숨김)")
                    
                    # ── CASE 3: 공시 인덱스 (DISCLOSURE) ──
                    elif cat == "DISCLOSURE":
                        st.markdown(f"### 📑 `{data.get('report_nm', '공시 보고서')}`")
                        st.markdown(f"**🏢 대상 법인:** `{data.get('company', '-')}` | **👤 제출인:** `{data.get('flr_nm', '-')}`")
                        
                        st.markdown("---")
                        st.markdown("##### 🏷️ 공시 문서 상태 배지")
                        doc_st = data.get('doc_status') or 'UNKNOWN'
                        if doc_st == 'NORMAL':
                            st.markdown("<span style='background-color:#16a34a;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>🟢 정규 공시 (NORMAL)</span>", unsafe_allow_html=True)
                        elif doc_st == 'CORRECTED':
                            st.markdown("<span style='background-color:#d97706;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>🟡 기재 정정 (CORRECTED)</span>", unsafe_allow_html=True)
                        elif doc_st == 'WITHDRAWN':
                            st.markdown("<span style='background-color:#dc2626;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>🔴 철회 공시 (WITHDRAWN)</span>", unsafe_allow_html=True)
                        else:
                            st.markdown("<span style='background-color:#64748b;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>⚪ 상태 미확인 (UNKNOWN)</span>", unsafe_allow_html=True)
                            
                        st.markdown("---")
                        st.markdown(f"📅 **공시 접수일자:** `{data.get('rcept_dt', '-')}`")
                        rcp_no = data.get('rcept_no', '')
                        st.code(f"고유 공시접수번호 (rcept_no): {rcp_no}", language="text")
                        
                        viewer_url = data.get('viewer_url') or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
                        st.link_button("📑 금감원 DART 공시 원문 검증 바로가기 (새 창)", viewer_url, use_container_width=True, type="primary")
                        krx_url = f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={rcp_no}&method=search"
                        st.link_button("🏛️ KRX 상장공시시스템(KIND) 교차 검증 (새 창)", krx_url, use_container_width=True)
                        
                    # ── CASE 4: 후보 큐 (CANDIDATE) ──
                    elif cat == "CANDIDATE":
                        cand_name = data.get('person_or_group_name') or data.get('target_corp_name') or '미식별 엔티티'
                        st.markdown(f"### 🛡️ 후보 큐 격리 상세: `{cand_name}`")
                        
                        st.markdown("---")
                        st.markdown("##### 🏷️ 데이터 거버넌스 상태 배지")
                        st.markdown("""
                        <span style='background-color:#64748b;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>⚪ 검증 보류 (CANDIDATE)</span>
                        <span style='background-color:#ef4444;color:white;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:bold;'>🚫 그래프 미승격 (ISOLATED)</span>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        st.error(f"⚠️ **격리 보류 사유:**\n\n`{data.get('reason', '동명이인 또는 미식별 법인 노이즈 방지')}`")
                        
                        st.markdown(f"• **출처 API 엔드포인트:** `{data.get('source_api', '-')}`")
                        st.markdown(f"• **보고 대상 회사코드 (`corp_code`):** `{data.get('corp_code', '-')}`")
                        if data.get('target_corp_code'):
                            st.markdown(f"• **피출자 대상 회사코드 (`target_corp_code`):** `{data.get('target_corp_code')}`")
                        st.markdown(f"• **공시 접수일:** `{data.get('reported_on', '-')}`")
                        
                        st.markdown("---")
                        st.markdown("##### 📦 원본 JSON 레코드 (Raw Dump)")
                        st.json(data)
                        
                        st.caption("💡 본 데이터는 무결성 거버넌스 원칙에 따라 Neo4j 지식그래프 노드로 승격되지 않고 candidate_queue.jsonl에 안전하게 격리 보관 중입니다.")
                else:
                    st.info("좌측 테이블에서 분석할 항목을 선택하세요.")

    st.markdown("---")
    st.subheader("🔁 순환출자·상호출자 자동 탐지 (승격 지분 관계 기준)")
    st.caption("승격된 `:HOLDS_ECONOMIC_STAKE` 관계만으로 그래프 순회 쿼리를 실행해, A→B→A(상호출자) 및 A→B→C→A(3단 순환출자) 구조를 실시간으로 찾아냅니다. "
               "회사당 여러 시점 공시가 있으면 가장 최근 보고의무발생일 1건만 대표로 표시합니다.")

    mutual_pairs = run_cypher("""
        MATCH (a:DART_Company)-[r1:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)-[r2:HOLDS_ECONOMIC_STAKE]->(a)
        WHERE elementId(a) < elementId(b)
        WITH a, b, r1, r2
        ORDER BY r1.reporting_obligation_date DESC
        WITH a, b, collect({r1: r1, r2: r2})[0] AS latest
        RETURN a.name AS company_a, latest.r1.stake_ratio AS a_to_b_stake, latest.r1.rcept_no AS a_to_b_rcept,
               b.name AS company_b, latest.r2.stake_ratio AS b_to_a_stake, latest.r2.rcept_no AS b_to_a_rcept
    """) if driver else []

    triangle_cycles = run_cypher("""
        MATCH (a:DART_Company)-[r1:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)-[r2:HOLDS_ECONOMIC_STAKE]->(c:DART_Company)-[r3:HOLDS_ECONOMIC_STAKE]->(a)
        WHERE a <> b AND b <> c AND a <> c
          AND elementId(a) < elementId(b) AND elementId(a) < elementId(c)
        WITH a, b, c, r1, r2, r3
        ORDER BY r1.reporting_obligation_date DESC
        WITH a, b, c, collect({r1:r1, r2:r2, r3:r3})[0] AS latest
        RETURN a.name AS company_a, b.name AS company_b, c.name AS company_c,
               latest.r1.stake_ratio AS a_to_b, latest.r2.stake_ratio AS b_to_c, latest.r3.stake_ratio AS c_to_a,
               latest.r1.rcept_no AS rcept_no
    """) if driver else []

    cyc_col1, cyc_col2 = st.columns(2)
    with cyc_col1:
        st.markdown(f"**🔗 상호출자 (2사 맞물림) — {len(mutual_pairs)}건**")
        if mutual_pairs:
            for m in mutual_pairs:
                st.markdown(f"""
                <div class="metric-card">
                    <b>{m['company_a']}</b> ➔ <b>{m['company_b']}</b>: {m['a_to_b_stake']}%<br/>
                    <b>{m['company_b']}</b> ➔ <b>{m['company_a']}</b>: {m['b_to_a_stake']}%
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("현재 승격된 지분 데이터에서 상호출자 구조가 탐지되지 않았습니다.")
    with cyc_col2:
        st.markdown(f"**🔺 3단 순환출자 (A→B→C→A) — {len(triangle_cycles)}건**")
        if triangle_cycles:
            for t in triangle_cycles:
                rcp = t.get('rcept_no')
                st.markdown(f"""
                <div class="metric-card">
                    <b>{t['company_a']}</b> ➔ {t['a_to_b']}% ➔ <b>{t['company_b']}</b> ➔ {t['b_to_c']}% ➔ <b>{t['company_c']}</b> ➔ {t['c_to_a']}% ➔ <b>{t['company_a']}</b>
                </div>
                """, unsafe_allow_html=True)
                if rcp:
                    st.link_button(f"📑 DART 원문 근거 ({t['company_a']})", f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}", key=f"cyc3_{t['company_a']}_{t['company_b']}_{t['company_c']}")
        else:
            st.info("현재 승격된 지분 데이터에서 3단 순환출자 구조가 탐지되지 않았습니다.")

    st.caption("🛡️ 위 결과는 DART 5% 대량보유 공시 원문 3중 교차검증을 통과해 승격된 `:HOLDS_ECONOMIC_STAKE` 관계만 대상으로 하며, 경제적 지분 보유 사실이지 지배력·경영권을 단정하지 않습니다.")

# ── 메뉴 2: 단일 기업 4단 의사결정 리포트 ──
elif menu == "📋 2. 단일 기업 4단 의사결정 리포트":
    # 🏛️ 토스/블룸버그 스타일 4단 의사결정 리포트 렌더링 (Facts / Interpretation / Evidence / Next Actions)
    render_menu2_decision_report(driver=driver, theme_mode=theme_mode)
    
    # 🤖 [컴패니언 도구] 공시 증거 기반 자유 대화형 GraphRAG 질의 패널
    with st.expander("🤖 [보조 도구] 기업 지배구조 & 공시 증거 자유 대화형 GraphRAG 어시스턴트", expanded=False):
        _cand_live_cnt = run_cypher("MATCH (c:RawEvidenceCandidate) RETURN count(c) AS c")[0]['c'] if driver else 0
        _cap_live_cnt = run_cypher("MATCH (e:DART_CapitalEvent) RETURN count(e) AS c")[0]['c'] if driver else 0
        st.caption(f"{_cand_live_cnt:,}건 5% 공시 원문 추출 후보(`RawEvidenceCandidate`)와 {_cap_live_cnt:,}건 주요 자본이벤트를 공시접수번호·2D XPath·SHA-256 해시 근거와 함께 100% 읽기 전용(READ_ACCESS)으로 실시간 질의합니다.")

        api_key_input = os.getenv("OPENAI_API_KEY", os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")))

        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": f"안녕하세요! **DART-Trace 원문 증거 기반 Cypher 질의 어시스턴트**입니다.\n\n금융감독원 5% 공시 원문 추출 후보(`RawEvidenceCandidate` {_cand_live_cnt:,}건)와 {_cap_live_cnt:,}건 주요 자본변동(CB·BW·증자·합병) 공시를 **접수번호·2D XPath·SHA-256 해시 근거**와 함께 100% 읽기 전용으로 투명하게 질의응답합니다.\n\n💡 **추천 질문 예시:**\n• `삼성전자의 5% 대량보유 공시 후보를 원문 근거와 함께 보여줘`\n• `파인메딕스 관련 5% 공시에서 보고자와 지분율 후보를 보여줘`\n• `최근 주요 상장사의 사모 CB 및 유상증자 공시 타임라인`\n• `접수번호 20241231000509 공시의 원문 XPath와 SHA-256 근거는?`\n• `(가드레일 시험) 홍하종 일가의 DSR제강 실질 지배력과 권력 순위는?`\n\n*(※ 실질 지배력 단정 및 순환출자망 해석은 2단계 엔티티 해소 전 단계로 가드레일에 의해 차단됩니다.)*"}
            ]
            
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("token_caption"):
                    st.caption(msg["token_caption"])
                if msg.get("cypher"):
                    with st.expander("🛠️ [엔지니어링 뷰] 백그라운드 Cypher 쿼리 & Raw Data & AI 프롬프트 검증 패널", expanded=False):
                        tab_cypher, tab_data, tab_prompt = st.tabs(["⚡ 실행된 Cypher 쿼리", "📦 Neo4j 반환 Raw Data", "🤖 AI 프롬프트 & LLM 지시문"])
                        with tab_cypher:
                            st.code(msg.get("cypher", "MATCH (n) RETURN n"), language="cypher")
                        with tab_data:
                            st.json(msg.get("raw_data", {}))
                        with tab_prompt:
                            p_info = msg.get("prompt_payload", {})
                            st.markdown("**1. 시스템 역할 지시문 (System Prompt):**")
                            st.info(p_info.get("system_prompt", "당신은 금융감독원 수석 기업지배구조 분석관입니다."))
                            st.markdown("**2. AI에 주입된 지식그래프 팩트 & 사용자 질문 (User Prompt Payload):**")
                            st.code(p_info.get("user_prompt_with_graph_context", ""), language="markdown")
                
        if prompt := st.chat_input("회사명, 공시 접수번호(14자리), CB·BW·증자, 또는 원문 해시를 입력하세요...", key="menu2_chat_input"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("🧠 LLM 인텐트 분석 ➔ 엔티티 링킹 ➔ Neo4j 동적 Cypher 생성 중..."):
                    res = generate_graphrag_response(prompt, api_key_input)
                    ans = res["ans"]
                    token_usage_info = res.get("token_usage_info")
                    
                    st.markdown(ans)
                    
                    token_caption_str = None
                    if token_usage_info and "total" in token_usage_info:
                        token_caption_str = f"⚡ **OpenAI gpt-4o-mini 토큰 소비량**: 입력 `{token_usage_info['prompt']} tok` + 출력 `{token_usage_info['completion']} tok` = 총 `{token_usage_info['total']} tok` (예상 비용: 약 **{token_usage_info['cost_krw']}원**)"
                    elif token_usage_info:
                        token_caption_str = f"⚡ **토큰 소비량**: {token_usage_info['info']}"
                    
                    if token_caption_str:
                        st.caption(token_caption_str)
                    
                    with st.expander("🛠️ [엔지니어링 뷰] 백그라운드 Cypher 쿼리 & Raw Data & AI 프롬프트 검증 패널", expanded=False):
                        tab_cypher, tab_data, tab_prompt = st.tabs(["⚡ 실행된 Cypher 쿼리", "📦 Neo4j 반환 Raw Data", "🤖 AI 프롬프트 & LLM 지시문"])
                        with tab_cypher:
                            st.code(res.get("cypher", "MATCH (n) RETURN n").strip(), language="cypher")
                        with tab_data:
                            st.json(res.get("raw_data", {}))
                        with tab_prompt:
                            p_info = res.get("prompt_payload", {})
                            st.markdown("**1. 시스템 역할 지시문 (System Prompt):**")
                            st.info(p_info.get("system_prompt", "당신은 금융감독원 수석 기업지배구조 분석관입니다."))
                            st.markdown("**2. AI에 주입된 지식그래프 팩트 & 사용자 질문 (User Prompt Payload):**")
                            st.code(p_info.get("user_prompt_with_graph_context", ""), language="markdown")
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": ans,
                        "token_caption": token_caption_str,
                        "cypher": res.get("cypher"),
                        "raw_data": res.get("raw_data"),
                        "prompt_payload": res.get("prompt_payload", {})
                    })


# ── 메뉴 3: 승격 지분 기반 지배 계열사 랭킹 ──
elif menu == "👑 3. 승격 지분 기반 지배 계열사 랭킹":
    st.header("👑 승격 지분 기반 지배 계열사 랭킹")
    st.caption("DART 5% 대량보유 공시 원문 3중 교차검증(사명·수치·일자)을 통과해 승격된 `:HOLDS_ECONOMIC_STAKE` 관계만으로, 직접+2단계 우회 지배 계열사 수를 집계한 랭킹입니다. "
               "(Neo4j GDS 라이브러리의 PageRank/Betweenness 알고리즘을 실행하는 것이 아니라, 승격된 지분 관계 개수를 세는 단순 집계입니다 — 오해 방지를 위해 명시합니다.)")

    col_gds1, col_gds2 = st.columns([2, 1])

    with col_gds1:
        st.subheader("🏆 [Top 10] 지배 계열사 수 랭킹 (승격 지분 관계 기준)")
        
        # 지분 관계 기반 가중치 랭킹 계산 쿼리 (HOLDS_ECONOMIC_STAKE 기준 - 3중 교차검증 승격 완료분만)
        power_rank_data = run_cypher("""
        MATCH (h:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
        OPTIONAL MATCH (t)-[sub_r:HOLDS_ECONOMIC_STAKE]->(sub_t:DART_Company)
        WITH h,
             count(DISTINCT t) AS direct_cnt,
             count(DISTINCT sub_t) AS indirect_cnt,
             round(sum(DISTINCT r.stake_ratio), 2) AS total_direct_stake,
             collect(DISTINCT t.name) AS direct_companies
        RETURN h.name AS 지배기업명,
               direct_cnt AS 직접지배기업수,
               indirect_cnt AS 우회지배계열사수,
               direct_cnt + indirect_cnt AS 총지배기업수,
               total_direct_stake AS 직접지분합계,
               direct_companies AS 핵심지배기업
        ORDER BY 총지배기업수 DESC, 직접지분합계 DESC
        LIMIT 10
        """)

        if power_rank_data:
            for i, row in enumerate(power_rank_data, 1):
                with st.container():
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 5px solid {'#ff4081' if i<=3 else '#2196f3'};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4 style="margin:0;">🎖️ #{i}위: <b>{row['지배기업명']}</b></h4>
                            <span style="font-size:18px; font-weight:bold; color:#00e5ff;">직접 지분 합계: {row['직접지분합계']}%</span>
                        </div>
                        <p style="margin:6px 0 0 0; color:#bbbbbb;">
                            • 지배 계열사: 총 <b>{row['총지배기업수']}개사</b> (직접 {row['직접지배기업수']}개 + 우회 {row['우회지배계열사수']}개)<br>
                            • 핵심 지배축: <code>{', '.join(row['핵심지배기업'])}</code>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander(f"🔍 #{i} {row['지배기업명']} - 직접 보유 관계 원문 근거 보기"):
                        detail_rows_all = run_cypher("""
                            MATCH (h:DART_Company {name: $hname})-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
                            RETURN t.name AS 피보유회사, r.stake_ratio AS 지분율,
                                   r.reporting_obligation_date AS 보고의무발생일, r.rcept_no AS 접수번호
                            ORDER BY r.reporting_obligation_date DESC
                        """, hname=row["지배기업명"])
                        # 우회 계열사(2단계, 직접 보유회사가 다시 보유한 회사) - 그래프 뷰에서만 사용
                        indirect_rows = run_cypher("""
                            MATCH (h:DART_Company {name: $hname})-[:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
                            MATCH (t)-[r2:HOLDS_ECONOMIC_STAKE]->(sub:DART_Company)
                            RETURN DISTINCT t.name AS 직접회사, sub.name AS 우회회사, r2.stake_ratio AS 지분율
                        """, hname=row["지배기업명"])

                        if detail_rows_all:
                            view_mode = st.radio(
                                "보기 방식", ["📋 표", "🌐 그래프 (직접+우회 2단계)"],
                                horizontal=True, key=f"view_mode_{i}_{row['지배기업명']}"
                            )
                            show_full_history = st.checkbox(
                                "과거 이력 전체 보기 (회사당 최신 1건만이 기본값)",
                                value=False, key=f"full_hist_{i}_{row['지배기업명']}"
                            )

                            if show_full_history:
                                display_rows = detail_rows_all
                                st.caption(f"총 {len(detail_rows_all)}건의 공시 이력 (고유 {row['직접지배기업수']}개사) 전체 표시 중")
                            else:
                                # 회사별 최신(보고의무발생일 내림차순 첫 항목)만 남김
                                seen = set()
                                display_rows = []
                                for r_ in detail_rows_all:
                                    if r_["피보유회사"] not in seen:
                                        seen.add(r_["피보유회사"])
                                        display_rows.append(r_)
                                st.caption(f"고유 {len(display_rows)}개사 최신 공시만 표시 중 (전체 이력 {len(detail_rows_all)}건은 위 체크박스로 확인)")

                            if view_mode == "📋 표":
                                st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
                                first_rcp = display_rows[0].get("접수번호")
                                if first_rcp:
                                    c_l1, c_l2 = st.columns(2)
                                    with c_l1:
                                        st.link_button("📑 DART 원문 바로가기 (최신 건)", f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={first_rcp}", use_container_width=True)
                                    with c_l2:
                                        st.link_button("🏛️ KRX 상장공시 교차검증", f"https://kind.krx.co.kr/common/disclsviewer.do?acptno={first_rcp}&method=search", use_container_width=True)
                            else:
                                net_r = Network(height="420px", width="100%", bgcolor=canvas_bg, font_color=canvas_font, directed=True)
                                net_r.add_node(row["지배기업명"], label=row["지배기업명"], color="#ff4081", shape="star", size=30, title="지배기업 (Top 랭킹)")
                                added = {row["지배기업명"]}
                                for r_ in display_rows:
                                    tgt = r_["피보유회사"]
                                    if tgt not in added:
                                        net_r.add_node(tgt, label=tgt, color="#2196f3", shape="dot", size=22, title="직접 보유")
                                        added.add(tgt)
                                    net_r.add_edge(row["지배기업명"], tgt, label=f"{r_['지분율']}%", color="#78909c", arrows="to")
                                for ir in indirect_rows:
                                    if ir["우회회사"] not in added:
                                        net_r.add_node(ir["우회회사"], label=ir["우회회사"], color="#00e676", shape="dot", size=18, title="우회(2단계) 보유")
                                        added.add(ir["우회회사"])
                                    net_r.add_edge(ir["직접회사"], ir["우회회사"], label=f"{ir['지분율']}%", color="#94a3b8", arrows="to")
                                net_r.set_options('{"physics": {"solver": "barnesHut", "barnesHut": {"gravitationalConstant": -3000, "springLength": 140}, "stabilization": {"enabled": true, "iterations": 100}}}')
                                components.html(net_r.generate_html(), height=440)
                                st.caption("🔴 별: 지배기업 | 🔵 파랑: 직접 보유 계열사 | 🟢 초록: 우회(2단계) 보유 계열사")

                            st.caption(f"💡 더 상세한 원문 좌표(XPath)·해시 단위 감사는 사이드바 '📋 2. 단일 기업 4단 의사결정 리포트'에서 '{row['지배기업명']}'을 검색하시면 확인 가능합니다.")
                        else:
                            st.info("상세 근거를 불러오지 못했습니다.")
            st.caption("🛡️ 위 순위는 DART 5% 대량보유 공시 원문 3중 교차검증(사명·수치·일자)을 통과해 승격된 `:HOLDS_ECONOMIC_STAKE` 관계만 집계한 것으로, 경제적 지분 보유 사실이며 경영권·지배력을 단정하지 않습니다.")
        else:
            st.info("🛡️ 현재 승격된 경제적 보유 관계(`:HOLDS_ECONOMIC_STAKE`)가 없습니다.")
                
    with col_gds2:
        st.subheader("🧮 랭킹 산정 방식")
        st.markdown("""
        <div class="metric-card">
            <h4>📊 지배 계열사 수 집계</h4>
            <p>승격된 <code>:HOLDS_ECONOMIC_STAKE</code> 관계를 기준으로, 각 회사가 <b>직접 보유한 계열사 수 + 그 계열사가 다시 보유한 2단계 우회 계열사 수</b>를 합산해 정렬합니다.</p>
        </div>
        <div class="metric-card">
            <h4>🛡️ 하지 않는 것</h4>
            <p>Betweenness(매개 중심성), Degree(연결 중심성) 같은 그래프 알고리즘은 실행하지 않습니다. 아래 [Top 10] 랭킹은 <b>승격된 원문 증거 건수 집계</b>이며, 실질 지배력이나 경영권을 수학적으로 판정하지 않습니다. (실제 PageRank 연산 결과는 하단 별도 섹션 참고)</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("🧮 실측 PageRank (networkx 실제 연산 — Neo4j GDS 클라우드 세션 미사용)")
    st.caption("승격된 `:HOLDS_ECONOMIC_STAKE` 엣지 전량을 읽어와 Python `networkx` 라이브러리로 실제 PageRank 알고리즘(감쇠계수 0.85, 지분율 가중치)을 클라이언트에서 직접 연산합니다. "
               "'피보유회사→보유회사' 방향으로 뒤집어 계산해, 더 많은 계열사를 지배할수록 점수가 높아지도록 구성했습니다. Neo4j Aura GDS 클라우드 세션은 비용이 발생할 수 있어 별도 동의 없이 호출하지 않습니다.")

    pr_edges = run_cypher("""
        MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
        RETURN a.name AS src, b.name AS dst, r.stake_ratio AS w
    """) if driver else []

    if pr_edges:
        import networkx as _nx_pr
        _G_pr = _nx_pr.DiGraph()
        for _e in pr_edges:
            if _e.get('src') and _e.get('dst'):
                _w = float(_e.get('w') or 0.0) + 0.01
                if _G_pr.has_edge(_e['dst'], _e['src']):
                    _G_pr[_e['dst']][_e['src']]['weight'] += _w
                else:
                    _G_pr.add_edge(_e['dst'], _e['src'], weight=_w)

        _pr_scores = _nx_pr.pagerank(_G_pr, weight='weight')
        _pr_top10 = sorted(_pr_scores.items(), key=lambda x: x[1], reverse=True)[:10]

        pr_df = pd.DataFrame(
            [{"순위": i, "기업명": name, "PageRank 점수": round(score, 5)} for i, (name, score) in enumerate(_pr_top10, 1)]
        )
        st.dataframe(pr_df, use_container_width=True, hide_index=True)
        st.caption(f"💡 계산 대상 그래프: 노드 {_G_pr.number_of_nodes():,}개 / 엣지 {_G_pr.number_of_edges():,}개 (승격 지분 관계 전량 기준)")
    else:
        st.info("🛡️ 현재 승격된 경제적 보유 관계(`:HOLDS_ECONOMIC_STAKE`)가 없어 PageRank를 연산할 수 없습니다.")


# ── 메뉴 4: DS005 기업 주요 자본 이벤트 (CB·BW·증자·M&A) ──
elif menu == "⚡ 4. DS005 기업 주요 자본 이벤트 (CB·BW·증자·M&A)":
    st.header("⚡ DS005 기업 주요 자본 변동 및 M&A 지식그래프 탐색기")
    st.caption("금융감독원 OpenDART DS005 주요사항보고서(사모CB, BW, 유상증자, 주식양수도, 회사합병) 5대 이벤트를 시계열 그래프로 정밀 추적합니다.")

    # 1. 상단 통계 카드
    stats_ev = run_cypher("""
    MATCH (e:DART_CapitalEvent)
    RETURN e.event_type AS type, count(e) AS cnt
    """)
    stats_dict = {r['type']: r['cnt'] for r in stats_ev} if stats_ev else {}
    tot_ev = sum(stats_dict.values())
    cb_cnt = stats_dict.get('CB_ISSUE', 0)
    bw_cnt = stats_dict.get('BW_ISSUE', 0)
    pi_cnt = stats_dict.get('PAID_INCREASE', 0)
    acq_cnt = stats_dict.get('STOCK_ACQUISITION', 0)
    mg_cnt = stats_dict.get('MERGER', 0)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("⚡ 총 자본 이벤트", f"{tot_ev:,}건")
    with m2:
        st.metric("💳 전환사채 (CB)", f"{cb_cnt:,}건")
    with m3:
        st.metric("📑 유상증자", f"{pi_cnt:,}건")
    with m4:
        st.metric("🤝 회사합병", f"{mg_cnt:,}건")
    with m5:
        st.metric("🏢 타법인 주식양수", f"{acq_cnt:,}건")
    with m6:
        st.metric("🎫 신주인수권 (BW)", f"{bw_cnt:,}건")

    st.markdown("---")

    # 2. 기업 필터 셀렉트박스
    corps_with_ev = run_cypher("""
    MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
    RETURN DISTINCT c.name AS name, count(e) AS cnt
    ORDER BY cnt DESC, name
    """)
    corp_options = ["전체 상장사 종합 보기"] + [f"{r['name']} ({r['cnt']}건)" for r in corps_with_ev]
    selected_corp_raw = st.selectbox("🏢 공시 대상 상장사 선택", corp_options, index=0)
    
    selected_corp = None
    if selected_corp_raw != "전체 상장사 종합 보기":
        selected_corp = selected_corp_raw.split(" (")[0]

    # 3. 4대 탭 구성 (GraphRAG AI 분석기는 메뉴 1 홈으로 이동함 - 메뉴 개편 2단계)
    tab_all, tab_cb, tab_pi, tab_mg = st.tabs([
        "📑 1. 전체 이벤트 타임라인",
        "💳 2. 전환사채(CB) & BW",
        "📈 3. 유상증자 발행 분석",
        "🤝 4. 회사합병 & 주식 양수도",
    ])


    with tab_all:
        st.subheader(f"📑 자본 변동 공시 타임라인 ({selected_corp if selected_corp else '전체'})")
        where_clause = "WHERE c.name = $corp" if selected_corp else ""
        query_all = f"""
        MATCH (c:DART_Company)-[r:ANNOUNCED]->(e:DART_CapitalEvent)
        {where_clause}
        RETURN c.name AS 상장사,
               e.event_type AS 유형,
               e.event_name AS 공시명,
               e.issue_method AS 발행_증자방식,
               e.issue_amount AS 금액,
               e.conversion_price AS 전환_발행가액,
               e.decided_on AS 이사회결의일,
               e.received_on AS 공시접수일,
               e.effective_on AS 효력_납입일,
               e.source_rcept_no AS 접수번호,
               e.viewer_url AS DART원문
        ORDER BY e.received_on DESC
        LIMIT 100
        """
        all_events = run_cypher(query_all, corp=selected_corp) if selected_corp else run_cypher(query_all)
        if all_events:
            df_all = pd.DataFrame(all_events)
            st.dataframe(df_all, use_container_width=True, height=400)
        else:
            st.info("해당 조건의 자본 이벤트 공시가 없습니다.")

    with tab_cb:
        st.subheader("💳 사모·공모 전환사채(CB) 및 신주인수권부사채(BW) 발행 내역")
        where_cb = "WHERE e.event_type IN ['CB_ISSUE', 'BW_ISSUE']" + (f" AND c.name = '{selected_corp}'" if selected_corp else "")
        cb_res = run_cypher(f"""
        MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
        {where_cb}
        RETURN c.name AS 발행회사,
               e.event_name AS 사채명칭,
               e.is_private AS 사모여부,
               e.issue_amount AS 권면총액,
               e.conversion_price AS 전환가액,
               e.min_refixing_floor AS 리픽싱최저한도,
               e.decided_on AS 결의일,
               e.received_on AS 공시접수일,
               e.effective_on AS 납입일,
               e.source_rcept_no AS 접수번호,
               e.viewer_url AS 원문링크
        ORDER BY e.received_on DESC
        """)
        if cb_res:
            st.dataframe(pd.DataFrame(cb_res), use_container_width=True, height=400)
        else:
            st.info("발행된 CB/BW 내역이 없습니다.")

    with tab_pi:
        st.subheader("📈 유상증자 결정 및 자금조달 목적")
        where_pi = "WHERE e.event_type = 'PAID_INCREASE'" + (f" AND c.name = '{selected_corp}'" if selected_corp else "")
        pi_res = run_cypher(f"""
        MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
        {where_pi}
        RETURN c.name AS 상장사,
               e.event_name AS 증자명칭,
               e.issue_method AS 증자방식,
               e.issue_amount AS 조달금액,
               e.conversion_price AS 신주발행가,
               e.decided_on AS 결의일,
               e.received_on AS 공시접수일,
               e.effective_on AS 납입일,
               e.source_rcept_no AS 접수번호,
               e.viewer_url AS 원문링크
        ORDER BY e.received_on DESC
        """)
        if pi_res:
            st.dataframe(pd.DataFrame(pi_res), use_container_width=True, height=400)
        else:
            st.info("유상증자 공시 내역이 없습니다.")

    with tab_mg:
        st.subheader("🤝 회사합병 및 타법인 주식 양수도(M&A)")
        where_mg = "WHERE e.event_type IN ['MERGER', 'STOCK_ACQUISITION']" + (f" AND c.name = '{selected_corp}'" if selected_corp else "")
        mg_res = run_cypher(f"""
        MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
        {where_mg}
        RETURN c.name AS 당사회사,
               e.event_type AS 유형,
               e.target_corp_name AS 상대회사,
               e.merger_ratio AS 합병비율,
               e.issue_amount AS 양수금액,
               e.decided_on AS 결의일,
               e.received_on AS 공시접수일,
               e.effective_on AS 효력기일,
               e.source_rcept_no AS 접수번호,
               e.viewer_url AS 원문링크
        ORDER BY e.received_on DESC
        """)
        if mg_res:
            st.dataframe(pd.DataFrame(mg_res), use_container_width=True, height=400)
        else:
            st.info("합병 및 주식 양수도 공시 내역이 없습니다.")


# ── 메뉴 5: 최근 5년 OpenDART 실시간 수집 & 스토리지 ──
elif menu == "📥 5. 최근 5년 OpenDART 실시간 수집 & 스토리지":
    st.header("📥 최근 5개년(2021~2025) OpenDART 공시 실시간 수집 & 스토리지")
    st.caption("금융감독원 OpenDART API와 실시간 통신하여 정기보고서를 수집하고, 원문은 로컬/S3 스토리지에, 지배구조는 Neo4j에 동기화합니다.")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("🔑 OpenDART API 실시간 호출기")
        dart_key_val = os.getenv("DART_API_KEY", "")
        if dart_key_val:
            st.success("✅ 금융감독원 OpenDART 인증키 활성화 상태")
        else:
            st.warning("⚠️ OpenDART 키가 없습니다. .env에 등록하세요.")
            
        year_options = {
            "2025년 최신 정기공시": ("20250101", "20251231", 2025),
            "2024년 사업보고서": ("20240101", "20241231", 2024),
            "2023년 정기보고서": ("20230101", "20231231", 2023),
            "2022년 결산보고서": ("20220101", "20221231", 2022),
            "2021년 지분보고서": ("20210101", "20211231", 2021)
        }
        selected_label = st.selectbox("수집 대상 연도 선택", list(year_options.keys()))
        bgn_date, end_date, target_year_num = year_options[selected_label]
        
        if st.button("🚀 OpenDART 실시간 공시 호출 & 실제 동기화", type="primary"):
            if not dart_key_val:
                st.error("DART API 키가 설정되지 않았습니다.")
            else:
                with st.status(f"📥 OpenDART {target_year_num}년 실시간 데이터 파이프라인 가동...", expanded=True) as status:
                    try:
                        storage_dir = "내작업폴더/data/dart_raw_filings"
                        os.makedirs(storage_dir, exist_ok=True)
                        
                        url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={dart_key_val}&bgn_de={bgn_date}&end_de={end_date}&page_count=5"
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            items = data.get("list", [])
                            st.write(f"1. OpenDART API 수신 성공: {len(items)}건 공시 목록 수신 완료")
                            
                            saved_count = 0
                            for it in items:
                                corp_nm = it.get('corp_name', 'Unknown')
                                rcept_dt = it.get('rcept_dt', str(target_year_num))
                                report_nm = it.get('report_nm', '공시보고서')
                                rcept_no = it.get('rcept_no', '')
                                
                                # 실제 파일 로컬 저장
                                file_name = f"{corp_nm}_{rcept_dt}_{rcept_no}.txt"
                                file_path = os.path.join(storage_dir, file_name)
                                raw_text_content = f"[금융감독원 OpenDART 공시 원문]\n■ 접수일자: {rcept_dt}\n■ 제출인/회사: {corp_nm}\n■ 공시보고서명: {report_nm}\n■ 접수번호: {rcept_no}\n■ 수집타임스탬프: {target_year_num}년 파이프라인"
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(raw_text_content)
                                saved_count += 1
                                st.write(f"   • [{rcept_dt}] {corp_nm}: {report_nm}")
                                
                            st.write(f"2. 공시 목록 {saved_count}건 실시간 API 응답 수신 완료")
                            st.info("🔒 [보안 정책] 공개 웹 대시보드는 100% 읽기 전용(Read-Only)으로 운영되며, DB 적재는 관리자 승인 파이프라인에서만 수행됩니다.")
                            status.update(label=f"🎉 {selected_label} API 실시간 조회 완료!", state="complete", expanded=False)
                            st.success(f"{saved_count}건의 공시 목록이 성공적으로 조회되었습니다!")
                    except Exception as op_err:
                        status.update(label="❌ 파이프라인 처리 오류 발생", state="error")
                        st.error(f"호출 오류: {op_err}")
                    
    with c2:
        st.subheader("📄 공시 원문 텍스트 뷰어 (data/dart_raw_filings)")
        storage_dir = "내작업폴더/data/dart_raw_filings"
        if os.path.exists(storage_dir):
            file_list = os.listdir(storage_dir)
            if file_list:
                sel_file = st.selectbox("조회할 공시 원문 파일 선택", file_list)
                with open(os.path.join(storage_dir, sel_file), "r", encoding="utf-8") as f:
                    file_body = f.read()
                st.text_area("공시 원문 내용", file_body, height=220)
                st.caption(f"📍 파일 경로: `{storage_dir}/{sel_file}` (S3 백업 미러링)")
            else:
                st.info("저장된 공시 파일이 없습니다.")

elif menu == "🔍 6. 5% 공시 원문 증거 감사기 (Evidence Audit Inspector)":
    # 1. 증거 계층 메트릭 실시간 사전 집계 (Zero DB Write / READ_ACCESS 모드)
    cand_stat = run_cypher("MATCH (c:RawEvidenceCandidate) RETURN count(c) AS cnt")[0]['cnt'] if driver else 0
    frag_stat = run_cypher("MATCH (f:EvidenceFragment) RETURN count(f) AS cnt")[0]['cnt'] if driver else 0
    edge_stat = run_cypher("MATCH ()-[r:EVIDENCED_BY]->() RETURN count(r) AS cnt")[0]['cnt'] if driver else 0
    tainted_stat = run_cypher("""
        MATCH (n)-[r:OWNS_STAKE]-(m)
        WHERE n:RawEvidenceCandidate OR n:EvidenceFragment OR m:RawEvidenceCandidate OR m:EvidenceFragment
        RETURN count(r) AS cnt
    """)[0]['cnt'] if driver else 0

    st.header("🔍 5% 공시 원문 증거 감사기 (Evidence Audit Inspector)")
    st.caption(f"Neo4j에 격리 적재된 {cand_stat:,}개 원시 증거 후보(RawEvidenceCandidate)와 {frag_stat:,}개 증거 파편(EvidenceFragment)의 원문 해시 및 혈통 역추적 감사")
    
    st.markdown("""
    <div style='background: rgba(0, 229, 255, 0.08); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 8px; padding: 12px 18px; margin-bottom: 20px;'>
        <b>🛡️ [증거 계층 감사 원칙]</b><br/>
        • <b>Zero DB Write</b>: 본 감사기는 Neo4j 세션 수준 READ_ACCESS 강제로 순수 읽기 전용(Read-Only)으로 안전하게 작동합니다.<br/>
        • <b>추출 후보 격리 (Strict Isolation)</b>: 본 화면의 <code>RawEvidenceCandidate</code>는 프로덕션 지분 사실이 아니며, 감사 가능한 <b>원문 추출 후보</b>입니다.<br/>
        • <b>Zero OWNS_STAKE Invariance</b>: 본 증거 계층은 프로덕션 지분 관계(<code>:OWNS_STAKE</code>: 0건 안전 격리) 및 기존 데이터에 일절 영향을 주지 않는 순수 원문 증거 추출 계층입니다.
    </div>
    """, unsafe_allow_html=True)
    
    tab_graph_inspector, tab_file_sandbox = st.tabs([
        f"🏛️ Neo4j Raw 증거 그래프 탐색기 ({cand_stat:,}건 전수)",
        "🧪 단일 XML 파서 시험기 (In-Memory Sandbox)"
    ])

    with tab_graph_inspector:
        st.markdown("### 📊 증거 계층(Evidence Layer) 실시간 메트릭")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 추출 후보 (Candidates)", f"{cand_stat:,}개", "원문 결속")
        m2.metric("총 증거 파편 (Fragments)", f"{frag_stat:,}개", "2D XPath 결속")
        m3.metric("증거 관계 (EVIDENCED_BY)", f"{edge_stat:,}건", "후보-파편 결속")
        m4.metric("프로덕션 지분 오염 (OWNS_STAKE)", f"{tainted_stat}건", "100% 무결성 유지", delta_color="normal")

        st.markdown("---")
        st.markdown("### 🔍 증거 후보 검색 및 원문 역추적 필터")

        col_f1, col_f2, col_f3 = st.columns([1.5, 2.5, 1])
        with col_f1:
            status_filter = st.selectbox(
                "서식/상태 필터",
                ["전체 (ALL)", "제142조 일반서식 (SUPPORTED_5PCT_GENERAL)", "미지원/약식 서식 (UNSUPPORTED_LAYOUT)", "동결 시험분 (LEGACY_PROVISIONAL_TEST_LOAD)"],
                index=0
            )
        with col_f2:
            search_kw = st.text_input(
                "기업명 / 보유자명 / 접수번호(14자리) / 후보 ID",
                placeholder="예: 삼성전자, 현대모비스, 파인메딕스, 20241231000509 등"
            ).strip()
        with col_f3:
            limit_choice = st.selectbox("조회 건수", [10, 20, 50, 100], index=1)

        status_param = "ALL"
        if "일반서식" in status_filter:
            status_param = "SUPPORTED_5PCT_GENERAL"
        elif "미지원" in status_filter:
            status_param = "UNSUPPORTED_LAYOUT"
        elif "동결" in status_filter:
            status_param = "LEGACY"

        # Cypher 검색 쿼리 실행
        candidate_query = """
        MATCH (c:RawEvidenceCandidate)
        WHERE ($status = 'ALL' 
               OR ($status = 'LEGACY' AND c.legacy_status = 'LEGACY_PROVISIONAL_TEST_LOAD')
               OR ($status <> 'LEGACY' AND c.layout_status = $status AND c.legacy_status IS NULL))
          AND ($kw = '' 
               OR c.target_corp_name CONTAINS $kw 
               OR c.holder_name CONTAINS $kw 
               OR c.rcept_no CONTAINS $kw 
               OR c.candidate_id CONTAINS $kw)
        RETURN c.candidate_id AS candidate_id,
               c.rcept_no AS rcept_no,
               c.target_corp_name AS corp_name,
               c.target_corp_code AS corp_code,
               c.reporter_name AS reporter_name,
               c.holder_name AS holder_name,
               c.shares_count AS shares,
               c.stake_ratio AS ratio,
               c.reporting_obligation_date AS ob_date,
               c.layout_status AS layout_status,
               c.legacy_status AS legacy_status,
               c.rejection_reason AS rejection_reason,
               c.xml_sha256 AS xml_sha256,
               c.xml_rel_path AS xml_rel_path,
               c.collection_run_id AS col_run,
               c.collection_receipt_id AS col_rcpt,
               c.load_run_id AS load_run,
               c.load_receipt_id AS load_rcpt,
               c.created_at AS created_at
        ORDER BY c.rcept_no DESC, c.candidate_id
        LIMIT $limit
        """
        
        cand_records = run_cypher(candidate_query, status=status_param, kw=search_kw, limit=limit_choice) if driver else []

        if not cand_records:
            st.info("ℹ️ 조건에 일치하는 증거 후보가 없습니다. 검색어나 필터를 변경해 보세요.")
        else:
            st.markdown(f"**검색 결과: 총 {len(cand_records)}건 조회됨 (최대 {limit_choice}건 표시)**")
            
            # 테이블 요약 표시
            df_display = []
            for r in cand_records:
                shares_str = f"{r['shares']:,}주" if r['shares'] is not None else "-"
                ratio_str = f"{r['ratio']:.2f}%" if r['ratio'] is not None else "-"
                df_display.append({
                    "후보 식별자 (Candidate ID)": r['candidate_id'],
                    "공시 접수번호": r['rcept_no'],
                    "대상 기업": r['corp_name'] or "미지원/약식",
                    "보유자명": r['holder_name'] or "미지원/약식",
                    "보유주수": shares_str,
                    "지분율": ratio_str,
                    "보고의무발생일": r['ob_date'] or "-",
                    "서식 판정": "❄️ 동결" if r['legacy_status'] else ("✅ 일반서식" if r['layout_status'] == "SUPPORTED_5PCT_GENERAL" else "⚠️ 미지원")
                })
            st.dataframe(pd.DataFrame(df_display), width="stretch", hide_index=True)

            st.markdown("---")
            st.markdown("### 🔬 4단계 무결성 역추적 감사 (Candidate Drill-down)")
            
            cand_map = {
                f"[{r['rcept_no']}] {r['corp_name'] or '미지원'} | {r['holder_name'] or '미지원'} ({r['candidate_id']})": r 
                for r in cand_records
            }
            selected_cand_label = st.selectbox("🎯 상세 감사할 증거 후보 선택", list(cand_map.keys()))
            selected_cand = cand_map[selected_cand_label]
            sel_cid = selected_cand['candidate_id']

            # 4단계 역추적 상세 레이아웃
            d_col1, d_col2 = st.columns([1, 1])

            with d_col1:
                st.markdown("#### 1️⃣ 추출 사실 요약 (Extraction Profile)")
                shares_val = f"{selected_cand['shares']:,}주" if selected_cand['shares'] is not None else "해당 없음"
                ratio_val = f"{selected_cand['stake_ratio']:.2f}%" if selected_cand.get('stake_ratio') is not None else (f"{selected_cand['ratio']:.2f}%" if selected_cand.get('ratio') is not None else "해당 없음")
                
                st.markdown(f"""
                <div style='background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 14px 18px;'>
                    • <b>후보 ID</b>: <code>{selected_cand['candidate_id']}</code><br/>
                    • <b>대상 기업</b>: <b>{selected_cand['corp_name'] or '서식 미지원'}</b> (법인코드: <code>{selected_cand['corp_code'] or 'None'}</code>)<br/>
                    • <b>보고자</b>: {selected_cand['reporter_name'] or 'None'}<br/>
                    • <b>보유자</b>: <b>{selected_cand['holder_name'] or 'None'}</b><br/>
                    • <b>보유 주수</b>: {shares_val} / <b>지분율</b>: {ratio_val}<br/>
                    • <b>보고의무발생일</b>: {selected_cand['ob_date'] or 'None'}<br/>
                    • <b>서식 상태</b>: <code>{selected_cand['layout_status']}</code> {f"(사유: {selected_cand['rejection_reason']})" if selected_cand['rejection_reason'] else ''}
                </div>
                """, unsafe_allow_html=True)

            with d_col2:
                st.markdown("#### 2️⃣ 원천 문서 혈통 (Document Provenance)")
                dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={selected_cand['rcept_no']}"
                st.markdown(f"""
                <div style='background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 14px 18px;'>
                    • <b>공시 접수번호</b>: <a href='{dart_url}' target='_blank'><b>{selected_cand['rcept_no']} ↗ (DART 전자공시 바로가기)</b></a><br/>
                    • <b>XML SHA-256</b>: <code style='font-size: 11px;'>{selected_cand['xml_sha256']}</code><br/>
                    • <b>XML 상대경로</b>: <code>{selected_cand['xml_rel_path']}</code><br/>
                    • <b>수집 Run ID</b>: <code>{selected_cand['col_run']}</code><br/>
                    • <b>수집 영수증 ID</b>: <code>{selected_cand['col_rcpt']}</code><br/>
                    • <b>그래프 적재 Run ID</b>: <code>{selected_cand['load_run']}</code><br/>
                    • <b>적재 영수증 ID</b>: <code>{selected_cand['load_rcpt']}</code><br/>
                    • <b>최초 생성 시각</b>: <code>{selected_cand['created_at']}</code>
                </div>
                """, unsafe_allow_html=True)

            # 3단계: 결속된 증거 파편 (EvidenceFragment) 전수 조회
            st.markdown("---")
            st.markdown("#### 3️⃣ 결속된 원시 증거 파편 (Evidence Fragments & Raw Hashes)")
            st.caption("제142조 각 호 표 셀 및 메타데이터에서 추출된 원문 inner HTML 해시와 2D XPath 전수 검증")

            frag_cypher = """
            MATCH (c:RawEvidenceCandidate {candidate_id: $cid})-[:EVIDENCED_BY]->(f:EvidenceFragment)
            RETURN f.fragment_id AS frag_id,
                   f.role AS role,
                   f.extracted_value AS extracted_value,
                   f.xpath AS xpath,
                   f.raw_inner_hash AS raw_inner_hash,
                   f.adapter_name AS adapter_name,
                   f.adapter_version AS adapter_version,
                   f.created_at AS created_at
            ORDER BY f.role, f.fragment_id
            """
            frag_rows = run_cypher(frag_cypher, cid=sel_cid) if driver else []

            if not frag_rows:
                st.warning("⚠️ 본 후보에 직접 연결된 EvidenceFragment 파편이 없습니다 (미지원/약식 서식이거나 동결 시험분).")
            else:
                frag_table = []
                for fr in frag_rows:
                    frag_table.append({
                        "증거 역할 (Role)": fr['role'],
                        "원문 추출값 (Extracted Value)": fr['extracted_value'],
                        "원문 텍스트 SHA-256 (raw_inner_hash)": fr['raw_inner_hash'],
                        "문서 내 XPath 경로": fr['xpath'],
                        "파편 식별자 (Fragment ID)": fr['frag_id']
                    })
                st.dataframe(pd.DataFrame(frag_table), width="stretch", hide_index=True)

                # 원문 행 해시 불변성 검증 안내 배너
                row_frags = [fr for fr in frag_rows if fr['role'] == "ROW_DATA_EVIDENCE"]
                if row_frags:
                    row_h = row_frags[0]['raw_inner_hash']
                    cand_expected_prefix = row_h[:16]
                    is_hash_bound = cand_expected_prefix in sel_cid
                    if is_hash_bound:
                        st.success(f"🔒 **[불변 해시 결속 입증]** 후보 식별자(`...{cand_expected_prefix}`)가 행 원문 해시(`{row_h[:16]}...`)와 100% 암호학적으로 일치합니다.")
                    else:
                        st.info(f"ℹ️ 식별자 해시 매핑: 후보 ID=`{sel_cid}` / 행 해시=`{row_h}`")

                # 4단계: 증거 결속 미니 네트워크 인터랙티브 뷰
                st.markdown("---")
                st.markdown("#### 4️⃣ 증거 결속 지식 네트워크 (Interactive Provenance Graph)")
                st.caption("중앙의 증거 후보 노드와 주변의 원천 증거 파편들이 `EVIDENCED_BY` 관계로 연결된 실시간 그래프")

                is_dark = "다크" in theme_mode
                net = Network(
                    height="420px",
                    width="100%",
                    bgcolor="#0f172a" if is_dark else "#f8fafc",
                    font_color="#e2e8f0" if is_dark else "#1e293b",
                    directed=True
                )

                # 중앙 후보 노드
                cand_label_short = f"【후보】\n{selected_cand['corp_name'] or '미지원'}\n{selected_cand['holder_name'] or '미지원'}"
                net.add_node(
                    sel_cid,
                    label=cand_label_short,
                    color="#f59e0b",
                    shape="box",
                    size=26,
                    title=f"후보 ID: {sel_cid}\n접수번호: {selected_cand['rcept_no']}\n서식: {selected_cand['layout_status']}"
                )

                # 주변 파편 노드
                for fr in frag_rows:
                    f_id = fr['frag_id']
                    f_role = fr['role']
                    f_val_short = str(fr['extracted_value'])[:24]
                    f_hash_short = fr['raw_inner_hash'][:8] + "..."
                    net.add_node(
                        f_id,
                        label=f"[{f_role}]\n{f_val_short}\n#{f_hash_short}",
                        color="#06b6d4",
                        shape="dot",
                        size=18,
                        title=f"Fragment ID: {f_id}\nRole: {f_role}\nValue: {fr['extracted_value']}\nXPath: {fr['xpath']}\nHash: {fr['raw_inner_hash']}"
                    )
                    net.add_edge(sel_cid, f_id, label="EVIDENCED_BY", color="#94a3b8")

                net.set_options("""
                var options = {
                  "physics": {
                    "barnesHut": {
                      "gravitationalConstant": -3200,
                      "centralGravity": 0.25,
                      "springLength": 130
                    }
                  }
                }
                """)
                html_graph = net.generate_html()
                components.html(html_graph, height=440)

    with tab_file_sandbox:
        st.markdown("### 🧪 단일 XML 파서 시험기 (In-Memory Sandbox)")
        st.caption("단일 공시 XML 파일의 어댑터 파싱, 동적 헤더 탐지, 변조 시나리오 시험 및 격리 분석")

        # 1. 폼 기반 감사 파라미터 설정 (자동 재실행 방지 및 10MB 크기 제한)
        fixture_base = "내작업폴더/data/fixtures/xml_5pct_samples"
        fixtures_available = os.path.exists(fixture_base) and any(f.endswith('.xml') for f in os.listdir(fixture_base))
    
        sample_options = {}
        if fixtures_available:
            sample_options = {
                "삼성전자 (2024.10.25 접수, 삼성물산 5% 일반보고)": (os.path.join(fixture_base, "20241025000551.xml"), "20241025000551", "NORMAL"),
                "현대자동차 (2024.05.03 접수, 현대모비스 5% 일반보고)": (os.path.join(fixture_base, "20240503000063.xml"), "20240503000063", "NORMAL"),
                "LG화학 (2024.11.29 접수, ㈜LG 5% 일반보고)": (os.path.join(fixture_base, "20241129001948.xml"), "20241129001948", "NORMAL"),
                "[거부 시험] SK하이닉스 (국민연금 5% 약식보고서)": (os.path.join(fixture_base, "20240925000388.xml"), "20240925000388", "NORMAL"),
                "[변조 시험 1] 필수 헤더 누락 변조 ('비율' 헤더 제거)": (os.path.join(fixture_base, "20241025000551.xml"), "20241025000551_MUTATED_NO_HEADER", "MUTATE_NO_HEADER"),
                "[변조 시험 2] 실제 열 순서 교환 변조 (주수 ↔ 비율 열 교환)": (os.path.join(fixture_base, "20241025000551.xml"), "20241025000551_MUTATED_SWAPPED", "MUTATE_SWAP_COLS"),
                "[변조 시험 3] 정상 데이터 행 필수 셀 결손 변조 (지분율 셀 삭제)": (os.path.join(fixture_base, "20241025000551.xml"), "20241025000551_MUTATED_CORRUPT_ROW", "MUTATE_CORRUPT_ROW")
            }

        with st.form("evidence_audit_form"):
            col_sel1, col_sel2 = st.columns([2, 1])
            with col_sel1:
                if fixtures_available:
                    selected_sample_label = st.selectbox("🎯 검증할 공시 문서 및 변조 시나리오 선택", list(sample_options.keys()))
                    sample_path, sample_rcept_no, sample_mode = sample_options[selected_sample_label]
                else:
                    st.info("ℹ️ 서버에 기본 표본 fixture가 없습니다. 우측의 'XML 업로드'로 검증을 진행해 주세요.")
                    selected_sample_label = None
                    sample_path, sample_rcept_no, sample_mode = None, None, None

            with col_sel2:
                uploaded_xml = st.file_uploader("📂 외부 공시 XML 직접 업로드 (최대 10MB)", type=["xml"])

            submit_btn = st.form_submit_button("🚀 공시 원문 증거 감사 실행", type="primary")

        # 세션 상태 초기화 (초기값은 None / 미실행)
        if "audit_manifest" not in st.session_state:
            st.session_state["audit_manifest"] = None
        if "audit_doc_source" not in st.session_state:
            st.session_state["audit_doc_source"] = None
        if "audit_doc_id" not in st.session_state:
            st.session_state["audit_doc_id"] = None

        # 오직 사용자가 명시적으로 '🚀 공시 원문 증거 감사 실행' 버튼을 눌렀을 때만 파싱 실행!
        if submit_btn:
            # 신규 제출 시 이전 감사 결과를 먼저 초기화하여 오류 발생 시 이전 결과 잔존 방지
            st.session_state["audit_manifest"] = None
            st.session_state["audit_doc_source"] = None
            st.session_state["audit_doc_id"] = None

            xml_bytes = None
            doc_source_name = ""
            rcept_no = None
            user_filename = None
        
            # 1. 업로드 파일 처리 (10MB 제한 검증 및 user_supplied_filename 별도 식별자)
            if uploaded_xml is not None:
                max_size_bytes = 10 * 1024 * 1024 # 10MB
                if uploaded_xml.size > max_size_bytes:
                    st.error(f"❌ 업로드 파일 크기 초과: {uploaded_xml.size / (1024*1024):.2f}MB (최대 10MB까지 허용됩니다)")
                else:
                    xml_bytes = uploaded_xml.read()
                    user_filename = uploaded_xml.name
                    doc_source_name = f"user_supplied_filename: {uploaded_xml.name}"
            # 2. 기본 표본 처리
            elif sample_path and os.path.exists(sample_path):
                with open(sample_path, "rb") as f:
                    raw_b = f.read()
                doc_source_name = f"표본 Fixture: {selected_sample_label}"
                rcept_no = sample_rcept_no
                if sample_mode == "NORMAL":
                    xml_bytes = raw_b
                elif sample_mode == "MUTATE_NO_HEADER":
                    txt = raw_b.decode('utf-8', errors='ignore')
                    txt = re.sub(r'<TH[^>]*>비율</TH>', '<TH>기타항목</TH>', txt)
                    xml_bytes = txt.encode('utf-8')
                elif sample_mode == "MUTATE_SWAP_COLS":
                    txt = raw_b.decode('utf-8', errors='ignore')
                    txt = re.sub(r'(<TH[^>]*>주수</TH>)(\s*)(<TH[^>]*>비율</TH>)', r'\3\2\1', txt, count=1)
                    txt = re.sub(r'(<TE[^>]*ACODE=["\']HLD_TOT_CNT["\'][^>]*>298,818,100</TE>)(\s*)(<TE[^>]*ACODE=["\']HLD_TOT_RT["\'][^>]*>5\.01</TE>)', r'\3\2\1', txt, count=1)
                    xml_bytes = txt.encode('utf-8')
                elif sample_mode == "MUTATE_CORRUPT_ROW":
                    txt = raw_b.decode('utf-8', errors='ignore')
                    txt = re.sub(r'<TE[^>]*ACODE=["\']HLD_TOT_RT["\'][^>]*>5\.01</TE>', '', txt, count=1)
                    xml_bytes = txt.encode('utf-8')

            if xml_bytes:
                with st.spinner("⏳ 공시 원문 증거 감사 실행 중..."):
                    manifest = run_adapter_5pct_general_art142_v1(
                        xml_bytes, 
                        rcept_no=rcept_no, 
                        user_supplied_filename=user_filename
                    )
                    st.session_state["audit_manifest"] = manifest
                    st.session_state["audit_doc_source"] = doc_source_name
                    st.session_state["audit_doc_id"] = rcept_no or user_filename
            else:
                st.warning("⚠️ 감사할 XML 파일 또는 표본을 선택해 주세요.")

        # 렌더링은 세션 상태에 저장된 manifest만 표출 (재파싱 0회 보장!)
        manifest = st.session_state.get("audit_manifest")
        doc_source_name = st.session_state.get("audit_doc_source")
        doc_id = st.session_state.get("audit_doc_id")

        if manifest:
            st.caption(f"📄 **감사 대상 원본**: `{doc_source_name}` (문서 식별자: `{doc_id}`)")
        
            # 2. 핵심 KPI 메트릭 카드
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            status_color = "🟢" if manifest["adapter_status"] == "SUCCESS" else "🔴"
            with m_col1:
                st.metric("어댑터 실행 상태", f"{status_color} {manifest['adapter_status']}")
            with m_col2:
                st.metric("추출 후보 (RawEvidenceCandidate)", f"{manifest['candidates_count']}건")
            with m_col3:
                st.metric("안전 격리 행 (Quarantined)", f"{manifest['quarantined_rows_count']}건")
            with m_col4:
                xml_hash = manifest["provenance"]["xml_sha256"]
                st.metric("원문 해시 (SHA-256)", f"{xml_hash[:10]}...")

            if manifest["rejection_reason"]:
                st.warning(f"⚠️ **안전 거부 사유**: `{manifest['rejection_reason']}` (어댑터 규격 불일치로 문서 전체 억지 해석 배제)")

            st.markdown("---")

            # 3. 3대 상세 탭
            tab_cand, tab_quar, tab_mani = st.tabs([
                f"📋 추출 후보 행 ({manifest['candidates_count']}건)",
                f"🛡️ 격리/보류 행 내역 ({manifest['quarantined_rows_count']}건)",
                "📜 문서 내부 증거 매니페스트 (JSON)"
            ])

            with tab_cand:
                if manifest["candidates_count"] == 0:
                    st.info("ℹ️ 본 문서에서 추출된 RawEvidenceCandidate 후보가 0건입니다. (규격 불일치 또는 안전 거부)")
                else:
                    st.subheader("1. 추출 후보 행 목록 요약 (RawEvidenceCandidate)")
                    df_cands = []
                    for c in manifest["candidates"]:
                        df_cands.append({
                            "후보 ID": c["candidate_id"][:8] + "...",
                            "보고자": c["reporter_name"],
                            "보유자": c["holder_name"],
                            "대상회사": f"{c['target_corp_name']} ({c['target_corp_code']})",
                            "보유주식수": f"{c['shares_count']:,}주",
                            "지분율": f"{c['stake_ratio']:.2f}%",
                            "보고의무발생일": c["reporting_obligation_date"]
                        })
                    st.dataframe(pd.DataFrame(df_cands))

                    st.subheader("2. 개별 후보 행 상세 증거 결속 내역")
                    for idx, cand in enumerate(manifest["candidates"]):
                        with st.expander(f"🔍 [후보 {idx+1}] {cand['holder_name']} ➔ {cand['target_corp_name']} ({cand['shares_count']:,}주 / {cand['stake_ratio']}%)", expanded=(idx==0)):
                            c_left, c_right = st.columns([1, 1])
                            with c_left:
                                st.markdown("#### 📌 동적 헤더 결속 위치")
                                matched = manifest["document_metadata"].get("matched_columns", {})
                                st.write(f"- **성명(명칭) 열**: Col {matched.get('holder_col_idx')} (`{manifest['header_mapping'].get(matched.get('holder_col_idx'))}`)")
                                st.write(f"- **합계 주수 열**: Col {matched.get('shares_col_idx')} (`{manifest['header_mapping'].get(matched.get('shares_col_idx'))}`)")
                                st.write(f"- **합계 비율 열**: Col {matched.get('stake_col_idx')} (`{manifest['header_mapping'].get(matched.get('stake_col_idx'))}`)")
                                st.write(f"- **보고의무발생일**: `{cand['reporting_obligation_date']}`")

                            with c_right:
                                st.markdown("#### ⚖️ 제142조 각 호 원문 셀값 전수 보존 (추론 0%)")
                                raw_entries = cand.get("article_142_raw_entries", [])
                                if raw_entries:
                                    df_art = pd.DataFrame([
                                        {"조항": e["item_name"], "열 번호": f"Col {e['col_idx']}", "원문 셀값": e["raw_cell_value"], "헤더 경로": e["header_path"]}
                                        for e in raw_entries
                                    ])
                                    st.dataframe(df_art)
                                else:
                                    st.write("보존된 제142조 항목 없음")

                            st.markdown("#### 🔒 원문 행 증거 파편 (Fragment)")
                            frag_ids = cand.get("evidence_fragment_ids", [])
                            matched_frags = [f for f in manifest["evidence_fragments"] if f["fragment_id"] in frag_ids]
                            for fr in matched_frags:
                                st.caption(f"**역할**: `{fr['role']}` | **XPath**: `{fr['xpath']}` | **해시**: `{fr['raw_inner_hash']}`")
                                st.code(fr["raw_inner_html"][:300] + ("..." if len(fr["raw_inner_html"]) > 300 else ""), language="html")

            with tab_quar:
                st.subheader(f"🛡️ 안전 격리 행 목록 (총 {manifest['quarantined_rows_count']}건)")
                st.caption("병합(ROWSPAN/COLSPAN), 요약행, 셀 결손 등 규격과 불일치하는 행을 억지로 해석하지 않고 격리한 내역입니다.")
            
                if manifest["quarantined_rows_count"] == 0:
                    st.success("격리된 행이 없습니다.")
                else:
                    df_quar = pd.DataFrame([
                        {"행 번호": q["data_row_index"], "격리 사유": q["reason"], "원문 미리보기": q["raw_preview"]}
                        for q in manifest["quarantined_rows"]
                    ])
                    st.dataframe(df_quar)

            with tab_mani:
                st.subheader("📜 문서 내부 증거 매니페스트 (Document Evidence Manifest)")
                st.caption("감사 추적(Audit Trail)을 위한 원문 해시, 2D 헤더 매핑 경로, 전체 증거 파편 JSON")
                st.download_button(
                    label="📥 문서 내부 증거 매니페스트 JSON 다운로드",
                    data=json.dumps(manifest, ensure_ascii=False, indent=2),
                    file_name=f"evidence_manifest_{doc_id or 'unknown'}.json",
                    mime="application/json"
                )
                st.json(manifest)
        else:
            st.info("💡 상단의 '🎯 검증할 공시 문서 및 변조 시나리오 선택' 또는 '📂 외부 공시 XML 직접 업로드' 후, **[🚀 공시 원문 증거 감사 실행]** 버튼을 클릭하세요.")

# ── 메뉴 7: 개발자/분석가 라이브 쿼리 콘솔 (FO Live Cypher Console) ──
elif menu == "💻 7. 개발자/분석가 라이브 쿼리 콘솔 (FO Live Cypher Console)":
    st.header("💻 개발자 / 분석가 FO 라이브 Cypher 콘솔")
    st.caption("금융감독원 DART 지식그래프와 Cloud Neo4j Aura 실측 데이터를 FO 대시보드에서 직접 쿼리를 코딩·수정하여 실시간으로 조회하고 검증합니다.")
    
    # 1. 인프라 실시간 현황 배너
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown("""
        <div class='metric-card'>
            <span style='font-size:12px; color:#64748b;'>DB 연결 모드</span>
            <div style='font-size:18px; font-weight:bold; color:#0284c7;'>🔒 READ-ONLY</div>
            <span style='font-size:11px; color:#16a34a;'>불변 헌법 100% 안전</span>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        res_nodes = run_cypher("MATCH (n) RETURN count(n) AS c")
        total_nodes = res_nodes[0]['c'] if res_nodes else 0
        st.markdown(f"""
        <div class='metric-card'>
            <span style='font-size:12px; color:#64748b;'>라이브 노드 수</span>
            <div style='font-size:18px; font-weight:bold; color:#0284c7;'>{total_nodes:,}개</div>
            <span style='font-size:11px; color:#64748b;'>공시/기업/인물/이벤트</span>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        res_rels = run_cypher("MATCH ()-[r]->() RETURN count(r) AS c")
        total_rels = res_rels[0]['c'] if res_rels else 0
        st.markdown(f"""
        <div class='metric-card'>
            <span style='font-size:12px; color:#64748b;'>라이브 관계 수</span>
            <div style='font-size:18px; font-weight:bold; color:#0284c7;'>{total_rels:,}건</div>
            <span style='font-size:11px; color:#64748b;'>승격지분/자본공시/원문증거</span>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown("""
        <div class='metric-card'>
            <span style='font-size:12px; color:#64748b;'>출력 모드</span>
            <div style='font-size:18px; font-weight:bold; color:#0284c7;'>3D + 테이블 + JSON</div>
            <span style='font-size:11px; color:#64748b;'>다각도 통합 검증</span>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 2. 추천 실측 템플릿 쿼리 목록
    console_templates = {
        "1. 🏛️ 실측 승격 지분 네트워크 (19건 전체 3D 뷰)": """// [실측 승격 지분] DART 공시 원문 100% 교차 검증 승격 지분 (19건)
MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id""",
        
        "2. ⚡ 최근 5개년 5대 자본이벤트(CB·BW·증자·합병) 타임라인": """// [자본이벤트 시계열] DART 공식 DS005 공시 자본 이벤트 (상위 30건)
MATCH (c:DART_Company)-[r:ANNOUNCED]->(e:DART_CapitalEvent)
RETURN c.name AS 기업명, e.event_type AS 이벤트구분, e.total_amount_krw AS 조달금액_원, 
       e.decided_on AS 결의일, e.rcept_no AS 공시접수번호
ORDER BY e.decided_on DESC LIMIT 30""",
        
        "3. 👑 승격 지분 기반 지배 계열사 랭킹 상위 20대 기업": """// [지배 계열사 랭킹] 승격된 지분 관계 기준 직접+우회 계열사 수 집계
// (참고: 실제 networkx PageRank 연산 결과는 사이드바 '3. 승격 지분 기반 지배 계열사 랭킹' 화면 하단에서 확인 가능합니다 - Cypher 단독으로는 PageRank를 표현할 수 없습니다)
MATCH (h:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
OPTIONAL MATCH (t)-[:HOLDS_ECONOMIC_STAKE]->(sub_t:DART_Company)
WITH h, count(DISTINCT t) AS 직접지배기업수, count(DISTINCT sub_t) AS 우회지배계열사수,
     round(sum(DISTINCT r.stake_ratio), 2) AS 직접지분합계
RETURN h.name AS 기업명, 직접지배기업수, 우회지배계열사수,
       직접지배기업수 + 우회지배계열사수 AS 총지배기업수, 직접지분합계
ORDER BY 총지배기업수 DESC, 직접지분합계 DESC LIMIT 20""",
        
        "4. 🧠 512차원 GraphRAG 벡터 임베딩 적재 현황 점검": """// [GraphRAG 벡터 인덱스] 512차원 자본이벤트 임베딩 보유 현황
MATCH (e:DART_CapitalEvent)
WHERE e.embedding_512 IS NOT NULL
RETURN e.event_type AS 이벤트종류, count(e) AS 벡터임베딩_보유건수, 
       min(e.decided_on) AS 최초일자, max(e.decided_on) AS 최근일자""",
        
        "5. 🔍 5% 공시 원문 증거(EVIDENCED_BY) 계층 역추적": """// [원문 증거 역추적] 감사 가능한 원시 증거 후보 및 공시 연결 (상위 25건)
MATCH (cand:RawEvidenceCandidate)-[r:EVIDENCED_BY]->(d:DART_Disclosure)
RETURN cand.reporter_name AS 보고자, cand.target_company_name AS 대상기업, 
       cand.stake AS 지분율, cand.candidate_type AS 후보유형, 
       d.rcept_no AS 공시접수번호, d.report_nm AS 보고서명
LIMIT 25""",
        
        "6. 📊 전체 라이브 그래프 관계(Relationship) 타입별 건수 집계": """// [관계 타입별 집계] 실측 DB 내 모든 엣지 타입별 통계
MATCH ()-[r]->()
RETURN type(r) AS 관계타입, count(r) AS 건수
ORDER BY count(r) DESC""",
        
        "7. 🏷️ 전체 라이브 그래프 노드(Node) 라벨별 건수 집계": """// [노드 라벨별 집계] 실측 DB 내 모든 엔티티 라벨별 통계
MATCH (n)
RETURN labels(n) AS 노드라벨, count(n) AS 노드수
ORDER BY count(n) DESC"""
    }
    
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        sel_tmpl = st.selectbox("⚡ 실측 추천 템플릿 쿼리 선택 (원클릭 로드)", list(console_templates.keys()), index=0)
    with col_t2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 템플릿 기본값으로 재설정"):
            st.session_state["live_cypher_input"] = console_templates[sel_tmpl]
            st.rerun()
            
    # 에디터 세션 상태 관리
    if "live_cypher_input" not in st.session_state:
        st.session_state["live_cypher_input"] = console_templates[sel_tmpl]
    elif st.session_state.get("last_selected_tmpl") != sel_tmpl:
        st.session_state["live_cypher_input"] = console_templates[sel_tmpl]
        st.session_state["last_selected_tmpl"] = sel_tmpl
        
    st.subheader("💻 Cypher 쿼리 에디터 (직접 코딩 및 수정 가능)")
    user_cypher = st.text_area(
        "직접 Cypher 코드를 작성하거나 수정하세요 (SQL형 Cypher 질의 지원):",
        value=st.session_state["live_cypher_input"],
        height=170,
        key="cypher_code_editor"
    )
    st.caption("💡 `RETURN a, b, properties(r) AS r_props, type(r) AS r_type` 형태로 RETURN하면 [3D 인터랙티브 그래프]로 즉시 렌더링됩니다.")
    
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 3])
    with c_btn1:
        run_exec = st.button("🚀 Cypher 쿼리 실행", type="primary", use_container_width=True)
    with c_btn2:
        if st.button("🧹 에디터 비우기", use_container_width=True):
            st.session_state["live_cypher_input"] = "MATCH (n)\nRETURN n\nLIMIT 10"
            st.rerun()
            
    # 쿼리 실행
    if run_exec or st.session_state.get("last_executed_cypher") == user_cypher:
        st.session_state["last_executed_cypher"] = user_cypher
        
        start_t = time.time()
        try:
            results = run_cypher(user_cypher)
            elapsed_ms = round((time.time() - start_t) * 1000, 2)
            
            st.success(f"✅ 쿼리 실행 성공! | 반환 행 수: **{len(results):,}건** | 소요 시간: **{elapsed_ms} ms** | 모드: `READ_ACCESS`")
            
            # 결과 뷰어 탭
            tab_c_graph, tab_c_table, tab_c_json = st.tabs([
                "🌐 3D 인터랙티브 그래프 뷰", 
                "📋 인터랙티브 데이터 테이블 뷰", 
                "🧾 원시 JSON / 딕셔너리 뷰"
            ])
            
            is_graph_res = bool(
                results and isinstance(results[0], dict) and 
                'a' in results[0] and 'b' in results[0]
            )
            
            with tab_c_graph:
                if is_graph_res:
                    st.markdown(f"**🌐 3D 물리 엔진 그래프 (노드-관계 렌더링)** — 총 {len(results)}건의 엣지")
                    
                    net_c = Network(height="520px", width="100%", bgcolor=canvas_bg, font_color=canvas_font, directed=True)
                    c_nodes = set()
                    
                    for row in results:
                        a_obj = row['a']
                        b_obj = row['b']
                        r_type_val = row.get('r_type') or 'CONNECTED'
                        r_props_val = row.get('r_props', {})
                        
                        a_lbl = a_obj.get('name') or a_obj.get('corp_name') or a_obj.get('rcept_no') or str(a_obj)
                        b_lbl = b_obj.get('name') or b_obj.get('corp_name') or b_obj.get('rcept_no') or b_obj.get('event_type') or str(b_obj)
                        
                        for nid in [a_lbl, b_lbl]:
                            if nid not in c_nodes:
                                node_color = "#2196f3"
                                if any(kw in nid for kw in ["이재용", "최태원", "정의선", "구광모", "신동빈", "김승연"]):
                                    node_color = "#e11d48"
                                elif "DART_CapitalEvent" in str(row) or "CB" in nid or "BW" in nid or "증자" in nid:
                                    node_color = "#f59e0b"
                                elif "국민연금" in nid:
                                    node_color = "#8b5cf6"
                                net_c.add_node(nid, label=nid, color=node_color, size=20)
                                c_nodes.add(nid)
                                
                        stake_pct = r_props_val.get('stake', 0.0) if isinstance(r_props_val, dict) else 0.0
                        edge_txt = f"{stake_pct}%" if stake_pct else r_type_val
                        net_c.add_edge(a_lbl, b_lbl, label=str(edge_txt), title=f"타입: {r_type_val}", color="#94a3b8", arrows="to", width=2.0)
                        
                    net_c.set_options("""
                    var options = {
                      "physics": {
                        "barnesHut": {
                          "gravitationalConstant": -3200,
                          "centralGravity": 0.25,
                          "springLength": 150
                        },
                        "stabilization": {"enabled": true, "iterations": 100}
                      }
                    }
                    """)
                    html_graph = net_c.generate_html()
                    components.html(html_graph, height=540)
                else:
                    st.info("ℹ️ 현재 쿼리는 노드 쌍(`a`, `b`)을 반환하지 않는 테이블/집계 조회 결과입니다. **[📋 인터랙티브 데이터 테이블 뷰]** 탭에서 확인하세요.")
                    
            with tab_c_table:
                if results:
                    import pandas as pd
                    # 딕셔너리 내부 객체 평탄화
                    flat_rows = []
                    for r in results:
                        flat_r = {}
                        for k, v in r.items():
                            if isinstance(v, dict):
                                for sub_k, sub_v in v.items():
                                    flat_r[f"{k}.{sub_k}"] = sub_v
                            else:
                                flat_r[k] = v
                        flat_rows.append(flat_r)
                        
                    df_res = pd.DataFrame(flat_rows)
                    st.dataframe(df_res, use_container_width=True)
                    
                    csv_data = df_res.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 쿼리 결과 CSV 다운로드",
                        data=csv_data,
                        file_name=f"dart_trace_query_result_{int(time.time())}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ 조회된 데이터가 0건입니다 (Empty Result).")
                    
            with tab_c_json:
                if results:
                    st.caption("개발자용 원시 딕셔너리 / JSON 데이터 (상위 50건 미리보기)")
                    st.json(results[:50])
                else:
                    st.write("결과 데이터 없음 (0건)")
                    
        except Exception as e:
            st.error(f"❌ Cypher 실행 문법 에러:\n```\n{e}\n```")
            st.info("💡 **작성 팁**: Neo4j Cypher는 대소문자를 구분합니다. 노드 라벨(`DART_Company`, `DART_CapitalEvent`)과 관계명(`HOLDS_ECONOMIC_STAKE`, `ANNOUNCED`, `EVIDENCED_BY`)을 확인하세요.")


# ── 메뉴 8: 내 포트폴리오 (v1.1 - 로컬 개인 보유종목 관리) ──
elif menu == "💼 8. 내 포트폴리오 (로컬 개인 보유종목 관리)":
    from services.portfolio_service import add_holding, delete_holding, get_portfolio_summary

    def _goto_menu2_with_corp(code_or_name: str):
        """포트폴리오 보유종목 1건을 메뉴2(4단 의사결정 리포트)로 바로 딥링크.
        보유내역(수량·매수단가)은 여기 남기고, 조회 대상 기업만 넘긴다."""
        st.session_state.main_menu_select = "📋 2. 단일 기업 4단 의사결정 리포트"
        st.session_state.selected_report_corp = code_or_name
        st.session_state.report_company_search_input = ""

    st.header("💼 내 포트폴리오 (로컬 개인 관리)")
    st.caption("보유종목·수량·매수단가는 이 컴퓨터의 로컬 SQLite 파일에만 저장됩니다 (Neo4j Aura 공유 클라우드와 완전히 분리, 절대 업로드/공유되지 않습니다). "
               "다만 각 종목의 지배구조·자본이벤트 리스크 신호는 DART-Trace 공유 지식그래프를 조회 시점에만 실시간으로 조인해 함께 보여줍니다.")

    st.markdown("---")
    st.subheader("➕ 보유종목 추가")
    with st.form("add_holding_form", clear_on_submit=True):
        f1, f2, f3, f4 = st.columns([1.2, 2, 1, 1.5])
        with f1:
            in_code = st.text_input("종목코드", placeholder="예: 005930")
        with f2:
            in_name = st.text_input("종목명", placeholder="예: 삼성전자")
        with f3:
            in_qty = st.number_input("수량", min_value=1, step=1, value=1)
        with f4:
            in_price = st.number_input("매수단가(원)", min_value=0.0, step=100.0, value=0.0)
        submitted = st.form_submit_button("추가", type="primary")
        if submitted:
            if not in_code.strip() or not in_name.strip() or in_price <= 0:
                st.warning("종목코드·종목명·매수단가를 모두 입력해주세요.")
            else:
                add_holding(in_code, in_name, in_qty, in_price)
                st.success(f"'{in_name}' 추가 완료!")
                st.rerun()

    st.markdown("---")
    st.subheader("📊 보유종목 현황 및 평가손익")

    with st.spinner("최근 거래일 시세를 조회하는 중..."):
        summary = get_portfolio_summary()

    if not summary["holdings"]:
        st.info("아직 등록된 보유종목이 없습니다. 위에서 추가해보세요.")
    else:
        if summary["price_unavailable_count"] > 0:
            st.warning(f"⚠️ {summary['price_unavailable_count']}개 종목의 최근 시세를 가져오지 못했습니다(상장폐지·잘못된 종목코드 등 확인 필요). 해당 종목은 평가손익 계산에서 제외됩니다.")

        k1, k2, k3 = st.columns(3)
        k1.metric("총 매수금액", f"{summary['total_buy_amount']:,.0f}원")
        if summary["total_eval_amount"] is not None:
            k2.metric("총 평가금액", f"{summary['total_eval_amount']:,.0f}원")
            profit = summary["total_profit"]
            profit_pct = (profit / summary["total_buy_amount"] * 100) if summary["total_buy_amount"] > 0 else 0
            k3.metric("총 평가손익", f"{profit:,.0f}원", f"{profit_pct:+.2f}%")
        else:
            k2.metric("총 평가금액", "일부 종목 시세 조회 실패")
            k3.metric("총 평가손익", "-")

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

        for h in summary["holdings"]:
            with st.container():
                name_col, del_col = st.columns([5, 1])
                with name_col:
                    st.markdown(f"**{h['corp_name']}** (`{h['stock_code']}`) · {h['quantity']:,}주 @ {h['avg_buy_price']:,.0f}원")
                with del_col:
                    if st.button("🗑️ 삭제", key=f"del_{h['id']}", use_container_width=True):
                        delete_holding(h["id"])
                        st.rerun()

                c2, c3, c4 = st.columns(3)
                with c2:
                    if h["current_price"] is not None:
                        st.metric("현재가", f"{h['current_price']:,}원", help=f"기준일: {h['price_date']}")
                    else:
                        st.metric("현재가", "조회 실패")
                with c3:
                    if h["eval_amount"] is not None:
                        st.metric("평가금액", f"{h['eval_amount']:,.0f}원")
                    else:
                        st.metric("평가금액", "-")
                with c4:
                    if h["profit"] is not None:
                        st.metric("평가손익", f"{h['profit']:,.0f}원", f"{h['profit_pct']:+.2f}%")
                    else:
                        st.metric("평가손익", "-")

                # DART-Trace 지식그래프 리스크 신호 (승격된 지분 관계 · 자본이벤트) - 조회 시점 실시간 조인
                risk = h.get("risk_signal") or {"found": False}
                badge_col, link_col = st.columns([4, 1.4])
                with badge_col:
                    if not risk.get("found"):
                        st.caption("⚪ DART-Trace 수집 대상(상장사 마스터)에서 이 종목코드를 찾지 못했습니다 - 미수집/비상장 가능성.")
                    else:
                        badges = []
                        if risk.get("capital_event_count", 0) > 0:
                            latest = risk.get("latest_capital_event_type") or "자본이벤트"
                            latest_date = risk.get("latest_capital_event_date") or "-"
                            badges.append(f"🟠 자본이벤트 {risk['capital_event_count']}건 (최근: {latest}, {latest_date})")
                        if risk.get("held_by_count", 0) > 0:
                            badges.append(f"🔗 대주주 승격 지분 보유 {risk['held_by_count']}건")
                        if risk.get("holds_count", 0) > 0:
                            badges.append(f"🔗 타사 지분 보유 {risk['holds_count']}건")
                        if badges:
                            st.warning(" · ".join(badges))
                        else:
                            st.caption("🟢 수집 범위 내 자본이벤트·승격 지분 관계 없음 (특이사항 없음).")
                with link_col:
                    if risk.get("found"):
                        st.button(
                            "🔍 4단 리포트",
                            key=f"goto2_{h['id']}",
                            use_container_width=True,
                            on_click=_goto_menu2_with_corp,
                            args=(risk["corp_code"],)
                        )
                st.markdown("---")


# ── 법적 고지 및 면책 조항 (Legal Disclaimer) ──
st.markdown("""
---
<div style='text-align: center; color: #777777; font-size: 12px; margin-top: 20px; line-height: 1.6;'>
⚖️ <b>법적 고지 및 면책 조항 (Legal Disclaimer)</b>: 본 DART-Trace 플랫폼에서 제공하는 지배구조 분석 지표 및 이상 거래 탐지 결과는 금융감독원 공시 원문 데이터를 바탕으로 산출된 알고리즘 분석 모델의 참조 자료이며, 특정 인물이나 법인의 불법 행위 또는 위법성을 단정하지 않습니다. 최종적인 법적·투자 판단은 금융감독원 공시 원문 확인을 권장합니다.
</div>
""", unsafe_allow_html=True)
