#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v1.0] 자본이벤트 512차원 GraphRAG 서비스 엔진
================================================================================
- Day 35 아키텍처 기반: 512차원 Vector Index + GDS 70:30 하이브리드 리랭커
- 4-Tier Response Contract (사실 / 해석 / 원문 근거 / 다음 확인 항목) 보장
- 원문 DART 접수번호 및 공시 링크 결속
================================================================================
"""

import os
import sys
import re
import math
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS
from openai import OpenAI

# Windows stdout UTF-8 보장
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"
if not ENV_PATH.exists():
    ENV_PATH = PROJECT_ROOT.parent / ".env"
load_dotenv(ENV_PATH, override=True)

AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_driver = None
_client = None


def get_neo4j_driver():
    global _driver
    if _driver is None:
        if not AURA_URI or not AURA_USER or not AURA_PASSWORD:
            raise ValueError("AURA_URI, AURA_USER, AURA_PASSWORD 환경 변수가 누락되었습니다.")
        _driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
    return _driver


def get_openai_client():
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 환경 변수가 누락되었습니다.")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def minmax_scale(values: List[float]) -> List[float]:
    """0.0 ~ 1.0 Min-Max 정규화 (Day 35 수식)"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi, abs_tol=1e-9):
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def search_vector_only(question: str, top_k: int = 10, corp_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    OpenAI text-embedding-3-small (512차원) 임베딩 후 Neo4j Vector Index 코사인 유사도 검색
    """
    client = get_openai_client()
    driver = get_neo4j_driver()

    # 1. 512차원 질의 임베딩 생성
    res = client.embeddings.create(
        model="text-embedding-3-small",
        dimensions=512,
        input=question
    )
    query_vector = res.data[0].embedding

    # 2. Neo4j Vector Index 쿼리
    # db.index.vector.queryNodes 사용 (Aura 프로덕션 완벽 호환)
    cypher_query = """
    CALL db.index.vector.queryNodes('dart_capital_event_vector_idx', $limit, $q_vec)
    YIELD node, score
    OPTIONAL MATCH (c:DART_Company {corp_code: node.corp_code})
    WITH node, score, coalesce(c.pagerank, c.page_rank, 0.15) AS pr, coalesce(node.scale_amount, 100000000) AS scale
    WHERE $corp_filter IS NULL 
       OR node.corp_name CONTAINS $corp_filter 
       OR node.corp_code = $corp_filter
    RETURN node.event_id AS event_id,
           coalesce(node.rcept_no, node.source_rcept_no, '') AS rcept_no,
           node.corp_code AS corp_code,
           node.corp_name AS corp_name,
           node.event_type AS event_type,
           node.purpose_text AS purpose_text,
           scale AS scale_amount,
           node.decided_on AS decided_on,
           node.viewer_url AS viewer_url,
           pr AS pagerank,
           score
    ORDER BY score DESC
    LIMIT $top_k
    """

    with driver.session(default_access_mode=READ_ACCESS) as session:
        # 필터링을 고려하여 초기 검색 범위를 여유있게 가져옴
        limit_pool = top_k * 3 if corp_filter else top_k
        result = session.run(
            cypher_query,
            q_vec=query_vector,
            limit=limit_pool,
            corp_filter=corp_filter,
            top_k=top_k
        )
        hits = [dict(record) for record in result]

    return hits


def search_hybrid_rerank(hits: List[Dict[str, Any]], sim_weight: float = 0.70) -> List[Dict[str, Any]]:
    """
    Day 35 MinMax 70:30 하이브리드 리랭킹
    Final_Score = 0.70 * Sim_norm + 0.30 * (0.5 * Scale_norm + 0.5 * PR_norm)
    """
    if not hits:
        return []

    # 1. 유사도 정규화
    sim_raw = [float(h["score"]) for h in hits]
    sim_norm = minmax_scale(sim_raw)

    # 2. 규모 로그 스케일 정규화 (log10)
    scale_raw = []
    for h in hits:
        val = float(h.get("scale_amount") or 100_000_000)
        scale_raw.append(math.log10(max(val, 1.0)))
    scale_norm = minmax_scale(scale_raw)

    # 3. 네트워크 중심성(PageRank) 정규화
    pr_raw = [float(h.get("pagerank") or 0.15) for h in hits]
    pr_norm = minmax_scale(pr_raw)

    # 4. 70:30 융합 점수 계산
    fused_scores = []
    for s_n, sc_n, p_n in zip(sim_norm, scale_norm, pr_norm):
        graph_norm = 0.5 * sc_n + 0.5 * p_n
        final_score = sim_weight * s_n + (1.0 - sim_weight) * graph_norm
        fused_scores.append(final_score)

    reranked = []
    for hit, fs, s_n, sc_n, p_n in sorted(
        zip(hits, fused_scores, sim_norm, scale_norm, pr_norm),
        key=lambda x: -x[1]
    ):
        item = dict(hit)
        item["final_score"] = round(fs, 4)
        item["sim_norm"] = round(s_n, 4)
        item["scale_norm"] = round(sc_n, 4)
        item["pr_norm"] = round(p_n, 4)
        reranked.append(item)

    return reranked


def build_evidence_context(hits: List[Dict[str, Any]]) -> str:
    """하이브리드 검색 적중 결과로부터 DART 증거 원문 컨텍스트 생성"""
    if not hits:
        return "관련된 자본이벤트 공시 내역이 존재하지 않습니다."

    lines = []
    for idx, h in enumerate(hits, 1):
        rcept_no = h.get("rcept_no") or "미제공"
        viewer_url = h.get("viewer_url") or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        lines.append(
            f"[{idx}] {h.get('corp_name')} | {h.get('event_type')} (이사회결의일: {h.get('decided_on')})\n"
            f"  - 조달규모: {h.get('scale_amount', 0):,}원\n"
            f"  - 세부목적: {h.get('purpose_text')}\n"
            f"  - DART 접수번호: {rcept_no} (공시원문링크: {viewer_url})\n"
            f"  - 검색 매칭 점수: 종합 {h.get('final_score', 0):.4f} (유사도 {h.get('score', 0):.4f})"
        )
    return "\n\n".join(lines)


def generate_graphrag_response(
    question: str,
    corp_filter: Optional[str] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    [DART-Trace v1.0 핵심 진입점]
    질문 입력 -> 512차원 벡터 검색 -> MinMax 70:30 하이브리드 리랭킹 -> 4단 의사결정 리포트 생성
    """
    client = get_openai_client()

    # 1. 벡터 검색
    initial_hits = search_vector_only(question, top_k=top_k * 2, corp_filter=corp_filter)

    # 2. MinMax 70:30 하이브리드 리랭킹
    reranked_hits = search_hybrid_rerank(initial_hits, sim_weight=0.70)[:top_k]

    # 3. 근거 컨텍스트 조립
    evidence_context = build_evidence_context(reranked_hits)

    # 4. LLM 4단 응답 생성
    system_prompt = (
        "당신은 금융감독원 DART 기업공시 및 자본변동 데이터에 엄격히 근거하는 DART-Trace 수석 금융 공시 분석가입니다.\n"
        "반드시 제공된 [공시 원문 근거] 내용에만 엄격히 기초하여 답변하십시오.\n"
        "공시 원문에 없는 수치나 사실을 지어내는 환각(Hallucination)은 절대 금지됩니다.\n\n"
        "답변은 반드시 다음 4단 구조로 작성해야 합니다:\n\n"
        "1. [사실 (Fact)]:\n"
        "- 공시된 자본조달의 구체적 사실(기업명, 이벤트 유형, 조달 규모, 자금용도별 구체 액수, 이사회결의일 등)을 팩트 위주로 기술\n\n"
        "2. [해석 (Interpretation)]:\n"
        "- 자금조달 목적의 성격(예: 단순 운영자금 충당 vs 타법인 인수/시설투자를 통한 성장동력 확보), 주주가치 희석 우려 및 시나리오 분석\n\n"
        "3. [원문 근거 (Evidence)]:\n"
        "- 근거가 된 DART 접수번호, 기업명, 공시 원문 링크 명시\n\n"
        "4. [다음 확인 항목 (Next Action)]:\n"
        "- 투자자가 다음으로 반드시 점검해야 할 일정(청약일/납입일, 전환청구시작일, 후속 정기보고서 등) 및 리스크 체크포인트 2~3가지 제시"
    )

    user_prompt = (
        f"[질문]: {question}\n\n"
        f"[공시 원문 근거]:\n{evidence_context}\n\n"
        "위 공시 근거만을 바탕으로 질문에 대해 4단 의사결정 리포트 형식으로 명확히 답변해 주십시오."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    answer_text = completion.choices[0].message.content or ""

    # 4단 파싱
    fact_part = ""
    interp_part = ""
    evidence_part = ""
    next_action_part = ""

    fact_match = re.search(r"1\.\s*\[?사실.*?\]?:?(.*?)(?=2\.\s*\[?해석|$)", answer_text, re.DOTALL)
    interp_match = re.search(r"2\.\s*\[?해석.*?\]?:?(.*?)(?=3\.\s*\[?원문\s*근거|$)", answer_text, re.DOTALL)
    evid_match = re.search(r"3\.\s*\[?원문\s*근거.*?\]?:?(.*?)(?=4\.\s*\[?다음\s*확인|$)", answer_text, re.DOTALL)
    next_match = re.search(r"4\.\s*\[?다음\s*확인.*?\]?:?(.*)", answer_text, re.DOTALL)

    if fact_match:
        fact_part = fact_match.group(1).strip()
    if interp_match:
        interp_part = interp_match.group(1).strip()
    if evid_match:
        evidence_part = evid_match.group(1).strip()
    if next_match:
        next_action_part = next_match.group(1).strip()

    return {
        "question": question,
        "corp_filter": corp_filter,
        "hits": reranked_hits,
        "evidence_context": evidence_context,
        "full_answer": answer_text,
        "fact": fact_part or answer_text,
        "interpretation": interp_part,
        "evidence": evidence_part,
        "next_action": next_action_part
    }


if __name__ == "__main__":
    print("=" * 80)
    print("🔍 [GraphRAG Service 테스트] 타법인 인수 및 신규 사업 투자 질문")
    print("=" * 80)
    q = "타법인 증권 취득이나 인수를 위해 자금을 조달한 기업과 조달 목적을 알려줘"
    report = generate_graphrag_response(q, top_k=3)
    print(f"\n[Q]: {report['question']}")
    print(f"\n[하이브리드 검색 적중 상위 3건]:")
    for idx, h in enumerate(report["hits"], 1):
        print(f"  {idx}. {h['corp_name']} ({h['event_type']}) - 점수: {h['final_score']} (규모: {h['scale_amount']:,}원)")
    print("\n[AI 4단 응답 전문]:\n")
    print(report["full_answer"])
