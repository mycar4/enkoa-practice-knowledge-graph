# 📑 [Day 35] 벡터 인덱스 및 GraphRAG 융합 스키마·쿼리 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 실데이터 기준 전면 신규)  
> **위치**: `내학습폴더/day35_벡터검색_GraphRAG/00_Day35_벡터검색_GraphRAG_스키마_및_명세서.md`  
> **기준 문서**: [DART_ART_학습대조_데이터명세서_v1.0.md](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 1. 개요
비정형 텍스트(공시 XML 본문, 입시 요강 본문) 임베딩 벡터 인덱스와 정형 지식그래프(속성 그래프)의 다중 홉 탐색을 하나로 융합한 GraphRAG(Graph-Augmented Retrieval-Augmented Generation) 스키마 및 질의 명세를 정의합니다.

---

## 2. 벡터 인덱스 DDL 명세

### 1) [DART-Trace] 공시 텍스트 청크 벡터 인덱스
```cypher
CREATE VECTOR INDEX dartTextChunkIndex IF NOT EXISTS
FOR (ch:TextChunk) ON (ch.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

### 2) [ART:READY] 미대입시 요강 청크 벡터 인덱스
```cypher
CREATE VECTOR INDEX artHandbookIndex IF NOT EXISTS
FOR (ch:AdmissionChunk) ON (ch.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

---

## 3. 핵심 GraphRAG 하이브리드 질의 템플릿

### Q1. [DART-Trace] 의미 검색 ➔ 주주 지분 및 공시 원문 증거 결합
```cypher
CALL db.index.vector.queryNodes('dartTextChunkIndex', $top_k, $query_embedding)
YIELD node AS chunk, score
MATCH (chunk)<-[:HAS_CHUNK]-(c:Company)<-[r:HOLDS_ECONOMIC_STAKE]-(s:Shareholder)
MATCH (c)-[:BACKED_BY_EVIDENCE]->(e:EvidenceFragment)
RETURN 
    c.name AS company,
    s.name AS shareholder,
    r.stake_ratio AS stake_ratio,
    r.base_date AS base_date,
    e.rcept_no AS rcept_no,
    e.table_xpath AS table_xpath,
    chunk.text AS context_text,
    score AS similarity_score
ORDER BY r.stake_ratio DESC;
```

### Q2. [ART:READY] 질문 임베딩 ➔ 실기 전형 요강 및 고사일정 결합
```cypher
CALL db.index.vector.queryNodes('artHandbookIndex', $top_k, $query_embedding)
YIELD node AS chunk, score
MATCH (chunk)<-[:MENTIONED_IN]-(t:AdmissionTrack)<-[:OFFERS_TRACK]-(u:University)
MATCH (t)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
OPTIONAL MATCH (t)-[:EXAM_ON]->(e:ExamSchedule)
RETURN 
    u.name AS university,
    u.campus AS campus,
    t.name AS track_name,
    p.name AS practical_subject,
    r.ratio AS practical_ratio,
    coalesce(e.exam_date, '미발표') AS exam_date,
    chunk.text AS snippet;
```

---

## 4. LLM 프롬프트 주입 및 환각 제어 수칙
1. **Grounding 필수**: LLM 시스템 프롬프트에 `오직 제공된 그래프 지분율(stake_ratio)과 공시 증거(table_xpath)만을 기반으로 답변할 것`을 강제한다.
2. **출처 명시 의무**: 답변 본문에 접수번호(`rcept_no`)와 표 위치(`table_xpath`)를 각주/참조로 무조건 첨부한다.
