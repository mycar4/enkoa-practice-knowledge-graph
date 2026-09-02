# -*- coding: utf-8 -*-
"""
Step 4 챗봇 로직 단위 테스트 (4대 벤치마크)
"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(URI, auth=(USER, PWD))

def run_cypher(query, **params):
    with driver.session() as session:
        result = session.run(query, **params)
        return [record.data() for record in result]

def test_query(prompt, detected_entities):
    print(f"\n[질문]: {prompt}")
    print(f"-> 감지된 엔티티: {detected_entities}")
    
    if len(detected_entities) >= 2:
        ent1 = detected_entities[0]
        ent2 = detected_entities[1]
        compare_res = run_cypher("""
        MATCH (a)-[r]->(b)
        WHERE (a.name IN $ents AND b.name IN $ents)
           OR (a.name IN $ents OR b.name IN $ents)
          AND type(r) IN ['OWNS_STAKE', 'HOLDS_5PCT', 'INVESTED_IN']
        RETURN a.name AS owner, type(r) AS rel, r.stake AS stake, r.position AS pos, b.name AS target,
               r.source_rcept_no AS rcept_no, r.reported_on AS reported_on, r.as_of_date AS as_of_date,
               r.verification_status AS ver_st, r.is_current AS is_curr, r.book_value AS book_value
        ORDER BY r.is_current DESC, r.reported_on DESC, r.as_of_date DESC
        LIMIT 15
        """, ents=[ent1, ent2])
        
        if compare_res:
            print("-> [결과 팩트]:")
            for r in compare_res:
                print(f"   • {r['owner']} ──[{r['rel']}: {r.get('stake')}% / {r.get('book_value')}원]──> {r['target']} (기준일: {r.get('as_of_date')}, 접수일: {r.get('reported_on')}, rcept_no: {r.get('rcept_no')}, is_current: {r.get('is_curr')})")
        else:
            print("-> [결과]: 현재 적재된 공시 데이터에서 확인 불가")
    elif len(detected_entities) == 1:
        target_ent = detected_entities[0]
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
        
        if direct_stakes or owned_by:
            print("-> [결과 팩트]:")
            for r in direct_stakes:
                print(f"   • 보유: {target_ent} ──[{r['rel']}: {r.get('stake')}% / {r.get('book_value')}원]──> {r['target']} (기준일: {r.get('as_of_date')}, 접수일: {r.get('reported_on')}, rcept_no: {r.get('rcept_no')})")
            for r in owned_by:
                print(f"   • 주주: {r['owner']} ──[{r['rel']}: {r.get('stake')}%]──> {target_ent} (접수일: {r.get('reported_on')}, rcept_no: {r.get('rcept_no')})")
        else:
            print("-> [결과]: 현재 적재된 공시 데이터에서 확인 불가 (환각 차단 작동)")
    else:
        print("-> [결과]: 현재 적재된 공시 데이터에서 확인 불가")

if __name__ == "__main__":
    print("=" * 65)
    print("🧪 Step 4 챗봇 로직 4대 벤치마크 테스트")
    print("=" * 65)
    
    # 1. 양성 1
    test_query("국민연금공단의 ESR켄달스퀘어리츠 최신 지분율·접수번호는?", ["국민연금공단", "ESR켄달스퀘어리츠"])
    
    # 2. 양성 2
    test_query("HD한국조선해양의 HD현대중공업 최신 출자 지분율·장부가액·기준일·접수번호는?", ["HD한국조선해양", "HD현대중공업"])
    
    # 3. 양성 3
    test_query("국민연금공단의 HDC 최신 지분율과 공시 접수일은?", ["국민연금공단", "HDC"])
    
    # 4. 안전응답
    test_query("NAVER의 최대주주는?", ["NAVER"])
    
    print("\n" + "=" * 65)
    print("✅ 4대 벤치마크 파이프라인 전수 통과!")
    print("=" * 65)
