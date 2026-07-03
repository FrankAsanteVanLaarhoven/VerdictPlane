# VerdictPlane v0.1.0 — Readiness Summary

**For external technical and academic reviewers.**
Version 0.1.0 · Repository <https://github.com/FrankAsanteVanLaarhoven/VerdictPlane> ·
PyPI <https://pypi.org/project/verdictplane/> (`pip install verdictplane`)

## What it is

VerdictPlane is a deterministic, zero-egress **control plane for consequential AI actions**.
It evaluates every action against declarative policy *before* execution, records tamper-evident
provenance in a hash-chained ledger, and places high-risk actions behind a mandatory, blocking
human gate — **without any model in the enforcement path**. The distinction from post-hoc
governance: a governed action physically cannot execute without deterministic pre-execution
control.

## Claim → validation status (verified against the repository)

Every row below was checked by running the suite and reading the enforcement modules, not taken
on trust. "Validated" = backed by a passing automated test **and** confirmed in code.

| Claim | Status | How it is backed |
| --- | --- | --- |
| No model / network module in the enforcement path | **Validated** | Static AST allowlist per module (`tests/test_enforcement_imports.py`); denies network SDKs and the advisory/CLI modules |
| Deterministic policy evaluation, safe defaults | **Validated** | Pure first-match engine; missing fields / unknown operators / incomparable types never match — fall through to default (`policy.py`, conformance tests) |
| Tamper-evident provenance, exact-index detection | **Validated** | SHA-256 hash chain; `verify()` returns first bad index; randomized forgery battery (`provenance.py`, `tests/test_provenance.py`) |
| Blocking human gate, default-deny, fail-safe timeout | **Validated** | File-backed cross-process gate; timeout resolves to **denied** (`gate.py`, `tests/test_interceptor.py`) |
| Zero unapproved side effects on real workloads | **Validated** | Governed MLflow promotion + incident rollback; every call leaves exactly one terminal record (`tests/test_workloads.py`) |
| Zero egress | **Validated** | Static allowlist + runtime socket kill-switch + kernel empty-netns battery + sidecar `network_mode: none` (`tests/test_zero_egress.py`, evidence appendix) |
| Fail-safe advisory (cannot influence a decision) | **Validated** | Enforcement cannot import advisory (static); broken-transport run leaves decisions byte-identical (`tests/test_advisory.py`) |
| Performance: allow-path p99 < 1 ms, > 10k actions/s | **Validated (this host)** | Fresh `make bench` on Intel i7-14700K: p99 ≈ **19 µs**, throughput ≈ **60k/s** — both well inside targets |
| Benchmark reproducibility (spread ≤ 10%) | **Conditional** | A dedicated-hardware claim; sensitive to CPU-governor state (documented). A cold first run can exceed the spread while absolute targets still pass |
| Independent (third-party) reproduction | **Pending** | All artefacts regenerate locally; foreign-hardware reproduction exists via CI runners (absolute targets met), but no external party has reproduced them yet |

**Test suite:** 180 tests, all passing (conformance, tamper, gating, zero-egress, workloads).

## Measured performance (fresh run, this review)

- Host: Intel Core i7-14700K, Linux 6.8, Python 3.13, ext4/NVMe, `fsync=False` (buffered).
- Governed allow path: p50 ≈ 16 µs, p99 ≈ **19 µs** (target < 1 ms). Raw-call baseline ≈ 0.03 µs,
  so ~19 µs is effectively the full cost of governance (validate + policy + hash-chained append).
- Throughput: ≈ **60,000 governed actions/s**, single core (target > 10,000).
- Tamper detection and provenance-completeness targets pass; the fail-safe-advisory assertion passes.
- Caveat observed live: the reproducibility-spread gate flipped to *fail* on a cold run (first run
  ≈ 38 µs before warm-up) — a governor/warm-up artefact, not a change in the absolute numbers. Pin
  the CPU governor (or discard the warm-up run) for a tight spread.

## Strengths

- Hard separation between deterministic enforcement and every optional AI component — statically
  enforced, not merely asserted.
- Cryptographic, append-only provenance by default; tampering is caught at the exact line.
- Very low overhead (~19 µs p99) suitable for high-frequency agent loops.
- First-class support for sovereign / air-gapped deployment, proven at socket and kernel level.
- Documentation is honest about scope: the evidence appendix states limitations and benchmark
  conditions rather than hiding them.

## Known limitations (as documented in the repository)

- **Chain-only verification cannot detect tail truncation** — requires comparison against an
  externally anchored head hash (Merkle / signed checkpoints are roadmap).
- **Allow-path provenance is written on completion**, not before the side effect (deny and
  require_human *are* recorded first). A crash mid-execution presents as a detectable tail gap; a
  strict pre-record mode for audit-critical paths is roadmap.
- **The human gate is a polling, single-reviewer mechanism** — correct and cross-process, but
  human-scale; multi-reviewer quorum, SLAs, and notifications are roadmap.
- **Headline latency is buffered-durability mode**; a durable-`fsync` benchmark mode is roadmap.
- **Benchmarks are host-dependent** — re-run `make bench` on target hardware.
- **Independent reproduction is still pending** — treat v0.1.0 performance/reproducibility claims
  as self-validated until a third party runs the protocol below.

## How to evaluate (≈ 5 minutes)

```bash
git clone https://github.com/FrankAsanteVanLaarhoven/VerdictPlane.git && cd VerdictPlane
make setup     # venv + editable install
make test      # 180 tests
make bench      # six-target scoreboard; nonzero exit on any absolute-target miss
make evidence  # regenerates docs/EVIDENCE.md from live runs
```

Then compare your regenerated `docs/EVIDENCE.md` / `artifacts/stats.json` against the committed
versions — each embeds the commit hash it was captured from. Full conditions and named proofs:
[`docs/EVIDENCE_APPENDIX.md`](EVIDENCE_APPENDIX.md).

## Bottom line

VerdictPlane v0.1.0 is a working, auditable, deterministic in-path governance layer whose core
security properties are backed by passing tests and readable code, with measured sub-20 µs
overhead. It is ready for controlled pilots and technical review. The single outstanding item for
full external credibility is **independent third-party reproduction** of the benchmark and evidence
runs; the protocol above is designed to make that a one-command exercise.

**Contact:** Frank Asante Van Laarhoven · frankleroyvan@gmail.com
