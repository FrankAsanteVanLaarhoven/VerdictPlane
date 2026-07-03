"""In-path enforcement: deterministic policy check + provenance + human gate.

`govern()` is the one choke point: it evaluates policy (no model), appends the
decision to the tamper-evident ledger BEFORE any side effect, blocks on the
human gate when required, and records the terminal outcome. A governed side
effect cannot run un-recorded, and cannot run at all if policy denies it or a
human does not approve it.

Enforcement-path module: deterministic, zero-egress, no model client.
"""

import functools
import inspect
import re
from contextvars import ContextVar

from .policy import DENY, REQUIRE_HUMAN, evaluate
from .types import Action

_agent: ContextVar[str] = ContextVar("keystone_agent", default="unknown")

_SECRET_KEY = re.compile(
    r"password|passwd|secret|token|api_?key|authorization|credential|private_key",
    re.IGNORECASE,
)
_MAX_VALUE_LEN = 256


class PolicyDenied(Exception):
    """Action blocked by policy before any side effect ran."""


class ApprovalDenied(Exception):
    """Action required human approval and did not get it (deny or timeout)."""


def set_agent(name: str):
    """Set the agent identity recorded for governed calls in this context."""
    return _agent.set(name)


def current_agent() -> str:
    return _agent.get()


def redact(args: dict) -> dict:
    """Provenance-safe copy of call args: secrets masked, long values truncated."""
    out = {}
    for key, value in args.items():
        if _SECRET_KEY.search(str(key)):
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = redact(value)
        elif isinstance(value, (int, float, bool, type(None))):
            out[key] = value
        else:
            text = str(value)
            out[key] = text if len(text) <= _MAX_VALUE_LEN else text[:_MAX_VALUE_LEN] + "...[truncated]"
    return out


def govern(action: dict, call, *, policy, ledger, gate, gate_timeout: float | None = None):
    """Enforce policy on one action, record provenance, then (maybe) execute."""
    action = Action.model_validate(action).model_dump()
    decision, rule = evaluate(action, policy)  # deterministic, no model
    base = {"action": action, "decision": decision, "rule": rule}

    if decision == DENY:
        ledger.append({**base, "outcome": "blocked"})
        raise PolicyDenied(f"{action['tool']}: denied by policy")

    if decision == REQUIRE_HUMAN:
        token = ledger.append({**base, "outcome": "pending"})
        base = {**base, "token": token}
        if not gate.await_approval(token, action, timeout=gate_timeout):
            ledger.append({**base, "outcome": "denied_by_human"})
            raise ApprovalDenied(f"{action['tool']}: not approved")

    try:
        result = call()  # only now does the side effect run
    except Exception as e:
        ledger.append({**base, "outcome": "failed", "error": repr(e)[:500]})
        raise
    ledger.append({**base, "outcome": "executed"})
    return result


def governed(effect: str = "write", tool: str | None = None, *,
             policy, ledger, gate, gate_timeout: float | None = None):
    """Decorator: route every call of a tool function through govern()."""

    def deco(fn):
        name = tool or fn.__name__
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                call_args = dict(bound.arguments)
            except TypeError:
                # signature mismatch: still record, let the call raise naturally
                call_args = {"args": [repr(a) for a in args], "kwargs": dict(kwargs)}
            action = {
                "tool": name,
                "effect": effect,
                "args": redact(call_args),
                "agent": current_agent(),
            }
            return govern(
                action, lambda: fn(*args, **kwargs),
                policy=policy, ledger=ledger, gate=gate, gate_timeout=gate_timeout,
            )

        return wrapper

    return deco
