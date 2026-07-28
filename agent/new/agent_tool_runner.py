"""Shared tool-calling loop for research-style agents."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from hosted_llm import call_llm

ToolFn = Callable[..., Any]


def execute_tool(name: str, args: dict[str, Any], registry: dict[str, ToolFn], **ctx) -> str:
    fn = registry.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool '{name}'."})
    try:
        result = fn(**args, **{k: v for k, v in ctx.items() if k in ("user_wallet", "session_id")})
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2, default=str)
    except TypeError as exc:
        return json.dumps({"error": str(exc), "received_args": args})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def run_tool_agent(
    user_input: str,
    conversation_history: list,
    *,
    system_prompt: str,
    tools: list,
    tool_registry: dict[str, ToolFn],
    model: str,
    app_suffix: str,
    user_wallet: Optional[str] = None,
    session_id: Optional[str] = None,
    max_rounds: int = 10,
) -> tuple[str, list, list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    prompt = user_input.strip()
    if user_wallet:
        prompt = f"[Connected user wallet: {user_wallet}]\n{prompt}"

    conversation_history.append({"role": "user", "content": prompt})
    messages = [{"role": "system", "content": system_prompt}] + conversation_history

    for _ in range(max_rounds):
        response = call_llm(
            messages,
            model=model,
            tools=tools,
            temperature=0.3,
            app_suffix=app_suffix,
        )
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            reply = (message.get("content") or "").strip()
            if not reply and actions:
                reply = "I completed the requested checks. See tool results above."
            conversation_history.append({"role": "assistant", "content": reply})
            return reply, conversation_history, actions

        sanitized: list[dict[str, Any]] = []
        parsed: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for idx, tc in enumerate(tool_calls):
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            call_id = tc.get("id") or f"call_{idx}"
            sanitized.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, separators=(",", ":"))},
                }
            )
            parsed.append((name, args, tc))

        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": sanitized})
        for name, args, tc in parsed:
            result = execute_tool(name, args, tool_registry, user_wallet=user_wallet, session_id=session_id)
            actions.append({"tool": name, "args": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "call"),
                    "tool_name": name,
                    "content": result,
                }
            )

    reply = "I hit the tool limit. Please ask a narrower question."
    conversation_history.append({"role": "assistant", "content": reply})
    return reply, conversation_history, actions
