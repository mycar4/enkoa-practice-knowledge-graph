-- ==============================================================================
-- 🏫 ART:READY 프랜차이즈 B2B 플랫폼 — 통합 데이터베이스 스키마 (v2.0)
-- ==============================================================================
-- 인프라: Supabase (PostgreSQL 15+)
-- 아키텍처: 3-Tier (BO: 통합관리 / CO: 학원별 관리 / FO: 원생 및 학부모)
-- 멀티테넌시: Row-Level Security (RLS) 기반 테넌트 격리 + 개인 단위 2중 접근 제어
-- 준수 지침: ART_FRANCHISE_PLATFORM_ANTIGRAVITY_BRIEF_v2.md
-- ==============================================================================

-- 1. 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 2. 핵심 비즈니스 테이블 정의 (Core Tables)
-- ==============================================================================

-- 2.1 가맹 학원/브랜드 (TENANTS)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    business_number VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    contract_months INTEGER DEFAULT 36,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_tenant_status CHECK (status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'CLOSED'))
);

-- 2.2 학원 지점 (BRANCHES)
CREATE TABLE IF NOT EXISTS branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_name VARCHAR(100) NOT NULL,
    address TEXT,
    contact VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2.3 통합 사용자 프로필 (USER_PROFILES)
-- Supabase auth.users 와 1:1 바인딩
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL, -- BO 관리자는 NULL 가능
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_user_role CHECK (role IN ('BO_ADMIN', 'BO_MANAGER', 'TENANT_ADMIN', 'INSTRUCTOR', 'STUDENT', 'PARENT')),
    CONSTRAINT chk_user_status CHECK (status IN ('INVITED', 'PENDING_GUARDIAN_CONSENT', 'ACTIVE', 'BLOCKED', 'WITHDRAWN'))
);

-- 2.4 메뉴 단위 세부 권한 (MENU_PERMISSIONS - 공백 ② 해결)
CREATE TABLE IF NOT EXISTS menu_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    menu_key VARCHAR(50) NOT NULL, -- 예: 'student.list', 'student.evaluation', 'billing.view'
    can_read BOOLEAN DEFAULT false,
    can_write BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_user_menu UNIQUE (user_id, menu_key)
);

-- 2.5 학생 상세 프로필 (STUDENT_PROFILES)
CREATE TABLE IF NOT EXISTS student_profiles (
    user_id UUID PRIMARY KEY REFERENCES user_profiles(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    birth_date DATE NOT NULL, -- 만 14세 미만 조건부 동의 검증 필수 컬럼
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    target_major VARCHAR(100),
    target_schools JSONB DEFAULT '[]'::jsonb,
    mock_scores JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_student_status CHECK (status IN ('ACTIVE', 'PROSPECTIVE', 'ON_LEAVE', 'WITHDRAWN'))
);

-- 2.6 강사-학생 배정 매핑 (INSTRUCTOR_STUDENT_MAPS)
CREATE TABLE IF NOT EXISTS instructor_student_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    instructor_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_instructor_student UNIQUE (instructor_id, student_id)
);

-- 2.7 학부모-학생 연동 매핑 (PARENT_STUDENT_MAPS)
CREATE TABLE IF NOT EXISTS parent_student_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    relationship VARCHAR(20) NOT NULL DEFAULT 'MOTHER',
    verified_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    linked_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_relationship CHECK (relationship IN ('MOTHER', 'FATHER', 'GUARDIAN', 'OTHER')),
    CONSTRAINT chk_parent_verified CHECK (verified_status IN ('PENDING', 'VERIFIED')),
    CONSTRAINT uq_parent_student UNIQUE (parent_id, student_id)
);

-- 2.8 원생 출결 기록 (ATTENDANCE)
CREATE TABLE IF NOT EXISTS attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    class_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'PRESENT',
    remark TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_attendance_status CHECK (status IN ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED'))
);

-- 2.9 학생별 수강료 수납 대장 (TUITION_LEDGER)
CREATE TABLE IF NOT EXISTS tuition_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    billing_month VARCHAR(7) NOT NULL, -- 형식: YYYY-MM
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'UNPAID',
    due_day INTEGER DEFAULT 25,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_tuition_status CHECK (status IN ('PAID', 'UNPAID', 'PARTIAL', 'CANCELLED'))
);

-- 2.10 수업앨범 (CLASS_ALBUM - 단체 공유용)
CREATE TABLE IF NOT EXISTS class_album (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    instructor_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    class_date DATE NOT NULL DEFAULT CURRENT_DATE,
    content_text VARCHAR(500),
    image_urls JSONB DEFAULT '[]'::jsonb, -- 비공개 버킷 Signed URL 처리 대상
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2.11 개인 실기 평가 및 피드백 (STUDENT_EVALUATIONS)
CREATE TABLE IF NOT EXISTS student_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    instructor_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    evaluation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    subject VARCHAR(100) NOT NULL,
    score INTEGER CHECK (score >= 0 AND score <= 100),
    feedback TEXT,
    image_urls JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2.12 학원 구독 계약 (SUBSCRIPTIONS)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_tier VARCHAR(30) NOT NULL DEFAULT 'BASIC',
    student_quota INTEGER DEFAULT 50,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    payment_status VARCHAR(30) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_plan_tier CHECK (plan_tier IN ('BASIC', 'PRO', 'ENTERPRISE'))
);

-- 2.13 학원별 월별 정산 및 수기결제 이력 (TENANT_BILLING)
CREATE TABLE IF NOT EXISTS tenant_billing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_month VARCHAR(7) NOT NULL, -- 형식: YYYY-MM
    expected_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    manual_adjustment_amount NUMERIC(12, 2) DEFAULT 0,
    adjustment_reason TEXT, -- 수기결제 조정 시 필수 기입
    final_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_billing_payment_status CHECK (payment_status IN ('PENDING', 'UNPAID', 'HELD', 'SETTLED', 'PAID')),
    -- 수기결제 조정액이 0이 아닐 경우 반드시 사유를 입력해야 하는 불변식 제약조건
    CONSTRAINT chk_manual_adjustment_reason CHECK (
        manual_adjustment_amount IS NULL 
        OR manual_adjustment_amount = 0 
        OR (adjustment_reason IS NOT NULL AND length(trim(adjustment_reason)) > 0)
    )
);

-- 2.14 정책 문서 버전관리 (POLICY_DOCUMENTS - 공백 ③ 해결)
CREATE TABLE IF NOT EXISTS policy_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type VARCHAR(30) NOT NULL,
    version VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_policy_doc_type CHECK (doc_type IN ('TERMS', 'PRIVACY', 'THIRD_PARTY', 'COLLECTION_CONSENT'))
);

-- 2.15 정책 동의 이력 (POLICY_AGREEMENTS)
CREATE TABLE IF NOT EXISTS policy_agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    policy_id UUID NOT NULL REFERENCES policy_documents(id) ON DELETE RESTRICT,
    agreed_at TIMESTAMPTZ DEFAULT now(),
    guardian_consent_at TIMESTAMPTZ, -- 만 14세 미만 법정대리인 동의 일시
    CONSTRAINT uq_user_policy UNIQUE (user_id, policy_id)
);

-- ==============================================================================
-- 3. RLS 헬퍼 함수 (Security Functions)
-- ==============================================================================

-- 3.1 현재 로그인 유저의 tenant_id 반환
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
    SELECT tenant_id FROM user_profiles WHERE id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- 3.2 현재 로그인 유저의 role 반환
CREATE OR REPLACE FUNCTION current_user_role()
RETURNS VARCHAR AS $$
    SELECT role FROM user_profiles WHERE id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- 3.3 BO 관리자(본사 플랫폼 운영자) 여부 확인
CREATE OR REPLACE FUNCTION is_bo_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM user_profiles 
        WHERE id = auth.uid() AND role IN ('BO_ADMIN', 'BO_MANAGER')
    );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ==============================================================================
-- 4. Row-Level Security (RLS) 정책 활성화 및 설정
-- ==============================================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE menu_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE instructor_student_maps ENABLE ROW LEVEL SECURITY;
ALTER TABLE parent_student_maps ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE tuition_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_album ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_billing ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_agreements ENABLE ROW LEVEL SECURITY;

-- 4.1 TENANTS 정책
CREATE POLICY rls_tenants_bo_all ON tenants
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_tenants_member_select ON tenants
    FOR SELECT TO authenticated
    USING (id = current_tenant_id());

-- 4.2 TENANT_BILLING 정책 (학원장은 조회만 가능, BO만 수정)
CREATE POLICY rls_billing_bo_all ON tenant_billing
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_billing_admin_select ON tenant_billing
    FOR SELECT TO authenticated
    USING (tenant_id = current_tenant_id() AND current_user_role() = 'TENANT_ADMIN');

-- 4.3 USER_PROFILES 정책
CREATE POLICY rls_user_profiles_bo ON user_profiles
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_user_profiles_tenant_admin ON user_profiles
    FOR ALL TO authenticated
    USING (tenant_id = current_tenant_id() AND current_user_role() = 'TENANT_ADMIN');

CREATE POLICY rls_user_profiles_self ON user_profiles
    FOR ALL TO authenticated
    USING (id = auth.uid());

-- 4.4 MENU_PERMISSIONS 정책
CREATE POLICY rls_menu_perm_bo ON menu_permissions
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_menu_perm_tenant_admin ON menu_permissions
    FOR ALL TO authenticated
    USING (tenant_id = current_tenant_id() AND current_user_role() = 'TENANT_ADMIN');

CREATE POLICY rls_menu_perm_self_read ON menu_permissions
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

-- 4.5 STUDENT_PROFILES 개인 단위 격리 정책 (핵심 2중 격리)
CREATE POLICY rls_student_profiles_bo ON student_profiles
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_student_profiles_tenant_admin ON student_profiles
    FOR ALL TO authenticated
    USING (tenant_id = current_tenant_id() AND current_user_role() = 'TENANT_ADMIN');

CREATE POLICY rls_student_profiles_individual ON student_profiles
    FOR SELECT TO authenticated
    USING (
        -- 1. 학생 본인
        user_id = auth.uid()
        -- 2. 배정된 강사
        OR EXISTS (
            SELECT 1 FROM instructor_student_maps
            WHERE instructor_id = auth.uid() AND student_id = student_profiles.user_id
        )
        -- 3. 인증된 학부모
        OR EXISTS (
            SELECT 1 FROM parent_student_maps
            WHERE parent_id = auth.uid() AND student_id = student_profiles.user_id AND verified_status = 'VERIFIED'
        )
    );

-- 4.6 STUDENT_EVALUATIONS 개인 단위 격리 정책
CREATE POLICY rls_evaluations_bo ON student_evaluations
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_evaluations_tenant_admin ON student_evaluations
    FOR ALL TO authenticated
    USING (tenant_id = current_tenant_id() AND current_user_role() = 'TENANT_ADMIN');

CREATE POLICY rls_evaluations_instructor ON student_evaluations
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM instructor_student_maps
            WHERE instructor_id = auth.uid() AND student_id = student_evaluations.student_id
        )
    );

CREATE POLICY rls_evaluations_student_parent ON student_evaluations
    FOR SELECT TO authenticated
    USING (
        student_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM parent_student_maps
            WHERE parent_id = auth.uid() AND student_id = student_evaluations.student_id AND verified_status = 'VERIFIED'
        )
    );

-- 4.7 CLASS_ALBUM 정책
CREATE POLICY rls_class_album_tenant_select ON class_album
    FOR SELECT TO authenticated
    USING (tenant_id = current_tenant_id());

CREATE POLICY rls_class_album_instructor_insert ON class_album
    FOR INSERT TO authenticated
    WITH CHECK (
        tenant_id = current_tenant_id() 
        AND current_user_role() IN ('TENANT_ADMIN', 'INSTRUCTOR')
    );

-- 4.8 POLICY_DOCUMENTS 정책 (누구나 활성 정책은 조회 가능, BO만 관리)
CREATE POLICY rls_policy_docs_bo ON policy_documents
    FOR ALL TO authenticated
    USING (is_bo_admin());

CREATE POLICY rls_policy_docs_public_active ON policy_documents
    FOR SELECT TO anon, authenticated
    USING (is_active = true);

-- 4.9 POLICY_AGREEMENTS 정책
CREATE POLICY rls_policy_agree_self ON policy_agreements
    FOR ALL TO authenticated
    USING (user_id = auth.uid());

-- ==============================================================================
-- 5. 비즈니스 불변식 트리거 및 자동화 로직
-- ==============================================================================

-- 5.1 만 14세 미만 조건부 가입 검증 트리거 (아동보호법 제22조의2 대응)
CREATE OR REPLACE FUNCTION trg_check_guardian_consent_func()
RETURNS TRIGGER AS $$
DECLARE
    v_age INTEGER;
BEGIN
    -- 만 나이 계산
    v_age := date_part('year', age(NEW.birth_date));
    
    -- 만 14세 미만인 경우
    IF v_age < 14 THEN
        -- 학부모 검증 완료 여부 확인
        IF NOT EXISTS (
            SELECT 1 FROM parent_student_maps 
            WHERE student_id = NEW.user_id AND verified_status = 'VERIFIED'
        ) THEN
            -- 프로필 상태를 법정대리인 동의 대기로 전환
            UPDATE user_profiles 
            SET status = 'PENDING_GUARDIAN_CONSENT' 
            WHERE id = NEW.user_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_check_guardian_consent ON student_profiles;
CREATE TRIGGER trg_check_guardian_consent
    AFTER INSERT OR UPDATE OF birth_date ON student_profiles
    FOR EACH ROW
    EXECUTE FUNCTION trg_check_guardian_consent_func();

-- 5.2 학부모 연동 승인 시 학생 계정 자동 활성화 트리거
CREATE OR REPLACE FUNCTION trg_activate_student_on_guardian_consent_func()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.verified_status = 'VERIFIED' THEN
        UPDATE user_profiles 
        SET status = 'ACTIVE' 
        WHERE id = NEW.student_id AND status = 'PENDING_GUARDIAN_CONSENT';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_activate_student_consent ON parent_student_maps;
CREATE TRIGGER trg_activate_student_consent
    AFTER INSERT OR UPDATE OF verified_status ON parent_student_maps
    FOR EACH ROW
    EXECUTE FUNCTION trg_activate_student_on_guardian_consent_func();
