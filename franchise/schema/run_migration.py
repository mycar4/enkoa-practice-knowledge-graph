import os
import sys
import argparse
from pathlib import Path

def run_migration(db_url: str):
    """
    Supabase PostgreSQL에 01_initial_schema.sql을 실행하고 실측 검증 데이터를 출력합니다.
    """
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print("[ERROR] psycopg2-binary 패키지가 필요합니다. (pip install psycopg2-binary)")
        sys.exit(1)

    sql_path = Path(__file__).parent / "01_initial_schema.sql"
    if not sql_path.exists():
        print(f"[ERROR] SQL 파일을 찾을 수 없습니다: {sql_path}")
        sys.exit(1)

    print(f"[INFO] 1단계: DDL 파일 로드 ({sql_path.name})")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print(f"[INFO] 2단계: Supabase PostgreSQL 연결 시도...")
    try:
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("[SUCCESS] DB 연결 성공!")
    except Exception as e:
        print(f"[FAIL] DB 연결 실패: {e}")
        sys.exit(1)

    print("[INFO] 3단계: 통합 스키마 DDL 실행 중...")
    try:
        cursor.execute(sql_content)
        print("[SUCCESS] DDL 스크립트 실행 완료!")
    except Exception as e:
        print(f"[FAIL] DDL 실행 에러: {e}")
        cursor.close()
        conn.close()
        sys.exit(1)

    # 4단계: 물리적 실측 검증 (Ground-Truth Verification)
    print("\n" + "=" * 60)
    print("📊 [실측 검증] 생성된 테이블 및 RLS 활성화 상태")
    print("=" * 60)
    
    target_tables = [
        "tenants", "branches", "user_profiles", "menu_permissions",
        "student_profiles", "instructor_student_maps", "parent_student_maps",
        "attendance", "tuition_ledger", "class_album", "student_evaluations",
        "subscriptions", "tenant_billing", "policy_documents", "policy_agreements"
    ]

    query = """
    SELECT 
        c.relname AS table_name,
        c.relrowsecurity AS rls_enabled
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' 
      AND c.relkind = 'r'
      AND c.relname = ANY(%s)
    ORDER BY c.relname;
    """
    
    cursor.execute(query, (target_tables,))
    results = cursor.fetchall()
    found_tables = {row[0]: row[1] for row in results}

    print(f"{'테이블명':<25} | {'존재 여부':<10} | {'RLS 활성화':<10}")
    print("-" * 55)

    all_passed = True
    for tbl in sorted(target_tables):
        exists = tbl in found_tables
        rls = found_tables.get(tbl, False)
        status_exists = "EXISTS ✅" if exists else "MISSING ❌"
        status_rls = "ON ✅" if rls else "OFF ❌"
        
        if not exists or not rls:
            all_passed = False
            
        print(f"{tbl:<25} | {status_exists:<10} | {status_rls:<10}")

    print("-" * 55)
    if all_passed and len(found_tables) == len(target_tables):
        print("🏆 [최종 결과] ALL PASS ✅ - 15개 핵심 테이블 및 RLS 완벽 반영 확인")
    else:
        print("⚠️ [최종 결과] FAIL ❌ - 누락된 테이블 또는 비활성 RLS 존재")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supabase B2B Schema Migration Runner")
    parser.add_argument("--db-url", type=str, default=os.getenv("SUPABASE_DB_URL"), help="Supabase Postgres Connection String")
    args = parser.parse_args()

    if not args.db_url:
        print("[ERROR] --db-url 옵션 또는 SUPABASE_DB_URL 환경변수가 지정되지 않았습니다.")
        print("사용법: python run_migration.py --db-url \"postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres\"")
        sys.exit(1)

    run_migration(args.db_url)
