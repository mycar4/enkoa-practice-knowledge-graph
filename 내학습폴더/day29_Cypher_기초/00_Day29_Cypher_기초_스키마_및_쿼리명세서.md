# 📋 [Day 29] Cypher 기본 쿼리 및 스키마 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 신규 구축)  
> **위치**: `내학습폴더/day29_Cypher_기초/00_Day29_Cypher_기초_스키마_및_쿼리명세서.md`  
> **기준 문서**: [DART·ART 실전 지식그래프 전체 데이터 명세서 v2.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🏢 1. [DART-Trace] 5대 실무 Cypher 쿼리 템플릿

### 템플릿 1: 상장사 기본 단일 노드 조회
```cypher
MATCH (c:Company {corp_code: $corp_code})
RETURN c.corp_code, c.name, c.is_listed;
```

### 템플릿 2: 특정 기업의 5% 대량보유 주주 및 지분율 랭킹
```cypher
MATCH (s:Shareholder)-[r:HOLDS_ECONOMIC_STAKE]->(c:Company {corp_code: $corp_code})
WHERE r.stake_ratio >= 5.0
RETURN s.name, s.holder_type, r.stake_ratio, r.shares, r.base_date
ORDER BY r.stake_ratio DESC
LIMIT 10;
```

### 템플릿 3: 기관투자자(연기금/사모펀드)가 보유한 포트폴리오 기업 목록
```cypher
MATCH (s:Shareholder {holder_type: '연기금'})-[r:HOLDS_ECONOMIC_STAKE]->(c:Company)
WHERE r.stake_ratio >= 5.0
RETURN s.name AS investor, c.name AS portfolio_company, r.stake_ratio AS ratio
ORDER BY s.name ASC, r.stake_ratio DESC;
```

### 템플릿 4: 멱등 지분 생성 및 속성 갱신 (MERGE + ON MATCH SET)
```cypher
MERGE (s:Shareholder {holder_key: $holder_key})
MERGE (c:Company {corp_code: $corp_code})
MERGE (s)-[r:HOLDS_ECONOMIC_STAKE]->(c)
ON CREATE SET 
    r.stake_ratio = $stake_ratio, 
    r.base_date = $base_date,
    r.created_at = datetime()
ON MATCH SET 
    r.stake_ratio = $stake_ratio,
    r.updated_at = datetime();
```

---

## 🎨 2. [ART:READY] 5대 실무 Cypher 쿼리 템플릿

### 템플릿 1: 특정 대학 및 캠퍼스의 개설 전형 전체 조회
```cypher
MATCH (u:University {name: $univ_name, campus: $campus})-[:OFFERS_TRACK]->(t:AdmissionTrack)
WHERE t.year = $admission_year
RETURN u.name, u.campus, t.name, t.admission_type, t.year;
```

### 템플릿 2: 실기 비중 70% 이상 전형 및 과목 역추적 필터링
```cypher
MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)-[r:REQUIRES_PRACTICAL]->(p:PracticalType)
WHERE r.stage = 1 AND r.ratio >= 70.0
RETURN u.name, u.campus, t.name, p.name AS practical_subject, r.ratio
ORDER BY r.ratio DESC, u.name ASC;
```

### 템플릿 3: 특정 고사 일자(10월 3일)에 치러지는 전형 탐색 (일정 충돌 사전 조회)
```cypher
MATCH (u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)-[:EXAM_ON]->(e:ExamSchedule)
WHERE e.exam_date = date('2026-10-03')
RETURN u.name, u.campus, t.name, e.exam_date, e.is_tentative;
```

### 템플릿 4: 학과 소속 대학 및 개설 전형 2-Hop 결합 탐색
```cypher
MATCH (d:Department {name: '공간연출전공'})-[:BELONGS_TO]->(u:University)-[:OFFERS_TRACK]->(t:AdmissionTrack)
RETURN d.name, u.name, u.campus, t.name, t.year;
```

---

## ⚠️ 3. Cypher 초급 3대 안티패턴 및 방어 수칙

1. **라벨 없는 무차별 `MATCH (n)` 절대 금지**:
   - `MATCH (n) RETURN n`은 전체 DB를 풀스캔하므로 프로덕션에서 즉시 타임아웃을 유발합니다. 반드시 `(:Company)`처럼 라벨을 명시하십시오.
2. **카테시안 곱(Cartesian Product) 주의**:
   - 관계 없이 `MATCH (s:Shareholder), (c:Company)`처럼 쉼표로 나열하면 두 테이블의 모든 조합(N × M)이 곱해져 메모리 오버플로우가 발생합니다. 반드시 화살표 관계 패턴을 명시하십시오.
3. **`CREATE` 대신 `MERGE` 기본 원칙**:
   - 배치가 재실행될 수 있는 환경에서는 `CREATE`를 쓰면 데이터가 중복 복제됩니다. 항상 `MERGE`를 기본으로 사용하십시오.
