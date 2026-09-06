# -*- coding: utf-8 -*-
"""
지배구조 네트워크 탐색기 + 순환출자·상호출자 자동 탐지.
프론트엔드 그래프 라이브러리(react-force-graph 등)가 바로 쓸 수 있도록
{nodes:[], edges:[]} 형태의 정규화된 JSON으로 반환한다 (pyvis HTML 아님).
"""

from typing import Optional
from fastapi import APIRouter, Query
from neo4j import READ_ACCESS

from api.deps import get_driver

router = APIRouter(prefix="/api/network", tags=["network"])

PRESET_QUERIES = {
    "verified_stakes": """
        MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
        RETURN a, b, r, type(r) AS r_type
    """,
    "lotte": """
        MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
        WHERE a.name STARTS WITH '롯데' OR b.name STARTS WITH '롯데'
        RETURN a, b, r, type(r) AS r_type
    """,
    "aluco": """
        MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
        WHERE a.name IN ['케이피티유', '알루코'] OR b.name IN ['케이피티유', '알루코']
        RETURN a, b, r, type(r) AS r_type
    """,
    "hyundai_home": """
        MATCH (a:DART_Company)-[r:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)
        WHERE a.name IN ['현대홈쇼핑', '현대퓨처넷'] OR b.name IN ['현대홈쇼핑', '현대퓨처넷']
        RETURN a, b, r, type(r) AS r_type
    """,
    "capital_events": """
        MATCH (a:DART_Company)-[r:ANNOUNCED]->(b:DART_CapitalEvent)
        RETURN a, b, r, type(r) AS r_type
        LIMIT 30
    """,
}


def _node_to_json(node) -> dict:
    props = dict(node)
    label = props.get("name") or props.get("corp_code") or props.get("rcept_no") or str(node.element_id)
    return {
        "id": node.element_id,
        "label": label,
        "labels": list(node.labels),
        "properties": props,
    }


def _edge_to_json(rel, r_type: str) -> dict:
    props = dict(rel)
    return {
        "id": rel.element_id,
        "source": rel.start_node.element_id,
        "target": rel.end_node.element_id,
        "type": r_type,
        "properties": props,
    }


@router.get("/graph")
def get_graph(preset: Optional[str] = Query(None), entity: Optional[str] = Query(None), limit: int = Query(50, le=200)):
    driver = get_driver()

    if entity:
        query = """
            MATCH (a)-[r]->(b)
            WHERE (a.name = $entity OR b.name = $entity)
              AND type(r) IN ['HOLDS_ECONOMIC_STAKE', 'ANNOUNCED', 'INVESTED_IN', 'REPRESENTS', 'ACQUIRED_STAKE']
            RETURN a, b, r, type(r) AS r_type
            LIMIT $limit
        """
        params = {"entity": entity, "limit": limit}
    else:
        query = PRESET_QUERIES.get(preset or "verified_stakes", PRESET_QUERIES["verified_stakes"])
        params = {}

    nodes_by_id = {}
    edges = []
    with driver.session(default_access_mode=READ_ACCESS) as session:
        for record in session.run(query, **params):
            a, b, r, r_type = record["a"], record["b"], record["r"], record["r_type"]
            nodes_by_id[a.element_id] = _node_to_json(a)
            nodes_by_id[b.element_id] = _node_to_json(b)
            edges.append(_edge_to_json(r, r_type))

    return {"nodes": list(nodes_by_id.values()), "edges": edges}


@router.get("/cycles")
def get_cycles():
    """승격된 HOLDS_ECONOMIC_STAKE 관계 기준 상호출자(2사)·3단 순환출자 자동 탐지."""
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        mutual_pairs = session.run("""
            MATCH (a:DART_Company)-[r1:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)-[r2:HOLDS_ECONOMIC_STAKE]->(a)
            WHERE elementId(a) < elementId(b)
            WITH a, b, r1, r2
            ORDER BY r1.reporting_obligation_date DESC
            WITH a, b, collect({r1: r1, r2: r2})[0] AS latest
            RETURN a.name AS company_a, latest.r1.stake_ratio AS a_to_b_stake, latest.r1.rcept_no AS a_to_b_rcept,
                   b.name AS company_b, latest.r2.stake_ratio AS b_to_a_stake, latest.r2.rcept_no AS b_to_a_rcept
        """).data()

        triangle_cycles = session.run("""
            MATCH (a:DART_Company)-[r1:HOLDS_ECONOMIC_STAKE]->(b:DART_Company)-[r2:HOLDS_ECONOMIC_STAKE]->(c:DART_Company)-[r3:HOLDS_ECONOMIC_STAKE]->(a)
            WHERE a <> b AND b <> c AND a <> c
              AND elementId(a) < elementId(b) AND elementId(a) < elementId(c)
            WITH a, b, c, r1, r2, r3
            ORDER BY r1.reporting_obligation_date DESC
            WITH a, b, c, collect({r1:r1, r2:r2, r3:r3})[0] AS latest
            RETURN a.name AS company_a, b.name AS company_b, c.name AS company_c,
                   latest.r1.stake_ratio AS a_to_b, latest.r2.stake_ratio AS b_to_c, latest.r3.stake_ratio AS c_to_a,
                   latest.r1.rcept_no AS rcept_no
        """).data()

    return {"mutual_pairs": mutual_pairs, "triangle_cycles": triangle_cycles}
