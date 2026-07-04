"""T6 durability modes: the in-memory ledger (path=None), the buffered default, and
durable-fsync all share the same tamper-evident hash chain and anchoring."""

from verdictplane.provenance import GENESIS, Ledger


def test_memory_ledger_append_head_entries_verify():
    lg = Ledger(None)
    assert lg.head() == GENESIS
    h1 = lg.append({"n": 1})
    h2 = lg.append({"n": 2})
    assert lg.head() == h2 and h1 != h2
    assert [e["record"]["n"] for e in lg.entries()] == [1, 2]
    assert lg.verify() == (True, None)


def test_memory_ledger_detects_tampering_at_exact_index():
    lg = Ledger(None)
    for i in range(5):
        lg.append({"n": i})
    lg._mem[2]["record"]["n"] = "forged"      # mutate the in-memory entry
    assert lg.verify() == (False, 2)


def test_memory_ledger_anchor_detects_truncation():
    lg = Ledger(None)
    for i in range(6):
        lg.append({"n": i})
    anchor = lg.checkpoint()
    del lg._mem[3:]                            # truncate below the anchor
    assert lg.verify() == (True, None)         # a valid prefix still chain-verifies
    ok, reason = lg.verify_extends(anchor)
    assert not ok and "truncat" in reason.lower()


def test_memory_ledgers_are_isolated_per_instance():
    a, b = Ledger(None), Ledger(None)
    a.append({"n": 1})
    assert list(b.entries()) == [] and b.head() == GENESIS


def test_fsync_mode_writes_and_reloads(tmp_path):
    p = str(tmp_path / "dur.jsonl")
    lg = Ledger(p, fsync=True)
    for i in range(4):
        lg.append({"n": i})
    assert lg.verify() == (True, None)
    fresh = Ledger(p)                          # re-read from disk in a new instance
    assert [e["record"]["n"] for e in fresh.entries()] == [0, 1, 2, 3]
    assert fresh.verify() == (True, None)
