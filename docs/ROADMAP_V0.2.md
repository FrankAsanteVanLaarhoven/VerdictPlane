# VerdictPlane v0.2 — EAG-Bench & Enterprise Hardening (DRAFT for scope agreement)

**Status:** proposed plan, not yet started. Building is gated on sign-off of the scope below.
**Predecessor:** v0.1.0 (deterministic in-path control plane; 187 tests; PyPI live).

## 1 · Thesis — what v0.2 proves

v0.1 proved the *mechanism*: a governed action cannot execute without deterministic pre-execution
control, with tamper-evident provenance and a human gate. v0.2 proves it **survives adversarial
enterprise conditions and is measurable against a public standard**.

> **The wedge, restated as a measurement.** Post-hoc governance observes actions after the fact.
> EAG-Bench measures the thing that actually matters: *can a consequential action reach a real side
> effect without passing deterministic policy + (where required) human approval?* The headline
> number is the count of **unapproved side effects that escaped** under sustained adversarial load —
> the target is **zero**.

**EIGS** (Enterprise In-path Governance Score) aggregates the tracks below into `/100`. Release
target: **EIGS ≥ 95/100 with zero critical failures**, where *any* escaped side effect, *any*
undetected tamper, or *any* model reachable from the enforcement path is a **critical** auto-fail
regardless of score.

## 2 · Design principles (non-negotiable, inherited from v0.1)

1. **The v0.1 enforcement core does not change semantics.** `policy`, `provenance`, `interceptor`,
   `gate` stay deterministic, zero-egress, model-free. New capability is additive and opt-in.
2. **The benchmark is adversarial and reproducible.** Every score regenerates from `make eag`;
   seeds fixed; artefacts file-backed and commit-pinned like v0.1's evidence pack.
3. **Honest scope.** We publish EAG-Bench as *an openly specified benchmark for pre-execution
   action governance*, not as an unqualified "SOTA" claim, until it has external reproduction.
4. **Close the documented v0.1 limitations first** (they are the credibility debt): tail-truncation,
   single-reviewer gate, buffered-only durability.

## 3 · Tracks

Sequenced in three phases. Phase A upgrades the product (closes v0.1's named limitations); Phase B
builds the benchmark; Phase C adds adversarial + compliance surface.

### Phase A — Enterprise hardening (closes v0.1 limitations)

**T7 · External anchoring / signed checkpoints.** *(shipped, c9559fc.)* `checkpoint()`
(head + count + Merkle root, optionally HMAC-signed) + `verify_extends(anchor)` make tail
truncation *below the last anchor* and rollback to a divergent history detectable against an
externally held checkpoint — mutations a self-contained chain walk cannot see. CLI: `verdictplane
anchor` / `verify-anchor`. **Honest scope:** the HMAC gives *keyed tamper-evidence to key-holders*
(the key must be held separately from the ledger writer), **not** asymmetric non-repudiation; the
post-anchor tail is only covered by the next checkpoint (anchor frequently); the Merkle root is a
forward commitment not yet load-bearing. *Documented follow-ups (later increment, off-path, core
untouched):* **ed25519 signing** for true non-repudiation + **Merkle inclusion proofs** for
selective auditor disclosure. *EIGS: 10.*

**T8 · Multi-reviewer quorum gate.** *(shipped.)* Per-rule `quorum: k` k-of-n approval with
**deny-veto**; one atomic vote per reviewer identity (cross-process), approver identities recorded in
the ledger; timeout still denies; backward compatible at quorum 1 (default). CLI `approve`/`deny`
accumulate votes and report progress. **Honest scope:** reviewer SLAs, expiry policies, and
notifications remain roadmap (enterprise workflow track). *EIGS: 7.*

**T6 · Durability-mode performance matrix.** *(shipped.)* `make bench` now measures the allow-path
cost across ledger durability modes with policy + gate held fixed: **memory** (≈ 9 µs p99 / ~150k
ops/s — diagnostic lower bound, no persistence), **jsonl-buffered** (≈ 18 µs / ~60k — the deployable
default), **durable-fsync** (≈ 2.4 ms p99 / ~600 ops/s on this host — crash-durable tail). Each row
states its guarantee. **Honest finding:** durability costs ~100× — `durable-fsync` does *not* meet
the buffered `<1 ms` / `>10k` targets, so the sub-20 µs headline is explicitly a buffered-mode number.
(`sidecar`/`approval` dropped from the matrix — a deployment mode and an already-measured decision
path, not ledger durability axes.) *EIGS: 5.*

### Phase B — EAG-Bench core

**T1 · Enterprise Action Corpus (EAC).** A labelled corpus of enterprise agent actions (target
300–1000) spanning tool families (fs, db, email, payments, infra, IAM, MCP tools), each labelled
with the *correct* governance verdict (allow / deny / require_human) and effect. *Deliverable:*
`corpus/eac/*.jsonl` + a policy pack + a schema + provenance for how each label was decided.
*Acceptance:* deterministic policy reproduces every label; inter-label consistency checked; corpus
is versioned and documented. *EIGS: 15.* **← highest credibility risk (see §6).**

*Hybrid execution standard (agreed):* v0.2 ships **synthetic-adversarial** cases authored by a
structured methodology, but held to a high bar so it is not dismissed as "just synthetic":
(a) every action carries a `source` field (`synthetic` / `real` / `anonymized`) plus provenance and
sensitivity metadata, so **real/anonymized traces drop in later without a schema change** (v0.3+);
(b) an **independent reviewer validates a significant sample** and per-action labelling rationale
*and disagreements* are published; (c) the write-up states plainly what is synthetic and roadmaps
real-trace integration. Transparency here increases credibility rather than reducing it.

**T2 · Side-Effect Escape track (THE headline).** An adversarial harness that drives thousands of
actions (incl. mutation attempts, race conditions, malformed args, policy-evasion shapes) through a
governed dispatch wired to *instrumented* fake side-effect sinks, and counts any mutation that fired
without an allow/approval. *Deliverable:* `bench/eag/escape.py`; target **0 / ≥10k**. *Acceptance:*
zero escapes across the adversarial suite; every attempt is in the ledger; result regenerates.
*EIGS: 30 (and any escape = critical auto-fail).*

**T4 · MCP conformance track.** A conformance suite for `governed_dispatch`: unknown tools default
to write→require_human, effect inference is safe, no tool is reachable un-governed, streaming/partial
calls are handled. *Deliverable:* `bench/eag/mcp_conformance.py`. *Acceptance:* full pass; a
deliberately mis-wired dispatch fails loudly. *EIGS: 8.*

### Phase C — Adversarial & compliance surface

**T3 · Agentic red-team.** An attack battery mapped to OWASP LLM Top-10 (esp. LLM06 excessive
agency, LLM08 excessive permissions) and CSA agentic guidance: prompt-injected tool calls,
confused-deputy, args smuggling, TOCTOU on the gate, ledger-forgery attempts. *Deliverable:*
`bench/eag/redteam/` with per-attack expected-outcome. *Acceptance:* every attack is denied/gated
and recorded; none reaches a sink. *EIGS: 15.*

**T5 · Compliance Evidence Compiler.** Maps VerdictPlane's artefacts to control matrices —
EU AI Act (logging/human-oversight arts.), NIST AI RMF (MEASURE/MANAGE), ISO/IEC 42001, OWASP LLM —
emitting an auditor-ready coverage report from the live evidence pack. *Deliverable:*
`compliance/*.yaml` mappings + `make compliance` → `docs/COMPLIANCE.md`. *Acceptance:* every mapped
control cites a regenerable artefact; gaps are listed honestly, not hidden. *EIGS: 8.*

**T9 · OTel / SIEM export.** Off-path exporter (never in the decision) emitting ledger events as
OpenTelemetry spans / CEF for Splunk/Elastic. *Deliverable:* `verdictplane export`. *Acceptance:*
exporter failure never affects enforcement (statically + at runtime); events round-trip. *EIGS: 2.*

## 4 · EIGS-100 allocation

| Track | Points | Critical-fail trigger |
| --- | ---: | --- |
| T2 Side-Effect Escape | 30 | any escaped side effect |
| T1 EAC policy conformance | 15 | — |
| T3 Agentic red-team | 15 | any attack reaches a sink |
| T7 External anchoring & tamper | 10 | any undetected tamper |
| T4 MCP conformance | 8 | any un-governed tool path |
| T5 Compliance coverage | 8 | — |
| T8 Multi-reviewer governance | 7 | partial approval executes |
| T6 Durability/perf targets | 5 | — |
| T9 Observability export | 2 | exporter reachable from enforcement |
| **Total** | **100** | plus: any model import in enforcement = critical |

`make eag` runs every track, writes `artifacts/eag.json` + `docs/EAG_BENCH.md`, prints the EIGS
scoreboard, and exits nonzero on score < threshold **or** any critical failure.

## 5 · Milestones

- **v0.2.0-alpha** — Phase A (T6, T7, T8): the product hardening, closing v0.1's named limitations.
- **v0.2.0-beta** — Phase B (T1, T2, T4): EAG-Bench core + the headline zero-escape number.
- **v0.2.0** — Phase C (T3, T5, T9) + EIGS aggregation, `make eag`, and a fresh independent-repro kit
  extended to cover the benchmark (reuse `deploy/repro.Dockerfile` + `make repro`).

## 6 · Risks & honest caveats

- **Corpus credibility (T1) is the crux.** A benchmark is only as good as its labels. Synthetic
  actions are reproducible but attackable as "you graded your own homework"; real/anonymized traces
  are stronger but scarce and sensitive. **Recommendation:** synthetic-but-adversarially-authored
  corpus for v0.2, with the labelling rationale published per action, and an explicit invitation for
  external review — do **not** brand it "SOTA" until a third party reproduces and critiques it.
- **Scope is large.** All nine tracks is a multi-milestone effort. Phase A alone is a shippable,
  defensible v0.2.0-alpha that closes real gaps — a reasonable place to re-evaluate.
- **Red-team completeness (T3)** can never be proven exhaustive; we claim coverage of a named,
  versioned attack set, not "unbreakable."

## 7 · Non-goals for v0.2

Distributed/HA ledger; a hosted control-plane service; a GUI reviewer console; and *making the
advisory model better* — the advisory stays strictly off-path and out of scope for governance claims.

## 8 · Scope decisions (agreed 2026-07-03)

1. **Breadth:** ship **Phase A (hardening) as v0.2.0-alpha first**, then re-scope B/C. ← in progress.
2. **Corpus:** **hybrid** — synthetic-adversarial for v0.2 with a schema designed so real/anonymized
   traces drop in later for a credibility upgrade (Phase B).
3. **Positioning:** lead with a **standard-setting** claim — EAG-Bench as *a new open standard for
   measuring pre-execution action governance* (a category claim we can defend by construction), and
   substantiate empirical-superiority claims only after external reproduction.

**Phase A COMPLETE** — T7 (external anchoring), T8 (quorum), T6 (durability matrix) all shipped; the
three limitations named in the evidence appendix are closed. **v0.2.0-alpha is tag-ready.** Next:
re-scope Phase B (EAG-Bench). Follow-ups parked: ed25519 signing + Merkle inclusion proofs (post-alpha).
