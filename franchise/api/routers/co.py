import requests
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..auth import require_roles, UserSession
from ..config import settings

router = APIRouter(prefix="/co", tags=["CO: 개별 가맹학원 원장/강사"])

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

class StudentCreateRequest(BaseModel):
    name: str = Field(..., description="원생 성명")
    grade: str = Field(..., description="학년 (고3, 고2, 고1, N수)")
    target_major: str = Field(..., description="목표 전공 (디자인, 서양화, 동양화, 조소)")
    target_univ: str = Field(..., description="목표 대학 (국민대, 서울대, 홍익대 등)")
    parent_phone: str = Field(..., description="학부모 연락처")
    status: str = Field("ENROLLED", description="재원 상태")

class AttendanceCreateRequest(BaseModel):
    student_id: str
    date: str
    status: str = Field("PRESENT", description="PRESENT, LATE, ABSENT")
    reason: Optional[str] = None

class EvaluationCreateRequest(BaseModel):
    student_id: str
    student_name: str
    title: str
    score: int
    feedback: str
    category: str = "기초디자인"

class AlbumCreateRequest(BaseModel):
    student_id: str
    student_name: str
    title: str
    image_url: str
    description: Optional[str] = None

class TuitionCreateRequest(BaseModel):
    student_id: str
    student_name: str
    month: str
    amount: int
    status: str = "PENDING"

class ParentLinkCreateRequest(BaseModel):
    student_id: str
    student_name: str
    parent_phone: str

class AcademyProfileUpdateRequest(BaseModel):
    name: str
    slug: str = Field(..., description="학원 고유 URL 식별자")
    intro_text: str = Field(..., description="학원 소개 문구")
    logo_url: Optional[str] = None
    highlight_stats: List[Dict[str, str]] = []
    contact_info: Dict[str, str] = {}
    request_publish_approval: bool = True

# ── 인메모리 시드 저장소 ──
CO_STUDENTS_STORE = [
    {"id": "s-01", "name": "김민지", "grade": "고3", "target_major": "시각디자인", "target_univ": "국민대 / 서울과기대", "parent_phone": "010-9876-5432", "status": "ENROLLED"},
    {"id": "s-02", "name": "이준호", "grade": "N수", "target_major": "산업디자인", "target_univ": "서울대 / 홍익대", "parent_phone": "010-8765-4321", "status": "ENROLLED"},
    {"id": "s-03", "name": "박서연", "grade": "고2", "target_major": "기초소양", "target_univ": "이화여대 / 건국대", "parent_phone": "010-7654-3210", "status": "ENROLLED"}
]

CO_ATTENDANCE_STORE = [
    {"id": "att-1", "student_id": "s-01", "student_name": "김민지", "date": "2026-09-19", "status": "PRESENT", "reason": None},
    {"id": "att-2", "student_id": "s-02", "student_name": "이준호", "date": "2026-09-19", "status": "LATE", "reason": "지하철 연착 10분 지각"},
    {"id": "att-3", "student_id": "s-03", "student_name": "박서연", "date": "2026-09-19", "status": "PRESENT", "reason": None}
]

CO_EVALUATIONS_STORE = [
    {
        "id": "eval-1",
        "student_id": "s-01",
        "student_name": "김민지",
        "title": "수시 실전모의 — 유리와 금속 구의 공간 구성",
        "score": 92,
        "category": "기초디자인",
        "feedback": "주제부 하이라이트 표현이 매우 우수하며 전체 공간 배치가 안정적입니다.",
        "created_at": "2026-09-18"
    },
    {
        "id": "eval-2",
        "student_id": "s-02",
        "student_name": "이준호",
        "title": "주간 테마과제 — 미래 운송기기 렌더링",
        "score": 95,
        "category": "산업디자인",
        "feedback": "선화의 강약 조절과 폼 렌더링이 전문가 수준입니다.",
        "created_at": "2026-09-17"
    }
]

CO_ALBUMS_STORE = [
    {"id": "alb-1", "student_id": "s-01", "student_name": "김민지", "title": "2026 국민대 실전 모의고사 우수작", "image_url": "https://placehold.co/600x400/9b111e/ffffff?text=ArtReady+Artwork", "created_at": "2026-09-18"},
    {"id": "alb-2", "student_id": "s-02", "student_name": "이준호", "title": "기초소양 입체 구성 포트폴리오", "image_url": "https://placehold.co/600x400/18181b/ffffff?text=Portfolio", "created_at": "2026-09-15"}
]

CO_TUITION_STORE = [
    {"id": "tui-1", "student_id": "s-01", "student_name": "김민지", "month": "2026년 9월분", "amount": 850000, "status": "PAID", "paid_at": "2026-09-08"},
    {"id": "tui-2", "student_id": "s-02", "student_name": "이준호", "month": "2026년 9월분", "amount": 920000, "status": "UNPAID", "paid_at": None},
    {"id": "tui-3", "student_id": "s-03", "student_name": "박서연", "month": "2026년 9월분", "amount": 850000, "status": "PAID", "paid_at": "2026-09-10"}
]

CO_PARENT_LINKS_STORE = [
    {"id": "pl-1", "student_id": "s-01", "student_name": "김민지", "parent_phone": "010-9876-5432", "link_code": "ART-7891", "is_linked": True, "created_at": "2026-09-01"},
    {"id": "pl-2", "student_id": "s-02", "student_name": "이준호", "parent_phone": "010-8765-4321", "link_code": "ART-4421", "is_linked": False, "created_at": "2026-09-12"}
]

CO_PROFILE_STORE = {
    "tenant_id": "t-01",
    "name": "강남 미술학원 본원",
    "slug": "gangnam-main",
    "logo_url": "🎨",
    "intro_text": "20년 전통의 디자인/기초소양 명문 학원. 국민대/서울대/과기대 수시 정시 압도적 합격률을 자랑합니다.",
    "highlight_stats": [
        {"title": "2026 수시 합격률", "value": "89.4%"},
        {"title": "국민대/서울과기대", "value": "42명 합격"},
        {"title": "실기 만점자 배출", "value": "8명"}
    ],
    "contact_info": {
        "address": "서울특별시 강남구 테헤란로 124 삼원빌딩 4~5층",
        "phone": "02-555-7890",
        "consult_open": "평일 13:00 ~ 22:00 / 토 09:00 ~ 18:00"
    },
    "is_public_published": True,
    "approval_status": "APPROVED"
}

# ── 엔드포인트 ─────────────────────────────────────────────────────────

@router.get("/students", summary="원생 명부 목록 조회")
async def get_students():
    """CO 2. 원생 명부 조회"""
    return {"success": True, "count": len(CO_STUDENTS_STORE), "students": CO_STUDENTS_STORE}

@router.post("/students", status_code=status.HTTP_201_CREATED, summary="원생 신규 등록")
async def create_student(req: StudentCreateRequest):
    """CO 2. 원생 신규 입학 등록"""
    new_student = {
        "id": f"s-{uuid.uuid4().hex[:4]}",
        "name": req.name,
        "grade": req.grade,
        "target_major": req.target_major,
        "target_univ": req.target_univ,
        "parent_phone": req.parent_phone,
        "status": req.status
    }
    CO_STUDENTS_STORE.append(new_student)
    return {"success": True, "message": "원생이 정상 등록되었습니다.", "student": new_student}

@router.put("/students/{student_id}", summary="원생 정보 수정")
async def update_student(student_id: str, req: StudentCreateRequest):
    for s in CO_STUDENTS_STORE:
        if s["id"] == student_id:
            s.update(req.dict())
            return {"success": True, "message": "원생 정보가 수정되었습니다.", "student": s}
    raise HTTPException(status_code=404, detail="원생을 찾을 수 없습니다.")

@router.get("/attendance", summary="출결 현황 조회")
async def get_attendance():
    """CO 3. 출결 캘린더 현황"""
    return {"success": True, "count": len(CO_ATTENDANCE_STORE), "records": CO_ATTENDANCE_STORE}

@router.post("/attendance", status_code=status.HTTP_201_CREATED, summary="출결 기록 등록")
async def create_attendance(req: AttendanceCreateRequest):
    new_att = {
        "id": f"att-{uuid.uuid4().hex[:4]}",
        "student_id": req.student_id,
        "student_name": next((s["name"] for s in CO_STUDENTS_STORE if s["id"] == req.student_id), "원생"),
        "date": req.date,
        "status": req.status,
        "reason": req.reason
    }
    CO_ATTENDANCE_STORE.insert(0, new_att)
    return {"success": True, "message": "출결이 처리되었습니다.", "attendance": new_att}

@router.get("/evaluations", summary="실기 평가 및 첨삭 목록")
async def get_evaluations():
    """CO 4. 실기평가 관리"""
    return {"success": True, "count": len(CO_EVALUATIONS_STORE), "evaluations": CO_EVALUATIONS_STORE}

@router.post("/evaluations", status_code=status.HTTP_201_CREATED, summary="실기 평가 등록")
async def create_evaluation(req: EvaluationCreateRequest):
    new_eval = {
        "id": f"eval-{uuid.uuid4().hex[:4]}",
        "student_id": req.student_id,
        "student_name": req.student_name,
        "title": req.title,
        "score": req.score,
        "category": req.category,
        "feedback": req.feedback,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d")
    }
    CO_EVALUATIONS_STORE.insert(0, new_eval)
    return {"success": True, "message": "실기 평가가 등록되었습니다.", "evaluation": new_eval}

@router.get("/albums", summary="원생 작품 앨범")
async def get_albums():
    """CO 5. 작품 앨범 관리"""
    return {"success": True, "count": len(CO_ALBUMS_STORE), "albums": CO_ALBUMS_STORE}

@router.post("/albums", status_code=status.HTTP_201_CREATED, summary="작품 업로드")
async def create_album(req: AlbumCreateRequest):
    new_album = {
        "id": f"alb-{uuid.uuid4().hex[:4]}",
        "student_id": req.student_id,
        "student_name": req.student_name,
        "title": req.title,
        "image_url": req.image_url,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d")
    }
    CO_ALBUMS_STORE.insert(0, new_album)
    return {"success": True, "message": "작품이 등록되었습니다.", "album": new_album}

@router.get("/tuition", summary="수강료 청구/수납 내역")
async def get_tuition():
    """CO 6. 수강료 수납 관리"""
    return {"success": True, "count": len(CO_TUITION_STORE), "records": CO_TUITION_STORE}

@router.post("/tuition", status_code=status.HTTP_201_CREATED, summary="수강료 청구서 발행")
async def create_tuition(req: TuitionCreateRequest):
    new_tui = {
        "id": f"tui-{uuid.uuid4().hex[:4]}",
        "student_id": req.student_id,
        "student_name": req.student_name,
        "month": req.month,
        "amount": req.amount,
        "status": req.status,
        "paid_at": datetime.utcnow().strftime("%Y-%m-%d") if req.status == "PAID" else None
    }
    CO_TUITION_STORE.insert(0, new_tui)
    return {"success": True, "message": "수강료 청구서가 발행되었습니다.", "record": new_tui}

@router.get("/parent-links", summary="학부모 연동 현황")
async def get_parent_links():
    """CO 7. 학부모 계정 연동"""
    return {"success": True, "count": len(CO_PARENT_LINKS_STORE), "links": CO_PARENT_LINKS_STORE}

@router.post("/parent-links", status_code=status.HTTP_201_CREATED, summary="학부모 연동 코드 신규 발급")
async def create_parent_link(req: ParentLinkCreateRequest):
    code = f"ART-{uuid.uuid4().hex[:4].upper()}"
    new_link = {
        "id": f"pl-{uuid.uuid4().hex[:4]}",
        "student_id": req.student_id,
        "student_name": req.student_name,
        "parent_phone": req.parent_phone,
        "link_code": code,
        "is_linked": False,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d")
    }
    CO_PARENT_LINKS_STORE.insert(0, new_link)
    return {"success": True, "message": f"연동 코드({code})가 발급되었습니다.", "link": new_link}

@router.get("/profile", summary="학원 기본정보 및 소개 페이지 설정 조회 (v5.0)")
async def get_academy_profile():
    """CO 9. 학원 기본정보 + v5.0 소개 페이지 콘텐츠"""
    return {"success": True, "profile": CO_PROFILE_STORE}

@router.put("/profile", summary="학원 소개 페이지 수정 및 본사 승인 신청 (v5.0)")
async def update_academy_profile(req: AcademyProfileUpdateRequest):
    """CO 9 + v5.0 3.3절: 학원 소개 페이지 편집 및 본사 승인 신청"""
    CO_PROFILE_STORE["name"] = req.name
    CO_PROFILE_STORE["slug"] = req.slug
    CO_PROFILE_STORE["intro_text"] = req.intro_text
    if req.logo_url:
        CO_PROFILE_STORE["logo_url"] = req.logo_url
    if req.highlight_stats:
        CO_PROFILE_STORE["highlight_stats"] = req.highlight_stats
    if req.contact_info:
        CO_PROFILE_STORE["contact_info"] = req.contact_info
    if req.request_publish_approval:
        CO_PROFILE_STORE["approval_status"] = "PENDING_APPROVAL"
        CO_PROFILE_STORE["is_public_published"] = False

    return {
        "success": True,
        "message": "학원 소개 정보가 저장되었으며 본사 게시 승인이 신청되었습니다.",
        "profile": CO_PROFILE_STORE
    }

@router.put("/tenants/{tenant_id}/permissions/{user_id}", summary="소속 강사/사용자 권한 설정")
async def update_user_menu_permissions(tenant_id: str, user_id: str, req: UpdateUserPermissionsRequest):
    """CO 10. 강사 권한 설정"""
    return {
        "success": True,
        "tenant_id": tenant_id,
        "target_user_id": user_id,
        "updated_count": len(req.permissions),
        "message": "메뉴 권한이 성공적으로 설정되었습니다."
    }

@router.post("/branches", status_code=status.HTTP_201_CREATED, summary="학원 지점 추가 등록")
async def create_branch(req: BranchCreateRequest):
    new_branch = {
        "id": f"br-{uuid.uuid4().hex[:4]}",
        "branch_name": req.branch_name,
        "address": req.address,
        "contact": req.contact
    }
    return {"success": True, "message": "지점이 등록되었습니다.", "data": new_branch}

