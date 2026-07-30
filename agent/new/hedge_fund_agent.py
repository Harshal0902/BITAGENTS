"""Hedge Fund Agent — Covenant-inspired Solana portfolio agent with 1/10 fee model."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from agent_tool_runner import run_tool_agent
from hosted_llm import CAPIX_MODEL, DEFAULT_LLM_MODEL, call_llm, use_capix
from hedge_fund_core import (
    MANAGEMENT_FEE_RATE,
    PERFORMANCE_FEE_RATE,
    analyze_token_for_portfolio,
    calculate_fees,
    get_fee_structure,
    run_portfolio_analysis,
)

HEDGE_FUND_MODEL = (
    CAPIX_MODEL
    if use_capix()
    else os.environ.get(
        "HEDGE_FUND_MODEL",
        os.environ.get("DCA_MODEL", os.environ.get("OPEN_ROUTER_MODEL", DEFAULT_LLM_MODEL)),
    )
)

PORTFOLIO_INTENT_RE = re.compile(
    r"\b(portfolio|analyze|analysis|allocate|allocation|hedge|fund|backtest|rebalance|positions?)\b",
    re.I,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_portfolio_analysis",
            "description": (
                "Run full Covenant-style portfolio analysis on Solana tokens: "
                "quant/value analyst signals, risk limits, suggested allocations."
            ),
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
            "description": "Single-token analyst signals + position limit for a given portfolio size.",
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
            "description": "Calculate 1/10 fees (1% mgmt + 10% performance) for given AUM and profit.",
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
            "description": "Return the hedge fund 1/10 fee model and comparison to 2/20.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOL_REGISTRY = {
    "run_portfolio_analysis": run_portfolio_analysis,
    "analyze_token_for_portfolio": analyze_token_for_portfolio,
    "calculate_fees": calculate_fees,
    "get_fee_structure": get_fee_structure,
}

SYSTEM_PROMPT = f"""You are **Hedge Fund Agent** on Solana — a Covenant Framework-inspired portfolio analyst.

Architecture (like covenant-hedge-fund):
- **Quant/value analysts** produce deterministic signals from on-chain data (liquidity, safety, concentration, valuation).
- **Risk engine** enforces position caps in code — never exceed tool-returned `max_allocation_pct`.
- **Fee model: 1/10** — {MANAGEMENT_FEE_RATE*100:.0f}% annual management + {PERFORMANCE_FEE_RATE*100:.0f}% performance (vs industry 2/20).

Rules:
- Always call tools for portfolio questions; never invent prices, signals, or allocations.
- Present analyst signals, synthesis action (overweight/hold/underweight), and suggested USD allocation.
- Mention the 1/10 fee model when discussing costs.
- Not financial advice. Execution via DCA Agent / Jupiter is separate.
"""


def _extract_tokens(text: str) -> list[str]:
    mints = re.findall(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b", text)
    if mints:
        return mints[:8]
    symbols = re.findall(r"\$?([A-Z][A-Z0-9]{1,15})\b", text.upper())
    stop = {"USD", "SOL", "THE", "AND", "FOR", "WITH", "FUND", "HEDGE", "ANALYZE", "PORTFOLIO", "FEE", "AUM"}
    out = [s for s in symbols if s not in stop]
    return out[:8]


def _extract_capital(text: str) -> float:
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(?:k|K)?\s*(?:usd|USD|capital|portfolio|aum)?", text)
    if not m:
        m = re.search(r"\b([\d,]+(?:\.\d+)?)\s*(?:k|K)\b", text, re.I)
    if not m:
        return 10_000.0
    raw = m.group(1).replace(",", "")
    val = float(raw)
    if re.search(r"\b[\d,]+(?:\.\d+)?\s*[kK]\b", text):
        val *= 1000
    return max(100.0, val)


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


def _fmt(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v >= 1_000_000:
        return f"{v:,.0f}"
    if v >= 1000:
        return f"{v:,.2f}"
    return f"{v:.2f}"


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


def run_hedge_fund_agent(
    user_input: str,
    conversation_history: list,
    user_wallet: Optional[str] = None,
    session_id: Optional[str] = None,
) -> tuple[str, list, list[dict[str, Any]]]:
    prompt = user_input.strip()

    if re.search(r"\b(fee|fees|pricing|1/10|2/20|management fee|performance fee)\b", prompt, re.I):
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

    shortcut = _try_portfolio_shortcut(prompt)
    if shortcut:
        reply, actions = shortcut
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": reply})
        return reply, conversation_history, actions

    return run_tool_agent(
        prompt,
        conversation_history,
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        model=HEDGE_FUND_MODEL,
        app_suffix="Hedge Fund",
        user_wallet=user_wallet,
        session_id=session_id,
    )
