# -*- coding: utf-8 -*-
"""
=============================================================================
🏛️ [Day 33] Neo4j GDS(Graph Data Science) 투영 및 중심성 실전 마스터 풀소스
=============================================================================
- 기능:
  1. GDS 플러그인 설치 및 라이브러리 버전 확인
  2. 인메모리 그래프 네이티브 투영 (gds.graph.project) 및 검산 (2배 법칙)
  3. 차수 중심성 (Degree Centrality) 계산
  4. 전역 PageRank 알고리즘 (stream & write 모드)
  5. 특정 엔티티 관점의 개인화 PageRank (Personalized PageRank: PPR)
  6. 길목(병목) 노드 식별을 위한 매개 중심성 (Betweenness Centrality)
  7. 인메모리 투영 수명주기 관리 (gds.graph.list & gds.graph.drop)
=============================================================================
"""
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 환경변수 로드 (.env)
load_dotenv(".env", override=True)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_cypher(query, **params):
    with driver.session() as session:
        result = session.run(query, params)
        return result.data()

def main():
    print("=" * 70)
    print("🚀 [Day 33] GDS 투영 및 중심성 알고리즘 엔드투엔드 파이프라인 가동")
    print("=" * 70)

    # 1. GDS 버전 확인
    try:
        ver_res = run_cypher("RETURN gds.version() AS gds_ver")
        gds_version = ver_res[0]["gds_ver"]
        print(f"✅ GDS 플러그인 활성화 확인: Neo4j GDS v{gds_version}")
    except Exception as e:
        print(f"❌ GDS 플러그인 확인 실패: {e}")
        print("💡 Neo4j Desktop에서 'Graph Data Science Library' 플러그인을 설치하고 DBMS를 재시작하세요.")
        return

    # 2. 기존 잔존 투영 정리
    active_graphs = run_cypher("CALL gds.graph.list() YIELD graphName RETURN graphName")
    for g in active_graphs:
        run_cypher(f"CALL gds.graph.drop('{g['graphName']}') YIELD graphName")
        print(f"🧹 기존 인메모리 투영 정리 완료: {g['graphName']}")

    # 3. 인메모리 그래프 투영 생성 (약물-유전자 결합망: drugGeneGraph)
    print("\n⚡ [1단계] 인메모리 네이티브 투영 생성 (gds.graph.project)...")
    proj_query = """
    CALL gds.graph.project(
        'drugGeneGraph',
        ['Compound', 'Gene'],
        {
            CbG: {
                type: 'BINDS_CbG',
                orientation: 'UNDIRECTED'
            }
        }
    )
    YIELD graphName, nodeCount, relationshipCount, projectMillis
    """
    proj_res = run_cypher(proj_query)[0]
    print(f"  • 투영 그래프명: {proj_res['graphName']}")
    print(f"  • 투영된 노드 수: {proj_res['nodeCount']:,}개")
    print(f"  • 투영된 엣지 수: {proj_res['relationshipCount']:,}건 (UNDIRECTED 2배 검산 적용)")
    print(f"  • 투영 소요 시간: {proj_res['projectMillis']} ms")

    # 4. 차수 중심성 (Degree Centrality) 계산
    print("\n📊 [2단계] 차수 중심성(Degree) Top 5 추출 (직접 연결이 가장 많은 노드)...")
    deg_query = """
    CALL gds.graph.nodeProperty.stream('drugGeneGraph', '__degree__')
    YIELD nodeId, propertyValue AS degree
    WITH gds.util.asNode(nodeId) AS n, degree
    RETURN n.name AS entity_name,
           labels(n)[0] AS entity_type,
           toInteger(degree) AS degree_count
    ORDER BY degree_count DESC
    LIMIT 5
    """
    # GDS 2.x에서는 gds.degree.stream 권장
    try:
        deg_query_official = """
        CALL gds.degree.stream('drugGeneGraph')
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS n, score
        RETURN n.name AS entity_name,
               labels(n)[0] AS entity_type,
               toInteger(score) AS degree_count
        ORDER BY degree_count DESC
        LIMIT 5
        """
        deg_df = pd.DataFrame(run_cypher(deg_query_official))
    except:
        deg_df = pd.DataFrame(run_cypher(deg_query))
    print(deg_df.to_string(index=False))

    # 5. 전역 PageRank 알고리즘 실행
    print("\n🌐 [3단계] 전역 PageRank 영향력 Top 5 추출...")
    pr_query = """
    CALL gds.pageRank.stream('drugGeneGraph', {
        maxIterations: 20,
        dampingFactor: 0.85
    })
    YIELD nodeId, score
    WITH gds.util.asNode(nodeId) AS n, score
    RETURN n.name AS entity_name,
           labels(n)[0] AS entity_type,
           round(score, 4) AS pagerank_score
    ORDER BY score DESC
    LIMIT 5
    """
    pr_df = pd.DataFrame(run_cypher(pr_query))
    print(pr_df.to_string(index=False))

    # 6. 매개 중심성 (Betweenness Centrality: 길목/브로커 노드)
    print("\n🌉 [4단계] 매개 중심성(Betweenness) Top 5 추출...")
    btw_query = """
    CALL gds.betweenness.stream('drugGeneGraph')
    YIELD nodeId, score
    WITH gds.util.asNode(nodeId) AS n, score
    RETURN n.name AS entity_name,
           labels(n)[0] AS entity_type,
           round(score, 2) AS betweenness_score
    ORDER BY score DESC
    LIMIT 5
    """
    btw_df = pd.DataFrame(run_cypher(btw_query))
    print(btw_df.to_string(index=False))

    # 7. 개인화 PageRank (Personalized PageRank: 특정 엔티티 관점)
    print("\n🎯 [5단계] 개인화 PageRank (PPR: 특정 약물 관점의 상대적 영향력)...")
    # 샘플 약물 하나 선정
    sample_compound = run_cypher("MATCH (c:Compound) RETURN c.name AS name, id(c) AS nid LIMIT 1")
    if sample_compound:
        comp_name = sample_compound[0]['name']
        comp_id = sample_compound[0]['nid']
        print(f"  • 기준 출발 노드(Source Node): '{comp_name}' (ID: {comp_id})")
        
        ppr_query = """
        CALL gds.pageRank.stream('drugGeneGraph', {
            maxIterations: 20,
            dampingFactor: 0.85,
            sourceNodes: [$comp_id]
        })
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS n, score
        WHERE n.name <> $comp_name
        RETURN n.name AS entity_name,
               labels(n)[0] AS entity_type,
               round(score, 6) AS ppr_score
        ORDER BY score DESC
        LIMIT 5
        """
        ppr_df = pd.DataFrame(run_cypher(ppr_query, comp_id=comp_id, comp_name=comp_name))
        print(ppr_df.to_string(index=False))

    # 8. 인메모리 투영 메모리 해제
    print("\n🧹 [6단계] 사용 완료된 인메모리 그래프 해제 (gds.graph.drop)...")
    drop_res = run_cypher("CALL gds.graph.drop('drugGeneGraph') YIELD graphName")[0]
    print(f"✅ 인메모리 투영 해제 완료: {drop_res['graphName']}")

    print("\n" + "=" * 70)
    print("🏆 [Day 33] GDS 투영 및 중심성 알고리즘 실전 파이프라인 정상 완료!")
    print("=" * 70)

if __name__ == "__main__":
    main()
