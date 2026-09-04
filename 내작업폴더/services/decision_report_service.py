# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace] Decision Report Service (Antigravity Domain)
================================================================================
- 단일 기업 대상 [사실 / 관찰 지표 / 원문 근거 / 다음 확인 항목] 4단 의사결정 리포트 데이터 엔진
- 100% 읽기 전용 (driver.session 레벨 READ_ACCESS 강제)
- Cloud Aura 지식그래프의 DART_Company, DART_CapitalEvent, RawEvidenceCandidate 실시간 통합 조회
- 원천 사실(Facts)과 규칙 기반 관찰(Rule-based Observation)의 엄격한 분리
- 자본이벤트(공시 링크 연동)와 5% 후보(행 해시 결속 증거)의 정직한 증거 등급 구분
================================================================================
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, READ_ACCESS
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")


class DecisionReportService:
    """단일 기업 대상 4단 의사결정 리포트 데이터 서비스"""

    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        if self.driver:
            self.driver.close()

    def find_companies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """기업명, 종목코드, 법인코드 기반 검색"""
        q = query.strip()
        if not q:
            return []

        cypher = """
        MATCH (c:DART_Company)
        WHERE c.name CONTAINS $q OR c.stock_code = $q OR c.corp_code = $q
        RETURN c.corp_code AS corp_code, c.name AS corp_name, c.stock_code AS stock_code, c.is_listed AS is_listed
        ORDER BY size(c.name) ASC
        LIMIT $limit
        """
        with self.driver.session(default_access_mode=READ_ACCESS) as session:
            return session.run(cypher, q=q, limit=limit).data()

    def generate_company_decision_report(self, corp_code_or_name: str, max_events: int = 15) -> Dict[str, Any]:
        """
        단일 기업에 대한 4단 의사결정 리포트 데이터 생성
        - 1단: 사실 (Facts) - 재무/공시/CB/원문 추출 지분율 수치 및 정확한 관찰 기간
        - 2단: 관찰 지표 (Rule-based Observation) - 규칙 기반 관찰, 키워드 탐지, 모니터링 시나리오 (투자 조언 아님)
        - 3단: 원문 근거 (Evidence) - 증거 등급 분리 (공시 링크 연동 vs 2D 행 해시 결속)
        - 4단: 다음 확인 항목 (Next Actions) - 실사 모니터링 체크리스트
        """
        target = corp_code_or_name.strip()
        with self.driver.session(default_access_mode=READ_ACCESS) as session:
            # 1. 대상 기업 기본 정보 조회
            comp_query = """
            MATCH (c:DART_Company)
            WHERE c.corp_code = $target OR c.name = $target OR c.stock_code = $target
            RETURN c.corp_code AS corp_code, c.name AS corp_name, c.stock_code AS stock_code, c.is_listed AS is_listed
            LIMIT 1
            """
            comp_res = session.run(comp_query, target=target).single()
            if not comp_res:
                return {
                    "status": "NOT_FOUND",
                    "message": f"'{target}'에 해당하는 상장사 마스터 노드를 찾을 수 없습니다."
                }

            corp_code = comp_res["corp_code"]
            corp_name = comp_res["corp_name"]
            stock_code = comp_res["stock_code"]

            # 2. 최근 자본이벤트 (CB, BW, 유상증자 등) 조회 (최신순)
            cap_query = """
            MATCH (c:DART_Company {corp_code: $corp_code})-[:ANNOUNCED]->(e:DART_CapitalEvent)
            RETURN e.event_type AS event_type,
                   e.decided_on AS decided_on,
                   e.received_on AS received_on,
                   e.effective_on AS effective_on,
                   e.issue_method AS issue_method,
                   e.issue_amount AS issue_amount,
                   e.conversion_price AS conversion_price,
                   e.min_refixing_floor AS min_refixing_floor,
                   e.purpose AS purpose,
                   e.source_rcept_no AS rcept_no,
                   e.viewer_url AS viewer_url
            ORDER BY e.decided_on DESC
            LIMIT $max_events
            """
            capital_events = session.run(cap_query, corp_code=corp_code, max_events=max_events).data()

            # 3. 5% 대량보유 공시 원문 추출 후보 조회 (Aura 경고 방지: 실재하는 속성만 조회)
            stake_query = """
            MATCH (cand:RawEvidenceCandidate {target_corp_code: $corp_code})
            OPTIONAL MATCH (cand)-[:EVIDENCED_BY]->(frag:EvidenceFragment {role: 'ROW_DATA_EVIDENCE'})
            RETURN 
                cand.candidate_id AS candidate_id,
                cand.holder_name AS holder_name,
                cand.stake_ratio AS stake_ratio,
                cand.shares_count AS shares_count,
                cand.reporting_obligation_date AS reporting_obligation_date,
                cand.rcept_no AS rcept_no,
                cand.layout_status AS layout_status,
                frag.xpath AS row_raw_parser_xpath,
                frag.raw_inner_hash AS row_inner_hash,
                frag.extracted_value AS extracted_value
            ORDER BY cand.reporting_obligation_date DESC, cand.stake_ratio DESC
            LIMIT 20
            """
            stake_rows = session.run(stake_query, corp_code=corp_code).data()

        # =========================================================================
        # 1단: 사실 (Facts) - 정확한 관찰 기간 계산 (가짜 '최근 2년' 주장 제거)
        # =========================================================================
        event_dates = [e["decided_on"] for e in capital_events if e.get("decided_on")]
        date_coverage = {
            "start_date": min(event_dates) if event_dates else None,
            "end_date": max(event_dates) if event_dates else None,
            "observed_events_count": len(capital_events),
            "description": f"최근 수집된 공시 {len(capital_events)}건 (기간: {min(event_dates)} ~ {max(event_dates)})" if event_dates else "수집된 자본이벤트 공시 없음"
        }

        # 원문 추출 후보 가공 (미검증 후보 상태 명시)
        raw_candidates = []
        for r in stake_rows:
            if r.get("holder_name"):
                raw_candidates.append({
                    "candidate_id": r["candidate_id"],
                    "holder_name": r["holder_name"],
                    "stake_ratio": r["stake_ratio"],
                    "shares_count": r["shares_count"],
                    "reporting_obligation_date": r["reporting_obligation_date"],
                    "rcept_no": r["rcept_no"],
                    "row_raw_parser_xpath": r["row_raw_parser_xpath"],
                    "row_inner_hash": r["row_inner_hash"],
                    "extracted_value": r["extracted_value"],
                    "status": "UNVERIFIED_EXTRACTED_CANDIDATE",
                    "status_label": "미검증 원문 추출 후보",
                    "verification_note": "DART 5% 공시 원문 테이블에서 추출된 1차 후보이며, 엔티티 해소 승격 전 단계입니다."
                })

        facts = {
            "company_profile": {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code,
                "is_listed": comp_res["is_listed"]
            },
            "date_coverage": date_coverage,
            "capital_events_summary": {
                "total_events_count": len(capital_events),
                "events_detail": capital_events
            },
            "major_holdings_summary": {
                "promoted_count": 0,
                "promoted_stakes": [],  # Phase 2 승격 전이므로 0건으로 정직하게 고정
                "raw_candidate_count": len(raw_candidates),
                "raw_candidates": raw_candidates[:10]
            }
        }

        # =========================================================================
        # 2단: 관찰 지표 (Rule-based Observation) - 단정적 금융 판단 배제 및 근거 명시
        # =========================================================================
        cb_bw_events = [e for e in capital_events if any(k in str(e.get("event_type", "")) for k in ["전환사채", "CB", "신주인수권", "BW"])]
        cb_bw_count = len(cb_bw_events)
        capital_increase_events = [e for e in capital_events if "유상증자" in str(e.get("event_type", ""))]
        increase_count = len(capital_increase_events)

        relevant_events = cb_bw_events + capital_increase_events
        basis_rcept_nos = list(dict.fromkeys([e["rcept_no"] for e in relevant_events if e.get("rcept_no")]))
        basis_event_dates = sorted(list(dict.fromkeys([e.get("decided_on") for e in relevant_events if e.get("decided_on")])))

        # 목적 문구 키워드 탐지
        purposes = [str(e.get("purpose", "")) for e in capital_events if e.get("purpose")]
        has_facility = any(any(k in p for k in ["시설", "설비", "연구", "R&D", "타법인"]) for p in purposes)
        has_debt = any(any(k in p for k in ["채무상환", "운영자금"]) for p in purposes)

        if has_facility and not has_debt:
            purpose_eval = "시설투자/R&D/타법인증권취득 키워드 중심 탐지"
        elif has_facility and has_debt:
            purpose_eval = "운영·채무상환 및 시설투자 병행 키워드 탐지"
        elif has_debt:
            purpose_eval = "운영자금/채무상환 키워드 중심 탐지"
        else:
            purpose_eval = "공시 서식상 특이 목적 키워드 미탐지"

        # 관찰 등급 (규칙 기반 탐지)
        if cb_bw_count >= 2 or (cb_bw_count + increase_count) >= 3:
            obs_level = "주의 관찰 요망 (CB/BW 또는 증자 2건 이상 누적 탐지)"
            obs_code = "OBS_WATCH_HIGH"
        elif (cb_bw_count + increase_count) >= 1:
            obs_level = "일반 관찰 (자본이벤트 발생 이력 탐지)"
            obs_code = "OBS_WATCH_MODERATE"
        else:
            obs_level = "특이 관찰 요망 사항 미발견"
            obs_code = "OBS_NORMAL"

        interpretations = {
            "rule_version": "RULE_HEURISTIC_v1.0",
            "observation_level": obs_level,
            "observation_code": obs_code,
            "basis_rcept_nos": basis_rcept_nos,
            "basis_event_dates": basis_event_dates,
            "cb_bw_overhang_observation": (
                f"수집된 공시 {len(capital_events)}건 중 CB/BW 공시 {cb_bw_count}건 감지. 전환청구 도래 시 잠재 주식수 증가에 따른 오버행 가능성 모니터링 필요."
                if cb_bw_count > 0 else
                f"수집된 공시 {len(capital_events)}건 기준 전환사채(CB) 및 BW 발행 이력 미발견."
            ),
            "financing_purpose_observation": purpose_eval,
            "tracking_scenarios": {
                "scenario_type": "추적 관찰용 시나리오 (참고용 - 가격 예측 아님)",
                "bull_case": "조달 자금의 시설투자 집행 및 신사업 가시화로 주당순이익(EPS) 희석 효과를 상쇄하는 성장 시나리오 (가정)",
                "base_case": "기존 주주 지분율 일부 희석이 발생하나, 만기 전 사채 취득 및 차환을 통해 재무 안정성을 유지하는 시나리오 (가정)",
                "bear_case": "전환가액 하향(리픽싱) 누적 및 주가 하락 시 잠재 전환물량 출회로 주가 하방 압력이 가중되는 시나리오 (가정)"
            },
            "disclaimer": "※ 본 관찰 지표 및 시나리오는 DART 공시 텍스트 규칙 기반 휴리스틱 탐지 결과이며, 투자 자문이나 주가 예측이 아닙니다."
        }

        # =========================================================================
        # 3단: 원문 근거 (Evidence) - 정직한 증거 등급 분리
        # =========================================================================
        evidence_list = []
        # 자본이벤트: 공시 접수번호 기준 원문 링크 연동 (행 단위 2D 해시 미적재 명시)
        for e in capital_events[:5]:
            rcp = e.get("rcept_no")
            evidence_list.append({
                "item_type": "CAPITAL_EVENT",
                "title": f"{e.get('event_type')} 결정 ({e.get('decided_on')})",
                "rcept_no": rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None,
                "evidence_level": "FILING_LINK_ONLY",
                "xpath": None,
                "inner_hash": None,
                "evidence_note": "공시 접수번호 기준 DART 원문 바로가기 연동 (행 단위 2D 해시 미적재)"
            })

        # 5% 보고 후보: 파서 추출 좌표 및 원문 행 SHA-256 결속
        for s in raw_candidates[:5]:
            rcp = s.get("rcept_no")
            evidence_list.append({
                "item_type": "MAJOR_STAKE_CANDIDATE",
                "title": f"[미검증 원문 추출 후보] {s.get('holder_name')} ({s.get('stake_ratio')}%, {s.get('reporting_obligation_date')})",
                "rcept_no": rcp,
                "dart_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else None,
                "evidence_level": "ROW_HASH_BOUND",
                "xpath": s.get("row_raw_parser_xpath"),
                "inner_hash": s.get("row_inner_hash"),
                "evidence_note": "파서 추출 좌표 + 원문 행 SHA-256 결속"
            })

        # =========================================================================
        # 4단: 다음 확인 항목 (Next Actions) - 실사 모니터링 체크리스트
        # =========================================================================
        next_actions = [
            "CB/BW 사채의 전환청구 시작일 및 전환가액 조정(리픽싱) 공시 주기적 추적",
            "유상증자 청약일 및 주금 납입일 준수 여부(납입 연기 정정공시 여부 확인)",
            "대주주 및 특수관계인의 추가 장내 매도/담보대출 설정 공시 모니터링",
            "다음 분기 정기보고서(사업보고서/분기보고서) 자본금 변동사항 표 대조"
        ]

        return {
            "status": "SUCCESS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_company": {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code
            },
            "tier1_facts": facts,
            "tier2_interpretations": interpretations,
            "tier3_evidence": evidence_list,
            "tier4_next_actions": next_actions
        }


if __name__ == "__main__":
    service = DecisionReportService()
    try:
        sample = service.generate_company_decision_report("HLB")
        print("Report Generated Successfully!")
        print("Date Coverage:", sample["tier1_facts"]["date_coverage"])
        print("Observation:", sample["tier2_interpretations"]["observation_level"])
        print("Evidence Count:", len(sample["tier3_evidence"]))
        for ev in sample["tier3_evidence"][:3]:
            print(f" - [{ev['evidence_level']}] {ev['title']} (XPath: {ev['xpath']}, Hash: {ev['inner_hash']})")
    finally:
        service.close()
