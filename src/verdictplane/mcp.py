"""Govern agent tool-calls at the MCP boundary.

Transport-agnostic: wrap whatever function actually dispatches an MCP tool
call (server-side call_tool handler, client-side session.call_tool, or a
router) with `governed_dispatch()`. Every tool call the agent makes then flows
through govern(): recorded, policy-checked, and human-gated before the tool
runs. The agent cannot reach the tool except through the wrapper.

`effect_of` maps a tool name to its effect class ("read", "write", ...) — a
dict or a callable. Unknown tools default to "write", which lands on the
policy's safe default rather than an implicit allow.

Enforcement-path module: deterministic, zero-egress, no model client.
"""

from .interceptor import current_agent, govern, redact


def _effect_resolver(effect_of):
    if callable(effect_of):
        return effect_of
    mapping = dict(effect_of or {})
    return lambda tool: mapping.get(tool, "write")  # unknown -> safe side


def guard_mcp_call(tool_name: str, arguments: dict | None, dispatch, *,
                   policy, ledger, gate, effect_of,
                   agent: str | None = None, gate_timeout: float | None = None):
    """Govern one MCP tool call; dispatch runs only if policy/human allow it."""
    action = {
        "tool": tool_name,
        "effect": _effect_resolver(effect_of)(tool_name),
        "args": redact(dict(arguments or {})),
        "agent": agent or current_agent(),
    }
    return govern(
        action, lambda: dispatch(tool_name, arguments),
        policy=policy, ledger=ledger, gate=gate, gate_timeout=gate_timeout,
    )


def governed_dispatch(dispatch, *, policy, ledger, gate, effect_of,
                      agent: str | None = None, gate_timeout: float | None = None):
    """Wrap an MCP dispatch function so every tool call is governed."""

    def wrapped(tool_name: str, arguments: dict | None = None):
        return guard_mcp_call(
            tool_name, arguments, dispatch,
            policy=policy, ledger=ledger, gate=gate, effect_of=effect_of,
            agent=agent, gate_timeout=gate_timeout,
        )

    return wrapped
