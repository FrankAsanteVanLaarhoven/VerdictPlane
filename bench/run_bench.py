"""VerdictPlane benchmark harness (P5) -> artifacts/stats.json + docs/BENCHMARK.md.

Measures, with VERDICTPLANE_ADVISORY forced off (perf) and forced-broken (fail-safe):
  - enforcement overhead per governed call vs raw call: p50/p95/p99 for the
    allow, deny, and require_human (auto-resolved) paths
  - single-core allow-path throughput (governed actions/sec)
  - ledger append latency and full-chain verify() time
  - tamper detection rate at exact index (randomized trials)
  - provenance completeness (zero gaps) over a mixed workload
  - fail-safe: advisory backend configured but broken -> decisions unchanged
  - the real P4 workload wrappers under load

Statistical stability: latency/throughput measurements repeat over --runs
independent runs (fresh ledger each), reporting per-run values and spread.
"""

import argparse
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["VERDICTPLANE_ADVISORY"] = "off"  # perf + safety runs: advisory off

from verdictplane import advisory  # noqa: E402  (bench-only import; not enforcement)
from verdictplane.gate import Gate  # noqa: E402
from verdictplane.interceptor import ApprovalDenied, PolicyDenied, govern  # noqa: E402
from verdictplane.policy import evaluate, load_policy  # noqa: E402
from verdictplane.provenance import Ledger  # noqa: E402
from workloads.driftguard_promote import governed_promote  # noqa: E402
from workloads.sentinel_action import record_proposal  # noqa: E402

POLICY = {
    "default": "require_human",
    "rules": [
        {"match": {"effect": "read"}, "decision": "allow"},
        {"match": {"agent": "untrusted", "effect": "write"}, "decision": "deny"},
        {"match": {"tool": "email.send"}, "decision": "require_human"},
    ],
}
ALLOW_ACTION = {"tool": "db.read", "effect": "read", "args": {"table": "t"}, "agent": "bench"}
DENY_ACTION = {"tool": "db.write", "effect": "write", "args": {}, "agent": "untrusted"}
GATED_ACTION = {"tool": "email.send", "effect": "write", "args": {}, "agent": "bench"}
GATE_PASS = {"passed": True, "candidate_macro_f1": 0.91, "baseline_macro_f1": 0.85, "margin": 0.02}


class AutoGate(Gate):
    """Resolves instantly in-process: measures the full submit/resolve
    machinery on the require_human path without human latency."""

    def await_approval(self, token, action, *, timeout=None):
        self.submit(token, action)
        self.resolve(token, True, by="bench-auto")
        return True


def pcts(samples_ns):
    s = sorted(samples_ns)

    def p(q):
        return s[min(len(s) - 1, int(len(s) * q / 100))] / 1000.0  # -> µs

    return {"p50_us": round(p(50), 2), "p95_us": round(p(95), 2), "p99_us": round(p(99), 2)}


def time_calls(fn, n):
    samples = [0] * n
    for i in range(n):
        t0 = time.perf_counter_ns()
        fn()
        samples[i] = time.perf_counter_ns() - t0
    return samples


def fs_type(path):
    best, fstype = "", "unknown"
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and path.startswith(parts[1]) and len(parts[1]) > len(best):
                    best, fstype = parts[1], parts[2]
    except OSError:
        pass
    return fstype


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def one_run(workdir, n_allow, n_gated):
    """One independent latency/throughput run on a fresh ledger."""
    ledger = Ledger(os.path.join(workdir, "ledger.jsonl"))
    gate = AutoGate(os.path.join(workdir, "gate"), poll_interval=0.001)
    env = dict(policy=POLICY, ledger=ledger, gate=gate)

    raw = time_calls(lambda: None, n_allow)

    allow = time_calls(lambda: govern(dict(ALLOW_ACTION), lambda: None, **env), n_allow)

    def deny_once():
        try:
            govern(dict(DENY_ACTION), lambda: None, **env)
        except PolicyDenied:
            pass

    deny = time_calls(deny_once, n_allow // 4)

    gated = time_calls(lambda: govern(dict(GATED_ACTION), lambda: None, **env), n_gated)

    # throughput: steady-state wall-clock over the allow path, fresh ledger
    tp_ledger = Ledger(os.path.join(workdir, "tp.jsonl"))
    tp_env = dict(policy=POLICY, ledger=tp_ledger, gate=gate)
    for _ in range(500):  # warmup
        govern(dict(ALLOW_ACTION), lambda: None, **tp_env)
    t0 = time.perf_counter()
    for _ in range(n_allow):
        govern(dict(ALLOW_ACTION), lambda: None, **tp_env)
    tp = n_allow / (time.perf_counter() - t0)

    append = time_calls(lambda: ledger.append({"bench": "append"}), 2000)
    t0 = time.perf_counter()
    ok, bad = ledger.verify()
    verify_s = time.perf_counter() - t0
    assert ok and bad is None
    entries = sum(1 for _ in ledger.entries())

    return {
        "raw_call": pcts(raw),
        "allow_path": pcts(allow),
        "deny_path": pcts(deny),
        "require_human_autoresolved": pcts(gated),
        "throughput_allow_ops_per_sec": round(tp),
        "ledger_append": pcts(append),
        "verify": {"entries": entries, "seconds": round(verify_s, 4)},
    }


def tamper_trials(workdir, entries=1000, trials=200):
    base = Ledger(os.path.join(workdir, "tamper_base.jsonl"))
    for i in range(entries):
        base.append({"n": i})
    with open(base.path) as f:
        baseline_lines = f.read().splitlines()

    def mutate(e, kind):
        if kind == 0:
            e["record"]["n"] = "forged"
        elif kind == 1:
            e["ts"] += 1
        elif kind == 2:
            e["prev"] = "f" * 64
        else:
            e["hash"] = "e" * 64
        return e

    detected = 0
    path = os.path.join(workdir, "tamper_case.jsonl")
    for seed in range(trials):
        rng = random.Random(seed)
        i = rng.randrange(entries)
        lines = list(baseline_lines)
        lines[i] = json.dumps(mutate(json.loads(lines[i]), rng.randrange(4)), sort_keys=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        if Ledger(path).verify() == (False, i):
            detected += 1
    return {"trials": trials, "detected": detected, "rate": detected / trials}


def completeness(workdir):
    """Mixed workload incl. the real P4 wrappers: every call leaves exactly
    one terminal record and the chain verifies."""
    wl_policy = load_policy(os.path.join(ROOT, "policies", "workloads.yaml"))
    ledger = Ledger(os.path.join(workdir, "complete.jsonl"))
    auto = AutoGate(os.path.join(workdir, "cgate"), poll_interval=0.001)
    deny_gate = Gate(os.path.join(workdir, "dgate"), poll_interval=0.001)
    calls = executed = 0
    for i in range(200):
        calls += 1
        kind = i % 5
        if kind == 0:
            govern(dict(ALLOW_ACTION), lambda: None, policy=POLICY, ledger=ledger, gate=auto)
            executed += 1
        elif kind == 1:
            try:
                govern(dict(DENY_ACTION), lambda: None, policy=POLICY, ledger=ledger, gate=auto)
            except PolicyDenied:
                pass
        elif kind == 2:
            try:
                govern(dict(GATED_ACTION), lambda: None, policy=POLICY,
                       ledger=ledger, gate=deny_gate, gate_timeout=0.001)
            except ApprovalDenied:
                pass
        elif kind == 3:
            governed_promote(str(i), GATE_PASS, lambda v: None, stage="Staging",
                             policy=wl_policy, ledger=ledger, gate=auto)
            executed += 1
        else:
            record_proposal({"detected": True, "localized": "svc", "detect_t": i},
                            "INCIDENT REPORT", policy=wl_policy, ledger=ledger, gate=auto)
            executed += 1
    terminal = [e["record"]["outcome"] for e in ledger.entries()
                if e["record"]["outcome"] in {"executed", "blocked", "denied_by_human", "failed"}]
    ok, _ = ledger.verify()
    return {"calls": calls, "terminal_records": len(terminal),
            "executed": terminal.count("executed"), "expected_executed": executed,
            "gaps": calls - len(terminal), "chain_ok": ok}


def fail_safe(workdir):
    """Advisory configured but broken -> summary None; decisions unchanged."""
    cases = [(ALLOW_ACTION, "allow"), (DENY_ACTION, "deny"), (GATED_ACTION, "require_human"),
             ({"tool": "unknown.op", "effect": "write", "args": {}, "agent": "x"}, "require_human")]
    before = [evaluate(a, POLICY)[0] for a, _ in cases]

    os.environ["VERDICTPLANE_ADVISORY"] = "fable5"
    os.environ["ANTHROPIC_API_KEY"] = "bench-key-not-real"
    real_urlopen = advisory.urllib.request.urlopen

    def broken(*a, **k):
        raise OSError("advisory transport down (forced by bench)")

    advisory.urllib.request.urlopen = broken
    try:
        summary = advisory.risk_summary(dict(GATED_ACTION),
                                        cache_path=os.path.join(workdir, "acache.json"))
        after = [evaluate(a, POLICY)[0] for a, _ in cases]
    finally:
        advisory.urllib.request.urlopen = real_urlopen
        os.environ["VERDICTPLANE_ADVISORY"] = "off"
        os.environ.pop("ANTHROPIC_API_KEY", None)

    return {
        "advisory_forced_error": True,
        "summary_returned": summary,  # must be None
        "decisions_unchanged": before == after == [e for _, e in cases],
        "unknown_action_default": after[3],  # must be require_human
    }


def workloads_under_load(workdir, n):
    wl_policy = load_policy(os.path.join(ROOT, "policies", "workloads.yaml"))
    ledger = Ledger(os.path.join(workdir, "wl.jsonl"))
    auto = AutoGate(os.path.join(workdir, "wlgate"), poll_interval=0.001)
    env = dict(policy=wl_policy, ledger=ledger, gate=auto)

    staging = time_calls(lambda: governed_promote("7", GATE_PASS, lambda v: None,
                                                  stage="Staging", **env), n)
    production = time_calls(lambda: governed_promote("7", GATE_PASS, lambda v: None,
                                                     stage="Production", **env), max(200, n // 10))
    proposal = time_calls(lambda: record_proposal(
        {"detected": True, "localized": "svc", "detect_t": 1}, "INCIDENT REPORT", **env), n)

    t0 = time.perf_counter()
    for _ in range(n):
        governed_promote("7", GATE_PASS, lambda v: None, stage="Staging", **env)
    tp = n / (time.perf_counter() - t0)
    ok, _ = ledger.verify()
    return {
        "promote_staging_allow": pcts(staging),
        "promote_production_gated_autoresolved": pcts(production),
        "sentinel_proposal": pcts(proposal),
        "promote_staging_ops_per_sec": round(tp),
        "chain_ok_after_load": ok,
    }


def spread_pct(values):
    med = statistics.median(values)
    return round(100 * (max(values) - min(values)) / med, 1) if med else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--n", type=int, default=20000, help="allow-path calls per run")
    ap.add_argument("--n-gated", type=int, default=2000)
    ap.add_argument("--max-spread-pct", type=float,
                    default=float(os.environ.get("VERDICTPLANE_BENCH_MAX_SPREAD", "10")),
                    help="reproducibility target for allow-p99 spread across runs "
                         "(default 10; a dedicated-hardware claim)")
    ap.add_argument("--spread-report-only", action="store_true",
                    help="record the spread against the target but do not gate the "
                         "exit code on it (for shared CI runners, where run-to-run "
                         "spread measures the runner, not the system)")
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "stats.json"))
    args = ap.parse_args()

    top = tempfile.mkdtemp(prefix="verdictplane-bench-")
    try:
        runs = []
        for r in range(args.runs):
            d = os.path.join(top, f"run{r}")
            os.makedirs(d)
            runs.append(one_run(d, args.n, args.n_gated))
            print(f"run {r + 1}/{args.runs}: allow p99={runs[-1]['allow_path']['p99_us']}us "
                  f"throughput={runs[-1]['throughput_allow_ops_per_sec']}/s")

        allow_p99s = [r["allow_path"]["p99_us"] for r in runs]
        tps = [r["throughput_allow_ops_per_sec"] for r in runs]
        median_run = runs[allow_p99s.index(sorted(allow_p99s)[len(allow_p99s) // 2])]

        shared = os.path.join(top, "shared")
        os.makedirs(shared)
        tamper = tamper_trials(shared)
        complete = completeness(shared)
        safe = fail_safe(shared)
        wl = workloads_under_load(shared, 5000)

        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
        if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip():
            commit += " (working tree DIRTY at capture time)"
        stats = {
            "meta": {
                "commit": commit,
                "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu": cpu_model(),
                "ledger_filesystem": fs_type(top),
                "fsync": False,
                "advisory_env": "off (forced); enforcement never imports advisory regardless",
                "runs": args.runs,
                "allow_calls_per_run": args.n,
                "spread_target_pct": args.max_spread_pct,
                "spread_enforced": not args.spread_report_only,
            },
            "latency": {**median_run, "note": "median run shown; per-run below"},
            "stability": {
                "allow_p99_us_per_run": allow_p99s,
                "allow_p99_spread_pct": spread_pct(allow_p99s),
                "throughput_per_run": tps,
                "throughput_spread_pct": spread_pct(tps),
            },
            "tamper_detection": tamper,
            "provenance_completeness": complete,
            "fail_safe": safe,
            "workloads_under_load": wl,
        }
        stats["targets"] = {
            "allow_p99_under_1ms": max(allow_p99s) < 1000.0,
            "throughput_over_10k_per_sec": min(tps) > 10000,
            "tamper_detection_100pct": tamper["rate"] == 1.0,
            "zero_provenance_gaps": complete["gaps"] == 0 and complete["chain_ok"],
            "fail_safe_verified": safe["summary_returned"] is None and safe["decisions_unchanged"],
            "reproducible_within_spread_target": spread_pct(allow_p99s) <= args.max_spread_pct,
        }

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(stats, f, indent=2)
        write_report(stats)
        print(json.dumps(stats["targets"], indent=2))
        print(f"wrote {args.out} and docs/BENCHMARK.md")
        gating = {k: v for k, v in stats["targets"].items()
                  if k != "reproducible_within_spread_target" or not args.spread_report_only}
        return 0 if all(gating.values()) else 1
    finally:
        shutil.rmtree(top, ignore_errors=True)


def write_report(s):
    lat, st, t = s["latency"], s["stability"], s["targets"]

    def row(name, d):
        return f"| {name} | {d['p50_us']} | {d['p95_us']} | {d['p99_us']} |"

    md = f"""# VerdictPlane — Benchmark Report (P5)

Produced by `make bench` (bench/run_bench.py) from live measurement.
Machine-readable source: `artifacts/stats.json` (regenerated, not committed).

- **Commit:** `{s['meta']['commit']}`
- **Captured:** {s['meta']['captured_utc']}
- **Host:** {s['meta']['cpu']} · Python {s['meta']['python']} · {s['meta']['platform']}
- **Ledger:** filesystem `{s['meta']['ledger_filesystem']}`, fsync={s['meta']['fsync']}
- **Advisory:** {s['meta']['advisory_env']}
- **Method:** {s['meta']['runs']} independent runs x {s['meta']['allow_calls_per_run']} allow-path calls
  (fresh ledger per run, 500-call warmup before throughput window); median run shown.

## Targets scoreboard

| Target | Result |
| --- | --- |
| Allow-path p99 < 1 ms (every run) | {'PASS' if t['allow_p99_under_1ms'] else 'FAIL'} — worst run {max(st['allow_p99_us_per_run'])} µs |
| Throughput > 10k governed actions/s (worst run) | {'PASS' if t['throughput_over_10k_per_sec'] else 'FAIL'} — worst run {min(st['throughput_per_run'])}/s |
| Tamper detection 100% at exact index | {'PASS' if t['tamper_detection_100pct'] else 'FAIL'} — {s['tamper_detection']['detected']}/{s['tamper_detection']['trials']} |
| Zero provenance gaps + chain verifies | {'PASS' if t['zero_provenance_gaps'] else 'FAIL'} — {s['provenance_completeness']['gaps']} gaps / {s['provenance_completeness']['calls']} calls |
| Fail-safe with advisory forced broken | {'PASS' if t['fail_safe_verified'] else 'FAIL'} |
| Reproducibility (allow p99 spread <= {s['meta']['spread_target_pct']:g}%{'' if s['meta']['spread_enforced'] else '; informational on shared runners'}) | {('PASS' if t['reproducible_within_spread_target'] else 'FAIL') if s['meta']['spread_enforced'] else ('PASS' if t['reproducible_within_spread_target'] else 'INFO')} — spread {st['allow_p99_spread_pct']}% |

## Enforcement latency (median run, µs)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
{row('raw call (baseline)', lat['raw_call'])}
{row('governed allow', lat['allow_path'])}
{row('governed deny', lat['deny_path'])}
{row('require_human (auto-resolved gate)', lat['require_human_autoresolved'])}
{row('ledger append', lat['ledger_append'])}

Full-chain verify: {lat['verify']['entries']} entries in {lat['verify']['seconds']} s.

## Stability across runs

- allow p99 per run (µs): {st['allow_p99_us_per_run']} — spread {st['allow_p99_spread_pct']}%
- throughput per run (ops/s): {st['throughput_per_run']} — spread {st['throughput_spread_pct']}%

## Real workloads under load (P4 wrappers, workloads.yaml policy)

| Path | p50 | p95 | p99 |
| --- | --- | --- | --- |
{row('DriftGuard promote (Staging, allow)', s['workloads_under_load']['promote_staging_allow'])}
{row('DriftGuard promote (Production, gated+auto-resolve)', s['workloads_under_load']['promote_production_gated_autoresolved'])}
{row('Sentinel proposal (recorded)', s['workloads_under_load']['sentinel_proposal'])}

- Staging-promote throughput: {s['workloads_under_load']['promote_staging_ops_per_sec']} ops/s
- Chain verifies after load: {s['workloads_under_load']['chain_ok_after_load']}

## Fail-safe detail

Advisory backend configured and transport forced to error: summary returned =
`{s['fail_safe']['summary_returned']}`; policy decisions unchanged =
{s['fail_safe']['decisions_unchanged']}; unmatched action default =
`{s['fail_safe']['unknown_action_default']}`.

## Caveats

- Human-gated paths are human-scale by design; the auto-resolved gate number
  measures VerdictPlane's machinery (submit + resolve + 2 ledger appends), not
  reviewer latency.
- Numbers are host- and filesystem-dependent; re-run `make bench` on the
  target machine. fsync=False (default): tamper evidence is unaffected, a
  crash can lose the buffered tail (truncation is detectable via an anchored
  head). CPU frequency scaling is the main variance source.
"""
    with open(os.path.join(ROOT, "docs", "BENCHMARK.md"), "w") as f:
        f.write(md)


if __name__ == "__main__":
    sys.exit(main())
