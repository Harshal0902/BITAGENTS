"""
Neon PostgreSQL persistence for DCA plans, user deposit ledger, and chat sessions.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent


def _load_env_file() -> None:
    """Load .env before reading DATABASE_URL (db may import before dca_agent)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
        load_dotenv(REPO_ROOT / ".env.local", override=True)
        load_dotenv(AGENT_DIR / ".env", override=True)
    except ImportError:
        env_file = AGENT_DIR / ".env"
        if not env_file.exists():
            return
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file()


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return ""
    # psycopg2/libpq may reject Neon's channel_binding query param
    if "channel_binding=" in url:
        base, _, query = url.partition("?")
        if query:
            parts = [p for p in query.split("&") if not p.startswith("channel_binding=")]
            url = base + ("?" + "&".join(parts) if parts else "")
    return url

_db_lock = threading.RLock()
_schema_ready = False
_import_done = False

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS dca_plans (
        id                  VARCHAR(16) PRIMARY KEY,
        user_wallet         VARCHAR(64),
        name                TEXT NOT NULL,
        input_token         VARCHAR(32) NOT NULL,
        output_token        VARCHAR(32) NOT NULL,
        input_mint          VARCHAR(64) NOT NULL,
        output_mint         VARCHAR(64) NOT NULL,
        amount_per_buy      DOUBLE PRECISION NOT NULL,
        interval_label      TEXT NOT NULL,
        interval_minutes    DOUBLE PRECISION NOT NULL,
        total_budget        DOUBLE PRECISION,
        spent_so_far        DOUBLE PRECISION NOT NULL DEFAULT 0,
        max_executions      INTEGER,
        executions_count    INTEGER NOT NULL DEFAULT 0,
        slippage_bps        INTEGER NOT NULL DEFAULT 100,
        status              VARCHAR(20) NOT NULL DEFAULT 'active',
        created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        next_execution_at   TIMESTAMPTZ,
        executions          JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dca_plans_user_wallet ON dca_plans (user_wallet)",
    "CREATE INDEX IF NOT EXISTS idx_dca_plans_status ON dca_plans (status)",
    """
    CREATE INDEX IF NOT EXISTS idx_dca_plans_next_execution ON dca_plans (next_execution_at)
        WHERE status = 'active'
    """,
    """
    CREATE TABLE IF NOT EXISTS user_ledger (
        id              VARCHAR(16) PRIMARY KEY,
        user_wallet     VARCHAR(64) NOT NULL,
        agent_wallet    VARCHAR(64),
        signature       VARCHAR(128),
        token           VARCHAR(32) NOT NULL,
        mint            VARCHAR(64) NOT NULL,
        amount          DOUBLE PRECISION NOT NULL,
        direction       VARCHAR(10) NOT NULL DEFAULT 'deposit',
        reference_type  VARCHAR(32),
        reference_id    VARCHAR(128),
        status          VARCHAR(20) NOT NULL DEFAULT 'confirmed',
        verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        explorer_url    TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_ledger_user_wallet ON user_ledger (user_wallet)",
    "CREATE INDEX IF NOT EXISTS idx_user_ledger_signature ON user_ledger (signature)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_ledger_deposit_sig
        ON user_ledger (signature, token, direction)
        WHERE direction = 'deposit' AND signature IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id              UUID PRIMARY KEY,
        user_wallet     VARCHAR(64),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_wallet ON chat_sessions (user_wallet)",
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id              BIGSERIAL PRIMARY KEY,
        session_id      UUID NOT NULL REFERENCES chat_sessions (id) ON DELETE CASCADE,
        role            VARCHAR(20) NOT NULL,
        content         TEXT NOT NULL,
        actions         JSONB,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages (session_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS wallet_auth_challenges (
        nonce           VARCHAR(64) PRIMARY KEY,
        user_wallet     VARCHAR(64) NOT NULL,
        message         TEXT NOT NULL,
        expires_at      TIMESTAMPTZ NOT NULL,
        used            BOOLEAN NOT NULL DEFAULT FALSE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wallet_auth_challenges_wallet ON wallet_auth_challenges (user_wallet)",
    """
    CREATE TABLE IF NOT EXISTS wallet_sessions (
        token_hash      VARCHAR(64) PRIMARY KEY,
        user_wallet     VARCHAR(64) NOT NULL,
        expires_at      TIMESTAMPTZ NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wallet_sessions_wallet ON wallet_sessions (user_wallet)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_sessions_expires ON wallet_sessions (expires_at)",
]

MIGRATION_STATEMENTS = [
    "ALTER TABLE user_ledger ALTER COLUMN reference_id TYPE VARCHAR(128)",
    "ALTER TABLE user_ledger ALTER COLUMN signature TYPE VARCHAR(128)",
]


def db_configured() -> bool:
    return bool(get_database_url())


def _require_db() -> None:
    if not get_database_url():
        raise RuntimeError(
            "DATABASE_URL is not set. Add your Neon connection string to agent/new/.env"
        )


@contextmanager
def get_conn():
    _require_db()
    conn = psycopg2.connect(
        get_database_url(),
        cursor_factory=RealDictCursor,
        connect_timeout=15,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return value


def _plan_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    executions = row.get("executions") or []
    if isinstance(executions, str):
        executions = json.loads(executions)
    return {
        "id": row["id"],
        "name": row["name"],
        "input_token": row["input_token"],
        "output_token": row["output_token"],
        "input_mint": row["input_mint"],
        "output_mint": row["output_mint"],
        "amount_per_buy": float(row["amount_per_buy"]),
        "interval": row["interval_label"],
        "interval_minutes": float(row["interval_minutes"]),
        "total_budget": float(row["total_budget"]) if row.get("total_budget") is not None else None,
        "spent_so_far": float(row.get("spent_so_far") or 0),
        "max_executions": row.get("max_executions"),
        "executions_count": int(row.get("executions_count") or 0),
        "slippage_bps": int(row.get("slippage_bps") or 100),
        "status": row["status"],
        "user_wallet": row.get("user_wallet"),
        "created_at": _iso(row.get("created_at")),
        "next_execution_at": _iso(row.get("next_execution_at")),
        "executions": executions,
    }


def _ledger_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_wallet": row["user_wallet"],
        "agent_wallet": row.get("agent_wallet"),
        "signature": row.get("signature"),
        "token": row["token"],
        "mint": row["mint"],
        "amount": float(row["amount"]),
        "direction": row.get("direction") or "deposit",
        "reference_type": row.get("reference_type"),
        "reference_id": row.get("reference_id"),
        "status": row.get("status") or "confirmed",
        "verified_at": _iso(row.get("verified_at")),
        "explorer_url": row.get("explorer_url"),
    }


def init_db() -> None:
    global _schema_ready, _import_done
    if not get_database_url():
        raise RuntimeError("DATABASE_URL is not set.")
    with _db_lock:
        if _schema_ready:
            return
        with get_conn() as conn:
            with conn.cursor() as cur:
                for stmt in SCHEMA_STATEMENTS:
                    cur.execute(stmt)
                for stmt in MIGRATION_STATEMENTS:
                    cur.execute(stmt)
        _schema_ready = True

    if _import_done:
        return
    with _db_lock:
        if _import_done:
            return
        _import_json_if_empty()
        _import_done = True


def _import_json_if_empty() -> None:
    """One-time import from legacy JSON files when DB tables are empty."""
    plans_file = Path(os.environ.get("DCA_PLANS_FILE", str(AGENT_DIR / "dca_plans.json")))
    deposits_file = Path(
        os.environ.get("DCA_DEPOSITS_FILE", str(AGENT_DIR / "user_deposits.json"))
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM dca_plans")
            plan_count = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM user_ledger")
            ledger_count = int(cur.fetchone()["n"])

    if plan_count == 0 and plans_file.exists():
        try:
            plans = json.loads(plans_file.read_text(encoding="utf-8"))
            if isinstance(plans, list):
                for plan in plans:
                    insert_plan(plan)
                print(f"  📦 Imported {len(plans)} DCA plan(s) from {plans_file.name}")
        except Exception as exc:
            print(f"  ⚠️  Could not import plans JSON: {exc}")

    if ledger_count == 0 and deposits_file.exists():
        try:
            rows = json.loads(deposits_file.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                for row in rows:
                    insert_ledger_entry(row)
                print(f"  📦 Imported {len(rows)} ledger row(s) from {deposits_file.name}")
        except Exception as exc:
            print(f"  ⚠️  Could not import deposits JSON: {exc}")


# ─── DCA plans ────────────────────────────────────────────────────────────────

def load_all_plans(user_wallet: Optional[str] = None) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_wallet:
                cur.execute(
                    "SELECT * FROM dca_plans WHERE user_wallet = %s ORDER BY created_at ASC",
                    (user_wallet.strip(),),
                )
            else:
                cur.execute("SELECT * FROM dca_plans ORDER BY created_at ASC")
            rows = cur.fetchall()
    return [_plan_row_to_dict(row) for row in rows]


def find_plan(plan_id: str) -> Optional[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dca_plans WHERE id = %s", (plan_id,))
            row = cur.fetchone()
    return _plan_row_to_dict(row) if row else None


def insert_plan(plan: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dca_plans (
                    id, user_wallet, name, input_token, output_token,
                    input_mint, output_mint, amount_per_buy, interval_label,
                    interval_minutes, total_budget, spent_so_far, max_executions,
                    executions_count, slippage_bps, status, created_at,
                    next_execution_at, executions
                ) VALUES (
                    %(id)s, %(user_wallet)s, %(name)s, %(input_token)s, %(output_token)s,
                    %(input_mint)s, %(output_mint)s, %(amount_per_buy)s, %(interval)s,
                    %(interval_minutes)s, %(total_budget)s, %(spent_so_far)s, %(max_executions)s,
                    %(executions_count)s, %(slippage_bps)s, %(status)s, %(created_at)s,
                    %(next_execution_at)s, %(executions)s
                )
                """,
                {
                    **plan,
                    "interval": plan.get("interval"),
                    "executions": Json(plan.get("executions") or []),
                },
            )
    return plan


def update_plan(plan_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    init_db()
    plan = find_plan(plan_id)
    if not plan:
        return None

    merged = {**plan, **updates}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dca_plans SET
                    user_wallet = %(user_wallet)s,
                    name = %(name)s,
                    input_token = %(input_token)s,
                    output_token = %(output_token)s,
                    input_mint = %(input_mint)s,
                    output_mint = %(output_mint)s,
                    amount_per_buy = %(amount_per_buy)s,
                    interval_label = %(interval)s,
                    interval_minutes = %(interval_minutes)s,
                    total_budget = %(total_budget)s,
                    spent_so_far = %(spent_so_far)s,
                    max_executions = %(max_executions)s,
                    executions_count = %(executions_count)s,
                    slippage_bps = %(slippage_bps)s,
                    status = %(status)s,
                    created_at = %(created_at)s,
                    next_execution_at = %(next_execution_at)s,
                    executions = %(executions)s
                WHERE id = %(id)s
                """,
                {
                    "id": plan_id,
                    "user_wallet": merged.get("user_wallet"),
                    "name": merged["name"],
                    "input_token": merged["input_token"],
                    "output_token": merged["output_token"],
                    "input_mint": merged["input_mint"],
                    "output_mint": merged["output_mint"],
                    "amount_per_buy": merged["amount_per_buy"],
                    "interval": merged["interval"],
                    "interval_minutes": merged["interval_minutes"],
                    "total_budget": merged.get("total_budget"),
                    "spent_so_far": merged.get("spent_so_far", 0),
                    "max_executions": merged.get("max_executions"),
                    "executions_count": merged.get("executions_count", 0),
                    "slippage_bps": merged.get("slippage_bps", 100),
                    "status": merged.get("status", "active"),
                    "created_at": merged.get("created_at"),
                    "next_execution_at": merged.get("next_execution_at"),
                    "executions": Json(merged.get("executions") or []),
                },
            )
    return find_plan(plan_id)


# ─── User ledger ──────────────────────────────────────────────────────────────

def load_all_ledger_entries() -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_ledger ORDER BY verified_at ASC")
            rows = cur.fetchall()
    return [_ledger_row_to_dict(row) for row in rows]


def load_ledger_for_user(user_wallet: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    init_db()
    query = """
        SELECT * FROM user_ledger
        WHERE user_wallet = %s
        ORDER BY verified_at DESC
    """
    params: list[Any] = [user_wallet.strip()]
    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [_ledger_row_to_dict(row) for row in rows]


def deposit_exists(signature: str) -> bool:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_ledger
                WHERE signature = %s AND direction = 'deposit'
                LIMIT 1
                """,
                (signature.strip(),),
            )
            return cur.fetchone() is not None


def find_deposit_by_signature(signature: str) -> Optional[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM user_ledger
                WHERE signature = %s AND direction = 'deposit'
                ORDER BY verified_at ASC
                LIMIT 1
                """,
                (signature.strip(),),
            )
            row = cur.fetchone()
    return _ledger_row_to_dict(row) if row else None


def insert_ledger_entry(record: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_ledger (
                    id, user_wallet, agent_wallet, signature, token, mint,
                    amount, direction, reference_type, reference_id,
                    status, verified_at, explorer_url
                ) VALUES (
                    %(id)s, %(user_wallet)s, %(agent_wallet)s, %(signature)s, %(token)s, %(mint)s,
                    %(amount)s, %(direction)s, %(reference_type)s, %(reference_id)s,
                    %(status)s, %(verified_at)s, %(explorer_url)s
                )
                ON CONFLICT DO NOTHING
                """,
                {
                    "id": record.get("id") or str(uuid.uuid4())[:8],
                    "user_wallet": record["user_wallet"],
                    "agent_wallet": record.get("agent_wallet"),
                    "signature": record.get("signature"),
                    "token": record["token"],
                    "mint": record["mint"],
                    "amount": float(record["amount"]),
                    "direction": record.get("direction") or "deposit",
                    "reference_type": record.get("reference_type"),
                    "reference_id": record.get("reference_id"),
                    "status": record.get("status") or "confirmed",
                    "verified_at": record.get("verified_at") or datetime.now(timezone.utc).isoformat(),
                    "explorer_url": record.get("explorer_url"),
                },
            )
    return record


# ─── Chat sessions ────────────────────────────────────────────────────────────

def ensure_chat_session(session_id: str, user_wallet: Optional[str] = None) -> str:
    init_db()
    sid = session_id.strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, user_wallet)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    user_wallet = COALESCE(EXCLUDED.user_wallet, chat_sessions.user_wallet),
                    updated_at = NOW()
                """,
                (sid, user_wallet.strip() if user_wallet else None),
            )
    return sid


def get_chat_session_owner(session_id: str) -> Optional[str]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_wallet FROM chat_sessions WHERE id = %s",
                (session_id.strip(),),
            )
            row = cur.fetchone()
    if not row:
        return None
    return row.get("user_wallet")


def assert_chat_session_access(session_id: str, user_wallet: str) -> Optional[str]:
    """Return error message if the wallet may not access this chat session."""
    owner = get_chat_session_owner(session_id.strip())
    if owner and owner != user_wallet.strip():
        return "This chat session belongs to another wallet."
    return None


def load_chat_history(session_id: str) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def append_chat_messages(
    session_id: str,
    user_content: str,
    assistant_content: str,
    actions: Optional[list[dict[str, Any]]] = None,
    user_wallet: Optional[str] = None,
) -> None:
    init_db()
    ensure_chat_session(session_id, user_wallet)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content)
                VALUES (%s, 'user', %s)
                """,
                (session_id, user_content),
            )
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, actions)
                VALUES (%s, 'assistant', %s, %s)
                """,
                (session_id, assistant_content, Json(actions or [])),
            )
            cur.execute(
                "UPDATE chat_sessions SET updated_at = NOW(), user_wallet = COALESCE(%s, user_wallet) WHERE id = %s",
                (user_wallet.strip() if user_wallet else None, session_id),
            )


def delete_chat_session(session_id: str) -> bool:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            return cur.rowcount > 0
