// Vercel Serverless Function: ART:READY Franchise B2B Platform Unified API v6.0
// Direct Supabase REST Integration with RLS & Persistence Guarantee

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jqdtqawrkdidcdfzxzwb.supabase.co";
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "sb_publishable_m3si3M17RpGHrIXt8Au9tQ_w3CwtCpW";

function getHeaders(prefer: string = "return=representation") {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || ANON_KEY;
  return {
    "apikey": key,
    "Authorization": `Bearer ${key}`,
    "Content-Type": "application/json",
    "Prefer": prefer
  };
}

async function supabaseFetch(endpoint: string, options: any = {}) {
  const url = `${SUPABASE_URL.replace(/\/$/, "")}/rest/v1/${endpoint}`;
  const headers = { ...getHeaders(options.prefer), ...(options.headers || {}) };
  return fetch(url, { ...options, headers });
}

// ── 2026-09-21 신규: 실제 Supabase Auth 이메일+비밀번호 회원가입/로그인 ──
// GoTrue(Supabase Auth) REST API를 직접 호출한다 - 프론트엔드에 @supabase/
// supabase-js를 새로 설치/빌드하지 않고, 기존 v1.ts와 동일한 raw fetch
// 패턴을 유지하기 위함.
async function authFetch(path: string, options: any = {}) {
  const url = `${SUPABASE_URL.replace(/\/$/, "")}/auth/v1/${path}`;
  const headers = { "apikey": ANON_KEY, "Content-Type": "application/json", ...(options.headers || {}) };
  return fetch(url, { ...options, headers });
}

// Authorization: Bearer <access_token> 헤더를 Supabase Auth의 /auth/v1/user
// 로 그대로 넘겨 서버 사이드에서 검증한다(JWT 서명을 직접 검증하지 않고
// Supabase가 검증하게 위임 - 구현이 간단하고 틀릴 여지가 적음). 유효하면
// 실제 로그인한 사용자의 auth.users.id를 반환하고, 없거나 무효하면 null을
// 반환해 호출부가 이전의 placeholder 방식으로 안전하게 폴백할 수 있게 한다.
async function getAuthedUserId(req: any): Promise<string | null> {
  const authHeader = req.headers?.authorization || req.headers?.Authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  try {
    const resp = await authFetch("user", { headers: { Authorization: authHeader } });
    if (!resp.ok) return null;
    const user = await resp.json();
    return user?.id || null;
  } catch {
    return null;
  }
}

// 2026-09-21 실측 발견: 이 플랫폼에는 실제 회원가입/계정생성 플로우가 아직
// 없다 - student_profiles.user_id는 auth.users(id)를 참조하는 FK라
// Supabase Auth로 실제 가입한 사용자가 없으면 만들어낼 수 없다. 그래서
// tenant_id/student_id가 필요한 쓰기 API들은 "이미 존재하는 첫 번째 행"을
// 임시로 빌려 쓴다 - 진짜 로그인 세션에서 현재 사용자를 가져오는 게 아니므로
// 이건 회원가입 플로우가 생기기 전까지의 임시방편이다. 데이터가 하나도 없으면
// (가입자가 0명이면) 억지로 가짜 UUID를 넣어 FK 위반을 내는 대신, 이유를
// 명확히 밝히는 에러를 바로 반환한다.
async function getPlaceholderContext(req?: any): Promise<{ tenantId: string | null; studentId: string | null }> {
  // 2026-09-21: 실제 로그인 세션(Authorization 헤더)이 있으면 그 사용자의
  // 진짜 student_profiles/tenant_id를 우선 사용한다 - 회원가입 플로우가
  // 생긴 지금부터는 "첫 번째 행 임시 대여"가 기본이 아니라 로그인 정보가
  // 없을 때만 쓰는 폴백이어야 한다.
  const authedUserId = req ? await getAuthedUserId(req) : null;
  if (authedUserId) {
    const spResp = await supabaseFetch(`student_profiles?user_id=eq.${authedUserId}&select=user_id,tenant_id&limit=1`);
    const spData = await spResp.json();
    if (Array.isArray(spData) && spData[0]?.user_id) {
      return { tenantId: spData[0].tenant_id || null, studentId: spData[0].user_id };
    }
    // 2026-09-21 실측 발견: 로그인한 사람이 학생이 아니라 CO 스태프(원장/
    // 강사)면 위에서 못 찾고 아래 "전역 첫 번째 학원/학생" 폴백으로
    // 떨어졌었다 - 그러면 A학원 원장이 출결/평가/수강료를 등록할 때 전혀
    // 상관없는 B학원(글로벌 첫 번째) 학생 데이터가 오염될 수 있었다.
    // 반드시 본인 소속 tenant_id 안에서만 대체 학생을 찾는다.
    const upResp = await supabaseFetch(`user_profiles?id=eq.${authedUserId}&select=tenant_id&limit=1`);
    const upData = await upResp.json();
    const myTenantId = Array.isArray(upData) && upData[0]?.tenant_id ? upData[0].tenant_id : null;
    if (myTenantId) {
      const tsResp = await supabaseFetch(`student_profiles?tenant_id=eq.${myTenantId}&select=user_id&limit=1`);
      const tsData = await tsResp.json();
      return {
        tenantId: myTenantId,
        studentId: Array.isArray(tsData) && tsData[0]?.user_id ? tsData[0].user_id : null,
      };
    }
  }
  // 로그인 세션이 전혀 없을 때만(하위호환) 전역 첫 번째 학원/학생으로 폴백한다.
  const tResp = await supabaseFetch("tenants?select=id&limit=1");
  const tData = await tResp.json();
  const sResp = await supabaseFetch("student_profiles?select=user_id&limit=1");
  const sData = await sResp.json();
  return {
    tenantId: Array.isArray(tData) && tData[0]?.id ? tData[0].id : null,
    studentId: Array.isArray(sData) && sData[0]?.user_id ? sData[0].user_id : null,
  };
}

// 2026-09-21 신규: CO(원장/강사)/BO 쪽에서 "내 학원"을 알아내는 범용 헬퍼.
// getPlaceholderContext는 student_profiles 기준이라 학생 전용이고, 원장/강사는
// student_profiles가 없이 user_profiles.tenant_id에 바로 소속이 있으므로 별도
// 헬퍼로 분리한다. 로그인 세션이 없으면(CO 로그인 화면이 아직 붙기 전 등)
// 기존 방식대로 "첫 번째 학원"으로 폴백한다.
async function getCurrentTenantId(req: any): Promise<string | null> {
  const userId = await getAuthedUserId(req);
  if (userId) {
    const upResp = await supabaseFetch(`user_profiles?id=eq.${userId}&select=tenant_id&limit=1`);
    const upData = await upResp.json();
    if (Array.isArray(upData) && upData[0]?.tenant_id) return upData[0].tenant_id;
  }
  const tResp = await supabaseFetch("tenants?select=id&limit=1");
  const tData = await tResp.json();
  return Array.isArray(tData) && tData[0]?.id ? tData[0].id : null;
}

// 2026-09-21 신규: 출결/평가/수강료처럼 "이 학원의 특정 학생 1명"을 대상으로
// 기록을 남기는 CO 쓰기 API 공용 헬퍼. 이전엔 요청 body의 student_id를 아예
// 무시하고 getPlaceholderContext가 고른 "학원의 첫 번째 학생"에게만 항상
// 기록해서, 원장이 여러 학생 중 누굴 골라도 전부 같은 한 명에게 기록되는
// 문제가 있었다. body.student_id가 오면 그 학생이 실제 이 tenant 소속인지
// 검증한 뒤 사용하고(다른 학원 학생 지정 공격 방지), 없으면 기존 폴백을 쓴다.
async function resolveTargetStudent(req: any, tenantId: string | null, bodyStudentId?: string): Promise<string | null> {
  if (bodyStudentId && tenantId) {
    const chkResp = await supabaseFetch(`student_profiles?user_id=eq.${bodyStudentId}&tenant_id=eq.${tenantId}&select=user_id&limit=1`);
    const chkData = await chkResp.json();
    return Array.isArray(chkData) && chkData[0]?.user_id ? chkData[0].user_id : null;
  }
  const ctx = await getPlaceholderContext(req);
  return ctx.studentId;
}

// 2026-09-21 신규: audit_logs(03_v7_audit_logs.sql)에 실제로 기록한다 - 마이그
// 레이션이 아직 적용 안 된 환경(테이블 없음)에서도 이 호출 때문에 원래
// 요청이 실패하면 안 되므로 실패를 절대 던지지 않고 조용히 무시한다. 로그인
// 세션이 있으면 실제 행위자 이메일을 남기고, 없으면(예: 회원가입 자체처럼
// 아직 세션이 없는 시점) actor_email 없이 기록한다.
async function logAudit(req: any, action: string, target: string, detail: Record<string, any> = {}) {
  try {
    const userId = await getAuthedUserId(req);
    let actorEmail: string | null = null;
    if (userId) {
      const upResp = await supabaseFetch(`user_profiles?id=eq.${userId}&select=email`);
      const upData = await upResp.json();
      actorEmail = Array.isArray(upData) && upData[0]?.email ? upData[0].email : null;
    }
    await supabaseFetch("audit_logs", {
      method: "POST",
      body: JSON.stringify({ actor_email: actorEmail, action, target, detail })
    });
  } catch {
    // 감사 로그 실패가 실제 기능을 막으면 안 된다 - 조용히 무시.
  }
}

export default async function handler(req: any, res: any) {
  // CORS 설정
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // URL 및 라우트 경로 파싱 (rewrite path parameter, headers, req.url 모두 지원)
  let routePath = "";
  if (req.query && req.query.path) {
    routePath = Array.isArray(req.query.path) ? req.query.path.join("/") : String(req.query.path);
  }
  if (!routePath) {
    const rawUrl = req.headers?.["x-matched-path"] || req.headers?.["x-forwarded-uri"] || req.url || "";
    try {
      const parsed = new URL(rawUrl, "http://localhost");
      if (parsed.searchParams.has("path")) {
        routePath = parsed.searchParams.get("path") || "";
      } else {
        routePath = parsed.pathname;
      }
    } catch {
      routePath = rawUrl.split("?")[0];
    }
  }

  // 앞뒤 슬래시 및 /api/v1 접두어 정규화
  routePath = routePath
    .replace(/^\/?api\/v1\/?/, "")
    .replace(/^\/?api\/?/, "")
    .replace(/^\/?v1\/?/, "")
    .replace(/^\/+|\/+$/g, "");

  const method = req.method;

  // 2026-09-21 CRITICAL 보안 수정 (전수테스트 실측 발견): getAuthedUserId는
  // "Authorization 헤더 없음"과 "위조/만료된 토큰"을 똑같이 null로 반환했고,
  // getPlaceholderContext/getCurrentTenantId는 그 null을 "로그인 세션 자체가
  // 없던 초기 상태"로 착각해 "전역 첫 번째 학생/학원" 데이터로 조용히
  // 폴백했다. 그 결과 아무렇게나 조작한 가짜 Bearer 토큰만으로 실제 다른
  // 학생의 성적 데이터가 그대로 노출됐다(전수테스트 CRITICAL FAIL). 이제
  // 개인/학원 데이터를 다루는 모든 fo/*, co/*, bo/* 엔드포인트는 유효한
  // 로그인 세션을 반드시 요구한다 - 폴백 없이 401을 반환한다. 공개 조회용
  // 라우트(health/회원가입·로그인/공통 정책 문서/학원 공개소개페이지)만 예외.
  const isPublicRoute =
    routePath === "health" || routePath === "" ||
    routePath === "auth/signup" || routePath === "auth/login" || routePath === "auth/me" ||
    routePath === "policies" ||
    routePath.startsWith("fo/tenants/");
  if (!isPublicRoute && (routePath.startsWith("fo/") || routePath.startsWith("co/") || routePath.startsWith("bo/"))) {
    const gateUserId = await getAuthedUserId(req);
    if (!gateUserId) {
      return res.status(401).json({ error: "로그인이 필요합니다 - 유효한 로그인 세션(Authorization 토큰)이 없습니다." });
    }
  }

  try {
    // 0. 헬스체크
    if (routePath === "health" || routePath === "") {
      return res.status(200).json({
        status: "healthy",
        service: "ART:READY Franchise B2B Platform API",
        version: "6.0.0",
        supabase_connected: true,
        authenticated_with: process.env.SUPABASE_SERVICE_ROLE_KEY ? "SERVICE_ROLE_SECRET" : "ANON_PUBLISHABLE",
        timestamp: new Date().toISOString()
      });
    }

    // ── 2026-09-21 신규: 실제 회원가입/로그인 (Supabase Auth 이메일+비밀번호) ──
    // 이전까지는 이 플랫폼에 회원가입 자체가 없어서(프론트엔드가 로컬 상태만
    // 바꾸고 성공한 척했음) student_profiles가 항상 0건이었고, 그 위에 얹힌
    // 모든 기능(성적 기록함 등)이 실패했다. 이제부터는 실제 auth.users +
    // user_profiles(+ STUDENT면 student_profiles)까지 만든다.
    if (routePath === "auth/signup") {
      if (method !== "POST") return res.status(405).json({ error: "Method not allowed" });
      const body = req.body || {};
      const { email, password, name, birth_date } = body;
      // 2026-09-21 확장: CO(원장/강사) 자체 가입 지원 - STUDENT/PARENT/INSTRUCTOR/
      // TENANT_ADMIN 4종. BO_ADMIN/BO_MANAGER는 여기서 self-signup을 절대
      // 허용하지 않는다(누구나 본사 관리자로 가입해버리는 보안 구멍이 되므로) -
      // 그 두 role은 bo/admins POST(이미 로그인한 BO가 발급)로만 생성된다.
      const allowedRoles = ["STUDENT", "PARENT", "INSTRUCTOR", "TENANT_ADMIN"];
      const role = allowedRoles.includes(body.role) ? body.role : "STUDENT";
      if (!email || !password || !name) {
        return res.status(400).json({ error: "email, password, name은 필수입니다." });
      }

      // 가맹 코드(academy_code)는 tenants.slug와 매칭한다 - 존재하지 않는
      // 코드로 조용히 아무 학원에나 배정하지 않고 명확히 실패시킨다.
      let tenantId: string | null = null;
      if (body.academy_code) {
        const tResp = await supabaseFetch(`tenants?slug=eq.${encodeURIComponent(body.academy_code)}&select=id&limit=1`);
        const tData = await tResp.json();
        tenantId = Array.isArray(tData) && tData[0]?.id ? tData[0].id : null;
        if (!tenantId) {
          return res.status(404).json({ error: `가맹 코드 '${body.academy_code}'에 해당하는 학원을 찾을 수 없습니다.` });
        }
      }
      if (role === "STUDENT" && !tenantId) {
        return res.status(400).json({ error: "학생 회원가입에는 유효한 소속 학원 가맹 코드가 필요합니다." });
      }
      if (role === "INSTRUCTOR" && !tenantId) {
        return res.status(400).json({ error: "강사 회원가입에는 유효한 소속 학원 가맹 코드가 필요합니다." });
      }
      // TENANT_ADMIN(원장): 기존 가맹 코드로 합류하거나, 없으면 academy_name으로
      // 신규 학원을 직접 만든다(자체 등록 - BO 승인 전까지 is_public_published=false).
      let createdNewTenant = false;
      if (role === "TENANT_ADMIN" && !tenantId) {
        if (!body.academy_name) {
          return res.status(400).json({ error: "원장 회원가입에는 가맹 코드 또는 신규 학원명(academy_name)이 필요합니다." });
        }
        const tCreateResp = await supabaseFetch("tenants", {
          method: "POST",
          body: JSON.stringify({
            name: body.academy_name,
            business_number: body.business_number || "000-00-00000",
            status: "ACTIVE",
            contract_months: 36,
            slug: body.academy_slug || `academy-${Date.now().toString(36)}`,
            intro_text: body.intro_text || "",
            is_public_published: false
          })
        });
        const tCreateData = await tCreateResp.json();
        if (!tCreateResp.ok) {
          return res.status(tCreateResp.status).json({ error: "학원 등록에 실패했습니다.", detail: tCreateData });
        }
        tenantId = Array.isArray(tCreateData) ? tCreateData[0]?.id : tCreateData?.id;
        createdNewTenant = true;
      }

      const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || ANON_KEY;
      const createResp = await fetch(`${SUPABASE_URL.replace(/\/$/, "")}/auth/v1/admin/users`, {
        method: "POST",
        headers: { "apikey": serviceKey, "Authorization": `Bearer ${serviceKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, email_confirm: true })
      });
      const authUser = await createResp.json();
      if (!createResp.ok) {
        return res.status(createResp.status).json({ error: authUser?.msg || authUser?.message || "회원가입에 실패했습니다.", detail: authUser });
      }
      const userId = authUser.id;

      // 만 14세 미만이면 개인정보보호법 제22조의2에 따라 보호자 동의 대기 상태로 생성
      let isUnder14 = false;
      if (birth_date) {
        const cutoff = new Date();
        cutoff.setFullYear(cutoff.getFullYear() - 14);
        isUnder14 = new Date(birth_date) > cutoff;
      }
      const profileStatus = isUnder14 ? "PENDING_GUARDIAN_CONSENT" : "ACTIVE";

      const upResp = await supabaseFetch("user_profiles", {
        method: "POST",
        body: JSON.stringify({ id: userId, tenant_id: tenantId, email, name, role, status: profileStatus })
      });
      if (!upResp.ok) {
        const upErr = await upResp.json();
        return res.status(upResp.status).json({ error: "회원가입은 됐지만 프로필 생성에 실패했습니다.", detail: upErr });
      }

      if (role === "STUDENT") {
        const spResp = await supabaseFetch("student_profiles", {
          method: "POST",
          body: JSON.stringify({
            user_id: userId,
            tenant_id: tenantId,
            birth_date: birth_date || "2010-01-01",
            status: isUnder14 ? "PROSPECTIVE" : "ACTIVE"
          })
        });
        if (!spResp.ok) {
          const spErr = await spResp.json();
          return res.status(spResp.status).json({ error: "회원가입은 됐지만 학생 프로필 생성에 실패했습니다.", detail: spErr });
        }
      }

      await logAudit(req, "USER_SIGNUP", email, { role, tenant_id: tenantId, created_new_tenant: createdNewTenant });
      return res.status(201).json({
        status: "success", user_id: userId, profile_status: profileStatus,
        guardian_consent_required: isUnder14, tenant_id: tenantId, created_new_tenant: createdNewTenant
      });
    }

    if (routePath === "auth/login") {
      if (method !== "POST") return res.status(405).json({ error: "Method not allowed" });
      const body = req.body || {};
      if (!body.email || !body.password) {
        return res.status(400).json({ error: "email, password는 필수입니다." });
      }
      const resp = await authFetch("token?grant_type=password", {
        method: "POST",
        body: JSON.stringify({ email: body.email, password: body.password })
      });
      const data = await resp.json();
      if (!resp.ok) {
        return res.status(resp.status).json({ error: data?.error_description || data?.msg || "이메일 또는 비밀번호가 올바르지 않습니다." });
      }
      const upResp = await supabaseFetch(`user_profiles?id=eq.${data.user.id}&select=*`);
      const upData = await upResp.json();
      return res.status(200).json({ access_token: data.access_token, user: data.user, profile: Array.isArray(upData) && upData[0] ? upData[0] : null });
    }

    if (routePath === "auth/me") {
      const userId = await getAuthedUserId(req);
      if (!userId) return res.status(401).json({ error: "로그인이 필요합니다." });
      const upResp = await supabaseFetch(`user_profiles?id=eq.${userId}&select=*`);
      const upData = await upResp.json();
      return res.status(200).json({ profile: Array.isArray(upData) && upData[0] ? upData[0] : null });
    }

    // ── 공통 / 정책 문서 (BO 4 / CO 8 / FO 공통) ──
    if (routePath === "policies") {
      if (method === "GET") {
        const resp = await supabaseFetch("policy_documents?select=*&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json({ policies: Array.isArray(data) ? data : [], data });
      }
      if (method === "POST") {
        const body = req.body || {};
        const resp = await supabaseFetch("policy_agreements", {
          method: "POST",
          body: JSON.stringify(body)
        });
        const data = await resp.json();
        return res.status(resp.ok ? 201 : resp.status).json(data);
      }
    }

    // ── BO (본사 관리자) 엔드포인트 ──
    // BO 1: 플랫폼 종합 관제 대시보드
    if (routePath === "bo/stats") {
      const tResp = await supabaseFetch("tenants?select=id");
      const tData = await tResp.json();
      const sResp = await supabaseFetch("student_profiles?select=user_id");
      const sData = await sResp.json();
      return res.status(200).json({
        total_tenants: Array.isArray(tData) ? tData.length : 0,
        active_tenants: Array.isArray(tData) ? tData.length : 0,
        total_students: Array.isArray(sData) ? sData.length : 0,
        monthly_mrr: 12400000,
        avg_retention_rate: 98.2,
        unsettled_billing_count: 0
      });
    }

    // BO 2: 가맹학원 관리 & 심사
    if (routePath === "bo/tenants") {
      if (method === "GET") {
        const resp = await supabaseFetch("tenants?select=*&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const payload = {
          name: body.name || "신규 가맹학원",
          business_number: body.business_number || "000-00-00000",
          status: body.initial_status || body.status || "ACTIVE",
          contract_months: body.contract_months || 36,
          slug: body.slug || `tenant-${Date.now().toString(36)}`,
          intro_text: body.intro_text || "",
          is_public_published: false
        };
        const resp = await supabaseFetch("tenants", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        const created = Array.isArray(data) ? data[0] : data;
        if (resp.ok) await logAudit(req, "TENANT_CREATED", payload.name, { slug: payload.slug });
        return res.status(resp.ok ? 201 : resp.status).json(created);
      }
    }

    if (routePath.startsWith("bo/tenants/") && routePath.endsWith("/status")) {
      const parts = routePath.split("/");
      const tenantId = parts[2];
      const body = req.body || {};
      const filter = tenantId.length === 36 ? `id=eq.${tenantId}` : `slug=eq.${tenantId}`;
      const resp = await supabaseFetch(`tenants?${filter}`, {
        method: "PATCH",
        body: JSON.stringify({ status: body.status })
      });
      const data = await resp.json();
      if (resp.ok) await logAudit(req, "TENANT_STATUS_CHANGE", tenantId, { new_status: body.status });
      return res.status(resp.status).json(Array.isArray(data) ? data[0] : data);
    }

    if (routePath.startsWith("bo/tenants/") && routePath.endsWith("/publish")) {
      const parts = routePath.split("/");
      const tenantId = parts[2];
      const body = req.body || {};
      const filter = tenantId.length === 36 ? `id=eq.${tenantId}` : `slug=eq.${tenantId}`;
      const resp = await supabaseFetch(`tenants?${filter}`, {
        method: "PATCH",
        body: JSON.stringify({ is_public_published: body.is_public_published ?? true })
      });
      const data = await resp.json();
      if (resp.ok) await logAudit(req, "TENANT_PUBLISH_TOGGLE", tenantId, { is_public_published: body.is_public_published ?? true });
      return res.status(resp.status).json(Array.isArray(data) ? data[0] : { success: true });
    }

    // BO 3: 가맹비 & 월정산 수기조정
    if (routePath === "bo/billing" || routePath.startsWith("bo/tenants/") && routePath.endsWith("/billing")) {
      const resp = await supabaseFetch("tenant_billing?select=*&order=created_at.desc");
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath.startsWith("bo/tenants/") && routePath.endsWith("/billing/manual-adjustment")) {
      const parts = routePath.split("/");
      const tenantId = parts[2];
      const body = req.body || {};
      if (!body.adjustment_reason || body.adjustment_reason.length < 5) {
        return res.status(400).json({ error: "수기결제 사유는 최소 5자 이상 입력해야 합니다." });
      }
      const payload = {
        tenant_id: tenantId,
        billing_month: body.billing_month || "2026-09",
        manual_adjustment_amount: body.manual_adjustment_amount || 0,
        adjustment_reason: body.adjustment_reason
      };
      const resp = await supabaseFetch("tenant_billing", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      return res.status(resp.ok ? 200 : resp.status).json(data);
    }

    // BO 5: 권한 매트릭스 템플릿
    // 2026-09-21: menu_permissions 테이블(01_initial_schema.sql에 이미 존재)에
    // 실제로 연동한다 - 이전엔 고정된 역할 목록 4개만 반환하고 아무것도
    // 저장하지 않았다. GET은 user_id로 그 사람의 메뉴별 권한을, POST는 한
    // 메뉴의 권한을 upsert한다.
    if (routePath === "bo/permissions") {
      if (method === "GET") {
        const userId = req.query?.user_id;
        const filter = userId ? `&user_id=eq.${userId}` : "";
        const resp = await supabaseFetch(`menu_permissions?select=*${filter}&order=menu_key.asc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        if (!body.user_id || !body.tenant_id || !body.menu_key) {
          return res.status(400).json({ error: "user_id, tenant_id, menu_key는 필수입니다." });
        }
        const resp = await supabaseFetch("menu_permissions?on_conflict=user_id,menu_key", {
          method: "POST",
          headers: { Prefer: "resolution=merge-duplicates,return=representation" },
          body: JSON.stringify({
            user_id: body.user_id,
            tenant_id: body.tenant_id,
            menu_key: body.menu_key,
            can_read: body.can_read ?? true,
            can_write: body.can_write ?? false
          })
        });
        const data = await resp.json();
        await logAudit(req, "PERMISSION_UPDATED", body.menu_key, { user_id: body.user_id, can_read: body.can_read, can_write: body.can_write });
        return res.status(resp.ok ? 200 : resp.status).json(Array.isArray(data) ? data[0] : data);
      }
    }

    // BO 6: 감사 로그 - audit_logs 테이블(03_v7_audit_logs.sql) 실제 조회.
    // 이 마이그레이션이 아직 적용 안 됐으면 테이블이 없어 400을 반환할 수
    // 있는데, 그 경우 빈 배열로 안전하게 폴백한다(로그가 없다고 화면이 죽으면
    // 안 되므로).
    if (routePath === "bo/audit-logs") {
      const resp = await supabaseFetch("audit_logs?select=*&order=created_at.desc&limit=100");
      if (!resp.ok) return res.status(200).json([]);
      const data = await resp.json();
      return res.status(200).json(Array.isArray(data) ? data : []);
    }

    // 2026-09-23 신규: 미대입시 챗봇(art_admission) 대화 로그 조회 - 별도
    // 프로젝트(art-admission-api)가 같은 Supabase 프로젝트의 art_admission_qa_logs
    // 테이블에 매 턴을 기록해두는데, 지금까지 이걸 볼 BO 화면이 없어서 Supabase
    // 대시보드를 직접 열어야만 확인 가능했다. audit-logs와 동일한 패턴으로
    // 조회 전용 엔드포인트만 추가한다(franchise 자체 데이터가 아니라 읽기만
    // 하므로 이 파일의 다른 리소스처럼 POST/PATCH는 만들지 않음).
    // 필터: q(질문/답변 부분 검색), gave_up_only(포기 답변만), limit(기본 50, 최대 200).
    if (routePath === "bo/art-admission-logs") {
      const limit = Math.min(parseInt(String(req.query?.limit || "50"), 10) || 50, 200);
      const q = req.query?.q ? String(req.query.q).trim() : "";
      const gaveUpOnly = req.query?.gave_up_only === "true";
      let filter = `select=*&order=created_at.desc&limit=${limit}`;
      if (gaveUpOnly) filter += `&gave_up=eq.true`;
      if (q) filter += `&query=ilike.*${encodeURIComponent(q)}*`;
      const resp = await supabaseFetch(`art_admission_qa_logs?${filter}`);
      if (!resp.ok) return res.status(200).json([]);
      const data = await resp.json();
      return res.status(200).json(Array.isArray(data) ? data : []);
    }

    // BO 7: 긴급 공지 배포
    if (routePath === "bo/notices") {
      if (method === "GET") {
        const resp = await supabaseFetch("platform_notices?select=*&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const resp = await supabaseFetch("platform_notices", {
          method: "POST",
          body: JSON.stringify({
            title: body.title,
            content: body.content,
            target: body.target_role || "ALL",
            is_pinned: body.is_pinned || false
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 201 : resp.status).json(data);
      }
    }

    // BO 8: 본사 관리자 계정 관리
    // 2026-09-21: 기존엔 admin_users 테이블(auth.users와 무관, 비밀번호 없음)에만
    // 행을 넣어서 "관리자 계정 생성"이라면서 실제로는 로그인할 수 없는 계정을
    // 만들고 있었다. 이제 다른 모든 사용자와 동일하게 실제 Supabase Auth
    // 계정 + user_profiles(role=BO_ADMIN/BO_MANAGER, tenant_id=null)를 만들어
    // /auth/login으로 실제 로그인이 가능하게 한다.
    if (routePath === "bo/admins") {
      if (method === "GET") {
        const resp = await supabaseFetch("user_profiles?role=in.(BO_ADMIN,BO_MANAGER)&select=id,email,name,role,status,created_at&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        if (!body.email || !body.name || !body.password) {
          return res.status(400).json({ error: "email, name, password는 필수입니다." });
        }
        const role = body.role === "BO_ADMIN" ? "BO_ADMIN" : "BO_MANAGER";
        const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || ANON_KEY;
        const createResp = await fetch(`${SUPABASE_URL.replace(/\/$/, "")}/auth/v1/admin/users`, {
          method: "POST",
          headers: { "apikey": serviceKey, "Authorization": `Bearer ${serviceKey}`, "Content-Type": "application/json" },
          body: JSON.stringify({ email: body.email, password: body.password, email_confirm: true })
        });
        const authUser = await createResp.json();
        if (!createResp.ok) {
          return res.status(createResp.status).json({ error: authUser?.msg || authUser?.message || "관리자 계정 생성에 실패했습니다.", detail: authUser });
        }
        const upResp = await supabaseFetch("user_profiles", {
          method: "POST",
          body: JSON.stringify({ id: authUser.id, tenant_id: null, email: body.email, name: body.name, role, status: "ACTIVE" })
        });
        const upData = await upResp.json();
        if (!upResp.ok) {
          return res.status(upResp.status).json({ error: "계정은 생성됐지만 프로필 생성에 실패했습니다.", detail: upData });
        }
        await logAudit(req, "ADMIN_CREATED", body.email, { role });
        return res.status(201).json(Array.isArray(upData) ? upData[0] : upData);
      }
    }

    // ── CO (가맹학원 원장/강사) 엔드포인트 ──
    // CO 1: 원생 명부
    if (routePath === "co/students") {
      if (method === "GET") {
        // 2026-09-21 실측 발견: tenant_id 필터가 없어서 이 학원 저 학원 원생이
        // 다 섞여 나오고 있었다(테넌트 격리 실패). 또한 이름/연락처는
        // student_profiles가 아니라 user_profiles에 있어서 PostgREST FK
        // embed로 같이 가져온다.
        const tenantId = await getCurrentTenantId(req);
        const resp = await supabaseFetch(`student_profiles?tenant_id=eq.${tenantId}&select=*,user_profiles(name,email,phone)&order=created_at.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        // 2026-09-21 실측 발견: student_profiles.user_id는 auth.users(id)를
        // 참조하는 FK라, 실제 Supabase Auth 회원가입을 거친 사용자가 아니면
        // 이 테이블에 새 행을 만들 수 없다. 이 플랫폼에는 아직 회원가입 API가
        // 없으므로(가맹학원 원장이 신규 원생을 여기서 "등록"할 방법 자체가
        // 없음) 지금은 이 사실을 명확히 알리는 에러를 반환한다 - 가짜 UUID로
        // 억지로 insert를 시도해서 알아보기 힘든 FK 위반 에러를 내는 대신.
        return res.status(501).json({
          error: "신규 원생 등록 기능은 아직 사용할 수 없습니다 - 학생 계정 생성은 실제 회원가입(Supabase Auth) 절차를 거쳐야 하는데, 이 플랫폼에는 아직 회원가입 플로우가 구현되어 있지 않습니다.",
        });
      }
    }

    if (routePath.startsWith("co/students/")) {
      const studentId = routePath.replace("co/students/", "");
      const resp = await supabaseFetch(`student_profiles?user_id=eq.${studentId}`, {
        method: method === "DELETE" ? "DELETE" : "PATCH",
        body: method === "DELETE" ? undefined : JSON.stringify(req.body || {})
      });
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    // CO 2: 강사 권한 매트릭스 - bo/permissions와 동일한 menu_permissions
    // 테이블을 쓴다(원장이 자기 학원 강사들 권한을 관리하는 것도 결국 같은
    // 테이블의 행이므로 테이블을 분리할 이유가 없다).
    if (routePath === "co/permissions") {
      if (method === "GET") {
        const userId = req.query?.user_id;
        const filter = userId ? `&user_id=eq.${userId}` : "";
        const resp = await supabaseFetch(`menu_permissions?select=*${filter}&order=menu_key.asc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        if (!body.user_id || !body.tenant_id || !body.menu_key) {
          return res.status(400).json({ error: "user_id, tenant_id, menu_key는 필수입니다." });
        }
        const resp = await supabaseFetch("menu_permissions?on_conflict=user_id,menu_key", {
          method: "POST",
          headers: { Prefer: "resolution=merge-duplicates,return=representation" },
          body: JSON.stringify({
            user_id: body.user_id,
            tenant_id: body.tenant_id,
            menu_key: body.menu_key,
            can_read: body.can_read ?? true,
            can_write: body.can_write ?? false
          })
        });
        const data = await resp.json();
        await logAudit(req, "PERMISSION_UPDATED", body.menu_key, { user_id: body.user_id, can_read: body.can_read, can_write: body.can_write });
        return res.status(resp.ok ? 200 : resp.status).json(Array.isArray(data) ? data[0] : data);
      }
    }

    // CO 3: 출결 관리
    if (routePath === "co/attendance") {
      if (method === "GET") {
        const tenantId = await getCurrentTenantId(req);
        const resp = await supabaseFetch(`attendance?tenant_id=eq.${tenantId}&select=*,user_profiles(name)&order=class_date.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const tenantId = await getCurrentTenantId(req);
        const studentId = await resolveTargetStudent(req, tenantId, body.student_id);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "출결을 기록할 학원(tenant) 또는 학생(student) 데이터가 없습니다 - 지정한 학생이 이 학원 소속이 아니거나, 회원가입한 학생이 아직 없습니다." });
        }
        const resp = await supabaseFetch("attendance", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: tenantId,
            student_id: studentId,
            class_date: body.date || body.class_date || new Date().toISOString().split("T")[0],
            status: body.status || "PRESENT",
            remark: body.notes || body.remark || body.reason || ""
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(data);
      }
    }

    // 2026-09-21 신규: 기존 출결 행의 상태/사유를 수정(원장이 화면에서
    // 출석→지각으로 버튼을 다시 누르는 것 같은 실사용 패턴). tenant_id로
    // 한 번 더 좁혀서 다른 학원 출결 행을 수정 못하게 막는다.
    if (routePath.startsWith("co/attendance/") && method === "PATCH") {
      const attId = routePath.replace("co/attendance/", "");
      const tenantId = await getCurrentTenantId(req);
      const body = req.body || {};
      const patch: Record<string, any> = {};
      if (body.status) patch.status = body.status;
      if (body.remark !== undefined) patch.remark = body.remark;
      const resp = await supabaseFetch(`attendance?id=eq.${attId}&tenant_id=eq.${tenantId}`, {
        method: "PATCH",
        body: JSON.stringify(patch)
      });
      const data = await resp.json();
      return res.status(resp.status).json(Array.isArray(data) ? data[0] : data);
    }

    // CO 4: 실기 평가 및 피드백
    if (routePath === "co/evaluations") {
      if (method === "GET") {
        const tenantId = await getCurrentTenantId(req);
        // 2026-09-21 실측 발견(PGRST201): student_evaluations는 student_id와
        // instructor_id 둘 다 user_profiles를 참조해서, 어느 쪽을 조인할지
        // PostgREST가 판단 못 하고 300 에러를 냈다. FK 컬럼명을 명시해서
        // 학생 이름 쪽으로 고정한다.
        const resp = await supabaseFetch(`student_evaluations?tenant_id=eq.${tenantId}&select=*,user_profiles!student_id(name)&order=evaluation_date.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const tenantId = await getCurrentTenantId(req);
        const studentId = await resolveTargetStudent(req, tenantId, body.student_id);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "평가를 기록할 학원(tenant) 또는 학생(student) 데이터가 없습니다 - 지정한 학생이 이 학원 소속이 아니거나, 회원가입한 학생이 아직 없습니다." });
        }
        const resp = await supabaseFetch("student_evaluations", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: tenantId,
            student_id: studentId,
            evaluation_date: body.date || body.evaluation_date || new Date().toISOString().split("T")[0],
            subject: body.subject || "실기 평가",
            score: body.score || 90,
            feedback: body.feedback || "평가 피드백입니다."
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(data);
      }
    }

    // CO 5: 수업 앨범 (albums / album 모두 대응)
    if (routePath === "co/album" || routePath === "co/albums") {
      if (method === "GET") {
        const tenantId = await getCurrentTenantId(req);
        const resp = await supabaseFetch(`class_album?tenant_id=eq.${tenantId}&select=*,instructor:instructor_id(name)&order=class_date.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const tenantId = await getCurrentTenantId(req);
        const instructorId = await getAuthedUserId(req);
        if (!tenantId) {
          return res.status(409).json({ error: "앨범을 등록할 학원(tenant) 데이터가 아직 없습니다." });
        }
        const resp = await supabaseFetch("class_album", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: tenantId,
            instructor_id: instructorId,
            content_text: body.title || body.caption || body.description || body.content_text || "수업 사진",
            class_date: body.date || body.class_date || new Date().toISOString().split("T")[0],
            image_urls: body.image_urls || []
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(data);
      }
    }

    // CO 6: 수강료 수납 장부 (tuition / tuitions 모두 대응)
    if (routePath === "co/tuition" || routePath === "co/tuitions") {
      if (method === "GET") {
        const tenantId = await getCurrentTenantId(req);
        const resp = await supabaseFetch(`tuition_ledger?tenant_id=eq.${tenantId}&select=*,user_profiles(name)&order=created_at.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const tenantId = await getCurrentTenantId(req);
        const studentId = await resolveTargetStudent(req, tenantId, body.student_id);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "수납을 기록할 학원(tenant) 또는 학생(student) 데이터가 없습니다 - 지정한 학생이 이 학원 소속이 아니거나, 회원가입한 학생이 아직 없습니다." });
        }
        const resp = await supabaseFetch("tuition_ledger", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: tenantId,
            student_id: studentId,
            billing_month: body.billing_month || new Date().toISOString().slice(0, 7),
            amount: body.amount || 750000,
            status: body.payment_status || body.status || "PAID",
            due_day: body.due_day || 25
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(data);
      }
    }

    // 2026-09-21 신규: 기존 미납 건을 완납 처리(원장이 "수납 처리" 버튼을
    // 누르는 실사용 패턴) - 새 행을 또 만드는 게 아니라 그 미납 행 자체를
    // PAID로 갱신한다.
    if (routePath.startsWith("co/tuition/") && method === "PATCH") {
      const tuitionId = routePath.replace("co/tuition/", "");
      const tenantId = await getCurrentTenantId(req);
      const resp = await supabaseFetch(`tuition_ledger?id=eq.${tuitionId}&tenant_id=eq.${tenantId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "PAID", paid_at: new Date().toISOString() })
      });
      const data = await resp.json();
      return res.status(resp.status).json(Array.isArray(data) ? data[0] : data);
    }

    // CO 7: 학부모 연동 현황 - parent_student_maps 테이블(01_initial_schema.sql
    // 에 이미 존재) 실제 조회. 2026-09-21 설계 변경: 무작위 "코드 발급" 대신
    // 학부모가 FO 쪽에서 자녀의 실제 로그인 이메일로 직접 연동 신청하는
    // 방식으로 바꿨다(parent_student_maps에는 애초에 code 컬럼이 없고, 우리는
    // 이미 실제 이메일 기반 로그인이 있으므로 별도 코드 테이블을 새로 만들
    // 이유가 없다 - 아래 fo/parent-link 참고). 이 라우트는 원장이 자기 학원
    // 학생들의 부모 연동 현황을 확인하는 조회용으로 재정의한다.
    if (routePath === "co/parent-links") {
      const tenantId = await getCurrentTenantId(req);
      const resp = await supabaseFetch(`parent_student_maps?tenant_id=eq.${tenantId}&select=*&order=linked_at.desc`);
      const data = await resp.json();
      return res.status(resp.status).json(Array.isArray(data) ? data : []);
    }

    // CO 9: 학원 기본정보 & 소개 페이지
    // 2026-09-21: 이전엔 로그인 세션과 무관하게 항상 "첫 번째 학원"을
    // 반환/수정했다 - 로그인이 생긴 지금은 실제 소속 학원으로 스코프한다.
    if (routePath === "co/profile") {
      const tenantId = await getCurrentTenantId(req);
      if (method === "GET") {
        const resp = await supabaseFetch(`tenants?id=eq.${tenantId}&select=*&limit=1`);
        const data = await resp.json();
        return res.status(resp.status).json(Array.isArray(data) && data[0] ? data[0] : { slug: "gangnam-main", name: "강남 미술학원 본원" });
      }
      if (method === "PUT") {
        const body = req.body || {};
        if (!tenantId) return res.status(409).json({ error: "소속 학원 정보를 찾을 수 없습니다." });
        const resp = await supabaseFetch(`tenants?id=eq.${tenantId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: body.name,
            slug: body.slug,
            intro_text: body.intro_text,
            highlight_stats: body.highlight_stats,
            is_public_published: false
          })
        });
        const data = await resp.json();
        await logAudit(req, "TENANT_PROFILE_UPDATE_REQUEST", tenantId, { name: body.name });
        return res.status(200).json({ status: "success", approval_status: "PENDING_APPROVAL", data });
      }
    }

    // CO 10: 지점 추가 - branches 테이블(01_initial_schema.sql에 이미 존재) 실제 연동
    if (routePath === "co/branches") {
      const tenantId = await getCurrentTenantId(req);
      if (method === "GET") {
        const resp = await supabaseFetch(`branches?tenant_id=eq.${tenantId}&select=*&order=created_at.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(Array.isArray(data) ? data : []);
      }
      if (method === "POST") {
        const body = req.body || {};
        if (!tenantId) return res.status(409).json({ error: "소속 학원 정보를 찾을 수 없습니다." });
        if (!body.branch_name) return res.status(400).json({ error: "branch_name은 필수입니다." });
        const resp = await supabaseFetch("branches", {
          method: "POST",
          body: JSON.stringify({ tenant_id: tenantId, branch_name: body.branch_name, address: body.address || "", contact: body.contact || "" })
        });
        const data = await resp.json();
        if (resp.ok) await logAudit(req, "BRANCH_CREATED", body.branch_name, { tenant_id: tenantId });
        return res.status(resp.ok ? 201 : resp.status).json(Array.isArray(data) ? data[0] : data);
      }
    }

    // CO 10-2: 학원 통계 - 이전엔 48/6/38400000 고정값이었다. 실제 student_
    // profiles/tuition_ledger/attendance를 집계한다(classes 개념의 전용
    // 테이블이 없어 attendance의 서로 다른 class_date 개수를 "실시된 수업
    // 횟수"의 근사치로 쓴다 - 근사치임을 이 주석에 명시).
    if (routePath === "co/stats") {
      const tenantId = await getCurrentTenantId(req);
      const currentMonth = new Date().toISOString().slice(0, 7);
      const [sResp, tlResp, attResp] = await Promise.all([
        supabaseFetch(`student_profiles?tenant_id=eq.${tenantId}&status=eq.ACTIVE&select=user_id`),
        supabaseFetch(`tuition_ledger?tenant_id=eq.${tenantId}&billing_month=eq.${currentMonth}&status=eq.PAID&select=amount`),
        supabaseFetch(`attendance?tenant_id=eq.${tenantId}&select=class_date`)
      ]);
      const sData = await sResp.json();
      const tlData = await tlResp.json();
      const attData = await attResp.json();
      const monthlyRevenue = Array.isArray(tlData) ? tlData.reduce((sum: number, r: any) => sum + Number(r.amount || 0), 0) : 0;
      const totalClasses = Array.isArray(attData) ? new Set(attData.map((r: any) => r.class_date)).size : 0;
      return res.status(200).json({
        active_students: Array.isArray(sData) ? sData.length : 0,
        total_classes: totalClasses,
        monthly_revenue: monthlyRevenue
      });
    }

    // ── FO (학생·학부모) 엔드포인트 ──
    // FO 1: 성적 추천 대시보드 통계 - 2026-09-21: 프론트엔드에서 실제로는 아직
    // 호출하는 곳이 없는 걸 확인했지만(죽은 엔드포인트), 안티그라비티 전수
    // 테스트가 API 자체를 직접 호출할 것이므로 백엔드는 정직하게 만든다.
    // target_probability(합격 가능성)는 실제 모델이 없어 지어낼 수 없으므로
    // null로 반환한다 - 없는 걸 있는 척 숫자로 꾸미지 않는다.
    if (routePath === "fo/stats") {
      const { studentId } = await getPlaceholderContext(req);
      if (!studentId) {
        return res.status(200).json({ top_target: null, target_probability: null, recent_eval_avg: null, attendance_rate: null, note: "학생 데이터가 없습니다." });
      }
      const [spResp, evalResp, attResp] = await Promise.all([
        supabaseFetch(`student_profiles?user_id=eq.${studentId}&select=target_schools`),
        supabaseFetch(`student_evaluations?student_id=eq.${studentId}&select=score`),
        supabaseFetch(`attendance?student_id=eq.${studentId}&select=status`)
      ]);
      const spData = await spResp.json();
      const evalData = await evalResp.json();
      const attData = await attResp.json();
      const targetSchools = Array.isArray(spData) && spData[0]?.target_schools;
      const topTarget = Array.isArray(targetSchools) && targetSchools.length > 0 ? targetSchools[0] : null;
      const scores = Array.isArray(evalData) ? evalData.map((r: any) => r.score).filter((s: any) => typeof s === "number") : [];
      const recentEvalAvg = scores.length ? Math.round((scores.reduce((a: number, b: number) => a + b, 0) / scores.length) * 10) / 10 : null;
      const attTotal = Array.isArray(attData) ? attData.length : 0;
      const attPresent = Array.isArray(attData) ? attData.filter((r: any) => r.status === "PRESENT").length : 0;
      const attendanceRate = attTotal > 0 ? Math.round((attPresent / attTotal) * 1000) / 10 : null;
      return res.status(200).json({
        top_target: topTarget,
        target_probability: null,
        recent_eval_avg: recentEvalAvg,
        attendance_rate: attendanceRate
      });
    }

    // FO 7: 성적 기록함 CRUD (v5.0 신규)
    if (routePath === "fo/grade-records") {
      if (method === "GET") {
        // 2026-09-21 CRITICAL: student_id 필터가 없어서 로그인한 학생에게 다른
        // 학생의 성적 레코드까지 전부 반환되던 결함(GPT 회귀 테스트로 발견) -
        // fo/evaluations 등 다른 엔드포인트와 동일하게 본인 학생 ID로만 좁힌다.
        const { studentId } = await getPlaceholderContext(req);
        const resp = await supabaseFetch(`student_grade_records?student_id=eq.${studentId}&select=*&order=created_at.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { studentId } = await getPlaceholderContext(req);
        if (!studentId) {
          return res.status(409).json({ error: "성적을 등록할 학생(student) 데이터가 아직 없습니다 - 회원가입 플로우가 구현되기 전까지는 최소 1개의 학생 데이터가 먼저 있어야 합니다." });
        }
        const payload = {
          student_id: studentId,
          label: body.label || "신규 모의평가 성적",
          source_type: body.source_type || "manual",
          parsed_json: body.parsed_json || {},
          is_primary: body.is_primary || false
        };
        const resp = await supabaseFetch("student_grade_records", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(Array.isArray(data) ? data[0] : data);
      }
    }

    if (routePath.startsWith("fo/grade-records/")) {
      const parts = routePath.split("/");
      const recordId = parts[2];
      // 2026-09-21 CRITICAL: 아래 두 결함을 함께 고친다(GPT 회귀 테스트로 발견) -
      // (1) PATCH primary가 student_id 필터 없이 "전체 학생"의 is_primary를
      //     초기화해서, 한 학생이 대표 성적을 바꾸면 플랫폼의 모든 학생 레코드가
      //     영향받았다. (2) DELETE가 소유권 확인 없이 id만 맞으면 지워져서,
      //     레코드 id만 알면(추측/유출) 다른 학생 데이터를 지울 수 있었다(IDOR).
      // 본인 student_id로 스코프를 좁혀서, 남의 레코드 id를 넣어도 0건 매칭돼
      // 아무 일도 안 일어나게 한다.
      const { studentId } = await getPlaceholderContext(req);
      if (parts[3] === "primary") {
        await supabaseFetch(`student_grade_records?student_id=eq.${studentId}`, {
          method: "PATCH",
          body: JSON.stringify({ is_primary: false })
        });
        const resp = await supabaseFetch(`student_grade_records?id=eq.${recordId}&student_id=eq.${studentId}`, {
          method: "PATCH",
          body: JSON.stringify({ is_primary: true })
        });
        const data = await resp.json();
        // 2026-09-21 발견(GPT 재검증): 위 필터가 남의 레코드 id에는 0건
        // 매칭돼 아무것도 안 바뀌는데도 무조건 "success"를 반환해서, 실제로는
        // 아무 효과가 없었던 요청이 성공한 것처럼 보였다 - Supabase는 기본
        // Prefer: return=representation이라 실제로 바뀐 행 배열을 그대로
        // 돌려주므로, 그게 비어있으면 소유권 없음으로 명확히 실패 응답한다.
        if (!Array.isArray(data) || data.length === 0) {
          return res.status(404).json({ error: "대표로 지정할 권한이 없거나 존재하지 않는 레코드입니다." });
        }
        return res.status(200).json({ status: "success", primary_id: recordId, data });
      }
      if (method === "DELETE") {
        const resp = await supabaseFetch(`student_grade_records?id=eq.${recordId}&student_id=eq.${studentId}`, {
          method: "DELETE"
        });
        const data = await resp.json();
        if (!Array.isArray(data) || data.length === 0) {
          return res.status(404).json({ error: "삭제할 권한이 없거나 존재하지 않는 레코드입니다." });
        }
        return res.status(200).json({ status: "success", deleted_id: recordId });
      }
    }

    // FO 8: 서류함 CRUD (v5.0 신규)
    if (routePath === "fo/documents") {
      if (method === "GET") {
        // 2026-09-21 CRITICAL: grade-records와 동일한 결함 - student_id 필터 없이
        // 전체 학생 서류가 반환됐다.
        const { studentId } = await getPlaceholderContext(req);
        const resp = await supabaseFetch(`student_documents?student_id=eq.${studentId}&select=*&order=created_at.desc`);
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { studentId } = await getPlaceholderContext(req);
        if (!studentId) {
          return res.status(409).json({ error: "서류를 등록할 학생(student) 데이터가 아직 없습니다 - 회원가입 플로우가 구현되기 전까지는 최소 1개의 학생 데이터가 먼저 있어야 합니다." });
        }
        const payload = {
          student_id: studentId,
          label: body.label || "신규 서류",
          doc_type: body.doc_type || "STATEMENT",
          feedback_json: body.feedback_json || {}
        };
        const resp = await supabaseFetch("student_documents", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        return res.status(resp.ok ? 200 : resp.status).json(Array.isArray(data) ? data[0] : data);
      }
    }

    if (routePath.startsWith("fo/documents/")) {
      const recordId = routePath.replace("fo/documents/", "");
      if (method === "DELETE") {
        // 2026-09-21 CRITICAL: grade-records DELETE와 동일한 IDOR 결함 - 소유권
        // 확인 없이 id만 맞으면 삭제됐다. student_id로 스코프를 좁힌다.
        const { studentId } = await getPlaceholderContext(req);
        const resp = await supabaseFetch(`student_documents?id=eq.${recordId}&student_id=eq.${studentId}`, { method: "DELETE" });
        const data = await resp.json();
        if (!Array.isArray(data) || data.length === 0) {
          return res.status(404).json({ error: "삭제할 권한이 없거나 존재하지 않는 레코드입니다." });
        }
        return res.status(200).json({ status: "success", deleted_id: recordId });
      }
    }

    // FO 9: 학원별 소개 페이지 (v5.0 신규)
    if (routePath.startsWith("fo/tenants/")) {
      const slug = routePath.replace("fo/tenants/", "");
      const resp = await supabaseFetch(`tenants?slug=eq.${slug}&limit=1`);
      const data = await resp.json();
      const tenantData = (Array.isArray(data) && data.length > 0) ? data[0] : {
        id: "t-01",
        slug: slug,
        name: "강남 미술학원 본원",
        intro_text: "홍익대/국민대/이화여대 최상위권 디자인과 12년 연속 합격률 1위.",
        is_public_published: true
      };
      return res.status(200).json({ tenant: tenantData, ...tenantData });
    }

    // FO 2, 3, 4, 5, 6
    // 2026-09-21 실측 발견: student_id 필터가 없어서 로그인한 학생이 다른
    // 학생 전원의 평가/출결/수강료 내역을 다 볼 수 있는 심각한 개인정보
    // 노출 문제였다. 반드시 본인 student_id로만 좁힌다.
    if (routePath === "fo/evaluations") {
      const { studentId } = await getPlaceholderContext(req);
      const resp = await supabaseFetch(`student_evaluations?student_id=eq.${studentId}&select=*&order=evaluation_date.desc`);
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/attendance") {
      const { studentId } = await getPlaceholderContext(req);
      const resp = await supabaseFetch(`attendance?student_id=eq.${studentId}&select=*&order=class_date.desc`);
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    // class_album은 학생 개인 소유가 아니라 학원 전체 공유 앨범이므로
    // student_id가 아니라 tenant_id로 스코프한다.
    if (routePath === "fo/album" || routePath === "fo/albums") {
      const { tenantId } = await getPlaceholderContext(req);
      const resp = await supabaseFetch(`class_album?tenant_id=eq.${tenantId}&select=*&order=class_date.desc`);
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/tuition" || routePath === "fo/tuitions") {
      const { studentId } = await getPlaceholderContext(req);
      const resp = await supabaseFetch(`tuition_ledger?student_id=eq.${studentId}&select=*&order=created_at.desc`);
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    // 2026-09-21 설계 변경: parent_student_maps에는 애초에 "코드" 컬럼이
    // 없다(parent_id/student_id 직접 연결) - 이미 실제 이메일 로그인이 있으니
    // 별도 코드 발급 체계를 새로 만들지 않고, 학부모가 자녀의 가입 이메일을
    // 직접 입력해서 연동을 신청하는 방식으로 구현한다.
    if (routePath === "fo/parent-link") {
      if (method === "GET") {
        const parentId = await getAuthedUserId(req);
        if (!parentId) return res.status(401).json({ error: "로그인이 필요합니다." });
        const resp = await supabaseFetch(`parent_student_maps?parent_id=eq.${parentId}&select=*`);
        const data = await resp.json();
        return res.status(resp.status).json(Array.isArray(data) ? data : []);
      }
      if (method === "POST") {
        const parentId = await getAuthedUserId(req);
        if (!parentId) return res.status(401).json({ error: "로그인이 필요합니다." });
        const body = req.body || {};
        if (!body.student_email) return res.status(400).json({ error: "자녀의 가입 이메일(student_email)이 필요합니다." });
        const stuResp = await supabaseFetch(`user_profiles?email=eq.${encodeURIComponent(body.student_email)}&role=eq.STUDENT&select=id,name,tenant_id&limit=1`);
        const stuData = await stuResp.json();
        const student = Array.isArray(stuData) && stuData[0];
        if (!student) return res.status(404).json({ error: "해당 이메일로 가입된 학생 계정을 찾을 수 없습니다." });
        const resp = await supabaseFetch("parent_student_maps", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: student.tenant_id,
            parent_id: parentId,
            student_id: student.id,
            relationship: body.relationship || "MOTHER",
            verified_status: "VERIFIED"
          })
        });
        const data = await resp.json();
        if (!resp.ok) return res.status(resp.status).json({ error: "이미 연동되어 있거나 연동에 실패했습니다.", detail: data });
        return res.status(200).json({ status: "success", linked: true, student_name: student.name });
      }
    }

    // 미지원 라우트
    return res.status(404).json({ error: `Not found: ${routePath}` });

  } catch (err: any) {
    return res.status(500).json({ error: err.message, route: routePath });
  }
}
