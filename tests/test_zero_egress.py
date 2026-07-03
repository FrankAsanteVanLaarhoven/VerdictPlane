"""P6 acceptance: enforcement makes NO network calls.

Two independent proofs, layered on the static AST guard from P0:
1. Socket kill-switch — every socket constructor in this process is replaced
   with one that raises; the full enforcement surface (policy, govern on all
   three paths, gate resolution, workloads, ledger verify) must run untouched.
2. Network namespace — the same battery runs in a fresh netns (`unshare -rn`)
   with no interfaces at all: the kernel guarantees nothing could have left.
"""

import os
import shutil
import socket
import subprocess
import sys
import textwrap
import threading
import time

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

BATTERY = textwrap.dedent("""
    import threading, time
    from verdictplane.gate import Gate
    from verdictplane.interceptor import ApprovalDenied, PolicyDenied, govern
    from verdictplane.policy import load_policy
    from verdictplane.provenance import Ledger
    from workloads.driftguard_promote import governed_promote
    from workloads.sentinel_action import record_proposal

    def run_battery(base):
        policy = {"default": "require_human", "rules": [
            {"match": {"effect": "read"}, "decision": "allow"},
            {"match": {"agent": "untrusted", "effect": "write"}, "decision": "deny"},
        ]}
        wl = load_policy("policies/workloads.yaml")
        ledger = Ledger(base + "/ledger.jsonl")
        gate = Gate(base + "/gate", poll_interval=0.01)
        env = dict(policy=policy, ledger=ledger, gate=gate)

        govern({"tool": "db.read", "effect": "read", "agent": "a"}, lambda: None, **env)
        try:
            govern({"tool": "db.write", "effect": "write", "agent": "untrusted"},
                   lambda: None, **env)
            raise AssertionError("deny path executed")
        except PolicyDenied:
            pass

        def approve():
            while not gate.list_pending():
                time.sleep(0.01)
            gate.approve(gate.list_pending()[0]["token"], by="netns-test")
        t = threading.Thread(target=approve); t.start()
        govern({"tool": "email.send", "effect": "write", "agent": "a"}, lambda: None, **env)
        t.join()

        try:
            govern({"tool": "email.send", "effect": "write", "agent": "a"},
                   lambda: None, gate_timeout=0.05, **env)
            raise AssertionError("timeout path executed")
        except ApprovalDenied:
            pass

        gp = {"passed": True, "candidate_macro_f1": 0.9, "baseline_macro_f1": 0.8, "margin": 0.02}
        governed_promote("7", gp, lambda v: None, stage="Staging",
                         policy=wl, ledger=ledger, gate=gate)
        record_proposal({"detected": True, "localized": "svc", "detect_t": 1},
                        "INCIDENT REPORT", policy=wl, ledger=ledger, gate=gate)

        assert ledger.verify() == (True, None)
        outcomes = [e["record"]["outcome"] for e in ledger.entries()]
        assert outcomes.count("executed") == 4
        return "BATTERY_OK"
""")


def test_enforcement_runs_with_sockets_disabled(monkeypatch, tmp_path):
    """Kill-switch: any socket creation during enforcement raises instantly."""

    def no_network(*args, **kwargs):
        raise AssertionError("network attempted during enforcement")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)

    namespace = {}
    exec(compile(BATTERY, "<battery>", "exec"), namespace)  # noqa: S102 (test-local code)
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        assert namespace["run_battery"](str(tmp_path)) == "BATTERY_OK"
    finally:
        os.chdir(cwd)


NETNS_SCRIPT = BATTERY + textwrap.dedent("""
    import socket, sys, tempfile
    # prove we really are in an empty netns: no interfaces beyond (down) loopback,
    # and any outbound attempt fails at the kernel.
    try:
        s = socket.create_connection(("1.1.1.1", 443), timeout=0.5)
        s.close()
        sys.exit("netns is NOT isolated: outbound connect succeeded")
    except OSError:
        pass
    print(run_battery(tempfile.mkdtemp()))
""")


def test_enforcement_runs_in_empty_network_namespace(tmp_path):
    """Blueprint's netns test: kernel-level isolation, zero interfaces."""
    unshare = shutil.which("unshare")
    if unshare is None:
        pytest.skip("unshare not available")
    probe = subprocess.run([unshare, "-rn", "true"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"unprivileged netns unavailable: {probe.stderr.decode().strip()}")

    src = os.path.abspath(os.path.join(ROOT, "src"))
    env = {**os.environ, "PYTHONPATH": f"{src}:{os.path.abspath(ROOT)}",
           "VERDICTPLANE_ADVISORY": "off"}
    result = subprocess.run(
        [unshare, "-rn", sys.executable, "-c", NETNS_SCRIPT],
        capture_output=True, text=True, env=env, cwd=ROOT, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "BATTERY_OK" in result.stdout
