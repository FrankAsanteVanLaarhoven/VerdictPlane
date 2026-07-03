# VerdictPlane — agent guardrails

Invariants (enforced by tests — never weaken them):
- The enforcement path (`src/verdictplane/*` except `advisory.py`, `cli.py`) is
  deterministic: no model client, no network import, no GPU.
  `tests/test_enforcement_imports.py` asserts this statically.
- Provenance is append-only; never rewrite ledger history. `verify()` is part of CI.
- Default decision is the safe one: unmatched actions -> `require_human`.
- Advisory (model-generated risk summaries) is optional, off the hot path, and
  fail-safe: if it errors, enforcement is unaffected and defaults safe.
- `artifacts/` (ledgers, gate queues, bench stats) is generated output — never commit it.

Workflow:
- Phased build (P0–P7, see README). Ship a phase, run its acceptance check,
  show output, then continue. Never advance on red.
- Validate with `make test`. Stats come from `make bench` (P5+), never prose.
