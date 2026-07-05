"""WWT pilot acceptance: the model-governance intake consumes a real DriftGuard
PromotionProposal (the producer's merge criterion, per its intake guide):
(1) accept + govern + ledger the committed fixture pair;
(2) reject a tampered record and an action/decision mismatch — at the door,
    before any governance or side effect;
(3) an action the policy has never heard of falls to the human gate, and an
    unapproved gate times out to denial (fail-safe)."""

import json
import sys
from pathlib import Path

import pytest

from verdictplane.gate import Gate
from verdictplane.interceptor import ApprovalDenied, PolicyDenied
from verdictplane.policy import load_policy
from verdictplane.provenance import Ledger

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "pilots" / "wwt"
sys.path.insert(0, str(PILOT))

from promotion_intake import (  # noqa: E402
    ACTION_BY_DECISION,
    InvalidProposal,
    canonical_hash,
    intake,
)

POLICY = load_policy(str(PILOT / "policies" / "model_governance.yaml"))


def _fixtures():
    proposal = json.loads((PILOT / "examples" / "sample_promotion_proposal.json").read_text())
    record = json.loads((PILOT / "examples" / "promotion_decision.json").read_text())
    return proposal, record


@pytest.fixture()
def env(tmp_path):
    return {
        "policy": POLICY,
        "ledger": Ledger(str(tmp_path / "ledger.jsonl")),
        "gate": Gate(str(tmp_path / "gate"), poll_interval=0.01),
    }


def outcomes(ledger):
    return [e["record"]["outcome"] for e in ledger.entries()]


# ---- (1) the happy path: a real proposal is consumed, governed, executed ----

def test_real_fixture_is_consumed_governed_and_ledgered(env):
    proposal, record = _fixtures()
    ran = []
    result = intake(proposal, record, lambda: ran.append(True) or "promoted", **env)
    assert result == "promoted" and ran == [True]
    # promote_model + low risk + requires_human False -> policy allows; one terminal
    # ledger record carries the proposal's identity and the sealed-record pin.
    assert outcomes(env["ledger"]) == ["executed"]
    entry = list(env["ledger"].entries())[-1]["record"]["action"]
    assert entry["tool"] == "promote_model"
    assert entry["args"]["proposal_id"] == proposal["proposal_id"]
    assert entry["args"]["evidence_ref"]["content_hash"] == record["content_hash"]
    ok, bad = env["ledger"].verify()
    assert ok and bad is None


# ---- (2) rejected at the door: tampering and inconsistency ----

def test_tampered_record_rejected_before_any_governance(env):
    proposal, record = _fixtures()
    tampered = dict(record, signals={"retention_ratio": 1.0})   # breaks the seal
    with pytest.raises(InvalidProposal, match="hash mismatch"):
        intake(proposal, tampered, lambda: pytest.fail("must not execute"), **env)
    assert outcomes(env["ledger"]) == []                        # nothing ledgered

    # Re-sealed but lying about the decision: fail-closed re-derivation catches it.
    lying = dict(record, decision="block")
    lying["content_hash"] = canonical_hash(lying)
    with pytest.raises(InvalidProposal, match="inconsistent with gates"):
        intake(proposal, lying, lambda: pytest.fail("must not execute"), **env)

    # Proposal action that disagrees with the record's derived decision.
    forged = dict(proposal, action="require_human_review")
    with pytest.raises(InvalidProposal, match="inconsistent with record decision"):
        intake(forged, record, lambda: pytest.fail("must not execute"), **env)

    # Proposal pinned to some other record.
    unpinned = dict(proposal, evidence_ref={"content_hash": "0" * 64})
    with pytest.raises(InvalidProposal, match="does not pin"):
        intake(unpinned, record, lambda: pytest.fail("must not execute"), **env)
    assert outcomes(env["ledger"]) == []


# ---- (3) default-deny: unmatched actions go to the human gate, fail-safe ----

def _hold_pair():
    """A consistent proposal+record pair whose action no policy rule matches."""
    proposal, record = _fixtures()
    record = dict(record, decision="hold_for_human",
                  policy=dict(record["policy"], human_required=True))
    record["content_hash"] = canonical_hash(record)
    proposal = dict(proposal, action=ACTION_BY_DECISION["hold_for_human"],
                    requires_human=True,
                    evidence_ref=dict(proposal["evidence_ref"],
                                      content_hash=record["content_hash"]))
    return proposal, record


def test_unmatched_action_falls_to_human_gate_and_times_out_denied(env):
    proposal, record = _hold_pair()
    with pytest.raises(ApprovalDenied):
        intake(proposal, record, lambda: pytest.fail("must not execute"),
               gate_timeout=0.2, **env)
    assert outcomes(env["ledger"]) == ["pending", "denied_by_human"]


def test_blocked_proposal_is_denied_and_ledgered(env):
    proposal, record = _fixtures()
    record = dict(record, decision="block",
                  gates=[dict(g, passed=False) if g["required"] else g
                         for g in record["gates"]])
    record["content_hash"] = canonical_hash(record)
    proposal = dict(proposal, action="block_deployment", risk_level=None,
                    evidence_ref=dict(proposal["evidence_ref"],
                                      content_hash=record["content_hash"]))
    record = dict(record, risk_level=None)
    record["content_hash"] = canonical_hash(record)
    proposal["evidence_ref"]["content_hash"] = record["content_hash"]
    with pytest.raises(PolicyDenied):
        intake(proposal, record, lambda: pytest.fail("must not execute"), **env)
    assert outcomes(env["ledger"]) == ["blocked"]
