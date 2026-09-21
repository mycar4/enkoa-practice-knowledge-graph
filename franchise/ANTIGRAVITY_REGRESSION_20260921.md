# ART:READY 프랜차이즈 - 2026-09-21 보안 결함 수정 회귀 재검증 요청

> **수신**: GPT (Antigravity)
> **목적**: 지난 회귀 테스트에서 발견한 CRITICAL 결함 1건(fo/grade-records 학생
> 데이터 격리)을 수정했고, 같은 파일을 검토하며 추가로 3건을 더 발견해서 함께
> 수정했다. 아래 4건 전부 실제 프로덕션 URL에 curl로 재검증할 것.

## 검증 원칙 (기존과 동일, 반드시 지킬 것)

1. 로컬/TestClient 검증 금지 - 실제 프로덕션 URL(`https://appartreadykr.vercel.app`)에 curl 직접 요청
2. grep/문자열 매칭으로 "확인됨" 판정 금지 - 실제 HTTP status code + body 전문 확인
3. 실행한 curl 명령 전문 + 실제 응답 전문을 보고서에 그대로 붙여넣을 것
4. 실패는 있는 그대로 FAIL 보고 - 우회/은폐 금지
5. 테스트로 만든 레코드는 검증 후 삭제(DELETE)까지 마칠 것

## 사전 준비 - 서로 다른 학생 2명 필요 (격리 테스트용)

```bash
STUDENT_A_EMAIL="antigravity-test-student@artready-test.com"
STUDENT_A_PW="TestPass1234!"
STUDENT_B_EMAIL="antigravity-test-student-2@artready-test.com"
STUDENT_B_PW="TestPass1234!"
# academy_code는 기존 문서(ANTIGRAVITY_FULL_TEST_SCENARIOS_v1.0.md)의 "gangnam-main" 재사용
```
두 계정 모두 없으면 `POST /api/v1/auth/signup` (role=STUDENT, academy_code="gangnam-main")으로
새로 만들고, 각각 `POST /api/v1/auth/login`으로 토큰(TOKEN_A, TOKEN_B)을 받는다.

---

## 1. fo/grade-records 학생 데이터 격리 (신규 수정 - 원래 FAIL이었던 것)

### 1.1 학생 A로 성적 등록
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"label":"regression-A-20260921"}'
```

### 1.2 학생 B로 성적 등록
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer $TOKEN_B" -H "Content-Type: application/json" \
  -d '{"label":"regression-B-20260921"}'
```

### 1.3 학생 A로 조회 - 반드시 본인 것만 나와야 함
```bash
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer $TOKEN_A"
```
**합격 기준**: 응답 배열에 `label:"regression-A-20260921"`만 있어야 함. `regression-B-20260921`가
하나라도 보이면 FAIL(원래 버그 그대로).

---

## 2. PATCH .../primary 가 다른 학생 레코드에 영향 주는지 (신규 발견 결함)

### 2.1 학생 A가 자기 레코드를 대표로 지정
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X PATCH "https://appartreadykr.vercel.app/api/v1/fo/grade-records/<1.1에서 받은 id>/primary" \
  -H "Authorization: Bearer $TOKEN_A"
```

### 2.2 학생 B로 자기 목록 조회 - B의 대표 지정 상태가 그대로여야 함
```bash
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer $TOKEN_B"
```
**합격 기준**: 2.1(학생 A의 조작) 이후에도 학생 B 레코드의 `is_primary` 값이 2.1 실행 전과
동일해야 함(영향 없어야 함). 바뀌었으면 FAIL.

---

## 3. DELETE 소유권 확인 (IDOR - 신규 발견 결함)

### 3.1 학생 A가 학생 B의 레코드 id로 삭제 시도 (실패해야 함)
```bash
curl -s -w "\nHTTP:%{http_code}\n" -X DELETE "https://appartreadykr.vercel.app/api/v1/fo/grade-records/<1.2에서 받은 학생 B의 id>" \
  -H "Authorization: Bearer $TOKEN_A"
```

### 3.2 학생 B로 조회 - 자기 레코드가 그대로 남아있어야 함
```bash
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Authorization: Bearer $TOKEN_B"
```
**합격 기준**: 3.1 응답 status와 무관하게, 3.2에서 학생 B의 `regression-B-20260921` 레코드가
그대로 존재해야 함(삭제되면 안 됨). 사라졌으면 FAIL(IDOR 재발).

---

## 4. fo/documents - 동일한 3가지(격리/PATCH 없음이라 격리+DELETE만) 반복

3.1~3.2와 동일한 절차를 `POST/GET/DELETE /api/v1/fo/documents`에도 반복 (PATCH는 없음).

---

## 5. 기존 통과 항목 회귀 확인 (지난번 PASS, 이번에도 유지되는지만 짧게)

- 위조 토큰(`Authorization: Bearer forged-token-regression-test`)으로 `GET /api/v1/fo/grade-records` → `HTTP:401` 유지 확인
- `GET /api/v1/co/evaluations` → `HTTP:200`, PGRST201 에러 없음 유지 확인

---

## 정리
테스트로 만든 모든 grade-records/documents 레코드는 각 소유 학생 토큰으로 DELETE해서 정리할 것.
