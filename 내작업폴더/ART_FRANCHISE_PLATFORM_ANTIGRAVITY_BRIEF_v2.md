# 🏫 ART:READY 프랜차이즈 B2B 플랫폼 — Antigravity 작업지시서 (v2.0)

> **작성일**: 2026-09-19
> **작성자**: Claude (프로젝트 - ART:READY 지식그래프 서비스 담당)
> **수신**: Antigravity (프랜차이즈/RDB 회원가입 플랫폼 별도 개발 담당)
> **상태**: **2단계(실 구현 착수 지시)** - v1.0 설계안 검토 완료, 이 문서 기준으로 바로 개발 착수
> **관계**: `ART_FRANCHISE_PLATFORM_ANTIGRAVITY_BRIEF.md`(v1.0)의 후속. v1.0은 최초 지시서였고,
> Antigravity가 제출한 1차 설계안(`franchise/ART_FRANCHISE_PLATFORM_DESIGN_v1.0.md`)을
> 검토한 뒤 발견한 구조적 공백 3가지를 **실제 완료된 유사 사례 분석으로 메워서** 이 문서에
> 구체적으로 반영했다. **이제부터는 추가 설계 라운드 없이 이 문서 기준으로 바로 구현 착수한다.**

---

## 0. 이 문서를 읽기 전에 (v1.0과 동일, 재확인)

1. 실행하지 않은 것을 "완료"라고 쓰지 않는다 - 매 산출물에 실제 실행 로그/캡처/curl 결과 첨부.
2. 수치를 지어내지 않는다.
3. 없는 승인/검증 절차를 있다고 쓰지 않는다.
4. 불확실하면 "확인 필요"로 정직하게 표시한다.

---

## 1. v1.0 설계안 검토 결과 — 왜 이 문서가 나왔나

Antigravity의 1차 설계안(ERD/RBAC/API초안/화면흐름)은 방향은 맞았으나 **구조적으로
3가지가 빠져 있었다**:

| 공백 | v1.0 설계안 상태 | 이 문서에서의 조치 |
|---|---|---|
| ① 플랫폼 운영사(엔코아) 계층 없음 | `TENANT_ADMIN`(학원장)이 최상위 역할이었음 - 엔코아가 여러 학원을 온보딩/정산/통제하는 화면 개념 자체가 없음 | 2절에 **BO(엔코아 통합관리자) 계층**을 별도 역할로 명시 |
| ② 권한이 역할(role) 단위뿐 | RLS가 `tenant_id`만 검사 - 같은 학원 안에서 강사가 자기 담당 아닌 학생을 볼 수 있는 등 개인 단위 격리가 안 됨(Claude가 이미 지적한 문제) | 4절에 **메뉴 단위 read/write 권한 테이블** 및 **개인 단위 RLS 정책 예시** 추가 |
| ③ 개인정보 처리 정책 관리 모듈 없음 | 이용약관/개인정보처리방침 등이 문서에 전혀 없었음(Claude가 이미 지적한 문제) | 5절에 **정책 문서 버전관리 테이블** 추가 |

이 3가지 공백은 임의로 지어낸 게 아니라, **실제로 완료되어 운영 중인 유사 B2B 프랜차이즈
플랫폼(타 업종, 학원 관리 SaaS)의 기획 산출물을 분석**해서 검증된 패턴만 가져온 것이다.
아래 매핑을 그대로 따를 것 - 이름만 우리 도메인에 맞게 바꾸면 된다.

### 1.1 도메인 용어 매핑

| 참고 사례 | ART:READY 프랜차이즈 |
|---|---|
| 태권도장 | 미술학원(지점) |
| 관장 | 학원장 |
| 사범 | 강사 |
| 수련생 | 학생 |
| 학부모 | 학부모 |
| 급수(띠) | 실기 레벨/등급(자유 설계) |
| 수업앨범(사진+코멘트) | 실기 작품 사진 + 강사 피드백 |
| 통합 Admin(BO) | 엔코아 통합 관리자 |
| 도장별 CO Admin | 학원별 관리자(학원장+강사) |

---

## 2. 시스템 계층 재정의 (3-Tier — 필수 반영)

```
[BO: 엔코아 통합 관리자]  ← 신규 추가, 필수
  ├── 학원(지점) 신규 승인/생성
  ├── 학원별 구독/정산 관리 (2.2 참고)
  ├── 부운영자(엔코아 내부 담당자: 영업/콘텐츠 등) 관리
  └── 정책 문서(약관 등) 버전 관리 (5절)
        │ (BO가 승인한 학원만 아래 CO가 활성화됨)
        ▼
[CO: 개별 학원 관리자]  ← v1.0의 TENANT_ADMIN 역할
  ├── 학원장(TENANT_ADMIN): 자기 학원 기본정보, 강사 초대/권한부여, 학생 명부, 학원 자체 결제내역 조회(읽기전용)
  └── 강사(INSTRUCTOR): 배정된 학생만 조회/평가 (메뉴 단위 권한으로 세분화)
        │
        ▼
[FO: 학생/학부모 앱]  ← v1.0과 동일
  ├── 학생(STUDENT)
  └── 학부모(PARENT, 자녀 정보 읽기 전용)
```

**역할 재정의**: 기존 4역할(학원장/강사/학생/학부모)에 **엔코아 내부용 역할(플랫폼 관리자,
필요시 영업담당/콘텐츠담당 등 세부 역할)**을 추가로 설계할 것 - 참고 사례처럼
"부운영자 구분(관리자/콘텐츠담당자/영업담당자)"을 하나의 역할 컬럼 값으로 확장 가능하게
설계(하드코딩 금지, ENUM 또는 코드테이블로).

---

## 3. ERD 갱신 사항 (v1.0 대비 추가/수정)

기존 v1.0의 `TENANTS`, `BRANCHES`, `USER_PROFILES`, `STUDENT_PROFILES`,
`INSTRUCTOR_STUDENT_MAPS`, `PARENT_STUDENT_MAPS`, `STUDENT_EVALUATIONS`,
`SUBSCRIPTIONS` 테이블 구조는 유지하되 아래를 반영/추가한다.

### 3.1 `TENANTS` 테이블 - 상태 필드 추가
```
status: PENDING(대기) | ACTIVE(운영중) | SUSPENDED(중지) | CLOSED(폐쇄)
contract_months: integer (약정기간, 예: 36)
```
**상태 전이 규칙(참고 사례 그대로 채택)**:
| 결제상태 | 허용되는 학원 상태 |
|---|---|
| 대기(최초 가입월) | PENDING만 가능 |
| 결제완료 | ACTIVE로 전환 가능 |
| 결제보류 | SUSPENDED로 전환 가능 |
| 정산완료 | CLOSED로 전환 가능 |
| 미납 | ACTIVE 유지(다음 결제 기다림) |

### 3.2 `SUBSCRIPTIONS` → `TENANT_BILLING`(월별 정산 이력)으로 확장
기존 `SUBSCRIPTIONS`(플랜/기간)는 계약 단위로 유지하고, **월별 결제 이력**을 별도 테이블로 추가:
```
TENANT_BILLING
  id PK, tenant_id FK
  billing_month (예: "2026-09")
  expected_amount (결제예정금액)
  manual_adjustment_amount (수기결제 조정액, +/- 가능)
  adjustment_reason (수기결제 사유 - 필수 기입)
  final_amount (최종결제금액)
  payment_status: PENDING | UNPAID | HELD | SETTLED | PAID
```
**"수기결제"는 반드시 사유(`adjustment_reason`)를 필수 입력받게 할 것** - 참고 사례에서
검증된 방식이며, 나중에 정산 분쟁 시 근거가 된다.

### 3.3 권한 테이블 신설 - `MENU_PERMISSIONS` (공백 ② 해결)
```
MENU_PERMISSIONS
  id PK
  user_id FK (USER_PROFILES.id)
  menu_key (예: "student.list", "student.evaluation", "billing.view")
  can_read boolean
  can_write boolean
```
- 학원장이 강사를 초대할 때, **메뉴별로 읽기/쓰기 권한을 개별 지정**할 수 있어야 한다
  (역할이 같은 INSTRUCTOR라도 강사마다 권한이 다를 수 있음).
- **RLS 정책은 `tenant_id` 체크만으로 끝내지 말 것.** `STUDENT_EVALUATIONS`,
  `STUDENT_PROFILES` 등 개인 데이터 테이블에는 추가로 다음 조건을 반드시 포함:
  ```sql
  -- 강사는 자기에게 배정된 학생만
  EXISTS (SELECT 1 FROM instructor_student_maps
          WHERE instructor_id = auth.uid() AND student_id = student_profiles.user_id)
  -- 학부모는 자기와 연결된 학생만
  OR EXISTS (SELECT 1 FROM parent_student_maps
          WHERE parent_id = auth.uid() AND student_id = student_profiles.user_id)
  ```

### 3.4 `STUDENT_PROFILES` - 상태 필드 추가
```
status: ACTIVE(재원중) | PROSPECTIVE(예비) | ON_LEAVE(휴원) | WITHDRAWN(탈원)
```

### 3.5 `ATTENDANCE`(출결), `TUITION_LEDGER`(학생별 수강료 납부) 테이블 신설
```
ATTENDANCE: id PK, tenant_id FK, student_id FK, class_date date, status(PRESENT|ABSENT)
TUITION_LEDGER: id PK, tenant_id FK, student_id FK, billing_month, status(PAID|UNPAID), due_day(납부기준일)
```

### 3.6 `CLASS_ALBUM`(실기 작품 앨범) 테이블 신설 - `STUDENT_EVALUATIONS`와 별개
참고 사례의 "수업앨범"에 해당 - 개별 학생 평가와 별개로, **수업 단위로 사진+코멘트를
기록**하는 기능(학생 여러 명이 같이 보는 수업 기록용):
```
CLASS_ALBUM
  id PK, tenant_id FK
  branch_id FK, instructor_id FK
  class_date, content_text (최대 200자 등 제한 검토)
  image_urls jsonb
```

### 3.7 `PARENT_STUDENT_MAPS` - 관계 구분 필드 추가
```
relationship: MOTHER | FATHER | GUARDIAN | OTHER
```
(참고 사례처럼 학생 1명에 학부모 여러 명이 등록 가능해야 함 - 어머니/아버지 각각)

### 3.8 `POLICY_DOCUMENTS` 테이블 신설 (공백 ③ 해결)
```
POLICY_DOCUMENTS
  id PK
  doc_type: TERMS(이용약관) | PRIVACY(개인정보취급방침) | THIRD_PARTY(제3자정보제공동의) | COLLECTION_CONSENT(개인정보수집및동의서)
  version varchar
  content text
  is_active boolean (사용자에게 노출 중인 현재 버전 여부, 같은 doc_type 중 하나만 true)
  created_at timestamptz
```
- BO에서 작성/버전관리하고, CO(학원장)는 **조회만** 가능(수정 불가 - 본사 정책이므로).
- 회원가입 시점에 현재 활성(`is_active=true`) 버전에 동의했다는 기록을 `USER_PROFILES`
  또는 별도 `POLICY_AGREEMENTS` 테이블에 남길 것(어떤 버전에 언제 동의했는지 추적 가능해야 함).
- **미성년자(학생 다수 해당) 개인정보 처리에 대한 법정대리인 동의 절차**: 개인정보보호법
  제22조의2는 **만 14세 미만** 아동의 개인정보 처리에 법정대리인 동의를 의무화한다.
  우리 서비스 대상(입시 준비 고등학생)은 대부분 만 15~19세라 이 조항이 강제 적용되는
  연령대가 아닐 가능성이 높지만, **최종 판단은 법률 검토 없이 이 문서가 확정하지 않는다.**
  다만 구현은 아래처럼 **연령 조건부로 동작하게** 만들어서, 나중에 법률 검토 결과에
  따라 기준 연령이나 강제 여부만 바꿔 끼울 수 있게 할 것:
  - `STUDENT_PROFILES`에 `birth_date` 필수 입력.
  - 가입 시점 나이가 설정값(기본 14세, 환경변수/설정 테이블로 조정 가능) 미만이면,
    `PARENT_STUDENT_MAPS`에 `VERIFIED` 상태인 학부모 연결이 있어야만 학생 계정을
    `ACTIVE`로 전환 - 그 전엔 `PENDING_GUARDIAN_CONSENT` 상태로 둠.
  - `POLICY_AGREEMENTS`에 학생 본인 동의와 별개로 `guardian_consent_at`(법정대리인
    동의 일시) 컬럼을 둬서 나중에 대상 연령이 바뀌어도 추적 가능하게 할 것.
  - **최종 기준 연령/강제 여부는 사용자(엔코아) 확정 전까지 "확인 필요"로 유지**하되,
    위 메커니즘 자체는 미리 구현해둔다.

### 3.9 개인정보 암호화 및 보관·파기 정책 (신규 - 이전 문서 누락분)

- **암호화**: 연락처(휴대폰번호), 실명, 생년월일, 주소 등 개인식별정보 컬럼은
  애플리케이션 레벨 암호화(예: Postgres `pgcrypto` 또는 Supabase Vault) 적용 검토.
  최소한 Supabase의 저장소 레벨 암호화(AES-256, 기본 제공)는 반드시 활성화된 상태로
  운영할 것 - 이건 별도 설정 없이 기본 적용되는지 Supabase 프로젝트 설정에서 확인하고
  결과를 보고할 것.
- **실기 이미지(`CLASS_ALBUM.image_urls`, `STUDENT_EVALUATIONS.image_urls`)**: 비공개
  버킷(Private Storage)에 저장하고, 접근 시 서명된 URL(signed URL, 짧은 만료시간)로만
  제공 - 공개 URL로 영구 노출하지 말 것.
- **보관기간 및 파기**:
  - 회원(학생/학부모/강사) 탈퇴 시: 개인식별정보는 **탈퇴 즉시 비식별화 처리**
    (이름/연락처 등을 마스킹하거나 삭제), 단 결제/정산 관련 기록은 전자상거래법 등
    관련 법령상 별도 보존의무 기간이 있을 수 있으므로 **삭제하지 말고 별도 보관** -
    정확한 보존 기간은 확인 필요로 남기되, 기본값은 5년으로 설계해둘 것(조정 가능하게).
  - 휴면 계정(장기 미접속) 처리 정책은 이번 단계에서 확정하지 않음 - 확인 필요.
  - 파기는 수동이 아니라 **정기 배치 작업**으로 처리해서 사람이 깜빡해서 안 지워지는
    일이 없게 할 것.

---

## 4. API 명세 추가분

기존 v1.0의 API 초안(`/api/v1/auth/*`, `/api/v1/tenants/*`, `/api/v1/dashboard/*`,
`/api/v1/evaluations`)은 유지하고 아래를 추가한다.

* `POST /api/v1/bo/tenants` (BO 전용) - 신규 학원 승인/생성
* `GET /api/v1/bo/tenants/{id}/billing` (BO 전용) - 학원별 월별 결제 이력 조회
* `POST /api/v1/bo/tenants/{id}/billing/manual-adjustment` (BO 전용) - 수기결제 조정(사유 필수)
* `PUT /api/v1/tenants/{id}/permissions/{user_id}` (TENANT_ADMIN 전용) - 강사 등 메뉴별 권한 설정
* `GET /api/v1/policies?type=TERMS` - 활성 정책 문서 조회 (공개, 인증 불필요)
* `POST /api/v1/students/{id}/attendance` - 출결 기록
* `POST /api/v1/class-albums` - 수업앨범 등록

---

## 5. 이번 단계에서 확정 안 하는 것 (v1.0과 동일하게 유지)

- 기존 지식그래프 서비스와의 연동 방식
- 결제/구독 PG(토스페이먼츠 등) 실연동 여부 (1차는 BO 수기 승인 방식으로 시작 권장 -
  참고 사례도 "수기결제" 기능이 있는 것으로 보아 완전 자동 PG 연동 없이도 운영 가능함이
  검증됨)
- 화이트라벨(독립 도메인) 지원 수준
- 미성년자 법정대리인 동의의 정확한 기준 연령·강제 여부(구현 메커니즘은 3.8절에 반영,
  최종 기준값만 확인 필요)
- 결제/정산 기록의 정확한 법정 보존기간(기본값 5년으로 설계, 3.9절 참고)
- 휴면 계정 처리 정책

---

## 6. 진행 절차 (변경)

**v1.0과 달리, 이 문서 승인 후 바로 구현 착수한다** (추가 설계안 제출 라운드 없음).
단, 아래는 계속 지킬 것:

1. 절대 금지사항(기존 서비스/Neo4j/배포파이프라인 격리, `franchise/` 전용 디렉토리)은
   v1.0 그대로 유지.
2. 매 기능 구현 단위(예: BO 학원 승인, CO 권한관리, 정책문서관리)마다 **실제 실행 결과**
   (마이그레이션 로그, API curl 응답, 화면 캡처)를 첨부해서 보고할 것.
3. RLS 정책은 배포 전 반드시 **다른 tenant/다른 학생 계정으로 실제 로그인해서 격리가
   되는지 실측 검증**하고 그 결과를 첨부할 것 - "정책을 작성했다"가 아니라 "실제로
   막히는지 확인했다"가 완료 기준이다.
