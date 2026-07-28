"""Token Research Agent - EASY Screener research for any Solana token."""

from __future__ import annotations

import os
from typing import Any, Optional

from agent_tool_runner import run_tool_agent
from hosted_llm import CAPIX_MODEL, DEFAULT_LLM_MODEL, use_capix
from kickstart_copilot_agent import (
    analyze_token_health,
    compare_tokens,
    detect_token_risks,
    get_improvement_suggestions,
    get_token_analytics,
    get_token_overview,
    get_token_performance,
    get_top_token_holders,
    recommend_tools,
    search_tokens,
)

TOKEN_RESEARCH_MODEL = (
    CAPIX_MODEL
    if use_capix()
    else os.environ.get(
        "TOKEN_RESEARCH_MODEL",
        os.environ.get("DCA_MODEL", os.environ.get("OPEN_ROUTER_MODEL", DEFAULT_LLM_MODEL)),
    )
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tokens",
            "description": "Search EASY Screener for tokens by name, symbol, or keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "verified_only": {"type": "boolean"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_overview",
            "description": "Full token summary from EASY Screener.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_analytics",
            "description": "Live price, mcap, liquidity, volume, holders.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_performance",
            "description": "Recent price performance windows.",
            "parameters": {
                "type": "object",
                "properties": {"token": {"type": "string"}, "days": {"type": "integer"}},
                "required": ["token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_token_holders",
            "description": "Top on-chain holders via Solana RPC.",
            "parameters": {
                "type": "object",
                "properties": {"token": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_token_health",
            "description": "Strengths, weaknesses, health score /100.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_token_risks",
            "description": "Flag liquidity, concentration, and listing risks.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_tokens",
            "description": "Side-by-side comparison of 2-5 tokens.",
            "parameters": {
                "type": "object",
                "properties": {"tokens": {"type": "array", "items": {"type": "string"}}},
                "required": ["tokens"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_improvement_suggestions",
            "description": "Actionable recommendations for a token project.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_tools",
            "description": "Recommend Solana tools for a research task.",
            "parameters": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
        },
    },
]

TOOL_REGISTRY = {
    "search_tokens": search_tokens,
    "get_token_overview": get_token_overview,
    "get_token_analytics": get_token_analytics,
    "get_token_performance": get_token_performance,
    "get_top_token_holders": get_top_token_holders,
    "analyze_token_health": analyze_token_health,
    "detect_token_risks": detect_token_risks,
    "compare_tokens": compare_tokens,
    "get_improvement_suggestions": get_improvement_suggestions,
    "recommend_tools": recommend_tools,
}

SYSTEM_PROMPT = """You are **Token Research Agent** on Solana — general-purpose token research powered by **EASY Screener**.

Unlike the EasyA Analysis Agent (Kickstart-focused), you research **any** token discoverable on EASY Screener: memecoins, DeFi tokens, new launches, etc.

Rules:
- Use tools for all market and holder data; never invent numbers.
- Attribute derived analysis to EASY Screener.
- Null numeric fields mean missing upstream data — do not treat as zero.
- Disambiguate tokens by mint when multiple search results match.
- Provide concise research briefs: overview → metrics → risks → verdict.
"""


def run_token_research_agent(
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
        model=TOKEN_RESEARCH_MODEL,
        app_suffix="Token Research",
        user_wallet=user_wallet,
        session_id=session_id,
    )
