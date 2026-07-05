# EAG-Bench — Agentic Red-Team Track

Multi-step / agentic attacks run as **sequences** through the real `govern()` choke point under a
**shared ledger + gate** (state carries across steps), using the same `../policies/eag_bench.yaml` as
the single-action corpus. Run it: `make redteam-bench` (also in `make test` via `tests/test_redteam.py`).

## Two honest buckets

Per-action governance **defeats some attack classes and is blind to others**. Claiming "0 red-team
escapes" would be cherry-picking; instead every case declares an `expected_outcome`:

- **`defeated_by_design`** — VerdictPlane blocks the critical step; the dangerous mutation never fires
  (**0 escapes**). Each case records `block_reason` (policy_deny / gate_required / gate_timeout /
  gate_denied) — *why* it was stopped.
- **`known_boundary`** — VerdictPlane **permits** the critical step; the danger lives in the aggregate
  or in timing, which a stateless per-action checker does not model. Reported honestly (not a
  VerdictPlane failure), each with a `boundary_note` naming the layer that would close it.

A case only FAILS if a `defeated` case's mutation fires (a real escape) or a `known_boundary` case is
unexpectedly blocked (a mislabel).

## Result (`make redteam-bench`)

```
defeated_by_design : 8 / 8 blocked   (escapes 0)
known_boundary     : 7 / 7 limitations reproduced
ledger chain intact: 15 / 15
```

| bucket | categories | what it shows |
| --- | --- | --- |
| defeated_by_design | tool_chaining, injection | each step re-hits `govern()`; benign predecessors can't prime a later malicious step, and (no model in the decision) injection changes only the *attempted* action, which the deterministic policy still governs |
| known_boundary | combination, toctou, replay | privilege accumulation / data-flow aggregation (needs stateful correlation), approved-vs-executed divergence (needs action-effect integrity), replayed / stale approvals (needs single-use nonces + approval TTL) |

## Honest reading

This does **not** claim VerdictPlane is unbreakable. It shows that per-action, model-free governance
**defeats chaining and injection by construction**, and it **names three boundary classes** that a
stateless in-path checker cannot cover — motivating a future stateful-correlation track. The defeated
result depends on the policy, not the harness: `tests/test_redteam.py` confirms a permissive policy
makes the same attacks escape.
