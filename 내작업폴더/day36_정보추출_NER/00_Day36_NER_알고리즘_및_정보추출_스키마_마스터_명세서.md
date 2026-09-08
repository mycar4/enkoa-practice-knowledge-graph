# 📋 [Day 36] NER 알고리즘 및 정보 추출 스키마 마스터 명세서

> **문서 목적**: 의학 및 바이오메디컬 텍스트 정보 추출(IE)을 위한 5대 개체 타입 스키마, BIO 태깅 규격, Pydantic 모델 명세, 정제 퍼널 수학적/논리적 필터 규칙 정의

---

## 🏷️ 1. 개체(Entity) 타입 스키마 상세 명세

| 개체 타입 (Type) | 의미 및 도메인 정의 | 대표 예시 | 지식그래프 노드 매핑 |
|---|---|---|:---:|
| `Compound` | 의약품, 화학 물질, 유효 성분 | `Aspirin`, `Simvastatin`, `Clopidogrel` | `:Compound (Hetionet)` |
| `Gene` | 인체 유전자, 단백질, 효소 | `CYP3A4`, `APOE`, `VKORC1`, `EGFR` | `:Gene (Hetionet)` |
| `Disease` | 질병, 증후군, 임상 진단 질환 | `Myocardial infarction`, `Alzheimer's` | `:Disease (Hetionet)` |
| `Symptom` | 환자가 호소하는 증상, 임상 징후 | `Headache`, `Nausea`, `Pain` | `:Symptom (Hetionet)` |
| `PharmacologicClass`| 약리학적 분류군, 약효 군 | `HMG-CoA reductase inhibitors`, `Statins` | `:PharmacologicClass` |
| `Other` | 상기 5종에 속하지 않는 기타 개체 (격리용) | 기관명, 연도, 일반 용어 | **폐기 (DISCARD)** |

---

## 🧬 2. 데이터 표현 스키마 및 규격

### 1) 구간(Span) 표현 명세
텍스트 문자열 내의 반열린 구간 $[start, end)$ 형식:
```python
Span = tuple[int, int, str]  # (start_index, end_index, entity_type)
# 불변식: text[start:end] == entity_name
```

### 2) BIO 태깅 규격
토큰 단위의 레이블링 체계:
* `O`: 개체 밖 (Outside)
* `B-<Type>`: 개체의 첫 번째 토큰 (Begin)
* `I-<Type>`: 개체의 두 번째 이후 토큰 (Inside)

**경계 보존 규칙 (Boundary Invariant)**:
* 연속된 두 토큰이 모두 동일한 타입이라도 개체가 서로 다르면 두 번째 개체의 시작은 반드시 `B-`로 시작해야 함.
* $T_k = \text{B-Compound}, T_{k+1} = \text{B-Compound} \implies 2\text{개의 독립된 약물 개체}$.
* $T_k = \text{B-Compound}, T_{k+1} = \text{I-Compound} \implies 1\text{개의 복합 약물 개체}$.

### 3) Pydantic 구조화 출력 스키마
```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

EntityType = Literal[
    "Compound",
    "Gene",
    "Disease",
    "Symptom",
    "PharmacologicClass",
    "Other",
]


class ExtractedEntity(BaseModel):
  """단일 개체 추출 스키마"""

  name: str = Field(
      description="원문에 등장한 개체의 정확한 텍스트 (변형/수정 금지)"
  )
  type: EntityType = Field(description="개체 유형 (5종 중 하나, 없으면 Other)")
  other_type: Optional[str] = Field(
      default=None, description="type이 Other인 경우 실제 의미하는 유형"
  )
  confidence: Optional[float] = Field(
      default=None, ge=0.0, le=1.0, description="모델의 자기 확신도 점수 (0~1)"
  )


class ExtractedEntityList(BaseModel):
  """복수 개체 목록 스키마"""

  entities: List[ExtractedEntity] = Field(
      default_factory=list, description="추출된 개체 목록"
  )
```

---

## 🧪 3. 3단계 후처리 정제 퍼널 필터링 규칙 (Post-Processing Filter Rules)

추출된 원시 개체 집합 $\mathcal{E}_{raw}$에 대해 순차적 필터 함수 $\mathcal{F}_1, \mathcal{F}_2, \mathcal{F}_3$을 적용:

$$\mathcal{E}_{clean} = \mathcal{F}_3 \circ \mathcal{F}_2 \circ \mathcal{F}_1 (\mathcal{E}_{raw})$$

```python
ALLOWED_TYPES = {
    "Compound",
    "Gene",
    "Disease",
    "Symptom",
    "PharmacologicClass",
}


def clean_entities(
    entities: list[dict], raw_text: str
) -> tuple[list[dict], dict]:
  """3단계 정제 퍼널 실행기"""
  # 1단계: 허용 유형 검증
  stage1 = [e for e in entities if e.get("type") in ALLOWED_TYPES]

  # 2단계: 원문 등장 대조 (환각 배제)
  stage2 = [e for e in stage1 if e.get("name") in raw_text]

  # 3단계: (name, type) 튜플 기준 중복 제거
  seen = set()
  stage3 = []
  for e in stage2:
    key = (e.get("name"), e.get("type"))
    if key not in seen:
      seen.add(key)
      stage3.append(e)

  stats = {
      "raw": len(entities),
      "after_type": len(stage1),
      "after_presence": len(stage2),
      "final": len(stage3),
      "dropped_by_type": len(entities) - len(stage1),
      "dropped_by_hallucination": len(stage1) - len(stage2),
      "dropped_by_duplicate": len(stage2) - len(stage3),
  }
  return stage3, stats
```

---

## 📚 4. 사전 및 패턴 매칭 세부 규격

### 1) 표준 사전 (`name2id.json`) 구조
```json
{
  "names": {
    "Simvastatin": "Compound::DB00641",
    "Alzheimer's disease": "Disease::DOID:10652"
  },
  "symbols": {
    "CYP3A4": "Gene::1576",
    "APOE": "Gene::348"
  },
  "brand_stopwords": [
    "today", "perform", "allegra", "focus", "target", "matrix", "normal", "advance"
  ]
}
```

### 2) 대소문자 방어 불변식 (Case-Sensitivity Invariants)
1. **일반 단어 오탐 방어**: 영문 소문자 단어(`large`, `today`)를 유전자나 약물로 매칭하지 않도록, 사전 검색 시 대소문자 일치를 엄격 적용하거나 불용어 사전을 선행 조회한다.
2. **변이 식별자 패턴**: 정규식 `r"\brs[0-9]+\b"`를 통해 변이 ID를 독립적으로 추출한다.
