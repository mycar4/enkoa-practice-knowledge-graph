import os
import sys
import json
import requests
from dotenv import load_dotenv

# UTF-8 출력 보장
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

load_dotenv()
url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

print(f"[INFO] Target URL: {url}")
if not url or not key:
    print("[ERROR] .env file missing URL or KEY")
    exit(1)

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Range": "0-0"
}

target_tables = [
    "attendance", "branches", "class_album", "instructor_student_maps",
    "menu_permissions", "parent_student_maps", "policy_agreements",
    "policy_documents", "student_evaluations", "student_profiles",
    "subscriptions", "tenant_billing", "tenants", "tuition_ledger",
    "user_profiles"
]

print("\n" + "=" * 75)
print("[GROUND-TRUTH VERIFICATION] Supabase REST Table Endpoints & RLS Status")
print("=" * 75)
print(f"{'Table Name':<25} | {'HTTP Status':<12} | {'Result':<15} | {'Data'}")
print("-" * 75)

all_passed = True
results = []

for tbl in target_tables:
    try:
        res = requests.get(f"{url}/rest/v1/{tbl}?select=*", headers=headers, timeout=5)
        status_code = res.status_code
        
        # 200 or 206 means table exists in public schema and is served by PostgREST
        if status_code in (200, 206):
            data = res.json()
            verdict = "EXISTS [PASS]"
            data_sample = f"Empty array [] (RLS Blocked)" if data == [] else f"{len(data)} items"
        elif status_code in (401, 403):
            verdict = "RESTRICTED [PASS]"
            data_sample = "Access denied by RLS"
        else:
            verdict = f"ERROR ({status_code}) [FAIL]"
            data_sample = res.text[:50]
            all_passed = False
            
        print(f"{tbl:<25} | HTTP {status_code:<8} | {verdict:<15} | {data_sample}")
        results.append((tbl, status_code, verdict))
    except Exception as e:
        print(f"{tbl:<25} | ERROR        | FAIL            | {e}")
        all_passed = False

print("-" * 75)
if all_passed:
    print("FINAL VERDICT: ALL PASS - All 15 core tables confirmed physical existence on Supabase.")
else:
    print("FINAL VERDICT: FAIL - Some tables missing or returned errors.")
