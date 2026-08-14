"""Hedge Fund Solana asset resolution — hedge-fund-tokens.json first, then Jupiter."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_SYMBOL = "USDC"
SOL_MINT = "So11111111111111111111111111111111111111112"

_TOKENS_PATH = Path(__file__).resolve().parent / "hedge-fund-tokens.json"


@lru_cache(maxsize=1)
def load_hf_token_catalog() -> list[dict[str, str]]:
    path = Path(os.environ.get("HF_TOKENS_JSON", str(_TOKENS_PATH)))
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for row in data if isinstance(data, list) else []:
        sym = str(row.get("symbol") or "").strip()
        addr = str(row.get("address") or row.get("mint") or "").strip()
        if sym and addr:
            out.append(
                {
                    "symbol": sym,
                    "name": str(row.get("name") or sym),
                    "address": addr,
                    "mint": addr,
                }
            )
    return out


def _catalog_index() -> dict[str, list[dict[str, str]]]:
    idx: dict[str, list[dict[str, str]]] = {}
    for row in load_hf_token_catalog():
        sym = row["symbol"].upper()
        idx.setdefault(sym, []).append(row)
        # Strip common suffixes for alias lookup: AAPLon / AAPLx → AAPL
        for suffix in ("ON", "X"):
            if sym.endswith(suffix) and len(sym) > len(suffix) + 1:
                base = sym[: -len(suffix)]
                idx.setdefault(base, []).append(row)
        name_key = "".join(ch for ch in (row.get("name") or "").upper() if ch.isalnum())
        if name_key:
            idx.setdefault(name_key, []).append(row)
    return idx


def lookup_hf_catalog(symbol: str) -> Optional[dict[str, Any]]:
    raw = (symbol or "").strip()
    if not raw:
        return None
    # Already a mint
    if len(raw) >= 32 and not raw.startswith("0x"):
        for row in load_hf_token_catalog():
            if row["address"] == raw:
                return {
                    "symbol": row["symbol"],
                    "display_symbol": row["symbol"],
                    "name": row["name"],
                    "mint": row["address"],
                    "decimals": 6,
                    "is_xstock": True,
                    "asset_class": "equity_tokenized",
                    "source": "hedge-fund-tokens.json",
                }
        return None

    sym = raw.upper().replace(" ", "").replace("-USD", "").replace("USD", "")
    idx = _catalog_index()
    candidates = idx.get(sym) or []
    if not candidates and sym.endswith("X"):
        candidates = idx.get(sym[:-1]) or []
    if not candidates:
        return None
    # Prefer *x (xStocks) then *on (ondo) then first
    preferred = None
    for c in candidates:
        s = c["symbol"].upper()
        if s == sym or s == f"{sym}X":
            preferred = c
            break
        if s.endswith("X") and preferred is None:
            preferred = c
        elif s.endswith("ON") and preferred is None:
            preferred = c
    row = preferred or candidates[0]
    return {
        "symbol": row["symbol"],
        "display_symbol": sym,
        "yahoo_symbol": sym,
        "name": row["name"],
        "mint": row["address"],
        "decimals": 6,
        "is_xstock": row["symbol"].upper().endswith("X") or row["symbol"].upper().endswith("ON"),
        "asset_class": "equity_tokenized",
        "source": "hedge-fund-tokens.json",
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
        "is_xstock": prefer_xstock or (sym.endswith("X") and len(sym) <= 6),
        "source": "jupiter",
    }


def resolve_hf_solana_asset(symbol: str, mint_override: Optional[str] = None) -> dict[str, Any]:
    """
    Map a Yahoo/display symbol (or mint) to a Solana mint.
    Order: mint override → hedge-fund-tokens.json → Jupiter (crypto / xStocks).
    """
    raw = (symbol or "").strip()
    if not raw and not mint_override:
        return {"error": "Empty symbol"}

    if mint_override and str(mint_override).strip():
        mint = str(mint_override).strip()
        item = _jup_search(mint)
        if item:
            out = _pick_best_jup(item, prefer_xstock=False)
            out["display_symbol"] = raw.upper() or out["symbol"]
            out["mint"] = mint
            out["asset_class"] = "token"
            out["source"] = "user_override"
            return out
        return {
            "symbol": raw.upper() or mint[:8],
            "display_symbol": raw.upper() or mint[:8],
            "mint": mint,
            "decimals": 6,
            "name": raw,
            "is_xstock": False,
            "asset_class": "token",
            "source": "user_override",
        }

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
    if sym in ("SOL", "WSOL"):
        return {
            "symbol": "SOL",
            "display_symbol": "SOL",
            "mint": SOL_MINT,
            "decimals": 9,
            "name": "Solana",
            "is_xstock": False,
            "asset_class": "crypto",
            "source": "known",
        }

    # Catalog (stocks / tokenized equities)
    catalog = lookup_hf_catalog(raw)
    if catalog and catalog.get("mint"):
        return catalog

    # Already a mint
    if len(sym) >= 32 and not sym.startswith("0X"):
        item = _jup_search(raw.strip())
        if item and (item.get("id") == raw.strip() or item.get("address") == raw.strip()):
            out = _pick_best_jup(item, prefer_xstock=False)
            out["display_symbol"] = sym
            out["asset_class"] = "token"
            return out
        return {"error": f"Could not resolve mint {raw} on Jupiter", "display_symbol": sym}

    # Crypto via Jupiter
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
        "BONK": ["BONK"],
        "WIF": ["WIF"],
        "JUP": ["JUP"],
    }
    base = sym.replace("-USD", "")
    queries = crypto_q.get(base) or [f"{base}x", f"{base}on", base]
    prefer_x = base not in crypto_q
    errors = []
    for q in queries:
        item = _jup_search(q)
        if not item or not (item.get("id") or item.get("address")):
            errors.append(f"Jupiter miss for '{q}'")
            continue
        out = _pick_best_jup(item, prefer_xstock=prefer_x)
        if not out.get("mint"):
            continue
        out["display_symbol"] = base
        out["yahoo_symbol"] = base
        out["asset_class"] = "crypto" if base in crypto_q else "equity_xstock"
        out["jupiter_query"] = q
        return out

    return {
        "error": f"No mint found for '{symbol}' (catalog + Jupiter)",
        "display_symbol": base,
        "errors": errors,
        "hint": "Use a symbol from hedge-fund-tokens.json, a crypto ticker, or paste a mint.",
    }


def resolve_hf_book_mints(
    symbols: list[str], mint_overrides: Optional[dict[str, str]] = None
) -> dict[str, Any]:
    overrides = {str(k).upper(): str(v) for k, v in (mint_overrides or {}).items()}
    assets = []
    errors = []
    mint_map: dict[str, str] = {}
    for s in symbols:
        key = str(s).strip().upper()
        r = resolve_hf_solana_asset(s, mint_override=overrides.get(key))
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
        "catalog_size": len(load_hf_token_catalog()),
    }
