# ART:READY 프랜차이즈 플랫폼 전수테스트 시나리오 (v1.0)

> **작성일**: 2026-09-21
> **작성자**: Claude (엔코아 프로젝트 - ART:READY 지식그래프 서비스 담당)
> **수신**: Antigravity
> **목적**: BO/CO/FO 3개 사이트의 모든 CRUD 엔드포인트를 실제 프로덕션 환경에서
> curl로 직접 검증. 이 문서에 적힌 curl 명령을 그대로 실행하고, "기대 결과"와
> 실제 응답을 비교해서 하나라도 다르면 FAIL로 보고할 것.

## 검증 원칙 (반드시 지킬 것)

1. **로컬/TestClient 검증 금지**. 반드시 아래 실제 프로덕션 URL에 curl로 직접 요청한다.
   - BO: `https://adminartreadykr.vercel.app`
   - CO: `https://partnerartreadykr.vercel.app`
   - FO: `https://appartreadykr.vercel.app`
2. **grep/문자열 매칭으로 "확인됨" 판정 금지**. 반드시 실제 HTTP 응답의 status
   code와 body 내용을 눈으로 확인한다.
3. 각 항목마다 실제 실행한 curl 명령 전문과 실제 응답 전문을 보고서에 그대로
   붙여넣는다 - 요약하거나 "정상 확인"이라고만 쓰지 말 것.
4. 실패한 항목은 있는 그대로 FAIL로 보고한다 - 억지로 우회하거나 숨기지 않는다.
5. 이 문서에서 만든 테스트 계정/데이터는 실제 프로덕션 DB에 남는다. 테스트
   완료 후 정리 방법은 문서 맨 아래 "정리" 섹션 참고.

## 사전 준비

```bash
# 아래 값들을 테스트 전체에서 재사용한다 (매번 새로 생성하지 말 것)
STUDENT_EMAIL="antigravity-test-student@artready-test.com"
STUDENT_PW="TestPass1234!"
PARENT_EMAIL="antigravity-test-parent@artready-test.com"
PARENT_PW="TestPass1234!"
DIRECTOR_EMAIL="antigravity-test-director@artready-test.com"
DIRECTOR_PW="TestPass1234!"
INSTRUCTOR_EMAIL="antigravity-test-instructor@artready-test.com"
INSTRUCTOR_PW="TestPass1234!"
```

---

## 1. 회원가입/로그인 (auth/*) - 모든 사이트 공통 API

### 1.1 학생 회원가입 (academy_code 없이 - 실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$STUDENT_EMAIL"'","password":"'"$STUDENT_PW"'","name":"테스트학생","role":"STUDENT","birth_date":"2009-01-01"}'
```
**기대 결과**: `HTTP:400`, `{"error":"학생 회원가입에는 유효한 소속 학원 가맹 코드가 필요합니다."}`

### 1.2 학생 회원가입 (실존하지 않는 academy_code - 실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$STUDENT_EMAIL"'","password":"'"$STUDENT_PW"'","name":"테스트학생","role":"STUDENT","birth_date":"2009-01-01","academy_code":"존재안하는코드"}'
```
**기대 결과**: `HTTP:404`, `가맹 코드 '존재안하는코드'에 해당하는 학원을 찾을 수 없습니다.`

### 1.3 학생 회원가입 성공 (실존 코드: `gangnam-main`)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$STUDENT_EMAIL"'","password":"'"$STUDENT_PW"'","name":"테스트학생","role":"STUDENT","birth_date":"2009-01-01","academy_code":"gangnam-main"}'
```
**기대 결과**: `HTTP:201`, `status:"success"`, `profile_status:"ACTIVE"`, `guardian_consent_required:false`, `tenant_id`가 실제 UUID로 채워짐

### 1.4 만 14세 미만 학생 회원가입 (보호자 동의 대기 상태 확인)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"antigravity-test-minor@artready-test.com","password":"'"$STUDENT_PW"'","name":"미성년테스트","role":"STUDENT","birth_date":"2015-01-01","academy_code":"gangnam-main"}'
```
**기대 결과**: `HTTP:201`, `profile_status:"PENDING_GUARDIAN_CONSENT"`, `guardian_consent_required:true`

### 1.5 중복 이메일 회원가입 (실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$STUDENT_EMAIL"'","password":"'"$STUDENT_PW"'","name":"중복테스트","role":"STUDENT","academy_code":"gangnam-main"}'
```
**기대 결과**: 4xx 에러 (이미 등록된 이메일이라는 취지의 에러 메시지)

### 1.6 원장(TENANT_ADMIN) 자체 학원 신규 등록
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$DIRECTOR_EMAIL"'","password":"'"$DIRECTOR_PW"'","name":"테스트원장","role":"TENANT_ADMIN","academy_name":"안티그라비티테스트학원"}'
```
**기대 결과**: `HTTP:201`, `created_new_tenant:true`, `tenant_id`가 새로 생성된 UUID. **이 tenant_id를 기록해두고 이후 CO 테스트에서 재사용한다.**

### 1.7 원장 로그인 및 소속 학원 slug 확인
```bash
curl -s -X POST "https://partnerartreadykr.vercel.app/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$DIRECTOR_EMAIL"'","password":"'"$DIRECTOR_PW"'"}'
# 응답의 access_token을 DIRECTOR_TOKEN 변수로 저장해서 이후 CO 테스트에 사용
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/profile" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: 로그인 응답에 `profile.role == "TENANT_ADMIN"`, `access_token` 존재. `co/profile` 응답의 `name`이 "안티그라비티테스트학원"과 일치(다른 학원이 섞여 나오면 FAIL).

### 1.8 강사(INSTRUCTOR) 회원가입 - 원장이 만든 학원에 합류
```bash
# 1.7에서 확인한 co/profile의 slug 값을 ACADEMY_SLUG로 사용
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$INSTRUCTOR_EMAIL"'","password":"'"$INSTRUCTOR_PW"'","name":"테스트강사","role":"INSTRUCTOR","academy_code":"'"$ACADEMY_SLUG"'"}'
```
**기대 결과**: `HTTP:201`, `tenant_id`가 1.6에서 만든 tenant_id와 동일

### 1.9 학부모(PARENT) 회원가입 - academy_code 없이도 성공해야 함
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$PARENT_EMAIL"'","password":"'"$PARENT_PW"'","name":"테스트학부모","role":"PARENT"}'
```
**기대 결과**: `HTTP:201`, `tenant_id:null` (학부모는 학원 소속이 없어도 됨)

### 1.10 BO_ADMIN self-signup 시도 (반드시 실패해야 함 - 보안 검증)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://adminartreadykr.vercel.app/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"fake-bo-admin@evil.com","password":"'"$STUDENT_PW"'","name":"해커","role":"BO_ADMIN"}'
```
**기대 결과**: 회원가입은 성공하더라도(`role` 파라미터가 무시됨) 생성된 계정의 실제 role이 **"STUDENT"** 여야 한다(role 값을 서버가 무시하고 기본값으로 강등시켰는지 확인). `role="BO_ADMIN"`으로 실제 생성됐다면 심각한 보안 결함이므로 **CRITICAL FAIL**로 별도 보고.

### 1.11 잘못된 비밀번호 로그인
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$STUDENT_EMAIL"'","password":"WrongPassword123"}'
```
**기대 결과**: `HTTP:400`, 로그인 실패 에러 메시지 (200이 나오면 FAIL)

---

## 2. FO(학생/학부모) CRUD

> 아래는 1.3에서 만든 학생 계정으로 로그인한 `STUDENT_TOKEN`을 사용한다.

### 2.1 성적 기록함 등록 (POST)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"label":"전수테스트 성적1","source_type":"manual","parsed_json":{"korean":1,"english":2}}'
```
**기대 결과**: `HTTP:200`, 응답의 `student_id`가 로그인한 학생의 실제 user_id와 일치(다른 학생 id나 `00000000-...`같은 가짜 값이면 FAIL)

### 2.2 성적 기록함 목록 조회 (GET) - 2.1에서 만든 게 보이는지
```bash
curl -s "https://appartreadykr.vercel.app/api/v1/fo/grade-records" -H "Authorization: Bearer $STUDENT_TOKEN"
```
**기대 결과**: 배열에 2.1에서 만든 레코드 포함

### 2.3 대표 성적 지정 (PATCH)
```bash
RECORD_ID="(2.1 응답의 id)"
curl -s -w "\nHTTP:%{http_code}\n" -X PATCH "https://appartreadykr.vercel.app/api/v1/fo/grade-records/$RECORD_ID/primary" \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```
**기대 결과**: `HTTP:200`, `status:"success"`

### 2.4 성적 기록 삭제 (DELETE)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X DELETE "https://appartreadykr.vercel.app/api/v1/fo/grade-records/$RECORD_ID" \
  -H "Authorization: Bearer $STUDENT_TOKEN"
# 삭제 후 재조회해서 실제로 없어졌는지 확인
curl -s "https://appartreadykr.vercel.app/api/v1/fo/grade-records" -H "Authorization: Bearer $STUDENT_TOKEN"
```
**기대 결과**: 삭제 응답 `HTTP:200`, 재조회 시 해당 id가 배열에서 사라짐

### 2.5 서류함 등록/조회/삭제 (2.1~2.4와 동일 패턴)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/documents" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"label":"전수테스트 자소서","doc_type":"자기소개서"}'
curl -s "https://appartreadykr.vercel.app/api/v1/fo/documents" -H "Authorization: Bearer $STUDENT_TOKEN"
```
**기대 결과**: POST `HTTP:200`이고 `student_id`가 실제 로그인 사용자와 일치. GET에 방금 만든 문서 포함.

### 2.6 로그인 없이 성적 등록 시도 (세션 없을 때 안전하게 처리되는지)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Content-Type: application/json" \
  -d '{"label":"비로그인 테스트"}'
```
**기대 결과**: 이 API는 로그인이 없으면 DB의 "첫 번째 학생"에게 임시로 붙는 폴백 동작을 한다(설계상 의도됨 - 로그인 세션이 없을 때의 하위호환 폴백). `HTTP:200`이 나오면 정상이며, `student_id`가 어떤 값이든 채워져 있으면 됨. 다만 이 동작이 실제 서비스에서 바람직한지는 별도 논의 필요 항목으로 보고에 남길 것(FAIL은 아님, 참고사항으로 기재).

### 2.7 부모-자녀 연동 신청 (자녀 이메일 기반)
```bash
# PARENT_TOKEN은 1.9 계정으로 로그인해서 얻는다
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/parent-link" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $PARENT_TOKEN" \
  -d '{"student_email":"'"$STUDENT_EMAIL"'","relationship":"MOTHER"}'
```
**기대 결과**: `HTTP:200`, `linked:true`, `student_name:"테스트학생"`

### 2.8 존재하지 않는 학생 이메일로 연동 시도 (실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/parent-link" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $PARENT_TOKEN" \
  -d '{"student_email":"존재안함@nowhere.com","relationship":"MOTHER"}'
```
**기대 결과**: `HTTP:404`, "학생 계정을 찾을 수 없습니다" 취지 에러

### 2.9 부모-자녀 연동 목록 재조회
```bash
curl -s "https://appartreadykr.vercel.app/api/v1/fo/parent-link" -H "Authorization: Bearer $PARENT_TOKEN"
```
**기대 결과**: 2.7에서 만든 연동 관계 포함

### 2.10 읽기 전용 메뉴 확인 (evaluations/attendance/album/tuition/tenants/:slug/stats)
```bash
for path in fo/evaluations fo/attendance fo/album fo/tuition fo/stats; do
  echo "=== $path ==="
  curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/$path"
done
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/tenants/gangnam-main"
```
**기대 결과**: 전부 `HTTP:200`, 컬럼명 오류(`column ... does not exist`) 절대 없어야 함

---

## 3. CO(원장/강사) CRUD

> `DIRECTOR_TOKEN`(1.7) 사용. `TENANT_ID`는 1.6 응답값.

### 3.1 지점 등록 (POST)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/co/branches" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_TOKEN" \
  -d '{"branch_name":"전수테스트 2호점","address":"서울시 서초구"}'
```
**기대 결과**: `HTTP:201`, `tenant_id`가 `$TENANT_ID`와 일치

### 3.2 지점 목록 조회 - 다른 학원의 지점이 섞여 나오면 FAIL
```bash
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/branches" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: 3.1에서 만든 지점만 나옴 (다른 테스트 학원의 지점이 보이면 tenant 격리 실패 - CRITICAL FAIL)

### 3.3 학원 통계 (co/stats) - 실제 집계값인지 확인
```bash
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/stats" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: `active_students`가 실제로 이 학원에 가입한 학생 수(1.8에서 강사만 가입했다면 학생은 0명)와 일치. 48/6/38400000 같은 예전 고정값이 나오면 FAIL.

### 3.4 학원 소개 페이지 수정
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X PUT "https://partnerartreadykr.vercel.app/api/v1/co/profile" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_TOKEN" \
  -d '{"name":"안티그라비티테스트학원(수정)","intro_text":"전수테스트로 수정한 소개글"}'
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/profile" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: PUT `HTTP:200`, 재조회 시 name이 "안티그라비티테스트학원(수정)"으로 바뀌어 있음

### 3.5 강사 권한 매트릭스 저장/조회
```bash
INSTRUCTOR_USER_ID="(1.8 응답의 user_id)"
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/co/permissions" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_TOKEN" \
  -d '{"user_id":"'"$INSTRUCTOR_USER_ID"'","tenant_id":"'"$TENANT_ID"'","menu_key":"student.evaluation","can_read":true,"can_write":true}'
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/permissions?user_id=$INSTRUCTOR_USER_ID" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: POST `HTTP:200`, GET 결과에 방금 저장한 권한 포함. 같은 menu_key로 다시 POST하면(can_write를 false로 바꿔서) 새 행이 추가되는 게 아니라 기존 행이 업데이트되어야 함(uq_user_menu 유니크 제약 - 중복 행 생기면 FAIL).

### 3.6 학부모 연동 현황 조회 (원장 시점)
```bash
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/parent-links" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: `HTTP:200`, 배열(이 학원 소속 학생의 부모 연동 현황). gangnam-main 학원 테스트(2.7)의 연동 건은 안 보여야 함(다른 tenant이므로) - 섞여 보이면 FAIL.

### 3.7 출결/평가/앨범/수강료 CRUD (student_id/tenant_id 필수 검증)
```bash
for path in co/attendance co/evaluations co/album co/tuition; do
  echo "=== GET $path ==="
  curl -s -w "\nHTTP:%{http_code}\n" "https://partnerartreadykr.vercel.app/api/v1/$path" -H "Authorization: Bearer $DIRECTOR_TOKEN"
done
# POST는 이 학원에 학생이 최소 1명 있어야 성공한다(getPlaceholderContext가 그 학원 학생을 못 찾으면
# 409 에러를 반환하는 게 정상 동작이다 - 500/크래시가 나면 FAIL)
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/co/attendance" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_TOKEN" \
  -d '{"status":"PRESENT"}'
```
**기대 결과**: GET 4종 모두 `HTTP:200`이고 컬럼 에러 없음. POST는 이 테스트 학원에 학생이 없으므로 `HTTP:409`와 "학생 데이터가 아직 없습니다" 취지 에러가 나오는 게 **정상**(크래시나 500이 아니라 이 명확한 에러가 나와야 PASS).

### 3.8 원생 등록 시도 (설계상 501이 나와야 함 - 회원가입 플로우 없이는 불가)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://partnerartreadykr.vercel.app/api/v1/co/students" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_TOKEN" \
  -d '{"target_major":"디자인학부"}'
```
**기대 결과**: `HTTP:501`, "회원가입(Supabase Auth) 절차를 거쳐야" 취지 에러. **200/201이 나오면 FAIL**(가짜 학생이 생성된 것).

---

## 4. BO(본사관리자) CRUD

> `bo-admin@artready.kr` / (Claude가 세션 중 생성한 비밀번호, 사용자에게 확인) 로 로그인해서 `BO_TOKEN` 획득. 또는 새 BO_ADMIN 계정을 아래로 부트스트랩:
```bash
curl -s -X POST "https://adminartreadykr.vercel.app/api/v1/bo/admins" \
  -H "Content-Type: application/json" \
  -d '{"email":"antigravity-bo-test@artready.kr","password":"BoTestPass1234!","name":"안티그라비티BO","role":"BO_MANAGER"}'
```

### 4.1 가맹학원 목록 조회
```bash
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/tenants" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: `HTTP:200`, 1.6에서 만든 "안티그라비티테스트학원" 포함

### 4.2 가맹학원 상태 변경 (승인)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X PATCH "https://adminartreadykr.vercel.app/api/v1/bo/tenants/$TENANT_ID/status" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"status":"ACTIVE"}'
```
**기대 결과**: `HTTP:200`

### 4.3 가맹학원 공개 게시 승인
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X PATCH "https://adminartreadykr.vercel.app/api/v1/bo/tenants/$TENANT_ID/publish" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"is_public_published":true}'
curl -s "https://appartreadykr.vercel.app/api/v1/fo/tenants/$ACADEMY_SLUG"
```
**기대 결과**: PATCH `HTTP:200`. FO 소개 페이지 조회 시 `is_public_published:true` 반영

### 4.4 수기결제 조정 (사유 5자 미만 - 실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://adminartreadykr.vercel.app/api/v1/bo/tenants/$TENANT_ID/billing/manual-adjustment" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"adjustment_reason":"짧음","manual_adjustment_amount":10000}'
```
**기대 결과**: `HTTP:400`, "수기결제 사유는 최소 5자 이상" 에러

### 4.5 수기결제 조정 성공
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://adminartreadykr.vercel.app/api/v1/bo/tenants/$TENANT_ID/billing/manual-adjustment" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"adjustment_reason":"전수테스트 수기조정 사유입니다","manual_adjustment_amount":10000,"billing_month":"2026-09"}'
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/billing" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: POST `HTTP:200`, GET에 방금 만든 조정 내역 포함

### 4.6 권한 매트릭스 (bo/permissions)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://adminartreadykr.vercel.app/api/v1/bo/permissions" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"user_id":"'"$INSTRUCTOR_USER_ID"'","tenant_id":"'"$TENANT_ID"'","menu_key":"billing.view","can_read":true,"can_write":false}'
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/permissions?user_id=$INSTRUCTOR_USER_ID" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: 3.5와 동일한 menu_permissions 테이블 사용하므로 결과에 3.5에서 넣은 것 + 이번에 넣은 것 둘 다 보여야 함

### 4.7 감사 로그 (bo/audit-logs) - **선행 조건**: `franchise/schema/03_v7_audit_logs.sql` 마이그레이션이 Supabase에 적용되어 있어야 함
```bash
curl -s -w "\nHTTP:%{http_code}\n" "https://adminartreadykr.vercel.app/api/v1/bo/audit-logs" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: `HTTP:200`. 마이그레이션이 적용되어 있다면 위 4.1~4.6에서 실행한 액션들(TENANT_STATUS_CHANGE, TENANT_PUBLISH_TOGGLE, PERMISSION_UPDATED 등)이 실제로 기록되어 있어야 한다. 마이그레이션 미적용 시 빈 배열 `[]`이 나오는 것은 정상(크래시가 아니라 빈 배열로 안전하게 처리되는지가 핵심 확인 포인트).

### 4.8 공지사항 등록/조회
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://adminartreadykr.vercel.app/api/v1/bo/notices" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BO_TOKEN" \
  -d '{"title":"전수테스트 공지","content":"테스트 공지 내용입니다","target_role":"ALL"}'
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/notices" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: POST `HTTP:201`, GET에 포함

### 4.9 본사 관리자 계정 목록 (실제 로그인 가능한 계정만 보이는지)
```bash
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/admins" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: BO_ADMIN/BO_MANAGER role의 실제 user_profiles 행만 나열됨(비밀번호 필드는 절대 포함되면 안 됨 - 포함되어 있으면 CRITICAL FAIL)

---

## 5. 교차 검증 (Cross-cutting)

### 5.1 로그인 세션 위조 시도 - 남의 access_token 없이 Authorization 헤더 조작
```bash
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer 아무렇게나-조작한-가짜토큰"
```
**기대 결과**: 가짜 토큰은 Supabase Auth 검증에서 무효 처리되어 로그인 안 한 것과 동일하게 처리되어야 한다(크래시하면 FAIL). `HTTP:200`(폴백 동작)이 나오는 건 정상.

### 5.2 다른 학원 학생 데이터 접근 시도 (tenant 격리)
```bash
# 원장A(TENANT_ADMIN, 1.6/1.7)의 토큰으로 다른 학원(gangnam-main)의 branches를 볼 수 있는지 확인
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/branches" -H "Authorization: Bearer $DIRECTOR_TOKEN"
```
**기대 결과**: 자기 학원(안티그라비티테스트학원) 소속 지점만 보여야 하고, gangnam-main의 지점 데이터가 섞여 나오면 **CRITICAL FAIL**(테넌트 격리 실패 - 다른 가맹점 데이터 유출).

### 5.3 프로덕션 번들에 localhost 하드코딩 재발 여부
```bash
for url in https://adminartreadykr.vercel.app https://partnerartreadykr.vercel.app https://appartreadykr.vercel.app; do
  html=$(curl -s "$url")
  js=$(echo "$html" | grep -oE 'src="/assets/[^"]*\.js"' | head -1 | sed 's/src="//;s/"$//')
  echo "=== $url ==="
  curl -s "$url$js" | grep -o "localhost:[0-9]*" || echo "없음(정상)"
done
```
**기대 결과**: 3개 사이트 모두 "없음"

---

## 정리 (테스트 종료 후)

이 문서로 만든 테스트 계정/데이터는 실제 프로덕션에 남습니다. 완료 후 Claude
또는 사용자에게 삭제를 요청하거나, 아래처럼 이메일에 `artready-test.com` /
`-test@artready.kr` 접미사를 써서 나중에 일괄 식별/삭제가 쉽게 해주세요(이미
위 시나리오가 그렇게 되어 있음).

## 보고 형식

각 섹션(1~5)마다:
- 통과: N/M개 항목
- 실패 항목: 실제 실행한 curl과 실제 응답 전문 첨부
- CRITICAL FAIL로 표시된 항목(1.10, 3.2/3.6, 5.2, 4.9)은 별도로 맨 위에 요약
