import { useState, useEffect } from 'react';

interface EvaluationItem {
  id: string;
  type: string;
  title: string;
  date: string;
  instructor: string;
  score: number;
  feedback: string;
  hasPrivateImage: boolean;
}

export default function App() {
  const [role, setRole] = useState<'STUDENT' | 'PARENT'>('STUDENT');
  const [currentTab, setCurrentTab] = useState<'evaluations' | 'attendance' | 'album' | 'policies'>('evaluations');
  const [policies, setPolicies] = useState<any[]>([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);

  const evaluations: EvaluationItem[] = [
    {
      id: 'eval-1',
      type: '실전모의평가',
      title: '기초디자인 — 유리 질감과 금속 구의 공간 구성',
      date: '2026-09-18',
      instructor: '이민혁 수석강사',
      score: 92,
      feedback: '주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 주제부와의 원근 대비를 극대화할 필요가 있습니다. 다음 모의고사에서는 구도 시간 단축에 집중합시다.',
      hasPrivateImage: true
    },
    {
      id: 'eval-2',
      type: '주간실기과제',
      title: '자연물 묘사 — 솔방울과 나뭇가지 채색',
      date: '2026-09-11',
      instructor: '이민혁 수석강사',
      score: 88,
      feedback: '솔방울의 반복적인 비늘 구조를 덩어리감 있게 잘 묶어주었습니다. 하이라이트 묘사를 조금 더 절제하면 자연스러운 무게감이 살아납니다.',
      hasPrivateImage: false
    }
  ];

  useEffect(() => {
    if (currentTab === 'policies') {
      fetchPolicies();
    }
  }, [currentTab]);

  const fetchPolicies = async () => {
    setLoadingPolicies(true);
    try {
      const supabaseUrl = "https://jqdtqawrkdidcdfzxzwb.supabase.co";
      const anonKey = "sb_publishable_m3si3M17RpGHrIXt8Au9tQ_w3CwtCpW";
      const res = await fetch(`${supabaseUrl}/rest/v1/policy_documents?is_active=eq.true&select=*`, {
        headers: {
          apikey: anonKey,
          Authorization: `Bearer ${anonKey}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setPolicies(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPolicies(false);
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText('AR-2026-9812');
    alert('학부모 연동 코드 [AR-2026-9812]가 복사되었습니다.\n학부모님 가입 시 자녀 연동란에 입력해 주세요.');
  };

  const handleSignedUrl = (title: string) => {
    alert(`[보안 서명 URL 발급]\n'${title}' 작품 이미지를 위한 1시간 만료 보안 Signed URL이 안전하게 생성되었습니다.\n(지시서 v2.0 제3.9절 비공개 버킷 정책 적용)`);
  };

  return (
    <div className="app-root">
      {/* 헤더 */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand">
            <span className="logo-badge">FO</span>
            <h1>ART:READY <span>수험생·학부모 포털 (React)</span></h1>
          </div>
          <div className="user-control">
            <div className="role-selector">
              <button
                className={`role-btn ${role === 'STUDENT' ? 'active' : ''}`}
                onClick={() => setRole('STUDENT')}
              >
                학생 뷰
              </button>
              <button
                className={`role-btn ${role === 'PARENT' ? 'active' : ''}`}
                onClick={() => setRole('PARENT')}
              >
                학부모 뷰
              </button>
            </div>
            <div className="user-badge">
              {role === 'STUDENT' ? '김예원 원생 (강남본원)' : '박현숙 학부모님 (보호자 모드)'}
            </div>
          </div>
        </div>
      </header>

      {/* 대시보드 레이아웃 (PC 2열 와이드 / 모바일 1열 반응형) */}
      <main className="dashboard-container">
        {/* 좌측 사이드바 */}
        <aside className="profile-card">
          <div className="avatar-box">
            <div className="avatar">🎨</div>
            <h3>김예원 (고3 수험생)</h3>
            <p className="target-major">목표: <strong>디자인학부 (기초디자인)</strong></p>
            <span className="badge badge-success">학부모 연동 완료 (모)</span>
          </div>

          <div className="metric-grid">
            <div className="metric-item">
              <span className="label">최근 실기 점수</span>
              <strong className="value text-primary">92점</strong>
            </div>
            <div className="metric-item">
              <span className="label">이번달 출석률</span>
              <strong className="value text-success">100%</strong>
            </div>
          </div>

          <div className="target-schools-box">
            <h4>🎯 목표 대학 지원군</h4>
            <ul className="school-list">
              <li><span className="rank">가군</span> <strong>국민대학교</strong> 시각디자인</li>
              <li><span className="rank">나군</span> <strong>서울과학기술대</strong> 디자인</li>
              <li><span className="rank">다군</span> <strong>건국대학교</strong> 산업디자인</li>
            </ul>
          </div>

          {role === 'STUDENT' && (
            <div className="guardian-link-box">
              <h4>👨‍👩‍👧 학부모 연동 코드</h4>
              <div className="code-display">
                <code>AR-2026-9812</code>
                <button className="btn btn-sm" onClick={handleCopyCode}>복사</button>
              </div>
              <small className="text-muted">학부모님 가입 시 이 코드를 입력하면 자녀 리포트가 즉시 연동됩니다.</small>
            </div>
          )}
        </aside>

        {/* 우측 메인 콘텐츠 */}
        <section className="content-area">
          <nav className="content-tabs">
            <button
              className={`tab-btn ${currentTab === 'evaluations' ? 'active' : ''}`}
              onClick={() => setCurrentTab('evaluations')}
            >
              실기 작품 & 피드백
            </button>
            <button
              className={`tab-btn ${currentTab === 'attendance' ? 'active' : ''}`}
              onClick={() => setCurrentTab('attendance')}
            >
              출결 이력
            </button>
            <button
              className={`tab-btn ${currentTab === 'album' ? 'active' : ''}`}
              onClick={() => setCurrentTab('album')}
            >
              수업 앨범
            </button>
            <button
              className={`tab-btn ${currentTab === 'policies' ? 'active' : ''}`}
              onClick={() => setCurrentTab('policies')}
            >
              약관 및 정책 (v2.0)
            </button>
          </nav>

          {/* 1. 실기 평가 */}
          {currentTab === 'evaluations' && (
            <div className="tab-pane">
              <div className="pane-header">
                <h2>실기 정밀 평가 & 강사 총평</h2>
                <span className="badge badge-info">총 {evaluations.length}건 기록</span>
              </div>

              {evaluations.map((item) => (
                <div key={item.id} className="evaluation-card">
                  <div className="eval-header">
                    <div className="subject-info">
                      <span className="badge badge-primary">{item.type}</span>
                      <h3>{item.title}</h3>
                      <span className="date">{item.date} | 담당: {item.instructor}</span>
                    </div>
                    <div className="score-badge">
                      <span className="score-num">{item.score}</span>
                      <span className="score-max">/ 100</span>
                    </div>
                  </div>
                  <div className="eval-body">
                    <div className="feedback-box">
                      <strong>👨‍🏫 강사 피드백</strong>
                      <p>{item.feedback}</p>
                    </div>
                    {item.hasPrivateImage && (
                      <div className="image-preview-box">
                        <div className="img-card private-img">
                          <div className="img-placeholder">
                            <span>🔒 비공개 실기 작품 원본 (Private Bucket)</span>
                            <button className="btn btn-outline btn-sm" onClick={() => handleSignedUrl(item.title)}>
                              보안 서명 URL로 열람 (만료형)
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 2. 출결 이력 */}
          {currentTab === 'attendance' && (
            <div className="tab-pane">
              <div className="pane-header">
                <h2>월간 출결 현황</h2>
                <span className="text-muted">2026년 9월</span>
              </div>
              <div className="table-card">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>일자</th>
                      <th>수업 구분</th>
                      <th>출결 상태</th>
                      <th>비고</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>2026-09-18 (금)</td>
                      <td>정규 입시 실기반</td>
                      <td><span className="badge badge-success">출석 (PRESENT)</span></td>
                      <td>정상 출석 (18:00 입실)</td>
                    </tr>
                    <tr>
                      <td>2026-09-16 (수)</td>
                      <td>정규 입시 실기반</td>
                      <td><span className="badge badge-success">출석 (PRESENT)</span></td>
                      <td>정상 출석</td>
                    </tr>
                    <tr>
                      <td>2026-09-13 (일)</td>
                      <td>주말 모의실기 집중반</td>
                      <td><span className="badge badge-success">출석 (PRESENT)</span></td>
                      <td>실전 모의평가 응시</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 3. 수업 앨범 */}
          {currentTab === 'album' && (
            <div className="tab-pane">
              <div className="pane-header">
                <h2>우리 반 수업 앨범</h2>
                <span className="text-muted">강남본원 실기정규 A반</span>
              </div>
              <div className="album-card">
                <div className="album-img-placeholder">
                  <span>📷 2026-09-18 실기 우수작 강평 시간 사진 (비공개 버킷)</span>
                </div>
                <div className="album-caption">
                  <strong>주제부 명도 대비 집중 시범</strong>
                  <p>빛 방향에 따른 양감 잡기와 잔터치 정리 시범 수업 진행 사진입니다.</p>
                  <span className="date">2026-09-18</span>
                </div>
              </div>
            </div>
          )}

          {/* 4. 약관 및 정책 */}
          {currentTab === 'policies' && (
            <div className="tab-pane">
              <div className="pane-header">
                <h2>서비스 정책 및 개인정보 처리방침</h2>
                <span className="badge badge-info">v2.0 공시</span>
              </div>
              <div className="policy-box">
                {loadingPolicies ? (
                  <p className="text-muted">Supabase 정책 문서를 조회 중입니다...</p>
                ) : policies.length > 0 ? (
                  policies.map((p) => (
                    <div key={p.id} className="feedback-box" style={{ marginBottom: 12 }}>
                      <strong>{p.doc_type} (v{p.version})</strong>
                      <p>{p.content}</p>
                    </div>
                  ))
                ) : (
                  <div className="feedback-box">
                    <strong>📌 공시 완료된 기본 정책 (v2.0)</strong>
                    <p>본 플랫폼은 개인정보보호법 제22조의2(만 14세 미만 법정대리인 동의) 및 학생 실기 작품 암호화 저장 규정을 준수합니다.</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <p>© 2026 ART:READY B2B Franchise Platform. All rights reserved. | Built with React & Vite</p>
      </footer>
    </div>
  );
}
