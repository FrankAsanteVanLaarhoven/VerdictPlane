"""Deterministic policy engine: declarative rules -> allow | deny | require_human.

First-match-wins over an ordered rule list; anything unmatched falls to the
policy default (require_human unless stated — default-deny posture). Match
conditions support glob patterns (fnmatchcase, case-sensitive on every
platform) and gt/lt/eq/in operators on dotted action paths ("args.amount").

Missing fields, incomparable types, and unknown operators never match a rule —
the action falls through toward the safe default rather than erroring open.

Enforcement-path module: deterministic, zero-egress, no model client.
"""

import fnmatch
from typing import Any

import yaml

ALLOW = "allow"
DENY = "deny"
REQUIRE_HUMAN = "require_human"
DECISIONS = {ALLOW, DENY, REQUIRE_HUMAN}

_MISSING = object()


class PolicyError(ValueError):
    """Raised when a policy document is malformed. Invalid policies never load."""


def _dig(action: dict, dotted: str):
    """Resolve a dotted path like 'args.amount'; _MISSING if absent."""
    cur: Any = action
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _cmp(val, cond) -> bool:
    """Compare one action value to one rule condition. Never raises."""
    if val is _MISSING:
        return False
    if isinstance(cond, dict):  # operator form: {gt: x} / {lt: x} / {eq: x} / {in: [...]}
        for op, ref in cond.items():
            try:
                if op == "gt":
                    ok = val > ref
                elif op == "lt":
                    ok = val < ref
                elif op == "eq":
                    ok = val == ref
                elif op == "in":
                    ok = val in ref
                else:
                    return False  # unknown operator never matches
            except TypeError:
                return False  # incomparable types never match
            if not ok:
                return False
        return True
    if isinstance(cond, bool) or isinstance(val, bool):
        return val == cond
    if isinstance(cond, (int, float)) and isinstance(val, (int, float)):
        return val == cond
    return fnmatch.fnmatchcase(str(val), str(cond))


def _match(action: dict, match: dict) -> bool:
    return all(_cmp(_dig(action, key), cond) for key, cond in match.items())


def evaluate(action: dict, policy: dict) -> tuple[str, dict | None]:
    """Deterministic decision for one action. Returns (decision, matched_rule|None)."""
    for rule in policy.get("rules", []):
        if _match(action, rule["match"]):
            return rule["decision"], rule
    return policy.get("default", REQUIRE_HUMAN), None


def validate_policy(policy) -> dict:
    """Structurally validate a policy document; raise PolicyError if malformed."""
    if not isinstance(policy, dict):
        raise PolicyError("policy must be a mapping")
    default = policy.get("default", REQUIRE_HUMAN)
    if default not in DECISIONS:
        raise PolicyError(f"invalid default decision: {default!r}")
    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        raise PolicyError("rules must be a list")
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise PolicyError(f"rule {i} must be a mapping")
        if not isinstance(rule.get("match"), dict) or not rule["match"]:
            raise PolicyError(f"rule {i} needs a non-empty 'match' mapping")
        if rule.get("decision") not in DECISIONS:
            raise PolicyError(f"rule {i} has invalid decision: {rule.get('decision')!r}")
    return policy


def load_policy(path: str) -> dict:
    """Load and validate a policy YAML file."""
    with open(path) as f:
        return validate_policy(yaml.safe_load(f))
