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

1. **`schema/action_case.schema.json`** — the canonical case format. ← Phase B step 1.
2. **25 seed cases** across 10 domains, validating against the schema.
3. **Side-Effect Escape harness** — instrumented sentinels around fake sinks; headline metric.
4. Policy-conformance / expected-verdict evaluation.
5. MCP / tool-governance cases → agentic red-team cases → compliance mapping outputs.
6. **EIGS-100 scoring only after the corpus + harness are stable.**

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
