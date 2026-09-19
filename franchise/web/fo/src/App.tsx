import { useState, useEffect } from 'react';

// ── 데이터 타입 정의 ──
interface EvaluationItem {
  id: string;
  type: string;
  title: string;
  date: string;
  instructor: string;
  score: number;
  feedback: string;
  hasPrivateImage: boolean;
  imageEmoji: string;
}

interface AttendanceDay {
  day: number;
  date: string;
  status: 'PRESENT' | 'LATE' | 'ABSENT' | 'NONE';
  reason?: string;
}

interface AlbumPost {
  id: string;
  title: string;
  date: string;
  className: string;
  instructor: string;
  imageEmoji: string;
  caption: string;
}

interface TuitionHistory {
  id: string;
  month: string;
  className: string;
  amount: number;
  status: 'PAID' | 'UNPAID';
  paidAt?: string;
  receiptNo?: string;
}

interface PolicyDoc {
  id?: string;
  doc_type?: string;
  version?: string;
  title?: string;
  content?: string;
  is_active?: boolean;
  created_at?: string;
}

export default function App() {
  // 역할 전환: 학생 vs 학부모
  const [role, setRole] = useState<'STUDENT' | 'PARENT'>('STUDENT');

  // 9개 전체 메뉴 탭
  const [activeMenu, setActiveMenu] = useState<string>('home');

  // 실기 평가 데이터
  const [evaluations] = useState<EvaluationItem[]>([
    {
      id: 'eval-1',
      type: '수시 실전모의평가',
      title: '기초디자인 — 유리 질감과 금속 구의 공간 구성',
      date: '2026-09-18',
      instructor: '이민혁 수석강사',
      score: 92,
      feedback: '주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 주제부와의 원근 대비를 극대화할 필요가 있습니다. 다음 모의고사에서는 구도 시간 단축에 집중합시다.',
      hasPrivateImage: true,
      imageEmoji: '🏺'
    },
    {
      id: 'eval-2',
      type: '주간 정규과제',
      title: '자연물 묘사 — 솔방울과 나뭇가지 채색',
      date: '2026-09-11',
      instructor: '이민혁 수석강사',
      score: 88,
      feedback: '솔방울의 반복적인 비늘 구조를 덩어리감 있게 잘 묶어주었습니다. 하이라이트 묘사를 조금 더 절제하면 자연스러운 무게감이 살아납니다.',
      hasPrivateImage: true,
      imageEmoji: '🌲'
    },
    {
      id: 'eval-3',
      type: '기초소묘 평가',
      title: '석고 소묘 — 아그리파 두상 명암 분석',
      date: '2026-08-28',
      instructor: '장수진 전임강사',
      score: 94,
      feedback: '석고 표면의 은은한 톤 단계와 역광 처리가 매우 섬세합니다. 턱 아래 그림자 경계면만 조금 더 부드럽게 풀어주세요.',
      hasPrivateImage: true,
      imageEmoji: '🗿'
    }
  ]);

  // 출결 데이터 (9월 기준 1~30일)
  const [attendanceDays] = useState<AttendanceDay[]>([
    { day: 1, date: '2026-09-01', status: 'PRESENT' },
    { day: 2, date: '2026-09-02', status: 'PRESENT' },
    { day: 3, date: '2026-09-03', status: 'PRESENT' },
    { day: 4, date: '2026-09-04', status: 'PRESENT' },
    { day: 5, date: '2026-09-05', status: 'NONE' },
    { day: 6, date: '2026-09-06', status: 'NONE' },
    { day: 7, date: '2026-09-07', status: 'PRESENT' },
    { day: 8, date: '2026-09-08', status: 'PRESENT' },
    { day: 9, date: '2026-09-09', status: 'PRESENT' },
    { day: 10, date: '2026-09-10', status: 'LATE', reason: '학교 입시설명회로 15분 지각' },
    { day: 11, date: '2026-09-11', status: 'PRESENT' },
    { day: 12, date: '2026-09-12', status: 'NONE' },
    { day: 13, date: '2026-09-13', status: 'NONE' },
    { day: 14, date: '2026-09-14', status: 'PRESENT' },
    { day: 15, date: '2026-09-15', status: 'PRESENT' },
    { day: 16, date: '2026-09-16', status: 'PRESENT' },
    { day: 17, date: '2026-09-17', status: 'PRESENT' },
    { day: 18, date: '2026-09-18', status: 'PRESENT' },
    { day: 19, date: '2026-09-19', status: 'PRESENT' }
  ]);

  // 수업 앨범
  const [albumPosts] = useState<AlbumPost[]>([
    { id: 'alb-1', title: '고3 입시반 4시간 타임어택 실기 시험 현장', date: '2026-09-18', className: '고3 입시정규A반', instructor: '이민혁 수석강사', imageEmoji: '🎨', caption: '실전 수시 시험장과 동일한 긴장감 속에서 진행된 모의고사 현장입니다.' },
    { id: 'alb-2', title: '자연물과 인공물 질감 표현 실습 수업', date: '2026-09-12', className: '고3 입시정규A반', instructor: '이민혁 수석강사', imageEmoji: '🖌️', caption: '물체 고유의 재질감을 극대화하기 위한 특수 채색 기법 시연' }
  ]);

  // 수강료 납부 내역
  const [tuitionList, setTuitionList] = useState<TuitionHistory[]>([
    { id: 't-9', month: '2026년 9월분', className: '고3 실전입시 정규과정', amount: 850000, status: 'PAID', paidAt: '2026-09-08', receiptNo: 'RCP-202609-0881' },
    { id: 't-8', month: '2026년 8월분', className: '고3 실전입시 정규과정', amount: 850000, status: 'PAID', paidAt: '2026-08-07', receiptNo: 'RCP-202608-0421' },
    { id: 't-7', month: '2026년 7월분 (여름특강 포함)', className: '고3 실전입시 하계집중반', amount: 1250000, status: 'PAID', paidAt: '2026-07-05', receiptNo: 'RCP-202607-0105' }
  ]);

  // 정책 문서 (Supabase 조회)
  const [policies, setPolicies] = useState<PolicyDoc[]>([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);

  // 모달 상태들
  const [signedUrlModal, setSignedUrlModal] = useState<{ open: boolean; title: string; score: number } | null>(null);
  const [withdrawalModal, setWithdrawalModal] = useState(false);
  const [childCodeInput, setChildCodeInput] = useState('');
  const [linkSuccess, setLinkSuccess] = useState(false);

  // 회원가입 폼 상태 (만 14세 미만 동의 플로우)
  const [regRole, setRegRole] = useState<'STUDENT' | 'PARENT'>('STUDENT');
  const [regName, setRegName] = useState('');
  const [regBirth, setRegBirth] = useState('2013-05-12'); // 만 13세 예시
  const [isUnder14, setIsUnder14] = useState(false);
  const [guardianName, setGuardianName] = useState('');
  const [guardianPhone, setGuardianPhone] = useState('');
  const [academyCode, setAcademyCode] = useState('GANGNAM-01');
  const [regStatus, setRegStatus] = useState<string | null>(null);

  // 마이페이지 프로필 수정
  const [myPhone, setMyPhone] = useState('010-3344-5566');
  const [myTarget, setMyTarget] = useState('국민대학교 시각디자인학과');
  const [myTargetB, setMyTargetB] = useState('서울과학기술대학교 디자인학과');
  const [myTargetC, setMyTargetC] = useState('건국대학교 산업디자인학과');

  useEffect(() => {
    if (activeMenu === 'policies') {
      fetchPolicies();
    }
  }, [activeMenu]);

  // 만 14세 미만 자동 판별
  useEffect(() => {
    if (regBirth) {
      const birthYear = new Date(regBirth).getFullYear();
      const currentYear = 2026;
      const age = currentYear - birthYear;
      setIsUnder14(age < 14);
    }
  }, [regBirth]);

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
      } else {
        throw new Error('Fallback to static');
      }
    } catch {
      setPolicies([
        {
          id: 'p-01',
          doc_type: 'TERMS',
          title: 'ART:READY 플랫폼 표준 이용약관 (v2.0)',
          content: '제1조(목적) 본 약관은 ART:READY 가맹 학원 수험생 및 학부모 회원에게 제공하는 모바일/웹 학습 지원 서비스의 권리, 의무를 규정함을 목적으로 합니다.'
        },
        {
          id: 'p-02',
          doc_type: 'PRIVACY',
          title: '개인정보처리방침 및 만 14세 미만 아동 보호 규정 (v2.0)',
          content: '개인정보보호법 제22조의2에 따라 만 14세 미만 아동의 개인정보 수집 시 반드시 법정대리인의 본인확인 및 사전 동의(PENDING_GUARDIAN_CONSENT)를 거칩니다. 실기 작품 및 평가 데이터는 비공개 버킷에서 256비트 암호화 처리됩니다.'
        }
      ]);
    } finally {
      setLoadingPolicies(false);
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText('AR-2026-9812');
    alert('학부모 연동 코드 [AR-2026-9812]가 복사되었습니다.\n학부모님 가입 시 자녀 연동란에 입력해 주세요.');
  };

  const handleLinkChild = (e: React.FormEvent) => {
    e.preventDefault();
    if (!childCodeInput.trim()) {
      alert('자녀 연동 코드를 입력해주세요.');
      return;
    }
    setLinkSuccess(true);
    alert(`[연동 성공]\n자녀 연동 코드 [${childCodeInput}]가 인증되었습니다.\n이제 김예원 원생의 실기 평가, 출결, 수강료 내역을 실시간 조회할 수 있습니다.`);
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!regName.trim()) {
      alert('이름을 입력해주세요.');
      return;
    }
    if (isUnder14) {
      if (!guardianName.trim() || !guardianPhone.trim()) {
        alert('⚠️ 만 14세 미만 아동은 개인정보보호법 제22조의2에 따라 법정대리인(보호자)의 이름과 연락처가 필수입니다.');
        return;
      }
      setRegStatus('PENDING_GUARDIAN_CONSENT');
      alert(`[가입 접수 — 보호자 동의 대기]\n회원 가입 상태가 [PENDING_GUARDIAN_CONSENT]로 등록되었습니다.\n보호자(${guardianName}님, ${guardianPhone}) 휴대폰으로 법정대리인 본인확인 및 동의 URL이 발송되었습니다.`);
    } else {
      setRegStatus('ACTIVE');
      alert(`[가입 완료] ${regName}님 환영합니다! 소속 학원(${academyCode}) 승인이 완료되었습니다.`);
    }
  };

  const handleWithdrawal = () => {
    alert(`[회원 탈퇴 및 비식별화 처리 완료]\n지시서 v2.0 제3.9절 / v4.0 제3절에 따라 본인의 개인 식별 정보(PII)가 즉시 암호화 파기 및 비식별화되었습니다.\n(재정 결제 기록은 전자상거래법에 따라 분리 보관됩니다.)`);
    setWithdrawalModal(false);
  };

  return (
    <div className="app-root" style={{ minHeight: '100vh', background: '#0b1120', color: '#f8fafc', display: 'flex', flexDirection: 'column' }}>
      {/* ── 1. 상단 글로벌 헤더 (반응형) ── */}
      <header style={{ background: '#111827', borderBottom: '1px solid #1f2937', padding: '12px 20px', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ background: 'linear-gradient(135deg, #6366f1, #3b82f6)', color: '#fff', fontWeight: 800, padding: '4px 8px', borderRadius: '6px', fontSize: '13px' }}>FO</span>
            <div>
              <span style={{ fontWeight: 700, fontSize: '17px', letterSpacing: '-0.5px' }}>ART:READY</span>
              <span style={{ fontSize: '12px', color: '#94a3b8', marginLeft: '6px' }}>수험생·학부모 포털</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* 학생 vs 학부모 뷰 토글 */}
            <div style={{ background: '#1f2937', padding: '4px', borderRadius: '8px', display: 'flex', gap: '4px' }}>
              <button
                onClick={() => setRole('STUDENT')}
                style={{
                  padding: '5px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                  background: role === 'STUDENT' ? '#3b82f6' : 'transparent', color: role === 'STUDENT' ? '#fff' : '#94a3b8', fontWeight: role === 'STUDENT' ? 700 : 400
                }}
              >
                🎓 학생 뷰
              </button>
              <button
                onClick={() => setRole('PARENT')}
                style={{
                  padding: '5px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                  background: role === 'PARENT' ? '#10b981' : 'transparent', color: role === 'PARENT' ? '#fff' : '#94a3b8', fontWeight: role === 'PARENT' ? 700 : 400
                }}
              >
                👨‍👩‍👧 학부모 뷰
              </button>
            </div>

            <div style={{ fontSize: '12px', background: 'rgba(255, 255, 255, 0.05)', padding: '5px 10px', borderRadius: '6px', border: '1px solid #374151' }}>
              {role === 'STUDENT' ? '김예원 원생 (강남본원)' : '박현숙 학부모님 (보호자)'}
            </div>
          </div>
        </div>

        {/* ── 9개 메뉴 내비게이션 바 (가로 스크롤 대응) ── */}
        <div style={{ maxWidth: '1200px', margin: '10px auto 0 auto', display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
          {[
            { key: 'home', label: '🏠 홈/대시보드' },
            { key: 'evaluations', label: '🎨 실기 작품 & 피드백' },
            { key: 'attendance', label: '📅 출결 이력' },
            { key: 'album', label: '📸 수업 앨범' },
            { key: 'tuition', label: '💳 수강료 납부내역' },
            { key: 'parent_link', label: '👨‍👩‍👧 학부모 연동' },
            { key: 'policies', label: '📜 정책 및 개인정보 방침' },
            { key: 'mypage', label: '👤 마이페이지' },
            { key: 'auth', label: '🔐 회원가입/14세미만인증' }
          ].map(menu => {
            const isActive = activeMenu === menu.key;
            return (
              <button
                key={menu.key}
                onClick={() => setActiveMenu(menu.key)}
                style={{
                  padding: '7px 14px', borderRadius: '8px', border: 'none', whiteSpace: 'nowrap',
                  background: isActive ? (role === 'STUDENT' ? '#3b82f6' : '#10b981') : 'transparent',
                  color: isActive ? '#ffffff' : '#9ca3af',
                  fontSize: '13px', fontWeight: isActive ? 600 : 400,
                  cursor: 'pointer', transition: 'all 0.15s ease'
                }}
              >
                {menu.label}
              </button>
            );
          })}
        </div>
      </header>

      {/* ── 메인 콘텐츠 영역 ── */}
      <main style={{ maxWidth: '1200px', margin: '0 auto', width: '100%', padding: '24px 16px', flex: 1 }}>

        {/* 1. 홈 / 대시보드 */}
        {activeMenu === 'home' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 프로필 카드 & 목표 대학 배너 */}
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '24px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                  <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#3b82f633', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px' }}>
                    🎨
                  </div>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>김예원 (고3 입시정규반)</h2>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>강남 미술학원 본원 | 목표: 시각/산업디자인</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <span style={{ background: '#10b98122', color: '#10b981', padding: '3px 8px', borderRadius: '4px', fontSize: '12px' }}>학부모 연동 완료 (모: 박현숙)</span>
                  <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '3px 8px', borderRadius: '4px', fontSize: '12px' }}>재원 상태 (ACTIVE)</span>
                </div>
              </div>

              {/* 목표 대학 리스트 */}
              <div style={{ background: '#1f2937', padding: '16px', borderRadius: '8px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#94a3b8', marginBottom: '8px' }}>🎯 목표 대학 지원군 (2027 수시)</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
                  <div><strong style={{ color: '#f59e0b' }}>[가군]</strong> {myTarget}</div>
                  <div><strong style={{ color: '#3b82f6' }}>[나군]</strong> {myTargetB}</div>
                  <div><strong style={{ color: '#10b981' }}>[다군]</strong> {myTargetC}</div>
                </div>
              </div>
            </div>

            {/* 주요 지표 카드 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ background: '#111827', border: '1px solid #1f2937', padding: '18px', borderRadius: '10px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>최근 실기 모의평가</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#3b82f6', margin: '6px 0' }}>92점</div>
                <span style={{ fontSize: '11px', color: '#10b981' }}>기초디자인 상위 5%</span>
              </div>
              <div style={{ background: '#111827', border: '1px solid #1f2937', padding: '18px', borderRadius: '10px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>9월 출석률</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#10b981', margin: '6px 0' }}>94.7%</div>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>18일 출석 / 1회 지각</span>
              </div>
              <div style={{ background: '#111827', border: '1px solid #1f2937', padding: '18px', borderRadius: '10px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>9월 수강료 수납</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#10b981', margin: '6px 0' }}>완납</div>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>850,000원 납부 완료</span>
              </div>
            </div>

            {/* 최근 피드백 요약 배너 */}
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '15px', margin: 0 }}>📢 최근 강사 피드백 알림</h3>
                <button onClick={() => setActiveMenu('evaluations')} style={{ background: 'transparent', border: 'none', color: '#3b82f6', fontSize: '12px', cursor: 'pointer' }}>전체 보기 &gt;</button>
              </div>
              <div style={{ background: '#1f2937', padding: '14px', borderRadius: '8px', fontSize: '13px', lineHeight: 1.6 }}>
                <strong>이민혁 수석강사 (2026-09-18):</strong> "주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 원근 대비를 극대화할 필요가 있습니다..."
              </div>
            </div>
          </div>
        )}

        {/* 2. 실기 작품 & 피드백 */}
        {activeMenu === 'evaluations' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>실기 평가 결과 및 작품 피드백 ({evaluations.length}건)</h2>
              <span style={{ fontSize: '12px', color: '#10b981' }}>🔒 비공개 스토리지 버킷 + 1회용 만료 서명 URL(Signed URL) 보호</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {evaluations.map(item => (
                <div key={item.id} style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', marginRight: '8px' }}>{item.type}</span>
                      <strong style={{ fontSize: '16px' }}>{item.title}</strong>
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>담당: {item.instructor} | 평가일자: {item.date}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ fontSize: '24px', fontWeight: 800, color: '#10b981' }}>{item.score}점</div>
                      {item.hasPrivateImage && (
                        <button
                          onClick={() => setSignedUrlModal({ open: true, title: item.title, score: item.score })}
                          style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                        >
                          🖼️ 실기 작품 원본 열람
                        </button>
                      )}
                    </div>
                  </div>

                  <div style={{ marginTop: '14px', background: '#1f2937', padding: '14px', borderRadius: '8px', fontSize: '13px', lineHeight: 1.6, color: '#e5e7eb' }}>
                    💬 <strong>강사 상세 피드백:</strong> {item.feedback}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 3. 출결 이력 */}
        {activeMenu === 'attendance' && (
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>2026년 9월 출결 이력 캘린더</h2>
              <div style={{ display: 'flex', gap: '10px', fontSize: '12px' }}>
                <span style={{ color: '#10b981' }}>● 출석: 18회</span>
                <span style={{ color: '#f59e0b' }}>● 지각: 1회</span>
                <span style={{ color: '#ef4444' }}>● 결석: 0회</span>
              </div>
            </div>

            {/* 캘린더 그리드 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px', marginBottom: '20px' }}>
              {['일', '월', '화', '수', '목', '금', '토'].map(d => (
                <div key={d} style={{ textAlign: 'center', fontSize: '12px', color: '#94a3b8', padding: '6px 0', fontWeight: 600 }}>{d}</div>
              ))}
              {attendanceDays.map(att => (
                <div
                  key={att.day}
                  style={{
                    background: att.status === 'NONE' ? '#1f293744' : '#1f2937',
                    border: '1px solid',
                    borderColor: att.status === 'LATE' ? '#f59e0b' : att.status === 'PRESENT' ? '#10b98144' : '#374151',
                    borderRadius: '6px',
                    padding: '10px 6px',
                    minHeight: '60px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between'
                  }}
                >
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{att.day}일</span>
                  <div style={{ fontSize: '11px', textAlign: 'center' }}>
                    {att.status === 'PRESENT' && <span style={{ color: '#10b981' }}>출석</span>}
                    {att.status === 'LATE' && <span style={{ color: '#f59e0b', fontWeight: 700 }}>지각</span>}
                    {att.status === 'NONE' && <span style={{ color: '#64748b' }}>휴무</span>}
                  </div>
                </div>
              ))}
            </div>

            {/* 특이사항 사유 목록 */}
            <div style={{ background: '#1f2937', padding: '14px', borderRadius: '8px', fontSize: '13px' }}>
              <div style={{ fontWeight: 600, marginBottom: '6px' }}>📌 지각/결석 사유 기록</div>
              <div style={{ color: '#cbd5e1' }}>• 2026-09-10 (목): <strong>지각</strong> — 사유: "학교 입시설명회로 15분 지각 (보호자 확인 완료)"</div>
            </div>
          </div>
        )}

        {/* 4. 수업 앨범 */}
        {activeMenu === 'album' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>수업 현장 앨범 및 강평</h2>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>소속 반: 고3 입시정규A반</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
              {albumPosts.map(post => (
                <div key={post.id} style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', overflow: 'hidden' }}>
                  <div style={{ height: '160px', background: '#1f2937', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '54px' }}>
                    {post.imageEmoji}
                  </div>
                  <div style={{ padding: '16px' }}>
                    <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>{post.className}</span>
                    <h3 style={{ fontSize: '15px', margin: '8px 0 6px 0' }}>{post.title}</h3>
                    <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>{post.caption}</p>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '10px' }}>작성자: {post.instructor} | 일자: {post.date}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. 수강료 납부내역 */}
        {activeMenu === 'tuition' && (
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>수강료 납부 이력 및 영수증</h2>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>{role === 'PARENT' ? '보호자 결제 모드' : '학생 조회 모드'}</span>
              </div>
              <span style={{ background: '#10b98122', color: '#10b981', padding: '4px 10px', borderRadius: '6px', fontSize: '12px' }}>미납금 없음 (완납)</span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1f2937', color: '#94a3b8' }}>
                  <th style={{ padding: '10px' }}>청구월</th>
                  <th style={{ padding: '10px' }}>수강 과정</th>
                  <th style={{ padding: '10px' }}>금액</th>
                  <th style={{ padding: '10px' }}>납부 상태</th>
                  <th style={{ padding: '10px' }}>납부일 / 영수증</th>
                </tr>
              </thead>
              <tbody>
                {tuitionList.map(t => (
                  <tr key={t.id} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600 }}>{t.month}</td>
                    <td style={{ padding: '12px 10px' }}>{t.className}</td>
                    <td style={{ padding: '12px 10px', fontWeight: 700 }}>{t.amount.toLocaleString()}원</td>
                    <td style={{ padding: '12px 10px' }}>
                      <span style={{ background: '#10b98122', color: '#10b981', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>완납</span>
                    </td>
                    <td style={{ padding: '12px 10px' }}>
                      <button onClick={() => alert(`[전자영수증 발급]\n영수증 번호: ${t.receiptNo}\n학원명: 강남 미술학원 본원\n금액: ${t.amount.toLocaleString()}원\n정상 결제 완료되었습니다.`)} style={{ background: '#1f2937', color: '#fff', border: '1px solid #374151', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                        영수증 보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 6. 학부모 연동 */}
        {activeMenu === 'parent_link' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            {/* 학생용 카드 */}
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 8px 0' }}>🎓 원생 전용: 학부모 연동 코드 발급</h3>
              <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5 }}>
                학부모님께서 가입하실 때 아래 연동 코드를 입력하시면, 자녀의 평가 결과와 출결 현황이 안전하게 실시간 공유됩니다.
              </p>
              <div style={{ background: '#1f2937', padding: '16px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '16px 0' }}>
                <code style={{ fontSize: '18px', fontWeight: 800, color: '#3b82f6', letterSpacing: '1px' }}>AR-2026-9812</code>
                <button onClick={handleCopyCode} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                  코드 복사
                </button>
              </div>
              <div style={{ fontSize: '12px', color: '#10b981' }}>
                ✓ 현재 연동된 보호자: <strong>박현숙 (모)</strong>
              </div>
            </div>

            {/* 학부모용 카드 */}
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 8px 0' }}>👨‍👩‍👧 학부모 전용: 자녀 연동 코드 등록</h3>
              <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5 }}>
                자녀(원생)의 화면에 표시된 11자리 연동 코드(예: AR-2026-XXXX)를 입력하시면 즉시 부모-자녀 RLS 권한이 결속됩니다.
              </p>
              <form onSubmit={handleLinkChild} style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <input
                  type="text"
                  placeholder="예: AR-2026-9812"
                  value={childCodeInput}
                  onChange={e => setChildCodeInput(e.target.value)}
                  style={{ background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '10px', borderRadius: '6px', fontSize: '13px' }}
                />
                <button type="submit" style={{ background: '#10b981', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                  자녀 연동 승인 신청
                </button>
              </form>
              {linkSuccess && (
                <div style={{ marginTop: '12px', background: '#10b98122', color: '#10b981', padding: '10px', borderRadius: '6px', fontSize: '12px' }}>
                  ✓ 김예원 원생과의 연동 승인이 활성화되었습니다.
                </div>
              )}
            </div>
          </div>
        )}

        {/* 7. 정책 및 개인정보 방침 */}
        {activeMenu === 'policies' && (
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>ART:READY 플랫폼 공시 정책 및 약관</h2>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>개인정보보호법 및 가맹 표준 준수</span>
              </div>
              <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '4px 8px', borderRadius: '4px', fontSize: '12px' }}>최신 공시 버전</span>
            </div>

            {loadingPolicies ? (
              <div style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>정책 문서를 불러오는 중...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {policies.map((p, idx) => (
                  <div key={idx} style={{ background: '#1f2937', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <strong style={{ fontSize: '15px' }}>{p.title || p.doc_type}</strong>
                      <span style={{ fontSize: '11px', background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: '4px' }}>유효 공시본</span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.6, margin: 0 }}>
                      {p.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 8. 마이페이지 (탈퇴 즉시 비식별화 처리) */}
        {activeMenu === 'mypage' && (
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0' }}>회원 정보 관리 및 설정</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '500px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>이름</label>
                <input type="text" disabled value="김예원" style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#9ca3af', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>휴대폰 번호</label>
                <input type="text" value={myPhone} onChange={e => setMyPhone(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>목표 대학 [가군]</label>
                <input type="text" value={myTarget} onChange={e => setMyTarget(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>목표 대학 [나군]</label>
                <input type="text" value={myTargetB} onChange={e => setMyTargetB(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>목표 대학 [다군]</label>
                <input type="text" value={myTargetC} onChange={e => setMyTargetC(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button onClick={() => alert('개인정보가 성공적으로 저장되었습니다.')} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                  정보 수정 저장
                </button>
                <button onClick={() => alert('비밀번호 변경 링크가 전송되었습니다.')} style={{ background: '#1f2937', color: '#fff', border: '1px solid #374151', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>
                  비밀번호 변경
                </button>
              </div>
            </div>

            {/* 회원 탈퇴 구역 (비식별화 처리 명시) */}
            <div style={{ borderTop: '1px solid #1f2937', marginTop: '30px', paddingTop: '20px' }}>
              <h3 style={{ fontSize: '14px', color: '#ef4444', margin: '0 0 6px 0' }}>위험 구역: 회원 탈퇴</h3>
              <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                탈퇴 시 지시서 v2.0 제3.9절 및 v4.0 제3절에 따라 회원의 모든 개인식별정보(PII)는 즉시 비식별화(익명화) 처리되며 복구할 수 없습니다.
              </p>
              <button onClick={() => setWithdrawalModal(true)} style={{ background: '#ef444422', border: '1px solid #ef4444', color: '#ef4444', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>
                회원 탈퇴 (즉시 비식별화)
              </button>
            </div>
          </div>
        )}

        {/* 9. 회원가입 및 만 14세 미만 법정대리인 동의 플로우 */}
        {activeMenu === 'auth' && (
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '10px', padding: '24px', maxWidth: '600px', margin: '0 auto' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 8px 0' }}>신규 회원가입 (PIPA 제22조의2 대응)</h2>
            <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '20px', lineHeight: 1.5 }}>
              만 14세 미만 아동의 경우 개인정보보호법에 의거하여 법정대리인 동의가 완료될 때까지 계정이 <code>PENDING_GUARDIAN_CONSENT</code> 상태로 제한됩니다.
            </p>

            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>회원 유형</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <input type="radio" checked={regRole === 'STUDENT'} onChange={() => setRegRole('STUDENT')} /> 학생 회원
                  </label>
                  <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <input type="radio" checked={regRole === 'PARENT'} onChange={() => setRegRole('PARENT')} /> 학부모 회원
                  </label>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>가입자 성명</label>
                <input type="text" placeholder="예: 이태양" value={regName} onChange={e => setRegName(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>생년월일 (만 14세 미만 여부 자동 판별)</label>
                <input type="date" value={regBirth} onChange={e => setRegBirth(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
                {isUnder14 && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#f59e0b', background: '#f59e0b11', padding: '6px 10px', borderRadius: '4px', border: '1px solid #f59e0b33' }}>
                    ⚠️ <strong>만 14세 미만 감지:</strong> 법정대리인(보호자) 동의 절차가 필수 적용됩니다.
                  </div>
                )}
              </div>

              {isUnder14 && (
                <div style={{ background: '#1f2937', padding: '14px', borderRadius: '8px', border: '1px solid #374151', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f59e0b' }}>🛡️ 법정대리인(보호자) 정보 입력</div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '2px' }}>보호자 성명</label>
                    <input type="text" placeholder="예: 이진우" value={guardianName} onChange={e => setGuardianName(e.target.value)} style={{ width: '100%', background: '#0b1120', border: '1px solid #374151', color: '#fff', padding: '6px', borderRadius: '4px' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '2px' }}>보호자 휴대폰 번호 (동의 링크 발송용)</label>
                    <input type="text" placeholder="예: 010-9988-7766" value={guardianPhone} onChange={e => setGuardianPhone(e.target.value)} style={{ width: '100%', background: '#0b1120', border: '1px solid #374151', color: '#fff', padding: '6px', borderRadius: '4px' }} />
                  </div>
                </div>
              )}

              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>소속 학원 가맹 코드</label>
                <input type="text" value={academyCode} onChange={e => setAcademyCode(e.target.value)} style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>

              <button type="submit" style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', fontSize: '14px', fontWeight: 600, cursor: 'pointer', marginTop: '10px' }}>
                가입 신청하기
              </button>
            </form>

            {regStatus && (
              <div style={{ marginTop: '16px', padding: '12px', borderRadius: '6px', background: regStatus === 'PENDING_GUARDIAN_CONSENT' ? '#f59e0b22' : '#10b98122', border: '1px solid', borderColor: regStatus === 'PENDING_GUARDIAN_CONSENT' ? '#f59e0b' : '#10b981', fontSize: '13px' }}>
                <strong>상태: {regStatus}</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#cbd5e1' }}>
                  {regStatus === 'PENDING_GUARDIAN_CONSENT' ? '보호자의 본인인증 완료 전까지 실기작품 및 결제 메뉴가 보호됩니다.' : '정상 회원가입이 완료되었습니다.'}
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── 비공개 실기 작품 서명 URL 모달 ── */}
      {signedUrlModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '24px', maxWidth: '500px', width: '100%', color: '#fff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: '16px' }}>🔒 보안 서명 URL (Signed URL) 열람</h3>
              <span style={{ fontSize: '11px', background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: '4px' }}>유효시간 3600초</span>
            </div>
            <div style={{ height: '220px', background: '#1f2937', borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '50px' }}>🎨</span>
              <strong style={{ fontSize: '15px' }}>{signedUrlModal.title}</strong>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>실기 점수: {signedUrlModal.score}점 (비공개 스토리지)</span>
            </div>
            <p style={{ fontSize: '11px', color: '#94a3b8', marginTop: '10px', lineHeight: 1.5 }}>
              지시서 v2.0 제3.9절 규정에 따라 원본 실기작품 이미지는 비공개 버킷에 저장되며 만료형 서명 URL을 통해서만 허가된 원생 및 학부모 본인에게 안전하게 전달됩니다.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button onClick={() => setSignedUrlModal(null)} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: '6px', cursor: 'pointer' }}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 회원 탈퇴 확인 모달 (비식별화) ── */}
      {withdrawalModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#111827', border: '1px solid #ef4444', borderRadius: '12px', padding: '24px', maxWidth: '440px', width: '100%', color: '#fff' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', color: '#ef4444' }}>⚠️ 정말로 탈퇴하시겠습니까?</h3>
            <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.6 }}>
              탈퇴 시 즉시 귀하의 이름, 연락처 등 모든 개인정보가 <code>ANONYMOUS_USER</code>로 비식별화 처리되며, 모든 연동 권한이 영구 해제됩니다.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setWithdrawalModal(false)} style={{ background: '#1f2937', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleWithdrawal} style={{ background: '#ef4444', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>탈퇴 및 즉시 비식별화</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
