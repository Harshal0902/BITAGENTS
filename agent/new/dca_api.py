"""
HTTP API for the Solana DCA agent — used by the BIT Agents frontend.

Run locally:
  cd agent/new
  pip install -r requirements.txt
  python dca_api.py

Default: http://127.0.0.1:8765
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import uuid

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from deposit_ledger import (
    get_agent_wallet_info,
    get_user_balances,
    list_user_deposits,
    verify_and_record_deposit,
    withdraw_user_tokens,
)
from db import (
    append_chat_messages,
    assert_chat_session_access,
    db_configured,
    delete_chat_session,
    init_db,
    load_chat_history,
)
from dca_agent import (
    GROQ_API_KEY,
    JUPITER_BUILD_API,
    MODEL,
    SCHEDULER_POLL_SECONDS,
    SOLANA_CLUSTER,
    SOLANA_RPC,
    get_wallet_pubkey,
    resolve_token,
    run_agent_with_actions,
    start_scheduler,
)
from wallet_auth import (
    create_auth_challenge,
    get_session_info,
    internal_api_configured,
    resolve_session_token,
    revoke_session_token,
    verify_auth_challenge,
    verify_internal_api_key,
)

API_HOST = os.environ.get("DCA_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("DCA_API_PORT", "8765"))

app = FastAPI(title="BIT Agents DCA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthChallengeResponse(BaseModel):
    user_wallet: str
    message: str
    nonce: str
    expires_at: str


class AuthVerifyRequest(BaseModel):
    user_wallet: str = Field(min_length=32)
    message: str = Field(min_length=8)
    signature: str = Field(min_length=32)


class AuthVerifyResponse(BaseModel):
    status: str
    token: str
    user_wallet: str
    expires_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions: list[dict[str, Any]]


class DepositVerifyRequest(BaseModel):
    signature: str = Field(min_length=32)


class WithdrawRequest(BaseModel):
    token: str = Field(min_length=1)
    amount: float = Field(gt=0)


def _redact_rpc_url(rpc_url: str) -> str:
    parts = urlsplit(rpc_url)
    if not parts.query:
        return rpc_url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "api-key=REDACTED", parts.fragment))


def require_internal_key(x_internal_key: Optional[str] = Header(default=None)) -> None:
    if not verify_internal_api_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Invalid internal API key.")


def require_wallet_session(
    authorization: Optional[str] = Header(default=None),
    _: None = Depends(require_internal_key),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Wallet sign-in required. Connect your wallet and authenticate.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    wallet = resolve_session_token(token)
    if not wallet:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Sign in again.")
    return wallet


@app.on_event("startup")
def _startup() -> None:
    if not db_configured():
        raise RuntimeError("DATABASE_URL is not set. Add your Neon connection string to agent/new/.env")
    try:
        init_db()
    except Exception as exc:
        raise RuntimeError(f"Neon database init failed: {exc}") from exc
    print("  🗄️  Neon database ready")
    if internal_api_configured():
        print("  🔐 Internal API key enabled")
    else:
        print("  ⚠️  DCA_INTERNAL_API_KEY not set (optional for local dev)")
    if start_scheduler():
        print(f"  ⏱️  DCA scheduler started (every {SCHEDULER_POLL_SECONDS}s)")


@app.get("/health")
def health() -> dict[str, Any]:
    wallet = get_wallet_pubkey()
    agent_info = get_agent_wallet_info()
    return {
        "status": "ok",
        "llm": "groq",
        "model": MODEL,
        "groq_configured": bool(GROQ_API_KEY),
        "database": "neon_postgres" if db_configured() else "unconfigured",
        "auth": "wallet_signature",
        "internal_api_key_required": internal_api_configured(),
        "cluster": SOLANA_CLUSTER,
        "rpc": _redact_rpc_url(SOLANA_RPC),
        "jupiter_api": JUPITER_BUILD_API,
        "wallet": wallet or None,
        "wallet_configured": bool(wallet),
        "agent_wallet": agent_info.get("agent_wallet"),
        "any_spl_token": agent_info.get("any_spl_token", True),
        "common_tokens": agent_info.get("common_tokens", []),
    }


@app.get("/tokens/resolve")
def resolve_token_info(
    query: str = Query(..., min_length=2),
    _: None = Depends(require_internal_key),
) -> dict[str, Any]:
    result = resolve_token(query.strip())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "symbol": result["symbol"],
        "mint": result["mint"],
        "decimals": result["decimals"],
        "name": result.get("name"),
    }


@app.get("/auth/challenge", response_model=AuthChallengeResponse)
def auth_challenge(
    user_wallet: str = Query(..., min_length=32),
    _: None = Depends(require_internal_key),
) -> dict[str, Any]:
    result = create_auth_challenge(user_wallet.strip())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/auth/verify", response_model=AuthVerifyResponse)
def auth_verify(
    body: AuthVerifyRequest,
    _: None = Depends(require_internal_key),
) -> dict[str, Any]:
    result = verify_auth_challenge(body.user_wallet.strip(), body.message, body.signature.strip())
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.get("/auth/me")
def auth_me(
    authorization: Optional[str] = Header(default=None),
    _: None = Depends(require_internal_key),
) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token.")
    info = get_session_info(authorization.removeprefix("Bearer ").strip())
    if not info:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return info


@app.post("/auth/logout")
def auth_logout(
    authorization: Optional[str] = Header(default=None),
    _: None = Depends(require_internal_key),
) -> dict[str, bool]:
    if authorization and authorization.startswith("Bearer "):
        revoke_session_token(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@app.get("/wallet/agent")
def wallet_agent(_: None = Depends(require_internal_key)) -> dict[str, Any]:
    return get_agent_wallet_info()


@app.get("/wallet/balance")
def wallet_balance(
    auth_wallet: str = Depends(require_wallet_session),
) -> dict[str, Any]:
    return get_user_balances(auth_wallet)


@app.get("/wallet/deposits")
def wallet_deposits(
    auth_wallet: str = Depends(require_wallet_session),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return list_user_deposits(auth_wallet, limit)


@app.post("/wallet/deposit/verify")
def wallet_deposit_verify(
    body: DepositVerifyRequest,
    auth_wallet: str = Depends(require_wallet_session),
) -> dict[str, Any]:
    result = verify_and_record_deposit(body.signature.strip(), auth_wallet)
    if "error" in result and result.get("status") != "already_recorded":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/wallet/withdraw")
def wallet_withdraw(
    body: WithdrawRequest,
    auth_wallet: str = Depends(require_wallet_session),
) -> dict[str, Any]:
    result = withdraw_user_tokens(auth_wallet, body.token.strip(), float(body.amount))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    auth_wallet: str = Depends(require_wallet_session),
) -> ChatResponse:
    session_id = body.session_id or str(uuid.uuid4())
    access_error = assert_chat_session_access(session_id, auth_wallet)
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    history = load_chat_history(session_id)
    user_message = body.message.strip()

    try:
        reply, history, actions = run_agent_with_actions(
            user_message,
            history,
            user_wallet=auth_wallet,
        )
    except requests.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach Groq API. Check your network connection.",
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Groq error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    append_chat_messages(session_id, user_message, reply, actions, user_wallet=auth_wallet)
    return ChatResponse(reply=reply, session_id=session_id, actions=actions)


@app.delete("/chat/{session_id}")
def clear_session(
    session_id: str,
    auth_wallet: str = Depends(require_wallet_session),
) -> dict[str, bool]:
    access_error = assert_chat_session_access(session_id, auth_wallet)
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)
    deleted = delete_chat_session(session_id)
    return {"ok": deleted}


if __name__ == "__main__":
    import uvicorn

    print(f"Starting DCA API on http://{API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
