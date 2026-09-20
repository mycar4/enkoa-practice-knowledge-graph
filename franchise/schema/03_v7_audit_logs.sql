-- ==============================================================================
-- ART:READY 프랜차이즈 플랫폼 v7.0 - 감사 로그 테이블 추가
-- 2026-09-21: bo/audit-logs가 하드코딩된 가짜 로그 1건을 반환하고 있던 것을
-- 실제 영속화된 로그로 교체하기 위한 마이그레이션. branches/menu_permissions/
-- parent_student_maps는 01_initial_schema.sql에 이미 존재하므로 이 파일에서는
-- audit_logs만 추가한다.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_email VARCHAR(255),           -- 행위자 이메일(비로그인/시스템 액션이면 NULL)
    action VARCHAR(100) NOT NULL,       -- 예: 'TENANT_STATUS_CHANGE', 'TENANT_PUBLISH', 'ADMIN_CREATED', 'USER_SIGNUP'
    target VARCHAR(255),                -- 예: 대상 학원명/이메일 등 사람이 읽을 수 있는 설명
    detail JSONB DEFAULT '{}'::jsonb,   -- 변경 전/후 값 등 구조화된 상세 정보
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);

-- 이 테이블은 서비스 API(service_role 키)만 기록/조회한다 - 일반 사용자가
-- 클라이언트에서 직접 읽거나 쓸 수 없어야 하므로 RLS를 켜고 별도 정책은
-- 두지 않는다(service_role은 RLS를 우회하므로 우리 백엔드는 항상 접근 가능).
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
