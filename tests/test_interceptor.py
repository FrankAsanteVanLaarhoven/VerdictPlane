"""P1 acceptance: deny blocks and is logged; require_human blocks until resolved;
executed path recorded; no governed side effect ever runs un-logged."""

import threading
import time

import pytest

from keystone.gate import Gate
from keystone.interceptor import (
    ApprovalDenied,
    PolicyDenied,
    govern,
    governed,
    redact,
    set_agent,
)
from keystone.provenance import Ledger

POLICY = {
    "default": "require_human",
    "rules": [
        {"match": {"effect": "read"}, "decision": "allow"},
        {"match": {"agent": "untrusted", "effect": "write"}, "decision": "deny"},
        {"match": {"tool": "notes.append"}, "decision": "allow"},
    ],
}


@pytest.fixture()
def env(tmp_path):
    return {
        "policy": POLICY,
        "ledger": Ledger(str(tmp_path / "ledger.jsonl")),
        "gate": Gate(str(tmp_path / "gate"), poll_interval=0.01),
    }


def outcomes(ledger):
    return [e["record"]["outcome"] for e in ledger.entries()]


# ---- allow path ----

def test_allowed_action_executes_and_is_recorded(env):
    calls = []
    result = govern(
        {"tool": "notes.append", "effect": "write", "args": {"text": "hi"}},
        lambda: calls.append(1) or "ok", **env,
    )
    assert result == "ok" and calls == [1]
    assert outcomes(env["ledger"]) == ["executed"]
    assert env["ledger"].verify() == (True, None)


# ---- deny path ----

def test_denied_action_blocks_before_side_effect(env):
    calls = []
    with pytest.raises(PolicyDenied):
        govern(
            {"tool": "db.write", "effect": "write", "agent": "untrusted"},
            lambda: calls.append(1), **env,
        )
    assert calls == []  # side effect never ran
    assert outcomes(env["ledger"]) == ["blocked"]


# ---- require_human paths ----

def test_gated_action_blocks_until_approved(env):
    calls = []
    approved_at = {}

    def approve_later():
        time.sleep(0.15)
        pending = env["gate"].list_pending()
        assert len(pending) == 1
        approved_at["t"] = time.monotonic()
        env["gate"].approve(pending[0]["token"], by="frank")

    t = threading.Thread(target=approve_later)
    t.start()
    result = govern(
        {"tool": "email.send", "effect": "write", "args": {"to": "x@y.z"}},
        lambda: calls.append(time.monotonic()) or "sent", **env,
    )
    t.join()
    assert result == "sent"
    assert calls[0] >= approved_at["t"]  # executed only after human approval
    assert outcomes(env["ledger"]) == ["pending", "executed"]


def test_gated_action_denied_by_human(env):
    calls = []

    def deny_later():
        time.sleep(0.1)
        env["gate"].deny(env["gate"].list_pending()[0]["token"], by="frank")

    t = threading.Thread(target=deny_later)
    t.start()
    with pytest.raises(ApprovalDenied):
        govern({"tool": "email.send", "effect": "write"}, lambda: calls.append(1), **env)
    t.join()
    assert calls == []
    assert outcomes(env["ledger"]) == ["pending", "denied_by_human"]


def test_gate_timeout_is_fail_safe_denied(env):
    calls = []
    with pytest.raises(ApprovalDenied):
        govern(
            {"tool": "email.send", "effect": "write"},
            lambda: calls.append(1), gate_timeout=0.15, **env,
        )
    assert calls == []
    assert outcomes(env["ledger"]) == ["pending", "denied_by_human"]
    token = next(e["record"]["token"] for e in env["ledger"].entries() if "token" in e["record"])
    resolved = env["gate"].resolution(token)
    assert resolved["resolved_by"] == "timeout" and resolved["approved"] is False


# ---- failure path ----

def test_failed_call_recorded_and_reraised(env):
    def boom():
        raise RuntimeError("db unreachable")

    with pytest.raises(RuntimeError):
        govern({"tool": "notes.append", "effect": "write"}, boom, **env)
    assert outcomes(env["ledger"]) == ["failed"]


# ---- decorator ----

def test_governed_decorator_binds_args_and_redacts(env):
    seen = []

    @governed(effect="write", tool="db.write", **env)
    def write_row(table, amount, api_key="k"):
        seen.append((table, amount))
        return "written"

    set_agent("pipeline")
    with pytest.raises(ApprovalDenied):  # default require_human, timeout via thread deny
        threading.Thread(
            target=lambda: (time.sleep(0.1), env["gate"].deny(env["gate"].list_pending()[0]["token"]))
        ).start() or write_row("users", 5000, api_key="s3cr3t")
    assert seen == []
    entry = list(env["ledger"].entries())[0]["record"]
    assert entry["action"]["tool"] == "db.write"
    assert entry["action"]["agent"] == "pipeline"
    assert entry["action"]["args"]["api_key"] == "[REDACTED]"
    assert "s3cr3t" not in str(entry)
    assert entry["action"]["args"] == {"table": "users", "amount": 5000, "api_key": "[REDACTED]"}


def test_governed_read_flows_without_gate(env):
    @governed(effect="read", **env)
    def fetch_rows(table):
        return ["row"]

    assert fetch_rows("users") == ["row"]
    assert outcomes(env["ledger"]) == ["executed"]


# ---- completeness: no governed call is un-logged ----

def test_provenance_completeness_over_mixed_workload(env):
    TERMINAL = {"executed", "blocked", "denied_by_human", "failed"}
    executed_spy = []

    @governed(effect="read", tool="q.read", **env)
    def read_q():
        executed_spy.append(1)

    @governed(effect="write", tool="q.write", **env)
    def write_q():
        executed_spy.append(1)

    attempts = 0
    for i in range(30):
        attempts += 1
        if i % 3 == 0:
            read_q()
        elif i % 3 == 1:
            set_agent("untrusted")
            with pytest.raises(PolicyDenied):
                write_q()
            set_agent("trusted")
        else:
            with pytest.raises(ApprovalDenied):
                govern({"tool": "q.gated", "effect": "write"}, lambda: executed_spy.append(1),
                       gate_timeout=0.05, **env)

    terminal = [o for o in outcomes(env["ledger"]) if o in TERMINAL]
    assert len(terminal) == attempts  # exactly one terminal record per governed call
    assert len(executed_spy) == terminal.count("executed")  # every side effect logged
    assert env["ledger"].verify() == (True, None)


# ---- redaction unit ----

def test_redact_masks_and_truncates():
    out = redact({"password": "p", "nested": {"auth_token": "t"}, "blob": "x" * 500, "n": 3})
    assert out["password"] == "[REDACTED]"
    assert out["nested"]["auth_token"] == "[REDACTED]"
    assert out["blob"].endswith("...[truncated]") and len(out["blob"]) < 300
    assert out["n"] == 3
