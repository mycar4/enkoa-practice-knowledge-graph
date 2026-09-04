# 📋 [Day 35] GraphRAG 알고리즘 및 인덱스 스키마 마스터 명세서

> **문서 목적**: Neo4j 2026.01+ HNSW 벡터 인덱스, Fulltext 전문 인덱스, GDS 인메모리 투영 및 하이브리드 리랭킹 수식의 완전한 기술 규격 정의

---

## 🏷️ 1. 노드(Node) 스키마 상세 명세

| 노드 라벨 | 주요 속성 (Properties) | 데이터 타입 | 설명 및 역할 |
|---|---|---|---|
| `:Document` | `pmcid`<br>`title`<br>`text`<br>`emb`<br>`graph_score` | STRING (Unique)<br>STRING<br>STRING<br>LIST&lt;FLOAT&gt; [768]<br>FLOAT | 의학 학술 논문 엔티티<br>PMC 식별자 (PK)<br>논문 제목<br>초록 및 본문 발췌 텍스트<br>OpenAI 768차원 임베딩 벡터<br>PageRank 기반 평균 그래프 점수 |
| `:Compound` | `id`<br>`name`<br>`pagerank`<br>`community` | STRING (PK)<br>STRING<br>FLOAT<br>INTEGER | 화합물 및 의약품 개체 (예: `DB00641`, `Simvastatin`)<br>GDS PageRank 점수<br>GDS Leiden 커뮤니티 ID |
| `:Disease` | `id`<br>`name`<br>`pagerank`<br>`community` | STRING (PK)<br>STRING<br>FLOAT<br>INTEGER | 질병 및 병증 개체 (예: `DOID:10652`, `Alzheimer's disease`) |
| `:PharmacologicClass`| `id`<br>`name`<br>`pagerank`<br>`community` | STRING (PK)<br>STRING<br>FLOAT<br>INTEGER | 약리학적 분류군 (예: HMG-CoA 환원효소 저해제) |
| `:Gene` | `id`<br>`name` | STRING (PK)<br>STRING | 인체 유전자 개체 (예: `CYP3A4`, `APOE`) |
| `:Symptom` | `id`<br>`name` | STRING (PK)<br>STRING | 임상 증상 개체 |

---

## 🔗 2. 관계(Relationship) 스키마 상세 명세

| 관계 유형 | 시작 노드 $\rightarrow$ 대상 노드 | 방향성 | 의미 및 비즈니스 규칙 |
|---|:---:|:---:|---|
| `:MENTIONS` | `:Document` $\rightarrow$ 개체 노드 | 단방향 ($\rightarrow$) | **문서-그래프 연결 다리**: 논문 본문에 등장한 약물, 질환 등을 사전(`name2id`) 매칭하여 연결 |
| `:TREATS` | `:Compound` $\rightarrow$ `:Disease` | 무방향 투영 대상 | 약물이 질환을 치료함 (공식 입증된 사실) |
| `:PALLIATES` | `:Compound` $\rightarrow$ `:Disease` | 무방향 투영 대상 | 약물이 질환의 증상을 완화함 |
| `:INCLUDES` | `:PharmacologicClass` $\rightarrow$ `:Compound` | 무방향 투영 대상 | 약물 분류군에 해당 화합물이 포함됨 |
| `:RESEMBLES_CC` | `:Compound` $\leftrightarrow$ `:Compound` | 양방향 | 두 화합물의 화학적 구조 유사성 |
| `:RESEMBLES_DD` | `:Disease` $\leftrightarrow$ `:Disease` | 양방향 | 두 질환의 임상적 유사성 |

---

## ⚡ 3. 인덱스(Index) 생성 DDL 명세

### 1) HNSW 벡터 인덱스 (`doc_vec`)
```cypher
CREATE VECTOR INDEX doc_vec IF NOT EXISTS
FOR (d:Document) ON (d.emb)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }
};
```
* **인덱스 유형**: HNSW (Hierarchical Navigable Small World)
* **차원 수**: 768 (`text-embedding-3-large` 축소 차원)
* **유사도 함수**: `cosine` (Neo4j SEARCH 절에서 `(1+cos)/2`로 0~1 정규화)

### 2) Fulltext 전문 인덱스 (`doc_fulltext`)
```cypher
CREATE FULLTEXT INDEX doc_fulltext IF NOT EXISTS
FOR (d:Document) ON EACH [d.title, d.text]
OPTIONS {
  indexConfig: {
    `fulltext.analyzer`: 'standard-no-stop-words'
  }
};
```
* **인덱스 유형**: Apache Lucene 기반 Fulltext Index
* **검색 문법**: `db.index.fulltext.queryNodes('doc_fulltext', 'CYP3A4 AND metabolism')`

---

## 🧠 4. GDS 인메모리 서브그래프 투영 명세

### 투영 파라미터 (`drugGraph`)
```cypher
CALL gds.graph.project(
  'drugGraph',
  ['Compound', 'Disease', 'PharmacologicClass'],
  {
    TREATS:       {orientation: 'UNDIRECTED'},
    PALLIATES:    {orientation: 'UNDIRECTED'},
    INCLUDES:     {orientation: 'UNDIRECTED'},
    RESEMBLES_DD: {orientation: 'UNDIRECTED'},
    RESEMBLES_CC: {orientation: 'UNDIRECTED'}
  }
);
```
* **Orientation = 'UNDIRECTED' 필수 사유**:
  - 치료/완화 관계는 단방향이지만, 지식의 유대와 클러스터링(Leiden), 영향력 전파(PageRank)에서는 상호 연결로 해석해야 하위 그래프 분절을 방지할 수 있습니다.

---

## 📐 5. 알고리즘 및 리랭킹 계산 수식

### 1) PageRank 중심성
```cypher
CALL gds.pageRank.write('drugGraph', {
  writeProperty: 'pagerank',
  dampingFactor: 0.85,
  maxIterations: 20
});
```
* **문서 그래프 스코어 전이**:
  $$\text{d.graph\_score} = \frac{1}{|\{e\}|} \sum_{e \in \text{Mentions}(d)} e.\text{pagerank}$$
  *(투영에 포함되지 않은 고립 문서의 경우 바닥값 `0.15` 부여)*

### 2) Min-Max 정규화 및 하이브리드 리랭킹 융합 수식
후보군 집합 $H = \{hit_1, hit_2, \dots, hit_k\}$에 대하여:

1. **벡터 유사도 정규화**:
   $$Sim_{norm}(i) = \frac{score_i - \min(score)}{\max(score) - \min(score)}$$
2. **그래프 중심성 정규화**:
   $$Graph_{norm}(i) = \frac{graph\_score_i - \min(graph\_score)}{\max(graph\_score) - \min(graph\_score)}$$
3. **가중 하이브리드 융합 스코어 (Fused Score)**:
   $$\text{FusedScore}_i = (1 - w) \cdot Sim_{norm}(i) + w \cdot Graph_{norm}(i)$$
   *(기본 권장 가중치: $w = 0.3 \sim 0.5$)*

### 3) Leiden 커뮤니티 탐지
```cypher
CALL gds.leiden.write('drugGraph', {
  writeProperty: 'community',
  randomSeed: 42,
  concurrency: 1
});
```
* **문맥 좁히기 질의**:
  기준 약물이 속한 $c = \text{Anchor.community}$에 대해:
  $$\{d \in \text{TopK}_{\text{Vector}} \mid \exists e \in \text{Mentions}(d) \text{ s.t. } e.\text{community} = c\}$$
