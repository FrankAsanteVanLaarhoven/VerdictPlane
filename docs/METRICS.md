# VerdictPlane — Metrics & Metric-to-Failure Mapping

Each metric is paired with the concrete failure it exposes and its **status** — so a reader can tell
what is *measured today* from what is *planned for EAG-Bench (Phase B)*. Nothing here is presented as
measured unless it is regenerable from `make bench` / `make test`.

Status key: **[measured]** regenerates from committed artefacts · **[operational]** cheap to add,
not yet a bench target · **[planned: EAG-Bench]** Phase B, not yet measured.

**How computed & kind.** Measured metrics regenerate from `make bench` (latency, throughput, tamper,
completeness, fail-safe) or `make test` (truncation/rollback, zero-egress). Latency and throughput
are **deployable** (they bound the runtime cost of sitting in the loop); the integrity and egress
metrics are **diagnostic** (they verify a property, not a per-request cost). Latency/throughput are
also published across **durability modes** (`memory` / `jsonl-buffered` / `durable-fsync`) in the
benchmark's durability matrix, so the buffered headline is never read as the durable-fsync cost.

## Measured now (v0.2.0-alpha)

| Metric | Definition | Failure exposed | Why it matters | Status |
| --- | --- | --- | --- | --- |
| Enforcement latency p50/p95/p99 | End-to-end time to reach a governance decision (allow / deny / require_human paths) | Control-plane bottleneck; governance too slow to sit in the loop | Whether VerdictPlane can sit in-path on **high-frequency agent action loops** | **[measured]** allow p99 ≈ 19 µs |
| Throughput | Governed actions/sec, single core | Control-plane saturation under load | Whether it scales with high-frequency decision streams | **[measured]** ≈ 60k/s |
| Provenance completeness | % of governed calls with exactly one terminal ledger record | Audit gap / missing decision record | Core auditability + incident investigation | **[measured]** 0 gaps |
| Tamper detection rate | `verify()` catches any mutation at the exact index (randomized battery) | Undetected rewrite of history | Integrity guarantee of the ledger | **[measured]** 200/200 |
| Truncation / rollback detection | `verify_extends()` catches tail loss / divergent history vs a signed anchor | Silent loss of recent history a chain walk can't see | Non-truncatability of the audit trail (up to the last anchor) | **[measured]** tests/test_anchor.py |
| Fail-safe rate | Decisions are byte-identical with the advisory forced broken | A model influencing an enforcement decision | Proves the advisory can never decide | **[measured]** |
| Zero-egress | Enforcement makes no network call (static + runtime socket kill-switch + empty netns) | Exfiltration / call-out from the decision path | Sovereign / air-gapped deployability | **[measured]** |

## Operational (cheap to add; not yet a bench target)

| Metric | Definition | Failure exposed | Why it matters | Status |
| --- | --- | --- | --- | --- |
| Human-gate timeout rate | % of `require_human` actions that time out | Liveness failure / operator bottleneck | Practicality of human oversight | **[operational]** |
| Default-deny rate | % of actions denied automatically (timeout or default) | Over-conservative policy / reduced availability | Safety-vs-usability trade-off | **[operational]** |
| Quorum attainment / veto rate | % of quorum actions that reach k approvals vs are vetoed / time out | Multi-reviewer impracticality | Whether k-of-n oversight is workable at scale | **[operational]** |

## Planned — EAG-Bench (Phase B, not yet measured)

| Metric | Definition | Failure exposed | Why it matters | Status |
| --- | --- | --- | --- | --- |
| Policy decision accuracy | % of decisions matching the label on the Enterprise Action Corpus | Incorrect enforcement | Correctness of deterministic policy on a labelled corpus | **[planned: EAG-Bench T1]** |
| Side-effect escape rate | Mutations that fire without an allow/approval, under adversarial load (target **0 / ≥10k**) | Governance bypass — the headline safety failure | End-to-end safety effectiveness | **[planned: EAG-Bench T2]** |
| Agentic red-team resistance | % of OWASP/CSA-mapped attacks denied/gated and recorded | Confused-deputy, injection, TOCTOU bypass | Adversarial robustness | **[planned: EAG-Bench T3]** |
| Full decision-path auditability | Reconstruct action → decision → approval(s) → outcome from the ledger | Incomplete / unverifiable decision history | Compliance + post-incident analysis | **[partial]** ledger already records action→decision→approver ids→outcome; end-to-end proof is Phase B |

> **Not applicable as stated:** "risk classification coverage" assumes a learned risk classifier.
> VerdictPlane's policy is a *deterministic rule engine*, not a model — there is no risk class to
> misclassify. The corresponding EAG-Bench metric is *policy coverage of the corpus's risk classes*,
> folded into "policy decision accuracy" above.
