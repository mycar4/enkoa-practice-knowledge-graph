# -*- coding: utf-8 -*-
"""
DART-Trace Streamlit Cloud Entrypoint
"""
import runpy
import sys
import os

# UTF-8 인코딩 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 대시보드 메인 파일 실행
dashboard_path = os.path.join(os.path.dirname(__file__), "내작업폴더", "app_dart_trace_dashboard.py")
runpy.run_path(dashboard_path, run_name="__main__")
