# -*- coding: utf-8 -*-
"""
🧪 [항목④] Jev 판정 회귀 하네스 - golden dataset

오늘(2026-09-22~23) 세션에서 Jev를 새로 넣거나 바꿀 때마다 즉석 스크래치 스크립트로
A/B(정확도 실측)를 하고 버렸다 - 다음에 프롬프트를 또 바꾸면 같은 실측을 처음부터
다시 만들어야 했다. 이 파일은 그 케이스들을 전부 모아 재사용 가능한 스크립트로
남긴다. 새 Jev 판정을 추가하거나 프롬프트를 바꿀 때 여기에 케이스를 추가하고
다시 실행하면 회귀 여부를 바로 알 수 있다.

ci_quality_gate.py와 분리한 이유: 여긴 실제 Jev/OpenAI 호출이 들어가 무료가
아니다(건당 매우 저렴하지만 0원은 아님) - 그래서 매 배포마다 자동 실행되지 않고,
Jev 관련 코드를 건드렸을 때 수동으로 실행한다.

사용법: python tests/jev_regression_harness.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from services.art_admission_agent import _classify_route
from services.art_admission_llm import _self_check_compat_claim
from services.art_admission_service import ArtAdmissionService

TOTAL_PASS = 0
TOTAL_CASES = 0


def _report(name: str, passed: int, total: int):
    global TOTAL_PASS, TOTAL_CASES
    TOTAL_PASS += passed
    TOTAL_CASES += total
    mark = "OK" if passed == total else "FAIL"
    print(f"[{mark}] {name}: {passed}/{total}")


# ============================================================
# 1. 라우터 분류 (_classify_route) - 2026-09-23 Choice 통합 시 실측 10/10
# ============================================================
_ROUTER_ALL_UNIS = ["홍익대학교", "중앙대학교", "한국예술종합학교", "가천대학교", "서경대학교"]
ROUTER_CASES = [
    ("자기소개서 대필하면 걸리나요?", "DOCUMENT_WRITING_HELP"),
    ("미술활동보고서에 인적사항 넣으면 감점되나요?", "DOCUMENT_WRITING_HELP"),
    ("자기소개서 글자수 제한이 얼마야?", "DOCUMENT_WRITING_HELP"),
    ("국어 3등급인데 어디 찔러야 해?", "COMPLEX_TOOL"),
    ("경쟁률 제일 낮은 학교 어디야?", "COMPLEX_TOOL"),
    ("중앙대 실기와 유사한 대학 찾아줘", "COMPLEX_TOOL"),
    ("전체 절차 총정리해줘", "COMPLEX_TOOL"),
    ("가천대학교 회화전공 실기전형 알려줘", "SIMPLE_GRAPH"),
    ("홍익대학교 실기고사일이 언제야?", "SIMPLE_GRAPH"),
    ("소묘로 지원 가능한 학교 알려줘", "SIMPLE_GRAPH"),
]


def run_router_cases():
    passed = 0
    for query, expected in ROUTER_CASES:
        result = _classify_route(query, _ROUTER_ALL_UNIS)
        ok = result["route"] == expected
        passed += ok
        if not ok:
            print(f"    MISMATCH: '{query}' expected={expected} got={result['route']} (method={result['method']})")
    _report("라우터 3지선다 분류", passed, len(ROUTER_CASES))


# ============================================================
# 2. 호환학교 자기검증 (_self_check_compat_claim) - overclaim/giveup + 오탐 방지
# 2026-09-22 실측: 원래 A/B 8/8, 2026-09-23 실사용 스윕에서 발견된 오탐 3건 추가
# ============================================================
COMPAT_CLAIM_CASES = [
    # (has_exact_match, context_compatible_tracks, answer, expect_overclaim, expect_giveup)
    (False, [{"shared_keywords": [], "shared_materials": ["연필"]}],
     "이 학과와 호환되는 학교는 단국대학교 천안캠퍼스 미술학부-동양화전공입니다.", True, False),
    (False, [{"shared_keywords": [], "shared_materials": ["연필"]}],
     "이 학과와 성격이 비슷한 학교로는 단국대학교가 있습니다.", True, False),
    (False, [{"shared_keywords": [], "shared_materials": ["연필"]}],
     "정확히 일치하는 학교를 찾지 못했습니다.", False, False),
    (False, [{"shared_keywords": [], "shared_materials": ["연필"]}],
     "죄송하지만 저희가 보유한 데이터베이스에는 없습니다.", False, False),
    (False, [{"shared_keywords": [], "shared_materials": ["연필"]}],
     "동일 계열의 전형을 갖춘 학교가 실제로 존재합니다.", True, False),
    (True, [{"shared_keywords": ["소묘"], "shared_materials": []}],
     "관련 학교를 확인하지 못했습니다.", False, True),
    (True, [{"shared_keywords": ["소묘"], "shared_materials": []}],
     "안내해 드리기 어렵습니다. 자세한 사항은 입학처에 문의하세요.", False, True),
    (True, [{"shared_keywords": ["소묘"], "shared_materials": []}],
     "네, 단국대학교 천안캠퍼스 미술학부-동양화전공이 실기유형 기준 호환됩니다.", False, False),
    # 2026-09-23 실사용 스윕 발견 오탐 3건 - context_compatible_tracks가 애초에 빈
    # 질문(호환검색 자체를 안 한 질문)에는 이 체크를 아예 건너뛰어야 한다.
    (None, [],
     "소묘로 지원 가능한 학교는 다음과 같습니다:\n1. 상명대학교 - 인체소묘 또는 인체수채화", False, False),
    (None, [],
     "중앙대학교의 공간연출전공과 성격이 비슷한 학과로는 계원예술대학교의 공간연출과가 있습니다. 76.9%의 유사성을 보입니다.", False, False),
    (None, [],
     "국어3/영어2/사회3으로 기초디자인을 준비 중인 학생이 지원 가능한 대학입니다. 모든 대학의 실기유형이 \"기초디자인\"으로 일치합니다.", False, False),
]


def run_compat_claim_cases():
    passed = 0
    for has_exact, ctx, answer, expect_overclaim, expect_giveup in COMPAT_CLAIM_CASES:
        warnings = _self_check_compat_claim(answer, ctx)
        got_overclaim = any("일치하는 근거가 없습니다" in w for w in warnings)
        got_giveup = any("포기" in w for w in warnings)
        ok = got_overclaim == expect_overclaim and got_giveup == expect_giveup
        passed += ok
        if not ok:
            print(f"    MISMATCH: '{answer[:40]}...' expected(overclaim={expect_overclaim}, giveup={expect_giveup}) got(overclaim={got_overclaim}, giveup={got_giveup})")
    _report("호환학교 자기검증(과잉주장/포기/오탐방지)", passed, len(COMPAT_CLAIM_CASES))


# ============================================================
# 3. 블라인드평가 개인식별정보 보완검사 (_jev_detects_identifying_info)
# 2026-09-22 실측: 정규식 단독 5/9, 정규식+Jev 보완 9/9
# ============================================================
BLIND_PII_CASES = [
    ("제 이름은 홍길동이고 A고등학교에 재학 중입니다.", True),
    ("제가 다니는 대원외고에서 3년간 미술을 배웠습니다.", True),
    ("지도해주신 김민수 선생님과 함께 작업했던 벽화를 소개하고 싶습니다.", True),
    ("동탄국제고등학교 미술반에서 3년간 활동하며 다양한 작품을 완성했습니다.", True),
    ("2026년 전국청소년미술실기대회 대상 수상 경력을 바탕으로 이 작품을 구상했습니다.", True),
    ("고등학교 시절 미술 동아리에서 활동하며 다양한 작품을 완성했습니다.", False),
    ("저는 미술을 전공하고 싶습니다.", False),
    ("저는 빈센트 반 고흐의 화풍에 영향을 받았습니다.", False),
    # 주의: 이메일/전화번호/주민번호는 정규식이 먼저 잡고(run_document_fact_checks에서
    # 정규식이 하나라도 걸리면 Jev를 아예 안 부름), 이 함수(_jev_detects_identifying_info)
    # 단독으로는 실명/학교명/지도교사/수상경력만 판정하도록 설계됐다 - 그래서 여기
    # 단독 호출 기준으로는 False가 맞는 동작이다(정규식+Jev 합집합 결과가 True인 것과는
    # 별개).
    ("제 이메일은 abc@example.com입니다.", False),
]


def run_blind_pii_cases():
    passed = 0
    for text, expected in BLIND_PII_CASES:
        got = ArtAdmissionService._jev_detects_identifying_info(text)
        ok = got == expected
        passed += ok
        if not ok:
            print(f"    MISMATCH: '{text[:40]}...' expected={expected} got={got}")
    _report("블라인드평가 개인식별정보 보완검사", passed, len(BLIND_PII_CASES))


if __name__ == "__main__":
    print("Jev 판정 회귀 하네스 실행 중 (실제 Jev/OpenAI 호출 발생, 소액 비용)...\n")
    run_router_cases()
    run_compat_claim_cases()
    run_blind_pii_cases()
    print(f"\n{'='*50}")
    print(f"전체: {TOTAL_PASS}/{TOTAL_CASES}")
    if TOTAL_PASS == TOTAL_CASES:
        print("모든 Jev 판정 회귀 없음 - PASS")
        sys.exit(0)
    else:
        print("일부 회귀 발견 - 위 MISMATCH 로그 확인 필요")
        sys.exit(1)
