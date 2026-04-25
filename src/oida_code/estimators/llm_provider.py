"""Phase 4.0-A (QA/A15.md, ADR-25) — LLM provider abstraction.

Three providers ship with the dry-run; **no external API call happens
by default**. The production CLI's only path that exercises an LLM is
behind an explicit ``--llm-provider`` flag whose default is ``"replay"``.

Providers:

* :class:`FakeLLMProvider`         — deterministic, tests-only.
  Emits a fixed JSON shape derived from the prompt's ``allowed_fields``;
  never touches network, env vars, or the filesystem.
* :class:`FileReplayLLMProvider`   — reads a fixture JSON file from
  disk and returns its body. Used by hermetic-dry-run fixtures and by
  the CLI's ``--llm-provider replay --llm-response-fixture <path>``
  invocation.
* :class:`OptionalExternalLLMProvider` — only triggered when an
  explicit ``--llm-provider external`` flag plus a documented env var
  is set. **Never imports the vendor SDK at module load.** When the
  env var is missing, ``estimate()`` raises a clean
  :class:`LLMProviderUnavailable` carrying a remediation message.

ADR-25 hard rules captured here:

* No vendor SDK import at module load.
* No HTTP at module load (no ``requests``, no ``httpx`` imported here).
* No secret value is logged or returned in :class:`LLMProviderError`
  messages.
* Tests use Fake or FileReplay only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Base exception for provider-level failures.

    Subclasses wrap concrete failure modes; messages MUST NOT contain
    secret values (API keys, tokens, full request bodies). Stack
    traces from the underlying client are dropped on purpose so the
    public log surface stays clean.
    """


class LLMProviderUnavailable(LLMProviderError):
    """The provider cannot be used right now.

    Examples: missing env var, missing fixture file, vendor SDK not
    installed. The runner converts this into a blocker on the
    :class:`~oida_code.estimators.contracts.EstimatorReport` rather
    than crashing the pipeline.
    """


class LLMProviderTimeout(LLMProviderError):
    """The provider took longer than the budget."""


class LLMProviderInvalidResponse(LLMProviderError):
    """The provider returned a non-string / unreadable payload."""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for an LLM estimator backend.

    Implementations MUST:

    * be deterministic in tests (Fake / FileReplay);
    * never raise raw vendor exceptions — wrap them in
      :class:`LLMProviderError` subclasses;
    * never log or return the prompt or any secret value.

    The ``estimate`` method returns a JSON string the runner can
    parse with :func:`json.loads`. Returning a non-string (e.g.
    ``None``) is a contract violation and the runner converts it
    into a blocker.
    """

    def estimate(self, prompt: str, *, timeout_s: int) -> str:
        ...


# ---------------------------------------------------------------------------
# Fake provider (tests only)
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMProvider:
    """Deterministic fixed-shape provider used by unit tests.

    Returns a hand-crafted JSON whose ``estimates`` array carries one
    LLM-only :class:`SignalEstimate` per ``allowed_fields`` entry
    (decoded from the prompt's ``allowed_fields`` JSON block). Confidence
    is 0.5 (well under the 0.6 cap), value is 0.7, evidence_refs cite
    the first evidence id present in the prompt. The provider does NOT
    parse the prompt body for instructions — it only extracts the
    ``allowed_fields`` and ``evidence_ids`` JSON arrays.
    """

    name: str = "fake"

    def estimate(self, prompt: str, *, timeout_s: int) -> str:
        del timeout_s  # FakeProvider is synchronous and instantaneous
        allowed = _extract_json_array(prompt, "ALLOWED_FIELDS")
        evidence_ids = _extract_json_array(prompt, "EVIDENCE_IDS")
        event_id = _extract_string(prompt, "EVENT_ID") or "event-unknown"
        cited = evidence_ids[:1] if evidence_ids else []
        out_estimates = [
            {
                "field": field,
                "event_id": event_id,
                "value": 0.7,
                "confidence": 0.5,
                "source": "llm",
                "method_id": f"fake.{field}",
                "method_version": "phase4.0",
                "evidence_refs": cited,
                "warnings": (),
                "blockers": (),
                "is_default": False,
                "is_authoritative": False,
            }
            for field in allowed
        ]
        return json.dumps({
            "estimates": out_estimates,
            "cited_evidence_refs": cited,
            "unsupported_claims": [],
        })


# ---------------------------------------------------------------------------
# File replay provider (fixtures)
# ---------------------------------------------------------------------------


@dataclass
class FileReplayLLMProvider:
    """Reads a fixed JSON response from disk and returns it verbatim.

    The fixture must already match :class:`LLMEstimatorOutput`'s
    schema; the runner validates it on parse. Use this to record an
    LLM response once (manually) and replay it deterministically in
    tests + CI.
    """

    fixture_path: Path
    name: str = "replay"

    def estimate(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s  # replay does not use the prompt
        if not self.fixture_path.is_file():
            raise LLMProviderUnavailable(
                f"replay fixture not found: {self.fixture_path}"
            )
        try:
            return self.fixture_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LLMProviderUnavailable(
                f"replay fixture unreadable: {self.fixture_path}"
            ) from exc


# ---------------------------------------------------------------------------
# Optional external provider (opt-in, no SDK at module load)
# ---------------------------------------------------------------------------


_EXTERNAL_ENV_VAR = "OIDA_LLM_API_KEY"
_EXTERNAL_BASE_URL_VAR = "OIDA_LLM_BASE_URL"


@dataclass
class OptionalExternalLLMProvider:
    """Only used when the integrator explicitly opts in.

    The constructor reads the env var lazily — module import does NOT
    require the vendor SDK or any network reach. The first
    :meth:`estimate` call validates that the env var is set and that
    the optional vendor SDK is installable; on failure it raises
    :class:`LLMProviderUnavailable` with a remediation message that
    NEVER quotes the env var's value.

    The implementation is deliberately a stub: in Phase 4.0 we only
    ship the contract and the failure path. A real vendor binding
    (Qwen, Claude, etc.) is Phase 4.2+ work.
    """

    env_var: str = _EXTERNAL_ENV_VAR
    base_url_var: str = _EXTERNAL_BASE_URL_VAR
    name: str = "external"

    def estimate(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s
        if self.env_var not in os.environ:
            raise LLMProviderUnavailable(
                f"OptionalExternalLLMProvider requires the {self.env_var} "
                "env var. Phase 4.0 ships only the contract; no external "
                "API is called by default. Set the env var AND pass "
                "--llm-provider external to opt in."
            )
        # ADR-25 forbids implementing the real call here. We surface
        # an explicit, clean refusal so the integrator knows this is a
        # contract stub rather than a silent failure.
        raise LLMProviderUnavailable(
            "OptionalExternalLLMProvider is a Phase 4.0 contract stub. "
            "Set up a vendor binding via a Phase 4.2 follow-up before "
            "wiring real calls."
        )


# ---------------------------------------------------------------------------
# Provider factory — used by the CLI / runner
# ---------------------------------------------------------------------------


def build_provider(
    name: str,
    *,
    fixture_path: Path | None = None,
) -> LLMProvider:
    """Return a provider instance for the chosen ``name``.

    Defaults to ``"replay"`` because that's the only deterministic
    path that exercises end-to-end JSON parsing without an LLM call.
    """
    if name == "fake":
        return FakeLLMProvider()
    if name == "replay":
        if fixture_path is None:
            raise LLMProviderUnavailable(
                "replay provider requires --llm-response-fixture <path>"
            )
        return FileReplayLLMProvider(fixture_path=fixture_path)
    if name == "external":
        return OptionalExternalLLMProvider()
    raise LLMProviderUnavailable(
        f"unknown LLM provider {name!r}; choose fake, replay, or external"
    )


# ---------------------------------------------------------------------------
# Internal helpers — strict, no eval, no exec
# ---------------------------------------------------------------------------


def _extract_json_array(prompt: str, marker: str) -> list[str]:
    """Find ``MARKER: [..]`` in the prompt and parse the JSON array.

    Used by FakeLLMProvider only. Uses :class:`json.JSONDecoder.raw_decode`
    to avoid bracket-balancing issues when the array contains string
    items like ``"[E.intent.1]"`` whose own brackets would confuse a
    naive ``find("[")``/``find("]")`` scan. Returns an empty list on
    any parsing failure — Fake never raises.
    """
    idx = prompt.find(f"{marker}:")
    if idx < 0:
        return []
    rest = prompt[idx + len(marker) + 1:].lstrip()
    if not rest.startswith("["):
        return []
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(rest)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(x) for x in parsed]
    return []


def _extract_string(prompt: str, marker: str) -> str | None:
    idx = prompt.find(f"{marker}:")
    if idx < 0:
        return None
    rest = prompt[idx + len(marker) + 1:].lstrip()
    if not rest:
        return None
    end = rest.find("\n")
    return rest[:end] if end >= 0 else rest


__all__ = [
    "FakeLLMProvider",
    "FileReplayLLMProvider",
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderInvalidResponse",
    "LLMProviderTimeout",
    "LLMProviderUnavailable",
    "OptionalExternalLLMProvider",
    "build_provider",
]
