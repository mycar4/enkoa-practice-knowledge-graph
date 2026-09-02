# -*- coding: utf-8 -*-
"""
Step 4 GraphRAG AI 챗봇 공식 인수검수 스크립트
- app_dart_trace_dashboard.py의 generate_graphrag_response 함수를 직접 호출
- 4대 벤치마크에 대한 정밀 검증 (두 엔티티 관계 이력만 반환, 팩트 100% 일치, DART 원문 URL 포함, 미등록 안전응답)
- 불일치 시 exit(1) 및 AssertionError 발생
"""
import os
import sys
import importlib.util

sys.stdout.reconfigure(encoding='utf-8')

# app_dart_trace_dashboard 모듈 동적 로드
spec = importlib.util.spec_from_file_location("app_dashboard", "내작업폴더/app_dart_trace_dashboard.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

generate_graphrag_response = app_module.generate_graphrag_response

def test_benchmark_1():
    print("\n" + "=" * 60)
    print("🧪 [검증 1] 국민연금공단 ↔ ESR켄달스퀘어리츠 최신 지분율 및 접수번호·DART URL")
    print("=" * 60)
    q = "국민연금공단의 ESR켄달스퀘어리츠 최신 지분율·접수번호는?"
    res = generate_graphrag_response(q)
    
    ans = res["ans"]
    raw_data = res["raw_data"].get("조회_데이터", [])
    
    print(f"• 질문: {q}")
    print(f"• 챗봇 응답:\n{ans}")
    print(f"• 반환된 관계 레코드 수: {len(raw_data)}건")
    
    # 1. 무관한 기업(삼성, 카카오, 포스코 등) 혼입 여부 검증
    for r in raw_data:
        assert r['owner'] in ['국민연금공단', 'ESR켄달스퀘어리츠'], f"무관한 소유자 혼입: {r['owner']}"
        assert r['target'] in ['국민연금공단', 'ESR켄달스퀘어리츠'], f"무관한 대상기업 혼입: {r['target']}"
        
    # 2. 최신 유효 사실 (Row 0) 수치 및 메타데이터 정밀 검증
    assert len(raw_data) >= 1, "관계 데이터가 비어있음"
    top_row = raw_data[0]
    assert top_row['owner'] == '국민연금공단', f"기대 소유자 불일치: {top_row['owner']}"
    assert top_row['target'] == 'ESR켄달스퀘어리츠', f"기대 대상기업 불일치: {top_row['target']}"
    assert top_row['stake'] == 4.8, f"지분율 불일치 (기대: 4.8, 실제: {top_row['stake']})"
    assert top_row['rcept_no'] == '20260701000364', f"접수번호 불일치 (기대: 20260701000364, 실제: {top_row['rcept_no']})"
    assert top_row['ver_st'] == 'VERIFIED', f"검증상태 불일치: {top_row['ver_st']}"
    assert top_row['is_curr'] is True, f"최신성 불일치: {top_row['is_curr']}"
    
    # 3. DART 원문 클릭 링크 존재 검증
    expected_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={top_row['rcept_no']}"
    assert expected_url in ans, f"DART 원문 링크 누락: {expected_url}"
    
    print(f"✅ [검증 1 PASS] 4.8% / 20260701000364 / VERIFIED / 최신 유효 사실 및 DART URL({expected_url}) 확인 완료!")

def test_benchmark_2():
    print("\n" + "=" * 60)
    print("🧪 [검증 2] HD한국조선해양 ↔ HD현대중공업 최신 출자 지분율·장부가액·기준일·접수번호·DART URL")
    print("=" * 60)
    q = "HD한국조선해양의 HD현대중공업 최신 출자 지분율·장부가액·기준일·접수번호는?"
    res = generate_graphrag_response(q)
    
    ans = res["ans"]
    raw_data = res["raw_data"].get("조회_데이터", [])
    
    print(f"• 질문: {q}")
    print(f"• 챗봇 응답:\n{ans}")
    print(f"• 반환된 관계 레코드 수: {len(raw_data)}건")
    
    # 1. 무관한 기업 혼입 여부 검증
    for r in raw_data:
        assert r['owner'] in ['HD한국조선해양', 'HD현대중공업'], f"무관한 소유자 혼입: {r['owner']}"
        assert r['target'] in ['HD한국조선해양', 'HD현대중공업'], f"무관한 대상기업 혼입: {r['target']}"
        
    # 2. 최신 유효 사실 (INVESTED_IN 출자 관계) 검증
    inv_rows = [r for r in raw_data if r['rel'] == 'INVESTED_IN']
    assert len(inv_rows) >= 1, "INVESTED_IN 출자 관계 누락"
    top_inv = inv_rows[0]
    assert top_inv['stake'] == 75.02, f"지분율 불일치: {top_inv['stake']}"
    assert top_inv['book_value'] == 5276008000000, f"장부가액 불일치: {top_inv['book_value']}"
    assert str(top_inv['as_of_date']) == '2024-12-31', f"기준일 불일치: {top_inv['as_of_date']}"
    assert top_inv['rcept_no'] == '20250318001131', f"접수번호 불일치: {top_inv['rcept_no']}"
    
    # 3. DART 원문 클릭 링크 존재 검증
    expected_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={top_inv['rcept_no']}"
    assert expected_url in ans, f"DART 원문 링크 누락: {expected_url}"
    
    print(f"✅ [검증 2 PASS] 75.02% / 5,276,008,000,000원 / 2024-12-31 / 20250318001131 및 DART URL({expected_url}) 확인 완료!")

def test_benchmark_3():
    print("\n" + "=" * 60)
    print("🧪 [검증 3] 국민연금공단 ↔ HDC 최신 지분율과 공시 접수일·DART URL")
    print("=" * 60)
    q = "국민연금공단의 HDC 최신 지분율과 공시 접수일은?"
    res = generate_graphrag_response(q)
    
    ans = res["ans"]
    raw_data = res["raw_data"].get("조회_데이터", [])
    
    print(f"• 질문: {q}")
    print(f"• 챗봇 응답:\n{ans}")
    print(f"• 반환된 관계 레코드 수: {len(raw_data)}건")
    
    # 1. 무관한 기업 혼입 여부 검증
    for r in raw_data:
        assert r['owner'] in ['국민연금공단', 'HDC'], f"무관한 소유자 혼입: {r['owner']}"
        assert r['target'] in ['국민연금공단', 'HDC'], f"무관한 대상기업 혼입: {r['target']}"
        
    # 2. 최신 유효 사실 검증
    assert len(raw_data) >= 1, "관계 데이터가 비어있음"
    top_row = raw_data[0]
    assert top_row['owner'] == '국민연금공단', f"소유자 불일치: {top_row['owner']}"
    assert top_row['target'] == 'HDC', f"대상기업 불일치: {top_row['target']}"
    assert top_row['stake'] == 5.8, f"지분율 불일치: {top_row['stake']}"
    assert str(top_row['reported_on']) == '2026-08-26', f"공시접수일 불일치: {top_row['reported_on']}"
    assert top_row['rcept_no'] == '20260826000408', f"접수번호 불일치: {top_row['rcept_no']}"
    
    # 3. DART 원문 클릭 링크 존재 검증
    expected_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={top_row['rcept_no']}"
    assert expected_url in ans, f"DART 원문 링크 누락: {expected_url}"
    
    print(f"✅ [검증 3 PASS] 5.8% / 2026-08-26 / 20260826000408 및 DART URL({expected_url}) 확인 완료!")

def test_benchmark_4():
    print("\n" + "=" * 60)
    print("🧪 [검증 4] NAVER의 최대주주 (미등록 엔티티 환각 차단 안전 응답)")
    print("=" * 60)
    q = "NAVER의 최대주주는?"
    res = generate_graphrag_response(q)
    
    ans = res["ans"]
    print(f"• 질문: {q}")
    print(f"• 챗봇 응답:\n{ans}")
    
    assert "현재 적재된 공시 데이터에서 확인 불가" in ans, f"안전 응답 문구 누락: {ans}"
    print("✅ [검증 4 PASS] 미등록 엔티티에 대해 '현재 적재된 공시 데이터에서 확인 불가' 안전 응답 100% 확인!")

if __name__ == "__main__":
    try:
        test_benchmark_1()
        test_benchmark_2()
        test_benchmark_3()
        test_benchmark_4()
        print("\n" + "=" * 60)
        print("🏆 [Step 4 GraphRAG AI 챗봇 4대 실측 벤치마크 100% 공식 합격 (ALL PASS)]")
        print("=" * 60)
    except AssertionError as err:
        print(f"\n❌ [검증 실패 AssertionError]: {err}")
        sys.exit(1)
    except Exception as ex:
        print(f"\n❌ [실행 오류 Exception]: {ex}")
        sys.exit(1)
