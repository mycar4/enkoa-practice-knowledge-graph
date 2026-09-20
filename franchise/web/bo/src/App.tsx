import { useState } from 'react';

// ── 데이터 타입 정의 ──
interface Tenant {
  id: string;
  name: string;
  slug: string;
  bizNo: string;
  contractMonths: number;
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'CLOSED';
  studentCount: number;
  monthlyRevenue: number;
  isPublicPublished: boolean;
  introText: string;
  highlightStats: Array<{ title: string; value: string }>;
}

interface BillingRecord {
  id: string;
  tenantId: string;
  tenantName: string;
  billingMonth: string;
  expectedAmount: number;
  manualAdjustment: number;
  adjustmentReason: string;
  finalAmount: number;
  status: 'PAID' | 'PENDING' | 'HELD';
}

interface PolicyDoc {
  id: string;
  docType: string;
  version: string;
  content: string;
  isActive: boolean;
  updatedAt: string;
}

interface NoticeItem {
  id: string;
  title: string;
  target: string;
  createdAt: string;
  author: string;
}

interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  status: string;
}

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'info' | 'error';
  timestamp: string;
}

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function App() {
  const [activeMenu, setActiveMenu] = useState<string>('dashboard');

  // 토스트 알림 상태
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'success') => {
    const id = Math.random().toString(36).substring(7);
    const now = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    setToasts(prev => [...prev, { id, message, type, timestamp: now }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  };

  // 1. 가맹학원 상태 (v5.0 소개 페이지 게시 승인 상태 추가)
  const [tenants, setTenants] = useState<Tenant[]>([
    {
      id: 't-01',
      name: '강남 미술학원 본원',
      slug: 'gangnam-main',
      bizNo: '120-81-98765',
      contractMonths: 36,
      status: 'ACTIVE',
      studentCount: 48,
      monthlyRevenue: 24000000,
      isPublicPublished: true,
      introText: '20년 전통의 디자인/기초소양 명문. 국민대, 서울대, 과기대 수시/정시 압도적 합격률.',
      highlightStats: [{ title: '2026 수시 합격률', value: '89.4%' }, { title: '국민대/과기대', value: '42명 합격' }]
    },
    {
      id: 't-02',
      name: '홍대 디자인캠퍼스',
      slug: 'hongdae-campus',
      bizNo: '105-82-45612',
      contractMonths: 24,
      status: 'ACTIVE',
      studentCount: 65,
      monthlyRevenue: 32500000,
      isPublicPublished: true,
      introText: '트렌디한 시각·산업디자인 기초디자인 집중 교육관. 첨단 빔프로젝트 실기 시연.',
      highlightStats: [{ title: '홍익대/건국대', value: '56명 합격' }, { title: '재원생 만족도', value: '98.7%' }]
    },
    {
      id: 't-03',
      name: '분당 예원 아트센터',
      slug: 'bundang-yewon',
      bizNo: '214-86-33211',
      contractMonths: 36,
      status: 'PENDING',
      studentCount: 15,
      monthlyRevenue: 7500000,
      isPublicPublished: false,
      introText: '신규 온보딩 심사 중인 분당 거점 학원. 기초소양 및 조형 전문.',
      highlightStats: [{ title: '목표 정원', value: '50명' }]
    },
    {
      id: 't-04',
      name: '송파 예일 미술학원',
      slug: 'songpa-yeil',
      bizNo: '211-88-99012',
      contractMonths: 12,
      status: 'SUSPENDED',
      studentCount: 0,
      monthlyRevenue: 0,
      isPublicPublished: false,
      introText: '운영 중지 상태 가맹점.',
      highlightStats: []
    }
  ]);

  // 2. 정산/과금 내역
  const [billings, setBillings] = useState<BillingRecord[]>([
    { id: 'b-01', tenantId: 't-01', tenantName: '강남 미술학원 본원', billingMonth: '2026-09', expectedAmount: 2400000, manualAdjustment: -240000, adjustmentReason: '9월 신규 오픈 이벤트 프로모션 10% 지원', finalAmount: 2160000, status: 'PAID' },
    { id: 'b-02', tenantId: 't-02', tenantName: '홍대 디자인캠퍼스', billingMonth: '2026-09', expectedAmount: 3250000, manualAdjustment: 0, adjustmentReason: '', finalAmount: 3250000, status: 'PENDING' },
    { id: 'b-03', tenantId: 't-03', tenantName: '분당 예원 아트센터', billingMonth: '2026-09', expectedAmount: 750000, manualAdjustment: 0, adjustmentReason: '', finalAmount: 750000, status: 'HELD' }
  ]);

  // 3. 정책 문서
  const [policies, setPolicies] = useState<PolicyDoc[]>([
    { id: 'p-01', docType: '이용약관 (TERMS)', version: '2.0', content: 'ART:READY 프랜차이즈 B2B 플랫폼 표준 이용약관입니다.', isActive: true, updatedAt: '2026-09-19' },
    { id: 'p-02', docType: '개인정보처리방침 (PRIVACY)', version: '2.0', content: '개인정보보호법 제22조의2(만 14세 미만 동의 의무) 및 실기작품 비공개 스토리지 보관 규정을 포함합니다.', isActive: true, updatedAt: '2026-09-19' }
  ]);

  // 4. 공지사항
  const [notices, setNotices] = useState<NoticeItem[]>([
    { id: 'n-01', title: '2026학년도 수시 입시 모의평가 기간 시스템 안정화 점검 안내', target: '전체 가맹학원', createdAt: '2026-09-18', author: '엔코아 본사' },
    { id: 'n-02', title: '개인정보보호법 개정에 따른 14세 미만 보호자 동의 기능 적용 완료', target: '원장단', createdAt: '2026-09-15', author: '컴플라이언스팀' }
  ]);

  // 5. 관리자 계정 목록
  const [admins, setAdmins] = useState<AdminUser[]>([
    { id: 'admin-01', name: '김본사 총괄이사', email: 'head@artready.kr', role: 'BO_SUPER_ADMIN', department: '경영전략총괄', status: 'ACTIVE' },
    { id: 'admin-02', name: '이운영 과장', email: 'ops@artready.kr', role: 'BO_MANAGER', department: '가맹운영지원팀', status: 'ACTIVE' }
  ]);

  // 수기결제 모달 상태
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedBilling, setSelectedBilling] = useState<BillingRecord | null>(null);
  const [adjAmount, setAdjAmount] = useState<number>(0);
  const [adjReason, setAdjReason] = useState<string>('');

  // 신규 학원 모달 상태
  const [tenantModalOpen, setTenantModalOpen] = useState(false);
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSlug, setNewTenantSlug] = useState('');
  const [newBizNo, setNewBizNo] = useState('');
  const [newMonths, setNewMonths] = useState(36);

  // 공지사항 모달 상태
  const [noticeModalOpen, setNoticeModalOpen] = useState(false);
  const [newNoticeTitle, setNewNoticeTitle] = useState('');
  const [newNoticeContent, setNewNoticeContent] = useState('');
  const [newNoticeTarget, setNewNoticeTarget] = useState('ALL');

  // 관리자 계정 모달
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [newAdminName, setNewAdminName] = useState('');
  const [newAdminEmail, setNewAdminEmail] = useState('');
  const [newAdminRole, setNewAdminRole] = useState('BO_MANAGER');

  // 수기결제 모달 열기
  const openAdjustmentModal = (record: BillingRecord) => {
    setSelectedBilling(record);
    setAdjAmount(record.manualAdjustment);
    setAdjReason(record.adjustmentReason);
    setModalOpen(true);
  };

  // 수기결제 저장 (사유 5자 미만 거부 불변식 + 백엔드 API 연동)
  const saveAdjustment = async () => {
    if (!adjReason.trim() || adjReason.trim().length < 5) {
      showToast('⚠️ [불변식 위반 방지]\n수기결제 조정 사유(adjustment_reason)는 최소 5자 이상 필수 기입해야 합니다.', 'error');
      return;
    }
    if (selectedBilling) {
      try {
        await fetch(`${API_BASE}/bo/tenants/${selectedBilling.tenantId}/billing/manual-adjustment`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            billing_month: selectedBilling.billingMonth,
            manual_adjustment_amount: adjAmount,
            adjustment_reason: adjReason.trim()
          })
        });
      } catch {}
      setBillings(prev =>
        prev.map(b =>
          b.id === selectedBilling.id
            ? {
                ...b,
                manualAdjustment: adjAmount,
                adjustmentReason: adjReason,
                finalAmount: b.expectedAmount + adjAmount
              }
            : b
        )
      );
      showToast(`[정산 조정 완료] ${selectedBilling.tenantName} 수기결제 조정이 안전하게 반영되었습니다.`);
      setModalOpen(false);
    }
  };

  // 학원 온보딩 등록
  const handleCreateTenant = async () => {
    if (!newTenantName.trim()) {
      showToast('학원명을 입력해 주세요.', 'error');
      return;
    }
    const slug = newTenantSlug.trim() || `tenant-${Date.now().toString(36)}`;
    const newT: Tenant = {
      id: `t-${Date.now().toString(36)}`,
      name: newTenantName,
      slug: slug,
      bizNo: newBizNo || '000-00-00000',
      contractMonths: newMonths,
      status: 'PENDING',
      studentCount: 0,
      monthlyRevenue: 0,
      isPublicPublished: false,
      introText: '신규 온보딩 등록 가맹학원입니다.',
      highlightStats: []
    };
    try {
      await fetch(`${API_BASE}/bo/tenants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newT.name,
          slug: newT.slug,
          business_number: newT.bizNo,
          contract_months: newT.contractMonths,
          initial_status: 'PENDING'
        })
      });
    } catch {}
    setTenants(prev => [...prev, newT]);
    showToast(`[가입 접수 완료] '${newTenantName}'이(가) PENDING(승인대기) 상태로 등록되었습니다.`);
    setTenantModalOpen(false);
    setNewTenantName('');
    setNewTenantSlug('');
    setNewBizNo('');
  };

  // 학원 상태 변경
  const handleStatusChange = async (id: string, newStatus: Tenant['status']) => {
    try {
      await fetch(`${API_BASE}/bo/tenants/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
    } catch {}
    setTenants(prev =>
      prev.map(t => (t.id === id ? { ...t, status: newStatus } : t))
    );
    showToast(`학원 상태가 [${newStatus}]로 갱신되었습니다.`);
  };

  // v5.0 학원 소개 페이지 게시 승인/반려
  const handleTogglePublish = async (tenantId: string, currentPublished: boolean) => {
    const nextPublished = !currentPublished;
    try {
      await fetch(`${API_BASE}/bo/tenants/${tenantId}/publish`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          is_public_published: nextPublished,
          review_notes: nextPublished ? '본사 품질 검수 통과 승인' : '콘텐츠 보완 필요로 게시 보류'
        })
      });
    } catch {}
    setTenants(prev =>
      prev.map(t => (t.id === tenantId ? { ...t, isPublicPublished: nextPublished } : t))
    );
    const tenant = tenants.find(t => t.id === tenantId);
    showToast(
      nextPublished
        ? `[소개 승인 완료] '${tenant?.name}' 소개 페이지가 app.artready.kr/t/${tenant?.slug}에 공개되었습니다.`
        : `[소개 공개 보류] '${tenant?.name}' 소개 페이지가 비공개 처리되었습니다.`,
      nextPublished ? 'success' : 'info'
    );
  };

  // 공지사항 등록
  const handleCreateNotice = async () => {
    if (!newNoticeTitle.trim() || !newNoticeContent.trim()) {
      showToast('공지 제목과 내용을 입력해주세요.', 'error');
      return;
    }
    const newN: NoticeItem = {
      id: `n-${Date.now().toString(36)}`,
      title: newNoticeTitle,
      target: newNoticeTarget === 'ALL' ? '전체 가맹학원' : '원장단',
      createdAt: new Date().toISOString().split('T')[0],
      author: '엔코아 본사'
    };
    try {
      await fetch(`${API_BASE}/bo/notices`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newN.title,
          content: newNoticeContent,
          target_role: newNoticeTarget,
          is_pinned: false
        })
      });
    } catch {}
    setNotices(prev => [newN, ...prev]);
    setNoticeModalOpen(false);
    setNewNoticeTitle('');
    setNewNoticeContent('');
    showToast(`'${newN.title}' 공지사항이 전국 가맹점에 발송되었습니다.`);
  };

  // 관리자 계정 생성
  const handleCreateAdmin = async () => {
    if (!newAdminName.trim() || !newAdminEmail.trim()) {
      showToast('관리자 이름과 이메일을 입력해주세요.', 'error');
      return;
    }
    const newA: AdminUser = {
      id: `admin-${Date.now().toString(36)}`,
      name: newAdminName,
      email: newAdminEmail,
      role: newAdminRole,
      department: '가맹운영지원팀',
      status: 'ACTIVE'
    };
    try {
      await fetch(`${API_BASE}/bo/admins`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newA)
      });
    } catch {}
    setAdmins(prev => [...prev, newA]);
    setAdminModalOpen(false);
    setNewAdminName('');
    setNewAdminEmail('');
    showToast(`신규 관리자 [${newA.name}] 계정이 생성되었습니다.`);
  };

  return (
    <div className="bo-layout">
      {/* ── 상단 글로벌 헤더 ── */}
      <header className="bo-header">
        <div className="header-brand">
          <span className="logo-badge">BO</span>
          <h1>ART:READY <span>엔코아 본사 통합관리자 (`admin.artready.kr` v5.0)</span></h1>
        </div>
        <div className="header-meta">
          <span className="badge badge-primary">최고운영자 (BO_ADMIN)</span>
          <span className="text-muted">마스터 통제 모드</span>
        </div>
      </header>

      <div className="bo-body">
        {/* ── 좌측 8개 메뉴 사이드바 ── */}
        <aside className="bo-sidebar">
          <nav className="bo-nav">
            {[
              { key: 'dashboard', label: '📊 플랫폼 통합 관제' },
              { key: 'tenants', label: '🏫 가맹학원 관리 & 심사' },
              { key: 'billings', label: '💳 정산 및 과금 관리' },
              { key: 'policies', label: '📜 정책/약관 버전 관리' },
              { key: 'templates', label: '🔒 메뉴 권한 템플릿' },
              { key: 'analytics', label: '📈 플랫폼 매출/순위 통계' },
              { key: 'notices', label: '📢 가맹점 공지사항 관리' },
              { key: 'accounts', label: '👤 본사 관리자 계정 관리' }
            ].map(m => (
              <button
                key={m.key}
                className={`nav-btn ${activeMenu === m.key ? 'active' : ''}`}
                onClick={() => setActiveMenu(m.key)}
              >
                {m.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* ── 메인 콘텐츠 뷰 (8개 분기 렌더) ── */}
        <main className="bo-content">
          {/* 1. 통합 관제 대시보드 */}
          {activeMenu === 'dashboard' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>플랫폼 실시간 운영 현황</h2>
                <span className="text-muted">전국 가맹학원 통합 텔레메트리 (v5.0)</span>
              </div>
              <div className="kpi-grid">
                <div className="kpi-card">
                  <span className="kpi-label">활성 가맹점 (ACTIVE)</span>
                  <strong className="kpi-val">{tenants.filter(t => t.status === 'ACTIVE').length}개소</strong>
                  <span className="kpi-desc">심사대기 {tenants.filter(t => t.status === 'PENDING').length}건</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">총 등록 수험생</span>
                  <strong className="kpi-val">{tenants.reduce((acc, t) => acc + t.studentCount, 0)}명</strong>
                  <span className="kpi-desc">실기 평가 누적 1,284건</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">당월 플랫폼 청구액</span>
                  <strong className="kpi-val">₩ 48,500,000</strong>
                  <span className="kpi-desc">수기조정 반영 완료</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">시스템 가동률</span>
                  <strong className="kpi-val text-success">99.98%</strong>
                  <span className="kpi-desc">FastAPI 3-Tier 정상 가동</span>
                </div>
              </div>
            </div>
          )}

          {/* 2. 가맹학원 관리 & v5.0 소개 페이지 심사 */}
          {activeMenu === 'tenants' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>가맹학원 계약 및 심사 관리</h2>
                <button className="btn btn-primary" onClick={() => setTenantModalOpen(true)}>+ 신규 학원 온보딩</button>
              </div>

              {/* 기본 계약 테이블 */}
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>학원명 / Slug</th>
                    <th>사업자번호</th>
                    <th>약정개월</th>
                    <th>상태 (Status)</th>
                    <th>원생수</th>
                    <th>소개 공개</th>
                    <th>상태 변경</th>
                  </tr>
                </thead>
                <tbody>
                  {tenants.map(t => (
                    <tr key={t.id}>
                      <td>
                        <strong>{t.name}</strong>
                        <div style={{ fontSize: '11px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>{t.slug}</div>
                      </td>
                      <td>{t.bizNo}</td>
                      <td>{t.contractMonths}개월</td>
                      <td>
                        <span className={`badge badge-${t.status === 'ACTIVE' ? 'success' : t.status === 'PENDING' ? 'warning' : 'danger'}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>{t.studentCount}명</td>
                      <td>
                        {t.isPublicPublished ? (
                          <span className="badge badge-success">공개중</span>
                        ) : (
                          <span className="badge badge-warning">비공개</span>
                        )}
                      </td>
                      <td>
                        <select
                          className="form-select-sm"
                          value={t.status}
                          onChange={(e) => handleStatusChange(t.id, e.target.value as Tenant['status'])}
                        >
                          <option value="ACTIVE">ACTIVE (가맹승인)</option>
                          <option value="PENDING">PENDING (심사대기)</option>
                          <option value="SUSPENDED">SUSPENDED (일시정지)</option>
                          <option value="CLOSED">CLOSED (해지)</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* v5.0 신규: 학원 공식 소개 페이지 심사 및 공개 승인/반려 패널 */}
              <div style={{ marginTop: '28px', background: '#1c2024', border: '1px solid #374151', borderRadius: '10px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '16px', color: '#ffffff' }}>
                      🌐 학원별 공식 소개 페이지 게시 심사 (v5.0 제3.3절)
                    </h3>
                    <span style={{ fontSize: '12px', color: '#9ca3af' }}>
                      각 가맹학원이 CO에서 신청한 소개문, 합격 실적, 고유 URL을 본사 브랜드 가이드라인에 맞춰 검수 및 공개 승인합니다.
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {tenants.map(t => (
                    <div key={t.id} style={{ background: '#262b30', border: '1px solid #3f474f', borderRadius: '8px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '14px' }}>
                      <div style={{ flex: 1, minWidth: '280px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <strong style={{ fontSize: '15px', color: '#ffffff' }}>{t.name}</strong>
                          <code style={{ fontSize: '12px', color: '#f87171', background: '#3b2528', padding: '2px 6px', borderRadius: '4px' }}>
                            app.artready.kr/t/{t.slug}
                          </code>
                          {t.isPublicPublished ? (
                            <span style={{ background: '#15803d', color: '#fff', fontSize: '11px', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
                              ✓ 공개 승인 상태
                            </span>
                          ) : (
                            <span style={{ background: '#b45309', color: '#fff', fontSize: '11px', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
                              ⏳ 심사 대기 / 비공개
                            </span>
                          )}
                        </div>
                        <p style={{ margin: '8px 0 0 0', fontSize: '13px', color: '#d1d5db', lineHeight: 1.5 }}>
                          "{t.introText}"
                        </p>
                        {t.highlightStats.length > 0 && (
                          <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                            {t.highlightStats.map((st, i) => (
                              <span key={i} style={{ fontSize: '11.5px', color: '#9ca3af', background: '#1c2024', padding: '2px 8px', borderRadius: '4px' }}>
                                {st.title}: <strong style={{ color: '#ef4444' }}>{st.value}</strong>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => handleTogglePublish(t.id, t.isPublicPublished)}
                          style={{
                            background: t.isPublicPublished ? '#374151' : '#d92632',
                            color: '#ffffff',
                            border: 'none',
                            padding: '8px 14px',
                            borderRadius: '6px',
                            fontSize: '12.5px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          {t.isPublicPublished ? '공개 보류/반려' : '소개 페이지 공개 승인'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 3. 정산 및 과금 관리 */}
          {activeMenu === 'billings' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>학원별 월별 과금 정산 및 수기결제 조정</h2>
                <span className="badge badge-warning">수기결제 조정 시 사유 5자 이상 필수 기입</span>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>가맹학원명</th>
                    <th>정산월</th>
                    <th>예상 정산액</th>
                    <th>수기조정액</th>
                    <th>조정 사유</th>
                    <th>최종 청구액</th>
                    <th>납부 상태</th>
                    <th>조정</th>
                  </tr>
                </thead>
                <tbody>
                  {billings.map(b => (
                    <tr key={b.id}>
                      <td><strong>{b.tenantName}</strong></td>
                      <td>{b.billingMonth}</td>
                      <td>₩ {b.expectedAmount.toLocaleString()}</td>
                      <td className={b.manualAdjustment < 0 ? 'text-danger' : b.manualAdjustment > 0 ? 'text-success' : ''}>
                        ₩ {b.manualAdjustment.toLocaleString()}
                      </td>
                      <td><small>{b.adjustmentReason || '-'}</small></td>
                      <td><strong>₩ {b.finalAmount.toLocaleString()}</strong></td>
                      <td>
                        <span className={`badge badge-${b.status === 'PAID' ? 'success' : b.status === 'PENDING' ? 'warning' : 'secondary'}`}>
                          {b.status}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-outline btn-xs" onClick={() => openAdjustmentModal(b)}>수기결제 조정</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 4. 정책문서 관리 */}
          {activeMenu === 'policies' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>서비스 약관 및 개인정보 처리방침 버전 관리</h2>
                <button className="btn btn-primary" onClick={() => showToast('신규 정책 개정 버전 등록 모달이 호출되었습니다.')}>+ 신규 버전 등록</button>
              </div>
              <div className="card-stack">
                {policies.map(p => (
                  <div key={p.id} className="bo-card">
                    <div className="card-header-flex">
                      <strong>{p.docType} (v{p.version})</strong>
                      <span className="badge badge-success">공시 활성 (ACTIVE)</span>
                    </div>
                    <p className="card-text">{p.content}</p>
                    <div className="card-footer-flex">
                      <span className="text-muted">최종 갱신일: {p.updatedAt}</span>
                      <button className="btn btn-outline btn-xs" onClick={() => showToast(`[${p.docType}] 개정 이력: v1.0(2024-01-01) -> v2.0(2026-09-19) 법정대리인 동의 신설`, 'info')}>개정 이력 (Audit)</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. 메뉴 권한 템플릿 관리 */}
          {activeMenu === 'templates' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>CO 기본 메뉴 권한 템플릿 관리</h2>
                <p className="text-muted">신규 가맹점 생성 시 강사/부운영자에게 자동 배포되는 권한 프리셋</p>
              </div>
              <div className="bo-card">
                <table className="bo-table">
                  <thead>
                    <tr>
                      <th>역할 구분</th>
                      <th>기본 부여 메뉴</th>
                      <th>읽기 권한</th>
                      <th>쓰기 권한</th>
                      <th>템플릿 수정</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>수석강사 (Senior)</strong></td>
                      <td>원생 명부, 실기 평가, 출결, 수업 앨범</td>
                      <td><span className="badge badge-success">전체 허용</span></td>
                      <td><span className="badge badge-success">수강료 제외 허용</span></td>
                      <td><button className="btn btn-outline btn-xs" onClick={() => showToast('수석강사 프리셋이 활성화되어 있습니다.')}>프리셋 편집</button></td>
                    </tr>
                    <tr>
                      <td><strong>보조강사 (Assistant)</strong></td>
                      <td>출결 관리, 수업 앨범</td>
                      <td><span className="badge badge-success">일부 허용</span></td>
                      <td><span className="badge badge-warning">출결만 허용</span></td>
                      <td><button className="btn btn-outline btn-xs" onClick={() => showToast('보조강사 프리셋이 활성화되어 있습니다.')}>프리셋 편집</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 6. 플랫폼 통계 */}
          {activeMenu === 'analytics' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>전국 가맹 플랫폼 통계 & 매출 순위</h2>
              </div>
              <div className="kpi-grid">
                <div className="kpi-card">
                  <span className="kpi-label">1위 최고 매출 학원</span>
                  <strong className="kpi-val text-primary">홍대 디자인캠퍼스</strong>
                  <span className="kpi-desc">월 3,250만원 (재원생 65명)</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">평균 재원율 유지</span>
                  <strong className="kpi-val text-success">94.8%</strong>
                  <span className="kpi-desc">전월 대비 2.1% 상승</span>
                </div>
              </div>
            </div>
          )}

          {/* 7. 공지사항 관리 */}
          {activeMenu === 'notices' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>가맹점 대상 공지사항 발행 관리</h2>
                <button className="btn btn-primary" onClick={() => setNoticeModalOpen(true)}>+ 신규 공지 작성</button>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>제목</th>
                    <th>발송 대상</th>
                    <th>작성자</th>
                    <th>발행일자</th>
                  </tr>
                </thead>
                <tbody>
                  {notices.map(n => (
                    <tr key={n.id}>
                      <td><strong>{n.title}</strong></td>
                      <td><span className="badge badge-info">{n.target}</span></td>
                      <td>{n.author}</td>
                      <td>{n.createdAt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 8. 계정 관리 */}
          {activeMenu === 'accounts' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>엔코아 본사 관리자 계정 권한 관리</h2>
                <button className="btn btn-primary" onClick={() => setAdminModalOpen(true)}>+ 관리자 초대</button>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>관리자명</th>
                    <th>소속/이메일</th>
                    <th>부여된 역할</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {admins.map(a => (
                    <tr key={a.id}>
                      <td><strong>{a.name}</strong></td>
                      <td>{a.email} ({a.department})</td>
                      <td><span className="badge badge-primary">{a.role}</span></td>
                      <td><span className="badge badge-success">{a.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* ── 수기결제 조정 모달 (사유 5자 검증) ── */}
      {modalOpen && selectedBilling && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>수기결제 조정 입력 (지시서 제3.2절 제약)</h3>
            <p className="text-muted">가맹학원: <strong>{selectedBilling.tenantName}</strong> ({selectedBilling.billingMonth})</p>

            <div className="form-group">
              <label>조정 금액 (원 단위, 차감 시 마이너스)</label>
              <input
                type="number"
                className="form-control"
                value={adjAmount}
                onChange={e => setAdjAmount(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>조정 사유 (최소 5자 이상 필수 기입)</label>
              <textarea
                className="form-control"
                rows={3}
                placeholder="예: 9월 신규 오픈 이벤트 프로모션 10% 지원 (5자 이상 입력)"
                value={adjReason}
                onChange={e => setAdjReason(e.target.value)}
              />
              <small className={adjReason.trim().length >= 5 ? 'text-success' : 'text-danger'}>
                현재 {adjReason.trim().length}자 / 최소 5자 필수
              </small>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setModalOpen(false)}>취소</button>
              <button className="btn btn-primary" onClick={saveAdjustment}>수기결제 안전 저장</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 신규 가맹학원 온보딩 모달 ── */}
      {tenantModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>신규 학원 승인 및 온보딩 등록</h3>
            <div className="form-group">
              <label>학원명 / 가맹 브랜드명</label>
              <input
                type="text"
                className="form-control"
                placeholder="예: 대전 둔산 미술학원"
                value={newTenantName}
                onChange={e => setNewTenantName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>URL 식별자 (Slug)</label>
              <input
                type="text"
                className="form-control"
                placeholder="예: daejeon-dunsan"
                value={newTenantSlug}
                onChange={e => setNewTenantSlug(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>사업자등록번호</label>
              <input
                type="text"
                className="form-control"
                placeholder="000-00-00000"
                value={newBizNo}
                onChange={e => setNewBizNo(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>약정 개월 수</label>
              <select
                className="form-control"
                value={newMonths}
                onChange={e => setNewMonths(Number(e.target.value))}
              >
                <option value={12}>12개월 (1년)</option>
                <option value={24}>24개월 (2년)</option>
                <option value={36}>36개월 (3년 - 표준)</option>
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setTenantModalOpen(false)}>취소</button>
              <button className="btn btn-primary" onClick={handleCreateTenant}>온보딩 등록 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 공지사항 작성 모달 ── */}
      {noticeModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>신규 가맹점 공지사항 발행</h3>
            <div className="form-group">
              <label>공지 제목</label>
              <input
                type="text"
                className="form-control"
                placeholder="공지 제목 입력"
                value={newNoticeTitle}
                onChange={e => setNewNoticeTitle(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>발송 대상</label>
              <select
                className="form-control"
                value={newNoticeTarget}
                onChange={e => setNewNoticeTarget(e.target.value)}
              >
                <option value="ALL">전체 가맹학원</option>
                <option value="TENANT_ADMIN">가맹학원 원장단</option>
                <option value="STUDENT">수험생 및 학부모</option>
              </select>
            </div>
            <div className="form-group">
              <label>공지 본문</label>
              <textarea
                className="form-control"
                rows={4}
                placeholder="공지 내용 상세..."
                value={newNoticeContent}
                onChange={e => setNewNoticeContent(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setNoticeModalOpen(false)}>취소</button>
              <button className="btn btn-primary" onClick={handleCreateNotice}>공지 발행</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 관리자 초대 모달 ── */}
      {adminModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>신규 본사 관리자 초대</h3>
            <div className="form-group">
              <label>관리자 성명</label>
              <input
                type="text"
                className="form-control"
                placeholder="예: 홍길동"
                value={newAdminName}
                onChange={e => setNewAdminName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>본사 이메일</label>
              <input
                type="email"
                className="form-control"
                placeholder="admin@artready.kr"
                value={newAdminEmail}
                onChange={e => setNewAdminEmail(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>부여 역할</label>
              <select
                className="form-control"
                value={newAdminRole}
                onChange={e => setNewAdminRole(e.target.value)}
              >
                <option value="BO_MANAGER">BO_MANAGER (가맹운영 담당)</option>
                <option value="BO_SUPER_ADMIN">BO_SUPER_ADMIN (최고운영자)</option>
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setAdminModalOpen(false)}>취소</button>
              <button className="btn btn-primary" onClick={handleCreateAdmin}>초대 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 토스트 알림 컨테이너 (첨삭펜 테마 마이크로 인터랙션) ── */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999, display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '380px' }}>
        {toasts.map((t: ToastItem) => (
          <div
            key={t.id}
            style={{
              background: '#262b30',
              border: '1px solid #3f474f',
              borderLeft: `4px solid ${t.type === 'error' ? '#ef4444' : t.type === 'info' ? '#3b82f6' : '#d92632'}`,
              borderRadius: '8px',
              padding: '12px 16px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              color: '#ffffff'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: t.type === 'error' ? '#ef4444' : '#f87171', fontFamily: "'IBM Plex Mono', monospace" }}>
                {t.type === 'error' ? '⚠️ BO ERROR' : t.type === 'info' ? 'ℹ️ BO NOTICE' : '✅ BO VERIFIED'}
              </span>
              <span style={{ fontSize: '10px', color: '#9ca3af', fontFamily: "'IBM Plex Mono', monospace" }}>{t.timestamp}</span>
            </div>
            <div style={{ fontSize: '12.5px', lineHeight: 1.4, whiteSpace: 'pre-line' }}>{t.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
