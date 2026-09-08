# 🏛️ [Day 35] 벡터 인덱스·GraphRAG(지식그래프+LLM) 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day35_벡터검색_GraphRAG/00_Day35_벡터검색_GraphRAG_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 35 GraphRAG 최종 완결]
   - Day 27 (그래프 모델링): 속성 그래프(LPG) 모델링 기초 (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 구축 및 실데이터 최초 적재 (완료 ✅)
   - Day 29 (Cypher 기초)  : MATCH, WHERE, RETURN 기본 문법 (완료 ✅)
   - Day 30 (Cypher 심화)  : UNWIND 배치 적재, WITH 체이닝, 다중 홉 탐색 (완료 ✅)
   - Day 31 (인덱스/집계)  : 지분율 합산(SUM), 모집정원 카운트, EXPLAIN/PROFILE 성능 최적화 (완료 ✅)
   - Day 32 (구축/적재)    : 3,746건 대량 공시 및 15개교 요강 멱등 트랜잭션 적재 (완료 ✅)
   - Day 33 (GDS 중심성)  : 인메모리 투영 및 실질 지배사 PageRank 랭킹 (완료 ✅)
   - Day 34 (커뮤니티/경로): 순환출자 루프(A➔B➔C➔A) 탐지 및 6개 대학 무충돌 입시 경로 (완료 ✅)
   - Day 35 (GraphRAG)     : 공시 XML 벡터 인덱스 + 그래프 결합 RAG 완결 (현재)
★ [Phase 1: 정보추출 & 온톨로지 고도화] (Day 36~37) (완료 ✅)
```
> **학습 목적**: "단순 텍스트 검색(일반 RAG)의 치명적 한계인 '숫자 왜곡'과 '관계 단절'을 극복하기 위해, **의미 검색(Vector Search)으로 질문과 관련된 엔터티를 먼저 찾고, 그 엔터티와 연결된 지식그래프의 엄밀한 지분율/일정 팩트(Graph Traversal)를 결합하여 환각 0%의 무결점 GraphRAG 서비스를 완성**하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 일반 RAG가 아니라 GraphRAG인가?)

### 10초 초등생 비유: "어렴풋한 기억(벡터 검색)과 정확한 가족관계증명서(지식그래프)"
1. **일반 RAG의 치명적 한계 (Vector-Only)**:
   - "삼성전자의 최대주주는 누구이며 지분율은 몇 %인가?"라고 물으면, 일반 RAG는 수천 개의 공시 텍스트 중 비슷한 문장을 대충 긁어와서 옛날 수치나 다른 회사 지분을 마구 섞어 엉뚱한 헛소리(Hallucination)를 지어냅니다.
2. **GraphRAG의 절대적 신뢰성 (Vector + Graph)**:
   - 1단계: 사용자의 자연어 질문("삼성전자 지분 구조 알려줘")을 벡터 검색으로 임베딩하여 그래프의 `Company {name: '삼성전자'}` 앵커 노드를 정확히 찍습니다.
   - 2단계: 그 앵커 노드로부터 뻗어나가는 `HOLDS_ECONOMIC_STAKE` 관계와 원천 공시 `EvidenceFragment`의 XPath 증거를 그래프 홉으로 100% 실측 추출합니다.
   - 3단계: LLM에게 "이 그래프 팩트와 출처 증거만을 바탕으로 답하라"고 지시하여 **오차 0.00%의 완벽한 답변**을 생성합니다.

---

## 🛠️ 2. HOW: GraphRAG 3단계 융합 파이프라인

```text
  [사용자 자연어 질문]
         │
         ▼ (1) Vector Search
  ┌────────────────────────────────────────────────────────┐
  │ CALL db.index.vector.queryNodes('chunkVectorIndex', ...)│
  │ ➔ 의미적으로 가장 유사한 청크 및 앵커 엔터티 노드 식별    │
  └────────────────────────────────────────────────────────┘
         │
         ▼ (2) Graph Multi-Hop Traversal (정밀 팩트 결합)
  ┌────────────────────────────────────────────────────────┐
  │ MATCH (anchor)-[:HOLDS_ECONOMIC_STAKE]-(related)       │
  │ MATCH (anchor)-[:BACKED_BY_EVIDENCE]->(evidence)       │
  │ ➔ 수치(지분율/실기비중) 및 법적 공시 원문 XPath 추출     │
  └────────────────────────────────────────────────────────┘
         │
         ▼ (3) LLM Grounded Generation (환각 0% 답변 생성)
  ┌────────────────────────────────────────────────────────┐
  │ "삼성전자의 최대주주는 삼성생명보험(8.51%)이며,          │
  │  국민연금공단(7.25%)이 2대 주주입니다. (출처: 공시 3호)" │
  └────────────────────────────────────────────────────────┘
```

---

## 🏢 3. [DART-Trace] 실전 GraphRAG 시나리오

```cypher
// 1. 공시 본문 벡터 인덱스 유사도 질의
CALL db.index.vector.queryNodes('dartTextChunkIndex', 3, $question_embedding)
YIELD node AS chunk, score
// 2. 검색된 청크와 연결된 기업 노드 및 주주 지분 그래프 확장
MATCH (chunk)<-[:HAS_CHUNK]-(c:Company)<-[r:HOLDS_ECONOMIC_STAKE]-(s:Shareholder)
MATCH (c)-[:BACKED_BY_EVIDENCE]->(e:EvidenceFragment)
RETURN 
    c.name AS company,
    s.name AS shareholder,
    r.stake_ratio AS stake_ratio,
    e.rcept_no AS report_no,
    e.table_xpath AS evidence_xpath,
    score AS semantic_similarity
ORDER BY stake_ratio DESC;
```

---

## 🎨 4. [ART:READY] 실전 GraphRAG 입시 질의 시나리오

> *"중앙대학교 실기 80% 이상 들어가는 전형과 일정 알려줘"*
```cypher
// 벡터 검색으로 '중앙대 실기 비중' 관련 요강 청크 탐색 후 그래프 확장
CALL db.index.vector.queryNodes('artHandbookIndex', 2, $question_embedding)
YIELD node AS chunk, score
MATCH (chunk)<-[:MENTIONED_IN]-(t:AdmissionTrack)<-[:OFFERS_TRACK]-(u:University)
MATCH (t)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
OPTIONAL MATCH (t)-[:EXAM_ON]->(e:ExamSchedule)
RETURN 
    u.name AS university,
    t.name AS track_name,
    p.name AS practical_type,
    r.ratio AS practical_ratio,
    coalesce(e.exam_date, '미정') AS exam_date;
```

---

## 📊 5. 7단 분석: 레거시 교육 대비 우리 실데이터 우위

| 분석 축 | 과거 레거시 교재 방식 (영화 줄거리 단순 RAG) | [DART·ART] 우리 실데이터 표준 GraphRAG 방식 |
| :--- | :--- | :--- |
| **검색 대상** | 영화 시놉시스 텍스트 몇 줄 | **3,746건 공시 XML 텍스트 청크 & 15개교 요강** |
| **결합 구조** | 단순 텍스트 Top-K 청크 LLM 주입 | **Vector Anchor ➔ Graph Hop ➔ Grounding Fact 결합** |
| **환각 방어력** | LLM이 지분율/일정을 마음대로 조작 | **원천 공시 접수번호 및 XPath 증거 100% 강제 검증** |
| **실서비스 직결** | 데모용 장난감 챗봇 | **실제 공시 추적 서비스 및 미대입시 챗봇 엔진 프로덕션** |

---

## 🏁 6. 최종 완료 판정 기준
- Vector Query ➔ Graph Traversal ➔ Context Assemble 3단계 정상 실행.
- 환각 없는 정밀 수치(지분율, 고사일) 및 증거 XPath 결합 완료 시 `ALL PASS` 판정.
