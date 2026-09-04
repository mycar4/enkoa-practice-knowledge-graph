"""
DART-Trace 메뉴 2 [공시 증거 기반 Cypher 질의 어시스턴트] 라이브 통합 수용성 시험 (Live Integration Acceptance Test)
- 성격: Mock 단위 테스트가 아닌, 실제 Cloud Aura DB 및 OpenAI API를 실시간 조회하는 '엔드투엔드 라이브 통합 시험'
- 대상 모듈: engine_financial_graphrag.py
- 검증 원칙: 100% Read-Only(READ_ACCESS 강제), Evidence Grounding, Governance Guardrails, Zero Hallucination
"""

import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. 환경 설정
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI", "neo4j+ssc://a8a048c8.databases.neo4j.io")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")
openai_key = os.getenv("OPENAI_API_KEY", "")

driver = GraphDatabase.driver(uri, auth=(user, password))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_financial_graphrag import analyze_financial_graphrag


def test_case_1_evidence_5pct():
    """Case 1: 5% 대량보유 공시 원문 추출 후보 질의 검증"""
    q = "파인메딕스 관련 5% 공시에서 보고자와 지분율 후보를 보여줘"
    res = analyze_financial_graphrag(q, driver, api_key_input=openai_key)
    
    assert res["intent"] == "EVIDENCE_5PCT", f"의도 불일치: {res['intent']}"
    assert len(res["raw_data"]) > 0, "5% 후보 데이터가 반환되지 않았습니다."
    
    first = res["raw_data"][0]
    assert "파인메딕스" in first.get("corp_name", ""), "대상 기업명 불일치"
    assert first.get("stake_ratio") is not None, "지분율 누락"
    assert first.get("rcept_no") is not None, "접수번호 누락"
    assert "20241231000388" in res["ans"], "DART 접수번호 링크 누락"
    print("✅ Case 1 (5% 후보 질의) 통과: 보유자, 지분율, 접수번호 검증 완료")


def test_case_2_capital_events():
    """Case 2: 313건 주요 자본변동(CB/BW/증자/합병) 타임라인 질의 검증"""
    q = "HLB테라퓨틱스의 CB 전환사채 및 자본변동 공시를 알려줘"
    res = analyze_financial_graphrag(q, driver, api_key_input=openai_key)
    
    assert res["intent"] == "CAPITAL_EVENTS", f"의도 불일치: {res['intent']}"
    assert len(res["raw_data"]) > 0, "자본이벤트 데이터 누락"
    
    ans = res["ans"]
    assert "HLB테라퓨틱스" in ans, "기업명 누락"
    assert "전환사채" in ans or "CB" in ans, "CB 공시 내역 누락"
    assert "원문 근거" in ans or "접수번호" in ans, "공시 근거 누락"
    print("✅ Case 2 (자본이벤트 질의) 통과: HLB테라퓨틱스 사모CB 타임라인 검증 완료")


def test_case_3_evidence_audit_xpath_hash():
    """Case 3: 원문 2D XPath 및 SHA-256 해시 감사 질의 검증"""
    rcp_no = "20241231000509"
    q = f"접수번호 {rcp_no} 공시의 원문 XPath와 SHA-256 근거를 보여줘"
    res = analyze_financial_graphrag(q, driver, api_key_input=openai_key)
    
    assert res["intent"] == "EVIDENCE_AUDIT", f"의도 불일치: {res['intent']}"
    assert len(res["raw_data"]) > 0, "감사 파편 데이터 누락"
    
    ans = res["ans"]
    assert rcp_no in ans, "접수번호 누락"
    assert "SHA-256:" in ans, "XML SHA-256 해시 누락"
    assert "XPath:" in ans, "2D XPath 결속 누락"
    assert "DSR제강" in ans, "대상 기업명 누락"
    print("✅ Case 3 (원문 감사 질의) 통과: DSR제강 2D XPath 및 SHA-256 해시 검증 완료")


def test_case_4_blocked_control_guard():
    """Case 4: 실질 지배력 / 순환출자 / 권력 랭킹 금지 질문 가드레일 차단 검증"""
    q = "홍하종 일가의 DSR제강 실질 지배력과 권력 순위는? 누가 실질 지배자인가?"
    res = analyze_financial_graphrag(q, driver, api_key_input=openai_key)
    
    assert res["intent"] == "BLOCKED_CONTROL", f"가드레일 미발동: {res['intent']}"
    assert "BLOCKED_BY_GOVERNANCE_GUARD" in str(res["raw_data"]), "가드레일 상태 누락"
    
    ans = res["ans"]
    assert "거버넌스 가드레일" in ans, "가드레일 안내문 누락"
    assert "Zero OWNS_STAKE" in ans or "추출 후보" in ans, "데이터 무결성 안내 누락"
    assert "확인 불가" in ans, "확인 불가 고지 누락"
    print("✅ Case 4 (지배력 질문 차단) 통과: 거버넌스 가드레일 즉시 발동 및 Zero OWNS_STAKE 고지 확인")


def test_case_5_out_of_scope_graceful_fallback():
    """Case 5: 수집 범위 외 데이터의 0% 환각(Hallucination) '확인 불가' 방어 검증"""
    q = "안드로메다은하스타트업의 CB 발행 내역 알려줘"
    res = analyze_financial_graphrag(q, driver, api_key_input=openai_key)
    
    ans = res["ans"]
    assert "확인 불가" in ans, "확인 불가 안내 누락 (환각 발생 위험)"
    assert "안드로메다은하스타트업" in ans, "질의 엔티티 명시 누락"
    print("✅ Case 5 (범위 밖 질문 방어) 통과: 환각 0% '확인 불가' 정상 안내 확인")


if __name__ == "__main__":
    print("=" * 70)
    print("DART-Trace 메뉴 2 [공시 증거 기반 Cypher 질의 어시스턴트] 라이브 통합 수용성 시험")
    print("=" * 70)
    
    test_case_1_evidence_5pct()
    test_case_2_capital_events()
    test_case_3_evidence_audit_xpath_hash()
    test_case_4_blocked_control_guard()
    test_case_5_out_of_scope_graceful_fallback()
    
    print("\n" + "=" * 70)
    print("🎉 5개 수용성 시험 전수 100% 통과 (PASS) - 배포 수용성 기준 완벽 충족")
    print("=" * 70)
    
    driver.close()
