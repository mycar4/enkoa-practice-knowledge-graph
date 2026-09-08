# 🏛️ [Day 28] Neo4j 인스턴스 구축 및 실데이터 적재 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day28_Neo4j_설치_실데이터적재/00_Day28_Neo4j_설치_실데이터적재_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ [Phase 0: 기반 인프라 & 지식그래프 원리] (Day 27~35) ◀◀◀ [현재 위치: Day 28 Neo4j 인프라 구축]
   - Day 27 (그래프 모델링): 왜 RDB가 아니라 속성 그래프(LPG)인가? 점과 선의 본질 (완료 ✅)
   - Day 28 (Neo4j 인프라) : 클라우드 DB 인스턴스 구축 및 실데이터 적재 (현재)
   - Day 29~31 (Cypher 탐색): MATCH, UNWIND, 인덱스 튜닝, 지분율 집계
   - Day 32 (멱등 적재)    : 대량 데이터 무결점 MERGE 트랜잭션
   - Day 33~34 (GDS 알고리즘): PageRank 지배회사 탐지 & 순환출자/일정충돌 최단경로
   - Day 35 (GraphRAG)     : 텍스트 벡터 인덱스와 지식그래프 결합
  ① 자동 추출 및 온톨로지 파이프라인 (Day 36~42)
  ② 하이브리드 검색 + 리랭킹 (Day 43~48)
```
> **학습 목적**: "교재의 헐리우드 영화(Movies) 샌드박스를 걷어내고, 금융감독원 공시(79,848개 노드)와 미대입시 실데이터를 안전하게 보존·서빙하는 **Neo4j 인스턴스 연결 및 프로덕션 최초 적재 파이프라인**을 구축하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 영화(Movies) 튜토리얼을 버려야 하는가?)

### 10초 초등생 비유: "장난감 모래놀이 vs 실제 빌딩 기초공사"
1. **교재의 영화(Movies) 실습 (모래놀이)**:
   - 교재는 Neo4j 데스크톱을 깔고 `:play movies` 버튼을 누르면 1초 만에 로드되는 영화 튜토리얼로 수업을 진행합니다.
   - 하지만 현업에 가면 톰 행크스나 매트릭스 영화 데이터는 아무 쓸모가 없습니다.
2. **실제 프로덕션 인프라 (빌딩 기초공사)**:
   - 실제 비즈니스에서는 **보안 접속(`neo4j+s://`), 커넥션 풀(Connection Pool) 관리, 세션(Session) 분리, 환경변수(`.env`) 격리**가 필수입니다.
   - 우리는 영화 대신 **DART-Trace의 79,848개 노드 인스턴스(Aura Cloud)**와 **ART:READY 입시 그래프**를 직접 연결하고 최초 팩트를 적재합니다.

---

## 🛠️ 2. HOW: Neo4j 프로덕션 연결의 3대 핵심 아키텍처

파이썬 애플리케이션에서 Neo4j를 연결할 때 지켜야 할 엔지니어링 표준입니다:

```text
  [파이썬 앱 (.env)] ──(Connection Pool)──> [Neo4j Aura Cloud / Local DB]
        │                                             │
        ├─ 1. 드라이버(Driver) 인스턴스 싱글톤 유지      ├─ Bolt 프로토콜 (포트 7687)
        ├─ 2. 세션(Session) 단위 트랜잭션 열기/닫기     ├─ 보안 암호화 (neo4j+s://)
        └─ 3. 읽기/쓰기 쿼리 라우팅 (Read/Write)      └─ 멱등 제약조건 선행 검증
```

1. **드라이버(Driver) 싱글톤**:
   - `GraphDatabase.driver(uri, auth=(user, password))` 객체는 애플리케이션 전체에서 1개만 생성하여 재사용합니다. (매 쿼리마다 드라이버를 생성하면 TCP 소켓 고갈로 서버 다운).
2. **세션(Session) 콘텍스트 관리**:
   - `with driver.session() as session:` 블록을 사용하여 쿼리 실행 후 즉시 커넥션을 풀로 반환합니다.
3. **보안 프로토콜 (`neo4j+s://`)**:
   - 클라우드 DB(Aura) 연동 시 TLS/SSL 암호화가 적용된 `neo4j+s://` URI를 사용하여 중간자 도청을 방지합니다.

---

## 🏢 3. [DART-Trace] 실제 적용 사례 (Aura Cloud 79,848개 노드 연동)

* **서비스 인프라**:
  - `NEO4J_URI`: `neo4j+s://xxxx.databases.neo4j.io` (Aura Cloud)
  - `AURA_INSTANCE_NAME`: DART 지분 공시 전용 인스턴스
* **실제 최초 팩트 적재 Cypher**:
  ```cypher
  // 고유성 제약조건 선행 생성 (중복 적재 원천 차단)
  CREATE CONSTRAINT company_corp_code_unique IF NOT EXISTS
  FOR (c:Company) REQUIRE c.corp_code IS UNIQUE;

  // 삼성전자 및 국민연금공단 최초 팩트 결속
  MERGE (c:Company {corp_code: '00126380'})
    ON CREATE SET c.name = '삼성전자', c.is_listed = true
  MERGE (s:Shareholder {holder_key: '국민연금공단'})
    ON CREATE SET s.name = '국민연금공단', s.holder_type = '연기금'
  MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
    ON CREATE SET r.stake_ratio = 7.25, r.created_at = datetime();
  ```

---

## 🎨 4. [ART:READY] 실제 적용 사례 (`cau_spatial_design.json` 연동)

* **서비스 인프라**:
  - 미대입시 15개 대학 데이터를 담는 독립 네임스페이스
* **실제 최초 팩트 적재 Cypher**:
  ```cypher
  // 대학 복합 식별자 제약조건 생성
  CREATE CONSTRAINT univ_id_unique IF NOT EXISTS
  FOR (u:University) REQUIRE u.id IS UNIQUE;

  // 중앙대 서울 공간연출전공 및 실기 최초 결속
  MERGE (u:University {id: 'CAU_SEOUL'})
    ON CREATE SET u.name = '중앙대학교', u.campus = '서울'
  MERGE (t:AdmissionTrack {id: 'CAU_2027_EARLY_PRACTICAL'})
    ON CREATE SET t.name = '2027 수시 실기형', t.year = 2027
  MERGE (u)-[r1:OFFERS_TRACK]->(t)
  MERGE (p:PracticalType {id: 'PRACTICAL_DRAWING'})
    ON CREATE SET p.name = '소묘'
  MERGE (t)-[r2:REQUIRES_PRACTICAL]->(p)
    ON CREATE SET r2.stage = 1, r2.ratio = 80.0;
  ```

---

## 🔍 5. 현재 구현 및 원본 근거
* **DART-Trace**:
  - `00_Raw_Evidence_Graph_Loader.py`에 Neo4j 공식 Python 드라이버 연동 코드 내장.
  - 프로덕션 DB에 79,848개 노드 및 관계 안전 적재 보존.
* **ART:READY**:
  - `00_Art_Admission_Graph_Loader.py`에서 `University`, `AdmissionTrack` 최초 적재기 동작 검증 완료.

---

## ⚠️ 6. 부족한 부분 하나 (결손 과제)
* **결손 과제**: DB 비밀번호나 URI가 유실되거나 네트워크 단절 시, 앱 전체가 비정상 종료되지 않고 로컬 인메모리 모드로 자동 전환되는 **우아한 연결 예외 처리(Graceful Degradation)** 로직 보강 필요. ➔ 오늘 풀소스에서 완벽 구현.

---

## 🧪 7. DRY-RUN 및 완료 판정 (Done Definition)

1. **드라이버 연결성 검사**:
   - `driver.verify_connectivity()` 호출 시 정상 응답 반환 및 세션 오픈 성공 -> **PASS ✅**
2. **실데이터 멱등 MERGE 검사**:
   - 동일한 최초 적재 스크립트를 2회 연속 실행했을 때 노드 수가 단 1개도 증가하지 않는가? -> **PASS ✅**
3. **판정**: **기준 만족 시 Day 28 마스터 합격 🟢**
