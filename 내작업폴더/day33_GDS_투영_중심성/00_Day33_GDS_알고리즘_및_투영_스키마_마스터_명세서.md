# 📋 [Day 33] GDS 알고리즘 및 투영 스키마 마스터 명세서
> **문서 버전**: v1.0 (2026-09-02)  
> **목적**: Hetionet 의료 지식그래프 및 서울 지하철 그래프 기반 GDS 투영 정의, 알고리즘 파라미터 DDL 및 실행 모드 표준 명세

---

## 1. 🧬 Hetionet v1.0 의료 지식그래프 데이터 구조 명세

### ① 노드 레이블 (Node Labels)

| 레이블 | 개수 | 설명 | 주요 속성 |
|---|:---:|---|---|
| `:Gene` | 13,113개 | 인체 유전자 엔티티 | `id` (NCBI Gene ID, 예: `'Gene::1017'`), `name` (유전자 기호, 예: `'CDK2'`) |
| `:Compound` | 1,531개 | 화학 약물/화합물 | `id` (DrugBank ID, 예: `'Compound::DB00530'`), `name` (약물명, 예: `'Erlotinib'`) |
| `:Symptom` | 415개 | 질병 증상/징후 | `id` (MeSH ID), `name` (증상명) |
| `:PharmacologicClass` | 345개 | 약효/약리 분류군 | `id` (FDA Class ID), `name` (분류명) |
| `:Disease` | 136개 | 질병 엔티티 | `id` (DOID, 예: `'Disease::DOID:1612'`), `name` (질병명, 예: `'breast cancer'`) |
| **총계** | **15,540개** | **인체 생물학·약학 복합 노드망** | **고유 식별자: `id` (Unique Index 적용)** |

---

### ② 관계 타입 (Relationship Types: 12종 91,966건)

| 관계 타입 | 출발 ➔ 도착 | 건수 | 설명 |
|---|---|:---:|---|
| `BINDS_CbG` | `Compound` ➔ `Gene` | 11,571건 | 약물이 특정 유전자(단백질)에 결합 |
| `UPREGULATES_CuG` | `Compound` ➔ `Gene` | 18,756건 | 약물이 유전자 발현을 상향 조절 |
| `DOWNREGULATES_CdG` | `Compound` ➔ `Gene` | 21,102건 | 약물이 유전자 발현을 하향 조절 |
| `INCLUDES_PCiC` | `PharmacologicClass` ➔ `Compound` | 1,029건 | 약효 분류에 특정 약물이 포함됨 |
| `ASSOCIATES_DaG` | `Disease` ➔ `Gene` | 12,623건 | 질병과 유전자 간의 발병 연관 |
| `UPREGULATES_DuG` | `Disease` ➔ `Gene` | 4,022건 | 질병 상태에서 유전자 발현 증가 |
| `DOWNREGULATES_DdG` | `Disease` ➔ `Gene` | 7,623건 | 질병 상태에서 유전자 발현 감소 |
| `TREATS_CtD` | `Compound` ➔ `Disease` | 755건 | 약물이 해당 질병을 치료 |
| `PALLIATES_CpD` | `Compound` ➔ `Disease` | 390건 | 약물이 해당 질병의 증상을 완화 |
| `PRESENTS_DpS` | `Disease` ➔ `Symptom` | 3,357건 | 질병이 특정 증상을 나타냄 |
| `INTERACTS_GiG` | `Gene` ➔ `Gene` | 147,164건 | 유전자(단백질) 간 상호작용 |
| `REGULATES_GrG` | `Gene` ➔ `Gene` | 265,672건 | 유전자 간 조절 관계 |

---

## 2. ⚡ GDS 인메모리 그래프 투영 DDL 명세

### ① 단일 이종 그래프 투영 (Compound-Gene Binding Graph)
* **목적**: 약물과 결합 표적 유전자 간의 무방향성 상호작용 분석
```cypher
CALL gds.graph.project(
    'drugGeneGraph',
    ['Compound', 'Gene'],
    {
        CbG: {
            type: 'BINDS_CbG',
            orientation: 'UNDIRECTED'
        }
    }
)
YIELD graphName, nodeCount, relationshipCount, projectMillis;
```

---

### ② 복합 질병-유전자-약물 삼각 투영 (Disease-Gene-Drug Triplet Graph)
* **목적**: 질병-유전자 연관 및 약물 결합을 동시에 고려한 신약 표적 발굴
```cypher
CALL gds.graph.project(
    'tripletGraph',
    ['Disease', 'Gene', 'Compound'],
    {
        DaG: {type: 'ASSOCIATES_DaG', orientation: 'UNDIRECTED'},
        CbG: {type: 'BINDS_CbG', orientation: 'UNDIRECTED'}
    }
)
YIELD graphName, nodeCount, relationshipCount;
```

---

## 3. 🎯 핵심 알고리즘 파라미터 및 실행 Cypher 명세

### ① PageRank 실행 명세
```cypher
// 1. stream 모드: Top 10 영향력 노드 추출
CALL gds.pageRank.stream('drugGeneGraph', {
    maxIterations: 20,
    dampingFactor: 0.85,
    tolerance: 0.00001
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name,
       labels(gds.util.asNode(nodeId))[0] AS type,
       score
ORDER BY score DESC
LIMIT 10;

// 2. write 모드: PageRank 점수를 디스크에 영구 속성으로 커밋
CALL gds.pageRank.write('drugGeneGraph', {
    maxIterations: 20,
    dampingFactor: 0.85,
    writeProperty: 'pagerank_score'
})
YIELD nodePropertiesWritten, computeMillis, writeMillis;
```

---

### ② 개인화 PageRank (Personalized PageRank) 실행 명세
```cypher
// 특정 질병(예: 'breast cancer') 관점에서의 개인화 PageRank
MATCH (d:Disease {name: 'breast cancer'})
WITH collect(id(d)) AS sourceNodes
CALL gds.pageRank.stream('tripletGraph', {
    maxIterations: 20,
    dampingFactor: 0.85,
    sourceNodes: sourceNodes
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS n, score
WHERE n:Compound OR n:Gene
RETURN n.name AS entity_name,
       labels(n)[0] AS entity_type,
       score AS ppr_score
ORDER BY ppr_score DESC
LIMIT 10;
```

---

### ③ 매개 중심성 (Betweenness Centrality) 실행 명세
```cypher
CALL gds.betweenness.stream('drugGeneGraph', {
    samplingSize: 1000 // 노드가 많을 경우 근사치(Sampling) 기법 적용
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name,
       labels(gds.util.asNode(nodeId))[0] AS type,
       score AS betweenness_score
ORDER BY betweenness_score DESC
LIMIT 10;
```
