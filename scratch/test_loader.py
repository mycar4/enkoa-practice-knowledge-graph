# -*- coding: utf-8 -*-
import os
import sys
import time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env")
load_dotenv("내작업폴더/.env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_cypher(query, **params):
    with driver.session() as s:
        return [r.data() for r in s.run(query, params)]

print("1. Resetting DB...")
run_cypher("MATCH (n) DETACH DELETE n")

print("2. Creating indices...")
NODE_LABELS = ["Compound", "Disease", "Gene", "Symptom", "PharmacologicClass"]
for lbl in NODE_LABELS:
    run_cypher(f"CREATE INDEX {lbl.lower()}_id IF NOT EXISTS FOR (n:{lbl}) ON (n.id)")

try:
    run_cypher("CALL db.awaitIndexes()")
except Exception as e:
    print("awaitIndexes:", e)

DATA_DIR = Path("day33_GDS_투영_중심성/data")
print("3. Loading nodes...")
nodes = {lbl: [] for lbl in NODE_LABELS}
for row in pd.read_csv(DATA_DIR / "hetionet_nodes.csv").to_dict("records"):
    nodes[row["label"]].append({"id": row["id"], "name": row["name"]})

for lbl, rows in nodes.items():
    run_cypher(f"UNWIND $rows AS row CREATE (n:{lbl}) SET n.id = row.id, n.name = row.name", rows=rows)

print("4. Loading relationships...")
REL_ENDS = {
    "TREATS": ("Compound", "Disease"),
    "PALLIATES": ("Compound", "Disease"),
    "BINDS": ("Compound", "Gene"),
    "UPREGULATES_CG": ("Compound", "Gene"),
    "DOWNREGULATES_CG": ("Compound", "Gene"),
    "ASSOCIATES": ("Disease", "Gene"),
    "UPREGULATES_DG": ("Disease", "Gene"),
    "DOWNREGULATES_DG": ("Disease", "Gene"),
    "RESEMBLES_DD": ("Disease", "Disease"),
    "RESEMBLES_CC": ("Compound", "Compound"),
    "PRESENTS": ("Disease", "Symptom"),
    "INCLUDES": ("PharmacologicClass", "Compound"),
}
edges = {rel: [] for rel in REL_ENDS}
for row in pd.read_csv(DATA_DIR / "hetionet_edges.csv").to_dict("records"):
    edges[row["rel"]].append({"s": row["source"], "t": row["target"]})

t0 = time.time()
for rel, rows in edges.items():
    src, dst = REL_ENDS[rel]
    for start in range(0, len(rows), 5000):
        run_cypher(f"UNWIND $rows AS row MATCH (a:{src} {{id: row.s}}), (b:{dst} {{id: row.t}}) CREATE (a)-[:{rel}]->(b)", rows=rows[start:start+5000])

n_cnt = run_cypher("MATCH (n) RETURN count(n) AS c")[0]["c"]
r_cnt = run_cypher("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
print(f"✅ Loaded in {time.time()-t0:.2f}s! Node count: {n_cnt:,}, Rel count: {r_cnt:,}")
