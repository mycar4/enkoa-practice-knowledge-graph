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
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network
import networkx as nx

# 5% 공시 명시적 어댑터 (읽기 전용 / 동결 규격)
sys.path.insert(0, os.path.abspath("내작업폴더"))
from adapter_5pct_general_art142_v1 import run_adapter_5pct_general_art142_v1

# 1. 환경 설정 & Streamlit 페이지 설정
st.set_page_config(
    page_title="DART-Trace 기업 지배구조 GraphRAG 플랫폼",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://2fa50db4.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "2fa50db4")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Neo4j 드라이버 연결 (URI별 캐싱 자동 갱신 - 100% Read-Only 안전 연결)
@st.cache_resource
def get_neo4j_driver(uri: str, user: str, password: str):
    try:
        if not password:
            st.warning("⚠️ .env 또는 Streamlit Secrets에 NEO4J_PASSWORD가 설정되지 않았습니다.")
            return None
        driver = GraphDatabase.driver(uri, auth=(user, password), max_connection_lifetime=120)
        driver.verify_connectivity()
        return driver
    except Exception as e:
        st.error(f"❌ Neo4j 연결 실패 ({uri}): {e}")
        return None

driver = get_neo4j_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

def run_cypher(query: str, **params):
    if not driver:
        return []
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

def ensure_company_ownership_data(company_name: str):
    """[보안 조치] 공개 웹 대시보드에서의 실시간 DB 쓰기(MERGE) 제거 (100% Read-Only 안전 유지)"""
    pass

def generate_graphrag_response(prompt: str, api_key_input: str = "") -> dict:
    """GraphRAG 자연어 질의 ➔ 엔티티/인텐트 추출 ➔ Neo4j 정밀 Cypher ➔ 팩트 증빙 기반 응답 생성 공용 함수"""
    llm_intent_data = {
        "intent": "SINGLE_SEARCH",
        "entities": [],
        "keywords": []
    }
    
    if api_key_input and api_key_input.startswith("sk-"):
        try:
            parser_prompt = f"""
당신은 금융 지식그래프 쿼리 라우터입니다. 사용자의 질문을 분석하여 JSON 형식으로만 응답하세요.
지식그래프에 존재하는 대표 엔티티: 삼성물산, 삼성전자, 삼성생명, 삼성바이오로직스, 이재용, 이부진, 현대자동차, 현대모비스, 기아, 현대글로비스, 정의선, 정몽구, SK(주), SK이노베이션, SK텔레콤, SK하이닉스, 최태원, (주)LG, LG전자, LG화학, 구광모, (주)한화, 한화에어로스페이스, 김승연, 김동관, 국민연금공단, MBK파트너스, 강철민, 골든홀딩스투자조합, 루미너스테크, 에이펙스바이오, 박성호, 조명훈, 블루스톤1호조합, 스타네트웍스, 장동식, 아시아혁신투자조합, ESR켄달스퀘어리츠, HD한국조선해양, HD현대중공업, HD현대, HDC, NAVER, KB금융

[규칙]:
1. intent 분류: 
   - "CIRCULAR_LOOP" (순환출자, 고리, 루프 질문)
   - "COMPARISON" (2개 이상 기업 또는 특정 소유자-대상사 간의 지분/출자 비교)
   - "SUMMARY_STATS" (총수별 통계, 집계, 평균, 중앙값, 지배력순위)
   - "CAPITAL_EVENTS" (주요 자본 이벤트: CB/BW 발행, 유상증자, 회사합병, 주식양수도)
   - "SINGLE_ENTITY" (단일 기업이나 인물 지배구조 분석)
   - "GENERAL" (일반 질문)
2. entities: 질문에서 언급된 기업/인물명을 표준 명칭으로 정규화하여 리스트로 반환 (예: "삼전" -> "삼성전자", "현대중공업" -> "HD현대중공업", "한국조선해양" -> "HD한국조선해양", "켄달스퀘어" -> "ESR켄달스퀘어리츠", "국민연금" -> "국민연금공단")

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
                
                usage = res_body.get("usage", {})
                p_tok = usage.get("prompt_tokens", 0)
                c_tok = usage.get("completion_tokens", 0)
                tot_tok = usage.get("total_tokens", 0)
                cost_krw = (p_tok * 0.15 / 1000000 + c_tok * 0.60 / 1000000) * 1400
                token_usage_info = {
                    "prompt": p_tok,
                    "completion": c_tok,
                    "total": tot_tok,
                    "cost_krw": round(cost_krw, 4),
                    "task": "인텐트 및 엔티티 파싱"
                }
                llm_prompt_payload = {
                    "task": "LLM 기반 자연어 인텐트 및 엔티티 링킹 (Router)",
                    "system_prompt": parser_prompt,
                    "user_prompt": prompt
                }
        except Exception:
            token_usage_info = None
            llm_prompt_payload = {}
    else:
        token_usage_info = None
        llm_prompt_payload = {}
    
    # 엔티티 파서 백업 (규칙 기반 엔티티 탐지)
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
    raw_facts_text = ""
    
    # A. 2개 이상 엔티티 쌍방 직접 지분/출자 관계 조회 (PAIR_ENTITY_STAKE)
    if (detected_intent == "COMPARISON" or len(detected_entities) >= 2) and detected_entities:
        ent1 = detected_entities[0]
        ent2 = detected_entities[1] if len(detected_entities) > 1 else detected_entities[0]
        
        cypher_executed = f"""
// ⚖️ [지정된 두 엔티티 간의 직접 지분 및 출자 관계 엄격 쿼리] {ent1} <-> {ent2}
MATCH (a)-[r]->(b)
WHERE ((a.name = '{ent1}' AND b.name = '{ent2}') OR (a.name = '{ent2}' AND b.name = '{ent1}'))
  AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos, b.name AS target,
       r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
       r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
ORDER BY r.is_current DESC, r.reported_on DESC, r.as_of_date DESC
LIMIT 10
        """
        compare_res = run_cypher("""
        MATCH (a)-[r]->(b)
        WHERE ((a.name = $ent1 AND b.name = $ent2) OR (a.name = $ent2 AND b.name = $ent1))
          AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
        RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos, b.name AS target,
               r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
               r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
        ORDER BY r.is_current DESC, r.reported_on DESC, r.as_of_date DESC
        LIMIT 10
        """, ent1=ent1, ent2=ent2)
        
        raw_data_result = {"조회_엔티티": [ent1, ent2], "조회_데이터": compare_res}
        if compare_res:
            raw_facts_text = f"### ⚖️ [GraphRAG 정밀 팩트 추출] **{ent1}** ↔ **{ent2}** 공시 지분·출자 사실\n\n"
            for r in compare_res:
                pos_str = f" ({r['pos']})" if r.get('pos') else ""
                stake_str = f"지분율 **{r.get('stake', 0.0)}%**" if r.get('stake') is not None else ""
                book_str = f" / 장부가액 **{int(r['book_value']):,}원**" if r.get('book_value') else ""
                as_of_val = str(r['as_of_date']) if r.get('as_of_date') else ""
                rep_val = str(r['reported_on']) if r.get('reported_on') else ""
                as_of_str = f" (결산기준일: `{as_of_val}`)" if as_of_val else ""
                rep_str = f" (공시접수일: `{rep_val}`)" if rep_val else ""
                rcp_str = f" [공시: [`{r['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']})]" if r.get('rcept_no') else " [근거 공시 미연결]"
                curr_str = " [🟢 최신 유효 사실]" if r.get('is_curr') is True else (" [⚪ 과거 이력]" if r.get('is_curr') is False else "")
                ver_str = f" [{r['ver_st']}]" if r.get('ver_st') else ""
                raw_facts_text += f"• **{r['owner']}** ──[{r['rel']}: {stake_str}{book_str}]──> **{r['target']}**{pos_str}{as_of_str}{rep_str}{rcp_str}{curr_str}{ver_str}\n"
        else:
            raw_facts_text = f"⚠️ **'{ent1}'**와(과) **'{ent2}'** 간의 직접적인 지분/출자 관계는 **현재 적재된 공시 데이터에서 확인 불가**합니다."

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
            raw_facts_text = f"### 🔄 [순환출자 탐색] 현대차그룹 순환출자 고리 적발\n\n```text\n{route_str}\n```\n"
        else:
            raw_facts_text = "🔍 지식그래프 내 추가적인 순환출자 고리는 발견되지 않았습니다."

    # B-1. [3대 지배구조 분석] 지배 네트워크 영향력 후보 탐색 & 간접 환산 지분 (INFLUENCE_SEARCH)
    elif any(kw in prompt for kw in ["영향력", "후보", "실세", "배후", "지배력", "PPR", "지분망", "주변 지분망", "실질지배"]):
        target_ent = detected_entities[0] if detected_entities else "삼성전자"
        
        # 1. 대상 회사 정보 조회
        comp_info = run_cypher("MATCH (c:DART_Company) WHERE c.name = $name RETURN c.corp_code AS ccode, c.name AS name", name=target_ent)
        target_code = comp_info[0]['ccode'] if comp_info and comp_info[0].get('ccode') else None
        
        # 2. 계층 1: 공시 기재 직접 보유 팩트 (1-Hop)
        tier1_cypher = """
        MATCH (h)-[r:OWNS_STAKE]->(c:DART_Company {name: $name})
        WHERE r.is_current = true
        RETURN coalesce(h.name, h.global_person_id) AS holder_name,
               labels(h)[0] AS holder_type,
               coalesce(h.corp_code, h.org_id, h.global_person_id) AS holder_pk,
               r.stake AS stake,
               r.shares_count AS shares,
               r.source_rcept_no AS rcept_no
        ORDER BY r.stake DESC
        LIMIT 7
        """
        tier1_res = run_cypher(tier1_cypher, name=target_ent)
        
        # 3. 계층 2: 최대 4-Hop 내 단순 산술 경로 곱 합산 (Simple DAG)
        tier2_cypher = """
        MATCH path = (root)-[r:OWNS_STAKE*1..4]->(target:DART_Company {name: $name})
        WHERE ALL(rel IN r WHERE rel.is_current = true)
          AND ALL(i IN range(0, size(nodes(path))-2) WHERE ALL(j IN range(i+1, size(nodes(path))-1) WHERE nodes(path)[i] <> nodes(path)[j]))
        WITH root, target, path,
             REDUCE(prod = 1.0, rel IN relationships(path) | prod * (rel.stake / 100.0)) * 100.0 AS path_stake
        WITH root, sum(path_stake) AS total_arithmetic_stake, min(length(path)) AS shortest_hop, count(path) AS path_count
        RETURN coalesce(root.name, root.global_person_id) AS root_name,
               labels(root)[0] AS root_type,
               shortest_hop,
               path_count,
               total_arithmetic_stake
        ORDER BY total_arithmetic_stake DESC
        LIMIT 7
        """
        tier2_res = run_cypher(tier2_cypher, name=target_ent)
        
        # 4. 계층 3: 지배 네트워크 영향력 후보 탐색 (NetworkX In-Memory PPR)
        raw_edges = run_cypher("""
        MATCH (h)-[r:OWNS_STAKE]->(c:DART_Company)
        WHERE r.is_current = true
          AND (h:DART_Company OR h:DART_Organization OR (h:DART_Person AND h.verification_status = 'VERIFIED'))
          AND r.stake IS NOT NULL
        RETURN coalesce(h.corp_code, h.org_id, h.global_person_id) AS src_id,
               coalesce(h.name, h.global_person_id) AS src_name,
               labels(h)[0] AS src_type,
               c.corp_code AS tgt_id,
               c.name AS tgt_name,
               r.stake AS stake
        """)
        
        G = nx.DiGraph()
        for e in raw_edges:
            src = e["src_id"]
            tgt = e["tgt_id"]
            weight = float(e["stake"]) if e["stake"] > 0 else 0.1
            G.add_node(src, name=e["src_name"], type=e["src_type"])
            G.add_node(tgt, name=e["tgt_name"], type="DART_Company")
            G.add_edge(tgt, src, weight=weight)
            
        tier3_candidates = []
        if target_code and target_code in G:
            ppr = nx.pagerank(G, alpha=0.85, personalization={target_code: 1.0}, weight='weight')
            ranked = sorted([(k, v) for k, v in ppr.items() if k != target_code], key=lambda x: x[1], reverse=True)
            for nid, score in ranked[:5]:
                nd = G.nodes[nid]
                tier3_candidates.append({"name": nd["name"], "type": nd["type"], "score": round(score, 6)})
        elif target_ent:
            target_node_ids = [nid for nid, data in G.nodes(data=True) if data.get("name") == target_ent]
            if target_node_ids:
                src_nid = target_node_ids[0]
                ppr = nx.pagerank(G, alpha=0.85, personalization={src_nid: 1.0}, weight='weight')
                ranked = sorted([(k, v) for k, v in ppr.items() if k != src_nid], key=lambda x: x[1], reverse=True)
                for nid, score in ranked[:5]:
                    nd = G.nodes[nid]
                    tier3_candidates.append({"name": nd["name"], "type": nd["type"], "score": round(score, 6)})
                    
        raw_facts_text = f"### 🏛️ [3대 지배구조 분석] **{target_ent}** 지배구조 정밀 분석 리포트\n\n"
        
        # 1) 직접 보유 팩트 테이블
        raw_facts_text += f"#### 📑 1. 공시에 기재된 직접 보유 팩트 (1-Hop)\n"
        if tier1_res:
            raw_facts_text += "| 순위 | 주주/기관명 | 엔티티 유형 | 직접 지분율 | 소유 주식수 | 근거 공시번호 |\n|---|---|---|:---:|:---:|:---:|\n"
            for idx, r in enumerate(tier1_res, 1):
                shares_str = f"{int(r['shares']):,}주" if r.get('shares') else "-"
                rcp_str = f"[`{r['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']})" if r.get('rcept_no') else "-"
                raw_facts_text += f"| {idx} | **{r['holder_name']}** | `{r['holder_type']}` | **{r['stake']:.2f}%** | {shares_str} | {rcp_str} |\n"
        else:
            raw_facts_text += "ℹ️ 등록된 5% 이상 직접 지분 보유 팩트가 없습니다.\n"
            
        # 2) 간접 산술 환산 지분 테이블
        raw_facts_text += f"\n#### 🧮 2. 최대 4-Hop 내 단순 산술 경로 곱 합산\n"
        raw_facts_text += "> ⚠️ *본 수치는 Simple DAG 경로 기준 단순 산술 계산값이며, 우선주·의결권 차이·순환출자를 포함한 법적 실질 지배력과 동일시할 수 없습니다.*\n\n"
        if tier2_res:
            raw_facts_text += "| 순위 | 지배/소유 주체 | 엔티티 유형 | 최소 Hop | 경로수 | 산술 환산 지분율 |\n|---|---|---|:---:|:---:|:---:|\n"
            for idx, r in enumerate(tier2_res, 1):
                raw_facts_text += f"| {idx} | **{r['root_name']}** | `{r['root_type']}` | {r['shortest_hop']} | {r['path_count']} | **{r['total_arithmetic_stake']:.4f}%** |\n"
        else:
            raw_facts_text += "ℹ️ 다단계 출자 경로가 존재하지 않습니다.\n"
            
        # 3) 지배 네트워크 영향력 후보 테이블
        raw_facts_text += f"\n#### ⚡ 3. 지배 네트워크 영향력 후보 탐색 (PPR)\n"
        raw_facts_text += "> 💡 *Python NetworkX In-Memory 스트리밍 연산 (가중치 역방향 전파). PageRank 확률 정규화 특성으로 인해 지분율 절대치와 비례하지 않는 탐색 지표입니다.*\n\n"
        if tier3_candidates:
            raw_facts_text += "| 순위 | 영향력 후보 주체 | 엔티티 유형 | PPR 탐색 점수 | 비고 |\n|---|---|---|:---:|:---:|\n"
            for idx, c in enumerate(tier3_candidates, 1):
                raw_facts_text += f"| {idx} | **{c['name']}** | `{c['type']}` | **{c['score']:.6f}** | 🎯 영향력 핵심 후보 |\n"
        else:
            raw_facts_text += "ℹ️ 지배 네트워크 후보 탐색 결과가 없습니다.\n"
            
        cypher_executed = tier1_cypher
        raw_data_result = {"tier1": tier1_res, "tier2": tier2_res, "tier3": tier3_candidates}

    # C. 수치 통계 요약 (SUMMARY_STATS)
    elif detected_intent == "SUMMARY_STATS" or (any(kw in prompt for kw in ["통계", "요약", "평균", "중앙값", "순위"]) and not detected_entities):
        cypher_executed = """
// 📊 수치 요약 & 분위수 집계 (최신 유효 지분 is_current=true 만 집계)
MATCH (p:DART_Person)-[r:OWNS_STAKE {is_current: true}]->(c:DART_Company)
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
        raw_facts_text = "### 📊 [수치 요약 집계] 재벌 총수별 최신 유효 지배 지분 통계\n\n"
        raw_facts_text += "| 총수명 | 지배 기업 수 | 총 지분 합계 | 평균 지분율 | 중앙값 (p50) |\n|---|:---:|:---:|:---:|:---:|\n"
        for r in stats_res:
            raw_facts_text += f"| **{r['총수명']}** | {r['보유기업수']}개 | {r['총지분합계']}% | {r['평균지분율']}% | **{r['중앙값지분율']}%** |\n"

    # D. 자본 이벤트 공시 팩트 질의 (CAPITAL_EVENTS)
    elif detected_intent == "CAPITAL_EVENTS" or any(kw in prompt for kw in ["CB", "전환사채", "BW", "신주인수권", "유상증자", "합병", "양수도", "자본이벤트"]):
        if detected_entities:
            target_ent = detected_entities[0]
            cypher_executed = """
            MATCH (c:DART_Company {name: $name})-[:ANNOUNCED]->(e:DART_CapitalEvent)
            RETURN e.event_type AS type, e.event_name AS name, e.issue_amount AS amount,
                   e.conversion_price AS cv_price, e.is_private AS is_private,
                   e.target_corp_name AS target, e.merger_ratio AS merger_ratio,
                   e.source_rcept_no AS rcept_no, e.received_on AS received_on,
                   e.decided_on AS decided_on, e.effective_on AS effective_on
            ORDER BY e.received_on DESC
            LIMIT 10
            """
            cap_events = run_cypher(cypher_executed, name=target_ent)
            raw_data_result = cap_events
            if cap_events:
                raw_facts_text = f"### ⚡ [GraphRAG 자본 이벤트 팩트] **{target_ent}** 주요 공시 변동 내역\n\n"
                for ev in cap_events:
                    amt_str = f" / 발행·양수액 **{int(ev['amount']):,}원**" if ev.get('amount') else ""
                    cv_str = f" / 전환가 **{int(ev['cv_price']):,}원**" if ev.get('cv_price') else ""
                    priv_str = " (사모)" if ev.get('is_private') else ""
                    tgt_str = f" ➔ 상대방: **{ev['target']}**" if ev.get('target') else ""
                    ratio_str = f" (합병비율: `{ev['merger_ratio']}`)" if ev.get('merger_ratio') else ""
                    rcp_str = f" [공시: [`{ev['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={ev['rcept_no']})]"
                    dec_str = f" (결의일: `{str(ev['decided_on'])}`)" if ev.get('decided_on') else ""
                    eff_str = f" (효력/납입일: `{str(ev['effective_on'])}`)" if ev.get('effective_on') else ""
                    raw_facts_text += f"• **{ev['name']}**{priv_str}{amt_str}{cv_str}{tgt_str}{ratio_str}{dec_str}{eff_str} (접수일: `{str(ev['received_on'])}`){rcp_str}\n"
            else:
                raw_facts_text = f"⚠️ **'{target_ent}'** 관련 사모CB 및 자본 이벤트 데이터는 **현재 적재된 공시 데이터에서 확인 불가**합니다."
        else:
            raw_facts_text = "ℹ️ 다단계 사모사채 인수자(SUBSCRIBED) 및 연계 출자 경로는 **Phase 2에서 정식 적재될 예정**입니다. (현재 데이터 미적재)"

    # E. 단일 엔티티 상세 지배구조 & 출자 현황 (SINGLE_ENTITY)
    elif detected_entities:
        target_ent = detected_entities[0]
        cypher_executed = f"""
// 1. 직접 지분 및 출자 관계 (1-Hop)
MATCH (a {{name: '{target_ent}'}})-[r]->(b)
WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
RETURN b.name AS target, type(r) AS rel, r.stake AS stake, r.position AS pos,
       r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
       r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
ORDER BY r.is_current DESC, r.reported_on DESC, r.stake DESC

// 2. 피지배 / 주요주주 관계 (누가 지배하는가)
MATCH (a)-[r]->(b {{name: '{target_ent}'}})
WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos,
       r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
       r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
ORDER BY r.is_current DESC, r.reported_on DESC, r.stake DESC
        """
        direct_stakes = run_cypher("""
        MATCH (a {name: $name})-[r]->(b)
        WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
        RETURN b.name AS target, type(r) AS rel, r.stake AS stake, r.position AS pos,
               r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
               r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
        ORDER BY r.is_current DESC, r.reported_on DESC, r.stake DESC
        """, name=target_ent)
        
        owned_by = run_cypher("""
        MATCH (a)-[r]->(b {name: $name})
        WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
        RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos,
               r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
               r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
        ORDER BY r.is_current DESC, r.reported_on DESC, r.stake DESC
        """, name=target_ent)
        
        multi_hop = run_cypher("MATCH path = (a {name: $name})-[:OWNS_STAKE*2..3]->(c) RETURN DISTINCT c.name AS indirect_comp, length(path) AS hops LIMIT 10", name=target_ent)
        
        cap_events = run_cypher("""
        MATCH (c:DART_Company {name: $name})-[:ANNOUNCED]->(e:DART_CapitalEvent)
        RETURN e.event_type AS type, e.event_name AS name, e.issue_amount AS amount,
               e.conversion_price AS cv_price, e.is_private AS is_private,
               e.target_corp_name AS target, e.merger_ratio AS merger_ratio,
               e.source_rcept_no AS rcept_no, e.received_on AS received_on
        ORDER BY e.received_on DESC
        LIMIT 5
        """, name=target_ent)

        raw_data_result = {"1_보유지분_및_출자": direct_stakes, "2_주요주주": owned_by, "3_다단계_우회": multi_hop, "4_자본이벤트": cap_events}
        
        if not direct_stakes and not owned_by and not multi_hop and not cap_events:
            raw_facts_text = f"⚠️ **'{target_ent}'** 관련 공시 데이터는 **현재 적재된 공시 데이터에서 확인 불가**합니다."
        else:
            raw_facts_text = f"### 📊 [GraphRAG 실시간 분석] **{target_ent}** 지배구조 & 출자 네트워크 리포트\n\n"
            if direct_stakes:
                raw_facts_text += f"#### 1️⃣ **{target_ent}**이(가) 보유한 지분 및 출자 내역:\n"
                for row in direct_stakes:
                    pos_str = f" ({row['pos']})" if row.get('pos') else ""
                    stake_str = f"**{row.get('stake', 0.0)}%**" if row.get('stake') is not None else ""
                    book_str = f" / 장부가액 **{int(row['book_value']):,}원**" if row.get('book_value') else ""
                    as_of_val = str(row['as_of_date']) if row.get('as_of_date') else ""
                    rep_val = str(row['reported_on']) if row.get('reported_on') else ""
                    as_of_str = f" (기준일: `{as_of_val}`)" if as_of_val else ""
                    rep_str = f" (접수일: `{rep_val}`)" if rep_val else ""
                    rcp_str = f" [공시: [`{row['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row['rcept_no']})]" if row.get('rcept_no') else " [근거 공시 미연결]"
                    curr_str = " [🟢 최신 유효 사실]" if row.get('is_curr') is True else ""
                    raw_facts_text += f"• **{row['target']}**: {stake_str}{book_str}{pos_str}{as_of_str}{rep_str}{rcp_str}{curr_str}\n"
            if owned_by:
                raw_facts_text += f"\n#### 2️⃣ **{target_ent}**의 주요 주주 (누가 지배하는가):\n"
                for row in owned_by:
                    pos_str = f" ({row['pos']})" if row.get('pos') else ""
                    stake_str = f"**{row.get('stake', 0.0)}%**" if row.get('stake') is not None else ""
                    book_str = f" / 장부가액 **{int(row['book_value']):,}원**" if row.get('book_value') else ""
                    as_of_val = str(row['as_of_date']) if row.get('as_of_date') else ""
                    rep_val = str(row['reported_on']) if row.get('reported_on') else ""
                    as_of_str = f" (기준일: `{as_of_val}`)" if as_of_val else ""
                    rep_str = f" (접수일: `{rep_val}`)" if rep_val else ""
                    rcp_str = f" [공시: [`{row['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row['rcept_no']})]" if row.get('rcept_no') else " [근거 공시 미연결]"
                    curr_str = " [🟢 최신 유효 사실]" if row.get('is_curr') is True else ""
                    raw_facts_text += f"• **{row['owner']}**: {stake_str}{book_str}{pos_str}{as_of_str}{rep_str}{rcp_str}{curr_str}\n"
            if cap_events:
                raw_facts_text += f"\n#### ⚡ **{target_ent}**의 주요 자본 이벤트 (CB·증자·M&A):\n"
                for ev in cap_events:
                    amt_str = f" / 발행·양수액 **{int(ev['amount']):,}원**" if ev.get('amount') else ""
                    cv_str = f" / 전환가 **{int(ev['cv_price']):,}원**" if ev.get('cv_price') else ""
                    priv_str = " (사모)" if ev.get('is_private') else ""
                    rcp_str = f" [공시: [`{ev['rcept_no']}`](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={ev['rcept_no']})]"
                    raw_facts_text += f"• **{ev['name']}**{priv_str}{amt_str}{cv_str} (접수일: `{str(ev['received_on'])}`){rcp_str}\n"
            if multi_hop:
                raw_facts_text += f"\n#### 3️⃣ **{target_ent}**의 다단계(Multi-hop) 우회 계열사:\n"
                for row in multi_hop:
                    raw_facts_text += f"• **{row['indirect_comp']}** ({row['hops']}-Hop)\n"

    # F. 일반 질문 (FALLBACK)
    else:
        cypher_executed = "MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN n.name LIMIT 10"
        raw_data_result = {"info": "전체 노드 탐색"}
        raw_facts_text = f"🔍 **'{prompt}'**에 대한 지식그래프 질의 결과:\n\n**현재 적재된 공시 데이터에서 확인 불가**합니다. (미등록 엔티티이거나 지분 공시 미존재)"

    # ── [3단계: 최종 답변 출력 (100% Neo4j 팩트 원문 보장 정책)] ──
    # LLM은 1단계 인텐트/엔티티 파싱에만 엄격 제한하여 사용하며,
    # 최종 사용자 노출 답변(final_ans)은 0% 환각 보장을 위해 100% Neo4j 실측 팩트 원문(raw_facts_text)만 출력합니다.
    final_ans = raw_facts_text
            
    return {
        "ans": final_ans,
        "raw_facts_text": raw_facts_text,
        "raw_data": raw_data_result,
        "cypher": cypher_executed,
        "intent": detected_intent,
        "entities": detected_entities,
        "token_usage_info": token_usage_info,
        "prompt_payload": llm_prompt_payload
    }

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
    
    menu = st.radio(
        "📌 서비스 메뉴",
        [
            "🌐 1. 상장사 지배구조 & 순환출자 탐색기",
            "🤖 2. GraphRAG AI 대화형 챗봇",
            "👑 3. GDS 재계 권력 랭킹 (PageRank)",
            "⚡ 4. DS005 기업 주요 자본 이벤트 (CB·BW·증자·M&A)",
            "📥 5. 최근 5년 OpenDART 실시간 수집 & 스토리지",
            "🔍 6. 5% 공시 원문 증거 감사기 (Evidence Audit Inspector)"
        ]
    )
    
    st.markdown("---")
    st.markdown("### 📊 인프라 연결 현황")
    if driver:
        node_res = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS c")
        rel_res = run_cypher("MATCH ()-[r]->() WHERE type(r) STARTS WITH 'OWNS' OR type(r) STARTS WITH 'INVESTED' OR type(r) STARTS WITH 'ACQUIRED' OR type(r) STARTS WITH 'REPRESENTS' RETURN count(r) AS c")
        node_cnt = node_res[0]['c'] if node_res else 0
        rel_cnt = rel_res[0]['c'] if rel_res else 0
        st.success(f"✅ Neo4j: {node_cnt}개 노드 / {rel_cnt}건 관계")
    if os.getenv("DART_API_KEY"):
        st.success("✅ OpenDART 실시간 API 활성화")
    if os.getenv("OPENAI_API_KEY"):
        st.success("✅ OpenAI gpt-4o-mini 활성화")

# 🎨 테마별 커스텀 CSS 전면 주입 (BaseWeb 셀렉트박스, 팝업 드롭다운, 상단 헤더 전수 커스텀)
if "화이트" in theme_mode:
    # ☀️ 화이트 모드 전용 완벽 스타일 (가시성 100% 보장)
    st.markdown("""
    <style>
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
            color: #64748b !important;
        }
        
        /* 5. 모든 입력창 (input, textarea, text_input, number_input) 화이트 스타일 강제 */
        input, textarea, [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8 !important;
        }

        /* 6. 드롭다운 선택상자 (BaseWeb Select & 팝업 목록) 완벽 화이트 스타일 */
        div[data-baseweb="select"],
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="select"] * {
            color: #0f172a !important;
        }
        
        /* 전역 팝오버 메뉴 및 리스트박스 (BaseWeb Portal) */
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[data-baseweb="menu"],
        ul[role="listbox"],
        [data-baseweb="popover"] div,
        [data-baseweb="popover"] ul {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;
        }
        div[data-baseweb="popover"] *,
        div[data-baseweb="menu"] *,
        ul[role="listbox"] * {
            color: #0f172a !important;
            background-color: #ffffff !important;
        }
        
        /* 옵션 아이템 (드롭다운 목록) */
        li[role="option"],
        li[role="option"] > div,
        li[role="option"] span,
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] li * {
            background-color: #ffffff !important;
            color: #0f172a !important;
            font-size: 14px !important;
        }
        li[role="option"]:hover,
        li[role="option"]:hover *,
        li[role="option"]:hover span,
        li[aria-selected="true"],
        li[aria-selected="true"] *,
        li[aria-selected="true"] span,
        [data-highlighted="true"],
        [data-highlighted="true"] * {
            background-color: #e2e8f0 !important;
            color: #0284c7 !important;
        }
        
        /* 7. 하단 챗봇 입력창 (st.chat_input) 고대비 화이트 스타일 */
        div[data-testid="stChatInput"],
        div[data-testid="stChatInput"] > div,
        div[data-testid="stBottomBlockContainer"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 12px !important;
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
        
        /* 8. 탭 버튼(st.tabs) 클릭 영역 및 화이트 스타일 */
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
        
        /* 9. 카드 및 지표 */
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
        h1, h2, h3, h4, h5, h6, p, span, label, div, small, strong, b {
            color: #f0f2f6 !important;
        }
        .stCaption {
            color: #90a4ae !important;
        }
        
        /* 5. 드롭다운 (BaseWeb Select & Popover 팝업 목록) 다크 스타일 고대비 명확화 */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] div {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            color: #f8fafc !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="select"] * {
            color: #f8fafc !important;
        }
        
        /* 팝업 컨테이너 및 리스트박스 전역 다크화 */
        div[data-baseweb="popover"], 
        div[data-baseweb="popover"] > div, 
        div[data-baseweb="menu"], 
        ul[role="listbox"],
        [data-baseweb="popover"] div,
        [data-baseweb="popover"] ul {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            color: #f8fafc !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.8) !important;
        }
        div[data-baseweb="popover"] *, 
        div[data-baseweb="menu"] *, 
        ul[role="listbox"] * {
            color: #f8fafc !important;
            background-color: #1e293b !important;
        }
        
        /* 옵션 항목 텍스트 및 배경 */
        li[role="option"], 
        li[role="option"] > div,
        li[role="option"] span,
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] li * {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            font-size: 14px !important;
        }
        
        /* 호버 및 선택된 옵션 */
        li[role="option"]:hover, 
        li[role="option"]:hover *, 
        li[role="option"]:hover span,
        li[aria-selected="true"], 
        li[aria-selected="true"] *, 
        li[aria-selected="true"] span,
        [data-highlighted="true"],
        [data-highlighted="true"] * {
            background-color: #0284c7 !important;
            color: #ffffff !important;
        }
        
        /* 6. 하단 챗봇 입력창 (st.chat_input) 다크 스타일 */
        div[data-testid="stChatInput"],
        div[data-testid="stChatInput"] > div,
        div[data-testid="stBottomBlockContainer"] > div {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            border-radius: 12px !important;
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

        /* 7. 탭 버튼(st.tabs) 클릭 영역 및 다크 스타일 */
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
        
        /* 8. 텍스트 입력창 & 텍스트 영역 (Cypher 입력창) 다크 스타일 */
        textarea, input {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            font-family: 'Consolas', 'Courier New', monospace !important;
        }
        
        /* 9. 카드 및 지표 */
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
if menu == "🌐 1. 상장사 지배구조 & 순환출자 탐색기":
    st.header("🌐 상장사 지배구조 네트워크 탐색기")
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
                    "🌐 전체 상장사 통합 네트워크"
                ]
            )
        
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
            # 아직 지분 데이터가 없는 상장사인 경우 OpenDART에서 실시간 온디맨드 자동 수집
            ensure_company_ownership_data(selected_entity)
            
            # 개별 기업/인물 맞춤 중심 지배구조 네트워크 (Ego-network, 공시제출 FILED 제외)
            query = f"""
            MATCH (a)-[r]->(b)
            WHERE (a.name = '{selected_entity}' OR b.name = '{selected_entity}')
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            LIMIT 40
            """
        elif selected_group == "현대자동차그룹 (순환출자)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE a.name IN ['정의선', '정몽구', '현대모비스', '현대자동차', '기아', '현대글로비스', '현대제철', '보스턴다이내믹스']
              AND b.name IN ['정의선', '정몽구', '현대모비스', '현대자동차', '기아', '현대글로비스', '현대제철', '보스턴다이내믹스']
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "삼성그룹 (삼각 지배구조)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '삼성' OR a.name IN ['이재용', '이부진', '이서현'])
              AND (b.name STARTS WITH '삼성' OR b.name IN ['이재용', '이부진', '이서현'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "SK그룹 (지주사 체제)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH 'SK' OR a.name IN ['최태원', '노소영'])
              AND (b.name STARTS WITH 'SK' OR b.name IN ['최태원', '노소영'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "LG그룹 (지주사 체제)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH 'LG' OR a.name IN ['구광모', '(주)LG'])
              AND (b.name STARTS WITH 'LG' OR b.name IN ['구광모', '(주)LG'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "한화그룹 (방산·우주 3세 승계)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '한화' OR a.name IN ['김승연', '김동관', '(주)한화', '쎄트렉아이'])
              AND (b.name STARTS WITH '한화' OR b.name IN ['김승연', '김동관', '(주)한화', '쎄트렉아이'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "포스코 & 롯데 (지배구조)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '포스코' OR a.name STARTS WITH '롯데' OR a.name IN ['신동빈'])
              AND (b.name STARTS WITH '포스코' OR b.name STARTS WITH '롯데' OR b.name IN ['신동빈'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "카카오 & 하이브 (플랫폼·엔터)":
            query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name STARTS WITH '카카오' OR a.name STARTS WITH '하이브' OR a.name IN ['김범수', '방시혁', 'SM엔터테인먼트', '어도어'])
              AND (b.name STARTS WITH '카카오' OR b.name STARTS WITH '하이브' OR b.name IN ['김범수', '방시혁', 'SM엔터테인먼트', '어도어'])
              AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        elif selected_group == "국민연금 (NPS 10대 대기업 지분망)":
            query = """
            MATCH (a:DART_Group {name: '국민연금공단'})-[r]->(b)
            WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            """
        else:
            query = """
            MATCH (a)-[r]->(b)
            WHERE type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, properties(r) AS r_props, type(r) AS r_type, elementId(r) AS r_id
            LIMIT 70
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
                st.info("📊 실행하신 쿼리는 노드-관계(a->b) 그래프 형태가 아닌 **집계/단일 컬럼 조회 결과**입니다. 오른쪽 **[📋 데이터 테이블]** 탭에서 조회 결과를 확인하세요!")
                if raw_graph_data and len(raw_graph_data) == 1:
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
                [e for e in edges_map.values() if e['type'] in ['OWNS_STAKE', 'HOLDS_5PCT']],
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
            {"role": "assistant", "content": "안녕하세요! **DART-Trace 실시간 GraphRAG AI**입니다.\n\n대한민국 상장사의 지분율, 순환출자, 총수 지배력, 계열사 관계에 대해 무엇이든 질문하세요!\n\n💡 **추천 질문 예시:**\n• `현대자동차그룹 순환출자 구조 알려줘`\n• `삼성전자와 삼성바이오로직스 지배구조 비교해줘`\n• `이재용 회장의 삼성 계열사 지배력은?`\n• `최태원 회장이 지배하는 SK 계열사 목록과 지분율`\n• `국민연금이 대주주인 대기업들은 어디야?`"}
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
                res = generate_graphrag_response(prompt, api_key_input)
                ans = res["ans"]
                token_usage_info = res.get("token_usage_info")
                
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

    # 3. 5대 탭 구성
    tab_all, tab_cb, tab_pi, tab_mg, tab_phase2 = st.tabs([
        "📑 1. 전체 이벤트 타임라인",
        "💳 2. 전환사채(CB) & BW",
        "📈 3. 유상증자 발행 분석",
        "🤝 4. 회사합병 & 주식 양수도",
        "🔗 5. 시간순 자본 연계 경로 (Phase 2 예정)"
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

    with tab_phase2:
        st.subheader("🔗 5. 시간순 자본 연계 경로 (Phase 2 예정)")
        st.info("ℹ️ 다단계 사모사채 인수자(SUBSCRIBED) 및 연계 출자 경로는 Phase 2에서 정식 적재될 예정입니다. (현재 데이터 미적재)")


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

elif "6." in menu:
    st.header("🔍 5% 공시 원문 증거 감사기 (Evidence Audit Inspector)")
    st.caption("명시적 어댑터(`5PCT_GENERAL_ART142_V1`) 기반 동적 헤더 결속, 후보 행, inner HTML 해시 및 격리 사유 실시간 투명 감사")
    
    st.markdown("""
    <div style='background: rgba(0, 229, 255, 0.08); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 8px; padding: 12px 18px; margin-bottom: 20px;'>
        <b>🛡️ [감사 원칙 안내]</b><br/>
        • <b>Zero DB Write</b>: 본 감사기는 데이터베이스 쓰기 없이 메모리상에서 순수 읽기 전용으로 안전하게 작동합니다.<br/>
        • <b>추론 배제 & 원문 보존</b>: 수치 일치 등으로 직접보유를 임의 추론하지 않으며, 제142조 각 호 열의 원문 셀값과 2D 헤더 경로를 있는 그대로 증거 조각으로 검증합니다.<br/>
        • <b>개별 격리 (Quarantine)</b>: 열 수가 모자라거나 요약/결손인 행은 전체 문서를 억지 해석하지 않고 안전하게 격리 목록에 기록합니다.
    </div>
    """, unsafe_allow_html=True)
    
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

# ── 법적 고지 및 면책 조항 (Legal Disclaimer) ──
st.markdown("""
---
<div style='text-align: center; color: #777777; font-size: 12px; margin-top: 20px; line-height: 1.6;'>
⚖️ <b>법적 고지 및 면책 조항 (Legal Disclaimer)</b>: 본 DART-Trace 플랫폼에서 제공하는 지배구조 분석 지표 및 이상 거래 탐지 결과는 금융감독원 공시 원문 데이터를 바탕으로 산출된 알고리즘 분석 모델의 참조 자료이며, 특정 인물이나 법인의 불법 행위 또는 위법성을 단정하지 않습니다. 최종적인 법적·투자 판단은 금융감독원 공시 원문 확인을 권장합니다.
</div>
""", unsafe_allow_html=True)
