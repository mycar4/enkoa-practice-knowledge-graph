# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v1.2] 사용자 포트폴리오 관리 서비스 (다중 사용자 대응)
================================================================================
- 보유 종목(종목코드·수량·매수단가)을 SQLite에 저장한다. Neo4j Aura(공유
  지식그래프)와는 완전히 분리된, 사용자 개인 데이터다.
- v1.1(Streamlit 단일 프로세스)까지는 "로컬 파일 = 사실상 1인용"이었으나,
  API 서버로 분리되면서 여러 사용자가 같은 서버에 접속하게 되어 holdings에
  user_id를 추가했다. 레거시 Streamlit 호출(인자 없이 호출)은 user_id=1
  (LEGACY_LOCAL_USER)로 취급해 하위 호환을 유지한다.
- 시세는 pykrx.stock.get_market_ohlcv(로그인 불필요)로 조회한다.
  (get_market_cap_by_ticker 등 일부 pykrx 엔드포인트는 KRX 로그인 계정이 필요해서
   사용하지 않는다 - 종가/등락률만으로 평가금액·평가손익 계산에는 충분하다.)
================================================================================
"""

import os
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "user_portfolio.db"

LEGACY_LOCAL_USER_ID = 1


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            stock_code TEXT NOT NULL,
            corp_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_buy_price REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # 기존(v1.1) DB 파일 하위 호환: user_id 컬럼이 없으면 추가
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(holdings)").fetchall()}
    if "user_id" not in existing_cols:
        conn.execute(f"ALTER TABLE holdings ADD COLUMN user_id INTEGER NOT NULL DEFAULT {LEGACY_LOCAL_USER_ID}")

    # id=1을 레거시(Streamlit 단일 프로세스 시절) 데이터 전용으로 예약해둔다.
    # 이 예약이 없으면 실제 회원가입 1호(auto-increment id=1)가 우연히 이
    # 레거시 데이터를 그대로 물려받는 데이터 격리 사고가 난다.
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (LEGACY_LOCAL_USER_ID, "__legacy_local_streamlit_user__", "", datetime.datetime.now().isoformat())
    )
    conn.commit()
    return conn


def add_holding(stock_code: str, corp_name: str, quantity: int, avg_buy_price: float, user_id: int = LEGACY_LOCAL_USER_ID) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO holdings (user_id, stock_code, corp_name, quantity, avg_buy_price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, stock_code.strip(), corp_name.strip(), int(quantity), float(avg_buy_price), datetime.datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_holding(holding_id: int, user_id: int = LEGACY_LOCAL_USER_ID) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM holdings WHERE id = ? AND user_id = ?", (holding_id, user_id))
        conn.commit()
    finally:
        conn.close()


def list_holdings(user_id: int = LEGACY_LOCAL_USER_ID) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM holdings WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_latest_price(stock_code: str, max_lookback_days: int = 10) -> Optional[Dict[str, Any]]:
    """
    최근 거래일 종가/등락률 조회 (로그인 불필요 pykrx 엔드포인트만 사용).
    당일 데이터가 아직 없으면(주말/공휴일/미래 시각 등) 최근 영업일까지 역순 탐색한다.
    """
    from pykrx import stock

    today = datetime.date.today()
    for i in range(max_lookback_days):
        d = (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv(d, d, stock_code)
        except Exception:
            continue
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                "date": d,
                "close": int(row["종가"]),
                "change_pct": float(row["등락률"]),
            }
    return None


def _fetch_risk_signal(service, stock_code: str) -> Dict[str, Any]:
    """DART-Trace 지식그래프(Aura, 읽기 전용)와 이 보유종목을 조회 시점에만 조인.
    실패해도 포트폴리오 조회 자체는 끊기지 않도록 안전하게 결측 처리한다."""
    try:
        return service.get_portfolio_risk_signal(stock_code)
    except Exception:
        return {"found": False, "error": True}


def get_portfolio_summary(user_id: int = LEGACY_LOCAL_USER_ID) -> Dict[str, Any]:
    """보유종목 전체에 현재가·평가손익 + DART-Trace 리스크 신호(승격 지분·자본이벤트)를 결합한 요약.
    시세 조회 실패 종목은 안전하게 결측 처리한다."""
    holdings = list_holdings(user_id)
    rows = []
    total_buy_amount = 0.0
    total_eval_amount = 0.0
    price_unavailable_count = 0

    service = None
    try:
        from services.decision_report_service import DecisionReportService
        service = DecisionReportService()
    except Exception:
        service = None

    for h in holdings:
        price_info = fetch_latest_price(h["stock_code"])
        buy_amount = h["quantity"] * h["avg_buy_price"]
        total_buy_amount += buy_amount
        risk_signal = _fetch_risk_signal(service, h["stock_code"]) if service else {"found": False}

        if price_info:
            current_price = price_info["close"]
            eval_amount = h["quantity"] * current_price
            profit = eval_amount - buy_amount
            profit_pct = (profit / buy_amount * 100) if buy_amount > 0 else 0.0
            total_eval_amount += eval_amount
        else:
            current_price = None
            eval_amount = None
            profit = None
            profit_pct = None
            price_unavailable_count += 1

        rows.append({
            "id": h["id"],
            "stock_code": h["stock_code"],
            "corp_name": h["corp_name"],
            "quantity": h["quantity"],
            "avg_buy_price": h["avg_buy_price"],
            "current_price": current_price,
            "price_date": price_info["date"] if price_info else None,
            "eval_amount": eval_amount,
            "profit": profit,
            "profit_pct": profit_pct,
            "risk_signal": risk_signal,
        })

    if service:
        service.close()

    total_profit = total_eval_amount - total_buy_amount if price_unavailable_count == 0 else None

    return {
        "holdings": rows,
        "total_buy_amount": total_buy_amount,
        "total_eval_amount": total_eval_amount if price_unavailable_count == 0 else None,
        "total_profit": total_profit,
        "price_unavailable_count": price_unavailable_count,
    }
