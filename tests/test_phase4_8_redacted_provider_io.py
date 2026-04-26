"""Phase 4.8-A (QA/A25.md, ADR-33) — redacted provider I/O capture.

Hard invariants:

* DISABLED BY DEFAULT — neither the CLI flag nor the constructor
  flag opts in unless explicitly set.
* Redaction happens INSIDE the provider where the API key value is
  in scope. The runner never holds the raw key.
* The captured payload contains:
  - prompt SHA256 (NOT the raw prompt)
  - response body AFTER `redact_secret(body, key)`
  - model id, http_status, wall_clock_ms
  - response_id / finish_reason / token usage when the provider
    returns them
* The captured payload NEVER contains the raw API key value
  (asserted via a long distinctive sentinel that would be
  unmistakable in grep).

These tests use a fake HTTP transport so they don't make any
real network call. The sentinel `sk-DETECT-LEAK-Z9KF1L-PROVIDER-
IO-CANARY-2026` is the canary — if it ever appears in a captured
artifact, the redaction has failed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.estimators.llm_provider import (
    LLMProviderError,
    LLMProviderInvalidResponse,
    LLMProviderUnavailable,
)
from oida_code.estimators.provider_config import ProviderProfile
from oida_code.estimators.providers.openai_compatible import (
    HttpRequest,
    HttpResponse,
    OpenAICompatibleChatProvider,
    ProviderRedactedIO,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATASET_ROOT = _REPO_ROOT / "datasets" / "calibration_v1"

# Long, unique, unmistakable sentinel — anywhere this appears in a
# captured artifact would prove the redaction failed.
_SENTINEL_KEY = "sk-DETECT-LEAK-Z9KF1L-PROVIDER-IO-CANARY-2026"


def _profile() -> ProviderProfile:
    return ProviderProfile(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-v4-pro",
        supports_json_mode=True,
    )


_DEFAULT_CONTENT = (
    '{"estimates":[],"cited_evidence_refs":[],'
    '"unsupported_claims":[]}'
)


def _ok_response_body(content: str = _DEFAULT_CONTENT) -> str:
    """Synthesize a valid OpenAI-format chat-completions response."""
    return json.dumps({
        "id": "chatcmpl-canary",
        "object": "chat.completion",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            },
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "total_tokens": 19,
        },
    })


def _fake_http(body: str) -> object:
    """Return a `HttpPostFn` that always responds with `body`."""
    def _post(_req: HttpRequest) -> HttpResponse:
        return HttpResponse(status_code=200, body=body)
    return _post


# ---------------------------------------------------------------------------
# Constructor / capture mechanics
# ---------------------------------------------------------------------------


def test_redacted_io_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default ``capture_redacted_io=False`` MUST mean no
    redacted IO is stashed."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_ok_response_body()),
    )
    provider.estimate("hello", timeout_s=5)
    assert provider.pop_last_redacted_io() is None


def test_redacted_io_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with capture enabled at construction, no other path
    silently turns it on."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    provider_off = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_ok_response_body()),
        capture_redacted_io=False,
    )
    provider_off.estimate("hello", timeout_s=5)
    assert provider_off.pop_last_redacted_io() is None
    provider_on = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_ok_response_body()),
        capture_redacted_io=True,
    )
    provider_on.estimate("hello", timeout_s=5)
    captured = provider_on.pop_last_redacted_io()
    assert isinstance(captured, ProviderRedactedIO)


def test_redacted_io_contains_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A response body containing the API key value (e.g., in a
    401-style error message) MUST be redacted before being stashed.
    The sentinel is a long unique token; if it appears anywhere in
    the captured payload, redaction has failed."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    # Construct a response body that ECHOES the sentinel inline —
    # simulating a provider 401 that says "invalid key sk-..." or
    # any other error path that surfaces the auth state.
    poisoned_content = '{"estimates":[],"cited_evidence_refs":[],"unsupported_claims":[]}'
    poisoned_body_dict = json.loads(_ok_response_body(poisoned_content))
    poisoned_body_dict["debug_echo"] = (
        f"server saw bearer={_SENTINEL_KEY} via header"
    )
    poisoned_body = json.dumps(poisoned_body_dict)
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(poisoned_body),
        capture_redacted_io=True,
    )
    provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    serialized = captured.model_dump_json()
    assert _SENTINEL_KEY not in serialized, (
        "redacted IO leaks the API key sentinel — redaction failed"
    )
    assert "[REDACTED]" in captured.redacted_response_body, (
        "redacted IO has no [REDACTED] marker; redaction did not fire"
    )


def test_redacted_io_contains_no_raw_prompt_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The captured payload MUST carry only the prompt SHA256, not
    the raw prompt content. A unique sentinel in the prompt would
    be unmistakable if it leaked."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    sentinel_prompt = (
        "OIDA-PROMPT-SENTINEL-Z9KF1L-PHASE4.8-DO-NOT-LEAK"
    )
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_ok_response_body()),
        capture_redacted_io=True,
    )
    provider.estimate(sentinel_prompt, timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    serialized = captured.model_dump_json()
    assert sentinel_prompt not in serialized, (
        "redacted IO contains the raw prompt — must only carry "
        "prompt_sha256"
    )


def test_redacted_io_contains_response_after_secret_redaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The redacted_response_body MUST be the full HTTP body AFTER
    `redact_secret(body, key)` — not truncated, not omitted."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    body = _ok_response_body(
        '{"estimates":[],"cited_evidence_refs":[],'
        '"unsupported_claims":["needle@event-A"]}',
    )
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(body),
        capture_redacted_io=True,
    )
    provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    # The needle distinguishes this body from any other; it must
    # land in the captured payload.
    assert "needle@event-A" in captured.redacted_response_body
    # And the captured body must equal the original (no key in it).
    assert captured.redacted_response_body == body


def test_redacted_io_records_prompt_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """The captured payload MUST carry a 64-char SHA256 of the
    prompt string."""
    import hashlib
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    prompt = "deterministic-prompt-for-hashing"
    expected_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_ok_response_body()),
        capture_redacted_io=True,
    )
    provider.estimate(prompt, timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    assert captured.prompt_sha256 == expected_hash
    assert len(captured.prompt_sha256) == 64


def test_redacted_io_records_model_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The captured payload MUST carry the model id the provider
    actually used (from the response body)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    body = _ok_response_body()
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(body),
        capture_redacted_io=True,
    )
    provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    assert captured.model == "deepseek-v4-pro"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


_CLI_RUNNER = CliRunner()


def _ensure_dataset_exists() -> None:
    if not (_DATASET_ROOT / "manifest.json").is_file():
        pytest.skip("calibration_v1 not built; run scripts/build_calibration_dataset.py first")


def test_cli_flag_present_in_calibration_eval_help() -> None:
    """The CLI MUST expose ``--store-redacted-provider-io`` on
    ``calibration-eval`` so an operator can opt in."""
    result = _CLI_RUNNER.invoke(
        app, ["calibration-eval", "--help"],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    # Strip ANSI for substring match (Phase 4.5.2 lesson).
    import re
    plain = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.output)
    assert "--store-redacted-provider-io" in plain


def test_cli_flag_no_op_warns_in_replay_mode(
    tmp_path: Path,
) -> None:
    """In replay mode the flag is a no-op; the CLI MUST emit a
    warning to stderr so an operator who fat-fingered the flag
    notices."""
    _ensure_dataset_exists()
    out = tmp_path / "out"
    result = _CLI_RUNNER.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "replay",
            "--store-redacted-provider-io",
        ],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    combined = result.output + (result.stderr or "")
    assert "no-op" in combined.lower() or "no real wire response" in combined.lower(), (
        f"expected no-op warning when replay+store-redacted; got: {combined}"
    )


def test_redacted_io_dir_not_created_under_replay(
    tmp_path: Path,
) -> None:
    """In replay mode, no `<out>/<provider>/redacted_io/` directory
    must appear — the flag is documented as a no-op, and silently
    creating an empty directory would mislead an operator."""
    _ensure_dataset_exists()
    out = tmp_path / "out"
    _CLI_RUNNER.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "replay",
            "--store-redacted-provider-io",
        ],
        env={"COLUMNS": "200"},
    )
    # Walk the output tree; any folder named `redacted_io` is a fail.
    matches = list(out.rglob("redacted_io"))
    assert not matches, (
        f"replay path created redacted_io dir(s): {matches}"
    )


# ---------------------------------------------------------------------------
# Phase 4.9.0 (QA/A26.md, ADR-34) — failure-path redacted IO capture
#
# These tests close the V4 Pro 6/8 missing-capture gap from Phase 4.8:
# every provider failure path (provider_unavailable, transport_error,
# timeout, invalid_json, invalid_shape) MUST stash a redacted IO with
# the right `failure_kind`, NEVER the raw API key, and only the
# prompt SHA256 (never the raw prompt).
# ---------------------------------------------------------------------------


def _v4pro_like_missing_choices_body() -> str:
    """Reproduce the empirical V4 Pro shape that hit Phase 4.8 6/8 — a
    valid JSON object that lacks the `choices` array (e.g., the
    server returned just `{"error": ...}` or a partial stub).
    The provider must still capture this body redacted, with
    failure_kind="invalid_shape"."""
    return json.dumps({
        "id": "chatcmpl-shape-stub",
        "object": "chat.completion",
        "model": "deepseek-v4-pro",
        # NO "choices" key — provider should classify as invalid_shape.
    })


def test_failure_path_redacted_io_invalid_shape_is_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response that lacks `choices` MUST stash a redacted IO with
    failure_kind=`invalid_shape` and the body captured (redacted)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    body = _v4pro_like_missing_choices_body()
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(body),
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderInvalidResponse):
        provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None, (
        "Phase 4.9.0: invalid_shape failures MUST still stash a "
        "redacted IO; the V4 Pro 6/8 gap was missing captures here"
    )
    assert captured.failure_kind == "invalid_shape"
    assert captured.redacted_response_body == body
    assert captured.redacted_error is not None
    assert "choices" in captured.redacted_error.lower()
    assert captured.http_status == 200


def test_failure_path_redacted_io_invalid_json_is_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-JSON HTTP 200 body MUST stash a redacted IO with
    failure_kind=`invalid_json`. The body is captured (redacted) so
    the operator can debug the malformed response."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    body = "this is not json at all"
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(body),
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderInvalidResponse):
        provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    assert captured.failure_kind == "invalid_json"
    assert captured.redacted_response_body == body
    assert captured.redacted_error is not None
    assert "non-json" in captured.redacted_error.lower()


def test_failure_path_redacted_io_transport_error_is_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transport-layer failure (status_code=0) MUST stash a redacted
    IO with failure_kind=`transport_error`. The body is empty (no
    HTTP response was received) but the error string IS captured."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)

    def _failing_post(_req: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=0, body="",
            error="connection refused (ECONNREFUSED)",
        )
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_failing_post,
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderUnavailable):
        provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    assert captured.failure_kind == "transport_error"
    assert captured.http_status == 0
    assert captured.redacted_response_body == ""
    assert captured.redacted_error is not None
    assert "connection refused" in captured.redacted_error.lower()


def test_failure_path_redacted_io_contains_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401-style error body that ECHOES the API key (which real
    providers occasionally do) MUST be redacted on the failure
    path too — the failure-path stash MUST go through the same
    `redact_secret(body, key)` and `redact_secret(error, key)`
    pipeline as the success path. The sentinel is the canary."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    # 401 with the key echoed back in the body — the worst case.
    poisoned_body = json.dumps({
        "error": {
            "message": (
                f"Invalid bearer token sk-... full=({_SENTINEL_KEY}) "
                f"please rotate"
            ),
            "code": "invalid_api_key",
        },
    })

    def _http_401(_req: HttpRequest) -> HttpResponse:
        return HttpResponse(status_code=401, body=poisoned_body)
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_http_401,
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderError):
        provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    serialized = captured.model_dump_json()
    assert _SENTINEL_KEY not in serialized, (
        "Phase 4.9.0 failure-path stash leaks the API key sentinel — "
        "redaction did not fire on the >=400 branch"
    )
    assert captured.failure_kind == "transport_error"
    assert captured.http_status == 401
    assert captured.redacted_response_body is not None
    assert "[REDACTED]" in captured.redacted_response_body


def test_failure_path_redacted_io_contains_prompt_hash_not_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even on the failure path, the captured payload MUST carry
    only the SHA256 of the prompt — NEVER the raw prompt body."""
    import hashlib
    monkeypatch.setenv("DEEPSEEK_API_KEY", _SENTINEL_KEY)
    sentinel_prompt = (
        "OIDA-PROMPT-FAILURE-PATH-SENTINEL-Z9KF1L-PHASE4.9-DO-NOT-LEAK"
    )
    expected_hash = hashlib.sha256(
        sentinel_prompt.encode("utf-8"),
    ).hexdigest()
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        http_post=_fake_http(_v4pro_like_missing_choices_body()),
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderInvalidResponse):
        provider.estimate(sentinel_prompt, timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None
    serialized = captured.model_dump_json()
    assert sentinel_prompt not in serialized, (
        "failure-path captured payload contains the raw prompt — "
        "must only carry prompt_sha256"
    )
    assert captured.prompt_sha256 == expected_hash


def test_failure_path_redacted_io_provider_unavailable_no_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The env-var-missing path raises BEFORE any HTTP call. The
    redacted IO MUST still be stashed with failure_kind=
    `provider_unavailable`, body=None, and an error string that
    names the missing env var (no key value to leak)."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = OpenAICompatibleChatProvider(
        profile=_profile(),
        # The HTTP transport must NEVER be called when the env var
        # is missing. We pass a transport that would explode if it
        # were invoked, to lock that contract.
        http_post=lambda _req: pytest.fail(
            "http_post called despite missing env var",
        ),
        capture_redacted_io=True,
    )
    with pytest.raises(LLMProviderUnavailable):
        provider.estimate("hello", timeout_s=5)
    captured = provider.pop_last_redacted_io()
    assert captured is not None, (
        "Phase 4.9.0: provider_unavailable MUST also stash a "
        "redacted IO so the operator sees WHY the run was skipped"
    )
    assert captured.failure_kind == "provider_unavailable"
    assert captured.redacted_response_body is None
    assert captured.http_status is None
    assert captured.redacted_error is not None
    assert "DEEPSEEK_API_KEY" in captured.redacted_error
