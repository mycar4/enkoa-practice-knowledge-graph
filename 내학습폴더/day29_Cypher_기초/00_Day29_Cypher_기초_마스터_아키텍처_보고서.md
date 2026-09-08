# 🏛️ [Day 29] Cypher 기본 문법(MATCH·WHERE·RETURN·MERGE) 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day29_Cypher_기초/00_Day29_Cypher_기초_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 29 Cypher 기본 쿼리]
   - Day 27 (그래프 모델링): 왜 RDB가 아니라 속성 그래프(LPG)인가? (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 인스턴스 구축 및 실데이터 적재 (완료 ✅)
   - Day 29 (Cypher 기초)  : MATCH, WHERE, RETURN, MERGE 기본 쿼리 (현재)
   - Day 30 (Cypher 심화)  : UNWIND 배치 적재, WITH 파이프라인, 다중 홉 탐색
   - Day 31 (인덱스/집계)  : 지분율 합산(SUM), 모집정원 카운트, 고유 인덱스
   - Day 32~35             : 대량 멱등적재 ➔ GDS PageRank ➔ 순환출자 탐지 ➔ GraphRAG
```
> **학습 목적**: "교재의 헐리우드 배우 찾기 쿼리를 걷어내고, 지식그래프에서 **'삼성전자 5% 이상 대주주 랭킹'과 '서울 소재 미대 실기 80% 전형'을 단 한 줄의 ASCII-Art 경로 패턴으로 선언 탐색**하는 Cypher 언어를 마스터하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 SQL이 아니라 Cypher인가?)

### 10초 초등생 비유: "그림 그리듯 화살표로 데이터 찾기"
1. **SQL (RDB 질의)**:
   - 관계를 찾으려면 `JOIN companies ON ... JOIN holdings ON ... JOIN shareholders ON ...` 처럼 컴퓨터의 물리적 연결 고리를 수동으로 설명해야 합니다.
2. **Cypher (그래프 질의)**:
   - 사람이 종이에 화살표를 그리듯 문법 자체가 ASCII-Art 그림입니다:
   - `(:Shareholder)-[:HOLDS_ECONOMIC_STAKE]->(:Company)`
   - 둥근 괄호 `( )`는 동그란 노드를 뜻하고, 대괄호 화살표 `-[ ]->`는 화살표 관계를 뜻합니다. 말 그대로 보고 싶은 그림을 적으면 엔진이 그대로 찾아옵니다.

---

## 🛠️ 2. HOW: Cypher 4대 기본 절의 실행 메커니즘

```text
  [MATCH]   (s:Shareholder)-[r:HOLDS_ECONOMIC_STAKE]->(c:Company)  ── 1. 그래프 경로 패턴 바인딩
     │
  [WHERE]   c.name = '삼성전자' AND r.stake_ratio >= 5.0            ── 2. 노드 및 관계 속성 필터링
     │
 [ORDER BY] r.stake_ratio DESC                                    ── 3. 지분율 내림차순 정렬
     │
  [RETURN]  s.name, r.stake_ratio, r.base_date                    ── 4. 필요한 속성 프로젝션 투영
```

1. **`MATCH` (패턴 탐색)**:
   - 그래프 저장소에서 지정한 구조(형태)와 일치하는 부분 그래프(Subgraph)를 스캔합니다.
2. **`WHERE` (술어 조건 필터)**:
   - 노드 속성(`c.name = '삼성전자'`)뿐 아니라 관계 속성(`r.stake_ratio >= 5.0`)까지 동시에 단일 절에서 필터링합니다.
3. **`RETURN` (결과 반환)**:
   - 경로에 바인딩된 변수 중 사용자에게 반환할 노드, 관계, 혹은 계산식(`r.shares * 1000`)을 선택합니다.
4. **`MERGE` (멱등 보장 생성)**:
   - 패턴이 존재하면 매칭(`MATCH`), 없으면 생성(`CREATE`)하여 데이터 중복 복제를 원천 차단합니다.

---

## 🏢 3. [DART-Trace] 실전 쿼리 시나리오 (기업지분 추적)

### 1) 서비스 질문
> *"삼성전자 주식의 5% 이상을 대량 보유한 보고자들을 지분율이 높은 순서대로 상위 5명만 출력하라."*

### 2) Cypher 실전 쿼리
```cypher
MATCH (s:Shareholder)-[r:HOLDS_ECONOMIC_STAKE]->(c:Company)
WHERE c.name = '삼성전자' AND r.stake_ratio >= 5.0
RETURN 
    s.name AS shareholder_name, 
    s.holder_type AS investor_type,
    r.stake_ratio AS ratio_pct,
    r.base_date AS report_date
ORDER BY r.stake_ratio DESC
LIMIT 5;
```

---

## 🎨 4. [ART:READY] 실전 쿼리 시나리오 (미대입시 조건 검색)

### 1) 서비스 질문
> *"서울에 있는 대학 중 1단계에서 실기를 70% 이상 반영하는 전형과 실기 종목을 찾아라."*

### 2) Cypher 실전 쿼리
```cypher
MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
WHERE u.campus = '서울' AND r.stage = 1 AND r.ratio >= 70.0
RETURN 
    u.name AS university,
    u.campus AS campus,
    t.name AS track_name,
    p.name AS practical_subject,
    r.ratio AS practical_ratio
ORDER BY r.ratio DESC;
```

---

## 🔍 5. 현재 구현 및 원본 근거
* **DART-Trace**:
  - `00_Raw_Evidence_Graph_Loader.py`에서 `MERGE`와 `SET` 구문으로 실적재 구현 완료.
  - Aura Cloud 콘솔에서 실제 쿼리 실행 검증 완료.
* **ART:READY**:
  - `api_art_admission.py`에서 백엔드 검색 API 쿼리로 `MATCH (u)-[:OFFERS_TRACK]->(t)` 기본 질의 엔진 구동 중.

---

## ⚠️ 6. 부족한 부분 하나 (결손 과제)
* **결손 과제**: 복잡한 조건(예: "실기 고사 일정이 10월 첫째 주말이면서 실기비율 80% 이상")을 질의할 때 날짜 함수(`date()`)와 관계 속성 필터링을 결합하는 표준 실무 쿼리 가이드라인 부재. ➔ 오늘 `00_Day29_Cypher_기초_스키마_및_쿼리명세서.md`에서 규격화.

---

## 🧪 7. DRY-RUN 및 완료 판정 (Done Definition)

1. **기본 패턴 질의 검증**:
   - DART 지분율 5% 이상 필터링 및 ART 실기비율 80% 이상 필터링 쿼리가 정상 실행되어 레코드를 반환하는가? -> **PASS ✅**
2. **정렬 및 제한 검증**:
   - `ORDER BY ... DESC LIMIT N` 절이 정확히 상위 N건만을 순서대로 투영하는가? -> **PASS ✅**
3. **판정**: **기준 만족 시 Day 29 마스터 합격 🟢**
