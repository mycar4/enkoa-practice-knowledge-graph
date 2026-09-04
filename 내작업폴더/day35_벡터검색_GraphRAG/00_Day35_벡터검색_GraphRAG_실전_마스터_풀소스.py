#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ [Day 35] 벡터 검색과 GraphRAG 실전 마스터 통합 풀소스
================================================================================
본 스크립트는 Day 35의 전체 파이프라인을 원클릭으로 완벽하게 구동·검증하는 마스터 소스입니다.

[핵심 6단계 파이프라인]
  1. 환경 점검 및 Neo4j GDS / OpenAI 연결 (.env 기반 보안 로딩)
  2. Hetionet 의학 지식그래프(15,540 노드 / 91,966 관계) & PMC 논문 69편 적재
  3. text-embedding-3-large (768차원) 임베딩 속성 적재 & HNSW/Fulltext 인덱스 빌드
  4. 논문-개체 간 다리 놓기 (:MENTIONS 관계 자동 프로젝션)
  5. GDS drugGraph 무방향 투영 및 PageRank / Leiden 커뮤니티 산출
  6. 3대 검색 기법 실측 비교 & LangChain + GPT-4o-mini 근거 기반 엄밀 질의응답
================================================================================
"""

import os
import sys
import json
import gzip
import pickle
import time
import re
from pathlib import Path
from typing import List, Dict, Any

# Windows CP949 인코딩 방어
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# ── 1. 환경 설정 및 드라이버 연결 ─────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

# Day 35 전용 .env 우선 로딩 (로컬 7689 포트 기본)
env_path = SCRIPT_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7689")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")

# 🛡️ [클라우드 운영 DB 오염 방지 가드 - Aura Block Guard]
# 상위 루트 .env의 클라우드 Aura(databases.neo4j.io)가 상속되었을 경우 무조건 로컬 7689로 강제 치환
if "databases.neo4j.io" in NEO4J_URI:
    NEO4J_URI = "bolt://localhost:7689"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "test0011"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("❌ [환경 오류] OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    sys.exit(1)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
embedder = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=768)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

GRAPH_NAME = "drugGraph"
TEST_QUESTION = "약물 대사 유전자 검사를 처방 전에 하면 무엇이 달라지나요?"

NODE_LABELS = ["Compound", "Disease", "Gene", "Symptom", "PharmacologicClass"]
REL_ENDS = {
    "TREATS": ("Compound", "Disease"),
    "PALLIATES": ("Compound", "Disease"),
    "BINDS": ("Compound", "Gene"),
    "UPREGULATES_CG": ("Compound", "Gene"),
    "DOWNREGULATES_CG": ("Compound", "Gene"),
    "ASSOCIATES": ("Disease", "Gene"),
    "UPREGULATES_DG": ("Disease", "Gene"),
    "DOWNREGULATES_DG": ("Disease", "Gene"),
    "RESEMBLES_CC": ("Compound", "Compound"),
    "RESEMBLES_DD": ("Disease", "Disease"),
    "PRESENTS": ("Disease", "Symptom"),
    "INCLUDES": ("PharmacologicClass", "Compound"),
}


def run_cypher(query: str, **params) -> List[Dict[str, Any]]:
    """Cypher 쿼리를 실행하고 dict 리스트로 반환"""
    with driver.session() as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


# ── 2. 초기화 및 스키마/데이터 적재 ──────────────────────────────────────────
def step1_initialize_and_load_data():
    print("\n" + "="*80)
    print("🚀 [Step 1] 실습 전용 DB 초기화 및 의학 지식그래프(Hetionet) + 논문 69편 적재")
    print("="*80)

    # 1) GDS 남은 투영 내리기
    for g in run_cypher("CALL gds.graph.list() YIELD graphName RETURN graphName"):
        run_cypher("CALL gds.graph.drop($name) YIELD graphName RETURN graphName", name=g["graphName"])

    # 2) 노드와 관계 전체 정리
    run_cypher("MATCH (n) DETACH DELETE n")

    # 3) 기존 인덱스 전체 정리
    for ix in run_cypher("SHOW INDEXES YIELD name, type WHERE type IN ['VECTOR','FULLTEXT'] RETURN name"):
        run_cypher(f"DROP INDEX {ix['name']} IF EXISTS")
    print("  🧹 기존 그래프 노드, 관계 및 인덱스 초기화 완료")

    # 4) Hetionet PK 인덱스 생성
    for label in NODE_LABELS:
        run_cypher(f"CREATE INDEX {label.lower()}_id IF NOT EXISTS FOR (n:{label}) ON (n.id)")
    run_cypher("CREATE INDEX document_pmcid IF NOT EXISTS FOR (d:Document) ON (d.pmcid)")
    print("  🔑 [PK 인덱스] 5종 노드 및 Document PK 인덱스 생성 완료")

    # 5) Hetionet 노드 적재 (nodes.csv)
    nodes_csv = DATA_DIR / "hetionet_nodes.csv"
    df_nodes = pd.read_csv(nodes_csv)
    grouped_nodes = {label: [] for label in NODE_LABELS}
    for row in df_nodes.to_dict("records"):
        grouped_nodes[row["label"]].append({"id": row["id"], "name": row["name"]})

    for label, rows in grouped_nodes.items():
        query = f"UNWIND $rows AS row CREATE (n:{label}) SET n.id = row.id, n.name = row.name"
        run_cypher(query, rows=rows)
    print(f"  ✅ Hetionet 노드 적재 완료: 총 {len(df_nodes):,}개 노드")

    # 6) Hetionet 엣지 적재 (edges.csv)
    edges_csv = DATA_DIR / "hetionet_edges.csv"
    df_edges = pd.read_csv(edges_csv)
    grouped_edges = {rel: [] for rel in REL_ENDS}
    for row in df_edges.to_dict("records"):
        grouped_edges[row["rel"]].append({"s": row["source"], "t": row["target"]})

    for rel, rows in grouped_edges.items():
        src, dst = REL_ENDS[rel]
        chunk_size = 20000
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start:start + chunk_size]
            query = f"""
            UNWIND $chunk AS row
            MATCH (a:{src} {{id: row.s}}), (b:{dst} {{id: row.t}})
            CREATE (a)-[:{rel}]->(b)
            """
            run_cypher(query, chunk=chunk)
    print(f"  ✅ Hetionet 엣지 적재 완료: 총 {len(df_edges):,}개 관계")

    # 7) PMC 논문 69편 적재
    docs_jsonl = DATA_DIR / "pmc_docs.jsonl"
    emb_cache_file = DATA_DIR / "emb_cache.pkl"
    with open(emb_cache_file, "rb") as ef:
        emb_cache = pickle.load(ef)

    docs = []
    with open(docs_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            docs.append(json.loads(line))

    doc_batch = []
    for d in docs:
        pmcid = d["pmcid"]
        title = d["title"]
        text = d["text"]
        emb = emb_cache.get(text, None)
        if not emb:
            emb = embedder.embed_query(text)
            emb_cache[text] = emb
        doc_batch.append({
            "pmcid": pmcid,
            "title": title,
            "text": text,
            "emb": emb
        })

    with open(emb_cache_file, "wb") as ef:
        pickle.dump(emb_cache, ef)

    run_cypher("""
    UNWIND $batch AS row
    CREATE (d:Document {
        pmcid: row.pmcid,
        title: row.title,
        text: row.text,
        emb: row.emb
    })
    """, batch=doc_batch)
    print(f"  ✅ PMC 논문 적재 및 768차원 임베딩 결속 완료: 총 {len(doc_batch):,}편")


# ── 3. 인덱스 생성 및 개체 연결 ──────────────────────────────────────────────
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")


def find_entities(text: str, name2id: Dict[str, Any]) -> Dict[str, Any]:
    """문서에서 사전에 있는 이름을 찾아 {id: (레이블, 표준이름)}으로 반환"""
    entries, genes = name2id["entries"], name2id["genes"]
    ambiguous, brand_stopwords = name2id["ambiguous"], name2id["brand_stopwords"]
    found = {}
    for word in TOKEN_PATTERN.findall(text):
        if word in genes:
            found[genes[word]] = ("Gene", word)
            continue
        name = word.lower()
        if name not in entries or name in ambiguous:
            continue
        if name in brand_stopwords and word.islower():
            continue
        entry = entries[name]
        found[entry["id"]] = (entry["label"], entry["canonical"])
    return found


def step2_create_indexes_and_bridge():
    print("\n" + "="*80)
    print("⚡ [Step 2] HNSW 벡터 인덱스 + Fulltext 전문 인덱스 빌드 & :MENTIONS 연결 다리 구축")
    print("="*80)

    # 1) HNSW 벡터 인덱스
    run_cypher("""
    CREATE VECTOR INDEX doc_vec IF NOT EXISTS
    FOR (d:Document) ON (d.emb)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """)
    print("  ✅ [HNSW Vector Index] 'doc_vec' (768차원 / Cosine) 생성 완료")

    # 2) Fulltext 인덱스
    run_cypher("""
    CREATE FULLTEXT INDEX doc_ft IF NOT EXISTS
    FOR (d:Document) ON EACH [d.title, d.text]
    """)
    print("  ✅ [Lucene Fulltext Index] 'doc_ft' (title, text) 생성 완료")

    # 3) 논문-개체 연결 다리 놓기 (:MENTIONS)
    name2id_path = DATA_DIR / "name2id.json.gz"
    with gzip.open(name2id_path, "rt", encoding="utf-8") as f:
        name2id = json.load(f)

    doc_nodes = run_cypher("MATCH (d:Document) RETURN d.pmcid AS pmcid, d.title AS title, d.text AS text")
    links_by_label = {}
    for doc in doc_nodes:
        full_text = doc["title"] + " " + doc["text"]
        entities = find_entities(full_text, name2id)
        for entity_id, (label, canonical) in entities.items():
            links_by_label.setdefault(label, []).append({
                "pmcid": doc["pmcid"],
                "id": entity_id
            })

    for label, rows in links_by_label.items():
        query = f"""
        UNWIND $rows AS row
        MATCH (d:Document {{pmcid: row.pmcid}}), (e:{label} {{id: row.id}})
        MERGE (d)-[:MENTIONS]->(e)
        """
        run_cypher(query, rows=rows)

    cnt = run_cypher("MATCH (:Document)-[r:MENTIONS]->() RETURN count(r) AS c")[0]["c"]
    print(f"  ✅ [:MENTIONS] 관계 연결 완료: 총 {cnt:,}건 브릿지 확립")


# ── 4. GDS 투영 및 PageRank / Leiden 계산 ─────────────────────────────────────
def step3_run_gds_analytics():
    print("\n" + "="*80)
    print("🧠 [Step 3] GDS 무방향 서브그래프 투영 및 PageRank 중심성 & Leiden 커뮤니티 산출")
    print("="*80)

    try:
        run_cypher(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
    except Exception:
        pass

    res = run_cypher(f"""
    CALL gds.graph.project(
        '{GRAPH_NAME}',
        ['Compound', 'Disease', 'PharmacologicClass'],
        {{
            TREATS:       {{orientation: 'UNDIRECTED'}},
            PALLIATES:    {{orientation: 'UNDIRECTED'}},
            INCLUDES:     {{orientation: 'UNDIRECTED'}},
            RESEMBLES_DD: {{orientation: 'UNDIRECTED'}},
            RESEMBLES_CC: {{orientation: 'UNDIRECTED'}}
        }}
    )
    YIELD nodeCount, relationshipCount
    RETURN nodeCount, relationshipCount
    """)
    print(f"  ✅ [GDS Projection] '{GRAPH_NAME}' 생성 (노드: {res[0]['nodeCount']:,}개, 무방향 관계: {res[0]['relationshipCount']:,}개)")

    # PageRank
    run_cypher(f"CALL gds.pageRank.write('{GRAPH_NAME}', {{writeProperty: 'pagerank'}})")
    run_cypher("""
    MATCH (d:Document)-[:MENTIONS]->(e)
    WHERE e.pagerank IS NOT NULL
    WITH d, avg(e.pagerank) AS mean
    SET d.graph_score = mean
    """)
    run_cypher("MATCH (d:Document) WHERE d.graph_score IS NULL SET d.graph_score = 0.15")
    print("  ✅ [PageRank] 개체 중심성 계산 ➔ 논문 :Document.graph_score 평균 전이 완료")

    # Leiden
    run_cypher(f"""
    CALL gds.leiden.write(
        '{GRAPH_NAME}',
        {{writeProperty: 'community', randomSeed: 42, concurrency: 1}}
    )
    """)
    comm_stats = run_cypher("""
    MATCH (e) WHERE e.community IS NOT NULL
    RETURN count(DISTINCT e.community) AS num_communities, count(e) AS assigned_nodes
    """)
    print(f"  ✅ [Leiden 커뮤니티] 분할 완료: {comm_stats[0]['num_communities']:,}개 커뮤니티 클러스터 형성")


# ── 5. 검색 및 리랭킹 함수 정의 ──────────────────────────────────────────────
def search_vector_only(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """SEARCH 절을 활용한 순수 벡터 유사도 검색"""
    q_vec = embedder.embed_query(question)
    return run_cypher("""
    MATCH (n:Document)
    SEARCH n IN (VECTOR INDEX doc_vec FOR $q LIMIT $k) SCORE AS score
    RETURN n.pmcid AS pmcid, n.title AS title, score, n.graph_score AS graph_score
    ORDER BY score DESC
    """, q=q_vec, k=top_k)


def minmax_scale(values: List[float]) -> List[float]:
    """0~1 Min-Max 정규화"""
    lo, hi = min(values), max(values)
    return [1.0] * len(values) if hi == lo else [(v - lo) / (hi - lo) for v in values]


def search_with_pagerank_rerank(hits: List[Dict[str, Any]], weight: float = 0.3) -> List[Dict[str, Any]]:
    """벡터 유사도와 PageRank 그래프 점수를 융합한 하이브리드 리랭킹"""
    sim_norm = minmax_scale([h["score"] for h in hits])
    graph_norm = minmax_scale([h["graph_score"] for h in hits])
    fused_scores = [(1.0 - weight) * s + weight * g for s, g in zip(sim_norm, graph_norm)]

    reranked = []
    for hit, fs in sorted(zip(hits, fused_scores), key=lambda pair: -pair[1]):
        item = dict(hit)
        item["fused_score"] = fs
        reranked.append(item)
    return reranked


def search_leiden_community_scoped(question: str, anchor_name: str, pool: int = 20) -> List[str]:
    """기준 개체가 속한 Leiden 커뮤니티 개체를 언급한 논문으로 한정하는 문맥 좁히기"""
    comm_records = run_cypher("MATCH (a {name: $name}) RETURN a.community AS c", name=anchor_name)
    if not comm_records or comm_records[0]["c"] is None:
        return []
    target_comm = comm_records[0]["c"]

    q_vec = embedder.embed_query(question)
    rows = run_cypher("""
    MATCH (n:Document)
    SEARCH n IN (VECTOR INDEX doc_vec FOR $q LIMIT $k) SCORE AS score
    MATCH (n)-[:MENTIONS]->(e)
    WHERE e.community = $c
    RETURN DISTINCT n.pmcid AS pmcid, score
    ORDER BY score DESC
    """, q=q_vec, k=pool, c=target_comm)
    return [r["pmcid"] for r in rows]


# ── 6. 근거 조립(Context Builder) 및 LLM 질의응답 ─────────────────────────────
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 의학 및 바이오 지식그래프 기반 전문 연구 보조 AI입니다.\n"
               "반드시 주어진 [논문 발췌] 내용에만 엄격히 근거하여 답변하세요.\n"
               "발췌문에 명시되지 않은 사실은 절대 지어내지 마세요 (환각 엄금).\n"
               "답변의 각 문장 끝에는 반드시 근거가 된 논문의 [PMCxxxxxxx] 식별자를 명시하세요."),
    ("human", "다음 논문 발췌를 근거로 질문에 한국어 세 문장 이내로 답변하세요.\n\n"
              "[논문 발췌문]\n{context}\n\n"
              "[질문]: {question}")
])
qa_chain = qa_prompt | llm | StrOutputParser()


def build_evidence_context(pmcids: List[str]) -> str:
    """선별된 논문 본문 및 언급 개체 명단을 결합하여 컴팩트한 근거 문단 구축"""
    rows = run_cypher("""
    MATCH (d:Document) WHERE d.pmcid IN $ids
    OPTIONAL MATCH (d)-[:MENTIONS]->(e)
    WITH d, e ORDER BY e.name
    RETURN d.pmcid AS pmcid, d.title AS title, d.text AS text,
           collect(DISTINCT e.name)[..6] AS entities
    """, ids=pmcids)
    by_id = {r["pmcid"]: r for r in rows}

    context_parts = []
    for pid in pmcids:
        if pid in by_id:
            r = by_id[pid]
            context_parts.append(
                f"[{r['pmcid']}] {r['title']}\n"
                f"  - 본문 발췌: {r['text'][:400]}...\n"
                f"  - 논문 언급 개체: {', '.join(r['entities'])}"
            )
    return "\n\n".join(context_parts)


def run_qa_evaluation(question: str, pmcids: List[str]) -> str:
    """근거 기반 LLM 질의응답 실행"""
    ctx = build_evidence_context(pmcids)
    return qa_chain.invoke({"context": ctx, "question": question})


# ── 7. 메인 실행 진입점 ───────────────────────────────────────────────────────
def main():
    print("\n" + "="*80)
    print("🏛️ [Day 35] 벡터 검색과 GraphRAG 실전 마스터 통합 파이프라인 가동")
    print("="*80)

    start_t = time.time()

    # 1~3단계: 적재, 인덱싱, GDS 연산
    step1_initialize_and_load_data()
    step2_create_indexes_and_bridge()
    step3_run_gds_analytics()

    # 4단계: 3대 검색 비교 실측
    print("\n" + "="*80)
    print(f"🎯 [Step 4] 3대 검색 기법 실측 비교 대조군 실험 (질문: '{TEST_QUESTION}')")
    print("="*80)

    # 1) 순수 벡터 검색
    vec_hits = search_vector_only(TEST_QUESTION, top_k=5)
    print("\n[기법 1: 순수 벡터 검색 (Top 3)]")
    for idx, h in enumerate(vec_hits[:3], 1):
        print(f"  {idx}. [{h['pmcid']}] score: {h['score']:.4f} | graph_score: {h['graph_score']:.4f} | {h['title'][:50]}...")

    # 2) PageRank 하이브리드 리랭킹 (w=0.3)
    rerank_hits = search_with_pagerank_rerank(vec_hits, weight=0.3)
    print("\n[기법 2: PageRank 하이브리드 리랭킹 (w=0.3, Top 3)]")
    for idx, h in enumerate(rerank_hits[:3], 1):
        print(f"  {idx}. [{h['pmcid']}] fused_score: {h['fused_score']:.4f} | orig_sim: {h['score']:.4f} | {h['title'][:50]}...")

    # 3) Leiden 커뮤니티 스코핑 (기준 약물: Clopidogrel)
    scoped_pmcids = search_leiden_community_scoped(TEST_QUESTION, anchor_name="Clopidogrel", pool=20)
    print(f"\n[기법 3: Leiden 커뮤니티 필터링 (기준약물: Clopidogrel, 필터링 결과 {len(scoped_pmcids)}편)]")
    print(f"  - 추출된 논문: {scoped_pmcids[:5]}")

    # 5단계: LLM 질의응답 및 근거 인용(Citation) 검증
    print("\n" + "="*80)
    print("🤖 [Step 5] LangChain + GPT-4o-mini 근거 기반 질의응답 비교")
    print("="*80)

    plain_pmcids = [h["pmcid"] for h in vec_hits[:3]]
    tuned_pmcids = [h["pmcid"] for h in rerank_hits[:3]]

    print("\n📝 [A. 순수 벡터 검색 근거 답변]")
    ans_plain = run_qa_evaluation(TEST_QUESTION, plain_pmcids)
    print(ans_plain)

    print("\n✨ [B. PageRank 리랭킹 하이브리드 근거 답변]")
    ans_tuned = run_qa_evaluation(TEST_QUESTION, tuned_pmcids)
    print(ans_tuned)

    # 정리
    try:
        run_cypher(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
    except Exception:
        pass
    driver.close()

    elapsed = time.time() - start_t
    print("\n" + "="*80)
    print(f"🏆 [Day 35 GraphRAG 통합 파이프라인 100% 성공 완료] 총 소요시간: {elapsed:.2f}초")
    print("="*80)


if __name__ == "__main__":
    main()
