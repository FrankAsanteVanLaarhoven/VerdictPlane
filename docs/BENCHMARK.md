# Keystone — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `8d8ec831c59e65af873d4d487a2a1385c6429c70`
- **Captured:** 2026-07-03T00:44:29Z
- **Host:** Intel(R) Core(TM) i7-14700K · Python 3.13.13 · Linux-6.8.0-111-generic-x86_64-with-glibc2.35
- **Ledger:** filesystem `ext4`, fsync=False
- **Advisory:** off (forced); enforcement never imports advisory regardless
- **Method:** 5 independent runs x 20000 allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | PASS — worst run 19.3 µs |
| Throughput > 10k governed actions/s (worst run) | PASS — worst run 59545/s |
| Tamper detection 100% at exact index | PASS — 200/200 |
| Zero provenance gaps + chain verifies | PASS — 0 gaps / 200 calls |
| Fail-safe with advisory forced broken | PASS |
| Reproducibility (allow p99 spread <= 10%) | PASS — spread 0.7% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| raw call (baseline) | 0.03 | 0.05 | 0.05 |
| governed allow | 16.52 | 17.83 | 19.25 |
| governed deny | 18.56 | 20.29 | 21.94 |
| require_human (auto-resolved gate) | 90.68 | 108.85 | 211.99 |
| ledger append | 10.93 | 11.79 | 12.87 |

Full-chain verify: 31000 entries in 0.1663 s.

## Stability across runs

- allow p99 per run (µs): [19.28, 19.17, 19.24, 19.25, 19.3] — spread 0.7%
- throughput per run (ops/s): [59545, 59986, 60270, 59881, 60294] — spread 1.2%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| DriftGuard promote (Staging, allow) | 26.65 | 28.99 | 40.07 |
| DriftGuard promote (Production, gated+auto-resolve) | 112.31 | 137.22 | 248.22 |
| Sentinel proposal (recorded) | 24.36 | 26.2 | 28.16 |

- Staging-promote throughput: 37754 ops/s
- Chain verifies after load: True

## Fail-safe detail

Advisory backend configured and transport forced to error: summary returned =
`None`; policy decisions unchanged =
True; unmatched action default =
`require_human`.

## Caveats

- Human-gated paths are human-scale by design; the auto-resolved gate number
  measures Keystone's machinery (submit + resolve + 2 ledger appends), not
  reviewer latency.
- Numbers are host- and filesystem-dependent; re-run `make bench` on the
  target machine. fsync=False (default): tamper evidence is unaffected, a
  crash can lose the buffered tail (truncation is detectable via an anchored
  head). CPU frequency scaling is the main variance source.
