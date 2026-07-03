"""Policy conformance suite: labelled (action -> expected decision) cases
against policies/policy.yaml, plus unit tests of the matching semantics.
Target: 100% correct, deterministic."""

import os

import pytest

from verdictplane.policy import (
    ALLOW,
    DENY,
    REQUIRE_HUMAN,
    PolicyError,
    evaluate,
    load_policy,
    validate_policy,
)

POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "policy.yaml")


@pytest.fixture(scope="module")
def policy():
    return load_policy(POLICY_PATH)


def act(tool, effect="write", agent="trusted", **args):
    return {"tool": tool, "effect": effect, "agent": agent, "args": args}


# ---- labelled conformance cases (id, action, expected decision) ----
CASES = [
    # reads are allowed, for any agent
    ("read-db", act("db.read", "read", "analyst"), ALLOW),
    ("read-fs", act("fs.read", "read", "agent-a"), ALLOW),
    ("read-untrusted", act("http.get", "read", "untrusted"), ALLOW),
    ("read-mcp", act("search.query", "read", "mcp"), ALLOW),
    ("read-ci", act("fs.list", "read", "ci"), ALLOW),
    ("read-scheduler", act("metrics.query", "read", "scheduler"), ALLOW),
    ("read-with-args", act("db.read", "read", "untrusted", table="users"), ALLOW),
    ("read-fs-stat", act("fs.stat", "read"), ALLOW),
    # email.send with claimed effect=read: first-match ordering lets the read rule win
    ("read-beats-email-rule", act("email.send", "read", "support"), ALLOW),
    # shell.exec is denied regardless of claimed effect (rule order beats read-allow)
    ("shell-exec", act("shell.exec", "execute", "dev"), DENY),
    ("shell-claimed-read", act("shell.exec", "read", "dev"), DENY),
    ("shell-claimed-delete", act("shell.exec", "delete", "dev"), DENY),
    ("shell-untrusted", act("shell.exec", "write", "untrusted"), DENY),
    ("shell-ci", act("shell.exec", "execute", "ci", cmd="rm -rf /"), DENY),
    # untrusted agents never write
    ("untrusted-db-small", act("db.write", "write", "untrusted", amount=5), DENY),
    ("untrusted-db-large", act("db.write", "write", "untrusted", amount=2000), DENY),
    ("untrusted-fs-tmp", act("fs.write", "write", "untrusted", path="/tmp/x"), DENY),
    ("untrusted-email", act("email.send", "write", "untrusted"), DENY),
    ("untrusted-deploy", act("deploy.rollout", "write", "untrusted", env="staging"), DENY),
    # db.write amount thresholds (gt 1000 gated, lt 1001 allowed)
    ("db-1001", act("db.write", amount=1001), REQUIRE_HUMAN),
    ("db-1000", act("db.write", amount=1000), ALLOW),
    ("db-0", act("db.write", amount=0), ALLOW),
    ("db-negative", act("db.write", amount=-5), ALLOW),
    ("db-huge", act("db.write", amount=10**9), REQUIRE_HUMAN),
    ("db-float-over", act("db.write", amount=1000.01), REQUIRE_HUMAN),
    ("db-1000-ci", act("db.write", "write", "ci", amount=1000), ALLOW),
    # incomparable / missing amounts fall through to the safe default
    ("db-amount-string", act("db.write", amount="lots"), REQUIRE_HUMAN),
    ("db-amount-missing", act("db.write"), REQUIRE_HUMAN),
    ("db-amount-nested-dict", act("db.write", amount={"value": 5}), REQUIRE_HUMAN),
    # rules match on tool+amount regardless of effect (documented first-match behavior)
    ("db-effect-promote", act("db.write", "promote", amount=5), ALLOW),
    # email is always gated for writes
    ("email-support", act("email.send", "write", "support", to="x@y.z"), REQUIRE_HUMAN),
    ("email-ci", act("email.send", "write", "ci"), REQUIRE_HUMAN),
    # globs are exact-prefix semantics: email.send.bulk is NOT email.send
    ("email-bulk-default", act("email.send.bulk"), REQUIRE_HUMAN),
    # filesystem writes
    ("fs-tmp-allowed", act("fs.write", path="/tmp/scratch.txt"), ALLOW),
    ("fs-tmp-deep", act("fs.write", path="/tmp/sub/deep.txt"), ALLOW),
    ("fs-etc-gated", act("fs.write", path="/etc/passwd"), REQUIRE_HUMAN),
    ("fs-tmpx-not-tmp", act("fs.write", path="/tmpx/file"), REQUIRE_HUMAN),
    ("fs-delete-tmp", act("fs.delete", path="/tmp/x"), REQUIRE_HUMAN),
    ("fs-chmod", act("fs.chmod", path="/srv/app"), REQUIRE_HUMAN),
    ("fs-glob-crosses-dots", act("fs.write.batch", path="/var/data"), REQUIRE_HUMAN),
    # deployments
    ("deploy-staging-ci", act("deploy.rollout", "write", "ci", env="staging"), ALLOW),
    ("deploy-staging-scheduler", act("deploy.rollout", "write", "scheduler", env="staging"), ALLOW),
    ("deploy-staging-human", act("deploy.rollout", "write", "dev-human", env="staging"), REQUIRE_HUMAN),
    ("deploy-staging-ci2", act("deploy.rollout", "write", "ci2", env="staging"), REQUIRE_HUMAN),
    ("deploy-prod-ci", act("deploy.rollout", "write", "ci", env="production"), REQUIRE_HUMAN),
    ("deploy-prod-admin", act("deploy.rollout", "write", "admin", env="production"), REQUIRE_HUMAN),
    ("deploy-dev-env", act("deploy.rollout", "write", "ci", env="dev"), REQUIRE_HUMAN),
    ("deploy-case-sensitive", act("deploy.rollout", "write", "admin", env="Production"), REQUIRE_HUMAN),
    ("deploy-env-missing", act("deploy.rollout", "write", "ci"), REQUIRE_HUMAN),
    # unmatched tools fall to the default (default-deny posture)
    ("unknown-tool", act("unknown.tool", "write", "agent-x"), REQUIRE_HUMAN),
    ("payments", act("payments.charge", amount=10), REQUIRE_HUMAN),
    ("k8s", act("k8s.scale", replicas=3), REQUIRE_HUMAN),
    ("slack", act("slack.post", channel="#ops"), REQUIRE_HUMAN),
    ("trusted-unknown-write", act("mystery.op", "write", "trusted"), REQUIRE_HUMAN),
    ("delete-effect-default", act("queue.purge", "delete"), REQUIRE_HUMAN),
    ("db-read-tool-but-write-effect", act("db.read", "write"), REQUIRE_HUMAN),
]


@pytest.mark.parametrize("case_id,action,expected", CASES, ids=[c[0] for c in CASES])
def test_conformance(policy, case_id, action, expected):
    decision, _rule = evaluate(action, policy)
    assert decision == expected


def test_suite_size():
    assert len(CASES) >= 50


def test_deterministic(policy):
    for _, action, _ in CASES:
        first = evaluate(action, policy)
        assert all(evaluate(action, policy) == first for _ in range(5))


def test_unmatched_returns_no_rule(policy):
    decision, rule = evaluate(act("unknown.tool"), policy)
    assert decision == REQUIRE_HUMAN and rule is None


def test_matched_returns_rule(policy):
    decision, rule = evaluate(act("email.send"), policy)
    assert decision == REQUIRE_HUMAN and rule["match"] == {"tool": "email.send"}


def test_default_is_require_human_when_absent():
    assert evaluate(act("anything"), {"rules": []}) == (REQUIRE_HUMAN, None)


def test_unknown_operator_never_matches():
    policy = {"rules": [{"match": {"args.amount": {"gte": 1}}, "decision": "deny"}]}
    assert evaluate(act("t", amount=5), policy) == (REQUIRE_HUMAN, None)


# ---- policy validation: malformed policies never load ----

def test_invalid_decision_rejected():
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"match": {"tool": "x"}, "decision": "maybe"}]})


def test_invalid_default_rejected():
    with pytest.raises(PolicyError):
        validate_policy({"default": "allow_all", "rules": []})


def test_missing_match_rejected():
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"decision": "allow"}]})


def test_empty_match_rejected():
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"match": {}, "decision": "allow"}]})


def test_non_mapping_policy_rejected():
    with pytest.raises(PolicyError):
        validate_policy(["not", "a", "mapping"])
