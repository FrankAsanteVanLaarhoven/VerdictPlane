PY := .venv/bin/python
# PYTHONPATH= + autoload-off keep system packages (e.g. ROS pytest plugins) out.
PYTEST := PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest
# Prefer the real docker CLI over any ~/.local/bin compose-injecting shim.
DOCKER := $(shell [ -x /usr/bin/docker ] && echo /usr/bin/docker || echo docker)

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

.PHONY: eag-validate
eag-validate:
	$(PY) benchmarks/eag_bench/validate.py

.PHONY: enterprise-bench
enterprise-bench:
	PYTHONPATH= $(PY) benchmarks/eag_bench/harness.py

.PHONY: redteam-bench
redteam-bench:
	PYTHONPATH= $(PY) benchmarks/eag_bench/redteam/harness.py

.PHONY: demo
demo:
	VERDICTPLANE_LEDGER=artifacts/demo/ledger.jsonl VERDICTPLANE_GATE=artifacts/demo/gate \
	VERDICTPLANE_DEMO_TIMEOUT=90 $(PY) deploy/demo_agent.py

# One-command reproduction for external reviewers: builds a clean image and runs
# the full protocol (tests + benchmark scoreboard + evidence pack) inside it.
.PHONY: repro
repro:
	$(DOCKER) build -f deploy/repro.Dockerfile \
	  --build-arg VERDICTPLANE_REPRO_COMMIT=$$(git rev-parse HEAD) \
	  -t verdictplane-repro .
	$(DOCKER) run --rm verdictplane-repro
