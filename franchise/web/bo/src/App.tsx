import { useState } from 'react';

// ── 데이터 타입 정의 ──
interface Tenant {
  id: string;
  name: string;
  bizNo: string;
  contractMonths: number;
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'CLOSED';
  studentCount: number;
  monthlyRevenue: number;
}

interface BillingRecord {
  id: string;
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

export default function App() {
  const [activeMenu, setActiveMenu] = useState<string>('dashboard');

  // 1. 가맹학원 상태
  const [tenants, setTenants] = useState<Tenant[]>([
    { id: 't-01', name: '강남 미술학원 본원', bizNo: '120-81-98765', contractMonths: 36, status: 'ACTIVE', studentCount: 48, monthlyRevenue: 24000000 },
    { id: 't-02', name: '홍대 디자인캠퍼스', bizNo: '105-82-45612', contractMonths: 24, status: 'ACTIVE', studentCount: 65, monthlyRevenue: 32500000 },
    { id: 't-03', name: '분당 정자 미술학원', bizNo: '214-86-33211', contractMonths: 36, status: 'PENDING', studentCount: 15, monthlyRevenue: 7500000 },
    { id: 't-04', name: '송파 예일 미술학원', bizNo: '211-88-99012', contractMonths: 12, status: 'SUSPENDED', studentCount: 0, monthlyRevenue: 0 }
  ]);

  // 2. 정산/과금 내역
  const [billings, setBillings] = useState<BillingRecord[]>([
    { id: 'b-01', tenantName: '강남 미술학원 본원', billingMonth: '2026-09', expectedAmount: 2400000, manualAdjustment: -240000, adjustmentReason: '9월 신규 오픈 이벤트 프로모션 10% 지원', finalAmount: 2160000, status: 'PAID' },
    { id: 'b-02', tenantName: '홍대 디자인캠퍼스', billingMonth: '2026-09', expectedAmount: 3250000, manualAdjustment: 0, adjustmentReason: '', finalAmount: 3250000, status: 'PENDING' },
    { id: 'b-03', tenantName: '분당 정자 미술학원', billingMonth: '2026-09', expectedAmount: 750000, manualAdjustment: 0, adjustmentReason: '', finalAmount: 750000, status: 'HELD' }
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

  // 수기결제 모달 상태
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedBilling, setSelectedBilling] = useState<BillingRecord | null>(null);
  const [adjAmount, setAdjAmount] = useState<number>(0);
  const [adjReason, setAdjReason] = useState<string>('');

  // 신규 학원 모달 상태
  const [tenantModalOpen, setTenantModalOpen] = useState(false);
  const [newTenantName, setNewTenantName] = useState('');
  const [newBizNo, setNewBizNo] = useState('');
  const [newMonths, setNewMonths] = useState(36);

  // 수기결제 모달 열기
  const openAdjustmentModal = (record: BillingRecord) => {
    setSelectedBilling(record);
    setAdjAmount(record.manualAdjustment);
    setAdjReason(record.adjustmentReason);
    setModalOpen(true);
  };

  // 수기결제 저장 (사유 5자 미만 거부 불변식)
  const saveAdjustment = () => {
    if (!adjReason.trim() || adjReason.trim().length < 5) {
      alert('⚠️ [불변식 위반 방지]\n지시서 v2.0 제3.2절 / v4.0 제1절에 따라 수기결제 조정 사유(adjustment_reason)는 최소 5자 이상 필수 기입해야 합니다.');
      return;
    }
    if (selectedBilling) {
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
      alert(`[정산 조정 완료] ${selectedBilling.tenantName} 수기결제 조정이 안전하게 저장되었습니다.`);
      setModalOpen(false);
    }
  };

  // 학원 온보딩 등록
  const handleCreateTenant = () => {
    if (!newTenantName.trim()) {
      alert('학원명을 입력해 주세요.');
      return;
    }
    const newT: Tenant = {
      id: `t-${Date.now()}`,
      name: newTenantName,
      bizNo: newBizNo || '000-00-00000',
      contractMonths: newMonths,
      status: 'PENDING',
      studentCount: 0,
      monthlyRevenue: 0
    };
    setTenants(prev => [...prev, newT]);
    alert(`[가입 접수 완료] '${newTenantName}'이(가) PENDING(승인대기) 상태로 등록되었습니다.`);
    setTenantModalOpen(false);
    setNewTenantName('');
    setNewBizNo('');
  };

  // 학원 상태 변경
  const handleStatusChange = (id: string, newStatus: Tenant['status']) => {
    setTenants(prev =>
      prev.map(t => (t.id === id ? { ...t, status: newStatus } : t))
    );
    alert(`학원 상태가 [${newStatus}]로 갱신되었습니다.`);
  };

  return (
    <div className="bo-layout">
      {/* ── 상단 글로벌 헤더 ── */}
      <header className="bo-header">
        <div className="header-brand">
          <span className="logo-badge">BO</span>
          <h1>ART:READY <span>엔코아 본사 통합관리자 (`admin.artready.kr`)</span></h1>
        </div>
        <div className="header-meta">
          <span className="badge badge-primary">최고운영자 (BO_ADMIN)</span>
          <span className="text-muted">마스터 통제 모드</span>
        </div>
      </header>

      <div className="bo-body">
        {/* ── 좌측 8개 메뉴 내비게이션 (v4.0 전수 구현) ── */}
        <aside className="bo-sidebar">
          <nav className="menu-list">
            <button className={`menu-btn ${activeMenu === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveMenu('dashboard')}>
              📊 1. 대시보드
            </button>
            <button className={`menu-btn ${activeMenu === 'tenants' ? 'active' : ''}`} onClick={() => setActiveMenu('tenants')}>
              🏫 2. 가맹학원 관리
            </button>
            <button className={`menu-btn ${activeMenu === 'billings' ? 'active' : ''}`} onClick={() => setActiveMenu('billings')}>
              💳 3. 정산/과금 관리
            </button>
            <button className={`menu-btn ${activeMenu === 'policies' ? 'active' : ''}`} onClick={() => setActiveMenu('policies')}>
              📜 4. 정책문서 관리
            </button>
            <button className={`menu-btn ${activeMenu === 'templates' ? 'active' : ''}`} onClick={() => setActiveMenu('templates')}>
              🔐 5. 메뉴 권한 템플릿
            </button>
            <button className={`menu-btn ${activeMenu === 'analytics' ? 'active' : ''}`} onClick={() => setActiveMenu('analytics')}>
              📈 6. 플랫폼 통계
            </button>
            <button className={`menu-btn ${activeMenu === 'notices' ? 'active' : ''}`} onClick={() => setActiveMenu('notices')}>
              📢 7. 공지사항 관리
            </button>
            <button className={`menu-btn ${activeMenu === 'accounts' ? 'active' : ''}`} onClick={() => setActiveMenu('accounts')}>
              👥 8. 계정 관리
            </button>
          </nav>
        </aside>

        {/* ── 우측 메인 뷰 ── */}
        <main className="bo-content">
          {/* 1. 대시보드 */}
          {activeMenu === 'dashboard' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>전국 가맹 플랫폼 총괄 대시보드</h2>
                <span className="text-muted">실시간 전국 지점 지표 요약</span>
              </div>
              <div className="kpi-grid">
                <div className="kpi-card">
                  <span className="kpi-label">전국 가맹학원 수</span>
                  <strong className="kpi-val">{tenants.length}개소</strong>
                  <span className="kpi-desc text-success">운영중 {tenants.filter(t => t.status === 'ACTIVE').length} / 대기 {tenants.filter(t => t.status === 'PENDING').length}</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">이번달 총 정산 수수료</span>
                  <strong className="kpi-val text-primary">₩ 6,160,000</strong>
                  <span className="kpi-desc">수기결제 감면 반영 완료</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">플랫폼 전체 재원생</span>
                  <strong className="kpi-val">128명</strong>
                  <span className="kpi-desc">수시 대비 집중 원생</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">현재 공시 정책 버전</span>
                  <strong className="kpi-val text-warning">v2.0 (활성)</strong>
                  <span className="kpi-desc">개인정보보호법 제22조의2 적용</span>
                </div>
              </div>
            </div>
          )}

          {/* 2. 가맹학원 관리 */}
          {activeMenu === 'tenants' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>전국 가맹 미술학원 온보딩 & 지점 관리</h2>
                <button className="btn btn-primary" onClick={() => setTenantModalOpen(true)}>+ 신규 학원 온보딩 접수</button>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>학원명</th>
                    <th>사업자번호</th>
                    <th>약정기간</th>
                    <th>재원생 수</th>
                    <th>운영 상태</th>
                    <th>상태 변경 액션</th>
                  </tr>
                </thead>
                <tbody>
                  {tenants.map(t => (
                    <tr key={t.id}>
                      <td><strong>{t.name}</strong></td>
                      <td>{t.bizNo}</td>
                      <td>{t.contractMonths}개월</td>
                      <td>{t.studentCount}명</td>
                      <td>
                        <span className={`badge badge-${t.status === 'ACTIVE' ? 'success' : t.status === 'PENDING' ? 'info' : 'warning'}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>
                        <div className="btn-group">
                          {t.status === 'PENDING' && (
                            <button className="btn btn-success btn-xs" onClick={() => handleStatusChange(t.id, 'ACTIVE')}>가맹 승인</button>
                          )}
                          {t.status === 'ACTIVE' && (
                            <button className="btn btn-outline btn-xs" onClick={() => handleStatusChange(t.id, 'SUSPENDED')}>일시 중지</button>
                          )}
                          {t.status === 'SUSPENDED' && (
                            <button className="btn btn-primary btn-xs" onClick={() => handleStatusChange(t.id, 'ACTIVE')}>정상 복구</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 3. 정산/과금 관리 */}
          {activeMenu === 'billings' && (
            <div className="tab-view">
              <div className="view-header">
                <h2>월별 정산 이력 및 수기결제 조정 관리</h2>
                <span className="text-muted">수기결제 조정 시 사유 5자 미만 저장 거부 불변식 적용</span>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>가맹학원명</th>
                    <th>정산월</th>
                    <th>정상 청구액</th>
                    <th>수기 조정액</th>
                    <th>조정 사유</th>
                    <th>최종 정산액</th>
                    <th>결제 상태</th>
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
                <button className="btn btn-primary" onClick={() => alert('신규 정책 개정 버전 등록')}>+ 신규 버전 등록</button>
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
                      <button className="btn btn-outline btn-xs" onClick={() => alert('개정 이력 조회')}>개정 이력 (Audit)</button>
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
                      <td><button className="btn btn-outline btn-xs">프리셋 편집</button></td>
                    </tr>
                    <tr>
                      <td><strong>보조강사 (Assistant)</strong></td>
                      <td>출결 관리, 수업 앨범</td>
                      <td><span className="badge badge-success">일부 허용</span></td>
                      <td><span className="badge badge-warning">출결만 허용</span></td>
                      <td><button className="btn btn-outline btn-xs">프리셋 편집</button></td>
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
                <button className="btn btn-primary" onClick={() => alert('신규 공지 작성 모달')}>+ 신규 공지 작성</button>
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
                <span className="badge badge-primary">최고관리자만 수정 가능</span>
              </div>
              <table className="bo-table">
                <thead>
                  <tr>
                    <th>관리자명</th>
                    <th>소속/이메일</th>
                    <th>부여된 역할</th>
                    <th>상태</th>
                    <th>권한 수정</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>김대표 (슈퍼어드민)</strong></td>
                    <td>admin@artready.kr</td>
                    <td><span className="badge badge-primary">BO_ADMIN (슈퍼관리자)</span></td>
                    <td><span className="badge badge-success">ACTIVE</span></td>
                    <td><span className="text-muted">수정불가</span></td>
                  </tr>
                  <tr>
                    <td><strong>이영업 팀장</strong></td>
                    <td>sales@artready.kr</td>
                    <td><span className="badge badge-info">BO_MANAGER (가맹영업)</span></td>
                    <td><span className="badge badge-success">ACTIVE</span></td>
                    <td><button className="btn btn-outline btn-xs">권한 조정</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* ── 수기결제 조정 모달 (v4.0 제1절 5자 이상 사유 필수 검증) ── */}
      {modalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div className="modal-header">
              <h3>수기결제 조정 (Manual Adjustment)</h3>
              <button className="close-btn" onClick={() => setModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="text-muted">대상 가맹점: <strong>{selectedBilling?.tenantName}</strong></p>
              <div className="form-group">
                <label>정산월:</label>
                <input type="text" className="form-control" value={selectedBilling?.billingMonth} readOnly />
              </div>
              <div className="form-group">
                <label>조정 금액 (+/- ₩):</label>
                <input
                  type="number"
                  className="form-control"
                  value={adjAmount}
                  onChange={(e) => setAdjAmount(Number(e.target.value))}
                  placeholder="예: -240000"
                />
              </div>
              <div className="form-group">
                <label className="required">수기결제 사유 (5자 이상 필수 기입):</label>
                <textarea
                  className="form-control"
                  rows={3}
                  value={adjReason}
                  onChange={(e) => setAdjReason(e.target.value)}
                  placeholder="지시서 v4.0 제1절: 정산 분쟁 방지를 위해 최소 5자 이상의 사유를 필수로 입력해야 저장이 허용됩니다."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setModalOpen(false)}>취소</button>
              <button className="btn btn-success" onClick={saveAdjustment}>조정 확정 (DB 불변식 검증)</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 가맹학원 온보딩 모달 ── */}
      {tenantModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div className="modal-header">
              <h3>신규 가맹 미술학원 온보딩 접수</h3>
              <button className="close-btn" onClick={() => setTenantModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="required">가맹 학원명:</label>
                <input
                  type="text"
                  className="form-control"
                  value={newTenantName}
                  onChange={(e) => setNewTenantName(e.target.value)}
                  placeholder="예: 송파 예일 미술학원"
                />
              </div>
              <div className="form-group">
                <label>사업자등록번호:</label>
                <input
                  type="text"
                  className="form-control"
                  value={newBizNo}
                  onChange={(e) => setNewBizNo(e.target.value)}
                  placeholder="예: 123-45-67890"
                />
              </div>
              <div className="form-group">
                <label>약정 개월 수:</label>
                <select className="form-control" value={newMonths} onChange={(e) => setNewMonths(Number(e.target.value))}>
                  <option value={12}>12개월 (1년)</option>
                  <option value={24}>24개월 (2년)</option>
                  <option value={36}>36개월 (3년 - 기본)</option>
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setTenantModalOpen(false)}>취소</button>
              <button className="btn btn-primary" onClick={handleCreateTenant}>온보딩 등록 (PENDING)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
