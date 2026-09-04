#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 [Playwright E2E] DART-Trace 대시보드 브라우저 자동화 테스트 스크립트 (실제 메뉴 매핑)
================================================================================
실행 전 필수 준비:
1) pip install playwright
2) playwright install chromium
3) Streamlit 대시보드 실행 (streamlit run app_dart_trace_dashboard.py)
================================================================================
"""

import time
import sys

# Windows stdout UTF-8 보장
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright


def run_e2e_test():
    print("🎭 Playwright 브라우저 자동화 시작...")
    with sync_playwright() as p:
        # headless=False로 설정하면 브라우저가 실제로 뜨면서 클릭하는 모습이 눈앞에 보입니다!
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1800})

        print("1. Streamlit 대시보드 접속 (http://localhost:8501)...")
        page.goto("http://localhost:8501", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("2. 사이드바에서 '⚡ 4. DS005 기업 주요 자본 이벤트' 선택...")
        # 사이드바 내의 4번 메뉴 라디오 옵션 클릭
        sidebar = page.locator("[data-testid='stSidebar']")
        sidebar.locator("p:has-text('4. DS005')").click()
        time.sleep(3)
        page.screenshot(path="debug_after_sidebar_click.png")

        print("3. 상단 5번째 탭 [GraphRAG AI 분석기] 클릭...")
        page.locator("text=512차원").first.click()
        time.sleep(2)

        print("4. 질문 입력창에 직접 질의 입력...")
        query_input = page.locator("input[aria-label*='자본이벤트 관련 질문']")
        query_input.fill("HLB의 대규모 전환사채(CB) 발행 목적과 잠재적 희석 리스크는?")
        time.sleep(1)

        print("5. '🚀 GraphRAG AI 분석 리포트 생성' 버튼 클릭...")
        page.locator("button:has-text('GraphRAG AI 분석 리포트 생성')").click()

        print("6. AI 4단 의사결정 리포트 생성 대기 중 (고유 헤더: '4단 의사결정 AI 리포트')...")
        # 하단 면책 조항 등의 일반 단어가 아닌, 리포트 전용 고유 헤더를 대기
        page.wait_for_selector("text=4단 의사결정 AI 리포트", timeout=60000)
        page.wait_for_selector("text=하이브리드 리랭킹 검색 결과", timeout=60000)
        time.sleep(3)  # 카드 렌더링 완료 안정화 대기

        print("7. 4단 리포트가 렌더링된 전체 화면 캡처 저장...")
        page.screenshot(path="playwright_graphrag_result.png", full_page=True)
        print("🎉 [테스트 성공] 4단 리포트가 포함된 'playwright_graphrag_result.png' 스크린샷 저장 완료!")

        time.sleep(3)
        browser.close()


if __name__ == "__main__":
    run_e2e_test()
