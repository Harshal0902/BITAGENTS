"""
Self-hosted Ollama chat API client (llm.bitagents.app).

Replaces OpenRouter when HOSTED_OLLAMA_URL / HOSTED_MODEL_API_KEY are set.
Docs: POST {base}/api/chat with X-API-Key header, stream=false for full JSON.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests

DEFAULT_HOSTED_MODEL = "llama3.2:3b"
DEFAULT_HOSTED_BASE_URL = "https://llm.bitagents.app"


def _looks_like_model_tag(value: str) -> bool:
    if not value:
        return False
    if value.startswith("llama") or value.startswith("mistral") or value.startswith("qwen"):
        return True
    return bool(re.fullmatch(r"[\w.-]+:[\w.-]+", value))


def _normalize_base_url(value: str) -> str:
    value = (value or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith("http"):
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.netloc:
        return ""
    return value.rstrip("/")


def resolve_hosted_base_url() -> str:
    explicit = (
        os.environ.get("HOSTED_OLLAMA_BASE_URL")
        or os.environ.get("HOSTED_OLLAMA_URL")
        or ""
    ).strip()
    if explicit:
        return _normalize_base_url(explicit) or DEFAULT_HOSTED_BASE_URL

    legacy = os.environ.get("HOSTED_OLLAMA_MODEL", "").strip()
    if legacy and not _looks_like_model_tag(legacy):
        return _normalize_base_url(legacy) or DEFAULT_HOSTED_BASE_URL

    return DEFAULT_HOSTED_BASE_URL


def resolve_hosted_model_name() -> str:
    legacy = os.environ.get("HOSTED_OLLAMA_MODEL", "").strip()
    if legacy and _looks_like_model_tag(legacy):
        return legacy
    return (
        os.environ.get("HOSTED_OLLAMA_MODEL_NAME")
        or os.environ.get("OLLAMA_MODEL")
        or DEFAULT_HOSTED_MODEL
    )


HOSTED_OLLAMA_BASE_URL = resolve_hosted_base_url()
HOSTED_OLLAMA_MODEL = resolve_hosted_model_name()
HOSTED_OLLAMA_API_KEY = (
    os.environ.get("HOSTED_MODEL_API_KEY")
    or os.environ.get("HOSTED_OLLAMA_API_KEY")
    or ""
).strip()

# Legacy OpenRouter (optional fallback)
OPEN_ROUTER_API = (
    os.environ.get("OPEN_ROUTER_API", "")
    or os.environ.get("OPENROUTER_API_KEY", "")
).strip()
OPEN_ROUTER_API_URL = os.environ.get(
    "OPEN_ROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)
OPEN_ROUTER_SITE_URL = os.environ.get("OPEN_ROUTER_SITE_URL", "https://bitagents.app")
OPEN_ROUTER_APP_NAME = os.environ.get("OPEN_ROUTER_APP_NAME", "BIT Agents")


def use_hosted_ollama() -> bool:
    return bool(HOSTED_OLLAMA_API_KEY)


def llm_provider() -> str:
    if use_hosted_ollama():
        return "hosted_ollama"
    if OPEN_ROUTER_API:
        return "openrouter"
    return "unconfigured"


def llm_configured() -> bool:
    return use_hosted_ollama() or bool(OPEN_ROUTER_API)


def _hosted_headers() -> dict[str, str]:
    if not HOSTED_OLLAMA_API_KEY:
        raise RuntimeError(
            "HOSTED_MODEL_API_KEY is not set. Add it to agent/new/.env (see .env.example)."
        )
    return {
        "Content-Type": "application/json",
        "X-API-Key": HOSTED_OLLAMA_API_KEY,
    }


def _openrouter_headers(app_suffix: str = "") -> dict[str, str]:
    if not OPEN_ROUTER_API:
        raise RuntimeError(
            "OPEN_ROUTER_API is not set. Configure hosted Ollama or OpenRouter in agent/new/.env."
        )
    title = OPEN_ROUTER_APP_NAME
    if app_suffix:
        title = f"{title} {app_suffix}".strip()
    return {
        "Authorization": f"Bearer {OPEN_ROUTER_API}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPEN_ROUTER_SITE_URL,
        "X-Title": title,
    }


def _error_from_response(resp: requests.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body.get("error"), str):
            return body["error"]
        if isinstance(body.get("error"), dict) and body["error"].get("message"):
            return str(body["error"]["message"])
        if body.get("message"):
            return str(body["message"])
    except Exception:
        pass
    return resp.text or resp.reason or "Unknown error"


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not tool_calls:
        return []
    normalized: list[dict[str, Any]] = []
    for idx, tc in enumerate(tool_calls):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name")
        arguments = fn.get("arguments", tc.get("arguments", {}))
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments)
        normalized.append(
            {
                "id": tc.get("id") or f"call_{idx}",
                "type": tc.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": arguments or "{}",
                },
            }
        )
    return normalized


def _normalize_assistant_message(raw: dict[str, Any]) -> dict[str, Any]:
    message = dict(raw or {})
    message.setdefault("role", "assistant")
    if message.get("tool_calls"):
        message["tool_calls"] = _normalize_tool_calls(message["tool_calls"])
    return message


def call_hosted_ollama(
    messages: list,
    *,
    model: Optional[str] = None,
    tools: Optional[list] = None,
    temperature: float = 0.2,
    stream: bool = False,
) -> dict[str, Any]:
    """Call self-hosted Ollama /api/chat. Returns OpenAI-shaped {\"message\": ...}."""
    payload: dict[str, Any] = {
        "model": model or HOSTED_OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools

    url = f"{HOSTED_OLLAMA_BASE_URL}/api/chat"
    last_error = "Unknown hosted Ollama error"
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=_hosted_headers(),
                timeout=180,
                stream=stream,
            )
        except requests.exceptions.RequestException as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"Cannot reach hosted Ollama API at {url}: {last_error}") from exc

        if resp.status_code >= 400:
            last_error = _error_from_response(resp)
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(
                f"Hosted Ollama API error ({resp.status_code}): {last_error}"
            )

        if stream:
            raise RuntimeError("Streaming responses are not used by the agent loop yet.")

        data = resp.json()
        message = data.get("message")
        if not isinstance(message, dict):
            last_error = "Hosted Ollama returned no message."
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(last_error)
        return {"message": _normalize_assistant_message(message)}

    raise RuntimeError(f"Hosted Ollama API error: {last_error}")


def call_openrouter(
    messages: list,
    *,
    model: str,
    tools: Optional[list] = None,
    temperature: float = 0.2,
    app_suffix: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    last_error = "Unknown OpenRouter error"
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                OPEN_ROUTER_API_URL,
                json=payload,
                headers=_openrouter_headers(app_suffix),
                timeout=180,
            )
        except requests.exceptions.RequestException as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"Cannot reach OpenRouter API: {last_error}") from exc

        if resp.status_code >= 400:
            last_error = _error_from_response(resp)
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"OpenRouter API error ({resp.status_code}): {last_error}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            last_error = "OpenRouter returned no choices."
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(last_error)
        message = choices[0].get("message") or {}
        return {"message": _normalize_assistant_message(message)}

    raise RuntimeError(f"OpenRouter API error: {last_error}")


def call_llm(
    messages: list,
    *,
    model: str,
    tools: Optional[list] = None,
    temperature: float = 0.2,
    app_suffix: str = "",
) -> dict[str, Any]:
    """Primary LLM entry: hosted Ollama when configured, else OpenRouter."""
    if use_hosted_ollama():
        return call_hosted_ollama(
            messages,
            model=model or HOSTED_OLLAMA_MODEL,
            tools=tools,
            temperature=temperature,
        )
    return call_openrouter(
        messages,
        model=model,
        tools=tools,
        temperature=temperature,
        app_suffix=app_suffix,
    )
