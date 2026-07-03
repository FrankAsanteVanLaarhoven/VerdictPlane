"""DriftGuard model promotion, governed by VerdictPlane.

Adapts the real DriftGuard entry points (driftguard/src/driftguard/registry.py):
  - ``baseline_gate(candidate_macro_f1, baseline_macro_f1, margin)`` — the
    fail-closed accuracy gate (registry.py:84).
  - ``promote_version(version) -> None`` — the side effect: points the
    ``production`` MLflow alias at the version (registry.py:371). Its own
    docstring promises "Human-gated promotion"; VerdictPlane enforces it.

What VerdictPlane adds:
  - the baseline-gate result is recorded as tamper-evident provenance,
  - a failed gate is deterministically DENIED (policy, no human needed),
  - a Production promotion physically cannot execute until a human approves.

The wrapper is thin: the side effect is an injected callable, so the same
governed path wraps the real MLflow-backed ``promote_version`` (see
``driftguard_promote_fn``) and the file-backed registry used in tests/demos.
"""

from verdictplane.interceptor import govern


def build_action(version, stage: str, gate_result: dict, agent: str = "driftguard") -> dict:
    """Map a DriftGuard promotion request onto a VerdictPlane action."""
    return {
        "tool": "model.promote",
        "effect": "promote",
        "agent": agent,
        "args": {
            "version": str(version),
            "stage": stage,
            "baseline": {
                "passed": bool(gate_result["passed"]),
                "candidate_macro_f1": gate_result.get("candidate_macro_f1"),
                "baseline_macro_f1": gate_result.get("baseline_macro_f1"),
                "margin": gate_result.get("margin"),
                "reason": gate_result.get("reason"),
            },
        },
    }


def governed_promote(version, gate_result: dict, promote_fn, *,
                     policy, ledger, gate, stage: str = "Production",
                     agent: str = "driftguard", gate_timeout: float | None = None):
    """Route one promotion through VerdictPlane; promote_fn runs only if allowed."""
    action = build_action(version, stage, gate_result, agent)
    return govern(
        action, lambda: promote_fn(str(version)),
        policy=policy, ledger=ledger, gate=gate, gate_timeout=gate_timeout,
    )


def driftguard_promote_fn(settings=None):
    """The real side effect: DriftGuard's MLflow-alias promotion (lazy import,
    so VerdictPlane itself never depends on the DriftGuard/MLflow stack)."""
    from driftguard.registry import promote_version

    return lambda version: promote_version(version, settings)
