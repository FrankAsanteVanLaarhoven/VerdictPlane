"""P4 acceptance, keyed to the phase-gate KPIs:
1. 100% governed-call ledger coverage      -> test_kpi_provenance_completeness
2. 100% human-gated side-effect blocking   -> promote/rollback block tests
3. 0 advisory imports in enforcement path  -> test_enforcement_imports.py (P3)
4. 100% tamper detection after execution   -> test_kpi_end_to_end_verifiability
5. 100% workload tests passing             -> this module in `make test`
"""

import os
import threading
import time

import pytest

from verdictplane.cli import main as cli_main
from verdictplane.gate import Gate
from verdictplane.interceptor import ApprovalDenied, PolicyDenied
from verdictplane.policy import load_policy
from verdictplane.provenance import Ledger
from workloads.driftguard_promote import build_action, governed_promote
from workloads.sentinel_action import governed_rollback, record_proposal

POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "workloads.yaml")

GATE_PASS = {"passed": True, "candidate_macro_f1": 0.91, "baseline_macro_f1": 0.85, "margin": 0.02}
GATE_FAIL = {"passed": False, "candidate_macro_f1": 0.79, "baseline_macro_f1": 0.85, "margin": 0.02,
             "reason": "candidate below baseline"}

# The report shape Sentinel's investigate() actually returns (incident_agent.py:40)
SENTINEL_METRICS = {"detected": True, "detect_t": 34, "localized": "productcatalog",
                    "root_cause_found": True}
SENTINEL_REPORT = "INCIDENT REPORT  (assistive - human approval required before any action)\n..."
SENTINEL_INCIDENT = {"service": "productcatalog", "change": "deploy v2.3.1", "detect_t": 34}


@pytest.fixture(scope="module")
def policy():
    return load_policy(POLICY_PATH)


@pytest.fixture()
def env(tmp_path, policy):
    return {
        "policy": policy,
        "ledger": Ledger(str(tmp_path / "ledger.jsonl")),
        "gate": Gate(str(tmp_path / "gate"), poll_interval=0.01),
    }


def outcomes(ledger):
    return [(e["record"]["action"]["tool"], e["record"]["outcome"]) for e in ledger.entries()]


def approve_when_pending(gate, by="frank"):
    for _ in range(200):
        pending = gate.list_pending()
        if pending:
            gate.approve(pending[0]["token"], by=by)
            return
        time.sleep(0.01)
    raise AssertionError("no pending approval appeared")


# ---- DriftGuard promotion ----

def test_failed_baseline_gate_is_deterministically_denied(env):
    promoted = []
    with pytest.raises(PolicyDenied):
        governed_promote("7", GATE_FAIL, promoted.append, **env)
    assert promoted == []  # side effect never ran; no human was even asked
    assert outcomes(env["ledger"]) == [("model.promote", "blocked")]
    record = next(env["ledger"].entries())["record"]
    assert record["action"]["args"]["baseline"] == {  # gate result IS the provenance
        "passed": False, "candidate_macro_f1": 0.79, "baseline_macro_f1": 0.85,
        "margin": 0.02, "reason": "candidate below baseline",
    }


def test_production_promotion_blocks_until_human_approves(env):
    promoted = []
    t = threading.Thread(target=approve_when_pending, args=(env["gate"],))
    t.start()
    governed_promote("7", GATE_PASS, promoted.append, **env)
    t.join()
    assert promoted == ["7"]
    assert outcomes(env["ledger"]) == [("model.promote", "pending"), ("model.promote", "executed")]


def test_production_promotion_denied_by_human_never_executes(env):
    promoted = []

    def deny():
        pending = []
        while not pending:
            pending = env["gate"].list_pending()
            time.sleep(0.01)
        env["gate"].deny(pending[0]["token"], by="frank")

    threading.Thread(target=deny).start()
    with pytest.raises(ApprovalDenied):
        governed_promote("8", GATE_PASS, promoted.append, **env)
    assert promoted == []
    assert outcomes(env["ledger"])[-1] == ("model.promote", "denied_by_human")


def test_production_promotion_timeout_fails_safe(env):
    promoted = []
    with pytest.raises(ApprovalDenied):
        governed_promote("9", GATE_PASS, promoted.append, gate_timeout=0.15, **env)
    assert promoted == []


def test_staging_promotion_with_passing_gate_flows(env):
    promoted = []
    governed_promote("7", GATE_PASS, promoted.append, stage="Staging", **env)
    assert promoted == ["7"]
    assert outcomes(env["ledger"]) == [("model.promote", "executed")]


def test_staging_promotion_with_failed_gate_still_denied(env):
    promoted = []
    with pytest.raises(PolicyDenied):
        governed_promote("7", GATE_FAIL, promoted.append, stage="Staging", **env)
    assert promoted == []


def test_unknown_stage_falls_to_safe_default(policy):
    from verdictplane.policy import evaluate
    action = build_action("7", "Shadow", GATE_PASS)
    assert evaluate(action, policy)[0] == "require_human"


# ---- Sentinel incident actions ----

def test_proposal_is_recorded_without_gate(env):
    result = record_proposal(SENTINEL_METRICS, SENTINEL_REPORT, **env)
    assert result == SENTINEL_REPORT
    ((tool, outcome),) = outcomes(env["ledger"])
    assert (tool, outcome) == ("incident.propose", "executed")
    args = next(env["ledger"].entries())["record"]["action"]["args"]
    assert args["service"] == "productcatalog"
    assert len(args["report_sha256"]) == 64  # report content-addressed in provenance


def test_rollback_requires_human_and_executes_after_approval(env):
    rolled_back = []
    t = threading.Thread(target=approve_when_pending, args=(env["gate"],))
    t.start()
    governed_rollback(SENTINEL_INCIDENT, rolled_back.append, **env)
    t.join()
    assert rolled_back == [SENTINEL_INCIDENT]
    assert outcomes(env["ledger"]) == [("incident.rollback", "pending"),
                                       ("incident.rollback", "executed")]


def test_rollback_timeout_never_executes(env):
    rolled_back = []
    with pytest.raises(ApprovalDenied):
        governed_rollback(SENTINEL_INCIDENT, rolled_back.append, gate_timeout=0.15, **env)
    assert rolled_back == []
    assert outcomes(env["ledger"])[-1] == ("incident.rollback", "denied_by_human")


# ---- End-to-end via the reviewer CLI (cross-surface proof) ----

def test_full_cycle_via_reviewer_cli(env, tmp_path):
    """Sentinel proposes -> human approves the rollback with the actual CLI."""
    record_proposal(SENTINEL_METRICS, SENTINEL_REPORT, **env)
    rolled_back = []
    executed = threading.Event()

    def run_rollback():
        governed_rollback(SENTINEL_INCIDENT, rolled_back.append, **env)
        executed.set()

    t = threading.Thread(target=run_rollback)
    t.start()
    while not env["gate"].list_pending():
        time.sleep(0.01)
    token = env["gate"].list_pending()[0]["token"]
    assert not executed.is_set() and rolled_back == []  # BEFORE approval: blocked
    rc = cli_main(["--ledger", env["ledger"].path, "--gate", env["gate"].root,
                   "approve", token[:12], "--by", "frank"])
    t.join(timeout=5)
    assert rc == 0 and rolled_back == [SENTINEL_INCIDENT]  # AFTER approval: executed


# ---- KPI roll-ups ----

def test_kpi_provenance_completeness(env):
    """Every governed workload call leaves exactly one terminal ledger record."""
    TERMINAL = {"executed", "blocked", "denied_by_human", "failed"}
    side_effects = []
    calls = 0

    calls += 1
    with pytest.raises(PolicyDenied):
        governed_promote("1", GATE_FAIL, side_effects.append, **env)
    calls += 1
    governed_promote("2", GATE_PASS, side_effects.append, stage="Staging", **env)
    calls += 1
    with pytest.raises(ApprovalDenied):
        governed_promote("3", GATE_PASS, side_effects.append, gate_timeout=0.1, **env)
    calls += 1
    record_proposal(SENTINEL_METRICS, SENTINEL_REPORT, **env)
    calls += 1
    with pytest.raises(ApprovalDenied):
        governed_rollback(SENTINEL_INCIDENT, side_effects.append, gate_timeout=0.1, **env)

    terminal = [o for _, o in outcomes(env["ledger"]) if o in TERMINAL]
    assert len(terminal) == calls  # KPI 1: 100% coverage, zero gaps
    # KPI 2: zero un-gated side effects. Two entries executed: the staging
    # promote (a real side effect) and the recorded proposal (side-effect-free).
    assert terminal.count("executed") == 2
    assert side_effects == ["2"]  # the only real side effect that ran


def test_kpi_end_to_end_verifiability(env):
    """After a full promote + rollback cycle the chain still verifies clean."""
    threading.Thread(target=approve_when_pending, args=(env["gate"],)).start()
    governed_promote("7", GATE_PASS, lambda v: None, **env)
    record_proposal(SENTINEL_METRICS, SENTINEL_REPORT, **env)
    threading.Thread(target=approve_when_pending, args=(env["gate"],)).start()
    governed_rollback(SENTINEL_INCIDENT, lambda i: None, **env)
    assert env["ledger"].verify() == (True, None)
    expected = [("model.promote", "pending"), ("model.promote", "executed"),
                ("incident.propose", "executed"),
                ("incident.rollback", "pending"), ("incident.rollback", "executed")]
    assert outcomes(env["ledger"]) == expected
