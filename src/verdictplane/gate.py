"""Blocking human approval gate. File-backed queue; fully inspectable.

A pending approval is one JSON file under <root>/pending/; each reviewer's vote
is one atomic file under <root>/votes/<token>/<reviewer>.json (one vote per
identity, so votes never race). An approval finalizes to <root>/resolved/ once
distinct approvals reach the required quorum (default 1); a single deny vetoes
immediately (fail toward not executing). `await_approval()` polls the filesystem
— crude, deterministic, cross-process (the CLI resolves what an interceptor in
another process is blocked on).

Fail-safe: an unresolved approval past its timeout resolves to DENIED, never to
allow; absent a quorum of approvals, nothing executes.

Enforcement-path module: stdlib only, deterministic, zero-egress, no model.
"""

import json
import os
import time


class Gate:
    def __init__(self, root: str = "artifacts/gate", *, poll_interval: float = 0.05,
                 quorum: int = 1):
        self.root = root
        self.poll_interval = poll_interval
        self.quorum = max(1, int(quorum))  # default approvals required; per-submit overridable
        os.makedirs(os.path.join(root, "pending"), exist_ok=True)
        os.makedirs(os.path.join(root, "resolved"), exist_ok=True)

    def _pending_path(self, token: str) -> str:
        return os.path.join(self.root, "pending", f"{token}.json")

    def _resolved_path(self, token: str) -> str:
        return os.path.join(self.root, "resolved", f"{token}.json")

    def _votes_dir(self, token: str) -> str:
        return os.path.join(self.root, "votes", token)

    @staticmethod
    def _write_json(path: str, entry: dict) -> None:
        """Atomic write: a concurrent reader sees the old state or the new
        state, never a truncated file (os.replace is atomic on POSIX)."""
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump(entry, f)
        os.replace(tmp, path)

    def submit(self, token: str, action: dict, advisory: str | None = None,
               *, quorum: int | None = None) -> None:
        entry = {
            "token": token,
            "action": action,
            "advisory": advisory,
            "quorum": self.quorum if quorum is None else max(1, int(quorum)),
            "submitted_ts": time.time_ns(),
        }
        os.makedirs(self._votes_dir(token), exist_ok=True)
        self._write_json(self._pending_path(token), entry)

    def list_pending(self) -> list[dict]:
        pending_dir = os.path.join(self.root, "pending")
        out = []
        for name in sorted(os.listdir(pending_dir)):
            try:
                with open(os.path.join(pending_dir, name)) as f:
                    out.append(json.load(f))
            except (OSError, json.JSONDecodeError):
                continue  # resolved concurrently / partial write; skip
        return out

    def resolution(self, token: str) -> dict | None:
        try:
            with open(self._resolved_path(token)) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None  # absent or in-flight; caller polls again

    def _tally(self, token: str) -> tuple[dict, dict]:
        """Read all recorded votes as ({approver: ts}, {denier: ts}); one per identity."""
        approvals, denials = {}, {}
        vdir = self._votes_dir(token)
        if os.path.isdir(vdir):
            for name in sorted(os.listdir(vdir)):
                try:
                    with open(os.path.join(vdir, name)) as f:
                        v = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue  # partial write; skip
                (approvals if v.get("approved") else denials)[v.get("by")] = v.get("ts")
        return approvals, denials

    def vote(self, token: str, approved: bool, by: str = "unknown") -> dict:
        """Record one reviewer's vote (one per identity, atomic, cross-process).

        Finalizes to APPROVED when distinct approvals reach the required quorum, or
        to DENIED the moment any reviewer denies (a deny is a veto — fail toward not
        executing). Until then the action stays pending and does not run. Idempotent
        once resolved; first writer wins on the terminal verdict.
        """
        existing = self.resolution(token)
        if existing is not None:
            return existing
        pending = self._pending_path(token)
        if not os.path.exists(pending):
            raise KeyError(f"no pending approval for token {token}")
        with open(pending) as f:
            entry = json.load(f)
        os.makedirs(self._votes_dir(token), exist_ok=True)
        self._write_json(os.path.join(self._votes_dir(token), f"{by}.json"),
                         {"by": by, "approved": bool(approved), "ts": time.time_ns()})
        approvals, denials = self._tally(token)
        quorum = int(entry.get("quorum", 1))
        if denials:
            return self._finalize(token, entry, approved=False, by=by,
                                  approvals=approvals, denials=denials)
        if len(approvals) >= quorum:
            return self._finalize(token, entry, approved=True, by=by,
                                  approvals=approvals, denials=denials)
        return {**entry, "approved": None,
                "approved_by": sorted(approvals), "denied_by": sorted(denials),
                "remaining": quorum - len(approvals)}

    def _finalize(self, token: str, entry: dict, *, approved: bool, by: str,
                  approvals: dict, denials: dict) -> dict:
        existing = self.resolution(token)
        if existing is not None:
            return existing  # first writer wins; votes are idempotent
        resolved = {**entry, "approved": bool(approved), "resolved_by": by,
                    "approved_by": sorted(approvals), "denied_by": sorted(denials),
                    "resolved_ts": time.time_ns()}
        self._write_json(self._resolved_path(token), resolved)
        try:
            os.remove(self._pending_path(token))
        except OSError:
            pass
        return resolved

    def resolve(self, token: str, approved: bool, by: str = "unknown") -> dict:
        """Backward-compatible single-call resolve — an alias for one `vote`."""
        return self.vote(token, approved, by)

    def approve(self, token: str, by: str = "unknown") -> dict:
        return self.vote(token, True, by)

    def deny(self, token: str, by: str = "unknown") -> dict:
        return self.vote(token, False, by)

    def await_approval(
        self, token: str, action: dict, *, timeout: float | None = None,
        quorum: int | None = None,
    ) -> bool:
        """Submit and BLOCK until resolved. Needs `quorum` approvals (default 1); any
        deny vetoes; timeout -> denied (fail-safe)."""
        self.submit(token, action, quorum=quorum)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            resolution = self.resolution(token)
            if resolution is not None:
                return bool(resolution.get("approved"))
            if deadline is not None and time.monotonic() >= deadline:
                try:
                    self.vote(token, False, by="timeout")  # veto unless already resolved
                except KeyError:
                    pass
                resolution = self.resolution(token)
                return bool(resolution.get("approved")) if resolution else False
            time.sleep(self.poll_interval)
