import json
import base64
import requests
from typing import Optional, List, Dict, Any
from fastapi import Header, HTTPException, Depends, status
from pydantic import BaseModel
from .config import settings

class UserSession(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: str
    tenant_id: Optional[str] = None
    branch_id: Optional[str] = None

def decode_unverified_jwt(token: str) -> Dict[str, Any]:
    """JWT 토큰의 페이로드를 디코딩합니다 (서명 검증은 Supabase 서버 또는 공개키로 처리)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload_b64 = parts[1] + padding
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        return json.loads(payload_json)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"인증 토큰 디코딩 실패: {str(e)}"
        )

async def get_current_user(authorization: Optional[str] = Header(None)) -> UserSession:
    """
    Authorization: Bearer <JWT> 헤더로부터 사용자 세션을 추출하고 Supabase auth와 연동합니다.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 Authorization: Bearer 헤더가 필요합니다."
        )
    
    token = authorization.split(" ")[1]
    payload = decode_unverified_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 사용자 식별자(sub)가 없습니다."
        )
        
    # Supabase PostgREST를 통해 user_profiles 정보 조회
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    profile_url = f"{settings.SUPABASE_URL}/rest/v1/user_profiles?id=eq.{user_id}&select=*"
    res = requests.get(profile_url, headers=headers, timeout=5)
    
    if res.status_code == 200 and len(res.json()) > 0:
        profile = res.json()[0]
        return UserSession(
            user_id=user_id,
            email=profile.get("email"),
            role=profile.get("role", "STUDENT"),
            tenant_id=profile.get("tenant_id"),
            branch_id=profile.get("branch_id")
        )
    else:
        # 프로필 레코드가 아직 없거나 초기 가입 단계인 경우 토큰의 app_metadata/user_metadata 기반 폴백
        app_meta = payload.get("app_metadata", {})
        user_meta = payload.get("user_metadata", {})
        return UserSession(
            user_id=user_id,
            email=payload.get("email"),
            role=app_meta.get("role") or user_meta.get("role", "STUDENT"),
            tenant_id=app_meta.get("tenant_id") or user_meta.get("tenant_id"),
            branch_id=app_meta.get("branch_id") or user_meta.get("branch_id")
        )

def require_roles(*allowed_roles: str):
    """지정된 역할 목록 중 하나를 보유했는지 검증하는 Dependency 팩토리"""
    async def role_checker(user: UserSession = Depends(get_current_user)) -> UserSession:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"해당 리소스에 접근 권한이 없습니다. (필요 권한: {', '.join(allowed_roles)}, 현재: {user.role})"
            )
        return user
    return role_checker

def check_menu_permission(user_id: str, menu_key: str, required_action: str = "read") -> bool:
    """
    menu_permissions 테이블에서 해당 사용자의 메뉴 권한(can_read / can_write)을 실측 검사합니다.
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}"
    }
    url = f"{settings.SUPABASE_URL}/rest/v1/menu_permissions?user_id=eq.{user_id}&menu_key=eq.{menu_key}&select=*"
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200 and len(res.json()) > 0:
        perm = res.json()[0]
        if required_action == "write":
            return bool(perm.get("can_write"))
        return bool(perm.get("can_read"))
    return False
