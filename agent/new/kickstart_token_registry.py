"""
EasyA Kickstart verified token registry.

Edit kickstart_verified_tokens.json to add/remove projects the copilot may use.
Set KICKSTART_REGISTRY_ENFORCED=false in .env to allow any token (dev only).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

AGENT_DIR = Path(__file__).resolve().parent

_default_file = AGENT_DIR / "kickstart_verified_tokens.json"
_env_path = os.environ.get("KICKSTART_VERIFIED_TOKENS_FILE", "").strip()
REGISTRY_FILE = Path(_env_path) if _env_path else _default_file

REGISTRY_ENFORCED = os.environ.get("KICKSTART_REGISTRY_ENFORCED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

_registry_cache: Optional[list[dict[str, Any]]] = None
_mint_index: dict[str, dict[str, Any]] = {}
_symbol_index: dict[str, dict[str, Any]] = {}
_name_index: dict[str, dict[str, Any]] = {}


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


def _normalize_mint(value: str) -> str:
    return (value or "").strip()


def _normalize_symbol(value: str) -> str:
    return (value or "").strip().upper()


def reload_registry() -> list[dict[str, Any]]:
    """Reload registry from disk (clears cache)."""
    global _registry_cache, _mint_index, _symbol_index, _name_index
    _registry_cache = None
    _mint_index = {}
    _symbol_index = {}
    _name_index = {}
    return load_verified_tokens(force=True)


def load_verified_tokens(*, force: bool = False) -> list[dict[str, Any]]:
    global _registry_cache, _mint_index, _symbol_index, _name_index
    if _registry_cache is not None and not force:
        return _registry_cache

    if not REGISTRY_FILE.exists():
        _registry_cache = []
        return _registry_cache

    try:
        raw = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _registry_cache = []
        return _registry_cache

    items = raw.get("tokens") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        _registry_cache = []
        return _registry_cache

    cleaned: list[dict[str, Any]] = []
    _mint_index = {}
    _symbol_index = {}
    _name_index = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        mint = _normalize_mint(str(item.get("mint") or ""))
        symbol = _normalize_symbol(str(item.get("symbol") or ""))
        name = _normalize_name(str(item.get("name") or ""))
        if not mint or len(mint) < 32:
            continue
        entry = dict(item)
        entry["mint"] = mint
        entry["symbol"] = symbol
        if name:
            entry["name"] = item.get("name") or name
        entry["active"] = bool(item.get("active", True))
        cleaned.append(entry)
        _mint_index[mint] = entry
        if symbol:
            _symbol_index[symbol] = entry
        if name:
            _name_index[name] = entry

    _registry_cache = cleaned
    return _registry_cache


def registry_is_enforced() -> bool:
    if not REGISTRY_ENFORCED:
        return False
    return True


def active_verified_tokens() -> list[dict[str, Any]]:
    return [t for t in load_verified_tokens() if t.get("active", True)]


def find_verified_token(token: str) -> Optional[dict[str, Any]]:
    raw = (token or "").strip()
    if not raw:
        return None
    load_verified_tokens()
    if len(raw) >= 32 and raw in _mint_index:
        hit = _mint_index[raw]
        return hit if hit.get("active", True) else None
    sym = _normalize_symbol(raw)
    hit = _symbol_index.get(sym)
    if hit and hit.get("active", True):
        return hit
    name = _normalize_name(raw)
    hit = _name_index.get(name)
    if hit and hit.get("active", True):
        return hit
    return None


def get_allowlist_prompt_block() -> str:
    tokens = active_verified_tokens()
    if not tokens:
        return (
            "## Active allowlist\n"
            "No active EasyA Kickstart tokens are configured. "
            "Do not answer token-specific questions until projects are added to kickstart_verified_tokens.json."
        )
    lines = [
        "## Active allowlist (ONLY these tokens - refuse all others)",
        f"Verified Kickstart projects: **{len(tokens)}**",
        "",
    ]
    for t in tokens:
        lines.append(
            f"- **{t.get('symbol')}** ({t.get('name')}) · mint `{t.get('mint')}` · "
            f"launched {t.get('launch_date', 'n/a')}"
        )
    lines.append("")
    lines.append(
        "If the user asks about any other token or project, refuse and redirect them to this list."
    )
    return "\n".join(lines)


def is_verified_kickstart_token(token: str) -> bool:
    if not registry_is_enforced():
        return True
    return find_verified_token(token) is not None


def require_verified_token(token: str) -> dict[str, Any]:
    """Return registry entry or an error payload."""
    if not registry_is_enforced():
        return {"enforced": False}
    entry = find_verified_token(token)
    if not entry:
        active = active_verified_tokens()
        names = ", ".join(t.get("symbol") or "?" for t in active) or "none"
        return {
            "error": (
                f"'{token}' is not an EasyA Kickstart verified token. "
                f"This copilot only covers: {names}. "
                "Use list_verified_kickstart_tokens to see full details."
            ),
            "verified_only": True,
            "allowed_symbols": [t.get("symbol") for t in active],
        }
    return {"enforced": True, "registry": entry}


def list_verified_kickstart_tokens(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    active_only: bool = True,
    query: Optional[str] = None,
) -> dict[str, Any]:
    tokens = load_verified_tokens()
    if active_only:
        tokens = [t for t in tokens if t.get("active", True)]

    cat = (category or "").strip().lower()
    tag_q = (tag or "").strip().lower()
    q = (query or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    for t in tokens:
        if cat and str(t.get("category") or "").lower() != cat:
            continue
        tags = [str(x).lower() for x in (t.get("tags") or [])]
        if tag_q and tag_q not in tags and tag_q not in str(t.get("name") or "").lower():
            if tag_q not in str(t.get("symbol") or "").lower():
                continue
        if q:
            hay = " ".join(
                [
                    str(t.get("symbol") or ""),
                    str(t.get("name") or ""),
                    str(t.get("category") or ""),
                    str(t.get("description") or ""),
                    " ".join(tags),
                ]
            ).lower()
            if q not in hay:
                continue
        filtered.append(
            {
                "symbol": t.get("symbol"),
                "name": t.get("name"),
                "mint": t.get("mint"),
                "category": t.get("category"),
                "tags": t.get("tags") or [],
                "launch_date": t.get("launch_date"),
                "description": t.get("description"),
                "website": t.get("website"),
                "docs": t.get("docs"),
                "verified_at": t.get("verified_at"),
                "active": t.get("active", True),
            }
        )

    return {
        "registry_file": str(REGISTRY_FILE),
        "enforced": registry_is_enforced(),
        "count": len(filtered),
        "tokens": filtered,
    }


def merge_registry_metadata(bundle: dict[str, Any], registry_entry: dict[str, Any]) -> dict[str, Any]:
    """Overlay curated EasyA fields onto live market data."""
    bundle["easya_verified"] = True
    bundle["registry"] = {
        "symbol": registry_entry.get("symbol"),
        "name": registry_entry.get("name"),
        "mint": registry_entry.get("mint"),
        "category": registry_entry.get("category"),
        "tags": registry_entry.get("tags") or [],
        "launch_date": registry_entry.get("launch_date"),
        "description": registry_entry.get("description"),
        "verified_at": registry_entry.get("verified_at"),
    }
    links = bundle.setdefault("links", {})
    for key in ("website", "docs", "twitter", "telegram", "discord"):
        if registry_entry.get(key):
            links[key] = registry_entry[key]
    return bundle
