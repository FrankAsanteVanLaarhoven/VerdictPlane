"""Advisory is optional and fail-safe: off by default, every failure returns
None, results are cached, and enforcement never touches it (see the static
import guard for the last part)."""

import io
import json

import pytest

from keystone import advisory

ACTION = {"tool": "email.send", "effect": "write", "args": {"to": "x@y.z"}, "agent": "a"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture()
def cache(tmp_path):
    return str(tmp_path / "cache.json")


def test_off_by_default(monkeypatch, cache):
    monkeypatch.delenv("KEYSTONE_ADVISORY", raising=False)
    assert advisory.risk_summary(ACTION, cache_path=cache) is None


def test_unknown_backend_is_off(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "quantum")
    assert advisory.risk_summary(ACTION, cache_path=cache) is None


def test_fable5_without_api_key_is_none(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "fable5")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert advisory.risk_summary(ACTION, cache_path=cache) is None


def test_network_error_is_fail_safe(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "fable5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    def boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(advisory.urllib.request, "urlopen", boom)
    assert advisory.risk_summary(ACTION, cache_path=cache) is None


def test_fable5_success_and_cache(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "fable5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        body = json.loads(req.data)
        assert body["model"] == "claude-fable-5"
        assert "thinking" not in body  # always-on for Fable 5; param must be omitted
        assert body["fallbacks"] == [{"model": "claude-opus-4-8"}]
        assert req.headers["X-api-key"] == "k"
        assert req.headers["Anthropic-version"] == "2023-06-01"
        assert req.headers["Anthropic-beta"] == "server-side-fallback-2026-06-01"
        return FakeResponse(json.dumps({
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "- writes to external inbox"}],
        }).encode())

    monkeypatch.setattr(advisory.urllib.request, "urlopen", fake_urlopen)
    assert advisory.risk_summary(ACTION, cache_path=cache) == "- writes to external inbox"
    assert advisory.risk_summary(ACTION, cache_path=cache) == "- writes to external inbox"
    assert len(calls) == 1  # second call served from the signature cache


def test_fable5_refusal_is_none(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "fable5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(
        advisory.urllib.request, "urlopen",
        lambda req, timeout=None: FakeResponse(
            json.dumps({"stop_reason": "refusal", "content": []}).encode()
        ),
    )
    assert advisory.risk_summary(ACTION, cache_path=cache) is None


def test_local_backend_via_ollama(monkeypatch, cache):
    monkeypatch.setenv("KEYSTONE_ADVISORY", "local")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def fake_urlopen(req, timeout=None):
        assert req.full_url.endswith("/api/generate")
        assert json.loads(req.data)["stream"] is False
        return FakeResponse(json.dumps({"response": "- local risk note"}).encode())

    monkeypatch.setattr(advisory.urllib.request, "urlopen", fake_urlopen)
    assert advisory.risk_summary(ACTION, cache_path=cache) == "- local risk note"


def test_signature_is_deterministic():
    a = advisory.action_signature({"tool": "t", "args": {"b": 2, "a": 1}})
    b = advisory.action_signature({"args": {"a": 1, "b": 2}, "tool": "t"})
    assert a == b
