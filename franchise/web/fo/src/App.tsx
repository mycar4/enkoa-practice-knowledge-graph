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

// ── v5.0 신규 타입 ──
interface GradeRecord {
  id: string;
  label: string;
  source_type: 'manual' | 'nice_html' | 'txt';
  is_primary: boolean;
  created_at: string;
  parsed_json: {
    korean?: number;
    english?: number;
    history?: number;
    inquiry1?: number;
    inquiry2?: number;
    practical_score?: number;
    gpa?: number;
    art_subject?: string;
  };
}

interface DocumentRecord {
  id: string;
  label: string;
  doc_type: string;
  created_at: string;
  feedback_json: {
    reviewer?: string;
    score?: number;
    comment?: string;
  };
}

interface TenantProfile {
  id: string;
  name: string;
  slug: string;
  logo_url: string;
  intro_text: string;
  instructors: Array<{ name: string; role: string; career: string }>;
  highlight_stats: Array<{ title: string; value: string }>;
  contact_info: {
    address: string;
    phone: string;
    consult_open: string;
  };
  is_public_published: boolean;
}

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'info' | 'error';
  timestamp: string;
}

const API_BASE = (import.meta as any).env?.VITE_API_URL || '/api/v1';

export default function App() {
  // 역할 전환: 학생 vs 학부모
  const [role, setRole] = useState<'STUDENT' | 'PARENT'>('STUDENT');

  // 전체 메뉴 탭 (v5.0 메뉴 3종 추가: grade_records, documents, tenant_intro)
  const [activeMenu, setActiveMenu] = useState<string>('home');

  // 토스트 알림 상태 (첨삭펜 마이크로 인터랙션)
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'success') => {
    const id = Math.random().toString(36).substring(7);
    const now = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    setToasts(prev => [...prev, { id, message, type, timestamp: now }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  };

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

  // 출결 데이터
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

  // ── v5.0 신규: 성적 기록함 상태 ──
  const [gradeRecords, setGradeRecords] = useState<GradeRecord[]>([
    {
      id: 'gr-01',
      label: '2026학년도 수시 실전모의 1차',
      source_type: 'manual',
      is_primary: true,
      created_at: '2026-09-18T16:30:00Z',
      parsed_json: { korean: 1, english: 2, history: 1, inquiry1: 2, inquiry2: 2, practical_score: 92 }
    },
    {
      id: 'gr-02',
      label: '고2 2학기 학교생활기록부',
      source_type: 'nice_html',
      is_primary: false,
      created_at: '2026-03-10T10:00:00Z',
      parsed_json: { gpa: 2.15, art_subject: 'A' }
    }
  ]);
  const [gradeModalOpen, setGradeModalOpen] = useState(false);
  const [newGradeLabel, setNewGradeLabel] = useState('');
  const [newGradeSource, setNewGradeSource] = useState<'manual' | 'nice_html' | 'txt'>('manual');
  const [newGradeKorean, setNewGradeKorean] = useState('1');
  const [newGradeEnglish, setNewGradeEnglish] = useState('2');
  const [newGradePractical, setNewGradePractical] = useState('92');

  // ── v5.0 신규: 서류함 상태 ──
  const [documents, setDocuments] = useState<DocumentRecord[]>([
    {
      id: 'doc-01',
      label: '국민대 조형대학 자기소개서 초안',
      doc_type: '자기소개서',
      created_at: '2026-09-15T14:20:00Z',
      feedback_json: {
        reviewer: '이민혁 수석강사',
        score: 90,
        comment: '지원 동기 부분의 조형적 계기가 구체적임. 2번 문항의 갈등 해결 과정을 미술 프로젝트 협업 사례로 보강할 것.'
      }
    }
  ]);
  const [docModalOpen, setDocModalOpen] = useState(false);
  const [newDocLabel, setNewDocLabel] = useState('');
  const [newDocType, setNewDocType] = useState('자기소개서');

  // ── v5.0 신규: 학원별 소개 페이지 및 전용 로그인 ──
  const [tenantSlug, setTenantSlug] = useState('gangnam-main');
  const [tenantProfile, setTenantProfile] = useState<TenantProfile>({
    id: 't-01',
    name: '강남 미술학원 본원',
    slug: 'gangnam-main',
    logo_url: '🎨',
    intro_text: '20년 전통의 디자인/기초소양 명문. 국민대, 서울대, 과기대 수시/정시 압도적 합격률을 자랑합니다. 1:1 강사 실시간 첨삭 시스템을 완비했습니다.',
    instructors: [
      { name: '이민혁', role: '수석전임강사', career: '홍익대 미술대학 졸, 12년차 입시총괄' },
      { name: '장수진', role: '전임강사', career: '국민대 조형대학 졸, 기초조형 전담' }
    ],
    highlight_stats: [
      { title: '2026 수시 합격률', value: '89.4%' },
      { title: '국민대/서울과기대', value: '42명 합격' },
      { title: '실기 만점자 배출', value: '8명' }
    ],
    contact_info: {
      address: '서울특별시 강남구 테헤란로 124 삼원빌딩 4~5층',
      phone: '02-555-7890',
      consult_open: '평일 13:00 ~ 22:00 / 토 09:00 ~ 18:00'
    },
    is_public_published: true
  });
  const [tenantLoginOpen, setTenantLoginOpen] = useState(false);
  const [tenantLoginId, setTenantLoginId] = useState('');
  const [tenantLoginPw, setTenantLoginPw] = useState('');

  // 정책 문서 (자체 백엔드 API 호출로 전면 교체 - Supabase direct anon key 차단)
  const [policies, setPolicies] = useState<PolicyDoc[]>([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);

  // 모달 상태들
  const [signedUrlModal, setSignedUrlModal] = useState<{ open: boolean; title: string; score: number } | null>(null);
  const [withdrawalModal, setWithdrawalModal] = useState(false);
  const [childCodeInput, setChildCodeInput] = useState('');
  const [linkSuccess, setLinkSuccess] = useState(false);

  // 회원가입 폼 상태
  const [regRole, setRegRole] = useState<'STUDENT' | 'PARENT'>('STUDENT');
  const [regName, setRegName] = useState('');
  const [regBirth, setRegBirth] = useState('2013-05-12');
  const [isUnder14, setIsUnder14] = useState(false);
  const [guardianName, setGuardianName] = useState('');
  const [guardianPhone, setGuardianPhone] = useState('');
  const [academyCode, setAcademyCode] = useState('GANGNAM-01');
  const [regStatus, setRegStatus] = useState<string | null>(null);

  // 마이페이지 프로필
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

  // 자체 백엔드 API 경유 정책 조회 (v5.0 1.3절 보안 수칙: Supabase REST/anon key 직접 노출 전면 차단)
  const fetchPolicies = async () => {
    setLoadingPolicies(true);
    try {
      const res = await fetch(`${API_BASE}/policies`);
      if (res.ok) {
        const data = await res.json();
        setPolicies(data.policies || []);
        showToast('최신 공시 정책 문서를 백엔드에서 안전하게 동기화했습니다.', 'info');
      } else {
        throw new Error('API Response not ok');
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

  // ── v5.0 성적 기록함 CRUD ──
  const handleSetPrimaryGrade = async (id: string) => {
    try {
      await fetch(`${API_BASE}/fo/grade-records/${id}/primary`, { method: 'PATCH' });
    } catch {}
    setGradeRecords(prev =>
      prev.map(r => ({ ...r, is_primary: r.id === id }))
    );
    showToast('대표 성적이 변경되었습니다. 추천/진학 상담 시 이 성적이 기본 적용됩니다.');
  };

  const handleCreateGradeRecord = async () => {
    if (!newGradeLabel.trim()) {
      showToast('성적표 구분을 입력해주세요 (예: 2026 수시 실전모의).', 'error');
      return;
    }
    const newRecord: GradeRecord = {
      id: `gr-${Date.now().toString(36)}`,
      label: newGradeLabel,
      source_type: newGradeSource,
      is_primary: gradeRecords.length === 0,
      created_at: new Date().toISOString(),
      parsed_json: {
        korean: Number(newGradeKorean),
        english: Number(newGradeEnglish),
        practical_score: Number(newGradePractical)
      }
    };
    try {
      await fetch(`${API_BASE}/fo/grade-records`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRecord)
      });
    } catch {}
    setGradeRecords(prev => [newRecord, ...prev]);
    setGradeModalOpen(false);
    setNewGradeLabel('');
    showToast(`'${newRecord.label}' 성적 기록이 계정에 안전하게 보관되었습니다.`);
  };

  const handleDeleteGradeRecord = async (id: string) => {
    try {
      await fetch(`${API_BASE}/fo/grade-records/${id}`, { method: 'DELETE' });
    } catch {}
    setGradeRecords(prev => prev.filter(r => r.id !== id));
    showToast('성적 기록이 삭제되었습니다.');
  };

  // ── v5.0 서류함 CRUD ──
  const handleCreateDocument = async () => {
    if (!newDocLabel.trim()) {
      showToast('서류 제목을 입력해주세요.', 'error');
      return;
    }
    const newDoc: DocumentRecord = {
      id: `doc-${Date.now().toString(36)}`,
      label: newDocLabel,
      doc_type: newDocType,
      created_at: new Date().toISOString(),
      feedback_json: {
        reviewer: '전임 평가팀',
        score: 88,
        comment: '신규 업로드 접수 완료. 전임 강사진의 1:1 맞춤 첨삭이 진행될 예정입니다.'
      }
    };
    try {
      await fetch(`${API_BASE}/fo/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newDoc)
      });
    } catch {}
    setDocuments(prev => [newDoc, ...prev]);
    setDocModalOpen(false);
    setNewDocLabel('');
    showToast(`'${newDoc.label}' 서류가 서류함에 등록되었습니다.`);
  };

  const handleDeleteDocument = async (id: string) => {
    try {
      await fetch(`${API_BASE}/fo/documents/${id}`, { method: 'DELETE' });
    } catch {}
    setDocuments(prev => prev.filter(d => d.id !== id));
    showToast('서류가 삭제되었습니다.');
  };

  // ── v5.0 학원 소개 페이지 전환 ──
  const handleTenantSelect = async (slug: string) => {
    setTenantSlug(slug);
    try {
      const res = await fetch(`${API_BASE}/fo/tenants/${slug}`);
      if (res.ok) {
        const data = await res.json();
        setTenantProfile(data.tenant);
      }
    } catch {}
    showToast(`'${slug === 'gangnam-main' ? '강남 미술학원 본원' : '홍대 디자인캠퍼스'}' 소개 정보가 로드되었습니다.`, 'info');
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText('AR-2026-9812');
    showToast('학부모 연동 코드 [AR-2026-9812]가 복사되었습니다.\n학부모님 가입 시 자녀 연동란에 입력해 주세요.');
  };

  const handleLinkChild = (e: React.FormEvent) => {
    e.preventDefault();
    if (!childCodeInput.trim()) {
      showToast('자녀 연동 코드를 입력해주세요.', 'error');
      return;
    }
    setLinkSuccess(true);
    showToast(`자녀 연동 코드 [${childCodeInput}]가 인증되었습니다.\n김예원 원생의 실기 평가, 출결, 수강료 내역이 연동됩니다.`);
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!regName.trim()) {
      showToast('이름을 입력해주세요.', 'error');
      return;
    }
    if (isUnder14) {
      if (!guardianName.trim() || !guardianPhone.trim()) {
        showToast('만 14세 미만 아동은 법정대리인(보호자)의 성명과 연락처가 필수입니다.', 'error');
        return;
      }
      setRegStatus('PENDING_GUARDIAN_CONSENT');
      showToast(`[가입 접수 — 보호자 동의 대기]\n회원 가입 상태가 [PENDING_GUARDIAN_CONSENT]로 등록되었습니다.\n보호자(${guardianName}님)께 동의 URL이 발송되었습니다.`);
    } else {
      setRegStatus('ACTIVE');
      showToast(`[가입 완료] ${regName}님 환영합니다! 소속 학원(${academyCode}) 승인이 완료되었습니다.`);
    }
  };

  const handleWithdrawal = () => {
    showToast('[회원 탈퇴 및 비식별화 처리 완료]\n개인 식별 정보(PII)가 즉시 암호화 파기 및 ANONYMOUS_USER로 비식별화되었습니다.');
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
              <span style={{ fontSize: '12px', color: '#646d78', marginLeft: '6px' }}>수험생·학부모 포털 (v5.0)</span>
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

        {/* ── 메뉴 알약형 탭 내비게이션 (v5.0 신규 메뉴 3종 포함) ── */}
        <div style={{ maxWidth: '960px', margin: '10px auto 0 auto', display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
          {[
            { key: 'home', label: '🏠 홈/성적표' },
            { key: 'grade_records', label: '📊 성적 기록함 (v5.0)' },
            { key: 'documents', label: '📁 서류함 (v5.0)' },
            { key: 'tenant_intro', label: '🏫 학원 소개/입학 (v5.0)' },
            { key: 'evaluations', label: '🎨 실기 작품 & 첨삭' },
            { key: 'attendance', label: '📅 출결 이력' },
            { key: 'album', label: '📸 수업 앨범' },
            { key: 'tuition', label: '💳 수강료 납부내역' },
            { key: 'parent_link', label: '👨‍👩‍👧 학부모 연동' },
            { key: 'policies', label: '📜 정책/약관' },
            { key: 'mypage', label: '👤 마이페이지' },
            { key: 'auth', label: '🔐 회원가입/인증' }
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
            <div style={{ background: '#ffffff', border: '2px solid #d92632', borderRadius: '12px', padding: '28px 24px', boxShadow: '0 4px 14px rgba(217,38,50,0.08)', position: 'relative' }}>
              <div style={{ position: 'absolute', top: '20px', right: '24px', border: '2px solid #d92632', color: '#d92632', padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 800, transform: 'rotate(-3deg)', letterSpacing: '1px', fontFamily: "'IBM Plex Mono', monospace", background: '#fff8f8' }}>
                첨삭완료 VERIFIED
              </div>

              <span style={{ fontSize: '13px', color: '#646d78', fontWeight: 600 }}>2026학년도 수시 1차 실전모의평가 결과</span>
              <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '4px 0 0 0', color: '#1c2024' }}>
                기초디자인 — 유리 질감과 금속 구의 공간 구성
              </h2>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '14px 0 6px 0' }}>
                <span style={{ fontSize: '56px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1 }}>
                  92
                </span>
                <span style={{ fontSize: '22px', fontWeight: 700, color: '#d92632' }}>점</span>
                <span style={{ marginLeft: '12px', fontSize: '13px', background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '4px 10px', borderRadius: '20px', fontWeight: 600 }}>
                  상위 4.8% (A+ 등급)
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', marginTop: '16px', borderTop: '1px solid #f0e9d8', paddingTop: '16px' }}>
                <div style={{ background: '#fbf9f5', padding: '10px 14px', borderRadius: '8px', border: '1px solid #e5dec9' }}>
                  <span style={{ fontSize: '11px', color: '#646d78' }}>채점 강사</span>
                  <div style={{ fontWeight: 700, fontSize: '14px', color: '#1c2024', marginTop: '2px' }}>이민혁 수석강사</div>
                </div>
                <div style={{ background: '#fbf9f5', padding: '10px 14px', borderRadius: '8px', border: '1px solid #e5dec9' }}>
                  <span style={{ fontSize: '11px', color: '#646d78' }}>평가일자</span>
                  <div style={{ fontWeight: 700, fontSize: '14px', color: '#1c2024', marginTop: '2px', fontFamily: "'IBM Plex Mono', monospace" }}>2026-09-18</div>
                </div>
                <div style={{ background: '#fbf9f5', padding: '10px 14px', borderRadius: '8px', border: '1px solid #e5dec9' }}>
                  <span style={{ fontSize: '11px', color: '#646d78' }}>소속 반</span>
                  <div style={{ fontWeight: 700, fontSize: '14px', color: '#1c2024', marginTop: '2px' }}>고3 실전입시 정규반</div>
                </div>
              </div>

              <div style={{ marginTop: '18px', background: '#fffbfa', borderLeft: '4px solid #d92632', padding: '14px 16px', borderRadius: '0 8px 8px 0' }}>
                <strong style={{ fontSize: '13px', color: '#d92632' }}>✍️ 수석강사 총평 (첨삭 가이드)</strong>
                <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: '#374151', lineHeight: 1.6 }}>
                  "주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 주제부와의 원근 대비를 극대화할 필요가 있습니다. 다음 모의고사에서는 구도 시간 단축에 집중합시다."
                </p>
              </div>

              <div style={{ marginTop: '16px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setSignedUrlModal({ open: true, title: '기초디자인 — 유리 질감과 금속 구의 공간 구성', score: 92 })}
                  style={{ background: '#d92632', color: '#ffffff', border: 'none', padding: '9px 18px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 2px 6px rgba(217,38,50,0.25)' }}
                >
                  🔒 보안 원본작품 보기 (1시간 만료)
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── v5.0 신규 메뉴 1: 성적 기록함 (STUDENT_GRADE_RECORDS) ── */}
        {activeMenu === 'grade_records' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>📊 성적 기록함 (계정 기반 이력 보관)</h2>
                  <span style={{ fontSize: '12px', color: '#646d78' }}>
                    1·2·3학년 학기별/모평별 성적을 영구 보관하고, 기존 공개 사이트(www.artready.kr/fo/grades.html)와 즉시 연동합니다.
                  </span>
                </div>
                <button
                  onClick={() => setGradeModalOpen(true)}
                  style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
                >
                  + 새 성적 등록
                </button>
              </div>

              {/* 연계 안내 배너 */}
              <div style={{ marginTop: '14px', background: '#fff8f8', border: '1px dashed #d92632', borderRadius: '8px', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '20px' }}>🔗</span>
                <div style={{ fontSize: '12.5px', color: '#1c2024' }}>
                  <strong>기존 공개 서비스 연계:</strong> '성적추천' 화면에서 로그인 시 아래 보관된 성적 중 하나를 골라 즉시 진학 진단 및 모의 지원을 실행할 수 있습니다.
                </div>
              </div>

              {/* 기록 목록 */}
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {gradeRecords.map(gr => (
                  <div key={gr.id} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', padding: '16px', position: 'relative' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <h4 style={{ margin: 0, fontSize: '15px', color: '#1c2024' }}>{gr.label}</h4>
                        {gr.is_primary && (
                          <span style={{ background: '#d92632', color: '#fff', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                            ★ 현재 대표 성적
                          </span>
                        )}
                        <span style={{ background: '#e5dec9', color: '#4b5563', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', textTransform: 'uppercase' }}>
                          {gr.source_type}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {!gr.is_primary && (
                          <button
                            onClick={() => handleSetPrimaryGrade(gr.id)}
                            style={{ background: '#ffffff', color: '#d92632', border: '1px solid #d92632', padding: '4px 10px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                          >
                            대표 성적 지정
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteGradeRecord(gr.id)}
                          style={{ background: '#ffffff', color: '#646d78', border: '1px solid #e5dec9', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}
                        >
                          삭제
                        </button>
                      </div>
                    </div>

                    <div style={{ marginTop: '10px', display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '13px' }}>
                      {gr.parsed_json.korean && <div>국어: <strong>{gr.parsed_json.korean}등급</strong></div>}
                      {gr.parsed_json.english && <div>영어: <strong>{gr.parsed_json.english}등급</strong></div>}
                      {gr.parsed_json.practical_score && <div>실기: <strong style={{ color: '#d92632' }}>{gr.parsed_json.practical_score}점</strong></div>}
                      {gr.parsed_json.gpa && <div>내신 평점: <strong>{gr.parsed_json.gpa}</strong></div>}
                      {gr.parsed_json.art_subject && <div>미술 교과: <strong>{gr.parsed_json.art_subject}</strong></div>}
                    </div>

                    <div style={{ marginTop: '8px', fontSize: '11px', color: '#9ca3af', fontFamily: "'IBM Plex Mono', monospace" }}>
                      등록일시: {new Date(gr.created_at).toLocaleString('ko-KR')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── v5.0 신규 메뉴 2: 서류함 (STUDENT_DOCUMENTS) ── */}
        {activeMenu === 'documents' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>📁 서류함 (첨삭 문서 이력 보관)</h2>
                  <span style={{ fontSize: '12px', color: '#646d78' }}>
                    자기소개서, 포트폴리오 설명서, 추천서 등의 첨삭 이력을 계정에 영구 보관하고 재활용합니다.
                  </span>
                </div>
                <button
                  onClick={() => setDocModalOpen(true)}
                  style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
                >
                  + 새 서류 등록
                </button>
              </div>

              {/* 연계 안내 배너 */}
              <div style={{ marginTop: '14px', background: '#fff8f8', border: '1px dashed #d92632', borderRadius: '8px', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '20px' }}>✍️</span>
                <div style={{ fontSize: '12.5px', color: '#1c2024' }}>
                  <strong>서류첨삭 연동:</strong> '서류첨삭' 서비스(www.artready.kr/fo/review.html)에서 작성된 첨삭 피드백이 이 서류함에 자동 보관됩니다.
                </div>
              </div>

              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {documents.map(doc => (
                  <div key={doc.id} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <span style={{ background: '#1c2024', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                          {doc.doc_type}
                        </span>
                        <h4 style={{ margin: '6px 0 0 0', fontSize: '15px', color: '#1c2024' }}>{doc.label}</h4>
                      </div>
                      <button
                        onClick={() => handleDeleteDocument(doc.id)}
                        style={{ background: '#ffffff', color: '#646d78', border: '1px solid #e5dec9', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}
                      >
                        삭제
                      </button>
                    </div>

                    {doc.feedback_json && (
                      <div style={{ marginTop: '12px', background: '#ffffff', borderLeft: '3px solid #d92632', padding: '10px 14px', borderRadius: '0 6px 6px 0', border: '1px solid #e5dec9', borderLeftWidth: '3px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 700, color: '#d92632' }}>첨삭 담당: {doc.feedback_json.reviewer}</span>
                          {doc.feedback_json.score && <span style={{ fontWeight: 800, fontFamily: "'IBM Plex Mono', monospace" }}>{doc.feedback_json.score}점</span>}
                        </div>
                        <p style={{ margin: 0, fontSize: '12.5px', color: '#374151', lineHeight: 1.5 }}>
                          {doc.feedback_json.comment}
                        </p>
                      </div>
                    )}

                    <div style={{ marginTop: '8px', fontSize: '11px', color: '#9ca3af', fontFamily: "'IBM Plex Mono', monospace" }}>
                      업로드: {new Date(doc.created_at).toLocaleString('ko-KR')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── v5.0 신규 메뉴 3: 학원별 소개 페이지 + 전용 로그인 ── */}
        {activeMenu === 'tenant_intro' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 캠퍼스 선택 바 */}
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#646d78' }}>가맹 캠퍼스 선택:</span>
                <button
                  onClick={() => handleTenantSelect('gangnam-main')}
                  style={{
                    padding: '6px 12px', borderRadius: '6px', border: '1px solid',
                    borderColor: tenantSlug === 'gangnam-main' ? '#d92632' : '#e5dec9',
                    background: tenantSlug === 'gangnam-main' ? '#d92632' : '#ffffff',
                    color: tenantSlug === 'gangnam-main' ? '#ffffff' : '#1c2024',
                    fontSize: '12.5px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  강남 미술학원 본원
                </button>
                <button
                  onClick={() => handleTenantSelect('hongdae-campus')}
                  style={{
                    padding: '6px 12px', borderRadius: '6px', border: '1px solid',
                    borderColor: tenantSlug === 'hongdae-campus' ? '#d92632' : '#e5dec9',
                    background: tenantSlug === 'hongdae-campus' ? '#d92632' : '#ffffff',
                    color: tenantSlug === 'hongdae-campus' ? '#ffffff' : '#1c2024',
                    fontSize: '12.5px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  홍대 디자인캠퍼스
                </button>
              </div>
              <div style={{ fontSize: '12px', color: '#15803d', fontWeight: 600 }}>
                ✓ 본사 인증 가맹 캠퍼스 공시
              </div>
            </div>

            {/* 학원 소개 히어로 섹션 */}
            <div style={{ background: '#ffffff', border: '2px solid #d92632', borderRadius: '12px', padding: '28px 24px', boxShadow: '0 4px 14px rgba(217,38,50,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                  <span style={{ fontSize: '42px', background: '#fbf9f5', padding: '8px 12px', borderRadius: '12px', border: '1px solid #e5dec9' }}>
                    {tenantProfile.logo_url || '🎨'}
                  </span>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: 0, color: '#1c2024' }}>{tenantProfile.name}</h1>
                      <span style={{ background: '#d92632', color: '#fff', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>
                        OFFICIAL
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>
                      URL: app.artready.kr/t/{tenantProfile.slug}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => setTenantLoginOpen(true)}
                  style={{ background: '#d92632', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '6px', fontSize: '14px', fontWeight: 700, cursor: 'pointer', boxShadow: '0 2px 8px rgba(217,38,50,0.3)' }}
                >
                  {tenantProfile.name} 전용 로그인 / 입학상담
                </button>
              </div>

              <p style={{ marginTop: '18px', fontSize: '14px', color: '#374151', lineHeight: 1.7 }}>
                {tenantProfile.intro_text}
              </p>

              {/* 합격 실적 및 지표 */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginTop: '20px' }}>
                {tenantProfile.highlight_stats.map((stat, idx) => (
                  <div key={idx} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', padding: '14px', textAlign: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#646d78' }}>{stat.title}</span>
                    <div style={{ fontSize: '22px', fontWeight: 800, color: '#d92632', marginTop: '4px', fontFamily: "'IBM Plex Mono', monospace" }}>
                      {stat.value}
                    </div>
                  </div>
                ))}
              </div>

              {/* 강사진 소개 */}
              <div style={{ marginTop: '24px' }}>
                <h3 style={{ fontSize: '15px', color: '#1c2024', margin: '0 0 10px 0' }}>👨‍🏫 전임 강사진</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
                  {tenantProfile.instructors.map((ins, idx) => (
                    <div key={idx} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '6px', padding: '12px' }}>
                      <div style={{ fontWeight: 700, fontSize: '14px', color: '#1c2024' }}>
                        {ins.name} <span style={{ fontSize: '12px', color: '#d92632', fontWeight: 600 }}>({ins.role})</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#646d78', marginTop: '4px' }}>{ins.career}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 위치 및 연락처 */}
              <div style={{ marginTop: '24px', background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', padding: '16px' }}>
                <h3 style={{ fontSize: '14px', color: '#1c2024', margin: '0 0 8px 0' }}>📍 캠퍼스 위치 및 상담 안내</h3>
                <div style={{ fontSize: '13px', color: '#4b5563', lineHeight: 1.6 }}>
                  <div><strong>주소:</strong> {tenantProfile.contact_info.address}</div>
                  <div><strong>전화번호:</strong> <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{tenantProfile.contact_info.phone}</span></div>
                  <div><strong>상담시간:</strong> {tenantProfile.contact_info.consult_open}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. 실기 작품 & 첨삭 */}
        {activeMenu === 'evaluations' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>실기 모의고사 & 과제 첨삭 이력</h2>
                <span style={{ fontSize: '12px', color: '#646d78' }}>누적 {evaluations.length}건 평가 완료</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {evaluations.map(ev => (
                  <div key={ev.id} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', padding: '18px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '28px' }}>{ev.imageEmoji}</span>
                        <div>
                          <span style={{ fontSize: '11px', background: '#d92632', color: '#ffffff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
                            {ev.type}
                          </span>
                          <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '4px 0 0 0', color: '#1c2024' }}>
                            {ev.title}
                          </h3>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                        <span style={{ fontSize: '32px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>
                          {ev.score}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 700, color: '#d92632' }}>점</span>
                      </div>
                    </div>

                    <div style={{ marginTop: '14px', background: '#ffffff', borderLeft: '3px solid #d92632', padding: '12px 14px', borderRadius: '0 6px 6px 0', border: '1px solid #e5dec9', borderLeftWidth: '3px' }}>
                      <strong style={{ fontSize: '12px', color: '#d92632' }}>{ev.instructor} 첨삭 피드백:</strong>
                      <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#374151', lineHeight: 1.5 }}>
                        {ev.feedback}
                      </p>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px', paddingTop: '10px', borderTop: '1px solid #f0e9d8' }}>
                      <span style={{ fontSize: '12px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>{ev.date}</span>
                      <button
                        onClick={() => setSignedUrlModal({ open: true, title: ev.title, score: ev.score })}
                        style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '5px 12px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                      >
                        🔒 보안 원본 이미지 열람
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 3. 출결 이력 */}
        {activeMenu === 'attendance' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#1c2024' }}>2026년 9월 출결 현황</h2>
                <span style={{ fontSize: '12px', color: '#646d78' }}>실시간 입퇴실 기록</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span style={{ background: '#15803d15', color: '#15803d', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>출석 18일</span>
                <span style={{ background: '#b4530915', color: '#b45309', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>지각 1회</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '6px', textAlign: 'center' }}>
              {['일', '월', '화', '수', '목', '금', '토'].map(d => (
                <div key={d} style={{ fontSize: '12px', fontWeight: 700, color: '#646d78', padding: '8px' }}>{d}</div>
              ))}
              {attendanceDays.map(d => (
                <div
                  key={d.day}
                  style={{
                    height: '56px',
                    borderRadius: '6px',
                    border: '1px solid #f0e9d8',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: d.status === 'PRESENT' ? '#15803d10' : d.status === 'LATE' ? '#b4530915' : '#fbf9f5'
                  }}
                >
                  <span style={{ fontSize: '11px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>{d.day}</span>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: d.status === 'PRESENT' ? '#15803d' : d.status === 'LATE' ? '#b45309' : '#9ca3af', marginTop: '2px' }}>
                    {d.status === 'PRESENT' ? '출석' : d.status === 'LATE' ? '지각' : '-'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 4. 수업 앨범 */}
        {activeMenu === 'album' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0', color: '#1c2024' }}>수업 앨범 (실습 및 시연 현장)</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              {albumPosts.map(post => (
                <div key={post.id} style={{ background: '#fbf9f5', border: '1px solid #e5dec9', borderRadius: '8px', overflow: 'hidden' }}>
                  <div style={{ height: '140px', background: '#f3eee4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '48px' }}>
                    {post.imageEmoji}
                  </div>
                  <div style={{ padding: '14px' }}>
                    <span style={{ fontSize: '11px', color: '#d92632', fontWeight: 600 }}>{post.className}</span>
                    <h4 style={{ margin: '4px 0', fontSize: '15px', color: '#1c2024' }}>{post.title}</h4>
                    <p style={{ margin: '6px 0 0 0', fontSize: '12px', color: '#4b5563', lineHeight: 1.5 }}>
                      {post.caption}
                    </p>
                    <div style={{ marginTop: '10px', fontSize: '11px', color: '#9ca3af', fontFamily: "'IBM Plex Mono', monospace" }}>
                      {post.date} · {post.instructor}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. 수강료 납부 내역 */}
        {activeMenu === 'tuition' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0', color: '#1c2024' }}>수강료 납부 및 영수증 내역</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5dec9', color: '#646d78' }}>
                  <th style={{ padding: '8px 10px' }}>청구월</th>
                  <th style={{ padding: '8px 10px' }}>과정명</th>
                  <th style={{ padding: '8px 10px' }}>금액</th>
                  <th style={{ padding: '8px 10px' }}>상태</th>
                  <th style={{ padding: '8px 10px' }}>영수증</th>
                </tr>
              </thead>
              <tbody>
                {tuitionList.map(t => (
                  <tr key={t.id} style={{ borderBottom: '1px solid #f0e9d8' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{t.month}</td>
                    <td style={{ padding: '12px 10px', color: '#646d78' }}>{t.className}</td>
                    <td style={{ padding: '12px 10px', fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{t.amount.toLocaleString()}원</td>
                    <td style={{ padding: '12px 10px' }}>
                      <span style={{ background: '#15803d15', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>완납</span>
                    </td>
                    <td style={{ padding: '12px 10px' }}>
                      <button
                        onClick={() => showToast(`[전자영수증 발급]\n영수증 번호: ${t.receiptNo}\n학원명: 강남 미술학원 본원\n금액: ${t.amount.toLocaleString()}원\n정상 결제 완료되었습니다.`)}
                        style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}
                      >
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
                <span style={{ fontSize: '12px', color: '#646d78' }}>개인정보보호법 및 가맹 표준 준수 (자체 백엔드 API 연동)</span>
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
                <button onClick={() => showToast('개인정보가 성공적으로 저장되었습니다.')} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                  정보 수정 저장
                </button>
                <button onClick={() => showToast('비밀번호 변경 링크가 등록된 휴대폰으로 전송되었습니다.', 'info')} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e5dec9', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>
                  비밀번호 변경
                </button>
              </div>
            </div>

            <div style={{ borderTop: '1px solid #e5dec9', marginTop: '30px', paddingTop: '20px' }}>
              <h3 style={{ fontSize: '14px', color: '#d92632', margin: '0 0 6px 0' }}>위험 구역: 회원 탈퇴</h3>
              <p style={{ fontSize: '12px', color: '#646d78', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                탈퇴 시 회원의 모든 개인식별정보(PII)는 즉시 비식별화(익명화) 처리되며 복구할 수 없습니다.
              </p>
              <button onClick={() => setWithdrawalModal(true)} style={{ background: '#fee2e2', color: '#d92632', border: '1px solid #fecaca', padding: '8px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                회원 탈퇴 신청
              </button>
            </div>
          </div>
        )}

        {/* 9. 회원가입 및 만 14세 미만 보호자 동의 플로우 */}
        {activeMenu === 'auth' && (
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '10px', padding: '24px', maxWidth: '560px', margin: '0 auto', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 4px 0', color: '#1c2024' }}>
              ART:READY 회원가입
            </h2>
            <p style={{ fontSize: '12px', color: '#646d78', margin: '0 0 16px 0' }}>
              개인정보보호법 제22조의2 준수 — 만 14세 미만 법정대리인 동의 필수
            </p>

            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>회원 유형</label>
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
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>성명</label>
                <input type="text" placeholder="예: 김예원" value={regName} onChange={e => setRegName(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>생년월일</label>
                <input type="date" value={regBirth} onChange={e => setRegBirth(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e5dec9', color: '#1c2024', padding: '8px', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
                {isUnder14 && (
                  <span style={{ fontSize: '11.5px', color: '#d92632', display: 'block', marginTop: '4px', fontWeight: 600 }}>
                    ⚠️ 만 14세 미만 아동으로 감지되었습니다. 보호자 동의 절차가 필요합니다.
                  </span>
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

      {/* ── v5.0 신규 모달 1: 성적 추가 모달 ── */}
      {gradeModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '12px', padding: '24px', maxWidth: '440px', width: '100%', boxShadow: '0 8px 24px rgba(0,0,0,0.15)' }}>
            <h3 style={{ margin: '0 0 14px 0', fontSize: '16px', color: '#d92632' }}>📊 새 성적 기록 추가 (v5.0)</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>성적 구분 라벨</label>
                <input type="text" placeholder="예: 고2-2학기 모의평가" value={newGradeLabel} onChange={e => setNewGradeLabel(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>입력 방식</label>
                <select value={newGradeSource} onChange={e => setNewGradeSource(e.target.value as any)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px' }}>
                  <option value="manual">수기 직접 입력</option>
                  <option value="nice_html">나이스(NEIS) HTML 파싱</option>
                  <option value="txt">성적 텍스트 파일 파싱</option>
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>국어 등급</label>
                  <input type="number" min="1" max="9" value={newGradeKorean} onChange={e => setNewGradeKorean(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>영어 등급</label>
                  <input type="number" min="1" max="9" value={newGradeEnglish} onChange={e => setNewGradeEnglish(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>실기 점수</label>
                  <input type="number" min="0" max="100" value={newGradePractical} onChange={e => setNewGradePractical(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
              <button onClick={() => setGradeModalOpen(false)} style={{ background: '#f3eee4', border: '1px solid #e5dec9', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleCreateGradeRecord} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>저장</button>
            </div>
          </div>
        </div>
      )}

      {/* ── v5.0 신규 모달 2: 서류 추가 모달 ── */}
      {docModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#ffffff', border: '1px solid #e5dec9', borderRadius: '12px', padding: '24px', maxWidth: '440px', width: '100%', boxShadow: '0 8px 24px rgba(0,0,0,0.15)' }}>
            <h3 style={{ margin: '0 0 14px 0', fontSize: '16px', color: '#d92632' }}>📁 새 서류 등록 (v5.0)</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>서류 명칭</label>
                <input type="text" placeholder="예: 서울대 디자인과 포트폴리오 설명서" value={newDocLabel} onChange={e => setNewDocLabel(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: '#646d78', display: 'block', marginBottom: '2px' }}>문서 종류</label>
                <select value={newDocType} onChange={e => setNewDocType(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e5dec9', borderRadius: '6px' }}>
                  <option value="자기소개서">자기소개서</option>
                  <option value="포트폴리오설명">포트폴리오 설명서</option>
                  <option value="추천서">추천서</option>
                  <option value="활동보고서">미술활동보고서</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
              <button onClick={() => setDocModalOpen(false)} style={{ background: '#f3eee4', border: '1px solid #e5dec9', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleCreateDocument} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>서류함 보관</button>
            </div>
          </div>
        </div>
      )}

      {/* ── v5.0 신규 모달 3: 학원 전용 로그인 모달 ── */}
      {tenantLoginOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#ffffff', border: '2px solid #d92632', borderRadius: '12px', padding: '28px', maxWidth: '420px', width: '100%', boxShadow: '0 8px 24px rgba(0,0,0,0.18)' }}>
            <div style={{ textAlign: 'center', marginBottom: '18px' }}>
              <span style={{ fontSize: '36px' }}>{tenantProfile.logo_url}</span>
              <h3 style={{ margin: '6px 0 2px 0', fontSize: '18px', color: '#1c2024' }}>{tenantProfile.name} 전용 로그인</h3>
              <span style={{ fontSize: '12px', color: '#646d78' }}>app.artready.kr/t/{tenantProfile.slug}/login</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <input type="text" placeholder="원생/학부모 아이디" value={tenantLoginId} onChange={e => setTenantLoginId(e.target.value)} style={{ padding: '10px', border: '1px solid #e5dec9', borderRadius: '6px', fontSize: '13px' }} />
              <input type="password" placeholder="비밀번호" value={tenantLoginPw} onChange={e => setTenantLoginPw(e.target.value)} style={{ padding: '10px', border: '1px solid #e5dec9', borderRadius: '6px', fontSize: '13px' }} />
              <button
                onClick={() => {
                  showToast(`[${tenantProfile.name}] 소속으로 안전하게 로그인되었습니다.`);
                  setTenantLoginOpen(false);
                }}
                style={{ background: '#d92632', color: '#fff', border: 'none', padding: '11px', borderRadius: '6px', fontSize: '14px', fontWeight: 700, cursor: 'pointer', marginTop: '6px' }}
              >
                소속 학원 포털 로그인
              </button>
            </div>
            <div style={{ textAlign: 'center', marginTop: '14px' }}>
              <button onClick={() => setTenantLoginOpen(false)} style={{ background: 'transparent', border: 'none', color: '#646d78', fontSize: '12px', cursor: 'pointer' }}>닫기</button>
            </div>
          </div>
        </div>
      )}

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

      {/* ── 토스트 알림 컨테이너 (첨삭펜 마이크로 인터랙션) ── */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999, display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '380px' }}>
        {toasts.map((t: ToastItem) => (
          <div
            key={t.id}
            style={{
              background: '#ffffff',
              border: '1px solid #e5dec9',
              borderLeft: `4px solid ${t.type === 'error' ? '#ef4444' : t.type === 'info' ? '#3b82f6' : '#d92632'}`,
              borderRadius: '8px',
              padding: '12px 16px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              color: '#1c2024'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: t.type === 'error' ? '#ef4444' : t.type === 'info' ? '#3b82f6' : '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>
                {t.type === 'error' ? '⚠️ ERROR' : t.type === 'info' ? 'ℹ️ NOTICE' : '✅ VERIFIED'}
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
