"""P2 acceptance: an MCP agent's read flows, its write physically cannot
happen without human approval, and both paths land in the ledger."""

import threading
import time

import pytest

from verdictplane.gate import Gate
from verdictplane.interceptor import ApprovalDenied, PolicyDenied
from verdictplane.mcp import governed_dispatch, guard_mcp_call
from verdictplane.provenance import Ledger

POLICY = {
    "default": "require_human",
    "rules": [
        {"match": {"effect": "read"}, "decision": "allow"},
        {"match": {"tool": "delete_repo"}, "decision": "deny"},
        {"match": {"effect": "write"}, "decision": "require_human"},
    ],
}

EFFECTS = {"read_file": "read", "write_file": "write", "list_dir": "read"}


@pytest.fixture()
def world(tmp_path):
    """A tiny MCP-style tool server over a real file, plus governed dispatch."""
    target = tmp_path / "notes.txt"
    target.write_text("original\n")

    def dispatch(tool, arguments):
        if tool == "read_file":
            return target.read_text()
        if tool == "write_file":
            target.write_text(arguments["content"])
            return "written"
        raise ValueError(tool)

    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    gate = Gate(str(tmp_path / "gate"), poll_interval=0.01)
    call_tool = governed_dispatch(
        dispatch, policy=POLICY, ledger=ledger, gate=gate,
        effect_of=EFFECTS, agent="mcp-agent",
    )
    return {"call": call_tool, "ledger": ledger, "gate": gate, "target": target}


def outcomes(ledger):
    return [(e["record"]["action"]["tool"], e["record"]["outcome"]) for e in ledger.entries()]


def test_agent_read_flows(world):
    assert world["call"]("read_file", {"path": "notes.txt"}) == "original\n"
    assert outcomes(world["ledger"]) == [("read_file", "executed")]


def test_agent_write_physically_blocked_without_approval(world):
    call = governed_dispatch(
        lambda t, a: (_ for _ in ()).throw(AssertionError("dispatch must not run")),
        policy=POLICY, ledger=world["ledger"], gate=world["gate"],
        effect_of=EFFECTS, agent="mcp-agent", gate_timeout=0.15,
    )
    with pytest.raises(ApprovalDenied):
        call("write_file", {"path": "notes.txt", "content": "hacked\n"})
    assert world["target"].read_text() == "original\n"  # file untouched
    assert outcomes(world["ledger"]) == [("write_file", "pending"), ("write_file", "denied_by_human")]


def test_agent_write_executes_after_human_approval(world):
    def approve():
        time.sleep(0.1)
        world["gate"].approve(world["gate"].list_pending()[0]["token"], by="frank")

    t = threading.Thread(target=approve)
    t.start()
    assert world["call"]("write_file", {"path": "notes.txt", "content": "approved\n"}) == "written"
    t.join()
    assert world["target"].read_text() == "approved\n"
    assert outcomes(world["ledger"]) == [("write_file", "pending"), ("write_file", "executed")]


def test_agent_full_session_both_paths_in_ledger(world):
    def deny():
        time.sleep(0.1)
        world["gate"].deny(world["gate"].list_pending()[0]["token"], by="frank")

    assert world["call"]("read_file", {"path": "notes.txt"}) == "original\n"
    threading.Thread(target=deny).start()
    with pytest.raises(ApprovalDenied):
        world["call"]("write_file", {"path": "notes.txt", "content": "nope\n"})
    assert world["target"].read_text() == "original\n"
    assert outcomes(world["ledger"]) == [
        ("read_file", "executed"),
        ("write_file", "pending"),
        ("write_file", "denied_by_human"),
    ]
    assert world["ledger"].verify() == (True, None)


def test_denied_tool_blocked_at_boundary(world):
    with pytest.raises(PolicyDenied):
        world["call"]("delete_repo", {})
    assert outcomes(world["ledger"]) == [("delete_repo", "blocked")]


def test_unknown_tool_defaults_to_write_and_safe_default(world):
    with pytest.raises(ApprovalDenied):
        guard_mcp_call(
            "mystery_tool", {}, lambda t, a: "ran",
            policy=POLICY, ledger=world["ledger"], gate=world["gate"],
            effect_of=EFFECTS, gate_timeout=0.1,
        )
    (tool, first), (_, last) = outcomes(world["ledger"])
    assert tool == "mystery_tool" and (first, last) == ("pending", "denied_by_human")


def test_effect_of_accepts_callable(world):
    call = governed_dispatch(
        lambda t, a: "ok", policy=POLICY, ledger=world["ledger"], gate=world["gate"],
        effect_of=lambda tool: "read",
    )
    assert call("anything") == "ok"
    assert outcomes(world["ledger"]) == [("anything", "executed")]


def test_arguments_are_redacted_in_ledger(world):
    def approve():
        time.sleep(0.1)
        world["gate"].approve(world["gate"].list_pending()[0]["token"])

    threading.Thread(target=approve).start()
    world["call"]("write_file", {"path": "notes.txt", "content": "x", "api_token": "s3cr3t"})
    assert "s3cr3t" not in open(world["ledger"].path).read()
