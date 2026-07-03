"""P3 acceptance: a human resolves blocked actions via the CLI; verify/log/head
work; advisory is opt-in and its absence never blocks the reviewer."""

import json
import threading
import time

import pytest

from keystone.cli import main
from keystone.gate import Gate
from keystone.interceptor import ApprovalDenied, govern
from keystone.provenance import Ledger

POLICY = {"default": "require_human", "rules": [{"match": {"effect": "read"}, "decision": "allow"}]}


@pytest.fixture()
def paths(tmp_path):
    return {"ledger": str(tmp_path / "ledger.jsonl"), "gate": str(tmp_path / "gate")}


def run_cli(paths, *argv):
    return main(["--ledger", paths["ledger"], "--gate", paths["gate"], *argv])


@pytest.fixture()
def env(paths):
    return {
        "policy": POLICY,
        "ledger": Ledger(paths["ledger"]),
        "gate": Gate(paths["gate"], poll_interval=0.01),
    }


def test_pending_empty(paths, capsys):
    Gate(paths["gate"])  # create dirs
    assert run_cli(paths, "pending") == 0
    assert "no pending approvals" in capsys.readouterr().out


def test_cli_approve_unblocks_interceptor(paths, env, capsys):
    result = {}

    def blocked_call():
        result["value"] = govern(
            {"tool": "email.send", "effect": "write", "args": {"to": "x@y.z"}},
            lambda: "sent", **env,
        )

    t = threading.Thread(target=blocked_call)
    t.start()
    for _ in range(100):  # wait for the pending file to appear
        if env["gate"].list_pending():
            break
        time.sleep(0.01)

    assert run_cli(paths, "pending") == 0
    out = capsys.readouterr().out
    assert "email.send" in out and "x@y.z" in out

    token = env["gate"].list_pending()[0]["token"]
    assert run_cli(paths, "approve", token[:12], "--by", "frank") == 0
    t.join(timeout=5)
    assert result["value"] == "sent"
    resolved = env["gate"].resolution(token)
    assert resolved["resolved_by"] == "frank" and resolved["approved"] is True


def test_cli_deny_blocks_interceptor(paths, env):
    errors = []

    def blocked_call():
        try:
            govern({"tool": "db.write", "effect": "write"}, lambda: "written", **env)
        except ApprovalDenied as e:
            errors.append(e)

    t = threading.Thread(target=blocked_call)
    t.start()
    for _ in range(100):
        if env["gate"].list_pending():
            break
        time.sleep(0.01)
    token = env["gate"].list_pending()[0]["token"]
    assert run_cli(paths, "deny", token, "--by", "frank") == 0
    t.join(timeout=5)
    assert len(errors) == 1
    outcomes = [e["record"]["outcome"] for e in env["ledger"].entries()]
    assert outcomes == ["pending", "denied_by_human"]


def test_cli_resolve_unknown_and_ambiguous(paths, env):
    with pytest.raises(SystemExit):
        run_cli(paths, "approve", "deadbeef")
    env["gate"].submit("a" * 64, {"tool": "t1"})
    env["gate"].submit("a" * 63 + "b", {"tool": "t2"})
    with pytest.raises(SystemExit):  # shared prefix -> ambiguous
        run_cli(paths, "approve", "aaaa")


def test_cli_verify_and_tamper(paths, env, capsys):
    for i in range(5):
        env["ledger"].append({"action": {"tool": f"t{i}"}, "outcome": "executed"})
    assert run_cli(paths, "verify") == 0
    assert "ledger ok (5 entries" in capsys.readouterr().out

    lines = open(paths["ledger"]).read().splitlines()
    entry = json.loads(lines[2])
    entry["record"]["outcome"] = "tampered"
    lines[2] = json.dumps(entry, sort_keys=True)
    with open(paths["ledger"], "w") as f:
        f.write("\n".join(lines) + "\n")
    assert run_cli(paths, "verify") == 1
    assert "TAMPERED at line 2" in capsys.readouterr().out


def test_cli_head_matches_ledger(paths, env, capsys):
    env["ledger"].append({"k": "v"})
    assert run_cli(paths, "head") == 0
    assert capsys.readouterr().out.strip() == env["ledger"].head()


def test_cli_log_filters(paths, env, capsys):
    env["ledger"].append({"action": {"tool": "db.write", "agent": "a"}, "decision": "allow", "outcome": "executed"})
    env["ledger"].append({"action": {"tool": "email.send", "agent": "a"}, "decision": "deny", "outcome": "blocked"})
    assert run_cli(paths, "log", "--tool", "db.*") == 0
    out = capsys.readouterr().out
    assert "db.write" in out and "email.send" not in out
    assert run_cli(paths, "log", "--outcome", "blocked") == 0
    out = capsys.readouterr().out
    assert "email.send" in out and "db.write" not in out


def test_pending_without_advisory_backend_still_reviews(paths, env, capsys, monkeypatch):
    """--advise with no backend configured degrades to a note, never an error."""
    monkeypatch.setenv("KEYSTONE_ADVISORY", "off")
    env["gate"].submit("c" * 64, {"tool": "email.send", "effect": "write", "args": {}, "agent": "x"})
    assert run_cli(paths, "pending", "--advise") == 0
    out = capsys.readouterr().out
    assert "email.send" in out and "advisory: (unavailable" in out
