# VerdictPlane — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `9572dfcac3fa6054058bfeb8f12c279c8c37d677 (working tree DIRTY at capture time)`
- **Captured:** 2026-07-03T10:51:10Z
- **Host:** Intel(R) Core(TM) i7-14700K · Python 3.13.13 · Linux-6.8.0-111-generic-x86_64-with-glibc2.35
- **Ledger:** filesystem `ext4`, fsync=False
- **Advisory:** off (forced); enforcement never imports advisory regardless
- **Method:** 5 independent runs x 20000 allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | PASS — worst run 19.11 µs |
| Throughput > 10k governed actions/s (worst run) | PASS — worst run 61036/s |
| Tamper detection 100% at exact index | PASS — 200/200 |
| Zero provenance gaps + chain verifies | PASS — 0 gaps / 200 calls |
| Fail-safe with advisory forced broken | PASS |
| Reproducibility (allow p99 spread <= 10%) | PASS — spread 2.6% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| raw call (baseline) | 0.03 | 0.03 | 0.05 |
| governed allow | 16.05 | 17.35 | 18.85 |
| governed deny | 17.61 | 19.27 | 20.76 |
| require_human (auto-resolved gate) | 100.02 | 128.49 | 218.44 |
| ledger append | 10.54 | 11.58 | 13.23 |

Full-chain verify: 31000 entries in 0.155 s.

## Stability across runs

- allow p99 per run (µs): [18.62, 19.11, 18.85, 19.03, 18.84] — spread 2.6%
- throughput per run (ops/s): [61521, 62657, 61677, 61435, 61036] — spread 2.6%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| DriftGuard promote (Staging, allow) | 25.12 | 27.08 | 36.3 |
| DriftGuard promote (Production, gated+auto-resolve) | 121.56 | 152.91 | 242.8 |
| Sentinel proposal (recorded) | 24.31 | 26.34 | 31.01 |

- Staging-promote throughput: 38563 ops/s
- Chain verifies after load: True

## Fail-safe detail

Advisory backend configured and transport forced to error: summary returned =
`None`; policy decisions unchanged =
True; unmatched action default =
`require_human`.

## Caveats

- Human-gated paths are human-scale by design; the auto-resolved gate number
  measures VerdictPlane's machinery (submit + resolve + 2 ledger appends), not
  reviewer latency.
- Numbers are host- and filesystem-dependent; re-run `make bench` on the
  target machine. fsync=False (default): tamper evidence is unaffected, a
  crash can lose the buffered tail (truncation is detectable via an anchored
  head). CPU frequency scaling is the main variance source.
