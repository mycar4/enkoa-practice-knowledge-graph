# -*- coding: utf-8 -*-
"""
[DART-Trace] 5대 대기업집단(삼성/SK/현대차/LG/한화) 미수집 22개사 신규 로딩분
전용 해소·승격 실행기.

promote_batch_1707_uncollected.py의 범용 Rule 1~5 해소 로직과 승격 트랜잭션을
그대로 재사용하되, TARGET_LOAD_RUN_ID만 오늘 신규 로딩 배치로 교체한다.
(원본 스크립트는 어제 배치의 감사 기록으로 그대로 보존, 여기서 덮어쓰지 않음)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_batch_1707_uncollected as base

base.TARGET_LOAD_RUN_ID = "load_batch_5groups_20260906_015853_20260906_015938"


def main():
    print(f"[대상 배치 교체] TARGET_LOAD_RUN_ID -> {base.TARGET_LOAD_RUN_ID}")
    base.main()


if __name__ == "__main__":
    main()
