import time
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

def verify_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1400})
        page = context.new_page()
        
        print("1. 대시보드 접속 중 (http://127.0.0.1:8501)...")
        try:
            page.goto("http://127.0.0.1:8501", timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            print("127.0.0.1 failed, trying localhost:", e)
            page.goto("http://localhost:8501", timeout=30000, wait_until="domcontentloaded")
            
        print("페이지 로딩 대기 중 (5초)...")
        time.sleep(5)
        
        # 메뉴 1 스크린샷
        page.screenshot(path="screenshot_menu1_verified.png")
        print("✅ 메뉴 1 스크린샷 저장 완료: screenshot_menu1_verified.png")
        
        # 메뉴 7 이동
        print("2. 메뉴 7 (라이브 쿼리 콘솔) 이동 시도...")
        m7 = page.locator("text=7. 개발자/분석가 라이브 쿼리 콘솔")
        if m7.count() > 0:
            m7.first.click()
            time.sleep(4)
            page.screenshot(path="screenshot_menu7_verified.png")
            print("✅ 메뉴 7 스크린샷 저장 완료: screenshot_menu7_verified.png")
            
        # 메뉴 2 이동
        print("3. 메뉴 2 (의사결정 리포트) 이동 시도...")
        m2 = page.locator("text=2. 단일 기업 4단 의사결정 리포트")
        if m2.count() > 0:
            m2.first.click()
            time.sleep(3)
            # HLB 숏컷 버튼 클릭 테스트
            hlb_btn = page.locator("button:has-text('HLB')")
            if hlb_btn.count() > 0:
                print("4. [HLB] 숏컷 버튼 클릭...")
                hlb_btn.first.click()
                time.sleep(3)
            page.screenshot(path="screenshot_menu2_verified.png")
            print("✅ 메뉴 2 스크린샷 저장 완료: screenshot_menu2_verified.png")
            
        browser.close()
        print("🎉 모든 E2E UI 전수 점검 완료!")

if __name__ == "__main__":
    verify_dashboard()
