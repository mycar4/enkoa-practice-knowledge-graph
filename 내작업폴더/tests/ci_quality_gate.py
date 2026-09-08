# -*- coding: utf-8 -*-
"""GitHub Actions 배포 게이트 전용 진입점. test_art_admission_rag_eval.py의 전체 3개
테스트 중, 무료·결정적인 두 개만 골라 배포 직전에 돌린다(비용 드는 LLM-as-Judge
테스트는 로컬/수동 실행용으로 남겨둔다 - 배포마다 API 비용이 나가지 않게).
실행: python 내작업폴더/tests/ci_quality_gate.py (리포 루트에서)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_art_admission_rag_eval import (  # noqa: E402
    test_exact_match_never_includes_material_only_overlaps,
    test_qa_search_and_agent_search_agree,
)

if __name__ == "__main__":
    test_exact_match_never_includes_material_only_overlaps()
    test_qa_search_and_agent_search_agree()
    print("🎉 CI QUALITY GATE PASSED (무료 회귀 테스트 2건)")
