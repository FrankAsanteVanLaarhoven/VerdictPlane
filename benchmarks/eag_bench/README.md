# EAG-Bench — Enterprise Action Governance Benchmark (Phase B kickoff)

**Status:** planning artefact for Phase B. Phase A is complete and tagged `v0.2.0-alpha`; the three
limitations named in the evidence appendix are closed. See [`../../docs/ROADMAP_V0.2.md`](../../docs/ROADMAP_V0.2.md).

## Mission

Prove — measurably and reproducibly — that VerdictPlane **prevents unauthorised consequential actions
before execution**, not merely observes them after. Core claim to substantiate:

> Non-bypassable pre-execution governance for enterprise AI actions, with **zero unapproved side
> effects** under adversarial, compliance-sensitive, and tool-mediated conditions.

Framed as an **open, standard-setting benchmark** for pre-execution action governance (empirical
"beats X" claims only after external reproduction — see [`../../docs/REVIEW_GATE.md`](../../docs/REVIEW_GATE.md)).

## Build order (schema-first; do NOT jump to a 300–1000 corpus)

1. **`schema/action_case.schema.json`** — the canonical case format. ✅ **shipped** (+ a
   dependency-free validator and 3 seed cases; see *Status* below).
2. **100 seed cases**, 10 per domain, validating against the schema. ✅ **shipped** (see `MATRIX.md`).
3. **Side-Effect Escape harness** — drives cases through `govern()`, instrumented sinks, headline
   metric. ✅ **shipped** (`make enterprise-bench` → **0/100 escapes**; `policies/eag_bench.yaml`).
4. Policy-conformance / expected-verdict evaluation. ✅ (folded into the harness: verdict 100/100).
5. **Agentic red-team track** (multi-step attacks) — ✅ **shipped** (`make redteam-bench`; two honest
   buckets: 8/8 defeated, 7/7 known-boundary; see [`redteam/README.md`](redteam/README.md)).
6. **Compliance-evidence compiler** — ✅ **shipped** (`make compliance-report` →
   [`compliance/COVERAGE.md`](compliance/COVERAGE.md); EU AI Act / NIST / ISO + threat matrices,
   framed as *coverage, not certification*).
7. **Real traces (self-owned).** De-identification safety rail — ✅ **shipped** (`deid.py`, hard gate:
   reject on residual PII, never `real`). Real-action **replay track** — ✅ **shipped** (`replay.py`:
   replay captured actions through `govern()`, report verdict distribution + 0 escapes, no fabricated
   scaffolding). Next: feed a real self-owned ledger from actual usage.
8. **EIGS-100 scoring only after the corpus + harness are stable.**

## Status & layout

```
benchmarks/eag_bench/
  schema/action_case.schema.json   canonical case format (v1.0)
  cases/*.json                     the corpus (100 seed cases, 10 per domain)
  policies/eag_bench.yaml          the enforcement policy the harness runs
  validate.py                      stdlib-only validator (interprets the schema)
  harness.py                       Side-Effect Escape harness (drives cases through govern())
  MATRIX.md                        coverage matrix + result
```

Validate the corpus and run the escape harness (both also run in `make test`):

```bash
make eag-validate       # schema-validate the 100 cases
make enterprise-bench   # drive them through VerdictPlane -> 0/100 escapes
```

The schema enforces two conditionals beyond structure: a **gated** verdict must declare
`required_gate: true` with ≥1 approver, and a **deny/timeout/veto** verdict must set the sentinel
`expected_timing: "never"` — so a case cannot claim a block while permitting the mutation.

## Step 1 — `action_case.schema.json`

One canonical case. Grouped fields:

- **Identity:** `case_id`, `title`, `description`, `domain`, `risk_level`, `evaluation_tags`
- **Action:** `actor`, `system`, `tool`, `action`, `effect_type`, `arguments`, `data_sensitivity`
- **Expected governance:** `expected_verdict`, `required_gate`, `required_approvers`, `deny_veto`,
  `expected_ledger_fields`
- **Verification:** `side_effect_sentinel` (how we prove the mutation did/didn't fire, and when),
  `negative_controls`, `reproduction_notes`
- **Corpus provenance (hybrid-ready):** `source` (`synthetic` | `real` | `anonymized`),
  sensitivity/provenance metadata — so real traces drop in later without a schema change
- **Adversarial / compliance:** `attack_annotations` (OWASP LLM / CSA), `compliance_mappings`
  (EU AI Act / NIST AI RMF / ISO 42001 / OWASP)

**Verdict vocabulary (keep minimal):** `allow`, `deny`, `require_human`, `allow_after_approval`,
`deny_after_timeout`, `deny_after_veto`. Resist adding more early.

## Seed domains (10) — one `allow`, one `require_human`, one `deny` (where sensible), one adversarial

Cloud IAM · model promotion · incident rollback · MCP write tool · data export / PII · security
response · finance / payment · code deployment · HR / employee data · robotics / OT command.

*(Robotics/OT is in-scope here as a genuine class of consequential enterprise actions — distinct from
the cross-domain metric mix-ups corrected earlier.)*

## Side-effect sentinel principle (the core of the benchmark)

A **side effect** is any externally visible mutation: file write, DB update, git op, deploy flag, IAM
change, network call, payment instruction, model-registry mutation, ticket/status change, robot/OT
dispatch. Every consequential case defines a sentinel that proves whether the effect fired **before
approval, after denial, after timeout, or without a ledger entry**. Target: **0 unapproved side
effects**.

## KPIs

Policy-conformance accuracy · false-allow rate on dangerous actions · **unapproved side-effect rate**
· ledger completeness · human-gate routing correctness · tamper/rollback detection · clean-env
reproduction success.

**Critical failure (auto-fail, any):** an unapproved side effect · an enforcement-path model
dependency · an enforcement-path network call · an undetected ledger tamper · an approval bypass · an
action executing after `deny`.

## Constraints (VerdictPlane core thesis — non-negotiable)

No model in the enforcement path · advisory optional and off-path · enforcement deterministic ·
unknown/malformed high-risk actions default to deny or human gate · benchmarks reproducible from
commands · claims map to evidence artefacts · no "non-repudiation" claim where only keyed
tamper-evidence exists · schema + harness stable **before** scaling the corpus.

## Definition of done — Step 1

- `schema/action_case.schema.json` exists and validates the 25 planned seed cases.
- Each case expresses expected verdict, gate requirement, side-effect sentinel, and compliance mapping.
- No unnecessary complexity; a future `make enterprise-bench` can consume it without redesign.
