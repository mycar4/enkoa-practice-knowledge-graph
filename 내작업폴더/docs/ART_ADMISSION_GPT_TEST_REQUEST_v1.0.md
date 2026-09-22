# GPT에게 그대로 전달할 요청문

아래 **14개 항목을 하나도 빠짐없이, 번호 순서대로** 실제 프로덕션 URL
(`https://api.unsuzone.com/art-admission`)에 curl로 직접 실행해줘. 카테고리로
뭉쳐서 요약하지 말고, **번호마다 개별로** curl 명령 + 실제 응답(원문 그대로) +
"기대 결과"와 대조한 PASS/FAIL을 표로 남겨줘.

**주의사항**:
- TestClient/로컬 mock 쓰지 말고 반드시 실제 프로덕션 URL로 curl 실행할 것.
- 한글 쿼리는 `--data-binary '@-'` 방식(파이프로 JSON 넘기기)으로 보낼 것 - 직접
  `-d` 옵션에 한글을 넣으면 인코딩이 깨질 수 있음.
- 응답이 길면 앞부분만 보고 판단하지 말고 `answer` 필드 전체와 `tool_trace`/
  `self_check_warnings`/`routing` 필드까지 확인할 것.
- 이 문서는 2026-09-22~23 세션에서 고친 버그들의 회귀 테스트다 - "예전엔 이랬는데
  지금은 이래야 한다"는 항목이 대부분이니, 옛날 동작(예전 버그)이 나오면 FAIL이다.

## 체크리스트 (14개 전부)

### 1. 라우팅 정확성 (Jev Choice 통합)
- [ ] 1.1 `POST /agent-chat` `{"query":"자기소개서 대필하면 걸리나요?"}` →
      기대: `tool_trace`에 `redirect_to_document_review`, 답변에 review.html 링크
- [ ] 1.2 `POST /agent-chat` `{"query":"국어 3등급인데 어디 찔러야 해?"}` →
      기대: `tool_trace`에 `recommend_by_grades` 포함
- [ ] 1.3 `POST /qa` `{"query":"가천대학교 회화전공 실기전형 알려줘"}` →
      기대: 정상 답변, `context_tracks`에 가천대 회화전공 포함

### 2. 실기호환 vs 커리큘럼유사 구분 (오라우팅 버그 수정)
- [ ] 2.1 `POST /agent-chat` `{"query":"한국예술종합학교 무대미술과와 같은 실기로 지원 가능한 학교는?"}` →
      기대: `tool_trace`에 `find_compatible_exam_tracks` 포함(❌ `find_similar_departments`만 있으면 FAIL),
      답변에 실기유형이 실제로 일치하는 학교가 10개 이상 나열
- [ ] 2.2 `POST /agent-chat` `{"query":"중앙대학교 공간연출전공이랑 성격이 비슷한 학과 있어?"}` →
      기대: `tool_trace`에 `find_similar_departments` 포함, 결과에 `source_url`이 빈 값이
      아님(❌ null이면 FAIL - 원문 링크 누락 버그 재발)

### 3. 학교 미지정 세부질문 (컨텍스트 희석 버그 수정)
- [ ] 3.1 `POST /qa` `{"query":"실기고사 당일 반입금지 물품이 뭐야?"}` (학교명 없음) →
      기대: 특정 학교 기준으로라도 구체적인 반입금지 물품 목록이 나와야 함
      (❌ "확인하지 못했습니다"면 FAIL)

### 4. 504 타임아웃 재현 여부 (N+1 쿼리 수정)
- [ ] 4.1 `POST /agent-chat` `{"query":"이 서비스는 뭐야? 왜 만들어짐? 뭐가 좋아?"}` →
      **응답 시간을 반드시 측정**(`curl -w "time:%{time_total}s"`) - 기대: HTTP 200,
      30초 이내 응답(❌ 504나 30초 초과면 FAIL - 예전엔 60초 타임아웃 나던 질문)

### 5. 호환학교 자기검증 오탐 (Jev 정밀도 수정)
- [ ] 5.1 `POST /qa` `{"query":"소묘로 지원 가능한 학교 알려줘"}` →
      기대: `self_check_warnings` 필드가 없거나 빈 배열(❌ "환각 의심"류 경고 있으면 FAIL -
      정상 답변인데 오탐 나던 버그)
- [ ] 5.2 `POST /agent-chat` `{"query":"국어 3등급, 영어 2등급, 사회 3등급인데 기초디자인 준비중이야. 어디 지원 가능해?"}` →
      기대: `self_check_warnings` 없음

### 6. 기출문제 연동
- [ ] 6.1 `POST /qa` `{"query":"중앙대학교 공간연출전공 작년 기출문제가 뭐였어?"}` →
      기대: 2025학년도 기출 내용("소묘(공간구성과 묘사)")이 구체적으로 나오고 몇 학년도
      기출인지 명시됨(❌ "확인하지 못했습니다"면 FAIL)

### 7. RAPTOR 라우팅 확장
- [ ] 7.1 `POST /agent-chat` `{"query":"홍익대학교 미술대학 전반적으로 어떤 분위기야?"}` →
      기대: `tool_trace`에 `summarize_admission_flow` 포함, 여러 절차를 관통하는
      개괄적 답변(❌ 단편적 사실 하나만 나오면 FAIL)

### 8. 히스토리 오염 (멀티턴 컨텍스트)
- [ ] 8.1 `POST /agent-chat` `{"query":"중앙대학교 공간연출전공과 실기 유형이 호환되는 학과는?"}` 먼저
      호출해서 답변을 받은 뒤, 그 답변을 `history`에 넣어서 곧바로
      `POST /agent-chat` `{"query":"소묘 준비 중인데 내신 4등급이면 어디 지원할 수 있을까?", "history":[{"role":"user","content":"<1번 질문>"},{"role":"assistant","content":"<1번 답변>"}]}` 호출 →
      기대: 2번째 답변이 성적 추천(`recommend_by_grades`) 결과여야 함
      (❌ 중앙대 공간연출전공 호환학과 답변이 반복되면 FAIL - 히스토리 오염 버그)

### 9. 블라인드평가 개인정보 보완검사
- [ ] 9.1 `POST /review-document` `{"text":"저는 대원외고에 재학 중이며, 지도해주신 김민수 선생님과 함께 교내 벽화를 완성했습니다.","doc_type":"자기소개서","university":"홍익대학교"}` →
      응답의 `fact_checks.checks` 중 `type:"blind_review"` 항목 확인 - 기대: `passed:false`,
      `suspects`에 Jev 판정 항목 포함(❌ 체크 자체가 없거나 passed:true면 FAIL - 정규식만으론
      "대원외고"/교사실명을 못 잡음)

### 10. text2cypher 안전장치 (참고용 - 재현 어려우면 스킵 가능)
- [ ] 10.1 `POST /agent-chat` `{"query":"실기고사일이 2개 이상 겹치는 전형 조합이 있는 대학이 몇 곳이야?"}` →
      기대: `tool_trace`에 `text2cypher_query` 포함, 정상적인 숫자 답변(에러 아님)
