# 📑 [Day 30] Cypher 심화 스키마 및 쿼리 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규)  
> **위치**: `내학습폴더/day30_Cypher_심화/00_Day30_Cypher_심화_스키마_및_쿼리명세서.md`  
> **기준 문서**: [DART_ART_학습대조_데이터명세서_v1.0.md](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 1. 개요 및 목적
본 명세서는 고성능 지식그래프 엔지니어링을 위해 필수적인 Cypher 심화 절(`UNWIND`, `WITH`, `OPTIONAL MATCH`, 다중 홉 탐색)의 실전 쿼리 템플릿과 실행 규칙을 정의합니다.
파이썬 왕복 통신을 최소화하는 대량 데이터 배치 적재 기법과 결손 속성 방어 쿼리를 표준화합니다.

---

## 2. 노드 및 관계 스키마 요약

### 1) [DART-Trace] 대상 스키마
- **노드**:
  - `Company` : `{corp_code (고유키), name, market_type}`
  - `Shareholder` : `{holder_key (고유키), name, holder_type}`
  - `EvidenceFragment` : `{fragment_id (고유키), rcept_no, table_xpath}`
- **관계**:
  - `(Shareholder)-[:HOLDS_ECONOMIC_STAKE {stake_ratio, base_date}]->(Company)`
  - `(Company)-[:BACKED_BY_EVIDENCE]->(EvidenceFragment)`

### 2) [ART:READY] 대상 스키마
- **노드**:
  - `University` : `{univ_code (고유키), name, campus}`
  - `AdmissionTrack` : `{track_id (고유키), name, season}`
  - `PracticalType` : `{code (고유키), name, category}`
  - `ExamSchedule` : `{schedule_id (고유키), exam_date, location}`
- **관계**:
  - `(University)-[:OFFERS_TRACK]->(AdmissionTrack)`
  - `(AdmissionTrack)-[:REQUIRES_PRACTICAL {stage, ratio}]->(PracticalType)`
  - `(AdmissionTrack)-[:EXAM_ON]->(ExamSchedule)` (일정 미발표 시 관계 누락 가능 ➔ OPTIONAL MATCH 대상)

---

## 3. 핵심 Cypher 심화 쿼리 템플릿

### Q1. 대량 지분 데이터 1방 배치 적재 (`UNWIND` + `MERGE`)
```cypher
// 설명: 파이썬에서 전송한 수십 개 딕셔너리 리스트를 DB 내부에서 고속 언패킹하여 멱등 적재
UNWIND $batch AS row
MERGE (c:Company {corp_code: row.corp_code})
  ON CREATE SET c.name = row.corp_name, c.market_type = row.market_type
MERGE (s:Shareholder {holder_key: row.holder_key})
  ON CREATE SET s.name = row.holder_name, s.holder_type = row.holder_type
MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
  ON CREATE SET r.stake_ratio = row.stake_ratio, r.base_date = row.base_date;
```

### Q2. 결손 일정 방어 및 다중 관계 조회 (`OPTIONAL MATCH` + `coalesce`)
```cypher
// 설명: 실기 일정이 아직 발표되지 않은 전형도 누락 없이 null 방어하여 조회
MATCH (u:University {univ_code: $univ_code})-[:OFFERS_TRACK]->(t:AdmissionTrack)
MATCH (t)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
OPTIONAL MATCH (t)-[:EXAM_ON]->(e:ExamSchedule)
RETURN 
    u.name AS university,
    u.campus AS campus,
    t.name AS track_name,
    p.name AS practical_subject,
    r.ratio AS practical_ratio,
    coalesce(e.exam_date, '일정 미발표(TBD)') AS exam_date
ORDER BY practical_ratio DESC, track_name;
```

### Q3. 파이프라인 중간 필터링 및 집계 바통 전달 (`WITH` 절)
```cypher
// 설명: 1단계 실기 비중이 70% 이상인 전형을 먼저 추린 뒤, 후속 조건(실기 과목명) 필터링
MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
WHERE r.ratio >= $min_ratio
WITH u, t, p, r
WHERE p.name CONTAINS $keyword
RETURN 
    u.name AS university,
    t.name AS track_name,
    p.name AS practical_subject,
    r.ratio AS practical_ratio;
```

### Q4. 1~2단계 연쇄 지분 소유 다중 홉 탐색 (Variable-Length Path)
```cypher
// 설명: 특정 기업의 주주 및 그 주주와 연결된 모회사/연계회사를 1~2홉 범위에서 탐색
MATCH path = (c:Company {corp_code: $target_corp_code})<-[:HOLDS_ECONOMIC_STAKE*1..2]-(investor)
RETURN 
    length(path) AS hops,
    [n in nodes(path) | coalesce(n.name, labels(n)[0])] AS chain,
    investor.name AS ultimate_investor;
```

---

## 4. 성능 최적화 및 멱등 가드 체크리스트
1. **UNWIND 배치 크기 가이드**: 1회 호출당 권장 배치 크기는 500 ~ 2,000건입니다.
2. **WITH 파이프라인 누수 방지**: WITH 절에 불필요한 노드/속성을 담지 않고 필수 키(`id`, `count`, `집계값`)만 넘겨 메모리를 절약합니다.
3. **OPTIONAL MATCH 위치**: 반드시 기본 앵커가 되는 `MATCH` 절 뒤에 배치하여 카테시안 곱(Cartesian Product) 연산을 차단합니다.
