"""
User deposit ledger for the AI Agent wallet.

Verifies on-chain transfers into the agent wallet and tracks per-user balances
so DCA plans cannot spend more than each user has deposited.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dca_agent import (
    AGENT_DIR,
    SOL_ADDRESS_FULL,
    TOKEN_MINTS,
    _load_plans,
    get_wallet_pubkey,
    resolve_token,
    sol_rpc,
)

DEPOSITS_FILE = Path(
    __import__("os").environ.get("DCA_DEPOSITS_FILE", str(AGENT_DIR / "user_deposits.json"))
)
_ledger_lock = threading.Lock()

MINT_TO_SYMBOL = {info["mint"]: sym for sym, info in TOKEN_MINTS.items()}


def _load_deposits() -> list[dict[str, Any]]:
    if not DEPOSITS_FILE.exists():
        return []
    try:
        data = json.loads(DEPOSITS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_deposits(deposits: list[dict[str, Any]]) -> None:
    DEPOSITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEPOSITS_FILE.write_text(json.dumps(deposits, indent=2), encoding="utf-8")


def _deposit_exists(signature: str) -> bool:
    return any(d.get("signature") == signature for d in _load_deposits())


def _mint_to_symbol(mint: str) -> str:
    return MINT_TO_SYMBOL.get(mint, mint[:8])


def _account_keys(tx: dict) -> list[str]:
    message = tx.get("transaction", {}).get("message", {})
    keys: list[str] = []
    for entry in message.get("accountKeys", []):
        if isinstance(entry, dict):
            keys.append(entry.get("pubkey", ""))
        else:
            keys.append(str(entry))
    return keys


def _user_in_transaction(tx: dict, user_wallet: str) -> bool:
    keys = _account_keys(tx)
    if user_wallet in keys:
        return True
    meta = tx.get("meta") or {}
    for bucket in ("preTokenBalances", "postTokenBalances"):
        for bal in meta.get(bucket, []):
            if bal.get("owner") == user_wallet:
                return True
    return False


def _parse_inbound_transfers(tx: dict, agent_wallet: str) -> list[dict[str, Any]]:
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return []

    found: list[dict[str, Any]] = []
    keys = _account_keys(tx)

    if agent_wallet in keys:
        idx = keys.index(agent_wallet)
        pre_balances = meta.get("preBalances") or []
        post_balances = meta.get("postBalances") or []
        if idx < len(pre_balances) and idx < len(post_balances):
            delta = post_balances[idx] - pre_balances[idx]
            if delta > 0:
                found.append({"token": "SOL", "mint": SOL_ADDRESS_FULL, "amount": delta / 1e9})

    pre_tokens: dict[tuple[str, str], float] = {}
    for bal in meta.get("preTokenBalances") or []:
        owner = bal.get("owner")
        mint = bal.get("mint")
        if not owner or not mint:
            continue
        ui = bal.get("uiTokenAmount") or {}
        pre_tokens[(owner, mint)] = float(ui.get("uiAmount") or 0)

    for bal in meta.get("postTokenBalances") or []:
        if bal.get("owner") != agent_wallet:
            continue
        mint = bal.get("mint")
        if not mint:
            continue
        ui = bal.get("uiTokenAmount") or {}
        post_amt = float(ui.get("uiAmount") or 0)
        pre_amt = pre_tokens.get((agent_wallet, mint), 0.0)
        delta = post_amt - pre_amt
        if delta > 0:
            found.append(
                {
                    "token": _mint_to_symbol(mint),
                    "mint": mint,
                    "amount": round(delta, 9),
                }
            )

    return found


def get_agent_wallet_info() -> dict[str, Any]:
    wallet = get_wallet_pubkey()
    return {
        "agent_wallet": wallet,
        "configured": bool(wallet),
        "supported_tokens": sorted(TOKEN_MINTS.keys()),
        "deposits_file": str(DEPOSITS_FILE),
    }


def verify_and_record_deposit(signature: str, user_wallet: str) -> dict[str, Any]:
    signature = signature.strip()
    user_wallet = user_wallet.strip()
    agent_wallet = get_wallet_pubkey()

    if not agent_wallet:
        return {"error": "AI Agent wallet is not configured on the server."}
    if not signature:
        return {"error": "Transaction signature is required."}
    if not user_wallet:
        return {"error": "User wallet address is required."}

    with _ledger_lock:
        if _deposit_exists(signature):
            existing = next(d for d in _load_deposits() if d.get("signature") == signature)
            return {
                "status": "already_recorded",
                "deposit": existing,
                "balances": get_user_balances(user_wallet),
            }

        tx = sol_rpc(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0,
                    "commitment": "confirmed",
                },
            ],
        )
        if not tx:
            return {"error": "Transaction not found. Wait for confirmation and try again."}

        if not _user_in_transaction(tx, user_wallet):
            return {"error": "Your wallet is not involved in this transaction."}

        inbound = _parse_inbound_transfers(tx, agent_wallet)
        if not inbound:
            return {"error": "No deposit to the AI Agent wallet found in this transaction."}

        now = datetime.now(timezone.utc).isoformat()
        records = []
        for transfer in inbound:
            tok = resolve_token(transfer["token"])
            if "error" in tok:
                continue
            record = {
                "id": str(uuid.uuid4())[:8],
                "user_wallet": user_wallet,
                "agent_wallet": agent_wallet,
                "signature": signature,
                "token": tok["symbol"],
                "mint": transfer["mint"],
                "amount": float(transfer["amount"]),
                "direction": "deposit",
                "status": "confirmed",
                "verified_at": now,
                "explorer_url": _explorer_url(signature),
            }
            records.append(record)

        if not records:
            return {"error": "Deposit token is not supported for DCA."}

        deposits = _load_deposits()
        deposits.extend(records)
        _save_deposits(deposits)

        return {
            "status": "confirmed",
            "deposits": records,
            "balances": get_user_balances(user_wallet),
        }


def list_user_deposits(user_wallet: str, limit: int = 20) -> dict[str, Any]:
    user_wallet = user_wallet.strip()
    rows = [d for d in _load_deposits() if d.get("user_wallet") == user_wallet]
    rows.sort(key=lambda r: r.get("verified_at", ""), reverse=True)
    return {
        "user_wallet": user_wallet,
        "deposits": rows[:limit],
        "balances": get_user_balances(user_wallet),
    }


def _user_plan_usage(user_wallet: str) -> dict[str, dict[str, float]]:
    usage: dict[str, dict[str, float]] = {}
    for plan in _load_plans():
        if plan.get("user_wallet") != user_wallet:
            continue
        if plan.get("status") in ("cancelled",):
            continue
        token = plan.get("input_token", "SOL")
        bucket = usage.setdefault(token, {"reserved": 0.0, "spent": 0.0})
        spent = float(plan.get("spent_so_far") or 0)
        bucket["spent"] += spent
        budget = plan.get("total_budget")
        if budget not in (None, "null", ""):
            try:
                budget_f = float(budget)
                bucket["reserved"] += max(budget_f, spent)
            except (TypeError, ValueError):
                bucket["reserved"] += spent
        else:
            executions = int(plan.get("executions_count") or 0)
            max_exec = plan.get("max_executions")
            per_buy = float(plan.get("amount_per_buy") or 0)
            if max_exec not in (None, "null", ""):
                try:
                    bucket["reserved"] += per_buy * int(max_exec)
                except (TypeError, ValueError):
                    bucket["reserved"] += spent
            else:
                bucket["reserved"] += max(spent, per_buy)

    return usage


def get_user_balances(user_wallet: str) -> dict[str, Any]:
    user_wallet = user_wallet.strip()
    deposited: dict[str, float] = {}
    for row in _load_deposits():
        if row.get("user_wallet") != user_wallet or row.get("status") != "confirmed":
            continue
        if row.get("direction", "deposit") != "deposit":
            continue
        token = row.get("token", "SOL")
        deposited[token] = round(deposited.get(token, 0.0) + float(row.get("amount") or 0), 9)

    usage = _user_plan_usage(user_wallet)
    tokens = sorted(set(deposited) | set(usage))
    breakdown = []
    for token in tokens:
        dep = deposited.get(token, 0.0)
        reserved = usage.get(token, {}).get("reserved", 0.0)
        spent = usage.get(token, {}).get("spent", 0.0)
        available = round(max(dep - reserved, 0.0), 9)
        breakdown.append(
            {
                "token": token,
                "deposited": dep,
                "reserved_for_plans": round(reserved, 9),
                "spent_in_plans": round(spent, 9),
                "available": available,
            }
        )

    return {
        "user_wallet": user_wallet,
        "balances": breakdown,
        "agent_wallet": get_wallet_pubkey(),
    }


def check_plan_budget(
    user_wallet: str,
    input_token: str,
    total_budget: Optional[float],
    amount_per_buy: float,
    max_executions: Optional[int],
) -> dict[str, Any]:
    if not user_wallet or not str(user_wallet).strip():
        return {
            "error": "user_wallet is required. User must connect wallet and deposit to the AI Agent wallet first.",
        }

    user_wallet = user_wallet.strip()
    tok = resolve_token(input_token)
    if "error" in tok:
        return tok

    balances = get_user_balances(user_wallet)
    available = 0.0
    for row in balances.get("balances", []):
        if row["token"] == tok["symbol"]:
            available = float(row["available"])
            break

    if total_budget is None and max_executions is not None:
        required = float(amount_per_buy) * int(max_executions)
    elif total_budget is not None:
        required = float(total_budget)
    else:
        required = float(amount_per_buy)

    if available + 1e-12 < required:
        return {
            "error": (
                f"Insufficient {tok['symbol']} balance. "
                f"Available: {available}, required: {required}. "
                f"Deposit {tok['symbol']} to the AI Agent wallet first."
            ),
            "available": available,
            "required": required,
            "user_wallet": user_wallet,
        }

    return {
        "ok": True,
        "available": available,
        "required": required,
        "token": tok["symbol"],
    }


def _explorer_url(signature: str) -> str:
    from dca_agent import SOLANA_CLUSTER

    cluster = SOLANA_CLUSTER.lower()
    base = f"https://explorer.solana.com/tx/{signature}"
    if cluster in ("mainnet", "mainnet-beta"):
        return base
    if cluster == "devnet":
        return f"{base}?cluster=devnet"
    return f"{base}?cluster={cluster}"
