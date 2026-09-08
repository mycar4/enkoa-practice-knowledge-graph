# 📋 [Day 28] Neo4j 연결 인프라 및 최초 팩트 적재 스키마 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day28_Neo4j_설치_실데이터적재/00_Day28_Neo4j_연결_및_적재_스키마_명세서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## ⚙️ 1. Neo4j 파이썬 드라이버 연결 풀(Connection Pool) 규격

```python
from neo4j import GraphDatabase, Driver

# 프로덕션 연결 풀 설정 표준
DRIVER_CONFIG = {
    "max_connection_lifetime": 3600,   # 1시간 후 커넥션 재생성
    "max_connection_pool_size": 50,    # 최대 동시 활성 커넥션 수
    "connection_acquisition_timeout": 60, # 커넥션 대기 타임아웃 (초)
    "keep_alive": True                 # 방화벽 세션 끊김 방지
}

def create_production_driver(uri: str, auth: tuple) -> Driver:
    """단일 싱글톤 드라이버 생성"""
    return GraphDatabase.driver(uri, auth=auth, **DRIVER_CONFIG)
```

---

## 🔒 2. DART & ART 고유성 제약조건 (Constraints) 명세서

적재 전 반드시 실행되어야 하는 DB 레벨의 무결성 제약조건입니다:

```cypher
// [DART-Trace] 법인코드 고유성 제약조건
CREATE CONSTRAINT company_corp_code_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.corp_code IS UNIQUE;

// [DART-Trace] 주주 식별키 고유성 제약조건
CREATE CONSTRAINT shareholder_key_unique IF NOT EXISTS
FOR (s:Shareholder) REQUIRE s.holder_key IS UNIQUE;

// [ART:READY] 대학교 식별자({univ}_{campus}) 고유성 제약조건
CREATE CONSTRAINT university_id_unique IF NOT EXISTS
FOR (u:University) REQUIRE u.id IS UNIQUE;

// [ART:READY] 입학전형 식별자({univ}_{track}_{year}) 고유성 제약조건
CREATE CONSTRAINT track_id_unique IF NOT EXISTS
FOR (t:AdmissionTrack) REQUIRE t.id IS UNIQUE;

// [ART:READY] 실기종목 식별자 고유성 제약조건
CREATE CONSTRAINT practical_id_unique IF NOT EXISTS
FOR (p:PracticalType) REQUIRE p.id IS UNIQUE;
```

---

## 🌐 3. 최초 팩트 적재 Cypher 트랜잭션 템플릿

```cypher
// 1) DART 지분 팩트 최초 적재 (Idempotent MERGE)
MERGE (c:Company {corp_code: $corp_code})
  ON CREATE SET c.name = $corp_name, c.is_listed = $is_listed, c.created_at = datetime()
MERGE (s:Shareholder {holder_key: $holder_key})
  ON CREATE SET s.name = $holder_name, s.holder_type = $holder_type, s.created_at = datetime()
MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
  ON CREATE SET 
    r.stake_ratio = $stake_ratio,
    r.shares = $shares,
    r.base_date = $base_date,
    r.evidence_level = 'curated',
    r.created_at = datetime();

// 2) ART 입시 팩트 최초 적재 (Idempotent MERGE)
MERGE (u:University {id: $univ_id})
  ON CREATE SET u.name = $univ_name, u.campus = $campus, u.created_at = datetime()
MERGE (t:AdmissionTrack {id: $track_id})
  ON CREATE SET t.name = $track_name, t.year = $year, t.created_at = datetime()
MERGE (u)-[r1:OFFERS_TRACK]->(t)
  ON CREATE SET r1.evidence_level = 'curated'
MERGE (p:PracticalType {id: $practical_id})
  ON CREATE SET p.name = $practical_name, p.category = $category, p.created_at = datetime()
MERGE (t)-[r2:REQUIRES_PRACTICAL]->(p)
  ON CREATE SET 
    r2.stage = $stage,
    r2.ratio = $ratio,
    r2.evidence_level = 'curated',
    r2.created_at = datetime();
```

---

## 🛡️ 4. 읽기(Read) / 쓰기(Write) 세션 분리 원칙

1. **쓰기 트랜잭션 (`session.execute_write`)**:
   - `MERGE`, `CREATE`, `SET`, `DELETE` 등 DB 변경이 일어나는 모든 쿼리는 반드시 `execute_write` 단위로 격리하여 롤백(Rollback) 안정성을 확보한다.
2. **읽기 트랜잭션 (`session.execute_read`)**:
   - `MATCH ... RETURN` 등 단순 조회 쿼리는 `execute_read`로 실행하여 클러스터 환경에서 읽기 전용 복제본(Read Replica)으로 부하를 분산한다.
