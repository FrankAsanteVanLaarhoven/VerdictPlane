# VerdictPlane — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `bc92b3eef979844ebd83f831589537f435e162df`
- **Captured:** 2026-07-03T17:37:03Z
- **Host:** Intel(R) Core(TM) i7-14700K · Python 3.13.13 · Linux-6.8.0-111-generic-x86_64-with-glibc2.35
- **CPU governor:** powersave — not pinned to performance; frequency scaling widens p99 spread — pin the governor for a dedicated-hardware spread claim
- **Ledger:** filesystem `ext4`, fsync=False
- **Advisory:** off (forced); enforcement never imports advisory regardless
- **Method:** 1 discarded warm-up run(s), then 5 measured runs x 20000 allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | PASS — worst run 19.37 µs |
| Throughput > 10k governed actions/s (worst run) | PASS — worst run 60426/s |
| Tamper detection 100% at exact index | PASS — 200/200 |
| Zero provenance gaps + chain verifies | PASS — 0 gaps / 200 calls |
| Fail-safe with advisory forced broken | PASS |
| Reproducibility (allow p99 spread <= 10%) | PASS — spread 4.1% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| raw call (baseline) | 0.03 | 0.04 | 0.05 |
| governed allow | 16.25 | 17.56 | 18.98 |
| governed deny | 18.75 | 20.18 | 21.71 |
| require_human (auto-resolved gate) | 100.91 | 133.49 | 224.95 |
| ledger append | 10.51 | 11.38 | 12.49 |

Full-chain verify: 31000 entries in 0.1568 s.

## Stability across runs

- allow p99 per run (µs): [19.37, 18.59, 18.98, 19.06, 18.86] — spread 4.1%
- throughput per run (ops/s): [62074, 60426, 61641, 61402, 61559] — spread 2.7%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| DriftGuard promote (Staging, allow) | 25.44 | 30.12 | 62.98 |
| DriftGuard promote (Production, gated+auto-resolve) | 124.78 | 154.47 | 254.86 |
| Sentinel proposal (recorded) | 24.16 | 25.98 | 29.13 |

- Staging-promote throughput: 38325 ops/s
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
