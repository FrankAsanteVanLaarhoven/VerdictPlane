"""Guardrail: the enforcement path imports no model client and no network module.

Every module under src/verdictplane/ is enforcement-path unless explicitly listed
in NON_ENFORCEMENT (advisory/CLI live off the hot path). Imports are checked
statically (AST) against a strict allowlist, so a violation fails CI before it
can ever run.
"""

import ast
import os

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "verdictplane")

# Off-hot-path modules, allowed to talk to models/CLIs (still zero-egress by default).
NON_ENFORCEMENT = {"advisory.py", "cli.py"}

ALLOWED_IMPORTS = {
    # stdlib, deterministic, no network
    "__future__", "collections", "contextvars", "dataclasses", "enum", "fnmatch",
    "functools", "hashlib", "inspect", "io", "json", "os", "pathlib", "re",
    "threading", "time", "typing", "uuid",
    # declared schema/config deps (no network)
    "pydantic", "yaml",
    # intra-package
    "verdictplane",
}

# Network modules called out explicitly for clarity. Model-client SDKs need no
# explicit list: any import outside ALLOWED_IMPORTS (which contains no model
# client and nothing that can open a connection) already fails the allowlist test.
FORBIDDEN_EXPLICIT = {
    "socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp",
    "websockets", "grpc", "smtplib", "ftplib",
}


def enforcement_modules():
    return sorted(
        f for f in os.listdir(SRC)
        if f.endswith(".py") and f not in NON_ENFORCEMENT
    )


def top_level_imports(path):
    with open(path) as f:
        tree = ast.parse(f.read())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:  # relative import -> intra-package
                roots.add("verdictplane")
            elif node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", enforcement_modules())
def test_enforcement_imports_allowlisted(module):
    roots = top_level_imports(os.path.join(SRC, module))
    violations = roots - ALLOWED_IMPORTS
    assert not violations, f"{module} imports outside the enforcement allowlist: {violations}"


@pytest.mark.parametrize("module", enforcement_modules())
def test_no_network_or_model_clients(module):
    roots = top_level_imports(os.path.join(SRC, module))
    hits = roots & FORBIDDEN_EXPLICIT
    assert not hits, f"{module} imports a network/model module: {hits}"


def test_enforcement_set_is_not_empty():
    assert {"provenance.py", "policy.py", "types.py"} <= set(enforcement_modules())


@pytest.mark.parametrize("module", enforcement_modules())
def test_enforcement_never_imports_advisory_or_cli(module):
    """The intra-package allowlist must not smuggle the off-path modules in."""
    with open(os.path.join(SRC, module)) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            referenced = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                referenced.append(node.module)
            for name in referenced:
                assert "advisory" not in name and name != "cli", (
                    f"{module} imports off-hot-path module {name!r}"
                )
