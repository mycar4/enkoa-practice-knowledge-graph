-- ==============================================================================
-- 🏫 ART:READY 프랜차이즈 B2B 플랫폼 — v5.0 스키마 확장 DDL
-- 1. 성적 기록함 (STUDENT_GRADE_RECORDS)
-- 2. 서류함 (STUDENT_DOCUMENTS)
-- 3. 본사 공지사항 (PLATFORM_NOTICES)
-- 4. 본사 관리자 계정 (ADMIN_USERS)
-- 5. 가맹학원 소개 페이지 필드 확장 (TENANTS.slug, intro_text, etc.)
-- ==============================================================================

-- 1. 가맹학원 테이블(TENANTS) 소개 페이지 컬럼 확장
ALTER TABLE tenants 
ADD COLUMN IF NOT EXISTS slug VARCHAR(64) UNIQUE,
ADD COLUMN IF NOT EXISTS intro_text TEXT,
ADD COLUMN IF NOT EXISTS logo_url TEXT,
ADD COLUMN IF NOT EXISTS highlight_stats JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS contact_info JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS is_public_published BOOLEAN DEFAULT false;

-- 기본 시드 학원 slug 설정
UPDATE tenants SET slug = 'gangnam-main', is_public_published = true WHERE slug IS NULL AND name LIKE '%강남%';
UPDATE tenants SET slug = 'hongdae-campus', is_public_published = true WHERE slug IS NULL AND name LIKE '%홍대%';

-- 2. 성적 기록함 테이블 (STUDENT_GRADE_RECORDS)
CREATE TABLE IF NOT EXISTS student_grade_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    label VARCHAR(64) NOT NULL, -- 예: "고2-2학기", "2026 수시모의 1차"
    source_type VARCHAR(32) NOT NULL DEFAULT 'nice_html', -- 'nice_html' | 'txt' | 'manual'
    raw_file_ref TEXT, -- Storage 경로(원본 파일)
    parsed_json JSONB NOT NULL DEFAULT '{}'::jsonb, -- 성적 파싱 결과 데이터
    is_primary BOOLEAN DEFAULT false, -- 대표 성적 여부
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. 서류함 테이블 (STUDENT_DOCUMENTS)
CREATE TABLE IF NOT EXISTS student_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    label VARCHAR(128) NOT NULL, -- 예: "국민대 시디과 자기소개서 초안"
    doc_type VARCHAR(32) NOT NULL DEFAULT 'STATEMENT', -- 'STATEMENT' | 'PORTFOLIO_DESC' | 'INTERVIEW_MEMO'
    raw_file_ref TEXT,
    feedback_json JSONB DEFAULT '{}'::jsonb, -- 첨삭 피드백 결과
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. 본사 공지사항 테이블 (PLATFORM_NOTICES)
CREATE TABLE IF NOT EXISTS platform_notices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(256) NOT NULL,
    content TEXT NOT NULL,
    target VARCHAR(32) NOT NULL DEFAULT 'ALL', -- 'ALL' | 'DIRECTORS' | 'INSTRUCTORS' | 'STUDENTS'
    author VARCHAR(64) NOT NULL DEFAULT '엔코아 본사',
    is_pinned BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. 본사 관리자 계정 테이블 (ADMIN_USERS)
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(128) UNIQUE NOT NULL,
    name VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'BO_MANAGER', -- 'SUPER_ADMIN' | 'BO_MANAGER' | 'COMPLIANCE'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ==============================================================================
-- Row-Level Security (RLS) 정책
-- ==============================================================================
ALTER TABLE student_grade_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

-- 공지사항: 전체 조회 가능
CREATE POLICY notice_read_all ON platform_notices
    FOR SELECT USING (true);

-- 학원 공개 소개: is_public_published = true 인 경우 누구나 조회 가능
CREATE POLICY tenant_public_read ON tenants
    FOR SELECT USING (is_public_published = true OR status = 'ACTIVE');

-- 성적 기록함/서류함: 본인 학생 및 연동된 학부모/학원 강사만 조회
CREATE POLICY student_grade_records_owner ON student_grade_records
    FOR ALL USING (
        student_id IN (
            SELECT id FROM student_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY student_documents_owner ON student_documents
    FOR ALL USING (
        student_id IN (
            SELECT id FROM student_profiles WHERE user_id = auth.uid()
        )
    );
