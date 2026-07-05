"""WWT pilot: the model-governance intake — DriftGuard PromotionProposal -> govern().

The second intake of the pilot's two-intakes design: Sentinel's incident-centric
ActionProposal governs runtime remediation; this intake governs MODEL PROMOTION
proposals produced by DriftGuard. Contract + fixtures + acceptance criteria are
defined by the producer's guide (driftguard: docs/PROMOTION_PROPOSAL_INTAKE.md);
the fixture pair under pilots/wwt/examples/ was generated from a real sealed run.

Zero driftguard imports — the wire contract is plain JSON and three checks. The
proposal carries no authority: it must be recomputable from the sealed
PromotionDecisionRecord it references, so this intake verifies the record first
(schema major, canonical SHA-256, fail-closed decision derivation), cross-checks
the proposal against it, and only then routes the action through ``govern()`` —
policy, hash-chained provenance, and the human gate all apply exactly as they do
to any other governed action.

Enforcement-path discipline: stdlib + verdictplane only, deterministic, zero-egress.
"""

from __future__ import annotations

import hashlib
import json

from verdictplane.interceptor import govern

SUPPORTED_MAJOR = "1"

# Fixed producer mapping (mirrors driftguard.contract.ACTION_BY_DECISION).
ACTION_BY_DECISION = {
    "promote": "promote_model",
    "block": "block_deployment",
    "hold_for_human": "require_human_review",
}


class InvalidProposal(ValueError):
    """Proposal or its referenced record failed verification. Nothing was governed,
    nothing was executed, nothing was ledgered — rejected at the door."""


def canonical_hash(payload: dict) -> str:
    unhashed = dict(payload, content_hash="")
    canonical = json.dumps(unhashed, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_decision(gates: list[dict], human_required: bool) -> str:
    required = [g for g in gates if g.get("required")]
    if not required or any(not g.get("passed") for g in required):
        return "block"
    return "hold_for_human" if human_required else "promote"


def _major(version) -> str:
    return str(version).split(".", 1)[0]


def verify_record(record: dict) -> str:
    """The producer contract's three checks; returns the verified decision."""
    if _major(record.get("schema_version", "")) != SUPPORTED_MAJOR:
        raise InvalidProposal(f"record schema major unsupported: "
                              f"{record.get('schema_version')!r}")
    if record.get("content_hash") and canonical_hash(record) != record["content_hash"]:
        raise InvalidProposal("record content hash mismatch — modified after sealing")
    derived = derive_decision(record.get("gates", []),
                              bool(record.get("policy", {}).get("human_required", True)))
    if record.get("decision") != derived:
        raise InvalidProposal(f"record decision {record.get('decision')!r} inconsistent "
                              f"with gates (fail-closed derivation: {derived!r})")
    return derived


def cross_check(proposal: dict, record: dict) -> None:
    """The proposal has zero authority — every derived field must match its record."""
    if _major(proposal.get("schema_version", "")) != SUPPORTED_MAJOR:
        raise InvalidProposal(f"proposal schema major unsupported: "
                              f"{proposal.get('schema_version')!r}")
    ref = proposal.get("evidence_ref") or {}
    if ref.get("content_hash") != record.get("content_hash"):
        raise InvalidProposal("proposal evidence_ref does not pin this record")
    expected_action = ACTION_BY_DECISION.get(record.get("decision"))
    if proposal.get("action") != expected_action:
        raise InvalidProposal(f"proposal action {proposal.get('action')!r} inconsistent "
                              f"with record decision (expected {expected_action!r})")
    record_risk = record.get("risk_level")
    if record_risk is not None and proposal.get("risk_level") != record_risk:
        raise InvalidProposal("proposal risk_level disagrees with the sealed record")


def proposal_to_action(proposal: dict) -> dict:
    """The governed-action shape (mirrors driftguard.contract.proposal_to_governed_action)."""
    return {
        "tool": proposal["action"],
        "effect": "write",
        "args": {
            "target": proposal.get("target", {}),
            "risk_level": proposal.get("risk_level"),
            "requires_human": proposal.get("requires_human", True),
            "reason": proposal.get("reason", ""),
            "proposal_id": proposal.get("proposal_id"),
            "evidence_ref": proposal.get("evidence_ref", {}),
        },
        "agent": proposal.get("source", "driftguard"),
        "context": {"proposal_schema_version": proposal.get("schema_version"),
                    "created_at": proposal.get("created_at")},
    }


def intake(proposal: dict, record: dict, execute, *, policy, ledger, gate,
           gate_timeout: float | None = None):
    """Verify, cross-check, then govern. The side effect (``execute``) runs only if
    policy allows it or a human approves it; every outcome lands in the ledger."""
    verify_record(record)
    cross_check(proposal, record)
    action = proposal_to_action(proposal)
    return govern(action, execute, policy=policy, ledger=ledger, gate=gate,
                  gate_timeout=gate_timeout)
