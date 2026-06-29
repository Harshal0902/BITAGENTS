"""
EasyA Analysis Agent - Solana token discovery, analytics, and guidance.

Free for users (wallet sign-in required). Powered by OpenRouter + Jupiter/DexScreener data.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

from dca_agent import (
    HEADERS,
    JUPITER_TOKENS_API,
    OPEN_ROUTER_API,
    OPEN_ROUTER_API_URL,
    OPEN_ROUTER_APP_NAME,
    OPEN_ROUTER_SITE_URL,
    SOLANA_CLUSTER,
    _fetch_token_from_jupiter,
    _jupiter_get,
    resolve_token,
    sol_rpc,
)
from db import (
    add_watchlist_token,
    compare_watchlist_tokens,
    list_watchlist,
    remove_watchlist_token,
)
from kickstart_token_registry import (
    active_verified_tokens,
    find_verified_token,
    get_allowlist_prompt_block,
    list_verified_kickstart_tokens,
    merge_registry_metadata,
    registry_is_enforced,
    require_verified_token,
)
from shared_governance import GOVERNANCE_PROMPT

KICKSTART_MODEL = os.environ.get(
    "KICKSTART_COPILOT_MODEL",
    os.environ.get("OPEN_ROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
)
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

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
    "analytics": ["Birdeye", "DexScreener", "EasyA Kickstart Copilot"],
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
        "X-Title": f"{OPEN_ROUTER_APP_NAME} Kickstart Copilot",
    }


def _dexscreener_token(mint: str) -> dict[str, Any]:
    try:
        r = requests.get(f"{DEXSCREENER_API}/tokens/{mint}", headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return {}
        pairs = r.json().get("pairs") or []
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        if not sol_pairs:
            sol_pairs = pairs
        if not sol_pairs:
            return {}
        sol_pairs.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
        return sol_pairs[0]
    except Exception:
        return {}


def _jupiter_token_detail(mint: str) -> dict[str, Any]:
    try:
        resp = _jupiter_get(f"{JUPITER_TOKENS_API}/search", {"query": mint})
        if resp.status_code != 200:
            return {}
        items = resp.json()
        if not isinstance(items, list):
            return {}
        for item in items:
            if item.get("id") == mint:
                return item
        return items[0] if items else {}
    except Exception:
        return {}


def _mint_authorities(mint: str) -> dict[str, Any]:
    try:
        result = sol_rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        value = (result or {}).get("value")
        if not value:
            return {}
        parsed = value.get("data", {}).get("parsed", {}).get("info", {})
        return {
            "mint_authority": parsed.get("mintAuthority"),
            "freeze_authority": parsed.get("freezeAuthority"),
            "supply_raw": parsed.get("supply"),
            "decimals": parsed.get("decimals"),
            "is_initialized": parsed.get("isInitialized"),
        }
    except Exception:
        return {}


def _token_bundle(token: str) -> dict[str, Any]:
    gate = require_verified_token(token)
    if gate.get("error"):
        return gate
    registry_entry = gate.get("registry")

    lookup = token
    if registry_entry:
        lookup = registry_entry.get("mint") or registry_entry.get("symbol") or token

    tok = resolve_token(str(lookup))
    if tok.get("error"):
        return tok
    mint = tok["mint"]
    jup = _jupiter_token_detail(mint)
    pair = _dexscreener_token(mint)
    authorities = _mint_authorities(mint)

    if jup:
        tok.setdefault("name", jup.get("name"))
        tok.setdefault("usd_price", jup.get("usdPrice"))
        tok["jupiter"] = {
            "verified": jup.get("isVerified"),
            "holder_count": jup.get("holderCount"),
            "organic_score": jup.get("organicScore"),
            "tags": jup.get("tags") or [],
            "mcap": jup.get("mcap"),
            "fdv": jup.get("fdv"),
            "liquidity": jup.get("liquidity"),
            "stats24h": jup.get("stats24h"),
            "stats7d": jup.get("stats7d"),
            "audit": jup.get("audit"),
            "website": jup.get("website"),
            "twitter": jup.get("twitter"),
            "telegram": jup.get("telegram"),
            "discord": jup.get("discord"),
            "coingecko_id": jup.get("coingeckoId"),
        }

    if pair:
        liq = pair.get("liquidity") or {}
        vol = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        h24 = txns.get("h24") or {}
        tok["market"] = {
            "price_usd": pair.get("priceUsd"),
            "market_cap_usd": pair.get("marketCap"),
            "fdv_usd": pair.get("fdv"),
            "liquidity_usd": liq.get("usd"),
            "volume_24h_usd": vol.get("h24"),
            "volume_6h_usd": vol.get("h6"),
            "price_change_24h_pct": (pair.get("priceChange") or {}).get("h24"),
            "price_change_7d_pct": (pair.get("priceChange") or {}).get("h7d"),
            "buys_24h": h24.get("buys"),
            "sells_24h": h24.get("sells"),
            "dex": pair.get("dexId"),
            "pair_url": pair.get("url"),
            "pair_created_at": pair.get("pairCreatedAt"),
        }

    tok["authorities"] = authorities
    if registry_entry:
        merge_registry_metadata(tok, registry_entry)
    return tok


def search_tokens(
    query: str,
    limit: int = 10,
    verified_only: bool = False,
    tag: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"error": "Search query is required.", "tokens": []}
    limit = max(1, min(int(limit), 25))

    if registry_is_enforced():
        listed = list_verified_kickstart_tokens(
            category=category,
            tag=tag,
            active_only=True,
            query=query,
        )
        tokens = listed.get("tokens") or []
        if not tokens:
            listed = list_verified_kickstart_tokens(active_only=True)
            tokens = listed.get("tokens") or []
        return {
            "query": query,
            "source": "easya_kickstart_registry",
            "enforced": True,
            "count": min(len(tokens), limit),
            "tokens": tokens[:limit],
            "note": "Results are limited to EasyA Kickstart verified projects only.",
        }

    try:
        resp = _jupiter_get(f"{JUPITER_TOKENS_API}/search", {"query": query})
        if resp.status_code != 200:
            return {"error": f"Token search failed ({resp.status_code}).", "tokens": []}
        items = resp.json()
        if not isinstance(items, list):
            return {"error": "Unexpected search response.", "tokens": []}
    except Exception as exc:
        return {"error": str(exc), "tokens": []}

    tag_lower = (tag or "").strip().lower()
    results = []
    for item in items:
        if verified_only and not item.get("isVerified"):
            continue
        tags = [str(t).lower() for t in (item.get("tags") or [])]
        if tag_lower and tag_lower not in tags and tag_lower not in (item.get("name") or "").lower():
            if tag_lower not in (item.get("symbol") or "").lower():
                continue
        results.append({
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "mint": item.get("id"),
            "verified": item.get("isVerified"),
            "usd_price": item.get("usdPrice"),
            "mcap": item.get("mcap"),
            "liquidity": item.get("liquidity"),
            "holder_count": item.get("holderCount"),
            "tags": item.get("tags") or [],
        })
        if len(results) >= limit:
            break
    return {
        "query": query,
        "source": "jupiter",
        "enforced": False,
        "count": len(results),
        "tokens": results,
    }


def get_token_overview(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    jup = bundle.get("jupiter") or {}
    market = bundle.get("market") or {}
    registry = bundle.get("registry") or {}
    return {
        "symbol": bundle.get("symbol"),
        "name": registry.get("name") or bundle.get("name"),
        "mint": bundle.get("mint"),
        "blockchain": "Solana",
        "cluster": SOLANA_CLUSTER,
        "easya_verified": bundle.get("easya_verified", False),
        "verified": bundle.get("easya_verified") or jup.get("verified"),
        "category": registry.get("category"),
        "description": registry.get("description"),
        "launch_date": registry.get("launch_date"),
        "price_usd": market.get("price_usd") or bundle.get("usd_price"),
        "market_cap_usd": market.get("market_cap_usd") or jup.get("mcap"),
        "liquidity_usd": market.get("liquidity_usd") or jup.get("liquidity"),
        "fdv_usd": market.get("fdv_usd") or jup.get("fdv"),
        "holder_count": jup.get("holder_count"),
        "tags": registry.get("tags") or jup.get("tags") or [],
        "links": {
            "website": registry.get("website") or jup.get("website"),
            "docs": registry.get("docs"),
            "twitter": registry.get("twitter") or jup.get("twitter"),
            "telegram": registry.get("telegram") or jup.get("telegram"),
            "discord": registry.get("discord") or jup.get("discord"),
            "dex_pair": market.get("pair_url"),
            "explorer": f"https://solscan.io/token/{bundle.get('mint')}",
        },
        "authorities": bundle.get("authorities"),
    }


def get_token_analytics(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    jup = bundle.get("jupiter") or {}
    market = bundle.get("market") or {}
    stats24 = jup.get("stats24h") or {}
    stats7 = jup.get("stats7d") or {}
    buys = market.get("buys_24h") or 0
    sells = market.get("sells_24h") or 0
    buy_sell_ratio = round(buys / sells, 2) if sells else None
    return {
        "symbol": bundle.get("symbol"),
        "mint": bundle.get("mint"),
        "price_usd": market.get("price_usd") or bundle.get("usd_price"),
        "market_cap_usd": market.get("market_cap_usd") or jup.get("mcap"),
        "liquidity_usd": market.get("liquidity_usd") or jup.get("liquidity"),
        "fdv_usd": market.get("fdv_usd") or jup.get("fdv"),
        "holder_count": jup.get("holder_count"),
        "volume_24h_usd": market.get("volume_24h_usd") or stats24.get("volumeChange"),
        "volume_7d_proxy": stats7,
        "supply": {
            "total_raw": (bundle.get("authorities") or {}).get("supply_raw"),
            "decimals": bundle.get("decimals"),
        },
        "trading": {
            "buys_24h": buys,
            "sells_24h": sells,
            "buy_sell_ratio_24h": buy_sell_ratio,
            "price_change_24h_pct": market.get("price_change_24h_pct"),
            "price_change_7d_pct": market.get("price_change_7d_pct"),
        },
        "organic_score": jup.get("organic_score"),
        "verified": jup.get("verified"),
    }


def get_token_performance(token: str, days: int = 7) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    market = bundle.get("market") or {}
    jup = bundle.get("jupiter") or {}
    days = max(1, min(int(days), 30))
    return {
        "symbol": bundle.get("symbol"),
        "mint": bundle.get("mint"),
        "lookback_days": days,
        "price_change_24h_pct": market.get("price_change_24h_pct"),
        "price_change_7d_pct": market.get("price_change_7d_pct"),
        "liquidity_usd": market.get("liquidity_usd") or jup.get("liquidity"),
        "volume_24h_usd": market.get("volume_24h_usd"),
        "holder_count": jup.get("holder_count"),
        "market_cap_usd": market.get("market_cap_usd") or jup.get("mcap"),
        "stats24h": jup.get("stats24h"),
        "stats7d": jup.get("stats7d"),
        "note": (
            "Summarize trends in plain language. Holder history requires indexed data; "
            "use current holder_count and volume/liquidity changes as proxies."
        ),
    }


def analyze_token_health(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    analytics = get_token_analytics(token)
    risks = detect_token_risks(token)
    risk_items = risks.get("risks") or []

    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 50

    if bundle.get("jupiter", {}).get("verified"):
        strengths.append("Verified on Jupiter token list")
        score += 10
    liq = float(analytics.get("liquidity_usd") or 0)
    if liq >= 50_000:
        strengths.append("Meaningful DEX liquidity")
        score += 10
    elif liq < 5_000:
        weaknesses.append("Low liquidity")
        score -= 10

    holders = int(analytics.get("holder_count") or 0)
    if holders >= 1000:
        strengths.append("Broad holder base")
        score += 8
    elif holders < 100:
        weaknesses.append("Small holder count")
        score -= 8

    if not any(r.get("severity") == "high" for r in risk_items):
        strengths.append("No critical on-chain red flags detected")
        score += 5
    for r in risk_items:
        if r.get("severity") == "high":
            weaknesses.append(r.get("title", "High severity risk"))
            score -= 12
        elif r.get("severity") == "medium":
            weaknesses.append(r.get("title", "Medium risk"))
            score -= 5

    vol = float(analytics.get("volume_24h_usd") or 0)
    if vol < 1_000 and liq > 0:
        weaknesses.append("Declining or low trading volume")
        score -= 5

    if not (bundle.get("jupiter") or {}).get("website"):
        weaknesses.append("Limited public documentation / website")
        score -= 3

    score = max(0, min(100, score))
    return {
        "symbol": bundle.get("symbol"),
        "mint": bundle.get("mint"),
        "strengths": strengths or ["Insufficient data for strengths"],
        "weaknesses": weaknesses or ["No major weaknesses flagged from available data"],
        "overall_health_score": score,
        "analytics_snapshot": analytics,
        "risks": risk_items,
    }


def get_improvement_suggestions(token: str) -> dict[str, Any]:
    health = analyze_token_health(token)
    if health.get("error"):
        return health
    suggestions = []
    for w in health.get("weaknesses") or []:
        wl = w.lower()
        if "liquidity" in wl:
            suggestions.append("Add or deepen DEX liquidity and consider locking LP tokens.")
        if "holder" in wl:
            suggestions.append("Run community campaigns and improve token utility to grow holders.")
        if "volume" in wl:
            suggestions.append("Increase market making visibility, CEX/DEX incentives, or partnerships.")
        if "documentation" in wl or "website" in wl:
            suggestions.append("Publish docs, litepaper, and verified links on Jupiter/EasyA profile.")
        if "mint" in wl or "authority" in wl:
            suggestions.append("Renounce mint authority or document treasury mint policy transparently.")
        if "concentration" in wl or "whale" in wl:
            suggestions.append("Encourage wider distribution; consider vesting for team/insider wallets.")
    if not suggestions:
        suggestions.append("Maintain transparency: keep liquidity locked, docs updated, and metrics public.")
    return {
        "symbol": health.get("symbol"),
        "mint": health.get("mint"),
        "health_score": health.get("overall_health_score"),
        "suggestions": list(dict.fromkeys(suggestions)),
    }


def detect_token_risks(token: str) -> dict[str, Any]:
    bundle = _token_bundle(token)
    if bundle.get("error"):
        return bundle
    risks: list[dict[str, Any]] = []
    auth = bundle.get("authorities") or {}
    if auth.get("mint_authority"):
        risks.append({
            "severity": "high",
            "title": "Mint authority still enabled",
            "detail": "Supply can be increased unless policy is documented and trusted.",
        })
    if auth.get("freeze_authority"):
        risks.append({
            "severity": "medium",
            "title": "Freeze authority enabled",
            "detail": "Accounts could be frozen by the authority holder.",
        })
    market = bundle.get("market") or {}
    liq = float(market.get("liquidity_usd") or 0)
    if liq < 5_000:
        risks.append({
            "severity": "medium",
            "title": "Low liquidity",
            "detail": "Large trades may cause high slippage; exit risk elevated.",
        })
    sells = int(market.get("sells_24h") or 0)
    buys = int(market.get("buys_24h") or 0)
    if sells > buys * 2 and sells > 20:
        risks.append({
            "severity": "medium",
            "title": "Heavy sell pressure (24h)",
            "detail": f"Sells ({sells}) materially exceed buys ({buys}) in the last 24h.",
        })
    if not (bundle.get("jupiter") or {}).get("verified"):
        risks.append({
            "severity": "low",
            "title": "Not Jupiter-verified",
            "detail": "Extra diligence recommended for unverified tokens.",
        })
    return {"symbol": bundle.get("symbol"), "mint": bundle.get("mint"), "risks": risks}


def compare_tokens(tokens: list[str]) -> dict[str, Any]:
    if not tokens or len(tokens) < 2:
        if registry_is_enforced():
            active = active_verified_tokens()
            if len(active) == 1:
                only = active[0]
                return {
                    "error": (
                        "Only one EasyA Kickstart verified token is configured "
                        f"({only.get('symbol')}). Comparison needs two allowlisted projects."
                    ),
                    "verified_only": True,
                }
        return {"error": "Provide at least two tokens to compare (symbols or mints)."}
    rows = []
    for t in tokens[:5]:
        overview = get_token_overview(t)
        if overview.get("error"):
            return overview
        rows.append(overview)
    return {"count": len(rows), "comparison": rows}


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
    auth = bundle.get("authorities") or {}
    jup = bundle.get("jupiter") or {}
    market = bundle.get("market") or {}
    faq = {
        "can_be_burned": "Any SPL token can be burned by sending to burn address or using burn UI - check your token program.",
        "liquidity_locked": "On-chain LP lock status is not fully indexed here; verify via lock provider proof links.",
        "contract_verified": bool(jup.get("verified")),
        "supports_staking": "Check project docs; not inferable from mint alone.",
        "documentation": jup.get("website"),
        "contact_team": {
            "twitter": jup.get("twitter"),
            "telegram": jup.get("telegram"),
            "discord": jup.get("discord"),
        },
        "mint_authority_renounced": auth.get("mint_authority") is None,
        "freeze_authority_renounced": auth.get("freeze_authority") is None,
        "dex_link": market.get("pair_url"),
    }
    return {
        "symbol": bundle.get("symbol"),
        "mint": bundle.get("mint"),
        "question": question,
        "faq": faq,
    }


def add_to_watchlist(token: str, user_wallet: str) -> dict[str, Any]:
    gate = require_verified_token(token)
    if gate.get("error"):
        return gate
    entry = gate.get("registry") or find_verified_token(token)
    if entry:
        return add_watchlist_token(
            user_wallet,
            entry["mint"],
            entry.get("symbol"),
            entry.get("name"),
        )
    tok = resolve_token(token)
    if tok.get("error"):
        return tok
    return add_watchlist_token(user_wallet, tok["mint"], tok.get("symbol"), tok.get("name"))


def remove_from_watchlist(token: str, user_wallet: str) -> dict[str, Any]:
    tok = resolve_token(token)
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

SYSTEM_PROMPT = """You are **EasyA Analysis Agent** on Solana - a free research assistant for **EasyA Kickstart verified projects only**.

## Pricing
- **Free** for authenticated users (wallet connect + sign-in required).
- You do **not** execute on-chain transactions. Guide users through operations and recommend tools.

## Verified token allowlist (STRICT)
- You may **only** discuss tokens listed in the active EasyA Kickstart allowlist below.
- **Never** discuss, analyze, compare, or recommend tokens outside that list - even if the user insists.
- If asked about another token (e.g. JUP, BONK, SOL meme coins), reply: this copilot only covers EasyA Kickstart verified projects, then name the allowlisted token(s).
- Use **list_verified_kickstart_tokens** before discovery questions.
- For token-specific data, always call the appropriate tool - never invent metrics.

## Capabilities (allowlisted tokens only)
- Verified list & discovery (list_verified_kickstart_tokens, search_tokens)
- Overviews, FAQ, analytics, performance, health, risks, improvements
- Operations guidance (get_operation_guide) & tool recommendations (recommend_tools)
- Watchlist (add_to_watchlist, remove_from_watchlist, get_watchlist)

## Rules
- **Always call tools** for token data. Never invent prices, holder counts, or verification status.
- Summarize trends in plain language - don't dump raw JSON.
- End research answers with: "Not financial advice. DYOR."
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
