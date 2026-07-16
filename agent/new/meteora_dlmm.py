"""
Meteora DLMM helpers: pool discovery, creation cost, and pool reuse checks.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import requests

METEORA_DLMM_API = os.environ.get(
    "METEORA_DLMM_API", "https://dlmm-api.meteora.ag"
).rstrip("/")
METEORA_POOL_CREATION_SOL = float(os.environ.get("METEORA_POOL_CREATION_SOL", "0.02669"))
METEORA_DEFAULT_BIN_STEP = int(os.environ.get("METEORA_DEFAULT_BIN_STEP", "80"))
METEORA_DEFAULT_FEE_BPS = int(os.environ.get("METEORA_DEFAULT_FEE_BPS", "25"))
METEORA_POOL_SCRIPT = Path(__file__).resolve().parent / "scripts" / "create_dlmm_pool.mjs"
SOL_MINT = "So11111111111111111111111111111111111111112"


def _normalize_mint_pair(mint_a: str, mint_b: str) -> tuple[str, str]:
    a = mint_a.strip()
    b = mint_b.strip()
    return (a, b) if a < b else (b, a)


def get_pool_creation_cost_sol() -> float:
    return METEORA_POOL_CREATION_SOL


def find_dlmm_pool(token_mint: str, quote_mint: str = SOL_MINT) -> Optional[dict[str, Any]]:
    """Return Meteora DLMM pair metadata if a pool exists for the mint pair."""
    token_mint = token_mint.strip()
    quote_mint = quote_mint.strip() or SOL_MINT
    mint_x, mint_y = _normalize_mint_pair(token_mint, quote_mint)

    try:
        resp = requests.get(
            f"{METEORA_DLMM_API}/pair/all_by_groups",
            params={"include_token_mints": f"{mint_x},{mint_y}"},
            timeout=25,
        )
        if resp.status_code == 404:
            return _find_pool_via_pair_all(mint_x, mint_y)
        resp.raise_for_status()
        data = resp.json()
        groups = data if isinstance(data, list) else data.get("groups") or data.get("pairs") or []
        for group in groups:
            pairs = group.get("pairs") if isinstance(group, dict) else None
            if not pairs and isinstance(group, dict) and group.get("address"):
                pairs = [group]
            for pair in pairs or []:
                matched = _pair_matches_mints(pair, mint_x, mint_y)
                if matched:
                    return matched
    except Exception as exc:
        print(f"  ⚠️  Meteora pair lookup failed: {exc}")

    return _find_pool_via_pair_all(mint_x, mint_y)


def _find_pool_via_pair_all(mint_x: str, mint_y: str) -> Optional[dict[str, Any]]:
    try:
        resp = requests.get(f"{METEORA_DLMM_API}/pair/all", timeout=30)
        resp.raise_for_status()
        pairs = resp.json()
        if not isinstance(pairs, list):
            return None
        for pair in pairs:
            matched = _pair_matches_mints(pair, mint_x, mint_y)
            if matched:
                return matched
    except Exception as exc:
        print(f"  ⚠️  Meteora pair/all lookup failed: {exc}")
    return None


def _pair_matches_mints(pair: dict[str, Any], mint_x: str, mint_y: str) -> Optional[dict[str, Any]]:
    x = str(pair.get("mint_x") or pair.get("token_x_mint") or "").strip()
    y = str(pair.get("mint_y") or pair.get("token_y_mint") or "").strip()
    if not x or not y:
        return None
    px, py = _normalize_mint_pair(x, y)
    if px == mint_x and py == mint_y:
        return {
            "pool_address": pair.get("address") or pair.get("lb_pair"),
            "mint_x": x,
            "mint_y": y,
            "bin_step": pair.get("bin_step"),
            "base_fee_bps": pair.get("base_fee") or pair.get("base_fee_percentage"),
            "name": pair.get("name"),
            "liquidity": pair.get("liquidity"),
            "trade_volume_24h": pair.get("trade_volume_24h"),
            "raw": pair,
        }
    return None


def check_pool_infrastructure(token_mint: str, quote_mint: str = SOL_MINT) -> dict[str, Any]:
    """Agent infrastructure check: reuse existing pool or flag creation required."""
    existing = find_dlmm_pool(token_mint, quote_mint)
    if existing and existing.get("pool_address"):
        return {
            "pool_exists": True,
            "pool_address": existing["pool_address"],
            "action": "reuse_pool",
            "pool": existing,
            "pool_creation_cost_sol": 0.0,
            "platform_fee_bps": METEORA_DEFAULT_FEE_BPS,
            "message": f"DLMM pool found. Reusing pool {existing['pool_address']}.",
        }
    return {
        "pool_exists": False,
        "pool_address": None,
        "action": "create_pool",
        "pool": None,
        "pool_creation_cost_sol": get_pool_creation_cost_sol(),
        "platform_fee_bps": METEORA_DEFAULT_FEE_BPS,
        "bin_step": METEORA_DEFAULT_BIN_STEP,
        "message": (
            f"No DLMM pool found for this pair. Pool creation requires "
            f"~{get_pool_creation_cost_sol()} SOL plus seed liquidity."
        ),
    }


def create_dlmm_pool(
    *,
    token_mint: str,
    quote_mint: str = SOL_MINT,
    initial_price: float = 1.0,
    bin_step: Optional[int] = None,
    fee_bps: Optional[int] = None,
    token_amount: float = 0.0,
    quote_amount: float = 0.0,
) -> dict[str, Any]:
    """
    Create a Meteora DLMM pool via the Node helper script when available.
    Falls back to a clear error if the script is not installed.
    """
    existing = find_dlmm_pool(token_mint, quote_mint)
    if existing and existing.get("pool_address"):
        return {
            "status": "exists",
            "pool_address": existing["pool_address"],
            "pool": existing,
            "message": "Pool already exists; reusing it.",
        }

    if not METEORA_POOL_SCRIPT.exists():
        return {
            "error": (
                "Meteora pool creation script missing. Install with: "
                "cd agent/new/scripts && npm install"
            ),
            "script": str(METEORA_POOL_SCRIPT),
        }

    payload = {
        "tokenMint": token_mint.strip(),
        "quoteMint": (quote_mint or SOL_MINT).strip(),
        "initialPrice": float(initial_price),
        "binStep": int(bin_step or METEORA_DEFAULT_BIN_STEP),
        "feeBps": int(fee_bps or METEORA_DEFAULT_FEE_BPS),
        "tokenAmount": float(token_amount),
        "quoteAmount": float(quote_amount),
    }

    try:
        proc = subprocess.run(
            ["node", str(METEORA_POOL_SCRIPT), json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return {
                "error": stderr or stdout or f"Pool creation script failed ({proc.returncode})",
            }
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return {"error": f"Invalid pool creation output: {stdout[:300]}"}

        if result.get("error"):
            return result

        pool_address = result.get("pool_address") or result.get("lbPair")
        if pool_address:
            time.sleep(2)
            verified = find_dlmm_pool(token_mint, quote_mint)
            return {
                "status": "created",
                "pool_address": pool_address,
                "signature": result.get("signature"),
                "explorer_url": result.get("explorer_url"),
                "verified_pool": verified,
                "message": f"Meteora DLMM pool created at {pool_address}.",
            }
        return {"error": "Pool creation script returned no pool address.", "raw": result}
    except FileNotFoundError:
        return {"error": "Node.js is not installed. Install Node 18+ to create Meteora pools."}
    except subprocess.TimeoutExpired:
        return {"error": "Meteora pool creation timed out after 180s."}
    except Exception as exc:
        return {"error": str(exc)}
