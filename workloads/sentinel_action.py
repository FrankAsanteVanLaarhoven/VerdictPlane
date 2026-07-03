"""Sentinel incident actions, governed by Keystone.

Adapts the real Sentinel engine (sentinel/src/sentinel/incident_agent.py):
  - ``investigate(store) -> (metrics, report)`` — detects an SLO breach,
    localizes the culprit service, finds the causal change, and PROPOSES a
    rollback, assistive-only: "[AWAIT HUMAN APPROVAL]" (incident_agent.py:40).

Sentinel already proposes-and-never-acts. Keystone makes that promise
enforceable and auditable:
  - the proposal itself is recorded in the tamper-evident ledger
    (content-addressed by the report's SHA-256),
  - executing the proposed rollback is ``require_human`` — it physically
    cannot run until a reviewer approves, and a timeout denies safely.
"""

import hashlib

from keystone.interceptor import govern


def proposal_action(metrics: dict, report: str, agent: str = "sentinel") -> dict:
    """Map Sentinel's investigate() output onto a recordable Keystone action."""
    return {
        "tool": "incident.propose",
        "effect": "propose",
        "agent": agent,
        "args": {
            "service": metrics.get("localized"),
            "detected": metrics.get("detected"),
            "detect_t": metrics.get("detect_t"),
            "proposal": "rollback",
            "report_sha256": hashlib.sha256(report.encode()).hexdigest(),
            "report_head": report.splitlines()[0] if report else "",
        },
    }


def record_proposal(metrics: dict, report: str, *, policy, ledger, gate,
                    agent: str = "sentinel") -> str:
    """Record the assistive proposal as provenance (allow path; no side effect)."""
    return govern(
        proposal_action(metrics, report, agent), lambda: report,
        policy=policy, ledger=ledger, gate=gate,
    )


def governed_rollback(incident: dict, rollback_fn, *, policy, ledger, gate,
                      agent: str = "sentinel", gate_timeout: float | None = None):
    """Execute the proposed rollback through the human gate.

    ``incident`` carries the fields Sentinel's engine produced:
    service (localized culprit), change (causal change), detect_t.
    """
    action = {
        "tool": "incident.rollback",
        "effect": "execute",
        "agent": agent,
        "args": {
            "service": incident["service"],
            "change": incident.get("change"),
            "detect_t": incident.get("detect_t"),
        },
    }
    return govern(
        action, lambda: rollback_fn(incident),
        policy=policy, ledger=ledger, gate=gate, gate_timeout=gate_timeout,
    )
