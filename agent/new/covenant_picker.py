"""
Horizon-aware asset selection — no fixed DEFAULT book.

Two-pass rank:
1) Fast price features for the liquid universe
2) Full 18-analyst + news on the top shortlist
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from covenant_analysts import run_all_analysts, synthesize_signals
from covenant_features import closes_from_prices, compute_features
from yahoo_market_data import (
    CANDIDATE_UNIVERSE,
    fetch_yahoo_daily_prices,
    fetch_yahoo_news,
    resolve_yahoo_asset,
)

HORIZON_PRESETS = {
    "ultra_short": {"days": 7, "lookback": 60, "prefer": "momentum", "max_names": 4},
    "short": {"days": 30, "lookback": 90, "prefer": "momentum", "max_names": 5},
    "medium": {"days": 90, "lookback": 180, "prefer": "balanced", "max_names": 6},
    "long": {"days": 180, "lookback": 365, "prefer": "value_quality", "max_names": 7},
    "strategic": {"days": 365, "lookback": 400, "prefer": "value_quality", "max_names": 8},
}


def parse_horizon_days(text: str = "", horizon_days: Optional[int] = None) -> int:
    if horizon_days and horizon_days > 0:
        return int(horizon_days)
    import re

    t = text or ""
    m = re.search(
        r"\b(?:for|over|next|within|horizon|trade(?:\s+for)?)\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)\b",
        t,
        re.I,
    )
    if not m:
        m = re.search(r"\b(\d+)\s*(day|days|week|weeks|month|months|year|years)\b", t, re.I)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("day"):
            return max(1, n)
        if unit.startswith("week"):
            return max(1, n * 7)
        if unit.startswith("month"):
            return max(1, n * 30)
        if unit.startswith("year"):
            return max(1, n * 365)
    return 90


def horizon_preset(days: int) -> dict[str, Any]:
    if days <= 10:
        key = "ultra_short"
    elif days <= 45:
        key = "short"
    elif days <= 120:
        key = "medium"
    elif days <= 270:
        key = "long"
    else:
        key = "strategic"
    preset = dict(HORIZON_PRESETS[key])
    preset["key"] = key
    preset["horizon_days"] = days
    return preset


def _tilt(features: dict[str, Any], prefer: str) -> float:
    if prefer == "momentum":
        return 0.002 * float(features.get("ret_21d") or 0) + 0.001 * float(features.get("ret_5d") or 0)
    if prefer == "value_quality":
        return -0.002 * float(features.get("distance_from_high_pct") or 0) - 0.001 * max(
            0.0, float(features.get("vol_63") or 40) - 30
        )
    return 0.001 * float(features.get("alpha_21d") or 0)


def select_assets_for_horizon(
    horizon_days: int = 90,
    max_names: Optional[int] = None,
    allow_crypto: bool = True,
    universe: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
) -> dict[str, Any]:
    preset = horizon_preset(horizon_days)
    lookback = int(preset["lookback"])
    n_take = int(max_names or preset["max_names"])
    prefer = preset["prefer"]
    exclude_set = {s.upper() for s in (exclude or [])}
    candidates = [c for c in (universe or CANDIDATE_UNIVERSE) if c.upper() not in exclude_set]

    end = date.today()
    start = end - timedelta(days=lookback + 5)
    start_s, end_s = start.isoformat(), end.isoformat()

    spy_hist = fetch_yahoo_daily_prices("SPY", start_s, end_s)
    spy_closes = closes_from_prices(spy_hist.get("prices") or []) if not spy_hist.get("error") else []

    # Pass 1 — fast features (no news)
    prelim: list[dict[str, Any]] = []
    errors: list[str] = []
    closes_cache: dict[str, list[float]] = {}
    resolved_cache: dict[str, dict[str, Any]] = {}

    for raw in candidates:
        resolved = resolve_yahoo_asset(raw)
        if resolved.get("error"):
            continue
        if not allow_crypto and resolved.get("asset_class") == "crypto":
            continue
        hist = fetch_yahoo_daily_prices(resolved["yahoo_symbol"], start_s, end_s)
        if hist.get("error"):
            errors.append(f"{resolved['symbol']}: {hist['error']}")
            continue
        closes = closes_from_prices(hist["prices"])
        if len(closes) < 20:
            continue
        features = compute_features(closes, spy_closes=spy_closes or None, news_titles=[])
        if features.get("error"):
            continue
        # Cheap composite proxy before full 18-analyst
        proxy = (
            0.3 * (1 if (features.get("ret_21d") or 0) > 0 else -1)
            + 0.2 * (1 if (features.get("rsi_14") or 50) < 45 else (-1 if (features.get("rsi_14") or 50) > 65 else 0))
            + 0.2 * (1 if (features.get("distance_from_high_pct") or 0) < -10 else 0)
            + _tilt(features, prefer)
        )
        sym = resolved["symbol"]
        closes_cache[sym] = closes
        resolved_cache[sym] = resolved
        prelim.append({"symbol": sym, "proxy": proxy, "features": features, "asset_class": resolved.get("asset_class")})

    prelim.sort(key=lambda r: r["proxy"], reverse=True)
    shortlist = prelim[: max(12, n_take * 3)]

    # Pass 2 — full 18 analysts + news on shortlist
    ranked: list[dict[str, Any]] = []
    for row in shortlist:
        sym = row["symbol"]
        news = fetch_yahoo_news([sym], limit_per_symbol=2)
        titles = [n.get("title") or "" for n in news]
        features = compute_features(closes_cache[sym], spy_closes=spy_closes or None, news_titles=titles)
        signals = run_all_analysts(features)
        synthesis = synthesize_signals(signals)
        score = float(synthesis["composite_score"]) + _tilt(features, prefer)
        ranked.append(
            {
                "symbol": sym,
                "yahoo_symbol": resolved_cache[sym]["yahoo_symbol"],
                "asset_class": row["asset_class"],
                "score": round(score, 4),
                "action": synthesis["action"],
                "confidence": synthesis["confidence"],
                "composite_score": synthesis["composite_score"],
                "features_summary": {
                    "ret_21d": features.get("ret_21d"),
                    "vol_63": features.get("vol_63"),
                    "rsi_14": features.get("rsi_14"),
                    "distance_from_high_pct": features.get("distance_from_high_pct"),
                },
                "domain_scores": synthesis.get("domain_scores"),
            }
        )

    ranked.sort(key=lambda r: (r["action"] == "buy", r["score"]), reverse=True)

    selected: list[dict[str, Any]] = []
    crypto_count = 0
    for row in ranked:
        if len(selected) >= n_take:
            break
        if row["asset_class"] == "crypto":
            if crypto_count >= max(1, n_take // 3):
                continue
            crypto_count += 1
        if row["action"] == "sell" and len(selected) >= max(2, n_take // 2):
            continue
        selected.append(row)

    if len(selected) < 2:
        for row in ranked:
            if any(s["symbol"] == row["symbol"] for s in selected):
                continue
            selected.append(row)
            if len(selected) >= 2:
                break

    return {
        "horizon_days": horizon_days,
        "preset": preset,
        "selected": selected,
        "symbols": [s["symbol"] for s in selected],
        "ranked_preview": ranked[:12],
        "universe_size": len(candidates),
        "shortlist_size": len(shortlist),
        "errors": errors[:8],
        "method": "covenant_18_analyst_horizon_rank",
        "note": (
            f"Selected {len(selected)} assets for {horizon_days}d horizon "
            f"({preset['key']}, prefer={prefer}) via 18-analyst ranking — not a fixed default book."
        ),
    }
