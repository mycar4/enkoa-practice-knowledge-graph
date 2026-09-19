from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import bo, co, fo, policies

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="ART:READY 프랜차이즈 B2B 3-Tier 관리 플랫폼 백엔드 API (AWS Lambda / ECS 배포용)",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정 (Vercel FO 및 로컬 프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 헬스체크 엔드포인트
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "supabase_connected": bool(settings.SUPABASE_URL and settings.SUPABASE_PUBLISHABLE_KEY)
    }

# 라우터 등록
app.include_router(bo.router, prefix=settings.API_V1_PREFIX)
app.include_router(co.router, prefix=settings.API_V1_PREFIX)
app.include_router(fo.router, prefix=settings.API_V1_PREFIX)
app.include_router(policies.router, prefix=settings.API_V1_PREFIX)
