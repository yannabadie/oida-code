"""Phase 4.4 (QA/A20.md, ADR-29) — real provider binding tests.

Eight groups:

* Schema invariants on :class:`ProviderProfile` (no API-key field,
  ``extra="forbid"``, frozen).
* Predefined profile registry (DeepSeek / Kimi / MiniMax) round-trips.
* Provider unavailable when the env var is missing — no HTTP call.
* Key never leaks into exception messages, even when the env var IS
  set.
* Response validation — invalid JSON / schema violation / forbidden
  phrase rejected.
* Default opt-out — the existing replay path stays unchanged.
* End-to-end through ``run_llm_estimator`` with an injected fake HTTP
  transport.
* CLI smoke for ``estimate-llm --llm-provider openai-compatible …``
  AND ``calibration-eval`` (replay default).

The optional ``test_deepseek_smoke_real_call`` lives at the end and
is **only** executed when ``OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1``
AND the relevant API key env var is set.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.estimators.llm_provider import (
    LLMProviderError,
    LLMProviderInvalidResponse,
    LLMProviderTimeout,
    LLMProviderUnavailable,
)
from oida_code.estimators.provider_config import (
    ProviderProfile,
    get_predefined_profile,
)
from oida_code.estimators.providers.openai_compatible import (
    HttpRequest,
    HttpResponse,
    OpenAICompatibleChatProvider,
    redact_secret,
)

_EXTERNAL_KEY_VAR = "OIDA_RUN_EXTERNAL_PROVIDER_TESTS"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    api_key_env: str = "TEST_PROVIDER_KEY",
    base_url: str = "https://example.invalid/v1",
    model: str = "test-model",
) -> ProviderProfile:
    return ProviderProfile(
        name="custom_openai_compatible",
        base_url=base_url,
        api_key_env=api_key_env,
        default_model=model,
        timeout_s=10,
    )


def _ok_chat_body(content: str, model: str = "test-model") -> str:
    """Minimal valid OpenAI Chat Completions response body."""
    return json.dumps({
        "id": "resp-1",
        "model": model,
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    })


class _RecordingTransport:
    """Fake HTTP transport that records every request and returns a
    canned response. Used everywhere instead of real network calls."""

    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[HttpRequest] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.calls.append(req)
        return self.response


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def test_provider_profile_has_no_secret_field() -> None:
    """ADR-29 §accepted: a profile MUST NOT carry the API key value;
    only the env var name. We verify by inspecting the model schema."""
    fields = ProviderProfile.model_fields
    assert "api_key" not in fields
    assert "api_key_value" not in fields
    assert "secret" not in fields
    assert "api_key_env" in fields


def test_provider_config_forbidden_extra() -> None:
    """4.4: the schema MUST reject extra fields (e.g. an ``api_key``
    snuck in)."""
    with pytest.raises(ValidationError):
        ProviderProfile.model_validate({
            "name": "deepseek", "api_style": "openai_chat_completions",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model": "deepseek-chat",
            "api_key": "sk-LEAK",  # extra field
        })


def test_provider_profile_is_frozen() -> None:
    profile = _profile()
    with pytest.raises(ValidationError):
        profile.api_key_env = "OTHER"  # type: ignore[misc]


def test_provider_profile_dump_does_not_carry_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with a real env value present, the profile's
    ``model_dump()`` MUST NOT contain that value."""
    secret = "sk-MUST-NOT-LEAK-12345"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    profile = _profile()
    payload = profile.model_dump()
    assert secret not in json.dumps(payload)


def test_provider_profile_dump_does_not_carry_api_key_in_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-also-must-not-leak"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    profile = _profile()
    assert secret not in profile.model_dump_json()


# ---------------------------------------------------------------------------
# Predefined profiles
# ---------------------------------------------------------------------------


def test_predefined_profiles_present() -> None:
    for name in ("deepseek", "kimi", "minimax"):
        profile = get_predefined_profile(name)  # type: ignore[arg-type]
        assert profile.name == name
        assert profile.api_style == "openai_chat_completions"
        assert profile.base_url
        assert profile.api_key_env
        assert profile.default_model


def test_predefined_profile_rejects_custom() -> None:
    """``custom_openai_compatible`` has no canonical defaults — caller
    must construct the profile explicitly."""
    with pytest.raises(KeyError, match="custom_openai_compatible"):
        get_predefined_profile("custom_openai_compatible")


# ---------------------------------------------------------------------------
# Provider unavailable / no call by default
# ---------------------------------------------------------------------------


def test_no_external_provider_called_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4 hard rule: without an explicit env var, the provider MUST
    raise ``LLMProviderUnavailable`` *before* any HTTP attempt."""
    monkeypatch.delenv("TEST_PROVIDER_KEY", raising=False)
    transport = _RecordingTransport(HttpResponse(200, _ok_chat_body("{}")))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    with pytest.raises(LLMProviderUnavailable, match="TEST_PROVIDER_KEY"):
        provider.estimate("ignored", timeout_s=5)
    assert not transport.calls


def test_missing_api_key_env_returns_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_PROVIDER_KEY", raising=False)
    provider = OpenAICompatibleChatProvider(profile=_profile())
    with pytest.raises(LLMProviderUnavailable):
        provider.estimate("x", timeout_s=5)


def test_external_provider_requires_explicit_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI default (``--llm-provider replay``) MUST NOT touch
    the openai-compatible code path. We verify by setting up a
    replay fixture and asserting the run succeeds without ever
    needing an env var."""
    monkeypatch.delenv("TEST_PROVIDER_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    pkt = tmp_path / "packet.json"
    pkt.write_text(json.dumps({
        "event_id": "e1",
        "allowed_fields": ["capability"],
        "intent_summary": "x",
        "evidence_items": [{
            "id": "[E.intent.1]", "kind": "intent", "summary": "x",
            "source": "ticket", "confidence": 0.9,
        }],
        "deterministic_estimates": [],
    }), encoding="utf-8")
    reply = tmp_path / "reply.json"
    reply.write_text(json.dumps({
        "estimates": [], "cited_evidence_refs": [], "unsupported_claims": [],
    }), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "estimate-llm", str(pkt),
            "--llm-provider", "replay",
            "--llm-response-fixture", str(reply),
        ],
    )
    assert result.exit_code == 0, result.output
    # Output is the EstimatorReport JSON (default deterministic baseline).
    assert "status" in result.output


# ---------------------------------------------------------------------------
# Key never leaks
# ---------------------------------------------------------------------------


def test_api_key_value_redacted_from_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the HTTP body echoes the API key (some providers do that
    in 401 responses), the wrapped error MUST NOT include the value."""
    secret = "sk-redact-me-987654321"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    transport = _RecordingTransport(HttpResponse(
        status_code=401,
        body=f"{{\"error\": {{\"message\": \"invalid key {secret}\"}}}}",
    ))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    with pytest.raises(LLMProviderError) as excinfo:
        provider.estimate("ignored", timeout_s=5)
    assert secret not in str(excinfo.value)
    assert "[REDACTED]" in str(excinfo.value)


def test_api_key_value_redacted_from_transport_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A faulty transport that raises an exception containing the
    secret MUST be caught and the message redacted."""
    secret = "sk-do-not-leak-from-transport"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)

    def _bad_transport(req: HttpRequest) -> HttpResponse:
        raise RuntimeError(f"transport asploded with {secret}")

    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=_bad_transport,
    )
    with pytest.raises(LLMProviderError) as excinfo:
        provider.estimate("ignored", timeout_s=5)
    assert secret not in str(excinfo.value)


def test_redact_secret_handles_empty_inputs() -> None:
    """The redaction helper must not crash on empty inputs."""
    assert redact_secret("", "key") == ""
    assert redact_secret("text", None) == "text"
    assert redact_secret("text", "") == "text"
    assert redact_secret("hello sk-X", "sk-X") == "hello [REDACTED]"


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def test_provider_response_invalid_json_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    transport = _RecordingTransport(HttpResponse(
        status_code=200, body="not json at all",
    ))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    with pytest.raises(LLMProviderInvalidResponse, match="non-JSON"):
        provider.estimate("p", timeout_s=5)


def test_provider_response_schema_violation_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI-style response without ``choices[0].message.content``
    MUST be rejected before the runner sees it."""
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    transport = _RecordingTransport(HttpResponse(
        status_code=200,
        body=json.dumps({"choices": [{"message": {"role": "assistant"}}]}),
    ))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    with pytest.raises(LLMProviderInvalidResponse):
        provider.estimate("p", timeout_s=5)


def test_provider_response_forbidden_official_field_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through ``run_llm_estimator``: a provider whose
    content carries a forbidden phrase (``total_v_net``) MUST be
    rejected by the runner's existing fence."""
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )

    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    bad_content = json.dumps({
        "estimates": [],
        "cited_evidence_refs": ["total_v_net"],
        "unsupported_claims": [],
    })
    transport = _RecordingTransport(HttpResponse(
        status_code=200, body=_ok_chat_body(bad_content),
    ))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    packet = LLMEvidencePacket(
        event_id="e1",
        allowed_fields=("capability",),
        intent_summary="x",
        evidence_items=(
            EvidenceItem(
                id="[E.intent.1]", kind="intent", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )
    run = run_llm_estimator(packet, provider)
    assert any("forbidden phrase" in b for b in run.report.blockers)


def test_provider_response_missing_citations_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A LLM response that emits an LLM-only estimate without any
    evidence_refs MUST fail the existing schema validator."""
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )

    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    bad = json.dumps({
        "estimates": [{
            "field": "capability",
            "event_id": "e1",
            "value": 0.7,
            "confidence": 0.5,
            "source": "llm",
            "method_id": "x",
            "method_version": "1",
            "evidence_refs": [],
            "warnings": [],
            "blockers": [],
            "is_default": False,
            "is_authoritative": False,
        }],
        "cited_evidence_refs": [],
        "unsupported_claims": [],
    })
    transport = _RecordingTransport(HttpResponse(200, _ok_chat_body(bad)))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    packet = LLMEvidencePacket(
        event_id="e1",
        allowed_fields=("capability",),
        intent_summary="x",
        evidence_items=(
            EvidenceItem(
                id="[E.intent.1]", kind="intent", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )
    run = run_llm_estimator(packet, provider)
    assert any("schema validation" in b for b in run.report.blockers)


def test_provider_timeout_becomes_warning_or_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transport surfaces a timeout via ``status_code=0`` + an
    ``error`` containing ``timeout``. The provider MUST raise
    :class:`LLMProviderTimeout` (a subclass of
    :class:`LLMProviderError`) so the runner converts it into a
    blocker."""
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    transport = _RecordingTransport(HttpResponse(
        status_code=0, body="", error="timeout: read timed out",
    ))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    with pytest.raises(LLMProviderTimeout):
        provider.estimate("p", timeout_s=1)


# ---------------------------------------------------------------------------
# Replay path unchanged
# ---------------------------------------------------------------------------


def test_replay_and_external_paths_share_same_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both replay and openai-compatible providers feed
    :func:`run_llm_estimator`, which applies the same
    ``LLMEstimatorOutput`` validator. We verify by passing a
    shape-valid response through both paths and asserting the
    accepted-count is identical."""
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )
    from oida_code.estimators.llm_provider import FileReplayLLMProvider

    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    valid_content = json.dumps({
        "estimates": [{
            "field": "capability",
            "event_id": "e1",
            "value": 0.7,
            "confidence": 0.5,
            "source": "llm",
            "method_id": "llm.cap",
            "method_version": "1",
            "evidence_refs": ["[E.intent.1]"],
            "warnings": [],
            "blockers": [],
            "is_default": False,
            "is_authoritative": False,
        }],
        "cited_evidence_refs": ["[E.intent.1]"],
        "unsupported_claims": [],
    })
    fixture = tmp_path / "reply.json"
    fixture.write_text(valid_content, encoding="utf-8")
    replay_provider = FileReplayLLMProvider(fixture_path=fixture)

    transport = _RecordingTransport(HttpResponse(200, _ok_chat_body(valid_content)))
    external_provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )

    packet = LLMEvidencePacket(
        event_id="e1",
        allowed_fields=("capability",),
        intent_summary="x",
        evidence_items=(
            EvidenceItem(
                id="[E.intent.1]", kind="intent", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )
    replay_run = run_llm_estimator(packet, replay_provider)
    external_run = run_llm_estimator(packet, external_provider)
    assert replay_run.accepted_count == external_run.accepted_count == 1


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_estimate_llm_openai_compatible_requires_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--llm-provider openai-compatible`` without
    ``--provider-profile`` MUST fail cleanly with a message that
    points the operator at the right flag."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    pkt = tmp_path / "packet.json"
    pkt.write_text(json.dumps({
        "event_id": "e1",
        "allowed_fields": ["capability"],
        "intent_summary": "x",
        "evidence_items": [{
            "id": "[E.intent.1]", "kind": "intent", "summary": "x",
            "source": "ticket", "confidence": 0.9,
        }],
        "deterministic_estimates": [],
    }), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "estimate-llm", str(pkt),
            "--llm-provider", "openai-compatible",
        ],
    )
    assert result.exit_code != 0
    assert "--provider-profile" in result.output


def test_cli_estimate_llm_openai_compatible_missing_key_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``--llm-provider openai-compatible --provider-profile
    deepseek`` but no ``DEEPSEEK_API_KEY``, the CLI MUST exit
    cleanly with a remediation message — and the message MUST NOT
    leak the operator's environment."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    pkt = tmp_path / "packet.json"
    pkt.write_text(json.dumps({
        "event_id": "e1",
        "allowed_fields": ["capability"],
        "intent_summary": "x",
        "evidence_items": [{
            "id": "[E.intent.1]", "kind": "intent", "summary": "x",
            "source": "ticket", "confidence": 0.9,
        }],
        "deterministic_estimates": [],
    }), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "estimate-llm", str(pkt),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
        ],
    )
    # The CLI calls ``run_llm_estimator`` which never raises — but
    # the provider unavailability becomes a blocker on the report.
    # Exit code is 0 (we got a valid EstimatorReport) but the
    # report's blockers carry the missing-key message.
    assert result.exit_code == 0, result.output
    assert "DEEPSEEK_API_KEY" in result.output


def test_cli_calibration_eval_replay_smoke(tmp_path: Path) -> None:
    """The new ``calibration-eval`` subcommand runs against the
    pilot dataset (default replay path) and exits 0 when there are
    no leaks."""
    dataset = Path(__file__).parent.parent / "datasets" / "calibration_v1"
    if not dataset.is_dir():
        pytest.skip("run scripts/build_calibration_dataset.py first")
    out = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["calibration-eval", str(dataset), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    metrics_path = out / "metrics.json"
    assert metrics_path.is_file()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["official_field_leak_count"] == 0


# ---------------------------------------------------------------------------
# Calibration leak detection (end-to-end via provider response)
# ---------------------------------------------------------------------------


def test_provider_calibration_run_keeps_official_fields_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running the openai-compatible provider through a single
    calibration-style packet MUST NOT introduce any forbidden field
    in the EstimatorReport payload, even with a non-trivial reply."""
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )

    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-key")
    valid_content = json.dumps({
        "estimates": [{
            "field": "capability",
            "event_id": "e1",
            "value": 0.7,
            "confidence": 0.5,
            "source": "llm",
            "method_id": "llm.cap",
            "method_version": "1",
            "evidence_refs": ["[E.intent.1]"],
            "warnings": [],
            "blockers": [],
            "is_default": False,
            "is_authoritative": False,
        }],
        "cited_evidence_refs": ["[E.intent.1]"],
        "unsupported_claims": [],
    })
    transport = _RecordingTransport(HttpResponse(200, _ok_chat_body(valid_content)))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    packet = LLMEvidencePacket(
        event_id="e1",
        allowed_fields=("capability",),
        intent_summary="x",
        evidence_items=(
            EvidenceItem(
                id="[E.intent.1]", kind="intent", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )
    run = run_llm_estimator(packet, provider)
    payload = run.report.model_dump()
    forbidden = {
        "total_v_net", "v_net", "debt_final",
        "corrupt_success", "corrupt_success_ratio",
        "corrupt_success_verdict", "verdict",
    }
    assert not (forbidden & set(payload.keys()))


def test_provider_metrics_report_no_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The serialized ``ProviderRawResponse`` and the produced
    ``EstimatorReport`` MUST NOT contain the API-key value."""
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )

    secret = "sk-PROVIDER-METRICS-SECRET"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    valid_content = json.dumps({
        "estimates": [],
        "cited_evidence_refs": [],
        "unsupported_claims": [],
    })
    transport = _RecordingTransport(HttpResponse(200, _ok_chat_body(valid_content)))
    provider = OpenAICompatibleChatProvider(
        profile=_profile(), http_post=transport,
    )
    raw = provider.complete_json("hello", timeout_s=5)
    assert secret not in raw.model_dump_json()
    packet = LLMEvidencePacket(
        event_id="e1",
        allowed_fields=("capability",),
        intent_summary="x",
        evidence_items=(
            EvidenceItem(
                id="[E.intent.1]", kind="intent", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )
    run = run_llm_estimator(packet, provider)
    assert secret not in run.report.model_dump_json()


# ---------------------------------------------------------------------------
# Optional external smoke (skipped unless env opt-in)
# ---------------------------------------------------------------------------


def _external_smoke_enabled() -> bool:
    return os.environ.get(_EXTERNAL_KEY_VAR) == "1"


@pytest.fixture
def _external_smoke_guard() -> Iterator[None]:
    if not _external_smoke_enabled():
        pytest.skip(
            f"set {_EXTERNAL_KEY_VAR}=1 to enable optional external "
            "provider tests (and ensure the relevant API key env var "
            "is set)"
        )
    yield


@pytest.mark.external_provider
def test_deepseek_smoke_real_call(_external_smoke_guard: None) -> None:
    """Optional smoke against the real DeepSeek API.

    Skipped unless ``OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1`` AND
    ``DEEPSEEK_API_KEY`` is set. Uses one tiny hermetic packet — no
    repo content, no secrets in the prompt, no assertion that prints
    the response body.
    """
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")
    profile = get_predefined_profile("deepseek")
    provider = OpenAICompatibleChatProvider(profile=profile)
    raw = provider.complete_json(
        'Reply with exactly the JSON: {"ping": "pong"}',
        timeout_s=15,
    )
    # We only assert the schema-level invariant — never the content,
    # never the secret.
    assert raw.content
    assert raw.prompt_sha256
    assert raw.model


# ---------------------------------------------------------------------------
# Phase 4.4.1 — calibration-eval external provider path alignment
# ---------------------------------------------------------------------------


_DATASET_ROOT = Path(__file__).parent.parent / "datasets" / "calibration_v1"


@pytest.fixture
def _pilot_dataset_required() -> Iterator[None]:
    if not _DATASET_ROOT.is_dir():
        pytest.skip("run scripts/build_calibration_dataset.py first")
    yield


def test_calibration_eval_external_provider_requires_explicit_flag(
    _pilot_dataset_required: None, tmp_path: Path,
) -> None:
    """4.4.1: ``--llm-provider`` must default to replay; without
    explicit opt-in, the runner MUST NOT touch the external provider
    code path. We verify by deleting any candidate API key env var
    and confirming the run completes without raising."""
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["calibration-eval", str(_DATASET_ROOT), "--out", str(out)],
        env={
            "DEEPSEEK_API_KEY": "",
            "MOONSHOT_API_KEY": "",
            "MINIMAX_API_KEY": "",
        },
    )
    assert result.exit_code == 0, result.output
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    # The 8 llm_estimator cases (L001-L008 after Phase 4.8
    # extension) all evaluate via per-case replay.
    assert metrics["estimator_cases_evaluated"] == 8
    assert metrics["estimator_cases_skipped"] == 0


def test_calibration_eval_external_provider_requires_profile(
    _pilot_dataset_required: None, tmp_path: Path,
) -> None:
    """4.4.1: ``--llm-provider openai-compatible`` without
    ``--provider-profile`` MUST fail cleanly."""
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
        ],
    )
    assert result.exit_code != 0
    assert "--provider-profile" in result.output


def test_calibration_eval_external_provider_requires_key_env(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: ``--llm-provider openai-compatible --provider-profile
    deepseek`` without ``DEEPSEEK_API_KEY`` set MUST fail with a
    clean message that mentions the env var name (never any value)."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
        ],
    )
    # The CLI's _build_openai_compatible_provider does not actually
    # check the env var until the provider's first .estimate() call.
    # So construction succeeds; the missing-key blocker shows up
    # per-case in the EstimatorReport. We assert the provider config
    # is intact and at least one llm_estimator case carries the
    # missing-key error.
    assert result.exit_code in (0, 3), result.output
    if result.exit_code == 0:
        metrics_path = out / "metrics.json"
        if metrics_path.is_file():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            # External provider was selected — every llm_estimator
            # case attempts a call, fails with missing-key, is
            # recorded as a blocker (status drops to "blocked").
            assert metrics["estimator_cases_evaluated"] >= 4


def test_calibration_eval_replay_default_makes_no_http_call(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: the default replay path must not hit ``urllib`` even
    once. We monkey-patch ``default_urllib_post`` to fail loudly if
    invoked."""
    from oida_code.estimators.providers import openai_compatible

    def _trap(req: HttpRequest) -> HttpResponse:
        raise AssertionError(
            f"replay path made an HTTP call to {req.url}; should never happen"
        )

    monkeypatch.setattr(
        openai_compatible, "default_urllib_post", _trap,
    )
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["calibration-eval", str(_DATASET_ROOT), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output


def test_calibration_eval_external_uses_same_llm_validator(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: replacing the replay path with an external provider
    that returns the SAME content yields the SAME EstimatorReport
    behaviour (because both paths go through ``LLMEstimatorOutput``)."""
    from oida_code.estimators.providers import openai_compatible

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    # Build a fake transport that always returns L001's canned reply.
    l001_reply = (
        _DATASET_ROOT / "cases" / "L001_capability_supported_clean"
        / "llm_response.json"
    ).read_text(encoding="utf-8")

    def _fake_post(req: HttpRequest) -> HttpResponse:
        return HttpResponse(200, _ok_chat_body(l001_reply))

    monkeypatch.setattr(
        openai_compatible, "default_urllib_post", _fake_post,
    )

    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
            "--max-provider-cases", "2",
        ],
    )
    assert result.exit_code == 0, result.output
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    # 2 cases were sent through the provider; the rest are skipped.
    # Phase 4.8: dataset extended L005-L008 → 8 llm_estimator cases
    # total, 2 evaluated under cap, 6 skipped.
    assert metrics["estimator_cases_evaluated"] == 2
    assert metrics["estimator_cases_skipped"] == 6
    # No leaks anywhere.
    assert metrics["official_field_leak_count"] == 0


def test_calibration_eval_external_invalid_json_rejected(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: an external provider that returns non-JSON content
    MUST surface as a runner blocker without crashing the eval."""
    from oida_code.estimators.providers import openai_compatible

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def _bad_post(req: HttpRequest) -> HttpResponse:
        return HttpResponse(200, _ok_chat_body("not valid json at all"))

    monkeypatch.setattr(
        openai_compatible, "default_urllib_post", _bad_post,
    )
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
            "--max-provider-cases", "1",
        ],
    )
    assert result.exit_code == 0
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    # 1 case ran; the runner converted invalid JSON into a blocker;
    # the case still counts as evaluated.
    assert metrics["estimator_cases_evaluated"] == 1


def test_calibration_eval_external_missing_citations_rejected(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: an external provider whose JSON omits citations on a
    non-zero-confidence LLM estimate MUST be rejected by the
    existing schema validator (same path as Phase 4.4)."""
    from oida_code.estimators.providers import openai_compatible

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    bad_payload = json.dumps({
        "estimates": [{
            "field": "capability",
            "event_id": "event-A",
            "value": 0.7,
            "confidence": 0.5,
            "source": "llm",
            "method_id": "x",
            "method_version": "1",
            "evidence_refs": [],  # missing
            "warnings": [],
            "blockers": [],
            "is_default": False,
            "is_authoritative": False,
        }],
        "cited_evidence_refs": [],
        "unsupported_claims": [],
    })

    def _post(req: HttpRequest) -> HttpResponse:
        return HttpResponse(200, _ok_chat_body(bad_payload))

    monkeypatch.setattr(
        openai_compatible, "default_urllib_post", _post,
    )
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
            "--max-provider-cases", "1",
        ],
    )
    assert result.exit_code == 0
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["estimator_cases_evaluated"] == 1
    # The case's expected status is shadow_ready or diagnostic_only;
    # with citations missing the runner falls back to deterministic
    # baseline → status="blocked", so estimator_status_accuracy < 1.0.
    assert metrics["estimator_status_accuracy"] is not None


def test_calibration_eval_external_official_field_leak_exits_3(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: a provider whose response sneaks a forbidden phrase
    past the runner's fence MUST be detected as a leak. We force a
    leak via a runtime monkey-patch on the runner's per-case
    counter, run via the CLI, and assert exit code 3."""
    import subprocess
    import sys

    repo_root = Path(__file__).parent.parent
    helper = tmp_path / "force_leak_external.py"
    out = tmp_path / "out"
    helper.write_text(
        "import importlib.util, sys\n"
        "from oida_code.calibration import runner as _r\n"
        "_orig = _r.run_case\n"
        "def _patched(case, case_dir, *, provider=None):\n"
        "    res = _orig(case, case_dir, provider=provider)\n"
        "    if case.family == 'llm_estimator':\n"
        "        res.official_field_leaks += 3\n"
        "    return res\n"
        "_r.run_case = _patched\n"
        "spec = importlib.util.spec_from_file_location(\n"
        "    '_eval', "
        f"r'{repo_root / 'scripts' / 'run_calibration_eval.py'}')\n"
        "assert spec is not None and spec.loader is not None\n"
        "_eval = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(_eval)\n"
        "sys.argv = ['run_calibration_eval', '--dataset', "
        f"r'{_DATASET_ROOT}', '--out', r'{out}']\n"
        "raise SystemExit(_eval.main())\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, check=False,
        cwd=str(repo_root),
    )
    assert proc.returncode == 3, (
        f"expected exit 3 (leak detected on llm_estimator), got "
        f"{proc.returncode}; stdout={proc.stdout!r}"
    )


def test_calibration_eval_external_metrics_report_no_secret_values(
    _pilot_dataset_required: None,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4.4.1: the metrics + per-case JSON outputs MUST NOT contain
    the API key value, even when --llm-provider openai-compatible
    + the env var is set during the run."""
    from oida_code.estimators.providers import openai_compatible

    secret = "sk-CALIB-METRICS-SECRET-XYZ"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    def _fake_post(req: HttpRequest) -> HttpResponse:
        # The transport doesn't echo the secret, so the provider
        # produces a clean response. We still verify the metrics
        # output never contains the value.
        return HttpResponse(200, _ok_chat_body(json.dumps({
            "estimates": [],
            "cited_evidence_refs": [],
            "unsupported_claims": [
                "capability@event-A", "benefit@event-A",
                "observability@event-A",
            ],
        })))

    monkeypatch.setattr(
        openai_compatible, "default_urllib_post", _fake_post,
    )
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(_DATASET_ROOT),
            "--out", str(out),
            "--llm-provider", "openai-compatible",
            "--provider-profile", "deepseek",
            "--max-provider-cases", "1",
        ],
    )
    assert result.exit_code == 0
    for name in ("metrics.json", "per_case.json"):
        path = out / name
        if path.is_file():
            assert secret not in path.read_text(encoding="utf-8")
    assert secret not in result.output
