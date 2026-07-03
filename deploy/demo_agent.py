"""Demo governed session for the sidecar deployment.

Runs inside a network-less container (network_mode: "none") and exercises the
full enforcement surface: an allowed read executes immediately, a gated write
blocks until a human resolves it from the reviewer container (or times out to
a safe deny). Exits 0 only if every path behaved and the chain verifies.
"""

import os
import sys

from verdictplane import ApprovalDenied, Gate, Ledger, PolicyDenied, govern

POLICY = {
    "default": "require_human",
    "rules": [
        {"match": {"effect": "read"}, "decision": "allow"},
        {"match": {"agent": "untrusted", "effect": "write"}, "decision": "deny"},
    ],
}

TIMEOUT = float(os.environ.get("VERDICTPLANE_DEMO_TIMEOUT", "60"))


def main() -> int:
    ledger = Ledger(os.environ.get("VERDICTPLANE_LEDGER", "/data/ledger.jsonl"))
    gate = Gate(os.environ.get("VERDICTPLANE_GATE", "/data/gate"))
    env = dict(policy=POLICY, ledger=ledger, gate=gate)

    print("agent: read (policy allow) ->", end=" ")
    govern({"tool": "db.read", "effect": "read", "agent": "demo"}, lambda: None, **env)
    print("executed")

    print("agent: write by untrusted (policy deny) ->", end=" ")
    try:
        govern({"tool": "db.write", "effect": "write", "agent": "untrusted"},
               lambda: None, **env)
        print("UNEXPECTED EXECUTION")
        return 1
    except PolicyDenied:
        print("blocked")

    print(f"agent: write (require_human) -> BLOCKED, waiting up to {TIMEOUT:.0f}s "
          "for `docker compose run reviewer approve <token>` ...")
    try:
        govern({"tool": "db.write", "effect": "write", "agent": "demo",
                "args": {"table": "users"}}, lambda: None, gate_timeout=TIMEOUT, **env)
        print("agent: write approved by a human -> executed")
    except ApprovalDenied:
        print("agent: not approved in time -> denied safely (fail-safe)")

    ok, bad = ledger.verify()
    print(f"agent: ledger verify -> {'ok' if ok else f'TAMPERED at {bad}'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
