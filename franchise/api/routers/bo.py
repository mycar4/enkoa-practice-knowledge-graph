import requests
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..auth import require_roles, UserSession
from ..config import settings

router = APIRouter(prefix="/bo", tags=["BO: 엔코아 본사 통합 관리자"])

# ── DTO 모델 ─────────────────────────────────────────────────────────────
class TenantCreateRequest(BaseModel):
    name: str = Field(..., description="학원/가맹 브랜드명")
    business_number: Optional[str] = Field(None, description="사업자등록번호")
    contract_months: int = Field(36, description="약정 개월 수")
    initial_status: str = Field("PENDING", description="초기 상태 (PENDING/ACTIVE)")
    slug: Optional[str] = None
    intro_text: Optional[str] = None

class TenantStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="ACTIVE, SUSPENDED, PENDING, TERMINATED")
    reason: Optional[str] = None

class TenantPublishApprovalRequest(BaseModel):
    is_public_published: bool = Field(..., description="소개 페이지 게시 승인 여부")
    review_notes: Optional[str] = None

class ManualAdjustmentRequest(BaseModel):
    billing_month: str = Field(..., description="정산 월 (YYYY-MM)")
    manual_adjustment_amount: float = Field(..., description="수기결제 조정액 (+/- 가능)")
    adjustment_reason: str = Field(..., min_length=2, description="수기결제 사유 (최소 2자 이상 필수)")

class NoticeCreateRequest(BaseModel):
    title: str = Field(..., description="공지사항 제목")
    content: str = Field(..., description="공지 본문")
    target_role: str = Field("ALL", description="전체/가맹원장/학생")
    is_pinned: bool = False

class AdminUserCreateRequest(BaseModel):
    name: str = Field(..., description="관리자 성명")
    email: str = Field(..., description="이메일 계정")
    role: str = Field("BO_MANAGER", description="BO_SUPER_ADMIN, BO_MANAGER, BO_VIEWER")
    department: str = Field("운영지원팀", description="소속 부서")

class PolicyCreateRequest(BaseModel):
    title: str
    doc_type: str = "TERMS"
    version: str = "v1.0"
    content: str
    is_mandatory: bool = True

# ── 인메모리 시드 저장소 (Supabase 폴백 및 실시간 반응용) ──
BO_TENANTS_STORE = [
    {
        "id": "t-01",
        "name": "강남 미술학원 본원",
        "slug": "gangnam-main",
        "business_number": "120-81-99881",
        "contract_months": 36,
        "status": "ACTIVE",
        "is_public_published": True,
        "intro_text": "20년 전통의 디자인/기초소양 명문 학원입니다.",
        "student_count": 84,
        "created_at": "2024-03-01T09:00:00Z"
    },
    {
        "id": "t-02",
        "name": "홍대 디자인캠퍼스",
        "slug": "hongdae-campus",
        "business_number": "105-82-44321",
        "contract_months": 24,
        "status": "ACTIVE",
        "is_public_published": True,
        "intro_text": "트렌디한 시각·산업디자인 집중 교육관.",
        "student_count": 62,
        "created_at": "2024-06-15T09:00:00Z"
    },
    {
        "id": "t-03",
        "name": "분당 예원 아트센터",
        "slug": "bundang-yewon",
        "business_number": "129-86-77112",
        "contract_months": 36,
        "status": "PENDING",
        "is_public_published": False,
        "intro_text": "신규 온보딩 검토 중인 분당 거점 학원입니다.",
        "student_count": 31,
        "created_at": "2026-09-10T11:00:00Z"
    }
]

BO_NOTICES_STORE = [
    {
        "id": "notice-01",
        "title": "[공지] 2026년 4분기 수시 모의평가 표준 가이드라인 배포",
        "content": "가맹학원 원장님 및 전임강사님을 위한 수시 실전 모의평가 채점 기준표가 배포되었습니다. 평가 관리 메뉴에서 표준 평가 양식을 확인해 주시기 바랍니다.",
        "target_role": "TENANT_ADMIN",
        "is_pinned": True,
        "created_at": "2026-09-18T10:00:00Z"
    },
    {
        "id": "notice-02",
        "title": "[안내] 9월 플랫폼 정기 점검 및 수강료 수기조정 마감일 안내",
        "content": "9월 정산 수기조정 마감은 9월 25일 18:00까지입니다. 사유 미입력 시 회계감사 규정에 의해 승인 불가하오니 유의하시기 바랍니다.",
        "target_role": "ALL",
        "is_pinned": False,
        "created_at": "2026-09-15T14:30:00Z"
    }
]

BO_ADMINS_STORE = [
    {
        "id": "admin-01",
        "name": "김본사 총괄이사",
        "email": "head@artready.kr",
        "role": "BO_SUPER_ADMIN",
        "department": "경영전략총괄",
        "status": "ACTIVE",
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": "admin-02",
        "name": "이운영 과장",
        "email": "ops@artready.kr",
        "role": "BO_MANAGER",
        "department": "가맹운영지원팀",
        "status": "ACTIVE",
        "created_at": "2024-04-10T09:00:00Z"
    }
]

# ── 엔드포인트 ─────────────────────────────────────────────────────────

@router.get("/stats", summary="BO 플랫폼 종합 통계")
async def get_platform_stats():
    """BO 1. 플랫폼 종합 관제 대시보드 통계"""
    total_tenants = len(BO_TENANTS_STORE)
    active_tenants = len([t for t in BO_TENANTS_STORE if t["status"] == "ACTIVE"])
    pending_tenants = len([t for t in BO_TENANTS_STORE if t["status"] == "PENDING"])
    total_students = sum(t.get("student_count", 0) for t in BO_TENANTS_STORE)
    return {
        "success": True,
        "stats": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "pending_tenants": pending_tenants,
            "total_students": total_students,
            "monthly_billing_estimate": 48500000,
            "total_evaluations_mtd": 1284,
            "server_uptime": "99.98%"
        }
    }

@router.get("/tenants", summary="가맹 학원 전체 목록 조회")
async def get_tenants(status_filter: Optional[str] = None):
    """BO 2. 가맹학원 목록 및 심사 관리"""
    results = BO_TENANTS_STORE
    if status_filter:
        results = [t for t in results if t["status"] == status_filter]
    return {"success": True, "count": len(results), "tenants": results}

@router.post("/tenants", status_code=status.HTTP_201_CREATED, summary="신규 학원 등록 및 온보딩")
async def create_tenant(req: TenantCreateRequest):
    """BO 2. 가맹학원 계약 및 온보딩 등록"""
    new_tenant = {
        "id": f"t-{uuid.uuid4().hex[:4]}",
        "name": req.name,
        "slug": req.slug or f"tenant-{uuid.uuid4().hex[:4]}",
        "business_number": req.business_number or "000-00-00000",
        "contract_months": req.contract_months,
        "status": req.initial_status,
        "is_public_published": False,
        "intro_text": req.intro_text or "신규 등록 가맹학원입니다.",
        "student_count": 0,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    BO_TENANTS_STORE.insert(0, new_tenant)
    return {"success": True, "message": "가맹학원이 신규 등록되었습니다.", "data": new_tenant}

@router.patch("/tenants/{tenant_id}/status", summary="가맹학원 가맹 상태 변경(승인/중지)")
async def update_tenant_status(tenant_id: str, req: TenantStatusUpdateRequest):
    found = False
    for t in BO_TENANTS_STORE:
        if t["id"] == tenant_id:
            t["status"] = req.status
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="해당 가맹학원을 찾을 수 없습니다.")
    return {"success": True, "message": f"가맹 상태가 {req.status}(으)로 변경되었습니다."}

@router.patch("/tenants/{tenant_id}/publish", summary="학원 소개 페이지 게시 승인/반려 (v5.0)")
async def approve_tenant_publish(tenant_id: str, req: TenantPublishApprovalRequest):
    """v5.0 3.3절: 학원 소개 페이지 본사 승인 절차"""
    found = False
    for t in BO_TENANTS_STORE:
        if t["id"] == tenant_id:
            t["is_public_published"] = req.is_public_published
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="해당 가맹학원을 찾을 수 없습니다.")
    action = "공개 승인" if req.is_public_published else "공개 반려"
    return {"success": True, "message": f"학원 소개 페이지 {action} 처리가 완료되었습니다."}

@router.get("/tenants/{tenant_id}/billing", summary="학원별 월별 정산 및 결제 이력 조회")
async def get_tenant_billing(tenant_id: str):
    """BO 3. 학원별 월별 정산 내역"""
    sample_billings = [
        {
            "id": f"bill-{tenant_id}-2026-09",
            "tenant_id": tenant_id,
            "billing_month": "2026-09",
            "expected_amount": 1680000,
            "manual_adjustment_amount": 0,
            "adjustment_reason": None,
            "final_amount": 1680000,
            "payment_status": "PENDING"
        },
        {
            "id": f"bill-{tenant_id}-2026-08",
            "tenant_id": tenant_id,
            "billing_month": "2026-08",
            "expected_amount": 1680000,
            "manual_adjustment_amount": -100000,
            "adjustment_reason": "하계 특강 프로모션 제휴 할인 적용",
            "final_amount": 1580000,
            "payment_status": "PAID"
        }
    ]
    return {"success": True, "tenant_id": tenant_id, "billings": sample_billings}

@router.post("/tenants/{tenant_id}/billing/manual-adjustment", summary="수기결제 조정 등록")
async def manual_billing_adjustment(tenant_id: str, req: ManualAdjustmentRequest):
    """BO 3. 수기결제 조정 등록 (지시서 필수 제약: 사유 2자 이상 입력)"""
    if not req.adjustment_reason or len(req.adjustment_reason.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="수기결제 조정 시 사유(adjustment_reason)는 2자 이상 법적/회계상 필수 기입 항목입니다."
        )
    return {
        "success": True,
        "message": "수기결제 조정이 성공적으로 반영되었습니다.",
        "data": {
            "tenant_id": tenant_id,
            "billing_month": req.billing_month,
            "adjustment_amount": req.manual_adjustment_amount,
            "reason": req.adjustment_reason.strip()
        }
    }

@router.get("/notices", summary="공지사항 목록 조회")
async def get_notices():
    """BO 6. 공지사항 관리"""
    return {"success": True, "count": len(BO_NOTICES_STORE), "notices": BO_NOTICES_STORE}

@router.post("/notices", status_code=status.HTTP_201_CREATED, summary="공지사항 등록")
async def create_notice(req: NoticeCreateRequest):
    """BO 6. 공지사항 신규 발송"""
    new_notice = {
        "id": f"notice-{uuid.uuid4().hex[:4]}",
        "title": req.title,
        "content": req.content,
        "target_role": req.target_role,
        "is_pinned": req.is_pinned,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    BO_NOTICES_STORE.insert(0, new_notice)
    return {"success": True, "message": "공지사항이 성공적으로 등록되었습니다.", "notice": new_notice}

@router.get("/admins", summary="본사 관리자 계정 목록")
async def get_admin_users():
    """BO 7. 본사 관리자 계정 관리"""
    return {"success": True, "count": len(BO_ADMINS_STORE), "admins": BO_ADMINS_STORE}

@router.post("/admins", status_code=status.HTTP_201_CREATED, summary="본사 관리자 계정 추가")
async def create_admin_user(req: AdminUserCreateRequest):
    """BO 7. 신규 본사 관리자 초대"""
    new_admin = {
        "id": f"admin-{uuid.uuid4().hex[:4]}",
        "name": req.name,
        "email": req.email,
        "role": req.role,
        "department": req.department,
        "status": "ACTIVE",
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    BO_ADMINS_STORE.append(new_admin)
    return {"success": True, "message": "관리자 계정이 생성되었습니다.", "admin": new_admin}

