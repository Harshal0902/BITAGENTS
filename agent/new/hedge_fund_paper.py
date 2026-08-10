"""Hedge Fund paper-trading engine: portfolios, strategies, shared market monitor, 4h scheduler."""

from __future__ import annotations

import os
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from psycopg2.extras import Json

from db import get_conn, init_db
from hedge_fund_core import run_mock_backtest
from yahoo_market_data import (
    fetch_yahoo_daily_prices,
    fetch_yahoo_news,
    resolve_yahoo_asset,
)

HF_MONITOR_INTERVAL_SECONDS = int(os.environ.get("HF_MONITOR_INTERVAL_SECONDS", str(4 * 3600)))
HF_SCHEDULER_POLL_SECONDS = int(os.environ.get("HF_SCHEDULER_POLL_SECONDS", "60"))
DEFAULT_PAPER_CAPITAL = float(os.environ.get("HF_DEFAULT_PAPER_CAPITAL", "10000"))

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()
_last_market_refresh_at: Optional[datetime] = None


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_hex(4)}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(r: Any) -> dict[str, Any]:
    if not r:
        return {}
    out = dict(r)
    for k, v in list(out.items()):
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
    return out


# ─── Market snapshots (shared across users) ───────────────────────────────────

def upsert_market_snapshot(symbol: str, force: bool = False) -> dict[str, Any]:
    """Fetch Yahoo quote into shared cache. Skip if fresh (<4h) unless force."""
    init_db()
    resolved = resolve_yahoo_asset(symbol)
    if resolved.get("error"):
        return resolved
    sym = resolved["symbol"]
    yahoo = resolved["yahoo_symbol"]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM hf_market_snapshots WHERE symbol = %s", (sym,))
            existing = cur.fetchone()
            if existing and not force:
                fetched = existing["fetched_at"]
                if fetched.tzinfo is None:
                    fetched = fetched.replace(tzinfo=timezone.utc)
                age = (_now() - fetched).total_seconds()
                if age < HF_MONITOR_INTERVAL_SECONDS:
                    return {**_row(existing), "cached": True}

    end = _now().date()
    start = end - timedelta(days=5)
    hist = fetch_yahoo_daily_prices(yahoo, start.isoformat(), end.isoformat())
    if hist.get("error"):
        return {"symbol": sym, "error": hist["error"]}
    prices = hist.get("prices") or []
    if not prices:
        return {"symbol": sym, "error": "No Yahoo prices"}
    last = prices[-1][1]
    prev = prices[-2][1] if len(prices) > 1 else last
    change = ((last - prev) / prev * 100) if prev else 0.0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hf_market_snapshots (symbol, yahoo_symbol, asset_class, price_usd, change_24h_pct, raw, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    yahoo_symbol = EXCLUDED.yahoo_symbol,
                    asset_class = EXCLUDED.asset_class,
                    price_usd = EXCLUDED.price_usd,
                    change_24h_pct = EXCLUDED.change_24h_pct,
                    raw = EXCLUDED.raw,
                    fetched_at = NOW()
                RETURNING *
                """,
                (
                    sym,
                    yahoo,
                    resolved.get("asset_class") or "equity",
                    float(last),
                    float(change),
                    Json({"bars": len(prices)}),
                ),
            )
            row = cur.fetchone()
    return {**_row(row), "cached": False}


def refresh_symbols(symbols: list[str], force: bool = False) -> dict[str, Any]:
    unique = []
    for s in symbols:
        u = (s or "").strip().upper()
        if u and u not in unique:
            unique.append(u)
    rows = []
    errors = []
    for sym in unique:
        r = upsert_market_snapshot(sym, force=force)
        if r.get("error"):
            errors.append(f"{sym}: {r['error']}")
        else:
            rows.append(r)
    return {"snapshots": rows, "errors": errors, "count": len(rows)}


def get_market_snapshots(symbols: Optional[list[str]] = None) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            if symbols:
                cur.execute(
                    "SELECT * FROM hf_market_snapshots WHERE symbol = ANY(%s) ORDER BY symbol",
                    (list(symbols),),
                )
            else:
                cur.execute("SELECT * FROM hf_market_snapshots ORDER BY fetched_at DESC LIMIT 100")
            return [_row(r) for r in cur.fetchall()]


def list_watched_symbols() -> list[str]:
    """Union of symbols across all active strategies (shared monitor set)."""
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT jsonb_array_elements_text(symbols) AS symbol
                FROM hf_strategies
                WHERE status = 'active'
                """
            )
            return [r["symbol"] for r in cur.fetchall() if r.get("symbol")]


# ─── Portfolios ───────────────────────────────────────────────────────────────

def get_or_create_portfolio(user_wallet: str, capital_usd: float = DEFAULT_PAPER_CAPITAL) -> dict[str, Any]:
    init_db()
    wallet = user_wallet.strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM hf_paper_portfolios
                WHERE user_wallet = %s AND status = 'active'
                ORDER BY created_at ASC LIMIT 1
                """,
                (wallet,),
            )
            row = cur.fetchone()
            if row:
                return _row(row)
            pid = _new_id("hp")
            capital = max(100.0, float(capital_usd))
            cur.execute(
                """
                INSERT INTO hf_paper_portfolios (id, user_wallet, name, cash_usd, starting_capital)
                VALUES (%s, %s, %s, %s, %s) RETURNING *
                """,
                (pid, wallet, "Paper Book", capital, capital),
            )
            return _row(cur.fetchone())


def get_portfolio(portfolio_id: str, user_wallet: Optional[str] = None) -> Optional[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_wallet:
                cur.execute(
                    "SELECT * FROM hf_paper_portfolios WHERE id = %s AND user_wallet = %s",
                    (portfolio_id, user_wallet),
                )
            else:
                cur.execute("SELECT * FROM hf_paper_portfolios WHERE id = %s", (portfolio_id,))
            row = cur.fetchone()
            return _row(row) if row else None


def list_positions(portfolio_id: str) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM hf_paper_positions WHERE portfolio_id = %s ORDER BY symbol",
                (portfolio_id,),
            )
            return [_row(r) for r in cur.fetchall()]


def portfolio_summary(user_wallet: str) -> dict[str, Any]:
    portfolio = get_or_create_portfolio(user_wallet)
    positions = list_positions(portfolio["id"])
    # Mark to market
    symbols = [p["symbol"] for p in positions]
    snaps = {s["symbol"]: s for s in get_market_snapshots(symbols)} if symbols else {}
    equity = float(portfolio["cash_usd"])
    marked = []
    for p in positions:
        mark = float((snaps.get(p["symbol"]) or {}).get("price_usd") or p.get("mark_price_usd") or p.get("avg_entry_usd") or 0)
        value = float(p["units"]) * mark
        cost = float(p["units"]) * float(p["avg_entry_usd"] or 0)
        equity += value
        marked.append(
            {
                **p,
                "mark_price_usd": mark,
                "market_value_usd": round(value, 2),
                "unrealized_pnl_usd": round(value - cost, 2),
            }
        )
    starting = float(portfolio["starting_capital"])
    return {
        "portfolio": portfolio,
        "positions": marked,
        "equity_usd": round(equity, 2),
        "cash_usd": round(float(portfolio["cash_usd"]), 2),
        "pnl_usd": round(equity - starting, 2),
        "pnl_pct": round(((equity - starting) / starting) * 100, 2) if starting else 0,
        "mode": "paper",
    }


# ─── Strategies ───────────────────────────────────────────────────────────────

def _default_rules(user_rules: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    rules = {
        "objective": "max_profit",
        "take_profit_pct": 15.0,
        "stop_loss_pct": 8.0,
        "max_position_pct": 25.0,
        "rebalance": "signal",
        "notes": "",
    }
    if user_rules:
        rules.update({k: v for k, v in user_rules.items() if v is not None})
    return rules


def create_strategy(
    user_wallet: str,
    symbols: Optional[list[str]] = None,
    name: str = "",
    mode: str = "agent",
    rules: Optional[dict[str, Any]] = None,
    allocation_pct: Optional[dict[str, float]] = None,
    capital_usd: Optional[float] = None,
    created_by: str = "agent",
    horizon_days: Optional[int] = None,
    horizon_text: str = "",
) -> dict[str, Any]:
    """Create paper strategy. Empty symbols => Covenant horizon picker (not a fixed book)."""
    from covenant_picker import horizon_preset, parse_horizon_days, select_assets_for_horizon

    portfolio = get_or_create_portfolio(user_wallet, capital_usd or DEFAULT_PAPER_CAPITAL)
    # If user specifies capital and book is unused, resize paper cash to match
    if capital_usd is not None:
        try:
            cap = max(100.0, float(capital_usd))
            init_db()
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, cash_usd, starting_capital FROM hf_paper_portfolios
                        WHERE id = %s
                        """,
                        (portfolio["id"],),
                    )
                    row = cur.fetchone()
                    cur.execute(
                        "SELECT COUNT(*) AS n FROM hf_paper_positions WHERE portfolio_id = %s AND units > 0",
                        (portfolio["id"],),
                    )
                    n_pos = int((cur.fetchone() or {}).get("n") or 0)
                    if row and n_pos == 0 and abs(float(row["cash_usd"]) - float(row["starting_capital"])) < 0.01:
                        cur.execute(
                            """
                            UPDATE hf_paper_portfolios
                            SET cash_usd = %s, starting_capital = %s, updated_at = NOW()
                            WHERE id = %s
                            RETURNING *
                            """,
                            (cap, cap, portfolio["id"]),
                        )
                        portfolio = _row(cur.fetchone()) or portfolio
        except Exception:
            pass

    days = parse_horizon_days(horizon_text, horizon_days)
    preset = horizon_preset(days)
    pick_meta: dict[str, Any] = {}

    syms = [str(s).strip() for s in (symbols or []) if s and str(s).strip()]
    if not syms:
        pick_meta = select_assets_for_horizon(horizon_days=days)
        syms = list(pick_meta.get("symbols") or [])
        created_by = created_by or "agent"
        mode = mode if mode in ("agent", "user", "hybrid") else "agent"
        if not name:
            name = f"Agent {preset['key']} {days}d"

    # Validate symbols via Yahoo (aliases + live probe for any Yahoo asset)
    valid = []
    errors = []
    for s in syms[:10]:
        r = resolve_yahoo_asset(s, probe=True)
        if r.get("error"):
            errors.append(r["error"])
        else:
            valid.append(r["symbol"])
    if not valid:
        return {
            "error": "No valid symbols",
            "errors": errors,
            "hint": "Use Yahoo tickers e.g. XRP, SPY (S&P500), AAPL, BTC-USD, ^GSPC",
            "picker": pick_meta,
        }

    if not allocation_pct:
        w = round(100.0 / len(valid), 4)
        allocation_pct = {s: w for s in valid}
    rules_final = _default_rules(rules)
    rules_final["horizon_days"] = days
    rules_final["horizon_label"] = preset["key"]
    sid = _new_id("hs")
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hf_strategies (
                    id, portfolio_id, user_wallet, name, mode, status, symbols, allocation_pct,
                    rules, created_by, horizon_days, horizon_label
                ) VALUES (%s,%s,%s,%s,%s,'active',%s,%s,%s,%s,%s,%s) RETURNING *
                """,
                (
                    sid,
                    portfolio["id"],
                    user_wallet.strip(),
                    name or f"{'Agent' if created_by == 'agent' else 'User'} Strategy {sid}",
                    mode if mode in ("agent", "user", "hybrid") else "agent",
                    Json(valid),
                    Json(allocation_pct),
                    Json(rules_final),
                    created_by if created_by in ("agent", "user") else "agent",
                    days,
                    preset["key"],
                ),
            )
            strategy = _row(cur.fetchone())

    refresh_symbols(valid, force=False)
    deploy = _deploy_initial_allocations(portfolio["id"], sid, user_wallet, valid, allocation_pct)
    return {
        **strategy,
        "strategy": strategy,
        "deploy": deploy,
        "errors": errors,
        "mode": strategy.get("mode") or mode,
        "paper": True,
        "picker": pick_meta,
        "horizon_days": days,
        "horizon_label": preset["key"],
    }


def update_strategy_rules(
    strategy_id: str,
    user_wallet: str,
    rules: Optional[dict[str, Any]] = None,
    symbols: Optional[list[str]] = None,
    allocation_pct: Optional[dict[str, float]] = None,
    name: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM hf_strategies WHERE id = %s AND user_wallet = %s",
                (strategy_id, user_wallet.strip()),
            )
            row = cur.fetchone()
            if not row:
                return {"error": "Strategy not found"}
            merged_rules = dict(row["rules"] or {})
            if rules:
                merged_rules.update(rules)
            new_symbols = symbols if symbols is not None else list(row["symbols"] or [])
            new_alloc = allocation_pct if allocation_pct is not None else dict(row["allocation_pct"] or {})
            new_name = name if name is not None else row["name"]
            new_status = status if status in ("active", "paused", "closed") else row["status"]
            cur.execute(
                """
                UPDATE hf_strategies SET
                    name = %s, symbols = %s, allocation_pct = %s, rules = %s,
                    status = %s, updated_at = NOW()
                WHERE id = %s RETURNING *
                """,
                (new_name, Json(new_symbols), Json(new_alloc), Json(merged_rules), new_status, strategy_id),
            )
            return {"strategy": _row(cur.fetchone())}


def list_strategies(user_wallet: str) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM hf_strategies WHERE user_wallet = %s ORDER BY created_at DESC",
                (user_wallet.strip(),),
            )
            return [_row(r) for r in cur.fetchall()]


def get_strategy(strategy_id: str, user_wallet: Optional[str] = None) -> Optional[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_wallet:
                cur.execute(
                    "SELECT * FROM hf_strategies WHERE id = %s AND user_wallet = %s",
                    (strategy_id, user_wallet.strip()),
                )
            else:
                cur.execute("SELECT * FROM hf_strategies WHERE id = %s", (strategy_id,))
            row = cur.fetchone()
            return _row(row) if row else None


# ─── Paper execution ──────────────────────────────────────────────────────────

def _get_price(symbol: str) -> Optional[float]:
    snap = upsert_market_snapshot(symbol, force=False)
    if snap.get("error"):
        return None
    return float(snap.get("price_usd") or 0) or None


def _deploy_initial_allocations(
    portfolio_id: str,
    strategy_id: str,
    user_wallet: str,
    symbols: list[str],
    allocation_pct: dict[str, float],
) -> dict[str, Any]:
    trades = []
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return {"trades": [], "count": 0, "error": "Portfolio not found"}
    initial_cash = float(portfolio["cash_usd"])
    for sym in symbols:
        pct = float(allocation_pct.get(sym) or (100.0 / max(len(symbols), 1)))
        notional = initial_cash * (pct / 100.0)
        price = _get_price(sym)
        if not price or notional < 1:
            continue
        portfolio = get_portfolio(portfolio_id)
        cash = float((portfolio or {}).get("cash_usd") or 0)
        spend = min(notional, cash)
        if spend < 1:
            continue
        t = execute_paper_trade(
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            user_wallet=user_wallet,
            symbol=sym,
            side="BUY",
            notional_usd=spend,
            reason="Initial paper allocation",
            decision="buy",
        )
        trades.append(t)
    return {"trades": trades, "count": len([t for t in trades if not t.get("error")])}


def execute_paper_trade(
    portfolio_id: str,
    user_wallet: str,
    symbol: str,
    side: str,
    notional_usd: Optional[float] = None,
    units: Optional[float] = None,
    strategy_id: Optional[str] = None,
    reason: str = "",
    decision: str = "",
) -> dict[str, Any]:
    init_db()
    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"error": "side must be BUY or SELL"}
    price = _get_price(symbol)
    if not price:
        return {"error": f"No price for {symbol}"}

    portfolio = get_portfolio(portfolio_id, user_wallet)
    if not portfolio:
        return {"error": "Portfolio not found"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            if strategy_id:
                cur.execute(
                    """
                    SELECT * FROM hf_paper_positions
                    WHERE portfolio_id = %s AND symbol = %s AND strategy_id = %s FOR UPDATE
                    """,
                    (portfolio_id, symbol.upper(), strategy_id),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM hf_paper_positions
                    WHERE portfolio_id = %s AND symbol = %s
                    ORDER BY updated_at DESC LIMIT 1 FOR UPDATE
                    """,
                    (portfolio_id, symbol.upper()),
                )
            pos = cur.fetchone()
            cash = float(portfolio["cash_usd"])

            if side == "BUY":
                if units is None:
                    if not notional_usd or notional_usd <= 0:
                        return {"error": "notional_usd or units required"}
                    units = float(notional_usd) / price
                units = float(units)
                cost = units * price
                if cost > cash + 1e-6:
                    return {"error": f"Insufficient paper cash (${cash:.2f}) for ${cost:.2f} buy"}
                new_cash = cash - cost
                if pos:
                    old_u = float(pos["units"])
                    old_avg = float(pos["avg_entry_usd"])
                    new_u = old_u + units
                    new_avg = ((old_u * old_avg) + cost) / new_u if new_u else price
                    cur.execute(
                        """
                        UPDATE hf_paper_positions SET units=%s, avg_entry_usd=%s, mark_price_usd=%s,
                            strategy_id=COALESCE(%s, strategy_id), updated_at=NOW()
                        WHERE id=%s
                        """,
                        (new_u, new_avg, price, strategy_id, pos["id"]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO hf_paper_positions (id, portfolio_id, strategy_id, symbol, units, avg_entry_usd, mark_price_usd)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (_new_id("hz"), portfolio_id, strategy_id, symbol.upper(), units, price, price),
                    )
            else:
                if not pos or float(pos["units"]) <= 0:
                    return {"error": f"No position in {symbol} to sell"}
                held = float(pos["units"])
                if units is None:
                    if notional_usd and notional_usd > 0:
                        units = min(held, float(notional_usd) / price)
                    else:
                        units = held
                units = min(held, float(units))
                proceeds = units * price
                new_cash = cash + proceeds
                new_u = held - units
                if new_u < 1e-8:
                    cur.execute("DELETE FROM hf_paper_positions WHERE id = %s", (pos["id"],))
                else:
                    cur.execute(
                        """
                        UPDATE hf_paper_positions SET units=%s, mark_price_usd=%s, updated_at=NOW()
                        WHERE id=%s
                        """,
                        (new_u, price, pos["id"]),
                    )
                cost = units  # for notional below
                cost = proceeds

            tid = _new_id("ht")
            notional = units * price
            cur.execute(
                """
                UPDATE hf_paper_portfolios SET cash_usd=%s, updated_at=NOW() WHERE id=%s
                """,
                (new_cash, portfolio_id),
            )
            cur.execute(
                """
                INSERT INTO hf_paper_trades (
                    id, portfolio_id, strategy_id, user_wallet, symbol, side, units, price_usd, notional_usd, reason, decision
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
                """,
                (
                    tid,
                    portfolio_id,
                    strategy_id,
                    user_wallet.strip(),
                    symbol.upper(),
                    side,
                    units,
                    price,
                    notional,
                    reason,
                    decision or side.lower(),
                ),
            )
            trade = _row(cur.fetchone())
    return {"trade": trade, "cash_usd": round(new_cash, 2)}


def list_trades(user_wallet: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM hf_paper_trades WHERE user_wallet = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (user_wallet.strip(), max(1, min(limit, 200))),
            )
            return [_row(r) for r in cur.fetchall()]


def list_decisions(user_wallet: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM hf_decisions WHERE user_wallet = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (user_wallet.strip(), max(1, min(limit, 200))),
            )
            return [_row(r) for r in cur.fetchall()]


# ─── Decision engine ──────────────────────────────────────────────────────────

def _record_decision(
    strategy_id: str,
    portfolio_id: str,
    user_wallet: str,
    symbol: str,
    action: str,
    rationale: str,
    price_usd: float,
    confidence: float = 0.5,
    executed: bool = False,
    trade_id: Optional[str] = None,
    signals: Optional[list] = None,
    decision_graph: Optional[dict] = None,
) -> dict[str, Any]:
    init_db()
    did = _new_id("hd")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hf_decisions (
                    id, strategy_id, portfolio_id, user_wallet, symbol, action,
                    confidence, rationale, price_usd, executed, trade_id, signals, decision_graph
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
                """,
                (
                    did,
                    strategy_id,
                    portfolio_id,
                    user_wallet,
                    symbol.upper(),
                    action,
                    confidence,
                    rationale,
                    price_usd,
                    executed,
                    trade_id,
                    Json(signals or []),
                    Json(decision_graph or {}),
                ),
            )
            return _row(cur.fetchone())


def list_positions_for_strategy(strategy_id: str) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM hf_paper_positions WHERE strategy_id = %s AND units > 0 ORDER BY symbol",
                (strategy_id,),
            )
            return [_row(r) for r in cur.fetchall()]


def evaluate_strategy(strategy_id: str, execute: bool = True) -> dict[str, Any]:
    """Covenant 18-analyst decisions + user TP/SL overrides. Auditable signal graph."""
    from covenant_pipeline import analyze_yahoo_asset

    strategy = get_strategy(strategy_id)
    if not strategy or strategy.get("status") != "active":
        return {"error": "Strategy not active", "strategy_id": strategy_id}

    symbols = list(strategy.get("symbols") or [])
    rules = strategy.get("rules") or {}
    tp = float(rules.get("take_profit_pct") or 0)
    sl = float(rules.get("stop_loss_pct") or 0)
    horizon = int(strategy.get("horizon_days") or rules.get("horizon_days") or 90)
    lookback = max(90, min(500, horizon * 2))
    portfolio_id = strategy["portfolio_id"]
    user_wallet = strategy["user_wallet"]

    refresh_symbols(symbols, force=False)
    positions = {p["symbol"]: p for p in list_positions_for_strategy(strategy_id)}
    portfolio = get_portfolio(portfolio_id)
    cash = float((portfolio or {}).get("cash_usd") or 0)
    # Mark equity for this strategy sleeve + shared cash
    snaps = {s["symbol"]: s for s in get_market_snapshots(symbols)}
    sleeve_value = 0.0
    marked_positions = []
    for sym, pos in positions.items():
        mark = float((snaps.get(sym) or {}).get("price_usd") or pos.get("mark_price_usd") or pos.get("avg_entry_usd") or 0)
        mv = float(pos["units"]) * mark
        sleeve_value += mv
        marked_positions.append({**pos, "market_value_usd": mv, "mark_price_usd": mark})
    equity = cash + sleeve_value

    decisions = []
    for sym in symbols:
        pos = positions.get(sym)
        price = float((snaps.get(sym) or {}).get("price_usd") or 0)
        analysis = analyze_yahoo_asset(
            sym,
            lookback_days=lookback,
            equity_usd=equity,
            cash_usd=cash,
            existing_positions=marked_positions,
        )
        if analysis.get("error"):
            dec = _record_decision(
                strategy_id, portfolio_id, user_wallet, sym, "hold",
                f"Analysis error: {analysis['error']}", price or 0, 10, False, None, [], {"error": analysis["error"]},
            )
            decisions.append(dec)
            continue

        action = analysis.get("action") or "hold"
        synthesis = analysis.get("synthesis") or {}
        rationale = (
            f"Covenant 18-analyst composite {synthesis.get('composite_score')} → {action} "
            f"(domains {synthesis.get('domain_scores')})"
        )
        confidence = float(synthesis.get("confidence") or 50)
        signals = analysis.get("analyst_signals") or []
        graph = analysis.get("decision_graph") or {}

        # User TP/SL overrides (compliance R15)
        if pos and float(pos.get("units") or 0) > 0 and price:
            entry = float(pos.get("avg_entry_usd") or price)
            pnl_pct = ((price - entry) / entry) * 100 if entry else 0
            if tp and pnl_pct >= tp:
                action = "sell"
                rationale = f"Take-profit hit: +{pnl_pct:.2f}% >= TP {tp}% (overrides signals)"
                confidence = max(confidence, 85)
                graph["override"] = "take_profit"
            elif sl and pnl_pct <= -abs(sl):
                action = "sell"
                rationale = f"Stop-loss hit: {pnl_pct:.2f}% <= -SL {abs(sl)}% (overrides signals)"
                confidence = max(confidence, 90)
                graph["override"] = "stop_loss"

        trade_id = None
        executed = False
        if execute and action in ("buy", "sell"):
            if action == "buy":
                notional = float(analysis.get("suggested_notional_usd") or 0)
                if notional >= 25 and cash >= 25:
                    result = execute_paper_trade(
                        portfolio_id=portfolio_id,
                        strategy_id=strategy_id,
                        user_wallet=user_wallet,
                        symbol=sym,
                        side="BUY",
                        notional_usd=notional,
                        reason=rationale[:240],
                        decision="buy",
                    )
                    if result.get("trade"):
                        executed = True
                        trade_id = result["trade"]["id"]
                        cash = float(result.get("cash_usd") or cash)
            elif action == "sell" and pos:
                result = execute_paper_trade(
                    portfolio_id=portfolio_id,
                    strategy_id=strategy_id,
                    user_wallet=user_wallet,
                    symbol=sym,
                    side="SELL",
                    units=float(pos["units"]),
                    reason=rationale[:240],
                    decision="sell",
                )
                if result.get("trade"):
                    executed = True
                    trade_id = result["trade"]["id"]
                    cash = float(result.get("cash_usd") or cash)

        price = price or float((analysis.get("features") or {}).get("price") or 0)
        dec = _record_decision(
            strategy_id,
            portfolio_id,
            user_wallet,
            sym,
            action,
            rationale[:500],
            price,
            confidence / 100.0 if confidence > 1 else confidence,
            executed,
            trade_id,
            signals,
            graph,
        )
        decisions.append(dec)

    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hf_strategies SET last_evaluated_at = NOW(), updated_at = NOW() WHERE id = %s",
                (strategy_id,),
            )

    return {
        "strategy_id": strategy_id,
        "horizon_days": horizon,
        "decisions": decisions,
        "count": len(decisions),
        "analysts": 18,
        "llm_required": False,
        "evaluated_at": _now().isoformat(),
    }


def evaluate_all_active_strategies() -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM hf_strategies WHERE status = 'active'")
            ids = [r["id"] for r in cur.fetchall()]
    results = []
    for sid in ids:
        results.append(evaluate_strategy(sid, execute=True))
    return {"strategies_evaluated": len(ids), "results": results}


def monitor_cycle(force_prices: bool = False) -> dict[str, Any]:
    """Refresh shared market data for watched symbols, then evaluate strategies."""
    global _last_market_refresh_at
    symbols = list_watched_symbols()
    market = refresh_symbols(symbols, force=force_prices) if symbols else {"snapshots": [], "count": 0}
    evals = evaluate_all_active_strategies()
    _last_market_refresh_at = _now()
    return {
        "market": market,
        "evaluations": evals,
        "monitored_symbols": symbols,
        "at": _last_market_refresh_at.isoformat(),
        "interval_seconds": HF_MONITOR_INTERVAL_SECONDS,
    }


# ─── Backtests for strategies ─────────────────────────────────────────────────

PERIOD_DAYS = {
    "1w": 7,
    "1week": 7,
    "1m": 30,
    "1month": 30,
    "3m": 90,
    "6m": 182,
    "6months": 182,
    "1y": 365,
    "1year": 365,
}


def run_strategy_backtest(
    user_wallet: str,
    period: str = "6m",
    strategy_id: Optional[str] = None,
    symbols: Optional[list[str]] = None,
    capital_usd: float = DEFAULT_PAPER_CAPITAL,
) -> dict[str, Any]:
    from covenant_picker import select_assets_for_horizon

    label = (period or "6m").lower().strip()
    days = PERIOD_DAYS.get(label)
    if not days:
        return {"error": f"Unknown period '{period}'. Use 1w, 1m, 3m, 6m, 1y."}

    rules = {}
    horizon_days = days
    if strategy_id:
        strategy = get_strategy(strategy_id, user_wallet)
        if not strategy:
            return {"error": "Strategy not found"}
        symbols = list(strategy.get("symbols") or [])
        rules = strategy.get("rules") or {}
        horizon_days = int(strategy.get("horizon_days") or rules.get("horizon_days") or days)
    elif not symbols:
        pick = select_assets_for_horizon(horizon_days=days)
        symbols = list(pick.get("symbols") or [])
        rules = {"picker": pick.get("note"), "horizon_days": days}

    syms = [s.strip().upper() for s in (symbols or [])]
    if not syms:
        return {"error": "No symbols to backtest"}
    end = _now().date()
    start = end - timedelta(days=days)
    result = run_mock_backtest(
        tokens=syms,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        capital_usd=capital_usd,
        include_news=True,
    )
    if result.get("error"):
        return result

    bid = _new_id("hb")
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hf_backtest_runs (
                    id, strategy_id, user_wallet, period_label, start_date, end_date, symbols, rules, result
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at
                """,
                (
                    bid,
                    strategy_id,
                    user_wallet.strip(),
                    label,
                    start,
                    end,
                    Json(syms),
                    Json(rules),
                    Json(result),
                ),
            )
            row = cur.fetchone()
    return {
        "backtest_id": bid,
        "period": label,
        "horizon_days": horizon_days,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "symbols": syms,
        "rules": rules,
        "result": result,
        "metrics": result.get("metrics"),
        "created_at": row["created_at"].isoformat() if row else None,
    }


def list_backtests(user_wallet: str, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, strategy_id, period_label, start_date, end_date, symbols, created_at,
                       result->'gross_pnl_pct' AS gross_pnl_pct,
                       result->'net_pnl_pct' AS net_pnl_pct,
                       result->'end_value_usd' AS end_value_usd
                FROM hf_backtest_runs
                WHERE user_wallet = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (user_wallet.strip(), max(1, min(limit, 50))),
            )
            return [_row(r) for r in cur.fetchall()]


def paper_dashboard(user_wallet: str) -> dict[str, Any]:
    summary = portfolio_summary(user_wallet)
    strategies = list_strategies(user_wallet)
    decisions = list_decisions(user_wallet, limit=50)
    trades = list_trades(user_wallet, limit=50)
    backtests = list_backtests(user_wallet, limit=10)
    watched = list_watched_symbols()
    market = get_market_snapshots(watched) if watched else []

    # Per-strategy breakdown (same asset can appear under multiple strategies)
    by_strategy: list[dict[str, Any]] = []
    for s in strategies:
        sid = s["id"]
        spos = list_positions_for_strategy(sid)
        snaps = {m["symbol"]: m for m in get_market_snapshots([p["symbol"] for p in spos])} if spos else {}
        marked = []
        sleeve = 0.0
        for p in spos:
            mark = float((snaps.get(p["symbol"]) or {}).get("price_usd") or p.get("mark_price_usd") or p.get("avg_entry_usd") or 0)
            mv = float(p["units"]) * mark
            cost = float(p["units"]) * float(p["avg_entry_usd"] or 0)
            sleeve += mv
            marked.append(
                {
                    **p,
                    "strategy_id": sid,
                    "strategy_name": s.get("name"),
                    "mark_price_usd": mark,
                    "market_value_usd": round(mv, 2),
                    "unrealized_pnl_usd": round(mv - cost, 2),
                }
            )
        s_trades = [t for t in trades if t.get("strategy_id") == sid][:15]
        s_decisions = [d for d in decisions if d.get("strategy_id") == sid][:15]
        by_strategy.append(
            {
                "strategy": s,
                "positions": marked,
                "sleeve_value_usd": round(sleeve, 2),
                "trades": s_trades,
                "decisions": s_decisions,
                "symbols": s.get("symbols") or [],
                "horizon_days": s.get("horizon_days"),
                "horizon_label": s.get("horizon_label"),
            }
        )

    # Shared assets across strategies
    symbol_to_strategies: dict[str, list[str]] = {}
    for block in by_strategy:
        for sym in block["symbols"]:
            symbol_to_strategies.setdefault(sym, []).append(block["strategy"]["id"])
    overlapping = {k: v for k, v in symbol_to_strategies.items() if len(v) > 1}

    return {
        "mode": "paper",
        "governance": "Covenant 18-analyst deterministic",
        "llm_required": False,
        "monitor_interval_seconds": HF_MONITOR_INTERVAL_SECONDS,
        "last_market_refresh_at": _last_market_refresh_at.isoformat() if _last_market_refresh_at else None,
        "portfolio": summary,
        "strategies": strategies,
        "by_strategy": by_strategy,
        "overlapping_assets": overlapping,
        "decisions": decisions,
        "trades": trades,
        "backtests": backtests,
        "market": market,
        "news": fetch_yahoo_news([s["symbol"] for s in market[:6]], limit_per_symbol=2) if market else [],
    }


# ─── Scheduler ────────────────────────────────────────────────────────────────

def _scheduler_loop() -> None:
    global _last_market_refresh_at
    # Stagger first run slightly
    time.sleep(5)
    while not _scheduler_stop.is_set():
        try:
            due = True
            if _last_market_refresh_at is not None:
                age = (_now() - _last_market_refresh_at).total_seconds()
                due = age >= HF_MONITOR_INTERVAL_SECONDS
            if due and list_watched_symbols():
                print(f"\n  📈 Hedge Fund paper monitor cycle ({HF_MONITOR_INTERVAL_SECONDS // 3600}h)")
                result = monitor_cycle(force_prices=True)
                print(
                    f"  HF monitor: {result.get('market', {}).get('count', 0)} symbols · "
                    f"{result.get('evaluations', {}).get('strategies_evaluated', 0)} strategies"
                )
            elif due:
                _last_market_refresh_at = _now()
        except Exception as exc:
            print(f"  ⚠️  HF paper scheduler error: {exc}")
        _scheduler_stop.wait(HF_SCHEDULER_POLL_SECONDS)


def start_hedge_fund_scheduler() -> bool:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return True
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, name="hf-paper-scheduler", daemon=True
    )
    _scheduler_thread.start()
    return True


def stop_hedge_fund_scheduler() -> None:
    _scheduler_stop.set()


def scheduler_status() -> dict[str, Any]:
    return {
        "running": bool(_scheduler_thread and _scheduler_thread.is_alive()),
        "interval_seconds": HF_MONITOR_INTERVAL_SECONDS,
        "poll_seconds": HF_SCHEDULER_POLL_SECONDS,
        "last_market_refresh_at": _last_market_refresh_at.isoformat() if _last_market_refresh_at else None,
        "watched_symbols": list_watched_symbols(),
    }
