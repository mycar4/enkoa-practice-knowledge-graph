# -*- coding: utf-8 -*-
"""
🔗 [미술 실기 입시 도우미] 파생 관계(엣지) 배치 구축 - COMPATIBLE_WITH / SIMILAR_TO
================================================================================
그동안 "이 전형이랑 같은 실기로 지원 가능한 곳"(find_compatible_tracks)과 "이
학과랑 커리큘럼이 비슷한 학과"(find_similar_departments)는 사용자가 질문할
때마다 그 자리에서 즉석 계산했다. 이 스크립트는 그 계산을 딱 한 번(배치)
전체 조합에 대해 미리 해두고, 결과를 그래프의 진짜 관계(엣지)로 저장한다.

왜 이게 지식그래프의 핵심 차별화인가: RDB라면 이런 "계산된 다대다 관계"를
저장하려면 별도 조인 테이블 설계 + 매번 재계산 배치가 필요하지만, 그래프는
그냥 엣지 하나 추가하는 것으로 끝난다. 그리고 한 번 저장해두면 그 뒤의 모든
질문은 "즉석 계산"이 아니라 "이미 확인된 그래프 순회"가 되어, 계산 비용도
없고 LLM이 university/department 인자를 잘못 넣는 것 같은 실수(2026-09-18
실측 버그)도 구조적으로 없어진다.

두 계산 모두 LLM을 전혀 쓰지 않는다(결정론적 텍스트 매칭 + 코사인 유사도) -
02번 스크립트(엔티티 추출)가 겪은 "검증 안 된 관계가 섞이는" 오염 문제를
반복하지 않도록, 두 관계 모두 원본이 공식 모집요강 JSON(Admission_Track/
Admission_Department, official_facts.source_url 검증을 이미 통과한 데이터)
이지 LLM이 뽑은 엔티티가 아니다.

1. COMPATIBLE_WITH (Admission_Track - Admission_Track)
   서비스 함수 find_compatible_tracks()와 완전히 동일한 로직(정규화된 실기종목
   키워드 + 재료 키워드 겹침)을 전체 트랙 쌍(다른 대학끼리만)에 대해 수행한다.
   속성: shared_keywords, shared_materials, match_type("exact"|"partial")

2. SIMILAR_TO (Admission_Department - Admission_Department)
   서비스 함수 find_similar_departments()와 같은 원리(표준 계열 태그가 같은
   학과들 안에서만 커리큘럼 임베딩 코사인 유사도 비교) - 태그 안에서 실측
   분포(2026-09-18, 2,198쌍)를 확인한 결과 상위 약 22%(유사도 0.70 이상)만
   의미 있는 신호로 보고 그 이상만 저장한다(전부 저장하면 최저 0.33까지도
   섞여 순수 잡음이 관계로 박제된다). 속성: similarity_pct

둘 다 기본 DRY-RUN(개수만 출력), --commit 시에만 실제 MERGE.
재실행해도 안전(idempotent) - MERGE 키가 트랙/학과 쌍이라 중복 생성 안 됨.
데이터가 갱신되면(신규 학교/연도) 이 스크립트를 다시 돌리면 최신 상태로 갱신된다.
================================================================================
"""
import os
import re
import sys
import argparse
from pathlib import Path
from itertools import combinations

import numpy as np
from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env")

from services.art_admission_service import ArtAdmissionService  # noqa: E402

# 실측(2026-09-18)으로 정한 컷 - 태그 내 서로 다른 대학 쌍 2,198건 중 0.70 이상은
# 491건(상위 약 22%). 0.9 이상은 0건이라 그보다 낮춰서 유의미한 상위권만 취함.
SIMILARITY_THRESHOLD = 0.70


def build_compatible_tracks(svc: ArtAdmissionService, driver, commit: bool):
    tracks = svc.list_all_tracks_full()
    canonical_topics = svc.list_kg_topic_keywords(min_schools=1)

    prepared = []
    for t in tracks:
        exam_name = t.get("exam_type_name") or ""
        topics = {kw for kw in canonical_topics if ArtAdmissionService._topic_keyword_matches(kw, exam_name)}
        materials = ArtAdmissionService._material_keywords(t.get("allowed_materials"))
        prepared.append({**t, "_topics": topics, "_materials": materials})

    edges = []
    for a, b in combinations(prepared, 2):
        if a["university"] == b["university"]:
            continue
        if not a.get("exam_type_name") or not b.get("exam_type_name"):
            continue
        shared_kw = a["_topics"] & b["_topics"]
        shared_mat = a["_materials"] & b["_materials"]
        if not shared_kw and not shared_mat:
            continue
        edges.append({
            "u1": a["university"], "d1": a["department"], "t1": a["track_name"],
            "u2": b["university"], "d2": b["department"], "t2": b["track_name"],
            "shared_keywords": sorted(shared_kw), "shared_materials": sorted(shared_mat),
            "match_type": "exact" if shared_kw else "partial",
        })

    print(f"[COMPATIBLE_WITH] 전체 트랙 {len(tracks)}개 중 {len(list(combinations(tracks, 2)))}쌍 검토 -> {len(edges)}건 관계 발견")
    exact = sum(1 for e in edges if e["match_type"] == "exact")
    print(f"  - exact(실기유형 자체 일치): {exact}건 / partial(재료만 겹침): {len(edges) - exact}건")

    if not commit:
        print("  (DRY-RUN - 실제 저장 안 함, --commit으로 재실행하면 저장)")
        return len(edges)

    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        # 재실행 시 옛 관계(오래된 exam_type_name 변경분 등)를 먼저 걷어내고 다시 채운다.
        s.run("MATCH ()-[r:COMPATIBLE_WITH]-() DELETE r")
        for i in range(0, len(edges), 300):
            batch = edges[i:i + 300]
            s.run("""
                UNWIND $rows AS row
                MATCH (t1:Admission_Track {name: row.t1, university: row.u1, department: row.d1})
                MATCH (t2:Admission_Track {name: row.t2, university: row.u2, department: row.d2})
                MERGE (t1)-[r:COMPATIBLE_WITH]->(t2)
                SET r.shared_keywords = row.shared_keywords, r.shared_materials = row.shared_materials,
                    r.match_type = row.match_type, r.computed_at = date()
            """, rows=batch)
            print(f"  저장 {min(i+300, len(edges))}/{len(edges)}")
    print("[커밋 완료] COMPATIBLE_WITH")
    return len(edges)


def build_similar_departments(svc: ArtAdmissionService, driver, commit: bool):
    with driver.session(default_access_mode=READ_ACCESS) as s:
        rows = s.run("""
            MATCH (u:Admission_University)-[:HAS_DEPARTMENT]->(d:Admission_Department)
            WHERE d.embedding IS NOT NULL AND d.standard_tag IS NOT NULL
            RETURN u.name AS university, d.name AS department, d.standard_tag AS tag, d.embedding AS emb
        """).data()

    by_tag = {}
    for r in rows:
        by_tag.setdefault(r["tag"], []).append(r)

    edges = []
    total_pairs = 0
    for tag, items in by_tag.items():
        vecs = np.array([it["emb"] for it in items])
        norm = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        sim = norm @ norm.T
        n = len(items)
        for i, j in combinations(range(n), 2):
            if items[i]["university"] == items[j]["university"]:
                continue
            total_pairs += 1
            score = float(sim[i, j])
            if score < SIMILARITY_THRESHOLD:
                continue
            edges.append({
                "u1": items[i]["university"], "d1": items[i]["department"],
                "u2": items[j]["university"], "d2": items[j]["department"],
                "similarity_pct": round(score * 100, 1), "standard_tag": tag,
            })

    print(f"[SIMILAR_TO] 태그 내 서로 다른 대학 학과쌍 {total_pairs}건 검토 (임계값 {SIMILARITY_THRESHOLD}) -> {len(edges)}건 관계 발견")

    if not commit:
        print("  (DRY-RUN - 실제 저장 안 함, --commit으로 재실행하면 저장)")
        return len(edges)

    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        s.run("MATCH ()-[r:SIMILAR_TO]-() DELETE r")
        for i in range(0, len(edges), 300):
            batch = edges[i:i + 300]
            s.run("""
                UNWIND $rows AS row
                MATCH (d1:Admission_Department {name: row.d1, university: row.u1})
                MATCH (d2:Admission_Department {name: row.d2, university: row.u2})
                MERGE (d1)-[r:SIMILAR_TO]->(d2)
                SET r.similarity_pct = row.similarity_pct, r.standard_tag = row.standard_tag, r.computed_at = date()
            """, rows=batch)
            print(f"  저장 {min(i+300, len(edges))}/{len(edges)}")
    print("[커밋 완료] SIMILAR_TO")
    return len(edges)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    svc = ArtAdmissionService()
    driver = svc.driver
    try:
        n1 = build_compatible_tracks(svc, driver, args.commit)
        n2 = build_similar_departments(svc, driver, args.commit)
        print(f"\n총 신규 관계: COMPATIBLE_WITH {n1}건 + SIMILAR_TO {n2}건 = {n1+n2}건")
    finally:
        svc.close()
