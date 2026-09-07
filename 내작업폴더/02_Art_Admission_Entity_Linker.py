# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] LLM 기반 개체 추출(MENTIONS) + PageRank/커뮤니티 + 커뮤니티 요약
================================================================================
- 이전 버전은 day36 교안의 "이름 매칭으로 MENTIONS 연결하는 거친 방법"을 그대로
  재현해 오매칭(false positive)을 일부러 남겼다. 이 버전은 그 뒤에 오는 개선 단계
  까지 포함해서, 실제 서비스에 쓸 수 있는 정확도로 다시 만든다:
    1. 구조화 LLM 추출 (surface / canonical / type / confidence)
    2. 원문 검증(origin-text verification): LLM이 뽑은 surface가 실제로 그 청크
       본문에 문자 그대로 있는지 확인 - 없으면 그 자리에서 버린다 (환각 방지).
    3. 신뢰도 필터링: confidence < CONFIDENCE_THRESHOLD 인 항목은 버린다.
    4. 사전 개체(university/department/exam_type/material)는 canonical로 정규화해
       기존 구조화 데이터의 노드와 그대로 합쳐지고, 사전에 없는 새 개체는
       "llm_discovered=true"로 별도 표시해 추가한다 (Other 타입 캐치올).
- 그 위에 PageRank(networkx 로컬 계산 - 이 Aura 티어는 GDS 세션이 유료라 못 씀)와
  Louvain 커뮤니티를 얹고, 각 커뮤니티에는 LLM 한 번씩 호출해 짧은 한글 라벨을
  붙인다(GraphRAG 스타일 커뮤니티 요약) - 그래프 화면에서 "이 덩어리가 뭔지"
  바로 알아볼 수 있게.
- 청크 1000개+ 라서 순차 호출은 비현실적 - ThreadPoolExecutor로 동시 호출한다.
- 기본 DRY-RUN(개수만 출력), --commit 시에만 실제 적재. --limit N으로 청크 수를
  제한해 비용/시간을 통제하며 테스트할 수 있다.
================================================================================
"""

import os
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from neo4j import GraphDatabase, WRITE_ACCESS, READ_ACCESS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from services.art_admission_llm import _call_llm  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

EXTRACTION_MODEL = "gpt-4o-mini"  # 저렴하고 충분히 정확 - 1000개+ 청크 배치 추출에 적합
CONFIDENCE_THRESHOLD = 0.5
MAX_WORKERS = 8  # OpenAI 레이트리밋 감안한 동시 호출 수
ALLOWED_CANON_TYPES = {"university", "department", "exam_type", "material"}

_EXTRACTION_SYSTEM_PROMPT = """당신은 미술 실기 입시 도우미의 개체명 추출기입니다.
아래 "알려진 개체 목록"과 본문 발췌를 보고, 본문에 실제로 등장하는 미술 실기 입시
관련 개체를 뽑아 JSON으로만 응답하십시오. 다른 말은 절대 덧붙이지 마십시오.

규칙:
1. surface: 본문에 실제로 그대로 등장하는 표기(부분 문자열로 검증할 것이므로
   본문에 없는 표현을 지어내면 안 됩니다).
2. canonical: "알려진 개체 목록"에 있는 개념과 같은 것이면 그 목록의 표기 그대로
   씁니다(동의어/줄임말이어도 개념이 같으면 매칭). 목록에 없는 새로운 개체(예:
   구체적인 평가기준 용어, 전형 방식 명칭, 특정 도구/기법 등 입시에 실질적으로
   의미 있는 개체)라면 canonical에 surface와 같은 값을 쓰고 is_new: true로 표시.
   본문에 흔한 일반 단어(예: "그리고", "학생")는 절대 개체로 뽑지 마십시오.
3. type: university | department | exam_type | material | other 중 하나.
   목록에 없는 새 개체는 그 개체의 성격을 짧은 한글로 type에 적어도 됩니다
   (예: "평가기준", "전형방식").
4. confidence: 이 매칭이 정확하다는 확신을 0.0~1.0으로 자기 평가.
5. 형식: {"entities": [{"surface": "...", "canonical": "...", "type": "...",
   "is_new": false, "confidence": 0.9}, ...]}
6. 본문에 관련 개체가 하나도 없으면 {"entities": []} 로 응답하십시오.
"""


def build_entity_dictionary(driver):
    """구조화 데이터(University/Department/ExamType/재료)에서 canonical 개체 사전을 뽑는다.
    이미 검증된 값이므로 개체명 자체는 정확하다 - LLM에게는 이 사전과 매칭시키라고
    지시해서 동의어/표기 차이를 흡수시킨다."""
    entities = {}  # name -> type
    with driver.session(default_access_mode=READ_ACCESS) as s:
        for row in s.run("MATCH (u:Admission_University) RETURN DISTINCT u.name AS name"):
            if row["name"]:
                entities[row["name"]] = "university"
        for row in s.run("""
            MATCH (t:Admission_Track) WHERE t.is_superseded IS NULL OR t.is_superseded = false
            MATCH (d:Admission_Department)-[:HAS_TRACK]->(t)
            RETURN DISTINCT d.name AS name
        """):
            if row["name"]:
                entities[row["name"]] = "department"
        for row in s.run("""
            MATCH (t:Admission_Track)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
            WHERE t.is_superseded IS NULL OR t.is_superseded = false
            RETURN DISTINCT e.name AS name
        """):
            if row["name"]:
                entities[row["name"]] = "exam_type"
        for row in s.run("""
            MATCH (t:Admission_Track)-[:REQUIRES_EXAM]->(e:Admission_ExamType)
            WHERE t.is_superseded IS NULL OR t.is_superseded = false
            UNWIND e.allowed_materials AS m
            RETURN DISTINCT m AS name
        """):
            if row["name"]:
                entities[row["name"]] = "material"
    return entities


def extract_entities_llm(chunk_text: str, known_entities: dict) -> list:
    """청크 1건에 대해 LLM 구조화 추출 + 원문검증 + 신뢰도필터를 수행한다.
    반환: [{"name": canonical, "type": type, "is_new": bool}, ...] (신뢰도/검증 통과분만)"""
    listing = ", ".join(sorted(known_entities.keys()))
    user_prompt = f"알려진 개체 목록: {listing}\n\n본문 발췌:\n{chunk_text[:2000]}"
    try:
        raw = _call_llm(_EXTRACTION_SYSTEM_PROMPT, user_prompt, EXTRACTION_MODEL, temperature=0.0)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        raw_entities = parsed.get("entities", [])
    except Exception as e:
        return []  # 실패한 청크는 조용히 스킵 (호출부에서 실패 건수 집계)

    result = []
    seen = set()
    for item in raw_entities:
        surface = (item.get("surface") or "").strip()
        canonical = (item.get("canonical") or surface).strip()
        conf = item.get("confidence", 0)
        if not surface or not canonical:
            continue
        # 원문검증: LLM이 지어낸 게 아니라 실제 본문에 있는 표현인지 확인
        if surface not in chunk_text:
            continue
        if not isinstance(conf, (int, float)) or conf < CONFIDENCE_THRESHOLD:
            continue
        # 알려진 사전에 있는 개념이면 사전 표기로 정규화, 아니면 LLM이 준 type을 그대로 씀
        if canonical in known_entities:
            etype = known_entities[canonical]
            is_new = False
        else:
            etype = (item.get("type") or "other").strip() or "other"
            is_new = True
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append({"name": canonical, "type": etype, "is_new": is_new})
    return result


_COMMUNITY_LABEL_SYSTEM_PROMPT = """다음은 그래프에서 자주 함께 언급되는(동시출현) 개체명
묶음입니다. 이 묶음을 대표하는 아주 짧은 한글 라벨(10자 이내, 예: "회화 계열 실기",
"서류/면접 전형")을 하나만 응답하십시오. 다른 말은 절대 덧붙이지 마십시오."""


def label_community_llm(names: list) -> str:
    try:
        raw = _call_llm(_COMMUNITY_LABEL_SYSTEM_PROMPT, ", ".join(names[:15]), EXTRACTION_MODEL, temperature=0.0)
        return raw.strip().strip('"').strip("'")[:30]
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="LLM 기반 개체 추출(MENTIONS) + PageRank/커뮤니티")
    parser.add_argument("--commit", action="store_true", help="실제 적재 (미지정 시 DRY-RUN)")
    parser.add_argument("--limit", type=int, default=0, help="처리할 청크 수 제한 (0=전체, 테스트용)")
    args = parser.parse_args()

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        known_entities = build_entity_dictionary(driver)
        print(f"알려진(사전) 개체명: {len(known_entities)}개 (university/department/exam_type/material)")

        with driver.session(default_access_mode=READ_ACCESS) as s:
            chunks = s.run("""
                MATCH (c:Admission_TextChunk)
                RETURN c.university AS university, c.chunk_index AS chunk_index, c.text AS text
            """).data()
        if args.limit:
            chunks = chunks[: args.limit]
        print(f"청크 {len(chunks)}건에 대해 LLM 구조화 추출 수행 중 (model={EXTRACTION_MODEL}, "
              f"동시 {MAX_WORKERS}개, confidence>={CONFIDENCE_THRESHOLD})...")

        chunk_mentions = {}  # (university, chunk_index) -> [{"name","type","is_new"}]
        entity_types = dict(known_entities)  # name -> type (LLM이 새로 찾은 것도 여기 누적)
        entity_chunk_map = defaultdict(set)
        failed = 0
        done = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(extract_entities_llm, ch["text"], known_entities): (ch["university"], ch["chunk_index"]) for ch in chunks}
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    found = fut.result()
                except Exception:
                    found = []
                    failed += 1
                chunk_mentions[key] = found
                for item in found:
                    entity_types.setdefault(item["name"], item["type"])
                    entity_chunk_map[item["name"]].add(key)
                done += 1
                if done % 100 == 0:
                    print(f"  진행: {done}/{len(chunks)}")

        total_mentions = sum(len(v) for v in chunk_mentions.values())
        new_entities = {n for n, t in entity_types.items() if n not in known_entities}
        print(f"\nMENTIONS 총 {total_mentions}건, LLM 호출 실패(스킵) {failed}건")
        print(f"사전에 없던 새 개체(is_new, day36 교안_02가 잡으려던 부분) {len(new_entities)}개 발견")
        top_new = sorted(new_entities, key=lambda n: -len(entity_chunk_map[n]))[:10]
        if top_new:
            print("[새로 발견된 개체 Top 10]")
            for n in top_new:
                print(f"  {n} ({entity_types[n]}): {len(entity_chunk_map[n])}개 청크")

        # 동시출현: 같은 청크에 같이 언급된 개체 쌍
        cooccur = defaultdict(int)
        for found in chunk_mentions.values():
            uniq = sorted({item["name"] for item in found})
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    cooccur[(uniq[i], uniq[j])] += 1
        print(f"개체 쌍 동시출현 {len(cooccur)}건")

        if not args.commit:
            print("\nDRY-RUN 완료 (DB 쓰기 0건). --commit 플래그로 재실행 시 실제 적재됩니다.")
            return

        with driver.session(default_access_mode=WRITE_ACCESS) as s:
            s.run("MATCH (e:Admission_Entity) DETACH DELETE e")
            for name, etype in entity_types.items():
                s.run(
                    "MERGE (e:Admission_Entity {name: $name}) SET e.type = $etype, e.llm_discovered = $is_new",
                    name=name, etype=etype, is_new=(name in new_entities),
                )
            for (univ, idx), found in chunk_mentions.items():
                for item in found:
                    s.run("""
                        MATCH (c:Admission_TextChunk {university: $univ, chunk_index: $idx})
                        MATCH (e:Admission_Entity {name: $name})
                        MERGE (c)-[:MENTIONS]->(e)
                    """, univ=univ, idx=idx, name=item["name"])
            for (a, b), weight in cooccur.items():
                s.run("""
                    MATCH (ea:Admission_Entity {name: $a})
                    MATCH (eb:Admission_Entity {name: $b})
                    MERGE (ea)-[r:CO_OCCURS_WITH]-(eb)
                    SET r.weight = $weight
                """, a=a, b=b, weight=weight)
        print(f"[커밋 완료] Admission_Entity={len(entity_types)}, MENTIONS={total_mentions}, CO_OCCURS_WITH={len(cooccur)}")

        # PageRank + Louvain: 이 Aura 티어는 gds.graph.project()가 유료 GDS 세션을
        # 요구해서(직접 호출해 확인함) networkx로 로컬 계산 후 SET으로 기록한다.
        try:
            import networkx as nx
            from networkx.algorithms.community import louvain_communities

            G = nx.Graph()
            for name in entity_types:
                G.add_node(name)
            for (a, b), weight in cooccur.items():
                G.add_edge(a, b, weight=weight)

            pagerank = nx.pagerank(G, weight="weight") if G.number_of_edges() > 0 else {n: 0.0 for n in G.nodes}
            communities = louvain_communities(G, weight="weight", seed=42) if G.number_of_edges() > 0 else []
            community_of = {name: idx for idx, comm in enumerate(communities) for name in comm}

            # GraphRAG 스타일 커뮤니티 요약: 크기 2 이상인 커뮤니티마다 LLM 라벨 1회 호출
            community_labels = {}
            sizable = [c for c in communities if len(c) >= 2]
            print(f"\n커뮤니티 {len(communities)}개 중 {len(sizable)}개(크기>=2)에 LLM 라벨 부여 중...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                label_futures = {pool.submit(label_community_llm, list(c)): idx for idx, c in enumerate(communities) if len(c) >= 2}
                for fut in as_completed(label_futures):
                    idx = label_futures[fut]
                    try:
                        community_labels[idx] = fut.result()
                    except Exception:
                        community_labels[idx] = ""

            with driver.session(default_access_mode=WRITE_ACCESS) as s:
                for name in entity_types:
                    cidx = community_of.get(name, -1)
                    s.run("""
                        MATCH (e:Admission_Entity {name: $name})
                        SET e.pagerank = $pagerank, e.community = $community, e.community_label = $label
                    """, name=name, pagerank=float(pagerank.get(name, 0.0)), community=cidx,
                        label=community_labels.get(cidx, ""))
            print(f"[PageRank/Louvain/커뮤니티라벨 완료] (networkx 로컬 계산, {len(communities)}개 커뮤니티)")

            top = sorted(pagerank.items(), key=lambda kv: -kv[1])[:10]
            print("\n[PageRank 상위 10개 개체]")
            for name, score in top:
                print(f"  {name} ({entity_types[name]}) pagerank={score:.4f} community={community_of.get(name)} "
                      f"label={community_labels.get(community_of.get(name), '')}")

            print("\n[커뮤니티별 구성 예시 (상위 5개, 라벨 포함)]")
            for comm in sorted(communities, key=len, reverse=True)[:5]:
                idx = community_of[next(iter(comm))]
                names = [f"{n}({entity_types[n]})" for n in list(comm)[:8]]
                print(f"  [{community_labels.get(idx, '(라벨없음)')}] ({len(comm)}개): {', '.join(names)}")
        except Exception as e:
            print(f"ℹ️ PageRank/Louvain 계산 실패: {e}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
