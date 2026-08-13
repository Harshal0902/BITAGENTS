"""Resolve Hedge Fund symbols to Solana mints via Jupiter (crypto + xStocks)."""

from __future__ import annotations

from typing import Any, Optional

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_SYMBOL = "USDC"

# Yahoo / display symbol → preferred Jupiter search queries (xStocks use *x suffix)
EQUITY_XSTOCK_QUERIES: dict[str, list[str]] = {
    "AAPL": ["AAPLx", "AAPL"],
    "MSFT": ["MSFTx", "MSFT"],
    "NVDA": ["NVDAx", "NVDA"],
    "AMZN": ["AMZNx", "AMZN"],
    "GOOGL": ["GOOGLx", "GOOGL"],
    "GOOG": ["GOOGLx", "GOOG"],
    "META": ["METAx", "META"],
    "TSLA": ["TSLAx", "TSLA"],
    "NFLX": ["NFLXx", "NFLX"],
    "AMD": ["AMDx", "AMD"],
    "CRM": ["CRMx", "CRM"],
    "ORCL": ["ORCLx", "ORCL"],
    "JPM": ["JPMx", "JPM"],
    "BAC": ["BACx", "BAC"],
    "GS": ["GSx", "GS"],
    "V": ["Vx", "V"],
    "MA": ["MAx", "MA"],
    "XOM": ["XOMx", "XOM"],
    "CVX": ["CVXx", "CVX"],
    "KO": ["KOx", "KO"],
    "PEP": ["PEPx", "PEP"],
    "WMT": ["WMTx", "WMT"],
    "COST": ["COSTx", "COST"],
    "DIS": ["DISx", "DIS"],
    "UNH": ["UNHx", "UNH"],
    "JNJ": ["JNJx", "JNJ"],
    "LLY": ["LLYx", "LLY"],
    "PLTR": ["PLTRx", "PLTR"],
    "COIN": ["COINx", "COIN"],
    "MSTR": ["MSTRx", "MSTR"],
    "UBER": ["UBERx", "UBER"],
    "SHOP": ["SHOPx", "SHOP"],
    "BA": ["BAx", "BA"],
    "CAT": ["CATx", "CAT"],
    "GE": ["GEx", "GE"],
    "SPY": ["SPYx", "SPY"],
    "QQQ": ["QQQx", "QQQ"],
    "IWM": ["IWMx", "IWM"],
    "GLD": ["GLDx", "GLD"],
    "TLT": ["TLTx", "TLT"],
    "ARKK": ["ARKKx", "ARKK"],
    "AVGO": ["AVGOx", "AVGO"],
}


def _jup_search(query: str) -> Optional[dict[str, Any]]:
    try:
        from dca_agent import _fetch_token_from_jupiter
    except Exception:
        return None
    return _fetch_token_from_jupiter(query)


def _pick_best_jup(item: dict[str, Any], prefer_xstock: bool) -> dict[str, Any]:
    sym = str(item.get("symbol") or "").upper()
    name = str(item.get("name") or "")
    mint = item.get("id") or item.get("address") or item.get("mint")
    return {
        "symbol": sym,
        "mint": mint,
        "decimals": int(item.get("decimals") or 6),
        "name": name,
        "usd_price": item.get("usdPrice") or item.get("usd_price"),
        "is_xstock": prefer_xstock or sym.endswith("X") and len(sym) <= 6,
        "source": "jupiter",
    }


def resolve_hf_solana_asset(symbol: str) -> dict[str, Any]:
    """
    Map a Yahoo/display symbol to a Solana mint via Jupiter.
    Equities prefer xStocks (AAPLx, SPYx…). Crypto uses BTC, XRP, etc.
    """
    raw = (symbol or "").strip()
    if not raw:
        return {"error": "Empty symbol"}
    sym = raw.upper().replace(" ", "")

    if sym in ("USDC", "USD"):
        return {
            "symbol": "USDC",
            "display_symbol": "USDC",
            "mint": USDC_MINT,
            "decimals": 6,
            "name": "USD Coin",
            "is_xstock": False,
            "asset_class": "stablecoin",
            "source": "known",
        }

    # Already a mint
    if len(sym) >= 32 and not sym.startswith("0X"):
        item = _jup_search(raw.strip())
        if item and (item.get("id") == raw.strip()):
            out = _pick_best_jup(item, prefer_xstock=False)
            out["display_symbol"] = sym
            out["asset_class"] = "token"
            return out
        return {"error": f"Could not resolve mint {raw} on Jupiter", "display_symbol": sym}

    # Crypto aliases
    crypto_q = {
        "BTC": ["BTC", "WBTC"],
        "ETH": ["ETH", "WETH"],
        "SOL": ["SOL"],
        "XRP": ["XRP"],
        "DOGE": ["DOGE"],
        "ADA": ["ADA"],
        "AVAX": ["AVAX"],
        "LINK": ["LINK"],
        "DOT": ["DOT"],
        "MATIC": ["MATIC", "POL"],
        "BNB": ["BNB"],
        "LTC": ["LTC"],
    }
    queries: list[str] = []
    prefer_x = False
    if sym in crypto_q:
        queries = crypto_q[sym]
        asset_class = "crypto"
    elif sym in EQUITY_XSTOCK_QUERIES:
        queries = EQUITY_XSTOCK_QUERIES[sym]
        prefer_x = True
        asset_class = "equity_xstock"
    elif sym.endswith("X") and sym[:-1] in EQUITY_XSTOCK_QUERIES:
        queries = [sym, sym[:-1]]
        prefer_x = True
        asset_class = "equity_xstock"
    else:
        # Try xStock form first, then raw
        queries = [f"{sym}x", sym]
        prefer_x = True
        asset_class = "unknown"

    errors = []
    for q in queries:
        item = _jup_search(q)
        if not item or not (item.get("id") or item.get("address")):
            errors.append(f"Jupiter miss for '{q}'")
            continue
        out = _pick_best_jup(item, prefer_xstock=prefer_x)
        if not out.get("mint"):
            continue
        # Prefer verified-looking xStock when requested
        jup_sym = out["symbol"]
        if prefer_x and q.lower().endswith("x") and not jup_sym.upper().endswith("X"):
            # keep searching for a better match
            if q != queries[-1]:
                continue
        out["display_symbol"] = sym
        out["yahoo_symbol"] = sym
        out["asset_class"] = asset_class
        out["jupiter_query"] = q
        return out

    return {
        "error": f"No Jupiter mint found for '{symbol}' (tried {queries})",
        "display_symbol": sym,
        "errors": errors,
        "hint": "For stocks use xStocks tickers e.g. AAPLx / SPYx on Jupiter; or paste the mint.",
    }


def resolve_hf_book_mints(symbols: list[str]) -> dict[str, Any]:
    assets = []
    errors = []
    mint_map: dict[str, str] = {}
    for s in symbols:
        r = resolve_hf_solana_asset(s)
        if r.get("error"):
            errors.append(r)
        else:
            assets.append(r)
            mint_map[r.get("display_symbol") or s] = r["mint"]
    return {
        "assets": assets,
        "mint_map": mint_map,
        "usdc": {"symbol": "USDC", "mint": USDC_MINT},
        "errors": errors,
        "ok": len(assets) > 0 and len(errors) == 0,
    }
