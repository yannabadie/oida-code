"""Phase 4.1 (QA/A16.md, ADR-26) — verifier providers.

Mirrors the Phase 4.0 LLM provider abstraction but for the
forward/backward verifier sub-system. **No external API call by
default.** Tests rely on Fake / FileReplay only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


class VerifierProviderError(Exception):
    """Base exception for verifier-provider failures.

    Messages MUST NOT contain secret values; the runner converts
    these into blockers on the
    :class:`~oida_code.verifier.contracts.VerifierAggregationReport`
    rather than crashing.
    """


class VerifierProviderUnavailable(VerifierProviderError):
    """The provider cannot be used right now."""


@runtime_checkable
class VerifierProvider(Protocol):
    """Minimal interface for a verifier backend.

    Returns a JSON string the runner can parse with :func:`json.loads`.
    Implementations MUST be deterministic in tests and never raise raw
    vendor exceptions.
    """

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        ...


# ---------------------------------------------------------------------------
# Fake (tests only)
# ---------------------------------------------------------------------------


@dataclass
class FakeVerifierProvider:
    """Echo a fixed empty result. Used by unit tests that do not
    require a specific provider response."""

    name: str = "fake"

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s
        return json.dumps({
            "supported_claims": [],
            "rejected_claims": [],
            "missing_evidence_refs": [],
            "contradictions": [],
            "warnings": [],
        })


# ---------------------------------------------------------------------------
# File replay (fixtures)
# ---------------------------------------------------------------------------


@dataclass
class FileReplayVerifierProvider:
    """Reads a fixed JSON response from disk and returns it verbatim."""

    fixture_path: Path
    name: str = "replay"

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s
        if not self.fixture_path.is_file():
            raise VerifierProviderUnavailable(
                f"replay fixture not found: {self.fixture_path}"
            )
        try:
            return self.fixture_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise VerifierProviderUnavailable(
                f"replay fixture unreadable: {self.fixture_path}"
            ) from exc


# ---------------------------------------------------------------------------
# Optional external (opt-in stub)
# ---------------------------------------------------------------------------


_EXTERNAL_ENV_VAR = "OIDA_VERIFIER_API_KEY"


@dataclass
class OptionalExternalVerifierProvider:
    """Phase 4.1 contract stub. **No external API call in 4.1.**

    The constructor is lazy — module import does NOT require any
    vendor SDK. The first :meth:`verify` call validates the env var
    is set and then refuses to proceed because the real binding is
    a Phase 4.2 follow-up. Error messages NEVER echo the env var's
    value.
    """

    env_var: str = _EXTERNAL_ENV_VAR
    name: str = "external"

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s
        if self.env_var not in os.environ:
            raise VerifierProviderUnavailable(
                f"OptionalExternalVerifierProvider requires the "
                f"{self.env_var} env var. Phase 4.1 ships only the "
                "contract; no external API is called by default. Set "
                "the env var AND pass --provider external to opt in."
            )
        raise VerifierProviderUnavailable(
            "OptionalExternalVerifierProvider is a Phase 4.1 contract "
            "stub. Set up a vendor binding via a Phase 4.2 follow-up "
            "before wiring real calls."
        )


def build_verifier_provider(
    name: str,
    *,
    fixture_path: Path | None = None,
) -> VerifierProvider:
    """Return a verifier provider for the chosen ``name``."""
    if name == "fake":
        return FakeVerifierProvider()
    if name == "replay":
        if fixture_path is None:
            raise VerifierProviderUnavailable(
                "replay verifier requires a fixture path"
            )
        return FileReplayVerifierProvider(fixture_path=fixture_path)
    if name == "external":
        return OptionalExternalVerifierProvider()
    raise VerifierProviderUnavailable(
        f"unknown verifier provider {name!r}; choose fake, replay, or external"
    )


__all__ = [
    "FakeVerifierProvider",
    "FileReplayVerifierProvider",
    "OptionalExternalVerifierProvider",
    "VerifierProvider",
    "VerifierProviderError",
    "VerifierProviderUnavailable",
    "build_verifier_provider",
]
