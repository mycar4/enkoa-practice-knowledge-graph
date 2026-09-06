# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace API] FastAPI 백엔드 진입점
================================================================================
- Streamlit(app_dart_trace_dashboard.py)을 대체할 API 서버. 프론트엔드(Next.js
  등)는 이 서버에만 HTTP로 통신하고, Neo4j Aura에는 절대 직접 접속하지 않는다.
- 실행: repo root에서 `uv run uvicorn --app-dir 내작업폴더 api.main:app --reload --port 8000`
  (--app-dir로 내작업폴더를 cwd처럼 sys.path에 태워서 실행 - 폴더명에 한글이 섞여 있어
  `내작업폴더.api.main:app` 식의 패키지 경로 지정은 피한다.)
- 100% 읽기 전용 원칙은 그대로 유지: 모든 Neo4j 세션은 서비스 계층
  (services/decision_report_service.py 등) 및 api/deps.py에서 READ_ACCESS로만 연다.
================================================================================
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 내작업폴더
REPO_ROOT = os.path.dirname(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from api.routers import auth_router, companies, network, rankings, capital_events, evidence, graphrag, portfolio

app = FastAPI(
    title="DART-Trace API",
    description="금융감독원 DART 공시 원문 기반 지배구조·자본이벤트 지식그래프 API",
    version="1.2.0",
)

_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(companies.router)
app.include_router(network.router)
app.include_router(rankings.router)
app.include_router(capital_events.router)
app.include_router(evidence.router)
app.include_router(graphrag.router)
app.include_router(portfolio.router)


@app.get("/api/health")
def health_check():
    from api.deps import get_driver
    try:
        driver = get_driver()
        driver.verify_connectivity()
        neo4j_status = "connected"
    except Exception as e:
        neo4j_status = f"error: {e}"
    return {"status": "ok", "neo4j": neo4j_status}
