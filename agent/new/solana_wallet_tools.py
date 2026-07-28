"""Shared Solana wallet inspection helpers for agent tools."""

from __future__ import annotations

from typing import Any, Optional

from dca_agent import SOLANA_CLUSTER, resolve_token, sol_rpc

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

SOLANA_WHALE_REGISTRY: dict[str, dict[str, str]] = {
    "smart_money": {
        "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "Raydium Authority",
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
    },
    "exchange": {
        "2ojv9BAiHUrvsm9gxDeTouWgW4Y1GBd2f7b2iP8zY4q3": "Example CEX hot wallet",
    },
    "defi": {
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator v6",
    },
}


def list_tracked_wallets(category: str = "all") -> dict[str, Any]:
    cat = (category or "all").strip().lower()
    if cat == "all":
        out: dict[str, list[dict[str, str]]] = {}
        total = 0
        for name, wallets in SOLANA_WHALE_REGISTRY.items():
            out[name] = [{"address": a, "label": l} for a, l in wallets.items()]
            total += len(wallets)
        return {"registry": out, "total": total, "cluster": SOLANA_CLUSTER}
    if cat not in SOLANA_WHALE_REGISTRY:
        return {"error": f"Unknown category. Choose: all, {', '.join(SOLANA_WHALE_REGISTRY)}"}
    wallets = SOLANA_WHALE_REGISTRY[cat]
    return {
        "category": cat,
        "wallets": [{"address": a, "label": l} for a, l in wallets.items()],
        "count": len(wallets),
        "cluster": SOLANA_CLUSTER,
    }


def get_wallet_sol_balance(address: str) -> dict[str, Any]:
    address = (address or "").strip()
    if len(address) < 32:
        return {"error": "Provide a valid Solana wallet address."}
    result = sol_rpc("getBalance", [address, {"commitment": "confirmed"}])
    lamports = int((result or {}).get("value") or 0)
    return {
        "address": address,
        "sol": round(lamports / 1_000_000_000, 9),
        "lamports": lamports,
        "cluster": SOLANA_CLUSTER,
    }


def get_wallet_token_balances(address: str, limit: int = 20) -> dict[str, Any]:
    address = (address or "").strip()
    if len(address) < 32:
        return {"error": "Provide a valid Solana wallet address."}
    limit = max(1, min(int(limit), 50))
    resp = sol_rpc(
        "getTokenAccountsByOwner",
        [
            address,
            {"programId": TOKEN_PROGRAM},
            {"encoding": "jsonParsed", "commitment": "confirmed"},
        ],
    )
    rows = (resp or {}).get("value") or []
    tokens: list[dict[str, Any]] = []
    for entry in rows[:limit]:
        info = (((entry.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
        token_amount = info.get("tokenAmount") or {}
        mint = info.get("mint")
        ui = float(token_amount.get("uiAmount") or 0)
        if ui <= 0:
            continue
        resolved = resolve_token(mint) if mint else {"symbol": "?"}
        tokens.append(
            {
                "mint": mint,
                "symbol": resolved.get("symbol") if isinstance(resolved, dict) else "?",
                "amount": ui,
                "decimals": token_amount.get("decimals"),
            }
        )
    tokens.sort(key=lambda x: x.get("amount") or 0, reverse=True)
    return {
        "address": address,
        "token_count": len(tokens),
        "tokens": tokens,
        "cluster": SOLANA_CLUSTER,
    }


def get_wallet_recent_activity(address: str, limit: int = 10) -> dict[str, Any]:
    address = (address or "").strip()
    if len(address) < 32:
        return {"error": "Provide a valid Solana wallet address."}
    limit = max(1, min(int(limit), 25))
    sigs = sol_rpc(
        "getSignaturesForAddress",
        [address, {"limit": limit, "commitment": "confirmed"}],
    ) or []
    activity = []
    for sig in sigs:
        activity.append(
            {
                "signature": sig.get("signature"),
                "slot": sig.get("slot"),
                "block_time": sig.get("blockTime"),
                "err": sig.get("err"),
                "memo": sig.get("memo"),
            }
        )
    return {
        "address": address,
        "recent_signatures": activity,
        "count": len(activity),
        "cluster": SOLANA_CLUSTER,
        "note": "Use Solana explorer links to inspect swap details for copy-trade research.",
    }


def analyze_wallet_profile(address: str) -> dict[str, Any]:
    balance = get_wallet_sol_balance(address)
    if balance.get("error"):
        return balance
    tokens = get_wallet_token_balances(address, limit=15)
    activity = get_wallet_recent_activity(address, limit=5)
    label = None
    for wallets in SOLANA_WHALE_REGISTRY.values():
        if address in wallets:
            label = wallets[address]
            break
    return {
        "address": address,
        "label": label,
        "sol_balance": balance.get("sol"),
        "top_tokens": (tokens.get("tokens") or [])[:5],
        "recent_activity_count": activity.get("count"),
        "recent_signatures": activity.get("recent_signatures"),
        "cluster": SOLANA_CLUSTER,
    }
