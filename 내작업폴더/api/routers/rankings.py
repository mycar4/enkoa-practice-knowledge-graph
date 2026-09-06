# -*- coding: utf-8 -*-
"""
승격 지분 기반 지배 계열사 랭킹 + 실측 PageRank(networkx 클라이언트 연산).
이 파일에 명시된 대로, gds.pageRank 등 Neo4j GDS 클라우드 세션은 비용이
발생할 수 있어 호출하지 않는다 - HOLDS_ECONOMIC_STAKE 엣지 전량을 읽어와
networkx로 서버(API) 프로세스 내에서 직접 연산한다.
"""

from fastapi import APIRouter, Query
from neo4j import READ_ACCESS
import networkx as nx

from api.deps import get_driver

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


@router.get("/stake-count")
def stake_count_ranking(limit: int = Query(10, le=50)):
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.run("""
            MATCH (h:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(t:DART_Company)
            OPTIONAL MATCH (t)-[:HOLDS_ECONOMIC_STAKE]->(sub_t:DART_Company)
            WITH h,
                 count(DISTINCT t) AS direct_cnt,
                 count(DISTINCT sub_t) AS indirect_cnt,
                 round(sum(DISTINCT r.stake_ratio), 2) AS total_direct_stake,
                 collect(DISTINCT t.name) AS direct_companies
            RETURN h.name AS holder_name,
                   direct_cnt AS direct_count,
                   indirect_cnt AS indirect_count,
                   direct_cnt + indirect_cnt AS total_count,
                   total_direct_stake AS total_direct_stake,
                   direct_companies AS core_holdings
            ORDER BY total_count DESC, total_direct_stake DESC
            LIMIT $limit
        """, limit=limit).data()
    return {
        "ranking": rows,
        "methodology": "승격된 HOLDS_ECONOMIC_STAKE 관계 기준 직접+2단계 우회 지배 계열사 수 집계 (PageRank/Betweenness/Degree 알고리즘 미사용)",
    }


@router.get("/pagerank")
def pagerank_ranking(limit: int = Query(10, le=50)):
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        edges = session.run("""
            MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
            RETURN a.name AS src, b.name AS dst, r.stake_ratio AS w
        """).data()

    graph = nx.DiGraph()
    for e in edges:
        if not e.get("src") or not e.get("dst"):
            continue
        weight = float(e.get("w") or 0.0) + 0.01
        # 지배력 관점: "피보유회사 -> 보유회사" 방향으로 뒤집어서, 더 많은 계열사를 지배할수록 점수가 높아지도록 구성
        if graph.has_edge(e["dst"], e["src"]):
            graph[e["dst"]][e["src"]]["weight"] += weight
        else:
            graph.add_edge(e["dst"], e["src"], weight=weight)

    if graph.number_of_nodes() == 0:
        return {"ranking": [], "graph_nodes": 0, "graph_edges": 0, "methodology": "networkx PageRank (클라이언트 연산, Neo4j GDS 클라우드 세션 미사용)"}

    scores = nx.pagerank(graph, weight="weight")
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    return {
        "ranking": [{"rank": i, "corp_name": name, "pagerank_score": round(score, 5)} for i, (name, score) in enumerate(top, 1)],
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "methodology": "networkx PageRank (클라이언트 연산, 감쇠계수 0.85, 지분율 가중치, Neo4j GDS 클라우드 세션 미사용)",
    }
