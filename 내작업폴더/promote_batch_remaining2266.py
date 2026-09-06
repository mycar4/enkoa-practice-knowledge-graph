# -*- coding: utf-8 -*-
"""
[DART-Trace] 잔여 미수집 2,266개사(신규 공시 17,132건) 전용 해소·승격 실행기.

promote_batch_1707_uncollected.py의 범용 Rule 1~5 해소 로직과 승격 트랜잭션을
그대로 재사용하되, TARGET_LOAD_RUN_ID만 이번 신규 로딩 배치로 교체한다.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_batch_1707_uncollected as base

base.TARGET_LOAD_RUN_ID = "load_batch_remaining2266_20260906_021804_20260906_035125"


def main():
    print(f"[대상 배치 교체] TARGET_LOAD_RUN_ID -> {base.TARGET_LOAD_RUN_ID}")
    base.main()


if __name__ == "__main__":
    main()
