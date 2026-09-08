#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ [Day 36] 정보 추출(IE)과 개체명 인식(NER) 실전 마스터 통합 풀소스
================================================================================
본 스크립트는 Day 36의 전체 파이프라인(구간/BIO 태깅, 규칙 기반 NER, 
LLM Pydantic 구조화 추출, 3단계 정제 퍼널, 배치 벤치마크)을 완벽하게 구동·검증하는
원스톱 마스터 소스입니다.

[핵심 5대 파이프라인]
  1. 환경 점검 및 OpenAI 연동 (.env 기반 보안 로딩)
  2. 구간(Span) 및 BIO 태깅 인코딩/디코딩 엔진 검증
  3. 규칙 기반 NER (사전 매칭, 변이 패턴 정규식, 대소문자/불용어 방어)
  4. LLM 기반 Pydantic 구조화 추출 (with_structured_output)
  5. 3단계 후처리 정제 퍼널 및 규칙 vs LLM 벤치마크 리포트
================================================================================
"""

import os
import sys
import json
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple, Literal

# Windows CP949 인코딩 방어
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ── 1. 환경 설정 및 API 로딩 ──────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

env_path = SCRIPT_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-5.6-luna"

# 허용된 5대 지식그래프 노드 레이블
ALLOWED_TYPES = {"Compound", "Gene", "Disease", "Symptom", "PharmacologicClass"}

EntityType = Literal["Compound", "Gene", "Disease", "Symptom", "PharmacologicClass", "Other"]

class ExtractedEntity(BaseModel):
    name: str = Field(description="원문에 등장한 개체의 정확한 텍스트 (변형 금지)")
    type: EntityType = Field(description="개체 유형 (5종 또는 Other)")
    other_type: Optional[str] = Field(default=None, description="type이 Other인 경우 실제 유형")
    confidence: Optional[float] = Field(default=None, description="0.0~1.0 확신도 점수")

class ExtractedEntityList(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list, description="추출된 개체 목록")


# ── 2. 구간(Span) 및 BIO 태깅 엔진 ────────────────────────────────────────────
def find_spans(text: str, entities: List[Tuple[str, str]]) -> List[Tuple[int, int, str]]:
    """텍스트에서 (개체명, 타입) 쌍을 찾아 (start, end, type) 구간 목록을 생성"""
    spans = []
    for name, ent_type in entities:
        start = text.find(name)
        if start != -1:
            end = start + len(name)
            spans.append((start, end, ent_type))
    return spans

def spans_to_bio(tokens: List[str], token_spans: List[Tuple[int, int]], 
                 entity_spans: List[Tuple[int, int, str]]) -> List[str]:
    """토큰과 개체 구간을 대조하여 BIO 태그 시퀀스를 생성"""
    tags = ["O"] * len(tokens)
    for ent_start, ent_end, ent_type in entity_spans:
        first = True
        for idx, (t_start, t_end) in enumerate(token_spans):
            # 토큰이 개체 구간과 겹치는지 확인
            if t_start >= ent_start and t_end <= ent_end:
                if first:
                    tags[idx] = f"B-{ent_type}"
                    first = False
                else:
                    tags[idx] = f"I-{ent_type}"
    return tags

def decode_bio(tokens: List[str], tags: List[str]) -> List[Tuple[str, str]]:
    """BIO 태그 시퀀스로부터 (개체명, 타입) 목록을 복원"""
    entities = []
    current_tokens = []
    current_type = None

    for token, tag in zip(tokens, tags):
        if tag.startswith("B-"):
            if current_tokens and current_type:
                entities.append((" ".join(current_tokens), current_type))
            current_tokens = [token]
            current_type = tag.split("-")[1]
        elif tag.startswith("I-"):
            if current_type == tag.split("-")[1]:
                current_tokens.append(token)
            else:
                if current_tokens and current_type:
                    entities.append((" ".join(current_tokens), current_type))
                current_tokens = [token]
                current_type = tag.split("-")[1]
        else:
            if current_tokens and current_type:
                entities.append((" ".join(current_tokens), current_type))
                current_tokens = []
                current_type = None

    if current_tokens and current_type:
        entities.append((" ".join(current_tokens), current_type))

    return entities


# ── 3. 규칙 기반 NER 엔진 ─────────────────────────────────────────────────────
class RuleBasedNER:
    def __init__(self, name2id_path: Path):
        self.names = {}
        self.symbols = {}
        self.brand_stopwords = set()
        if name2id_path.exists():
            with open(name2id_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.names = data.get("names", {})
                self.symbols = data.get("symbols", {})
                self.brand_stopwords = set(data.get("brand_stopwords", []))

    def extract(self, text: str) -> List[Dict[str, Any]]:
        results = []
        # 1) 단어 토큰화
        words = re.findall(r"\b\w+\b", text)
        
        # 2) 표준 사전 대조 (대소문자 엄격 일치 및 불용어 필터)
        for w in words:
            if w.lower() in self.brand_stopwords:
                continue
            
            # 화합물/질병 명칭
            if w in self.names:
                cat = self.names[w].split("::")[0]
                results.append({"name": w, "type": cat, "method": "dictionary"})
            # 유전자 기호 (대문자 우선)
            elif w in self.symbols and w.isupper():
                results.append({"name": w, "type": "Gene", "method": "dictionary"})

        # 3) 정규식 패턴 매칭 (변이 ID: rs[0-9]+)
        variants = re.findall(r"\brs[0-9]+\b", text)
        for v in variants:
            results.append({"name": v, "type": "Variant", "method": "pattern"})

        return results


# ── 4. 3단계 후처리 정제 퍼널 (Post-Processing Funnel) ────────────────────────
def clean_entities(entities: List[Dict[str, Any]], raw_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    1단계: 허용 유형 검증 (Other 및 비표준 타입 배제)
    2단계: 원문 등장 대조 (환각 방어)
    3단계: (name, type) 기준 중복 제거
    """
    # 1단계
    stage1 = [e for e in entities if e.get("type") in ALLOWED_TYPES]
    # 2단계
    stage2 = [e for e in stage1 if e.get("name") in raw_text]
    # 3단계
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
        "dropped_type": len(entities) - len(stage1),
        "dropped_hallucination": len(stage1) - len(stage2),
        "dropped_duplicate": len(stage2) - len(stage3),
    }
    return stage3, stats


# ── 5. LLM 기반 추출기 (LangChain) ─────────────────────────────────────────────
def extract_with_llm(text: str) -> List[Dict[str, Any]]:
    if not OPENAI_API_KEY:
        print("⚠️ [경고] OPENAI_API_KEY 미설정으로 LLM 추출을 모의(Mock) 데이터로 진행합니다.")
        return [
            {"name": "Simvastatin", "type": "Compound", "confidence": 0.98},
            {"name": "CYP3A4", "type": "Gene", "confidence": 0.95},
            {"name": "myopathy", "type": "Disease", "confidence": 0.92},
            {"name": "statins", "type": "PharmacologicClass", "confidence": 0.90},
            {"name": "PMC13432136", "type": "Other", "other_type": "Citation", "confidence": 0.99}
        ]

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate

        llm = ChatOpenAI(model=MODEL_NAME)
        structured_llm = llm.with_structured_output(ExtractedEntityList)

        prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an expert biomedical information extraction system. "
             "Extract all biomedical entities from the provided text into the structured format. "
             "Allowed types: Compound, Gene, Disease, Symptom, PharmacologicClass. "
             "If an entity does not fit these five types, label it as 'Other' and specify 'other_type'. "
             "Do NOT modify or alter the original text of the entity name."),
            ("user", "Text: {text}")
        ])

        chain = prompt | structured_llm
        res = chain.invoke({"text": text})
        return [e.model_dump() for e in res.entities]
    except Exception as ex:
        print(f"❌ [LLM 호출 에러]: {ex}")
        return []


# ── 6. 통합 마스터 실행 및 벤치마크 ───────────────────────────────────────────
def main():
    print("=" * 80)
    print("🏛️ [Day 36] 정보 추출(IE) 및 개체명 인식(NER) 실전 마스터 파이프라인")
    print("=" * 80)

    # 1. 테스트 원문 데이터 로딩
    core_papers_path = DATA_DIR / "core_papers.jsonl"
    name2id_path = DATA_DIR / "name2id.json"
    
    sample_text = (
        "Statins like Simvastatin are metabolized by CYP3A4. "
        "Patients taking Warfarin may experience adverse drug interactions leading to severe myopathy."
    )
    
    if core_papers_path.exists():
        with open(core_papers_path, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            sample_text = first_line.get("text", sample_text)
            print(f"📄 [원천 논문 로드]: {first_line.get('pmcid', 'DEMO')} (길이: {len(sample_text)}자)")

    print(f"\n[분석 대상 원문 발췌]\n\"{sample_text[:140]}...\"\n")

    # 2. 구간 및 BIO 태깅 데모
    print("─" * 80)
    print("🧬 1. 구간(Span) 및 BIO 태깅 엔진 검증")
    demo_tokens = ["Patients", "taking", "Simvastatin", "developed", "severe", "myopathy", "."]
    demo_spans = [(16, 27), (44, 52)] # Simvastatin, myopathy
    token_spans = [(0, 8), (9, 15), (16, 27), (28, 37), (38, 44), (45, 53), (53, 54)]
    ent_spans = [(16, 27, "Compound"), (45, 53, "Disease")]
    
    bio_tags = spans_to_bio(demo_tokens, token_spans, ent_spans)
    restored = decode_bio(demo_tokens, bio_tags)
    
    print(f"  • 토큰 목록: {demo_tokens}")
    print(f"  • BIO 태그:  {bio_tags}")
    print(f"  • 디코딩 복원: {restored}")
    assert len(restored) == 2, "BIO 복원 무결성 실패"
    print("  ✅ [PASS] BIO 태깅 인코딩/디코딩 경계 보존 완료")

    # 3. 규칙 기반 NER 실행
    print("─" * 80)
    print("📐 2. 규칙 기반 NER (사전 매칭 + 정규식 패턴)")
    rule_ner = RuleBasedNER(name2id_path)
    rule_raw = rule_ner.extract(sample_text)
    print(f"  • 규칙 기반 원시 추출 건수: {len(rule_raw)}건")
    for r in rule_raw[:5]:
        print(f"    - [{r['type']}] {r['name']} ({r['method']})")

    # 4. LLM 기반 구조화 추출 실행
    print("─" * 80)
    print("🧠 3. LLM Pydantic 구조화 추출 (with_structured_output)")
    llm_raw = extract_with_llm(sample_text)
    print(f"  • LLM 원시 추출 건수: {len(llm_raw)}건")
    for r in llm_raw[:5]:
        conf = f"(conf: {r.get('confidence'):.2f})" if r.get('confidence') else ""
        print(f"    - [{r['type']}] {r['name']} {conf}")

    # 5. 3단계 후처리 정제 퍼널 적용
    print("─" * 80)
    print("🧪 4. 3단계 후처리 정제 퍼널 (Post-Processing Funnel)")
    clean_llm, stats = clean_entities(llm_raw, sample_text)
    print(f"  • [퍼널 감축 통계]")
    print(f"    - 원시 추출:       {stats['raw']:2d}개")
    print(f"    - 1단계 (유형 검증): {stats['after_type']:2d}개 (탈락: {stats['dropped_type']}개)")
    print(f"    - 2단계 (원문 등장): {stats['after_presence']:2d}개 (탈락: {stats['dropped_hallucination']}개)")
    print(f"    - 3단계 (중복 제거): {stats['final']:2d}개 (탈락: {stats['dropped_duplicate']}개)")
    print(f"  • 최종 확정 개체:")
    for e in clean_llm:
        print(f"    ✨ [{e['type']}] {e['name']}")

    # 6. 최종 벤치마크 및 비교
    print("─" * 80)
    print("📊 5. 규칙 기반 vs LLM 하이브리드 대조 벤치마크")
    rule_names = {r["name"] for r in rule_raw}
    llm_names = {e["name"] for e in clean_llm}
    
    common = rule_names & llm_names
    llm_only = llm_names - rule_names
    rule_only = rule_names - llm_names

    print(f"  • 공통 포착 개체 ({len(common)}건): {list(common)}")
    print(f"  • LLM 단독 포착 (미등록어/신규어) ({len(llm_only)}건): {list(llm_only)}")
    print(f"  • 규칙 단독 포착 ({len(rule_only)}건): {list(rule_only)}")

    print("\n" + "=" * 80)
    print("✅ [Day 36 실전 마스터 파이프라인 정상 가동 완료]")
    print("=" * 80)

if __name__ == "__main__":
    main()
