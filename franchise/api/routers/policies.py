import requests
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from ..auth import get_current_user, UserSession
from ..config import settings

router = APIRouter(prefix="/policies", tags=["POLICIES: 정책 문서 및 동의"])

class AgreementCreateRequest(BaseModel):
    policy_id: str = Field(..., description="동의 대상 정책 문서 UUID")
    guardian_consent_at: Optional[str] = Field(None, description="만 14세 미만 법정대리인 동의 일시 (ISO-8601)")

@router.get("")
async def get_active_policies(
    type: Optional[str] = Query(None, description="TERMS / PRIVACY / THIRD_PARTY / COLLECTION_CONSENT")
):
    """
    [공개 API] 현재 활성화된(is_active=true) 정책 문서 조회 (지시서 v2.0 제3.8절 & 제4절)
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}"
    }

    url = f"{settings.SUPABASE_URL}/rest/v1/policy_documents?is_active=eq.true"
    if type:
        url += f"&doc_type=eq.{type}"

    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=f"정책 문서 조회 실패: {res.text}")

    return {"success": True, "policies": res.json()}

@router.post("/agreements", status_code=status.HTTP_201_CREATED)
async def record_policy_agreement(
    req: AgreementCreateRequest,
    current_user: UserSession = Depends(get_current_user)
):
    """
    [인증 필수] 정책 동의 기록 저장 (미성년자 법정대리인 동의 일시 추적 지원)
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "user_id": current_user.user_id,
        "policy_id": req.policy_id,
        "guardian_consent_at": req.guardian_consent_at
    }

    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/policy_agreements", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"정책 동의 기록 실패: {res.text}")

    return {"success": True, "data": res.json()}
