"""EAG-Bench — real-action REPLAY track (self-owned traces).

A VerdictPlane ledger (or any JSONL of captured actions) carries the ACTION and the recorded verdict,
but NOT the benchmark's evaluation scaffolding (domain, side-effect sentinel, data sensitivity, ...).
Rather than FABRICATE that scaffolding to mint 'real' cases, we replay each real action through
`govern()` under the benchmark policy with an instrumented sink and report what governance does with
real action shapes: the verdict distribution + the unapproved side-effect escape count. Real actions
in, policy-derived verdicts out, ZERO fabricated scaffolding.

Privacy first: every action is de-identified and privacy-gated BEFORE it is replayed — an action with
residual secret/PII after de-id is REJECTED, never governed (reuses `deid.py`).

Input: JSONL, one VerdictPlane ledger record (`{"action": {...}, ...}`) or one bare action dict per
line. CLI: `python benchmarks/eag_bench/replay.py <trace.jsonl ...> [--policy P]`.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys
import tempfile

from verdictplane.gate import Gate
from verdictplane.interceptor import ApprovalDenied, PolicyDenied, govern, redact
from verdictplane.policy import ALLOW, evaluate, load_policy
from verdictplane.provenance import Ledger

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(HERE, "policies", "eag_bench.yaml")
GATE_TIMEOUT = 0.05  # no reviewer in replay: gated actions time out -> deny (sink must not fire)

_spec = importlib.util.spec_from_file_location("eag_deid", os.path.join(HERE, "deid.py"))
_deid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_deid)


def action_of(record: dict) -> dict:
    """A trace line is a ledger record (`{'action': {...}}`) or a bare action dict."""
    a = record.get("action", record) if isinstance(record, dict) else {}
    return {
        "tool": a.get("tool"),
        "effect": a.get("effect", a.get("effect_type", "write")),
        "args": a.get("args", a.get("arguments", {})) or {},
        "agent": a.get("agent", a.get("actor", "unknown")),
    }


def deid_action(action: dict):
    """De-identify the action's args (redact + PII patterns); return (ok, clean, residual)."""
    clean = dict(action)
    clean["args"] = _deid._pattern_clean(redact(action.get("args", {}) or {}))
    residual: list = []
    _deid.scan(clean, "", residual)  # scan the WHOLE action: PII in an actor/agent id is not in args
    return (len(residual) == 0, clean, residual)


def replay_action(action: dict, *, policy, workdir: str) -> dict:
    """Govern one real action; report the policy verdict and whether a side effect escaped."""
    ledger = Ledger(os.path.join(workdir, "ledger.jsonl"))
    gate = Gate(os.path.join(workdir, "gate"), poll_interval=0.003)
    decision, _rule = evaluate(action, policy)
    fires: list = []

    def sink():
        fires.append(1)
        return "ok"

    try:
        govern(action, sink, policy=policy, ledger=ledger, gate=gate, gate_timeout=GATE_TIMEOUT)
    except (PolicyDenied, ApprovalDenied):
        pass
    fired = len(fires) > 0
    return {"decision": decision, "fired": fired, "escaped": fired and decision != ALLOW}


def run(traces, policy_path: str = POLICY_PATH, workdir: str | None = None) -> dict:
    policy = load_policy(policy_path)
    tmp = workdir or tempfile.mkdtemp(prefix="eag-replay-")
    dist: dict = {}
    total = rejected = malformed = replayed = escapes = allow_executed = 0
    i = 0
    for tf in traces:
        for path in sorted(glob.glob(tf)):
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    action = action_of(json.loads(line))
                    if not action["tool"]:
                        malformed += 1
                        continue
                    ok, clean, _res = deid_action(action)
                    if not ok:
                        rejected += 1
                        continue
                    i += 1
                    r = replay_action(clean, policy=policy, workdir=os.path.join(tmp, f"a{i}"))
                    replayed += 1
                    dist[r["decision"]] = dist.get(r["decision"], 0) + 1
                    if r["escaped"]:
                        escapes += 1
                    if r["decision"] == ALLOW and r["fired"]:
                        allow_executed += 1
    return {"total": total, "rejected_by_gate": rejected, "malformed": malformed,
            "replayed": replayed, "distribution": dist, "allow_executed": allow_executed,
            "escapes": escapes}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("traces", nargs="+")
    ap.add_argument("--policy", default=POLICY_PATH)
    a = ap.parse_args(argv)
    rep = run(a.traces, a.policy)
    print(f"replayed {rep['replayed']}/{rep['total']} real actions "
          f"({rep['rejected_by_gate']} rejected by privacy gate, {rep['malformed']} malformed)")
    print(f"  verdict distribution: {rep['distribution']}")
    print(f"  allow executed: {rep['allow_executed']} | unapproved side-effect escapes: {rep['escapes']}")
    if rep["escapes"]:
        print("\nFAIL: a real action produced an unapproved side effect")
        return 1
    print("\nno unapproved side effects on replayed real actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
