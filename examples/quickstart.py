"""Govern your first tool call. Run me, then approve me from another terminal.

    PYTHONPATH=. .venv/bin/python examples/quickstart.py     # terminal 1
    .venv/bin/verdictplane pending                               # terminal 2
    .venv/bin/verdictplane approve <token-prefix>
"""

from verdictplane import Gate, Ledger, governed

policy = {
    "default": "require_human",  # anything unmatched needs a human — safe by default
    "rules": [
        {"match": {"effect": "read"}, "decision": "allow"},
    ],
}
ledger = Ledger("artifacts/ledger.jsonl")   # tamper-evident provenance
gate = Gate("artifacts/gate")               # file-backed human approval queue


@governed(effect="write", tool="email.send", policy=policy, ledger=ledger, gate=gate)
def send_email(to, subject):
    print(f"    >> email {subject!r} sent to {to}")
    return "sent"


@governed(effect="read", tool="crm.lookup", policy=policy, ledger=ledger, gate=gate)
def lookup_customer(name):
    return {"name": name, "tier": "enterprise"}


print("read  (policy: allow)         ->", lookup_customer("ACME"))
print("write (policy: require_human) -> BLOCKED until you approve it:")
print("    .venv/bin/verdictplane pending")
print("    .venv/bin/verdictplane approve <token-prefix>")
send_email("cfo@example.com", "Q3 invoice")
ok, _ = ledger.verify()
print(f"hash-chained ledger verifies: {ok}   (inspect: .venv/bin/verdictplane log)")
