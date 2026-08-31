import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv('.env', override=True)
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.getenv('NEO4J_PASSWORD')))

with driver.session() as s:
    q1 = s.run("""
    MATCH (c:DART_Company {name: 'NAVER'})-[:FILED]->(d:DART_Disclosure)
    RETURN count(d) AS total, count(CASE WHEN d.doc_status = 'CORRECTED' THEN 1 END) AS corrected
    """).single()
    print(f"Q1 실측값: NAVER 전체 {q1['total']}건 중 정정 {q1['corrected']}건")
    
    q2 = s.run("""
    MATCH (c:DART_Company)
    WHERE c.is_listed = true
    OPTIONAL MATCH (c)-[:FILED]->(d:DART_Disclosure)
    WITH c, count(d) AS disclosure_count
    RETURN
      count(*) AS 전체상장사,
      count(CASE WHEN disclosure_count > 0 THEN 1 END) AS 공시연결기업,
      count(CASE WHEN disclosure_count = 0 THEN 1 END) AS 미수집기업
    """).single()
    print(f"Q2 실측값: 전체상장사 {q2['전체상장사']}개사, 공시연결 {q2['공시연결기업']}개사, 미수집 {q2['미수집기업']}개사")
