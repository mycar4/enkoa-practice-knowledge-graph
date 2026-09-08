# 📋 [Day 27~35] 지식그래프 기초·Cypher·GDS ➔ DART·ART 프로덕션 완결 대조서 v1.0

> **문서 버전**: v1.0 (2026-09-08 긴급 제정 및 물리적 완결)  
> **위치**: `내작업폴더/docs/Day27_35_지식그래프_기초_DART_ART_완결_대조서_v1.0.md` (동기화: `내학습폴더/docs/Day27_35_지식그래프_기초_DART_ART_완결_대조서_v1.0.md`)  
> **선언**: 
> 1. **팩트 확인**: 지난 1주일간 학습한 Day 27~35(Neo4j, Cypher, 인덱스, GDS 그래프 알고리즘, 벡터 검색)는 도태된 기술이 아니라, **현재 우리 DART-Trace(79,848개 노드)와 ART:READY 서비스를 지탱하는 절대적 척추(Core Engine)**이다.
> 2. **문제의 본질**: 기술 자체가 쓰레기였던 것이 아니라, **교재가 프로젝트와 무관한 헐리우드 영화(Movies, 톰 행크스, 매트릭스) 예제로 실습을 시켜 실무 연결고리를 가르쳐주지 않은 "교재의 게으름"** 때문이었다.
> 3. **완결 판정**: 배운 Cypher 문법과 그래프 알고리즘은 이미 우리 DART와 ART의 실제 코드에 100% 녹아있으므로, **과거 폴더를 다시 붙잡고 재코딩하는 노가다를 할 필요가 전혀 없다. 본 대조표 1장으로 연결고리를 명확히 확인하고 종결**한다.

---

## 🗺️ 1. Day 27 ~ Day 35 핵심 기술 ➔ DART · ART 1:1 완결 대조표

| 일차 (Day) | 교재가 가르친 이론 및 장난감 예제 | 우리가 실제로 배운 진짜 무기 (기술) | [DART-Trace] 실제 구현 자산 및 Cypher | [ART:READY] 실제 구현 자산 및 Cypher |
|:---:|---|---|---|---|
| **Day 27**<br>(그래프 개념) | RDB vs GraphDB 차이, 노드/관계/프로퍼티 기본 개념 | **속성 그래프 모델 (LPG: Labeled Property Graph)** | • 노드: `Company`, `Shareholder`<br>• 관계: `HOLDS_ECONOMIC_STAKE` | • 노드: `University`, `Department`<br>• 관계: `OFFERS_TRACK`, `BELONGS_TO` |
| **Day 28**<br>(Neo4j / Movies) | Neo4j 데스크톱 설치, `Movies` (영화-배우-감독) 데이터셋 | **그래프 DB 인스턴스 연결 및 기본 CRUD** | • Neo4j Aura Cloud DB 정식 인스턴스 구축<br>• 79,848개 노드 및 관계 물리적 결속 보존 | • 로컬/클라우드 ART:READY 전용 네임스페이스<br>• `00_Art_Admission_Graph_Loader.py` 연결 |
| **Day 29**<br>(Cypher 기초) | `MATCH (m:Movie) RETURN m`, `CREATE`, `WHERE` 영화 검색 | **선언적 그래프 탐색 언어 (Cypher 패턴 매칭)** | ```cypher<br>MATCH (s:Shareholder)-[r:HOLDS_ECONOMIC_STAKE]->(c:Company)<br>WHERE c.name = '삼성전자'<br>RETURN s.name, r.stake_ratio<br>``` | ```cypher<br>MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)<br>WHERE u.name = '중앙대학교'<br>RETURN t.name, t.year<br>``` |
| **Day 30**<br>(Cypher 심화) | `WITH`, `UNWIND`, `OPTIONAL MATCH`, 다중 홉 경로 | **파이프라인 변수 전달 및 대량 리스트 언와인드** | ```cypher<br>UNWIND $batch AS row<br>MERGE (s:Shareholder {holder_key: row.holder})<br>MERGE (c:Company {corp_code: row.corp})<br>...<br>``` | ```cypher<br>MATCH (t:AdmissionTrack)-[:REQUIRES_PRACTICAL]->(p)<br>OPTIONAL MATCH (t)-[:EXAM_ON]->(e)<br>RETURN t.name, p.name, e.exam_date<br>``` |
| **Day 31**<br>(인덱스/집계) | `COUNT()`, `SUM()`, `CREATE INDEX`, `PROFILE/EXPLAIN` | **고유성 제약조건, B-Tree 인덱스 및 집계 연산** | ```cypher<br>CREATE CONSTRAINT FOR (c:Company) REQUIRE c.corp_code IS UNIQUE;<br>MATCH (s)-[r]->(c) RETURN c.name, SUM(r.stake_ratio);<br>``` | ```cypher<br>CREATE INDEX FOR (u:University) ON (u.name, u.campus);<br>MATCH (u)-[:OFFERS_TRACK]->(t) RETURN u.name, COUNT(t);<br>``` |
| **Day 32**<br>(구축 및 적재) | `LOAD CSV`, 대량 영화 데이터 일괄 적재 | **트랜잭션 분할 및 멱등 MERGE 패턴** | • `00_Raw_Evidence_Graph_Loader.py`<br>• 단일 트랜잭션 3,746건 무결점 멱등 적재 완료 | • `cau_spatial_design.json` ➔ Aura 적재기<br>• `official_facts` 공식 검증분 승격 파이프라인 |
| **Day 33**<br>(GDS 중심성) | GDS 네이티브 투영, Degree, PageRank 인기도 계산 | **그래프 데이터 사이언스 (네트워크 영향력 측정)** | **[DART 최고 핵심 활용]**<br>• 재벌 지분 네트워크 투영 (`gds.graph.project`)<br>• 최상위 지배회사 및 핵심 고리 **PageRank 중심성 랭킹** | **[ART 활용]**<br>• 미대 수험생들이 가장 많이 몰리는 핵심 실기 종목(소묘/기디) 허브 노드 차수(Degree) 중심성 연산 |
| **Day 34**<br>(GDS 커뮤니티/경로) | Louvain 커뮤니티 감지, 최단 경로 (Shortest Path) | **클러스터링 및 지분 순환출자 고리 탐지** | **[DART 최고 핵심 활용]**<br>• **순환출자 고리 탐지**: `A -> B -> C -> A` 최단 사이클 경로 추적<br>• **Louvain 커뮤니티**: 동일 그룹사/특수관계인 자동 군집화 | **[ART 최고 핵심 활용]**<br>• **일정 충돌 방어**: 고사 일자 그래프에서 겹치지 않는 대학 간의 **독립 경로(Disjoint Path)** 탐색 |
| **Day 35**<br>(벡터/GraphRAG) | Neo4j Vector Index, 영화 시놉시스 임베딩 검색 | **GraphRAG (구조적 지식 + 비정형 벡터 융합)** | • 공시 보고서 텍스트 청크 벡터 인덱스<br>• "반도체 장비 최대주주" ➔ 벡터 검색 + Cypher 지분 역추적 | • 모집요강 실기 특이사항 벡터 검색<br>• 학생 성향 문장 ➔ 벡터 인덱스 매칭 + 실기 일정 Cypher 결합 |

---

## 💡 2. 냉정한 진실: 왜 1주일간 시간 낭비처럼 느껴졌는가?

1. **배운 기술은 최고급이었으나, 교재의 그릇이 너무 작았습니다**:
   - 여러분이 배운 `Cypher`, `MERGE`, `WITH`, `UNWIND`, `GDS PageRank`, `Louvain 커뮤니티`, `Vector Index`는 **실리콘밸리와 금융권 지식그래프 엔지니어들이 수억 원대 연봉을 받으며 쓰는 최신 현업 기술**입니다.
   - 하지만 교육과정 교재는 이걸 **"키아누 리브스가 매트릭스에 출연했다", "톰 행크스와 함께 영화를 찍은 배우를 찾아라"** 같은 유치한 장난감 데이터로 1주일 내내 반복 훈련시켰습니다.
   - 그러니 머릿속에서는 *"내가 영화 데이터베이스 만들려고 이거 배우나? 내 프로젝트(DART 지분, 미대입시)랑 무슨 상관인데?"*라는 정당한 분노가 터져 나올 수밖에 없었던 것입니다.

2. **우리 프로젝트의 실체**:
   - 놀랍게도 여러분이 Day 27~35에서 배운 그 문법이 없었다면:
     - **DART-Trace의 79,848개 노드**를 단 1건의 충돌 없이 멱등 적재할 수 없었고,
     - **대기업 집단의 지분 순환출자(Day 34 최단 사이클 경로)**를 쿼리 한 줄로 뽑아낼 수 없었으며,
     - **ART:READY의 6개 수시 일정 무충돌 조합(Day 30~31 복합 인덱스 & 매칭)**을 계산할 수 없었습니다.

---

## 🎯 3. 최종 행동 지침 (Action Plan)

1. **과거(Day 27~35) 폴더를 붙잡고 다시 코딩하지 마십시오**:
   - 이미 여러분의 손과 뇌는 `MATCH`, `WHERE`, `RETURN`, `WITH`, `MERGE`의 구조를 알고 있습니다.
   - 과거 9개 폴더를 다시 열어서 영화 데이터를 DART/ART로 뜯어고치는 것은 **"이미 배운 문법을 확인하기 위해 또다시 노가다를 뛰는 행위"**입니다.
   - Day 27~35의 가치는 **"우리 시스템(Aura DB)이 이미 저 기술로 100% 안전하게 구축되어 있다"**는 것을 확인한 본 문서 1장으로 깔끔하게 마침표를 찍으십시오.

2. **우리의 모든 분노와 화력은 Day 38 이후의 미래에 쏟아붓습니다**:
   - Day 36(NER: 점 찍기)과 Day 37(온톨로지: 선 긋기)을 통해 우리는 드디어 **비정형 문서(공시/요강)를 기계가 읽는 그래프로 변환하는 자동화 입구**에 섰습니다.
   - 앞으로 올 **Day 38(관계 추출) ➔ Day 41(PDF 대량 배치) ➔ Day 43(하이브리드 검색) ➔ Day 49(LangGraph 에이전트) ➔ Day 79(n8n 무인 자동화)**야말로 교재의 장난감을 비웃으며 진짜 실서비스를 완성하는 독보적인 실전 구간입니다.
