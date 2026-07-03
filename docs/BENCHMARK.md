# VerdictPlane — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `2937cec62b6989f1361672b86fedfbc3e5466e26`
- **Captured:** 2026-07-03T10:53:34Z
- **Host:** Intel(R) Core(TM) i7-14700K · Python 3.13.13 · Linux-6.8.0-111-generic-x86_64-with-glibc2.35
- **Ledger:** filesystem `ext4`, fsync=False
- **Advisory:** off (forced); enforcement never imports advisory regardless
- **Method:** 5 independent runs x 20000 allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | PASS — worst run 19.2 µs |
| Throughput > 10k governed actions/s (worst run) | PASS — worst run 60539/s |
| Tamper detection 100% at exact index | PASS — 200/200 |
| Zero provenance gaps + chain verifies | PASS — 0 gaps / 200 calls |
| Fail-safe with advisory forced broken | PASS |
| Reproducibility (allow p99 spread <= 10%) | PASS — spread 3.5% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| raw call (baseline) | 0.03 | 0.04 | 0.05 |
| governed allow | 16.17 | 17.52 | 18.92 |
| governed deny | 17.82 | 19.39 | 20.68 |
| require_human (auto-resolved gate) | 100.8 | 132.29 | 224.75 |
| ledger append | 10.8 | 11.92 | 12.96 |

Full-chain verify: 31000 entries in 0.1564 s.

## Stability across runs

- allow p99 per run (µs): [18.92, 19.2, 18.54, 18.91, 19.16] — spread 3.5%
- throughput per run (ops/s): [61045, 60960, 61183, 60881, 60539] — spread 1.1%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| DriftGuard promote (Staging, allow) | 25.75 | 27.51 | 29.7 |
| DriftGuard promote (Production, gated+auto-resolve) | 124.84 | 159.5 | 266.37 |
| Sentinel proposal (recorded) | 23.97 | 25.59 | 27.36 |

- Staging-promote throughput: 38546 ops/s
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
