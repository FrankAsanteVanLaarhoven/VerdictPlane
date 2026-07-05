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

**Build first — the safety rail** (before any real data lands):
- `deid.py` reusing `verdictplane.interceptor.redact` (already masks secrets) to strip PII/secrets from
  `arguments`, plus identifier→synthetic-token replacement.
- a test that scans every `source != synthetic` case for secret/PII patterns and **fails** if any leak.

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

## Open questions for the next session
- Which real-log source is licence-clean and available (public agent/tool-call datasets? self-owned
  pilot logs with consent?).
- Target size of the first real/anonymized batch (keep small; quality + provenance over volume).
- EIGS-100 weights — adopt the roadmap's or revisit.
