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
import uuid
from typing import Any, Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from deposit_ledger import (
    get_agent_wallet_info,
    get_user_balances,
    list_user_deposits,
    verify_and_record_deposit,
)
from dca_agent import (
    JUPITER_BUILD_API,
    MODEL,
    SCHEDULER_POLL_SECONDS,
    SOLANA_CLUSTER,
    SOLANA_RPC,
    get_wallet_pubkey,
    run_agent_with_actions,
    start_scheduler,
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

_sessions: dict[str, list[dict[str, Any]]] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = None
    user_wallet: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions: list[dict[str, Any]]


class DepositVerifyRequest(BaseModel):
    signature: str = Field(min_length=32)
    user_wallet: str = Field(min_length=32)


@app.on_event("startup")
def _startup() -> None:
    if start_scheduler():
        print(f"  ⏱️  DCA scheduler started (every {SCHEDULER_POLL_SECONDS}s)")


@app.get("/health")
def health() -> dict[str, Any]:
    wallet = get_wallet_pubkey()
    agent_info = get_agent_wallet_info()
    return {
        "status": "ok",
        "model": MODEL,
        "cluster": SOLANA_CLUSTER,
        "rpc": SOLANA_RPC,
        "jupiter_api": JUPITER_BUILD_API,
        "wallet": wallet or None,
        "wallet_configured": bool(wallet),
        "agent_wallet": agent_info.get("agent_wallet"),
        "supported_deposit_tokens": agent_info.get("supported_tokens", []),
    }


@app.get("/wallet/agent")
def wallet_agent() -> dict[str, Any]:
    return get_agent_wallet_info()


@app.get("/wallet/balance")
def wallet_balance(user_wallet: str = Query(..., min_length=32)) -> dict[str, Any]:
    return get_user_balances(user_wallet.strip())


@app.get("/wallet/deposits")
def wallet_deposits(
    user_wallet: str = Query(..., min_length=32),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return list_user_deposits(user_wallet.strip(), limit)


@app.post("/wallet/deposit/verify")
def wallet_deposit_verify(body: DepositVerifyRequest) -> dict[str, Any]:
    result = verify_and_record_deposit(body.signature.strip(), body.user_wallet.strip())
    if "error" in result and result.get("status") != "already_recorded":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    session_id = body.session_id or str(uuid.uuid4())
    history = _sessions.setdefault(session_id, [])

    try:
        reply, history, actions = run_agent_with_actions(
            body.message.strip(),
            history,
            user_wallet=body.user_wallet.strip() if body.user_wallet else None,
        )
    except requests.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Start it with: ollama serve",
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _sessions[session_id] = history
    return ChatResponse(reply=reply, session_id=session_id, actions=actions)


@app.delete("/chat/{session_id}")
def clear_session(session_id: str) -> dict[str, bool]:
    _sessions.pop(session_id, None)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    print(f"Starting DCA API on http://{API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
