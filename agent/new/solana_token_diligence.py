"""Solana token / mint due diligence helpers."""

from __future__ import annotations

from typing import Any, Optional

from dca_agent import SOLANA_CLUSTER, resolve_token, sol_rpc

from easya_screener_client import ATTRIBUTION
from kickstart_copilot_agent import (
    detect_token_risks,
    get_token_analytics,
    get_token_overview,
    get_top_token_holders,
)


def get_mint_authorities(token: str) -> dict[str, Any]:
    resolved = resolve_token(token)
    if "error" in resolved:
        return resolved
    mint = resolved["mint"]
    info = sol_rpc(
        "getAccountInfo",
        [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
    )
    value = (info or {}).get("value")
    if not value:
        return {"error": "Mint account not found on-chain.", "mint": mint}
    parsed = ((value.get("data") or {}).get("parsed") or {}).get("info") or {}
    mint_authority = parsed.get("mintAuthority")
    freeze_authority = parsed.get("freezeAuthority")
    supply = parsed.get("supply")
    decimals = parsed.get("decimals")
    flags: list[str] = []
    if mint_authority:
        flags.append("mint_authority_active")
    else:
        flags.append("mint_authority_renounced")
    if freeze_authority:
        flags.append("freeze_authority_active")
    else:
        flags.append("freeze_authority_renounced")
    return {
        "symbol": resolved.get("symbol"),
        "mint": mint,
        "mint_authority": mint_authority,
        "freeze_authority": freeze_authority,
        "supply": supply,
        "decimals": decimals,
        "flags": flags,
        "cluster": SOLANA_CLUSTER,
    }


def run_due_diligence_report(token: str) -> dict[str, Any]:
    overview = get_token_overview(token)
    if overview.get("error"):
        return overview
    authorities = get_mint_authorities(token)
    analytics = get_token_analytics(token)
    holders = get_top_token_holders(token, limit=5)
    risks_payload = detect_token_risks(token)
    risks = list(risks_payload.get("risks") or [])

    score = 70
    findings: list[str] = []

    if authorities.get("mint_authority"):
        risks.append(
            {
                "severity": "high",
                "title": "Active mint authority",
                "detail": "Supply can still be inflated unless authority is renounced.",
            }
        )
        score -= 20
        findings.append("Mint authority is still set.")
    else:
        findings.append("Mint authority appears renounced.")

    if authorities.get("freeze_authority"):
        risks.append(
            {
                "severity": "high",
                "title": "Active freeze authority",
                "detail": "Token accounts could be frozen by the authority holder.",
            }
        )
        score -= 15
        findings.append("Freeze authority is still set.")
    else:
        findings.append("Freeze authority appears renounced.")

    liq = analytics.get("liquidity_usd")
    if liq is not None and liq < 10_000:
        score -= 10
        findings.append("Liquidity is relatively low.")

    top = (holders.get("top_holders") or [])[:3]
    if top:
        top_pct = sum(float(h.get("percent_of_supply") or 0) for h in top)
        if top_pct > 50:
            risks.append(
                {
                    "severity": "medium",
                    "title": "Concentrated top holders",
                    "detail": f"Top 3 wallets hold ~{top_pct:.1f}% of supply.",
                }
            )
            score -= 10
            findings.append("Holder concentration is elevated among top wallets.")

    if overview.get("verified"):
        score += 5
        findings.append("Listed as verified on EASY Screener.")
    else:
        score -= 5
        findings.append("Not verified on EASY Screener.")

    score = max(0, min(100, score))
    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

    return {
        "symbol": overview.get("symbol"),
        "mint": overview.get("mint"),
        "due_diligence_score": score,
        "grade": grade,
        "findings": findings,
        "authorities": authorities,
        "analytics": analytics,
        "top_holders": top,
        "risks": risks,
        "overview_links": overview.get("links"),
        "attribution": ATTRIBUTION,
        "cluster": SOLANA_CLUSTER,
        "recommendation": (
            "Proceed with caution and size positions conservatively."
            if score < 65
            else "Fundamentals look acceptable for further research; confirm thesis before trading."
        ),
    }
