# -*- coding: utf-8 -*-
"""DS005 기업 주요 자본 이벤트(CB·BW·증자·M&A) 조회."""

from typing import Optional
from fastapi import APIRouter, Query
from neo4j import READ_ACCESS

from api.deps import get_driver

router = APIRouter(prefix="/api/capital-events", tags=["capital-events"])


@router.get("/stats")
def capital_event_stats():
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.run("MATCH (e:DART_CapitalEvent) RETURN e.event_type AS type, count(e) AS cnt").data()
    stats = {r["type"]: r["cnt"] for r in rows}
    return {
        "total": sum(stats.values()),
        "cb_issue": stats.get("CB_ISSUE", 0),
        "bw_issue": stats.get("BW_ISSUE", 0),
        "paid_increase": stats.get("PAID_INCREASE", 0),
        "stock_acquisition": stats.get("STOCK_ACQUISITION", 0),
        "merger": stats.get("MERGER", 0),
    }


@router.get("/companies")
def companies_with_events():
    """자본이벤트가 있는 기업 목록 (필터 드롭다운용)."""
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.run("""
            MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
            RETURN DISTINCT c.name AS name, count(e) AS event_count
            ORDER BY event_count DESC, name
        """).data()
    return {"companies": rows}


@router.get("")
def list_capital_events(
    corp_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, description="CB_ISSUE | BW_ISSUE | PAID_INCREASE | STOCK_ACQUISITION | MERGER"),
    limit: int = Query(30, le=200),
):
    driver = get_driver()
    where_clauses = []
    params = {"limit": limit}
    if corp_name:
        where_clauses.append("c.name = $corp_name")
        params["corp_name"] = corp_name
    if event_type:
        where_clauses.append("e.event_type = $event_type")
        params["event_type"] = event_type
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
        {where_sql}
        RETURN c.name AS corp_name,
               e.event_type AS event_type,
               e.issue_amount AS issue_amount,
               e.conversion_price AS conversion_price,
               e.min_refixing_floor AS refixing_floor,
               e.issue_method AS issue_method,
               e.is_private AS is_private,
               e.decided_on AS decided_on,
               e.received_on AS received_on,
               e.effective_on AS effective_on,
               e.source_rcept_no AS rcept_no,
               e.viewer_url AS viewer_url
        ORDER BY e.received_on DESC
        LIMIT $limit
    """
    with driver.session(default_access_mode=READ_ACCESS) as session:
        events = session.run(query, **params).data()
    return {"events": events, "count": len(events)}
