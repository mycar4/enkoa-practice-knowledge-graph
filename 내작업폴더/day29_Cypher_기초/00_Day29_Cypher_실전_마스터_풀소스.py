# -*- coding: utf-8 -*-
"""
🏛️ [Day 29 마스터 풀소스] Cypher 그래프 질의 언어(GQL) 실전 엔드투엔드 파이프라인
- 도메인: 스타트업 "노바랩스 (NovaLabs)" 엔지니어링 조직 및 프로젝트 지식 그래프
- 기능: CREATE / MERGE / SET / REMOVE / DETACH DELETE / WHERE / 2-Hop 탐색 / $params 바인딩
- 실행 방법: uv run python 내작업폴더/day29_Cypher_기초/00_Day29_Cypher_실전_마스터_풀소스.py
"""

import os
import sys
import io
from dotenv import load_dotenv
from neo4j import GraphDatabase

# UTF-8 콘솔 출력 보장 (Windows 인코딩 대응)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. 환경 변수 로드 (.env)
load_dotenv(".env", override=True)
load_dotenv("../.env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")

print(f"🔗 Neo4j 접속 시도: {NEO4J_URI} (사용자: {NEO4J_USER})")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ Neo4j 연결 성공!")
except Exception as e:
    print(f"❌ 연결 실패: {e}")
    sys.exit(1)


def run_cypher(query: str, **params):
    """Cypher 질의를 실행하고 결과를 딕셔너리 리스트로 반환하는 공용 헬퍼 함수"""
    with driver.session() as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def main():
    print("\n" + "=" * 80)
    print("🚀 [Step 1] 실습 격리용 이전 데이터 초기화 (MATCH (n) DETACH DELETE n)")
    print("=" * 80)
    
    # 이전 데이터 정리
    run_cypher("MATCH (n:NovaEmployee) DETACH DELETE n")
    run_cypher("MATCH (n:NovaTeam) DETACH DELETE n")
    run_cypher("MATCH (n:NovaProject) DETACH DELETE n")
    run_cypher("MATCH (n:NovaSkill) DETACH DELETE n")
    print("🧹 '노바랩스' 실습 네임스페이스 노드/관계 깔끔 초기화 완료!")

    print("\n" + "=" * 80)
    print("🚀 [Step 2] 멱등성(MERGE) 기반 노드 생성 & 속성 자료형(date, list) 시연")
    print("=" * 80)

    # 1) 팀 노드 생성
    run_cypher("""
    MERGE (t1:NovaTeam {team_id: 'TEAM_AI', name: 'AI Research Lab', room: '701호'})
    MERGE (t2:NovaTeam {team_id: 'TEAM_DEV', name: 'Backend Platform', room: '702호'})
    """)

    # 2) 직원 노드 생성 (자료형: 문자열, 정수, 불리언, date, 리스트)
    run_cypher("""
    MERGE (e1:NovaEmployee:NovaLead {emp_id: 'E001'})
    ON CREATE SET 
        e1.name = 'Alice',
        e1.joined_date = date('2023-01-15'),
        e1.skills = ['Python', 'Neo4j', 'FastAPI'],
        e1.salary = 8500,
        e1.active = true

    MERGE (e2:NovaEmployee {emp_id: 'E002'})
    ON CREATE SET 
        e2.name = 'Bob',
        e2.joined_date = date('2024-03-01'),
        e2.skills = ['Python', 'Docker', 'Kubernetes'],
        e2.salary = 7000,
        e2.active = true

    MERGE (e3:NovaEmployee {emp_id: 'E003'})
    ON CREATE SET 
        e3.name = 'Charlie',
        e3.joined_date = date('2025-06-01'),
        e3.skills = ['Java', 'Spring', 'Kafka'],
        e3.salary = 6500,
        e3.active = true
    """)

    # 3) 프로젝트 노드 생성
    run_cypher("""
    MERGE (p1:NovaProject {proj_id: 'P01', name: 'GraphRAG System', deadline: date('2026-09-30'), budget: 50000000})
    MERGE (p2:NovaProject {proj_id: 'P02', name: 'Cloud Migration', deadline: date('2026-05-15'), budget: 30000000})
    """)

    print("✅ 팀 2개, 직원 3명, 프로젝트 2개 노드 생성 완료!")

    print("\n" + "=" * 80)
    print("🚀 [Step 3] 관계(Relationship) 연결 & 관계 속성(roles, assigned_at) 부여")
    print("=" * 80)

    # 1) 팀 배정 관계
    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E001'}), (t:NovaTeam {team_id: 'TEAM_AI'})
    MERGE (e)-[:WORKS_IN {since: 2023}]->(t)
    """)

    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E002'}), (t:NovaTeam {team_id: 'TEAM_AI'})
    MERGE (e)-[:WORKS_IN {since: 2024}]->(t)
    """)

    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E003'}), (t:NovaTeam {team_id: 'TEAM_DEV'})
    MERGE (e)-[:WORKS_IN {since: 2025}]->(t)
    """)

    # 2) 프로젝트 투입 관계 (다중 관계 및 관계 속성)
    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E001'}), (p:NovaProject {proj_id: 'P01'})
    MERGE (e)-[:ASSIGNED_TO {role: 'Architect', contribution_pct: 60}]->(p)
    """)

    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E002'}), (p:NovaProject {proj_id: 'P01'})
    MERGE (e)-[:ASSIGNED_TO {role: 'MLOps Engineer', contribution_pct: 40}]->(p)
    """)

    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E002'}), (p:NovaProject {proj_id: 'P02'})
    MERGE (e)-[:ASSIGNED_TO {role: 'Cloud Tech Lead', contribution_pct: 50}]->(p)
    """)

    print("✅ WORKS_IN 및 ASSIGNED_TO 관계선 연결 완료!")

    print("\n" + "=" * 80)
    print("🚀 [Step 4] 수정(SET) 및 삭제(REMOVE / DELETE) 문법 시연")
    print("=" * 80)

    # 1) SET: Charlie 승진 -> :NovaLead 레이블 추가 & 연봉 인상
    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E003'})
    SET e:NovaLead, e.salary = 7500, e.updated_at = date()
    """)

    # 2) REMOVE: Bob의 active 임시 속성 제거
    run_cypher("""
    MATCH (e:NovaEmployee {emp_id: 'E002'})
    REMOVE e.active
    """)

    # 검증
    charlie_info = run_cypher("MATCH (e:NovaEmployee {emp_id: 'E003'}) RETURN e.salary AS sal, labels(e) AS lbls")[0]
    assert charlie_info["sal"] == 7500, "Charlie salary mismatch!"
    assert "NovaLead" in charlie_info["lbls"], "Charlie Lead label not set!"
    print(f"🔧 수정 검증 성공: Charlie 연봉 = {charlie_info['sal']}, 레이블 = {charlie_info['lbls']}")

    print("\n" + "=" * 80)
    print("🚀 [Step 5] 조건 필터링 (WHERE 복합 조건 & date 비교)")
    print("=" * 80)

    # 2024년 1월 1일 이후 입사자 중 연봉 7000 이상인 직원 검색
    filtered = run_cypher("""
    MATCH (e:NovaEmployee)
    WHERE e.joined_date >= date('2024-01-01') AND e.salary >= 7000
    RETURN e.name AS name, e.salary AS salary, e.joined_date AS joined
    ORDER BY e.salary DESC
    """)
    print("📋 조건 검색 결과 (2024년 이후 입사 & 연봉 7000 이상):", filtered)
    assert len(filtered) == 2, f"Expected 2 rows, got {len(filtered)}"

    print("\n" + "=" * 80)
    print("🚀 [Step 6] 2-Hop 공유 허브 질의: 'Alice와 같은 팀인 동료 찾기'")
    print("=" * 80)

    # (Alice) -[:WORKS_IN]-> (Team) <-[:WORKS_IN]- (Colleague)
    colleagues = run_cypher("""
    MATCH (me:NovaEmployee {name: 'Alice'})-[:WORKS_IN]->(t:NovaTeam)<-[:WORKS_IN]-(colleague:NovaEmployee)
    RETURN me.name AS me, t.name AS team, colleague.name AS colleague
    """)
    print("🤝 2-Hop 같은 팀 동료 검색:", colleagues)
    assert len(colleagues) == 1 and colleagues[0]["colleague"] == "Bob"

    print("\n" + "=" * 80)
    print("🚀 [Step 7] 다중 프로젝트 참여 직원 검색 & DISTINCT / 파라미터($params) 바인딩")
    print("=" * 80)

    param_query = """
    MATCH (e:NovaEmployee)-[r:ASSIGNED_TO]->(p:NovaProject)
    WHERE r.contribution_pct >= $min_pct
    RETURN DISTINCT e.name AS employee_name, count(p) AS project_count
    ORDER BY project_count DESC, employee_name ASC
    """
    param_res = run_cypher(param_query, min_pct=40)
    print("📊 파라미터($min_pct=40) 질의 결과:", param_res)

    print("\n" + "=" * 80)
    print("🎉 [최종 검증] Day 29 Cypher 마스터 파이프라인 100% 무결점 통과!")
    print("=" * 80)


if __name__ == "__main__":
    main()
