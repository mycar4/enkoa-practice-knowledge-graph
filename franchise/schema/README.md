# 🚀 Supabase 스키마 반영 및 마이그레이션 가이드

본 문서는 **ART:READY 프랜차이즈 B2B 플랫폼(v2.0)**의 데이터베이스 스키마를 Supabase 클라우드 인스턴스에 안전하게 반영하기 위한 절차서입니다.

---

## 📁 산출물 구성
* [`01_initial_schema.sql`](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/franchise/schema/01_initial_schema.sql): 13개 핵심 테이블, 2중 RLS 정책, 만14세 조건부 동의 트리거 일체
* [`run_migration.py`](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/franchise/schema/run_migration.py): 파이썬 기반 원격 자동 마이그레이션 및 실측 검증 스크립트

---

## 🛠️ 반영 방법

### 방법 1: Supabase 대시보드 SQL Editor 직접 실행 (가장 추천)
1. [Supabase Console](https://supabase.com/dashboard)에서 생성한 프로젝트 진입
2. 좌측 메뉴에서 **[SQL Editor]** 아이콘 클릭
3. **`+ New query`** 클릭
4. [`01_initial_schema.sql`](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/franchise/schema/01_initial_schema.sql) 파일의 전체 내용을 복사하여 붙여넣기
5. 우측 하단의 **`Run`** 버튼 클릭
6. `Success. No rows returned` 메시지 확인

### 방법 2: Python 러너를 통한 자동 실행 및 실측 검증
1. Supabase **Project Settings → Database → Connection string (URI)** 복사  
   *(예: `postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`)*
2. 환경변수 또는 실행 인자로 전달하여 러너 가동:
   ```powershell
   python franchise/schema/run_migration.py --db-url "postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres"
   ```
3. 콘솔에 13개 테이블 및 RLS 정책 생성 결과가 물리적 실측치로 자동 출력됩니다.

---

## 🔒 스토리지 버킷 설정 (필수 사전 작업)
지시서 제3.9절에 따라 학생 실기 작품 이미지 보호를 위해 비공개 버킷을 생성해야 합니다:
1. 좌측 메뉴 **[Storage]** 진입
2. **`New bucket`** 클릭
3. Name: `art-franchise-private`
4. **Public bucket 스위치: `OFF` (반드시 비공개)**
5. 저장 클릭 (Signed URL로만 접근하도록 백엔드 API에서 제어)
