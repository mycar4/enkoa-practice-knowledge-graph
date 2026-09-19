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
  const [tuitionList] = useState<TuitionHistory[]>([
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
  const [regBirth, setRegBirth] = useState('2013-05-12');
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
        throw new Error('Fallback');
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
          content: '개인정보보호법 제22조의2에 따라 만 14세 미만 아동의 개인정보 수집 시 반드시 법정대리인의 본인확인 및 사전 동의(PENDING_GUARDIAN_CONSENT)를 거칩니다. 실기 작품 및 첨삭 데이터는 비공개 버킷에서 256비트 암호화 처리됩니다.'
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
      alert(`[가입 접수 — 보호자 동의 대기]\n회원 가입 상태가 [PENDING_GUARDIAN_CONSENT]로 등록되었습니다.\n보호자(${guardianName}님, ${guardianPhone}) 휴대폰으로 법정대리인 동의 URL이 발송되었습니다.`);
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
    <div className="app-root" style={{ minHeight: '100vh', background: '#fbf9f5', color: '#1c2024', display: 'flex', flexDirection: 'column' }}>
      {/* ── 상단 모바일/웹 헤더 (첨삭펜 테마) ── */}
      <header style={{ background: '#ffffff', borderBottom: '1px solid #e5dec9', padding: '12px 20px', position: 'sticky', top: 0, zIndex: 100, boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
        <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ background: '#d92632', color: '#ffffff', fontWeight: 800, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', boxShadow: '0 2px 6px rgba(217,38,50,0.3)' }}>FO</span>
            <div>
              <span style={{ fontWeight: 700, fontSize: '17px', letterSpacing: '-0.3px', color: '#1c2024' }}>ART:READY</span>
              <span style={{ fontSize: '12px', color: '#646d78', marginLeft: '6px' }}>수험생·학부모 포털</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* 학생 vs 학부모 뷰 토글 */}
            <div style={{ background: '#f3eee4', padding: '3px', borderRadius: '8px', display: 'flex', gap: '3px' }}>
              <button
                onClick={() => setRole('STUDENT')}
                style={{
                  padding: '5px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                  background: role === 'STUDENT' ? '#ffffff' : 'transparent',
                  color: role === 'STUDENT' ? '#d92632' : '#646d78',
                  fontWeight: role === 'STUDENT' ? 700 : 500,
                  boxShadow: role === 'STUDENT' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                🎓 학생 뷰
              </button>
              <button
                onClick={() => setRole('PARENT')}
                style={{
                  padding: '5px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                  background: role === 'PARENT' ? '#ffffff' : 'transparent',
                  color: role === 'PARENT' ? '#d92632' : '#646d78',
                  fontWeight: role === 'PARENT' ? 700 : 500,
                  boxShadow: role === 'PARENT' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                👨‍👩‍👧 학부모 뷰
              </button>
            </div>

            <div style={{ fontSize: '12px', background: '#fbf9f5', border: '1px solid #e5dec9', padding: '5px 10px', borderRadius: '6px', color: '#4b5563' }}>
              {role === 'STUDENT' ? '김예원 원생' : '박현숙 학부모님'}
            </div>
          </div>
        </div>

        {/* ── 9개 메뉴 알약형 탭 내비게이션 (모바일 스크롤 지원) ── */}
        <div style={{ maxWidth: '960px', margin: '10px auto 0 auto', display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
          {[
            { key: 'home', label: '🏠 홈/성적표' },
            { key: 'evaluations', label: '🎨 실기 작품 & 첨삭' },
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
                  padding: '7px 14px', borderRadius: '20px', border: '1px solid',
                  borderColor: isActive ? '#d92632' : '#e5dec9',
                  whiteSpace: 'nowrap',
                  background: isActive ? '#d92632' : '#ffffff',
                  color: isActive ? '#ffffff' : '#646d78',
                  fontSize: '12.5px', fontWeight: isActive ? 700 : 500,
                  boxShadow: isActive ? '0 2px 6px rgba(217,38,50,0.25)' : 'none',
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
      <main style={{ maxWidth: '960px', margin: '0 auto', width: '100%', padding: '24px 16px', flex: 1 }}>

        {/* 1. 홈 / 성적표 카드 중심 (Hero Score Card) */}
        {activeMenu === 'home' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* 🌟 핵심 강조: "첨삭펜 성적표 카드" (92점 큰 숫자 모노스페이스) */}
            <div style={{ background: '#ffffff', border: '2px solid #d92632', borderRadius: '12px', padding: '28px 24px', boxShadow: '0 4px 14px rgba(217,38,50,0.08)', position: 'relative' }}>
              {/* 빨간 첨삭 도장 스탬프 */}
              <div style={{ position: 'absolute', top: '20px', right: '24px', border: '2px solid #d92632', color: '#d92632', padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 800, transform: 'rotate(-3deg)', letterSpacing: '1px', fontFamily: "'IBM Plex Mono', monospace", background: '#fff8f8' }}>
                첨삭완료 VERIFIED
              </div>

              <span style={{ fontSize: '13px', color: '#646d78', fontWeight: 600 }}>2026학년도 수시 1차 실전모의평가 결과</span>
              <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '4px 0 0 0', color: '#1c2024' }}>
                기초디자인 — 유리 질감과 금속 구의 공간 구성
              </h2>

              {/* 큼직한 92점 모노스페이스 숫자 강조 */}
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '14px 0 6px 0' }}>
                <span style={{ fontSize: '56px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1 }}>
                  92
                </span>
                <span style={{ fontSize: '22px', fontWeight: 700, color: '#d92632' }}>점</span>
                <span style={{ fontSize: '13px', background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '3px 8px', borderRadius: '4px', fontWeight: 700, marginLeft: '8px' }}>
                  A+ 등급 (상위 5%)
                </span>
              </div>

              {/* 첨삭 코멘트 박스 (빨간펜 잉크 감성) */}
              <div style={{ background: '#fff8f8', borderLeft: '3px solid #d92632', padding: '14px 16px', borderRadius: '0 6px 6px 0', fontSize: '13.5px', lineHeight: 1.6, color: '#374151', marginTop: '14px' }}>
                ✍️ <strong>이민혁 수석강사 첨삭 총평:</strong><br />
                "주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 주제부와의 원근 대비를 극대화할 필요가 있습니다. 다음 모의고사에서는 구도 시간 단축에 집중합시다."
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '14px', borderTop: '1px dashed #e5dec9', fontSize: '12px', color: '#8a939e' }}>
                <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>평가일: 2026-09-18 | 비공개 버킷 암호화 보관</span>
                <button
                  onClick={() => setActiveMenu('evaluations')}
                  style={{ background: '#d92632', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                >
                  작품 첨삭본 열람 &gt;
                </button>
              </div>
            </div>

            {/* 수험생 프로필 & 목표 대학 지원군 (채점표 모노스페이스) */}
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '18px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                  <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(217,38,50,0.1)', color: '#d92632', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '22px' }}>
                    🎨
                  </div>
                  <div>
                    <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: '#1c2024' }}>김예원 (고3 입시정규반)</h3>
                    <span style={{ fontSize: '12px', color: '#646d78' }}>강남 미술학원 본원 | 목표: 디자인학부</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                  <span style={{ background: '#15803d15', color: '#15803d', padding: '3px 8px', borderRadius: '4px', fontSize: '11.5px', fontWeight: 600 }}>학부모 연동 완료 (모: 박현숙)</span>
                  <span style={{ background: '#2563eb15', color: '#2563eb', padding: '3px 8px', borderRadius: '4px', fontSize: '11.5px', fontWeight: 600 }}>재원생 (ACTIVE)</span>
                </div>
              </div>

              {/* 목표 대학 채점표 리스트 */}
              <div style={{ background: '#fbf9f5', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e5dec9' }}>
                <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#1c2024', marginBottom: '8px' }}>🎯 2027 수시 목표 대학 지원군</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
                  <div><strong style={{ color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>[가군]</strong> {myTarget}</div>
                  <div><strong style={{ color: '#2563eb', fontFamily: "'IBM Plex Mono', monospace" }}>[나군]</strong> {myTargetB}</div>
                  <div><strong style={{ color: '#15803d', fontFamily: "'IBM Plex Mono', monospace" }}>[다군]</strong> {myTargetC}</div>
                </div>
              </div>
            </div>

            {/* 주요 지표 3단 카드 (모노스페이스 수치) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
              <div style={{ background: '#ffffff', border: '1px solid #e5dec9', padding: '16px', borderRadius: '8px' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>9월 출석률</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#15803d', margin: '4px 0', fontFamily: "'IBM Plex Mono', monospace" }}>94.7%</div>
                <span style={{ fontSize: '11px', color: '#8a939e' }}>18일 출석 / 1회 지각</span>
              </div>
              <div style={{ background: '#ffffff', border: '1px solid #e5dec9', padding: '16px', borderRadius: '8px' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>9월 수강료</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#1c2024', margin: '4px 0', fontFamily: "'IBM Plex Mono', monospace" }}>완납</div>
                <span style={{ fontSize: '11px', color: '#15803d', fontWeight: 600 }}>850,000원 납부 완료</span>
              </div>
              <div style={{ background: '#ffffff', border: '1px solid #e5dec9', padding: '16px', borderRadius: '8px' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>누적 실기 평가</span>
                <div style={{ fontSize: '26px', fontWeight: 800, color: '#d92632', margin: '4px 0', fontFamily: "'IBM Plex Mono', monospace" }}>3건</div>
                <span style={{ fontSize: '11px', color: '#8a939e' }}>평균 91.3점</span>
              </div>
            </div>
          </div>
        )}

        {/* 2. 실기 작품 & 첨삭 피드백 */}
        {activeMenu === 'evaluations' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>실기 평가 결과 및 첨삭본 ({evaluations.length}건)</h2>
              <span style={{ fontSize: '12px', color: '#d92632', fontWeight: 600 }}>🔒 비공개 스토리지 + Signed URL 보호</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {evaluations.map(item => (
                <div key={item.id} style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <span style={{ background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', marginRight: '8px', fontWeight: 600 }}>{item.type}</span>
                      <strong style={{ fontSize: '16px', color: '#1c2024' }}>{item.title}</strong>
                      <div style={{ fontSize: '12px', color: '#646d78', marginTop: '4px' }}>담당: {item.instructor} | 일자: <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{item.date}</span></div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ fontSize: '26px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>{item.score}점</div>
                      {item.hasPrivateImage && (
                        <button
                          onClick={() => setSignedUrlModal({ open: true, title: item.title, score: item.score })}
                          style={{ background: '#d92632', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                        >
                          🖼️ 첨삭 원본 열람
                        </button>
                      )}
                    </div>
                  </div>

                  <div style={{ marginTop: '14px', background: '#fff8f8', borderLeft: '3px solid #d92632', padding: '14px', borderRadius: '0 6px 6px 0', fontSize: '13px', lineHeight: 1.6, color: '#374151' }}>
                    ✍️ <strong>강사 첨삭 피드백:</strong> {item.feedback}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 3. 출결 이력 */}
        {activeMenu === 'attendance' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>2026년 9월 출결 이력 캘린더</h2>
              <div style={{ display: 'flex', gap: '10px', fontSize: '12px', fontFamily: "'IBM Plex Mono', monospace" }}>
                <span style={{ color: '#15803d' }}>● 출석: 18회</span>
                <span style={{ color: '#b45309' }}>● 지각: 1회</span>
                <span style={{ color: '#d92632' }}>● 결석: 0회</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px', marginBottom: '20px' }}>
              {['일', '월', '화', '수', '목', '금', '토'].map(d => (
                <div key={d} style={{ textAlign: 'center', fontSize: '12px', color: '#646d78', padding: '6px 0', fontWeight: 600 }}>{d}</div>
              ))}
              {attendanceDays.map(att => (
                <div
                  key={att.day}
                  style={{
                    background: att.status === 'NONE' ? '#fbf9f5' : '#ffffff',
                    border: '1px solid',
                    borderColor: att.status === 'LATE' ? '#b45309' : att.status === 'PRESENT' ? '#15803d44' : '#e5dec9',
                    borderRadius: '6px',
                    padding: '8px 4px',
                    minHeight: '56px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between'
                  }}
                >
                  <span style={{ fontSize: '12px', fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>{att.day}</span>
                  <div style={{ fontSize: '11px', textAlign: 'center', fontWeight: 600 }}>
                    {att.status === 'PRESENT' && <span style={{ color: '#15803d' }}>출석</span>}
                    {att.status === 'LATE' && <span style={{ color: '#b45309' }}>지각</span>}
                    {att.status === 'NONE' && <span style={{ color: '#8a939e' }}>-</span>}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ background: '#fbf9f5', padding: '14px', borderRadius: '8px', fontSize: '13px', border: '1px solid #e5dec9' }}>
              <div style={{ fontWeight: 600, marginBottom: '4px', color: '#1c2024' }}>📌 지각/결석 사유 기록</div>
              <div style={{ color: '#4b5563' }}>• 2026-09-10 (목): <strong>지각</strong> — 사유: "학교 입시설명회로 15분 지각 (보호자 확인 완료)"</div>
            </div>
          </div>
        )}

        {/* 4. 수업 앨범 */}
        {activeMenu === 'album' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>수업 현장 앨범 및 강평</h2>
              <span style={{ fontSize: '12px', color: '#646d78' }}>소속 반: 고3 입시정규A반</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
              {albumPosts.map(post => (
                <div key={post.id} style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
                  <div style={{ height: '160px', background: '#ede8dc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '54px' }}>
                    {post.imageEmoji}
                  </div>
                  <div style={{ padding: '16px' }}>
                    <span style={{ background: 'rgba(37,99,235,0.1)', color: '#2563eb', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>{post.className}</span>
                    <h3 style={{ fontSize: '15px', margin: '8px 0 6px 0', color: '#1c2024' }}>{post.title}</h3>
                    <p style={{ fontSize: '13px', color: '#646d78', lineHeight: 1.5, margin: 0 }}>{post.caption}</p>
                    <div style={{ fontSize: '11px', color: '#8a939e', marginTop: '10px', fontFamily: "'IBM Plex Mono', monospace" }}>작성자: {post.instructor} | {post.date}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. 수강료 납부내역 */}
        {activeMenu === 'tuition' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>수강료 납부 이력 및 영수증</h2>
                <span style={{ fontSize: '12px', color: '#646d78' }}>{role === 'PARENT' ? '보호자 결제 모드' : '학생 조회 모드'}</span>
              </div>
              <span style={{ background: '#15803d15', color: '#15803d', padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600 }}>미납금 없음 (완납)</span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e5dec9', color: '#646d78', background: '#f8f5ee' }}>
                  <th style={{ padding: '10px' }}>청구월</th>
                  <th style={{ padding: '10px' }}>수강 과정</th>
                  <th style={{ padding: '10px' }}>금액</th>
                  <th style={{ padding: '10px' }}>납부 상태</th>
                  <th style={{ padding: '10px' }}>납부일 / 영수증</th>
                </tr>
              </thead>
              <tbody>
                {tuitionList.map(t => (
                  <tr key={t.id} style={{ borderBottom: '1px solid #e5dec9' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{t.month}</td>
                    <td style={{ padding: '12px 10px', color: '#646d78' }}>{t.className}</td>
                    <td style={{ padding: '12px 10px', fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{t.amount.toLocaleString()}원</td>
                    <td style={{ padding: '12px 10px' }}>
                      <span style={{ background: '#15803d15', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>완납</span>
                    </td>
                    <td style={{ padding: '12px 10px' }}>
                      <button onClick={() => alert(`[전자영수증 발급]\n영수증 번호: ${t.receiptNo}\n학원명: 강남 미술학원 본원\n금액: ${t.amount.toLocaleString()}원\n정상 결제 완료되었습니다.`)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 8px 0', color: '#1c2024' }}>🎓 원생 전용: 학부모 연동 코드 발급</h3>
              <p style={{ fontSize: '12px', color: '#646d78', lineHeight: 1.5 }}>
                학부모님 가입 시 아래 연동 코드를 입력하시면 자녀의 실기 평가와 첨삭 피드백이 실시간 공유됩니다.
              </p>
              <div style={{ background: '#fbf9f5', padding: '16px', borderRadius: '8px', border: '1px solid #e5dec9', display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '16px 0' }}>
                <code style={{ fontSize: '18px', fontWeight: 800, color: '#d92632', letterSpacing: '1px', fontFamily: "'IBM Plex Mono', monospace" }}>AR-2026-9812</code>
                <button onClick={handleCopyCode} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                  코드 복사
                </button>
              </div>
              <div style={{ fontSize: '12px', color: '#15803d', fontWeight: 600 }}>
                ✓ 현재 연동된 보호자: <strong>박현숙 (모)</strong>
              </div>
            </div>

            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 8px 0', color: '#1c2024' }}>👨‍👩‍👧 학부모 전용: 자녀 연동 코드 등록</h3>
              <p style={{ fontSize: '12px', color: '#646d78', lineHeight: 1.5 }}>
                자녀(원생) 화면의 11자리 연동 코드(예: AR-2026-XXXX)를 입력하시면 즉시 RLS 권한이 결속됩니다.
              </p>
              <form onSubmit={handleLinkChild} style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <input
                  type="text"
                  placeholder="예: AR-2026-9812"
                  value={childCodeInput}
                  onChange={e => setChildCodeInput(e.target.value)}
                  style={{ background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '10px', borderRadius: '6px', fontSize: '13px' }}
                />
                <button type="submit" style={{ background: '#15803d', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                  자녀 연동 승인 신청
                </button>
              </form>
              {linkSuccess && (
                <div style={{ marginTop: '12px', background: '#15803d15', color: '#15803d', padding: '10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600 }}>
                  ✓ 김예원 원생과의 연동 승인이 활성화되었습니다.
                </div>
              )}
            </div>
          </div>
        )}

        {/* 7. 정책 및 개인정보 방침 */}
        {activeMenu === 'policies' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>ART:READY 플랫폼 공시 정책 및 약관</h2>
                <span style={{ fontSize: '12px', color: '#646d78' }}>개인정보보호법 및 가맹 표준 준수</span>
              </div>
              <span style={{ background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>최신 공시 버전</span>
            </div>

            {loadingPolicies ? (
              <div style={{ textAlign: 'center', padding: '30px', color: '#646d78' }}>정책 문서를 불러오는 중...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {policies.map((p, idx) => (
                  <div key={idx} style={{ background: '#fbf9f5', borderRadius: '8px', padding: '16px', border: '1px solid #e5dec9' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <strong style={{ fontSize: '15px', color: '#1c2024' }}>{p.title || p.doc_type}</strong>
                      <span style={{ fontSize: '11px', background: '#15803d15', color: '#15803d', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>유효 공시본</span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#4b5563', lineHeight: 1.6, margin: 0 }}>
                      {p.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 8. 마이페이지 (탈퇴 즉시 비식별화) */}
        {activeMenu === 'mypage' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0', color: '#1c2024' }}>회원 정보 관리 및 설정</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '500px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>이름</label>
                <input type="text" disabled value="김예원" style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#8a939e', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>휴대폰 번호</label>
                <input type="text" value={myPhone} onChange={e => setMyPhone(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>목표 대학 [가군]</label>
                <input type="text" value={myTarget} onChange={e => setMyTarget(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>목표 대학 [나군]</label>
                <input type="text" value={myTargetB} onChange={e => setMyTargetB(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>목표 대학 [다군]</label>
                <input type="text" value={myTargetC} onChange={e => setMyTargetC(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button onClick={() => alert('개인정보가 성공적으로 저장되었습니다.')} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                  정보 수정 저장
                </button>
                <button onClick={() => alert('비밀번호 변경 링크가 전송되었습니다.')} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>
                  비밀번호 변경
                </button>
              </div>
            </div>

            <div style={{ borderTop: '1px solid #e5dec9', marginTop: '30px', paddingTop: '20px' }}>
              <h3 style={{ fontSize: '14px', color: '#d92632', margin: '0 0 6px 0' }}>위험 구역: 회원 탈퇴</h3>
              <p style={{ fontSize: '12px', color: '#646d78', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                탈퇴 시 회원의 모든 개인식별정보(PII)는 즉시 비식별화(익명화) 처리되며 복구할 수 없습니다.
              </p>
              <button onClick={() => setWithdrawalModal(true)} style={{ background: 'rgba(217,38,50,0.08)', border: '1px solid #d92632', color: '#d92632', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer', fontWeight: 600 }}>
                회원 탈퇴 (즉시 비식별화)
              </button>
            </div>
          </div>
        )}

        {/* 9. 회원가입 및 만 14세 미만 법정대리인 동의 플로우 */}
        {activeMenu === 'auth' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '24px', maxWidth: '600px', margin: '0 auto', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 8px 0', color: '#1c2024' }}>신규 회원가입 (PIPA 제22조의2 대응)</h2>
            <p style={{ fontSize: '12px', color: '#646d78', marginBottom: '20px', lineHeight: 1.5 }}>
              만 14세 미만 아동의 경우 법정대리인 동의가 완료될 때까지 계정이 <code>PENDING_GUARDIAN_CONSENT</code> 상태로 제한됩니다.
            </p>

            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>회원 유형</label>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <input type="radio" checked={regRole === 'STUDENT'} onChange={() => setRegRole('STUDENT')} style={{ accentColor: '#d92632' }} /> 학생 회원
                  </label>
                  <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <input type="radio" checked={regRole === 'PARENT'} onChange={() => setRegRole('PARENT')} style={{ accentColor: '#d92632' }} /> 학부모 회원
                  </label>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>가입자 성명</label>
                <input type="text" placeholder="예: 이태양" value={regName} onChange={e => setRegName(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>생년월일 (만 14세 미만 여부 자동 판별)</label>
                <input type="date" value={regBirth} onChange={e => setRegBirth(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
                {isUnder14 && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#d92632', background: 'rgba(217,38,50,0.08)', padding: '6px 10px', borderRadius: '4px', border: '1px solid rgba(217,38,50,0.25)' }}>
                    ⚠️ <strong>만 14세 미만 감지:</strong> 법정대리인(보호자) 동의 절차가 필수 적용됩니다.
                  </div>
                )}
              </div>

              {isUnder14 && (
                <div style={{ background: '#fbf9f5', padding: '14px', borderRadius: '8px', border: '1px solid #e5dec9', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#d92632' }}>🛡️ 법정대리인(보호자) 정보 입력</div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>보호자 성명</label>
                    <input type="text" placeholder="예: 이진우" value={guardianName} onChange={e => setGuardianName(e.target.value)} style={{ width: '100%', background: '#ffffff', border: '1px solid #e5dec9', color: '#1c2024', padding: '6px', borderRadius: '4px' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>보호자 휴대폰 번호 (동의 링크 발송용)</label>
                    <input type="text" placeholder="예: 010-9988-7766" value={guardianPhone} onChange={e => setGuardianPhone(e.target.value)} style={{ width: '100%', background: '#ffffff', border: '1px solid #e5dec9', color: '#1c2024', padding: '6px', borderRadius: '4px', fontFamily: "'IBM Plex Mono', monospace" }} />
                  </div>
                </div>
              )}

              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>소속 학원 가맹 코드</label>
                <input type="text" value={academyCode} onChange={e => setAcademyCode(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
              </div>

              <button type="submit" style={{ background: '#d92632', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', fontSize: '14px', fontWeight: 600, cursor: 'pointer', marginTop: '10px', boxShadow: '0 2px 6px rgba(217,38,50,0.3)' }}>
                가입 신청하기
              </button>
            </form>

            {regStatus && (
              <div style={{ marginTop: '16px', padding: '12px', borderRadius: '6px', background: regStatus === 'PENDING_GUARDIAN_CONSENT' ? 'rgba(217,38,50,0.08)' : 'rgba(21,128,61,0.08)', border: '1px solid', borderColor: regStatus === 'PENDING_GUARDIAN_CONSENT' ? '#d92632' : '#15803d', fontSize: '13px' }}>
                <strong style={{ color: regStatus === 'PENDING_GUARDIAN_CONSENT' ? '#d92632' : '#15803d' }}>상태: {regStatus}</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#4b5563' }}>
                  {regStatus === 'PENDING_GUARDIAN_CONSENT' ? '보호자의 본인인증 완료 전까지 실기작품 및 결제 메뉴가 보호됩니다.' : '정상 회원가입이 완료되었습니다.'}
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── 비공개 실기 작품 서명 URL 모달 ── */}
      {signedUrlModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '12px', padding: '24px', maxWidth: '500px', width: '100%', color: '#1c2024', boxShadow: '0 4px 20px rgba(0,0,0,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', color: '#d92632' }}>🔒 보안 서명 URL (Signed URL) 열람</h3>
              <span style={{ fontSize: '11px', background: '#15803d15', color: '#15803d', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>유효시간 3600초</span>
            </div>
            <div style={{ height: '220px', background: '#fbf9f5', borderRadius: '8px', border: '1px solid #e5dec9', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '50px' }}>🎨</span>
              <strong style={{ fontSize: '15px' }}>{signedUrlModal.title}</strong>
              <span style={{ fontSize: '14px', color: '#d92632', fontWeight: 800, fontFamily: "'IBM Plex Mono', monospace" }}>실기 점수: {signedUrlModal.score}점 (비공개 스토리지)</span>
            </div>
            <p style={{ fontSize: '11px', color: '#646d78', marginTop: '10px', lineHeight: 1.5 }}>
              지시서 v2.0 제3.9절 규정에 따라 원본 실기작품 이미지는 비공개 버킷에 저장되며 만료형 서명 URL을 통해서만 허가된 원생 및 학부모 본인에게 안전하게 전달됩니다.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button onClick={() => setSignedUrlModal(null)} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 회원 탈퇴 확인 모달 (비식별화) ── */}
      {withdrawalModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#ffffff', border: '1px solid #d92632', borderRadius: '12px', padding: '24px', maxWidth: '440px', width: '100%', color: '#1c2024', boxShadow: '0 4px 20px rgba(0,0,0,0.15)' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', color: '#d92632' }}>⚠️ 정말로 탈퇴하시겠습니까?</h3>
            <p style={{ fontSize: '13px', color: '#4b5563', lineHeight: 1.6 }}>
              탈퇴 시 즉시 귀하의 이름, 연락처 등 모든 개인정보가 <code>ANONYMOUS_USER</code>로 비식별화 처리되며, 모든 연동 권한이 영구 해제됩니다.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setWithdrawalModal(false)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleWithdrawal} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>탈퇴 및 즉시 비식별화</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
