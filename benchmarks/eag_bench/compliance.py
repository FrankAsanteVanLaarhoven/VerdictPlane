"""EAG-Bench — compliance / threat coverage compiler.

Aggregates the corpus's `compliance_mappings` (regulatory) and `attack_annotations` (threat)
into per-framework coverage matrices. This is an EVIDENCE / COVERAGE map — which cases exercise
each control or threat — NOT a compliance certification: it does not claim VerdictPlane satisfies
any regulation. Run: `make compliance-report` (writes compliance/COVERAGE.md).
"""

from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASE_DIRS = [os.path.join(HERE, "cases"), os.path.join(HERE, "redteam", "cases")]
OUT = os.path.join(HERE, "compliance", "COVERAGE.md")

FRAMEWORKS = {
    "eu_ai_act": "EU AI Act",
    "nist_ai_rmf": "NIST AI RMF",
    "iso_42001": "ISO/IEC 42001",
    "owasp_llm": "OWASP LLM Top 10",
    "mitre_atlas": "MITRE ATLAS",
    "csa_caiq": "CSA CAIQ",
    "custom": "Custom",
}
REGULATORY = ["eu_ai_act", "nist_ai_rmf", "iso_42001"]
THREAT = ["owasp_llm", "mitre_atlas", "custom", "csa_caiq"]

DISCLAIMER = (
    "> **Scope — coverage, not certification.** This is an evidence map: which benchmark cases "
    "exercise each control or threat, compiled from the corpus's `compliance_mappings` and "
    "`attack_annotations`. It does **not** claim VerdictPlane satisfies any regulation or is "
    "certified against any standard; it shows where the benchmark provides testable evidence."
)


def _load_cases():
    cases = []
    for d in CASE_DIRS:
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            with open(f) as fh:
                cases.append(json.load(fh))
    return cases


def compile_coverage(cases=None) -> dict:
    """Return {'regulatory': {fw: {control: [ids]}}, 'threat': {fw: {id: [ids]}}, 'n_cases': N}."""
    cases = cases if cases is not None else _load_cases()
    reg: dict = {}
    thr: dict = {}
    for c in cases:
        cid = c["case_id"]
        for m in c.get("compliance_mappings", []):
            reg.setdefault(m["framework"], {}).setdefault(m["control"], [])
            if cid not in reg[m["framework"]][m["control"]]:
                reg[m["framework"]][m["control"]].append(cid)
        for a in c.get("attack_annotations", []):
            thr.setdefault(a["framework"], {}).setdefault(a["id"], [])
            if cid not in thr[a["framework"]][a["id"]]:
                thr[a["framework"]][a["id"]].append(cid)
    return {"regulatory": reg, "threat": thr, "n_cases": len(cases)}


def _table(section: dict) -> str:
    rows = ["| control | cases | count |", "| --- | --- | --- |"]
    for control in sorted(section):
        ids = sorted(section[control])
        shown = ", ".join(f"`{i}`" for i in ids[:6]) + (" …" if len(ids) > 6 else "")
        rows.append(f"| **{control}** | {shown} | {len(ids)} |")
    return "\n".join(rows)


def render_markdown(cov: dict) -> str:
    out = ["# EAG-Bench — Regulatory & Threat Coverage", "", DISCLAIMER, "",
           f"Compiled by `make compliance-report` from **{cov['n_cases']}** cases "
           f"(single-action corpus + red-team track).", "", "## Regulatory coverage", ""]
    for fw in REGULATORY:
        if fw in cov["regulatory"]:
            out += [f"### {FRAMEWORKS[fw]}", "", _table(cov["regulatory"][fw]), ""]
    out += ["## Threat coverage (attack annotations)", ""]
    for fw in THREAT:
        if fw in cov["threat"]:
            out += [f"### {FRAMEWORKS.get(fw, fw)}", "", _table(cov["threat"][fw]), ""]
    out += ["## Summary", "", "| framework | kind | controls | cases |", "| --- | --- | --- | --- |"]
    for fw in REGULATORY:
        if fw in cov["regulatory"]:
            sec = cov["regulatory"][fw]
            out.append(f"| {FRAMEWORKS[fw]} | regulatory | {len(sec)} | {len({i for v in sec.values() for i in v})} |")
    for fw in THREAT:
        if fw in cov["threat"]:
            sec = cov["threat"][fw]
            out.append(f"| {FRAMEWORKS.get(fw, fw)} | threat | {len(sec)} | {len({i for v in sec.values() for i in v})} |")
    return "\n".join(out) + "\n"


def main(argv: list) -> int:
    cov = compile_coverage()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render_markdown(cov))
    n_reg = sum(len(cov["regulatory"].get(fw, {})) for fw in REGULATORY)
    n_thr = sum(len(cov["threat"].get(fw, {})) for fw in THREAT)
    print(f"compliance coverage: {n_reg} regulatory controls, {n_thr} threat techniques "
          f"across {cov['n_cases']} cases -> {os.path.relpath(OUT, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
