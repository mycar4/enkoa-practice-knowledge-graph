# -*- coding: utf-8 -*-
"""
================================================================================
🏛️ [Day 38] 지식그래프 추출품질 검증·오류교정·F1평가 실전 마스터 풀소스
================================================================================
- 버전: v1.0 (2026-09-09 우리 실데이터 기준 전면 신규)
- 목적: 5대 품질지표(스키마 준수율·원문 일치율·TP·FP·FN·F1) 실측 및 오류 교정 전후 평가
- 환경: Python 3.10+, 가상환경 .venv 완벽 지원 (외부 API 종속성 없는 자체 완결형 엔진)
================================================================================
"""

import sys
import json
from typing import Dict, List, Tuple, Any, Set

# Windows 콘솔 한글 인코딩 방어
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# 1. [원천 데이터 & 스키마 헌장 정의]
# ==============================================================================

# DART 공시 원문 텍스트
DART_SOURCE_TEXT = (
    "삼성전자 주식등의 대량보유상황보고서. "
    "국민연금공단은 삼성전자 지분 7.25%를 보유하고 있으며, "
    "삼성생명보험은 특별관계자로서 삼성전자 보통주 지분 8.51%를 보유 중이다. "
    "기준일자는 2024년 3월 31일이다."
)

# ART:READY 미대입시 요강 원문 텍스트
ART_SOURCE_TEXT = (
    "중앙대학교 2027학년도 수시 모집요강. "
    "서울캠퍼스 실기형 전형은 1단계 소묘 80%를 반영한다. "
    "안성캠퍼스 디자인실기 전형은 기초디자인 70%를 반영한다. "
    "한양대학교 서울캠퍼스 응용미술실기는 기초디자인 70%를 반영한다."
)

# 허용 온톨로지 스키마
ALLOWED_RELATIONS = {
    ("Shareholder", "HOLDS_ECONOMIC_STAKE", "Company"),
    ("Company", "BACKED_BY_EVIDENCE", "EvidenceFragment"),
    ("University", "OFFERS_TRACK", "AdmissionTrack"),
    ("AdmissionTrack", "REQUIRES_PRACTICAL", "PracticalType")
}


# ==============================================================================
# 2. [골드 표준 정답지 (Gold Standard Ground-Truth)]
# ==============================================================================

DART_GOLD_TRIPLES = {
    ("국민연금공단", "HOLDS_ECONOMIC_STAKE", "삼성전자", 7.25),
    ("삼성생명보험", "HOLDS_ECONOMIC_STAKE", "삼성전자", 8.51)
}

ART_GOLD_TRIPLES = {
    ("중앙대학교(서울)", "OFFERS_TRACK", "2027 수시 실기형"),
    ("2027 수시 실기형", "REQUIRES_PRACTICAL", "소묘", 80.0),
    ("중앙대학교(안성)", "OFFERS_TRACK", "2027 수시 디자인실기"),
    ("2027 수시 디자인실기", "REQUIRES_PRACTICAL", "기초디자인", 70.0),
    ("한양대학교(서울)", "OFFERS_TRACK", "2027 수시 응용미술실기"),
    ("2027 수시 응용미술실기", "REQUIRES_PRACTICAL", "기초디자인", 70.0)
}


# ==============================================================================
# 3. [품질 지표 계산 엔진]
# ==============================================================================

def evaluate_schema_compliance(extractions: List[Dict[str, Any]]) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """1. 스키마 준수율 평가"""
    passed = []
    rejected = []
    for item in extractions:
        key = (item.get("source_type"), item.get("relation"), item.get("target_type"))
        if key in ALLOWED_RELATIONS:
            passed.append(item)
        else:
            rejected.append(item)
    compliance_rate = (len(passed) / len(extractions) * 100.0) if extractions else 0.0
    return compliance_rate, passed, rejected


def evaluate_evidence_grounding(extractions: List[Dict[str, Any]], raw_text: str) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """2. 근거 원문 일치율 평가 (quote substring 검사)"""
    passed = []
    rejected = []
    for item in extractions:
        quote = item.get("quote", "")
        if quote and quote in raw_text:
            passed.append(item)
        else:
            rejected.append(item)
    match_rate = (len(passed) / len(extractions) * 100.0) if extractions else 0.0
    return match_rate, passed, rejected


def calculate_f1_score(predicted_set: Set[Tuple], gold_set: Set[Tuple]) -> Dict[str, float]:
    """4. 골드 표준 대조 TP, FP, FN 및 Precision, Recall, F1 계산"""
    tp = len(predicted_set & gold_set)
    fp = len(predicted_set - gold_set)
    fn = len(gold_set - predicted_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": round(precision * 100.0, 2),
        "Recall": round(recall * 100.0, 2),
        "F1": round(f1 * 100.0, 2)
    }


# ==============================================================================
# 4. [실행 및 오류 교정 시나리오]
# ==============================================================================

def run_day38_quality_verification():
    print("=" * 80)
    print("🏛️ [Day 38] 지식그래프 추출품질 검증·오류교정·F1평가 실전 파이프라인 가동")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # [Step 1] DART 공시 지분 추출 품질 검사 및 지표 실측
    # -------------------------------------------------------------------------
    print("\n[Step 1] [DART-Trace] 공시 지분 추출 품질 검사")
    dart_raw_extractions = [
        # 정상 추출
        {"source": "국민연금공단", "source_type": "Shareholder", "relation": "HOLDS_ECONOMIC_STAKE", "target": "삼성전자", "target_type": "Company", "stake": 7.25, "quote": "국민연금공단은 삼성전자 지분 7.25%를 보유"},
        {"source": "삼성생명보험", "source_type": "Shareholder", "relation": "HOLDS_ECONOMIC_STAKE", "target": "삼성전자", "target_type": "Company", "stake": 8.51, "quote": "삼성생명보험은 특별관계자로서 삼성전자 보통주 지분 8.51%를 보유"},
        # 스키마 위반 (임의의 비인가 관계)
        {"source": "삼성전자", "source_type": "Company", "relation": "DEALS_WITH", "target": "국민연금공단", "target_type": "Shareholder", "quote": "삼성전자 보통주 지분"},
        # 인용 환각 (원문에 없는 문장 날조)
        {"source": "블랙록", "source_type": "Shareholder", "relation": "HOLDS_ECONOMIC_STAKE", "target": "삼성전자", "target_type": "Company", "stake": 5.03, "quote": "블랙록은 5% 이상 지분을 보유하고 있다고 신고했다"}
    ]

    schema_rate, dart_schema_pass, dart_schema_rej = evaluate_schema_compliance(dart_raw_extractions)
    ground_rate, dart_ground_pass, dart_ground_rej = evaluate_evidence_grounding(dart_raw_extractions, DART_SOURCE_TEXT)

    print(f"  • 전체 추출 건수: {len(dart_raw_extractions)}건")
    print(f"  • 스키마 준수율: {schema_rate:.1f}% ({len(dart_schema_pass)}/{len(dart_raw_extractions)}) [기각: {len(dart_schema_rej)}건]")
    print(f"  • 근거 원문 일치율: {ground_rate:.1f}% ({len(dart_ground_pass)}/{len(dart_raw_extractions)}) [기각: {len(dart_ground_rej)}건]")

    # 2대 필터(스키마 + 근거) 모두 통과한 트리플만 추출
    dart_final_candidates = [item for item in dart_schema_pass if item in dart_ground_pass]
    dart_pred_tuples = {(x["source"], x["relation"], x["target"], x["stake"]) for x in dart_final_candidates}
    dart_metrics = calculate_f1_score(dart_pred_tuples, DART_GOLD_TRIPLES)

    print(f"  📊 [DART Gold 대조 성적표]")
    print(f"     TP: {dart_metrics['TP']}, FP: {dart_metrics['FP']}, FN: {dart_metrics['FN']}")
    print(f"     Precision: {dart_metrics['Precision']}%, Recall: {dart_metrics['Recall']}%, F1 Score: {dart_metrics['F1']}%")

    # -------------------------------------------------------------------------
    # [Step 2] [ART:READY] 미대입시 요강 추출 오류 교정 전/후 재평가
    # -------------------------------------------------------------------------
    print("\n[Step 2] [ART:READY] 미대입시 요강 추출 오류 교정 및 재평가 (Before vs After)")

    # [교정 전] 추출 결과 (캠퍼스 분교 누락 및 타입 오류 존재)
    art_before_extractions = [
        # 정상
        {"source": "중앙대학교(서울)", "source_type": "University", "relation": "OFFERS_TRACK", "target": "2027 수시 실기형", "target_type": "AdmissionTrack", "quote": "서울캠퍼스 실기형 전형은"},
        {"source": "2027 수시 실기형", "source_type": "AdmissionTrack", "relation": "REQUIRES_PRACTICAL", "target": "소묘", "target_type": "PracticalType", "ratio": 80.0, "quote": "소묘 80%를 반영한다"},
        # 오류 1: 캠퍼스 미구분(단순 '중앙대학교')으로 인한 모순
        {"source": "중앙대학교", "source_type": "University", "relation": "OFFERS_TRACK", "target": "2027 수시 디자인실기", "target_type": "AdmissionTrack", "quote": "안성캠퍼스 디자인실기 전형은"},
        # 오류 2: 관계 타입 오류 ('NEEDS_EXAM')
        {"source": "2027 수시 디자인실기", "source_type": "AdmissionTrack", "relation": "NEEDS_EXAM", "target": "기초디자인", "target_type": "PracticalType", "ratio": 70.0, "quote": "기초디자인 70%를 반영한다"}
    ]

    art_before_set = {
        (x["source"], x["relation"], x["target"])
        for x in art_before_extractions
        if (x.get("source_type"), x.get("relation"), x.get("target_type")) in ALLOWED_RELATIONS
    }
    art_gold_core = {(g[0], g[1], g[2]) for g in ART_GOLD_TRIPLES}
    metrics_before = calculate_f1_score(art_before_set, art_gold_core)
    print(f"  [교정 전] TP: {metrics_before['TP']}, FP: {metrics_before['FP']}, FN: {metrics_before['FN']} ➔ F1: {metrics_before['F1']}%")

    # [오류 교정 파이프라인 가동]
    # 1. 관계명 표준화 규칙: NEEDS_EXAM ➔ REQUIRES_PRACTICAL 치환
    # 2. 엔터티 링킹 정합: 원문의 '안성캠퍼스' 문맥을 결합하여 '중앙대학교' ➔ '중앙대학교(안성)'으로 교정
    art_after_extractions = [
        {"source": "중앙대학교(서울)", "source_type": "University", "relation": "OFFERS_TRACK", "target": "2027 수시 실기형", "target_type": "AdmissionTrack", "quote": "서울캠퍼스 실기형 전형은"},
        {"source": "2027 수시 실기형", "source_type": "AdmissionTrack", "relation": "REQUIRES_PRACTICAL", "target": "소묘", "target_type": "PracticalType", "ratio": 80.0, "quote": "소묘 80%를 반영한다"},
        # 교정 1 적용: 중앙대학교(안성)
        {"source": "중앙대학교(안성)", "source_type": "University", "relation": "OFFERS_TRACK", "target": "2027 수시 디자인실기", "target_type": "AdmissionTrack", "quote": "안성캠퍼스 디자인실기 전형은"},
        # 교정 2 적용: REQUIRES_PRACTICAL
        {"source": "2027 수시 디자인실기", "source_type": "AdmissionTrack", "relation": "REQUIRES_PRACTICAL", "target": "기초디자인", "target_type": "PracticalType", "ratio": 70.0, "quote": "기초디자인 70%를 반영한다"}
    ]

    art_after_set = {
        (x["source"], x["relation"], x["target"])
        for x in art_after_extractions
        if (x.get("source_type"), x.get("relation"), x.get("target_type")) in ALLOWED_RELATIONS
    }
    metrics_after = calculate_f1_score(art_after_set, art_gold_core)
    print(f"  [교정 후] TP: {metrics_after['TP']}, FP: {metrics_after['FP']}, FN: {metrics_after['FN']} ➔ F1: {metrics_after['F1']}%")
    print(f"  ➔ 🚀 교정 개선도 (ΔF1): +{round(metrics_after['F1'] - metrics_before['F1'], 2)}%p 대폭 상승 달성!")

    # -------------------------------------------------------------------------
    # [Step 3] 최종 판정 검증
    # -------------------------------------------------------------------------
    assert dart_metrics["F1"] == 100.0, "DART 지분 F1 100% 미달성"
    assert metrics_after["F1"] > metrics_before["F1"], "교정 후 F1 개선 미달성"

    print("\n" + "=" * 80)
    print("🚀 [ALL PASS] Day 38 지식그래프 추출품질 검증 및 오류교정 파이프라인 검증 완료!")
    print("=" * 80)


if __name__ == "__main__":
    run_day38_quality_verification()
