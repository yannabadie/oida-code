"""Phase 4.1 (QA/A16.md, ADR-26) — forward/backward verifier contract.

Sub-modules:

* :mod:`oida_code.verifier.contracts` — frozen Pydantic schemas
  ``VerifierClaim``, ``ForwardVerificationResult``,
  ``BackwardRequirement``, ``BackwardVerificationResult``,
  ``VerifierAggregationReport``, ``VerifierToolCallSpec``.
* :mod:`oida_code.verifier.aggregator` — pure aggregation logic that
  combines forward + backward + deterministic-tool evidence.
* :mod:`oida_code.verifier.replay` — Fake / FileReplay / Optional
  external verifier providers. **No external API call by default.**
* :mod:`oida_code.verifier.forward_backward` — high-level entry point
  that drives a packet through the two providers and runs the
  aggregator.

Phase 4.1 is **contractual**. Tool execution is Phase 4.2 — the
:class:`VerifierToolCallSpec` schema exists so a verifier can describe
what it WOULD ask, but no tool is executed here.
"""

from oida_code.verifier.aggregator import aggregate_verification
from oida_code.verifier.contracts import (
    BackwardRequirement,
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierAggregationReport,
    VerifierClaim,
    VerifierClaimType,
    VerifierToolCallSpec,
)
from oida_code.verifier.forward_backward import (
    VerifierRun,
    run_verifier,
)
from oida_code.verifier.replay import (
    FakeVerifierProvider,
    FileReplayVerifierProvider,
    OptionalExternalVerifierProvider,
    VerifierProvider,
    VerifierProviderError,
    VerifierProviderUnavailable,
    build_verifier_provider,
)

__all__ = [
    "BackwardRequirement",
    "BackwardVerificationResult",
    "FakeVerifierProvider",
    "FileReplayVerifierProvider",
    "ForwardVerificationResult",
    "OptionalExternalVerifierProvider",
    "VerifierAggregationReport",
    "VerifierClaim",
    "VerifierClaimType",
    "VerifierProvider",
    "VerifierProviderError",
    "VerifierProviderUnavailable",
    "VerifierRun",
    "VerifierToolCallSpec",
    "aggregate_verification",
    "build_verifier_provider",
    "run_verifier",
]
