import sys
import io
import os
sys.path.insert(0, os.path.abspath("."))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from fastapi.testclient import TestClient
from franchise.api.main import app

client = TestClient(app)

def run_tests():
    print("=" * 75)
    print("[API VERIFICATION] ART:READY v5.0 FastAPI 3-Tier CRUD & Records Suite")
    print("=" * 75)

    # 1. Health check
    res = client.get("/health")
    print(f"1. GET /health -> Status: {res.status_code}, Service: {res.json().get('service')}")
    assert res.status_code == 200, "Health check failed"

    # 2. FO v5.0 - Grade Records (성적 기록함)
    res = client.get("/api/v1/fo/grade-records")
    print(f"2. GET /api/v1/fo/grade-records -> Status: {res.status_code}, Records: {len(res.json().get('records', []))}")
    assert res.status_code == 200

    new_gr = {
        "label": "2026학년도 9월 모평",
        "source_type": "manual",
        "parsed_json": {"korean": 1, "english": 1, "practical": 94},
        "is_primary": True
    }
    res = client.post("/api/v1/fo/grade-records", json=new_gr)
    print(f"3. POST /api/v1/fo/grade-records -> Status: {res.status_code}, ID: {res.json().get('record', {}).get('id')}")
    assert res.status_code == 200
    gr_id = res.json()["record"]["id"]

    res = client.patch(f"/api/v1/fo/grade-records/{gr_id}/primary")
    print(f"4. PATCH /api/v1/fo/grade-records/{gr_id}/primary -> Status: {res.status_code}")
    assert res.status_code == 200

    # 3. FO v5.0 - Documents (서류함)
    res = client.get("/api/v1/fo/documents")
    print(f"5. GET /api/v1/fo/documents -> Status: {res.status_code}, Docs: {len(res.json().get('documents', []))}")
    assert res.status_code == 200

    new_doc = {
        "label": "서울대 디자인과 포트폴리오 설명서",
        "doc_type": "PORTFOLIO",
        "feedback_json": {"reviewer": "이민혁 수석강사", "score": 95}
    }
    res = client.post("/api/v1/fo/documents", json=new_doc)
    print(f"6. POST /api/v1/fo/documents -> Status: {res.status_code}, ID: {res.json().get('document', {}).get('id')}")
    assert res.status_code == 200

    # 4. FO v5.0 - Public Tenant Intro (학원별 소개 비로그인 공개 조회)
    res = client.get("/api/v1/fo/tenants/gangnam-main")
    print(f"7. GET /api/v1/fo/tenants/gangnam-main -> Status: {res.status_code}, Name: {res.json().get('tenant', {}).get('name')}")
    assert res.status_code == 200
    assert res.json()["tenant"]["slug"] == "gangnam-main"

    # 5. BO v5.0 - Stats, Tenants, Publish Approval, Manual Adjustment
    res = client.get("/api/v1/bo/stats")
    print(f"8. GET /api/v1/bo/stats -> Status: {res.status_code}, Tenants: {res.json().get('stats', {}).get('total_tenants')}")
    assert res.status_code == 200

    res = client.post("/api/v1/bo/tenants", json={"name": "일산 주엽 캠퍼스", "contract_months": 24, "initial_status": "PENDING"})
    print(f"9. POST /api/v1/bo/tenants -> Status: {res.status_code}")
    assert res.status_code == 201

    res = client.patch("/api/v1/bo/tenants/t-01/publish", json={"is_public_published": True, "review_notes": "승인 완료"})
    print(f"10. PATCH /api/v1/bo/tenants/t-01/publish -> Status: {res.status_code}")
    assert res.status_code == 200

    res = client.post("/api/v1/bo/tenants/t-01/billing/manual-adjustment", json={
        "billing_month": "2026-09",
        "manual_adjustment_amount": -50000,
        "adjustment_reason": "하계 특강 할인 정산 반영"
    })
    print(f"11. POST /api/v1/bo/tenants/t-01/billing/manual-adjustment -> Status: {res.status_code}")
    assert res.status_code == 200

    # 6. CO v5.0 - Students, Attendance, Evaluations, Profile Editing (본사 승인 신청)
    res = client.get("/api/v1/co/students")
    print(f"12. GET /api/v1/co/students -> Status: {res.status_code}, Count: {res.json().get('count')}")
    assert res.status_code == 200

    res = client.post("/api/v1/co/students", json={
        "name": "윤서진",
        "grade": "고3",
        "target_major": "시각디자인",
        "target_univ": "국민대",
        "parent_phone": "010-1122-3344",
        "status": "ENROLLED"
    })
    print(f"13. POST /api/v1/co/students -> Status: {res.status_code}, New Student: {res.json().get('student', {}).get('name')}")
    assert res.status_code == 201

    res = client.get("/api/v1/co/profile")
    print(f"14. GET /api/v1/co/profile -> Status: {res.status_code}, Slug: {res.json().get('profile', {}).get('slug')}")
    assert res.status_code == 200

    res = client.put("/api/v1/co/profile", json={
        "name": "강남 미술학원 본원",
        "slug": "gangnam-main",
        "intro_text": "2026학년도 최다 합격생 배출 명문관.",
        "highlight_stats": [{"title": "국민대 합격률", "value": "91.2%"}],
        "request_publish_approval": True
    })
    print(f"15. PUT /api/v1/co/profile -> Status: {res.status_code}, ApprovalStatus: {res.json().get('profile', {}).get('approval_status')}")
    assert res.status_code == 200

    # 7. Policies
    res = client.get("/api/v1/policies")
    print(f"16. GET /api/v1/policies -> Status: {res.status_code}")
    assert res.status_code == 200

    print("=" * 75)
    print("FINAL VERDICT: ALL PASS - v5.0 FastAPI 3-Tier CRUD & Records Fully Verified.")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()

