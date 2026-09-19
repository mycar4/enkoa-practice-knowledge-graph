import { useState } from 'react';

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

export default function App() {
  // 현재 선택된 메뉴 (10개 메뉴 전수 대응)
  const [activeMenu, setActiveMenu] = useState<string>('dashboard');

  // 사용자 권한 모드 토글 (원장 vs 강사)
  const [userRole, setUserRole] = useState<'DIRECTOR' | 'INSTRUCTOR'>('DIRECTOR');

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
    { menu_key: 'student.evaluation', label: '실기 평가 및 피드백', description: '원생 실기 평가 및 피드백 작성/이미지 등록', can_read: true, can_write: true },
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
    { id: 'eval-2', studentName: '이준우', category: '사고의전환', title: '전구와 자연물의 융합 조형', date: '2026-09-15', instructorName: '이민혁 수석강사', score: 86, feedback: '아이디어 발상은 참신하나, 주제부 전구의 투시 비례가 살짝 왜곡되었습니다. 타원 투시 연습 보강 요망.' }
  ]);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [newEvalStudent, setNewEvalStudent] = useState('김예원');
  const [newEvalCategory, setNewEvalCategory] = useState('기초디자인');
  const [newEvalTitle, setNewEvalTitle] = useState('');
  const [newEvalScore, setNewEvalScore] = useState(90);
  const [newEvalFeedback, setNewEvalFeedback] = useState('');

  // 5. 수업 앨범 데이터
  const [albumList, setAlbumList] = useState<AlbumItem[]>([
    { id: 'alb-1', className: '고3 입시정규A반', title: '수시 대비 실전 모의고사 현장', date: '2026-09-18', author: '이민혁 강사', imageUrl: '🎨', description: '4시간 타임어택 실기 시험 진행. 실전 시험장 긴장감 극복 및 완성도 훈련' },
    { id: 'alb-2', className: '고2 디자인예비반', title: '질감 마스터 특강 (금속/나무/물)', date: '2026-09-14', author: '장수진 강사', imageUrl: '🖌️', description: '빛 방향에 따른 음영 처리 및 재질감별 붓 터치 기법 실습' }
  ]);
  const [albumModalOpen, setAlbumModalOpen] = useState(false);
  const [newAlbumClass, setNewAlbumClass] = useState('고3 입시정규A반');
  const [newAlbumTitle, setNewAlbumTitle] = useState('');
  const [newAlbumDesc, setNewAlbumDesc] = useState('');

  // 6. 수강료 데이터 (원장 전용)
  const [tuitionList, setTuitionList] = useState<TuitionRecord[]>([
    { id: 't-01', studentName: '김예원', className: '고3 입시정규반', amount: 850000, dueDate: '2026-09-10', paidDate: '2026-09-08', status: 'PAID' },
    { id: 't-02', studentName: '이준우', className: '고3 입시정규반', amount: 850000, dueDate: '2026-09-10', paidDate: '2026-09-10', status: 'PAID' },
    { id: 't-03', studentName: '박서연', className: '고2 디자인반', amount: 650000, dueDate: '2026-09-10', paidDate: '2026-09-09', status: 'PAID' },
    { id: 't-04', studentName: '최민서', className: '고2 디자인반', amount: 650000, dueDate: '2026-09-10', status: 'UNPAID' },
    { id: 't-05', studentName: '정태양', className: '고1 기초반', amount: 500000, dueDate: '2026-09-10', status: 'UNPAID' }
  ]);

  // 7. 학부모 연동 데이터
  const [parentLinks, setParentLinks] = useState<ParentLink[]>([
    { id: 'pl-1', studentName: '김예원', studentId: 's-01', parentName: '박현숙', relation: '모', linkedAt: '2026-09-01', code: 'AR-2026-9812' },
    { id: 'pl-2', studentName: '이준우', studentId: 's-02', parentName: '이상철', relation: '부', linkedAt: '2026-09-02', code: 'AR-2026-5541' },
    { id: 'pl-3', studentName: '최민서', studentId: 's-04', parentName: '정미영', relation: '모', linkedAt: '2026-09-05', code: 'AR-2026-7833' }
  ]);

  // 8. 정책/약관 데이터 (조회 전용)
  const policies = [
    { id: 'pol-1', title: 'ART:READY 가맹 표준 이용약관', version: 'v2.0', effectiveDate: '2026-09-19', status: '본사 공시 유효', content: '본 약관은 ART:READY 프랜차이즈 B2B 플랫폼을 이용하는 가맹학원 및 수험생 회원의 권리, 의무를 규정합니다.' },
    { id: 'pol-2', title: '개인정보처리방침 및 아동보호 규정', version: 'v2.0', effectiveDate: '2026-09-19', status: '본사 공시 유효', content: '개인정보보호법 제22조의2(만 14세 미만 법정대리인 동의) 및 실기 작품 이미지의 암호화 저장/비공개 버킷 보안 규정을 포함합니다.' }
  ];

  // 9. 학원 기본정보
  const academyInfo = {
    name: '강남 미술학원 본원',
    bizNo: '120-81-98765',
    repName: '홍원장',
    address: '서울특별시 강남구 테헤란로 124 삼원빌딩 4~5층',
    tel: '02-555-7890',
    contractMonths: 36,
    status: 'ACTIVE',
    openedAt: '2024-03-01'
  };
  const [infoModalOpen, setInfoModalOpen] = useState(false);
  const [changeReqText, setChangeReqText] = useState('');

  // 핸들러 함수들
  const handleTogglePerm = (key: string, field: 'can_read' | 'can_write') => {
    if (userRole !== 'DIRECTOR') {
      alert('⚠️ 권한 변경은 원장(TENANT_ADMIN) 전용 기능입니다.');
      return;
    }
    setPermissions(prev =>
      prev.map(p => (p.menu_key === key && !p.isLocked ? { ...p, [field]: !p[field] } : p))
    );
  };

  const handleSavePermissions = () => {
    alert(`[저장 완료]\n강사(${selectedInstructorId})의 메뉴 권한 설정이 Supabase menu_permissions 테이블에 반영되었습니다.\n(지시서 v2.0 제3.3절 2중 RLS 정책 결속)`);
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
    alert('원생 상태가 변경되었습니다.');
  };

  const handleAddStudent = () => {
    if (!newStudentName.trim()) {
      alert('원생 이름을 입력해주세요.');
      return;
    }
    const newS: Student = {
      id: `s-0${students.length + 1}`,
      name: newStudentName,
      grade: newStudentGrade,
      targetMajor: newStudentTarget || '기초디자인',
      status: 'ACTIVE',
      parentLinked: false,
      phone: '010-0000-0000',
      attendanceRate: 100
    };
    setStudents(prev => [newS, ...prev]);
    setStudentModalOpen(false);
    setNewStudentName('');
    alert(`[등록 완료] ${newStudentName} 원생이 신규 등록되었습니다.`);
  };

  const handleAddEvaluation = () => {
    if (!newEvalTitle.trim() || !newEvalFeedback.trim()) {
      alert('평가 제목과 피드백을 모두 입력해주세요.');
      return;
    }
    const newEval: Evaluation = {
      id: `eval-${evaluations.length + 1}`,
      studentName: newEvalStudent,
      category: newEvalCategory,
      title: newEvalTitle,
      date: new Date().toISOString().split('T')[0],
      instructorName: '이민혁 수석강사',
      score: newEvalScore,
      feedback: newEvalFeedback
    };
    setEvaluations(prev => [newEval, ...prev]);
    setEvalModalOpen(false);
    setNewEvalTitle('');
    setNewEvalFeedback('');
    alert(`[평가 완료] ${newEvalStudent} 학생의 실기 평가가 등록되었습니다. (비공개 버킷 암호화 저장)`);
  };

  const handleAddAlbum = () => {
    if (!newAlbumTitle.trim()) {
      alert('앨범 제목을 입력해주세요.');
      return;
    }
    const newAlb: AlbumItem = {
      id: `alb-${albumList.length + 1}`,
      className: newAlbumClass,
      title: newAlbumTitle,
      date: new Date().toISOString().split('T')[0],
      author: '이민혁 강사',
      imageUrl: '📸',
      description: newAlbumDesc
    };
    setAlbumList(prev => [newAlb, ...prev]);
    setAlbumModalOpen(false);
    setNewAlbumTitle('');
    setNewAlbumDesc('');
    alert('새 수업 앨범이 등록되었습니다.');
  };

  const handleRegenCode = (linkId: string) => {
    const randomCode = `AR-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    setParentLinks(prev =>
      prev.map(pl => pl.id === linkId ? { ...pl, code: randomCode } : pl)
    );
    alert(`[재발급 완료] 새로운 학부모 연동 코드: ${randomCode}`);
  };

  const handleSendReminder = (studentName: string) => {
    alert(`[알림 발송]\n${studentName} 원생의 학부모님께 미납 수강료 결제 안내 알림톡이 전송되었습니다.`);
  };

  const handleTuitionPay = (id: string) => {
    setTuitionList(prev =>
      prev.map(t => t.id === id ? { ...t, status: 'PAID', paidDate: new Date().toISOString().split('T')[0] } : t)
    );
    alert('수강료 수납이 정상 등록되었습니다.');
  };

  const filteredStudents = students.filter(s =>
    s.name.includes(studentSearch) || s.grade.includes(studentSearch) || s.targetMajor.includes(studentSearch)
  );

  return (
    <div className="admin-wrapper" style={{ display: 'flex', minHeight: '100vh', background: '#0f172a', color: '#f8fafc' }}>
      {/* ── 좌측 사이드바 (10개 메뉴) ── */}
      <aside className="sidebar" style={{ width: '270px', background: '#1e293b', borderRight: '1px solid #334155', display: 'flex', flexDirection: 'column', padding: '20px 14px', gap: '16px' }}>
        <div className="sidebar-brand" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ background: 'linear-gradient(135deg, #10b981, #3b82f6)', color: 'white', fontWeight: 800, padding: '4px 8px', borderRadius: '6px', fontSize: '13px' }}>CO</span>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>ART:READY</h2>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>가맹학원 운영포털</span>
          </div>
        </div>

        {/* 학원 정보 배지 */}
        <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid #334155', padding: '12px', borderRadius: '8px' }}>
          <div style={{ fontSize: '14px', fontWeight: 'bold' }}>{academyInfo.name}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
            <span style={{ fontSize: '11px', background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: '4px', border: '1px solid #10b98144' }}>운영중 (ACTIVE)</span>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>재원생 {students.filter(s => s.status === 'ACTIVE').length}명</span>
          </div>
        </div>

        {/* 역할 전환 스위처 */}
        <div style={{ background: '#0f172a', padding: '6px', borderRadius: '8px', display: 'flex', gap: '4px' }}>
          <button
            onClick={() => setUserRole('DIRECTOR')}
            style={{
              flex: 1, padding: '6px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
              background: userRole === 'DIRECTOR' ? '#3b82f6' : 'transparent', color: userRole === 'DIRECTOR' ? '#fff' : '#94a3b8', fontWeight: userRole === 'DIRECTOR' ? 700 : 400
            }}
          >
            👑 원장 모드
          </button>
          <button
            onClick={() => setUserRole('INSTRUCTOR')}
            style={{
              flex: 1, padding: '6px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
              background: userRole === 'INSTRUCTOR' ? '#3b82f6' : 'transparent', color: userRole === 'INSTRUCTOR' ? '#fff' : '#94a3b8', fontWeight: userRole === 'INSTRUCTOR' ? 700 : 400
            }}
          >
            🎨 강사 모드
          </button>
        </div>

        {/* 10대 메뉴 내비게이션 */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '3px', flex: 1, overflowY: 'auto' }}>
          {[
            { key: 'dashboard', label: '📊 운영 대시보드' },
            { key: 'students', label: '👥 원생 명부 관리' },
            { key: 'instructors', label: '🔐 강사(부운영자) 관리', badge: '원장전용' },
            { key: 'attendance', label: '📅 출결 관리' },
            { key: 'evaluations', label: '🎨 실기 평가/피드백' },
            { key: 'album', label: '📸 수업 앨범' },
            { key: 'tuition', label: '💳 수강료 수납 관리', badge: '원장전용' },
            { key: 'parent_links', label: '👨‍👩‍👧 학부모 연동 관리' },
            { key: 'policies', label: '📜 정책/약관 조회' },
            { key: 'academy_info', label: '🏫 학원 기본정보' }
          ].map(m => {
            const isActive = activeMenu === m.key;
            return (
              <button
                key={m.key}
                onClick={() => setActiveMenu(m.key)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '9px 12px', borderRadius: '8px', border: 'none', textAlign: 'left',
                  background: isActive ? '#3b82f6' : 'transparent',
                  color: isActive ? '#ffffff' : '#94a3b8',
                  fontSize: '13px', fontWeight: isActive ? 600 : 400,
                  cursor: 'pointer', transition: 'all 0.15s ease'
                }}
              >
                <span>{m.label}</span>
                {m.badge && (
                  <span style={{ fontSize: '10px', background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', padding: '1px 5px', borderRadius: '4px' }}>
                    {m.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* 사이드바 푸터 */}
        <div style={{ borderTop: '1px solid #334155', paddingTop: '12px', fontSize: '12px', color: '#94a3b8' }}>
          <div>로그인: <strong style={{ color: '#f8fafc' }}>{userRole === 'DIRECTOR' ? '홍원장 (원장단)' : '이민혁 (수석강사)'}</strong></div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>partner.artready.kr v4.0</div>
        </div>
      </aside>

      {/* ── 우측 메인 콘텐츠 영역 ── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
        <header style={{ padding: '18px 28px', borderBottom: '1px solid #334155', background: '#1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0 }}>
              {activeMenu === 'dashboard' && '학원 운영 현황 대시보드'}
              {activeMenu === 'students' && '원생 명부 및 학부모 연동 관리'}
              {activeMenu === 'instructors' && '강사(부운영자) 목록 및 세부 메뉴 권한 매트릭스'}
              {activeMenu === 'attendance' && '일별 출결 체크 및 결석 사유 관리'}
              {activeMenu === 'evaluations' && '원생 실기 평가 및 비공개 피드백 관리'}
              {activeMenu === 'album' && '반별 수업 사진 및 강평 앨범'}
              {activeMenu === 'tuition' && '학생별 수강료 납부 현황 및 장부 관리'}
              {activeMenu === 'parent_links' && '학부모 연동 코드 발급 및 승인 내역'}
              {activeMenu === 'policies' && '본사 공시 정책 및 이용약관 열람 (조회 전용)'}
              {activeMenu === 'academy_info' && '학원 기본정보 조회 및 본사 변경 신청'}
            </h1>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>ART:READY 프랜차이즈 가맹 운영 시스템 — Supabase 2중 RLS 보안 적용</span>
          </div>
          <div>
            {activeMenu === 'students' && (
              <button onClick={() => setStudentModalOpen(true)} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                + 신규 원생 등록
              </button>
            )}
            {activeMenu === 'evaluations' && (
              <button onClick={() => setEvalModalOpen(true)} style={{ background: '#10b981', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                + 새 실기 평가 작성
              </button>
            )}
            {activeMenu === 'album' && (
              <button onClick={() => setAlbumModalOpen(true)} style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                + 수업 사진 업로드
              </button>
            )}
          </div>
        </header>

        <div style={{ padding: '24px 28px', flex: 1 }}>
          {/* 1. 대시보드 */}
          {activeMenu === 'dashboard' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '24px' }}>
                <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', border: '1px solid #334155' }}>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>재원 원생 수</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0', color: '#f8fafc' }}>{students.filter(s => s.status === 'ACTIVE').length}명</div>
                  <div style={{ fontSize: '12px', color: '#10b981' }}>정원 50명 대비 96%</div>
                </div>
                <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', border: '1px solid #334155' }}>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>이번달 수납률</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0', color: '#3b82f6' }}>91.6%</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>완납 44명 / 미납 4명</div>
                </div>
                <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', border: '1px solid #334155' }}>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>출결 평균 (이번주)</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0', color: '#10b981' }}>98.2%</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>병결 1건 / 지각 1건</div>
                </div>
                <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', border: '1px solid #334155' }}>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>소속 강사 수</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0', color: '#f8fafc' }}>{instructors.length}명</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>수석전임 1 / 전임 1 / 보조 1</div>
                </div>
                <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', border: '1px solid #334155' }}>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>오늘의 채점 대기</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0', color: '#f59e0b' }}>2건</div>
                  <div style={{ fontSize: '12px', color: '#f59e0b' }}>고3 정규 모의평가</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
                <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
                  <h3 style={{ fontSize: '16px', marginBottom: '14px' }}>📋 오늘의 채점 대기 목록</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0f172a', padding: '12px 16px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <div>
                        <strong>김예원 (고3 수험생)</strong> — 기초디자인 타임어택 평가
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>제출 시각: 오늘 16:30 | 담당: 이민혁 수석강사</div>
                      </div>
                      <button onClick={() => { setActiveMenu('evaluations'); setEvalModalOpen(true); }} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>채점하기</button>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0f172a', padding: '12px 16px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <div>
                        <strong>이준우 (고3 수험생)</strong> — 자연물 묘사 정밀소묘 과제
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>제출 시각: 오늘 15:45 | 담당: 이민혁 수석강사</div>
                      </div>
                      <button onClick={() => { setActiveMenu('evaluations'); setEvalModalOpen(true); }} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>채점하기</button>
                    </div>
                  </div>
                </div>

                <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
                  <h3 style={{ fontSize: '16px', marginBottom: '14px' }}>📢 본사 공지사항 요약</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                    <div style={{ borderBottom: '1px solid #334155', paddingBottom: '8px' }}>
                      <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', marginRight: '6px' }}>중요</span>
                      <strong>2026 수시 실기고사 대비 전국 모의평가</strong>
                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>엔코아 본사 | 2026-09-18</div>
                    </div>
                    <div>
                      <span style={{ background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', marginRight: '6px' }}>보안</span>
                      <strong>14세 미만 보호자 동의 RLS 강화 적용</strong>
                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>컴플라이언스팀 | 2026-09-15</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 2. 원생 관리 */}
          {activeMenu === 'students' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                <input
                  type="text"
                  placeholder="원생 이름, 학년, 목표 대학 검색..."
                  value={studentSearch}
                  onChange={e => setStudentSearch(e.target.value)}
                  style={{ background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px 14px', borderRadius: '6px', width: '320px', fontSize: '13px' }}
                />
                <div style={{ fontSize: '13px', color: '#94a3b8', alignSelf: 'center' }}>총 원생 수: {filteredStudents.length}명</div>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                    <th style={{ padding: '10px' }}>원생명</th>
                    <th style={{ padding: '10px' }}>학년/구분</th>
                    <th style={{ padding: '10px' }}>목표 대학/전공</th>
                    <th style={{ padding: '10px' }}>출석률</th>
                    <th style={{ padding: '10px' }}>학부모 연동</th>
                    <th style={{ padding: '10px' }}>상태 변경</th>
                    <th style={{ padding: '10px' }}>상세보기</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map(s => (
                    <tr key={s.id} style={{ borderBottom: '1px solid #334155' }}>
                      <td style={{ padding: '12px 10px', fontWeight: 600 }}>{s.name}</td>
                      <td style={{ padding: '12px 10px' }}>{s.grade}</td>
                      <td style={{ padding: '12px 10px' }}>{s.targetMajor}</td>
                      <td style={{ padding: '12px 10px', color: '#10b981', fontWeight: 600 }}>{s.attendanceRate}%</td>
                      <td style={{ padding: '12px 10px' }}>
                        {s.parentLinked ? (
                          <span style={{ background: '#10b98122', color: '#10b981', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>연동완료 ({s.parentRelation}: {s.parentName})</span>
                        ) : (
                          <span style={{ background: '#ef444422', color: '#ef4444', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>미연동 (코드발급필요)</span>
                        )}
                      </td>
                      <td style={{ padding: '12px 10px' }}>
                        <select
                          value={s.status}
                          onChange={e => handleStudentStatusChange(s.id, e.target.value as any)}
                          style={{ background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '4px 8px', borderRadius: '4px', fontSize: '12px' }}
                        >
                          <option value="ACTIVE">재원 (ACTIVE)</option>
                          <option value="LEAVE">휴원 (LEAVE)</option>
                          <option value="DROPOUT">퇴원 (DROPOUT)</option>
                        </select>
                      </td>
                      <td style={{ padding: '12px 10px' }}>
                        <button onClick={() => setSelectedStudent(s)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '4px 10px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>
                          프로필
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 3. 강사(부운영자) 관리 (원장 전용) */}
          {activeMenu === 'instructors' && (
            <div>
              {userRole !== 'DIRECTOR' ? (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', padding: '24px', borderRadius: '10px', textAlign: 'center' }}>
                  <h3 style={{ color: '#ef4444', margin: '0 0 8px 0' }}>⚠️ 원장 전용 보안 접근 제한</h3>
                  <p style={{ fontSize: '14px', color: '#94a3b8' }}>강사 관리 및 메뉴 권한 매트릭스 설정은 원장(TENANT_ADMIN) 계정으로만 접근 가능합니다. 상단 모드 스위처에서 '원장 모드'를 선택하십시오.</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
                  {/* 강사 목록 */}
                  <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <h3 style={{ fontSize: '16px', margin: 0 }}>강사 명단 ({instructors.length}명)</h3>
                      <button onClick={() => alert('신규 강사 초대 링크가 복사되었습니다.')} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>+ 초대</button>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {instructors.map(ins => (
                        <div
                          key={ins.id}
                          onClick={() => setSelectedInstructorId(ins.id)}
                          style={{
                            padding: '12px', borderRadius: '8px', border: '1px solid',
                            borderColor: selectedInstructorId === ins.id ? '#3b82f6' : '#334155',
                            background: selectedInstructorId === ins.id ? '#1e3a8a33' : '#0f172a',
                            cursor: 'pointer'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <strong>{ins.name} ({ins.role})</strong>
                            <span style={{ fontSize: '11px', color: '#3b82f6' }}>{ins.className}</span>
                          </div>
                          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>{ins.phone} | {ins.email}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 강사별 메뉴 권한 매트릭스 설정 */}
                  <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <div>
                        <h3 style={{ fontSize: '16px', margin: 0 }}>메뉴별 세부 권한 매트릭스 (v2.0 제3.3절)</h3>
                        <span style={{ fontSize: '12px', color: '#94a3b8' }}>대상: {instructors.find(i => i.id === selectedInstructorId)?.name} 강사 — Supabase RLS 자동 연동</span>
                      </div>
                      <button onClick={handleSavePermissions} style={{ background: '#10b981', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                        설정 저장
                      </button>
                    </div>

                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                          <th style={{ padding: '10px' }}>메뉴 기능명</th>
                          <th style={{ padding: '10px' }}>설명</th>
                          <th style={{ padding: '10px', textAlign: 'center' }}>조회 (READ)</th>
                          <th style={{ padding: '10px', textAlign: 'center' }}>수정/등록 (WRITE)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {permissions.map(p => (
                          <tr key={p.menu_key} style={{ borderBottom: '1px solid #334155' }}>
                            <td style={{ padding: '12px 10px', fontWeight: 600 }}>{p.label}</td>
                            <td style={{ padding: '12px 10px', color: '#94a3b8', fontSize: '12px' }}>{p.description}</td>
                            <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                checked={p.can_read}
                                disabled={p.isLocked}
                                onChange={() => handleTogglePerm(p.menu_key, 'can_read')}
                                style={{ width: '16px', height: '16px', cursor: p.isLocked ? 'not-allowed' : 'pointer' }}
                              />
                            </td>
                            <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                checked={p.can_write}
                                disabled={p.isLocked}
                                onChange={() => handleTogglePerm(p.menu_key, 'can_write')}
                                style={{ width: '16px', height: '16px', cursor: p.isLocked ? 'not-allowed' : 'pointer' }}
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
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', margin: 0 }}>2026년 9월 19일 일별 출결 체크 (수업별)</h3>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>결석 처리 시 사유를 반드시 입력하여 학부모 알림 연동</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => alert('전체 출석 처리되었습니다.')} style={{ background: '#334155', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer' }}>전체 출석</button>
                  <button onClick={() => alert('출결 데이터가 Supabase DB에 저장되었습니다.')} style={{ background: '#10b981', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>출결 저장</button>
                </div>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                    <th style={{ padding: '10px' }}>원생명</th>
                    <th style={{ padding: '10px' }}>담당 반</th>
                    <th style={{ padding: '10px' }}>출결 상태</th>
                    <th style={{ padding: '10px' }}>결석/지각 사유 입력</th>
                  </tr>
                </thead>
                <tbody>
                  {attendanceList.map(item => (
                    <tr key={item.id} style={{ borderBottom: '1px solid #334155' }}>
                      <td style={{ padding: '12px 10px', fontWeight: 600 }}>{item.studentName}</td>
                      <td style={{ padding: '12px 10px', color: '#94a3b8' }}>{item.className}</td>
                      <td style={{ padding: '12px 10px' }}>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            onClick={() => handleAttendanceChange(item.id, 'PRESENT')}
                            style={{
                              padding: '4px 10px', borderRadius: '4px', border: 'none', fontSize: '12px', cursor: 'pointer',
                              background: item.status === 'PRESENT' ? '#10b981' : '#334155', color: '#fff'
                            }}
                          >
                            출석
                          </button>
                          <button
                            onClick={() => handleAttendanceChange(item.id, 'LATE')}
                            style={{
                              padding: '4px 10px', borderRadius: '4px', border: 'none', fontSize: '12px', cursor: 'pointer',
                              background: item.status === 'LATE' ? '#f59e0b' : '#334155', color: '#fff'
                            }}
                          >
                            지각
                          </button>
                          <button
                            onClick={() => handleAttendanceChange(item.id, 'ABSENT')}
                            style={{
                              padding: '4px 10px', borderRadius: '4px', border: 'none', fontSize: '12px', cursor: 'pointer',
                              background: item.status === 'ABSENT' ? '#ef4444' : '#334155', color: '#fff'
                            }}
                          >
                            결석
                          </button>
                        </div>
                      </td>
                      <td style={{ padding: '12px 10px' }}>
                        <input
                          type="text"
                          placeholder={item.status === 'PRESENT' ? '정상 출석' : '사유 입력 필수 (예: 감기 몸살, 학교 행사)'}
                          value={item.reason}
                          onChange={e => handleReasonChange(item.id, e.target.value)}
                          disabled={item.status === 'PRESENT'}
                          style={{
                            background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '6px 10px', borderRadius: '4px', width: '90%', fontSize: '12px',
                            opacity: item.status === 'PRESENT' ? 0.4 : 1
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 5. 실기 평가/피드백 */}
          {activeMenu === 'evaluations' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', margin: 0 }}>원생 실기 평가 및 피드백 이력 ({evaluations.length}건)</h3>
                <span style={{ fontSize: '12px', color: '#10b981' }}>🔒 비공개 스토리지 버킷 + Signed URL 암호화 보호</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {evaluations.map(ev => (
                  <div key={ev.id} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', marginRight: '8px' }}>{ev.category}</span>
                        <strong style={{ fontSize: '15px' }}>{ev.title}</strong>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>원생: {ev.studentName} | 작성: {ev.instructorName} | 날짜: {ev.date}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '20px', fontWeight: 800, color: '#10b981' }}>{ev.score}점</div>
                        <button onClick={() => alert(`[보안 서명 URL 발급]\n'${ev.title}' 작품 이미지 열람을 위한 1시간 만료 보안 Signed URL이 안전하게 생성되었습니다.`)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer', marginTop: '4px' }}>
                          🖼️ 실기작품 열람
                        </button>
                      </div>
                    </div>
                    <div style={{ marginTop: '12px', background: '#1e293b', padding: '12px', borderRadius: '6px', fontSize: '13px', lineHeight: 1.6, color: '#e2e8f0' }}>
                      💬 <strong>강사 총평 피드백:</strong> {ev.feedback}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 6. 수업 앨범 */}
          {activeMenu === 'album' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', margin: 0 }}>반별 수업 활동 앨범</h3>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>학생·학부모 포털(FO)에 실시간 공유</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                {albumList.map(alb => (
                  <div key={alb.id} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', overflow: 'hidden' }}>
                    <div style={{ height: '140px', background: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '48px' }}>
                      {alb.imageUrl}
                    </div>
                    <div style={{ padding: '14px' }}>
                      <span style={{ background: '#6366f122', color: '#6366f1', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>{alb.className}</span>
                      <h4 style={{ fontSize: '15px', margin: '8px 0 4px 0' }}>{alb.title}</h4>
                      <p style={{ fontSize: '12px', color: '#94a3b8', margin: 0 }}>{alb.description}</p>
                      <div style={{ marginTop: '10px', fontSize: '11px', color: '#64748b' }}>등록자: {alb.author} | {alb.date}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 7. 수강료 관리 (원장 전용) */}
          {activeMenu === 'tuition' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              {userRole !== 'DIRECTOR' ? (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', padding: '24px', borderRadius: '10px', textAlign: 'center' }}>
                  <h3 style={{ color: '#ef4444', margin: '0 0 8px 0' }}>⚠️ 원장 전용 금융 보안 화면</h3>
                  <p style={{ fontSize: '14px', color: '#94a3b8' }}>수강료 장부 및 미납 내역 관리는 지시서 v2.0 제3.5절 / v4.0 제2절에 따라 강사 접근이 원천 차단된 원장 전용 기능입니다.</p>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <div>
                      <h3 style={{ fontSize: '16px', margin: 0 }}>2026년 9월 수강료 수납 장부</h3>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>총 청구 3,500,000원 | 완납 2,350,000원 | 미납 1,150,000원</span>
                    </div>
                    <button onClick={() => alert('미납자 전원에게 1차 납부 독려 메시지가 발송되었습니다.')} style={{ background: '#f59e0b', color: '#000', border: 'none', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                      📢 미납 원생 일괄 알림 발송
                    </button>
                  </div>

                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
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
                        <tr key={t.id} style={{ borderBottom: '1px solid #334155' }}>
                          <td style={{ padding: '12px 10px', fontWeight: 600 }}>{t.studentName}</td>
                          <td style={{ padding: '12px 10px', color: '#94a3b8' }}>{t.className}</td>
                          <td style={{ padding: '12px 10px', fontWeight: 700 }}>{t.amount.toLocaleString()}원</td>
                          <td style={{ padding: '12px 10px', color: '#94a3b8' }}>{t.dueDate}</td>
                          <td style={{ padding: '12px 10px' }}>
                            {t.status === 'PAID' ? (
                              <span style={{ background: '#10b98122', color: '#10b981', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>완납 ({t.paidDate})</span>
                            ) : (
                              <span style={{ background: '#ef444422', color: '#ef4444', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>미납</span>
                            )}
                          </td>
                          <td style={{ padding: '12px 10px' }}>
                            {t.status === 'UNPAID' ? (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => handleTuitionPay(t.id)} style={{ background: '#10b981', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                                  납부등록
                                </button>
                                <button onClick={() => handleSendReminder(t.studentName)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                                  알림톡
                                </button>
                              </div>
                            ) : (
                              <span style={{ fontSize: '12px', color: '#64748b' }}>영수증 발급완료</span>
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

          {/* 8. 학부모 연동 관리 */}
          {activeMenu === 'parent_links' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', margin: 0 }}>학생별 학부모 연동 코드 및 승인 내역</h3>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>학부모 가입 시 코드를 입력하면 1:N / N:1 안전 결속 (RLS 매핑)</span>
                </div>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                    <th style={{ padding: '10px' }}>학생명</th>
                    <th style={{ padding: '10px' }}>보호자명 (관계)</th>
                    <th style={{ padding: '10px' }}>연동 코드</th>
                    <th style={{ padding: '10px' }}>연동 승인일</th>
                    <th style={{ padding: '10px' }}>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {parentLinks.map(pl => (
                    <tr key={pl.id} style={{ borderBottom: '1px solid #334155' }}>
                      <td style={{ padding: '12px 10px', fontWeight: 600 }}>{pl.studentName}</td>
                      <td style={{ padding: '12px 10px' }}>{pl.parentName} ({pl.relation})</td>
                      <td style={{ padding: '12px 10px' }}>
                        <code style={{ background: '#0f172a', padding: '4px 8px', borderRadius: '4px', color: '#3b82f6', fontWeight: 700 }}>{pl.code}</code>
                      </td>
                      <td style={{ padding: '12px 10px', color: '#94a3b8' }}>{pl.linkedAt}</td>
                      <td style={{ padding: '12px 10px' }}>
                        <button onClick={() => handleRegenCode(pl.id)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                          코드 재발급
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 9. 정책/약관 조회 (조회 전용) */}
          {activeMenu === 'policies' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', margin: 0 }}>본사 공시 정책 및 이용약관 열람</h3>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>가맹점은 조회 전용 권한을 가지며, 정책 개정은 본사(BO) 승인 하에 일괄 고지됩니다.</span>
                </div>
                <span style={{ background: '#3b82f622', color: '#3b82f6', padding: '4px 10px', borderRadius: '6px', fontSize: '12px' }}>🔒 본사 공시본 (수정불가)</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {policies.map(pol => (
                  <div key={pol.id} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div>
                        <strong style={{ fontSize: '15px' }}>{pol.title}</strong>
                        <span style={{ marginLeft: '8px', background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>{pol.version}</span>
                      </div>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>발효일자: {pol.effectiveDate}</span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.6, margin: 0 }}>{pol.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 10. 학원 기본정보 */}
          {activeMenu === 'academy_info' && (
            <div style={{ background: '#1e293b', borderRadius: '10px', padding: '20px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', margin: 0 }}>가맹학원 사업자 기본 정보</h3>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>주요 사업자 정보 변경은 프랜차이즈 본사 검수 및 승인 절차가 필요합니다.</span>
                </div>
                <button onClick={() => setInfoModalOpen(true)} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                  ✏️ 본사에 변경 신청
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', fontSize: '13px' }}>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>가맹 학원명:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.name}</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>사업자등록번호:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.bizNo}</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>대표 원장명:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.repName}</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>대표 연락처:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.tel}</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155', gridColumn: 'span 2' }}>
                  <span style={{ color: '#94a3b8' }}>학원 소재지 (주소):</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.address}</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>프랜차이즈 계약 기간:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>{academyInfo.contractMonths}개월 (개원일: {academyInfo.openedAt})</div>
                </div>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                  <span style={{ color: '#94a3b8' }}>운영 승인 상태:</span>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px', color: '#10b981' }}>{academyInfo.status} (정상 운영)</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── 모달: 신규 원생 등록 ── */}
      {studentModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', width: '420px', color: '#fff' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>신규 원생 입학 등록</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>원생 이름</label>
                <input type="text" value={newStudentName} onChange={e => setNewStudentName(e.target.value)} placeholder="예: 홍길동" style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>학년 구분</label>
                <select value={newStudentGrade} onChange={e => setNewStudentGrade(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }}>
                  <option value="고3 수험생">고3 수험생 (실전입시반)</option>
                  <option value="고2 예비반">고2 디자인예비반</option>
                  <option value="고1 기초반">고1 조형기초반</option>
                  <option value="중등/취미반">중등 영재/기초반</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>목표 대학/전공</label>
                <input type="text" value={newStudentTarget} onChange={e => setNewStudentTarget(e.target.value)} placeholder="예: 서울대 디자인과 / 기초소양" style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setStudentModalOpen(false)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddStudent} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>등록 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 원생 상세 프로필 ── */}
      {selectedStudent && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', width: '460px', color: '#fff' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>원생 상세 프로필</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>이름:</strong> {selectedStudent.name} ({selectedStudent.grade})</div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>목표 대학:</strong> {selectedStudent.targetMajor}</div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>연락처:</strong> {selectedStudent.phone}</div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>학부모 연동:</strong> {selectedStudent.parentLinked ? `${selectedStudent.parentName} (${selectedStudent.parentRelation})` : '미연동'}</div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>출석률:</strong> {selectedStudent.attendanceRate}%</div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px' }}><strong>상태:</strong> {selectedStudent.status}</div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '18px' }}>
              <button onClick={() => setSelectedStudent(null)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 새 실기 평가 작성 ── */}
      {evalModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', width: '480px', color: '#fff' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>실기 평가 및 피드백 작성</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>대상 원생</label>
                <select value={newEvalStudent} onChange={e => setNewEvalStudent(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }}>
                  {students.map(s => <option key={s.id} value={s.name}>{s.name} ({s.grade})</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>실기 유형</label>
                <select value={newEvalCategory} onChange={e => setNewEvalCategory(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }}>
                  <option value="기초디자인">기초디자인</option>
                  <option value="사고의전환">사고의전환 / 발상과표현</option>
                  <option value="정밀소묘">정밀소묘 / 인체드로잉</option>
                  <option value="기초조형">기초조형 (서울대/국민대)</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>평가 제목</label>
                <input type="text" value={newEvalTitle} onChange={e => setNewEvalTitle(e.target.value)} placeholder="예: 9월 정기 수시모의고사 — 공간구성" style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>평가 점수: {newEvalScore}점</label>
                <input type="range" min="50" max="100" value={newEvalScore} onChange={e => setNewEvalScore(Number(e.target.value))} style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>서술 피드백 및 강평</label>
                <textarea rows={4} value={newEvalFeedback} onChange={e => setNewEvalFeedback(e.target.value)} placeholder="원생의 장점과 보완해야 할 구도/명도/채도 피드백을 서술하세요..." style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px', fontSize: '12px' }} />
              </div>
              <div style={{ background: '#0f172a', padding: '10px', borderRadius: '6px', border: '1px dashed #334155', textAlign: 'center', fontSize: '12px', color: '#94a3b8' }}>
                📁 실기 작품 비공개 스토리지 버킷 첨부 시뮬레이션 (자동 암호화)
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setEvalModalOpen(false)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddEvaluation} style={{ background: '#10b981', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>저장 및 학생 알림</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 수업 앨범 등록 ── */}
      {albumModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', width: '440px', color: '#fff' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>새 수업 앨범 사진 등록</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>대상 학급</label>
                <select value={newAlbumClass} onChange={e => setNewAlbumClass(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }}>
                  <option value="고3 입시정규A반">고3 입시정규A반</option>
                  <option value="고2 디자인예비반">고2 디자인예비반</option>
                  <option value="고1 기초소묘반">고1 기초소묘반</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>앨범 제목</label>
                <input type="text" value={newAlbumTitle} onChange={e => setNewAlbumTitle(e.target.value)} placeholder="예: 9월 주말 집중 특강 현장" style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px' }} />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>수업 설명 / 캡션</label>
                <textarea rows={3} value={newAlbumDesc} onChange={e => setNewAlbumDesc(e.target.value)} placeholder="활동 내용 및 수업 분위기 기록..." style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '8px', borderRadius: '6px', fontSize: '12px' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button onClick={() => setAlbumModalOpen(false)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={handleAddAlbum} style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>등록 완료</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 모달: 학원 정보 본사 변경 신청 ── */}
      {infoModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', width: '440px', color: '#fff' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px' }}>학원 기본정보 변경 신청</h3>
            <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '14px', lineHeight: 1.5 }}>
              사업자등록번호, 학원 주소, 대표자 정보 등 주요 법적 정보는 프랜차이즈 계약 무결성을 위해 본사(BO) 관리자 승인 후 반영됩니다.
            </p>
            <textarea
              rows={4}
              value={changeReqText}
              onChange={e => setChangeReqText(e.target.value)}
              placeholder="변경 요청 사항을 상세히 기재하세요 (예: 학원 확장 이전에 따른 소재지 주소 변경 신청)..."
              style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '10px', borderRadius: '6px', fontSize: '12px' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
              <button onClick={() => setInfoModalOpen(false)} style={{ background: '#334155', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>취소</button>
              <button onClick={() => { alert('본사에 기본정보 변경 승인 신청이 접수되었습니다.'); setInfoModalOpen(false); setChangeReqText(''); }} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>신청 제출</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
