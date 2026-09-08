# 📋 [DART · ART:READY] 실전 지식그래프 전체 데이터 명세서 v2.0
## (전체 교육과정 및 프로덕션 파이프라인 단일 기준 원천: Single Source of Truth)

> **문서 버전**: v2.0 (2026-09-08 전 주기 파이프라인 전면 확장 개정)  
> **위치**: `내작업폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md` (동기화: `내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md`)  
> **최우선 헌장**:
> 1. **고정 기준점 (Invariant Foundation)**: 본 명세서는 교재의 박제된 옛날 의학 실습(2016 Hetionet)을 전면 배제하고, 실제 프로덕션 서비스인 **DART-Trace(기업지분·공시 지식그래프)**와 **ART:READY(미대입시 지식그래프)**의 전 주기 데이터 구조와 비즈니스 요건을 고정 기준으로 선언한다.
> 2. **관계의 본질 (Contract-First)**: 관계(선: Edge)는 AI가 창작하는 것이 아니라, **서비스의 핵심 질문(지분 변동 추적 / 입시 일정 충돌 방어) 때문에 사전에 엄격히 계약(정의)**하는 것이다.
> 3. **AI의 엄격한 역할 (Candidate Finder)**: AI와 파서는 그 엄격한 계약(온톨로지)에 들어갈 **후보(Candidate)를 찾아주는 탐색 도구**에 불과하며, 무결성 검증을 통과하기 전에는 프로덕션 DB에 1건도 직결되지 않는다.
> 4. **전 주기 포괄 원칙 (Full Pipeline Coverage)**: 본 문서는 Day 36·37의 추출/온톨로지 단계를 넘어, **Day 36부터 Day 80까지의 전 주기 파이프라인(추출 ➔ 링킹 ➔ 증분배치 ➔ 검색 ➔ GraphRAG ➔ 에이전트 ➔ 품질평가 ➔ 서빙/자동화)**을 모두 포괄한다.
> 5. **데이터 결손 사전 공지 및 대체 원칙 (Data Gap Pre-Notification Rule)**: 향후 교육과정 진행 중 특정 엔지니어링 기법에 요구되는 우리 서비스 데이터의 속성/필드가 일시적으로 부족할 경우, 강의 내용을 임의로 누락하거나 교재의 낡은 의학/영화 예제로 되돌아가지 않는다. **반드시 사전에 '부족한 데이터 필드 명세'와 '프로덕션 스키마 확장 또는 고품질 합성 데이터(Synthetic Data) 대체 계획'을 명확히 사전 공지하고 사용자 승인을 득한 후 진행**한다.

---

## 📜 Revision History

| 버전 | 일자 | 개정 내용 | 작성 주체 | 상태 |
|:---:|:---:|---|:---:|:---:|
| **v1.0** | 2026-09-08 | Day 36(점: NER) 및 Day 37(선: 온톨로지) 중심 기초 대조표 최초 제정 | Antigravity QC | 레거시 |
| **v2.0** | 2026-09-08 | **[전면 개정]** Day 36~80 전 주기 파이프라인, DART/ART 전체 노드·관계·속성 풀스펙, 검색/에이전트/자동화 연계 전면 반영 | Antigravity QC | **공식 제정 🟢** |

---

## 🗺️ 1. 전 주기 6대 파이프라인 조감도 (Master Blueprint: Day 36 ~ Day 80)

```text
====================================================================================================
                              [DART · ART:READY 전 주기 지식그래프 파이프라인]
====================================================================================================

[Phase 1: 자동 수집 및 온톨로지 추출 공장] (Day 36 ~ Day 42)
  • Day 36 (개체/NER)     : 비정형 원문(공시/요강)에서 고유 복합키 '점(Node)' 자동 식별
  • Day 37 (온톨로지 계약): 허용된 관계 시그니처(Edge) 계약 및 3단계 정제 퍼널(원문대조->시그니처->중복제거)
  • Day 38 (관계 추출/RE) : 원문 문맥 기반 복합 관계(다중 지분, 단계별 전형요소) 정밀 판정
  • Day 39 (속성 정규화)  : 지분율(%), 주식수, 실기반영비, 시험시간 등 팩트 테이블 프로퍼티 정규화
  • Day 40 (엔티티 링킹)  : 동음이의 사명, 약어(중대, 한예종), 사명 변경 이력 해소 및 지식 융합
  • Day 41 (배치 자동화)  : 수백 장 PDF 및 일일 공시 XML 비동기 대량 파싱·증분 적재 파이프라인
  • Day 42 (검수 큐 & HITL): :Candidate 격리 큐, 품질 감사 로그 및 휴먼인더루프 검수 대시보드

[Phase 2: 하이브리드 지식그래프 검색 엔진] (Day 43 ~ Day 48)
  • Day 43~45 (그래프+벡터): 구조적 Cypher 쿼리(1-hop~N-hop 경로) + 텍스트 Dense 임베딩 하이브리드 인덱싱
  • Day 46~48 (리랭킹/압축): Cross-Encoder 기반 검색 결과 재순위화 및 LLM 컨텍스트 윈도우 최적 압축

[Phase 3: GraphRAG 및 에이전트 오케스트레이션] (Day 49 ~ Day 56)
  • Day 49~52 (멀티 에이전트): LangGraph 기반 질의 의도 라우터, Cypher 생성 에이전트, 일정 연산 에이전트
  • Day 53~54 (Self-RAG 루프): 추출 결과의 원문 근거(XPath/PDF 쪽수) 역추적 자기검증 및 환각 원천 차단
  • Day 55~56 (도메인 에이전트): DART 지분 순환출자 경로 추적기 & ART 실기 일정 무충돌 지원 조합 추천기

[Phase 4: 자동 품질평가 및 프로덕션 가드레일] (Day 57 ~ Day 64)
  • Day 57~60 (평가 파이프라인): RAGAS 지표(Faithfulness, Answer Relevance) 및 그래프 데이터 정합성 자동 측정
  • Day 61~64 (가드레일 & 보안): 비인가 DB 쓰기 원천 차단, 개인정보(PII) 마스킹, API 쿼터 보호 가드

[Phase 5: 도메인 모델 서빙 및 n8n 무인 자동화] (Day 65 ~ Day 80)
  • Day 65~72 (도메인 파인튜닝): 공시/입시 특화 구조화 추출 및 Cypher 번역 파인튜닝 맞춤 LoRA SFT 학습
  • Day 73~78 (자체 인프라 서빙): vLLM / Ollama 로컬 고성능 서빙 및 저지연 스트리밍 인프라 구축
  • Day 79~80 (n8n 자동화 결합) : 매일 아침 DART 신규 공시 및 대학 요강 변경 자동 감지 ➔ Slack 알림
====================================================================================================
```

---

## 🏢 2. [DART-Trace] 프로덕션 전체 데이터 명세 (Full Production Specification)

### 1) 서비스 핵심 비즈니스 질문
1. *"이 상장사의 실질적 지배주주(최대주주 및 특수관계인)는 누구이며, 지분율 변동 추이는 어떻게 되는가?"*
2. *"해당 지분 보유 사실을 입증하는 공시 보고서 원문(XML 2D XPath 행/열)은 정확히 어디인가?"*
3. *"복잡한 순환출자 고리나 우회 지분 보유 관계가 그래프 경로상에 존재하는가?"*

### 2) 원천 데이터 자산 (Raw Sources)
* **원천 아카이브**: `batch_runs/`, `xml/` 디렉토리 내 보존된 1,500+건의 원천 XML 파일
* **공시 식별자**: 14자리 공시 접수번호(`rcept_no`, 예: `20230515001234`)
* **법인 식별자**: 금융감독원 고유 8자리 법인코드(`corp_code`, 예: `00126380` 삼성전자)

### 3) 전체 노드 스키마 명세 (Node Types & Properties)
| 노드 레이블 | 역할 및 정의 | 고유 식별자 (ID) | 필수 프로퍼티 (Properties) | 부가 프로퍼티 |
|---|---|---|---|---|
| `:Company` | 공시 대상 상장/비상장 법인 | `corp_code` (8자리) | `corp_name`, `corp_code`, `is_listed` | `stock_code`(6자리), `industry_code`, `ceo_name` |
| `:Shareholder` | 지분 보유 주체 (개인/법인/기관) | `holder_key` (정규화키) | `name`, `holder_type` (개인/연기금/사모펀드) | `is_executive`, `is_special_relation`, `birth_year` |
| `:DART_Disclosure` | 금융감독원 전자공시 접수 보고서 | `rcept_no` (14자리) | `rcept_no`, `report_nm`, `rcept_dt` | `flr_nm`(공시제출인), `pblntf_ty`(공시유형) |
| `:EvidenceFragment` | XML 원문 2D XPath 테이블 파편 | `fragment_id` | `rcept_no`, `xpath`, `raw_text_snippet` | `table_index`, `row_index`, `col_index`, `hash_md5` |
| `:RawHoldingFact` | XML에서 1차 추출된 원시 팩트 | `fact_id` | `rcept_no`, `holder_raw_name`, `shares`, `ratio` | `table_coordinate`, `extracted_at` |
| `:Candidate` | 미등록/오류 격리 큐 노드 | `candidate_id` | `name`, `raw_type`, `isolation_reason` | `isolated_at`, `audit_status` |

### 4) 전체 관계 스키마 명세 (Relation Types & Properties)

| 관계명 (Edge Label) | 출발 노드 (Source) | 도착 노드 (Target) | 관계 방향 | 필수 프로퍼티 (Properties) | 부가 프로퍼티 | 엄격 판정 기준 (Ontology Contract) |
|---|---|---|:---:|---|---|---|
| `HOLDS_ECONOMIC_STAKE` | `:Shareholder` | `:Company` | `(s)-[:HOLDS_ECONOMIC_STAKE]->(c)` | `stake_ratio`(%), `shares`, `base_date` | `voting_shares`, `share_type`, `evidence_level` | 보고자가 대상 상장사의 의결권 주식을 5% 이상 대량 보유하거나 특수관계인으로 참여한다. |
| `HOLDS_LEGAL_STAKE` | `:Shareholder` | `:Company` | `(s)-[:HOLDS_LEGAL_STAKE]->(c)` | `stake_ratio`(%), `shares`, `custody_type` | `evidence_level` | 수탁 기관이나 펀드가 명의상 주식을 보유하나 실질적 의결권을 행사하지 않는다. |
| `EVIDENCED_BY` | `[HOLDS_ECONOMIC_STAKE]` | `:EvidenceFragment` | `(r)-[:EVIDENCED_BY]->(f)` | `xpath`, `match_score` | `verified_at`, `audit_status` | 지분 보유 수치와 사실이 공시 XML의 특정 2D 테이블 행에 100% 실존한다. |
| `SUBMITTED` | `:Company` | `:DART_Disclosure` | `(c)-[:SUBMITTED]->(d)` | `submission_time` | `filing_agent` | 대상 상장사가 금융감독원에 공식 보고서를 접수·공시한다. |
| `REPORTED_IN` | `:Shareholder` | `:DART_Disclosure` | `(s)-[:REPORTED_IN]->(d)` | `reporter_role` | `report_date` | 주주 본인 또는 대리인이 해당 공시의 보고자로 명시되어 있다. |
| `PRECEDED_BY` | `[HOLDS_ECONOMIC_STAKE]` | `[HOLDS_ECONOMIC_STAKE]` | `(r_new)-[:PRECEDED_BY]->(r_old)` | `ratio_delta`, `shares_delta` | `elapsed_days` | 동일 주주-기업 간 직전 공시 기준일의 지분 상태를 신규 지분 상태로 연결한다 (시계열). |

```python
DART_PROD_RELATION_SIGNATURES = {
    # 1. 지분 보유 핵심 관계 (의결권 있는 경제적 지분)
    "HOLDS_ECONOMIC_STAKE": {
        "from": "Shareholder", "to": "Company",
        "properties": ["stake_ratio", "shares", "voting_shares", "base_date", "share_type", "evidence_level"],
        "criterion": "보고자가 대상 상장사의 의결권 주식을 5% 이상 대량 보유하거나 특수관계인으로 참여한다."
    },
    # 2. 단순 수탁/명의상 지분 보유 관계
    "HOLDS_LEGAL_STAKE": {
        "from": "Shareholder", "to": "Company",
        "properties": ["stake_ratio", "shares", "custody_type", "evidence_level"],
        "criterion": "수탁 기관이나 펀드가 명의상 주식을 보유하나 실질적 의결권을 행사하지 않는다."
    },
    # 3. 원천 증거 결속 관계 (Knowledge Graph ➔ Evidence)
    "EVIDENCED_BY": {
        "from": "HOLDS_ECONOMIC_STAKE", "to": "EvidenceFragment",
        "properties": ["xpath", "match_score", "verified_at"],
        "criterion": "지분 보유 수치와 사실이 공시 XML의 특정 2D 테이블 행에 100% 실존한다."
    },
    # 4. 공시 제출 관계
    "SUBMITTED": {
        "from": "Company", "to": "DART_Disclosure",
        "properties": ["submission_time"],
        "criterion": "대상 상장사가 금융감독원에 공식 보고서를 접수·공시한다."
    },
    # 5. 공시 보고자 관계
    "REPORTED_IN": {
        "from": "Shareholder", "to": "DART_Disclosure",
        "properties": ["reporter_role"],
        "criterion": "주주 본인 또는 대리인이 해당 공시의 보고자로 명시되어 있다."
    },
    # 6. 시계열 지분 변동 이력 연결 (Temporal Transition)
    "PRECEDED_BY": {
        "from": "HOLDS_ECONOMIC_STAKE", "to": "HOLDS_ECONOMIC_STAKE",
        "properties": ["ratio_delta", "shares_delta", "elapsed_days"],
        "criterion": "동일 주주-기업 간 이전 공시 기준일의 지분 상태를 신규 지분 상태로 연결한다."
    }
}
```

### 5) 멱등 적재 및 근거 등급 불변식 (Cypher Invariant)
* **근거 등급**: `official_verified` (공식 승격분) > `reported` (모델 추출분) > `candidate` (격리분)
* **보호 규칙**: 이미 검증된 공식 등급은 신규 배치가 재실행되어도 다운그레이드되지 않는다.
```cypher
MERGE (s:Shareholder {holder_key: $holder_key})
  ON CREATE SET s.name = $holder_name, s.holder_type = $holder_type
MERGE (c:Company {corp_code: $corp_code})
  ON CREATE SET c.name = $company_name
MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
  ON CREATE SET 
    r.stake_ratio = $stake_ratio,
    r.shares = $shares,
    r.base_date = $base_date,
    r.evidence_level = $evidence_level,
    r.created_at = datetime()
  ON MATCH SET 
    r.stake_ratio = $stake_ratio,
    r.evidence_level = CASE WHEN r.evidence_level = 'official_verified' THEN 'official_verified' ELSE $evidence_level END;
```

---

## 🎨 3. [ART:READY] 프로덕션 전체 데이터 명세 (Full Production Specification)

### 1) 서비스 핵심 비즈니스 질문
1. *"공간연출전공이나 시각디자인과를 지망하는 학생이 실기(소묘) 80%로 지원할 수 있는 대학과 전형은 어디인가?"*
2. *"지원 희망 대학들(중앙대, 국민대, 서울과기대) 간의 실기고사 일정(날짜 및 오전/오후 시간대)이 충돌하지 않는 최적의 6개 수시 조합은 무엇인가?"*
3. *"1단계 합격 배수(배수 선발)와 2단계 면접/실기 반영 비율이 정확히 요강 원문 몇 쪽에 근거하는가?"*

### 2) 원천 데이터 자산 (Raw Sources)
* **원천 아카이브**: 대학 입학처 공식 배포 2026/2027 모집요강 원본 PDF 문서
* **실데이터 벤치마크**: `내작업폴더/data/art_admission/raw/cau_spatial_design.json` (중앙대 서울 공간연출전공 2027 수시 실기형)
* **표준 대학 코드**: `CAU_SEOUL`(중앙대 서울), `CAU_ANSEONG`(중앙대 안성), `KMU`(국민대), `SNU`(서울대)

### 3) 전체 노드 스키마 명세 (Node Types & Properties)
| 노드 레이블 | 역할 및 정의 | 고유 식별자 (ID) | 필수 프로퍼티 (Properties) | 부가 프로퍼티 |
|---|---|---|---|---|
| `:University` | 대학 및 캠퍼스 본체 | `{univ_name}_{campus}` | `name`, `campus`, `region` | `univ_code`, `est_type`(국립/사립), `address` |
| `:Department` | 모집 단위 학과/학부/전공 | `{dept_name}` (표준화) | `name`, `category`(디자인/회화/공간연출) | `dept_code`, `degree_type` |
| `:AdmissionTrack` | 입학 전형 단위 | `{univ}_{track}_{year}` | `track_name`, `admission_type`(수시/정시), `year` | `recruit_count`, `stage_type`(일괄/단계별), `min_csat` |
| `:PracticalType` | 실기 시험 종목 | `{practical_code}` | `name`(소묘/기초디자인), `category` | `standard_time`(분), `paper_size`(절지), `materials` |
| `:ExamSchedule` | 실기 고사 일시 및 장소 | `{track_id}_{date}` | `exam_date`, `start_time`, `is_tentative` | `end_time`, `location`, `conflict_group` |
| `:EvaluationRatio` | 단계별 성적 반영 비율 | `{track_id}_stage_{N}` | `stage`, `practical_ratio`, `school_record_ratio` | `csat_ratio`, `interview_ratio`, `attendance_ratio` |
| `:Candidate` | 미등록 학과/신설 전형 격리 큐 | `candidate_id` | `name`, `raw_text`, `isolation_reason` | `detected_at`, `source_pdf_page` |

### 4) 전체 관계 스키마 명세 (Relation Types & Properties)

| 관계명 (Edge Label) | 출발 노드 (Source) | 도착 노드 (Target) | 관계 방향 | 필수 프로퍼티 (Properties) | 부가 프로퍼티 | 엄격 판정 기준 (Ontology Contract) |
|---|---|---|:---:|---|---|---|
| `OFFERS_TRACK` | `:University` | `:AdmissionTrack` | `(u)-[:OFFERS_TRACK]->(t)` | `admission_year` | `evidence_level` | 대학이 해당 학년도 신입생 선발을 위해 전형을 공식 개설한다. |
| `BELONGS_TO` | `:Department` | `:University` | `(d)-[:BELONGS_TO]->(u)` | `college_name` | `campus` | 해당 학과가 특정 대학교의 특정 캠퍼스 단과대학 소속이다. |
| `RECRUITS_FOR` | `:AdmissionTrack` | `:Department` | `(t)-[:RECRUITS_FOR]->(d)` | `recruit_quota` | `competition_ratio_prev` | 해당 전형을 통해 특정 학과의 정원 내/외 신입생을 모집한다. |
| `REQUIRES_PRACTICAL` | `:AdmissionTrack` | `:PracticalType` | `(t)-[:REQUIRES_PRACTICAL]->(p)` | `stage`, `ratio`(%) | `paper_size`, `exam_duration`, `evidence` | 전형에 응시하기 위해 특정 실기 시험(소묘, 기초디자인 등)을 반드시 치러야 한다. |
| `EXAM_ON` | `:AdmissionTrack` | `:ExamSchedule` | `(t)-[:EXAM_ON]->(e)` | `stage`, `is_confirmed` | `announcement_date` | 해당 전형의 실기 고사가 지정된 날짜와 시간에 고사장에서 치러진다. |
| `HAS_EVALUATION` | `:AdmissionTrack` | `:EvaluationRatio` | `(t)-[:HAS_EVALUATION]->(ev)` | `stage` | `multiplier`(배수 선발) | 전형의 1단계/2단계별 실기, 학생부, 면접 반영 비율 구조를 결속한다. |
| `SCHEDULE_CONFLICTS_WITH` | `:ExamSchedule` | `:ExamSchedule` | `(e1)-[:SCHEDULE_CONFLICTS_WITH]-(e2)` | `overlap_hours` | `conflict_severity` | 두 시험 일정의 날짜 및 진행 시간대가 겹쳐 학생의 동시 응시가 불가능하다 (양방향 추론). |

```python
ART_PROD_RELATION_SIGNATURES = {
    # 1. 대학 -> 입학 전형 개설
    "OFFERS_TRACK": {
        "from": "University", "to": "AdmissionTrack",
        "properties": ["admission_year", "evidence_level"],
        "criterion": "대학이 해당 학년도 신입생 선발을 위해 전형을 공식 개설한다."
    },
    # 2. 학과 -> 대학 소속
    "BELONGS_TO": {
        "from": "Department", "to": "University",
        "properties": ["college_name"],
        "criterion": "해당 학과가 특정 대학교의 특정 캠퍼스 단과대학 소속이다."
    },
    # 3. 전형 -> 학과 신입생 선발 연결
    "RECRUITS_FOR": {
        "from": "AdmissionTrack", "to": "Department",
        "properties": ["recruit_quota", "competition_ratio_prev"],
        "criterion": "해당 전형을 통해 특정 학과의 정원 내/외 신입생을 모집한다."
    },
    # 4. 전형 -> 실기 종목 필수 반영
    "REQUIRES_PRACTICAL": {
        "from": "AdmissionTrack", "to": "PracticalType",
        "properties": ["stage", "ratio", "paper_size", "exam_duration", "evidence_level"],
        "criterion": "전형에 응시하기 위해 특정 실기 시험(소묘, 기초디자인 등)을 반드시 치러야 한다."
    },
    # 5. 전형 -> 실기 고사 일정 배정
    "EXAM_ON": {
        "from": "AdmissionTrack", "to": "ExamSchedule",
        "properties": ["stage", "announcement_date", "is_confirmed"],
        "criterion": "해당 전형의 실기 고사가 지정된 날짜와 시간에 고사장에서 치러진다."
    },
    # 6. 전형 -> 단계별 평가 배점 비율 결속
    "HAS_EVALUATION": {
        "from": "AdmissionTrack", "to": "EvaluationRatio",
        "properties": ["stage", "multiplier"],  # 1단계 5배수 선발 등
        "criterion": "전형의 1단계/2단계별 실기, 학생부, 면접 반영 비율 구조를 결속한다."
    },
    # 7. 일정 충돌 그래프 관계 (양방향 가상 엣지: Schedule Conflict)
    "SCHEDULE_CONFLICTS_WITH": {
        "from": "ExamSchedule", "to": "ExamSchedule",
        "properties": ["overlap_hours", "conflict_severity"],
        "criterion": "두 시험 일정의 날짜 및 진행 시간대가 겹쳐 학생의 동시 응시가 불가능하다."
    }
}
```

### 5) 멱등 적재 및 검증 불변식 (Cypher Invariant)
* **불변식 1 (복합키 식별)**: `University`는 반드시 `{name}_{campus}`로 구별하여 중앙대 서울과 안성을 절대 합치지 않는다.
* **불변식 2 (비율 합산)**: `EvaluationRatio`의 반영 비율 총합은 반드시 100%이어야 한다.
* **불변식 3 (출처 등급)**: 입학처 공식 요강 확정 데이터는 `curated`로 선언하여 추정치와 혼동을 차단한다.
```cypher
MERGE (u:University {id: $univ_id})
  ON CREATE SET u.name = $univ_name, u.campus = $campus
MERGE (t:AdmissionTrack {id: $track_id})
  ON CREATE SET t.name = $track_name, t.year = $year
MERGE (u)-[r1:OFFERS_TRACK]->(t)
  ON CREATE SET r1.evidence_level = 'curated'
MERGE (p:PracticalType {id: $practical_id})
  ON CREATE SET p.name = $practical_name
MERGE (t)-[r2:REQUIRES_PRACTICAL]->(p)
  ON CREATE SET 
    r2.ratio = $practical_ratio,
    r2.stage = $stage,
    r2.evidence = $evidence,
    r2.evidence_level = 'curated'
  ON MATCH SET 
    r2.evidence_level = CASE WHEN r2.evidence_level = 'curated' THEN 'curated' ELSE 'curated' END;
```

---

## 📊 4. 전 주기(Day 36 ~ Day 80) 교육과정 1:1 대조 매트릭스

본 매트릭스는 매일의 교육 과정에서 다루는 주제가 **DART-Trace**와 **ART:READY**의 어떤 구체적 자산 및 코드와 직결되는지를 정의합니다:

| 단계 (Phase) | Day | 교육과정 학습 주제 | [DART-Trace] 실제 구현 자산 | [ART:READY] 실제 구현 자산 | 완료 판정 기준 (Done Definition) |
|:---:|:---:|---|---|---|---|
| **Phase 1**<br>(추출/온톨) | **Day 36** | 개체명 인식 (NER), Span, BIO, Pydantic | 상장사(`Company`), 주주(`Shareholder`) 복합키 식별 | 대학, 학과, 전형, 실기종목 5대 노드 식별 | 동음이의어/캠퍼스 분리 복합키 정의 완료 |
| | **Day 37** | 온톨로지 계약, 3단 정제 퍼널, 멱등 Cypher | `HOLDS_ECONOMIC_STAKE`, `EVIDENCED_BY` 계약 | `OFFERS_TRACK`, `REQUIRES_PRACTICAL` 4종 계약 | [승격 / Candidate / 기각] 3분류 자동화 |
| | **Day 38** | 관계 추출(RE) 고도화 및 다중 관계 판정 | 법인-주주 간 복합 지분/의결권 관계 판정 | 전형 ➔ 학과 선발 및 다중 실기종목 분기 | 관계 시그니처 위반율 0% 검증 |
| | **Day 39** | 속성 정규화 (Property/Fact Table) | 지분율(%), 주식수, 3대 기준일자 포맷팅 | 단계별 실기 반영비(80%), 전형 일정 포맷팅 | 숫자형/ISO 날짜형 스키마 100% 준수 |
| | **Day 40** | 엔티티 링킹 (EL) 및 지식 융합 | 사명 변경 기업 ➔ 동일 `corp_code` 매핑 | 대학 약어(중대, 한예종) ➔ 정규 대학 ID 결속 | ID 결속 실패분 `:Candidate` 격리율 100% |
| | **Day 41** | 대량 배치 수집 및 비동기 파이프라인 | OpenDART 공시 1,500건 자동 증분 파이프라인 | 15개교 ➔ 전국 미대 모집요강 PDF 파싱 파이프라인 | 재실행 시 중복 노드 0건 (완전 멱등성) |
| | **Day 42** | 자동 검수 큐, 감사 로깅, HITL | 결손 지분 공시 자동 감사 로그 (`AUDIT_LOG`) | 미등록 신설 학과 검수 대시보드 | 에러 발생 시 사유/위치 즉시 보고 체계 |
| **Phase 2**<br>(검색/인덱스) | **Day 43~45** | 지식그래프 하이브리드 검색 (Cypher + Dense) | 주주별 소유 구조 Cypher + 공시 본문 벡터 검색 | 실기 과목/일정 Cypher + 전형 특징 벡터 검색 | 1-hop~3-hop 경로 검색 응답 1초 이내 |
| | **Day 46~48** | Cross-Encoder 리랭킹 및 컨텍스트 압축 | 관련 공시 단락 정밀 재순위화 | 학생 내신/실기 조건 부합 전형 리랭킹 | Top-5 검색 정확도(MRR@5) 90% 이상 |
| **Phase 3**<br>(에이전트) | **Day 49~52** | LangGraph 멀티 에이전트 오케스트레이션 | 의도 분석기 ➔ Cypher 생성기 ➔ 지분 계산기 | 전형 탐색기 ➔ 일정 충돌 계산기 ➔ 포트폴리오 상담기 | 의도 분기 및 도구 호출 성공률 95% 이상 |
| | **Day 53~54** | Self-RAG 자기검증 및 환각 차단 | 생성된 지분율 수치를 XML XPath와 역대조 | 추천 전형의 실기 일정을 요강 원문과 역대조 | 환각(Hallucination) 검출률 100% 차단 |
| | **Day 55~56** | 도메인 특화 에이전트 워크플로우 | 최대주주 지분 변동 및 순환출자 추적 에이전트 | 실기 무충돌 수시 6개 대학 최적 조합 추천기 | "일정 안 겹치는 6개 조합" 즉시 생성 |
| **Phase 4**<br>(품질/가드) | **Day 57~60** | RAGAS 정량 평가 및 그래프 정합성 지표 | 지분 데이터 정합성 및 Groundedness 평가 | 입시 요강 팩트 보존율 및 Context Precision 평가 | 정량 평가 점수 0.85 이상 달성 |
| | **Day 61~64** | 프로덕션 가드레일 및 보안/비용 방어 | 비인가 DB 쓰기 가드 (`Production Safety`) | 비현실적 전형 추천 방어 가드레일 | 비인가 스크립트 실행 원천 차단 100% |
| **Phase 5**<br>(서빙/자동화) | **Day 65~72** | 도메인 맞춤 LLM 파인튜닝 (LoRA SFT) | 공시 텍스트 전용 Cypher 번역 파인튜닝 | 모집요강 텍스트 전용 구조화 추출 파인튜닝 | 베이스 모델 대비 추출 에러율 50% 감축 |
| | **Day 73~78** | vLLM / Ollama 로컬 인프라 자체 서빙 | 사내 보안 DART 분석 엔진 vLLM 서빙 | 실시간 입시 컨설팅 챗봇 온디바이스 서빙 | 토큰 생성 속도 50 tokens/sec 이상 |
| | **Day 79~80** | n8n 무인 엔지니어링 자동화 파이프라인 | 매일 아침 08:00 신규 5% 공시 수집 ➔ Slack 보고 | 매일 09:00 요강 정정공지 크롤링 ➔ 변동 알림 | 휴먼 개입 없는 일일 증분 자동화 완성 |

---

## 🎯 5. 서비스 워크북 표준 7단 구조 (작성 SOP)

각 학습 폴더(`dayXX_...`)에서 산출물을 작성할 때는 새로운 장난감 예제를 만들지 않고, 본 명세서의 DART 및 ART 실제 데이터를 기준으로 아래 7대 고정 섹션을 준수하여 작성한다:

```text
1. [1단] 오늘 개념 한 줄         : 본질을 초등생 비유 및 한 문장으로 정의
2. [2단] 전체 지도에서의 위치     : Day 36~80 전체 파이프라인 중 현재 위치 조감
3. [3단] DART 적용 사례          : 기업공시 지분 추적에서의 실제 데이터 매핑
4. [4단] ART:READY 적용 사례     : 미대입시 전형/실기/일정에서의 실제 데이터 매핑
5. [5단] 현재 구현 및 원본 근거   : 실제 소스코드 파일 및 DB 실측 물리 자산
6. [6단] 부족한 부분 하나 (결손)  : 현업 프로덕션 서비스로 도약하기 위한 당면 보강 과제
7. [7단] DRY-RUN 및 완료 판정    : 실제 쿼리 실행 기준 및 ALL PASS 합격 기준
```

---

## 🛡️ 6. 최종 승인 및 헌장 집행 선언

1. **단일 원천의 권위**: 본 문서는 `내학습폴더` 및 `내작업폴더` 전역의 최상위 데이터 헌장이며, 향후 Day 38 이후의 모든 산출물은 본 문서에 정의된 노드, 관계, 파이프라인 매트릭스를 반드시 준용한다.
2. **독립적 폴더 분리**: 각 학습일(`day36_...`, `day37_...`)의 세부 코드와 실습 워크북은 각 폴더 내에서 독립적으로 구동하되, 데이터 스키마와 온톨로지 계약은 반드시 본 명세서를 상속한다.
