import requests
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..auth import require_roles, UserSession
from ..config import settings

router = APIRouter(tags=["CO: 개별 학원 관리자"])

# ── DTO 모델 ─────────────────────────────────────────────────────────────
class MenuPermissionItem(BaseModel):
    menu_key: str = Field(..., description="메뉴 식별자 (예: student.list, student.evaluation, billing.view)")
    can_read: bool = Field(False, description="읽기 권한 여부")
    can_write: bool = Field(False, description="쓰기/수정 권한 여부")

class UpdateUserPermissionsRequest(BaseModel):
    permissions: List[MenuPermissionItem]

class BranchCreateRequest(BaseModel):
    branch_name: str = Field(..., description="지점명 (예: 강남본원, 홍대점)")
    address: Optional[str] = None
    contact: Optional[str] = None

# ── 엔드포인트 ─────────────────────────────────────────────────────────
@router.put("/tenants/{tenant_id}/permissions/{user_id}")
async def update_user_menu_permissions(
    tenant_id: str,
    user_id: str,
    req: UpdateUserPermissionsRequest,
    current_user: UserSession = Depends(require_roles("TENANT_ADMIN", "BO_ADMIN"))
):
    """
    [TENANT_ADMIN 전용] 소속 강사/사용자의 메뉴별 세부 권한 설정 (지시서 v2.0 제3.3절 & 제4절)
    """
    # 학원장은 본인 학원의 소속 유저만 권한 변경 가능
    if current_user.role == "TENANT_ADMIN" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인이 총괄하는 학원의 권한만 설정할 수 있습니다."
        )

    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    # 메뉴 권한 일괄 업서트
    records = []
    for item in req.permissions:
        records.append({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "menu_key": item.menu_key,
            "can_read": item.can_read,
            "can_write": item.can_write
        })

    res = requests.post(
        f"{settings.SUPABASE_URL}/rest/v1/menu_permissions",
        json=records,
        headers=headers,
        timeout=5
    )

    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"메뉴 권한 갱신 실패: {res.text}")

    return {
        "success": True,
        "tenant_id": tenant_id,
        "target_user_id": user_id,
        "updated_count": len(records),
        "message": "메뉴 권한이 성공적으로 설정되었습니다."
    }

@router.post("/co/branches", status_code=status.HTTP_201_CREATED)
async def create_branch(
    req: BranchCreateRequest,
    current_user: UserSession = Depends(require_roles("TENANT_ADMIN", "BO_ADMIN"))
):
    """
    [TENANT_ADMIN 전용] 학원 지점 추가 등록
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="소속 학원(tenant_id) 정보가 필요합니다.")

    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "tenant_id": current_user.tenant_id,
        "branch_name": req.branch_name,
        "address": req.address,
        "contact": req.contact
    }

    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/branches", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"지점 등록 실패: {res.text}")

    return {"success": True, "data": res.json()}
