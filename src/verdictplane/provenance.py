"""Tamper-evident, append-only provenance ledger.

Hash-chained JSONL: every entry commits to the previous entry's hash, so any
mutation, insertion, deletion, or reordering of recorded history breaks the
chain at a detectable index. `verify()` walks the chain and reports the first
bad line.

Threat model: detects tampering with recorded history. Tail truncation and
rollback are detected by `verify_extends()` against an externally anchored,
optionally HMAC-signed `checkpoint()` (head + count + Merkle root) — mutations a
self-contained chain walk cannot see, because a truncated-but-valid prefix still
verifies. Preventing privileged deletion of the whole file is out of scope for a
file-backed ledger.

Enforcement-path module: stdlib only, deterministic, zero-egress, no model.
"""

import hashlib
import hmac
import json
import os
import threading
import time

GENESIS = "0" * 64


def _entry_hash(prev: str, body: dict) -> str:
    """Hash of one entry body chained to the previous entry's hash."""
    return hashlib.sha256(
        (prev + json.dumps(body, sort_keys=True)).encode()
    ).hexdigest()


def merkle_root(leaf_hashes) -> str:
    """Merkle root over ordered leaf hashes (SHA-256, domain-separated nodes).

    Unpaired nodes are carried up unchanged rather than duplicated, avoiding the
    duplicate-last second-preimage weakness. Empty -> GENESIS. A compact,
    order-committing digest of the whole ledger for external anchoring.
    """
    level = list(leaf_hashes)
    if not level:
        return GENESIS
    while len(level) > 1:
        nxt = [hashlib.sha256(("node:" + level[i] + level[i + 1]).encode()).hexdigest()
               for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])  # carry the unpaired node up unchanged
        level = nxt
    return level[0]


def _canon(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True).encode()


class Ledger:
    """Append-only JSONL ledger with a SHA-256 hash chain.

    fsync=True trades append latency for crash durability; tamper evidence is
    unaffected either way (a lost tail is truncation, detectable via an
    anchored head, not silent rewrite).
    """

    def __init__(self, path: str = "artifacts/ledger.jsonl", *, fsync: bool = False):
        self.path = path
        self.fsync = fsync
        self._lock = threading.Lock()
        self._head: str | None = None  # cached; loaded lazily from disk

    def head(self) -> str:
        """Hash of the last entry (GENESIS for an empty ledger)."""
        if self._head is not None:
            return self._head
        if not os.path.exists(self.path):
            return GENESIS
        last = None
        with open(self.path) as f:
            for line in f:
                if line.strip():
                    last = line
        self._head = json.loads(last)["hash"] if last else GENESIS
        return self._head

    def append(self, record: dict) -> str:
        """Append one record; returns its hash (used as the gate token)."""
        with self._lock:
            prev = self.head()
            body = {"ts": time.time_ns(), "prev": prev, "record": record}
            h = _entry_hash(prev, body)
            d = os.path.dirname(self.path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(self.path, "a") as f:
                f.write(json.dumps({**body, "hash": h}, sort_keys=True) + "\n")
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())
            self._head = h
            return h

    def entries(self):
        """Yield all entries in order (parsed, unverified)."""
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def verify(self) -> tuple[bool, int | None]:
        """Walk the full chain. Returns (True, None) or (False, first_bad_index)."""
        prev = GENESIS
        if not os.path.exists(self.path):
            return True, None
        with open(self.path) as f:
            for i, line in enumerate(f):
                if not line.strip():
                    return False, i
                try:
                    e = json.loads(line)
                    body = {"ts": e["ts"], "prev": e["prev"], "record": e["record"]}
                    entry_prev, entry_hash = e["prev"], e["hash"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    return False, i
                if entry_prev != prev or entry_hash != _entry_hash(prev, body):
                    return False, i
                prev = entry_hash
        return True, None

    def entry_hashes(self) -> list[str]:
        """All entry hashes in order (the Merkle leaves)."""
        return [e["hash"] for e in self.entries()]

    def checkpoint(self, *, key: bytes | None = None) -> dict:
        """A verifiable snapshot of ledger state, for EXTERNAL anchoring.

        Anchoring a checkpoint out-of-band lets `verify_extends` later detect tail
        truncation *below this point* and rollback — which a self-contained chain
        walk cannot, because a truncated-but-valid prefix still verifies. Entries
        appended after a checkpoint are only covered by the next one, so anchor
        frequently. The optional HMAC gives keyed tamper-evidence to holders of the
        key (the key must live apart from the ledger writer) — this is integrity,
        not asymmetric non-repudiation (ed25519 signing is a roadmap item). The
        Merkle root is a forward commitment reserved for future inclusion proofs.
        """
        hashes = self.entry_hashes()
        cp = {
            "head": hashes[-1] if hashes else GENESIS,
            "count": len(hashes),
            "merkle_root": merkle_root(hashes),
            "ts": time.time_ns(),
        }
        if key is not None:
            cp["hmac"] = hmac.new(key, _canon(cp), hashlib.sha256).hexdigest()
        return cp

    def verify_extends(self, anchor: dict, *, key: bytes | None = None) -> tuple[bool, str]:
        """True iff the current ledger is an append-only extension of `anchor`.

        Detects truncation (fewer entries than anchored, or the anchored head no
        longer at its index) and rollback (history diverged at/under the anchor).
        Verifies the anchor's HMAC first when a key is supplied.
        """
        if key is not None:
            expected = anchor.get("hmac")
            unsigned = {k: v for k, v in anchor.items() if k != "hmac"}
            if not expected or not hmac.compare_digest(
                expected, hmac.new(key, _canon(unsigned), hashlib.sha256).hexdigest()
            ):
                return False, "anchor signature invalid"
        ok, bad = self.verify()
        if not ok:
            return False, f"chain broken at line {bad}"
        hashes = self.entry_hashes()
        anchored = anchor.get("count", 0)
        if len(hashes) < anchored:
            return False, f"truncated: {len(hashes)} entries < anchored {anchored}"
        if anchored == 0:
            return True, "extends genesis"
        if hashes[anchored - 1] != anchor.get("head"):
            return False, "rollback: anchored head not present at its index"
        return True, "append-only extension verified"
