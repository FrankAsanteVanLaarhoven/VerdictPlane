"""Tamper-evidence conformance: every mutation of history is detected at the exact index."""

import json
import random

import pytest

from verdictplane.provenance import GENESIS, Ledger, _entry_hash

N = 100  # entries per test ledger


@pytest.fixture()
def ledger(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    for i in range(N):
        led.append({"action": {"tool": f"tool.{i}", "effect": "write"}, "outcome": "executed", "n": i})
    return led


def _lines(path):
    with open(path) as f:
        return f.read().splitlines()


def _write(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def test_empty_ledger_verifies(tmp_path):
    led = Ledger(str(tmp_path / "none.jsonl"))
    assert led.head() == GENESIS
    assert led.verify() == (True, None)


def test_intact_chain_verifies(ledger):
    assert ledger.verify() == (True, None)


def test_head_survives_reload(ledger):
    fresh = Ledger(ledger.path)
    assert fresh.head() == ledger.head() != GENESIS


def test_append_returns_head_hash(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    h = led.append({"k": "v"})
    assert h == led.head()
    assert led.verify() == (True, None)


# ---- mutation battery: each corruption type, random line, many seeds ----

def _mutate_record(e):
    e["record"]["n"] = "tampered"
    return e


def _mutate_ts(e):
    e["ts"] += 1
    return e


def _mutate_prev(e):
    e["prev"] = "f" * 64
    return e


def _mutate_hash(e):
    e["hash"] = "e" * 64
    return e


MUTATIONS = [_mutate_record, _mutate_ts, _mutate_prev, _mutate_hash]


@pytest.mark.parametrize("seed", range(12))
def test_random_line_mutation_detected_at_exact_index(ledger, seed):
    rng = random.Random(seed)
    lines = _lines(ledger.path)
    i = rng.randrange(N)
    mutate = rng.choice(MUTATIONS)
    lines[i] = json.dumps(mutate(json.loads(lines[i])), sort_keys=True)
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, i)


@pytest.mark.parametrize("seed", range(6))
def test_hash_fixed_mutation_detected_downstream(ledger, seed):
    """Attacker mutates a line AND recomputes its hash: the break moves to i+1."""
    rng = random.Random(seed)
    lines = _lines(ledger.path)
    i = rng.randrange(N - 1)  # not the last line (tail rewrite needs an anchored head)
    e = json.loads(lines[i])
    e["record"]["n"] = "tampered"
    body = {"ts": e["ts"], "prev": e["prev"], "record": e["record"]}
    e["hash"] = _entry_hash(e["prev"], body)
    lines[i] = json.dumps(e, sort_keys=True)
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, i + 1)


@pytest.mark.parametrize("seed", range(6))
def test_deleted_middle_line_detected(ledger, seed):
    i = random.Random(seed).randrange(N - 1)
    lines = _lines(ledger.path)
    del lines[i]
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, i)


@pytest.mark.parametrize("seed", range(6))
def test_inserted_forged_line_detected(ledger, seed):
    i = random.Random(seed).randrange(N)
    lines = _lines(ledger.path)
    forged = {"ts": 1, "prev": "d" * 64, "record": {"forged": True}, "hash": "d" * 64}
    lines.insert(i, json.dumps(forged, sort_keys=True))
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, i)


@pytest.mark.parametrize("seed", range(6))
def test_reordered_lines_detected(ledger, seed):
    i = random.Random(seed).randrange(N - 1)
    lines = _lines(ledger.path)
    lines[i], lines[i + 1] = lines[i + 1], lines[i]
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, i)


def test_garbage_line_detected(ledger):
    lines = _lines(ledger.path)
    lines[42] = "not json at all"
    _write(ledger.path, lines)
    assert Ledger(ledger.path).verify() == (False, 42)


def test_tail_truncation_detected_via_anchored_head(ledger):
    """Chain-only verify can't see a deleted tail; an anchored head can."""
    anchored = ledger.head()
    lines = _lines(ledger.path)
    _write(ledger.path, lines[:-3])
    truncated = Ledger(ledger.path)
    assert truncated.verify() == (True, None)  # documented limitation of chain-only check
    assert truncated.head() != anchored  # anchor comparison catches it
