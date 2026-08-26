# 🖐️ 함께 따라하기 (아래 순서대로 직접 작성해 보세요)
# 1) 사람에서 영화로 향하는 ACTED_IN 패턴을 쓰되, 영화 노드에 title 조건을 직접 적는다
# 2) 사람 이름만 돌려받아 matrix_cast 에 담는다
# 3) len(matrix_cast) 로 인원수를 출력한다

matrix_cast = run_cypher("MATCH (p:Person)-[:ACTED_IN]->(:Movie {title:'The Matrix'}) "
                       "RETURN p.name AS name ORDER BY p.name")

print(matrix_cast)
print(len(matrix_cast))"""
=============================================================================
🏛️ Day 28 Neo4j & LPG 실전 엔드투엔드 마스터 풀소스
- Neo4j 드라이버 연결 및 헬스체크
- Movies 예제 그래프 적재 및 다차원 그래프 분석
- LPG 4대 구성요소 (노드, 레이블, 방향성 관계, 관계 속성) 완전 검증
- 실전 온라인 서점(Bookstore) 도메인 그래프 모델링 & 유효성/도달성 검증기
=============================================================================
"""

import os
import sys
from collections import Counter
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 강제 적용
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from neo4j import GraphDatabase

# =============================================================================
# 1. 환경 설정 및 싱글톤 드라이버 초기화
# =============================================================================
current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir / ".env", override=True)
load_dotenv(current_dir.parent / ".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

print("=" * 80)
print(f"[1단계] Neo4j 드라이버 초기화 및 연결 점검: {NEO4J_URI} ({NEO4J_USER})")
print("=" * 80)

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print(">> [성공] Neo4j 데이터베이스 연결 확인 완료!")
except Exception as e:
    print(f">> [실패] Neo4j 연결 실패: {e}")
    sys.exit(1)


def run_cypher(query: str, **params) -> list[dict]:
    """Cypher 실행 -> 결과를 dict 리스트로 반환하는 공용 헬퍼."""
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]


# =============================================================================
# 2. Movies 그래프 데이터셋 점검 및 자동 적재 (Self-Healing)
# =============================================================================
print("\n" + "=" * 80)
print("[2단계] Movies 데이터셋 적재 상태 점검")
print("=" * 80)

node_count_res = run_cypher("MATCH (n) RETURN count(n) AS cnt")
current_node_count = node_count_res[0]["cnt"] if node_count_res else 0
print(f"현재 데이터베이스 총 노드 수: {current_node_count}개")

if current_node_count == 0:
    cypher_file = current_dir / "data" / "movies_setup.cypher"
    if cypher_file.exists():
        print(f">> Movies 데이터셋이 비어 있어 '{cypher_file.name}' 파일을 자동 적재합니다...")
        with open(cypher_file, "r", encoding="utf-8") as f:
            full_cypher = f.read()
        
        # 세미콜론 기준으로 문장 분할 후 순차 실행
        statements = [stmt.strip() for stmt in full_cypher.split(";") if stmt.strip()]
        with driver.session() as session:
            for stmt in statements:
                session.run(stmt)
        
        new_cnt = run_cypher("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
        print(f">> [성공] Movies 데이터셋 적재 완료! (총 노드 수: {new_cnt}개)")
    else:
        print(">> [경고] 'data/movies_setup.cypher' 파일을 찾을 수 없습니다. 수동 적재가 필요합니다.")
else:
    print(">> [확인] Movies 그래프가 이미 적재되어 있습니다 (준비 완료).")


# =============================================================================
# 3. LPG 4대 핵심 요소 탐색 및 Cypher 질의 실습
# =============================================================================
print("\n" + "=" * 80)
print("[3단계] LPG(Labeled Property Graph) 핵심 요소 탐색")
print("=" * 80)

# 1) 레이블(Label) 및 노드 분포
labels = [row["label"] for row in run_cypher("CALL db.labels() YIELD label")]
movie_cnt = run_cypher("MATCH (m:Movie) RETURN count(m) AS cnt")[0]["cnt"]
person_cnt = run_cypher("MATCH (p:Person) RETURN count(p) AS cnt")[0]["cnt"]
print(f"1. 레이블 목록: {labels}")
print(f"   - Movie 노드 수: {movie_cnt}개")
print(f"   - Person 노드 수: {person_cnt}개")

# 2) 관계(Relationship Type) 목록
rel_types = [row["relationshipType"] for row in run_cypher("CALL db.relationshipTypes() YIELD relationshipType")]
print(f"\n2. 관계 종류 목록: {rel_types}")

# 3) 관계의 방향성과 사실의 인과관계
keanu_movies = run_cypher(
    "MATCH (p:Person {name: $name})-[:ACTED_IN]->(m:Movie) "
    "RETURN m.title AS title, m.released AS released ORDER BY m.released LIMIT 5",
    name="Keanu Reeves"
)
print("\n3. 단방향 관계 탐색 (Keanu Reeves -> ACTED_IN -> Movie):")
for r in keanu_movies:
    print(f"   - {r['title']} ({r['released']}년)")

# 4) 다중 관계 (동일 노드 쌍에 여러 관계가 존재하는 사례)
multi_role = run_cypher(
    "MATCH (p:Person)-[:ACTED_IN]->(m:Movie), (p)-[:DIRECTED]->(m) "
    "RETURN p.name AS person, m.title AS movie ORDER BY p.name"
)
print("\n4. 다중 관계 탐색 (출연과 감독을 동시에 수행한 인물):")
for r in multi_role:
    print(f"   - 인물: {r['person']} | 영화: {r['movie']}")

# 5) 관계 속성 (Relationship Property: roles, rating)
matrix_roles = run_cypher(
    "MATCH (p:Person)-[r:ACTED_IN]->(m:Movie {title: 'The Matrix'}) "
    "RETURN p.name AS actor, r.roles AS roles ORDER BY p.name"
)
print("\n5. 관계 속성 탐색 ('The Matrix' 출연진의 배역(roles) 속성):")
for r in matrix_roles:
    print(f"   - 배우: {r['actor']:<20} | 배역(roles 속성): {r['roles']}")

reviews = run_cypher(
    "MATCH (p:Person)-[r:REVIEWED]->(m:Movie) "
    "RETURN p.name AS reviewer, m.title AS movie, r.rating AS rating, r.summary AS summary LIMIT 5"
)
print("\n6. 리뷰 별점(rating 속성) 탐색:")
for r in reviews:
    print(f"   - 리뷰어: {r['reviewer']} | 영화: {r['movie']} | 평점: {r['rating']}점 | 요약: '{r['summary']}'")


# =============================================================================
# 4. 파이썬 데이터 후처리 및 그래프 통계 분석
# =============================================================================
print("\n" + "=" * 80)
print("[4단계] 파이썬 데이터 후처리 & 그래프 통계 (Collections/Pandas 연계)")
print("=" * 80)

# 1) 개봉 연대별 영화 수 분포
all_movies = run_cypher("MATCH (m:Movie) RETURN m.title AS title, m.released AS released")
decades = Counter((m["released"] // 10) * 10 for m in all_movies if m["released"])
print("1. 연대별 영화 개봉 분포:")
for decade, count in sorted(decades.items()):
    print(f"   - {decade}년대: {count}편 {'#' * count}")

# 2) 다작 배우 TOP 5
actors = run_cypher("MATCH (p:Person)-[:ACTED_IN]->(m:Movie) RETURN p.name AS actor, m.title AS movie")
actor_counts = Counter(row["actor"] for row in actors)
print("\n2. 최다 출연 배우 TOP 5:")
for actor, count in actor_counts.most_common(5):
    print(f"   - {actor:<20}: {count}편 출연")

# 3) 키아누 리브스와 가장 많이 함께 출연한 동료 배우 (2-Hop 순회)
co_actors = run_cypher(
    "MATCH (p:Person {name: 'Keanu Reeves'})-[:ACTED_IN]->(m:Movie)<-[:ACTED_IN]-(co:Person) "
    "RETURN co.name AS co_actor, count(m) AS shared_count "
    "ORDER BY shared_count DESC, co_actor LIMIT 5"
)
print("\n3. 키아누 리브스와 최다 공동 출연 배우 TOP 5 (2-Hop 추천 패턴):")
for r in co_actors:
    print(f"   - {r['co_actor']:<20}: {r['shared_count']}편 공동 출연")


# =============================================================================
# 5. 실전 온라인 서점(Bookstore) 도메인 그래프 모델링 & 검증
# =============================================================================
print("\n" + "=" * 80)
print("[5단계] 실전 온라인 서점(Bookstore) 그래프 모델 설계 & 검증")
print("=" * 80)

QUESTIONS = ['같은 카테고리 책', '이 저자의 다른 책', '이 독자가 산 책', '이 책 평균 별점']

# 표준 모범 서점 그래프 모델 (Candidate A)
book_model = {
    'nodes': {'Reader', 'Book', 'Author', 'Publisher', 'Category'},
    'relationships': {
        'PURCHASED': ('Reader', 'Book'),
        'REVIEWED': ('Reader', 'Book'),
        'WROTE': ('Author', 'Book'),
        'PUBLISHED': ('Publisher', 'Book'),
        'IN_CATEGORY': ('Book', 'Category')
    },
    'node_properties': {
        'Reader': {'name', 'user_id'},
        'Book': {'title', 'isbn', 'price'},
        'Author': {'name'},
        'Publisher': {'name'},
        'Category': {'name'}
    },
    'rel_properties': {
        'PURCHASED': {'bought_at'},
        'REVIEWED': {'rating', 'comment'},
        'PUBLISHED': {'published_year'}
    }
}


def validate_model(model: dict) -> bool:
    """도메인 모델 스키마 유효성 검증 엔진."""
    nodes = model.get('nodes', set())
    rels = model.get('relationships', {})
    node_props = model.get('node_properties', {})
    rel_props = model.get('rel_properties', {})

    assert isinstance(nodes, (set, frozenset)), "nodes는 set 집합이어야 합니다."
    assert isinstance(rels, dict), "relationships는 dict여야 합니다."
    assert len(nodes) >= 5, "노드 레이블은 5개 이상이어야 합니다."
    assert len(rels) >= 4, "관계는 4개 이상이어야 합니다."

    for name, endpoints in rels.items():
        assert name.replace('_', '').isupper(), f"관계 이름은 대문자 스네이크여야 합니다: {name}"
        subj, obj = endpoints
        assert subj in nodes, f"'{name}'의 주어 {subj}가 nodes에 없습니다."
        assert obj in nodes, f"'{name}'의 목적어 {obj}가 nodes에 없습니다."

    used = {label for pair in rels.values() for label in pair}
    orphans = nodes - used
    assert not orphans, f"고립된 노드가 있습니다: {sorted(orphans)}"

    for label in node_props:
        assert label in nodes, f"node_properties의 {label}가 nodes에 없습니다."
    for name in rel_props:
        assert name in rels, f"rel_properties의 {name}가 relationships에 없습니다."

    assert any('rating' in props for props in rel_props.values()), "별점(rating)은 관계 속성에 있어야 합니다."
    assert not any('rating' in props for props in node_props.values()), "별점(rating)이 노드 속성에 있으면 안 됩니다."
    return True


def _walk_ends(rels: dict, chain: list) -> list:
    results = []
    for start in set(rels[chain[0]]):
        current, path, ok = start, [start], True
        for name in chain:
            left, right = rels[name]
            if current == left:
                current = right
            elif current == right:
                current = left
            else:
                ok = False
                break
            path.append(current)
        if ok:
            results.append((start, current, tuple(path)))
    return results


def check_reachable(model: dict, answers: dict) -> bool:
    """4대 질문에 대한 관계 순회 경로 도달성 검증 엔진."""
    rels = model.get('relationships', {})
    rel_props = model.get('rel_properties', {})
    
    missing = [q for q in QUESTIONS if q not in answers]
    assert not missing, f"누락된 질문: {missing}"

    walks = {}
    for question in QUESTIONS:
        chain = answers[question]
        assert isinstance(chain, (list, tuple)) and chain, f"'{question}' 경로는 리스트여야 합니다."
        for name in chain:
            assert name in rels, f"'{question}': 없는 관계 {name}"
        ends = _walk_ends(rels, chain)
        assert ends, f"'{question}': 경로가 연결되지 않습니다."
        walks[question] = ends

    # 1·2번 질문: 2-Hop 왕복 검사
    for q in [QUESTIONS[0], QUESTIONS[1]]:
        found = [w for w in walks[q] if w[0] == w[1] and w[2][1] != w[0]]
        assert found, f"'{q}': 출발지로 되돌아오는 2-Hop 왕복 경로가 아닙니다."

    # 3번 질문: 구매 1-Hop 직접 연결
    direct = [w for w in walks[QUESTIONS[2]] if len(answers[QUESTIONS[2]]) == 1 and w[0] != w[1]]
    assert direct, f"'{QUESTIONS[2]}': 1-Hop 직접 연결이어야 합니다."
    buy_rel = answers[QUESTIONS[2]][0]
    assert 'rating' not in rel_props.get(buy_rel, set()), f"'{buy_rel}'는 구매 관계여야 하며 별점이 붙으면 안 됩니다."

    # 4번 질문: 별점이 붙은 관계 1-Hop
    rating_chain = answers[QUESTIONS[3]]
    assert len(rating_chain) == 1, f"'{QUESTIONS[3]}': 1-Hop 관계여야 합니다."
    assert 'rating' in rel_props.get(rating_chain[0], set()), f"'{rating_chain[0]}'에 rating 속성이 없습니다."

    return True


answers = {
    '같은 카테고리 책': ['IN_CATEGORY', 'IN_CATEGORY'],
    '이 저자의 다른 책': ['WROTE', 'WROTE'],
    '이 독자가 산 책': ['PURCHASED'],
    '이 책 평균 별점': ['REVIEWED']
}

print("1. 서점 도메인 모델 스키마 검증:", "통과 [OK]" if validate_model(book_model) else "실패 [FAIL]")
print("2. 4대 비즈니스 질문 도달성 검증:", "통과 [OK]" if check_reachable(book_model, answers) else "실패 [FAIL]")


# =============================================================================
# 6. 후보 모델 결함 진단 (A~E 비교 분석)
# =============================================================================
print("\n" + "=" * 80)
print("[6단계] 5개 후보 모델 결함 자동 진단 (Anti-Pattern Analysis)")
print("=" * 80)

candidates = {
    'A': book_model,
    'B': {  # 결함: rating을 Book 노드 속성에 둠
        'nodes': {'Reader', 'Book', 'Author', 'Publisher', 'Category'},
        'relationships': {'PURCHASED': ('Reader', 'Book'), 'REVIEWED': ('Reader', 'Book'),
                          'WROTE': ('Author', 'Book'), 'PUBLISHED': ('Publisher', 'Book'),
                          'IN_CATEGORY': ('Book', 'Category')},
        'node_properties': {'Book': {'title', 'rating'}},
        'rel_properties': {},
    },
    'C': {  # 시맨틱 결함: WROTE 방향이 Book -> Author (책이 작가를 씀)
        'nodes': {'Reader', 'Book', 'Author', 'Publisher', 'Category'},
        'relationships': {'PURCHASED': ('Reader', 'Book'), 'REVIEWED': ('Reader', 'Book'),
                          'WROTE': ('Book', 'Author'), 'PUBLISHED': ('Publisher', 'Book'),
                          'IN_CATEGORY': ('Book', 'Category')},
        'node_properties': {'Book': {'title'}},
        'rel_properties': {'REVIEWED': {'rating'}},
    },
    'D': {  # 결함: Publisher 노드가 고립됨 (Orphan Node)
        'nodes': {'Reader', 'Book', 'Author', 'Publisher', 'Category'},
        'relationships': {'PURCHASED': ('Reader', 'Book'), 'REVIEWED': ('Reader', 'Book'),
                          'WROTE': ('Author', 'Book'), 'IN_CATEGORY': ('Book', 'Category')},
        'node_properties': {'Book': {'title'}, 'Publisher': {'name'}},
        'rel_properties': {'REVIEWED': {'rating'}},
    },
    'E': {  # 통과: 한글 레이블 및 확장 속성
        'nodes': {'회원', '도서', '작가', '펴낸곳', '분야'},
        'relationships': {'BOUGHT': ('회원', '도서'), 'RATED': ('회원', '도서'),
                          'AUTHORED': ('작가', '도서'), 'ISSUED': ('펴낸곳', '도서'),
                          'BELONGS_TO': ('도서', '분야')},
        'node_properties': {'도서': {'title'}},
        'rel_properties': {'RATED': {'rating'}, 'BOUGHT': {'bought_at'}},
    }
}

for name, cand in sorted(candidates.items()):
    try:
        validate_model(cand)
        if name == 'C':
            print(f"후보 {name}: [주의] 구조적 유효성 통과, 그러나 치명적 시맨틱 오류 ('WROTE' 방향 역전: Book -> Author)")
        else:
            print(f"후보 {name}: [통과] 완전 무결한 유효 모델")
    except AssertionError as err:
        print(f"후보 {name}: [결함 발견] -> {err}")

print("\n" + "=" * 80)
print("[완료] Day 28 Neo4j & LPG 마스터 풀소스 전체 실행 및 검증 완료!")
print("=" * 80)

driver.close()
