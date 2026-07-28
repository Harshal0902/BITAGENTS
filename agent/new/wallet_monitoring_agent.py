"""Wallet Monitoring Agent - analyze connected wallet and suggest trades."""

from __future__ import annotations

import os
from typing import Any, Optional

from agent_tool_runner import run_tool_agent
from hosted_llm import CAPIX_MODEL, DEFAULT_LLM_MODEL, use_capix
from kickstart_copilot_agent import get_token_analytics, search_tokens
from solana_wallet_tools import (
    analyze_wallet_profile,
    get_wallet_recent_activity,
    get_wallet_sol_balance,
    get_wallet_token_balances,
)

WALLET_MONITORING_MODEL = (
    CAPIX_MODEL
    if use_capix()
    else os.environ.get(
        "WALLET_MONITORING_MODEL",
        os.environ.get("DCA_MODEL", os.environ.get("OPEN_ROUTER_MODEL", DEFAULT_LLM_MODEL)),
    )
)


def analyze_connected_wallet(user_wallet: Optional[str] = None) -> dict[str, Any]:
    if not user_wallet:
        return {"error": "Connect and sign in with your wallet to analyze holdings."}
    profile = analyze_wallet_profile(user_wallet)
    tokens = get_wallet_token_balances(user_wallet, limit=25)
    activity = get_wallet_recent_activity(user_wallet, limit=12)
    return {
        "wallet": user_wallet,
        "profile": profile,
        "holdings": tokens,
        "recent_activity": activity,
        "cluster_note": "Use holdings + market data to assess concentration and idle SOL.",
    }


def suggest_wallet_trades(user_wallet: Optional[str] = None, risk_profile: str = "balanced") -> dict[str, Any]:
    if not user_wallet:
        return {"error": "Connect and sign in with your wallet for personalized suggestions."}
    analysis = analyze_connected_wallet(user_wallet=user_wallet)
    if analysis.get("error"):
        return analysis
    holdings = (analysis.get("holdings") or {}).get("tokens") or []
    sol = (analysis.get("profile") or {}).get("sol_balance") or 0
    suggestions: list[dict[str, str]] = []

    if sol > 0.5 and len(holdings) < 3:
        suggestions.append(
            {
                "type": "diversification",
                "idea": "Consider DCA into large-cap Solana tokens (SOL ecosystem leaders) using the DCA Agent.",
                "rationale": f"Wallet holds {sol:.3f} SOL with few SPL positions — concentration in native SOL.",
            }
        )
    if len(holdings) >= 5:
        top = holdings[0]
        suggestions.append(
            {
                "type": "rebalance",
                "idea": f"Review overweight position in {top.get('symbol')} ({top.get('amount')} tokens).",
                "rationale": "Large single-token exposure increases idiosyncratic risk.",
            }
        )
    if sol < 0.05 and holdings:
        suggestions.append(
            {
                "type": "gas",
                "idea": "Top up SOL for transaction fees before executing swaps.",
                "rationale": "Low SOL balance may block future trades.",
            }
        )
    if not suggestions:
        suggestions.append(
            {
                "type": "monitor",
                "idea": "Portfolio looks balanced — set alerts or DCA plans for systematic entries.",
                "rationale": "No urgent rebalance flags from on-chain snapshot.",
            }
        )

    enriched = []
    for row in holdings[:5]:
        symbol = row.get("symbol")
        if symbol and symbol not in ("SOL", "?"):
            market = get_token_analytics(symbol)
            if not market.get("error"):
                enriched.append({"holding": row, "market": market})

    return {
        "wallet": user_wallet,
        "risk_profile": risk_profile,
        "suggestions": suggestions,
        "holdings_with_market": enriched,
        "disclaimer": "Suggestions are informational only — not financial advice. Verify before trading.",
    }


def lookup_holding_token(token: str, user_wallet: Optional[str] = None) -> dict[str, Any]:
    if not user_wallet:
        return {"error": "Wallet sign-in required."}
    holdings = get_wallet_token_balances(user_wallet, limit=50)
    tokens = holdings.get("tokens") or []
    token_q = (token or "").strip().upper()
    match = next((t for t in tokens if str(t.get("symbol", "")).upper() == token_q), None)
    analytics = get_token_analytics(token)
    return {
        "wallet": user_wallet,
        "holding": match,
        "market": analytics,
        "in_wallet": match is not None,
    }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_connected_wallet",
            "description": "Full snapshot of the signed-in user's wallet.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wallet_sol_balance",
            "description": "SOL balance for an address (defaults to connected wallet when analyzing self).",
            "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wallet_token_balances",
            "description": "SPL token balances for a wallet address.",
            "parameters": {
                "type": "object",
                "properties": {"address": {"type": "string"}, "limit": {"type": "integer"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wallet_recent_activity",
            "description": "Recent signatures for a wallet.",
            "parameters": {
                "type": "object",
                "properties": {"address": {"type": "string"}, "limit": {"type": "integer"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_wallet_trades",
            "description": "Portfolio-aware trade suggestions (informational, no auto execution).",
            "parameters": {
                "type": "object",
                "properties": {"risk_profile": {"type": "string", "description": "conservative, balanced, aggressive"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_holding_token",
            "description": "Cross-reference a token symbol with user's holdings and live market data.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tokens",
            "description": "Search EASY Screener when user asks about tokens not in their wallet.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_analytics",
            "description": "Live market data for a token symbol or mint.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
]


def _wallet_tool(name: str, user_wallet: Optional[str] = None, **kwargs):
    address = (kwargs.pop("address", None) or user_wallet or "").strip()
    if name == "analyze_connected_wallet":
        return analyze_connected_wallet(user_wallet=user_wallet)
    if name == "suggest_wallet_trades":
        return suggest_wallet_trades(user_wallet=user_wallet, **kwargs)
    if name == "lookup_holding_token":
        return lookup_holding_token(user_wallet=user_wallet, **kwargs)
    if name == "get_wallet_sol_balance":
        return get_wallet_sol_balance(address) if address else {"error": "No wallet address."}
    if name == "get_wallet_token_balances":
        return get_wallet_token_balances(address, kwargs.get("limit", 20)) if address else {"error": "No wallet address."}
    if name == "get_wallet_recent_activity":
        return get_wallet_recent_activity(address, kwargs.get("limit", 10)) if address else {"error": "No wallet address."}
    raise KeyError(name)


TOOL_REGISTRY = {
    "analyze_connected_wallet": lambda **kw: _wallet_tool("analyze_connected_wallet", **kw),
    "get_wallet_sol_balance": lambda **kw: _wallet_tool("get_wallet_sol_balance", **kw),
    "get_wallet_token_balances": lambda **kw: _wallet_tool("get_wallet_token_balances", **kw),
    "get_wallet_recent_activity": lambda **kw: _wallet_tool("get_wallet_recent_activity", **kw),
    "suggest_wallet_trades": lambda **kw: _wallet_tool("suggest_wallet_trades", **kw),
    "lookup_holding_token": lambda **kw: _wallet_tool("lookup_holding_token", **kw),
    "search_tokens": search_tokens,
    "get_token_analytics": get_token_analytics,
}

SYSTEM_PROMPT = """You are **Wallet Monitoring Agent** on Solana.

Monitor the user's connected wallet: SOL balance, SPL holdings, recent activity, and informational trade suggestions.

Rules:
- Prefer `analyze_connected_wallet` for holistic questions about "my wallet".
- Suggestions are **informational only** — not financial advice. Never claim to have executed trades.
- Use EASY Screener analytics when discussing token market context; attribute the source.
- Encourage DCA Agent or Jupiter for actual execution when user wants to act on a suggestion.
"""


def run_wallet_monitoring_agent(
    user_input: str,
    conversation_history: list,
    user_wallet: Optional[str] = None,
    session_id: Optional[str] = None,
) -> tuple[str, list, list[dict[str, Any]]]:
    return run_tool_agent(
        user_input,
        conversation_history,
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        model=WALLET_MONITORING_MODEL,
        app_suffix="Wallet Monitoring",
        user_wallet=user_wallet,
        session_id=session_id,
    )
