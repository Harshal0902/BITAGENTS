"""Due Diligence Agent - token and smart contract risk assessment on Solana."""

from __future__ import annotations

import os
from typing import Any, Optional

from agent_tool_runner import run_tool_agent
from hosted_llm import CAPIX_MODEL, DEFAULT_LLM_MODEL, use_capix
from kickstart_copilot_agent import (
    detect_token_risks,
    get_token_analytics,
    get_token_overview,
    get_top_token_holders,
    search_tokens,
)
from solana_token_diligence import get_mint_authorities, run_due_diligence_report

DUE_DILIGENCE_MODEL = (
    CAPIX_MODEL
    if use_capix()
    else os.environ.get(
        "DUE_DILIGENCE_MODEL",
        os.environ.get("DCA_MODEL", os.environ.get("OPEN_ROUTER_MODEL", DEFAULT_LLM_MODEL)),
    )
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tokens",
            "description": "Find a token on EASY Screener before running diligence.",
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
            "name": "run_due_diligence_report",
            "description": "Full due diligence: authorities, holders, liquidity, risk score.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mint_authorities",
            "description": "Check mint and freeze authority on-chain.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_overview",
            "description": "Token metadata and links from EASY Screener.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_analytics",
            "description": "Liquidity, volume, mcap for exit-risk assessment.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_token_holders",
            "description": "Whale concentration check via Solana RPC.",
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
            "name": "detect_token_risks",
            "description": "EASY Screener risk flags.",
            "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]},
        },
    },
]

TOOL_REGISTRY = {
    "search_tokens": search_tokens,
    "run_due_diligence_report": run_due_diligence_report,
    "get_mint_authorities": get_mint_authorities,
    "get_token_overview": get_token_overview,
    "get_token_analytics": get_token_analytics,
    "get_top_token_holders": get_top_token_holders,
    "detect_token_risks": detect_token_risks,
}

SYSTEM_PROMPT = """You are **Due Diligence Agent** on Solana.

Perform due diligence on tokens and SPL mints before users interact or trade: mint/freeze authorities, holder concentration, liquidity, verification status, and composite risk score.

Rules:
- Start with `run_due_diligence_report` when user asks to vet a specific token.
- Highlight **high severity** risks first (active mint/freeze authority, low liquidity, concentration).
- This is not a formal audit — clarify limitations and recommend professional review for large allocations.
- Attribute market data to EASY Screener; on-chain authority data from Solana RPC.
- Never approve a token as "safe" — use graded assessments (A-D) and conditional language.
"""


def run_due_diligence_agent(
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
        model=DUE_DILIGENCE_MODEL,
        app_suffix="Due Diligence",
        user_wallet=user_wallet,
        session_id=session_id,
    )
