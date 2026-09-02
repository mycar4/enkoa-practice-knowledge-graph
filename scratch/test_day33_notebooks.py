# -*- coding: utf-8 -*-
"""
Day 33 과제 LV1, LV2, LV3 노트북 셀 순차 실행 및 전체 자가채점 100% 자동 검증기
"""
import os
import sys
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
load_dotenv("내작업폴더/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, params)]

def run_notebook(nb_path):
    print(f"\n🧪 [{nb_path}] 전체 셀 순차 실행 및 채점 검증 시작...")
    orig_cwd = os.getcwd()
    nb_dir = os.path.dirname(os.path.abspath(nb_path))
    os.chdir(nb_dir)
    try:
        with open(os.path.basename(nb_path), "r", encoding="utf-8") as f:
            nb = json.load(f)

        ns = {
            "os": os,
            "sys": sys,
            "driver": driver,
            "run_cypher": run_cypher,
            "__builtins__": __builtins__
        }

        exec("""
import pandas as pd
from neo4j import GraphDatabase
def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, params)]
""", ns)

        passed_tests = 0
        total_tests = 0

        for idx, cell in enumerate(nb["cells"]):
            if cell["cell_type"] == "code":
                code = "".join(cell["source"]).strip()
                if not code:
                    continue
                if "[자가채점]" in code:
                    total_tests += 1
                try:
                    exec(code, ns)
                    if "[자가채점]" in code:
                        passed_tests += 1
                except Exception as e:
                    print(f"❌ Cell {idx} 실행 오류:\n{code[:200]}\n에러: {e}")
                    raise e

        print(f"🏆 [{nb_path}] 자가채점 결과: {passed_tests}/{total_tests} 전원 PASS ✅")
    finally:
        os.chdir(orig_cwd)

if __name__ == "__main__":
    run_notebook("내작업폴더/day33_GDS_투영_중심성/과제_LV1_기초.ipynb")
    run_notebook("내작업폴더/day33_GDS_투영_중심성/과제_LV2_응용.ipynb")
    run_notebook("내작업폴더/day33_GDS_투영_중심성/과제_LV3_통합.ipynb")
