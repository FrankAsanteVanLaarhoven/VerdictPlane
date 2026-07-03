# Evidence Appendix — Conditions, Named Proofs, Reproduction

This appendix states the exact conditions behind every public claim so an
external auditor can reproduce them. Companion documents:
[EVIDENCE.md](EVIDENCE.md) (live-run artefacts) and
[BENCHMARK.md](BENCHMARK.md) (measured numbers).

## Claim → reproduction command

| Claim | Evidence | Reproduce with |
| --- | --- | --- |
| No model / network import in the enforcement path | Static AST allowlist, per module | `make test` (tests/test_enforcement_imports.py) |
| Zero egress at runtime | Socket kill-switch + empty network namespace | `make test` (tests/test_zero_egress.py) |
| Tamper detection at exact index | Randomized forgery battery + live forgery demo | `make test` (tests/test_provenance.py) + `make evidence` (E3, E6) |
| Tail truncation / rollback detected against a signed anchor | `checkpoint()` + `verify_extends()`; HMAC-signed with `VERDICTPLANE_ANCHOR_KEY` | `make test` (tests/test_anchor.py); `verdictplane anchor` / `verify-anchor` |
| 100% governed-call ledger coverage | Mixed-workload completeness incl. P4 wrappers | `make test` (tests/test_workloads.py) + `make bench` |
| Strict provenance records allow-intent *before* the side effect (opt-in) | `intent`→`executed` ordering; the `intent` survives a failed call; `intent` is non-terminal so the completeness KPI is unchanged | `VERDICTPLANE_STRICT_PROVENANCE=1`; `make test` (tests/test_interceptor.py strict-provenance cases) |
| Human gate blocks side effects (approve/deny/timeout) | Live cross-process before/after transcript | `make evidence` (E4); interactive: `examples/quickstart.py` + `verdictplane approve` |
| Multi-reviewer k-of-n quorum + deny-veto | Partial approval never executes; per-rule quorum via `govern`; approver identities recorded | `make test` (tests/test_quorum.py) |
| Fail-closed on failed accuracy gate | Deterministic deny, no reviewer contacted | `make test` (tests/test_workloads.py) |
| Advisory is fail-safe and cannot decide | Broken-transport run, decisions byte-identical | `make bench` (fail_safe section) + `make test` (tests/test_advisory.py) |
| Performance targets | 6-target scoreboard, exits nonzero on regression | `make bench` |
| Air-gapped cross-container approval | Both containers `network_mode: "none"` | `docker compose -f deploy/sidecar-compose.yml up --build agent`, then `run reviewer approve <token>` |
| Fresh-environment install | Wheel install + quickstart in a virgin venv | CI "Package builds and installs" step; locally: `python -m build --wheel` then install in a new venv |

## Benchmark conditions (behind the 19 µs / 62k numbers)

- **Host:** Intel Core i7-14700K, Linux 6.8 (glibc 2.35), Python 3.13.13.
- **Storage:** ext4 on local NVMe; ledger written with `fsync=False`
  (buffered). Tamper evidence is unaffected by buffering; a crash can lose
  the buffered tail, which presents as truncation and is detectable via an
  externally anchored head (`verdictplane head`). Durability-sensitive
  deployments pass `Ledger(..., fsync=True)` and must re-measure — fsync cost
  is storage-dependent and NOT included in the headline numbers.
- **Method:** 5 independent runs × 20,000 allow-path calls, fresh ledger per
  run, 500-call warmup before the throughput window; per-call
  `perf_counter_ns` timings; median run reported, per-run values and spread
  published alongside (`stability` section of `artifacts/stats.json`).
- **Advisory:** `VERDICTPLANE_ADVISORY=off` for all measurements; separately
  forced into error mode for the fail-safe assertion.
- **Reproducibility gate:** allow-p99 spread ≤ 10% across runs is a
  **dedicated-hardware claim**, gated locally. On shared CI runners the
  spread is recorded but informational (`--spread-report-only`): a single
  noisy-neighbor run can spike one p99 sample, which measures the runner,
  not the system. Absolute targets are never relaxed anywhere — observed
  shared-runner worsts (GitHub hosted, 2026-07): p99 ≈ 117 µs, throughput
  ≈ 12k/s — both still comfortably inside the absolute targets.
- **What the numbers mean:** `raw call` baseline is ~0.03 µs, so the
  ~16–19 µs governed-allow figure is effectively the full cost of governance
  (validation + policy + hash-chained append). The `require_human`
  auto-resolved figure (~90 µs p50) measures gate machinery only — real
  approvals are human-scale by design.
- CPU frequency scaling is the dominant variance source; pin the governor for
  tighter spreads.

## Named zero-egress proofs

1. **Static (AST allowlist).** Every enforcement module's imports must come
   from an allowlist containing no network or model-client module, and may
   never reference the advisory/CLI modules. Fails CI before code can run.
2. **Runtime (socket kill-switch).** `socket.socket`, `create_connection`,
   and `getaddrinfo` are replaced with raisers; the full enforcement battery
   (all three decision paths, gate resolution, both real workloads, chain
   verify) must pass untouched.
3. **Kernel (empty network namespace).** The same battery runs under
   `unshare -rn` — no interfaces exist; the harness first proves the netns is
   isolated by requiring an outbound probe to fail, then runs the battery.
4. **Deployment (runtime-enforced).** The sidecar compose runs agent and
   reviewer with `network_mode: "none"`; the container runtime allocates no
   interfaces, and the live cross-container approval flow was executed and
   recorded under that configuration.

## Fresh-environment installation validation

The wheel (`verdictplane`, import name `verdictplane`) is built from source,
installed into a virgin venv with no access to the repository, and validated
by importing the package, running the reviewer CLI, and executing the full
quickstart (blocked call → CLI approval → execution → chain verification).
This runs on every CI push (`.github/workflows/ci.yml`, final step).

## Known limitations (stated, not hidden)

- **Chain-only verification cannot see tail truncation on its own** — truncation
  *below the last anchor* and rollback are now caught by `verify_extends()` against
  an externally held `checkpoint()` (head + count + Merkle root; `verdictplane
  anchor` / `verify-anchor`). The optional HMAC (`VERDICTPLANE_ANCHOR_KEY`, held
  apart from the ledger writer) is keyed tamper-evidence, **not** asymmetric
  non-repudiation; the post-anchor tail is only covered by the next checkpoint, so
  anchor frequently. Privileged whole-file deletion, ed25519 signing (true
  non-repudiation), and Merkle inclusion proofs remain out of scope / roadmap.
- **The gate is a polling mechanism** (human-scale, cross-process). Multi-reviewer
  **k-of-n quorum with deny-veto** is now supported: a `require_human` rule may set
  `quorum: k`, `verdictplane approve` / `deny` accumulate one vote per identity, and
  the approver identities are recorded in the ledger. Reviewer SLAs / notifications
  remain roadmap (enterprise workflow track).
- **Headline latency is buffered-durability mode.** See benchmark conditions
  above; a durable-fsync benchmark mode is roadmap.
- **Benchmarks are host-dependent.** Re-run `make bench` on target hardware;
  the harness pins and publishes its environment in `stats.json` and flags
  dirty-tree captures.
- **Independent reproduction pending.** All artefacts regenerate from
  `make test` / `make bench` / `make evidence`, but no third party has yet
  reproduced them; treat v0.1.0 claims accordingly.

## Independent reproduction protocol

```bash
git clone https://github.com/FrankAsanteVanLaarhoven/VerdictPlane.git
cd VerdictPlane
make setup        # venv + editable install
make test         # 201 tests: conformance, tamper, gating, zero-egress, anchoring, quorum
make bench        # six-target scoreboard; nonzero exit on any miss
make evidence     # regenerates docs/EVIDENCE.md from live runs
```

Compare your regenerated `docs/EVIDENCE.md` / `artifacts/stats.json` against
the committed versions; the commit hash inside each file identifies the source
state it was captured from.

### Turnkey reproduction (Docker — one command)

For reviewers with only Docker installed, the whole protocol runs in a clean,
pinned container:

```bash
make repro       # builds deploy/repro.Dockerfile and runs the protocol
```

or directly:

```bash
docker build -f deploy/repro.Dockerfile \
  --build-arg VERDICTPLANE_REPRO_COMMIT=$(git rev-parse HEAD) \
  -t verdictplane-repro .
docker run --rm verdictplane-repro
```

The container runs the test suite, the benchmark scoreboard, and the evidence
pack, and **exits nonzero on any failure**. The absolute benchmark targets
(p99 < 1 ms, > 10k actions/s, tamper 100%, zero gaps, fail-safe) gate the run;
the allow-p99 **spread** target is reported but not gated inside a container,
because a shared/virtualized host measures the environment, not the system — the
tight ≤ 10% spread is a dedicated-hardware claim you reproduce natively with a
pinned CPU governor (the benchmark report records the governor, so this is
verifiable). The commit is stamped into the run via the build argument.
