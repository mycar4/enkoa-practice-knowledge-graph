# 🏛️ [Day 27] 그래프 데이터베이스 개념 및 지식그래프(LPG) 모델링 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day27_그래프DB_개념_지식그래프/00_Day27_그래프DB_개념_지식그래프_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 27 그래프 모델링 기초]
   - Day 27 (그래프 모델링): 왜 RDB가 아니라 속성 그래프(LPG)인가? 점과 선의 본질
   - Day 28 (Neo4j 인프라) : 클라우드 DB 인스턴스 구축 및 실데이터 적재
   - Day 29~31 (Cypher 탐색): MATCH, UNWIND, 인덱스 튜닝, 지분율 집계
   - Day 32 (멱등 적재)    : 대량 데이터 무결점 MERGE 트랜잭션
   - Day 33~34 (GDS 알고리즘): PageRank 지배회사 탐지 & 순환출자/일정충돌 최단경로
   - Day 35 (GraphRAG)     : 텍스트 벡터 인덱스와 지식그래프 결합
  ① 자동 추출 및 온톨로지 파이프라인 (Day 36~42)
  ② 하이브리드 검색 + 리랭킹 (Day 43~48)
  ③ 에이전트 오케스트레이션 (Day 49~56)
  ④ 자동 품질평가 + 가드레일 (Day 57~64)
  ⑤ 도메인 파인튜닝 + 서빙/자동화 (Day 65~80)
```
> **학습 목적**: "수십 개의 테이블을 JOIN하다가 서버가 터지는 관계형 데이터베이스(RDB)의 한계를 깨닫고, 기업 지배구조와 대학 입시 복합 조건을 단 1번의 포인터 홉(Pointer Hopping)으로 탐색하는 **속성 그래프 모델(LPG: Labeled Property Graph)**을 직접 설계하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 RDB가 아니라 그래프 데이터베이스인가?)

### 10초 초등생 비유: "서류철 뒤지기(RDB) vs 실뜨기 지도(그래프)"
1. **관계형 데이터베이스 (RDB: 서류철 뒤지기)**:
   - "A 회사 주주가 B 회사도 쥐고 있고, 그 B가 C를 소유하는가?"를 찾으려면, 수백만 장의 '주주 테이블', '법인 테이블', '지분 변동 테이블'을 펼쳐놓고 컴퓨터가 눈이 빠져라 JOIN을 반복해야 합니다. 다리(Hop)가 3개만 넘어가도 컴퓨터가 멈춰버립니다 (JOIN 폭발).
2. **그래프 데이터베이스 (GraphDB: 실뜨기 지도)**:
   - 회사와 주주를 핀(노드)으로 꽂고, 둘 사이를 화살표 실(관계)로 직접 묶어둡니다.
   - "A의 지분을 따라가 봐!" 하면 실을 잡고 스르륵 손가락만 이동하면 끝납니다. 데이터가 수억 건으로 늘어나도 **내 손에 닿아있는 실의 개수만큼만 시간이 걸립니다 (Index-Free Adjacency).**

---

## 🛠️ 2. HOW: 속성 그래프 모델(LPG)의 4대 핵심 구성 요소

현업 실무에서 가장 널리 쓰이는 Neo4j의 **LPG (Labeled Property Graph)** 모델은 4가지 요소로 구성됩니다:

```text
       ┌────────────────────────────────────────────────────────┐
       │                      [LPG 4대 요소]                     │
       │                                                        │
       │   (:Label) ───[ :RELATION_TYPE { properties } ]───> (:Label)
       │    [노드]                   [관계/엣지]               [노드]
       └────────────────────────────────────────────────────────┘
```

1. **노드 (Node / Vertex)**:
   - 실세계의 고유한 개체(Entity).
   - 예: `삼성전자` (회사), `국민연금공단` (주주), `중앙대학교` (대학), `공간연출전공` (학과)
2. **라벨 (Label)**:
   - 노드의 역할을 그룹화하고 인덱스를 걸기 위한 분류 태그 (다중 라벨 가능).
   - 예: `:Company`, `:Shareholder:InstitutionalInvestor`, `:University`, `:PracticalType`
3. **관계 (Relationship / Edge)**:
   - 노드와 노드를 연결하는 방향성 있는 화살표 (반드시 출발 노드와 도착 노드가 존재함).
   - 예: `-[:HOLDS_ECONOMIC_STAKE]->`, `-[:OFFERS_TRACK]->`, `-[:REQUIRES_PRACTICAL]->`
4. **속성 (Properties)**:
   - 노드나 관계 자체에 붙는 Key-Value 쌍의 데이터.
   - 예: 노드 속성 `corp_code: '00126380'`, 관계 속성 `stake_ratio: 7.25%`, `stage: 1`

---

## 🏢 3. [DART-Trace] 실제 적용 사례 (RDB vs LPG 비교)

### 1) 서비스 질문
> *"삼성전자의 5% 이상 지분을 보유한 주주들과, 그 주주가 동시에 투자하고 있는 다른 상장사 목록을 찾아라."*

### 2) RDB 모델 vs LPG 그래프 모델 구조 대조
* **RDB 접근 방식 (테이블 4중 JOIN)**:
  ```sql
  -- 극심한 테이블 스캔과 외래키(FK) 결합으로 쿼리 지연 발생
  SELECT c2.corp_name, s.holder_name, h2.stake_ratio
  FROM companies c1
  JOIN holdings h1 ON c1.corp_code = h1.target_corp_code
  JOIN shareholders s ON h1.holder_id = s.id
  JOIN holdings h2 ON s.id = h2.holder_id
  JOIN companies c2 ON h2.target_corp_code = c2.corp_code
  WHERE c1.corp_name = '삼성전자' AND h1.stake_ratio >= 5.0;
  ```
* **LPG 그래프 모델 (직관적 경로 패턴 매칭)**:
  ```cypher
  // 포인터를 따라 손가락 이동하듯 0.001초 만에 2-hop 경로 탐색
  MATCH (c1:Company {name: '삼성전자'})<-[h1:HOLDS_ECONOMIC_STAKE]-(s:Shareholder)-[h2:HOLDS_ECONOMIC_STAKE]->(c2:Company)
  WHERE h1.stake_ratio >= 5.0
  RETURN s.name, c2.name, h2.stake_ratio;
  ```

---

## 🎨 4. [ART:READY] 실제 적용 사례 (`cau_spatial_design.json` 기준)

### 1) 서비스 질문
> *"공간연출전공에서 1단계 실기 80%로 소묘를 평가하고 10월 3일에 시험을 보는 전형을 찾아라."*

### 2) LPG 그래프 모델 설계
* **노드**:
  - `(u:University {name: '중앙대학교', campus: '서울'})`
  - `(d:Department {name: '공간연출전공'})`
  - `(t:AdmissionTrack {name: '2027 수시 실기형', year: 2027})`
  - `(p:PracticalType {name: '소묘'})`
  - `(e:ExamSchedule {date: '2026-10-03'})`
* **관계 (선)**:
  - `(u)-[:OFFERS_TRACK]->(t)`
  - `(d)-[:BELONGS_TO]->(u)`
  - `(t)-[:REQUIRES_PRACTICAL {stage: 1, ratio: 80}]->(p)`
  - `(t)-[:EXAM_ON {stage: 1}]->(e)`
* **비즈니스 가치**:
  - 학생이 "10월 3일 시험 없는 다른 미대 전형 보여줘"라고 했을 때, RDB처럼 복잡한 날짜 서브쿼리 없이 `NOT (t)-[:EXAM_ON]->(:ExamSchedule {date: '2026-10-03'})`로 즉시 그래프 필터링 가능!

---

## ⚖️ 5. RDF vs LPG 실무 선택 기준: 왜 우리는 LPG(Neo4j)를 쓰는가?

| 비교 항목 | 학술용 시맨틱 웹 (RDF / OWL) | 실무 프로덕션 지식그래프 (LPG / Neo4j) | 우리 서비스 선택 이유 |
|---|---|---|:---:|
| **데이터 단위** | `(Subject, Predicate, Object)` 순수 3칸 | `(:Node {props}) -[:EDGE {props}]-> (:Node)` | LPG 채택 |
| **관계 속성** | 관계 자체에 속성을 달 수 없음 (재구체화 필요) | **관계(Edge)에 `stake_ratio: 7.25`를 바로 기록** | **LPG 압승 (지분율, 시험배점 즉시 기록)** |
| **질의 언어** | SPARQL (학술적, 복잡함) | **Cypher (ASCII 아트 기반 직관적 문법)** | **LPG 압승 (엔지니어 생산성 극대화)** |
| **주요 활용처** | 위키데이터(Wikidata), 의학 온톨로지 공개 | **금융 부정거래 탐지, 지배구조 추적, 추천 챗봇** | **LPG 압승 (실서비스 고성능 서빙)** |

---

## 🔍 6. 현재 구현 및 원본 근거
* **DART-Trace**:
  - Neo4j Aura Cloud에 79,848개 노드 및 관계 적재 완료.
  - `Company`, `Shareholder`, `EvidenceFragment` 간의 LPG 모델이 `00_Raw_Evidence_Graph_Loader.py`에 완전 반영.
* **ART:READY**:
  - `cau_spatial_design.json` 및 15개교 미대 입시 데이터셋이 `University`, `AdmissionTrack`, `PracticalType` LPG 구조로 정의 완료.

---

## ⚠️ 7. 부족한 부분 하나 (결손 과제)
* **결손 과제**: RDB(CSV, JSON) 데이터를 처음 접했을 때, "어떤 컬럼을 노드로 빼고, 어떤 컬럼을 관계 속성으로 넣어야 하는가?"에 대한 **체계적 그래프 모델링 변환 규칙서**가 명문화되어 있지 않았음. ➔ 오늘 `00_Day27_그래프_모델링_스키마_및_명세서.md`에서 완벽히 수립함.

---

## 🧪 8. DRY-RUN 및 완료 판정 (Done Definition)

1. **RDB vs LPG 변환 검증**:
   - DART 지분 관계(주주-기업)와 ART 입시 관계(대학-전형-실기)를 3칸 이상의 외래키 JOIN 없이 단일 경로 패턴으로 표현 가능한가? -> **PASS ✅**
2. **관계 속성 보존 검증**:
   - 지분율(7.25%)이나 실기 반영비(80%)가 별도 중계 테이블 없이 관계(Edge) 프로퍼티에 직접 저장되는가? -> **PASS ✅**
3. **판정**: **기준 만족 시 Day 27 마스터 합격 🟢**
