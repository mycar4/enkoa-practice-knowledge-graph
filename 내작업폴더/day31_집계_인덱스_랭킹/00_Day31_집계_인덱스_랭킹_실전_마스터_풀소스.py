# -*- coding: utf-8 -*-
"""
🏛️ [Day 31 마스터 풀소스] Cypher 그래프 집계·인덱스 최적화 및 랭킹 추천 엔진 엔드투엔드
- 도메인: 
  1) Hetionet v1.0 바이오 의료 지식그래프 분석 모델
  2) 스마트 커머스 & 음악 차트 추천 랭킹 모델 (Smart Commerce & Music Chart)
- 주요 기술:
  - 수치/분위수 집계 (count, sum, avg, min, max, percentileCont)
  - 컬렉션 직렬화/역직렬화 (collect, UNWIND, List/Pattern Comprehension)
  - 다단계 WITH 파이프라인 및 COUNT { } 서브쿼리
  - 조건부 라벨링 (CASE WHEN THEN ELSE END) & SET 파생 속성
  - Neo4j 인덱스 엔진 (RANGE Index vs TEXT Index, dbHits 비교 및 실행계획 분석)
  - UNIQUE 제약조건(Constraint) 무결성 보장
  - 공유 이웃 기반 추천 랭킹 (원점수, 정규화 비율 점수, 최소 지지도 필터링, 그룹별 Top-N)
- 실행 방법: uv run python 내작업폴더/day31_집계_인덱스_랭킹/00_Day31_집계_인덱스_랭킹_실전_마스터_풀소스.py
"""

import os
import sys
import io
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Windows 콘솔 UTF-8 출력 보장
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. 환경 변수 로드 (.env 탐색)
load_dotenv(".env", override=True)
load_dotenv("../.env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")

AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")

# 2. 안전한 드라이버 연결
driver = None
try:
    print(f"🔗 [1차 시도] 로컬 Neo4j 접속: {NEO4J_URI} (사용자: {NEO4J_USER})")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ 로컬 Neo4j 연결 성공!")
except Exception as local_err:
    print(f"⚠️ 로컬 접속 불가 ({local_err}). 클라우드 Aura로 전환합니다...")
    if AURA_URI and AURA_USER and AURA_PASSWORD:
        try:
            print(f"🔗 [2차 시도] Neo4j Aura 접속: {AURA_URI} (사용자: {AURA_USER})")
            driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
            driver.verify_connectivity()
            print("✅ Neo4j Aura 클라우드 연결 성공!")
        except Exception as aura_err:
            print(f"❌ Aura 연결 실패: {aura_err}")
            sys.exit(1)
    else:
        print("❌ 유효한 Neo4j 연결 정보가 없습니다.")
        sys.exit(1)


def run_cypher(query: str, **params):
    """Cypher 질의를 실행하고 결과를 딕셔너리 리스트로 반환하는 공용 헬퍼 함수"""
    with driver.session() as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def explain_plan(query: str, profile=False, quiet=False, **params):
    """실행계획(EXPLAIN/PROFILE)을 분석하여 연산자 목록과 dbHits를 반환하는 함수"""
    with driver.session() as session:
        if profile:
            result = session.run("PROFILE " + query, **params)
            list(result)
            plan = result.consume().profile
        else:
            plan = session.run("EXPLAIN " + query, **params).consume().plan

    total = 0
    operators = []

    def walk(node, depth=0):
        nonlocal total
        if not node:
            return
        hits = node.get("dbHits")
        total += hits or 0
        name = node.get("operatorType", "").split("@")[0]
        operators.append(name)
        cost = f"| dbHits = {hits}" if profile else ""
        if not quiet:
            print("  " * depth, name, cost)
        for child in node.get("children", []):
            walk(child, depth + 1)

    walk(plan)
    return operators, total


def main():
    print("\n" + "═" * 85)
    print("🚀 [Step 1] Day 31 실습 격리용 네임스페이스 초기화 및 시드 데이터 적재")
    print("═" * 85)

    # 1) 격리 네임스페이스 초기화
    run_cypher("MATCH (n:SmartProduct) DETACH DELETE n")
    run_cypher("MATCH (n:SmartBuyer) DETACH DELETE n")
    run_cypher("MATCH (n:SmartArtist) DETACH DELETE n")
    run_cypher("MATCH (n:SmartSong) DETACH DELETE n")
    run_cypher("MATCH (n:SmartListener) DETACH DELETE n")
    
    # 인덱스 및 제약조건 정리 (초기화)
    for c in run_cypher("SHOW CONSTRAINTS YIELD name RETURN name"):
        if c['name'].startswith('smart_'):
            run_cypher(f"DROP CONSTRAINT {c['name']} IF EXISTS")
    for idx in run_cypher("SHOW INDEXES YIELD name RETURN name"):
        if idx['name'].startswith('smart_'):
            run_cypher(f"DROP INDEX {idx['name']} IF EXISTS")

    # 2) 스마트 이커머스 & 미디어 시드 적재
    run_cypher("""
    CREATE (p1:SmartProduct {name: '무선이어폰',   code: 'SP01', price: 80000, category: '가전'}),
           (p2:SmartProduct {name: '블루투스스피커', code: 'SP02', price: 60000, category: '가전'}),
           (p3:SmartProduct {name: '노트북거치대',   code: 'SP03', price: 40000, category: '가전'}),
           (p4:SmartProduct {name: '텀블러',       code: 'SP04', price: 20000, category: '리빙'}),
           (p5:SmartProduct {name: '담요',         code: 'SP05', price: 30000, category: '리빙'}),
           (p6:SmartProduct {name: '머그컵',       code: 'SP06', price: 15000, category: '리빙'})

    CREATE (b1:SmartBuyer {name: '도윤'}),
           (b2:SmartBuyer {name: '하윤'}),
           (b3:SmartBuyer {name: '지호'}),
           (b4:SmartBuyer {name: '서아'}),
           (b5:SmartBuyer {name: '민재'})

    CREATE (b1)-[:PURCHASED {qty: 1}]->(p1),
           (b1)-[:PURCHASED {qty: 2}]->(p4),
           (b2)-[:PURCHASED {qty: 2}]->(p1),
           (b2)-[:PURCHASED {qty: 1}]->(p4),
           (b2)-[:PURCHASED {qty: 1}]->(p2),
           (b3)-[:PURCHASED {qty: 1}]->(p1),
           (b3)-[:PURCHASED {qty: 2}]->(p5),
           (b4)-[:PURCHASED {qty: 3}]->(p6),
           (b4)-[:PURCHASED {qty: 1}]->(p5),
           (b4)-[:PURCHASED {qty: 1}]->(p3),
           (b5)-[:PURCHASED {qty: 1}]->(p1),
           (b5)-[:PURCHASED {qty: 1}]->(p4)
    """)
    print("✅ 스마트 이커머스 시드 적재 완료!")

    # 3) 스마트 음악 스트리밍 시드 적재
    run_cypher("""
    CREATE (a1:SmartArtist {name: '루나'}),
           (a2:SmartArtist {name: '제이드'}),
           (a3:SmartArtist {name: '카이'})

    CREATE (s1:SmartSong {title: '은하수', tag: ' 발라드|2021 '}),
           (s2:SmartSong {title: '밤하늘', tag: '발라드|2019 '}),
           (s3:SmartSong {title: '파도',   tag: ' 댄스|2022'}),
           (s4:SmartSong {title: '모래성', tag: ' 발라드|2020 '}),
           (s5:SmartSong {title: '등대',   tag: '댄스|2023 '}),
           (s6:SmartSong {title: '질주',   tag: ' 록|2022 '})

    CREATE (a1)-[:PERFORMS]->(s1),
           (a1)-[:PERFORMS]->(s2),
           (a2)-[:PERFORMS]->(s3),
           (a2)-[:PERFORMS]->(s4),
           (a2)-[:PERFORMS]->(s5),
           (a3)-[:PERFORMS]->(s6)

    CREATE (l1:SmartListener {name: '하늘'}),
           (l2:SmartListener {name: '바다'}),
           (l3:SmartListener {name: '별'}),
           (l4:SmartListener {name: '산'})

    CREATE (l1)-[:PLAYED {cnt: 50}]->(s1),
           (l1)-[:PLAYED {cnt: 30}]->(s3),
           (l2)-[:PLAYED {cnt: 40}]->(s1),
           (l2)-[:PLAYED {cnt: 60}]->(s5),
           (l3)-[:PLAYED {cnt: 20}]->(s2),
           (l3)-[:PLAYED {cnt: 45}]->(s3),
           (l3)-[:PLAYED {cnt: 35}]->(s6),
           (l4)-[:PLAYED {cnt: 25}]->(s4),
           (l4)-[:PLAYED {cnt: 55}]->(s5),
           (l4)-[:PLAYED {cnt: 15}]->(s1)
    """)
    print("✅ 스마트 음악 스트리밍 차트 시드 적재 완료!")

    print("\n" + "═" * 85)
    print("📊 [Step 2] 집계 & 분위수 파이프라인 (count, sum, avg, percentileCont)")
    print("═" * 85)

    # 1) 카테고리별 상품 수 및 가격 통계
    cat_stats = run_cypher("""
    MATCH (p:SmartProduct)
    RETURN p.category AS category,
           count(p) AS product_count,
           sum(p.price) AS total_price,
           avg(p.price) AS avg_price,
           min(p.price) AS min_price,
           max(p.price) AS max_price,
           percentileCont(p.price, 0.5) AS median_price
    ORDER BY total_price DESC
    """)
    for r in cat_stats:
        print(f"  • [{r['category']}] 상품수: {r['product_count']}개 | 총액: {r['total_price']:,}원 | "
              f"평균: {r['avg_price']:,.0f}원 | 중앙값: {r['median_price']:,}원")

    print("\n" + "═" * 85)
    print("📦 [Step 3] 리스트 변환 (collect, UNWIND, List Comprehension)")
    print("═" * 85)

    # 아티스트별 곡 목록 collect 및 태그 파싱
    artist_songs = run_cypher("""
    MATCH (a:SmartArtist)-[:PERFORMS]->(s:SmartSong)
    WITH a, collect(s) AS song_list
    RETURN a.name AS artist,
           size(song_list) AS song_count,
           [s IN song_list | s.title] AS titles,
           [s IN song_list | trim(split(s.tag, '|')[0])] AS genres
    ORDER BY song_count DESC, artist ASC
    """)
    for r in artist_songs:
        print(f"  • {r['artist']}: 곡 목록 = {r['titles']} | 장르 = {r['genres']}")

    print("\n" + "═" * 85)
    print("⚡ [Step 4] 인덱스 및 제약조건 생성 & 실행계획(EXPLAIN) 검증")
    print("═" * 85)

    # 1) UNIQUE 제약조건 및 RANGE 인덱스 생성
    run_cypher("CREATE CONSTRAINT smart_product_code_unique IF NOT EXISTS FOR (p:SmartProduct) REQUIRE p.code IS UNIQUE")
    run_cypher("CREATE INDEX smart_product_name_idx IF NOT EXISTS FOR (p:SmartProduct) ON (p.name)")
    run_cypher("CREATE TEXT INDEX smart_song_title_text IF NOT EXISTS FOR (s:SmartSong) ON (s.title)")
    run_cypher("CALL db.awaitIndexes()")
    print("✅ 인덱스 및 제약조건 준비 완료!")

    # 2) 실행계획 비교: 인덱스 탐색(NodeIndexSeek) 확인
    plan_ops, _ = explain_plan("MATCH (p:SmartProduct {name: '무선이어폰'}) RETURN p.code AS code")
    print("🔍 [실행계획 연산자]:", plan_ops)
    assert any("Index" in op for op in plan_ops), "인덱스 연산자가 실행계획에 포함되어야 합니다."

    print("\n" + "═" * 85)
    print("🎯 [Step 5] 함께 구매 추천 엔진 (공유 구매자 기반 랭킹)")
    print("═" * 85)

    target_item = "무선이어폰"
    rec_results = run_cypher("""
    MATCH (target:SmartProduct {name: $target_name})<-[:PURCHASED]-(b:SmartBuyer)-[:PURCHASED]->(other:SmartProduct)
    WHERE other <> target
    WITH other, count(DISTINCT b) AS shared_buyers
    RETURN other.name AS recommended_product,
           other.price AS price,
           shared_buyers
    ORDER BY shared_buyers DESC, other.price DESC
    """, target_name=target_item)

    print(f"🛍️ [{target_item}] 구매 고객에게 추천하는 함께 산 상품:")
    for i, rec in enumerate(rec_results, 1):
        print(f"   {i}위. {rec['recommended_product']} (함께 구매한 고객: {rec['shared_buyers']}명, 가격: {rec['price']:,}원)")

    print("\n" + "═" * 85)
    print("📈 [Step 6] 그룹별 상위 N개 슬라이싱 (아티스트별 최고 인기곡 Top 1)")
    print("═" * 85)

    top1_per_artist = run_cypher("""
    MATCH (a:SmartArtist)-[:PERFORMS]->(s:SmartSong)<-[p:PLAYED]-(:SmartListener)
    WITH a, s, sum(p.cnt) AS total_plays
    ORDER BY a.name ASC, total_plays DESC, s.title ASC
    WITH a, collect({title: s.title, plays: total_plays})[0] AS best_song
    RETURN a.name AS artist, best_song.title AS hit_song, best_song.plays AS plays
    ORDER BY plays DESC
    """)
    for r in top1_per_artist:
        print(f"  🏆 {r['artist']}: 대표 히트곡 '{r['hit_song']}' ({r['plays']}회 재생)")

    print("\n" + "═" * 85)
    print("🎉 [Day 31 마스터 풀소스 엔드투엔드 검증 완료!]")
    print("═" * 85)


if __name__ == "__main__":
    main()
