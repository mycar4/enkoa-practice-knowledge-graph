# -*- coding: utf-8 -*-
"""
🏛️ [Day 30 마스터 풀소스] Cypher 심화 다차원 경로 탐색 & WITH 파이프라인 엔드투엔드
- 도메인: 
  1) 스마트 광역 물류 허브 & 배송 네트워크 (Smart Logistics Graph)
  2) 프리미엄 캠핑 & 다이닝 서비스 지식 그래프 (Smart Dining & Spot Graph)
- 주요 기술:
  - 가변 길이 경로 순회 (*1..2, *0..3) & 0-Hop 계층 분석
  - 최단 경로 엔진 (shortestPath, allShortestPaths) & 총 소요시간/거리 동적 산출
  - 경로 해부 (nodes, relationships, length, 리스트 컴프리헨션)
  - 고계 리스트 술어 (all, any, none, single)
  - 정밀 문자열/정규식/리스트 $params 파라미터화 바인딩
  - 패턴 존재/부재 술어 (WHERE (a)-[:REL]->(b), NOT, EXISTS { })
  - OPTIONAL MATCH (외부조인) & WITH 스코프 격리 & NULL 처리
  - WITH 다단계 파이프라인 (파생 비용 계산, 중간 집계 및 상위 N개 슬라이싱)
  - 결정적 페이징 (ORDER BY 1차, 2차 보조키 + SKIP + LIMIT)
  - 실무 비즈니스 엔진: smart_logistics_router() & intelligent_spot_recommender()
- 실행 방법: uv run python 내작업폴더/day30_Cypher_심화/00_Day30_Cypher_심화_실전_마스터_풀소스.py
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

# 2. 안전한 드라이버 연결 (로컬 우선 -> 연결 실패 시 클라우드 Aura 자동 전환)
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


def main():
    print("\n" + "═" * 85)
    print("🚀 [Step 1] 실습 격리용 네임스페이스 초기화 및 시드 데이터 적재")
    print("═" * 85)

    # 이전 실습 노드 격리 삭제
    run_cypher("MATCH (n:SmartHub) DETACH DELETE n")
    run_cypher("MATCH (n:SmartCity) DETACH DELETE n")
    run_cypher("MATCH (n:SmartSpot) DETACH DELETE n")
    run_cypher("MATCH (n:SmartManager) DETACH DELETE n")
    run_cypher("MATCH (n:SmartUser) DETACH DELETE n")
    print("🧹 'Smart' 네임스페이스 격리 초기화 완료!")

    # 1) 스마트 물류 허브 & 배송 네트워크 적재
    run_cypher("""
    CREATE (h1:SmartHub {name: '인천메가허브', hub_id: 'H01', capacity: 50000}),
           (h2:SmartHub {name: '군포허브',     hub_id: 'H02', capacity: 30000}),
           (h3:SmartHub {name: '대전허브',     hub_id: 'H03', capacity: 40000}),
           (h4:SmartHub {name: '대구허브',     hub_id: 'H04', capacity: 25000}),
           (c1:SmartCity {name: '서울강남',   city_id: 'C01', zone: '수도권'}),
           (c2:SmartCity {name: '수원',       city_id: 'C02', zone: '경기남부'}),
           (c3:SmartCity {name: '천안',       city_id: 'C03', zone: '충청권'}),
           (c4:SmartCity {name: '부산',       city_id: 'C04', zone: '영남권'}),
           (c5:SmartCity {name: '제주',       city_id: 'C05', zone: '도서산간'})

    // 육상 간선 노선 (TRUCK) & 항공/특송 노선 (AIR)
    CREATE (h1)-[:TRUCK_ROUTE {time: 45,  cost: 15000, distance_km: 35}]->(c1),
           (h1)-[:TRUCK_ROUTE {time: 50,  cost: 18000, distance_km: 42}]->(h2),
           (h2)-[:TRUCK_ROUTE {time: 30,  cost: 12000, distance_km: 25}]->(c2),
           (h2)-[:TRUCK_ROUTE {time: 80,  cost: 25000, distance_km: 85}]->(h3),
           (h3)-[:TRUCK_ROUTE {time: 40,  cost: 14000, distance_km: 38}]->(c3),
           (h3)-[:TRUCK_ROUTE {time: 90,  cost: 30000, distance_km: 120}]->(h4),
           (h4)-[:TRUCK_ROUTE {time: 60,  cost: 20000, distance_km: 75}]->(c4),
           (h1)-[:AIR_ROUTE   {time: 120, cost: 80000, distance_km: 450}]->(c5),
           (h1)-[:AIR_ROUTE   {time: 60,  cost: 50000, distance_km: 380}]->(c4)
    """)

    # 2) 스마트 캠핑 & 다이닝 스팟 적재
    run_cypher("""
    CREATE (s1:SmartSpot {name: '포레스트 글램핑', category: '글램핑', area: '가평', price: 180000, rating: 4.8}),
           (s2:SmartSpot {name: '별빛 오토캠핑장', category: '오토캠핑', area: '가평', price: 60000,  rating: 4.5}),
           (s3:SmartSpot {name: '오션뷰 카라반',   category: '카라반', area: '강릉', price: 150000, rating: 4.9}),
           (s4:SmartSpot {name: '마운틴 힐링파크', category: '오토캠핑', area: '평창', price: 50000,  rating: 4.2}),
           (s5:SmartSpot {name: '도심속 루프탑가든', category: '글램핑', area: '서울', price: 220000, rating: 4.6}),
           (m1:SmartManager {name: '김총괄', phone: '010-1111-2222', grade: 'Master'}),
           (m2:SmartManager {name: '이관리', phone: '010-3333-4444', grade: 'Senior'})

    CREATE (s1)-[:MANAGED_BY]->(m1),
           (s2)-[:MANAGED_BY]->(m1),
           (s3)-[:MANAGED_BY]->(m2)
           // s4, s5는 관리자가 없는 상태 (OPTIONAL MATCH 실습용)
    """)
    print("📦 [시드 완료] 허브/도시 9개 + 스팟/관리자 7개 노드 적재 완료!")

    print("\n" + "═" * 85)
    print("🔍 [Step 2] 가변 길이 경로 순회 (*1..2, *0..3) & 0-Hop 분석")
    print("═" * 85)

    # 1) 인천메가허브에서 1~2단계 안에 도달 가능한 도시/허브
    rows_v1 = run_cypher("""
    MATCH (start:SmartHub {name: '인천메가허브'})-[:TRUCK_ROUTE*1..2]->(dest)
    RETURN DISTINCT dest.name AS destination, labels(dest)[0] AS type
    ORDER BY type, destination
    """)
    print("▶ 인천메가허브 출발 1~2 Hop 도달 가능 지점:")
    for r in rows_v1:
        print(f"   • [{r['type']}] {r['destination']}")

    # 2) 0-Hop(*0..2) 포함 시 자기 자신 노드가 포함되는 동작 원리
    rows_v0 = run_cypher("""
    MATCH (start:SmartHub {name: '군포허브'})-[:TRUCK_ROUTE*0..1]->(dest)
    RETURN dest.name AS target
    ORDER BY target
    """)
    print("\n▶ 군포허브 0~1 Hop 탐색 (0-Hop 자기 자신 포함):", [r['target'] for r in rows_v0])

    print("\n" + "═" * 85)
    print("🧭 [Step 3] shortestPath & allShortestPaths 기반 최단 경로 및 속성 합산")
    print("═" * 85)

    # 인천메가허브 -> 부산 최단 경로 (육상 vs 항공)
    shortest_res = run_cypher("""
    MATCH p = shortestPath((start:SmartHub {name: '인천메가허브'})-[:TRUCK_ROUTE|AIR_ROUTE*]-(end:SmartCity {name: '부산'}))
    RETURN [n IN nodes(p) | n.name] AS path_nodes,
           [r IN relationships(p) | type(r)] AS route_types,
           length(p) AS hop_count
    """)
    print("▶ 인천메가허브 → 부산 홉 수 기준 최단 경로:")
    if shortest_res:
        row = shortest_res[0]
        print(f"   • 최단 홉 수: {row['hop_count']} Hop")
        print(f"   • 경유 노드: {' ──> '.join(row['path_nodes'])}")
        print(f"   • 이용 노선: {row['route_types']}")

    # 전 구간 거리(km) 및 총 소요시간(분) 합산 계산
    route_calc = run_cypher("""
    MATCH p = (start:SmartHub {name: '인천메가허브'})-[:TRUCK_ROUTE*]->(end:SmartCity {name: '부산'})
    RETURN [n IN nodes(p) | n.name] AS path_nodes,
           reduce(total_time = 0, r IN relationships(p) | total_time + r.time) AS total_time_min,
           reduce(total_dist = 0, r IN relationships(p) | total_dist + r.distance_km) AS total_distance_km
    ORDER BY total_time_min ASC
    """)
    print("\n▶ 육상 배송 경로별 소요시간 & 거리 분석:")
    for r in route_calc:
        print(f"   • 경로: {' → '.join(r['path_nodes'])}")
        print(f"     소요시간: {r['total_time_min']}분, 총거리: {r['total_distance_km']}km")

    print("\n" + "═" * 85)
    print("🔬 [Step 4] 경로 해부 (nodes, relationships) & 고계 리스트 술어 (all, any, none)")
    print("═" * 85)

    # 1) all(): 모든 구간이 60분 이하로 쾌속인 경로
    # 2) any(): 항공 노선(AIR_ROUTE)이 포함된 경로
    # 3) none(): 소요시간이 100분 이상인 악성 지연 구간이 없는 경로
    list_predicate_res = run_cypher("""
    MATCH p = (start:SmartHub {name: '인천메가허브'})-[*1..4]->(dest:SmartCity)
    RETURN dest.name AS destination,
           [n IN nodes(p) | n.name] AS route_nodes,
           all(r IN relationships(p) WHERE r.time <= 60) AS is_all_fast,
           any(r IN relationships(p) WHERE type(r) = 'AIR_ROUTE') AS has_air_route,
           none(r IN relationships(p) WHERE r.time >= 100) AS no_heavy_delay
    ORDER BY destination
    """)
    print("▶ 경로 품질 평가 리포트 (all / any / none 술어):")
    for r in list_predicate_res:
        flags = []
        if r['is_all_fast']: flags.append("⚡전구간고속")
        if r['has_air_route']: flags.append("✈️항공포함")
        if r['no_heavy_delay']: flags.append("🛡️지연없음")
        print(f"   • 목적지: {r['destination']:<6} | {' → '.join(r['route_nodes']):<40} | {' / '.join(flags)}")

    print("\n" + "═" * 85)
    print("🎯 [Step 5] 정밀 조건 필터링 & 파라미터화 바인딩 ($params)")
    print("═" * 85)

    # 문자열 정규식 + 목록 파라미터 바인딩 ($areas, $keyword)
    param_query = """
    MATCH (s:SmartSpot)
    WHERE s.area IN $target_areas 
      AND s.name =~ $regex_pattern
      AND s.price <= $max_price
    RETURN s.name AS name, s.category AS category, s.area AS area, s.price AS price, s.rating AS rating
    ORDER BY s.rating DESC
    """
    param_res = run_cypher(
        param_query, 
        target_areas=['가평', '강릉'], 
        regex_pattern='(?i).*글램핑|오토.*', 
        max_price=200000
    )
    print("▶ $params 바인딩 검색 결과 (가평/강릉 + 글램핑/오토 + 20만원 이하):")
    for r in param_res:
        print(f"   • [{r['category']}] {r['name']} ({r['area']}) - {r['price']:,}원 | ⭐ {r['rating']}")

    print("\n" + "═" * 85)
    print("🔍 [Step 6] 패턴 술어 (Pattern Predicate) & EXISTS { } 서브쿼리")
    print("═" * 85)

    # 1) 관리자가 배정되지 않은 스팟 찾기 (WHERE NOT (s)-[:MANAGED_BY]->())
    unmanaged_spots = run_cypher("""
    MATCH (s:SmartSpot)
    WHERE NOT (s)-[:MANAGED_BY]->(:SmartManager)
    RETURN s.name AS name, s.area AS area
    """)
    print("▶ 관리자 미배정 스팟 (WHERE NOT):", [f"{r['name']}({r['area']})" for r in unmanaged_spots])

    # 2) 대전허브로 가는 직통 노선이 있는 허브 (EXISTS { })
    hubs_with_daejeon = run_cypher("""
    MATCH (h:SmartHub)
    WHERE EXISTS {
        MATCH (h)-[:TRUCK_ROUTE]->(target:SmartHub {name: '대전허브'})
    }
    RETURN h.name AS hub_name
    """)
    print("▶ 대전 직통 연결 허브 (EXISTS { }):", [r['hub_name'] for r in hubs_with_daejeon])

    print("\n" + "═" * 85)
    print("🛡️ [Step 7] OPTIONAL MATCH + WITH 스코프 격리 & NULL 처리")
    print("═" * 85)

    # OPTIONAL MATCH 이후 WITH로 격리하여 NULL인 행만 안전하게 필터링
    opt_with_res = run_cypher("""
    MATCH (s:SmartSpot)
    OPTIONAL MATCH (s)-[:MANAGED_BY]->(m:SmartManager)
    WITH s, m
    RETURN s.name AS spot_name,
           s.area AS area,
           coalesce(m.name, '🚨 담당자 없음') AS manager_name,
           coalesce(m.phone, '-') AS manager_contact
    ORDER BY s.area, s.name
    """)
    print("▶ 전체 스팟 관리 현황 (OPTIONAL MATCH + coalesce):")
    for r in opt_with_res:
        print(f"   • {r['spot_name']:<12} ({r['area']:<2}) | 관리자: {r['manager_name']:<10} | 연락처: {r['manager_contact']}")

    print("\n" + "═" * 85)
    print("🚰 [Step 8] WITH 다단계 파이프라인 (파생값 계산 & 중간 상위 N개 자르기)")
    print("═" * 85)

    # 1) 가평/강릉 지역 스팟 중 평점 상위 2곳을 뽑고,
    # 2) 그 2곳의 관리자 정보만 2차 연결
    pipeline_res = run_cypher("""
    MATCH (s:SmartSpot)
    WHERE s.area IN ['가평', '강릉', '서울']
    WITH s, (s.price / 2) AS per_person_cost
    ORDER BY s.rating DESC
    LIMIT 3
    OPTIONAL MATCH (s)-[:MANAGED_BY]->(m:SmartManager)
    RETURN s.name AS name,
           s.rating AS rating,
           per_person_cost,
           coalesce(m.name, '미배정') AS manager
    """)
    print("▶ 평점 TOP 3 스팟 선별 및 관리자 2차 연결 파이프라인:")
    for r in pipeline_res:
        print(f"   • {r['name']} (⭐ {r['rating']}) | 1인예상가: {r['per_person_cost']:,.0f}원 | 담당: {r['manager']}")

    print("\n" + "═" * 85)
    print("📄 [Step 9] 정렬(ORDER BY) & 페이징(SKIP/LIMIT) 보조키 최적화")
    print("═" * 85)

    # 2페이지 조회 (페이지당 2건, 1차: 가격 오름차순, 2차: 이름 오름차순)
    page_res = run_cypher("""
    MATCH (s:SmartSpot)
    RETURN s.name AS name, s.price AS price, s.rating AS rating
    ORDER BY s.price ASC, s.name ASC
    SKIP 2
    LIMIT 2
    """)
    print("▶ 가격순 2페이지 조회 (SKIP 2 LIMIT 2, 보조정렬키 name):")
    for r in page_res:
        print(f"   • {r['name']:<12} | 가격: {r['price']:,}원 | ⭐ {r['rating']}")

    print("\n" + "═" * 85)
    print("🚀 [Step 10] 엔터프라이즈 실무 비즈니스 함수 시연")
    print("═" * 85)

    def smart_logistics_router(start_hub_name: str, dest_city_name: str):
        """출발 허브에서 목적지 도시까지의 최적 경로, 총 거리, 총 비용, 소요시간을 분석하는 엔진"""
        query = """
        MATCH p = (start:SmartHub {name: $start})-[:TRUCK_ROUTE|AIR_ROUTE*1..4]->(dest:SmartCity {name: $dest})
        WITH p,
             [n IN nodes(p) | n.name] AS route_nodes,
             reduce(time = 0, r IN relationships(p) | time + r.time) AS total_time,
             reduce(cost = 0, r IN relationships(p) | cost + r.cost) AS total_cost,
             reduce(dist = 0, r IN relationships(p) | dist + r.distance_km) AS total_dist,
             all(r IN relationships(p) WHERE type(r) = 'TRUCK_ROUTE') AS is_all_land
        RETURN route_nodes, total_time, total_cost, total_dist, is_all_land
        ORDER BY total_time ASC, total_cost ASC
        LIMIT 1
        """
        res = run_cypher(query, start=start_hub_name, dest=dest_city_name)
        return res[0] if res else None

    # 함수 테스트 1: 인천 -> 부산
    route1 = smart_logistics_router("인천메가허브", "부산")
    print(f"📍 [스마트 라우터] 인천메가허브 ──> 부산 배송 최적화 결과:")
    if route1:
        print(f"   • 추천 경로: {' ──> '.join(route1['route_nodes'])}")
        print(f"   • 총 소요시간: {route1['total_time']}분 ({route1['total_time']/60:.1f}시간)")
        print(f"   • 총 운송비용: {route1['total_cost']:,}원")
        print(f"   • 총 운송거리: {route1['total_dist']}km (운송수단: {'육상전용' if route1['is_all_land'] else '항공특송포함'})")

    # 함수 테스트 2: 인천 -> 제주
    route2 = smart_logistics_router("인천메가허브", "제주")
    print(f"\n📍 [스마트 라우터] 인천메가허브 ──> 제주 배송 최적화 결과:")
    if route2:
        print(f"   • 추천 경로: {' ──> '.join(route2['route_nodes'])}")
        print(f"   • 총 소요시간: {route2['total_time']}분")
        print(f"   • 총 운송비용: {route2['total_cost']:,}원")

    print("\n" + "═" * 85)
    print("🎉 [Day 30 Cypher 심화 마스터 풀소스] 전 단계 실행 완료!")
    print("═" * 85)


if __name__ == "__main__":
    main()
