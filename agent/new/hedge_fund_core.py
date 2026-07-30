"""Covenant-inspired hedge fund core — Solana token portfolio analysis + fee model.

Adapted from https://github.com/asalsali/covenant-hedge-fund (MIT).
Deterministic quant/risk layers + optional LLM macro synthesis in hedge_fund_agent.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from solana_token_onchain import get_onchain_token_research

MANAGEMENT_FEE_RATE = 0.01  # 1% annual (1/10 of classic 2%)
PERFORMANCE_FEE_RATE = 0.10  # 10% of profits (1/2 of classic 20%)

MAX_POSITION_PCT = 0.25
MIN_LIQUIDITY_USD = 5_000.0
BUY_THRESHOLD = 0.30
SELL_THRESHOLD = -0.30


@dataclass
class AnalystSignal:
    analyst: str
    domain: str
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int
    score: float
    reasoning: str


def _clamp_conf(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _score_to_signal(score: float) -> str:
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"


def liquidity_analyst(profile: dict[str, Any]) -> AnalystSignal:
    pool = profile.get("primary_pool") or {}
    liq = float(pool.get("liquidity_usd") or 0)
    vol = float(pool.get("volume_24h_usd") or 0)
    score = 0.0
    reasons: list[str] = []
    if liq >= 100_000:
        score += 0.4
        reasons.append(f"strong TVL ${_fmt(liq)}")
    elif liq >= 25_000:
        score += 0.15
        reasons.append(f"moderate TVL ${_fmt(liq)}")
    elif liq >= MIN_LIQUIDITY_USD:
        score -= 0.1
        reasons.append(f"thin TVL ${_fmt(liq)}")
    else:
        score -= 0.5
        reasons.append("very low liquidity")
    if vol >= 10_000:
        score += 0.2
        reasons.append(f"active 24h vol ${_fmt(vol)}")
    elif vol > 0:
        score += 0.05
    else:
        score -= 0.15
        reasons.append("minimal recent volume")
    return AnalystSignal(
        analyst="liquidity",
        domain="quant",
        signal=_score_to_signal(score),
        confidence=_clamp_conf(abs(score) * 100),
        score=round(score, 3),
        reasoning="; ".join(reasons)[:200] or "liquidity data unavailable",
    )


def safety_analyst(profile: dict[str, Any]) -> AnalystSignal:
    score = 0.0
    reasons: list[str] = []
    if profile.get("mint_authority_renounced"):
        score += 0.35
        reasons.append("mint renounced")
    else:
        score -= 0.45
        reasons.append("active mint authority")
    if profile.get("freeze_authority_renounced"):
        score += 0.25
        reasons.append("freeze renounced")
    else:
        score -= 0.35
        reasons.append("active freeze authority")
    risks = profile.get("risks") or []
    high = sum(1 for r in risks if r.get("severity") == "high")
    if high:
        score -= 0.2 * high
        reasons.append(f"{high} high-severity flags")
    return AnalystSignal(
        analyst="safety",
        domain="quant",
        signal=_score_to_signal(score),
        confidence=_clamp_conf(abs(score) * 90 + 20),
        score=round(score, 3),
        reasoning="; ".join(reasons)[:200],
    )


def concentration_analyst(profile: dict[str, Any]) -> AnalystSignal:
    top3 = profile.get("top3_holder_pct")
    score = 0.0
    reasons: list[str] = []
    if top3 is None:
        return AnalystSignal(
            analyst="concentration",
            domain="quant",
            signal="neutral",
            confidence=20,
            score=0.0,
            reasoning="holder concentration unavailable",
        )
    if top3 < 30:
        score += 0.35
        reasons.append(f"top-3 hold {top3:.1f}% — dispersed")
    elif top3 < 50:
        score += 0.05
        reasons.append(f"top-3 hold {top3:.1f}% — moderate")
    elif top3 < 70:
        score -= 0.25
        reasons.append(f"top-3 hold {top3:.1f}% — concentrated")
    else:
        score -= 0.45
        reasons.append(f"top-3 hold {top3:.1f}% — whale-heavy")
    holders = profile.get("holder_count")
    if holders is not None:
        if holders >= 500:
            score += 0.15
            reasons.append(f"{holders} holders")
        elif holders < 100:
            score -= 0.15
            reasons.append(f"only {holders} holders")
    return AnalystSignal(
        analyst="concentration",
        domain="quant",
        signal=_score_to_signal(score),
        confidence=_clamp_conf(abs(score) * 85 + 25),
        score=round(score, 3),
        reasoning="; ".join(reasons)[:200],
    )


def valuation_analyst(profile: dict[str, Any]) -> AnalystSignal:
    mcap = profile.get("market_cap_usd")
    price = profile.get("price_usd")
    score = 0.0
    reasons: list[str] = []
    if mcap is None or price is None:
        return AnalystSignal(
            analyst="valuation",
            domain="value",
            signal="neutral",
            confidence=15,
            score=0.0,
            reasoning="market cap / price unavailable",
        )
    mcap_f = float(mcap)
    if 1_000_000 <= mcap_f <= 500_000_000:
        score += 0.2
        reasons.append(f"mid/small cap ${_fmt(mcap_f)}")
    elif mcap_f > 1_000_000_000:
        score += 0.05
        reasons.append(f"large cap ${_fmt(mcap_f)}")
    elif mcap_f < 100_000:
        score -= 0.25
        reasons.append(f"micro cap ${_fmt(mcap_f)} — high idiosyncratic risk")
    change = profile.get("change_24h_pct")
    if change is not None:
        ch = float(change)
        if ch > 15:
            score -= 0.2
            reasons.append(f"+{ch:.1f}% 24h — extended")
        elif ch < -15:
            score += 0.1
            reasons.append(f"{ch:.1f}% 24h — potential mean reversion")
    return AnalystSignal(
        analyst="valuation",
        domain="value",
        signal=_score_to_signal(score),
        confidence=_clamp_conf(abs(score) * 70 + 30),
        score=round(score, 3),
        reasoning="; ".join(reasons)[:200],
    )


def run_quant_value_analysts(profile: dict[str, Any]) -> list[AnalystSignal]:
    return [
        liquidity_analyst(profile),
        safety_analyst(profile),
        concentration_analyst(profile),
        valuation_analyst(profile),
    ]


def synthesize_signals(signals: list[AnalystSignal]) -> dict[str, Any]:
    if not signals:
        return {"composite_score": 0.0, "action": "hold", "confidence": 0, "bullish": 0, "bearish": 0, "neutral": 0}
    weighted = 0.0
    weight_sum = 0.0
    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    for sig in signals:
        counts[sig.signal] = counts.get(sig.signal, 0) + 1
        w = max(sig.confidence, 1)
        weighted += sig.score * w
        weight_sum += w
    composite = weighted / weight_sum if weight_sum else 0.0
    if composite >= BUY_THRESHOLD:
        action = "overweight"
    elif composite <= SELL_THRESHOLD:
        action = "underweight"
    else:
        action = "hold"
    return {
        "composite_score": round(composite, 4),
        "action": action,
        "confidence": _clamp_conf(abs(composite) * 100),
        "signal_counts": counts,
    }


def compute_position_limit(portfolio_value_usd: float, profile: dict[str, Any]) -> dict[str, Any]:
    pool = profile.get("primary_pool") or {}
    liq = float(pool.get("liquidity_usd") or 0)
    base_pct = MAX_POSITION_PCT
    if liq < MIN_LIQUIDITY_USD:
        final_pct = min(base_pct, 0.05)
        reason = "liquidity below minimum — cap at 5%"
    elif liq < 25_000:
        final_pct = base_pct * 0.5
        reason = "thin liquidity — halved position cap"
    else:
        risks = profile.get("risks") or []
        high_risk = any(r.get("severity") == "high" for r in risks)
        final_pct = base_pct * 0.5 if high_risk else base_pct
        reason = "authority risk — halved cap" if high_risk else "standard risk budget"
    max_notional = portfolio_value_usd * final_pct
    return {
        "max_allocation_pct": round(final_pct * 100, 2),
        "max_notional_usd": round(max_notional, 2),
        "reason": reason,
    }


def calculate_fees(
    aum_usd: float,
    profit_usd: float = 0.0,
    months: float = 12.0,
    high_water_mark: float = 0.0,
) -> dict[str, Any]:
    aum = max(0.0, float(aum_usd))
    profit = float(profit_usd)
    months = max(0.0, float(months))
    hwm = max(0.0, float(high_water_mark))

    management_fee = aum * MANAGEMENT_FEE_RATE * (months / 12.0)
    taxable_profit = max(0.0, profit - hwm)
    performance_fee = taxable_profit * PERFORMANCE_FEE_RATE
    total_fees = management_fee + performance_fee
    net_profit = profit - total_fees

    return {
        "fee_model": "1/10",
        "management_fee_rate_annual_pct": MANAGEMENT_FEE_RATE * 100,
        "performance_fee_rate_pct": PERFORMANCE_FEE_RATE * 100,
        "traditional_comparison": "vs 2/20 (2% mgmt + 20% performance)",
        "aum_usd": round(aum, 2),
        "profit_usd": round(profit, 2),
        "high_water_mark_usd": round(hwm, 2),
        "taxable_profit_usd": round(taxable_profit, 2),
        "management_fee_usd": round(management_fee, 2),
        "performance_fee_usd": round(performance_fee, 2),
        "total_fees_usd": round(total_fees, 2),
        "net_profit_after_fees_usd": round(net_profit, 2),
        "months": months,
    }


def analyze_token_for_portfolio(token: str, portfolio_value_usd: float = 10_000.0) -> dict[str, Any]:
    profile = get_onchain_token_research(token)
    if profile.get("error") or not profile.get("mint"):
        return {"token": token, "error": profile.get("error", "Could not resolve token"), "needs_mint_address": True}

    signals = run_quant_value_analysts(profile)
    synthesis = synthesize_signals(signals)
    limits = compute_position_limit(portfolio_value_usd, profile)
    suggested_usd = limits["max_notional_usd"]
    if synthesis["action"] == "underweight":
        suggested_usd = 0.0
    elif synthesis["action"] == "hold":
        suggested_usd = round(suggested_usd * 0.5, 2)

    return {
        "token": profile.get("symbol") or token,
        "mint": profile.get("mint"),
        "profile_summary": {
            "price_usd": profile.get("price_usd"),
            "market_cap_usd": profile.get("market_cap_usd"),
            "liquidity_usd": (profile.get("primary_pool") or {}).get("liquidity_usd"),
            "holder_count": profile.get("holder_count"),
        },
        "analyst_signals": [s.__dict__ for s in signals],
        "synthesis": synthesis,
        "position_limit": limits,
        "suggested_allocation_usd": suggested_usd,
        "compliance": {
            "max_single_name_pct": MAX_POSITION_PCT * 100,
            "min_liquidity_usd": MIN_LIQUIDITY_USD,
        },
    }


def run_portfolio_analysis(tokens: list[str], capital_usd: float = 10_000.0) -> dict[str, Any]:
    capital = max(100.0, float(capital_usd))
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in tokens[:8]:
        row = analyze_token_for_portfolio(raw.strip(), portfolio_value_usd=capital)
        if row.get("error"):
            errors.append(f"{raw}: {row.get('error')}")
        else:
            rows.append(row)

    total_suggested = sum(float(r.get("suggested_allocation_usd") or 0) for r in rows)
    overweight = [r["token"] for r in rows if r.get("synthesis", {}).get("action") == "overweight"]
    underweight = [r["token"] for r in rows if r.get("synthesis", {}).get("action") == "underweight"]

    return {
        "capital_usd": capital,
        "tokens_analyzed": len(rows),
        "positions": rows,
        "portfolio_summary": {
            "total_suggested_allocation_usd": round(total_suggested, 2),
            "cash_remaining_usd": round(max(0.0, capital - total_suggested), 2),
            "overweight_candidates": overweight,
            "underweight_avoid": underweight,
            "deployment_pct": round((total_suggested / capital) * 100, 2) if capital else 0,
        },
        "fee_structure": get_fee_structure(),
        "errors": errors,
        "governance": "Covenant-inspired: deterministic quant/value signals, code-enforced position limits, LLM macro layer optional.",
    }


def get_fee_structure() -> dict[str, Any]:
    return {
        "name": "BIT Agents Hedge Fund — 1/10 model",
        "management_fee_annual_pct": MANAGEMENT_FEE_RATE * 100,
        "performance_fee_pct": PERFORMANCE_FEE_RATE * 100,
        "traditional_2_20": {"management_pct": 2.0, "performance_pct": 20.0},
        "description": (
            "1% annual management fee on assets under management, plus 10% of net profits "
            "above the high-water mark. Half the cost of the traditional 2/20 hedge fund fee stack."
        ),
        "example_100k_12mo": calculate_fees(100_000, profit_usd=15_000, months=12),
    }


def _fmt(value: float) -> str:
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:.2f}"
