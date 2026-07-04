# VerdictPlane — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `f64f3bcddf183d3a3db0bfd1f484ac5a7d92fbba`
- **Captured:** 2026-07-04T00:22:22Z
- **Host:** Intel(R) Core(TM) i7-14700K · Python 3.13.13 · Linux-6.8.0-111-generic-x86_64-with-glibc2.35
- **CPU governor:** powersave — not pinned to performance; frequency scaling widens p99 spread — pin the governor for a dedicated-hardware spread claim
- **Ledger:** filesystem `ext4`, fsync=False
- **Advisory:** off (forced); enforcement never imports advisory regardless
- **Method:** 1 discarded warm-up run(s), then 5 measured runs x 20000 allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | PASS — worst run 19.06 µs |
| Throughput > 10k governed actions/s (worst run) | PASS — worst run 60747/s |
| Tamper detection 100% at exact index | PASS — 200/200 |
| Zero provenance gaps + chain verifies | PASS — 0 gaps / 200 calls |
| Fail-safe with advisory forced broken | PASS |
| Reproducibility (allow p99 spread <= 10%) | PASS — spread 3.9% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| raw call (baseline) | 0.03 | 0.04 | 0.05 |
| governed allow | 16.04 | 17.28 | 18.6 |
| governed deny | 18.65 | 20.09 | 21.31 |
| require_human (auto-resolved gate) | 168.27 | 231.31 | 309.49 |
| ledger append | 10.47 | 11.15 | 12.19 |

Full-chain verify: 31000 entries in 0.1542 s.

## Stability across runs

- allow p99 per run (µs): [18.92, 18.6, 18.34, 18.59, 19.06] — spread 3.9%
- throughput per run (ops/s): [62016, 62479, 61449, 60870, 60747] — spread 2.8%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
| DriftGuard promote (Staging, allow) | 25.61 | 27.78 | 34.2 |
| DriftGuard promote (Production, gated+auto-resolve) | 204.03 | 283.21 | 345.5 |
| Sentinel proposal (recorded) | 24.09 | 25.69 | 27.34 |

- Staging-promote throughput: 37896 ops/s
- Chain verifies after load: True

## Durability-mode performance matrix (T6)

Allow-path governance cost as the ledger durability mode varies (policy + gate held fixed, so the
deltas isolate the cost of durability):

| Mode | p50 µs | p95 µs | p99 µs | ops/s | guarantee |
| --- | --- | --- | --- | --- | --- |
| memory | 6.25 | 7.55 | 8.68 | 152660 | in-memory only; ephemeral, no cross-process (diagnostic lower bound) |
| jsonl-buffered | 16.15 | 17.4 | 18.73 | 61396 | disk append + flush, no fsync (default headline); a crash may lose the buffered tail |
| durable-fsync | 1663.04 | 2105.33 | 2418.33 | 589 | fsync per append; crash-durable tail |

`memory` is a diagnostic lower bound (no persistence, no cross-process); `jsonl-buffered` is the
deployable default; `durable-fsync` trades latency for a crash-durable tail. Tamper evidence is
identical across all three.

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
