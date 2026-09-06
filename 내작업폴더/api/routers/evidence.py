# -*- coding: utf-8 -*-
"""5% 공시 원문 증거 감사기 (Evidence Audit Inspector) - 100% 읽기 전용."""

from typing import Optional
from fastapi import APIRouter, Query
from neo4j import READ_ACCESS

from api.deps import get_driver

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/metrics")
def evidence_metrics():
    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        cand = session.run("MATCH (c:RawEvidenceCandidate) RETURN count(c) AS c").single()["c"]
        frag = session.run("MATCH (f:EvidenceFragment) RETURN count(f) AS c").single()["c"]
        edge = session.run("MATCH ()-[r:EVIDENCED_BY]->() RETURN count(r) AS c").single()["c"]
        tainted = session.run("""
            MATCH (n)-[r:OWNS_STAKE]-(m)
            WHERE n:RawEvidenceCandidate OR n:EvidenceFragment OR m:RawEvidenceCandidate OR m:EvidenceFragment
            RETURN count(r) AS c
        """).single()["c"]
    return {"candidates": cand, "fragments": frag, "evidenced_by": edge, "owns_stake_contamination": tainted}


@router.get("/candidates")
def list_candidates(
    status: Optional[str] = Query(None, description="ALL | SUPPORTED_5PCT_GENERAL | UNSUPPORTED_LAYOUT | LEGACY"),
    kw: str = Query(""),
    limit: int = Query(20, le=200),
):
    driver = get_driver()
    status_param = status or "ALL"
    query = """
        MATCH (c:RawEvidenceCandidate)
        WHERE ($status = 'ALL'
               OR ($status = 'LEGACY' AND c.legacy_status = 'LEGACY_PROVISIONAL_TEST_LOAD')
               OR ($status <> 'LEGACY' AND c.layout_status = $status AND c.legacy_status IS NULL))
          AND ($kw = ''
               OR c.target_corp_name CONTAINS $kw
               OR c.holder_name CONTAINS $kw
               OR c.rcept_no CONTAINS $kw
               OR c.candidate_id CONTAINS $kw)
        RETURN c.candidate_id AS candidate_id,
               c.rcept_no AS rcept_no,
               c.target_corp_name AS corp_name,
               c.target_corp_code AS corp_code,
               c.reporter_name AS reporter_name,
               c.holder_name AS holder_name,
               c.shares_count AS shares,
               c.stake_ratio AS ratio,
               c.reporting_obligation_date AS ob_date,
               c.layout_status AS layout_status,
               c.legacy_status AS legacy_status,
               c.xml_sha256 AS xml_sha256
        ORDER BY c.rcept_no DESC, c.candidate_id
        LIMIT $limit
    """
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.run(query, status=status_param, kw=kw, limit=limit).data()
    return {"candidates": rows, "count": len(rows)}


@router.get("/candidates/{candidate_id}")
def get_candidate_detail(candidate_id: str):
    driver = get_driver()
    query = """
        MATCH (c:RawEvidenceCandidate {candidate_id: $cid})
        OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
        RETURN c.candidate_id AS candidate_id, c.rcept_no AS rcept_no,
               c.target_corp_name AS corp_name, c.holder_name AS holder_name,
               c.stake_ratio AS stake_ratio, c.shares_count AS shares_count,
               c.xml_sha256 AS xml_sha256, c.xml_rel_path AS xml_rel_path,
               f.role AS role, f.xpath AS xpath, f.extracted_value AS extracted_value,
               f.raw_inner_hash AS inner_hash
    """
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.run(query, cid=candidate_id).data()
    return {"candidate_id": candidate_id, "fragments": rows}
