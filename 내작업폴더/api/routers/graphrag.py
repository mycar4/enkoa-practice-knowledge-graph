# -*- coding: utf-8 -*-
"""
GraphRAG 자연어 질의응답 2종:
- /query: 홈 화면용, 자본이벤트 512차원 벡터검색 + 70:30 하이브리드 리랭커
- /evidence-chat: 5% 공시 원문 증거 + 자본이벤트 규칙기반 질의 (지배력 단정 질의 가드레일 포함)
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import get_driver

router = APIRouter(prefix="/api/graphrag", tags=["graphrag"])


class GraphRagQueryRequest(BaseModel):
    query: str
    corp_filter: Optional[str] = None
    top_k: int = 3


class EvidenceChatRequest(BaseModel):
    query: str


@router.post("/query")
def graphrag_query(body: GraphRagQueryRequest):
    from services.graphrag_service import generate_graphrag_response
    return generate_graphrag_response(body.query, corp_filter=body.corp_filter, top_k=body.top_k)


@router.post("/evidence-chat")
def evidence_chat(body: EvidenceChatRequest):
    import os
    from engine_financial_graphrag import analyze_financial_graphrag

    api_key = os.getenv("OPENAI_API_KEY", "")
    driver = get_driver()
    return analyze_financial_graphrag(body.query, driver, api_key)
