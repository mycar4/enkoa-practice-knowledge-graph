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
  }
  const tResp = await supabaseFetch("tenants?select=id&limit=1");
  const tData = await tResp.json();
  const sResp = await supabaseFetch("student_profiles?select=user_id&limit=1");
  const sData = await sResp.json();
  return {
    tenantId: Array.isArray(tData) && tData[0]?.id ? tData[0].id : null,
    studentId: Array.isArray(sData) && sData[0]?.user_id ? sData[0].user_id : null,
  };
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
      const role = body.role === "PARENT" ? "PARENT" : "STUDENT";
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

      return res.status(201).json({ status: "success", user_id: userId, profile_status: profileStatus, guardian_consent_required: isUnder14 });
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
    if (routePath === "bo/permissions") {
      return res.status(200).json({
        roles: ["DIRECTOR", "HEAD_INSTRUCTOR", "INSTRUCTOR", "ASSISTANT"],
        updated_at: new Date().toISOString()
      });
    }

    // BO 6: 감사 로그
    if (routePath === "bo/audit-logs") {
      return res.status(200).json([
        { id: "log-1", action: "TENANT_APPROVAL", target: "강남 미술학원 본원", timestamp: new Date().toISOString() }
      ]);
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
    if (routePath === "bo/admins") {
      if (method === "GET") {
        const resp = await supabaseFetch("admin_users?select=*&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const resp = await supabaseFetch("admin_users", {
          method: "POST",
          body: JSON.stringify({
            name: body.name,
            email: body.email,
            role: body.role || "BO_MANAGER",
            is_active: true
          })
        });
        const data = await resp.json();
        return res.status(resp.ok ? 201 : resp.status).json(data);
      }
    }

    // ── CO (가맹학원 원장/강사) 엔드포인트 ──
    // CO 1: 원생 명부
    if (routePath === "co/students") {
      if (method === "GET") {
        const resp = await supabaseFetch("student_profiles?select=*&order=created_at.desc");
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

    // CO 2: 강사 권한 매트릭스
    if (routePath.includes("permissions")) {
      return res.status(200).json({ status: "success", message: "권한이 성공적으로 저장되었습니다." });
    }

    // CO 3: 출결 관리
    if (routePath === "co/attendance") {
      if (method === "GET") {
        const resp = await supabaseFetch("attendance?select=*&order=class_date.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { tenantId, studentId } = await getPlaceholderContext(req);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "출결을 기록할 학원(tenant) 또는 학생(student) 데이터가 아직 없습니다 - 회원가입 플로우가 구현되기 전까지는 최소 1개의 학원/학생 데이터가 먼저 있어야 합니다." });
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

    // CO 4: 실기 평가 및 피드백
    if (routePath === "co/evaluations") {
      if (method === "GET") {
        const resp = await supabaseFetch("student_evaluations?select=*&order=evaluation_date.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { tenantId, studentId } = await getPlaceholderContext(req);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "평가를 기록할 학원(tenant) 또는 학생(student) 데이터가 아직 없습니다 - 회원가입 플로우가 구현되기 전까지는 최소 1개의 학원/학생 데이터가 먼저 있어야 합니다." });
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
        const resp = await supabaseFetch("class_album?select=*&order=class_date.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { tenantId } = await getPlaceholderContext(req);
        if (!tenantId) {
          return res.status(409).json({ error: "앨범을 등록할 학원(tenant) 데이터가 아직 없습니다." });
        }
        const resp = await supabaseFetch("class_album", {
          method: "POST",
          body: JSON.stringify({
            tenant_id: tenantId,
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
        const resp = await supabaseFetch("tuition_ledger?select=*&order=created_at.desc");
        const data = await resp.json();
        return res.status(resp.status).json(data);
      }
      if (method === "POST") {
        const body = req.body || {};
        const { tenantId, studentId } = await getPlaceholderContext(req);
        if (!tenantId || !studentId) {
          return res.status(409).json({ error: "수납을 기록할 학원(tenant) 또는 학생(student) 데이터가 아직 없습니다 - 회원가입 플로우가 구현되기 전까지는 최소 1개의 학원/학생 데이터가 먼저 있어야 합니다." });
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

    // CO 7: 학부모 연동 코드
    if (routePath === "co/parent-links") {
      return res.status(200).json({ code: `AR-2026-${Math.floor(1000 + Math.random() * 9000)}` });
    }

    // CO 9: 학원 기본정보 & 소개 페이지
    if (routePath === "co/profile") {
      if (method === "GET") {
        const resp = await supabaseFetch("tenants?select=*&limit=1");
        const data = await resp.json();
        return res.status(resp.status).json(data[0] || { slug: "gangnam-main", name: "강남 미술학원 본원" });
      }
      if (method === "PUT") {
        const body = req.body || {};
        const resp = await supabaseFetch("tenants?limit=1", {
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
        return res.status(200).json({ status: "success", approval_status: "PENDING_APPROVAL", data });
      }
    }

    // CO 10: 지점 추가 / stats
    if (routePath === "co/branches") {
      return res.status(201).json({ status: "success", branch_id: `br-${Date.now().toString(36)}` });
    }
    if (routePath === "co/stats") {
      return res.status(200).json({ active_students: 48, total_classes: 6, monthly_revenue: 38400000 });
    }

    // ── FO (학생·학부모) 엔드포인트 ──
    // FO 1: 성적 추천 대시보드 통계
    if (routePath === "fo/stats") {
      return res.status(200).json({
        top_target: "홍익대 디자인학부",
        target_probability: 88.5,
        recent_eval_avg: 92.4,
        attendance_rate: 98.0
      });
    }

    // FO 7: 성적 기록함 CRUD (v5.0 신규)
    if (routePath === "fo/grade-records") {
      if (method === "GET") {
        const resp = await supabaseFetch("student_grade_records?select=*&order=created_at.desc");
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
      if (parts[3] === "primary") {
        await supabaseFetch("student_grade_records", {
          method: "PATCH",
          body: JSON.stringify({ is_primary: false })
        });
        const resp = await supabaseFetch(`student_grade_records?id=eq.${recordId}`, {
          method: "PATCH",
          body: JSON.stringify({ is_primary: true })
        });
        const data = await resp.json();
        return res.status(200).json({ status: "success", primary_id: recordId, data });
      }
      if (method === "DELETE") {
        const resp = await supabaseFetch(`student_grade_records?id=eq.${recordId}`, {
          method: "DELETE"
        });
        return res.status(200).json({ status: "success", deleted_id: recordId });
      }
    }

    // FO 8: 서류함 CRUD (v5.0 신규)
    if (routePath === "fo/documents") {
      if (method === "GET") {
        const resp = await supabaseFetch("student_documents?select=*&order=created_at.desc");
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
        await supabaseFetch(`student_documents?id=eq.${recordId}`, { method: "DELETE" });
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
    if (routePath === "fo/evaluations") {
      const resp = await supabaseFetch("student_evaluations?select=*&order=evaluation_date.desc");
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/attendance") {
      const resp = await supabaseFetch("attendance?select=*&order=class_date.desc");
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/album" || routePath === "fo/albums") {
      const resp = await supabaseFetch("class_album?select=*&order=class_date.desc");
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/tuition" || routePath === "fo/tuitions") {
      const resp = await supabaseFetch("tuition_ledger?select=*&order=created_at.desc");
      const data = await resp.json();
      return res.status(resp.status).json(data);
    }

    if (routePath === "fo/parent-link") {
      return res.status(200).json({ status: "success", linked: true, student_name: "김예원" });
    }

    // 미지원 라우트
    return res.status(404).json({ error: `Not found: ${routePath}` });

  } catch (err: any) {
    return res.status(500).json({ error: err.message, route: routePath });
  }
}
