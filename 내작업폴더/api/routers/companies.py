# -*- coding: utf-8 -*-
"""
기업 검색 / 4단 의사결정 리포트 / 지배력 관계 / 포트폴리오 리스크 신호.
DecisionReportService(서비스 계층, READ_ACCESS 강제)를 얇게 감싸는 라우터.
"""

from fastapi import APIRouter, HTTPException, Query, status

from services.decision_report_service import DecisionReportService

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/search")
def search_companies(q: str = Query(min_length=1), limit: int = Query(10, le=50)):
    svc = DecisionReportService()
    try:
        return {"results": svc.find_companies(q, limit=limit)}
    finally:
        svc.close()


@router.get("/{corp_code_or_name}/report")
def get_report(corp_code_or_name: str, max_events: int = Query(15, le=100)):
    svc = DecisionReportService()
    try:
        result = svc.generate_company_decision_report(corp_code_or_name, max_events=max_events)
        if result.get("status") == "NOT_FOUND":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=result.get("message"))
        return result
    finally:
        svc.close()


@router.get("/{corp_code}/influence")
def get_influence(corp_code: str, corp_name: str = Query("")):
    svc = DecisionReportService()
    try:
        return svc.get_influence_and_evidence(corp_code, corp_name)
    finally:
        svc.close()


@router.get("/by-stock/{stock_code}/risk-signal")
def get_risk_signal(stock_code: str):
    """포트폴리오 화면의 리스크 배지용 (승격 지분·자본이벤트 실시간 조인)."""
    svc = DecisionReportService()
    try:
        return svc.get_portfolio_risk_signal(stock_code)
    finally:
        svc.close()
