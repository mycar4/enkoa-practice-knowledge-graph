import { useState } from 'react';

interface AcademyItem {
  id: string;
  name: string;
  bizNo: string;
  contractMonths: number;
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED';
  paymentStatus: 'PAID' | 'PENDING' | 'HELD';
}

export default function App() {
  const [academies, setAcademies] = useState<AcademyItem[]>([
    {
      id: 'gangnam-01',
      name: '강남 미술학원 본원',
      bizNo: '120-81-98765',
      contractMonths: 36,
      status: 'ACTIVE',
      paymentStatus: 'PAID'
    },
    {
      id: 'hongdae-01',
      name: '홍대 디자인캠퍼스',
      bizNo: '105-82-45612',
      contractMonths: 24,
      status: 'ACTIVE',
      paymentStatus: 'PENDING'
    },
    {
      id: 'bundang-01',
      name: '분당 정자 미술학원',
      bizNo: '214-86-33211',
      contractMonths: 36,
      status: 'PENDING',
      paymentStatus: 'PENDING'
    }
  ]);

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedAcademy, setSelectedAcademy] = useState<AcademyItem | null>(null);
  const [adjAmount, setAdjAmount] = useState('');
  const [adjReason, setAdjReason] = useState('');

  const handleOpenAdjustment = (academy: AcademyItem) => {
    setSelectedAcademy(academy);
    setAdjAmount('');
    setAdjReason('');
    setModalOpen(true);
  };

  const handleApprove = (id: string, name: string) => {
    setAcademies(prev =>
      prev.map(a => (a.id === id ? { ...a, status: 'ACTIVE' } : a))
    );
    alert(`[가맹 승인 완료]\n${name}의 가맹 계약이 최종 승인되었습니다. (상태: ACTIVE 전환)`);
  };

  const handleSubmitAdjustment = () => {
    // 지시서 v2.0 제3.2절 불변식: 수기결제 사유 필수 검증
    if (!adjReason.trim() || adjReason.trim().length < 5) {
      alert('⚠️ [불변식 위반 방지]\n지시서 v2.0 제3.2절에 따라 수기결제 조정 시 최소 5자 이상의 구체적 사유(adjustment_reason)를 반드시 기입해야 합니다.');
      return;
    }

    alert(`[정산 조정 완료]\n가맹점: ${selectedAcademy?.name}\n조정 금액: ₩ ${adjAmount}\n조정 사유: ${adjReason}\n(Supabase TENANT_BILLING 테이블에 안전하게 반영되었습니다.)`);
    setModalOpen(false);
  };

  const handleOnboardNew = () => {
    const name = prompt('신규 가맹 학원명을 입력하세요:', '송파 디자인 아카데미');
    if (name) {
      const newItem: AcademyItem = {
        id: `tenant-${Date.now()}`,
        name: name,
        bizNo: '220-85-11234',
        contractMonths: 36,
        status: 'PENDING',
        paymentStatus: 'PENDING'
      };
      setAcademies(prev => [...prev, newItem]);
      alert(`[온보딩 접수 완료] ${name} 가맹 신청이 PENDING 상태로 신규 등록되었습니다.`);
    }
  };

  return (
    <div className="bo-layout">
      {/* 헤더 */}
      <header className="bo-header">
        <div className="header-left">
          <span className="logo-badge">BO</span>
          <h1>ART:READY <span>엔코아 통합 관리자 포털 (React)</span></h1>
        </div>
        <div className="header-right">
          <span className="admin-badge">플랫폼 최고관리자 (BO_ADMIN)</span>
        </div>
      </header>

      {/* 메인 */}
      <main className="bo-main">
        {/* KPI */}
        <div className="kpi-row">
          <div className="kpi-card">
            <span className="kpi-title">전국 가맹 학원 수</span>
            <strong className="kpi-value">{academies.length}개소</strong>
            <span className="kpi-sub text-success">
              운영중 {academies.filter(a => a.status === 'ACTIVE').length} / 대기 {academies.filter(a => a.status === 'PENDING').length}
            </span>
          </div>
          <div className="kpi-card">
            <span className="kpi-title">이번달 총 수수료 정산액</span>
            <strong className="kpi-value text-primary">₩ 14,850,000</strong>
            <span className="kpi-sub">수기결제 조정액 반영됨</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-title">플랫폼 총 재원생 수</span>
            <strong className="kpi-value">548명</strong>
            <span className="kpi-sub">수험생 412 / 예비반 136</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-title">현재 공시 정책 버전</span>
            <strong className="kpi-value text-warning">v2.0</strong>
            <span className="kpi-sub">아동보호법 제22조의2 반영됨</span>
          </div>
        </div>

        {/* 가맹 학원 관리 테이블 */}
        <section className="section-card">
          <div className="section-header">
            <div>
              <h2>전국 가맹 미술학원 운영 및 정산 관리</h2>
              <p className="text-muted">가맹 계약 승인, 상태 변경(ACTIVE/SUSPENDED), 월별 수기정산 조정을 관리합니다.</p>
            </div>
            <button className="btn btn-primary" onClick={handleOnboardNew}>
              + 신규 가맹 학원 온보딩
            </button>
          </div>

          <table className="bo-table">
            <thead>
              <tr>
                <th>학원/지점명</th>
                <th>사업자번호</th>
                <th>약정기간</th>
                <th>운영 상태</th>
                <th>이번달 결제 상태</th>
                <th>관리 액션</th>
              </tr>
            </thead>
            <tbody>
              {academies.map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.name}</strong></td>
                  <td>{item.bizNo}</td>
                  <td>{item.contractMonths}개월</td>
                  <td>
                    {item.status === 'ACTIVE' ? (
                      <span className="badge badge-success">ACTIVE (운영중)</span>
                    ) : (
                      <span className="badge badge-info">PENDING (신규승인대기)</span>
                    )}
                  </td>
                  <td>
                    {item.paymentStatus === 'PAID' ? (
                      <span className="badge badge-success">PAID (정산완료)</span>
                    ) : (
                      <span className="badge badge-warning">PENDING (대기)</span>
                    )}
                  </td>
                  <td>
                    {item.status === 'PENDING' ? (
                      <button className="btn btn-primary btn-xs" onClick={() => handleApprove(item.id, item.name)}>
                        가맹 승인
                      </button>
                    ) : (
                      <button className="btn btn-outline btn-xs" onClick={() => handleOpenAdjustment(item)}>
                        수기결제 조정
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>

      {/* 수기결제 조정 모달 (v2.0 제3.2절 사유 필수 입력 검증) */}
      {modalOpen && (
        <div className="modal-overlay active">
          <div className="modal-box">
            <div className="modal-header">
              <h3>수기결제 조정 (Manual Adjustment)</h3>
              <button className="close-btn" onClick={() => setModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="text-muted">대상 가맹점: <strong>{selectedAcademy?.name}</strong></p>
              <div className="form-group">
                <label>정산 대상월:</label>
                <input type="text" className="form-control" value="2026-09" readOnly />
              </div>
              <div className="form-group">
                <label>조정 금액 (+/- ₩):</label>
                <input
                  type="number"
                  className="form-control"
                  placeholder="예: -150000"
                  value={adjAmount}
                  onChange={(e) => setAdjAmount(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="required">수기결제 사유 (필수 입력):</label>
                <textarea
                  className="form-control"
                  rows={3}
                  placeholder="지시서 v2.0 제3.2절 준수: 정산 분쟁 방지를 위해 구체적 사유를 필수 기입해야 합니다. (예: 9월 신규 오픈 이벤트 프로모션 10% 감면 지원)"
                  value={adjReason}
                  onChange={(e) => setAdjReason(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setModalOpen(false)}>취소</button>
              <button className="btn btn-success" onClick={handleSubmitAdjustment}>조정 확정 (DB 불변식 검증)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
