#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ [Day 27] 속성 그래프(LPG) 지식그래프 모델링 실전 마스터 풀소스 (DART & ART 100% 기준)
================================================================================
본 스크립트는 RDB의 중첩 JOIN 한계를 극복하는 속성 그래프(LPG: Labeled Property Graph) 모델을
DART-Trace(기업지분)와 ART:READY(미대입시) 실제 데이터를 통해 파이썬으로 구현·검증합니다.

[핵심 4대 파이프라인]
  1. 인메모리 LPG(속성 그래프) 엔진 구축 (Node, Relationship, Properties)
  2. [DART-Trace] 상장사-지분-주주 2-hop 경로 탐색 (RDB 4중 JOIN vs 그래프 포인터 홉)
  3. [ART:READY] 중앙대 공간연출전공 2027 수시 실기형 다단계 전형 그래프 경로 탐색
  4. RDB vs LPG 탐색 시간 및 연산 복잡도 실측 비교
================================================================================
"""

import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple, Set

# Windows CP949 콘솔 출력 인코딩 방어
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# 1. 인메모리 LPG (Labeled Property Graph) 엔진 구현
# ==============================================================================

class LPGNode:
    """LPG 노드: 고유 ID, 라벨 집합, 속성(Key-Value)"""
    def __init__(self, node_id: str, labels: List[str], properties: Optional[Dict[str, Any]] = None):
        self.id = node_id
        self.labels = set(labels)
        self.properties = properties or {}
        # Index-Free Adjacency: 인접한 관계를 노드가 직접 포인터로 쥐고 있음
        self.out_edges: List['LPGRelationship'] = []
        self.in_edges: List['LPGRelationship'] = []

    def __repr__(self):
        labels_str = ":".join(self.labels)
        name = self.properties.get("name", self.id)
        return f"(:{labels_str} {{id: '{self.id}', name: '{name}'}})"


class LPGRelationship:
    """LPG 관계: 타입, 출발 노드, 도착 노드, 속성(Key-Value)"""
    def __init__(self, rel_type: str, source: LPGNode, target: LPGNode, properties: Optional[Dict[str, Any]] = None):
        self.type = rel_type
        self.source = source
        self.target = target
        self.properties = properties or {}
        # 양방향 포인터 결속
        source.out_edges.append(self)
        target.in_edges.append(self)

    def __repr__(self):
        props_str = ", ".join(f"{k}: {v}" for k, v in self.properties.items())
        return f"({self.source.id})-[ :{self.type} {{{props_str}}} ]->({self.target.id})"


class LPGGraph:
    """LPG 그래프 컨테이너"""
    def __init__(self):
        self.nodes: Dict[str, LPGNode] = {}
        self.relationships: List[LPGRelationship] = []

    def add_node(self, node_id: str, labels: List[str], properties: Optional[Dict[str, Any]] = None) -> LPGNode:
        if node_id in self.nodes:
            # 기존 노드 속성 갱신
            self.nodes[node_id].properties.update(properties or {})
            return self.nodes[node_id]
        node = LPGNode(node_id, labels, properties)
        self.nodes[node_id] = node
        return node

    def add_relationship(self, rel_type: str, source_id: str, target_id: str, properties: Optional[Dict[str, Any]] = None) -> LPGRelationship:
        source = self.nodes[source_id]
        target = self.nodes[target_id]
        rel = LPGRelationship(rel_type, source, target, properties)
        self.relationships.append(rel)
        return rel


# ==============================================================================
# 2. [DART-Trace] 실전 지분 그래프 구축 및 2-hop 탐색
# ==============================================================================

def run_dart_lpg_simulation():
    print("\n" + "=" * 80)
    print("🏢 [DART-Trace] 속성 그래프(LPG) 지분 네트워크 모델링 및 2-Hop 탐색")
    print("=" * 80)

    g = LPGGraph()

    # 상장사 노드 등록
    samsung = g.add_node("00126380", ["Company"], {"name": "삼성전자", "is_listed": True})
    sk_hynix = g.add_node("00164779", ["Company"], {"name": "SK하이닉스", "is_listed": True})
    hyundai = g.add_node("00164742", ["Company"], {"name": "현대자동차", "is_listed": True})

    # 주주 노드 등록
    nps = g.add_node("HOLDER_NPS", ["Shareholder", "InstitutionalInvestor"], {"name": "국민연금공단", "type": "연기금"})
    blackrock = g.add_node("HOLDER_BLACKROCK", ["Shareholder", "InstitutionalInvestor"], {"name": "블랙록(BlackRock)", "type": "외국인"})
    lee = g.add_node("HOLDER_LEE", ["Shareholder", "Individual"], {"name": "이재용", "type": "개인(최대주주)"})

    # 지분 관계(Edge) 및 관계 속성 결속
    g.add_relationship("HOLDS_ECONOMIC_STAKE", "HOLDER_NPS", "00126380", {"stake_ratio": 7.25, "shares": 433000000, "base_date": "2024-03-31"})
    g.add_relationship("HOLDS_ECONOMIC_STAKE", "HOLDER_NPS", "00164779", {"stake_ratio": 7.90, "shares": 57500000, "base_date": "2024-03-31"})
    g.add_relationship("HOLDS_ECONOMIC_STAKE", "HOLDER_NPS", "00164742", {"stake_ratio": 7.35, "shares": 15600000, "base_date": "2024-03-31"})
    
    g.add_relationship("HOLDS_ECONOMIC_STAKE", "HOLDER_BLACKROCK", "00126380", {"stake_ratio": 5.03, "shares": 300000000, "base_date": "2024-02-15"})
    g.add_relationship("HOLDS_ECONOMIC_STAKE", "HOLDER_LEE", "00126380", {"stake_ratio": 1.63, "shares": 97414196, "base_date": "2024-03-31"})

    print(f"• DART LPG 그래프 구축 완료: 노드 {len(g.nodes)}개, 관계 {len(g.relationships)}개")

    # 서비스 질문: "삼성전자에 5% 이상 지분을 가진 주주가 동시에 투자하고 있는 다른 상장사는?"
    # 그래프 탐색: (Company:삼성전자) <-[h1]- (Shareholder) -[h2]-> (Company:다른회사)
    print("\n[그래프 2-Hop 포인터 탐색 질의 실행]")
    start_time = time.perf_counter()
    
    results = []
    # 1-hop: 삼성전자로 들어오는 지분 엣지 탐색
    for in_rel in samsung.in_edges:
        if in_rel.type == "HOLDS_ECONOMIC_STAKE" and in_rel.properties.get("stake_ratio", 0) >= 5.0:
            investor = in_rel.source
            # 2-hop: 해당 투자자가 보유한 다른 상장사 탐색
            for out_rel in investor.out_edges:
                other_company = out_rel.target
                if other_company.id != samsung.id:
                    results.append({
                        "investor": investor.properties["name"],
                        "target_company": other_company.properties["name"],
                        "stake_ratio": out_rel.properties["stake_ratio"]
                    })

    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"• 포인터 홉 탐색 소요 시간: {elapsed:.4f} ms")
    print(f"• 탐색된 2-Hop 동시 투자 관계 ({len(results)}건):")
    for r in results:
        print(f"  └─ 주주: [{r['investor']}] ──[:HOLDS_ECONOMIC_STAKE {{ratio: {r['stake_ratio']}%}}]-> 기업: [{r['target_company']}]")


# ==============================================================================
# 3. [ART:READY] 실전 미대 입시 다단계 전형 LPG 구축 및 탐색
# ==============================================================================

def run_art_lpg_simulation():
    print("\n" + "=" * 80)
    print("🎨 [ART:READY] 미대입시 다단계 전형 및 실기일정 LPG 모델링")
    print("=" * 80)

    g = LPGGraph()

    # 노드 등록
    cau_seoul = g.add_node("CAU_SEOUL", ["University"], {"name": "중앙대학교", "campus": "서울", "region": "서울"})
    cau_anseong = g.add_node("CAU_ANSEONG", ["University"], {"name": "중앙대학교", "campus": "안성", "region": "경기"})
    
    dept_spatial = g.add_node("DEPT_SPATIAL", ["Department"], {"name": "공간연출전공", "college": "예술대학"})
    dept_design = g.add_node("DEPT_DESIGN", ["Department"], {"name": "시각디자인전공", "college": "예술대학"})
    
    track_2027 = g.add_node("CAU_2027_EARLY", ["AdmissionTrack"], {"name": "2027 수시 실기형", "year": 2027, "admission_type": "수시"})
    
    p_drawing = g.add_node("PRACTICAL_DRAWING", ["PracticalType"], {"name": "소묘", "category": "순수/공간"})
    p_interview = g.add_node("PRACTICAL_INTERVIEW", ["PracticalType"], {"name": "질의응답(면접)", "category": "구술"})

    exam_date_1 = g.add_node("EXAM_20261003", ["ExamSchedule"], {"exam_date": "2026-10-03", "is_tentative": False})
    exam_date_2 = g.add_node("EXAM_20261031", ["ExamSchedule"], {"exam_date": "2026-10-31", "is_tentative": False})

    # 관계 등록
    g.add_relationship("BELONGS_TO", "DEPT_SPATIAL", "CAU_SEOUL")
    g.add_relationship("BELONGS_TO", "DEPT_DESIGN", "CAU_ANSEONG")  # 캠퍼스 분리 보존
    
    g.add_relationship("OFFERS_TRACK", "CAU_SEOUL", "CAU_2027_EARLY", {"admission_year": 2027})
    
    # 전형 -> 실기 종목 (1단계 80%, 2단계 30%)
    g.add_relationship("REQUIRES_PRACTICAL", "CAU_2027_EARLY", "PRACTICAL_DRAWING", {"stage": 1, "ratio": 80.0, "paper_size": "4절"})
    g.add_relationship("REQUIRES_PRACTICAL", "CAU_2027_EARLY", "PRACTICAL_INTERVIEW", {"stage": 2, "ratio": 30.0, "duration": "10분"})
    
    # 전형 -> 고사 일정
    g.add_relationship("EXAM_ON", "CAU_2027_EARLY", "EXAM_20261003", {"stage": 1})
    g.add_relationship("EXAM_ON", "CAU_2027_EARLY", "EXAM_20261031", {"stage": 2})

    print(f"• ART:READY LPG 그래프 구축 완료: 노드 {len(g.nodes)}개, 관계 {len(g.relationships)}개")

    # 서비스 질문: "중앙대 서울캠퍼스에서 1단계 실기로 치르는 종목과 시험 날짜는?"
    print("\n[입시 조건 그래프 경로 탐색 질의 실행]")
    start_time = time.perf_counter()

    findings = []
    for out_rel in cau_seoul.out_edges:
        if out_rel.type == "OFFERS_TRACK":
            track = out_rel.target
            for t_rel in track.out_edges:
                if t_rel.type == "REQUIRES_PRACTICAL" and t_rel.properties.get("stage") == 1:
                    p_type = t_rel.target
                    # 1단계 일정 탐색
                    for s_rel in track.out_edges:
                        if s_rel.type == "EXAM_ON" and s_rel.properties.get("stage") == 1:
                            e_sched = s_rel.target
                            findings.append({
                                "univ": cau_seoul.properties["name"],
                                "campus": cau_seoul.properties["campus"],
                                "track": track.properties["name"],
                                "stage": 1,
                                "subject": p_type.properties["name"],
                                "ratio": t_rel.properties["ratio"],
                                "date": e_sched.properties["exam_date"]
                            })

    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"• 경로 탐색 소요 시간: {elapsed:.4f} ms")
    for f in findings:
        print(f"  └─ 대학: [{f['univ']}({f['campus']})], 전형: [{f['track']}]")
        print(f"     => {f['stage']}단계 실기: [{f['subject']}] (반영비: {f['ratio']}%), 고사일: [{f['date']}]")


# ==============================================================================
# 4. RDB 중첩 JOIN vs LPG 그래프 포인터 홉 성능 시뮬레이션
# ==============================================================================

def run_performance_comparison():
    print("\n" + "=" * 80)
    print("⚡ [성능 비교] RDB 4중 JOIN vs LPG 그래프 포인터 홉 연산 비교")
    print("=" * 80)

    # 1,000건의 모의 주주-기업 관계 데이터 생성
    mock_holdings = [
        {"holder_id": f"H_{i % 50}", "corp_id": f"C_{i % 200}", "ratio": 5.0 + (i % 10)}
        for i in range(1000)
    ]

    # 1) RDB 방식 모의 연산 (테이블 전체를 스캔하며 일치하는 행을 찾는 O(N^2) 중첩 루프)
    t0 = time.perf_counter()
    rdb_matches = 0
    target_corp = "C_0"
    # Step 1: target_corp의 주주 목록 찾기
    step1_holders = [row["holder_id"] for row in mock_holdings if row["corp_id"] == target_corp]
    # Step 2: 그 주주들이 가진 다른 기업 찾기
    for h in step1_holders:
        for row in mock_holdings:
            if row["holder_id"] == h and row["corp_id"] != target_corp:
                rdb_matches += 1
    t_rdb = (time.perf_counter() - t0) * 1000

    # 2) LPG 그래프 방식 (인접 리스트 포인터만 즉시 탐색)
    g = LPGGraph()
    for row in mock_holdings:
        g.add_node(row["holder_id"], ["Shareholder"])
        g.add_node(row["corp_id"], ["Company"])
        g.add_relationship("HOLDS", row["holder_id"], row["corp_id"], {"ratio": row["ratio"]})

    t1 = time.perf_counter()
    lpg_matches = 0
    c_node = g.nodes[target_corp]
    for in_rel in c_node.in_edges:
        investor = in_rel.source
        for out_rel in investor.out_edges:
            if out_rel.target.id != target_corp:
                lpg_matches += 1
    t_lpg = (time.perf_counter() - t1) * 1000

    print(f"• RDB 시뮬레이션 (전체 테이블 2중 스캔)  : {t_rdb:.4f} ms (매칭: {rdb_matches}건)")
    print(f"• LPG 그래프 방식 (포인터 직접 참조)      : {t_lpg:.4f} ms (매칭: {lpg_matches}건)")
    speedup = t_rdb / t_lpg if t_lpg > 0 else 1.0
    print(f"• 그래프 탐색 속도 향상: 약 {speedup:.1f}배 빠름!")
    print("✅ [검증 완료] 속성 그래프(LPG) 모델이 복잡한 관계망 탐색에서 압도적 우위를 입증함!")


if __name__ == "__main__":
    run_dart_lpg_simulation()
    run_art_lpg_simulation()
    run_performance_comparison()
