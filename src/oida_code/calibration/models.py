"""Phase 4.3-A (QA/A19.md, ADR-28) — calibration dataset schemas.

Frozen Pydantic types describing one calibration case + its expected
labels. Designed to **measure** estimator / verifier / tool-loop
behaviour on controlled cases — NOT to validate predictive performance
or unlock official OIDA fusion fields. ADR-22 + ADR-28 hold.

Key invariants enforced at the model level:

* ``code_outcome`` family REQUIRES an ``ExpectedCodeOutcome`` with at
  least one F2P test (per QA/A19.md §4.3-A "no F2P/P2P → must stay in
  claim_contract or shadow_pressure").
* ``ExpectedClaimLabel`` is one of three Pydantic-checked outcomes
  (``accepted`` / ``unsupported`` / ``rejected``); reasons are a strict
  Literal so the runner can branch on them deterministically.
* ``CalibrationProvenance`` is mandatory; ``contamination_risk`` ladders
  from ``synthetic`` (safest) to ``public_high`` (excluded from headline
  metrics by the runner).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CalibrationFamily = Literal[
    "claim_contract",
    "tool_grounded",
    "shadow_pressure",
    "code_outcome",
    "safety_adversarial",
    "llm_estimator",
]

ContaminationRisk = Literal[
    "synthetic", "private", "public_low", "public_high",
]

ClaimExpected = Literal["accepted", "unsupported", "rejected"]

ClaimReason = Literal[
    "supported_by_forward_backward",
    "missing_backward_requirement",
    "unknown_evidence_ref",
    "tool_contradiction",
    "forbidden_claim",
    "missing_citation",
    "prompt_injection",
    "confidence_cap_exceeded",
    "event_id_mismatch",
]

ToolResultExpected = Literal[
    "ok", "failed", "error", "timeout", "tool_missing", "blocked",
]

ShadowBucket = Literal["low", "medium", "high", "not_applicable"]


EstimateExpected = Literal["accepted", "rejected", "unsupported", "missing"]
"""Phase 4.4.1 — per-estimate ground-truth label.

* ``accepted``    — the LLM estimator produced this estimate; runner
                    accepted it after schema/citation/forbidden-phrase
                    checks.
* ``rejected``    — the runner dropped the estimate (cap breach,
                    forbidden phrase, contradicting tool, etc.).
* ``unsupported`` — listed in the response's ``unsupported_claims``.
* ``missing``     — the LLM did not emit this field at all (and the
                    deterministic baseline carries ``source="missing"``).
"""


EstimatorStatusExpected = Literal[
    "blocked", "diagnostic_only", "shadow_ready", "official_ready_candidate",
]
"""Phase 4.4.1 — expected :class:`EstimatorReport.status` for an
``llm_estimator`` family case."""


class ExpectedClaimLabel(BaseModel):
    """One ground-truth label for a single :class:`VerifierClaim`."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    claim_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    expected: ClaimExpected
    reason: ClaimReason
    required_evidence_refs: tuple[str, ...] = ()


class ExpectedToolResultLabel(BaseModel):
    """One ground-truth label for a single :class:`VerifierToolResult`."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    request_id: str = Field(min_length=1)
    tool: Literal["ruff", "mypy", "pytest", "semgrep", "codeql"]
    expected_status: ToolResultExpected
    expected_findings_min: int = Field(default=0, ge=0)
    expected_findings_max: int | None = Field(default=None, ge=0)
    expected_block_reason_substring: str | None = None


class ExpectedEstimateLabel(BaseModel):
    """Phase 4.4.1 — ground-truth label for one LLM estimate slot.

    ``min_value`` / ``max_value`` are optional bounds on the estimate's
    numeric ``value`` field. They guard against runs that produce a
    technically schema-valid estimate but with an absurd magnitude
    (e.g. a capability-low case where the LLM cites the right ref but
    still claims ``value=0.95``)."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    field: Literal[
        "capability", "benefit", "observability",
        "completion", "tests_pass", "operator_accept", "edge_confidence",
    ]
    event_id: str | None = None
    expected_status: EstimateExpected
    min_value: float | None = Field(default=None, ge=0.0, le=1.0)
    max_value: float | None = Field(default=None, ge=0.0, le=1.0)
    required_evidence_refs: tuple[str, ...] = ()


class ExpectedRepairBehavior(BaseModel):
    """Optional ground truth for repair-needed claims."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    must_be_diagnostic_only: bool = True
    required_evidence_kinds: tuple[str, ...] = ()


class ExpectedCodeOutcome(BaseModel):
    """SWE-bench-style F2P + P2P labels for ``code_outcome`` cases.

    F2P (fail-to-pass) tests verify the bug fix; P2P (pass-to-pass)
    tests verify the absence of regressions. ADR-28: this is the only
    pathway through which the calibration eval makes any executable
    claim about code behaviour.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    f2p_tests: tuple[str, ...]
    p2p_tests: tuple[str, ...] = ()
    expected_f2p_before: Literal["fail"] = "fail"
    expected_f2p_after: Literal["pass"] = "pass"
    expected_p2p_before: Literal["pass"] = "pass"
    expected_p2p_after: Literal["pass"] = "pass"
    stability_runs: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _f2p_required(self) -> ExpectedCodeOutcome:
        if not self.f2p_tests:
            raise ValueError(
                "ExpectedCodeOutcome requires at least one F2P test "
                "(ADR-28 §4.3-A: no F2P → case must stay in "
                "claim_contract or shadow_pressure, not code_outcome)."
            )
        return self


class CalibrationProvenance(BaseModel):
    """Anti-contamination metadata. Public benchmark cases are flagged
    so headline metrics can exclude them."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    source: Literal["synthetic", "hand_seeded", "private_trace", "public_repo"]
    created_by: Literal["human", "script", "mixed"]
    source_commit: str | None = None
    public_url: str | None = None
    contamination_notes: str = ""


class CalibrationCase(BaseModel):
    """One calibration case. Frozen, fully-typed, schema-checked.

    Family-specific invariants:

    * ``code_outcome`` REQUIRES ``expected_code_outcome``;
    * other families REJECT ``expected_code_outcome`` (kept null).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    case_id: str = Field(min_length=1)
    family: CalibrationFamily

    # Optional file references — relative to the case directory.
    repo_fixture: str | None = None
    request_path: str | None = None
    trace_path: str | None = None
    packet_path: str | None = None
    tool_policy_path: str | None = None
    tool_requests_path: str | None = None
    canned_tool_outputs_path: str | None = None
    forward_replay_path: str | None = None
    backward_replay_path: str | None = None
    # Phase 4.4.1 — for ``llm_estimator`` family cases, this is the
    # canned LLM JSON response replayed by FileReplayLLMProvider when
    # the operator hasn't opted in to a real provider.
    llm_response_path: str | None = None

    expected_claim_labels: tuple[ExpectedClaimLabel, ...] = ()
    expected_tool_results: tuple[ExpectedToolResultLabel, ...] = ()
    expected_shadow_bucket: ShadowBucket = "not_applicable"
    expected_repair_behavior: ExpectedRepairBehavior | None = None
    expected_code_outcome: ExpectedCodeOutcome | None = None
    # Phase 4.4.1 — ground truth for ``llm_estimator`` family cases.
    expected_estimator_status: EstimatorStatusExpected | None = None
    expected_estimates: tuple[ExpectedEstimateLabel, ...] = ()

    provenance: CalibrationProvenance
    contamination_risk: ContaminationRisk
    notes: str = ""

    @model_validator(mode="after")
    def _family_specific_invariants(self) -> CalibrationCase:
        if self.family == "code_outcome" and self.expected_code_outcome is None:
            raise ValueError(
                f"case {self.case_id}: family='code_outcome' requires "
                "expected_code_outcome (ADR-28 §4.3-A)."
            )
        if self.family != "code_outcome" and self.expected_code_outcome is not None:
            raise ValueError(
                f"case {self.case_id}: only family='code_outcome' may set "
                "expected_code_outcome."
            )
        if self.family == "shadow_pressure" and self.expected_shadow_bucket == "not_applicable":
            raise ValueError(
                f"case {self.case_id}: family='shadow_pressure' requires "
                "expected_shadow_bucket ∈ {low, medium, high}."
            )
        if self.family == "tool_grounded" and not self.expected_tool_results:
            raise ValueError(
                f"case {self.case_id}: family='tool_grounded' requires at "
                "least one expected_tool_results entry."
            )
        # Phase 4.4.1 — llm_estimator family invariants.
        if self.family == "llm_estimator":
            if self.packet_path is None:
                raise ValueError(
                    f"case {self.case_id}: family='llm_estimator' "
                    "requires packet_path (LLMEvidencePacket JSON)."
                )
            if self.expected_estimator_status is None:
                raise ValueError(
                    f"case {self.case_id}: family='llm_estimator' "
                    "requires expected_estimator_status."
                )
        if self.family != "llm_estimator" and (
            self.expected_estimator_status is not None
            or self.expected_estimates
            or self.llm_response_path is not None
        ):
            raise ValueError(
                f"case {self.case_id}: only family='llm_estimator' may set "
                "expected_estimator_status / expected_estimates / "
                "llm_response_path."
            )
        return self


class CalibrationManifest(BaseModel):
    """``datasets/calibration_v1/manifest.json`` payload."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    dataset_id: str
    version: str
    created_at: str
    families: dict[CalibrationFamily, int]
    case_count: int = Field(ge=0)
    public_claims_allowed: Literal[False] = False
    official_vnet_allowed: Literal[False] = False
    notes: str = ""


__all__ = [
    "CalibrationCase",
    "CalibrationFamily",
    "CalibrationManifest",
    "CalibrationProvenance",
    "ClaimExpected",
    "ClaimReason",
    "ContaminationRisk",
    "EstimateExpected",
    "EstimatorStatusExpected",
    "ExpectedClaimLabel",
    "ExpectedCodeOutcome",
    "ExpectedEstimateLabel",
    "ExpectedRepairBehavior",
    "ExpectedToolResultLabel",
    "ShadowBucket",
    "ToolResultExpected",
]
