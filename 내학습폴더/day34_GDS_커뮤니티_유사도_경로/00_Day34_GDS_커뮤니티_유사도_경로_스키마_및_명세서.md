# 📑 [Day 34] 커뮤니티 탐지 및 경로 탐색 스키마 및 쿼리 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규)  
> **위치**: `내학습폴더/day34_GDS_커뮤니티_유사도_경로/00_Day34_GDS_커뮤니티_유사도_경로_스키마_및_명세서.md`  
> **기준 문서**: [DART_ART_학습대조_데이터명세서_v1.0.md](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 1. 개요
지분 네트워크에서의 폐쇄 루프(순환출자 사이클) 검출, 지분 공유 기반 기업 클러스터링(WCC), 그리고 미대입시 복수 지원 시 일정 충돌을 방지하는 독립 경로(Disjoint Path) 쿼리 템플릿을 정의합니다.

---

## 2. 핵심 쿼리 템플릿 명세

### Q1. [DART-Trace] 순환출자 폐쇄 루프 사이클 탐지 (2~4 홉)
```cypher
// 설명: A사에서 출발하여 다른 계열사들을 거쳐 다시 A사로 돌아오는 지분 고리 탐지
MATCH path = (c:Company)-[r:HOLDS_ECONOMIC_STAKE*2..4]->(c)
RETURN 
    c.name AS starting_company,
    length(path) AS cycle_length,
    [n in nodes(path) | n.name] AS cycle_chain,
    [rel in relationships(path) | rel.stake_ratio] AS stake_ratios;
```

### Q2. [DART-Trace] 약한 연결 컴포넌트(WCC) 기반 기업집단 클러스터링
```cypher
// 설명: 서로 지분으로 묶여있는 연결 컴포넌트별로 그룹 ID를 부여하여 재벌 그룹 자동 분할
CALL gds.wcc.stream('dartStakeGraph')
YIELD nodeId, componentId
WITH gds.util.asNode(nodeId) AS n, componentId
RETURN 
    componentId,
    collect(n.name) AS group_members,
    count(n) AS group_size
ORDER BY group_size DESC;
```

### Q3. [ART:READY] 실기일정 무충돌(Non-Overlapping) 복수 지원 조합 생성
```cypher
// 설명: 2개 대학 지원 시 실기 시험 날짜가 겹치지 않는 안전 지원 포트폴리오
MATCH (u1:University)-[:OFFERS_TRACK]->(t1:AdmissionTrack)-[:EXAM_ON]->(e1:ExamSchedule)
MATCH (u2:University)-[:OFFERS_TRACK]->(t2:AdmissionTrack)-[:EXAM_ON]->(e2:ExamSchedule)
WHERE u1.univ_code < u2.univ_code AND e1.exam_date <> e2.exam_date
RETURN 
    u1.name AS univ_1,
    t1.name AS track_1,
    e1.exam_date AS exam_date_1,
    u2.name AS univ_2,
    t2.name AS track_2,
    e2.exam_date AS exam_date_2;
```

---

## 3. 검증 및 성능 고려사항
1. **가변 경로 길이 제한**: 사이클 탐지 시 `*` 무제한 홉을 주면 지수적 경로 폭발(Exponential Path Explosion)이 발생하므로 반드시 `*2..4`와 같이 명시적 상한선을 둘 것.
2. **비대칭 비교 필터링**: 무충돌 조합 탐색 시 `u1.univ_code < u2.univ_code` 조건을 부여하여 (A, B)와 (B, A)의 대칭 중복 페어를 원천 제거할 것.
