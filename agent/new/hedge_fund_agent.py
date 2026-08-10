"""Hedge Fund Agent — Covenant-inspired portfolio agent with 1/10 fees + mock backtests."""

from __future__ import annotations

import json
import os
import re
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Optional

from agent_tool_runner import run_tool_agent
from hosted_llm import CAPIX_MODEL, DEFAULT_LLM_MODEL, call_llm, use_capix
from hedge_fund_core import (
    MANAGEMENT_FEE_RATE,
    PERFORMANCE_FEE_RATE,
    analyze_token_for_portfolio,
    calculate_fees,
    get_fee_structure,
    run_mock_backtest,
    run_portfolio_analysis,
)
from hedge_fund_paper import (
    HF_MONITOR_INTERVAL_SECONDS,
    create_strategy,
    list_strategies,
    monitor_cycle,
    paper_dashboard,
    run_strategy_backtest,
    update_strategy_rules,
)
from yahoo_market_data import extract_tickers_from_text
from covenant_picker import parse_horizon_days

HEDGE_FUND_MODEL = (
    CAPIX_MODEL
    if use_capix()
    else os.environ.get(
        "HEDGE_FUND_MODEL",
        os.environ.get("DCA_MODEL", os.environ.get("OPEN_ROUTER_MODEL", DEFAULT_LLM_MODEL)),
    )
)

PORTFOLIO_INTENT_RE = re.compile(
    r"\b(portfolio|analyze|analysis|allocate|allocation|hedge|fund|rebalance|positions?)\b",
    re.I,
)

BACKTEST_INTENT_RE = re.compile(
    r"\b(backtest|back\s*test|mock\s*trad|paper\s*trad|simulate|simulation|pnl|p&l|profit\s*and\s*loss|"
    r"historical\s*(?:return|performance)|from\s+\w+\s+20\d{2}|start\s+trading|"
    r"allowed\s+to\s+trade|give\s+(?:the\s+)?pnl|20\d{2}-\d{2}-\d{2})\b",
    re.I,
)

OPEN_MANDATE_RE = re.compile(
    r"\b(whatever|any\s+assets?|stocks?\s+or\s+crypto|crypto\s+or\s+stocks?|"
    r"allowed\s+to\s+trade|trade\s+whatever|pick\s+(?:the\s+)?assets?|"
    r"name\s+of\s+assets|you\s+would\s+trade)\b",
    re.I,
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

PAPER_INTENT_RE = re.compile(
    r"\b(paper\s*trad|start\s+(?:a\s+)?(?:paper\s+)?(?:fund|strategy|portfolio)|"
    r"create\s+strategy|monitor|dashboard|tp\b|sl\b|take[\s-]?profit|stop[\s-]?loss|"
    r"my\s+(?:positions|strategy|strategies|trades|decisions))\b",
    re.I,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_paper_strategy",
            "description": (
                "Create a PAPER strategy under the Covenant 18-analyst system. "
                "Omit tokens to let the agent pick best-fit assets for the trading horizon "
                "(e.g. 2 weeks, 6 months) — NOT a fixed default book. "
                "Pass take_profit_pct / stop_loss_pct / horizon_days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "name": {"type": "string"},
                    "mode": {"type": "string", "description": "agent | user | hybrid"},
                    "take_profit_pct": {"type": "number"},
                    "stop_loss_pct": {"type": "number"},
                    "capital_usd": {"type": "number"},
                    "horizon_days": {"type": "number", "description": "Trading horizon in days"},
                    "notes": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_paper_strategy",
            "description": "Edit paper strategy rules (TP/SL), symbols, name, or status (active/paused/closed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "string"},
                    "take_profit_pct": {"type": "number"},
                    "stop_loss_pct": {"type": "number"},
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "name": {"type": "string"},
                    "status": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["strategy_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_dashboard",
            "description": (
                "Paper portfolio with per-strategy positions/trades/decisions "
                "(same asset can appear under multiple strategies)."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_strategy_backtest",
            "description": "Backtest a saved strategy with SPY benchmark, Sharpe/Sortino/drawdown (1w|1m|3m|6m|1y).",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "strategy_id": {"type": "string"},
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "capital_usd": {"type": "number"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_mock_backtest",
            "description": (
                "Ad-hoc historical simulation. Omit tokens for Covenant horizon-based asset pick. "
                "Includes SPY benchmark metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "capital_usd": {"type": "number"},
                    "include_news": {"type": "boolean"},
                    "horizon_days": {"type": "number"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_portfolio_analysis",
            "description": "Live Solana on-chain portfolio analysis (legacy path).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "capital_usd": {"type": "number"},
                },
                "required": ["tokens"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_token_for_portfolio",
            "description": "Single Solana token analyst signals.",
            "parameters": {
                "type": "object",
                "properties": {"token": {"type": "string"}, "portfolio_value_usd": {"type": "number"}},
                "required": ["token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_fees",
            "description": "Calculate 1/10 fees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "aum_usd": {"type": "number"},
                    "profit_usd": {"type": "number"},
                    "months": {"type": "number"},
                    "high_water_mark": {"type": "number"},
                },
                "required": ["aum_usd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_structure",
            "description": "Return the hedge fund 1/10 fee model.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _paper_tools(user_wallet: Optional[str] = None):
    wallet = (user_wallet or "").strip()

    def create_paper_strategy(**kwargs):
        if not wallet:
            return {"error": "Wallet sign-in required for paper trading"}
        notes = kwargs.get("notes") or ""
        rules = {
            "take_profit_pct": kwargs.get("take_profit_pct", 15),
            "stop_loss_pct": kwargs.get("stop_loss_pct", 8),
            "notes": notes,
            "objective": "max_profit",
        }
        tokens = kwargs.get("tokens")
        created_by = "user" if tokens else "agent"
        mode = kwargs.get("mode") or ("user" if tokens else "agent")
        horizon_days = kwargs.get("horizon_days")
        if horizon_days is None:
            horizon_days = parse_horizon_days(notes)
        return create_strategy(
            user_wallet=wallet,
            symbols=tokens,
            name=kwargs.get("name") or "",
            mode=mode,
            rules=rules,
            capital_usd=kwargs.get("capital_usd"),
            created_by=created_by,
            horizon_days=int(horizon_days) if horizon_days else None,
            horizon_text=notes,
        )

    def update_paper_strategy(**kwargs):
        if not wallet:
            return {"error": "Wallet sign-in required"}
        rules = {}
        if kwargs.get("take_profit_pct") is not None:
            rules["take_profit_pct"] = kwargs["take_profit_pct"]
        if kwargs.get("stop_loss_pct") is not None:
            rules["stop_loss_pct"] = kwargs["stop_loss_pct"]
        if kwargs.get("notes") is not None:
            rules["notes"] = kwargs["notes"]
        return update_strategy_rules(
            strategy_id=kwargs.get("strategy_id", ""),
            user_wallet=wallet,
            rules=rules or None,
            symbols=kwargs.get("tokens"),
            name=kwargs.get("name"),
            status=kwargs.get("status"),
        )

    def get_paper_dashboard(**_kwargs):
        if not wallet:
            return {"error": "Wallet sign-in required"}
        return paper_dashboard(wallet)

    def run_strategy_backtest_tool(**kwargs):
        if not wallet:
            return {"error": "Wallet sign-in required"}
        return run_strategy_backtest(
            user_wallet=wallet,
            period=kwargs.get("period") or "6m",
            strategy_id=kwargs.get("strategy_id"),
            symbols=kwargs.get("tokens"),
            capital_usd=float(kwargs.get("capital_usd") or 10_000),
        )

    return {
        "create_paper_strategy": create_paper_strategy,
        "update_paper_strategy": update_paper_strategy,
        "get_paper_dashboard": get_paper_dashboard,
        "run_strategy_backtest": run_strategy_backtest_tool,
        "run_mock_backtest": run_mock_backtest,
        "run_portfolio_analysis": run_portfolio_analysis,
        "analyze_token_for_portfolio": analyze_token_for_portfolio,
        "calculate_fees": calculate_fees,
        "get_fee_structure": get_fee_structure,
    }


TOOL_REGISTRY = _paper_tools()  # default without wallet; run_* rebuilds per request

SYSTEM_PROMPT = f"""You are **Hedge Fund Agent** — Covenant Framework paper trading (1/10 fees:
{MANAGEMENT_FEE_RATE*100:.0f}% mgmt + {PERFORMANCE_FEE_RATE*100:.0f}% performance).

Architecture (deterministic — LLM never required for trade decisions):
- 18 analysts: Quant(5) + Value(6) + Macro(7) → confidence-weighted synthesis → Risk Engine → paper fills
- Optional LLM is commentary only

Capabilities:
- `create_paper_strategy` — user tickers OR omit tokens for horizon-based Covenant picker (NOT a fixed book).
  Pass horizon_days / notes like "trade for 6 months". TP/SL stored and editable.
- Shared Yahoo quotes; positions isolated per strategy (same symbol can appear under multiple strategies).
- Monitor every {HF_MONITOR_INTERVAL_SECONDS // 3600}h.
- `run_strategy_backtest` / `run_mock_backtest` — SPY benchmark, Sharpe/Sortino/max drawdown.

Rules: never invent fills/PnL — use tools. Paper only. Not financial advice.
"""


def _extract_tokens(text: str) -> list[str]:
    """Return Yahoo-eligible tickers / aliases from free text (XRP, S&P500, AAPL, …)."""
    found = extract_tickers_from_text(text)
    # Open mandate with no explicit assets → empty so picker runs
    if not found and OPEN_MANDATE_RE.search(text):
        return []
    return found[:12]


def _extract_capital(text: str) -> float:
    # Prefer explicit $ amounts or amounts with usd/capital/k markers — avoid years like 2025
    patterns = [
        r"\$\s*([\d,]+(?:\.\d+)?)\s*([kK])?\b",
        r"\b([\d,]+(?:\.\d+)?)\s*([kK])\s*(?:usd|USD)?\b",
        r"\b([\d,]+(?:\.\d+)?)\s*(?:usd|USD)\b",
        r"\b(?:capital|aum|portfolio)\s*(?:of|=|:)?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*([kK])?\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        # Skip year-like bare numbers without $ or k
        if "$" not in pattern and "k" not in pattern.lower() and "usd" not in pattern.lower():
            if 1900 <= val <= 2100:
                continue
        suffix = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        if suffix and suffix.lower() == "k":
            val *= 1000
        elif re.search(r"\b[\d,]+(?:\.\d+)?\s*[kK]\b", text) and "$" in (m.group(0) or ""):
            pass
        return max(100.0, val)
    return 10_000.0


def _parse_month_year(text: str) -> Optional[date]:
    m = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
        r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{4})\b",
        text,
        re.I,
    )
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    year = int(m.group(2))
    return date(year, month, 1)


def _extract_date_range(text: str) -> tuple[str, str]:
    """Return (start_yyyy_mm_dd, end_yyyy_mm_dd)."""
    iso = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if len(iso) >= 2:
        return iso[0], iso[1]

    # "from Dec 2025" / "today is Apr 2026"
    start = None
    end = None
    from_m = re.search(
        r"\b(?:from|starting|start(?:ing)?\s+(?:trading\s+)?(?:on|in)?|since)\s+"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
        r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{4})\b",
        text,
        re.I,
    )
    if from_m:
        month = _MONTHS[from_m.group(1).lower()]
        year = int(from_m.group(2))
        start = date(year, month, 1)

    today_m = re.search(
        r"\b(?:today\s+is|until|through|to|ending|end(?:ing)?\s+(?:on|in)?)\s+"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
        r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{4})\b",
        text,
        re.I,
    )
    if today_m:
        month = _MONTHS[today_m.group(1).lower()]
        year = int(today_m.group(2))
        last = monthrange(year, month)[1]
        end = date(year, month, last)

    months_found = re.findall(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
        r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{4})\b",
        text,
        re.I,
    )
    if not start and months_found:
        month = _MONTHS[months_found[0][0].lower()]
        year = int(months_found[0][1])
        start = date(year, month, 1)
    if not end and len(months_found) >= 2:
        month = _MONTHS[months_found[-1][0].lower()]
        year = int(months_found[-1][1])
        last = monthrange(year, month)[1]
        end = date(year, month, last)

    if not start:
        start = date(2025, 12, 1)
    if not end:
        # Prefer "today" if provided in prompt context; else use calendar today
        end = date.today()
        if end <= start:
            end = date(start.year, start.month, monthrange(start.year, start.month)[1])

    if end <= start:
        last = monthrange(end.year, end.month)[1]
        end = date(end.year, end.month, last)
        if end <= start:
            end = date(start.year + 1, start.month, min(start.day, monthrange(start.year + 1, start.month)[1]))

    return start.isoformat(), end.isoformat()


def _generate_macro_analysis(analysis: dict[str, Any]) -> str:
    try:
        response = call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the macro/portfolio manager layer of a Covenant-governed hedge fund. "
                        "Given JSON portfolio analysis (deterministic analyst signals already computed), "
                        "write a concise **Portfolio Analysis** with: Thesis, Overweights, Risks, Fee impact (1/10 model), Verdict. "
                        "Use ONLY data from the JSON. Under 300 words. Not financial advice."
                    ),
                },
                {"role": "user", "content": json.dumps(analysis, indent=2, default=str)[:12000]},
            ],
            model=HEDGE_FUND_MODEL,
            temperature=0.35,
            app_suffix="Hedge Fund Analysis",
        )
        return ((response.get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        return f"_Macro analysis unavailable ({exc}). Review deterministic signals above._"


def _format_portfolio_reply(analysis: dict[str, Any], macro: str = "") -> str:
    lines = [
        "**Covenant Hedge Fund — Portfolio Report**",
        f"Capital: ${_fmt(analysis.get('capital_usd', 0))} · Tokens analyzed: {analysis.get('tokens_analyzed', 0)}",
        "",
    ]
    summary = analysis.get("portfolio_summary") or {}
    lines.extend(
        [
            "**Portfolio summary**",
            f"- Suggested deployment: ${_fmt(summary.get('total_suggested_allocation_usd', 0))} ({summary.get('deployment_pct', 0)}%)",
            f"- Cash reserve: ${_fmt(summary.get('cash_remaining_usd', 0))}",
            f"- Overweight candidates: {', '.join(summary.get('overweight_candidates') or []) or 'none'}",
            f"- Underweight / avoid: {', '.join(summary.get('underweight_avoid') or []) or 'none'}",
            "",
        ]
    )

    for pos in analysis.get("positions") or []:
        syn = pos.get("synthesis") or {}
        lines.append(
            f"**{pos.get('token')}** → {syn.get('action', 'hold').upper()} "
            f"(score {syn.get('composite_score', 0)}, conf {syn.get('confidence', 0)}%) "
            f"· suggest ${_fmt(pos.get('suggested_allocation_usd', 0))}"
        )
        for sig in pos.get("analyst_signals") or []:
            lines.append(f"  - {sig.get('analyst')}: {sig.get('signal')} — {sig.get('reasoning')}")
        lines.append("")

    fees = analysis.get("fee_structure") or {}
    lines.extend(
        [
            "**Fee model (1/10)**",
            f"- {fees.get('management_fee_annual_pct', 1)}% annual management · "
            f"{fees.get('performance_fee_pct', 10)}% performance above high-water mark",
            f"- Traditional 2/20: {fees.get('traditional_2_20', {})}",
            "",
        ]
    )

    if analysis.get("errors"):
        lines.extend(["**Warnings**", *[f"- {e}" for e in analysis["errors"]], ""])

    if macro:
        lines.extend(["---", "", "**Portfolio Analysis**", "", macro, "", "Not financial advice. DYOR."])
    else:
        lines.append("Not financial advice. DYOR.")

    return "\n".join(lines)


def _format_backtest_reply(result: dict[str, Any]) -> str:
    if result.get("error"):
        lines = [f"**Backtest failed:** {result.get('error')}"]
        for e in result.get("errors") or []:
            lines.append(f"- {e}")
        if result.get("hint"):
            lines.append(f"\n_{result['hint']}_")
        return "\n".join(lines)

    fees = result.get("fees") or {}
    counts = result.get("trade_counts") or {}
    lines = [
        "**Covenant Hedge Fund — Mock Backtest / PnL Report**",
        f"Window: `{result.get('start_date')}` → `{result.get('end_date')}`",
        f"Strategy: equal-weight + quarterly rebalance · Capital: ${_fmt(result.get('capital_usd', 0))}",
        f"Book: {', '.join(result.get('selected_assets') or [])}",
        f"Note: {result.get('strategy_note') or 'Yahoo Finance simulation'}",
        f"Data: {result.get('data_source')}",
        "",
        "**Allocations (initial)**",
    ]
    for row in result.get("allocations") or []:
        lines.append(
            f"- **{row.get('symbol')}**: {row.get('allocation_pct')}% · ${_fmt(row.get('allocation_usd'))}"
        )

    lines.extend(
        [
            "",
            "**Trade activity**",
            f"- Buys: {counts.get('buys', 0)}",
            f"- Sells: {counts.get('sells', 0)}",
            f"- Total fills: {counts.get('total', 0)}",
            "",
            "**Portfolio PnL**",
            f"- End value: ${_fmt(result.get('end_value_usd', 0))}",
            f"- Gross PnL: ${_fmt(result.get('gross_pnl_usd', 0))} ({result.get('gross_pnl_pct', 0)}%)",
            f"- Fees (1/10): mgmt ${_fmt(fees.get('management_fee_usd', 0))} · "
            f"perf ${_fmt(fees.get('performance_fee_usd', 0))} · "
            f"total ${_fmt(fees.get('total_fees_usd', 0))}",
            f"- Net PnL after fees: ${_fmt(result.get('net_pnl_usd', 0))} ({result.get('net_pnl_pct', 0)}%)",
            "",
            "**Risk / benchmark (SPY)**",
        ]
    )
    metrics = result.get("metrics") or {}
    if metrics and not metrics.get("error"):
        lines.extend(
            [
                f"- Sharpe: {metrics.get('sharpe')} · Sortino: {metrics.get('sortino')}",
                f"- Max drawdown: {metrics.get('max_drawdown_pct')}%",
                f"- SPY return: {metrics.get('spy_return_pct')}% · Alpha vs SPY: {metrics.get('alpha_vs_spy_pct')}%",
                f"- Beta vs SPY: {metrics.get('beta_vs_spy')}",
                "",
                "**Positions**",
            ]
        )
    else:
        lines.append("**Positions**")
    for pos in result.get("positions") or []:
        lines.append(
            f"- **{pos.get('symbol')}** ({pos.get('asset_class') or 'asset'}): "
            f"${_fmt(pos.get('allocation_usd'))} @ ${_fmt(pos.get('entry_price_usd'))} "
            f"→ ${_fmt(pos.get('exit_price_usd'))} · end ${_fmt(pos.get('end_value_usd'))} · "
            f"PnL ${_fmt(pos.get('pnl_usd'))} ({pos.get('pnl_pct')}%)"
        )

    marks = result.get("monthly_marks") or []
    if marks:
        lines.extend(["", "**Monthly marks**"])
        for m in marks[-8:]:
            lines.append(
                f"- {m.get('date')}: value ${_fmt(m.get('portfolio_value_usd'))} · PnL ${_fmt(m.get('pnl_usd'))}"
            )

    trades = [t for t in (result.get("mock_trades") or []) if t.get("side") in ("BUY", "SELL")]
    if trades:
        lines.extend(["", "**Mock trades (sample)**"])
        for t in trades[:20]:
            lines.append(
                f"- {t.get('date')} {t.get('side')} {t.get('symbol')} · "
                f"${_fmt(t.get('notional_usd'))}"
                + (f" @ ${_fmt(t.get('price_usd'))}" if t.get("price_usd") is not None else "")
                + (f" — {t.get('note')}" if t.get("note") else "")
            )
        if len(trades) > 20:
            lines.append(f"- …and {len(trades) - 20} more fills")

    news = result.get("news") or []
    if news:
        lines.extend(["", "**Yahoo Finance news (recent)**"])
        for n in news[:10]:
            lines.append(f"- [{n.get('symbol')}] {n.get('title')} _{n.get('publisher')}_")

    if result.get("errors"):
        lines.extend(["", "**Warnings**", *[f"- {e}" for e in result["errors"]]])

    lines.extend(["", result.get("disclaimer") or "Mock simulation only. Not financial advice. DYOR."])
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    try:
        if value is None or value == "":
            return "0.00"
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v) >= 1_000_000:
        return f"{v:,.0f}"
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:.2f}"
    return f"{v:.6g}"


def _try_backtest_shortcut(user_input: str) -> Optional[tuple[str, list[dict[str, Any]]]]:
    if not BACKTEST_INTENT_RE.search(user_input) and not OPEN_MANDATE_RE.search(user_input):
        # Still allow pure ISO date-range PnL asks
        if not re.search(r"20\d{2}-\d{2}-\d{2}.*20\d{2}-\d{2}-\d{2}", user_input):
            return None
    tokens = _extract_tokens(user_input)
    # Empty tokens => default diversified Yahoo book inside run_mock_backtest
    capital = _extract_capital(user_input)
    start_date, end_date = _extract_date_range(user_input)
    result = run_mock_backtest(
        tokens or None,
        start_date=start_date,
        end_date=end_date,
        capital_usd=capital,
        include_news=True,
    )
    reply = _format_backtest_reply(result)
    actions = [
        {
            "tool": "run_mock_backtest",
            "args": {
                "tokens": tokens or result.get("selected_assets") or [],
                "start_date": start_date,
                "end_date": end_date,
                "capital_usd": capital,
            },
            "result": json.dumps(result, indent=2, default=str),
        }
    ]
    return reply, actions


def _try_portfolio_shortcut(user_input: str) -> Optional[tuple[str, list[dict[str, Any]]]]:
    tokens = _extract_tokens(user_input)
    if not tokens:
        return None
    if not PORTFOLIO_INTENT_RE.search(user_input) and len(tokens) < 2:
        return None

    capital = _extract_capital(user_input)
    analysis = run_portfolio_analysis(tokens, capital_usd=capital)
    macro = _generate_macro_analysis(analysis)
    reply = _format_portfolio_reply(analysis, macro)
    actions = [
        {
            "tool": "run_portfolio_analysis",
            "args": {"tokens": tokens, "capital_usd": capital},
            "result": json.dumps(analysis, indent=2, default=str),
        }
    ]
    return reply, actions


def _extract_tp_sl(text: str) -> tuple[Optional[float], Optional[float]]:
    tp = None
    sl = None
    m_tp = re.search(r"\b(?:tp|take[\s-]?profit)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*%?", text, re.I)
    m_sl = re.search(r"\b(?:sl|stop[\s-]?loss)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*%?", text, re.I)
    if m_tp:
        try:
            tp = abs(float(m_tp.group(1)))
        except ValueError:
            pass
    if m_sl:
        try:
            sl = abs(float(m_sl.group(1)))
        except ValueError:
            pass
    return tp, sl


def _format_paper_dashboard(dash: dict[str, Any]) -> str:
    if dash.get("error"):
        return f"**Paper dashboard error:** {dash['error']}"
    port = dash.get("portfolio") or {}
    lines = [
        "**Paper Trading Dashboard**",
        f"Mode: paper · Covenant 18-analyst · Monitor every {HF_MONITOR_INTERVAL_SECONDS // 3600}h",
        f"Cash: ${_fmt(port.get('cash_usd'))} · Equity: ${_fmt(port.get('equity_usd'))} · "
        f"PnL: ${_fmt(port.get('pnl_usd') or port.get('unrealized_pnl_usd'))} "
        f"({port.get('pnl_pct', 0)}%)",
        "",
        "**Strategies**",
    ]
    for s in dash.get("strategies") or []:
        rules = s.get("rules") or {}
        lines.append(
            f"- `{s.get('id')}` **{s.get('name')}** [{s.get('mode')}/{s.get('status')}] "
            f"· horizon {s.get('horizon_days') or rules.get('horizon_days') or '?'}d "
            f"· {', '.join(s.get('symbols') or [])} "
            f"· TP {rules.get('take_profit_pct')}% / SL {rules.get('stop_loss_pct')}%"
        )
    overlap = dash.get("overlapping_assets") or {}
    if overlap:
        lines.append("")
        lines.append("**Overlapping assets (multi-strategy)**")
        for sym, sids in overlap.items():
            lines.append(f"- **{sym}** in strategies: {', '.join(sids)}")

    lines.append("")
    lines.append("**Positions by strategy**")
    by_strategy = dash.get("by_strategy") or []
    if by_strategy:
        for block in by_strategy:
            st = block.get("strategy") or {}
            lines.append(
                f"### `{st.get('id')}` {st.get('name')} · sleeve ${_fmt(block.get('sleeve_value_usd'))}"
            )
            positions = block.get("positions") or []
            if not positions:
                lines.append("- no open positions")
            for p in positions:
                lines.append(
                    f"- **{p.get('symbol')}**: {p.get('units')} @ ${_fmt(p.get('avg_entry_usd'))} "
                    f"· mkt ${_fmt(p.get('mark_price_usd'))} · PnL ${_fmt(p.get('unrealized_pnl_usd'))}"
                )
            for d in (block.get("decisions") or [])[:4]:
                lines.append(
                    f"  · decision `{d.get('action')}` {d.get('symbol')} — {(d.get('rationale') or '')[:100]}"
                )
    else:
        lines.append("")
        lines.append("**Positions**")
        positions = port.get("positions") or dash.get("positions") or []
        if not positions:
            lines.append("- none yet (monitor will allocate on next cycle)")
        for p in positions:
            lines.append(
                f"- **{p.get('symbol')}** {p.get('side') or 'long'}: "
                f"{p.get('units') or p.get('qty')} @ ${_fmt(p.get('avg_entry_usd') or p.get('avg_price_usd'))} "
                f"· mkt ${_fmt(p.get('mark_price_usd') or p.get('mark_usd'))} · "
                f"PnL ${_fmt(p.get('unrealized_pnl_usd'))}"
            )
    lines.extend(["", "**Recent decisions**"])
    for d in (dash.get("decisions") or [])[:8]:
        lines.append(
            f"- {str(d.get('created_at', ''))[:16]} `{d.get('action')}` "
            f"{d.get('symbol') or ''} [{d.get('strategy_id')}] — {d.get('rationale') or ''}"
        )
    lines.append("\nAsk me to create/update strategies, run a backtest (1w/6m/1y), or edit TP/SL.")
    return "\n".join(lines)


def _try_paper_shortcut(
    user_input: str, user_wallet: Optional[str]
) -> Optional[tuple[str, list[dict[str, Any]]]]:
    if not PAPER_INTENT_RE.search(user_input) and not re.search(
        r"\b(create|start).{0,20}(paper|strategy|fund)\b", user_input, re.I
    ):
        return None
    if not user_wallet:
        return (
            "Sign in with your wallet to use paper trading (strategies are saved per wallet).",
            [],
        )

    # Dashboard / monitor / positions
    if re.search(r"\b(dashboard|positions|decisions|my\s+strateg|monitor\s+status)\b", user_input, re.I):
        dash = paper_dashboard(user_wallet)
        return _format_paper_dashboard(dash), [
            {"tool": "get_paper_dashboard", "args": {}, "result": json.dumps(dash, default=str)}
        ]

    # Period backtest on saved strategy or tokens
    period_m = re.search(r"\b(1w|1m|3m|6m|1y|1\s*week|1\s*month|6\s*months?|1\s*year)\b", user_input, re.I)
    if period_m and re.search(r"\bbacktest\b", user_input, re.I):
        raw = period_m.group(1).lower().replace(" ", "")
        period_map = {
            "1week": "1w",
            "1month": "1m",
            "6month": "6m",
            "6months": "6m",
            "1year": "1y",
        }
        period = period_map.get(raw, raw if raw in ("1w", "1m", "3m", "6m", "1y") else "6m")
        tokens = _extract_tokens(user_input)
        sid_m = re.search(r"\b(str_[a-f0-9]+|[a-f0-9]{8})\b", user_input, re.I)
        result = run_strategy_backtest(
            user_wallet=user_wallet,
            period=period,
            strategy_id=sid_m.group(1) if sid_m else None,
            symbols=tokens or None,
            capital_usd=_extract_capital(user_input),
        )
        # Prefer mock backtest formatting if nested
        bt = result.get("result") or result
        reply = _format_backtest_reply(bt if isinstance(bt, dict) else result)
        return reply, [
            {
                "tool": "run_strategy_backtest",
                "args": {"period": period, "tokens": tokens},
                "result": json.dumps(result, default=str),
            }
        ]

    # Create strategy (agent or user symbols)
    if re.search(r"\b(create|start|new|set\s*up)\b", user_input, re.I) or OPEN_MANDATE_RE.search(
        user_input
    ):
        tokens = _extract_tokens(user_input)
        tp, sl = _extract_tp_sl(user_input)
        rules = {
            "take_profit_pct": tp if tp is not None else 15,
            "stop_loss_pct": sl if sl is not None else 8,
            "objective": "max_profit",
            "notes": user_input[:500],
        }
        created_by = "user" if tokens else "agent"
        mode = "user" if tokens else "agent"
        result = create_strategy(
            user_wallet=user_wallet,
            symbols=tokens or None,
            name="",
            mode=mode,
            rules=rules,
            capital_usd=_extract_capital(user_input),
            created_by=created_by,
            horizon_days=parse_horizon_days(user_input),
            horizon_text=user_input,
        )
        if result.get("error"):
            return f"**Could not create strategy:** {result['error']}", [
                {"tool": "create_paper_strategy", "args": {}, "result": json.dumps(result, default=str)}
            ]
        # Kick one monitor pass so user sees initial decisions sooner
        try:
            monitor_cycle(force_prices=False)
        except Exception:
            pass
        dash = paper_dashboard(user_wallet)
        pick_note = (result.get("picker") or {}).get("note") or ""
        reply = (
            f"**Paper strategy created** `{result.get('id')}`\n"
            f"- Mode: {result.get('mode')} · Horizon: {result.get('horizon_days')}d "
            f"({result.get('horizon_label')})\n"
            f"- Symbols: {', '.join(result.get('symbols') or [])}\n"
            f"- TP {rules['take_profit_pct']}% / SL {rules['stop_loss_pct']}%\n"
            f"- Covenant 18-analyst decisions · LLM not required\n"
            + (f"- {pick_note}\n" if pick_note else "")
            + f"- Market monitor every {HF_MONITOR_INTERVAL_SECONDS // 3600}h\n\n"
            + _format_paper_dashboard(dash)
        )
        return reply, [
            {
                "tool": "create_paper_strategy",
                "args": {"tokens": tokens, "mode": mode},
                "result": json.dumps(result, default=str),
            }
        ]

    # Update TP/SL
    if re.search(r"\b(update|edit|change|set)\b.*\b(tp|sl|take|stop|strategy)\b", user_input, re.I):
        strategies = list_strategies(user_wallet)
        if not strategies:
            return "No strategies yet — say e.g. `create paper strategy with BTC ETH TP 20 SL 10`.", []
        sid_m = re.search(r"\b(str_[a-f0-9]+|[a-f0-9]{8})\b", user_input, re.I)
        strategy_id = sid_m.group(1) if sid_m else strategies[0].get("id")
        tp, sl = _extract_tp_sl(user_input)
        rules = {}
        if tp is not None:
            rules["take_profit_pct"] = tp
        if sl is not None:
            rules["stop_loss_pct"] = sl
        if not rules:
            return "Specify TP/SL like `set TP 20 SL 8` for your strategy.", []
        result = update_strategy_rules(strategy_id=strategy_id, user_wallet=user_wallet, rules=rules)
        return (
            f"**Updated** `{strategy_id}` → {rules}\n\n" + _format_paper_dashboard(paper_dashboard(user_wallet)),
            [{"tool": "update_paper_strategy", "args": {"strategy_id": strategy_id, **rules}, "result": json.dumps(result, default=str)}],
        )

    # Generic paper → dashboard
    if PAPER_INTENT_RE.search(user_input):
        dash = paper_dashboard(user_wallet)
        return _format_paper_dashboard(dash), [
            {"tool": "get_paper_dashboard", "args": {}, "result": json.dumps(dash, default=str)}
        ]
    return None


def run_hedge_fund_agent(
    user_input: str,
    conversation_history: list,
    user_wallet: Optional[str] = None,
    session_id: Optional[str] = None,
) -> tuple[str, list, list[dict[str, Any]]]:
    prompt = user_input.strip()
    tools = _paper_tools(user_wallet)

    if re.search(r"\b(fee|fees|pricing|1/10|2/20|management fee|performance fee)\b", prompt, re.I):
        if not BACKTEST_INTENT_RE.search(prompt) and not re.search(r"\b(BTC|ETH|SOL|backtest|mock)\b", prompt, re.I):
            fees = get_fee_structure()
            reply = (
                "**Hedge Fund Fee Structure (1/10 model)**\n\n"
                f"- **Management:** {fees['management_fee_annual_pct']}% per year on AUM\n"
                f"- **Performance:** {fees['performance_fee_pct']}% of net profits above high-water mark\n"
                f"- **vs 2/20:** traditional funds charge 2% + 20%\n\n"
                f"Example on $100k with $15k profit (12 mo): "
                f"mgmt ${fees['example_100k_12mo']['management_fee_usd']:,.2f}, "
                f"perf ${fees['example_100k_12mo']['performance_fee_usd']:,.2f}, "
                f"total ${fees['example_100k_12mo']['total_fees_usd']:,.2f}\n\n"
                "See `/agents/hedge-fund/pricing` for full details."
            )
            conversation_history.append({"role": "user", "content": prompt})
            conversation_history.append({"role": "assistant", "content": reply})
            return reply, conversation_history, [{"tool": "get_fee_structure", "args": {}, "result": json.dumps(fees)}]

    paper = _try_paper_shortcut(prompt, user_wallet)
    if paper:
        reply, actions = paper
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": reply})
        return reply, conversation_history, actions

    # Prefer saved-strategy period backtests before ad-hoc date backtests when user says paper/strategy
    backtest = _try_backtest_shortcut(prompt)
    if backtest and not PAPER_INTENT_RE.search(prompt):
        reply, actions = backtest
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": reply})
        return reply, conversation_history, actions

    shortcut = _try_portfolio_shortcut(prompt)
    if shortcut:
        reply, actions = shortcut
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": reply})
        return reply, conversation_history, actions

    reply, history, actions = run_tool_agent(
        prompt,
        conversation_history,
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_registry=tools,
        model=HEDGE_FUND_MODEL,
        app_suffix="Hedge Fund",
        user_wallet=user_wallet,
        session_id=session_id,
    )

    for action in reversed(actions):
        tool = action.get("tool")
        if tool not in ("run_mock_backtest", "run_strategy_backtest", "get_paper_dashboard", "create_paper_strategy"):
            continue
        try:
            data = json.loads(action.get("result") or "{}")
        except json.JSONDecodeError:
            break
        if tool == "get_paper_dashboard" or tool == "create_paper_strategy":
            if tool == "create_paper_strategy" and not data.get("error"):
                formatted = (
                    f"**Paper strategy `{data.get('id')}` created**\n\n"
                    + _format_paper_dashboard(paper_dashboard(user_wallet or ""))
                )
            else:
                formatted = _format_paper_dashboard(data if tool == "get_paper_dashboard" else paper_dashboard(user_wallet or ""))
            history[-1] = {"role": "assistant", "content": formatted}
            return formatted, history, actions
        bt = data.get("result") if tool == "run_strategy_backtest" else data
        if isinstance(bt, dict):
            formatted = _format_backtest_reply(bt)
            history[-1] = {"role": "assistant", "content": formatted}
            return formatted, history, actions

    return reply, history, actions
