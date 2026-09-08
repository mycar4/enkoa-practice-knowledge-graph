# 🏛️ [Day 34] GDS 커뮤니티 탐지·순환출자 사이클·무충돌 입시경로 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day34_GDS_커뮤니티_유사도_경로/00_Day34_GDS_커뮤니티_유사도_경로_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 34 커뮤니티 탐지 & 순환출자/일정 경로 탐색]
   - Day 27 (그래프 모델링): 속성 그래프(LPG) 모델링 기초 (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 구축 및 실데이터 최초 적재 (완료 ✅)
   - Day 29 (Cypher 기초)  : MATCH, WHERE, RETURN 기본 문법 (완료 ✅)
   - Day 30 (Cypher 심화)  : UNWIND 배치 적재, WITH 체이닝, 다중 홉 탐색 (완료 ✅)
   - Day 31 (인덱스/집계)  : 지분율 합산(SUM), 모집정원 카운트, EXPLAIN/PROFILE 성능 최적화 (완료 ✅)
   - Day 32 (구축/적재)    : 3,746건 대량 공시 및 15개교 요강 멱등 트랜잭션 적재 (완료 ✅)
   - Day 33 (GDS 중심성)  : 인메모리 투영 및 실질 지배사 PageRank 랭킹 (완료 ✅)
   - Day 34 (커뮤니티/경로): 순환출자 루프(A➔B➔C➔A) 탐지 및 6개 대학 무충돌 입시 경로 (현재)
   - Day 35 (GraphRAG)     : 공시 XML 벡터 인덱스 + 그래프 결합 RAG 완결
```
> **학습 목적**: "단순 1:1 관계를 넘어, **법적으로 엄격히 규제되는 대기업 집단의 순환출자 폐쇄 루프(`A ➔ B ➔ C ➔ A`)를 최단/가변 경로 알고리즘으로 적발하고, 수험생에게 날짜가 겹치지 않는 최적의 수시 6개 대학 실기 시험 응시 경로(Disjoint Path)**를 그래프로 완전 자동화하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 커뮤니티와 경로 탐색인가?)

### 10초 초등생 비유: "꼬리 물기 뱀(순환출자)과 겹치지 않는 기차 시간표(무충돌 경로)"
1. **순환출자 루프 (꼬리 물기 뱀)**:
   - A 회사가 B 회사에 돈을 넣고, B가 C에 넣고, C가 다시 A에 넣으면 '가짜 자본'이 만들어집니다. Cypher 경로 탐색(`MATCH path = (c)-[*..]->(c)`)으로 꼬리를 물고 있는 폐쇄 고리를 찾아냅니다.
2. **커뮤니티 탐지 (WCC / Louvain - 재벌 그룹 분리)**:
   - 3,746건 공시에서 서로 지분을 주고받은 회사들끼리 같은 색깔을 칠하면, '삼성그룹', 'SK그룹', '현대차그룹'이 사람 손길 없이도 자동으로 깔끔하게 그룹핑(Clustering)됩니다.
3. **무충돌 일정 경로 (Disjoint Path)**:
   - 수험생은 수시 6개 대학에 지원할 수 있습니다. 6개 대학의 실기 시험 날짜가 하루라도 겹치면 원서비 10만 원을 날리고 시험을 못 봅니다. 그래프 경로 탐색으로 날짜 충돌이 전혀 없는 안전한 6개 대학 조합을 추천합니다.

---

## 🛠️ 2. HOW: 알고리즘 실행 메커니즘

```text
       ┌────────────────────────────────────────────────────────┐
       │             [순환출자 및 무충돌 경로 탐색 메커니즘]       │
       │                                                        │
       │   1. 사이클 탐지:                                      │
       │      MATCH p = (c:Company)-[:OWNS*2..4]->(c)           │
       │      └─ 시작 노드와 끝 노드가 동일한 Closed Loop 적발   │
       │                                                        │
       │   2. 약한 연결 컴포넌트 (WCC 커뮤니티):                │
       │      CALL gds.wcc.stream('dartGraph')                  │
       │      └─ 지분 연결망 기반 재벌 그룹 자동 클러스터링     │
       │                                                        │
       │   3. 고사 일정 무충돌 매칭:                            │
       │      MATCH (t1)-[:EXAM_ON]->(e1), (t2)-[:EXAM_ON]->(e2)│
       │      WHERE e1.exam_date <> e2.exam_date                │
       │      └─ 일자 충돌 0건 독립 집합(Disjoint Set) 도출     │
       └────────────────────────────────────────────────────────┘
```

---

## 🏢 3. [DART-Trace] 순환출자 사이클 및 계열사 클러스터링 시나리오

```cypher
// 1. 대기업 순환출자 폐쇄 루프 탐지 (2~4홉)
MATCH path = (c:Company)-[r:HOLDS_ECONOMIC_STAKE*2..4]->(c)
RETURN 
    c.name AS starting_company,
    length(path) AS cycle_length,
    [n in nodes(path) | n.name] AS cycle_chain;
```

---

## 🎨 4. [ART:READY] 수시 실기 일정 무충돌(Non-Overlapping) 경로 시나리오

```cypher
// 2개 이상 대학 지원 시 실기 고사일이 겹치지 않는 안전 지원 조합 도출
MATCH (u1:University)-[:OFFERS_TRACK]->(t1:AdmissionTrack)-[:EXAM_ON]->(e1:ExamSchedule)
MATCH (u2:University)-[:OFFERS_TRACK]->(t2:AdmissionTrack)-[:EXAM_ON]->(e2:ExamSchedule)
WHERE u1.univ_code < u2.univ_code AND e1.exam_date <> e2.exam_date
RETURN 
    u1.name + ' (' + t1.name + ')' AS choice_1,
    e1.exam_date AS date_1,
    u2.name + ' (' + t2.name + ')' AS choice_2,
    e2.exam_date AS date_2;
```

---

## 📊 5. 7단 분석: 레거시 교육 대비 우리 실데이터 우위

| 분석 축 | 과거 레거시 교재 방식 (영화/장난감) | [DART·ART] 우리 실데이터 표준 방식 |
| :--- | :--- | :--- |
| **분석 대상** | 배우 간 공동 출연 최단 경로 (케빈 베이컨) | **공정위 규제 대상 대기업 순환출자 루프 적발** |
| **커뮤니티** | 영화 장르별 단순 묶음 | **WCC 기반 상호출자제한 대기업집단 자동 식별** |
| **경로 가치** | 단순 재미용 퀴즈 | **수시 원서 접수 실수 방지 무충돌 캘린더 생성** |

---

## 🏁 6. 최종 완료 판정 기준
- 순환출자 루프 1건 이상 감지 및 사이클 체인 출력 성공.
- 고사일자 무충돌 지원 조합 도출 완료 시 `ALL PASS` 판정.
