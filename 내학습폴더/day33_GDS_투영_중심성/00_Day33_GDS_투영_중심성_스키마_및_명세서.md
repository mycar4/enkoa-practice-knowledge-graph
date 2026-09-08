# 📑 [Day 33] GDS 인메모리 투영 및 중심성 알고리즘 쿼리 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규)  
> **위치**: `내학습폴더/day33_GDS_투영_중심성/00_Day33_GDS_투영_중심성_스키마_및_명세서.md`  
> **기준 문서**: [DART_ART_학습대조_데이터명세서_v1.0.md](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 1. 개요
Neo4j Graph Data Science(GDS) 엔진을 사용하여 디스크 병목 없이 RAM 상에서 대규모 지분 네트워크 및 전형 그래프의 구조적 영향력(PageRank, Degree Centrality)을 고속 산출하는 쿼리 명세를 정의합니다.

---

## 2. GDS 인메모리 서브그래프 투영 명세

### 1) [DART-Trace] 가중 지분 그래프 투영 (`dartStakeGraph`)
- **노드 프로젝션**: `Company`, `Shareholder`
- **관계 프로젝션**: `HOLDS_ECONOMIC_STAKE`
  - 방향: `NATURAL`
  - 속성: `stake_ratio` (가중치)
```cypher
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
```

### 2) [ART:READY] 실기 요강 이분 그래프 투영 (`artPracticalGraph`)
- **노드 프로젝션**: `AdmissionTrack`, `PracticalType`
- **관계 프로젝션**: `REQUIRES_PRACTICAL` (방향: `UNDIRECTED` 또는 `NATURAL`)
```cypher
CALL gds.graph.project(
  'artPracticalGraph',
  ['AdmissionTrack', 'PracticalType'],
  'REQUIRES_PRACTICAL'
);
```

---

## 3. 핵심 중심성 알고리즘 실행 템플릿

### Q1. 실질 지배사 발굴: 가중치 PageRank 스트리밍
```cypher
CALL gds.pageRank.stream('dartStakeGraph', {
  relationshipWeightProperty: 'stake_ratio',
  dampingFactor: 0.85,
  maxIterations: 20
})
YIELD nodeId, score
RETURN 
    gds.util.asNode(nodeId).name AS entity_name,
    labels(gds.util.asNode(nodeId))[0] AS label,
    round(score, 4) AS pagerank_score
ORDER BY score DESC
LIMIT 10;
```

### Q2. 실기종목 허브 분석: Degree Centrality (In-Degree)
```cypher
CALL gds.degree.stream('artPracticalGraph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS n, score
WHERE n:PracticalType
RETURN 
    n.name AS practical_subject,
    n.category AS category,
    toInteger(score) AS connected_tracks_count
ORDER BY connected_tracks_count DESC;
```

### Q3. 그래프 투영 정리 (Memory Drop)
```cypher
CALL gds.graph.drop('dartStakeGraph', false);
CALL gds.graph.drop('artPracticalGraph', false);
```

---

## 4. 운영 수칙 및 자원 회수 가이드
1. **메모리 누수 차단**: 투영된 그래프(`gds.graph.project`)는 JVM 힙 외 메모리에 상주하므로 분석 완료 즉시 반드시 `CALL gds.graph.drop()`을 호출하여 자원을 반환한다.
2. **멱등 투영**: 이미 동일한 이름의 그래프가 존재하는 경우를 대비하여 투영 전 `gds.graph.exists()` 체크 또는 `drop`을 선행한다.
