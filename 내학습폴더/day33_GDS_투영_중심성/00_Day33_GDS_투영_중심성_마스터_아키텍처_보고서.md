# 🏛️ [Day 33] GDS 인메모리 그래프 투영·중심성(PageRank) 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day33_GDS_투영_중심성/00_Day33_GDS_투영_중심성_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 33 GDS 인메모리 투영 & 중심성 분석]
   - Day 27 (그래프 모델링): 속성 그래프(LPG) 모델링 기초 (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 구축 및 실데이터 최초 적재 (완료 ✅)
   - Day 29 (Cypher 기초)  : MATCH, WHERE, RETURN 기본 문법 (완료 ✅)
   - Day 30 (Cypher 심화)  : UNWIND 배치 적재, WITH 체이닝, 다중 홉 탐색 (완료 ✅)
   - Day 31 (인덱스/집계)  : 지분율 합산(SUM), 모집정원 카운트, EXPLAIN/PROFILE 성능 최적화 (완료 ✅)
   - Day 32 (구축/적재)    : 3,746건 대량 공시 및 15개교 요강 멱등 트랜잭션 적재 (완료 ✅)
   - Day 33 (GDS 중심성)  : 인메모리 투영(gds.graph.project) 및 실질 지배사 PageRank 랭킹 (현재)
   - Day 34~35             : 순환출자 탐지 ➔ GraphRAG
```
> **학습 목적**: "단순 1촌 지분율 조회를 넘어, **수천 개 기업과 주주가 얽힌 복잡한 지분 네트워크를 고속 RAM에 통째로 투영(`gds.graph.project`)하고 PageRank 알고리즘을 돌려, 겉으로 드러나지 않는 그룹 내 '실질 최상위 지배회사'와 입시 지원의 핵심 허브 실기과목을 정밀 산출**하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 GDS와 PageRank인가?)

### 10초 초등생 비유: "구글 검색 랭킹(PageRank)과 거미줄 중심 왕거미"
1. **디스크 vs 메모리 (GDS 투영의 이유)**:
   - 디스크 DB에서 수만 번 왕복하며 중심성을 계산하면 하드디스크가 닳아 없어집니다. GDS는 분석할 노드와 관계만 고속 RAM으로 쏙 복제해 올려서 1초에 수백만 번 연산합니다.
2. **PageRank (영향력의 크기)**:
   - 나에게 돈을 투자한 회사가 얼마나 대단한 회사인가? 대단한 주주들이 돈을 몰아준 회사일수록 PageRank 점수가 치솟습니다. 단순 지분율 1위가 아니라, 그룹 지배구조의 진짜 '정점'을 밝혀냅니다.
3. **연결 중심성 (Degree Centrality - 입시 허브)**:
   - 어떤 실기 과목(예: 기초디자인)이 서울 주요 대학들의 전형에 가장 많이 연결되어 있는가? 학생들에게 '가장 가성비 높은 필승 실기과목'을 데이터로 증명해 줍니다.

---

## 🛠️ 2. HOW: GDS 3단계 실행 사이클

```text
       ┌────────────────────────────────────────────────────────┐
       │               [GDS 실행 3단계 표준 라이프사이클]          │
       │                                                        │
       │   1. 서브그래프 투영 (Project):                         │
       │      CALL gds.graph.project('dartStakeGraph', ...)     │
       │                                                        │
       │   2. 중심성 알고리즘 스트리밍 (Execute & Stream):       │
       │      CALL gds.pageRank.stream('dartStakeGraph')        │
       │      YIELD nodeId, score ── 점수 산출 및 정렬          │
       │                                                        │
       │   3. 메모리 해제 (Drop):                               │
       │      CALL gds.graph.drop('dartStakeGraph')             │
       └────────────────────────────────────────────────────────┘
```

---

## 🏢 3. [DART-Trace] 지배회사 PageRank 실전 시나리오

```cypher
// 1. DART 지분 그래프 인메모리 투영
CALL gds.graph.project(
  'dartStakeGraph',
  ['Company', 'Shareholder'],
  {
    HOLDS_ECONOMIC_STAKE: {
      type: 'HOLDS_ECONOMIC_STAKE',
      orientation: 'NATURAL',
      properties: 'stake_ratio'
    }
  }
);

// 2. 가중치 기반 PageRank 실행 -> 실질 지배력 랭킹 도출
CALL gds.pageRank.stream('dartStakeGraph', {
  relationshipWeightProperty: 'stake_ratio',
  dampingFactor: 0.85,
  maxIterations: 20
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS entity_name, score
ORDER BY score DESC
LIMIT 5;
```

---

## 🎨 4. [ART:READY] 실기과목 연결 중심성(Degree Centrality) 시나리오

```cypher
// 1. 미대 전형 요강 그래프 인메모리 투영
CALL gds.graph.project(
  'artPracticalGraph',
  ['AdmissionTrack', 'PracticalType'],
  'REQUIRES_PRACTICAL'
);

// 2. 실기종목별 연결된 전형 수(In-Degree) 중심성 랭킹 산출
CALL gds.degree.stream('artPracticalGraph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS n, score
WHERE n:PracticalType
RETURN n.name AS practical_subject, score AS connected_tracks_count
ORDER BY score DESC;
```

---

## 📊 5. 7단 분석: 레거시 교육 대비 우리 실데이터 우위

| 분석 축 | 과거 레거시 교재 방식 (영화/의학) | [DART·ART] 우리 실데이터 표준 방식 |
| :--- | :--- | :--- |
| **분석 대상** | 영화 배우 출연작 PageRank | **재벌 지배구조 실질 지배사 PageRank & 입시 실기 중심성** |
| **관계 가중치** | 단순 무가중치(Unweighted) | **공시 지분율(stake_ratio) 기반 가중 그래프 투영** |
| **비즈니스 활용** | 유명 배우 찾기 (흥미 위주) | **실질 지배주주 규명, 공정위 규제 대상 식별, 입시 최적 종목 도출** |

---

## 🏁 6. 최종 완료 판정 기준
- `gds.graph.project` 정상 투영 및 메모리 반환(`drop`) 100% 확인.
- 가중치 PageRank 및 Degree Centrality 계산 완료 시 `ALL PASS` 판정.
