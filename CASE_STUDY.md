# Case Study — Governing Two Real AI Systems on Day One

VerdictPlane's wedge claim is composability: existing AI systems adopt it by
wrapping their consequential entry points, not by rewriting anything. These
are the first two, both real codebases, both integrated with ~60-line
adapters (`workloads/`).

## 1 · DriftGuard: MLflow model promotion

**The system.** DriftGuard is a governed-adaptation MLOps framework. Its
registry exposes a fail-closed accuracy gate and a promotion entry point:

- `baseline_gate(candidate_macro_f1, baseline_macro_f1, margin)` — candidate
  must beat the baseline by ≥ margin (registry.py:84);
- `promote_version(version)` — points the `production` MLflow alias at a
  version (registry.py:371). Its docstring already promised "human-gated
  promotion"; before VerdictPlane, nothing enforced that.

**The integration** (`workloads/driftguard_promote.py`): the gate result rides
inside the action's `args`, the side effect is an injected callable
(`driftguard_promote_fn()` lazily binds the real MLflow call, so VerdictPlane
gains zero MLflow dependency), and policy does the rest:

```yaml
- match: { tool: model.promote, args.baseline.passed: false }
  decision: deny                    # failed gate can NEVER ship — no human can override
- match: { tool: model.promote, args.stage: Production, args.baseline.passed: true }
  decision: require_human           # passing gate still needs a person for prod
- match: { tool: model.promote, args.stage: Staging, args.baseline.passed: true }
  decision: allow                   # canary-style staging flows unattended
```

**What changed.** The baseline-gate result is now tamper-evident provenance
attached to every promotion decision; a failed candidate is deterministically
blocked without reaching a reviewer; and pointing production at a new version
physically cannot happen until someone runs `verdictplane approve`. Live
before/after transcript: docs/EVIDENCE.md § E4.

## 2 · Sentinel: incident-response rollback

**The system.** Sentinel's incident engine detects an SLO breach, localizes
the culprit service, finds the causal change, and *proposes* a rollback —
assistive-only, "[AWAIT HUMAN APPROVAL]" in its own report
(incident_agent.py:40). The approval promise was a comment, not a mechanism.

**The integration** (`workloads/sentinel_action.py`):

- `record_proposal(metrics, report)` — the proposal enters the ledger on the
  allow path, content-addressed by the report's SHA-256, so the exact text a
  reviewer saw is bound to the chain;
- `governed_rollback(incident, rollback_fn)` — executing the rollback is
  `require_human`; a timeout denies safely.

**What changed.** "Proposes, never acts" went from a design intention to an
enforced property with an audit trail: the proposal, the human verdict, and
the execution (or refusal) are one verifiable hash chain.

## Measured cost of governance (both workloads under load)

From `make bench` on the reference host (full method in docs/BENCHMARK.md):

| Path | p50 | p99 |
| --- | --- | --- |
| DriftGuard promote — Staging (allow) | ~18 µs | ~22 µs |
| DriftGuard promote — Production (gated, auto-resolved machinery) | ~90 µs | ~220 µs |
| Sentinel proposal (recorded) | ~18 µs | ~22 µs |

Zero provenance gaps across the mixed benchmark load; the chain verifies after
every run. The pattern generalizes: if your system has a consequential entry
point with a callable signature, a ~60-line adapter and a few policy rules put
it under provenance and a human gate — without the system knowing VerdictPlane
exists.
