# -*- coding: utf-8 -*-
"""
과제 1, 2, 3권의 모범 정답 코드를 주피터 노트북에 주입하고,
Neo4j에 직접 연결하여 모든 assert 테스트를 완전하게 검증하는 스크립트
"""
import os
import sys
import io
import json
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Neo4j 접속
load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")
AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")

driver = None
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ 로컬 Neo4j 연결")
except Exception:
    if AURA_URI and AURA_USER and AURA_PASSWORD:
        driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        driver.verify_connectivity()
        print("✅ Aura Cloud DB 연결")
    else:
        raise ConnectionError("DB 연결 실패")

def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

def update_notebook(filepath, updates):
    with open(filepath, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    for cell in nb['cells']:
        cid = cell.get('id')
        if cid in updates:
            new_src = updates[cid]
            if isinstance(new_src, str):
                lines = [l + '\n' for l in new_src.splitlines()]
                if lines:
                    lines[-1] = lines[-1].rstrip('\n')
                cell['source'] = lines
            elif isinstance(new_src, list):
                cell['source'] = new_src
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"✅ 노트북 업데이트 완료: {filepath}")


# ==========================================
# 1. LV1 기초 과제 업데이트 & 테스트
# ==========================================
print("\n" + "="*70)
print("📘 [LV1 기초 과제 채점 및 검증]")
print("="*70)

# 시드 적재
run_cypher("MATCH (n) DETACH DELETE n")
run_cypher("""
CREATE (c5:Course {name:'CS302 운영체제', credits:4}),
       (c3:Course {name:'CS202 알고리즘', credits:4}),
       (c6:Course {name:'CS401 머신러닝', credits:4}),
       (m2:Course {name:'수학201 선형대수', credits:3}),
       (c1:Course {name:'CS101 프로그래밍입문', credits:3}),
       (m3:Course {name:'수학202 확률통계', credits:3}),
       (c2:Course {name:'CS201 자료구조', credits:3}),
       (m1:Course {name:'수학101 미적분학', credits:3}),
       (c4:Course {name:'CS301 데이터베이스', credits:3})
CREATE (c1)-[:PREREQ_OF]->(c2),
       (c2)-[:PREREQ_OF]->(c3),
       (c2)-[:PREREQ_OF]->(c4),
       (c2)-[:PREREQ_OF]->(c5),
       (c3)-[:PREREQ_OF]->(c6),
       (m1)-[:PREREQ_OF]->(m2),
       (m1)-[:PREREQ_OF]->(m3),
       (m2)-[:PREREQ_OF]->(c6),
       (m3)-[:PREREQ_OF]->(c6)
""")

# 1-1
rows1_1 = run_cypher("MATCH (:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*1..2]->(dest:Course) RETURN DISTINCT dest.name AS name")
assert sorted(r['name'] for r in rows1_1) == ['CS201 자료구조', 'CS202 알고리즘', 'CS301 데이터베이스', 'CS302 운영체제']
print("LV1 1-1 통과")

# 1-2
rows1_2 = run_cypher("MATCH (pre:Course)-[:PREREQ_OF*1..]->(:Course {name: 'CS401 머신러닝'}) RETURN DISTINCT pre.name AS name")
assert sorted(r['name'] for r in rows1_2) == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS202 알고리즘', '수학101 미적분학', '수학201 선형대수', '수학202 확률통계']
print("LV1 1-2 통과")

# 1-3
rows1_3 = run_cypher("MATCH (:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*0..2]->(dest:Course) RETURN DISTINCT dest.name AS name")
assert sorted(r['name'] for r in rows1_3) == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS202 알고리즘', 'CS301 데이터베이스', 'CS302 운영체제']
print("LV1 1-3 통과")

# 1-4
rows1_4 = run_cypher("MATCH p = shortestPath((start:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*]->(end:Course {name: 'CS401 머신러닝'})) RETURN [n IN nodes(p) | n.name] AS names")
assert rows1_4[0]['names'] == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS202 알고리즘', 'CS401 머신러닝']
print("LV1 1-4 통과")

# 1-5
rows1_5 = run_cypher("MATCH p = shortestPath((start:Course {name: '수학101 미적분학'})-[:PREREQ_OF*]->(end:Course {name: 'CS401 머신러닝'})) RETURN length(p) AS L")
assert rows1_5[0]['L'] == 2
print("LV1 1-5 통과")

# 1-6
rows1_6 = run_cypher("MATCH p = shortestPath((start:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*]->(b:Course)) WHERE b.name <> 'CS101 프로그래밍입문' RETURN b.name AS name, length(p) AS L ORDER BY L DESC, name ASC")
assert [(r['name'], r['L']) for r in rows1_6] == [('CS401 머신러닝', 3), ('CS202 알고리즘', 2), ('CS301 데이터베이스', 2), ('CS302 운영체제', 2), ('CS201 자료구조', 1)]
print("LV1 1-6 통과")

# 2-1
rows2_1 = run_cypher("MATCH (c:Course) WHERE c.name IN ['CS201 자료구조', 'CS301 데이터베이스', 'CS999 없는과목'] RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_1) == ['CS201 자료구조', 'CS301 데이터베이스']
print("LV1 2-1 통과")

# 2-2
rows2_2 = run_cypher("MATCH (c:Course) WHERE c.name CONTAINS '201' RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_2) == ['CS201 자료구조', '수학201 선형대수']
print("LV1 2-2 통과")

# 2-3
rows2_3 = run_cypher("MATCH (c:Course) WHERE c.name STARTS WITH '수학' RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_3) == ['수학101 미적분학', '수학201 선형대수', '수학202 확률통계']
print("LV1 2-3 통과")

# 2-4
rows2_4 = run_cypher("MATCH (c:Course) WHERE c.name ENDS WITH '학' RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_4) == ['수학101 미적분학']
print("LV1 2-4 통과")

# 2-5
rows2_5 = run_cypher("MATCH (c:Course) WHERE c.credits <> 4 RETURN c.name AS name ORDER BY name ASC")
assert [r['name'] for r in rows2_5] == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS301 데이터베이스', '수학101 미적분학', '수학201 선형대수', '수학202 확률통계']
print("LV1 2-5 통과")

# 2-6
rows2_6 = run_cypher("MATCH (c:Course) WHERE c.name =~ '(?i)cs.*' RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_6) == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS202 알고리즘', 'CS301 데이터베이스', 'CS302 운영체제', 'CS401 머신러닝']
print("LV1 2-6 통과")

# 2-7
target_names = ['CS201 자료구조', '수학201 선형대수', 'CS999 없는과목']
rows2_7 = run_cypher("MATCH (c:Course) WHERE c.name IN $names RETURN c.name AS name", names=target_names)
assert sorted(r['name'] for r in rows2_7) == ['CS201 자료구조', '수학201 선형대수']
print("LV1 2-7 통과")

# 2-8
rows2_8 = run_cypher("MATCH (c:Course) WHERE c.name STARTS WITH '수학' OR c.credits = 4 RETURN c.name AS name")
assert sorted(r['name'] for r in rows2_8) == ['CS202 알고리즘', 'CS302 운영체제', 'CS401 머신러닝', '수학101 미적분학', '수학201 선형대수', '수학202 확률통계']
print("LV1 2-8 통과")

# 3-1
rows3_1 = run_cypher("MATCH (c:Course) WHERE NOT (:Course)-[:PREREQ_OF]->(c) RETURN c.name AS name")
assert sorted(r['name'] for r in rows3_1) == ['CS101 프로그래밍입문', '수학101 미적분학']
print("LV1 3-1 통과")

# 3-2
rows3_2 = run_cypher("MATCH (c:Course) WHERE (c)-[:PREREQ_OF]->(:Course) RETURN c.name AS name")
assert sorted(r['name'] for r in rows3_2) == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS202 알고리즘', '수학101 미적분학', '수학201 선형대수', '수학202 확률통계']
print("LV1 3-2 통과")

# 4-1
rows4_1 = run_cypher("MATCH (c:Course) RETURN c.name AS name ORDER BY c.credits DESC, name ASC LIMIT 3")
assert [r['name'] for r in rows4_1] == ['CS202 알고리즘', 'CS302 운영체제', 'CS401 머신러닝']
print("LV1 4-1 통과")

# 4-2
rows4_2 = run_cypher("MATCH (c:Course) RETURN c.name AS name ORDER BY c.credits DESC, name ASC SKIP 3 LIMIT 3")
assert [r['name'] for r in rows4_2] == ['CS101 프로그래밍입문', 'CS201 자료구조', 'CS301 데이터베이스']
print("LV1 4-2 통과")

lv1_updates = {
    '7488832a': '''rows1_1 = run_cypher("""
MATCH (:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*1..2]->(dest:Course)
RETURN DISTINCT dest.name AS name
""")''',
    '75503557': '''rows1_2 = run_cypher("""
MATCH (pre:Course)-[:PREREQ_OF*1..]->(:Course {name: 'CS401 머신러닝'})
RETURN DISTINCT pre.name AS name
""")''',
    'b2069e84': '''rows1_3 = run_cypher("""
MATCH (:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*0..2]->(dest:Course)
RETURN DISTINCT dest.name AS name
""")''',
    'f25adf65': '''rows1_4 = run_cypher("""
MATCH p = shortestPath((start:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*]->(end:Course {name: 'CS401 머신러닝'}))
RETURN [n IN nodes(p) | n.name] AS names
""")''',
    'e958af43': '''rows1_5 = run_cypher("""
MATCH p = shortestPath((start:Course {name: '수학101 미적분학'})-[:PREREQ_OF*]->(end:Course {name: 'CS401 머신러닝'}))
RETURN length(p) AS L
""")''',
    '7eccc81e': '''rows1_6 = run_cypher("""
MATCH p = shortestPath((start:Course {name: 'CS101 프로그래밍입문'})-[:PREREQ_OF*]->(b:Course))
WHERE b.name <> 'CS101 프로그래밍입문'
RETURN b.name AS name, length(p) AS L
ORDER BY L DESC, name ASC
""")''',
    '521b4e3d': '''rows2_1 = run_cypher("""
MATCH (c:Course)
WHERE c.name IN ['CS201 자료구조', 'CS301 데이터베이스', 'CS999 없는과목']
RETURN c.name AS name
""")''',
    '38036399': '''rows2_2 = run_cypher("""
MATCH (c:Course)
WHERE c.name CONTAINS '201'
RETURN c.name AS name
""")''',
    'b76769e1': '''rows2_3 = run_cypher("""
MATCH (c:Course)
WHERE c.name STARTS WITH '수학'
RETURN c.name AS name
""")''',
    'de245ffa': '''rows2_4 = run_cypher("""
MATCH (c:Course)
WHERE c.name ENDS WITH '학'
RETURN c.name AS name
""")''',
    'd0d84a48': '''rows2_5 = run_cypher("""
MATCH (c:Course)
WHERE c.credits <> 4
RETURN c.name AS name
ORDER BY name ASC
""")''',
    'f5aaf4fa': '''rows2_6 = run_cypher("""
MATCH (c:Course)
WHERE c.name =~ '(?i)cs.*'
RETURN c.name AS name
""")''',
    '8be81d04': '''target_names = ['CS201 자료구조', '수학201 선형대수', 'CS999 없는과목']
rows2_7 = run_cypher("""
MATCH (c:Course)
WHERE c.name IN $names
RETURN c.name AS name
""", names=target_names)''',
    '4ff2218b': '''rows2_8 = run_cypher("""
MATCH (c:Course)
WHERE c.name STARTS WITH '수학' OR c.credits = 4
RETURN c.name AS name
""")''',
    'f4ffaa88': '''rows3_1 = run_cypher("""
MATCH (c:Course)
WHERE NOT (:Course)-[:PREREQ_OF]->(c)
RETURN c.name AS name
""")''',
    'c43a7df1': '''rows3_2 = run_cypher("""
MATCH (c:Course)
WHERE (c)-[:PREREQ_OF]->(:Course)
RETURN c.name AS name
""")''',
    '361018f9': '''rows4_1 = run_cypher("""
MATCH (c:Course)
RETURN c.name AS name
ORDER BY c.credits DESC, name ASC
LIMIT 3
""")''',
    '027e2243': '''rows4_2 = run_cypher("""
MATCH (c:Course)
RETURN c.name AS name
ORDER BY c.credits DESC, name ASC
SKIP 3
LIMIT 3
""")'''
}
update_notebook('내작업폴더/day30_Cypher_심화/과제_LV1_기초.ipynb', lv1_updates)


# ==========================================
# 2. LV2 응용 과제 업데이트 & 테스트
# ==========================================
print("\n" + "="*70)
print("📘 [LV2 응용 과제 채점 및 검증]")
print("="*70)

# 시드 적재
run_cypher("MATCH (n) DETACH DELETE n")
run_cypher("""
CREATE (icn:Warehouse {name:'인천창고'}),
       (busan:Warehouse {name:'부산창고'})
CREATE (seoul:Hub {name:'서울허브'}),
       (daejeon:Hub {name:'대전허브'}),
       (gwangju:Hub {name:'광주허브'})
CREATE (suwon:City {name:'수원시'}),
       (cheonan:City {name:'천안시'}),
       (jeonju:City {name:'전주시'}),
       (mokpo:City {name:'목포시'}),
       (jeju:City {name:'제주시'})
CREATE (icn)-[:ROUTE {time:40}]->(seoul),
       (icn)-[:ROUTE {time:90}]->(daejeon),
       (busan)-[:ROUTE {time:70}]->(gwangju),
       (seoul)-[:ROUTE {time:30}]->(suwon),
       (seoul)-[:ROUTE {time:80}]->(cheonan),
       (daejeon)-[:ROUTE {time:50}]->(cheonan),
       (daejeon)-[:ROUTE {time:70}]->(jeonju),
       (gwangju)-[:ROUTE {time:40}]->(jeonju),
       (gwangju)-[:ROUTE {time:55}]->(mokpo)
CREATE (icn)-[:AIR_ROUTE {time:25}]->(mokpo)
""")

# 1-1
rows1_1 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[:ROUTE*1..]->(c:City)
RETURN DISTINCT c.name AS name
""")
assert sorted(r['name'] for r in rows1_1) == ['수원시', '전주시', '천안시']
print("LV2 1-1 통과")

# 1-2
rows1_2 = run_cypher("""
MATCH p = shortestPath((:Warehouse {name: '인천창고'})-[:ROUTE*]->(:City {name: '전주시'}))
RETURN [n IN nodes(p) | n.name] AS names,
       [r IN relationships(p) | r.time] AS times,
       [r IN relationships(p) WHERE r.time > 70 | r.time] AS slow
""")
assert rows1_2[0]['names'] == ['인천창고', '대전허브', '전주시']
assert rows1_2[0]['times'] == [90, 70]
assert rows1_2[0]['slow'] == [90]
print("LV2 1-2 통과")

# 1-3
rows1_3 = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE all(x IN relationships(p) WHERE x.time <= 70)
RETURN w.name AS w, c.name AS c
""")
assert sorted((r['w'], r['c']) for r in rows1_3) == [('부산창고', '목포시'), ('부산창고', '전주시'), ('인천창고', '수원시')]
print("LV2 1-3 통과")

# 1-4
rows1_4_one = run_cypher("""
MATCH p = shortestPath((a:Warehouse {name: '인천창고'})-[:ROUTE*]->(b:City {name: '천안시'}))
RETURN [n IN nodes(p) | n.name] AS names
""")
rows1_4 = run_cypher("""
MATCH p = allShortestPaths((a:Warehouse {name: '인천창고'})-[:ROUTE*]->(b:City {name: '천안시'}))
RETURN [n IN nodes(p) | n.name] AS names
""")
assert len(rows1_4_one) == 1 and rows1_4_one[0]['names'] in [['인천창고', '대전허브', '천안시'], ['인천창고', '서울허브', '천안시']]
assert sorted(r['names'] for r in rows1_4) == [['인천창고', '대전허브', '천안시'], ['인천창고', '서울허브', '천안시']]
print("LV2 1-4 통과")

# 1-5
rows1_5 = run_cypher("""
MATCH (a:Warehouse {name: '인천창고'}), (b:City {name: '목포시'})
OPTIONAL MATCH p = shortestPath((a)-[:ROUTE*]->(b))
RETURN p IS NOT NULL AS connected
""")
assert rows1_5[0]['connected'] == False
print("LV2 1-5 통과")

# 1-6
rows1_6_any = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE any(x IN relationships(p) WHERE x.time > 80)
RETURN [n IN nodes(p) | n.name] AS names
""")
rows1_6_none = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE none(x IN relationships(p) WHERE x.time > 80)
RETURN [n IN nodes(p) | n.name] AS names
""")
assert sorted(r['names'] for r in rows1_6_any) == [['인천창고', '대전허브', '전주시'], ['인천창고', '대전허브', '천안시']]
assert sorted(r['names'] for r in rows1_6_none) == [['부산창고', '광주허브', '목포시'], ['부산창고', '광주허브', '전주시'], ['인천창고', '서울허브', '수원시'], ['인천창고', '서울허브', '천안시']]
print("LV2 1-6 통과")

# 1-7
rows1_7 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[x:ROUTE|AIR_ROUTE]->(n)
RETURN type(x) AS kind, n.name AS name
""")
assert sorted((r['kind'], r['name']) for r in rows1_7) == [('AIR_ROUTE', '목포시'), ('ROUTE', '대전허브'), ('ROUTE', '서울허브')]
print("LV2 1-7 통과")

# 2-1
rows2_1 = run_cypher("""
MATCH (:Warehouse {name: '부산창고'})-[:ROUTE]->(h:Hub)-[:ROUTE]->(c:City)
RETURN h.name AS hub, c.name AS city
""")
assert sorted((r['hub'], r['city']) for r in rows2_1) == [('광주허브', '목포시'), ('광주허브', '전주시')]
print("LV2 2-1 통과")

# 2-2
rows2_2 = run_cypher("""
MATCH (c:City)
OPTIONAL MATCH (x)-[:ROUTE]->(c)
WITH c, x
WHERE x IS NULL
RETURN c.name AS name
""")
assert sorted(r['name'] for r in rows2_2) == ['제주시']
print("LV2 2-2 통과")

# 2-3
rows2_3 = run_cypher("""
MATCH (h:Hub)
WHERE NOT EXISTS { (h)-[:ROUTE]->(:City {name: '천안시'}) }
RETURN h.name AS name
""")
assert sorted(r['name'] for r in rows2_3) == ['광주허브']
print("LV2 2-3 통과")

# 2-4
rows2_4 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
WHERE a.name ENDS WITH '허브' AND r.time >= 55
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
""")
assert [(r['a'], r['b'], r['t']) for r in rows2_4] == [('서울허브', '천안시', 80), ('대전허브', '전주시', 70), ('광주허브', '목포시', 55)]
print("LV2 2-4 통과")

# 2-5
rows2_5 = run_cypher("""
MATCH (h:Hub)
WHERE NOT EXISTS {
    MATCH (h)-[r:ROUTE]->(:City)
    WHERE r.time <= 30
}
RETURN h.name AS name
""")
assert sorted(r['name'] for r in rows2_5) == ['광주허브', '대전허브']
print("LV2 2-5 통과")

# 3-1
rows3_1 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[r:ROUTE]->(h:Hub)
WITH h, r.time AS t
ORDER BY t ASC
LIMIT 1
MATCH (h)-[:ROUTE]->(c:City)
RETURN h.name AS hub, c.name AS city
""")
assert sorted((r['hub'], r['city']) for r in rows3_1) == [('서울허브', '수원시'), ('서울허브', '천안시')]
print("LV2 3-1 통과")

# 3-2
rows3_2 = run_cypher("""
MATCH (src)-[r:ROUTE]->(:City {name: '천안시'})
WITH src.name AS src, r.time AS t
WHERE t <= 60
RETURN src, t
ORDER BY t ASC
""")
assert [(r['src'], r['t']) for r in rows3_2] == [('대전허브', 50)]
print("LV2 3-2 통과")

# 3-3
rows3_3 = run_cypher("""
MATCH (w:Warehouse)-[r1:ROUTE]->(h:Hub)-[r2:ROUTE]->(c:City)
WITH w, c, r1.time + r2.time AS 총시간
WHERE 총시간 <= 130
RETURN w.name AS w, c.name AS c, 총시간 AS t
ORDER BY t ASC, w.name ASC, c.name ASC
""")
assert [(r['w'], r['c'], r['t']) for r in rows3_3] == [('인천창고', '수원시', 70), ('부산창고', '전주시', 110), ('인천창고', '천안시', 120), ('부산창고', '목포시', 125)]
print("LV2 3-3 통과")

# 4-1
rows4_1 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
LIMIT 3
""")
assert [(r['a'], r['b'], r['t']) for r in rows4_1] == [('인천창고', '대전허브', 90), ('서울허브', '천안시', 80), ('대전허브', '전주시', 70)]
print("LV2 4-1 통과")

# 4-2
rows4_2 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
SKIP 3
LIMIT 3
""")
assert [(r['a'], r['b'], r['t']) for r in rows4_2] == [('부산창고', '광주허브', 70), ('광주허브', '목포시', 55), ('대전허브', '천안시', 50)]
print("LV2 4-2 통과")

lv2_updates = {
    '32f3af05': '''rows1_1 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[:ROUTE*1..]->(c:City)
RETURN DISTINCT c.name AS name
""")''',
    '85c42455': '''rows1_2 = run_cypher("""
MATCH p = shortestPath((:Warehouse {name: '인천창고'})-[:ROUTE*]->(:City {name: '전주시'}))
RETURN [n IN nodes(p) | n.name] AS names,
       [r IN relationships(p) | r.time] AS times,
       [r IN relationships(p) WHERE r.time > 70 | r.time] AS slow
""")''',
    '4d7bb944': '''rows1_3 = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE all(x IN relationships(p) WHERE x.time <= 70)
RETURN w.name AS w, c.name AS c
""")''',
    '22ec5f9f': '''rows1_4_one = run_cypher("""
MATCH p = shortestPath((a:Warehouse {name: '인천창고'})-[:ROUTE*]->(b:City {name: '천안시'}))
RETURN [n IN nodes(p) | n.name] AS names
""")

rows1_4 = run_cypher("""
MATCH p = allShortestPaths((a:Warehouse {name: '인천창고'})-[:ROUTE*]->(b:City {name: '천안시'}))
RETURN [n IN nodes(p) | n.name] AS names
""")''',
    '7d50e1b8': '''rows1_5 = run_cypher("""
MATCH (a:Warehouse {name: '인천창고'}), (b:City {name: '목포시'})
OPTIONAL MATCH p = shortestPath((a)-[:ROUTE*]->(b))
RETURN p IS NOT NULL AS connected
""")''',
    '872e5b55': '''**서술 답안**
인천창고에서 목포시로 향하는 육상 노선(ROUTE)은 광주허브를 거쳐야 하는데, 인천창고에서는 서울허브와 대전허브로만 육상 노선이 연결되어 있고 대전에서 광주로 가는 육상 노선이 없으므로 방향 있는 육상 배송 경로가 존재하지 않아 `connected`가 `False`로 판별됩니다.''',
    'd1052506': '''rows1_6_any = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE any(x IN relationships(p) WHERE x.time > 80)
RETURN [n IN nodes(p) | n.name] AS names
""")

rows1_6_none = run_cypher("""
MATCH p = (w:Warehouse)-[:ROUTE*1..2]->(c:City)
WHERE none(x IN relationships(p) WHERE x.time > 80)
RETURN [n IN nodes(p) | n.name] AS names
""")''',
    'b759f604': '''rows1_7 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[x:ROUTE|AIR_ROUTE]->(n)
RETURN type(x) AS kind, n.name AS name
""")''',
    '58596b25': '''rows2_1 = run_cypher("""
MATCH (:Warehouse {name: '부산창고'})-[:ROUTE]->(h:Hub)-[:ROUTE]->(c:City)
RETURN h.name AS hub, c.name AS city
""")''',
    '3c089aff': '''rows2_2 = run_cypher("""
MATCH (c:City)
OPTIONAL MATCH (x)-[:ROUTE]->(c)
WITH c, x
WHERE x IS NULL
RETURN c.name AS name
""")''',
    '8695d350': '''rows2_3 = run_cypher("""
MATCH (h:Hub)
WHERE NOT EXISTS { (h)-[:ROUTE]->(:City {name: '천안시'}) }
RETURN h.name AS name
""")''',
    'cb7965d9': '''rows2_4 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
WHERE a.name ENDS WITH '허브' AND r.time >= 55
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
""")''',
    'e262a673': '''rows2_5 = run_cypher("""
MATCH (h:Hub)
WHERE NOT EXISTS {
    MATCH (h)-[r:ROUTE]->(:City)
    WHERE r.time <= 30
}
RETURN h.name AS name
""")''',
    '57676716': '''rows3_1 = run_cypher("""
MATCH (:Warehouse {name: '인천창고'})-[r:ROUTE]->(h:Hub)
WITH h, r.time AS t
ORDER BY t ASC
LIMIT 1
MATCH (h)-[:ROUTE]->(c:City)
RETURN h.name AS hub, c.name AS city
""")''',
    'bc17b791': '''rows3_2 = run_cypher("""
MATCH (src)-[r:ROUTE]->(:City {name: '천안시'})
WITH src.name AS src, r.time AS t
WHERE t <= 60
RETURN src, t
ORDER BY t ASC
""")''',
    '3fb09414': '''rows3_3 = run_cypher("""
MATCH (w:Warehouse)-[r1:ROUTE]->(h:Hub)-[r2:ROUTE]->(c:City)
WITH w, c, r1.time + r2.time AS 총시간
WHERE 총시간 <= 130
RETURN w.name AS w, c.name AS c, 총시간 AS t
ORDER BY t ASC, w.name ASC, c.name ASC
""")''',
    '1e135cb4': '''rows4_1 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
LIMIT 3
""")''',
    '441309aa': '''rows4_2 = run_cypher("""
MATCH (a)-[r:ROUTE]->(b)
RETURN a.name AS a, b.name AS b, r.time AS t
ORDER BY t DESC, a.name ASC, b.name ASC
SKIP 3
LIMIT 3
""")'''
}
update_notebook('내작업폴더/day30_Cypher_심화/과제_LV2_응용.ipynb', lv2_updates)


# ==========================================
# 3. LV3 통합 과제 업데이트 & 테스트
# ==========================================
print("\n" + "="*70)
print("📘 [LV3 통합 과제 채점 및 검증]")
print("="*70)

# 시드 적재
run_cypher("MATCH (n) DETACH DELETE n")
run_cypher("""
CREATE (ari:Person {name:'아리', city:'서울'}),
       (bomi:Person {name:'보미', city:'서울'}),
       (chris:Person {name:'크리스', city:'부산'}),
       (dana:Person {name:'다나', city:'서울'}),
       (eun:Person {name:'은수', city:'대구'}),
       (fin:Person {name:'피니', city:'부산'}),
       (gale:Person {name:'가을', city:'서울'}),
       (dal:Person {name:'달이', city:'제주'})\n
CREATE (ari)-[:FRIEND]->(bomi),
       (ari)-[:FRIEND]->(chris),
       (bomi)-[:FRIEND]->(dana),
       (chris)-[:FRIEND]->(eun),
       (dana)-[:FRIEND]->(fin),
       (eun)-[:FRIEND]->(gale),
       (fin)-[:FRIEND]->(gale),
       (bomi)-[:FRIEND]->(chris),
       (dana)-[:FRIEND]->(chris)
""")

# 1-1
def friends(name):
    query = """
    MATCH (:Person {name: $name})-[:FRIEND]-(friend:Person)
    RETURN friend.name AS n
    """
    rows = run_cypher(query, name=name)
    return sorted(r['n'] for r in rows)

assert friends('아리') == ['보미', '크리스']
assert friends('크리스') == ['다나', '보미', '아리', '은수']
print("LV3 1-1 통과")

# 1-2
def recommend(name):
    query = """
    MATCH (a:Person {name: $name})-[:FRIEND]-()-[:FRIEND]-(fof:Person)
    WHERE fof <> a AND NOT (a)-[:FRIEND]-(fof)
    WITH DISTINCT fof.name AS n
    RETURN n
    """
    rows = run_cypher(query, name=name)
    return sorted(r['n'] for r in rows)

assert recommend('아리') == ['다나', '은수']
assert recommend('보미') == ['은수', '피니']
print("LV3 1-2 통과")

# 1-3
os.makedirs("output", exist_ok=True)
report = {}
for p in ['아리', '보미', '크리스']:
    report[p] = {
        'friends': friends(p),
        'recommend': recommend(p)
    }

with open("output/sns_recommend.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

saved = json.load(open('output/sns_recommend.json', encoding='utf-8'))
assert set(saved) == {'아리', '보미', '크리스'}
assert saved['아리']['friends'] == ['보미', '크리스']
assert saved['아리']['recommend'] == ['다나', '은수']
assert saved['보미']['recommend'] == ['은수', '피니']
print("LV3 1-3 통과")

# 2-1
def diagnose(a, b):
    query = """
    MATCH (start:Person {name: $a}), (end:Person {name: $b})
    OPTIONAL MATCH p = shortestPath((start)-[:FRIEND*]-(end))
    RETURN p IS NOT NULL AS connected,
           length(p) AS hops,
           CASE WHEN p IS NOT NULL THEN [n IN nodes(p) | n.name] ELSE null END AS path,
           CASE WHEN p IS NOT NULL THEN all(n IN nodes(p) WHERE n.city = '서울') ELSE null END AS all_seoul
    """
    rows = run_cypher(query, a=a, b=b)
    return rows[0]

r1 = diagnose('아리', '가을')
assert r1['connected'] == True and r1['hops'] == 3 and r1['path'] == ['아리', '크리스', '은수', '가을']
assert r1['all_seoul'] == False
r3 = diagnose('가을', '아리')
assert r3['connected'] == True and r3['hops'] == 3 and r3['path'] == ['가을', '은수', '크리스', '아리']
r2 = diagnose('아리', '달이')
assert r2['connected'] == False and r2['hops'] is None and r2['path'] is None and r2['all_seoul'] is None
print("LV3 2-1 통과")

# 2-2
pairs = [('아리', '가을'), ('아리', '피니'), ('아리', '달이')]
path_report = []

for a, b in pairs:
    diag = diagnose(a, b)
    path_report.append({
        'a': a,
        'b': b,
        'connected': diag['connected'],
        'hops': diag['hops'],
        'path': diag['path']
    })

with open("output/sns_path_report.json", "w", encoding="utf-8") as f:
    json.dump(path_report, f, ensure_ascii=False, indent=2)

saved_path = json.load(open('output/sns_path_report.json', encoding='utf-8'))
assert len(saved_path) == 3
assert all(set(row) == {'a', 'b', 'connected', 'hops', 'path'} for row in saved_path)
gale = [r for r in saved_path if r['b'] == '가을'][0]
assert gale['connected'] == True and gale['path'] == ['아리', '크리스', '은수', '가을']
dal = [r for r in saved_path if r['b'] == '달이'][0]
assert dal['connected'] == False and dal['path'] is None
print("LV3 2-2 통과")

lv3_updates = {
    '8428b6e0': '''def friends(name):
    query = """
    MATCH (:Person {name: $name})-[:FRIEND]-(friend:Person)
    RETURN friend.name AS n
    """
    rows = run_cypher(query, name=name)
    return sorted(r['n'] for r in rows)''',
    '9c66f6f0': '''def recommend(name):
    query = """
    MATCH (a:Person {name: $name})-[:FRIEND]-()-[:FRIEND]-(fof:Person)
    WHERE fof <> a AND NOT (a)-[:FRIEND]-(fof)
    WITH DISTINCT fof.name AS n
    RETURN n
    """
    rows = run_cypher(query, name=name)
    return sorted(r['n'] for r in rows)''',
    '8d32b684': '''import os
import json

os.makedirs("output", exist_ok=True)
report = {}
for p in ['아리', '보미', '크리스']:
    report[p] = {
        'friends': friends(p),
        'recommend': recommend(p)
    }

with open("output/sns_recommend.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)''',
    'a6ca26a1': '''def diagnose(a, b):
    query = """
    MATCH (start:Person {name: $a}), (end:Person {name: $b})
    OPTIONAL MATCH p = shortestPath((start)-[:FRIEND*]-(end))
    RETURN p IS NOT NULL AS connected,
           length(p) AS hops,
           CASE WHEN p IS NOT NULL THEN [n IN nodes(p) | n.name] ELSE null END AS path,
           CASE WHEN p IS NOT NULL THEN all(n IN nodes(p) WHERE n.city = '서울') ELSE null END AS all_seoul
    """
    rows = run_cypher(query, a=a, b=b)
    return rows[0]''',
    '656c92dc': '''import os
import json

os.makedirs("output", exist_ok=True)
pairs = [('아리', '가을'), ('아리', '피니'), ('아리', '달이')]
path_report = []

for a, b in pairs:
    diag = diagnose(a, b)
    path_report.append({
        'a': a,
        'b': b,
        'connected': diag['connected'],
        'hops': diag['hops'],
        'path': diag['path']
    })

with open("output/sns_path_report.json", "w", encoding="utf-8") as f:
    json.dump(path_report, f, ensure_ascii=False, indent=2)''',
    '865034e5': '''**서술 답안**
1. **달이가 아무와도 연결되지 않는 이유**: '달이' 노드는 어떤 이웃 노드와도 `FRIEND` 관계가 연결되어 있지 않은 고립 노드(Degree = 0)이기 때문에 `shortestPath` 탐색 시 경로가 존재하지 않아 `connected=False`가 됩니다.
2. **미리 찾아내는 쿼리**: `MATCH (p:Person) WHERE NOT (p)-[:FRIEND]-() RETURN p.name` 과 같이 관계 부재 패턴 술어를 사용하면 어떤 친구와도 연결되지 않은 고립 사용자를 매일 주기적으로 손쉽게 탐지할 수 있습니다.'''
}
update_notebook('내작업폴더/day30_Cypher_심화/과제_LV3_통합.ipynb', lv3_updates)

print("\n" + "="*70)
print("🎉 [과제 1, 2, 3권 모든 문제 100% 자가채점 통과 및 업데이트 완료!]")
print("="*70)
