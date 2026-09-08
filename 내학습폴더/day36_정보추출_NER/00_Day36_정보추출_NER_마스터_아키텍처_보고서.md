# 🏛️ [Day 36] 정보 추출(IE)과 개체명 인식(NER) 마스터 아키텍처 보고서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 개편)  
> **위치**: `내학습폴더/day36_정보추출_NER/00_Day36_정보추출_NER_마스터_아키텍처_보고서.md`  
> **기준 문서**: [DART·ART 학습 대조 데이터 명세서 v1.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🗺️ [전체 지도에서의 위치: 우리는 무엇을 위해 이것을 배우는가?]

```text
[전체 6대 파이프라인 조감도]
★ ① 자동 추출 파이프라인 (Day 36~42) ◀◀◀ [현재 위치: Day 36 '점(Node)' 식별]
   - Day 36 (개체/NER): 비정형 모집요강/공시 텍스트에서 '점(Node)'을 복합키로 식별
   - Day 37 (온톨로지): 점과 점 사이에 허용된 '선(Edge)'을 규격대로 긋고 검증
   - Day 38~42 (배치 자동화): 요강 PDF 인입 시 수백 개 대학·전형 지식그래프 자동 적재
  ② 하이브리드 검색 + 리랭킹 (Day 46~48)
  ③ 에이전트 오케스트레이션 (Day 50~56)
  ④ 자기검증 루프 Self-RAG (Day 53~54)
  ⑤ 자동 품질평가 + 가드레일 (Day 59~64)
  ⑥ 도메인 파인튜닝 + 자체 서빙 (Day 65~79)
```
> **학습 목적**: "미대 모집요강(PDF)과 기업공시(XML)에서 지식그래프의 기둥이 될 '대학, 학과, 실기종목, 상장사, 주주' 노드를 1건의 오차 없이 컴퓨터가 자동 추출하기 위함이다."

---

## 💡 1. WHY (본질과 정의: 왜 정보 추출과 개체명 인식이 필요한가?)

### 10초 초등생 비유: "흙탕물 속에서 보석 골라내기"
1. **비정형 문서 (흙탕물)**: 수백 페이지의 대학 입시 모집요강 PDF나 금융감독원 공시 보고서는 복잡한 안내문과 줄글이 뒤섞여 있어 컴퓨터가 바로 이해할 수 없습니다.
2. **개체명 인식 (보석 탐지기)**: 글자들 속에서 **"중앙대학교(대학)", "공간연출전공(학과)", "소묘(실기종목)", "삼성전자(회사)", "국민연금(주주)"**처럼 우리 서비스에 꼭 필요한 **진짜 보석(개체, Entity)**만 네모 칸 쳐서 정확히 골라내는 기술입니다.
3. **노드(Node)의 탄생**: 이렇게 골라낸 단어들이 바로 지식그래프에서 동그라미로 표현되는 **'점(Node)'**이 됩니다.

---

## 🛠️ 2. HOW: 개체 표현의 2대 표준 규격

컴퓨터가 텍스트에서 단어를 인식할 때 쓰는 2가지 표준 표현 방식입니다:

### 1) 구간 (Span) 방식
* 텍스트 문자열 내에서 단어가 시작하는 글자 번호(`start`)와 끝나는 글자 번호(`end`)를 지정:
  ```python
  text = "중앙대학교 서울캠퍼스 공간연출전공 실기형 소묘"
  # (start, end, label)
  spans = [
      (0, 5, "University"),  # text[0:5] == '중앙대학교'
      (6, 11, "Campus"),  # text[6:11] == '서울캠퍼스'
      (12, 18, "Department"),  # text[12:18] == '공간연출전공'
      (23, 25, "PracticalType"),  # text[23:25] == '소묘'
  ]
```

### 2) BIO 태깅 (Begin - Inside - Outside) 규격
* 단어(토큰) 단위로 위치와 역할을 라벨링하는 전통적 표준 체계:
  * `B-<Type>`: 개체가 시작하는 첫 번째 토큰 (Begin)
  * `I-<Type>`: 개체 내에 연속되는 두 번째 이후 토큰 (Inside)
  * `O`: 개체에 속하지 않는 일반 단어 (Outside)
* **우리 데이터에서의 경계 보존 불변식**:
  * 한 문장에 실기 종목 2개가 연속으로 등장할 때: `"1단계는 소묘 기초디자인 중 택1"`
  * `B-PracticalType` 태그가 없으면 `소묘`와 `기초디자인`이 하나의 이상한 종목으로 합쳐지는 치명적 오류가 발생합니다.
  * `소묘(B-PracticalType)`, `기초디자인(B-PracticalType)`으로 분리해야 독립된 2개의 실기 노드로 보존됩니다.

---

## 🚫 3. 규칙 기반 NER(사전 매칭)의 4대 한계점과 우리 서비스의 함정

단순히 사전에 대학 목록/상장사 목록을 넣어두고 문자열을 검색하는 방식은 실무에서 반드시 실패합니다:

1. **미등록어 (신설 전형/신규 상장사)**: 사전에 없는 `AI융합미디어아트전공(신설)`이나 신규 IPO 기업을 전혀 감지하지 못함.
2. **복합어 경계 분리 실패**: `중앙대-안성캠`, `포스코-퓨처엠`처럼 붙임표나 조사가 붙으면 단어 분리 실패.
3. **캠퍼스 및 동음이의어 함정**: `중앙대학교(서울)`과 `중앙대학교(안성)`은 입시 컷트라인과 실기 종목이 완전히 다른 학교인데, 단순 '중앙대' 검색 시 하나의 노드로 뭉개짐.
4. **약어 충돌**: `SNU`가 서울대인지, 다른 기관인지 문맥 없이는 구별 불가.

---

## 🧠 4. 현대적 해결책: Pydantic + LLM 구조화 출력 (`with_structured_output`)

과거의 400MB짜리 레거시 BERT 모델을 일일이 파인튜닝하던 방식은 폐기되었습니다.  
현대 표준 기술은 **우리 서비스의 Pydantic 스키마를 선언하고 LLM이 그 타입에 맞춰 정형 JSON을 출력하도록 강제**합니다:

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# ART:READY 표준 엔티티 타입
ArtNodeType = Literal[
    'University',
    'Department',
    'AdmissionTrack',
    'PracticalType',
    'ExamSchedule',
    'Other',
]


class ExtractedArtEntity(BaseModel):
  name: str = Field(
      description='모집요강 원문에 등장한 명칭 그대로 (예: 중앙대학교, 공간연출전공)'
  )
  type: ArtNodeType = Field(description='사전에 정의된 입시 노드 타입')
  detail: Optional[str] = Field(
      default=None, description='캠퍼스(서울/안성) 또는 실기 세부정보'
  )


class ArtEntityList(BaseModel):
  entities: List[ExtractedArtEntity] = Field(description='추출된 입시 개체 목록')
```
> **효과**: LLM이 사전에 없는 엉뚱한 레이블을 출력하는 것을 원천 차단하고, 100% 정형화된 데이터 수신.

---

## 🏢 5. [DART-Trace] 실제 적용 사례 (실전 서비스 1)

* **서비스 질문**: *"공시 보고서에서 누가 주식을 소유하고 있고, 대상 회사는 어디인가?"*
* **실제 데이터 매핑**:
  - `Company`: 대상 상장사 (예: 삼성전자 `00126380`)
  - `Shareholder`: 지분 보유자 (예: `국민연금공단`, `최태원`)
  - `DART_Disclosure`: 공시 접수번호 14자리 (`rcept_no`)
  - `EvidenceFragment`: XML 2D XPath 테이블 파편 (`table[3]/tr[5]`)
* **핵심 판정**: *"동음이의 사명(예: 케이티씨에스 vs 케이티)을 법인코드(`corp_code`)로 분리하고, 미확인 법인은 `:Candidate`로 안전하게 격리."*

---

## 🎨 6. [ART:READY] 실제 적용 사례 (실전 서비스 2)

* **서비스 질문**: *"미대 모집요강에서 어느 대학, 어느 캠퍼스, 어느 학과, 어느 전형을 노드로 찍을 것인가?"*
* **실제 데이터 매핑 (`cau_spatial_design.json` 기준)**:
  - `University`: `중앙대학교 (서울)` ➔ `{univ_code: 'CAU_SEOUL'}`
  - `Department`: `공간연출전공` ➔ `{dept_name: '공간연출전공'}`
  - `AdmissionTrack`: `2027 수시 실기형` ➔ `{track_id: 'CAU_2027_REG_PRACTICAL'}`
  - `PracticalType`: `소묘(공간구성과 묘사)` ➔ `{type: '소묘'}`
* **핵심 판정**: *"같은 학과라도 캠퍼스나 학년도가 다르면 완전히 다른 입시 조건을 고유 복합키 노드로 격리."*

---

## 🔍 7. 현재 구현 및 원본 근거
* **DART-Trace**:
  - `00_Raw_Evidence_Graph_Loader.py`에서 `RawHoldingFact`를 정의하고 `target_corp_code` 기반의 고유성 검증 확립.
  - `EvidenceFragment` 노드로 원천 XML 행 번호 및 XPath 결속 완료 (Aura Cloud 79,848개 노드 적재 보존).
* **ART:READY**:
  - `내작업폴더/data/art_admission/raw/cau_spatial_design.json` 실데이터 기반.
  - `00_Art_Admission_Graph_Loader.py`에서 `University`, `Department`, `AdmissionTrack` 노드 스키마 정의 완료.

---

## ⚠️ 8. 부족한 부분 하나 (결손 과제)
* **DART-Trace**: 사명 변경 기업(예: `포스코케미칼` ➔ `포스코퓨처엠`) 발생 시 수동 개입 없이 `:Candidate` 큐로 밀어 넣는 엔티티 링킹 자동화.
* **ART:READY**: 현재 15개 대학 데이터를 손으로 JSON 입력 중이므로, **"모집요강 PDF 텍스트를 LLM Pydantic 구조화 스키마로 읽어 학과/전형 노드를 자동 추출하는 파서(`extract_art_admission.py`)"** 구축이 핵심 당면 과제임.

---

## 🧪 9. DRY-RUN 또는 읽기 전용 검증 기준
1. **단일 레코드 식별성 검사**:
   - 추출된 대학명/학과명이 모집요강 원문에 100% 실존하는가? (`ground_truth_check`)
2. **복합키 충돌 검사 (Deduplication)**:
   - `(univ_name, campus, dept_name, track_name, year)` 5대 복합키가 정확히 1개의 `:AdmissionTrack` 노드로만 매핑되는가?
3. **DB 오염 방지**:
   - 매핑에 실패한 신설 학과는 프로덕션 노드로 승격되지 않고 `:CandidateMajor` 레이블로 격리되는가?

---

## ✅ 10. 완료 판정 (Done Definition)
> **[합격 판정 기준]**  
> 1. **DART**: "같은 이름·다른 법인(동음이의어), 법인코드 변경 이력을 혼동하지 않는 고유 복합키가 정의되어 있는가?"  
> 2. **ART**: "같은 대학·다른 캠퍼스(중앙대 서울 vs 안성), 같은 학과·다른 학년도(2026 vs 2027)를 1건의 오차도 없이 구별하는 고유 복합키 노드가 생성되는가?"  
> **판정**: **기준 만족 시 Day 36 합격 🟢**
