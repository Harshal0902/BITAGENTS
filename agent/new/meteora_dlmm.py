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
METEORA_DLMM_DATAPI = os.environ.get(
    "METEORA_DLMM_DATAPI", "https://dlmm.datapi.meteora.ag"
).rstrip("/")
METEORA_POOL_CREATION_SOL = float(os.environ.get("METEORA_POOL_CREATION_SOL", "0.02669"))
METEORA_DEFAULT_BIN_STEP = int(os.environ.get("METEORA_DEFAULT_BIN_STEP", "80"))
METEORA_DEFAULT_FEE_BPS = int(os.environ.get("METEORA_DEFAULT_FEE_BPS", "25"))
METEORA_POOL_SCRIPT = Path(__file__).resolve().parent / "scripts" / "create_dlmm_pool.cjs"
SOL_MINT = "So11111111111111111111111111111111111111112"


def _normalize_mint_pair(mint_a: str, mint_b: str) -> tuple[str, str]:
    a = mint_a.strip()
    b = mint_b.strip()
    return (a, b) if a < b else (b, a)


def get_pool_creation_cost_sol() -> float:
    return METEORA_POOL_CREATION_SOL


def _pair_from_datapi_pool(pair: dict[str, Any]) -> dict[str, Any]:
    token_x = pair.get("token_x") or {}
    token_y = pair.get("token_y") or {}
    x = token_x.get("address") if isinstance(token_x, dict) else str(token_x or "")
    y = token_y.get("address") if isinstance(token_y, dict) else str(token_y or "")
    pool_config = pair.get("pool_config") or {}
    volume = pair.get("volume") or {}
    base_fee_pct = pool_config.get("base_fee_pct")
    base_fee_bps = None
    if base_fee_pct is not None:
        try:
            base_fee_bps = int(round(float(base_fee_pct) * 100))
        except (TypeError, ValueError):
            base_fee_bps = None
    return {
        "pool_address": pair.get("address") or pair.get("lb_pair"),
        "mint_x": x,
        "mint_y": y,
        "bin_step": pool_config.get("bin_step") or pair.get("bin_step"),
        "base_fee_bps": base_fee_bps,
        "name": pair.get("name"),
        "liquidity": pair.get("tvl") or pair.get("liquidity"),
        "trade_volume_24h": volume.get("24h") if isinstance(volume, dict) else pair.get("trade_volume_24h"),
        "raw": pair,
    }


def _find_pool_via_datapi(mint_x: str, mint_y: str) -> Optional[dict[str, Any]]:
    """Query Meteora's indexed DLMM API (dlmm.datapi.meteora.ag)."""
    try:
        resp = requests.get(
            f"{METEORA_DLMM_DATAPI}/pools",
            params={
                "filter_by": f"token_x={mint_x} && token_y={mint_y}",
                "page_size": 5,
                "sort_by": "volume_24h:desc",
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        pools = data.get("data") if isinstance(data, dict) else None
        if not pools:
            return None
        return _pair_from_datapi_pool(pools[0])
    except Exception as exc:
        print(f"  Meteora datapi lookup failed: {exc}")
        return None


def find_dlmm_pool(token_mint: str, quote_mint: str = SOL_MINT) -> Optional[dict[str, Any]]:
    """Return Meteora DLMM pair metadata if a pool exists for the mint pair."""
    token_mint = token_mint.strip()
    quote_mint = quote_mint.strip() or SOL_MINT
    mint_x, mint_y = _normalize_mint_pair(token_mint, quote_mint)

    found = _find_pool_via_datapi(mint_x, mint_y)
    if found and found.get("pool_address"):
        return found

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
        print(f"  Meteora pair lookup failed: {exc}")

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
        print(f"  Meteora pair/all lookup failed: {exc}")
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


def meteora_pool_app_url(pool_address: str) -> str:
    """Link to the pool on Meteora's app (on-chain pool address, not our DB)."""
    return f"https://app.meteora.ag/dlmm/{pool_address.strip()}"


def check_jupiter_route_exists(token_mint: str, quote_mint: str = SOL_MINT) -> dict[str, Any]:
    """
    Cheap, wallet-free liquidity check: does Jupiter's aggregator already have a
    route for this pair, regardless of which pool type (DLMM, DAMM v2, DBC,
    Raydium, etc.) actually holds the liquidity? Most real launched tokens
    (e.g. EasyA Kickstart tokens) live on DAMM v2/DBC pools, not DLMM, so this
    is the correct "does tradeable liquidity exist" signal — the DLMM-specific
    lookup above only catches the narrower case of a dedicated DLMM pool.

    Also reports which venue Jupiter's route actually goes through and the
    price impact for a small test trade — Jupiter itself does not add a fee
    on top (confirmed: `platformFee` is null unless we set one, which we
    don't), so any real cost above our own 0.25%/leg is either the venue's
    own pool fee or price impact from thin liquidity, not an aggregator tax.
    """
    try:
        resp = requests.get(
            "https://api.jup.ag/swap/v1/quote",
            params={
                "inputMint": quote_mint,
                "outputMint": token_mint,
                "amount": "10000000",
                "slippageBps": "500",
            },
            timeout=15,
        )
        if not resp.ok:
            return {"exists": False}
        data = resp.json()
        route = data.get("routePlan") or []
        if not route:
            return {"exists": False}
        venues = sorted({(leg.get("swapInfo") or {}).get("label") for leg in route if leg.get("swapInfo")})
        return {
            "exists": True,
            "venues": [v for v in venues if v],
            "is_meteora": any("meteora" in (v or "").lower() for v in venues),
            "price_impact_pct": data.get("priceImpactPct"),
        }
    except Exception as exc:
        print(f"  Jupiter route check failed: {exc}")
        return {"exists": False}


def check_pool_infrastructure(token_mint: str, quote_mint: str = SOL_MINT) -> dict[str, Any]:
    """Live Meteora DLMM lookup for the mint pair (not our database)."""
    existing = find_dlmm_pool(token_mint, quote_mint)
    if existing and existing.get("pool_address"):
        pool_address = existing["pool_address"]
        return {
            "pool_exists": True,
            "pool_address": pool_address,
            "action": "reuse_pool",
            "source": "meteora",
            "meteora_url": meteora_pool_app_url(pool_address),
            "pool": existing,
            "pool_creation_cost_sol": 0.0,
            "platform_fee_bps": METEORA_DEFAULT_FEE_BPS,
            "message": f"Meteora DLMM pool found: {pool_address}",
        }

    jupiter_route = check_jupiter_route_exists(token_mint, quote_mint)
    if jupiter_route.get("exists"):
        venues = jupiter_route.get("venues") or []
        source = "meteora (via Jupiter)" if jupiter_route.get("is_meteora") else "jupiter"
        venue_note = f" Routing through: {', '.join(venues)}." if venues else ""
        return {
            "pool_exists": True,
            "pool_address": None,
            "action": "reuse_existing_liquidity",
            "source": source,
            "pool": None,
            "pool_creation_cost_sol": 0.0,
            "platform_fee_bps": METEORA_DEFAULT_FEE_BPS,
            "price_impact_pct": jupiter_route.get("price_impact_pct"),
            "message": (
                "No dedicated DLMM pool, but Jupiter already routes this pair "
                f"through existing liquidity.{venue_note} Trading via Jupiter "
                "directly rather than creating a redundant pool — Jupiter adds "
                "no fee of its own on top."
            ),
        }

    return {
        "pool_exists": False,
        "pool_address": None,
        "action": "create_pool",
        "source": "meteora",
        "pool": None,
        "pool_creation_cost_sol": get_pool_creation_cost_sol(),
        "platform_fee_bps": METEORA_DEFAULT_FEE_BPS,
        "bin_step": METEORA_DEFAULT_BIN_STEP,
        "message": (
            f"No Meteora DLMM pool for this pair. Creation requires "
            f"~{get_pool_creation_cost_sol()} SOL plus seed liquidity."
        ),
    }


def ensure_meteora_dlmm_pool(
    token_mint: str,
    quote_mint: str = SOL_MINT,
    *,
    create_if_missing: bool = False,
    quote_amount: float = 0.0,
    token_amount: float = 0.0,
    bin_step: Optional[int] = None,
    fee_bps: Optional[int] = None,
) -> dict[str, Any]:
    """
    Check Meteora for a DLMM pool; optionally create one on Meteora if missing.
    Always returns the on-chain Meteora pool address when available.
    """
    existing = find_dlmm_pool(token_mint, quote_mint)
    if existing and existing.get("pool_address"):
        pool_address = existing["pool_address"]
        return {
            "status": "exists",
            "pool_exists": True,
            "pool_address": pool_address,
            "source": "meteora",
            "meteora_url": meteora_pool_app_url(pool_address),
            "pool": existing,
            "message": f"Meteora DLMM pool already exists: {pool_address}",
        }

    if not create_if_missing:
        return {
            "status": "missing",
            "pool_exists": False,
            "pool_address": None,
            "source": "meteora",
            "pool_creation_cost_sol": get_pool_creation_cost_sol(),
            "message": "No Meteora DLMM pool for this pair.",
        }

    created = create_dlmm_pool(
        token_mint=token_mint,
        quote_mint=quote_mint,
        fee_bps=fee_bps or METEORA_DEFAULT_FEE_BPS,
        bin_step=bin_step,
        quote_amount=quote_amount,
        token_amount=token_amount,
    )
    if created.get("error"):
        return created

    pool_address = created.get("pool_address") or (created.get("pool") or {}).get("pool_address")
    if not pool_address:
        return {"error": "Pool creation finished but no Meteora pool address was returned.", "raw": created}

    verified = find_dlmm_pool(token_mint, quote_mint)
    if verified and verified.get("pool_address"):
        pool_address = verified["pool_address"]

    return {
        "status": created.get("status") or "created",
        "pool_exists": True,
        "pool_address": pool_address,
        "source": "meteora",
        "meteora_url": meteora_pool_app_url(pool_address),
        "signature": created.get("signature"),
        "explorer_url": created.get("explorer_url"),
        "verified_pool": verified,
        "liquidity": created.get("liquidity") or {"status": "skipped"},
        "message": f"Meteora DLMM pool created: {pool_address}",
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
                "liquidity": result.get("liquidity") or {"status": "skipped"},
                "message": f"Meteora DLMM pool created at {pool_address}.",
            }
        return {"error": "Pool creation script returned no pool address.", "raw": result}
    except FileNotFoundError:
        return {"error": "Node.js is not installed. Install Node 18+ to create Meteora pools."}
    except subprocess.TimeoutExpired:
        return {"error": "Meteora pool creation timed out after 180s."}
    except Exception as exc:
        return {"error": str(exc)}
