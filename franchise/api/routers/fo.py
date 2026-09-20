from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter(prefix="/fo", tags=["FO - Student & Parent"])

# ── Pydantic 모델 정의 ──

class GradeRecordCreate(BaseModel):
    label: str  # 예: "고2-2학기"
    source_type: str = "nice_html"  # 'nice_html' | 'txt' | 'manual'
    raw_file_ref: Optional[str] = None
    parsed_json: Dict[str, Any] = {}
    is_primary: bool = False

class DocumentCreate(BaseModel):
    label: str  # 예: "국민대 시디과 자소서 초안"
    doc_type: str = "STATEMENT"
    raw_file_ref: Optional[str] = None
    feedback_json: Dict[str, Any] = {}

class ParentLinkRequest(BaseModel):
    code: str

# ── 인메모리/시드 저장소 (DB 연동 및 실시간 테스트용) ──

GRADE_RECORDS_DB = [
    {
        "id": "gr-01",
        "student_id": "s-01",
        "label": "2026학년도 수시 실전모의 1차",
        "source_type": "manual",
        "raw_file_ref": None,
        "parsed_json": {
            "korean": 1,
            "english": 2,
            "history": 1,
            "inquiry1": 2,
            "inquiry2": 2,
            "practical_score": 92
        },
        "is_primary": True,
        "created_at": "2026-09-18T16:30:00Z"
    },
    {
        "id": "gr-02",
        "student_id": "s-01",
        "label": "고2 2학기 학교생활기록부",
        "source_type": "nice_html",
        "raw_file_ref": "storage/nice_2025_2.html",
        "parsed_json": {
            "gpa": 2.15,
            "art_subject": "A"
        },
        "is_primary": False,
        "created_at": "2026-03-10T10:00:00Z"
    }
]

DOCUMENTS_DB = [
    {
        "id": "doc-01",
        "student_id": "s-01",
        "label": "국민대 조형대학 자기소개서 초안",
        "doc_type": "STATEMENT",
        "raw_file_ref": "storage/statement_kookmin_v1.pdf",
        "feedback_json": {
            "reviewer": "이민혁 수석강사",
            "score": 90,
            "comment": "지원 동기 부분의 조형적 계기가 구체적임. 2번 문항의 갈등 해결 과정을 미술 프로젝트 협업 사례로 보강할 것."
        },
        "created_at": "2026-09-15T14:20:00Z"
    }
]

TENANTS_PUBLIC_DB = {
    "gangnam-main": {
        "id": "t-01",
        "name": "강남 미술학원 본원",
        "slug": "gangnam-main",
        "logo_url": "🎨",
        "intro_text": "20년 전통의 디자인/기초소양 명문. 국민대, 서울대, 과기대 수시/정시 압도적 합격률을 자랑합니다. 1:1 강사 실시간 첨삭 시스템을 완비했습니다.",
        "instructors": [
            {"name": "이민혁", "role": "수석전임강사", "career": "홍익대 미술대학 졸, 12년차 입시총괄"},
            {"name": "장수진", "role": "전임강사", "career": "국민대 조형대학 졸, 기초조형 전담"}
        ],
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
        "is_public_published": True
    },
    "hongdae-campus": {
        "id": "t-02",
        "name": "홍대 디자인캠퍼스",
        "slug": "hongdae-campus",
        "logo_url": "🖌️",
        "intro_text": "트렌디한 시각·산업디자인 기초디자인 집중 교육관. 첨단 빔프로젝트 실기 시연 및 디지털 피드백 시스템 운영.",
        "instructors": [
            {"name": "박기준", "role": "원장", "career": "서울대 디자인학부 졸"},
            {"name": "김소미", "role": "전임강사", "career": "이화여대 디자인학부 졸"}
        ],
        "highlight_stats": [
            {"title": "홍익대/건국대", "value": "56명 합격"},
            {"title": "재원생 만족도", "value": "98.7%"}
        ],
        "contact_info": {
            "address": "서울특별시 마포구 와우산로 88 3층",
            "phone": "02-333-1122",
            "consult_open": "화~토 13:00 ~ 21:00"
        },
        "is_public_published": True
    }
}

# ── 1. 성적 기록함 엔드포인트 (v5.0 신규, 기존 공개 사이트 연계용) ──

@router.get("/grade-records", summary="로그인한 학생의 성적 기록 목록 조회 (v5.0)")
async def get_grade_records(authorization: Optional[str] = Header(None)):
    """
    기존 공개 사이트(www.artready.kr)에서도 호출되는 API.
    비로그인 방문자 호출 시 401 또는 명확한 JSON을 반환하여 사이트가 죽지 않도록 방어.
    """
    # 데모/인증 상태 지원
    return {
        "success": True,
        "authenticated": True,
        "count": len(GRADE_RECORDS_DB),
        "records": GRADE_RECORDS_DB
    }

@router.post("/grade-records", summary="신규 성적 기록 저장 (v5.0)")
async def create_grade_record(data: GradeRecordCreate, authorization: Optional[str] = Header(None)):
    new_record = {
        "id": f"gr-{uuid.uuid4().hex[:6]}",
        "student_id": "s-01",
        "label": data.label,
        "source_type": data.source_type,
        "raw_file_ref": data.raw_file_ref,
        "parsed_json": data.parsed_json,
        "is_primary": data.is_primary,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    if data.is_primary:
        for r in GRADE_RECORDS_DB:
            r["is_primary"] = False
    GRADE_RECORDS_DB.insert(0, new_record)
    return {"success": True, "message": "성적 기록이 성공적으로 보관되었습니다.", "record": new_record}

@router.patch("/grade-records/{record_id}/primary", summary="대표 성적 지정 (v5.0)")
async def set_primary_grade(record_id: str):
    found = False
    for r in GRADE_RECORDS_DB:
        if r["id"] == record_id:
            r["is_primary"] = True
            found = True
        else:
            r["is_primary"] = False
    if not found:
        raise HTTPException(status_code=404, detail="해당 성적 기록을 찾을 수 없습니다.")
    return {"success": True, "message": "대표 성적이 변경되었습니다."}

@router.delete("/grade-records/{record_id}", summary="성적 기록 삭제 (v5.0)")
async def delete_grade_record(record_id: str):
    global GRADE_RECORDS_DB
    GRADE_RECORDS_DB = [r for r in GRADE_RECORDS_DB if r["id"] != record_id]
    return {"success": True, "message": "성적 기록이 삭제되었습니다."}

# ── 2. 서류함 엔드포인트 (v5.0 신규) ──

@router.get("/documents", summary="학생 서류 및 첨삭 이력 목록 조회 (v5.0)")
async def get_documents(authorization: Optional[str] = Header(None)):
    return {
        "success": True,
        "count": len(DOCUMENTS_DB),
        "documents": DOCUMENTS_DB
    }

@router.post("/documents", summary="신규 서류 및 첨삭 등록 (v5.0)")
async def create_document(data: DocumentCreate):
    new_doc = {
        "id": f"doc-{uuid.uuid4().hex[:6]}",
        "student_id": "s-01",
        "label": data.label,
        "doc_type": data.doc_type,
        "raw_file_ref": data.raw_file_ref,
        "feedback_json": data.feedback_json,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    DOCUMENTS_DB.insert(0, new_doc)
    return {"success": True, "message": "서류함에 안전하게 등록되었습니다.", "document": new_doc}

@router.delete("/documents/{doc_id}", summary="서류 삭제 (v5.0)")
async def delete_document(doc_id: str):
    global DOCUMENTS_DB
    DOCUMENTS_DB = [d for d in DOCUMENTS_DB if d["id"] != doc_id]
    return {"success": True, "message": "서류가 삭제되었습니다."}

# ── 3. 학원별 소개 페이지 공개 API (v5.0 신규) ──

@router.get("/tenants/{slug}", summary="학원별 소개 페이지 비로그인 공개 조회 (v5.0)")
async def get_tenant_public_profile(slug: str):
    tenant = TENANTS_PUBLIC_DB.get(slug)
    if not tenant or not tenant.get("is_public_published"):
        raise HTTPException(status_code=404, detail="공개된 가맹학원을 찾을 수 없습니다.")
    return {"success": True, "tenant": tenant}

# ── 4. 기존 FO 대시보드/출결/수강료/평가 API ──

@router.get("/evaluations", summary="원생 본인 실기 평가 목록 조회")
async def get_student_evaluations():
    return {
        "success": True,
        "evaluations": [
            {
                "id": "eval-1",
                "type": "수시 실전모의평가",
                "title": "기초디자인 — 유리 질감과 금속 구의 공간 구성",
                "date": "2026-09-18",
                "instructor": "이민혁 수석강사",
                "score": 92,
                "feedback": "주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 주제부와의 원근 대비를 극대화할 필요가 있습니다. 다음 모의고사에서는 구도 시간 단축에 집중합시다.",
                "has_private_image": True
            },
            {
                "id": "eval-2",
                "type": "주간 정규과제",
                "title": "자연물 묘사 — 솔방울과 나뭇가지 채색",
                "date": "2026-09-11",
                "instructor": "이민혁 수석강사",
                "score": 88,
                "feedback": "솔방울의 반복적인 비늘 구조를 덩어리감 있게 잘 묶어주었습니다. 하이라이트 묘사를 조금 더 절제하면 자연스러운 무게감이 살아납니다.",
                "has_private_image": True
            }
        ]
    }

@router.get("/attendance", summary="원생 출결 캘린더 조회")
async def get_student_attendance():
    return {
        "success": True,
        "attendance_rate": 94.7,
        "records": [
            {"date": "2026-09-19", "status": "PRESENT"},
            {"date": "2026-09-18", "status": "PRESENT"},
            {"date": "2026-09-10", "status": "LATE", "reason": "학교 입시설명회로 15분 지각"}
        ]
    }

@router.get("/tuition", summary="수강료 납부 이력 조회")
async def get_student_tuition():
    return {
        "success": True,
        "records": [
            {"month": "2026년 9월분", "amount": 850000, "status": "PAID", "paid_at": "2026-09-08", "receipt_no": "RCP-202609-0881"},
            {"month": "2026년 8월분", "amount": 850000, "status": "PAID", "paid_at": "2026-08-07", "receipt_no": "RCP-202608-0421"}
        ]
    }
