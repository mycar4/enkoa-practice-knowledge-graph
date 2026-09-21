# -*- coding: utf-8 -*-
"""
🌲 [미술 실기 입시 도우미] RAPTOR 재귀 요약 트리 빌더
================================================================================
day46 교안_02(재귀요약_RAPTOR) 반영. 리프 청크(Admission_TextChunk)를 임베딩
기준으로 KMeans 클러스터링 -> 클러스터별 LLM 요약(L1) -> L1을 다시 클러스터링
-> 요약(L2) 순으로 2단 트리를 만든다. "이 학교 절차 전체를 훑어야 답이 나오는"
넓은 질문(예: "미술활동보고서 전체 절차를 요약해줘")에 낱개 청크 검색으로는
답이 안 되는 문제를 메운다 - 개별 사실 질문은 기존 hybrid_search/auto_merge가
이미 더 정확하므로 이 트리는 "요약/전체 흐름" 질문에만 보조로 쓰인다.

비용 원칙: 요약은 새 사실을 만드는 게 아니라 이미 있는 원문을 압축하는 작업이라
gpt-4o-mini(저렴한 모델)로 충분하다 - 02_Entity_Linker.py에서 추론 모델(gpt-5.6-luna)을
무분별하게 써서 비용 사고가 났던 전례가 있으므로, 이 스크립트는 모델을 하드코딩하고
바꾸려면 코드를 직접 고치게 한다(실수로 비싼 모델이 섞여 들어가는 걸 막기 위함).

기본 DRY-RUN(클러스터 구성/예상 토큰만 출력), --commit 시에만 실제 LLM 호출 + 적재.
================================================================================
"""
import os
import sys
import argparse
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(REPO_ROOT / ".env")

from services.art_admission_llm import embed_text, _call_llm  # noqa: E402

uri = os.getenv("ART_ADMISSION_NEO4J_URI") or os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("ART_ADMISSION_NEO4J_USER") or os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("ART_ADMISSION_NEO4J_PASSWORD") or os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(uri, auth=(user, pwd))

# 절대 바꾸지 말 것 - 위 docstring 참고(비싼 추론 모델 오용 방지).
SUMMARY_MODEL = "gpt-4o-mini"

# 클러스터당 평균 리프 5~8개 목표 (day46 교안 관례). L2는 L1을 다시 5개 안팎으로 묶는다.
_LEAVES_PER_CLUSTER = 6
_L1_PER_L2_CLUSTER = 5

_SUMMARY_SYSTEM_PROMPT = """당신은 대학 입시요강 원문 발췌 여러 개를 하나로 요약하는
도우미입니다. 아래 발췌문들은 모두 같은 대학의 관련된 절차/규정에서 나온 것입니다.
- 발췌문에 실제로 있는 내용만 요약하십시오. 없는 숫자·날짜·절차를 지어내지 마십시오.
- 어느 발췌문 하나만의 세부사항이 아니라, 여러 발췌문을 관통하는 공통 절차/주제를
  중심으로 5~8문장 이내로 간결하게 요약하십시오.
- 특정 대학명이 나오면 유지하되, "이 대학은" 같은 모호한 지칭 대신 실제 이름을 쓰십시오."""


def _summarize_cluster(texts: list) -> str:
    joined = "\n\n---\n\n".join(texts)
    return _call_llm(_SUMMARY_SYSTEM_PROMPT, f"발췌문들:\n\n{joined}", model_id=SUMMARY_MODEL)


def _cluster(vectors: np.ndarray, target_per_cluster: int, seed: int = 42):
    n = len(vectors)
    k = max(1, round(n / target_per_cluster))
    if k >= n:
        # 노드 수가 너무 적어 클러스터링이 무의미하면 전부 한 클러스터로 묶는다.
        return np.zeros(n, dtype=int), 1
    km = KMeans(n_clusters=k, n_init=5, random_state=seed).fit(vectors)
    return km.labels_, k


def ensure_raptor_index():
    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        s.run("""
            CREATE VECTOR INDEX admission_raptor_embedding IF NOT EXISTS
            FOR (n:Admission_RaptorNode) ON (n.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)
        s.run("""
            CREATE FULLTEXT INDEX admission_raptor_fulltext IF NOT EXISTS
            FOR (n:Admission_RaptorNode) ON EACH [n.text]
        """)


def build_for_university(university: str, commit: bool):
    with driver.session(default_access_mode=READ_ACCESS) as s:
        leaves = s.run("""
            MATCH (c:Admission_TextChunk {university: $university})
            RETURN elementId(c) AS eid, c.text AS text, c.embedding AS embedding
        """, university=university).data()
    if not leaves:
        print(f"[{university}] 리프 청크가 없습니다 - 색인을 먼저 하십시오.")
        return

    leaf_vecs = np.array([l["embedding"] for l in leaves])
    labels1, k1 = _cluster(leaf_vecs, _LEAVES_PER_CLUSTER)
    clusters1 = {}
    for i, lab in enumerate(labels1):
        clusters1.setdefault(lab, []).append(leaves[i])

    print(f"[{university}] 리프 {len(leaves)}개 -> L1 클러스터 {k1}개 "
          f"(평균 {len(leaves)/k1:.1f}개/클러스터)")

    if not commit:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        total_in = sum(len(enc.encode("\n\n---\n\n".join(m["text"] for m in members))) + 150
                       for members in clusters1.values())
        print(f"[DRY-RUN] L1 요약 입력 토큰(실측): {total_in} "
              f"(모델={SUMMARY_MODEL}, 실제 호출/적재는 --commit 필요)")
        return

    # --- L1 요약 생성 + 임베딩 + 적재 ---
    l1_nodes = []  # {"text":..., "embedding":..., "leaf_eids":[...]}
    for lab, members in clusters1.items():
        summary = _summarize_cluster([m["text"] for m in members])
        vec = embed_text(summary)
        l1_nodes.append({"text": summary, "embedding": vec, "leaf_eids": [m["eid"] for m in members]})
        print(f"  L1 클러스터 {lab} ({len(members)}개 리프) 요약 완료 ({len(summary)}자)")

    # --- L2: L1 요약을 다시 클러스터링 + 요약 ---
    l1_vecs = np.array([n["embedding"] for n in l1_nodes])
    labels2, k2 = _cluster(l1_vecs, _L1_PER_L2_CLUSTER)
    clusters2 = {}
    for i, lab in enumerate(labels2):
        clusters2.setdefault(lab, []).append(l1_nodes[i])

    l2_nodes = []
    for lab, members in clusters2.items():
        summary = _summarize_cluster([m["text"] for m in members])
        vec = embed_text(summary)
        l2_nodes.append({"text": summary, "embedding": vec, "l1_members": members})
        print(f"  L2 클러스터 {lab} ({len(members)}개 L1) 요약 완료 ({len(summary)}자)")

    # --- Neo4j 적재: 기존 트리 삭제 후 재생성(멱등) ---
    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        s.run("MATCH (n:Admission_RaptorNode {university: $university}) DETACH DELETE n",
              university=university)
        for l1_idx, node in enumerate(l1_nodes):
            s.run("""
                CREATE (n:Admission_RaptorNode {
                    university: $university, level: 1, cluster_id: $cid,
                    text: $text, embedding: $embedding
                })
                WITH n
                UNWIND $leaf_eids AS eid
                MATCH (c) WHERE elementId(c) = eid
                CREATE (n)-[:SUMMARIZES]->(c)
            """, university=university, cid=l1_idx, text=node["text"],
                 embedding=node["embedding"], leaf_eids=node["leaf_eids"])
        for l2_idx, node in enumerate(l2_nodes):
            l1_texts = [m["text"] for m in node["l1_members"]]
            s.run("""
                CREATE (n:Admission_RaptorNode {
                    university: $university, level: 2, cluster_id: $cid,
                    text: $text, embedding: $embedding
                })
                WITH n
                UNWIND $l1_texts AS l1t
                MATCH (c:Admission_RaptorNode {university: $university, level: 1, text: l1t})
                CREATE (n)-[:SUMMARIZES]->(c)
            """, university=university, cid=l2_idx, text=node["text"],
                 embedding=node["embedding"], l1_texts=l1_texts)
    print(f"[커밋 완료] {university}: L1 {len(l1_nodes)}개 + L2 {len(l2_nodes)}개 RAPTOR 노드 색인")


def main():
    parser = argparse.ArgumentParser(description="art_admission RAPTOR 재귀요약 트리 빌더")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--university", required=True)
    args = parser.parse_args()
    if args.commit:
        ensure_raptor_index()
    build_for_university(args.university, commit=args.commit)


if __name__ == "__main__":
    main()
