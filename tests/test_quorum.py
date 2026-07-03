"""T8 multi-reviewer quorum gate: k-of-n approvals, deny-veto, partial-never-executes,
cross-instance tally, and per-rule quorum through govern(). Backward compatible at quorum=1."""

import threading
import time

from verdictplane.gate import Gate
from verdictplane.interceptor import govern
from verdictplane.provenance import Ledger

ACTION = {"tool": "db.write", "effect": "write", "args": {}, "agent": "svc"}


def _gate(tmp_path, **kw):
    return Gate(str(tmp_path / "gate"), poll_interval=0.01, **kw)


def test_quorum_one_is_backward_compatible(tmp_path):
    g = _gate(tmp_path)
    g.submit("t", ACTION)
    res = g.approve("t", by="frank")
    assert res["approved"] is True and res["resolved_by"] == "frank"
    assert g.resolution("t")["approved"] is True


def test_two_of_three_stays_pending_until_quorum(tmp_path):
    g = _gate(tmp_path)
    g.submit("t", ACTION, quorum=3)
    r1 = g.approve("t", by="alice")
    assert r1["approved"] is None and r1["remaining"] == 2   # not final
    assert g.resolution("t") is None                          # nothing executes yet
    r2 = g.approve("t", by="bob")
    assert r2["approved"] is None and r2["remaining"] == 1
    r3 = g.approve("t", by="carol")
    assert r3["approved"] is True
    assert sorted(g.resolution("t")["approved_by"]) == ["alice", "bob", "carol"]


def test_duplicate_reviewer_counts_once(tmp_path):
    g = _gate(tmp_path)
    g.submit("t", ACTION, quorum=2)
    g.approve("t", by="alice")
    r = g.approve("t", by="alice")             # same identity again
    assert r["approved"] is None and r["remaining"] == 1   # still one distinct approval


def test_deny_is_a_veto_even_after_approvals(tmp_path):
    g = _gate(tmp_path)
    g.submit("t", ACTION, quorum=3)
    g.approve("t", by="alice")
    g.approve("t", by="bob")
    res = g.deny("t", by="carol")
    assert res["approved"] is False and res["resolved_by"] == "carol"
    assert g.resolution("t")["approved"] is False


def test_cross_instance_tally(tmp_path):
    root = str(tmp_path / "gate")
    g1 = Gate(root, poll_interval=0.01, quorum=2)
    g2 = Gate(root, poll_interval=0.01)        # different instance, same root (another process)
    g1.submit("t", ACTION, quorum=2)
    g2.approve("t", by="alice")
    res = g1.approve("t", by="bob")            # the first instance completes the quorum
    assert res["approved"] is True
    assert g2.resolution("t")["approved"] is True


def test_await_approval_reaches_quorum_via_threads(tmp_path):
    g = _gate(tmp_path)

    def approve_soon(by):
        for _ in range(400):
            if g.list_pending():
                g.approve("t", by=by)
                return
            time.sleep(0.005)

    threads = [threading.Thread(target=approve_soon, args=(n,)) for n in ("alice", "bob")]
    for t in threads:
        t.start()
    ok = g.await_approval("t", ACTION, timeout=3.0, quorum=2)
    for t in threads:
        t.join()
    assert ok is True


def test_await_approval_times_out_denied_under_quorum(tmp_path):
    g = _gate(tmp_path)
    approver = threading.Thread(target=lambda: (time.sleep(0.05), g.approve("t", by="alice")))
    approver.start()
    ok = g.await_approval("t", ACTION, timeout=0.3, quorum=2)  # only 1 of 2 ever approves
    approver.join()
    assert ok is False                          # never reached quorum -> fail-safe deny


def test_govern_respects_per_rule_quorum_and_records_approvers(tmp_path):
    policy = {"default": "require_human",
              "rules": [{"match": {"tool": "db.write"}, "decision": "require_human", "quorum": 2}]}
    ledger = Ledger(str(tmp_path / "l.jsonl"))
    gate = _gate(tmp_path)

    def two_approvals():
        for _ in range(400):
            pending = gate.list_pending()
            if pending:
                token = pending[0]["token"]
                gate.approve(token, by="alice")
                gate.approve(token, by="bob")
                return
            time.sleep(0.005)

    t = threading.Thread(target=two_approvals)
    t.start()
    result = govern(dict(ACTION), lambda: "done", policy=policy, ledger=ledger, gate=gate,
                    gate_timeout=3.0)
    t.join()
    assert result == "done"
    executed = [e["record"] for e in ledger.entries() if e["record"]["outcome"] == "executed"][0]
    assert sorted(executed["approved_by"]) == ["alice", "bob"]
