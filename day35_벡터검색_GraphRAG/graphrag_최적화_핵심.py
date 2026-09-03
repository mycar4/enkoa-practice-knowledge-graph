"""GraphRAG 최적화 핵심 코드 (35일차 교안_02 참고용).

벡터 검색만으로 부족한 자리를 그래프로 메우는 세 가지 도구를 한 파일에 모았다.
  1) 리랭킹    : 유사도 순위를 그래프 중심성(PageRank)으로 다시 세운다
  2) 커뮤니티 필터: 검색 범위를 한 갈래로 좁힌다
  3) 근거 조립  : 고른 논문의 본문과 개체를 이어 모델에 넘긴다

교안_02 를 한 번 끝까지 돌린 뒤(:Document 노드와 doc_vec 인덱스가 있는 상태에서) 실행한다.
    python graphrag_최적화_핵심.py
"""

import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from neo4j import GraphDatabase

load_dotenv(".env")

driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                              auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
embedder = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=768)
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

QUESTION = "약물 대사 유전자 검사를 처방 전에 하면 무엇이 달라지나요?"
GRAPH = "drugGraph"


def run_cypher(cypher, **params):
    return driver.execute_query(cypher, parameters_=params).records


# ── 0. 그래프 투영: 약물 중심의 사본을 메모리에 뜬다 ──────────────────────────
def project():
    """중심성과 커뮤니티를 잴 부분 그래프를 만든다. 무방향이라 관계가 두 배로 실린다."""
    run_cypher(f"CALL gds.graph.drop('{GRAPH}', false)")
    run_cypher(f"""CALL gds.graph.project('{GRAPH}',
                       ['Compound', 'Disease', 'PharmacologicClass'],
                       {{TREATS:       {{orientation: 'UNDIRECTED'}},
                         PALLIATES:    {{orientation: 'UNDIRECTED'}},
                         INCLUDES:     {{orientation: 'UNDIRECTED'}},
                         RESEMBLES_DD: {{orientation: 'UNDIRECTED'}},
                         RESEMBLES_CC: {{orientation: 'UNDIRECTED'}}}})""")


# ── 1. 검색: SEARCH 절로 뜻이 가까운 논문을 받는다 ───────────────────────────
def search_docs(question, top_k=5):
    """질문으로 논문을 찾아 pmcid·제목·유사도·그래프 점수를 함께 돌려준다.

    본문은 안 가져온다. 아래 리랭킹과 필터가 본문을 한 번도 안 읽기 때문이다.
    """
    return run_cypher("""MATCH (n:Document)
                           SEARCH n IN (VECTOR INDEX doc_vec FOR $q LIMIT $k) SCORE AS score
                         RETURN n.pmcid AS pmcid, n.title AS title, score,
                                n.graph_score AS graph_score
                         ORDER BY score DESC""",
                      q=embedder.embed_query(question), k=top_k)


# ── 2. 리랭킹: 개체의 PageRank 를 문서 점수로 옮겨 순위를 다시 세운다 ─────────
def write_graph_score():
    """개체에 PageRank 를 새기고, 논문이 언급한 개체들의 평균을 그 논문 점수로 삼는다."""
    run_cypher(f"CALL gds.pageRank.write('{GRAPH}', {{writeProperty: 'pagerank'}})")
    # 투영에 없는 개체(유전자·증상)는 pagerank 가 없어 분모에서 통째로 빠진다
    run_cypher("""MATCH (d:Document)-[:MENTIONS]->(e) WHERE e.pagerank IS NOT NULL
                  WITH d, avg(e.pagerank) AS mean SET d.graph_score = mean""")
    # 투영에 든 개체를 하나도 안 쓴 논문에는 바닥값을 준다(0 을 주면 외톨이보다 낮아진다)
    run_cypher("MATCH (d:Document) WHERE d.graph_score IS NULL SET d.graph_score = 0.15")


def minmax(values):
    """눈금이 다른 두 점수를 섞기 전에 0~1 로 눌러 맞춘다. 다 같으면 전부 1.0."""
    lo, hi = min(values), max(values)
    return [1.0] * len(values) if hi == lo else [(v - lo) / (hi - lo) for v in values]


def rerank(hits, weight):
    """유사도와 그래프 점수를 weight 비율로 섞어 다시 정렬한 pmcid 목록.

    weight 0 이면 유사도만, 1 이면 그래프 점수만. 값은 답을 읽어 가며 정한다.
    """
    similarity = minmax([hit["score"] for hit in hits])
    graph = minmax([hit["graph_score"] for hit in hits])
    fused = [(1 - weight) * s + weight * g for s, g in zip(similarity, graph)]
    return [hit["pmcid"] for hit, _ in sorted(zip(hits, fused), key=lambda pair: -pair[1])]


# ── 3. 커뮤니티 필터: 검색 범위를 기준 개체가 든 갈래로 좁힌다 ────────────────
def write_community():
    """관계 구조만 보고 개체를 묶는다. randomSeed 와 concurrency 를 고정해야 결과가 같다."""
    run_cypher(f"""CALL gds.leiden.write('{GRAPH}',
                       {{writeProperty: 'community', randomSeed: 42, concurrency: 1}})""")


def search_in_community(question, anchor_name, pool=20):
    """벡터 상위 pool 편 중 기준 개체와 같은 묶음의 개체를 언급한 논문만 남긴다.

    좁히기는 범위를 자르는 도구다. 질문이 그 갈래 안에 있을 때만 맞다.
    """
    # 묶음 번호 자체에는 뜻이 없다. 외우지 말고 그때그때 이름으로 읽어 온다
    community = run_cypher("MATCH (a {name: $name}) RETURN a.community AS c",
                           name=anchor_name)[0]["c"]
    rows = run_cypher("""MATCH (n:Document)
                           SEARCH n IN (VECTOR INDEX doc_vec FOR $q LIMIT $k) SCORE AS score
                         MATCH (n)-[:MENTIONS]->(e) WHERE e.community = $c
                         RETURN DISTINCT n.pmcid AS pmcid, score ORDER BY score DESC""",
                      q=embedder.embed_query(question), k=pool, c=community)
    return [row["pmcid"] for row in rows]


# ── 4. 근거 조립과 답: 고른 논문만 본문·개체와 함께 꺼내 모델에 넘긴다 ────────
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", "주어진 논문 발췌 안에서만 답하는 조수다. 발췌에 없는 내용은 지어내지 않는다."),
    ("human", "다음 논문 발췌를 근거로 질문에 한국어 세 문장 안으로 답하세요.\n"
              "각 문장 끝에 근거가 된 논문의 pmcid 를 대괄호로 다세요.\n\n"
              "[논문]\n{context}\n\n[질문] {question}"),
])
qa_chain = qa_prompt | model | StrOutputParser()


def build_context(pmcids):
    """논문 본문과 그 논문이 언급한 개체를 이어 근거 문단으로 만든다.

    검색은 pmcid 만 받고 본문은 여기서 한 번에 꺼낸다. 고른 것만 나르므로 짐이 가볍다.
    """
    # ORDER BY 없이 collect 하면 이름 순서가 안 정해져 같은 질문에 프롬프트가 달라진다
    rows = run_cypher("""MATCH (d:Document) WHERE d.pmcid IN $ids
                         OPTIONAL MATCH (d)-[:MENTIONS]->(e)
                         WITH d, e ORDER BY e.name
                         RETURN d.pmcid AS pmcid, d.title AS title, d.text AS text,
                                collect(DISTINCT e.name)[..8] AS entities""", ids=pmcids)
    by_id = {row["pmcid"]: row for row in rows}
    parts = []
    for pmcid in pmcids:            # 넘긴 순서 그대로 이어 붙인다
        row = by_id[pmcid]
        # 본문을 통째로 넣는다. 검색을 본문 전체로 했으니 근거도 전체라야 앞뒤가 맞는다
        parts.append(f"[{row['pmcid']}] {row['title']}\n"
                     f"  본문: {row['text']}\n"
                     f"  이 논문이 언급한 개체: {', '.join(row['entities'])}")
    return "\n\n".join(parts)


def ask(question, pmcids):
    """찾은 논문을 근거로 붙여 모델의 답을 돌려준다."""
    return qa_chain.invoke({"context": build_context(pmcids), "question": question})


# ── 세 도구를 나란히 놓고 무엇이 달라지는지 본다 ─────────────────────────────
if __name__ == "__main__":
    project()
    write_graph_score()
    write_community()

    hits = search_docs(QUESTION, top_k=5)
    print("벡터 검색만 :", [hit["pmcid"] for hit in hits][:3])
    print("리랭킹 w=0.3:", rerank(hits, 0.3)[:3])
    print("커뮤니티 좁히기:", search_in_community(QUESTION, "Clopidogrel"))

    plain = [hit["pmcid"] for hit in hits][:3]
    tuned = rerank(hits, 0.3)[:3]
    print("\n[벡터 검색만]\n" + ask(QUESTION, plain))
    print("\n[리랭킹 뒤]\n" + ask(QUESTION, tuned))

    run_cypher(f"CALL gds.graph.drop('{GRAPH}', false)")
    driver.close()
