# 🏛️ [Day 30] Cypher 심화(UNWIND·WITH·OPTIONAL MATCH·다중 홉) 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day30_Cypher_심화/00_Day30_Cypher_심화_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 30 Cypher 심화 파이프라인]
   - Day 27 (그래프 모델링): 속성 그래프(LPG) 모델링 기초 (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 구축 및 실데이터 최초 적재 (완료 ✅)
   - Day 29 (Cypher 기초)  : MATCH, WHERE, RETURN 기본 문법 (완료 ✅)
   - Day 30 (Cypher 심화)  : UNWIND 배치 적재, WITH 체이닝, 다중 홉 탐색 (현재)
   - Day 31 (인덱스/집계)  : 지분율 합산(SUM), 모집정원 카운트, 인덱스 튜닝
   - Day 32~35             : 멱등 적재 ➔ GDS PageRank ➔ 순환출자 탐지 ➔ GraphRAG
```
> **학습 목적**: "수천 번의 파이썬 for문 API 호출 대신 **`UNWIND`로 한 번에 대량 공시를 배치 적재**하고, 일정이 아직 확정되지 않은 전형도 누락 없이 살려내는 **`OPTIONAL MATCH`**와 **다중 홉(Multi-Hop) 지분 연쇄 추적**을 장악하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 Cypher 심화 절들이 필요한가?)

### 10초 초등생 비유: "포크레인 한 바가지(UNWIND)와 이어달리기 바통(WITH)"
1. **`UNWIND` (포크레인 한 바가지)**:
   - 공시 보고서 1건에는 주주 50명의 지분 정보가 들어있습니다. 파이썬 for문으로 50번 `session.run()`을 돌리면 50번의 왕복 네트워크 지연(RTT)으로 세월이 다 갑니다.
   - 50개 리스트를 `UNWIND $batch AS row`로 한 번에 던지면, DB 내부에서 1방에 50개 행으로 쫘악 풀어서 단 0.01초 만에 적재합니다.
2. **`WITH` (이어달리기 바통)**:
   - 1단계에서 삼성전자 주주를 찾고, 그 결과를 바통(`WITH`)으로 넘겨받아 2단계로 그 주주들의 다른 투자사를 찾습니다. 중간 계산 결과나 필터링 조건을 다음 쿼리 단계로 깔끔하게 파이프라인 연결합니다.
3. **`OPTIONAL MATCH` (너그러운 외부 조인)**:
   - 어떤 대학은 요강에 실기 날짜가 아직 '미정'으로 비어 있습니다. 일반 `MATCH`를 쓰면 일정이 없다는 이유로 전형 전체가 결과에서 통째로 증발합니다. `OPTIONAL MATCH`를 쓰면 일정이 없어도 `null`로 살려둡니다.

---

## 🛠️ 2. HOW: Cypher 심화 4대 절의 실행 메커니즘

```text
       ┌────────────────────────────────────────────────────────┐
       │             [Cypher 심화 파이프라인 메커니즘]             │
       │                                                        │
       │   1. UNWIND $batch AS row      ── 리스트 파라미터를 행으로 언패킹
       │   2. MERGE ... ON CREATE SET   ── 대량 데이터 멱등 적재
       │   3. WITH s, count(*) AS cnt   ── 중간 집계 및 다음 단계 바통 전달
       │   4. OPTIONAL MATCH (t)-[:EXAM]── 결손 속성을 null로 안전 포괄
       │   5. MATCH p=(c1)-[*1..3]->(c2)── 1~3홉 가변 경로 연쇄 추적
       └────────────────────────────────────────────────────────┘
```

---

## 🏢 3. [DART-Trace] 실전 심화 시나리오

### 1) 서비스 질문 1: 대량 공시 배치 적재 (`UNWIND`)
```cypher
// 1회 네트워크 호출로 수십 개 주주 지분을 동시 멱등 적재
UNWIND $shareholders_batch AS row
MERGE (c:Company {corp_code: row.corp_code})
  ON CREATE SET c.name = row.corp_name
MERGE (s:Shareholder {holder_key: row.holder_key})
  ON CREATE SET s.name = row.holder_name, s.holder_type = row.holder_type
MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
  ON CREATE SET r.stake_ratio = row.stake_ratio, r.base_date = row.base_date;
```

### 2) 서비스 질문 2: 연쇄 지분 소유 2-Hop 탐색 (다중 홉)
> *"A 기업에 5% 이상 지분을 가진 주주가 지분을 5% 이상 가진 또 다른 기업 B, 그리고 그 B가 지배하는 기업 C를 찾아라."*
```cypher
MATCH path = (c1:Company {name: '삼성전자'})<-[:HOLDS_ECONOMIC_STAKE*1..2]-(investor)
RETURN path
LIMIT 10;
```

---

## 🎨 4. [ART:READY] 실전 심화 시나리오

### 1) 서비스 질문 1: 고사 일정이 미정인 전형도 누락 없이 조회 (`OPTIONAL MATCH`)
> *"중앙대학교의 모든 전형과 실기 과목을 조회하되, 실기 일정이 아직 발표되지 않은 전형도 누락 없이 표시하라."*
```cypher
MATCH (u:University {name: '중앙대학교'})-[:OFFERS_TRACK]->(t:AdmissionTrack)
MATCH (t)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
OPTIONAL MATCH (t)-[:EXAM_ON]->(e:ExamSchedule)
RETURN 
    u.campus AS campus,
    t.name AS track_name,
    p.name AS practical_subject,
    r.ratio AS practical_ratio,
    coalesce(e.exam_date, '일정 미정(TBD)') AS exam_date
ORDER BY campus, t.name;
```

### 2) 서비스 질문 2: 1단계 실기 80% 이상 전형을 뽑고, 2단계 면접이 있는 전형만 필터링 (`WITH` 체이닝)
```cypher
MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)-[r1:REQUIRES_PRACTICAL]->(p1:PracticalType)
WHERE r1.stage = 1 AND r1.ratio >= 80.0
// 1단계 조건을 만족한 전형만 바통을 넘김
WITH u, t, p1, r1
MATCH (t)-[r2:REQUIRES_PRACTICAL]->(p2:PracticalType)
WHERE r2.stage = 2
RETURN 
    u.name, t.name, 
    p1.name AS stage1_exam, r1.ratio AS stage1_ratio,
    p2.name AS stage2_exam, r2.ratio AS stage2_ratio;
```

---

## 🔍 5. 현재 구현 및 원본 근거
* **DART-Trace**:
  - `00_DART_Batch_Collector_1500.py` 및 `00_Raw_Evidence_Graph_Loader.py`에서 `UNWIND` 문을 사용하여 1,500건 이상의 대량 공시 데이터를 10초 이내에 배치 적재 중.
* **ART:READY**:
  - `art_admission_app.py`에서 실기 일정 미확정 대학을 안전하게 렌더링하기 위해 `OPTIONAL MATCH` 쿼리 활용 중.

---

## ⚠️ 6. 부족한 부분 하나 (결손 과제)
* **결손 과제**: 가변 길이 홉(`[*1..3]`) 탐색 시 순환 참조(A ➔ B ➔ A)가 걸렸을 때 탐색 깊이 제한(`maxLevel`)이 없으면 쿼리 폭주 위험 ➔ Cypher 쿼리에 명시적 홉 수(`*1..3`)와 `LIMIT` 가드레일 장착 의무화.

---

## 🧪 7. DRY-RUN 및 완료 판정 (Done Definition)

1. **`UNWIND` 배치 적재 검증**:
   - 10건 이상의 리스트 매개변수를 1회의 `UNWIND` 쿼리로 단일 트랜잭션 적재 성공 -> **PASS ✅**
2. **`OPTIONAL MATCH` 결손 방어 검증**:
   - 일정이 없는 노드도 증발하지 않고 `coalesce` 기본값('일정 미정')을 달고 정상 반환되는가? -> **PASS ✅**
3. **판정**: **기준 만족 시 Day 30 마스터 합격 🟢**
