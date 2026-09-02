# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    try:
        s.run("CALL gds.graph.drop('testGraph', false)")
    except Exception:
        pass
        
    res = s.run("""
    CALL gds.graph.project(
        'testGraph',
        ['DART_Company', 'DART_Person'],
        ['OWNS_STAKE']
    )
    YIELD graphName, nodeCount, relationshipCount
    RETURN graphName, nodeCount, relationshipCount
    """).single()
    print(f"✅ 기본 프로젝션 성공! 그래프: {res['graphName']}, 노드: {res['nodeCount']}, 관계: {res['relationshipCount']}")
    
    # PPR stream 테스트
    sample_res = s.run("""
    MATCH (source:DART_Company {corp_code: '00126380'})
    CALL gds.pageRank.stream('testGraph', {
        sourceNodes: [source],
        maxIterations: 20,
        dampingFactor: 0.85
    })
    YIELD nodeId, score
    RETURN gds.util.asNode(nodeId).name AS name, score
    ORDER BY score DESC
    LIMIT 5
    """).data()
    print("삼성전자 기준 PPR 상위 후보:")
    for r in sample_res:
        print(f"  • {r['name']}: {r['score']:.6f}")
    
    s.run("CALL gds.graph.drop('testGraph', false)")
