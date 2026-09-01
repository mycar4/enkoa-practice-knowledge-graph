# -*- coding: utf-8 -*-
"""
v0.3 GraphRAG 자본 이벤트 AI 챗봇 팩트 단정(Assert) 검증 스크립트
- 3S: 전환사채 50억 발행액, 1,945원 전환가액, 접수번호 20241217000407, DART 공식 URL 검증
- APS: 전환사채 100억 발행액, 4,151원 전환가액, 접수번호 20260805000477, DART 공식 URL 검증
"""
import sys
sys.path.insert(0, '내작업폴더')
from app_dart_trace_dashboard import generate_graphrag_response

sys.stdout.reconfigure(encoding='utf-8')

print("============================================================")
print("🧪 [v0.3 검증 1] 3S의 CB(전환사채) 발행 공시 질문")
print("============================================================")
res1 = generate_graphrag_response("3S의 CB 발행 내역과 전환가액은?")
ans1 = res1["ans"]
print(ans1)
assert "3S 전환사채발행결정" in ans1 or "전환사채" in ans1, "3S CB 응답 누락"
assert "5,000,000,000원" in ans1, "3S 발행금액(50억원) 누락"
assert "1,945원" in ans1, "3S 전환가액(1,945원) 누락"
assert "20241217000407" in ans1, "3S 접수번호(20241217000407) 누락"
assert "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20241217000407" in ans1, "3S DART 공식 URL 누락"
print("✅ [검증 1 PASS] 3S 전환사채 50억 / 1,945원 / 20241217000407 / DART URL 전수 일치 확인!")

print("\n============================================================")
print("🧪 [v0.3 검증 2] APS의 전환사채 질문")
print("============================================================")
res2 = generate_graphrag_response("APS의 전환사채 발행금액과 공시 접수번호는?")
ans2 = res2["ans"]
print(ans2)
assert "APS" in ans2 and "전환사채" in ans2, "APS CB 응답 누락"
assert "10,000,000,000원" in ans2, "APS 발행금액(100억원) 누락"
assert "4,151원" in ans2, "APS 전환가액(4,151원) 누락"
assert "20260805000477" in ans2, "APS 접수번호(20260805000477) 누락"
assert "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260805000477" in ans2, "APS DART 공식 URL 누락"
print("✅ [검증 2 PASS] APS 전환사채 100억 / 4,151원 / 20260805000477 / DART URL 전수 일치 확인!")

print("\n============================================================")
print("🏆 [v0.3 GraphRAG 자본 이벤트 챗봇 팩트 단정 100% ALL PASS!]")
print("============================================================")
