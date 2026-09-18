> ⚠️ **[안내 - 2026-09-18 오후]** 이 문서는 같은 날 오전 실측치이며, 오후 작업
> (엔티티 재추출, `COMPATIBLE_WITH`/`SIMILAR_TO` 관계 신설)으로 수치가 낡았고,
> 관계 타입 3종(`ESTIMATED_CUTOFF`/`HAD_PAST_TOPIC`/`HAS_YEARLY_RESULT`) 누락과
> 노드 라벨 오기(`Admission_Stage` → 실제로는 `Admission_SelectionStage`)가
> 있다. 최신 정정판은
> `20_ART_READY_지식그래프_전체_노드_및_엣지_온톨로지_상세명세서_v1.1.md` 참고.

# 🎨 [ART:READY] 지식그래프 전체 노드 및 엣지 온톨로지 상세명세서 (v1.0)

> **문서 식별자**: `ART_READY_ONTOLOGY_SPEC_v1.0`  
> **최초 작성일**: 2026-09-18  
> **버전**: v1.0 (최초 발간)  
> **작성 주체**: ART:READY 데이터 거버넌스 및 품질관리(QC) 전담팀  
> **상태**: 프로덕션 실측 확정본 (Ground-Truth Verified)  
> **대상 데이터베이스**: Neo4j Aura 클라우드 인스턴스 (접두어: `Admission_`)

---

## 📋 개정이력 (Revision History)

| 버전 | 일자 | 작성자 | 변경 내역 요약 |
| :---: | :---: | :---: | :--- |
| **v1.0** | 2026-09-18 | 거버넌스/QC팀 | • 1층 공식 팩트(5종) 및 2층 비정형 의미망(2종) 전체 노드 라벨 전수 명세화<br>• 전체 엣지(6종)의 출발/도착 노드, 속성, 실측 건수 전수 수록<br>• `e.type`, `e.community`, `e.pagerank` 속성 설계 원리 및 GraphRAG 횡단 메커니즘 명시 |

---

## 🏛️ 1. 온톨로지 전체 아키텍처 개요

ART:READY의 지식그래프는 **"1층 공식 팩트 장부(Ground-Truth Fact Layer)"**와 **"2층 비정형 의미 그물망(Semantic Mesh Layer)"**의 2-Tier 하이브리드 토폴로지로 설계되었습니다.

```text
========================================================================================
[2층: 비정형 의미 그물망 (Semantic Mesh Layer)]
  (:Admission_TextChunk) ──[:MENTIONS (22,398건)]──▶ (:Admission_Entity)
      (4,016개 노드)                                      (5,185개 노드)
                                                               │  ▲
                                                [:CO_OCCURS_WITH (62,810건)]
                                                               ▼  │
                                                      (:Admission_Entity)
======================================= ▲ ==============================================
                          (이름 일치 기반 하이브리드 결합)
======================================= ▼ ==============================================
[1층: 공식 팩트 장부 (Ground-Truth Fact Layer)]
  (:Admission_University)
      │
      └─[:HAS_DEPARTMENT]─▶ (:Admission_Department: 212개 실기학과)
                                  │
                                  └─[:HAS_TRACK]─▶ (:Admission_Track: 수시전형)
                                                        │
                                ┌───────────────────────┼───────────────────────┐
                                ▼                       ▼                       ▼
                     [:REQUIRES_EXAM]             [:HAS_SCHEDULE]          [:HAS_STAGE]
                                │                       │                       │
                                ▼                       ▼                       ▼
                     (:Admission_ExamType)   (:Admission_Schedule)     (:Admission_Stage)
========================================================================================
```

---

## 🧩 2. 전체 노드 라벨 상세 명세표 (Node Specifications)

총 7개 노드 라벨이 존재하며, 1층 공식 팩트 5종과 2층 의미망 2종으로 엄격히 분리됩니다.

### 2.1 [1층] 공식 팩트 노드 (Ground-Truth Nodes)

| 노드 라벨 | 생성 주체 | 실측 노드 수 | 고유 식별 키 (Identity) | 핵심 속성 및 데이터 타입 | 설명 및 비즈니스 목적 |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`Admission_University`** | `00_Art_Admission_Graph_Loader.py` | 52개 | `name`, `campus` | • `name` (String): 대학명<br>• `campus` (String): 캠퍼스명 (서울, ERICA, 글로벌 등) | 공식 수시 모집요강이 수집된 전국 주요 미술대학 |
| **`Admission_Department`** | `00_Art_Admission_Graph_Loader.py` | **212개** | `name`, `university` | • `name` (String): 학과/전공명<br>• `university` (String): 소속 대학명 | 실제 실기전형을 운영하는 공식 검증 미술계열 학과 |
| **`Admission_Track`** | `00_Art_Admission_Graph_Loader.py` | 300+개 | `name`, `university`, `department` | • `quota` (Integer): 모집정원<br>• `ratio` (String): 공식 반영비율 문구<br>• `school_record_ratio_pct` (Float): 학생부 반영비율(%)<br>• `practical_ratio_pct` (Float): 실기 반영비율(%)<br>• `school_record_rule_json` (String/JSON): 대학별 복합 내신 계산 규칙<br>• `is_staged` (Boolean): 단계형 전형 여부<br>• `is_superseded` (Boolean): 구버전 전형 여부(최신성 관리)<br>• `competition_rate` (Float): 실시간 경쟁률<br>• `source_url` (String): 입학처 요강 원문 링크 | **시스템의 핵심 심장 노드.** 정밀 내신 환산 및 6장 포트폴리오 산출 기준 |
| **`Admission_ExamType`** | `00_Art_Admission_Graph_Loader.py` | 300+개 | `name`, `track_name`, `university`, `department` | • `name` (String): 실기 과목명 (기초조형, 소묘 등)<br>• `paper_size` (String): 켄트지 규격 (3절, 4절 등)<br>• `time_limit_minutes` (Integer): 고사 시간 (240분 등)<br>• `allowed_materials` (List[String]): 허용 지참 준비물 목록 | 실기고사 현장 평가 규격 및 도구 가이드라인 |
| **`Admission_Schedule`** | `00_Art_Admission_Graph_Loader.py` | 300+개 | `track_name`, `university`, `department` | • `application_start` (String: YYYY-MM-DD): 원서접수 시작일<br>• `application_end` (String: YYYY-MM-DD): 원서접수 마감일<br>• `exam_date` (String: YYYY-MM-DD): 실기고사 일자<br>• `result_date` (String: YYYY-MM-DD): 최초 합격자 발표일 | **무충돌 6장 조합 판정 기준.** 실기고사 일정 중복 회피 |
| **`Admission_Stage`** | `00_Art_Admission_Graph_Loader.py` | 수십 건 | `track_name`, `stage_number` | • `stage_number` (Integer): 전형 단계 (1단계, 2단계)<br>• `multiplier` (Float): 1단계 통과 배수 (예: 5배수)<br>• `practical_pct` (Float): 해당 단계 실기 반영비율 | 다단계 선발(1단계 성적 ➔ 2단계 실기) 구조화 |

---

### 2.2 [2층] 비정형 의미망 노드 (Semantic Mesh Nodes)

| 노드 라벨 | 생성 주체 | 실측 노드 수 | 고유 식별 키 (Identity) | 핵심 속성 및 데이터 타입 | 설명 및 비즈니스 목적 |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`Admission_TextChunk`** | `01_Art_Admission_Vector_Indexer.py` | **4,016개** | `university`, `source_file`, `chunk_index` | • `text` (String): **1,500자 원문 본문 텍스트**<br>• `university` (String): 대상 대학명<br>• `source_file` (String): 원천 PDF 파일명<br>• `page_start` (Integer): 시작 페이지<br>• `page_end` (Integer): 종료 페이지<br>• `embedding` (List[Float]): **1,536차원 벡터** | LLM 근거 제시용 원문 텍스트 조각 및 하이브리드 검색 대상 |
| **`Admission_Entity`** | `02_Art_Admission_Entity_Linker.py` | **5,185개** | `name` | • `name` (String): 엔티티 명칭 (단어/개념)<br>• `type` (String): **엔티티 카테고리 (아래 5대 분류)**<br>• `llm_discovered` (Boolean): **AI 신규 발굴 여부**<br>• `community` (Integer): **Louvain 커뮤니티 ID (군집)**<br>• `community_label` (String): **군집 한글 요약 라벨**<br>• `pagerank` (Float): **동시출현 중심성 가중치** | AI가 본문에서 추출해 검증한 핵심 지식 개념. GraphRAG 추천 지표 |

---

## 🏷️ 3. `Admission_Entity` 노드의 내부 속성 정의

사용자께서 가장 많이 질문하시는 `Admission_Entity`의 속성 체계는 다음과 같습니다.

### 3.1 5대 `type` 속성 분류
`Admission_Entity`는 별도 노드 라벨을 쪼개지 않고, **`type` 속성 단일 필드로 5대 카테고리를 엄격히 관리**합니다:
1. **`university`**: 대학 공식 명칭 (예: "국민대학교", "서울대학교")
2. **`department`**: 미술계열 학과/전공 명칭 (예: "시각디자인학과", "조소전공")
3. **`exam_type`**: 실기고사 종목 및 전형 방식 (예: "기초조형평가", "발상과표현")
4. **`material`**: 실기 지참 도구/화구/재료 (예: "4절지", "건식재료", "켄트지", "색연필")
5. **`other`**: 기타 입시 평가기준 및 유의사항 용어 (예: "투시도", "주제해석", "수시모집")

### 3.2 `llm_discovered` (AI 신규 발굴 계보 속성)
* **`false`**: 1층 공식 요강 표(`data/art_admission/raw/*.json`)에 이미 명시되어 인간 사전(`known_entities`)에 등록되어 있던 공식 엔티티.
* **`true`**: 1층 표에는 없었지만, **gpt-5.6-luna가 PDF 줄글 본문을 읽다가 "이건 입시에서 중요한 실기 재료/도구/기법이다!"라고 스스로 발굴(Discovered)해낸 신규 엔티티**.

### 3.3 `community` 및 `community_label` (군집 속성)
* **별도 노드가 아닌 속성으로 구현된 이유**:
  커뮤니티는 알고리즘(Louvain) 재계산 시 동적으로 변하는 **분석적 메타데이터**입니다. 별도 노드로 만들 경우 수천 개의 엣지를 매번 재연결하는 락(Lock) 오버헤드가 발생하므로, 속성으로 박아두어 인덱스 검색(`WHERE e.community = 138`)과 초고속 갱신을 보장합니다.
* **실측 현황**: 총 **258개 커뮤니티**, 상위 25개 주요 군집에 gpt-5.6-luna 한글 요약 라벨(예: "미술디자인 실기전형", "회화 계열 실기")이 부여되어 있습니다.

---

## 🔗 4. 전체 엣지(관계) 상세 명세표 (Relationship Specifications)

총 6개 관계 타입이 존재하며, 실측 수치는 다음과 같습니다.

| 관계 타입 (Relationship) | 출발 노드 (Source) | 도착 노드 (Target) | 속성 (Properties) | 실측 건수 (Actual) | 설명 및 비즈니스 목적 |
| :--- | :---: | :---: | :--- | :---: | :--- |
| **`HAS_DEPARTMENT`** | `Admission_University` | `Admission_Department` | 없음 | 212건 | 대학 산하 공식 개설된 실기 학과 소속 관계 |
| **`HAS_TRACK`** | `Admission_Department` | `Admission_Track` | 없음 | 300+건 | 학과 산하 수시 모집 전형 연결 (일반실기, 특기자 등) |
| **`REQUIRES_EXAM`** | `Admission_Track` | `Admission_ExamType` | 없음 | 300+건 | 해당 수시 전형이 치러야 하는 실기고사 종목 연결 |
| **`HAS_SCHEDULE`** | `Admission_Track` | `Admission_Schedule` | 없음 | 300+건 | 전형별 원서접수 기간 및 실기고사 일정 연결 |
| **`HAS_STAGE`** | `Admission_Track` | `Admission_Stage` | 없음 | 수십 건 | 다단계 선발 전형의 단계별 배점 연결 |
| **`MENTIONS`** | `Admission_TextChunk` | `Admission_Entity` | 없음 | **22,398건** | **1,500자 원문 청크에 해당 엔티티가 실제로 언급됨** (근거 엣지) |
| **`CO_OCCURS_WITH`** | `Admission_Entity` | `Admission_Entity` | `weight` (Integer): 함께 등장한 청크 수 | **62,810건**<br>*(정제 전 89,474건)* | **같은 1,500자 청크에 동시에 출현한 개체 간 동시출현 엣지** (커뮤니티/PageRank 계산의 원천) |

---

## 💡 5. JSON과 PDF 원문의 역할 구분 (왜 두 갈래인가?)

| 비교 항목 | [1층] 정형 JSON (`raw/*.json`) | [2층] 비정형 PDF 원문 (`prospectus/*.pdf`) |
| :--- | :--- | :--- |
| **주요 대상** | 요강의 **"표(Table)"와 "수치(Numbers)"** | 요강의 **"줄글 본문(Text)"과 "세부 지침"** |
| **포함 내용** | 모집인원, 내신 환산 공식, 반영비율, 원서접수일 | 허용 재료 조건, 화판 제공 여부, 평가 기준, 출제의도, 유의사항 |
| **데이터 성격** | **100% 결정론적 팩트 (오차 0% 필수)** | **미묘한 도메인 문맥 및 어휘 텍스트** |
| **서비스 목적** | **"엔진의 정밀 산술 계산"** (내신 점수, 6장 조합 충돌 검사) | **"LLM의 신뢰성 있는 질의응답 및 상담"** (원문 근거 제시) |
| **처리 방식** | 인간 연구원 정밀 검수 ➔ `00번 로더` 직접 적재 | 1,500자 청킹 ➔ 임베딩 ➔ AI 엔티티 추출 ➔ 원문 검증 |

> **결론**:  
> 숫자가 틀리면 안 되는 **"계산"**은 1층 JSON 장부가 담당하고, 풍부한 맥락이 필요한 **"상담과 추천"**은 2층 PDF 의미망이 담당하므로, 두 갈래는 선택의 문제가 아닌 **필수적인 상호보완 관계**입니다.
