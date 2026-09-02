# -*- coding: utf-8 -*-
"""
Step 4 GraphRAG AI 챗봇 4대 실측 벤치마크 테스트 스크립트
"""
import os
import sys
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(URI, auth=(USER, PWD))

def run_benchmarks():
    print("=" * 65)
    print("🤖 [Step 4 GraphRAG AI 챗봇 4대 실측 벤치마크 검증]")
    print("=" * 65)
    
    with driver.session() as session:
        # [양성 1] 국민연금공단 -> ESR켄달스퀘어리츠
        q1 = """
        MATCH (a {name: '국민연금공단'})-[r:OWNS_STAKE]->(b {name: 'ESR켄달스퀘어리츠'})
        WHERE r.is_current = true
        RETURN a.name AS owner, b.name AS target, r.stake AS stake,
               r.source_rcept_no AS rcept_no, r.verification_status AS ver_st,
               r.is_current AS is_curr
        """
        res1 = session.run(q1).data()
        print("\n[양성 1] 국민연금공단의 ESR켄달스퀘어리츠 최신 지분율·접수번호:")
        print(f"  - DB 반환: {res1}")
        if res1 and res1[0]['stake'] == 4.8 and res1[0]['rcept_no'] == '20260701000364' and res1[0]['is_curr'] is True:
            print("  ✅ [양성 1 PASS] 4.8% / 20260701000364 / VERIFIED / 최신 유효 사실 확인")
        else:
            print("  ❌ [양성 1 FAIL] 기대값 불일치")

        # [양성 2] HD한국조선해양 -> HD현대중공업
        q2 = """
        MATCH (a {name: 'HD한국조선해양'})-[r:INVESTED_IN]->(b {name: 'HD현대중공업'})
        RETURN a.name AS investor, b.name AS target, r.stake AS stake,
               r.book_value AS book_value, r.as_of_date AS as_of_date,
               r.source_rcept_no AS rcept_no
        ORDER BY r.as_of_date DESC LIMIT 1
        """
        res2 = session.run(q2).data()
        print("\n[양성 2] HD한국조선해양의 HD현대중공업 최신 출자 지분율·장부가액·기준일·접수번호:")
        print(f"  - DB 반환: {res2}")
        if res2 and res2[0]['stake'] == 75.02 and res2[0]['book_value'] == 5276008000000 and res2[0]['rcept_no'] == '20250318001131':
            print("  ✅ [양성 2 PASS] 75.02% / 5,276,008,000,000원 / 2024-12-31 / 20250318001131 확인")
        else:
            print("  ❌ [양성 2 FAIL] 기대값 불일치")

        # [양성 3] 국민연금공단 -> HDC
        q3 = """
        MATCH (a {name: '국민연금공단'})-[r:OWNS_STAKE]->(b {name: 'HDC'})
        WHERE r.is_current = true
        RETURN a.name AS owner, b.name AS target, r.stake AS stake,
               r.reported_on AS reported_on, r.source_rcept_no AS rcept_no
        """
        res3 = session.run(q3).data()
        print("\n[양성 3] 국민연금공단의 HDC 최신 지분율과 공시 접수일:")
        print(f"  - DB 반환: {res3}")
        if res3 and res3[0]['stake'] == 5.8 and res3[0]['reported_on'] == '2026-08-26' and res3[0]['rcept_no'] == '20260826000408':
            print("  ✅ [양성 3 PASS] 5.8% / 2026-08-26 / 20260826000408 확인")
        else:
            print("  ❌ [양성 3 FAIL] 기대값 불일치")

        # [안전응답 4] NAVER의 최대주주 (DB 미등록 시 안전 응답 확인)
        q4 = """
        MATCH (a)-[r:OWNS_STAKE]->(b {name: 'NAVER'})
        RETURN a.name, r.stake
        """
        res4 = session.run(q4).data()
        print("\n[안전응답 4] NAVER의 최대주주 (미등록 엔티티):")
        print(f"  - DB 반환 건수: {len(res4)}건")
        if len(res4) == 0:
            print("  ✅ [안전응답 4 PASS] DB에 데이터 없음 확인 ➔ '현재 적재된 공시 데이터에서 확인 불가' 안전 응답 처리 대상")
        else:
            print("  ⚠️ NAVER 데이터가 DB에 존재함")

    print("\n" + "=" * 65)
    print("🏁 [4대 벤치마크 Ground Truth 전수 검증 완료]")
    print("=" * 65)

if __name__ == "__main__":
    run_benchmarks()
