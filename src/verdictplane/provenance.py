"""Tamper-evident, append-only provenance ledger.

Hash-chained JSONL: every entry commits to the previous entry's hash, so any
mutation, insertion, deletion, or reordering of recorded history breaks the
chain at a detectable index. `verify()` walks the chain and reports the first
bad line.

Threat model: detects tampering with recorded history. Truncation of the tail
is detected by comparing `head()` against an externally anchored head hash
(see tests); preventing privileged deletion of the whole file is out of scope
for the file-backed ledger (P6+ can anchor heads externally / Merkle-ize).

Enforcement-path module: stdlib only, deterministic, zero-egress, no model.
"""

import hashlib
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
