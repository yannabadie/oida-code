"""Phase 4.1 (QA/A16.md, ADR-26) — verifier contract schemas.

Frozen Pydantic shapes consumed by every verifier provider and the
aggregator. Hard ADR-26 rules are enforced at the model level:

* No `V_net` / `debt_final` / `corrupt_success` / `verdict` field
  exists on any model.
* `VerifierClaim.is_authoritative` is pinned to ``Literal[False]``.
* Only seven `claim_type` values are allowed; promotion-flavoured
  phrases (`merge_safe`, `production_safe`, `bug_free`, etc.) are
  rejected at construction by the validator.
* `VerifierAggregationReport.authoritative` is pinned to
  ``Literal[False]`` so the report can never be re-cast as official.
* `VerifierToolCallSpec` exists so a verifier can DESCRIBE which
  tools it WOULD ask; **execution is Phase 4.2**, not 4.1.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VerifierClaimType = Literal[
    "capability_sufficient",
    "benefit_aligned",
    "observability_sufficient",
    "precondition_supported",
    "negative_path_covered",
    "repair_needed",
    "shadow_pressure_explained",
]
"""Phase 4.1 allowlist of diagnostic claim types.

Anything outside this Literal cannot reach a :class:`VerifierClaim`.
The set is deliberately narrow: the verifier may say "this claim
type is supported by these refs" but it CANNOT say "this code is
safe / merge-ready / bug-free / production-safe / security-verified"
(those are the rejected phrases below)."""


_FORBIDDEN_CLAIM_PHRASES: tuple[str, ...] = (
    "total_v_net",
    "v_net",
    "debt_final",
    "debt-final",
    "corrupt_success",
    "corrupt-success",
    "verdict",
    "official_v_net",
    "official_debt",
    "official_corrupt_success",
    "merge_safe",
    "production_safe",
    "bug_free",
    "security_verified",
)


def _has_forbidden_phrase(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _FORBIDDEN_CLAIM_PHRASES)


_VerifierClaimSource = Literal[
    "forward", "backward", "aggregator", "tool", "replay",
]


_VerifierEvidenceKind = Literal[
    "intent",
    "event",
    "precondition",
    "tool_finding",
    "test_result",
    "graph_edge",
    "trajectory",
    "repair_signal",
]


class VerifierClaim(BaseModel):
    """One diagnostic claim emitted by a forward / backward verifier.

    `is_authoritative` is pinned to ``Literal[False]`` — verifier
    claims can never become official, regardless of source.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    claim_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    claim_type: VerifierClaimType

    statement: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()

    source: _VerifierClaimSource
    is_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def _no_forbidden_phrases(self) -> VerifierClaim:
        for field_text in (self.statement, self.claim_id):
            if _has_forbidden_phrase(field_text):
                raise ValueError(
                    "VerifierClaim text references a forbidden official "
                    "phrase (V_net / debt_final / corrupt_success / "
                    "verdict / merge_safe / production_safe / bug_free / "
                    "security_verified). ADR-26 — verifier claims are "
                    "diagnostic only."
                )
        return self


class ForwardVerificationResult(BaseModel):
    """Output of the forward verifier (premises → conclusion).

    The forward agent answers: "Given these premises, which
    conclusions can I support?". It does NOT enumerate what would
    be required to support a hypothetical claim — that's the
    backward verifier's job.

    Phase 5.2 (ADR-37): the forward agent may also request that
    a deterministic tool be re-run via the local gateway through
    ``requested_tools``. Phase 4.1 replay fixtures predate the
    field, so the default is the empty tuple.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    event_id: str = Field(min_length=1)
    supported_claims: tuple[VerifierClaim, ...] = ()
    rejected_claims: tuple[VerifierClaim, ...] = ()
    missing_evidence_refs: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    requested_tools: tuple[VerifierToolCallSpec, ...] = ()


class BackwardRequirement(BaseModel):
    """Specifies the evidence kinds a claim WOULD need."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    claim_id: str = Field(min_length=1)
    required_evidence_kinds: tuple[_VerifierEvidenceKind, ...]
    satisfied_evidence_refs: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()


class BackwardVerificationResult(BaseModel):
    """Output of the backward verifier (claim → required evidence).

    Answers: "For this claim, which evidence kinds are necessary,
    and are they all present?".
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    event_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    requirement: BackwardRequirement
    necessary_conditions_met: bool
    warnings: tuple[str, ...] = ()


VerifierStatus = Literal[
    "blocked",
    "diagnostic_only",
    "verification_candidate",
]


class VerifierAggregationReport(BaseModel):
    """Final output of the verifier sub-system.

    `authoritative` is pinned to ``Literal[False]`` — even at status
    ``verification_candidate``, the report does NOT promote any
    estimate to official. Phase 4.2+ may add a corroboration loop;
    Phase 4.1 stops here.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    status: VerifierStatus
    accepted_claims: tuple[VerifierClaim, ...] = ()
    rejected_claims: tuple[VerifierClaim, ...] = ()
    unsupported_claims: tuple[VerifierClaim, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommendation: str = ""
    authoritative: Literal[False] = False


class VerifierToolCallSpec(BaseModel):
    """Phase 4.1 — describes which tools the verifier WOULD ask.

    **NOT executed** in Phase 4.1. The schema exists so a verifier can
    declare its intent (e.g. "I would re-run pytest scoped to
    src/app.py") and Phase 4.2's tool-grounded loop can pick the
    declarations up. ADR-26 explicitly forbids tool execution at the
    verifier layer in Phase 4.1.

    Phase 5.3 (ADR-38) adds the optional ``requested_by_claim_id``
    so the calibration runner can attribute a tool result to the
    claim it was asked to support.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool: Literal["ruff", "mypy", "pytest", "semgrep", "codeql"]
    purpose: str = Field(min_length=1, max_length=200)
    expected_evidence_kind: _VerifierEvidenceKind
    scope: tuple[str, ...] = ()
    requested_by_claim_id: str | None = None


__all__ = [
    "BackwardRequirement",
    "BackwardVerificationResult",
    "ForwardVerificationResult",
    "VerifierAggregationReport",
    "VerifierClaim",
    "VerifierClaimType",
    "VerifierStatus",
    "VerifierToolCallSpec",
]
