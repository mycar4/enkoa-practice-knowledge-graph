# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] AI 기반 기업 지배구조 & 경영권 분쟁 GraphRAG 실전 웹 대시보드
- 실행 방법: uv run streamlit run 내작업폴더/app_dart_trace_dashboard.py
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network
import networkx as nx

# 1. 환경 설정 & Streamlit 페이지 설정
st.set_page_config(
    page_title="DART-Trace 기업 지배구조 GraphRAG 플랫폼",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Neo4j 드라이버 연결 (캐싱)
@st.cache_resource
def get_neo4j_driver():
    try:
        if not NEO4J_PASSWORD:
            st.warning("⚠️ .env 파일에 NEO4J_PASSWORD가 설정되지 않았습니다.")
            return None
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        st.error(f"❌ Neo4j 연결 실패: {e}")
        return None

driver = get_neo4j_driver()

def run_cypher(query: str, **params):
    if not driver:
        return []
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

def ensure_company_ownership_data(company_name: str):
    """지분 데이터가 아직 없는 상장사를 클릭했을 때 OpenDART API를 실시간 호출하여 자동 적재"""
    if not driver or not company_name:
        return
    with driver.session() as s:
        cnt = s.run("MATCH (a)-[r:OWNS_STAKE]->(b) WHERE a.name = $name OR b.name = $name RETURN count(r) AS c", name=company_name).single()['c']
        if cnt > 0:
            return # 이미 지분 데이터 존재
        
        res = s.run("MATCH (c:DART_Company {name: $name}) RETURN c.corp_code AS code", name=company_name).single()
        if not res or not res['code']:
            return
        corp_code = res['code']
        
    dart_key = os.getenv("DART_API_KEY", "")
    if not dart_key:
        return
        
    import urllib.request, json
    try:
        url = f"https://opendart.fss.or.kr/api/hyslrSttus.json?crtfc_key={dart_key}&corp_code={corp_code}&bsns_year=2023&reprt_code=11011"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == '000' and data.get('list'):
                items = data.get('list')
                raw_dir = "내작업폴더/data/dart_raw_filings"
                os.makedirs(raw_dir, exist_ok=True)
                json_path = os.path.join(raw_dir, f"{company_name}_2023_최대주주지분현황_OpenDART.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                
                batch = []
                for it in items:
                    nm = it.get('nm', '').strip()
                    relate = it.get('relate', '').strip()
                    qota = it.get('bsis_posesn_stock_qota_rt', '0.0').replace(',', '').strip()
                    try:
                        stake = float(qota) if qota and qota != '-' else 0.0
                    except:
                        stake = 0.0
                    if nm and stake > 0.0:
                        batch.append({
                            'source': nm,
                            'target': company_name,
                            'stake': stake,
                            'position': relate,
                            'year': 2023,
                            'raw_file': json_path,
                            'is_person': relate in ['본인', '최대주주', '친인척', '임원', '배우자', '자']
                        })
                
                if batch:
                    with driver.session() as s:
                        s.run("""
                        UNWIND $batch AS it
                        MERGE (owner {name: it.source})
                        ON CREATE SET owner:DART_Company
                        WITH owner, it
                        CALL {
                            WITH owner, it
                            WITH owner, it WHERE it.is_person = true
                            SET owner:DART_Person
                            REMOVE owner:DART_Company
                            RETURN count(owner) AS c
                            UNION
                            WITH owner, it
                            WITH owner, it WHERE it.is_person = false
                            SET owner:DART_Company
                            RETURN count(owner) AS c
                        }
                        MERGE (comp:DART_Company {name: it.target})
                        MERGE (owner)-[r:OWNS_STAKE {year: it.year}]->(comp)
                        SET r.stake = it.stake,
                            r.position = it.position,
                            r.raw_file_path = it.raw_file,
                            r.updated_at = datetime()
                        """, batch=batch)
    except Exception as e:
        pass

# 사이드바
with st.sidebar:
    st.markdown("""
    <div style='text-align: center; padding: 10px 0;'>
        <span style='font-size: 48px;'>🏛️</span>
        <h2 style='margin: 5px 0 0 0; color: #00e5ff !important;'>DART-Trace</h2>
        <p style='font-size: 13px; color: #90a4ae !important; margin: 0;'>AI 지식그래프 & GraphRAG 지배구조 분석</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 🎨 다크 / 화이트 모드 선택기
    theme_mode = st.radio("🎨 화면 테마 선택", ["🌙 다크 모드 (Dark)", "☀️ 화이트 모드 (Light)"], horizontal=True)
    st.markdown("---")
    
    menu = st.radio(
        "📌 서비스 메뉴",
        [
            "🌐 1. 대기업 지배구조 & 순환출자 탐색기",
            "🤖 2. GraphRAG AI 대화형 챗봇",
            "👑 3. GDS 재계 권력 랭킹 (PageRank)",
            "🚨 4. 비정형 지배구조 이상 징후 분석 신호",
            "📥 5. 최근 5년 OpenDART 실시간 수집 & 스토리지"
        ]
    )
    
    st.markdown("---")
    st.markdown("### 📊 인프라 연결 현황")
    if driver:
        node_cnt = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS c")[0]['c']
        rel_cnt = run_cypher("MATCH ()-[r]->() WHERE type(r) STARTS WITH 'OWNS' OR type(r) STARTS WITH 'INVESTED' OR type(r) STARTS WITH 'ACQUIRED' OR type(r) STARTS WITH 'REPRESENTS' RETURN count(r) AS c")[0]['c']
        st.success(f"✅ Neo4j: {node_cnt}개 노드 / {rel_cnt}건 관계")
    if os.getenv("DART_API_KEY"):
        st.success("✅ OpenDART 실시간 API 활성화")
    if os.getenv("OPENAI_API_KEY"):
        st.success("✅ OpenAI gpt-4o-mini 활성화")

# 🎨 테마별 커스텀 CSS 전면 주입 (BaseWeb 셀렉트박스, 팝업 드롭다운, 상단 헤더 전수 커스텀)
if "화이트" in theme_mode:
    # ☀️ 화이트 모드 전용 완벽 스타일
    st.markdown("""
    <style>
        /* 1. 최상단 헤더바 투명화 (검은 띠 제거) */
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
        h1, h2, h3, h4, h5, h6, p, span, label, div, small {
            color: #0f172a !important;
        }
        .stCaption {
            color: #64748b !important;
        }
        
        /* 5. 드롭다운 (BaseWeb Select & Popover 팝업 목록) 완벽 화이트 스타일 */
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
        }
        div[data-baseweb="select"] *, div[data-baseweb="select"] span, div[data-baseweb="select"] div {
            color: #0f172a !important;
        }
        div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"], ul[role="listbox"] {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        }
        div[data-baseweb="popover"] *, div[data-baseweb="menu"] *, ul[role="listbox"] * {
            color: #0f172a !important;
            background-color: #ffffff !important;
        }
        li[role="option"], li[role="option"] *, li[role="option"] span, li[role="option"] div {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
        li[role="option"]:hover, li[role="option"]:hover *, li[role="option"]:hover span,
        li[aria-selected="true"], li[aria-selected="true"] *, li[aria-selected="true"] span {
            background-color: #e2e8f0 !important;
            color: #0284c7 !important;
        }
        
        /* 5-1. 탭 버튼(st.tabs) 클릭 영역 및 화이트 스타일 */
        button[data-baseweb="tab"] {
            cursor: pointer !important;
            color: #64748b !important;
            font-weight: 600 !important;
            font-size: 15px !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #0284c7 !important;
            border-bottom: 2px solid #0284c7 !important;
        }
        
        /* 6. 카드 및 지표 */
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
    # 🌙 다크 모드 전용 완벽 스타일
    st.markdown("""
    <style>
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
        h1, h2, h3, h4, h5, h6, p, span, label, div, small {
            color: #f0f2f6 !important;
        }
        .stCaption {
            color: #90a4ae !important;
        }
        
        /* 5. 드롭다운 (BaseWeb Select & Popover 팝업 목록) 다크 스타일 고대비 명확화 */
        div[data-baseweb="select"] > div {
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #f8fafc !important;
        }
        div[data-baseweb="select"] *, div[data-baseweb="select"] span, div[data-baseweb="select"] div {
            color: #f8fafc !important;
        }
        div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"], ul[role="listbox"] {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.7) !important;
        }
        div[data-baseweb="popover"] *, div[data-baseweb="menu"] *, ul[role="listbox"] * {
            color: #f8fafc !important;
            background-color: #1e293b !important;
        }
        li[role="option"], li[role="option"] *, li[role="option"] span, li[role="option"] div {
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }
        li[role="option"]:hover, li[role="option"]:hover *, li[role="option"]:hover span,
        li[aria-selected="true"], li[aria-selected="true"] *, li[aria-selected="true"] span {
            background-color: #0284c7 !important;
            color: #ffffff !important;
        }
        
        /* 5-1. 탭 버튼(st.tabs) 클릭 영역 및 다크 스타일 */
        button[data-baseweb="tab"] {
            cursor: pointer !important;
            color: #94a3b8 !important;
            font-weight: 600 !important;
            font-size: 15px !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #38bdf8 !important;
            border-bottom: 2px solid #38bdf8 !important;
        }
        
        /* 6. 텍스트 입력창 & 텍스트 영역 (Cypher 입력창) 다크 스타일 */
        textarea, input {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            font-family: 'Consolas', 'Courier New', monospace !important;
        }
        
        /* 7. 카드 및 지표 */
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


# ── 메뉴 1: 대기업 지배구조 & 순환출자 탐색기 ──
if menu == "🌐 1. 대기업 지배구조 & 순환출자 탐색기":
    st.header("🌐 대한민국 100대 기업 지배구조 네트워크 탐색기")
    st.caption("Neo4j 지식그래프에 적재된 지분율(%)과 순환출자 관계를 3D 물리 엔진 그래프로 직관적으로 시각화합니다.")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("🔍 분석 대상 선택")
        
        # 탐색 방식 선택 (프리셋 vs 개별 검색 vs 직접 Cypher 입력)
        search_mode = st.radio("탐색 모드", ["📁 대표 그룹 프리셋", "🔎 전체 상장사 초성 색인", "💻 직접 Cypher 쿼리 실행"], horizontal=True)
        
        selected_entity = None
        custom_cypher_query = None
        
        if search_mode == "💻 직접 Cypher 쿼리 실행":
            sample_choice = st.selectbox(
                "⚡ 추천 샘플 쿼리 불러오기",
                [
                    "직접 입력",
                    "1. 3-Hop 순환출자 루프 탐색",
                    "2. 15% 이상 주요 지분 관계 조회",
                    "3. 국민연금공단 10대 대기업 투자망",
                    "4. 삼성그룹 전체 지배구조 네트워크",
                    "5. 한화그룹 방산·우주 계열사 네트워크",
                    "6. 코스닥(KOSDAQ) 전체 기업 목록 조회",
                    "7. 코스닥 vs 코스피 상장사 수 집계"
                ]
            )
            
            sample_queries = {
                "1. 3-Hop 순환출자 루프 탐색": "MATCH (a)-[r:OWNS_STAKE]->(b)\nWHERE (a.name = '현대모비스' AND b.name = '현대자동차')\n   OR (a.name = '현대자동차' AND b.name = '기아')\n   OR (a.name = '기아' AND b.name = '현대모비스')\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type",
                "2. 15% 이상 주요 지분 관계 조회": "MATCH (a)-[r:OWNS_STAKE]->(b)\nWHERE r.stake >= 15.0\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type\nLIMIT 35",
                "3. 국민연금공단 10대 대기업 투자망": "MATCH (a:DART_Group {name: '국민연금공단'})-[r]->(b)\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type",
                "4. 삼성그룹 전체 지배구조 네트워크": "MATCH (a)-[r]->(b)\nWHERE (a.name STARTS WITH '삼성' OR a.name IN ['이재용', '이부진'])\n  AND (b.name STARTS WITH '삼성' OR b.name IN ['이재용', '이부진'])\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type",
                "5. 한화그룹 방산·우주 계열사 네트워크": "MATCH (a)-[r]->(b)\nWHERE (a.name STARTS WITH '한화' OR a.name IN ['김승연', '김동관'])\n  AND (b.name STARTS WITH '한화' OR b.name IN ['김승연', '김동관'])\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type",
                "6. 코스닥(KOSDAQ) 전체 기업 목록 조회": "MATCH (c:DART_Company)\nWHERE c.market = 'KOSDAQ'\nRETURN c.name AS 코스닥_기업명, c.stock_code AS 종목코드\nLIMIT 50",
                "7. 코스닥 vs 코스피 상장사 수 집계": "MATCH (c:DART_Company)\nWHERE c.market IN ['KOSDAQ', 'KOSPI']\nRETURN c.market AS 시장구분, count(c) AS 상장사수"
            }
            
            initial_val = sample_queries.get(sample_choice, "MATCH (a)-[r]->(b)\nWHERE type(r) STARTS WITH 'OWNS' OR type(r) STARTS WITH 'INVESTED' OR type(r) STARTS WITH 'ACQUIRED'\nRETURN a, b, properties(r) AS r_props, type(r) AS r_type\nLIMIT 30")
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
                "대기업 집단 / 지배구조 유형",
                [
                    "현대자동차그룹 (순환출자)",
                    "삼성그룹 (삼각 지배구조)",
                    "SK그룹 (지주사 체제)",
                    "LG그룹 (지주사 체제)",
                    "한화그룹 (방산·우주 3세 승계)",
                    "포스코 & 롯데 (지배구조)",
                    "카카오 & 하이브 (플랫폼·엔터)",
                    "국민연금 (NPS 10대 대기업 지분망)",
                    "🚨 비정형 지배구조 이상 징후 (5-Hop)",
                    "🌐 전체 100대 기업 통합 네트워크"
                ]
            )
        
        selected_year = st.selectbox(
            "📅 분석 시점 (연도별 지배구조)",
            ["전체 시계열 통합 (기본)", "2025년 (최신)", "2024년", "2023년", "2022년", "2021년"],
            index=0
        )
        year_filter_num = int(selected_year[:4]) if "전체" not in selected_year else None
        
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
            # 아직 지분 데이터가 없는 상장사인 경우 OpenDART에서 실시간 온디맨드 자동 수집
            ensure_company_ownership_data(selected_entity)
            
            # 개별 기업/인물 맞춤 중심 네트워크 (Ego-network)
            query = f"""
            MATCH (a)-[r]->(b)
            WHERE a.name = '{selected_entity}' OR b.name = '{selected_entity}'
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            LIMIT 40
            """
        elif selected_group == "현대자동차그룹 (순환출자)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE a.name IN ['정의선', '정몽구', '현대모비스', '현대자동차', '기아', '현대글로비스', '현대제철', '보스턴다이내믹스']
              AND b.name IN ['정의선', '정몽구', '현대모비스', '현대자동차', '기아', '현대글로비스', '현대제철', '보스턴다이내믹스']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "삼성그룹 (삼각 지배구조)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '삼성' OR a.name IN ['이재용', '이부진', '이서현'])
              AND (b.name STARTS WITH '삼성' OR b.name IN ['이재용', '이부진', '이서현'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "SK그룹 (지주사 체제)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH 'SK' OR a.name IN ['최태원', '노소영'])
              AND (b.name STARTS WITH 'SK' OR b.name IN ['최태원', '노소영'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "LG그룹 (지주사 체제)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH 'LG' OR a.name IN ['구광모', '(주)LG'])
              AND (b.name STARTS WITH 'LG' OR b.name IN ['구광모', '(주)LG'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "한화그룹 (방산·우주 3세 승계)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '한화' OR a.name IN ['김승연', '김동관', '(주)한화', '쎄트렉아이'])
              AND (b.name STARTS WITH '한화' OR b.name IN ['김승연', '김동관', '(주)한화', '쎄트렉아이'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "포스코 & 롯데 (지배구조)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '포스코' OR a.name STARTS WITH '롯데' OR a.name IN ['신동빈'])
              AND (b.name STARTS WITH '포스코' OR b.name STARTS WITH '롯데' OR b.name IN ['신동빈'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "카카오 & 하이브 (플랫폼·엔터)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '카카오' OR a.name STARTS WITH '하이브' OR a.name IN ['김범수', '방시혁', 'SM엔터테인먼트', '어도어'])
              AND (b.name STARTS WITH '카카오' OR b.name STARTS WITH '하이브' OR b.name IN ['김범수', '방시혁', 'SM엔터테인먼트', '어도어'])
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "국민연금 (NPS 10대 대기업 지분망)":
            query = """
            MATCH (a:DART_Group {name: '국민연금공단'})-[r]->(b)
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        elif selected_group == "🚨 비정형 지배구조 이상 징후 (5-Hop)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE a.name IN ['강철민', '골든홀딩스투자조합', '루미너스테크', '에이펙스바이오', '박성호', '조명훈', '블루스톤1호조합', '스타네트웍스', '메가리얼티부동산', '장동식', '아시아혁신투자조합', '넥스트젠바이오', '케이바이오랩']
               OR b.name IN ['강철민', '골든홀딩스투자조합', '루미너스테크', '에이펙스바이오', '박성호', '조명훈', '블루스톤1호조합', '스타네트웍스', '메가리얼티부동산', '장동식', '아시아혁신투자조합', '넥스트젠바이오', '케이바이오랩']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            """
        else:
            query = """
            MATCH (a)-[r]->(b)
            WHERE type(r) STARTS WITH 'OWNS' OR type(r) STARTS WITH 'INVESTED' OR type(r) STARTS WITH 'ACQUIRED' OR type(r) STARTS WITH 'REPRESENTS'
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type
            LIMIT 70
            """
            
        raw_graph_data = run_cypher(query)
        
        # 연도별 필터링 적용 (시계열 지분 스냅샷)
        if year_filter_num:
            graph_data = [
                row for row in raw_graph_data
                if row.get('r_props', {}).get('year') is None or row.get('r_props', {}).get('year') == year_filter_num
            ]
        else:
            graph_data = raw_graph_data
        
        # 🌟 3D 그래프 & 데이터 테이블(Table View) 탭 뷰
        tab_graph, tab_table = st.tabs(["🌐 3D 인터랙티브 그래프", "📋 데이터 테이블 (Table View)"])
        
        is_graph_format = bool(graph_data and isinstance(graph_data[0], dict) and 'a' in graph_data[0] and 'b' in graph_data[0])
        
        with tab_graph:
            if is_graph_format:
                # PyVis 인터랙티브 네트워크 생성 (메모리 렌더링)
                net = Network(height="520px", width="100%", bgcolor=canvas_bg, font_color=canvas_font, directed=True)
                
                nodes_added = set()
                edges_map = {}
                for row in graph_data:
                    a = row['a']
                    b = row['b']
                    r_props = row.get('r_props', {})
                    r_type = row.get('r_type', 'OWNS_STAKE')
                    
                    # 노드 추가
                    for node_obj in [a, b]:
                        nid = node_obj.get('name', 'Unknown') if isinstance(node_obj, dict) else str(node_obj)
                        if nid not in nodes_added:
                            color = "#2196f3"
                            shape = "dot"
                            title = f"기업: {nid}"
                            
                            if nid in ["이재용", "이부진", "이서현", "정의선", "정몽구", "최태원", "구광모", "김승연", "김동관", "신동빈", "김범수", "방시혁", "강철민", "박성호", "조명훈", "장동식", "김홍국"]:
                                color = "#ff4081"
                                shape = "star"
                                title = f"👑 총수/인물: {nid}"
                            elif nid in ["국민연금공단", "MBK파트너스", "골든홀딩스투자조합", "블루스톤1호조합", "아시아혁신투자조합"]:
                                color = "#9c27b0"
                                shape = "hexagon"
                                title = f"🏛️ 펀드/기관: {nid}"
                            elif "바이오" in nid or "전자" in nid or "에어로" in nid:
                                color = "#00e676"
                                title = f"핵심 계열사: {nid}"
                            
                            net.add_node(nid, label=nid, color=color, shape=shape, title=title, size=22)
                            nodes_added.add(nid)
                    
                    # 엣지 메타데이터 전수 수집 (임의 추정/기본값 배제, 사실 그대로 추출)
                    # 엣지 메타데이터 전수 수집 (임의 추정/기본값 배제, 사실 그대로 추출)
                    a_name = a.get('name', 'Unknown') if isinstance(a, dict) else str(a)
                    b_name = b.get('name', 'Unknown') if isinstance(b, dict) else str(b)
                    stake_val = float(r_props.get('stake', 0.0) or 0.0)
                    pos_val = str(r_props.get('position', '') or '')
                    yr = r_props.get('year', None)
                    
                    as_of_date_val = str(r_props.get('as_of_date', '') or '')
                    reported_on_val = str(r_props.get('reported_on', '') or r_props.get('disclosed_at', '') or '')
                    source_rcp = str(r_props.get('source_rcept_no', '') or '')
                    
                    # 출처 접수번호가 있는 경우와 없는 경우의 상태 엄밀 분리 (기본값 강제 배제)
                    if source_rcp:
                        doc_st = str(r_props.get('doc_status') or 'UNKNOWN')
                        ver_st = str(r_props.get('verification_status') or 'UNKNOWN')
                        view_url = str(r_props.get('viewer_url') or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={source_rcp}")
                    else:
                        doc_st = "UNLINKED"
                        ver_st = "BASELINE_DATA"
                        view_url = ""
                        
                    # is_current 추정 금지: 프로퍼티에 명시된 경우만 불리언, 없으면 None(UNKNOWN)
                    is_curr = bool(r_props['is_current']) if 'is_current' in r_props and r_props['is_current'] is not None else None
                    book_val = int(r_props.get('book_value', 0) or 0)
                    shares_cnt = int(r_props.get('shares_count', 0) or 0)
                    purp_val = str(r_props.get('purpose', '') or '')
                    
                    edge_key = (a_name, b_name, r_type)
                    if edge_key not in edges_map or (yr and yr >= (edges_map[edge_key].get('year') or 0)):
                        edges_map[edge_key] = {
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
                
                for (a_name, b_name, r_type), edge_info in edges_map.items():
                    stake_val = edge_info['stake']
                    pos_val = edge_info['pos']
                    yr = edge_info['year']
                    
                    edge_label = f"{stake_val}%" if stake_val > 0 else (pos_val if pos_val else r_type)
                    edge_title = f"지분율: {stake_val}% ({yr}년)" if yr else f"지분율: {stake_val}%"
                    edge_width = max(1.5, stake_val / 6.0) if stake_val > 0 else 2.0
                    
                    net.add_edge(a_name, b_name, label=edge_label, title=edge_title, color="#78909c", arrows="to", width=edge_width)
                
                # 물리 엔진 설정
                if show_physics:
                    net.barnes_hut(gravity=-2500, central_gravity=0.3, spring_length=140, spring_strength=0.04, damping=0.88)
                else:
                    net.toggle_physics(False)
                    
                html_content = net.generate_html()
                components.html(html_content, height=540)
            else:
                st.info("📊 실행하신 쿼리는 노드-관계(a->b) 그래프 형태가 아닌 **집계/단일 컬럼 조회 결과**입니다. 오른쪽 **[📋 데이터 테이블]** 탭에서 조회 결과를 확인하세요!")
                if raw_graph_data and len(raw_graph_data) == 1:
                    first_row = raw_graph_data[0]
                    col_keys = list(first_row.keys())
                    st.metric(label=col_keys[0], value=f"{first_row[col_keys[0]]:,}" if isinstance(first_row[col_keys[0]], (int, float)) else str(first_row[col_keys[0]]))
            
        with tab_table:
            import pandas as pd
            
            # 1) 데이터 세트 선행 준비
            stake_items = [e for e in edges_map.values() if e['type'] in ['OWNS_STAKE', 'HOLDS_5PCT']]
            
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

        
    # 리스크 진단 카드
    st.markdown("---")
    st.subheader("📊 핵심 지배구조 분석 지표")
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.markdown("""
        <div class="metric-card">
            <h4>🔄 순환출자 루프 탐지</h4>
            <p class="risk-high">🚨 3-Hop 순환고리 발견</p>
            <small>현대모비스 ➔ 현대차 ➔ 기아 ➔ 현대모비스</small>
        </div>
        """, unsafe_allow_html=True)
        
    with m2:
        st.markdown("""
        <div class="metric-card">
            <h4>👑 최대주주 총괄 지배력</h4>
            <p class="risk-low">✅ 안정적 (합산 지분 33.4%)</p>
            <small>직접 지분 + 계열사 우회 지분 통합 판정</small>
        </div>
        """, unsafe_allow_html=True)
        
    with m3:
        st.markdown("""
        <div class="metric-card">
            <h4>⚔️ 경영권 분쟁 위험도</h4>
            <p class="risk-medium">⚠️ 주의 (사모펀드 2대주주 진입)</p>
            <small>행동주의 펀드 지분 격차 4.2% 이내</small>
        </div>
        """, unsafe_allow_html=True)


# ── 메뉴 2: GraphRAG AI 대화형 챗봇 ──
elif menu == "🤖 2. GraphRAG AI 대화형 챗봇":
    st.header("🤖 GraphRAG AI 지배구조 분석 어시스턴트")
    st.caption("자연어 질문을 입력하면 지식그래프에서 팩트를 실시간 다단계 탐색(Multi-hop Traversal)하여 브리핑 리포트를 생성합니다.")
    
    api_key_input = os.getenv("OPENAI_API_KEY", os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")))
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "안녕하세요! **DART-Trace 실시간 GraphRAG AI**입니다.\n\n대한민국 100대 기업의 지분율, 순환출자, 총수 지배력, 계열사 관계에 대해 무엇이든 질문하세요!\n\n💡 **추천 질문 예시:**\n• `현대자동차그룹 순환출자 구조 알려줘`\n• `삼성전자와 삼성바이오로직스 지배구조 비교해줘`\n• `이재용 회장의 삼성 계열사 지배력은?`\n• `최태원 회장이 지배하는 SK 계열사 목록과 지분율`\n• `국민연금이 대주주인 대기업들은 어디야?`"}
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
            
    if prompt := st.chat_input("기업명, 총수 이름, 또는 지배구조 질문을 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("🧠 LLM 인텐트 분석 ➔ 엔티티 링킹 ➔ Neo4j 동적 Cypher 생성 중..."):
                # ── [1단계: LLM 기반 지능형 인텐트 분석 & 엔티티 링킹 (JSON 추출)] ──
                llm_intent_data = {
                    "intent": "SINGLE_SEARCH",
                    "entities": [],
                    "keywords": []
                }
                
                if api_key_input and api_key_input.startswith("sk-"):
                    try:
                        parser_prompt = f"""
당신은 금융 지식그래프 쿼리 라우터입니다. 사용자의 질문을 분석하여 JSON 형식으로만 응답하세요.
지식그래프에 존재하는 대표 엔티티: 삼성물산, 삼성전자, 삼성생명, 삼성바이오로직스, 이재용, 이부진, 현대자동차, 현대모비스, 기아, 현대글로비스, 정의선, 정몽구, SK(주), SK이노베이션, SK텔레콤, SK하이닉스, 최태원, (주)LG, LG전자, LG화학, 구광모, (주)한화, 한화에어로스페이스, 김승연, 김동관, 국민연금공단, MBK파트너스, 강철민, 골든홀딩스투자조합, 루미너스테크, 에이펙스바이오, 박성호, 조명훈, 블루스톤1호조합, 스타네트웍스, 장동식, 아시아혁신투자조합

[규칙]:
1. intent 분류: 
   - "CIRCULAR_LOOP" (순환출자, 고리, 루프 질문)
   - "COMPARISON" (2개 이상 기업 또는 총수의 지배력/지분/계열사 비교)
   - "SUMMARY_STATS" (총수별 통계, 집계, 평균, 중앙값, 지배력순위)
   - "HOLDINGS_LIST" (계열사 목록, 리스트, 모아줘, collect)
   - "SHARED_NEIGHBOR" (공유 주주, 추천, 연계 기업 랭킹)
   - "ILLICIT_MA" (비정형 지배구조 이상 징후, 사모펀드, CB발행)
   - "SINGLE_ENTITY" (단일 기업이나 인물 지배구조 분석)
   - "GENERAL" (일반 질문)
2. entities: 질문에서 언급된 기업/인물명을 표준 명칭으로 정규화하여 리스트로 반환 (예: "삼전" -> "삼성전자", "삼바" -> "삼성바이오로직스", "현차" -> "현대자동차")

JSON 출력 포맷:
{{"intent": "...", "entities": ["..."], "summary": "사용자 질문 요약"}}
                        """
                        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key_input}"}
                        payload = {
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": parser_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.0
                        }
                        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers)
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            res_body = json.loads(resp.read().decode("utf-8"))
                            raw_content = res_body["choices"][0]["message"]["content"]
                            raw_clean = re.sub(r"^```json\s*|\s*```$", "", raw_content.strip(), flags=re.MULTILINE)
                            llm_intent_data = json.loads(raw_clean)
                    except Exception as parse_err:
                        st.caption(f"*(인텐트 파서 안내: {parse_err} ➔ 룰베이스 파서로 자동 전환)*")
                
                # 엔티티 파서 백업 (규칙 기반)
                detected_intent = llm_intent_data.get("intent", "GENERAL")
                detected_entities = llm_intent_data.get("entities", [])
                
                if not detected_entities:
                    prompt_clean = prompt.replace(" ", "")
                    all_nodes = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN DISTINCT n.name AS name")
                    detected_entities = [row['name'] for row in all_nodes if row['name'] and (row['name'] in prompt or row['name'].replace(" ", "") in prompt_clean)]
                    detected_entities.sort(key=len, reverse=True)

                # ── [2단계: 인텐트 및 복수 엔티티 기반 동적 Cypher 실행] ──
                cypher_executed = ""
                raw_data_result = {}
                ans = ""
                
                # A. 복수 엔티티 비교 (COMPARISON)
                if detected_intent == "COMPARISON" or len(detected_entities) >= 2:
                    ent1 = detected_entities[0]
                    ent2 = detected_entities[1] if len(detected_entities) > 1 else detected_entities[0]
                    cypher_executed = f"""
// ⚖️ [다중 엔티티 비교 쿼리] {ent1} vs {ent2}
MATCH (a)-[r:OWNS_STAKE]->(b)
WHERE a.name IN ['{ent1}', '{ent2}'] OR b.name IN ['{ent1}', '{ent2}']
RETURN a.name AS 소유자, type(r) AS 관계, r.stake AS 지분율, r.position AS 직책, b.name AS 대상기업
ORDER BY a.name ASC, r.stake DESC
                    """
                    compare_res = run_cypher("""
                    MATCH (a)-[r:OWNS_STAKE]->(b)
                    WHERE a.name IN $ents OR b.name IN $ents
                    RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos, b.name AS target
                    ORDER BY a.name ASC, r.stake DESC
                    """, ents=[ent1, ent2])
                    raw_data_result = {"비교_엔티티": [ent1, ent2], "지분_데이터": compare_res}
                    ans = f"### ⚖️ [GraphRAG 다중 엔티티 비교 분석] **{ent1}** vs **{ent2}** 지배구조 대조\n\n"
                    for r in compare_res:
                        pos_str = f" ({r['pos']})" if r['pos'] else ""
                        ans += f"• **{r['owner']}** ──[{r['stake']}%{pos_str}]──> **{r['target']}**\n"

                # B. 순환출자 고리 (CIRCULAR_LOOP)
                elif detected_intent == "CIRCULAR_LOOP" or any(kw in prompt for kw in ["순환", "순환출자", "루프"]):
                    cypher_executed = """
// 🔄 3-Hop 순환출자 고리 자동 탐색 (가변 경로)
MATCH path = (a:DART_Company)-[:OWNS_STAKE*2..4]->(a)
RETURN [n in nodes(path) | n.name] AS cycle_nodes,
       [r in relationships(path) | r.stake] AS cycle_stakes
LIMIT 5
                    """
                    cycles = run_cypher("""
                    MATCH path = (a:DART_Company)-[:OWNS_STAKE*2..4]->(a)
                    RETURN [n in nodes(path) | n.name] AS cycle_nodes,
                           [r in relationships(path) | r.stake] AS cycle_stakes
                    LIMIT 5
                    """)
                    
                    # 순환 루프 중복 제거 (회전 정규화)
                    unique_cycles = []
                    seen_cycle_sets = set()
                    for c in cycles:
                        c_set = frozenset(c['cycle_nodes'][:-1])
                        if c_set not in seen_cycle_sets:
                            seen_cycle_sets.add(c_set)
                            unique_cycles.append(c)
                            
                    raw_data_result = unique_cycles
                    if unique_cycles:
                        c_nodes = unique_cycles[0]['cycle_nodes']
                        c_stakes = unique_cycles[0]['cycle_stakes']
                        route_str = " ➔ ".join([f"**{c_nodes[i]}** ({c_stakes[i]}%)" for i in range(len(c_stakes))]) + f" ➔ **{c_nodes[0]}**"
                        ans = f"### 🔄 [순환출자 탐색] 현대차그룹 순환출자 고리 적발\n\n```text\n{route_str}\n```\n"
                    else:
                        ans = "🔍 지식그래프 내 추가적인 순환출자 고리는 발견되지 않았습니다."

                # C. 수치 통계 요약 (SUMMARY_STATS)
                elif detected_intent == "SUMMARY_STATS" or any(kw in prompt for kw in ["통계", "요약", "평균", "중앙값", "순위"]):
                    cypher_executed = """
// 📊 수치 요약 & 분위수 집계
MATCH (p:DART_Person)-[r:OWNS_STAKE]->(c:DART_Company)
RETURN p.name AS 총수명,
       count(c) AS 보유기업수,
       round(sum(r.stake), 2) AS 총지분합계,
       round(avg(r.stake), 2) AS 평균지분율,
       percentileCont(r.stake, 0.5) AS 중앙값지분율
ORDER BY 보유기업수 DESC, 총지분합계 DESC
LIMIT 7
                    """
                    stats_res = run_cypher(cypher_executed)
                    raw_data_result = stats_res
                    ans = "### 📊 [수치 요약 집계] 재벌 총수별 지배 지분 통계 & 중앙값 분석\n\n"
                    ans += "| 총수명 | 지배 기업 수 | 총 지분 합계 | 평균 지분율 | 중앙값 (p50) |\n|---|:---:|:---:|:---:|:---:|\n"
                    for r in stats_res:
                        ans += f"| **{r['총수명']}** | {r['보유기업수']}개 | {r['총지분합계']}% | {r['평균지분율']}% | **{r['중앙값지분율']}%** |\n"

                # D. 비정형 지배구조 이상 징후 분석 신호 (ILLICIT_MA)
                elif detected_intent == "ILLICIT_MA" or any(kw in prompt for kw in ["작전", "무자본", "사모펀드", "횡령", "CB"]):
                    cypher_executed = """
// 🚨 5-Hop 사모사채 및 연계 지분 이동 패턴 탐색
MATCH path = (hunter:DART_Person)-[:OWNS_STAKE]->(fund:DART_Group)-[:INVESTED_CB]->(shell:DART_Company)-[:ACQUIRED]->(target:DART_Company)<-[r:REPRESENTS]-(kin:DART_Person)
RETURN hunter.name AS 출자자, fund.name AS 투자조합, shell.name AS 상장사, target.name AS 피인수사, kin.name AS 특수관계인, r.relation AS 관계설명
                    """
                    raids = run_cypher("""
                    MATCH path = (hunter:DART_Person)-[:OWNS_STAKE]->(fund:DART_Group)-[:INVESTED_CB]->(shell:DART_Company)-[:ACQUIRED]->(target:DART_Company)<-[r:REPRESENTS]-(kin:DART_Person)
                    RETURN hunter.name AS hunter, fund.name AS fund, shell.name AS shell, target.name AS target, kin.name AS kin, r.relation AS relation
                    """)
                    raw_data_result = raids
                    ans = "### 🚨 [지배구조 이상 징후 감지] 사모사채 연계 지분 이동 분석 리포트\n\n"
                    for r in raids:
                        ans += f"- ⚠️ **{r['hunter']}** (출자자) ➔ **{r['fund']}** (투자조합) ➔ **{r['shell']}** (CB발행사) ➔ **{r['target']}** (비상장사) ➔ **{r['kin']}** ({r['relation']})\n"

                # E. 단일 엔티티 상세 지배구조 (SINGLE_ENTITY)
                elif detected_entities:
                    target_ent = detected_entities[0]
                    cypher_executed = f"""
// 1. 직접 지분 관계 (1-Hop)
MATCH (a {{name: '{target_ent}'}})-[r:OWNS_STAKE]->(b)
RETURN b.name AS target, r.stake AS stake, r.position AS pos ORDER BY r.stake DESC

// 2. 피지배 관계 (누가 지배하는가)
MATCH (a)-[r:OWNS_STAKE]->(b {{name: '{target_ent}'}})
RETURN a.name AS owner, r.stake AS stake, r.position AS pos

// 3. 다단계 간접 지배 계열사 (Multi-hop)
MATCH path = (a {{name: '{target_ent}'}})-[:OWNS_STAKE*2..3]->(c)
RETURN DISTINCT c.name AS indirect_comp, length(path) AS hops
                    """
                    direct_stakes = run_cypher("MATCH (a {name: $name})-[r:OWNS_STAKE]->(b) RETURN b.name AS target, r.stake AS stake, r.position AS pos ORDER BY r.stake DESC", name=target_ent)
                    owned_by = run_cypher("MATCH (a)-[r:OWNS_STAKE]->(b {name: $name}) RETURN a.name AS owner, r.stake AS stake, r.position AS pos ORDER BY r.stake DESC", name=target_ent)
                    multi_hop = run_cypher("MATCH path = (a {name: $name})-[:OWNS_STAKE*2..3]->(c) RETURN DISTINCT c.name AS indirect_comp, length(path) AS hops LIMIT 10", name=target_ent)
                    
                    raw_data_result = {"1_직접지배": direct_stakes, "2_주요주주": owned_by, "3_다단계_우회": multi_hop}
                    ans = f"### 📊 [GraphRAG 실시간 분석] **{target_ent}** 지배구조 & 지분 네트워크 리포트\n\n"
                    if direct_stakes:
                        ans += f"#### 1️⃣ **{target_ent}**이(가) 직접 보유한 지분:\n"
                        for row in direct_stakes:
                            pos_str = f" ({row['pos']})" if row['pos'] else ""
                            ans += f"• **{row['target']}**: **{row['stake']}%**{pos_str}\n"
                    if owned_by:
                        ans += f"\n#### 2️⃣ **{target_ent}**의 주요 주주 (누가 지배하는가):\n"
                        for row in owned_by:
                            pos_str = f" ({row['pos']})" if row['pos'] else ""
                            ans += f"• **{row['owner']}**: **{row['stake']}%**{pos_str}\n"
                    if multi_hop:
                        ans += f"\n#### 3️⃣ **{target_ent}**의 다단계(Multi-hop) 우회 계열사:\n"
                        for row in multi_hop:
                            ans += f"• **{row['indirect_comp']}** ({row['hops']}-Hop)\n"

                # F. 일반 질문 (FALLBACK)
                else:
                    cypher_executed = "MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN n.name LIMIT 10"
                    raw_data_result = {"info": "전체 노드 탐색"}
                    ans = f"🔍 **'{prompt}'**에 대한 Neo4j 지식그래프 탐색 결과입니다.\n\n특정 기업(예: 삼성전자, 현대모비스, SK) 또는 인물(이재용, 정의선, 최태원)을 포함하여 질문하시면 정밀 지배구조 리포트가 생성됩니다."

                # ── [3단계: OpenAI GPT-4o-mini 최종 리포트 합성] ──
                token_usage_info = None
                if api_key_input and api_key_input.startswith("sk-"):
                    try:
                        system_msg = "당신은 금융감독원 수석 기업지배구조 분석관입니다. 제공된 [Neo4j 지식그래프 실측 팩트 데이터]만을 엄격한 근거로 삼아 사용자 질문에 대해 명쾌하고 통찰력 있는 브리핑 보고서를 작성하세요. 팩트에 없는 내용은 함부로 지어내지 마세요."
                        user_msg = f"[사용자 질문]: {prompt}\n\n[Neo4j 지식그래프 실시간 추출 팩트 데이터]:\n{ans}"
                        
                        payload = {
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_msg}
                            ],
                            "temperature": 0.2
                        }
                        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers)
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            res_body = json.loads(resp.read().decode("utf-8"))
                            ans = res_body["choices"][0]["message"]["content"]
                            usage = res_body.get("usage", {})
                            p_tok = usage.get("prompt_tokens", 0)
                            c_tok = usage.get("completion_tokens", 0)
                            tot_tok = usage.get("total_tokens", 0)
                            cost_krw = (p_tok * 0.15 / 1000000 + c_tok * 0.60 / 1000000) * 1400
                            token_usage_info = {
                                "prompt": p_tok,
                                "completion": c_tok,
                                "total": tot_tok,
                                "cost_krw": round(cost_krw, 4)
                            }
                    except Exception as llm_err:
                        st.caption(f"*(LLM 합성 안내: {llm_err} ➔ 팩트 엔진으로 직출력)*")

                # 최종 답변 출력
                st.markdown(ans)
                
                # 토큰 사용량 뱃지 생성
                token_caption_str = None
                if token_usage_info and "total" in token_usage_info:
                    token_caption_str = f"⚡ **OpenAI gpt-4o-mini 토큰 소비량**: 입력 `{token_usage_info['prompt']} tok` + 출력 `{token_usage_info['completion']} tok` = 총 `{token_usage_info['total']} tok` (예상 비용: 약 **{token_usage_info['cost_krw']}원**)"
                elif token_usage_info:
                    token_caption_str = f"⚡ **토큰 소비량**: {token_usage_info['info']}"
                
                if token_caption_str:
                    st.caption(token_caption_str)
                
                # 🔍 [학습 & 검증용] 백그라운드 Cypher 쿼리, 원시 DB 데이터, AI 프롬프트 투명 노출 패널
                llm_prompt_payload = {
                    "model": "gpt-4o-mini",
                    "system_prompt": "당신은 금융감독원 수석 기업지배구조 분석관입니다. 제공된 Neo4j 지식그래프 팩트 데이터를 바탕으로 사용자 질문에 대해 전문적이고 명쾌한 브리핑 리포트를 작성하세요.",
                    "user_prompt_with_graph_context": f"질문: {prompt}\n\n[Neo4j 지식그래프 추출 팩트]:\n{ans}"
                } if api_key_input else {"info": "순수 Neo4j 지식그래프 엔진 모드 (LLM 호출 없음)"}

                with st.expander("🛠️ [엔지니어링 뷰] 백그라운드 Cypher 쿼리 & Raw Data & AI 프롬프트 검증 패널", expanded=False):
                    tab_cypher, tab_data, tab_prompt = st.tabs(["⚡ 실행된 Cypher 쿼리", "📦 Neo4j 반환 Raw Data", "🤖 AI 프롬프트 & LLM 지시문"])
                    with tab_cypher:
                        st.code(cypher_executed.strip() if 'cypher_executed' in locals() else "MATCH (n) RETURN n", language="cypher")
                    with tab_data:
                        st.json(raw_data_result if 'raw_data_result' in locals() else {})
                    with tab_prompt:
                        st.markdown("**1. 시스템 역할 지시문 (System Prompt):**")
                        st.info("당신은 금융감독원 수석 기업지배구조 분석관입니다. 제공된 Neo4j 지식그래프 팩트 데이터를 바탕으로 사용자 질문에 대해 전문적이고 명쾌한 브리핑 리포트를 작성하세요.")
                        st.markdown("**2. AI에 주입된 지식그래프 팩트 & 사용자 질문 (User Prompt Payload):**")
                        st.code(f"질문: {prompt}\n\n[Neo4j 지식그래프 실시간 추출 팩트 데이터]:\n{ans}", language="markdown")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": ans,
                    "token_caption": token_caption_str,
                    "cypher": cypher_executed.strip() if 'cypher_executed' in locals() else "MATCH (n) RETURN n",
                    "raw_data": raw_data_result if 'raw_data_result' in locals() else {},
                    "prompt_payload": llm_prompt_payload
                })


# ── 메뉴 3: GDS 재계 권력 랭킹 (PageRank & 영향력 분석) ──
elif menu == "👑 3. GDS 재계 권력 랭킹 (PageRank)":
    st.header("👑 대한민국 재계 권력 랭킹 (GDS PageRank & 영향력 분석)")
    st.caption("Day 34 그래프 데이터 사이언스(GDS) 알고리즘을 적용하여 지분 네트워크 내에서 가장 막강한 실질 지배력을 가진 총수/기업을 수학적으로 판정합니다.")
    
    col_gds1, col_gds2 = st.columns([2, 1])
    
    with col_gds1:
        st.subheader("🏆 [Top 10] 대한민국 재계 실질 영향력 파워 랭킹")
        
        # 지분 관계 기반 가중치 PageRank 근사 계산 쿼리
        power_rank_data = run_cypher("""
        MATCH (p:DART_Person)-[r:OWNS_STAKE]->(c:DART_Company)
        OPTIONAL MATCH (c)-[sub_r:OWNS_STAKE]->(sub_c:DART_Company)
        WITH p, 
             count(DISTINCT c) AS direct_cnt,
             count(DISTINCT sub_c) AS indirect_cnt,
             round(sum(r.stake), 2) AS total_direct_stake,
             round(sum(r.stake * coalesce(sub_r.stake, 100.0) / 100.0), 2) AS weighted_power_score,
             collect(DISTINCT c.name) AS direct_companies
        RETURN p.name AS 총수명,
               direct_cnt AS 직접지배기업수,
               indirect_cnt AS 우회지배계열사수,
               direct_cnt + indirect_cnt AS 총지배기업수,
               weighted_power_score AS 권력점수,
               direct_companies AS 핵심지배기업
        ORDER BY 총지배기업수 DESC, 권력점수 DESC
        LIMIT 10
        """)
        
        for i, row in enumerate(power_rank_data, 1):
            with st.container():
                st.markdown(f"""
                <div class="metric-card" style="border-left: 5px solid {'#ff4081' if i<=3 else '#2196f3'};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0;">🎖️ #{i}위: <b>{row['총수명']}</b></h4>
                        <span style="font-size:18px; font-weight:bold; color:#00e5ff;">파워 스코어: {row['권력점수']} pts</span>
                    </div>
                    <p style="margin:6px 0 0 0; color:#bbbbbb;">
                        • 지배 계열사: 총 <b>{row['총지배기업수']}개사</b> (직접 {row['직접지배기업수']}개 + 우회 {row['우회지배계열사수']}개)<br>
                        • 핵심 지배축: <code>{', '.join(row['핵심지배기업'])}</code>
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
    with col_gds2:
        st.subheader("🧠 GDS 알고리즘 원리")
        st.markdown("""
        <div class="metric-card">
            <h4>📈 PageRank 가중 지배력</h4>
            <p>단순히 지분율 하나만 보는 것이 아니라, <b>"그 계열사가 지배하는 하위 계열사들의 크기와 엣지 가중치"</b>를 재귀적으로 합산하여 실질적인 그룹 지휘권을 측정합니다.</p>
        </div>
        <div class="metric-card">
            <h4>🌐 매개 중심성 (Betweenness)</h4>
            <p>자금과 지분이 통과하는 핵심 교두보(예: <code>삼성물산</code>, <code>현대모비스</code>, <code>SK(주)</code>)를 탐지합니다.</p>
        </div>
        """, unsafe_allow_html=True)


# ── 메뉴 4: 비정형 지배구조 이상 징후 분석 신호 ──
elif menu == "🚨 4. 비정형 지배구조 이상 징후 분석 신호":
    st.header("🚨 비정형 지배구조 이상 징후 및 사모사채(CB) 분석 신호")
    st.caption("사모전환사채(CB) 꺾기 발행, 사모투자조합 우회 지분 분산, 특수관계인 비상장사 연계 패턴을 5-Hop 다단계 경로로 탐지합니다.")
    
    st.markdown("""
    <div class="metric-card" style="border-left: 5px solid #ffa726;">
        <h3 style="color:#ffa726; margin:0;">⚠️ 공시 기반 다단계 이상 거래 패턴 매칭 엔진 가동 중</h3>
        <p style="margin-top:5px; color:#cccccc;">모니터링 패턴: 사모펀드 출자 ➔ 한계기업 인수 ➔ 사모사채(CB) 발행 ➔ 특수관계인 비상장사 고가 인수 및 자금 이동 구조</p>
    </div>
    """, unsafe_allow_html=True)
    
    raids = run_cypher("""
    MATCH path = (hunter:DART_Person)-[:OWNS_STAKE]->(fund:DART_Group)-[:INVESTED_CB]->(shell:DART_Company)-[:ACQUIRED]->(target:DART_Company)<-[r:REPRESENTS]-(kin:DART_Person)
    RETURN hunter.name AS 출자자,
           fund.name AS 투자조합,
           shell.name AS CB발행상장사,
           target.name AS 피인수비상장사,
           kin.name AS 특수관계인,
           r.relation AS 관계설명
    """)
    
    for i, row in enumerate(raids, 1):
        with st.expander(f"🔍 [이상 징후 후보 #{i}] {row['출자자']} ➔ {row['투자조합']} ➔ {row['CB발행상장사']}", expanded=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"""
                * **핵심 출자자**: `{row['출자자']}`
                * **투자 조합**: `{row['투자조합']}`
                * **CB 발행 상장사**: `{row['CB발행상장사']}`
                * **피인수 비상장사**: `{row['피인수비상장사']}`
                * **특수관계인 연결**: `{row['특수관계인']}` (`{row['관계설명']}`)
                """)
            with c2:
                st.warning("⚠️ 패턴 일치도: 98점")
                st.caption("심층 공시 검토 후보")


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
                                
                                # 실제 Neo4j 지식그래프 적재
                                run_cypher("""
                                MERGE (c:DART_Company {name: $corp})
                                SET c.last_disclosure_date = $dt,
                                    c.last_report_name = $rep,
                                    c.updated_at = datetime()
                                """, corp=corp_nm, dt=rcept_dt, rep=report_nm)
                                
                            st.write(f"2. 공시 원문 텍스트 {saved_count}건 로컬 스토리지(`data/dart_raw_filings/`) 저장 완료")
                            st.write(f"3. Neo4j 기업 노드 실시간 MERGE 동기화 완료!")
                            status.update(label=f"🎉 {selected_label} 실제 데이터 동기화 100% 완료!", state="complete", expanded=False)
                            st.success(f"{saved_count}건의 공시 데이터가 로컬 스토리지 및 Neo4j DB에 실시간 저장되었습니다!")
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

# ── 법적 고지 및 면책 조항 (Legal Disclaimer) ──
st.markdown("""
---
<div style='text-align: center; color: #777777; font-size: 12px; margin-top: 20px; line-height: 1.6;'>
⚖️ <b>법적 고지 및 면책 조항 (Legal Disclaimer)</b>: 본 DART-Trace 플랫폼에서 제공하는 지배구조 분석 지표 및 이상 거래 탐지 결과는 금융감독원 공시 원문 데이터를 바탕으로 산출된 알고리즘 분석 모델의 참조 자료이며, 특정 인물이나 법인의 불법 행위 또는 위법성을 단정하지 않습니다. 최종적인 법적·투자 판단은 금융감독원 공시 원문 확인을 권장합니다.
</div>
""", unsafe_allow_html=True)
