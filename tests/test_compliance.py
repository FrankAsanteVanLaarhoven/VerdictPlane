"""EAG-Bench compliance/threat coverage compiler. Verifies it aggregates real mappings and
stays framed as coverage (not certification)."""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EAG = os.path.join(ROOT, "benchmarks", "eag_bench")


def _load():
    spec = importlib.util.spec_from_file_location("eag_compliance", os.path.join(EAG, "compliance.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


C = _load()


def test_regulatory_and_threat_coverage_present():
    cov = C.compile_coverage()
    assert cov["n_cases"] >= 100
    for fw in ("eu_ai_act", "nist_ai_rmf", "iso_42001"):
        assert fw in cov["regulatory"] and cov["regulatory"][fw], fw
        for control, ids in cov["regulatory"][fw].items():
            assert ids, (fw, control)  # every listed control is exercised by >=1 case
    assert "owasp_llm" in cov["threat"]


def test_output_is_framed_as_coverage_not_certification():
    md = C.render_markdown(C.compile_coverage())
    assert "coverage, not certification" in md.lower() or "not claim" in md.lower()
    assert "## Regulatory coverage" in md
    assert "## Summary" in md
