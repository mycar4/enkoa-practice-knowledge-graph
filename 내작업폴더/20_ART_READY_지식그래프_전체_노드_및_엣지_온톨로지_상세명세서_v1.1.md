# 🎨 [ART:READY] 지식그래프 전체 노드 및 엣지 온톨로지 상세명세서 (v1.1)

> **문서 식별자**: `ART_READY_ONTOLOGY_SPEC_v1.1`
> **작성일**: 2026-09-18
> **작성 주체**: Claude (Neo4j 스키마 직접 조회로 전수 재검증)
> **관계**: v1.0(거버넌스/QC팀 작성, 2026-09-18 오전)은 그날 오전 시점 실측치였고,
> 같은 날 오후 진행된 작업(OCR 복구, 엔티티 재추출, `COMPATIBLE_WITH`/`SIMILAR_TO`
> 관계 신설)으로 수치와 스키마 구성이 달라졌다. 이 문서는 `CALL db.labels()`/
> `CALL db.relationshipTypes()`로 실제 DB 스키마를 직접 조회해 라벨 오기까지
> 전수 정정했다.
>
> **버전 관리**:
> - v1.0 (2026-09-18 오전): 최초 발간
> - **v1.1 (2026-09-18 오후)**: 실측 재검증 - 수치 갱신, 누락 노드/관계 3종 추가, 라벨 오기 정정

---

## 0. v1.0 대비 달라진 점 요약

| 항목 | v1.0 | v1.1(실측) |
|---|---|---|
| 대학 수 | 52개 | **60개** |
| 학과 수 | 212개 | **213개** |
| TextChunk 수 | 4,016개 | **4,061개** |
| Entity 수 | 5,185개 | **5,412개**(LLM 신규발견 4,846개) |
| MENTIONS | 22,398건 | **23,054건** |
| 관계 타입 개수 | 6종 | **12종** (누락 3종 추가 + 오늘 신설 2종 + 기존 1종 재확인) |
| 노드 라벨명 오류 | `Admission_Stage`(존재하지 않는 라벨) | **`Admission_SelectionStage`**(실제 라벨명) |
| 누락됐던 노드 | `Admission_PastTopic`, `Admission_YearlyResult` 언급 없음 | 실제 스키마에 존재 확인, 표에 추가 |

---

## 1. 온톨로지 전체 아키텍처 (2-Tier + 배치 파생 관계)

v1.0의 "1층 공식 팩트 / 2층 비정형 의미망" 2-Tier 구분은 유효하다. 다만 2026-09-18
오후에 **세 번째 성격의 관계(배치로 미리 계산해 저장한 파생 관계)**가 추가됐다 -
이건 1층도 2층도 아니고, "1층의 검증된 구조화 데이터를 재료로 결정론적으로
계산한 관계"다(LLM 미사용).

```text
========================================================================================
[2층: 비정형 의미 그물망 (Semantic Mesh Layer)]
  (:Admission_TextChunk) ──[:MENTIONS (23,054건)]──▶ (:Admission_Entity)
      (4,061개 노드)                                      (5,412개 노드)
                                                               │  ▲
                                                [:CO_OCCURS_WITH (94,563건, 무방향)]
                                                               ▼  │
                                                      (:Admission_Entity)
                                          * 1,136개는 검증된 Track 없어 PageRank/
                                            커뮤니티 계산에서 제외(오염 방지 필터)
======================================= ▲ ==============================================
                          (이름 일치 기반 - 실제 그래프 관계는 없음)
======================================= ▼ ==============================================
[1층: 공식 팩트 장부 (Ground-Truth Fact Layer)]
  (:Admission_University, 60개)
      │
      └─[:HAS_DEPARTMENT (213건)]─▶ (:Admission_Department, 213개)
                                  │
                                  └─[:HAS_TRACK (299건)]─▶ (:Admission_Track, 299개)
                                                        │
                    ┌───────────────┬───────────────────┼───────────────┬──────────────┐
                    ▼               ▼                   ▼               ▼              ▼
           [:REQUIRES_EXAM]  [:HAS_SCHEDULE]      [:HAS_STAGE]  [:ESTIMATED_CUTOFF] [:HAD_PAST_TOPIC]
                    │               │                   │               │              │
                    ▼               ▼                   ▼               ▼              ▼
         (:Admission_ExamType) (:Admission_Schedule) (:Admission_      (:Admission_   (:Admission_
              299개                299개            SelectionStage    CutoffEstimate  PastTopic
                                                        98개)            77개)          12개)

           (:Admission_Track) ─[:HAS_YEARLY_RESULT (75건)]─▶ (:Admission_YearlyResult, 75개)
========================================================================================
[배치 파생 관계 (2026-09-18 오후 신설, 03_Art_Admission_Relationship_Builder.py)]
  (:Admission_Track) ──[:COMPATIBLE_WITH (13,847건)]── (:Admission_Track)
     실기유형/재료 키워드 겹침 - 결정론적 텍스트 매칭, LLM 미사용

  (:Admission_Department) ──[:SIMILAR_TO (491건)]── (:Admission_Department)
     같은 표준계열 태그 내 커리큘럼 임베딩 코사인 유사도 0.70 이상만 채택
========================================================================================
```

---

## 2. 전체 노드 라벨 (11개, 실측: `CALL db.labels()`)

### 2.1 [1층] 공식 팩트 노드

| 노드 라벨 | 실측 노드 수 | 생성 스크립트 | 설명 |
|---|---:|---|---|
| `Admission_University` | 60 | `00_Art_Admission_Graph_Loader.py` | 공식 수시 모집요강이 수집된 대학(캠퍼스 구분 포함) |
| `Admission_Department` | 213 | 〃 | 실기전형을 운영하는 검증된 미술계열 학과 (임베딩 보유 201개) |
| `Admission_Track` | 299 | 〃 | 전형(수시 모집 단위) - 정밀 계산의 핵심 노드 |
| `Admission_ExamType` | 299 | 〃 | 실기고사 과목/규격/시간/준비물 |
| `Admission_Schedule` | 299 | 〃 | 원서접수/실기고사/발표 일정 |
| `Admission_SelectionStage` | 98 | 〃 | 다단계 전형의 단계별 배점 (v1.0의 "Admission_Stage"는 **오기** - 실제 라벨명 아님) |
| `Admission_CutoffEstimate` | 77 | 〃 | 전년도 입시결과 기반 추정 컷(공식 아님, 별도 표기) |
| `Admission_PastTopic` | 12 | 〃 | 기출 실기주제 원문 발췌 |
| `Admission_YearlyResult` | 75 | 〃 | 연도별 경쟁률 등 과거 결과 (v1.0에 언급조차 없던 노드) |

### 2.2 [2층] 비정형 의미망 노드

| 노드 라벨 | 실측 노드 수 | 생성 스크립트 | 설명 |
|---|---:|---|---|
| `Admission_TextChunk` | 4,061 | `01_Art_Admission_Vector_Indexer.py` | PDF 원문 1,500자 청크 + 1,536차원 임베딩 |
| `Admission_Entity` | 5,412 (LLM 신규발견 4,846) | `02_Art_Admission_Entity_Linker.py` | LLM이 원문에서 추출한 개체 - `type`(university/department/exam_type/material/기타), `community`, `pagerank` 속성 보유 |

---

## 3. 전체 관계 타입 (12개, 실측: `CALL db.relationshipTypes()`)

v1.0은 6종만 기록했다. 실제로는 12종이 존재한다 - 누락 3종(`ESTIMATED_CUTOFF`,
`HAD_PAST_TOPIC`, `HAS_YEARLY_RESULT`)과 오늘 오후 신설 2종(`COMPATIBLE_WITH`,
`SIMILAR_TO`)을 추가했다.

| 관계 타입 | 출발 → 도착 | 속성 | 실측 건수 | 비고 |
|---|---|---|---:|---|
| `HAS_DEPARTMENT` | University → Department | 없음 | 213 | |
| `HAS_TRACK` | Department → Track | 없음 | 299 | |
| `REQUIRES_EXAM` | Track → ExamType | 없음 | 299 | |
| `HAS_SCHEDULE` | Track → Schedule | 없음 | 299 | |
| `HAS_STAGE` | Track → SelectionStage | 없음 | 98 | |
| `ESTIMATED_CUTOFF` | Track → CutoffEstimate | 없음 | 77 | **v1.0 누락** |
| `HAD_PAST_TOPIC` | Track → PastTopic | 없음 | 12 | **v1.0 누락** |
| `HAS_YEARLY_RESULT` | Track → YearlyResult | 없음 | 75 | **v1.0 누락** |
| `MENTIONS` | TextChunk → Entity | 없음 | 23,054 | 원문에 실제 언급된 근거 |
| `CO_OCCURS_WITH` | Entity ↔ Entity | `weight` | 94,563(무방향, 중복제거) | 커뮤니티/PageRank 계산 원천 |
| `COMPATIBLE_WITH` | Track ↔ Track | `shared_keywords`, `shared_materials`, `match_type` | **13,847** | **2026-09-18 오후 신설** - 실기유형/재료 키워드 겹침, LLM 미사용, 배치 사전계산 |
| `SIMILAR_TO` | Department ↔ Department | `similarity_pct`, `standard_tag` | **491** | **2026-09-18 오후 신설** - 같은 표준계열 태그 내 커리큘럼 임베딩 코사인 유사도 0.70 이상, 배치 사전계산 |

---

## 4. 커뮤니티/PageRank 오염 방지 (v1.0에 없던 내용)

`Admission_Entity`의 `community`/`pagerank` 속성은 전체 5,412개 중 **1,136개가
제외된 상태**로 계산된다 - 검증된 `Admission_Track`이 실제로 있는 대학/학과만
남기고, 나머지(다른 학교 원문에 이름만 등장한 학교 등)는 커뮤니티 계산에서
뺀다. 총 254개 커뮤니티가 존재하며, 상위 커뮤니티에는 LLM이 붙인 한글 라벨이
있다. (배경: 2026-09-17 "컴퓨터공학부가 미술 커뮤니티에 섞인" 오염 사고, 2026-09-18
"계명대 원문의 무관한 대학 명단에 등장한 중앙대학교가 하나의 전역 노드로 합쳐진"
오염 사고 - 둘 다 "같은 텍스트에 등장 = 관련 있음"이라는 잘못된 가정에서 발생)

---

## 5. 세 번째 관계 유형: 배치 파생 관계 (v1.0에 없던 개념)

v1.0은 "1층/2층" 2-Tier만 설명했다. 오늘 오후 신설된 `COMPATIBLE_WITH`/
`SIMILAR_TO`는 이 두 층 어디에도 속하지 않는 **세 번째 성격**이다:

| 구분 | 1층 | 2층 | 배치 파생 관계 |
|---|---|---|---|
| 원재료 | 사람이 검수한 JSON | LLM이 PDF에서 추출 | 1층의 검증된 값(Track/Department) |
| 계산 방식 | 없음(그대로 적재) | LLM 판단 | 결정론적 계산(키워드 매칭/코사인 유사도) |
| LLM 사용 | 없음 | 있음 | **없음** |
| 신뢰도 | 최고(사람 검수) | 검증 필요(원문검증+신뢰도필터 적용됨) | 계산 자체는 결정론적이나, 정확도는 별도 검증됨(SIMILAR_TO는 무작위 대비 1.3배 수준 - 완전한 신뢰 신호는 아님, 18번 문서 참고) |

---

## 6. 참고 - JSON과 PDF 원문의 역할 구분

v1.0의 이 절 내용(정형 JSON=계산용, 비정형 PDF=상담용)은 그대로 유효하다.
변경 없음.
