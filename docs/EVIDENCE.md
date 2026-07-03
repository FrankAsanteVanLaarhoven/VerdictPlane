# Keystone — Evidence Pack (P0–P4)

Assembled from live runs by `make evidence` (scripts/build_evidence.py).
Nothing below is hand-written output.

- **Commit:** `039bd9e81861849a2c599e46e196d3e7ab52f8c7 (working tree DIRTY at capture time)`
- **Repo:** https://github.com/FrankAsanteVanLaarhoven/Keystone-AIOPs
- **Reproduce:** `make setup && make test && make evidence`

## Evidence Matrix

| Claim | Evidence | Result |
| --- | --- | --- |
| Enforcement path is deterministic (no model/network import) | E2 — static AST allowlist test output | 0 violations |
| Advisory cannot affect decisions | E2 — `test_enforcement_never_imports_advisory_or_cli` per module | 0 imports |
| Human approval blocks execution | E4 — before/after transcript: side effect absent until CLI approve; deny/timeout leave it absent | 100% gated |
| Failed baseline gate can never ship | E4 case C — deterministic `PolicyDenied`, no approval requested | fail-closed |
| Ledger is tamper-evident | E3 battery + E6 live forgery pinpointed at exact line | 100% detected |
| Provenance completeness | E5 — one terminal record per governed call, chain verifies clean | 0 gaps |
| P4 workloads governed end-to-end | E1 + E4/E5 — DriftGuard promote + Sentinel rollback through the gate | pass |


## E1 — Full test suite

```
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 2.53s
```

Recent history:

```
039bd9e P4 governed workloads: DriftGuard promotion + Sentinel rollback, with audit evidence pack
5067030 P3 reviewer CLI + config-switched advisory (Fable 5 API | local Ollama | off)
368755e P2 MCP interceptor: govern agent tool-calls at the dispatch boundary
1d944b9 P1 interceptor + human gate: in-path enforcement with provenance by default
84ad810 P0 trust core: hash-chained provenance ledger + deterministic policy engine
```


## E2 — Enforcement-path import guard (static, per module)

```
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[__init__.py] PASSED [  4%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[gate.py] PASSED [  9%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[interceptor.py] PASSED [ 13%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[mcp.py] PASSED [ 18%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[policy.py] PASSED [ 22%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[provenance.py] PASSED [ 27%]
tests/test_enforcement_imports.py::test_enforcement_imports_allowlisted[types.py] PASSED [ 31%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[__init__.py] PASSED [ 36%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[gate.py] PASSED [ 40%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[interceptor.py] PASSED [ 45%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[mcp.py] PASSED [ 50%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[policy.py] PASSED [ 54%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[provenance.py] PASSED [ 59%]
tests/test_enforcement_imports.py::test_no_network_or_model_clients[types.py] PASSED [ 63%]
tests/test_enforcement_imports.py::test_enforcement_set_is_not_empty PASSED [ 68%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[__init__.py] PASSED [ 72%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[gate.py] PASSED [ 77%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[interceptor.py] PASSED [ 81%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[mcp.py] PASSED [ 86%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[policy.py] PASSED [ 90%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[provenance.py] PASSED [ 95%]
tests/test_enforcement_imports.py::test_enforcement_never_imports_advisory_or_cli[types.py] PASSED [100%]
============================== 22 passed in 0.02s ==============================
```


## E3 — Tamper-detection battery (exact-index localization)

```
tests/test_provenance.py::test_empty_ledger_verifies PASSED              [  2%]
tests/test_provenance.py::test_intact_chain_verifies PASSED              [  4%]
tests/test_provenance.py::test_head_survives_reload PASSED               [  7%]
tests/test_provenance.py::test_append_returns_head_hash PASSED           [  9%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[0] PASSED [ 11%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[1] PASSED [ 14%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[2] PASSED [ 16%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[3] PASSED [ 19%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[4] PASSED [ 21%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[5] PASSED [ 23%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[6] PASSED [ 26%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[7] PASSED [ 28%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[8] PASSED [ 30%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[9] PASSED [ 33%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[10] PASSED [ 35%]
tests/test_provenance.py::test_random_line_mutation_detected_at_exact_index[11] PASSED [ 38%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[0] PASSED [ 40%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[1] PASSED [ 42%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[2] PASSED [ 45%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[3] PASSED [ 47%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[4] PASSED [ 50%]
tests/test_provenance.py::test_hash_fixed_mutation_detected_downstream[5] PASSED [ 52%]
tests/test_provenance.py::test_deleted_middle_line_detected[0] PASSED    [ 54%]
tests/test_provenance.py::test_deleted_middle_line_detected[1] PASSED    [ 57%]
tests/test_provenance.py::test_deleted_middle_line_detected[2] PASSED    [ 59%]
tests/test_provenance.py::test_deleted_middle_line_detected[3] PASSED    [ 61%]
tests/test_provenance.py::test_deleted_middle_line_detected[4] PASSED    [ 64%]
tests/test_provenance.py::test_deleted_middle_line_detected[5] PASSED    [ 66%]
tests/test_provenance.py::test_inserted_forged_line_detected[0] PASSED   [ 69%]
tests/test_provenance.py::test_inserted_forged_line_detected[1] PASSED   [ 71%]
tests/test_provenance.py::test_inserted_forged_line_detected[2] PASSED   [ 73%]
tests/test_provenance.py::test_inserted_forged_line_detected[3] PASSED   [ 76%]
tests/test_provenance.py::test_inserted_forged_line_detected[4] PASSED   [ 78%]
tests/test_provenance.py::test_inserted_forged_line_detected[5] PASSED   [ 80%]
tests/test_provenance.py::test_reordered_lines_detected[0] PASSED        [ 83%]
tests/test_provenance.py::test_reordered_lines_detected[1] PASSED        [ 85%]
tests/test_provenance.py::test_reordered_lines_detected[2] PASSED        [ 88%]
tests/test_provenance.py::test_reordered_lines_detected[3] PASSED        [ 90%]
tests/test_provenance.py::test_reordered_lines_detected[4] PASSED        [ 92%]
tests/test_provenance.py::test_reordered_lines_detected[5] PASSED        [ 95%]
tests/test_provenance.py::test_garbage_line_detected PASSED              [ 97%]
tests/test_provenance.py::test_tail_truncation_detected_via_anchored_head PASSED [100%]
============================== 42 passed in 0.13s ==============================
```


## E4 — Live gate demo: DriftGuard promote + Sentinel rollback (cross-process, via the reviewer CLI)

```
$ # governed_promote('7', gate_passed) is now BLOCKED in another process

$ test -f registry.json && echo exists || echo absent
absent   <- side effect has NOT run

$ keystone pending
b11a088e0c205045  model.promote  effect=promote  agent=driftguard  age=0s
  args: {"baseline": {"baseline_macro_f1": 0.85, "candidate_macro_f1": 0.91, "margin": 0.02, "passed": true, "reason": null}, "stage": "Production", "version": "7"}

$ keystone approve b11a088e0c20 --by frank
approved b11a088e0c205045 (model.promote) by frank

$ cat registry.json
{"production_alias": "7"}   <- side effect ran ONLY after approval

$ keystone deny 6ea0a7f0067b --by frank
denied 6ea0a7f0067b2674 (model.promote) by frank

$ cat registry.json
{"production_alias": "7"}   <- unchanged; caller got ApprovalDenied

# governed_promote('9', gate_FAILED) -> PolicyDenied: model.promote: denied by policy
# (deterministic policy deny; no approval was ever requested)

$ keystone approve 802b79b7823b --by frank   # Sentinel rollback
approved 802b79b7823b4d40 (incident.rollback) by frank

# rollback executed with incident payload: {'service': 'productcatalog', 'change': 'deploy v2.3.1', 'detect_t': 34}
```


## E5 — Resulting provenance ledger

`keystone log`:

```
b11a088e0c205045  pending          require_human  model.promote  agent=driftguard
607020f1175ba875  executed         require_human  model.promote  agent=driftguard
6ea0a7f0067b2674  pending          require_human  model.promote  agent=driftguard
3b4dd0f813486694  denied_by_human  require_human  model.promote  agent=driftguard
4ec40d4fca26c16c  blocked          deny           model.promote  agent=driftguard
991efc07c9a367b4  executed         allow          incident.propose  agent=sentinel
802b79b7823b4d40  pending          require_human  incident.rollback  agent=sentinel
52cadb71e31886fa  executed         require_human  incident.rollback  agent=sentinel
```

`keystone verify`:

```
ledger ok (8 entries, head=52cadb71e31886fa)
```

Raw hash-chained records (first 2 of 8):

```json
{"hash": "b11a088e0c2050457d12e53b19398b741c48de0959846f2c21c21952c135ad92", "prev": "0000000000000000000000000000000000000000000000000000000000000000", "record": {"action": {"agent": "driftguard", "args": {"baseline": {"baseline_macro_f1": 0.85, "candidate_macro_f1": 0.91, "margin": 0.02, "passed": true, "reason": null}, "stage": "Production", "version": "7"}, "context": {}, "effect": "promote", "tool": "model.promote"}, "decision": "require_human", "outcome": "pending", "rule": {"decision": "require_human", "match": {"args.baseline.passed": true, "args.stage": "Production", "tool": "model.promote"}}}, "ts": 1783038820037347931}
{"hash": "607020f1175ba87597433ebc732bb1569961e13abbff04ad1545034419beb4db", "prev": "b11a088e0c2050457d12e53b19398b741c48de0959846f2c21c21952c135ad92", "record": {"action": {"agent": "driftguard", "args": {"baseline": {"baseline_macro_f1": 0.85, "candidate_macro_f1": 0.91, "margin": 0.02, "passed": true, "reason": null}, "stage": "Production", "version": "7"}, "context": {}, "effect": "promote", "tool": "model.promote"}, "decision": "require_human", "outcome": "executed", "rule": {"decision": "require_human", "match": {"args.baseline.passed": true, "args.stage": "Production", "tool": "model.promote"}}, "token": "b11a088e0c2050457d12e53b19398b741c48de0959846f2c21c21952c135ad92"}, "ts": 1783038820199352256}
```


## E6 — Live forgery detection

```
$ keystone verify   # after forging line 3's outcome
LEDGER TAMPERED at line 3
exit code: 1
```


## Governing policy (policies/workloads.yaml)

```yaml
# Policy for the first two governed workloads (P4).
# First-match wins; anything unmatched falls to the safe default.

default: require_human

rules:
  # DriftGuard — fail-closed: a candidate that failed the baseline gate can
  # never ship, no matter who asks. Deterministic deny, no human needed.
  - match: { tool: model.promote, args.baseline.passed: false }
    decision: deny

  # Production promotion always needs a human, even with a passing gate.
  - match: { tool: model.promote, args.stage: Production, args.baseline.passed: true }
    decision: require_human

  # Staging promotions with a passing gate flow unattended (canary-style).
  - match: { tool: model.promote, args.stage: Staging, args.baseline.passed: true }
    decision: allow

  # Sentinel — recording an assistive proposal is safe and always audited.
  - match: { tool: incident.propose, effect: propose }
    decision: allow

  # Executing a proposed rollback is a real side effect: human required.
  - match: { tool: incident.rollback }
    decision: require_human
```

