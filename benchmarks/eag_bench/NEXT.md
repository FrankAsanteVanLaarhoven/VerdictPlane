# EAG-Bench — Phase B handoff / next milestone

Checkpoint for a fresh session. Everything below is committed on `main`.

## Done (Phase B, four tracks — all in `make test`, 224 tests)

| track | command | result | honest scope |
| --- | --- | --- | --- |
| Case schema + validator | `make eag-validate` | 100/100 valid | stdlib-only; verdict↔sentinel guards |
| Single-action corpus | `make enterprise-bench` | **0/100 escapes**, verdict 100/100 | synthetic breadth, one host, not externally validated |
| Agentic red-team | `make redteam-bench` | **8/8 defeated · 7/7 boundary** | 2 buckets; does NOT claim unbreakability |
| Compliance compiler | `make compliance-report` | 115 cases → per-framework matrices | **coverage, not certification** (disclaimed) |

## Next major milestone — real / anonymized traces (the credibility lever)

The `source: real | anonymized` field and `provenance` block already exist; the harness is
**source-agnostic**, so real cases flow through the same 0-escape check — no harness change needed.
The work is *safe ingestion*, not new evaluation logic.

**Safety rail — ✅ SHIPPED** (`benchmarks/eag_bench/deid.py`, `tests/test_deid.py`, 230 tests):
- de-identify reuses `verdictplane.interceptor.redact` (masks secret-named keys) + PII pattern scrub
  (email, IPv4, SSN, card, AWS key, private key, JWT) on carrier fields.
- **hard gate:** re-scans the WHOLE record; any residual secret/PII → the ingest CLI **rejects**
  (non-zero exit, no file written), and output is force-tagged `source: anonymized` (never `real`).
  CLI: `python benchmarks/eag_bench/deid.py <in.json ...> --out <dir>`.

**Wave-1 pivoted to self-owned traces** (public datasets deferred — see Sourcing below): the
credibility-clean path is our own governed-action traces, not licence-encumbered public corpora.

**Real-action replay track — ✅ SHIPPED** (`benchmarks/eag_bench/replay.py`, `tests/test_replay.py`):
a VerdictPlane ledger record carries the action + verdict but NOT the benchmark scaffolding (domain,
sentinel, sensitivity), so minting full `action_case` records from a trace would mean FABRICATING that
scaffolding. Instead we **replay** each real action through `govern()` under the benchmark policy with
an instrumented sink and report the **verdict distribution + unapproved-escape count** — real action
shapes in, policy-derived verdicts out, zero fabricated scaffolding. Every action is de-id'd + gated
(PII in an actor id → rejected, never governed) BEFORE replay.
CLI: `python benchmarks/eag_bench/replay.py <trace.jsonl ...>` (ledger records or bare actions).

**First real trace — ✅ INGESTED** (`traces/driftguard_promotions.jsonl` + `traces/README.md`): 2 real
production model-promotion decisions from DriftGuard's measured runs (ag_news 2026-07-01, distilbert
2026-07-02). Replayed → **{require_human: 2}, 0 escapes** (locked into `make test`). The cross-layer
story: DriftGuard's *ML* gate passed both on quality; VerdictPlane's *action* policy independently
routes prod promotions to dual-control approval. Real action shapes, policy-derived verdicts.

**EIGS-100 scoring — ✅ SHIPPED** (`benchmarks/eag_bench/eag.py`, `make eag` → `docs/EAG_BENCH.md`):
computed from real track runs, canonical roadmap allocation (non-equal by design), explicit
critical-fail gating, T9 gap honest. **EIGS = 98/100, 0 critical** on the current corpus (scoped:
mostly synthetic + red-team; real slice = early signal, NOT scored). `artifacts/eag.json` gitignored.

**Next:** (a) grow the real slice — **Sentinel logs** (not reachable in this session; point me at the
path) or a real VP deployment ledger → `replay.py`; (b) close the **T9 gap** — the OTel observability
exporter (the only missing 2 points), keeping it provably unreachable from enforcement.

**Then:** small `provenance` additions (`origin`, `deid_method`, `license`); a de-identification
checklist (strip secrets/PII, tokenise identifiers, drop free-text, verify no real credentials,
confirm licence/consent, record `deid_method`); source only permissively-licensed or self-owned logs.

**Risks:** PII leakage (→ the scan test), licensing/consent, and over-claiming "real" for lightly-
anonymised synthetic (→ keep `source` honest; `anonymized` ≠ `real`).

## Alternative / parallel — EIGS-100 scoring

Lower-risk quick win: aggregate the *already-measured* numbers into the 8-track weighted rubric
(enforcement correctness, side-effect escape, tamper, red-team, zero-egress, compliance coverage,
performance, workflow). Mostly wiring, no new data. **Caveat:** a headline score on a synthetic corpus
must be scoped as such until real traces + external repro exist.

## Recommended order

**Real traces first** (biggest credibility lever), starting with the de-id safety rail. Do EIGS-100
after, so the headline score reflects a partly-real corpus rather than a purely synthetic one.

## Sourcing plan (revised after licence check)

**Wave 1 = self-owned traces** (was public datasets). Why the change: an empirical licence check of
**ToolBench** found it ambiguous for a commercial product — the repo README states Apache-2.0 **but**
adds an "intended solely for research and educational purposes" disclaimer, other sources cite
**CC BY-NC 4.0** (NonCommercial), and the trajectories are crawled from **RapidAPI** (whose ToS govern
the underlying content regardless). Not a clean Wave-1. So the licence-clean, higher-integrity path is
our own governed-action traces (VerdictPlane / DriftGuard / Sentinel usage) — zero third-party licence
risk, more governance-relevant, and the de-id gate already fits.

**Public datasets (deferred, optional):** ToolBench/WebArena/GAIA/AgentBench remain candidates **only
if** you personally clear the current `LICENSE` + upstream ToS for commercial derivation and record it
in `provenance.license`. Do NOT assume "open".

**Honest scope caveat (important):** these datasets supply real *action distributions / shapes*, not
real enterprise *governance decisions* — the `expected_verdict` stays policy-derived. So the upgrade is
"real actions, synthetic labels", tagged `source: anonymized` (never `real`); do not claim "real
governance data".

## Still open for the next session
- Target size of the first anonymized batch (keep small; provenance/quality over volume).
- EIGS-100 weights — adopt the roadmap's or revisit.
