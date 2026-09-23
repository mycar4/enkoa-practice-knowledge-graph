# ART:READY 프랜차이즈 플랫폼 통합테스트 시나리오 (v2.0)

> **작성일**: 2026-09-23
> **작성자**: Claude (엔코아 프로젝트 - ART:READY 지식그래프 서비스 담당)
> **수신**: GPT, Antigravity (동일 문서를 양쪽에 각각 전달 - 서로 독립적으로 실행시켜
> 결과를 교차 대조한다. 한쪽이 놓친 걸 다른 쪽이 잡아내는 경우가 실제로 있었다.)
> **목적**: v1.0(`franchise/ANTIGRAVITY_FULL_TEST_SCENARIOS_v1.0.md`, 41개 항목,
> 2026-09-21 작성) 이후 코드 감사로 새로 발견된 갭을 반영한 개정판. v1.0의 항목을
> 대체하는 게 아니라, **stale해진 2개 항목을 고치고 신규 5개 항목을 추가**한다.
> v1.0은 그대로 유효하므로 폐기하지 말 것 - 이번 라운드는 v1.0 전체 + 아래
> "0. 대상 시스템 명확화" + "6. 신규 항목"을 합쳐서 실행한다.

## 0. 대상 시스템 명확화 (반드시 먼저 읽을 것)

**이 저장소에는 두 개의 서로 다른 백엔드 구현이 존재한다.**

1. `franchise/api/` - FastAPI(Python) 백엔드. `bo.py`/`co.py`/`fo.py` 라우터
   전부 인증 의존성(`Depends(require_roles(...))`)을 **import만 하고 실제로는
   어디에도 걸지 않았고**, 조회 쿼리에도 `tenant_id`/`student_id` 필터가 전혀
   없다(모든 GET이 전체 테이블을 반환). `fo.py`는 아예 auth 모듈을 import하지도
   않는다.
2. `franchise/web/{bo,co,fo}/api/v1.ts` - Vercel 서버리스 함수(TypeScript),
   Supabase PostgREST/GoTrue와 직접 통신. 여기에 실제 로그인(`auth/signup`,
   `auth/login`), 전역 인증 게이트(§실제 프로덕션 코드 193~212행 부근), 테넌트/
   학생 스코핑이 구현되어 있다.

**실제 배포되어 사용자가 접근하는 것은 2번(`v1.ts`, Vercel)이다.** 1번은
스캐폴딩/구버전으로 보이며 인증·격리가 전혀 없다. **아래 모든 시나리오는
반드시 2번(실제 프로덕션 Vercel URL)에 curl로 실행한다.** 로컬에서
`franchise/api/`를 uvicorn으로 띄워 테스트하면 "전부 뚫려있다"는 잘못된
결론이 나온다 - 그건 애초에 서비스되지 않는 코드를 테스트한 것일 뿐이다.

```
BO: https://adminartreadykr.vercel.app
CO: https://partnerartreadykr.vercel.app
FO: https://appartreadykr.vercel.app
```

## 검증 원칙

1. **실제 프로덕션 URL에 curl로 직접 요청**(로컬/TestClient 금지).
2. **grep/문자열 매칭 금지** - 실제 HTTP status/body를 눈으로 확인.
3. 실행한 curl 명령 전문과 응답 전문을 그대로 보고서에 첨부.
4. 실패는 있는 그대로 FAIL로 보고 - 우회/은폐 금지.
5. 테스트 계정은 `-test@`/`.test.com` 접미사를 써서 나중에 식별·정리 쉽게 한다.

---

## 1~5. (v1.0 문서 그대로 실행)

`franchise/ANTIGRAVITY_FULL_TEST_SCENARIOS_v1.0.md`의 섹션 1~5(41개 항목)를
그대로 실행한다. 단, 아래 2개 항목은 **v1.0 문서의 "기대 결과"가 낡았으므로
이 문서의 값으로 대체해서 판정**한다(v1.0 파일 자체는 고치지 않았다 - 실행 시
이 문서를 기준으로 삼을 것).

### [갱신] 2.6 로그인 없이 성적 등록 시도

v1.0 원문은 "`HTTP:200`이 정상(설계상 폴백)"이라고 되어 있으나, 2026-09-21
전역 인증 게이트 도입 이후 이 기대값은 틀렸다.

```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/fo/grade-records" \
  -H "Content-Type: application/json" \
  -d '{"label":"비로그인 테스트"}'
```
**기대 결과(v2.0 정정)**: `HTTP:401`, "로그인이 필요합니다" 취지 에러.
`HTTP:200`이 나오면 **CRITICAL FAIL**(전역 인증 게이트가 무력화됐다는 뜻 -
남의 학생 데이터에 익명으로 쓰기가 가능하다는 사고가 재발한 것).

### [갱신] 2.10 읽기 전용 메뉴 확인

v1.0 원문은 "인증 헤더 없이 `HTTP:200`이 정상"이라고 되어 있으나 마찬가지로
낡았다.

```bash
for path in fo/evaluations fo/attendance fo/album fo/tuition fo/stats; do
  echo "=== $path ==="
  curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/$path"
done
```
**기대 결과(v2.0 정정)**: 전부 `HTTP:401`. 인증 헤더 없이 `HTTP:200`과 실제
데이터가 나오면 **CRITICAL FAIL**. (단, `fo/tenants/gangnam-main`처럼
`fo/tenants/*` 경로는 공개 화이트리스트라 인증 없이 `HTTP:200`이 나오는 게
정상이다 - 이건 여전히 v1.0 그대로 유효)

---

## 6. 신규 항목 (v2.0 추가)

### 6.1 [CRITICAL 후보] 원생 정보 크로스테넌트 IDOR - `co/students/{id}` PATCH/DELETE

코드 감사로 발견: `co/students` GET은 `getCurrentTenantId`로 테넌트 스코핑이
되어 있지만, 같은 파일의 `PATCH/DELETE co/students/{id}`는 `user_id=eq.{id}`
조건만 걸고 **테넌트 필터가 전혀 없다.** 즉 원장A가 원장B 학원 학생의
`user_id`(UUID)만 알면(또는 추측하면) 그 학생 프로필을 수정/삭제할 수 있는
구조로 보인다. 실제로 뚫리는지 직접 검증 필요.

```bash
# 사전 준비: 서로 다른 두 학원의 원장 토큰과, "학원B" 소속 학생의 user_id가 필요하다.
# DIRECTOR_A_TOKEN: v1.0의 1.6/1.7에서 만든 원장(안티그라비티테스트학원) 토큰
# TARGET_STUDENT_ID: v1.0의 1.3에서 만든 학생(gangnam-main 소속)의 user_id

curl -s -w "\nHTTP:%{http_code}\n" -X PATCH "https://partnerartreadykr.vercel.app/api/v1/co/students/$TARGET_STUDENT_ID" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $DIRECTOR_A_TOKEN" \
  -d '{"target_major":"해킹테스트-다른학원학생수정"}'

# 성공(200)했다면 실제로 학생 프로필이 바뀌었는지 재확인
curl -s "https://partnerartreadykr.vercel.app/api/v1/co/students" -H "Authorization: Bearer $STUDENT_A_LOGIN_TOKEN_OR_BO_TOKEN"
```
**기대 결과**: 다른 학원(gangnam-main) 소속 학생을, 그 학원 소속이 아닌
원장A의 토큰으로 수정할 수 있으면 안 된다. `HTTP:403`(권한 없음) 또는
`HTTP:404`(그 원장 입장에서는 존재하지 않는 학생으로 취급)가 나와야 정상.
**`HTTP:200`이 나오고 실제로 수정이 반영됐다면 CRITICAL FAIL**(다른
가맹학원의 학생 개인정보를 임의로 변조/삭제할 수 있는 심각한 테넌트 격리
결함). DELETE도 동일한 방식으로 반드시 같이 검증할 것(실제로 삭제해버리면
복구가 안 되므로, 먼저 PATCH로 격리 여부를 확인한 뒤 DELETE는 신중하게 -
가능하면 이번 테스트용으로 새로 만든 "희생양" 학생 계정으로만 DELETE를
시도한다).

### 6.2 정책 동의 기록(`POST policies`) 위조 user_id 허용 여부

`policies` 경로는 전역 인증 화이트리스트에 포함되어 있어(공개 조회가
필요해서), POST(동의 기록)까지 게이트를 안 거친다. 이 핸들러 자체가 세션을
별도로 검증하는지 확인 필요.

```bash
curl -s -w "\nHTTP:%{http_code}\n" -X POST "https://appartreadykr.vercel.app/api/v1/policies" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","policy_id":"(실제 존재하는 policy_documents.id)","agreed":true}'
```
**기대 결과**: 로그인 세션 없이 임의의(존재하지도 않는) `user_id`로 동의
기록이 실제로 저장되면 안 된다. `HTTP:401`이 나오거나, 최소한 `user_id`를
요청 바디가 아니라 검증된 세션에서만 가져와야 한다. 만약 `HTTP:200/201`과
함께 그 가짜 `user_id`로 `policy_agreements` 행이 실제로 생겼다면, 누구든
타인 명의로 "정책에 동의했다"는 허위 기록을 남길 수 있다는 뜻이므로
**FAIL로 보고**(악용 시나리오: 나중에 분쟁에서 "그 학생이 동의했다"는 조작된
근거로 쓰일 수 있음).

### 6.3 `bo/tenants/{id}/billing` 경로가 실제로 해당 테넌트만 반환하는지

URL 형태(`.../tenants/{id}/billing`)는 특정 테넌트 것만 보여줄 것처럼
보이지만, 코드상 이 경로도 `bo/billing`과 동일하게 전체 테넌트의 청구
데이터를 반환하는 것으로 보인다(BO는 원래 전체를 볼 수 있는 권한이라
보안 문제는 아니지만, API 계약이 URL과 실제 동작이 다르면 프론트가 오동작할
위험이 있다).

```bash
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/tenants/$TENANT_ID/billing" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과 확인 포인트**: 응답이 `$TENANT_ID` 것만 필터링돼 나오는지, 아니면
전체 테넌트의 청구 내역이 다 섞여 나오는지 실제로 확인해서 있는 그대로
보고할 것(어느 쪽이든 CRITICAL은 아니지만, 전체가 섞여 나온다면 "이 URL은
per-tenant처럼 보이지만 실제로는 아니다"를 명시적으로 기재).

### 6.4 학부모(PARENT) 계정으로 `fo/album` 접근 시 테넌트 해석

학부모는 `student_profiles` 행이 없다. `fo/album`이 내부적으로 호출자의
테넌트를 결정하는 로직이 학생이 아닌 사용자에게는 다르게 동작할 수 있는데,
그 경우 실제로 어느 학원 앨범이 나오는지 확인 필요(잘못하면 엉뚱한 학원
앨범이 보이거나, 아무 데이터도 못 찾아 전체 중 "첫 번째 테넌트"로 새는 등의
사고 가능성).

```bash
# PARENT_TOKEN: v1.0의 1.9에서 만든 학부모 계정(아직 어느 학생과도 연동 안 된 상태에서 먼저 시도)
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/album" -H "Authorization: Bearer $PARENT_TOKEN"

# 그 다음 2.7(자녀 연동)을 완료한 뒤 다시 조회
curl -s -w "\nHTTP:%{http_code}\n" "https://appartreadykr.vercel.app/api/v1/fo/album" -H "Authorization: Bearer $PARENT_TOKEN"
```
**기대 결과**: 자녀 연동 전에는 앨범이 비어있거나 명확한 에러(다른 학원
데이터가 섞이면 안 됨)가 나와야 하고, 연동 후에는 정확히 그 자녀가 다니는
학원의 앨범만 나와야 한다. 연동 전인데도 특정 학원의 실제 앨범 사진이
보인다면 **어느 학원인지 확인해서 FAIL로 보고**(테넌트 오판정 - 엉뚱한
학원 데이터 유출 가능성).

### 6.5 감사 로그(`bo/audit-logs`)가 6.1~6.4에서 발생한 쓰기 작업을 실제로 기록하는지

```bash
curl -s "https://adminartreadykr.vercel.app/api/v1/bo/audit-logs" -H "Authorization: Bearer $BO_TOKEN"
```
**기대 결과**: 6.1(성공했다면 학생 정보 변경)/6.3 같은 민감한 작업들이
감사 로그에 실제로 남아있는지 확인. 특히 6.1처럼 IDOR로 의심되는 쓰기가
성공했는데 감사 로그에 아무 흔적도 없다면, 사고가 나도 추적조차 안 된다는
뜻이므로 이 부분도 별도로 명시해서 보고할 것.

---

## 보고 형식

- v1.0 섹션 1~5: 각 섹션마다 통과 N/M, 실패 항목은 curl+응답 전문 첨부.
- **2.6/2.10은 이 문서(v2.0)의 기대값(401)으로 판정**(v1.0 원문 기준으로
  판정하면 낡은 기준을 쓴 것이므로 무효).
- 섹션 6(6.1~6.5) 전부 개별 PASS/FAIL로 나열 - 카테고리로 뭉뚱그려 요약하지
  말 것(과거 경험상 뭉뚱그리면 절반 가까이 누락됨).
- **CRITICAL FAIL 후보**: 1.10, 3.2/3.6, 5.2, 4.9(v1.0) + **6.1, 6.2**(v2.0
  신규) - 이 항목들은 실패 시 보고서 맨 위에 별도로 요약할 것.
