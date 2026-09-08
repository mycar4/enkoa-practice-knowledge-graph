# 📋 [Day 36] NER 알고리즘 및 정보 추출 스키마 마스터 명세서

> **문서 버전**: v2.0 (2026-09-08 우리 데이터 100% 기준 전면 개편)  
> **위치**: `내학습폴더/day36_정보추출_NER/00_Day36_NER_스키마_및_명세서.md`  
> **기준 문서**: [DART·ART 학습 대조 데이터 명세서 v1.0](file:///c:/Users/Playdata/enkoa-practice-knowledge-graph/enkoa-practice-knowledge-graph/내학습폴더/docs/DART_ART_학습대조_데이터명세서_v1.0.md)

---

## 🏷️ 1. [ART:READY] 미대 입시 핵심 개체(Entity) 스키마 상세 명세

| 개체 타입 (Type) | 의미 및 도메인 정의 | 대표 예시 (`cau_spatial_design.json` 기준) | 지식그래프 노드 매핑 및 고유키 |
|---|---|---|---|
| `University` | 대학 기관 (본교/캠퍼스 분리) | `중앙대학교 (서울)`, `중앙대학교 (안성)` | `:University {univ_id: 'CAU_SEOUL'}` |
| `Department` | 모집 학과 / 전공 단위 | `공간연출전공`, `시각디자인과` | `:Department {dept_id: 'DEPT_SPATIAL'}` |
| `AdmissionTrack` | 수시/정시 전형 단위 | `2027 수시 실기형`, `정시 다군 일반` | `:AdmissionTrack {track_id: 'CAU_2027_REG_01'}` |
| `PracticalType` | 실기 고사 종목 | `소묘(공간구성과 묘사)`, `기초디자인` | `:PracticalType {type_code: 'PRACTICAL_DRAWING'}` |
| `ExamSchedule` | 실기 고사 일시 및 장소 | `2026-10-03 (1단계 소묘)` | `:ExamSchedule {schedule_id: 'SCHED_20261003'}` |
| `CandidateMajor` | 미등록/신설 학과 (격리용) | `융합미디어디자인학부 (2027 신설)` | `:CandidateMajor (프로덕션 오염 방지 격리)` |

---

## 🏢 2. [DART-Trace] 기업공시 핵심 개체(Entity) 스키마 상세 명세

| 개체 타입 (Type) | 의미 및 도메인 정의 | 대표 예시 (삼성전자 공시 기준) | 지식그래프 노드 매핑 및 고유키 |
|---|---|---|---|
| `Company` | 상장사 / 공시대상회사 | `삼성전자` | `:Company {corp_code: '00126380'}` |
| `Shareholder` | 대량보유자 / 보고자 | `국민연금공단`, `블랙록펀드` | `:Shareholder {holder_key: 'HOLDER_NPS'}` |
| `DART_Disclosure` | 공시 보고서 메타데이터 | `주식등의대량보유상황보고서` | `:DART_Disclosure {rcept_no: '20230515001234'}` |
| `EvidenceFragment` | XML 2D XPath 테이블 파편 | `table[3]/tr[5] (지분율 7.25%)` | `:EvidenceFragment {fragment_hash: 'HASH_...'}` |
| `RawHoldingFact` | 미검증 원천 사실 (격리용) | `보고자 홍길동 15,000주` | `:RawEvidenceCandidate (미승격 격리)` |

---

## 🧬 3. [ART:READY] Pydantic 구조화 추출 스키마 명세

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# 허용된 입시 노드 타입 Enum 강제
ArtNodeType = Literal[
    "University",
    "Department",
    "AdmissionTrack",
    "PracticalType",
    "ExamSchedule",
    "Other",
]


class ExtractedArtEntity(BaseModel):
  """단일 입시 개체 추출 단위"""

  name: str = Field(
      description=(
          "모집요강 원문에 등장한 명칭 그대로 (예: 중앙대학교, 공간연출전공,"
          " 소묘)"
      )
  )
  type: ArtNodeType = Field(description="5대 입시 개체 타입 중 하나")
  campus: Optional[str] = Field(
      default=None, description="캠퍼스 구분 (예: 서울, 안성)"
  )
  admission_year: Optional[int] = Field(
      default=2027, description="모집 학년도"
  )
  confidence: Optional[float] = Field(
      default=1.0, ge=0.0, le=1.0, description="모델 확신도"
  )


class ArtEntityExtractionResult(BaseModel):
  """복수 개체 추출 결과 컨테이너"""

  entities: List[ExtractedArtEntity] = Field(
      default_factory=list, description="추출된 개체 목록"
  )
```

---

## 🧪 4. 3단계 무결성 정제 퍼널 알고리즘 (우리 데이터 전용)

$$\mathcal{E}_{clean} = \mathcal{F}_{dedup} \circ \mathcal{F}_{ground} \circ \mathcal{F}_{schema} (\mathcal{E}_{raw})$$

```python
ALLOWED_ART_TYPES = {
    "University",
    "Department",
    "AdmissionTrack",
    "PracticalType",
    "ExamSchedule",
}


def clean_art_entities(
    entities: list[dict], raw_text: str
) -> tuple[list[dict], dict]:
  """모집요강 원문 대조 3단계 정제 퍼널"""
  # 1단계: 허용 입시 타입 검증 ('Other' 및 비인가 타입 폐기)
  stage1 = [e for e in entities if e.get("type") in ALLOWED_ART_TYPES]

  # 2단계: Ground-Truth 원문 실존 대조 (LLM 환각 및 임의 명칭 변형 차단)
  stage2 = [e for e in stage1 if e.get("name") in raw_text]

  # 3단계: (name, type, campus) 복합키 기준 중복 제거
  seen = set()
  stage3 = []
  for e in stage2:
    key = (e.get("name").strip(), e.get("type"), e.get("campus", ""))
    if key not in seen:
      seen.add(key)
      stage3.append(e)

  stats = {
      "raw": len(entities),
      "after_type": len(stage1),
      "after_presence": len(stage2),
      "final": len(stage3),
      "dropped_unknown_type": len(entities) - len(stage1),
      "dropped_hallucination": len(stage1) - len(stage2),
      "dropped_duplicates": len(stage2) - len(stage3),
  }
  return stage3, stats
```

---

## 🔑 5. 복합키(Composite Key) 충돌 방지 불변식

1. **캠퍼스 분리 불변식**:
   - `중앙대학교 서울캠퍼스` ➔ `CAU_SEOUL`
   - `중앙대학교 안성캠퍼스` ➔ `CAU_ANSEONG`
   - *동일 대학이라도 캠퍼스가 다르면 지식그래프 노드는 물리적으로 완전히 분리된다.*
2. **학년도 분리 불변식**:
   - 동일 학과, 동일 전형이라도 학년도(`year`)가 다르면 완전히 다른 `:AdmissionTrack` 노드로 격리 바인딩된다.
   - 예: `CAU_SPATIAL_2026` vs `CAU_SPATIAL_2027`
