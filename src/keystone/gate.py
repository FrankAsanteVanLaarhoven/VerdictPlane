"""Blocking human approval gate. File-backed queue; fully inspectable.

A pending approval is one JSON file under <root>/pending/; resolving it moves
the file to <root>/resolved/ with the verdict. `await_approval()` polls the
filesystem — crude, deterministic, and works across processes (the CLI in P3
resolves what an interceptor in another process is blocked on).

Fail-safe: an unresolved approval past its timeout resolves to DENIED, never
to allow.

Enforcement-path module: stdlib only, deterministic, zero-egress, no model.
"""

import json
import os
import time


class Gate:
    def __init__(self, root: str = "artifacts/gate", *, poll_interval: float = 0.05):
        self.root = root
        self.poll_interval = poll_interval
        os.makedirs(os.path.join(root, "pending"), exist_ok=True)
        os.makedirs(os.path.join(root, "resolved"), exist_ok=True)

    def _pending_path(self, token: str) -> str:
        return os.path.join(self.root, "pending", f"{token}.json")

    def _resolved_path(self, token: str) -> str:
        return os.path.join(self.root, "resolved", f"{token}.json")

    @staticmethod
    def _write_json(path: str, entry: dict) -> None:
        """Atomic write: a concurrent reader sees the old state or the new
        state, never a truncated file (os.replace is atomic on POSIX)."""
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump(entry, f)
        os.replace(tmp, path)

    def submit(self, token: str, action: dict, advisory: str | None = None) -> None:
        entry = {
            "token": token,
            "action": action,
            "advisory": advisory,
            "submitted_ts": time.time_ns(),
        }
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

    def resolve(self, token: str, approved: bool, by: str = "unknown") -> dict:
        pending = self._pending_path(token)
        if not os.path.exists(pending):
            raise KeyError(f"no pending approval for token {token}")
        with open(pending) as f:
            entry = json.load(f)
        entry.update(
            approved=bool(approved), resolved_by=by, resolved_ts=time.time_ns()
        )
        self._write_json(self._resolved_path(token), entry)
        os.remove(pending)
        return entry

    def approve(self, token: str, by: str = "unknown") -> dict:
        return self.resolve(token, True, by)

    def deny(self, token: str, by: str = "unknown") -> dict:
        return self.resolve(token, False, by)

    def await_approval(
        self, token: str, action: dict, *, timeout: float | None = None
    ) -> bool:
        """Submit and BLOCK until a human resolves. Timeout -> denied (fail-safe)."""
        self.submit(token, action)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            resolution = self.resolution(token)
            if resolution is not None:
                return bool(resolution.get("approved"))
            if deadline is not None and time.monotonic() >= deadline:
                try:
                    self.resolve(token, False, by="timeout")
                except KeyError:
                    # raced with a human resolution; honor their verdict
                    resolution = self.resolution(token)
                    if resolution is not None:
                        return bool(resolution.get("approved"))
                return False
            time.sleep(self.poll_interval)
