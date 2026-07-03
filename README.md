# VerdictPlane

[![ci](https://github.com/FrankAsanteVanLaarhoven/VerdictPlane/actions/workflows/ci.yml/badge.svg)](https://github.com/FrankAsanteVanLaarhoven/VerdictPlane/actions/workflows/ci.yml)

**VerdictPlane is a deterministic, zero-egress control plane for consequential
AI actions.** It evaluates every action against declarative policy *before*
execution, records tamper-evident provenance in a hash-chained ledger, and
places high-risk actions behind mandatory human approval — without placing any
model in the enforcement path.

Post-hoc governance observes actions after the fact. VerdictPlane's claim is
different: **a governed action physically cannot execute without deterministic
pre-execution control.**

- **Deterministic enforcement.** The decision path is pure code: a dict match,
  one SHA-256, a file append. No model is ever consulted to decide.
- **Zero egress.** Enforcement makes no network calls — proven statically
  (import allowlist), at runtime (socket kill-switch), and at the kernel
  (empty network namespace). Runs entirely inside your VPC or air-gapped.
- **Default-deny posture.** Unmatched actions require human approval. Timeouts
  deny. A broken advisory component changes nothing.
- **Provenance by default.** No governed action runs un-recorded; any
  mutation of history is detected at the exact line.

Measured, not claimed (`make bench`, full method in [docs/BENCHMARK.md](docs/BENCHMARK.md)):

| | measured | target |
| --- | --- | --- |
| Enforcement overhead (allow path, p99) | **~19 µs** | < 1 ms |
| Governed actions/sec (single core) | **~62,000** | > 10,000 |
| Tamper detection (randomized trials) | **200/200, exact line** | 100% |
| Provenance gaps under mixed load | **0** | 0 |

Every claim above has a live-run artefact in [docs/EVIDENCE.md](docs/EVIDENCE.md);
machine specs, benchmark conditions, named proofs, and reproduction commands are
in [docs/EVIDENCE_APPENDIX.md](docs/EVIDENCE_APPENDIX.md).

**Status:** P0–P7 acceptance criteria have passed. v0.1.0 is ready for OSS
release and controlled pilot deployments, subject to the reproduction
conditions documented in the evidence appendix.

## Five-minute quickstart

```bash
git clone https://github.com/FrankAsanteVanLaarhoven/VerdictPlane.git
cd VerdictPlane
make setup && make test
```

Or as a library (dist name `verdictplane`, import name `verdictplane`;
PyPI release pending — install from source until then):

```bash
pip install git+https://github.com/FrankAsanteVanLaarhoven/VerdictPlane.git
```

Terminal 1 — run a governed tool call (it blocks on the gate):

```bash
PYTHONPATH=. .venv/bin/python examples/quickstart.py
```

Terminal 2 — you are the human in the loop:

```bash
.venv/bin/verdictplane pending            # see what's waiting, and why
.venv/bin/verdictplane approve <token>    # or: verdictplane deny <token>
.venv/bin/verdictplane log                # the tamper-evident audit trail
.venv/bin/verdictplane verify             # walk the hash chain
```

That's the whole product: the `send_email` call in terminal 1 physically
cannot run until you approve it, and everything that happened is in a
hash-chained ledger you can hand to an auditor.

## How it works

```
agent / model / workflow
        |  (tool call, decision, trigger)
        v
+--------------------------------------------------+  IN-PATH, ZERO-EGRESS
|  @governed decorator | MCP dispatch | sidecar     |
|   1. build Action{tool, effect, args, agent}      |
|   2. policy.evaluate(action) -> allow | deny |    |
|      require_human      (deterministic, no model) |
|   3. ledger.append(record)  (hash-chained, BEFORE |
|      any side effect)                             |
|   4. require_human -> gate blocks for a reviewer  |
|   5. execute OR refuse; append the outcome        |
+--------------------------------------------------+
        |                        ^
        v                        | optional, OFF the hot path, fail-safe
   actual side effect       advisory risk summary for the reviewer
```

Details, threat model, and invariants: [ARCHITECTURE.md](ARCHITECTURE.md).

## Governing an MCP agent

Wrap whatever dispatches your agent's tool calls; the agent keeps only the
governed handle:

```python
from verdictplane import Gate, Ledger, load_policy
from verdictplane.mcp import governed_dispatch

call_tool = governed_dispatch(
    dispatch,                                  # your existing MCP dispatch fn
    policy=load_policy("policies/mcp_demo.yaml"),
    ledger=Ledger("artifacts/ledger.jsonl"),
    gate=Gate("artifacts/gate"),
    effect_of={"read_file": "read", "write_file": "write"},  # unknown -> write
)
```

Reads flow, writes wait for a human, and the agent cannot reach the tools any
other way. Runnable version: `examples/mcp_agent_demo.py`.

## Policy

Declarative YAML, first-match-wins, safe default for anything unmatched:

```yaml
default: require_human
rules:
  - match: { effect: read }
    decision: allow
  - match: { agent: untrusted, effect: write }
    decision: deny
  - match: { tool: db.write, args.amount: { gt: 1000 } }
    decision: require_human
  - match: { tool: "fs.*", effect: write }        # globs; gt/lt/eq/in operators
    decision: require_human
```

Missing fields, unknown operators, and incomparable types never match a rule —
actions fall through toward the safe default, never through an error. Examples
in [`policies/`](policies/).

## Real workloads, day one

Two production-shaped systems already flow through VerdictPlane — an MLflow model
promotion (fail-closed accuracy gate, human-gated production alias) and an
incident-response rollback (proposal recorded, execution gated). Interfaces,
policies, and measured overhead: [CASE_STUDY.md](CASE_STUDY.md).

## Deploy as a sidecar (no network at all)

```bash
docker compose -f deploy/sidecar-compose.yml up --build agent   # network_mode: none
docker compose -f deploy/sidecar-compose.yml run reviewer pending
docker compose -f deploy/sidecar-compose.yml run reviewer approve <token>
```

Both containers get zero network interfaces; enforcement and review coordinate
through a shared volume. `make demo` runs the same session locally.

## Optional advisory (never in the decision)

Reviewers can opt into model-written risk summaries next to each pending
action: `VERDICTPLANE_ADVISORY=fable5` (hosted frontier model) or
`VERDICTPLANE_ADVISORY=local` (Ollama on your own GPU — fully air-gapped). The
enforcement path cannot even import the advisory module (statically tested),
and every advisory failure degrades to "no summary", never to a decision.

## Repository map

```
src/verdictplane/     enforcement core: types, provenance, policy, interceptor,
                  mcp, gate  (+ off-path: cli, advisory)
policies/         example + workload policies
workloads/        governed DriftGuard promotion, Sentinel rollback
bench/            make bench -> artifacts/stats.json + docs/BENCHMARK.md
tests/            180 tests: conformance, tamper, gating, zero-egress
deploy/           Dockerfile, network-less sidecar compose, demo agent
docs/             EVIDENCE.md (audit pack), BENCHMARK.md (measured numbers)
```

## Contributing

`make setup && make test` must stay green and the invariants in
[CONTRIBUTING.md](CONTRIBUTING.md) are non-negotiable (deterministic
enforcement, zero egress, append-only provenance, safe defaults).

MIT license.
