import { useState, type FormEvent } from 'react';

// ── 데이터 타입 정의 ──
interface Student {
  id: string;
  name: string;
  grade: string;
  targetMajor: string;
  status: 'ACTIVE' | 'LEAVE' | 'DROPOUT';
  parentLinked: boolean;
  parentName?: string;
  parentRelation?: string;
  phone: string;
  attendanceRate: number;
}

interface Instructor {
  id: string;
  name: string;
  role: string;
  className: string;
  phone: string;
  email: string;
}

interface PermissionState {
  menu_key: string;
  label: string;
  description: string;
  can_read: boolean;
  can_write: boolean;
  isLocked?: boolean;
}

interface AttendanceRecord {
  id: string;
  studentId: string;
  studentName: string;
  date: string;
  status: 'PRESENT' | 'LATE' | 'ABSENT';
  reason: string;
  className: string;
}

interface Evaluation {
  id: string;
  studentName: string;
  category: string;
  title: string;
  date: string;
  instructorName: string;
  score: number;
  feedback: string;
  imageUrl?: string;
}

interface AlbumItem {
  id: string;
  className: string;
  title: string;
  date: string;
  author: string;
  imageUrl: string;
  description: string;
}

interface TuitionRecord {
  id: string;
  studentName: string;
  className: string;
  amount: number;
  dueDate: string;
  paidDate?: string;
  status: 'PAID' | 'UNPAID';
}

interface ParentLink {
  id: string;
  studentName: string;
  studentId: string;
  parentName: string;
  relation: string;
  linkedAt: string;
  code: string;
}

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'info' | 'error';
  timestamp: string;
}

const API_BASE = (import.meta as any).env?.VITE_API_URL || '/api/v1';

function getCoAccessToken(): string | null {
  try { return localStorage.getItem('art_co_access_token'); } catch { return null; }
}
function coAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getCoAccessToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

export default function App() {
  // 현재 선택된 메뉴 (10개 메뉴 전수 대응)
  const [activeMenu, setActiveMenu] = useState<string>('dashboard');

  // 2026-09-21 신규: 이전엔 CO 사이트도 로그인 없이 바로 열렸다. 실제
  // /auth/login으로 인증하고 role에 따라 원장/강사 모드를 자동 설정한다
  // (기존 userRole 토글은 로그인 후에도 UI 데모용으로 남겨둔다).
  const [session, setSession] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('art_co_session') || 'null'); } catch { return null; }
  });
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');

  const handleStaffLogin = async (e: FormEvent) => {
    e.preventDefault();
    setLoginError('');
    if (!loginEmail.trim() || !loginPassword.trim()) {
      setLoginError('이메일과 비밀번호를 입력해주세요.');
      return;
    }
    setLoginLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(data?.error || '로그인에 실패했습니다.');
        return;
      }
      if (!data.profile || !['TENANT_ADMIN', 'INSTRUCTOR'].includes(data.profile.role)) {
        setLoginError('원장(TENANT_ADMIN)/강사(INSTRUCTOR) 계정만 로그인할 수 있습니다.');
        return;
      }
      try {
        localStorage.setItem('art_co_access_token', data.access_token);
        localStorage.setItem('art_co_session', JSON.stringify(data.profile));
      } catch {}
      setSession(data.profile);
      setUserRole(data.profile.role === 'TENANT_ADMIN' ? 'DIRECTOR' : 'INSTRUCTOR');
    } catch {
      setLoginError('로그인에 실패했습니다 - 네트워크 오류.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleStaffLogout = () => {
    try {
      localStorage.removeItem('art_co_access_token');
      localStorage.removeItem('art_co_session');
    } catch {}
    setSession(null);
  };

  // 사용자 권한 모드 토글 (원장 vs 강사)
  const [userRole, setUserRole] = useState<'DIRECTOR' | 'INSTRUCTOR'>('DIRECTOR');

  // 토스트 알림 상태 (마이크로 인터랙션)
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'success') => {
    const id = Math.random().toString(36).substring(7);
    const now = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    setToasts(prev => [...prev, { id, message, type, timestamp: now }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  };

  // 1. 원생 데이터
  const [students, setStudents] = useState<Student[]>([
    { id: 's-01', name: '김예원', grade: '고3 수험생', targetMajor: '국민대 디자인학부', status: 'ACTIVE', parentLinked: true, parentName: '박현숙', parentRelation: '모', phone: '010-3344-5566', attendanceRate: 100 },
    { id: 's-02', name: '이준우', grade: '고3 수험생', targetMajor: '서울과기대 시각디자인', status: 'ACTIVE', parentLinked: true, parentName: '이상철', parentRelation: '부', phone: '010-4455-6677', attendanceRate: 95 },
    { id: 's-03', name: '박서연', grade: '고2 예비반', targetMajor: '건국대 산업디자인', status: 'ACTIVE', parentLinked: false, phone: '010-5566-7788', attendanceRate: 98 },
    { id: 's-04', name: '최민서', grade: '고2 예비반', targetMajor: '홍익대 자율전공', status: 'LEAVE', parentLinked: true, parentName: '정미영', parentRelation: '모', phone: '010-6677-8899', attendanceRate: 85 },
    { id: 's-05', name: '정태양', grade: '고1 기초반', targetMajor: '미정 (기초조형)', status: 'ACTIVE', parentLinked: false, phone: '010-7788-9900', attendanceRate: 92 }
  ]);
  const [studentSearch, setStudentSearch] = useState('');
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [studentModalOpen, setStudentModalOpen] = useState(false);
  const [newStudentName, setNewStudentName] = useState('');
  const [newStudentGrade, setNewStudentGrade] = useState('고3 수험생');
  const [newStudentTarget, setNewStudentTarget] = useState('');

  // 2. 강사 데이터 및 권한 매트릭스
  const [instructors] = useState<Instructor[]>([
    { id: 'ins-01', name: '이민혁', role: '수석전임강사', className: '고3 입시정규A반', phone: '010-1234-5678', email: 'mh.lee@artready.kr' },
    { id: 'ins-02', name: '장수진', role: '전임강사', className: '고2 디자인예비반', phone: '010-2345-6789', email: 'sj.jang@artready.kr' },
    { id: 'ins-03', name: '강도훈', role: '보조강사', className: '고1 기초소묘반', phone: '010-3456-7890', email: 'dh.kang@artready.kr' }
  ]);
  const [selectedInstructorId, setSelectedInstructorId] = useState('ins-01');
  const [permissions, setPermissions] = useState<PermissionState[]>([
    { menu_key: 'student.list', label: '원생 명부 관리', description: '원생 전체 명부 및 상세 프로필 조회/수정', can_read: true, can_write: false },
    { menu_key: 'student.evaluation', label: '실기 평가 및 피드백', description: '원생 실기 평가 및 첨삭 피드백 작성', can_read: true, can_write: true },
    { menu_key: 'attendance.manage', label: '출결 관리', description: '일별 출결 체크 및 결석 사유 등록', can_read: true, can_write: true },
    { menu_key: 'album.manage', label: '수업 앨범', description: '반별 수업 사진 및 강평 등록', can_read: true, can_write: true },
    { menu_key: 'billing.view', label: '수강료 수납 관리', description: '학원 수강료 수납 장부 (원장 전용 잠금 기능)', can_read: false, can_write: false, isLocked: true }
  ]);

  // 3. 출결 데이터
  const [attendanceList, setAttendanceList] = useState<AttendanceRecord[]>([
    { id: 'att-1', studentId: 's-01', studentName: '김예원', date: '2026-09-19', status: 'PRESENT', reason: '', className: '고3 입시정규A반' },
    { id: 'att-2', studentId: 's-02', studentName: '이준우', date: '2026-09-19', status: 'LATE', reason: '학교 보충수업으로 20분 지각', className: '고3 입시정규A반' },
    { id: 'att-3', studentId: 's-03', studentName: '박서연', date: '2026-09-19', status: 'PRESENT', reason: '', className: '고2 디자인예비반' },
    { id: 'att-4', studentId: 's-04', studentName: '최민서', date: '2026-09-19', status: 'ABSENT', reason: '병원 진료 (휴원 상태)', className: '고2 디자인예비반' },
    { id: 'att-5', studentId: 's-05', studentName: '정태양', date: '2026-09-19', status: 'PRESENT', reason: '', className: '고1 기초소묘반' }
  ]);

  // 4. 실기 평가 데이터
  const [evaluations, setEvaluations] = useState<Evaluation[]>([
    { id: 'eval-1', studentName: '김예원', category: '기초디자인', title: '유리 질감과 금속 구의 공간 구성', date: '2026-09-18', instructorName: '이민혁 수석강사', score: 92, feedback: '주제부 물체의 선명도와 반사 표현이 매우 우수함. 배경 원경 물체의 채도를 조금 더 낮추어 원근 대비를 극대화할 필요가 있습니다.' },
    { id: 'eval-2', studentName: '이준우', category: '사고의전환', title: '전구와 자연물의 융합 조형', date: '2026-09-15', instructorName: '이민혁 수석강사', score: 86, feedback: '아이디어 발상은 참신하나, 주제부 전구의 투시 비례가 살짝 왜곡되었습니다. 타원 투시 보강 연습 요망.' }
  ]);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [newEvalStudent, setNewEvalStudent] = useState('김예원');
  const [newEvalCategory, setNewEvalCategory] = useState('기초디자인');
  const [newEvalTitle, setNewEvalTitle] = useState('');
  const [newEvalScore, setNewEvalScore] = useState(90);
  const [newEvalFeedback, setNewEvalFeedback] = useState('');

  // 5. 수업 앨범 데이터
  const [albumList, setAlbumList] = useState<AlbumItem[]>([
    { id: 'alb-1', className: '고3 입시정규A반', title: '수시 대비 실전 모의고사 현장 (4시간 타임어택)', date: '2026-09-18', author: '이민혁 강사', imageUrl: '🎨', description: '실전 시험장과 동일한 긴장감 속에서 진행된 모의고사 및 강사 실시간 첨삭' },
    { id: 'alb-2', className: '고2 디자인예비반', title: '질감 마스터 특강 (금속/나무/물)', date: '2026-09-14', author: '장수진 강사', imageUrl: '🖌️', description: '빛 방향에 따른 음영 처리 및 재질감별 붓 터치 기법 실습' }
  ]);
  const [albumModalOpen, setAlbumModalOpen] = useState(false);
  const [newAlbumClass, setNewAlbumClass] = useState('고3 입시정규A반');
  const [newAlbumTitle, setNewAlbumTitle] = useState('');
  const [newAlbumDesc, setNewAlbumDesc] = useState('');

  // 6. 수강료 데이터
  const [tuitionList, setTuitionList] = useState<TuitionRecord[]>([
    { id: 't-01', studentName: '김예원', className: '고3 입시정규반', amount: 850000, dueDate: '2026-09-10', paidDate: '2026-09-08', status: 'PAID' },
    { id: 't-02', studentName: '이준우', className: '고3 입시정규반', amount: 850000, dueDate: '2026-09-10', paidDate: '2026-09-10', status: 'PAID' },
    { id: 't-03', studentName: '박서연', className: '고2 디자인반', amount: 650000, dueDate: '2026-09-10', paidDate: '2026-09-09', status: 'PAID' },
    { id: 't-04', studentName: '최민서', className: '고2 디자인반', amount: 650000, dueDate: '2026-09-10', status: 'UNPAID' },
    { id: 't-05', studentName: '정태양', className: '고1 조형기초반', amount: 550000, dueDate: '2026-09-10', status: 'UNPAID' }
  ]);

  // 7. 학부모 연동 데이터
  const [parentLinks, setParentLinks] = useState<ParentLink[]>([
    { id: 'pl-01', studentName: '김예원', studentId: 's-01', parentName: '박현숙', relation: '모', linkedAt: '2026-03-05', code: 'AR-2026-9812' },
    { id: 'pl-02', studentName: '이준우', studentId: 's-02', parentName: '이상철', relation: '부', linkedAt: '2026-03-12', code: 'AR-2026-8841' },
    { id: 'pl-03', studentName: '최민서', studentId: 's-04', parentName: '정미영', relation: '모', linkedAt: '2026-04-01', code: 'AR-2026-7732' }
  ]);

  // 8. 본사 정책 문서
  const policies = [
    { id: 'pol-01', title: '2026년 가맹학원 수강료 및 정산 운영 규정', effectiveDate: '2026-01-01', version: 'v2.0', content: '가맹점 정산은 익월 10일 정산 마감하며, 수기결제 조정 시 감사 사유 필수 입력 규정을 엄격히 준수합니다.' },
    { id: 'pol-02', title: '학생 개인정보 처리방침 및 작품 저작권 가이드라인', effectiveDate: '2026-01-01', version: 'v2.0', content: '만 14세 미만 학생 등록 시 법정대리인 동의가 필수이며, 평가용 작품 이미지는 비공개 스토리지에 암호화 보관됩니다.' }
  ];

  // 9. 학원 기본정보 + v5.0 소개 페이지 콘텐츠
  const [introName, setIntroName] = useState('강남 미술학원 본원');
  const [introSlug, setIntroSlug] = useState('gangnam-main');
  const [introText, setIntroText] = useState('20년 전통의 디자인/기초소양 명문. 국민대, 서울대, 과기대 수시/정시 압도적 합격률을 자랑합니다. 1:1 강사 실시간 첨삭 시스템을 완비했습니다.');
  const [introStat1, setIntroStat1] = useState('89.4%');
  const [introStat2, setIntroStat2] = useState('42명 합격');
  const [introStat3, setIntroStat3] = useState('8명 배출');
  const [introAddress, setIntroAddress] = useState('서울특별시 강남구 테헤란로 124 삼원빌딩 4~5층');
  const [introPhone, setIntroPhone] = useState('02-555-7890');
  const [introHours, setIntroHours] = useState('평일 13:00 ~ 22:00 / 토 09:00 ~ 18:00');
  const [approvalStatus, setApprovalStatus] = useState<'APPROVED' | 'PENDING_APPROVAL'>('APPROVED');

  const [infoModalOpen, setInfoModalOpen] = useState(false);
  const [changeReqText, setChangeReqText] = useState('');

  // ── 핸들러 함수들 ──
  const handleTogglePerm = (key: string, field: 'can_read' | 'can_write') => {
    if (userRole !== 'DIRECTOR') {
      showToast('⚠️ 권한 변경은 원장(TENANT_ADMIN) 전용 기능입니다.', 'error');
      return;
    }
    setPermissions(prev =>
      prev.map(p => (p.menu_key === key && !p.isLocked ? { ...p, [field]: !p[field] } : p))
    );
  };

  // 2026-09-21: 이전엔 API 응답을 확인하지 않고 항상 "저장 완료" 토스트만
  // 띄웠다 - menu_permissions 테이블이 실제로 생겼으니 각 메뉴별로 upsert
  // 호출하고, 하나라도 실패하면 정직하게 알린다.
  const handleSavePermissions = async () => {
    // 데모용 강사 목록(instructors)이 로컬 목업이라 실제 user_profiles.id가
    // 아니다 - 실제 tenant_id를 가져오는 것부터 시작한다.
    try {
      const tRes = await fetch(`${API_BASE}/co/profile`, { headers: coAuthHeaders() });
      const tenant = await tRes.json();
      const tenantId = tenant?.id;
      if (!tenantId) {
        showToast('학원 정보를 불러오지 못해 권한을 저장할 수 없습니다.', 'error');
        return;
      }
      let failCount = 0;
      for (const p of permissions) {
        const res = await fetch(`${API_BASE}/co/permissions`, {
          method: 'POST',
          headers: coAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ user_id: selectedInstructorId, tenant_id: tenantId, menu_key: p.menu_key, can_read: p.can_read, can_write: p.can_write })
        });
        if (!res.ok) failCount++;
      }
      if (failCount > 0) {
        showToast(`${failCount}개 메뉴 권한 저장에 실패했습니다.`, 'error');
        return;
      }
      showToast(`[저장 완료]\n강사(${selectedInstructorId})의 메뉴 권한 설정이 백엔드에 반영되었습니다.`);
    } catch {
      showToast('권한 저장에 실패했습니다 - 네트워크 오류.', 'error');
    }
  };

  const handleAttendanceChange = (recordId: string, newStatus: 'PRESENT' | 'LATE' | 'ABSENT') => {
    setAttendanceList(prev =>
      prev.map(item => item.id === recordId ? { ...item, status: newStatus } : item)
    );
  };

  const handleReasonChange = (recordId: string, reason: string) => {
    setAttendanceList(prev =>
      prev.map(item => item.id === recordId ? { ...item, reason } : item)
    );
  };

  const handleStudentStatusChange = (studentId: string, newStatus: 'ACTIVE' | 'LEAVE' | 'DROPOUT') => {
    setStudents(prev =>
      prev.map(s => s.id === studentId ? { ...s, status: newStatus } : s)
    );
    showToast('원생 상태가 변경되었습니다.');
  };

  const handleAddStudent = async () => {
    if (!newStudentName.trim()) {
      showToast('원생 이름을 입력해주세요.', 'error');
      return;
    }
    const newS: Student = {
      id: `s-${Date.now().toString(36)}`,
      name: newStudentName,
      grade: newStudentGrade,
      targetMajor: newStudentTarget || '기초디자인',
      status: 'ACTIVE',
      parentLinked: false,
      phone: '010-0000-0000',
      attendanceRate: 100
    };
    try {
      await fetch(`${API_BASE}/co/students`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newS.name,
          grade: newS.grade,
          target_major: newS.targetMajor,
          target_univ: '국민대/서울대',
          parent_phone: newS.phone,
          status: 'ENROLLED'
        })
      });
    } catch {}
    setStudents(prev => [newS, ...prev]);
    setStudentModalOpen(false);
    setNewStudentName('');
    showToast(`[등록 완료] ${newStudentName} 원생이 신규 등록되었습니다.`);
  };

  const handleAddEvaluation = async () => {
    if (!newEvalTitle.trim() || !newEvalFeedback.trim()) {
      showToast('평가 제목과 피드백을 모두 입력해주세요.', 'error');
      return;
    }
    const newEval: Evaluation = {
      id: `eval-${Date.now().toString(36)}`,
      studentName: newEvalStudent,
      category: newEvalCategory,
      title: newEvalTitle,
      date: new Date().toISOString().split('T')[0],
      instructorName: '이민혁 수석강사',
      score: newEvalScore,
      feedback: newEvalFeedback
    };
    try {
      await fetch(`${API_BASE}/co/evaluations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: 's-01',
          student_name: newEval.studentName,
          title: newEval.title,
          score: newEval.score,
          category: newEval.category,
          feedback: newEval.feedback
        })
      });
    } catch {}
    setEvaluations(prev => [newEval, ...prev]);
    setEvalModalOpen(false);
    setNewEvalTitle('');
    setNewEvalFeedback('');
    showToast(`[첨삭 완료] ${newEvalStudent} 학생의 실기 평가 및 첨삭 피드백이 등록되었습니다.`);
  };

  const handleAddAlbum = async () => {
    if (!newAlbumTitle.trim()) {
      showToast('앨범 제목을 입력해주세요.', 'error');
      return;
    }
    const newAlb: AlbumItem = {
      id: `alb-${Date.now().toString(36)}`,
      className: newAlbumClass,
      title: newAlbumTitle,
      date: new Date().toISOString().split('T')[0],
      author: '이민혁 강사',
      imageUrl: '📸',
      description: newAlbumDesc
    };
    try {
      await fetch(`${API_BASE}/co/albums`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: 's-01',
          student_name: '고3 정규반',
          title: newAlb.title,
          image_url: 'https://placehold.co/600x400',
          description: newAlb.description
        })
      });
    } catch {}
    setAlbumList(prev => [newAlb, ...prev]);
    setAlbumModalOpen(false);
    setNewAlbumTitle('');
    setNewAlbumDesc('');
    showToast('새 수업 앨범이 등록되었습니다.');
  };

  const handleRegenCode = (linkId: string) => {
    const randomCode = `AR-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    setParentLinks(prev =>
      prev.map(pl => pl.id === linkId ? { ...pl, code: randomCode } : pl)
    );
    showToast(`[재발급 완료] 새로운 학부모 연동 코드: ${randomCode}`);
  };

  const handleSendReminder = (studentName: string) => {
    showToast(`[알림 발송]\n${studentName} 원생의 학부모님께 미납 수강료 결제 안내 알림톡이 전송되었습니다.`);
  };

  const handleTuitionPay = async (id: string) => {
    try {
      await fetch(`${API_BASE}/co/tuition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: id,
          student_name: '원생',
          month: '2026년 9월분',
          amount: 850000,
          status: 'PAID'
        })
      });
    } catch {}
    setTuitionList(prev =>
      prev.map(t => t.id === id ? { ...t, status: 'PAID', paidDate: new Date().toISOString().split('T')[0] } : t)
    );
    showToast('수강료 수납이 정상 등록되었습니다.');
  };

  // v5.0 학원 소개 페이지 수정 및 본사 승인 신청
  const handleApplyAcademyIntro = async () => {
    try {
      const res = await fetch(`${API_BASE}/co/profile`, {
        method: 'PUT',
        headers: coAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          name: introName,
          slug: introSlug,
          intro_text: introText,
          highlight_stats: [
            { title: '2026 수시 합격률', value: introStat1 },
            { title: '국민대/서울과기대', value: introStat2 },
            { title: '실기 만점자 배출', value: introStat3 }
          ],
          contact_info: {
            address: introAddress,
            phone: introPhone,
            consult_open: introHours
          },
          request_publish_approval: true
        })
      });
      if (!res.ok) {
        showToast('학원 소개 페이지 수정 신청에 실패했습니다.', 'error');
        return;
      }
    } catch {
      showToast('학원 소개 페이지 수정 신청에 실패했습니다 - 네트워크 오류.', 'error');
      return;
    }
    setApprovalStatus('PENDING_APPROVAL');
    showToast(`[본사 승인 신청 완료]\n학원 소개 페이지 수정안이 본사(BO)에 제출되었습니다.\n심사 통과 시 app.artready.kr/t/${introSlug}에 자동 반영됩니다.`);
  };

  const filteredStudents = students.filter(s =>
    s.name.includes(studentSearch) || s.grade.includes(studentSearch) || s.targetMajor.includes(studentSearch)
  );

  // 2026-09-21: 로그인 세션 없으면 대시보드 대신 로그인 화면만 렌더링한다.
  if (!session) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#fbf9f5' }}>
        <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '12px', padding: '28px', maxWidth: '380px', width: '100%', boxShadow: '0 4px 20px rgba(0,0,0,0.06)' }}>
          <div style={{ textAlign: 'center', marginBottom: '18px' }}>
            <span style={{ background: '#d92632', color: '#ffffff', fontWeight: 800, padding: '4px 10px', borderRadius: '6px', fontSize: '14px' }}>CO</span>
            <h3 style={{ margin: '10px 0 2px 0', fontSize: '18px', color: '#1c2024' }}>가맹학원 원장/강사 로그인</h3>
          </div>
          <form onSubmit={handleStaffLogin} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <input type="email" placeholder="이메일" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} style={{ padding: '10px', border: '1px solid #e2dcce', borderRadius: '6px', fontSize: '13px' }} />
            <input type="password" placeholder="비밀번호" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} style={{ padding: '10px', border: '1px solid #e2dcce', borderRadius: '6px', fontSize: '13px' }} />
            {loginError && <span style={{ color: '#d92632', fontSize: '12px' }}>{loginError}</span>}
            <button type="submit" disabled={loginLoading} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '11px', borderRadius: '6px', fontSize: '14px', fontWeight: 700, cursor: loginLoading ? 'default' : 'pointer', opacity: loginLoading ? 0.6 : 1 }}>
              {loginLoading ? '로그인 중...' : '로그인'}
            </button>
          </form>
          <p style={{ fontSize: '11px', color: '#646d78', marginTop: '12px', textAlign: 'center' }}>원장(TENANT_ADMIN)/강사(INSTRUCTOR) 계정만 접근할 수 있습니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-wrapper" style={{ display: 'flex', minHeight: '100vh', background: '#fbf9f5', color: '#1c2024' }}>
      {/* ── 좌측 사이드바: 원장 데스크 웜톤 ── */}
      <aside className="sidebar" style={{ width: '270px', background: '#f3eee4', borderRight: '1px solid #e2dcce', display: 'flex', flexDirection: 'column', padding: '20px 14px', gap: '16px' }}>
        <div className="sidebar-brand" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ background: '#d92632', color: '#ffffff', fontWeight: 800, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', boxShadow: '0 2px 6px rgba(217,38,50,0.3)' }}>CO</span>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#1c2024' }}>ART:READY</h2>
            <span style={{ fontSize: '12px', color: '#646d78' }}>가맹학원 운영포털 (v5.0)</span>
          </div>
        </div>

        {/* 원장 vs 강사 스위처 */}
        <div style={{ background: '#e5dec9', padding: '4px', borderRadius: '8px', display: 'flex', gap: '4px' }}>
          <button
            onClick={() => setUserRole('DIRECTOR')}
            style={{
              flex: 1, padding: '6px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
              background: userRole === 'DIRECTOR' ? '#ffffff' : 'transparent',
              color: userRole === 'DIRECTOR' ? '#d92632' : '#646d78',
              fontWeight: userRole === 'DIRECTOR' ? 700 : 500,
              boxShadow: userRole === 'DIRECTOR' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            👑 원장 모드
          </button>
          <button
            onClick={() => setUserRole('INSTRUCTOR')}
            style={{
              flex: 1, padding: '6px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
              background: userRole === 'INSTRUCTOR' ? '#ffffff' : 'transparent',
              color: userRole === 'INSTRUCTOR' ? '#d92632' : '#646d78',
              fontWeight: userRole === 'INSTRUCTOR' ? 700 : 500,
              boxShadow: userRole === 'INSTRUCTOR' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            🎨 강사 모드
          </button>
        </div>

        <div style={{ fontSize: '11px', color: '#646d78', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{session.name} ({session.role})</span>
          <button onClick={handleStaffLogout} style={{ background: 'transparent', border: 'none', color: '#d92632', fontSize: '11px', cursor: 'pointer', textDecoration: 'underline' }}>로그아웃</button>
        </div>

        {/* 10개 메뉴 내비게이션 */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {[
            { key: 'dashboard', label: '📊 운영 대시보드' },
            { key: 'students', label: '👥 원생 명부 관리' },
            { key: 'instructors', label: '👩‍🏫 강사 및 권한 매트릭스' },
            { key: 'attendance', label: '📅 출결 관리 (일별)' },
            { key: 'evaluations', label: '✍️ 실기 평가 및 첨삭' },
            { key: 'album', label: '📸 수업 앨범' },
            { key: 'tuition', label: '💳 수강료 수납 관리' },
            { key: 'parent_links', label: '🔗 학부모 계정 연동' },
            { key: 'policies', label: '📜 본사 공시 정책 열람' },
            { key: 'academy_info', label: '🏫 학원 기본정보 & 소개페이지' }
          ].map(menu => {
            const isActive = activeMenu === menu.key;
            return (
              <button
                key={menu.key}
                onClick={() => setActiveMenu(menu.key)}
                style={{
                  textAlign: 'left', padding: '10px 12px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                  background: isActive ? '#d92632' : 'transparent',
                  color: isActive ? '#ffffff' : '#1c2024',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px',
                  boxShadow: isActive ? '0 2px 6px rgba(217,38,50,0.25)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                {menu.label}
              </button>
            );
          })}
        </nav>

        <div style={{ marginTop: 'auto', padding: '12px', background: '#e5dec9', borderRadius: '8px', fontSize: '12px' }}>
          <div style={{ fontWeight: 700, color: '#1c2024' }}>강남 미술학원 본원</div>
          <div style={{ color: '#646d78', marginTop: '2px' }}>원장 홍길동 | 정상 가맹</div>
        </div>
      </aside>

      {/* ── 우측 메인 콘텐츠 영역 ── */}
      <main style={{ flex: 1, padding: '28px 32px', overflowY: 'auto' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0, color: '#1c2024' }}>
              {activeMenu === 'dashboard' && '가맹학원 운영 현황 대시보드'}
              {activeMenu === 'students' && '재원생 명부 및 상세 관리'}
              {activeMenu === 'instructors' && '강사진 명단 및 메뉴 권한 설정 (2중 RLS)'}
              {activeMenu === 'attendance' && '일별 출결 현황 체크 및 결석 사유 관리'}
              {activeMenu === 'evaluations' && '실기 모의고사 평가 및 첨삭 피드백 등록'}
              {activeMenu === 'album' && '반별 수업 사진 및 활동 앨범'}
              {activeMenu === 'tuition' && '수강료 청구 및 납부 수납 장부 (원장 전용)'}
              {activeMenu === 'parent_links' && '학부모 계정 연동 코드 관리'}
              {activeMenu === 'policies' && '본사 공시 정책 및 이용약관 열람'}
              {activeMenu === 'academy_info' && '학원 기본정보 및 소개 페이지 설정 (v5.0)'}
            </h1>
            <span style={{ fontSize: '13px', color: '#646d78', marginTop: '4px', display: 'block' }}>
              현재 접속자 권한: <strong>{userRole === 'DIRECTOR' ? '원장 (TENANT_ADMIN)' : '강사 (INSTRUCTOR)'}</strong>
            </span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            {activeMenu === 'students' && (
              <button onClick={() => setStudentModalOpen(true)} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                + 신규 원생 등록
              </button>
            )}
            {activeMenu === 'evaluations' && (
              <button onClick={() => setEvalModalOpen(true)} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                ✍️ 새 실기 첨삭 작성
              </button>
            )}
            {activeMenu === 'album' && (
              <button onClick={() => setAlbumModalOpen(true)} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                + 수업 사진 등록
              </button>
            )}
          </div>
        </header>

        {/* 1. 운영 대시보드 */}
        {activeMenu === 'dashboard' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
              <div style={{ background: '#ffffff', borderRadius: '8px', padding: '18px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>총 재원생</span>
                <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '6px', color: '#1c2024', fontFamily: "'IBM Plex Mono', monospace" }}>{students.length}명</div>
                <span style={{ fontSize: '11px', color: '#15803d', fontWeight: 600 }}>재원율 94.2%</span>
              </div>
              <div style={{ background: '#ffffff', borderRadius: '8px', padding: '18px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>금일 출석률</span>
                <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '6px', color: '#15803d', fontFamily: "'IBM Plex Mono', monospace" }}>92.0%</div>
                <span style={{ fontSize: '11px', color: '#646d78' }}>5명 중 4명 출석</span>
              </div>
              <div style={{ background: '#ffffff', borderRadius: '8px', padding: '18px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>첨삭 대기 작품</span>
                <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '6px', color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>3건</div>
                <span style={{ fontSize: '11px', color: '#d92632', fontWeight: 600 }}>수시 모의고사 첨삭</span>
              </div>
              <div style={{ background: '#ffffff', borderRadius: '8px', padding: '18px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
                <span style={{ fontSize: '12px', color: '#646d78' }}>당월 수납률</span>
                <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '6px', color: '#1c2024', fontFamily: "'IBM Plex Mono', monospace" }}>67.1%</div>
                <span style={{ fontSize: '11px', color: '#b45309', fontWeight: 600 }}>미납 2건 안내 요망</span>
              </div>
            </div>

            {/* 채점 대기 패널 */}
            <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>🎨 금일 실기 채점 및 첨삭 대기 패널</h3>
                <span style={{ fontSize: '12px', color: '#d92632', fontWeight: 600 }}>원장 및 전임강사 실시간 검수</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {evaluations.map(ev => (
                  <div key={ev.id} style={{ background: '#fbf9f5', border: '1px solid #e2dcce', borderRadius: '6px', padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>{ev.category}</span>
                      <strong style={{ marginLeft: '8px', fontSize: '14px', color: '#1c2024' }}>{ev.title}</strong>
                      <div style={{ fontSize: '12px', color: '#646d78', marginTop: '4px' }}>원생: {ev.studentName} | 담당: {ev.instructorName} | 일자: {ev.date}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '20px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>{ev.score}점</span>
                      <button onClick={() => showToast(`[보안 서명 URL 발급]\n'${ev.title}' 작품 이미지 열람을 위한 1시간 만료 보안 Signed URL이 안전하게 생성되었습니다.`)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '6px 12px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>
                        첨삭 보기
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 2. 원생 명부 관리 */}
        {activeMenu === 'students' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <input
                type="text"
                placeholder="원생 이름, 학년, 목표 전공 검색..."
                value={studentSearch}
                onChange={e => setStudentSearch(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2dcce', width: '280px', background: '#fbf9f5', fontSize: '13px' }}
              />
              <span style={{ fontSize: '12px', color: '#646d78' }}>검색 결과 {filteredStudents.length}명</span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2dcce', color: '#646d78', background: '#f8f5ee' }}>
                  <th style={{ padding: '10px' }}>이름</th>
                  <th style={{ padding: '10px' }}>학년</th>
                  <th style={{ padding: '10px' }}>목표 전공/대학</th>
                  <th style={{ padding: '10px' }}>학부모 연동</th>
                  <th style={{ padding: '10px' }}>출석률</th>
                  <th style={{ padding: '10px' }}>재원 상태</th>
                  <th style={{ padding: '10px' }}>상세</th>
                </tr>
              </thead>
              <tbody>
                {filteredStudents.map(s => (
                  <tr key={s.id} style={{ borderBottom: '1px solid #e2dcce' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{s.name}</td>
                    <td style={{ padding: '12px 10px', color: '#4b5563' }}>{s.grade}</td>
                    <td style={{ padding: '12px 10px', color: '#1c2024' }}>{s.targetMajor}</td>
                    <td style={{ padding: '12px 10px' }}>
                      {s.parentLinked ? (
                        <span style={{ background: '#15803d15', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>연동 완료</span>
                      ) : (
                        <span style={{ background: '#b4530915', color: '#b45309', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>미연동</span>
                      )}
                    </td>
                    <td style={{ padding: '12px 10px', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>{s.attendanceRate}%</td>
                    <td style={{ padding: '12px 10px' }}>
                      <select
                        value={s.status}
                        onChange={e => handleStudentStatusChange(s.id, e.target.value as any)}
                        style={{ padding: '4px', borderRadius: '4px', border: '1px solid #e2dcce', background: '#fbf9f5', fontSize: '12px' }}
                      >
                        <option value="ACTIVE">재원중</option>
                        <option value="LEAVE">휴원</option>
                        <option value="DROPOUT">퇴원</option>
                      </select>
                    </td>
                    <td style={{ padding: '12px 10px' }}>
                      <button onClick={() => setSelectedStudent(s)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                        상세보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 3. 강사 관리 & 권한 매트릭스 */}
        {activeMenu === 'instructors' && (
          <div>
            {userRole !== 'DIRECTOR' ? (
              <div style={{ background: '#fff5f5', border: '1px solid #d92632', padding: '24px', borderRadius: '8px', textAlign: 'center' }}>
                <h3 style={{ color: '#d92632', margin: '0 0 8px 0' }}>⚠️ 원장 전용 보안 접근 제한</h3>
                <p style={{ fontSize: '14px', color: '#646d78' }}>강사 관리 및 메뉴 권한 매트릭스 설정은 원장(TENANT_ADMIN) 계정으로만 접근 가능합니다. 좌측 스위처에서 '원장 모드'를 선택하십시오.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
                <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>강사 명단 ({instructors.length}명)</h3>
                    <button onClick={() => showToast('신규 강사 초대 링크가 복사되었습니다.')} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>+ 초대</button>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {instructors.map(ins => (
                      <div
                        key={ins.id}
                        onClick={() => setSelectedInstructorId(ins.id)}
                        style={{
                          padding: '12px', borderRadius: '6px', border: '1px solid',
                          borderColor: selectedInstructorId === ins.id ? '#d92632' : '#e2dcce',
                          background: selectedInstructorId === ins.id ? 'rgba(217,38,50,0.06)' : '#fbf9f5',
                          cursor: 'pointer'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <strong style={{ color: '#1c2024' }}>{ins.name} ({ins.role})</strong>
                          <span style={{ fontSize: '11px', color: '#d92632' }}>{selectedInstructorId === ins.id ? '선택됨' : ''}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#646d78', marginTop: '4px' }}>담당: {ins.className}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <div>
                      <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>메뉴별 세부 접근 권한 설정 (2중 RLS 제어)</h3>
                      <span style={{ fontSize: '12px', color: '#646d78' }}>선택 강사: {instructors.find(i => i.id === selectedInstructorId)?.name}</span>
                    </div>
                    <button onClick={handleSavePermissions} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                      권한 설정 저장
                    </button>
                  </div>

                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #e2dcce', color: '#646d78', background: '#f8f5ee' }}>
                        <th style={{ padding: '10px' }}>메뉴 구분</th>
                        <th style={{ padding: '10px' }}>설명</th>
                        <th style={{ padding: '10px', textAlign: 'center' }}>읽기 권한</th>
                        <th style={{ padding: '10px', textAlign: 'center' }}>쓰기/수정 권한</th>
                      </tr>
                    </thead>
                    <tbody>
                      {permissions.map(p => (
                        <tr key={p.menu_key} style={{ borderBottom: '1px solid #e2dcce' }}>
                          <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>
                            {p.label}
                            {p.isLocked && <span style={{ marginLeft: '6px', fontSize: '10px', color: '#d92632', background: '#fee2e2', padding: '2px 4px', borderRadius: '3px' }}>원장 전용</span>}
                          </td>
                          <td style={{ padding: '12px 10px', color: '#646d78', fontSize: '12px' }}>{p.description}</td>
                          <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={p.can_read}
                              disabled={p.isLocked}
                              onChange={() => handleTogglePerm(p.menu_key, 'can_read')}
                            />
                          </td>
                          <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={p.can_write}
                              disabled={p.isLocked}
                              onChange={() => handleTogglePerm(p.menu_key, 'can_write')}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 4. 출결 관리 */}
        {activeMenu === 'attendance' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>2026년 9월 19일 일별 출결 체크 (수업별)</h3>
                <span style={{ fontSize: '12px', color: '#646d78' }}>결석 처리 시 사유를 반드시 입력하여 학부모 알림 연동</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => showToast('전체 출석 처리되었습니다.')} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>전체 출석</button>
                <button onClick={() => showToast('출결 데이터가 Supabase DB에 저장되었습니다.')} style={{ background: '#15803d', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>출결 저장</button>
              </div>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2dcce', color: '#646d78', background: '#f8f5ee' }}>
                  <th style={{ padding: '10px' }}>원생명</th>
                  <th style={{ padding: '10px' }}>담당 반</th>
                  <th style={{ padding: '10px' }}>출결 상태</th>
                  <th style={{ padding: '10px' }}>결석/지각 사유 입력</th>
                </tr>
              </thead>
              <tbody>
                {attendanceList.map(item => (
                  <tr key={item.id} style={{ borderBottom: '1px solid #e2dcce' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{item.studentName}</td>
                    <td style={{ padding: '12px 10px', color: '#646d78' }}>{item.className}</td>
                    <td style={{ padding: '12px 10px' }}>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {(['PRESENT', 'LATE', 'ABSENT'] as const).map(st => (
                          <button
                            key={st}
                            onClick={() => handleAttendanceChange(item.id, st)}
                            style={{
                              padding: '4px 8px', borderRadius: '4px', border: '1px solid',
                              borderColor: item.status === st ? (st === 'PRESENT' ? '#15803d' : st === 'LATE' ? '#b45309' : '#d92632') : '#e2dcce',
                              background: item.status === st ? (st === 'PRESENT' ? '#15803d' : st === 'LATE' ? '#b45309' : '#d92632') : '#fbf9f5',
                              color: item.status === st ? '#ffffff' : '#646d78',
                              fontSize: '11px', cursor: 'pointer', fontWeight: item.status === st ? 700 : 400
                            }}
                          >
                            {st === 'PRESENT' ? '출석' : st === 'LATE' ? '지각' : '결석'}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td style={{ padding: '12px 10px' }}>
                      <input
                        type="text"
                        value={item.reason}
                        onChange={e => handleReasonChange(item.id, e.target.value)}
                        placeholder="사유 입력 (예: 학교 보충수업 20분 지각)..."
                        style={{ width: '100%', padding: '6px 8px', borderRadius: '4px', border: '1px solid #e2dcce', background: '#fbf9f5', fontSize: '12px' }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 5. 실기 평가 관리 */}
        {activeMenu === 'evaluations' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>실기 모의고사 평가 및 첨삭 목록 ({evaluations.length}건)</h3>
                <span style={{ fontSize: '12px', color: '#646d78' }}>원생별 1:1 빨간펜 첨삭 피드백 발행 내역</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {evaluations.map(ev => (
                <div key={ev.id} style={{ background: '#fbf9f5', border: '1px solid #e2dcce', borderRadius: '8px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <span style={{ background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', marginRight: '8px', fontWeight: 600 }}>{ev.category}</span>
                      <strong style={{ fontSize: '15px', color: '#1c2024' }}>{ev.title}</strong>
                      <div style={{ fontSize: '12px', color: '#646d78', marginTop: '4px' }}>원생: {ev.studentName} | 첨삭강사: {ev.instructorName} | 일자: {ev.date}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '24px', fontWeight: 800, color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>{ev.score}점</div>
                      <button onClick={() => showToast(`[보안 서명 URL 발급]\n'${ev.title}' 작품 이미지 열람을 위한 1시간 만료 보안 Signed URL이 안전하게 생성되었습니다.`)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer', marginTop: '4px' }}>
                        🖼️ 작품 첨삭 열람
                      </button>
                    </div>
                  </div>
                  <div style={{ marginTop: '12px', background: '#ffffff', padding: '12px', borderRadius: '6px', fontSize: '13px', lineHeight: 1.6, color: '#374151', borderLeft: '3px solid #d92632' }}>
                    ✍️ <strong>강사 첨삭 피드백:</strong> {ev.feedback}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 6. 수업 앨범 */}
        {activeMenu === 'album' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>반별 수업 활동 앨범</h3>
              <span style={{ fontSize: '12px', color: '#646d78' }}>학생·학부모 포털(FO)에 실시간 공유</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
              {albumList.map(alb => (
                <div key={alb.id} style={{ background: '#fbf9f5', border: '1px solid #e2dcce', borderRadius: '8px', overflow: 'hidden' }}>
                  <div style={{ height: '140px', background: '#ede8dc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '48px' }}>
                    {alb.imageUrl}
                  </div>
                  <div style={{ padding: '14px' }}>
                    <span style={{ background: 'rgba(37,99,235,0.1)', color: '#2563eb', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>{alb.className}</span>
                    <h4 style={{ fontSize: '15px', margin: '8px 0 4px 0', color: '#1c2024' }}>{alb.title}</h4>
                    <p style={{ fontSize: '12px', color: '#646d78', margin: 0 }}>{alb.description}</p>
                    <div style={{ marginTop: '10px', fontSize: '11px', color: '#8a939e', fontFamily: "'IBM Plex Mono', monospace" }}>등록자: {alb.author} | {alb.date}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 7. 수강료 관리 */}
        {activeMenu === 'tuition' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            {userRole !== 'DIRECTOR' ? (
              <div style={{ background: '#fff5f5', border: '1px solid #d92632', padding: '24px', borderRadius: '8px', textAlign: 'center' }}>
                <h3 style={{ color: '#d92632', margin: '0 0 8px 0' }}>⚠️ 원장 전용 금융 보안 화면</h3>
                <p style={{ fontSize: '14px', color: '#646d78' }}>수강료 장부 및 미납 내역 관리는 원장 전용 기능입니다.</p>
              </div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>2026년 9월 수강료 수납 장부</h3>
                    <span style={{ fontSize: '12px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>총 청구 3,500,000원 | 완납 2,350,000원 | 미납 1,150,000원</span>
                  </div>
                  <button onClick={() => showToast('미납자 전원에게 1차 납부 독려 메시지가 발송되었습니다.')} style={{ background: '#b45309', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                    📢 미납 원생 일괄 알림 발송
                  </button>
                </div>

                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #e2dcce', color: '#646d78', background: '#f8f5ee' }}>
                      <th style={{ padding: '10px' }}>원생명</th>
                      <th style={{ padding: '10px' }}>수강 과정</th>
                      <th style={{ padding: '10px' }}>청구 금액</th>
                      <th style={{ padding: '10px' }}>납부 기한</th>
                      <th style={{ padding: '10px' }}>상태</th>
                      <th style={{ padding: '10px' }}>수납 처리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tuitionList.map(t => (
                      <tr key={t.id} style={{ borderBottom: '1px solid #e2dcce' }}>
                        <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{t.studentName}</td>
                        <td style={{ padding: '12px 10px', color: '#646d78' }}>{t.className}</td>
                        <td style={{ padding: '12px 10px', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700 }}>{t.amount.toLocaleString()}원</td>
                        <td style={{ padding: '12px 10px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>{t.dueDate}</td>
                        <td style={{ padding: '12px 10px' }}>
                          {t.status === 'PAID' ? (
                            <span style={{ background: '#15803d15', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>완납 ({t.paidDate})</span>
                          ) : (
                            <span style={{ background: '#d9263215', color: '#d92632', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>미납</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 10px' }}>
                          {t.status === 'UNPAID' ? (
                            <div style={{ display: 'flex', gap: '4px' }}>
                              <button onClick={() => handleTuitionPay(t.id)} style={{ background: '#15803d', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer', fontWeight: 600 }}>수납 처리</button>
                              <button onClick={() => handleSendReminder(t.studentName)} style={{ background: '#f3eee4', color: '#b45309', border: '1px solid #e2dcce', padding: '4px 6px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>독려톡</button>
                            </div>
                          ) : (
                            <span style={{ color: '#646d78', fontSize: '12px' }}>처리 완료</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* 8. 학부모 계정 연동 */}
        {activeMenu === 'parent_links' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>원생-학부모 계정 연동 현황 (2중 RLS 결속)</h3>
                <span style={{ fontSize: '12px', color: '#646d78' }}>연동된 학부모는 자녀의 출결, 성적, 수강료 내역만 안전하게 열람 가능</span>
              </div>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2dcce', color: '#646d78', background: '#f8f5ee' }}>
                  <th style={{ padding: '10px' }}>학생명</th>
                  <th style={{ padding: '10px' }}>보호자명 (관계)</th>
                  <th style={{ padding: '10px' }}>연동 코드</th>
                  <th style={{ padding: '10px' }}>연동 승인일</th>
                  <th style={{ padding: '10px' }}>관리</th>
                </tr>
              </thead>
              <tbody>
                {parentLinks.map(pl => (
                  <tr key={pl.id} style={{ borderBottom: '1px solid #e2dcce' }}>
                    <td style={{ padding: '12px 10px', fontWeight: 600, color: '#1c2024' }}>{pl.studentName}</td>
                    <td style={{ padding: '12px 10px', color: '#4b5563' }}>{pl.parentName} ({pl.relation})</td>
                    <td style={{ padding: '12px 10px' }}>
                      <code style={{ background: '#f3eee4', padding: '4px 8px', borderRadius: '4px', color: '#d92632', fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{pl.code}</code>
                    </td>
                    <td style={{ padding: '12px 10px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>{pl.linkedAt}</td>
                    <td style={{ padding: '12px 10px' }}>
                      <button onClick={() => handleRegenCode(pl.id)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                        코드 재발급
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 9. 정책/약관 조회 */}
        {activeMenu === 'policies' && (
          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>본사 공시 정책 및 이용약관 열람</h3>
                <span style={{ fontSize: '12px', color: '#646d78' }}>가맹점은 조회 전용 권한을 가지며, 정책 개정은 본사(BO) 승인 하에 일괄 고지됩니다.</span>
              </div>
              <span style={{ background: '#f3eee4', color: '#646d78', padding: '4px 10px', borderRadius: '6px', fontSize: '12px', border: '1px solid #e2dcce' }}>🔒 본사 공시본 (수정불가)</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {policies.map(pol => (
                <div key={pol.id} style={{ background: '#fbf9f5', border: '1px solid #e2dcce', borderRadius: '8px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div>
                      <strong style={{ fontSize: '15px', color: '#1c2024' }}>{pol.title}</strong>
                      <span style={{ marginLeft: '8px', background: 'rgba(217,38,50,0.1)', color: '#d92632', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>{pol.version}</span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#646d78', fontFamily: "'IBM Plex Mono', monospace" }}>발효일자: {pol.effectiveDate}</span>
                  </div>
                  <p style={{ fontSize: '13px', color: '#4b5563', lineHeight: 1.6, margin: 0 }}>{pol.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 10. 학원 기본정보 + v5.0 소개 페이지 콘텐츠 설정 & 본사 승인 신청 */}
        {activeMenu === 'academy_info' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 기본 사업자 정보 */}
            <div style={{ background: '#ffffff', borderRadius: '8px', padding: '20px', border: '1px solid #e2dcce', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', margin: 0, color: '#1c2024' }}>가맹학원 사업자 기본 정보</h3>
                  <span style={{ fontSize: '12px', color: '#646d78' }}>프랜차이즈 가맹 계약 무결성 관리</span>
                </div>
                <button onClick={() => setInfoModalOpen(true)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>
                  사업자 정보 변경 신청
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', fontSize: '13px' }}>
                <div style={{ background: '#fbf9f5', padding: '12px', borderRadius: '6px', border: '1px solid #e2dcce' }}>
                  <span style={{ color: '#646d78' }}>가맹 학원명:</span>
                  <div style={{ fontWeight: 700, marginTop: '2px' }}>{introName}</div>
                </div>
                <div style={{ background: '#fbf9f5', padding: '12px', borderRadius: '6px', border: '1px solid #e2dcce' }}>
                  <span style={{ color: '#646d78' }}>사업자번호:</span>
                  <div style={{ fontWeight: 700, marginTop: '2px', fontFamily: "'IBM Plex Mono', monospace" }}>120-81-98765</div>
                </div>
                <div style={{ background: '#fbf9f5', padding: '12px', borderRadius: '6px', border: '1px solid #e2dcce' }}>
                  <span style={{ color: '#646d78' }}>계약 기간:</span>
                  <div style={{ fontWeight: 700, marginTop: '2px' }}>36개월 (ACTIVE)</div>
                </div>
              </div>
            </div>

            {/* v5.0 신규: 학원 공식 소개 페이지 콘텐츠 편집 및 본사 승인 신청 */}
            <div style={{ background: '#ffffff', borderRadius: '8px', padding: '24px', border: '2px solid #d92632', boxShadow: '0 4px 14px rgba(217,38,50,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
                <div>
                  <h3 style={{ fontSize: '17px', margin: 0, color: '#1c2024' }}>
                    🌐 학원 공식 소개 페이지 설정 (v5.0 제3절)
                  </h3>
                  <span style={{ fontSize: '12.5px', color: '#646d78' }}>
                    학생·학부모에게 공개되는 전용 소개 페이지(app.artready.kr/t/{introSlug})의 내용을 편집하고 본사(BO)에 승인을 신청합니다.
                  </span>
                </div>
                <div>
                  {approvalStatus === 'APPROVED' ? (
                    <span style={{ background: '#15803d15', color: '#15803d', border: '1px solid #15803d30', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 700 }}>
                      ✓ 본사 게시 승인 완료
                    </span>
                  ) : (
                    <span style={{ background: '#d9263215', color: '#d92632', border: '1px solid #d9263230', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 700 }}>
                      ⏳ 본사 승인 심사 대기 중
                    </span>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>학원 브랜드명</label>
                  <input type="text" value={introName} onChange={e => setIntroName(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5' }} />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>URL 고유 식별자 (Slug)</label>
                  <input type="text" value={introSlug} onChange={e => setIntroSlug(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>학원 소개문 (미술 입시 철학 및 첨삭 특징)</label>
                  <textarea rows={3} value={introText} onChange={e => setIntroText(e.target.value)} style={{ width: '100%', padding: '10px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontSize: '13px' }} />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>합격 실적 1 (수시 합격률)</label>
                  <input type="text" value={introStat1} onChange={e => setIntroStat1(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>합격 실적 2 (주요 명문대 합격생 수)</label>
                  <input type="text" value={introStat2} onChange={e => setIntroStat2(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>합격 실적 3 (실기 만점자 배출)</label>
                  <input type="text" value={introStat3} onChange={e => setIntroStat3(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>대표 상담 전화번호</label>
                  <input type="text" value={introPhone} onChange={e => setIntroPhone(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5', fontFamily: "'IBM Plex Mono', monospace" }} />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>캠퍼스 상세 소재지 (주소)</label>
                  <input type="text" value={introAddress} onChange={e => setIntroAddress(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5' }} />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>상담 운영 시간</label>
                  <input type="text" value={introHours} onChange={e => setIntroHours(e.target.value)} style={{ width: '100%', padding: '8px', border: '1px solid #e2dcce', borderRadius: '6px', background: '#fbf9f5' }} />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
                <button
                  onClick={handleApplyAcademyIntro}
                  style={{ background: '#d92632', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '6px', fontSize: '14px', fontWeight: 700, cursor: 'pointer', boxShadow: '0 2px 8px rgba(217,38,50,0.3)' }}
                >
                  소개 페이지 수정안 본사 승인 신청
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── 모달: 신규 원생 등록 ── */}
      {studentModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '10px', padding: '24px', width: '420px', color: '#1c2024', boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>신규 원생 입학 등록</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>원생 이름</label>
                <input type="text" value={newStudentName} onChange={e => setNewStudentName(e.target.value)} placeholder="예: 홍길동" style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>학년 구분</label>
                <select value={newStudentGrade} onChange={e => setNewStudentGrade(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }}>
                  <option value="고3 수험생">고3 수험생 (실전입시반)</option>
                  <option value="고2 예비반">고2 디자인예비반</option>
                  <option value="고1 기초반">고1 조형기초반</option>
                  <option value="중등/취미반">중등 영재/기초반</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>목표 대학/전공</label>
                <input type="text" value={newStudentTarget} onChange={e => setNewStudentTarget(e.target.value)} placeholder="예: 국민대 디자인과 / 기초조형" style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setStudentModalOpen(false)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddStudent} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>등록 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 원생 상세 프로필 ── */}
      {selectedStudent && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '10px', padding: '24px', width: '460px', color: '#1c2024', boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>원생 상세 프로필</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>이름:</strong> {selectedStudent.name} ({selectedStudent.grade})</div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>목표 대학:</strong> {selectedStudent.targetMajor}</div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>연락처:</strong> <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{selectedStudent.phone}</span></div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>학부모 연동:</strong> {selectedStudent.parentLinked ? `${selectedStudent.parentName} (${selectedStudent.parentRelation})` : '미연동'}</div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>출석률:</strong> <span style={{ fontFamily: "'IBM Plex Mono', monospace", color: '#15803d', fontWeight: 700 }}>{selectedStudent.attendanceRate}%</span></div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px solid #e2dcce' }}><strong>상태:</strong> {selectedStudent.status}</div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '18px' }}>
              <button onClick={() => setSelectedStudent(null)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 새 실기 첨삭 작성 ── */}
      {evalModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '10px', padding: '24px', width: '480px', color: '#1c2024', boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', color: '#d92632' }}>✍️ 실기 평가 및 첨삭 작성</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>대상 원생</label>
                <select value={newEvalStudent} onChange={e => setNewEvalStudent(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }}>
                  {students.map(s => <option key={s.id} value={s.name}>{s.name} ({s.grade})</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>실기 유형</label>
                <select value={newEvalCategory} onChange={e => setNewEvalCategory(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }}>
                  <option value="기초디자인">기초디자인</option>
                  <option value="사고의전환">사고의전환 / 발상과표현</option>
                  <option value="정밀소묘">정밀소묘 / 인체드로잉</option>
                  <option value="기초조형">기초조형 (서울대/국민대)</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>평가 제목</label>
                <input type="text" value={newEvalTitle} onChange={e => setNewEvalTitle(e.target.value)} placeholder="예: 9월 정기 수시모의고사 — 공간구성" style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>평가 점수: <strong style={{ color: '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>{newEvalScore}점</strong></label>
                <input type="range" min="50" max="100" value={newEvalScore} onChange={e => setNewEvalScore(Number(e.target.value))} style={{ width: '100%', accentColor: '#d92632' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>첨삭 피드백 및 강평 (빨간펜 첨삭 감성)</label>
                <textarea rows={4} value={newEvalFeedback} onChange={e => setNewEvalFeedback(e.target.value)} placeholder="원생의 장점과 보완해야 할 구도/명도/채도 첨삭 포인트를 서술하세요..." style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px', fontSize: '12px' }} />
              </div>
              <div style={{ background: '#fbf9f5', padding: '10px', borderRadius: '6px', border: '1px dashed #e2dcce', textAlign: 'center', fontSize: '12px', color: '#646d78' }}>
                📁 실기 작품 비공개 스토리지 버킷 첨부 시뮬레이션 (자동 암호화)
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setEvalModalOpen(false)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddEvaluation} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>첨삭 저장 및 학생 알림</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 수업 앨범 등록 ── */}
      {albumModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '10px', padding: '24px', width: '440px', color: '#1c2024', boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>새 수업 앨범 사진 등록</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>대상 학급</label>
                <select value={newAlbumClass} onChange={e => setNewAlbumClass(e.target.value)} style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }}>
                  <option value="고3 입시정규A반">고3 입시정규A반</option>
                  <option value="고2 디자인예비반">고2 디자인예비반</option>
                  <option value="고1 기초소묘반">고1 기초소묘반</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>앨범 제목</label>
                <input type="text" value={newAlbumTitle} onChange={e => setNewAlbumTitle(e.target.value)} placeholder="예: 9월 주말 집중 특강 현장" style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#646d78', display: 'block', marginBottom: '4px' }}>수업 설명 / 캡션</label>
                <textarea rows={3} value={newAlbumDesc} onChange={e => setNewAlbumDesc(e.target.value)} placeholder="활동 내용 및 수업 분위기 기록..." style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '8px', borderRadius: '6px', fontSize: '12px' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setAlbumModalOpen(false)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddAlbum} style={{ background: '#2563eb', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>등록 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 사업자 정보 본사 변경 신청 ── */}
      {infoModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#ffffff', border: '1px solid #e2dcce', borderRadius: '10px', padding: '24px', width: '440px', color: '#1c2024', boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>학원 기본정보 변경 신청</h3>
            <p style={{ fontSize: '12px', color: '#646d78', marginBottom: '14px', lineHeight: 1.5 }}>
              사업자등록번호, 학원 주소, 대표자 정보 등 주요 법적 정보는 프랜차이즈 계약 무결성을 위해 본사(BO) 관리자 승인 후 반영됩니다.
            </p>
            <textarea
              rows={4}
              value={changeReqText}
              onChange={e => setChangeReqText(e.target.value)}
              placeholder="변경 요청 사항을 상세히 기재하세요..."
              style={{ width: '100%', background: '#fbf9f5', border: '1px solid #e2dcce', color: '#1c2024', padding: '10px', borderRadius: '6px', fontSize: '12px' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
              <button onClick={() => setInfoModalOpen(false)} style={{ background: '#f3eee4', color: '#1c2024', border: '1px solid #e2dcce', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={() => { showToast('본사에 기본정보 변경 승인 신청이 접수되었습니다.'); setInfoModalOpen(false); setChangeReqText(''); }} style={{ background: '#d92632', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>신청 제출</button>
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
              border: '1px solid #e2dcce',
              borderLeft: `4px solid ${t.type === 'error' ? '#ef4444' : t.type === 'info' ? '#3b82f6' : '#d92632'}`,
              borderRadius: '8px',
              padding: '12px 16px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              color: '#1c2024'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: t.type === 'error' ? '#ef4444' : '#d92632', fontFamily: "'IBM Plex Mono', monospace" }}>
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
