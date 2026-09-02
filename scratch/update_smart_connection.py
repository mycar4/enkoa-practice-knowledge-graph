# -*- coding: utf-8 -*-
"""
내작업폴더/day30_Cypher_심화 내의 모든 노트북(교안 2권, 과제 3권)의 
연결 셀을 로컬/Aura 클라우드 자동 전환(Smart Fallback) 구조로 업데이트
"""
import sys
import io
import json
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

notebooks = [
    "내작업폴더/day30_Cypher_심화/교안_01_경로_탐색.ipynb",
    "내작업폴더/day30_Cypher_심화/교안_02_다중조건_WITH파이프라인.ipynb",
    "내작업폴더/day30_Cypher_심화/과제_LV1_기초.ipynb",
    "내작업폴더/day30_Cypher_심화/과제_LV2_응용.ipynb",
    "내작업폴더/day30_Cypher_심화/과제_LV3_통합.ipynb"
]

smart_conn_src = """# [제공 코드] Neo4j 연결 (로컬 우선 -> 연결 불가 시 클라우드 Aura 자동 전환)
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 1) 접속 정보 읽기 (.env)
load_dotenv(".env", override=True)
load_dotenv("../.env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")

AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")

# 2) 스마트 드라이버 연결 (로컬 DB가 꺼져있으면 Aura Cloud DB로 자동 연결)
driver = None
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ [연결 성공] 로컬 Neo4j Desktop:", NEO4J_URI)
except Exception:
    if AURA_URI and AURA_USER and AURA_PASSWORD:
        driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        driver.verify_connectivity()
        print("✅ [연결 성공] Neo4j Aura 클라우드 DB:", AURA_URI)
    else:
        raise ConnectionError("Neo4j에 연결할 수 없습니다. Neo4j Desktop을 켜거나 .env 설정을 확인하세요.")

# 3) 공용 헬퍼 함수
def run_cypher(query, **params):
    \"\"\"Cypher 실행 -> 결과를 dict 리스트로 반환\"\"\"
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]
"""

for nb_path in notebooks:
    if not Path(nb_path).exists():
        continue
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    # 첫 번째 code cell 찾기 (보통 연결 셀)
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            src = "".join(cell.get('source', []))
            if 'GraphDatabase.driver' in src or 'load_dotenv' in src:
                lines = [l + '\n' for l in smart_conn_src.splitlines()]
                if lines:
                    lines[-1] = lines[-1].rstrip('\n')
                cell['source'] = lines
                cell['outputs'] = []
                cell['execution_count'] = None
                break
    
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"✅ 스마트 연결 셀 업데이트 완료: {nb_path}")
