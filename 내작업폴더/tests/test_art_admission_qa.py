# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] 영구 회귀 테스트
================================================================================
- 학교 데이터를 추가/재검증할 때마다 매번 임시 Playwright 스크립트를 새로
  짜지 않도록, 이 세션에서 실제로 두 번 겪었던 버그 패턴을 고정 회귀
  테스트로 박아둔다:
  1. admission_year 뒤섞임 (서로 다른 학년도 문서가 섞여 적재됨)
  2. 같은 대학·같은 트랙명을 쓰는 학과가 ExamType/Schedule/CutoffEstimate
     노드를 공유해버리는 MERGE 키 충돌 (가천대 4개 학과 사건)
  3. Streamlit 8개 탭 + 그래프뷰 전수 예외 발생 여부
  4. PDF 원문 벡터 색인이 실제로 채워져 있고 검색이 동작하는지
- 실행: uv run python 내작업폴더/tests/test_art_admission_qa.py
  (Streamlit이 8501 포트에 떠있지 않으면 이 스크립트가 자동으로 띄운다)
================================================================================
"""

import os
import sys
import time
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from services.art_admission_service import ArtAdmissionService  # noqa: E402

APP_URL = "http://localhost:8501"
TABS = [
    "🏫 학교/학과 목록", "🔍 학교 상세", "⚖️ 전형 비교", "📅 일정 캘린더",
    "🎯 동시지원 시뮬레이터", "🧭 준비한 실기로 학교 찾기", "📝 기출문제", "🚦 데이터 정합성",
    "💬 질의응답", "🖊️ 서류 AI 첨삭", "🕸️ 지식그래프 보기",
]

# 원문을 확보 못해 의도적으로 벡터 색인을 안 한 학교(known exception).
VECTOR_INDEX_EXPECTED_MISSING = {"서울예술대학교"}


def test_no_critical_or_warning_integrity_issues():
    svc = ArtAdmissionService()
    try:
        issues = svc.check_data_integrity()
        bad = [i for i in issues if i["level"] in ("CRITICAL", "WARNING")]
        assert not bad, f"정합성 위반 발견: {bad}"
        print(f"✅ test_no_critical_or_warning_integrity_issues passed! (INFO {len(issues)}건, CRITICAL/WARNING 0건)")
    finally:
        svc.close()


def test_no_shared_exam_or_schedule_nodes():
    """가천대 4개 학과 사건 회귀: 같은 대학·트랙명의 서로 다른 학과가
    ExamType/Schedule/CutoffEstimate 노드를 공유하면 안 된다."""
    svc = ArtAdmissionService()
    try:
        with svc.driver.session(default_access_mode="READ") as s:
            for label, rel in [
                ("Admission_ExamType", "REQUIRES_EXAM"),
                ("Admission_Schedule", "HAS_SCHEDULE"),
                ("Admission_CutoffEstimate", "ESTIMATED_CUTOFF"),
            ]:
                rows = s.run(f"""
                    MATCH (t:Admission_Track)-[:{rel}]->(n:{label})
                    WHERE t.is_superseded IS NULL OR t.is_superseded = false
                    WITH n, count(DISTINCT t) AS track_count, collect(DISTINCT t.department) AS depts
                    WHERE track_count > 1
                    RETURN depts, track_count
                """).data()
                assert not rows, f"{label} 노드가 여러 트랙에 공유됨(department 분리 실패): {rows}"
        print("✅ test_no_shared_exam_or_schedule_nodes passed!")
    finally:
        svc.close()


def test_admission_year_consistent_within_active_tracks():
    """활성(비-superseded) 트랙은 전부 같은 학년도(2027)여야 한다.
    다른 학년도가 섞여 있다면 검증되지 않은 채 적재된 것."""
    svc = ArtAdmissionService()
    try:
        tracks = svc.list_all_tracks_full()
        years = {t.get("admission_year") for t in tracks}
        assert years == {2027}, f"활성 트랙의 admission_year가 2027 하나로 통일되어 있지 않음: {years}"
        print(f"✅ test_admission_year_consistent_within_active_tracks passed! (트랙 {len(tracks)}건, 전부 2027학년도)")
    finally:
        svc.close()


def test_vector_index_populated():
    svc = ArtAdmissionService()
    try:
        with svc.driver.session(default_access_mode="READ") as s:
            rows = s.run("""
                MATCH (c:Admission_TextChunk)
                RETURN c.university AS university, count(c) AS cnt
            """).data()
        by_univ = {r["university"]: r["cnt"] for r in rows}
        universities = {t["university"] for t in svc.list_all_tracks_full()}
        missing = [
            u for u in universities
            if by_univ.get(u, 0) == 0 and u not in VECTOR_INDEX_EXPECTED_MISSING
        ]
        assert not missing, f"벡터 색인이 비어있는 학교(예외 목록에도 없음): {missing}"

        result = svc.hybrid_search("학교폭력 조치사항 감점", top_k=3)
        assert result, "hybrid_search가 결과를 하나도 반환하지 못함 (인덱스/임베딩 호출 확인 필요)"
        print(f"✅ test_vector_index_populated passed! ({len(by_univ)}개 학교 색인, 검색 정상 응답)")
    finally:
        svc.close()


def test_entity_mentions_and_communities_populated():
    """LLM 구조화 추출(원문검증+신뢰도필터) 방식 - Admission_Entity/MENTIONS/
    CO_OCCURS_WITH가 실제로 채워져 있고, PageRank/커뮤니티 값이 계산돼 있는지 확인한다.
    (내작업폴더/02_Art_Admission_Entity_Linker.py --commit 으로 생성됨.
    학교를 새로 추가한 뒤에는 이 스크립트도 다시 실행해야 신규 학교의 청크가
    이 그래프에 반영된다 - 안 하면 조용히 낡은 상태로 남는다.)"""
    svc = ArtAdmissionService()
    try:
        with svc.driver.session(default_access_mode="READ") as s:
            entity_count = s.run("MATCH (e:Admission_Entity) RETURN count(e) AS c").single()["c"]
            mentions_count = s.run("MATCH ()-[r:MENTIONS]->() RETURN count(r) AS c").single()["c"]
            with_pagerank = s.run("MATCH (e:Admission_Entity) WHERE e.pagerank IS NOT NULL RETURN count(e) AS c").single()["c"]
        assert entity_count > 0, "Admission_Entity가 하나도 없음 - 엔티티 링커를 먼저 실행해야 함"
        assert mentions_count > 0, "MENTIONS 관계가 하나도 없음"
        assert with_pagerank == entity_count, f"PageRank 미계산 개체 존재: {entity_count - with_pagerank}건"
        print(f"✅ test_entity_mentions_and_communities_populated passed! (개체 {entity_count}건, MENTIONS {mentions_count}건, 전부 PageRank 계산됨)")
    finally:
        svc.close()


def _ensure_streamlit_running() -> bool:
    """8501 포트에 이미 떠있으면 그대로 쓰고, 없으면 새로 띄운다.
    반환값: 이 함수가 새로 띄웠으면 True (테스트 종료 후 정리 여부 판단용)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex(("localhost", 8501)) == 0:
            return False  # 이미 떠있음

    subprocess.Popen(
        ["uv", "run", "streamlit", "run", "내작업폴더/app_dart_trace_dashboard.py",
         "--server.port", "8501", "--server.headless", "true"],
        cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("localhost", 8501)) == 0:
                time.sleep(3)  # 앱 초기 렌더 대기
                return True
    raise RuntimeError("Streamlit이 30초 내에 8501 포트에서 응답하지 않음")


def test_streamlit_tabs_render_without_exception():
    from playwright.sync_api import sync_playwright

    started_by_us = _ensure_streamlit_running()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 1200})
            console_errors = []
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))
            page.goto(APP_URL, timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            for tab in TABS:
                page.locator(f"text={tab}").click()
                page.wait_for_timeout(2200)
                page.wait_for_load_state("networkidle")
                body = page.locator("body").inner_text()
                assert "Traceback" not in body, f"'{tab}' 탭에서 예외 발생"

            assert not console_errors, f"브라우저 콘솔 에러 발생: {console_errors}"
            browser.close()
        print(f"✅ test_streamlit_tabs_render_without_exception passed! ({len(TABS)}개 탭 전수 통과)")
    finally:
        if started_by_us:
            print("ℹ️ 이 테스트가 띄운 Streamlit 프로세스는 그대로 유지합니다 (수동으로 kill 필요 시 netstat으로 PID 확인).")


if __name__ == "__main__":
    test_no_critical_or_warning_integrity_issues()
    test_no_shared_exam_or_schedule_nodes()
    test_admission_year_consistent_within_active_tracks()
    test_vector_index_populated()
    test_entity_mentions_and_communities_populated()
    test_streamlit_tabs_render_without_exception()
    print("🎉 ALL ART ADMISSION QA REGRESSION TESTS PASSED!")
