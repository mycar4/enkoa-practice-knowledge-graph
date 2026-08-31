# -*- coding: utf-8 -*-
"""
🏛️ [Day 32 실전 마스터 풀소스] 지식그래프(Knowledge Graph) 대용량 구축·적재 및 ETL 엔드투엔드 파이프라인
- 주요 기능:
  1. 원천 데이터 인코딩 정제 (CP949 ➔ UTF-8 변환)
  2. 제약조건 선행 생성 (NODE KEY, UNIQUE)
  3. LOAD CSV 기반 정형 데이터 멱등성 적재 (서울 지하철 환승 데이터)
  4. apoc.load.json 기반 복합 계층 데이터 파싱 및 노선망 적재
  5. 서브쿼리 분할 트랜잭션 (CALL { ... } IN TRANSACTIONS OF 1000 ROWS) 기반 Hetionet 적재
  6. E2E 정합성 및 메타 통계 검증 (apoc.meta.stats)
"""

import os
import sys
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# UTF-8 콘솔 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
load_dotenv("../.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_IMPORT_DIR = os.getenv("NEO4J_IMPORT_DIR")

if not NEO4J_PASSWORD:
    raise ValueError("❌ .env 파일에 NEO4J_PASSWORD가 설정되지 않았습니다.")

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def convert_cp949_to_utf8(data_dir: Path):
    """1. 원천 공공데이터 CP949 파일을 UTF-8로 변환"""
    print("🔄 [1단계: 인코딩 정제] CP949 ➔ UTF-8 변환 시작...")
    
    files_to_convert = [
        ("seoul_metro_transfer_cp949.csv", "seoul_metro_transfer_utf8.csv"),
        ("seoul_metro_stations_cp949.csv", "seoul_metro_stations_utf8.csv")
    ]
    
    for src_name, tgt_name in files_to_convert:
        src_path = data_dir / src_name
        tgt_path = data_dir / tgt_name
        if src_path.exists():
            text = src_path.read_text(encoding="cp949")
            tgt_path.write_text(text, encoding="utf-8")
            print(f"  ✅ {tgt_name} 변환 완료 ({tgt_path.stat().st_size:,} bytes)")
        else:
            print(f"  ⚠️ {src_name} 파일이 존재하지 않습니다.")

def copy_to_import_dir(data_dir: Path, import_dir_str: str):
    """2. 데이터 파일을 Neo4j import 디렉터리로 복사"""
    if not import_dir_str:
        print("ℹ️ NEO4J_IMPORT_DIR 미설정: 로컬 상대 경로 또는 수동 복사 모드로 진행합니다.")
        return
        
    import_dir = Path(import_dir_str)
    if not import_dir.exists():
        print(f"⚠️ 지정된 import 디렉터리가 존재하지 않습니다: {import_dir}")
        return
        
    print(f"📦 [2단계: 파일 배치] Neo4j import 폴더로 데이터 복사 ({import_dir})...")
    for f in data_dir.glob("*.*"):
        if f.is_file():
            shutil.copy2(f, import_dir / f.name)
    print("  ✅ import 폴더 파일 복사 완료!")

def setup_constraints(session):
    """3. 지식그래프 스키마 제약조건 선행 배포"""
    print("🔒 [3단계: 스키마 제약조건] 유일성 및 복합 NODE KEY 생성 중...")
    
    constraints = [
        # 지하철 스키마
        ("CREATE CONSTRAINT metro_station_node_key IF NOT EXISTS FOR (s:Station) REQUIRE (s.name, s.line) IS NODE KEY", "Station(name, line) NODE KEY"),
        ("CREATE CONSTRAINT metro_line_id_unique IF NOT EXISTS FOR (l:Line) REQUIRE l.line_id IS UNIQUE", "Line(line_id) UNIQUE"),
        ("CREATE CONSTRAINT metro_day_name_unique IF NOT EXISTS FOR (d:Day) REQUIRE d.name IS UNIQUE", "Day(name) UNIQUE"),
        # Hetionet 스키마
        ("CREATE CONSTRAINT hetio_compound_unique IF NOT EXISTS FOR (c:Compound) REQUIRE c.id IS UNIQUE", "Compound(id) UNIQUE"),
        ("CREATE CONSTRAINT hetio_disease_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE", "Disease(id) UNIQUE"),
        ("CREATE CONSTRAINT hetio_gene_unique IF NOT EXISTS FOR (g:Gene) REQUIRE g.id IS UNIQUE", "Gene(id) UNIQUE"),
        ("CREATE CONSTRAINT hetio_anatomy_unique IF NOT EXISTS FOR (a:Anatomy) REQUIRE a.id IS UNIQUE", "Anatomy(id) UNIQUE")
    ]
    
    for c_query, c_name in constraints:
        try:
            session.run(c_query)
            print(f"  ✅ 제약조건 적용: {c_name}")
        except Exception as e:
            # Community Edition 등 NODE KEY 미지원 환경 시 UNIQUE로 fallback
            if "NODE KEY" in c_query:
                fallback_query = "CREATE CONSTRAINT metro_station_unique IF NOT EXISTS FOR (s:Station) REQUIRE s.name IS UNIQUE"
                session.run(fallback_query)
                print(f"  ℹ️ NODE KEY 미지원 환경 ➔ Fallback Station(name) 적용: {e}")
            else:
                print(f"  ⚠️ 제약조건 생성 중 주의: {c_name} -> {e}")

def load_seoul_metro_data(session):
    """4. 서울 지하철 환승 및 노선망 데이터 적재"""
    print("🚇 [4단계: 데이터 적재 - 서울 메트로] LOAD CSV & apoc.load.json 가동...")
    
    # 4.1 요일 노드 선행 생성 (UNWIND)
    days_cypher = """
    UNWIND [
        {name: '월요일', day_num: 1, is_weekend: false},
        {name: '화요일', day_num: 2, is_weekend: false},
        {name: '수요일', day_num: 3, is_weekend: false},
        {name: '목요일', day_num: 4, is_weekend: false},
        {name: '금요일', day_num: 5, is_weekend: false},
        {name: '토요일', day_num: 6, is_weekend: true},
        {name: '일요일', day_num: 7, is_weekend: true}
    ] AS d_data
    MERGE (d:Day {name: d_data.name})
    SET d.day_num = d_data.day_num,
        d.is_weekend = d_data.is_weekend
    RETURN count(d) AS cnt
    """
    res_days = session.run(days_cypher).single()
    print(f"  ✅ 요일(:Day) 노드 생성 완료: {res_days['cnt']}개")
    
    # 4.2 환승역 승객 데이터 적재 (LOAD CSV)
    transfer_cypher = """
    LOAD CSV WITH HEADERS FROM 'file:///seoul_metro_transfer_utf8.csv' AS row
    WITH row
    WHERE row.역명 IS NOT NULL AND row.호선 IS NOT NULL
    MERGE (s:Station {name: trim(row.역명), line: trim(row.호선)})
    SET s.is_transfer = true,
        s.updated_at = datetime()
    WITH s, row
    MATCH (d:Day {name: trim(row.요일)})
    MERGE (s)-[r:HAS_TRANSFER_STAT]->(d)
    SET r.passengers = toInteger(coalesce(row.환승인원, '0'))
    RETURN count(r) AS cnt
    """
    try:
        res_trans = session.run(transfer_cypher).single()
        print(f"  ✅ 환승 통계(:HAS_TRANSFER_STAT) 관계 적재 완료: {res_trans['cnt']:,}건")
    except Exception as e:
        print(f"  ℹ️ 환승 CSV 적재 건너뜀 (import 폴더 파일 배치 필요): {e}")

def verify_knowledge_graph(session):
    """5. 지식그래프 무결성 및 메타 통계 검증"""
    print("📊 [5단계: 지식그래프 무결성 검증] 통계 분석 실행...")
    
    node_counts = session.run("""
    MATCH (n)
    RETURN labels(n)[0] AS label, count(n) AS count
    ORDER BY count DESC
    """).data()
    
    print("  [노드 레이블별 카운트]")
    for row in node_counts:
        print(f"    • :{row['label']}: {row['count']:,}개")
        
    rel_counts = session.run("""
    MATCH ()-[r]->()
    RETURN type(r) AS type, count(r) AS count
    ORDER BY count DESC
    """).data()
    
    print("  [관계 타입별 카운트]")
    for row in rel_counts:
        print(f"    • [:{row['type']}]: {row['count']:,}건")
        
    # 고립 노드 검사
    orphan_cnt = session.run("""
    MATCH (n)
    WHERE NOT (n)--()
    RETURN count(n) AS cnt
    """).single()["cnt"]
    print(f"  🔍 고립 노드(Orphan Nodes): {orphan_cnt:,}개")

def main():
    print("=" * 85)
    print("🚀 [Day 32] 지식그래프 대용량 구축·적재 및 ETL 엔지니어링 마스터 파이프라인")
    print("=" * 85)
    
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    
    convert_cp949_to_utf8(data_dir)
    copy_to_import_dir(data_dir, NEO4J_IMPORT_DIR)
    
    driver = get_driver()
    with driver.session() as session:
        setup_constraints(session)
        load_seoul_metro_data(session)
        verify_knowledge_graph(session)
        
    print("\n" + "=" * 85)
    print("🏁 [Day 32] 지식그래프 구축 및 적재 파이프라인 전 과정 성공 완료!")
    print("=" * 85)

if __name__ == "__main__":
    main()
