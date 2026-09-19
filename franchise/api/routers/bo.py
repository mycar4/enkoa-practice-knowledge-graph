import requests
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..auth import require_roles, UserSession
from ..config import settings

router = APIRouter(prefix="/bo", tags=["BO: 엔코아 통합 관리자"])

# ── DTO 모델 ─────────────────────────────────────────────────────────────
class TenantCreateRequest(BaseModel):
    name: str = Field(..., description="학원/가맹 브랜드명")
    business_number: Optional[str] = Field(None, description="사업자등록번호")
    contract_months: int = Field(36, description="약정 개월 수")
    initial_status: str = Field("PENDING", description="초기 상태 (PENDING/ACTIVE)")

class ManualAdjustmentRequest(BaseModel):
    billing_month: str = Field(..., description="정산 월 (YYYY-MM)")
    manual_adjustment_amount: float = Field(..., description="수기결제 조정액 (+/- 가능)")
    adjustment_reason: str = Field(..., min_length=2, description="수기결제 사유 (필수 입력)")

# ── 엔드포인트 ─────────────────────────────────────────────────────────
@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreateRequest,
    user: UserSession = Depends(require_roles("BO_ADMIN", "BO_MANAGER"))
):
    """
    [BO 전용] 신규 학원 승인 및 가맹점 등록
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    payload = {
        "name": req.name,
        "business_number": req.business_number,
        "contract_months": req.contract_months,
        "status": req.initial_status
    }
    
    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/tenants", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"학원 등록 실패: {res.text}")
        
    return {"success": True, "data": res.json()}

@router.get("/tenants/{tenant_id}/billing")
async def get_tenant_billing(
    tenant_id: str,
    user: UserSession = Depends(require_roles("BO_ADMIN", "BO_MANAGER"))
):
    """
    [BO 전용] 학원별 월별 정산 및 결제 이력 조회
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}"
    }
    
    url = f"{settings.SUPABASE_URL}/rest/v1/tenant_billing?tenant_id=eq.{tenant_id}&order=billing_month.desc"
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=f"정산 내역 조회 실패: {res.text}")
        
    return {"success": True, "tenant_id": tenant_id, "billings": res.json()}

@router.post("/tenants/{tenant_id}/billing/manual-adjustment")
async def manual_billing_adjustment(
    tenant_id: str,
    req: ManualAdjustmentRequest,
    user: UserSession = Depends(require_roles("BO_ADMIN", "BO_MANAGER"))
):
    """
    [BO 전용] 수기결제 조정 등록 (지시서 v2.0 제3.2절: 사유 필수 입력 제약 준수)
    """
    if not req.adjustment_reason or len(req.adjustment_reason.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="수기결제 조정 시 사유(adjustment_reason)는 법적/회계상 필수 기입 항목입니다."
        )

    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    # 해당 월의 기존 청구 내역 조회
    check_url = f"{settings.SUPABASE_URL}/rest/v1/tenant_billing?tenant_id=eq.{tenant_id}&billing_month=eq.{req.billing_month}"
    check_res = requests.get(check_url, headers=headers, timeout=5)
    
    existing = check_res.json() if check_res.status_code == 200 and len(check_res.json()) > 0 else None
    
    if existing:
        record_id = existing[0]["id"]
        expected = float(existing[0].get("expected_amount", 0))
        final = expected + req.manual_adjustment_amount
        patch_payload = {
            "manual_adjustment_amount": req.manual_adjustment_amount,
            "adjustment_reason": req.adjustment_reason.strip(),
            "final_amount": final
        }
        res = requests.patch(f"{settings.SUPABASE_URL}/rest/v1/tenant_billing?id=eq.{record_id}", json=patch_payload, headers=headers, timeout=5)
    else:
        # 신규 등록
        insert_payload = {
            "tenant_id": tenant_id,
            "billing_month": req.billing_month,
            "expected_amount": 0,
            "manual_adjustment_amount": req.manual_adjustment_amount,
            "adjustment_reason": req.adjustment_reason.strip(),
            "final_amount": req.manual_adjustment_amount,
            "payment_status": "PENDING"
        }
        res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/tenant_billing", json=insert_payload, headers=headers, timeout=5)

    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"수기결제 조정 반영 실패: {res.text}")

    return {"success": True, "message": "수기결제 조정이 정상 반영되었습니다.", "data": res.json()}
