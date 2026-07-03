"""verdictplane — reviewer CLI: list pending approvals, approve/deny, verify the
ledger, query provenance. Works across processes: an interceptor blocked in
another process resolves the moment you approve/deny here.

Advisory summaries are opt-in (`pending --advise`) and fail-safe; enforcement
never calls the advisory module at all.
"""

import argparse
import fnmatch
import json
import os
import sys
import time

from .gate import Gate
from .provenance import Ledger


def _resolve_token(gate: Gate, prefix: str) -> str:
    matches = [p["token"] for p in gate.list_pending() if p["token"].startswith(prefix)]
    if not matches:
        raise SystemExit(f"verdictplane: no pending approval matching {prefix!r}")
    if len(matches) > 1:
        raise SystemExit(f"verdictplane: token prefix {prefix!r} is ambiguous ({len(matches)} matches)")
    return matches[0]


def _cmd_pending(args, gate: Gate) -> int:
    pending = gate.list_pending()
    if not pending:
        print("no pending approvals")
        return 0
    advise = None
    if args.advise:
        from . import advisory  # lazy: reviewer-side only, never on the hot path
        advise = advisory.risk_summary
    for entry in pending:
        action = entry.get("action", {})
        age = (time.time_ns() - entry.get("submitted_ts", 0)) / 1e9
        quorum = entry.get("quorum", 1)
        qstr = f"  quorum={quorum}" if quorum > 1 else ""
        print(f"{entry['token'][:16]}  {action.get('tool', '?')}  "
              f"effect={action.get('effect', '?')}  agent={action.get('agent', '?')}  "
              f"age={age:.0f}s{qstr}")
        print(f"  args: {json.dumps(action.get('args', {}), sort_keys=True)}")
        if advise:
            summary = advise(action)
            if summary:
                print("  advisory:")
                for line in summary.splitlines():
                    print(f"    {line}")
            else:
                print("  advisory: (unavailable — decide from the action record)")
    return 0


def _cmd_resolve(args, gate: Gate, approved: bool) -> int:
    token = _resolve_token(gate, args.token)
    result = gate.resolve(token, approved, by=args.by)
    if result.get("approved") is None:  # quorum not yet reached — vote recorded, still pending
        got, need = len(result.get("approved_by", [])), result.get("quorum", 1)
        print(f"vote recorded by {args.by}: {token[:16]} "
              f"({got}/{need} approvals; awaiting {result.get('remaining', 0)} more)")
        return 0
    verdict = "approved" if result["approved"] else "denied"
    deciders = result.get("approved_by") if result["approved"] else result.get("denied_by")
    who = ", ".join(deciders or [args.by])
    print(f"{verdict} {token[:16]} ({result['action'].get('tool', '?')}) by {who}")
    return 0


def _cmd_verify(ledger: Ledger) -> int:
    ok, bad = ledger.verify()
    entries = sum(1 for _ in ledger.entries())
    if ok:
        print(f"ledger ok ({entries} entries, head={ledger.head()[:16]})")
        return 0
    print(f"LEDGER TAMPERED at line {bad}")
    return 1


def _cmd_log(args, ledger: Ledger) -> int:
    rows = []
    for entry in ledger.entries():
        record = entry.get("record", {})
        action = record.get("action", {})
        if args.tool and not fnmatch.fnmatchcase(str(action.get("tool", "")), args.tool):
            continue
        if args.outcome and record.get("outcome") != args.outcome:
            continue
        rows.append((entry, record, action))
    for entry, record, action in rows[-args.tail:]:
        print(f"{entry['hash'][:16]}  {record.get('outcome', '?'):<16} "
              f"{record.get('decision', '?'):<14} {action.get('tool', '?')}  "
              f"agent={action.get('agent', '?')}")
    return 0


def _anchor_key() -> bytes | None:
    """Optional HMAC key for signed anchors, from VERDICTPLANE_ANCHOR_KEY (hex)."""
    hexkey = os.environ.get("VERDICTPLANE_ANCHOR_KEY", "").strip()
    return bytes.fromhex(hexkey) if hexkey else None


def _cmd_anchor(args, ledger: Ledger) -> int:
    cp = ledger.checkpoint(key=_anchor_key())
    text = json.dumps(cp, sort_keys=True)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"anchored {cp['count']} entries -> {args.out} "
              f"(head {cp['head'][:16]}{', signed' if 'hmac' in cp else ''})")
    else:
        print(text)
    return 0


def _cmd_verify_anchor(args, ledger: Ledger) -> int:
    with open(args.anchor) as f:
        anchor = json.load(f)
    ok, reason = ledger.verify_extends(anchor, key=_anchor_key())
    print(f"{'OK' if ok else 'FAIL'}: {reason}")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="verdictplane", description=__doc__)
    parser.add_argument("--ledger", default=os.environ.get("VERDICTPLANE_LEDGER", "artifacts/ledger.jsonl"))
    parser.add_argument("--gate", default=os.environ.get("VERDICTPLANE_GATE", "artifacts/gate"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("pending", help="list pending approvals")
    p_pending.add_argument("--advise", action="store_true",
                           help="add model risk summaries (VERDICTPLANE_ADVISORY backend; fail-safe)")
    for name, help_text in (("approve", "approve a pending action"), ("deny", "deny a pending action")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("token", help="gate token or unique prefix")
        p.add_argument("--by", default=os.environ.get("USER", "unknown"))
    sub.add_parser("verify", help="verify the ledger hash chain")
    sub.add_parser("head", help="print the ledger head hash (anchor it externally)")
    p_anchor = sub.add_parser("anchor",
                              help="write a (optionally signed) checkpoint to anchor externally")
    p_anchor.add_argument("--out", default=None, help="file to write (default: stdout)")
    p_va = sub.add_parser("verify-anchor",
                          help="verify the ledger is an append-only extension of an anchor")
    p_va.add_argument("anchor", help="path to a checkpoint file written by `anchor`")
    p_log = sub.add_parser("log", help="query provenance records")
    p_log.add_argument("--tool", default=None, help="glob filter on tool name")
    p_log.add_argument("--outcome", default=None,
                       help="filter: executed|blocked|denied_by_human|failed|pending")
    p_log.add_argument("--tail", type=int, default=20)

    args = parser.parse_args(argv)
    ledger = Ledger(args.ledger)
    gate = Gate(args.gate)

    if args.command == "pending":
        return _cmd_pending(args, gate)
    if args.command == "approve":
        return _cmd_resolve(args, gate, approved=True)
    if args.command == "deny":
        return _cmd_resolve(args, gate, approved=False)
    if args.command == "verify":
        return _cmd_verify(ledger)
    if args.command == "head":
        print(ledger.head())
        return 0
    if args.command == "anchor":
        return _cmd_anchor(args, ledger)
    if args.command == "verify-anchor":
        return _cmd_verify_anchor(args, ledger)
    if args.command == "log":
        return _cmd_log(args, ledger)
    return 2  # unreachable: argparse enforces the command set


if __name__ == "__main__":
    sys.exit(main())
