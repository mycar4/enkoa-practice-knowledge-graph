import React, { useState } from 'react';

interface PermissionState {
  menu_key: string;
  label: string;
  description: string;
  can_read: boolean;
  can_write: boolean;
  isLocked?: boolean;
}

export default function App() {
  const [currentTab, setCurrentTab] = useState<'overview' | 'permissions'>('overview');
  const [selectedInstructor, setSelectedInstructor] = useState('ins-01');
  const [permissions, setPermissions] = useState<PermissionState[]>([
    {
      menu_key: 'student.list',
      label: '원생 명부 관리',
      description: '원생 전체 명부 및 상세 프로필 조회/수정',
      can_read: true,
      can_write: false
    },
    {
      menu_key: 'student.evaluation',
      label: '실기 평가 및 피드백',
      description: '원생 실기 평가 및 피드백 작성',
      can_read: true,
      can_write: true
    },
    {
      menu_key: 'attendance.manage',
      label: '출결 관리',
      description: '출결 체크 및 결석 사유 입력',
      can_read: true,
      can_write: true
    },
    {
      menu_key: 'album.manage',
      label: '수업 앨범',
      description: '수업 앨범 사진 및 강평 등록',
      can_read: true,
      can_write: true
    },
    {
      menu_key: 'billing.view',
      label: '수강료 수납 대장',
      description: '학원 수납 현황 조회 (원장 전용 기능)',
      can_read: false,
      can_write: false,
      isLocked: true
    }
  ]);

  const handleToggle = (key: string, field: 'can_read' | 'can_write') => {
    setPermissions(prev =>
      prev.map(p => {
        if (p.menu_key === key && !p.isLocked) {
          return { ...p, [field]: !p[field] };
        }
        return p;
      })
    );
  };

  const handleSavePermissions = () => {
    alert(`[저장 완료]\n강사(${selectedInstructor})의 메뉴 권한 설정이 Supabase menu_permissions 테이블에 즉시 반영되었습니다.\n(지시서 v2.0 제3.3절 2중 RLS 정책 자동 결속)`);
  };

  return (
    <div className="admin-wrapper">
      {/* 좌측 사이드바 */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo-badge">CO</span>
          <h2>ART:READY <span>학원포털 (React)</span></h2>
        </div>
        <div className="academy-badge">
          <strong>강남 미술학원 본원</strong>
          <span className="badge badge-success">운영중 (ACTIVE)</span>
        </div>

        <nav className="sidebar-menu">
          <button
            className={`menu-item ${currentTab === 'overview' ? 'active' : ''}`}
            onClick={() => setCurrentTab('overview')}
          >
            📊 학원 운영 현황
          </button>
          <button
            className={`menu-item ${currentTab === 'permissions' ? 'active' : ''}`}
            onClick={() => setCurrentTab('permissions')}
          >
            🔐 강사 권한 설정 (v2.0)
          </button>
        </nav>

        <div className="sidebar-footer">
          <span className="user-info">홍원장 (TENANT_ADMIN)</span>
        </div>
      </aside>

      {/* 우측 메인 영역 */}
      <main className="main-content">
        <header className="content-header">
          <div className="header-title">
            <h1>{currentTab === 'overview' ? '학원 운영 현황 대시보드' : '강사별 세부 메뉴 권한 설정 (v2.0)'}</h1>
            <span className="text-muted">Supabase RDB 실시간 연동 모드</span>
          </div>
          <div className="header-actions">
            <button className="btn btn-primary" onClick={() => alert('신규 원생 초대 링크: https://app.artready.kr/invite?t=gangnam-01')}>
              + 원생 초대 링크
            </button>
          </div>
        </header>

        {currentTab === 'overview' && (
          <div className="tab-pane">
            <div className="kpi-grid">
              <div className="kpi-card">
                <span className="kpi-title">재원 원생 수</span>
                <strong className="kpi-value">48명</strong>
                <span className="kpi-sub text-success">정원 50명 대비 96%</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-title">이번달 수납률</span>
                <strong className="kpi-value text-primary">91.6%</strong>
                <span className="kpi-sub">44명 완납 / 4명 미납</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-title">출결 평균 (이번주)</span>
                <strong className="kpi-value text-success">98.2%</strong>
                <span className="kpi-sub">결석 2건 (사유 병결)</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-title">소속 강사 수</span>
                <strong className="kpi-value">6명</strong>
                <span className="kpi-sub">수석강사 2명 / 전임 4명</span>
              </div>
            </div>

            <div className="dashboard-grid">
              <div className="panel-card">
                <div className="panel-header">
                  <h3>오늘의 실기 평가 대기</h3>
                  <span className="badge badge-info">2건 대기</span>
                </div>
                <ul className="task-list">
                  <li>
                    <div>
                      <strong>김예원 (고3 정규반)</strong>
                      <p className="text-muted">기초디자인 공간구성 모의실기</p>
                    </div>
                    <span className="badge badge-warning">채점 대기</span>
                  </li>
                  <li>
                    <div>
                      <strong>박준서 (고2 예비반)</strong>
                      <p className="text-muted">소묘 정물 묘사 과제</p>
                    </div>
                    <span className="badge badge-warning">채점 대기</span>
                  </li>
                </ul>
              </div>

              <div className="panel-card">
                <div className="panel-header">
                  <h3>최근 등록된 수업앨범</h3>
                </div>
                <p className="text-muted" style={{ marginBottom: 12 }}>강남본원 실기정규 A반 (2026-09-18)</p>
                <div className="album-mini-preview">
                  <div className="mini-img">📷 사진 3장 업로드됨</div>
                  <small className="text-muted">비공개 버킷 암호화 저장 완료</small>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentTab === 'permissions' && (
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <h2>강사별 세부 메뉴 권한 매트릭스 (MENU_PERMISSIONS)</h2>
                <p className="text-muted">지시서 v2.0 제3.3절 준수: 역할 외에 메뉴별 읽기/쓰기 권한을 개별 제어합니다.</p>
              </div>
              <button className="btn btn-success" onClick={handleSavePermissions}>
                변경사항 저장 (API 반영)
              </button>
            </div>

            <div className="instructor-select-bar">
              <label>권한 설정 대상 강사:</label>
              <select
                className="form-control"
                value={selectedInstructor}
                onChange={(e) => setSelectedInstructor(e.target.value)}
              >
                <option value="ins-01">이민혁 수석강사 (정규입시 A반 담임)</option>
                <option value="ins-02">최서연 전임강사 (기초조형 B반)</option>
                <option value="ins-03">정다운 보조강사 (예비반 실기보조)</option>
              </select>
            </div>

            <table className="data-table">
              <thead>
                <tr>
                  <th>메뉴 식별자 (Menu Key)</th>
                  <th>설명</th>
                  <th style={{ textAlign: 'center' }}>읽기 권한 (can_read)</th>
                  <th style={{ textAlign: 'center' }}>쓰기 권한 (can_write)</th>
                </tr>
              </thead>
              <tbody>
                {permissions.map((p) => (
                  <tr key={p.menu_key}>
                    <td><code>{p.menu_key}</code></td>
                    <td>{p.description}</td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={p.can_read}
                        disabled={p.isLocked}
                        onChange={() => handleToggle(p.menu_key, 'can_read')}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={p.can_write}
                        disabled={p.isLocked}
                        onChange={() => handleToggle(p.menu_key, 'can_write')}
                      />
                      {p.isLocked && <small className="text-muted" style={{ marginLeft: 6 }}>(원장 전용)</small>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
