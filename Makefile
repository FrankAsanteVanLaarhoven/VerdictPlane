PY := .venv/bin/python
# PYTHONPATH= + autoload-off keep system packages (e.g. ROS pytest plugins) out.
PYTEST := PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest

.PHONY: setup test verify bench

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -e .[dev]

test:
	$(PYTEST)

verify:
	$(PY) -c "import sys; from verdictplane.provenance import Ledger; ok, bad = Ledger().verify(); print('ledger ok' if ok else f'TAMPERED at line {bad}'); sys.exit(0 if ok else 1)"


.PHONY: evidence
evidence:
	PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PY) scripts/build_evidence.py

.PHONY: bench
bench:
	PYTHONPATH= VERDICTPLANE_ADVISORY=off $(PY) bench/run_bench.py

.PHONY: demo
demo:
	VERDICTPLANE_LEDGER=artifacts/demo/ledger.jsonl VERDICTPLANE_GATE=artifacts/demo/gate \
	VERDICTPLANE_DEMO_TIMEOUT=90 $(PY) deploy/demo_agent.py
