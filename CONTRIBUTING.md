# Contributing to Keystone

## Setup

```bash
make setup     # venv + editable install
make test      # 180 tests; must stay green
make bench     # measured targets; exits nonzero on any regression
make evidence  # regenerates docs/EVIDENCE.md from live runs
```

## Invariants (non-negotiable)

These define the product. PRs that weaken them will be declined regardless of
what they gain elsewhere:

1. **Deterministic enforcement.** The decision path (`policy.py`,
   `interceptor.py`, `provenance.py`, `gate.py`, `mcp.py`, `types.py`) calls
   no model and makes no network I/O. The AST allowlist in
   `tests/test_enforcement_imports.py` enforces this — extend the allowlist
   only for stdlib modules that cannot open a connection.
2. **Zero egress.** `tests/test_zero_egress.py` must pass: the full
   enforcement battery under a socket kill-switch and inside an empty network
   namespace.
3. **Provenance by default, append-only.** No governed side effect without a
   prior ledger record; never rewrite history; `verify()` stays part of CI.
4. **Safe defaults.** Unmatched actions → `require_human`. Gate timeout →
   deny. Advisory failure → `None`, never a decision.
5. **Measured claims.** Performance statements come from `make bench` output,
   not prose. If your change touches the hot path, include before/after
   numbers.

## Working style

- Keep the hot path stdlib-light and dependency-free; heavy integrations
  belong in `workloads/` adapters or off-path modules.
- Every behavioral claim needs a test; every acceptance-level claim should be
  reproducible via `make evidence`.
- `artifacts/` is generated output — never commit it.

## License

MIT. By contributing you agree your contributions are MIT-licensed.
