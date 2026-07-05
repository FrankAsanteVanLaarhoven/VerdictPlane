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
  mutation of history is detected at the exact line, and truncation below the last
  anchor (or rollback) is caught by verifying against an externally held,
  optionally signed checkpoint.

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

**Reviewers:** [REPRODUCE.md](REPRODUCE.md) is the one-command reproduction + critique guide for
EAG-Bench (what each track tests, how to read the EIGS score, and **how to attack the benchmark**).

**Status:** P0–P7 acceptance criteria have passed. v0.1.0 is published on PyPI
(`pip install verdictplane`) and ready for controlled pilot deployments, subject
to the reproduction conditions documented in the evidence appendix.

## How VerdictPlane compares

VerdictPlane is a **deterministic, in-path control plane** for consequential AI
actions: it sits between an agent and the systems it acts on and enforces policy
*before* execution. That puts it in a different category from three adjacent classes
of tools it is often confused with.

| | VerdictPlane | Observability / AIOps<br>(Datadog, Dynatrace, Dash0+Agent0) | Model guardrails<br>(NeMo Guardrails, Llama Guard) | Policy engines<br>(OPA / Cedar) |
| --- | --- | --- | --- | --- |
| **When it acts** | Pre-execution, in-path | Post-hoc / during | Pre/inline, on content | Pre-execution, in-path |
| **Decision basis** | Deterministic policy | Model-assisted analysis | A model classifies risk | Deterministic policy |
| **Model in the decision** | Never (statically proven) | Yes | Yes — it *is* the mechanism | No |
| **Provenance** | Hash-chained tamper-evident ledger | Traces / logs | Usually none | External audit log |
| **Human approval** | First-class, blocking, default-deny | Advisory | Rare | Not built in |
| **Zero-egress / air-gap** | Design goal (static + kernel proof) | Cloud-hosted | Often calls a hosted model | Self-hostable |
| **Shaped for agent actions** | Yes (tool, effect, args, agent) | Generic infra | Content, not actions | Generic policy |

The nearest neighbour is a **policy engine** (OPA/Cedar) — both are deterministic and
pre-execution. VerdictPlane's difference is that it is purpose-built for *agent actions*:
it bundles the decision with a tamper-evident provenance ledger and a blocking human
gate, ships with socket- and kernel-level zero-egress proofs, and is validated on real
workloads (model promotion, incident rollback). It is **not** a model guardrail — no
model ever sits in the decision (statically enforced), so verdicts are reproducible and
auditable rather than probabilistic.

**Use it *with* observability, not instead of it.** Feed VerdictPlane's ledger events
into your existing platform for correlation and investigation; VerdictPlane's job is to
make non-compliant actions *unable to execute* and to leave an auditor-grade trail.

## Five-minute quickstart

```bash
git clone https://github.com/FrankAsanteVanLaarhoven/VerdictPlane.git
cd VerdictPlane
make setup && make test
```

Or as a library — published on PyPI (dist and import name `verdictplane`):

```bash
pip install verdictplane
```

Or track `main` from source:

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
.venv/bin/verdictplane anchor --out a.json    # signed checkpoint to anchor externally
.venv/bin/verdictplane verify-anchor a.json   # prove the ledger only ever grew
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
|   3. deny / require_human: append the decision    |
|      (hash-chained) BEFORE any side effect        |
|   4. require_human -> gate blocks for a reviewer  |
|   5. allow: execute, then append the terminal     |
|      outcome (the decision is always pre-exec)    |
+--------------------------------------------------+
        |                        ^
        v                        | optional, OFF the hot path, fail-safe
   actual side effect       advisory risk summary for the reviewer
```

Details, threat model, and invariants: [ARCHITECTURE.md](ARCHITECTURE.md).

> **Provenance ordering, precisely.** The policy *decision* is always made before
> execution. The *record* is written before the side effect for `deny` and
> `require_human`; on the `allow` hot path the single terminal record is written on
> completion — so a crash mid-execution presents as a detectable tail gap, never a
> silently unrecorded action (see [docs/EVIDENCE_APPENDIX.md](docs/EVIDENCE_APPENDIX.md)).
> For audit-critical paths, opt into **strict provenance**
> (`VERDICTPLANE_STRICT_PROVENANCE=1`, or `strict_provenance=True` per call) to record an
> `intent` entry before the allow side effect too, at the cost of a second append per action.

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
    quorum: 2                                       # k-of-n approval; any deny vetoes
  - match: { tool: "fs.*", effect: write }        # globs; gt/lt/eq/in operators
    decision: require_human
```

Missing fields, unknown operators, and incomparable types never match a rule —
actions fall through toward the safe default, never through an error. A
`require_human` rule may set `quorum: k` for k-of-n approval (each reviewer's
`verdictplane approve` counts once; any `deny` vetoes; the approver identities
are recorded in the ledger). Examples in [`policies/`](policies/).

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
                  mcp, gate  (+ off-path: cli, advisory, observability)
policies/         example + workload policies
workloads/        governed DriftGuard promotion, Sentinel rollback
bench/            make bench -> artifacts/stats.json + docs/BENCHMARK.md
tests/            249 tests: conformance, tamper, gating, zero-egress, strict-provenance,
                  anchoring, quorum, durability, eag-schema/harness/redteam/replay/eigs/observability
benchmarks/       eag_bench: 100-case corpus + schema, Side-Effect Escape harness (0/100), agentic
                  red-team, compliance coverage, real-trace replay + de-id gate, EIGS scorer (make eag
                  -> 100/100); see REPRODUCE.md
deploy/           Dockerfile, network-less sidecar compose, demo agent
docs/             EVIDENCE.md (audit pack), BENCHMARK.md (measured numbers),
                  EVIDENCE_APPENDIX.md (conditions + reproduction),
                  READINESS_SUMMARY.md (one-page reviewer brief),
                  METRICS.md (metric -> failure mapping), REVIEW_GATE.md (pre-final checklist)
```

## Contributing

`make setup && make test` must stay green and the invariants in
[CONTRIBUTING.md](CONTRIBUTING.md) are non-negotiable (deterministic
enforcement, zero egress, append-only provenance, safe defaults).

MIT license.
