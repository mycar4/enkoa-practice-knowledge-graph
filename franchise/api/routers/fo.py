import requests
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..auth import get_current_user, require_roles, UserSession
from ..config import settings

router = APIRouter(tags=["FO: 학생 및 강사/학부모"])

# ── DTO 모델 ─────────────────────────────────────────────────────────────
class AttendanceCreateRequest(BaseModel):
    class_date: str = Field(..., description="출석 일자 (YYYY-MM-DD)")
    status: str = Field("PRESENT", description="PRESENT / ABSENT / LATE / EXCUSED")
    remark: Optional[str] = None

class ClassAlbumCreateRequest(BaseModel):
    branch_id: Optional[str] = None
    class_date: str = Field(..., description="수업 일자 (YYYY-MM-DD)")
    content_text: str = Field(..., max_length=500, description="수업 내용 및 총평 (최대 500자)")
    image_urls: List[str] = Field(default_factory=list, description="비공개 스토리지 파일 경로 목록")

class EvaluationCreateRequest(BaseModel):
    student_id: str = Field(..., description="원생 식별자(UUID)")
    evaluation_date: str = Field(..., description="평가 일자 (YYYY-MM-DD)")
    subject: str = Field(..., description="실기 과목명 (예: 기초디자인)")
    score: int = Field(..., ge=0, le=100, description="실기 점수 (0~100)")
    feedback: str = Field(..., description="강사 피드백 및 총평")
    image_urls: List[str] = Field(default_factory=list, description="실기 작품 파일 경로 목록")

class SignedUrlRequest(BaseModel):
    file_path: str = Field(..., description="버킷 내 파일 상대 경로")
    expires_in: int = Field(3600, description="만료 시간(초, 기본 1시간)")

# ── 엔드포인트 ─────────────────────────────────────────────────────────
@router.post("/students/{student_id}/attendance", status_code=status.HTTP_201_CREATED)
async def record_attendance(
    student_id: str,
    req: AttendanceCreateRequest,
    current_user: UserSession = Depends(require_roles("TENANT_ADMIN", "INSTRUCTOR"))
):
    """
    [강사/원장 전용] 학생 출결 기록 등록 (지시서 v2.0 제3.5절 & 제4절)
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "tenant_id": current_user.tenant_id,
        "student_id": student_id,
        "class_date": req.class_date,
        "status": req.status,
        "remark": req.remark
    }

    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/attendance", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"출결 기록 실패: {res.text}")

    return {"success": True, "data": res.json()}

@router.post("/class-albums", status_code=status.HTTP_201_CREATED)
async def create_class_album(
    req: ClassAlbumCreateRequest,
    current_user: UserSession = Depends(require_roles("TENANT_ADMIN", "INSTRUCTOR"))
):
    """
    [강사/원장 전용] 수업앨범 단체 기록 등록 (지시서 v2.0 제3.6절 & 제4절)
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "tenant_id": current_user.tenant_id,
        "branch_id": req.branch_id or current_user.branch_id,
        "instructor_id": current_user.user_id,
        "class_date": req.class_date,
        "content_text": req.content_text,
        "image_urls": req.image_urls
    }

    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/class_album", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"수업앨범 등록 실패: {res.text}")

    return {"success": True, "data": res.json()}

@router.post("/evaluations", status_code=status.HTTP_201_CREATED)
async def create_student_evaluation(
    req: EvaluationCreateRequest,
    current_user: UserSession = Depends(require_roles("TENANT_ADMIN", "INSTRUCTOR"))
):
    """
    [강사/원장 전용] 개별 원생 실기 평가 및 피드백 등록
    """
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "tenant_id": current_user.tenant_id,
        "student_id": req.student_id,
        "instructor_id": current_user.user_id,
        "evaluation_date": req.evaluation_date,
        "subject": req.subject,
        "score": req.score,
        "feedback": req.feedback,
        "image_urls": req.image_urls
    }

    res = requests.post(f"{settings.SUPABASE_URL}/rest/v1/student_evaluations", json=payload, headers=headers, timeout=5)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=res.status_code, detail=f"실기 평가 등록 실패: {res.text}")

    return {"success": True, "data": res.json()}

@router.post("/storage/signed-url")
async def create_signed_url(
    req: SignedUrlRequest,
    current_user: UserSession = Depends(get_current_user)
):
    """
    [보안] 비공개 버킷(Private Storage)의 실기 이미지 만료형 Signed URL 생성 (지시서 v2.0 제3.9절)
    """
    url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/{settings.PRIVATE_STORAGE_BUCKET}/{req.file_path}"
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"expiresIn": req.expires_in}

    res = requests.post(url, json=payload, headers=headers, timeout=5)
    if res.status_code == 200:
        data = res.json()
        full_signed_url = f"{settings.SUPABASE_URL}/storage/v1{data.get('signedURL')}"
        return {"success": True, "signed_url": full_signed_url, "expires_in": req.expires_in}
    else:
        # 버킷 미생성 또는 권한 부족 시 안내
        return {
            "success": False,
            "error": "Signed URL 발급 실패 (Storage 버킷 생성 여부 확인 필요)",
            "detail": res.text
        }
