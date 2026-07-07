"""
EasyA Analysis Agent — Solana token discovery, analytics, and guidance.

Free for users (wallet sign-in required). Token data from EASY Screener (cached 1h per mint).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

from dca_agent import (
    OPEN_ROUTER_API,
    OPEN_ROUTER_API_URL,
    OPEN_ROUTER_APP_NAME,
    OPEN_ROUTER_SITE_URL,
    SOLANA_CLUSTER,
)
from db import (
    add_watchlist_token,
    compare_watchlist_tokens,
    list_watchlist,
    remove_watchlist_token,
)
from easya_screener_client import (
    ATTRIBUTION,
    CACHE_TTL_SECONDS,
    get_allowlist_prompt_block,
    get_token_bundle,
    list_tokens as screener_list_tokens,
    resolve_token as screener_resolve_token,
    screener_configured,
    search_tokens as screener_search,
)
from shared_governance import GOVERNANCE_PROMPT

KICKSTART_MODEL = os.environ.get(
    "KICKSTART_COPILOT_MODEL",
    os.environ.get("OPEN_ROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
)

OPERATION_GUIDES: dict[str, dict[str, Any]] = {
    "burn_tokens": {
        "summary": "Permanently destroy tokens from circulation.",
        "benefits": ["Reduces supply", "Can signal commitment to holders"],
        "risks": ["Irreversible", "Wrong amount or token cannot be undone"],
        "steps": [
            "Confirm mint and amount with your team",
            "Use a trusted burn tool or send to a known burn address",
            "Verify supply change on-chain",
        ],
        "tools": ["Solana CLI", "Squads", "EasyA Kickstart burn flow"],
    },
    "lock_liquidity": {
        "summary": "Time-lock LP tokens so liquidity cannot be removed early.",
        "benefits": ["Builds trust", "Reduces rug-pull risk perception"],
        "risks": ["Locked funds are inaccessible until unlock", "Wrong pool or duration"],
        "steps": [
            "Identify LP token mint from your DEX pool",
            "Choose lock duration and provider",
            "Lock LP tokens and publish proof link",
        ],
        "tools": ["Streamflow", "UNCX", "Team Finance", "Solana lock providers"],
    },
    "relock_liquidity": {
        "summary": "Extend or renew an existing liquidity lock before it expires.",
        "benefits": ["Maintains community trust", "Avoids unlock FUD"],
        "risks": ["Missing deadline leaves liquidity unlocked", "Provider fees"],
        "steps": ["Check current lock expiry", "Initiate re-lock with same provider", "Announce new expiry"],
        "tools": ["Streamflow", "Original lock provider dashboard"],
    },
    "migrate_liquidity": {
        "summary": "Move liquidity from one pool/DEX to another.",
        "benefits": ["Better routing", "Consolidated volume", "Upgrade to new token version"],
        "risks": ["Temporary price impact", "User confusion", "Smart contract risk on new pool"],
        "steps": [
            "Communicate migration timeline",
            "Remove/add liquidity on target DEX",
            "Update docs and links",
        ],
        "tools": ["Raydium", "Orca", "Meteora", "Jupiter limit orders"],
    },
    "verify_contract": {
        "summary": "Publish verified source on a block explorer.",
        "benefits": ["Transparency", "Easier audits", "Community trust"],
        "risks": ["Exposes implementation details if not audited", "Verification mismatch breaks trust"],
        "steps": [
            "Build reproducible artifact",
            "Submit to Solscan/SolanaFM verify flow",
            "Match on-chain program ID exactly",
        ],
        "tools": ["Solscan verify", "SolanaFM", "Anchor verify"],
    },
    "transfer_ownership": {
        "summary": "Move admin/upgrade authority to another wallet or multisig.",
        "benefits": ["Operational security", "Multisig governance"],
        "risks": ["Wrong recipient is catastrophic", "Loss of control if multisig misconfigured"],
        "steps": ["Prepare recipient wallet/multisig", "Transfer authority on-chain", "Test admin actions"],
        "tools": ["Squads multisig", "Solana CLI", "Program-specific admin UI"],
    },
    "renounce_ownership": {
        "summary": "Permanently remove admin control (mint/freeze/upgrade where applicable).",
        "benefits": ["Maximum decentralization signal", "No admin key risk"],
        "risks": ["Cannot fix bugs or upgrade", "Irreversible"],
        "steps": ["Audit code thoroughly first", "Renounce mint/freeze/upgrade authorities", "Verify on explorer"],
        "tools": ["Solana CLI", "Squads", "EasyA Kickstart renounce flow"],
    },
    "vesting": {
        "summary": "Schedule token unlocks for team, investors, or contributors.",
        "benefits": ["Aligns incentives", "Reduces sell pressure"],
        "risks": ["Complex schedules confuse community", "Cliff/unlock calendar must be public"],
        "steps": ["Define recipients and schedule", "Deploy vesting contracts", "Publish dashboard link"],
        "tools": ["Streamflow", "Magna", "Sablier-style Solana vesting"],
    },
    "staking": {
        "summary": "Reward holders for locking or delegating tokens.",
        "benefits": ["Retention", "Governance participation", "Yield narrative"],
        "risks": ["Emission dilution", "Smart contract exploit surface", "Mercenary capital"],
        "steps": ["Design emissions and duration", "Deploy staking program", "Audit and launch UI"],
        "tools": ["Marinade-style staking", "Custom Anchor program", "Realms governance"],
    },
    "treasury": {
        "summary": "Manage project funds across wallets and multisigs.",
        "benefits": ["Operational runway", "Transparent grants"],
        "risks": ["Key compromise", "Poor OPSEC", "Concentrated treasury"],
        "steps": ["Use multisig", "Separate hot/cold wallets", "Publish treasury policy"],
        "tools": ["Squads", "Goki", "Realms", "Solana FM portfolio"],
    },
}

TOOL_RECOMMENDATIONS: dict[str, list[str]] = {
    "liquidity_locking": ["Streamflow", "UNCX", "Team Finance"],
    "token_migration": ["Raydium", "Orca", "Meteora", "Jupiter"],
    "vesting": ["Streamflow", "Magna"],
    "contract_verification": ["Solscan", "SolanaFM", "Anchor verify"],
    "explorer": ["Solscan", "SolanaFM", "Solana Explorer"],
    "portfolio_tracking": ["Solana FM", "Step Finance", "Birdeye"],
    "analytics": ["EASY Screener", "Birdeye", "DexScreener"],
    "dex_trading": ["Jupiter", "Raydium", "Orca"],
    "multisig": ["Squads", "Goki"],
    "launch": ["EasyA Kickstart", "Raydium launchlab"],
}


def _openrouter_headers() -> dict[str, str]:
    if not OPEN_ROUTER_API:
        raise RuntimeError("OPEN_ROUTER_API is not set in agent/new/.env")
    return {
        "Authorization": f"Bearer {OPEN_ROUTER_API}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPEN_ROUTER_SITE_URL,
        "X-Title": f"{OPEN_ROUTER_APP_NAME} EasyA Analysis",
    }


def _screener_gate() -> Optional[dict[str, Any]]:
    if screener_configured():
        return None
    return {
        "error": "EZ_API_KEY is not configured. Add it to agent/new/.env to use EASY Screener.",
        "code": "INVALID_KEY",
    }


def _token_bundle(token: str) -> dict[str, Any]:
    blocked = _screener_gate()
    if blocked:
        return blocked
    return get_token_bundle(token)


def _row(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("error"):
        return bundle
    return bundle.get("token") or {}


def list_verified_kickstart_tokens(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    active_only: bool = True,
    query: Optional[str] = None,
) -> dict[str, Any]:
    blocked = _screener_gate()
    if blocked:
        return blocked

    q = (query or "").strip()
    if q:
        result = screener_search(q, limit=20)
        if result.get("error"):
            return result
        tokens = result.get("tokens") or []
    else:
        result = screener_list_tokens(page=0, limit=50, verified_only=active_only)
        if result.get("error"):
            return result
        tokens = result.get("tokens") or []

    tag_q = (tag or category or "").strip().lower()
    if tag_q:
        filtered = []
        for t in tokens:
            tags = [str(x).lower() for x in (t.get("tags") or [])]
            hay = " ".join(
                [str(t.get("symbol") or ""), str(t.get("name") or ""), " ".join(tags)]
            ).lower()
            if tag_q in hay:
                filtered.append(t)
        tokens = filtered

    return {
        "source": "easy_screener",
        "enforced": True,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "count": len(tokens),
        "tokens": tokens,
        "attribution": ATTRIBUTION,
    }


def search_tokens(
    query: str,
    limit: int = 10,
    verified_only: bool = True,
    tag: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"error": "Search query is required.", "tokens": []}

    blocked = _screener_gate()
    if blocked:
        return blocked

    limit = max(1, min(int(limit), 20))
    result = screener_search(query, limit=limit)
    if result.get("error"):
        return result

    tokens = result.get("tokens") or []
    if verified_only:
        tokens = [t for t in tokens if t.get("is_verified")]

    tag_q = (tag or category or "").strip().lower()
    if tag_q:
        filtered = []
        for t in tokens:
            tags = [str(x).lower() for x in (t.get("tags") or [])]
            hay = " ".join(
                [str(t.get("symbol") or ""), str(t.get("name") or ""), " ".join(tags)]
            ).lower()
            if tag_q in hay:
                filtered.append(t)
        tokens = filtered or tokens

    if not tokens:
        listed = list_verified_kickstart_tokens(active_only=verified_only)
        tokens = listed.get("tokens") or []

    return {
        "query": query,
        "source": "easy_screener",
        "count": min(len(tokens), limit),
        "tokens": tokens[:limit],
        "attribution": ATTRIBUTION,
        "note": "Only EasyA Kickstart tokens indexed by EASY Screener are returned.",
    }


def get_token_overview(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    summary = bundle.get("summary") or {}
    return {
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "mint": row.get("mint"),
        "blockchain": row.get("chain") or "Solana",
        "cluster": SOLANA_CLUSTER,
        "verified": row.get("is_verified"),
        "price_usd": row.get("price_usd"),
        "market_cap_usd": row.get("market_cap_usd"),
        "liquidity_usd": row.get("liquidity_usd"),
        "fdv_usd": row.get("fdv_usd"),
        "holder_count": row.get("holder_count"),
        "volume_24h_usd": row.get("volume_24h_usd"),
        "tags": row.get("tags") or [],
        "created_at": row.get("created_at"),
        "dex": row.get("dex"),
        "links": {
            "website": row.get("website"),
            "twitter": row.get("twitter"),
            "telegram": row.get("telegram"),
            "github": row.get("github"),
            "explorer": f"https://solscan.io/token/{row.get('mint')}",
        },
        "ai_summary": summary,
        "locked_supply": bundle.get("locked_supply"),
        "attribution": ATTRIBUTION,
    }


def get_token_analytics(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    return {
        "symbol": row.get("symbol"),
        "mint": row.get("mint"),
        "price_usd": row.get("price_usd"),
        "market_cap_usd": row.get("market_cap_usd"),
        "liquidity_usd": row.get("liquidity_usd"),
        "fdv_usd": row.get("fdv_usd"),
        "holder_count": row.get("holder_count"),
        "volume_24h_usd": row.get("volume_24h_usd"),
        "price_change_5m_pct": row.get("price_change_5m_pct"),
        "price_change_1h_pct": row.get("price_change_1h_pct"),
        "price_change_6h_pct": row.get("price_change_6h_pct"),
        "price_change_24h_pct": row.get("price_change_24h_pct"),
        "verified": row.get("is_verified"),
        "attribution": ATTRIBUTION,
        "note": "Null numeric fields mean upstream data is missing — do not treat as zero.",
    }


def get_token_performance(token: str, days: int = 7) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    days = max(1, min(int(days), 30))
    return {
        "symbol": row.get("symbol"),
        "mint": row.get("mint"),
        "lookback_days": days,
        "price_change_5m_pct": row.get("price_change_5m_pct"),
        "price_change_1h_pct": row.get("price_change_1h_pct"),
        "price_change_6h_pct": row.get("price_change_6h_pct"),
        "price_change_24h_pct": row.get("price_change_24h_pct"),
        "liquidity_usd": row.get("liquidity_usd"),
        "volume_24h_usd": row.get("volume_24h_usd"),
        "holder_count": row.get("holder_count"),
        "market_cap_usd": row.get("market_cap_usd"),
        "attribution": ATTRIBUTION,
        "note": "EASY Screener exposes recent price-change windows; summarize trends in plain language.",
    }


def analyze_token_health(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    analytics = get_token_analytics(token)
    risks = detect_token_risks(token)
    risk_items = risks.get("risks") or []
    summary = bundle.get("summary") or {}

    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 50

    if row.get("is_verified"):
        strengths.append("Listed and verified on EASY Screener / EasyA Kickstart")
        score += 10

    liq = row.get("liquidity_usd")
    if liq is not None:
        if liq >= 50_000:
            strengths.append("Meaningful DEX liquidity")
            score += 10
        elif liq < 5_000:
            weaknesses.append("Low liquidity")
            score -= 10

    holders = row.get("holder_count")
    if holders is not None:
        if holders >= 1000:
            strengths.append("Broad holder base")
            score += 8
        elif holders < 100:
            weaknesses.append("Small holder count")
            score -= 8

    trust = summary.get("trustScore") or summary.get("githubTrustScore")
    if isinstance(trust, (int, float)):
        if trust >= 70:
            strengths.append(f"Strong EASY Screener trust score ({trust})")
            score += 8
        elif trust < 40:
            weaknesses.append(f"Low EASY Screener trust score ({trust})")
            score -= 8

    locked = bundle.get("locked_supply") or {}
    pct_locked = locked.get("percentLocked") or locked.get("lockedPercent")
    if pct_locked is not None:
        if float(pct_locked) >= 80:
            strengths.append(f"High locked supply ({pct_locked}%)")
            score += 8
        elif float(pct_locked) < 20:
            weaknesses.append(f"Low locked supply ({pct_locked}%)")
            score -= 6

    for r in risk_items:
        if r.get("severity") == "high":
            weaknesses.append(r.get("title", "High severity risk"))
            score -= 12
        elif r.get("severity") == "medium":
            weaknesses.append(r.get("title", "Medium risk"))
            score -= 5

    if not any(r.get("severity") == "high" for r in risk_items):
        strengths.append("No critical red flags in EASY Screener diligence data")

    vol = row.get("volume_24h_usd")
    if vol is not None and liq is not None and vol < 1_000 and liq > 0:
        weaknesses.append("Low 24h trading volume")

    if not row.get("website"):
        weaknesses.append("Limited public website link on EASY Screener")

    score = max(0, min(100, score))
    return {
        "symbol": row.get("symbol"),
        "mint": row.get("mint"),
        "strengths": strengths or ["Insufficient data for strengths"],
        "weaknesses": weaknesses or ["No major weaknesses flagged from available data"],
        "overall_health_score": score,
        "analytics_snapshot": analytics,
        "easya_summary": summary,
        "risks": risk_items,
        "attribution": ATTRIBUTION,
    }


def get_improvement_suggestions(token: str) -> dict[str, Any]:
    health = analyze_token_health(token)
    if health.get("error"):
        return health
    suggestions = []
    for w in health.get("weaknesses") or []:
        wl = w.lower()
        if "liquidity" in wl:
            suggestions.append("Add or deepen DEX liquidity and publish lock proof on EASY Screener.")
        if "holder" in wl:
            suggestions.append("Run community campaigns and improve token utility to grow holders.")
        if "volume" in wl:
            suggestions.append("Increase market making visibility, DEX incentives, or partnerships.")
        if "website" in wl or "documentation" in wl:
            suggestions.append("Publish docs and verified social links on your Kickstart profile.")
        if "lock" in wl:
            suggestions.append("Increase Streamflow lock coverage and link proof on EASY Screener.")
        if "trust" in wl:
            suggestions.append("Improve GitHub activity and transparency to raise EASY Screener trust score.")
    if not suggestions:
        suggestions.append("Maintain transparency: keep liquidity locked, docs updated, and metrics public.")
    return {
        "symbol": health.get("symbol"),
        "mint": health.get("mint"),
        "health_score": health.get("overall_health_score"),
        "suggestions": list(dict.fromkeys(suggestions)),
        "attribution": ATTRIBUTION,
    }


def detect_token_risks(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    risks: list[dict[str, Any]] = []

    liq = row.get("liquidity_usd")
    if liq is not None and liq < 5_000:
        risks.append({
            "severity": "medium",
            "title": "Low liquidity",
            "detail": "Large trades may cause high slippage; exit risk elevated.",
        })

    locked = bundle.get("locked_supply") or {}
    pct_locked = locked.get("percentLocked") or locked.get("lockedPercent")
    if pct_locked is not None and float(pct_locked) < 50:
        risks.append({
            "severity": "medium",
            "title": "Low locked supply",
            "detail": f"Only {pct_locked}% locked per EASY Screener Streamflow data.",
        })

    if row.get("is_verified") is False:
        risks.append({
            "severity": "low",
            "title": "Not verified on EASY Screener",
            "detail": "Extra diligence recommended for unverified Kickstart listings.",
        })

    summary = bundle.get("summary") or {}
    trust = summary.get("trustScore") or summary.get("githubTrustScore")
    if isinstance(trust, (int, float)) and trust < 35:
        risks.append({
            "severity": "medium",
            "title": "Low EASY Screener trust score",
            "detail": f"Trust score {trust}/100 — review AI + GitHub diligence summary.",
        })

    return {
        "symbol": row.get("symbol"),
        "mint": row.get("mint"),
        "risks": risks,
        "attribution": ATTRIBUTION,
    }


def compare_tokens(tokens: list[str]) -> dict[str, Any]:
    if not tokens or len(tokens) < 2:
        return {"error": "Provide at least two EasyA Kickstart tokens to compare (symbols or mints)."}
    rows = []
    for t in tokens[:5]:
        overview = get_token_overview(t)
        if overview.get("error"):
            return overview
        rows.append(overview)
    return {"count": len(rows), "comparison": rows, "attribution": ATTRIBUTION}


def get_operation_guide(operation: str) -> dict[str, Any]:
    key = (operation or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "burn": "burn_tokens",
        "lock": "lock_liquidity",
        "relock": "relock_liquidity",
        "migrate": "migrate_liquidity",
        "verify": "verify_contract",
        "ownership": "transfer_ownership",
        "renounce": "renounce_ownership",
        "vesting": "vesting",
        "stake": "staking",
        "staking": "staking",
        "treasury": "treasury",
    }
    key = aliases.get(key, key)
    guide = OPERATION_GUIDES.get(key)
    if not guide:
        return {
            "error": f"Unknown operation '{operation}'.",
            "available": sorted(OPERATION_GUIDES.keys()),
        }
    return {"operation": key, **guide}


def recommend_tools(task: str) -> dict[str, Any]:
    task_key = (task or "").strip().lower().replace(" ", "_")
    matches = []
    for category, tools in TOOL_RECOMMENDATIONS.items():
        if task_key in category or category in task_key:
            matches.append({"category": category, "tools": tools})
    if not matches:
        for category, tools in TOOL_RECOMMENDATIONS.items():
            if any(word in category for word in task_key.split("_") if len(word) > 3):
                matches.append({"category": category, "tools": tools})
    if not matches:
        return {
            "task": task,
            "recommendations": [
                {"category": k, "tools": v} for k, v in list(TOOL_RECOMMENDATIONS.items())[:5]
            ],
            "note": "No exact match; showing common Kickstart tool categories.",
        }
    return {"task": task, "recommendations": matches}


def answer_token_faq(token: str, question: Optional[str] = None) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    row = _row(bundle)
    locked = bundle.get("locked_supply") or {}
    summary = bundle.get("summary") or {}
    pct_locked = locked.get("percentLocked") or locked.get("lockedPercent")
    faq = {
        "listed_on_easy_screener": row.get("is_verified"),
        "liquidity_locked": (
            f"{pct_locked}% locked (Streamflow via EASY Screener)"
            if pct_locked is not None
            else "See locked_supply in EASY Screener response"
        ),
        "documentation": row.get("website"),
        "contact_team": {
            "twitter": row.get("twitter"),
            "telegram": row.get("telegram"),
            "github": row.get("github"),
        },
        "ai_diligence_summary": summary,
        "explorer": f"https://solscan.io/token/{row.get('mint')}",
    }
    return {
        "symbol": row.get("symbol"),
        "mint": row.get("mint"),
        "question": question,
        "faq": faq,
        "attribution": ATTRIBUTION,
    }


def add_to_watchlist(token: str, user_wallet: str) -> dict[str, Any]:
    tok = screener_resolve_token(token)
    if tok.get("error"):
        return tok
    return add_watchlist_token(
        user_wallet,
        tok["mint"],
        tok.get("symbol"),
        tok.get("name"),
    )


def remove_from_watchlist(token: str, user_wallet: str) -> dict[str, Any]:
    tok = screener_resolve_token(token)
    if tok.get("error"):
        return tok
    return remove_watchlist_token(user_wallet, tok["mint"])


def get_watchlist(user_wallet: str) -> dict[str, Any]:
    return list_watchlist(user_wallet)


def compare_watchlist(user_wallet: str) -> dict[str, Any]:
    items = compare_watchlist_tokens(user_wallet)
    if items.get("error"):
        return items
    tokens = [row.get("mint") or row.get("symbol") for row in items.get("watchlist", [])]
    if len(tokens) < 2:
        return {"error": "Add at least two tokens to your watchlist to compare.", "watchlist": items}
    return compare_tokens(tokens)


TOOLS = [
    {"type": "function", "function": {"name": "list_verified_kickstart_tokens", "description": "List EasyA Kickstart verified tokens (the allowlist).", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}, "tag": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "search_tokens", "description": "Discover EasyA verified tokens by keyword, category, or tag.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}, "verified_only": {"type": "boolean"}, "tag": {"type": "string"}, "category": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_token_overview", "description": "Full verified token summary.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "get_token_analytics", "description": "Live price, mcap, liquidity, volume, holders, buy/sell ratio.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "get_token_performance", "description": "Historical performance over N days.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}, "days": {"type": "integer"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "analyze_token_health", "description": "Strengths, weaknesses, and health score /100.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "get_improvement_suggestions", "description": "Actionable recommendations for a token project.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "detect_token_risks", "description": "Flag whale concentration, mint authority, liquidity risks, etc.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "compare_tokens", "description": "Side-by-side comparison of 2-5 tokens.", "parameters": {"type": "object", "properties": {"tokens": {"type": "array", "items": {"type": "string"}}}, "required": ["tokens"]}}},
    {"type": "function", "function": {"name": "get_operation_guide", "description": "Explain token ops: burn, lock liquidity, vesting, etc.", "parameters": {"type": "object", "properties": {"operation": {"type": "string"}}, "required": ["operation"]}}},
    {"type": "function", "function": {"name": "recommend_tools", "description": "Recommend tools for a task.", "parameters": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}}},
    {"type": "function", "function": {"name": "answer_token_faq", "description": "Answer common FAQ for a token.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}, "question": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "add_to_watchlist", "description": "Add token to user watchlist.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}, "user_wallet": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "remove_from_watchlist", "description": "Remove token from watchlist.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}, "user_wallet": {"type": "string"}}, "required": ["token"]}}},
    {"type": "function", "function": {"name": "get_watchlist", "description": "List user watchlist tokens.", "parameters": {"type": "object", "properties": {"user_wallet": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "compare_watchlist", "description": "Compare all tokens on user watchlist.", "parameters": {"type": "object", "properties": {"user_wallet": {"type": "string"}}, "required": []}}},
]

TOOL_MAP = {
    "list_verified_kickstart_tokens": list_verified_kickstart_tokens,
    "search_tokens": search_tokens,
    "get_token_overview": get_token_overview,
    "get_token_analytics": get_token_analytics,
    "get_token_performance": get_token_performance,
    "analyze_token_health": analyze_token_health,
    "get_improvement_suggestions": get_improvement_suggestions,
    "detect_token_risks": detect_token_risks,
    "compare_tokens": compare_tokens,
    "get_operation_guide": get_operation_guide,
    "recommend_tools": recommend_tools,
    "answer_token_faq": answer_token_faq,
    "add_to_watchlist": add_to_watchlist,
    "remove_from_watchlist": remove_from_watchlist,
    "get_watchlist": get_watchlist,
    "compare_watchlist": compare_watchlist,
}

WALLET_SCOPED = {
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_watchlist",
    "compare_watchlist",
}

SYSTEM_PROMPT = """You are **EasyA Analysis Agent** on Solana — free research for **EasyA Kickstart tokens on EASY Screener**.

## Data source
- Live market, lock, and diligence data from **EASY Screener** (easyscreener.xyz).
- Token bundles are cached server-side for 1 hour per mint — reuse tool results within a conversation.
- **Attribute EASY Screener** when publishing derived analysis.
- Numeric nulls mean missing upstream data — never treat null as zero.

## Pricing
- **Free** for authenticated users (wallet sign-in required).
- You do **not** execute on-chain transactions.

## Scope (STRICT)
- Only discuss tokens indexed by EASY Screener / EasyA Kickstart.
- If a token is NOT_FOUND on EASY Screener, refuse and suggest list_verified_kickstart_tokens.
- Never discuss JUP, BONK, or other non-Kickstart tokens.

## Capabilities
- Discovery (list_verified_kickstart_tokens, search_tokens)
- Overview, analytics, performance, health, risks, improvements, FAQ
- Operations guidance & tool recommendations
- Watchlist helpers

## Rules
- **Always call tools** — never invent prices, holder counts, or trust scores.
- Summarize trends in plain language.
- End with: "Not financial advice. DYOR."
""" + GOVERNANCE_PROMPT


def build_system_prompt() -> str:
    return SYSTEM_PROMPT + "\n\n" + get_allowlist_prompt_block()


def call_openrouter(messages: list) -> dict[str, Any]:
    payload = {
        "model": KICKSTART_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.3,
    }
    last_error = "Unknown OpenRouter error"
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                OPEN_ROUTER_API_URL,
                json=payload,
                headers=_openrouter_headers(),
                timeout=180,
            )
        except requests.exceptions.RequestException as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"Cannot reach OpenRouter API: {last_error}") from exc
        if resp.status_code >= 400:
            last_error = resp.text or resp.reason
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"OpenRouter API error ({resp.status_code}): {last_error}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter returned no choices.")
        return choices[0]
    raise RuntimeError(last_error)


def execute_tool(
    tool_name: str,
    tool_args: dict,
    user_wallet: Optional[str] = None,
) -> str:
    func = TOOL_MAP.get(tool_name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        args = dict(tool_args or {})
        if tool_name in WALLET_SCOPED:
            if not user_wallet:
                return json.dumps({"error": "Wallet authentication required for watchlist actions."})
            args["user_wallet"] = user_wallet
        return json.dumps(func(**args), indent=2)
    except TypeError as exc:
        return json.dumps({"error": str(exc), "received_args": tool_args})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def run_kickstart_agent(
    user_input: str,
    conversation_history: list,
    user_wallet: Optional[str] = None,
) -> tuple[str, list, list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    prompt = user_input.strip()
    if user_wallet:
        prompt = f"[Connected user wallet: {user_wallet}]\n{prompt}"
    conversation_history.append({"role": "user", "content": prompt})
    messages = [{"role": "system", "content": build_system_prompt()}] + conversation_history

    for i in range(12):
        response = call_openrouter(messages)
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            reply = message.get("content") or ""
            conversation_history.append({"role": "assistant", "content": reply})
            return reply, conversation_history, actions

        messages.append({
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(name, args, user_wallet=user_wallet)
            actions.append({"tool": name, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", f"call_{i}"),
                "content": result,
            })

    reply = "I hit the tool loop limit. Please narrow your question and try again."
    conversation_history.append({"role": "assistant", "content": reply})
    return reply, conversation_history, actions
