# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v1.1] 사용자 포트폴리오 로컬 관리 서비스
================================================================================
- 보유 종목(종목코드·수량·매수단가)을 로컬 SQLite에만 저장한다.
  Neo4j Aura(공유 클라우드)와는 완전히 분리된, 사용자 개인 비공개 데이터다.
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


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            corp_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_buy_price REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def add_holding(stock_code: str, corp_name: str, quantity: int, avg_buy_price: float) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO holdings (stock_code, corp_name, quantity, avg_buy_price, created_at) VALUES (?, ?, ?, ?, ?)",
            (stock_code.strip(), corp_name.strip(), int(quantity), float(avg_buy_price), datetime.datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_holding(holding_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        conn.commit()
    finally:
        conn.close()


def list_holdings() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM holdings ORDER BY created_at DESC").fetchall()
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


def get_portfolio_summary() -> Dict[str, Any]:
    """보유종목 전체에 현재가·평가손익 + DART-Trace 리스크 신호(승격 지분·자본이벤트)를 결합한 요약.
    시세 조회 실패 종목은 안전하게 결측 처리한다."""
    holdings = list_holdings()
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
