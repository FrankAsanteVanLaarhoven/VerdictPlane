"""Optional model-generated risk summaries for the HUMAN REVIEWER.

NEVER in the enforcement path: govern() does not import or call this module
(asserted statically in tests/test_enforcement_imports.py). The reviewer CLI
invokes it on demand, off the hot path. Every failure — no backend configured,
no key, no network, model down, refusal — returns None; the approval flow is
unaffected and the summary never decides the gate.

Backend selection (VERDICTPLANE_ADVISORY): "off" (default) | "fable5" | "local".
- fable5: claude-fable-5 via the Claude API (raw HTTP, no SDK dependency),
  with a server-side claude-opus-4-8 refusal fallback enabled by default.
- local:  an Ollama-served model on the local GPU (default qwen2.5:7b on the
  RTX 4080) for fully air-gapped, zero-egress deployments.
VERDICTPLANE_ADVISORY_MODEL overrides the model for either backend.

Summaries are cached by action signature (backend:model:sha256 of the action)
so repeated identical actions cost nothing.
"""

import hashlib
import json
import os
import urllib.request

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CACHE_PATH = "artifacts/advisory_cache.json"
TIMEOUT_SECONDS = 30

PROMPT = """You are assisting a human reviewer who must approve or deny a pending \
AI-driven action intercepted by a governance layer. In at most 3 short bullets, \
summarize the concrete risks of approving it (blast radius, reversibility, \
anything suspicious in the arguments). Do NOT make or recommend the decision — \
the human decides.

Pending action:
{action}
"""


def backend() -> str:
    return os.environ.get("VERDICTPLANE_ADVISORY", "off").strip().lower()


def action_signature(action: dict) -> str:
    return hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()


def _load_cache(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: str, cache: dict) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f)


def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read())


def _fable5_summary(action: dict) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("VERDICTPLANE_ADVISORY_MODEL", "claude-fable-5")
    body = {
        "model": model,
        "max_tokens": 512,
        # Fable 5: thinking is always on — no thinking/temperature params.
        "messages": [
            {"role": "user", "content": PROMPT.format(action=json.dumps(action, indent=2, sort_keys=True))}
        ],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if model == "claude-fable-5":
        # Server-side refusal fallback: a safety-classifier decline is re-served
        # by Opus 4.8 in the same call instead of failing the summary.
        body["fallbacks"] = [{"model": "claude-opus-4-8"}]
        headers["anthropic-beta"] = "server-side-fallback-2026-06-01"
    data = _post_json(CLAUDE_API_URL, body, headers)
    if data.get("stop_reason") == "refusal":
        return None
    text = "\n".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    ).strip()
    return text or None


def _local_summary(action: dict) -> str | None:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    body = {
        "model": os.environ.get("VERDICTPLANE_ADVISORY_MODEL", "qwen2.5:7b"),
        "prompt": PROMPT.format(action=json.dumps(action, indent=2, sort_keys=True)),
        "stream": False,
    }
    data = _post_json(f"{host}/api/generate", body, {})
    text = (data.get("response") or "").strip()
    return text or None


def risk_summary(action: dict, *, cache_path: str = CACHE_PATH) -> str | None:
    """Advisory text for the reviewer, or None. Never raises, never decides."""
    try:
        mode = backend()
        if mode in ("", "off", "none", "0", "false"):
            return None
        model = os.environ.get("VERDICTPLANE_ADVISORY_MODEL", "default")
        key = f"{mode}:{model}:{action_signature(action)}"
        cache = _load_cache(cache_path)
        if key in cache:
            return cache[key]
        if mode == "fable5":
            text = _fable5_summary(action)
        elif mode == "local":
            text = _local_summary(action)
        else:
            return None  # unknown backend: advisory off, enforcement unaffected
        if text:
            cache[key] = text
            _save_cache(cache_path, cache)
        return text
    except Exception:
        return None  # fail-safe: any error means "no summary", never a block
