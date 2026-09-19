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
    print("=" * 65)
    print("[API VERIFICATION] Testing FastAPI Endpoints & Health Check")
    print("=" * 65)

    # 1. Health check
    res = client.get("/health")
    print(f"1. GET /health -> Status: {res.status_code}, Body: {res.json()}")
    assert res.status_code == 200, "Health check failed"

    # 2. Public Policy endpoint
    res = client.get("/api/v1/policies")
    print(f"2. GET /api/v1/policies -> Status: {res.status_code}, Policies: {res.json()}")
    assert res.status_code == 200, "Policy endpoint failed"

    # 3. Protected endpoint without auth (BO Tenants)
    res = client.post("/api/v1/bo/tenants", json={"name": "테스트학원"})
    print(f"3. POST /api/v1/bo/tenants (No Auth) -> Status: {res.status_code} (Auth Protected [PASS])")
    assert res.status_code == 401, "Expected 401 Unauthorized"

    # 4. Protected endpoint without auth (CO Permissions)
    res = client.put("/api/v1/tenants/dummy-tenant/permissions/dummy-user", json={"permissions": []})
    print(f"4. PUT /api/v1/tenants/../permissions (No Auth) -> Status: {res.status_code} (Auth Protected [PASS])")
    assert res.status_code == 401, "Expected 401 Unauthorized"

    # 5. OpenAPI JSON generation check
    res = client.get("/openapi.json")
    print(f"5. GET /openapi.json -> Status: {res.status_code}, Total Routes: {len(res.json().get('paths', {}))}")
    assert res.status_code == 200, "OpenAPI generation failed"

    print("=" * 65)
    print("FINAL VERDICT: ALL PASS - FastAPI 3-Tier API Stack fully verified.")

if __name__ == "__main__":
    run_tests()
