# Keystone — Architecture

## The one sentence

Keystone sits **in the path** of consequential AI actions and does three
deterministic things before anything commits: record, check, gate.

## Enforcement flow

`govern(action, call, *, policy, ledger, gate)` is the single choke point
(`src/keystone/interceptor.py`). Every entry surface funnels into it:

| Surface | Module | Use when |
| --- | --- | --- |
| `@governed` decorator | `interceptor.py` | you own the tool function (Python) |
| `governed_dispatch` / `guard_mcp_call` | `mcp.py` | agent tool-calls at the MCP boundary |
| sidecar containers | `deploy/` | services you can't wrap in code |

Order of operations, and why it matters:

1. **Validate** the action against the schema (`types.Action`) — boundary
   only; the hot path works on plain dicts.
2. **Evaluate policy** (`policy.evaluate`) — pure, first-match-wins over an
   ordered rule list. No I/O, no model, no clock.
3. **Append to the ledger BEFORE any side effect** — a governed action can
   fail, but it cannot run un-recorded.
4. **Gate** — `require_human` blocks on a file-backed approval queue until a
   reviewer resolves it. Timeout resolves to DENIED.
5. **Execute or refuse**, then append the terminal outcome
   (`executed | blocked | denied_by_human | failed`).

## Trust anchor: the provenance ledger

`provenance.Ledger` is an append-only JSONL file where each entry commits to
the previous entry's SHA-256 (`hash = H(prev + body)`).

- `verify()` walks the chain and returns the exact first bad line on any
  mutation, insertion, deletion, or reordering of recorded history.
- **Threat model:** tamper-*evidence*, not tamper-*prevention*. A privileged
  attacker can delete the file or rewrite the tail wholesale; that is
  detectable by comparing `head()` against an externally anchored head hash
  (`keystone head` exists for exactly this — anchor it somewhere the attacker
  can't reach). Merkle-tree anchoring is the planned upgrade path.
- **Durability:** `fsync=False` by default (measured ~19 µs p99 end-to-end);
  a crash can lose the buffered tail, which presents as truncation — an
  anchored head detects it. Pass `fsync=True` where durability beats latency.

## Policy semantics

Declarative YAML, validated on load (malformed policies refuse to load).
Conditions: scalars are case-sensitive globs (`fnmatchcase`); mappings are
operators (`gt/lt/eq/in`) on dotted paths into the action (`args.amount`).

Failure philosophy: **fall through toward the safe default, never through an
error.** Missing fields, unknown operators, and incomparable types simply
don't match; anything unmatched takes `default` (which itself defaults to
`require_human`).

## Human gate

File-backed `pending/` → `resolved/` queue (`gate.py`). Cross-process by
construction: an interceptor blocked in one process/container resolves the
moment a reviewer runs `keystone approve` in another — including across
network-less containers sharing a volume.

Latency characteristics are **human-scale by design**: polling (50 ms default)
plus reviewer time. The machinery itself (submit + resolve + two ledger
appends) measures ~90 µs p50 (see BENCHMARK.md). This is a gate for
consequential actions, not a real-time control loop.

## Advisory isolation (the moat)

The optional risk-summary module (`advisory.py`) may call a hosted model or a
local Ollama model — **for the reviewer's eyes only**. Isolation is enforced,
not promised:

- statically: enforcement modules import from an allowlist that contains no
  network or model client, and can never import `advisory`/`cli`
  (`tests/test_enforcement_imports.py`, AST-level, runs in CI);
- at runtime: the full enforcement battery passes with every socket
  constructor replaced by a raiser, and inside an empty network namespace
  (`tests/test_zero_egress.py`);
- by behavior: every advisory failure returns `None`; decisions are
  byte-identical with advisory off, on, or broken (asserted in `make bench`).

## Invariants and where they're enforced

| Invariant | Enforced by |
| --- | --- |
| No model/network import in enforcement | `test_enforcement_imports.py` (AST allowlist) |
| Zero egress at runtime | `test_zero_egress.py` (socket kill-switch + netns) |
| No side effect without a ledger record | `govern()` ordering + completeness tests |
| No side effect without approval when gated | interceptor/workload/MCP test suites |
| Timeout / advisory failure → safe decision | gate timeout tests + bench fail-safe check |
| Append-only, tamper-evident history | tamper battery (exact-index) + live forgery demo |
| Performance claims are measured | `make bench` exits nonzero if any target regresses |

## Module map

```
types.py        Action / Decision / LedgerEntry schemas (pydantic, boundary only)
provenance.py   hash-chained append-only ledger: append / head / verify / entries
policy.py       load_policy / validate_policy / evaluate  (pure)
interceptor.py  govern(), @governed, redaction, agent contextvar
mcp.py          governed_dispatch / guard_mcp_call at the MCP boundary
gate.py         file-backed blocking approval queue, fail-safe timeout
cli.py          reviewer surface: pending/approve/deny/verify/log/head   [off-path]
advisory.py     optional risk summaries (hosted or local model), cached  [off-path]
```
