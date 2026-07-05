"""EAG-Bench agentic red-team track. Asserts the two-bucket result: defeated attacks are
blocked (0 escapes) and known-boundary attacks reproduce as documented — plus a check that
the defeated bucket genuinely depends on the policy (permissive policy -> escapes)."""

import glob
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EAG = os.path.join(ROOT, "benchmarks", "eag_bench")
RT = os.path.join(EAG, "redteam")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


H = _load(os.path.join(RT, "harness.py"), "rt_harness")
V = _load(os.path.join(EAG, "validate.py"), "rt_validate")
SCHEMA = V.load_schema(os.path.join(RT, "schema", "redteam_case.schema.json"))


def test_all_redteam_cases_validate():
    files = glob.glob(os.path.join(RT, "cases", "*.json"))
    assert files
    for f in files:
        assert V.validate_case(json.load(open(f)), SCHEMA) == [], f


def test_defeated_blocked_and_boundary_reproduced(tmp_path):
    rep = H.run(workdir=str(tmp_path))
    assert rep["defeated_total"] > 0 and rep["boundary_total"] > 0
    escaped = [r["case_id"] for r in rep["results"]
               if r["expected_outcome"] == "defeated_by_design" and not r["ok"]]
    assert rep["escapes"] == 0, escaped
    assert rep["boundary_reproduced"] == rep["boundary_total"]
    assert rep["chain_intact"] == rep["total_cases"]
    assert rep["passed"]


def test_defeated_bucket_depends_on_policy(tmp_path):
    # under a permissive allow-everything policy the defeated attacks' critical steps execute,
    # so the harness must report escapes — proving the 0 above is the policy's doing, not the harness'.
    permissive = tmp_path / "permissive.yaml"
    permissive.write_text("default: allow\nrules: []\n")
    rep = H.run(policy_path=str(permissive), workdir=str(tmp_path / "w"))
    assert rep["escapes"] > 0
    assert not rep["passed"]
