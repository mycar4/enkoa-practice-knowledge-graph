import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "ART:READY Franchise B2B Platform API"
    VERSION: str = "5.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Supabase 환경 변수
    SUPABASE_URL: str = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://jqdtqawrkdidcdfzxzwb.supabase.co")
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_m3si3M17RpGHrIXt8Au9tQ_w3CwtCpW")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # Private Storage 버킷 이름
    PRIVATE_STORAGE_BUCKET: str = "art-franchise-private"
    
    # CORS 설정 (Vercel 프론트엔드, 기존 공개 사이트 www.artready.kr 허용 필수 - v5.0 제2.3절)
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
        "https://artready.kr",
        "https://www.artready.kr",
        "https://adminartreadykr.vercel.app",
        "https://partnerartreadykr.vercel.app",
        "https://appartreadykr.vercel.app"
    ]

settings = Settings()
