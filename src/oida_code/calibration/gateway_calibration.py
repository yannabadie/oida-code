"""Phase 5.3 (QA/A30.md, ADR-38) — gateway-grounded verifier
calibration runner.
Phase 5.4 (QA/A31.md, ADR-39) — real-execution upgrade.
Phase 5.5 (QA/A32.md, ADR-40) — runnable holdout expansion +
true macro-F1 + diagnostic-only recommendation lock.

The runner pairs each holdout case's
:class:`GatewayHoldoutExpected` labels with two actual runs:

* ``baseline`` — :func:`run_verifier` (Phase 4.1) with no
  gateway. Forward + backward replays only; no tool execution.
* ``gateway``  — :func:`run_gateway_grounded_verifier``
  (Phase 5.2) routed through the local deterministic gateway.

Phase 5.4 replaces the stub metric emitters with real
execution: each case's directory is loaded, the providers are
constructed from the per-case replay JSON files, and the two
modes are run against the same packet. The runner falls back
to the stub for cases that don't ship the full file set
(criterion #8 — the public runnable subset must contain ZERO
``insufficient_fixture`` rows; private/example slates can use
the fallback).

Phase 5.5 replaces the symmetric-difference proxy macro-F1
(which was numerically equal to F1 but did not expose
precision and recall separately) with a real per-class
confusion matrix tracking TP/FP/FN for accepted, unsupported,
and rejected. ``claim_macro_f1`` is now the mean of three
per-class F1 scores, and ``decision_summary.json`` carries
``promotion_allowed: false`` as a STRUCTURAL pin — Phase 5.5
decides the next phase, not the action's default.

It computes per-mode metrics and a ``gateway_delta`` and emits:

* ``baseline_metrics.json``      — per-case + macro metrics (no
  gateway).
* ``gateway_metrics.json``       — per-case + macro metrics
  (gateway-grounded).
* ``delta_metrics.json``         — gateway minus baseline.
* ``decision_summary.json``      — Phase 5.5 recommendation
  (``integrate_opt_in_candidate`` / ``revise_prompts`` /
  ``revise_labels`` / ``revise_tool_policy`` /
  ``insufficient_data``). The recommendation is an INPUT for
  the operator, never a production threshold;
  ``promotion_allowed`` is hardcoded ``False``.
* ``failure_analysis.md``        — per-case classification +
  proposed action + three "proposed change" flags
  (``label_change_proposed``,
  ``tool_request_policy_change_proposed``,
  ``prompt_change_proposed``). **NO automatic label / policy /
  prompt mutation.**
* ``artifact_manifest.json``     — SHA256 hashes of all written
  artifacts so a future run can prove integrity.

ADR-38 + ADR-39 + ADR-40 + QA/A30 + QA/A31 + QA/A32 hard rules
enforced here:

* The runner NEVER writes anywhere under ``datasets/``.
* Per-case audit logs land under ``<out_dir>/audit/<case_id>/``
  to keep calibration runs from polluting the operator's
  ``.oida/tool-gateway/audit/`` namespace. Concrete example::

      .oida/gateway-calibration/audit/tool_needed_then_supported/2026-04-26/pytest.jsonl

* No external provider, no MCP, no remote-procedure-call
  runtime, no network. The whole module imports from existing
  replay-only paths.
* The runner asserts ``official_field_leak_count == 0`` in
  every emitted JSON; any leak is itself a recorded failure
  classification, never a status promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FAILURE_CLASSIFICATIONS: tuple[str, ...] = (
    "label_too_strict",
    "gateway_bug",
    "tool_adapter_bug",
    "aggregator_bug",
    "citation_gap",
    "tool_request_policy_gap",
    "insufficient_fixture",
    "expected_behavior_changed",
    # Phase 5.5 (QA/A32 §5.5-D) — added only because the
    # expanded slate actually exercises these paths.
    "tool_budget_gap",
    "uncertainty_preserved",
)

_RECOMMENDATION_LITERAL: tuple[str, ...] = (
    "integrate_opt_in_candidate",
    "revise_prompts",
    "revise_labels",
    "revise_tool_policy",
    "insufficient_data",
)


_ManifestMode = Literal["replay", "fake"]


_DELTA_POSITIVE_THRESHOLD = 0.05
_DELTA_NEGATIVE_THRESHOLD = -0.05
_RUNNABLE_THRESHOLD = 12


class CalibrationCaseEntry(BaseModel):
    """One row in ``manifest.json``."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    case_id: str = Field(min_length=1)
    family: Literal[
        "claim_contract",
        "gateway_grounded",
        "code_outcome",
        "safety_adversarial",
    ]
    directory: str = Field(min_length=1)
    provenance: Literal[
        "synthetic",
        "private_trace",
        "private_repo",
        "public_low",
        "public_high",
    ]
    contamination_risk: Literal[
        "synthetic", "private", "public_low", "public_high",
    ]
    expected_delta: Literal[
        "improves", "same", "worse_expected", "not_applicable",
    ]
    notes: str = ""


class GatewayCalibrationManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    manifest_version: str = Field(min_length=1)
    description: str = ""
    headline_metrics_exclude: tuple[
        Literal[
            "synthetic", "private", "public_low", "public_high",
        ],
        ...,
    ] = ()
    cases: tuple[CalibrationCaseEntry, ...]


@dataclass
class _PerClassConfusion:
    """Phase 5.5 (QA/A32 §5.5.0-B) — per-class confusion
    counters. A claim_id is a TP for class C iff it appears in
    BOTH the expected_C and actual_C sets, FP for class C iff
    it appears in actual_C but not expected_C (predicted as C
    but should have been a different class), FN for class C
    iff it appears in expected_C but not actual_C (should have
    been C but the verifier classified it elsewhere).

    Phase 5.4 used a single ``correct``/``wrong`` count
    (correct = TP, wrong = FP+FN as a symmetric difference);
    that produced a NUMERICALLY correct F1 via the
    ``2*TP/(2*TP + FP + FN)`` identity but did NOT expose
    precision and recall to the operator. Phase 5.5 keeps the
    numerical agreement and adds the structural P/R surface."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float:
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)

    def recall(self) -> float:
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def correct(self) -> int:
        """Phase 5.4 backward-compat alias — same as ``tp``."""
        return self.tp

    @property
    def wrong(self) -> int:
        """Phase 5.4 backward-compat alias — same as
        ``fp + fn``; this is what Phase 5.4 stored as
        ``accepted_wrong`` etc. via the symmetric difference."""
        return self.fp + self.fn


@dataclass
class _PerModeMetrics:
    """Lightweight per-mode metric bundle used internally by
    the runner. The serialised form lives in the JSON files.

    Phase 5.5 — the three classification buckets are now full
    confusion counters (TP/FP/FN). The Phase 5.4 ``*_correct``
    / ``*_wrong`` keys remain in :meth:`to_json` for backward
    compatibility (they are derived properties on
    :class:`_PerClassConfusion`)."""

    cases_evaluated: int = 0
    accepted: _PerClassConfusion = field(
        default_factory=_PerClassConfusion,
    )
    unsupported: _PerClassConfusion = field(
        default_factory=_PerClassConfusion,
    )
    rejected: _PerClassConfusion = field(
        default_factory=_PerClassConfusion,
    )
    official_field_leak_count: int = 0
    # Phase 5.4 additions (unchanged).
    fresh_tool_ref_citations: int = 0
    accepted_claims_total: int = 0
    tool_contradiction_rejections: int = 0
    tool_contradiction_opportunities: int = 0
    evidence_refs_cited: int = 0
    evidence_refs_required: int = 0
    evidence_refs_required_satisfied: int = 0

    def claim_accept_accuracy(self) -> float:
        # Same shape as Phase 5.4 — TP / (TP + FP + FN) for the
        # accepted bucket. This is the Jaccard similarity of the
        # accepted set, not strict accuracy.
        total = (
            self.accepted.tp + self.accepted.fp + self.accepted.fn
        )
        if total == 0:
            return 0.0
        return self.accepted.tp / total

    def claim_macro_f1(self) -> float:
        """Phase 5.5 — true macro-F1 = mean of per-class F1.

        Numerically equal to the Phase 5.4 proxy when FP and FN
        are reported as a single ``wrong`` count
        (``2*TP/(2*TP + FP + FN) ≡ 2*P*R/(P+R)``). The change is
        structural: precision and recall are now exposed
        independently, so the report can flag asymmetric
        precision/recall splits that the symmetric proxy
        hid."""
        return (
            self.accepted.f1()
            + self.unsupported.f1()
            + self.rejected.f1()
        ) / 3

    def fresh_tool_ref_citation_rate(self) -> float:
        if self.accepted_claims_total == 0:
            return 0.0
        return (
            self.fresh_tool_ref_citations / self.accepted_claims_total
        )

    def tool_contradiction_rejection_rate(self) -> float:
        if self.tool_contradiction_opportunities == 0:
            return 0.0
        return (
            self.tool_contradiction_rejections
            / self.tool_contradiction_opportunities
        )

    def evidence_ref_precision(self) -> float:
        if self.evidence_refs_cited == 0:
            return 0.0
        return (
            self.evidence_refs_required_satisfied
            / self.evidence_refs_cited
        )

    def evidence_ref_recall(self) -> float:
        if self.evidence_refs_required == 0:
            return 0.0
        return (
            self.evidence_refs_required_satisfied
            / self.evidence_refs_required
        )

    def to_json(self) -> dict[str, int | float]:
        payload: dict[str, int | float] = {
            "cases_evaluated": self.cases_evaluated,
            # Phase 5.4 backward-compat keys (derived).
            "accepted_correct": self.accepted.correct,
            "accepted_wrong": self.accepted.wrong,
            "unsupported_correct": self.unsupported.correct,
            "unsupported_wrong": self.unsupported.wrong,
            "rejected_correct": self.rejected.correct,
            "rejected_wrong": self.rejected.wrong,
            # Phase 5.5 — explicit per-class confusion +
            # precision/recall/f1.
            "accepted_tp": self.accepted.tp,
            "accepted_fp": self.accepted.fp,
            "accepted_fn": self.accepted.fn,
            "accepted_precision": round(
                self.accepted.precision(), 4,
            ),
            "accepted_recall": round(self.accepted.recall(), 4),
            "accepted_f1": round(self.accepted.f1(), 4),
            "unsupported_tp": self.unsupported.tp,
            "unsupported_fp": self.unsupported.fp,
            "unsupported_fn": self.unsupported.fn,
            "unsupported_precision": round(
                self.unsupported.precision(), 4,
            ),
            "unsupported_recall": round(
                self.unsupported.recall(), 4,
            ),
            "unsupported_f1": round(self.unsupported.f1(), 4),
            "rejected_tp": self.rejected.tp,
            "rejected_fp": self.rejected.fp,
            "rejected_fn": self.rejected.fn,
            "rejected_precision": round(
                self.rejected.precision(), 4,
            ),
            "rejected_recall": round(self.rejected.recall(), 4),
            "rejected_f1": round(self.rejected.f1(), 4),
            # Aggregate metrics.
            "claim_accept_accuracy": round(
                self.claim_accept_accuracy(), 4,
            ),
            "claim_macro_f1": round(self.claim_macro_f1(), 4),
            "fresh_tool_ref_citation_rate": round(
                self.fresh_tool_ref_citation_rate(), 4,
            ),
            "tool_contradiction_rejection_rate": round(
                self.tool_contradiction_rejection_rate(), 4,
            ),
            "evidence_ref_precision": round(
                self.evidence_ref_precision(), 4,
            ),
            "evidence_ref_recall": round(
                self.evidence_ref_recall(), 4,
            ),
            "official_field_leak_count": self.official_field_leak_count,
        }
        return payload


@dataclass
class _CaseClassification:
    case_id: str
    family: str
    expected_delta: str
    actual_delta: str
    baseline_result: str
    gateway_result: str
    classification: str
    root_cause: str
    proposed_action: str
    # Phase 5.4 — single proposal flag.
    label_change_proposed: bool = False
    # Phase 5.5 (QA/A32 §5.5-D) — two more proposal flags. The
    # runner ONLY proposes; no automatic mutation.
    tool_request_policy_change_proposed: bool = False
    prompt_change_proposed: bool = False


@dataclass
class _CaseRunResult:
    """Bundle returned by ``_run_one_case`` covering both modes."""

    baseline_runnable: bool = False
    gateway_runnable: bool = False
    baseline_outcome: str = "not_run"
    gateway_outcome: str = "not_run"
    classifications: list[_CaseClassification] = field(
        default_factory=list,
    )
    baseline_official_leak: bool = False
    gateway_official_leak: bool = False


def load_manifest(manifest_path: Path) -> GatewayCalibrationManifest:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return GatewayCalibrationManifest.model_validate(raw)


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes(),
    ).hexdigest()


_REQUIRED_GATEWAY_CASE_FILES: tuple[str, ...] = (
    "packet.json",
    "baseline_forward.json",
    "baseline_backward.json",
    "gateway_pass1_forward.json",
    "gateway_pass1_backward.json",
    "gateway_pass2_forward.json",
    "gateway_pass2_backward.json",
    "tool_policy.json",
    "gateway_definitions.json",
    "approved_tools.json",
    "expected.json",
)


def _case_has_full_fixture(case_dir: Path) -> bool:
    """Phase 5.4 — a case is "runnable" only if every required
    file is present. Optional files (executor.json, README.md,
    repo/) are not in the gating set."""
    return all(
        (case_dir / name).is_file()
        for name in _REQUIRED_GATEWAY_CASE_FILES
    )


def _run_one_case(
    case: CalibrationCaseEntry,
    case_dir: Path,
    *,
    baseline_metrics: _PerModeMetrics,
    gateway_metrics: _PerModeMetrics,
    audit_dir_root: Path,
) -> _CaseRunResult:
    """Drive both baseline and gateway modes for one case.

    Imports happen inside the function so the calibration
    module can be loaded without dragging the whole verifier
    runtime into the import graph for trivial introspection.
    """
    from oida_code.calibration.gateway_holdout import (
        GatewayHoldoutExpected,
    )
    from oida_code.estimators.llm_prompt import LLMEvidencePacket
    from oida_code.verifier.forward_backward import run_verifier
    from oida_code.verifier.gateway_loop import (
        run_gateway_grounded_verifier,
    )
    from oida_code.verifier.replay import (
        FileReplayVerifierProvider,
    )
    from oida_code.verifier.tool_gateway.contracts import (
        GatewayToolDefinition,
        ToolAdmissionRegistry,
    )
    from oida_code.verifier.tool_gateway.gateway import (
        LocalDeterministicToolGateway,
    )
    from oida_code.verifier.tools.adapters import (
        ExecutionContext,
        ExecutionOutcome,
    )
    from oida_code.verifier.tools.contracts import ToolPolicy

    out = _CaseRunResult()

    if not _case_has_full_fixture(case_dir):
        out.classifications.append(
            _CaseClassification(
                case_id=case.case_id,
                family=case.family,
                expected_delta=case.expected_delta,
                actual_delta="not_run",
                baseline_result="not_run",
                gateway_result="not_run",
                classification="insufficient_fixture",
                root_cause=(
                    "case directory missing one or more of the "
                    f"{len(_REQUIRED_GATEWAY_CASE_FILES)} required "
                    "fixture files (packet.json + replays + "
                    "policy + admissions + expected)"
                ),
                proposed_action=(
                    "commit the missing files under "
                    f"{case_dir} or remove the entry from the "
                    "manifest"
                ),
                label_change_proposed=False,
            ),
        )
        return out

    expected = GatewayHoldoutExpected.model_validate_json(
        (case_dir / "expected.json").read_text(encoding="utf-8"),
    )
    packet = LLMEvidencePacket.model_validate_json(
        (case_dir / "packet.json").read_text(encoding="utf-8"),
    )
    raw_tool_policy = ToolPolicy.model_validate_json(
        (case_dir / "tool_policy.json").read_text(encoding="utf-8"),
    )
    # Per-case tool_policy.json carries a placeholder
    # repo_root (typically ``.``); rebind to the actual case
    # directory so the sandbox's ``_is_under`` check has a
    # real, existing path. The case_dir itself is the right
    # anchor: every scope entry in a calibration fixture is
    # interpreted relative to the case directory.
    tool_policy = raw_tool_policy.model_copy(
        update={"repo_root": case_dir.resolve()},
    )
    registry = ToolAdmissionRegistry.model_validate_json(
        (case_dir / "approved_tools.json").read_text(encoding="utf-8"),
    )
    raw_definitions = json.loads(
        (case_dir / "gateway_definitions.json").read_text(
            encoding="utf-8",
        ),
    )
    # The runner's gateway-definitions map is keyed by the
    # ``ToolName`` Literal; the JSON keys are plain strings
    # validated by ``GatewayToolDefinition``'s schema. The
    # cast tells mypy that operator-supplied keys must already
    # match the Literal (the schema enforced this on the
    # values; runtime callers pass through a typed signature).
    from typing import cast

    from oida_code.verifier.tools.contracts import ToolName

    gateway_definitions = cast(
        "dict[ToolName, GatewayToolDefinition]",
        {
            name: GatewayToolDefinition.model_validate(payload)
            for name, payload in raw_definitions.items()
        },
    )

    # Optional canned executor outcome. When absent, the
    # default executor is a no-op that returns rc=0 with empty
    # stdout (so the gateway hits the adapter's "no findings"
    # path and produces no evidence).
    #
    # Phase 5.5 — ``executor.json`` may carry a ``by_tool`` key
    # mapping tool names to per-tool outcomes. This lets a
    # single case exercise multiple adapters with distinct
    # results (e.g. ``multi_tool_static_then_test`` runs ruff +
    # mypy + pytest in pass-1 and needs the static checkers to
    # come back ``ok`` while pytest comes back with a finding).
    executor_path = case_dir / "executor.json"
    default_outcome: ExecutionOutcome | None = None
    by_tool_outcomes: dict[str, ExecutionOutcome] = {}
    if executor_path.is_file():
        raw_executor = json.loads(
            executor_path.read_text(encoding="utf-8"),
        )
        if "by_tool" in raw_executor:
            for tool_name, tool_outcome in raw_executor[
                "by_tool"
            ].items():
                by_tool_outcomes[tool_name] = ExecutionOutcome(
                    returncode=tool_outcome.get("returncode"),
                    stdout=tool_outcome.get("stdout", ""),
                    stderr=tool_outcome.get("stderr", ""),
                    timed_out=tool_outcome.get("timed_out", False),
                    runtime_ms=tool_outcome.get("runtime_ms", 0),
                )
        else:
            default_outcome = ExecutionOutcome(
                returncode=raw_executor.get("returncode"),
                stdout=raw_executor.get("stdout", ""),
                stderr=raw_executor.get("stderr", ""),
                timed_out=raw_executor.get("timed_out", False),
                runtime_ms=raw_executor.get("runtime_ms", 0),
            )

    def _executor(ctx: ExecutionContext) -> ExecutionOutcome:
        if by_tool_outcomes:
            keyed = by_tool_outcomes.get(ctx.binary)
            if keyed is not None:
                return keyed
        if default_outcome is not None:
            return default_outcome
        return ExecutionOutcome(
            returncode=0, stdout="", stderr="",
            timed_out=False, runtime_ms=1,
        )

    # ---- baseline ----
    baseline_run = run_verifier(
        packet,
        FileReplayVerifierProvider(
            fixture_path=case_dir / "baseline_forward.json",
        ),
        FileReplayVerifierProvider(
            fixture_path=case_dir / "baseline_backward.json",
        ),
    )
    out.baseline_runnable = True
    out.baseline_outcome = _summarise_outcome(baseline_run.report)
    out.baseline_official_leak = _has_official_leak(
        baseline_run.report,
    )

    # ---- gateway ----
    audit_dir = audit_dir_root / case.case_id
    gateway = LocalDeterministicToolGateway(executor=_executor)
    # Phase 5.5 — wire ``tool_policy.max_tool_calls`` through
    # to the gateway loop so the per-case budget acts as the
    # cap. The Phase 5.4 default (5) is still used when the
    # policy doesn't constrain it further.
    gateway_run = run_gateway_grounded_verifier(
        packet,
        forward_pass1=FileReplayVerifierProvider(
            fixture_path=case_dir / "gateway_pass1_forward.json",
        ),
        backward_pass1=FileReplayVerifierProvider(
            fixture_path=case_dir / "gateway_pass1_backward.json",
        ),
        forward_pass2=FileReplayVerifierProvider(
            fixture_path=case_dir / "gateway_pass2_forward.json",
        ),
        backward_pass2=FileReplayVerifierProvider(
            fixture_path=case_dir / "gateway_pass2_backward.json",
        ),
        gateway=gateway,
        tool_policy=tool_policy,
        admission_registry=registry,
        gateway_definitions=gateway_definitions,
        audit_log_dir=audit_dir,
        max_tool_calls=tool_policy.max_tool_calls,
    )
    out.gateway_runnable = True
    out.gateway_outcome = _summarise_outcome(gateway_run.report)
    out.gateway_official_leak = _has_official_leak(
        gateway_run.report,
    )

    # ---- update per-mode counts ----
    _update_metrics(
        baseline_metrics,
        actual=baseline_run.report,
        expected=expected.expected_baseline,
        required_tool_refs=expected.required_tool_evidence_refs,
        official_leak=out.baseline_official_leak,
    )
    _update_metrics(
        gateway_metrics,
        actual=gateway_run.report,
        expected=expected.expected_gateway,
        required_tool_refs=expected.required_tool_evidence_refs,
        official_leak=out.gateway_official_leak,
        enriched_evidence_refs=gateway_run.enriched_evidence_refs,
    )

    # ---- per-case classification ----
    actual_delta = _classify_actual_delta(
        baseline_outcome=out.baseline_outcome,
        gateway_outcome=out.gateway_outcome,
    )
    # Phase 5.5 — the classifier can detect
    # uncertainty_preserved / tool_budget_gap when the
    # corresponding code paths were exercised.
    pass1_forward_raw = json.loads(
        (case_dir / "gateway_pass1_forward.json").read_text(
            encoding="utf-8",
        ),
    )
    pass1_requested_tools_count = len(
        pass1_forward_raw.get("requested_tools", []),
    )
    classification = _classify_case(
        expected=expected,
        actual_baseline=baseline_run.report,
        actual_gateway=gateway_run.report,
        expected_delta=case.expected_delta,
        actual_delta=actual_delta,
        gateway_tool_results=tuple(gateway_run.tool_results),
        pass1_requested_tools_count=pass1_requested_tools_count,
    )
    out.classifications.append(
        _CaseClassification(
            case_id=case.case_id,
            family=case.family,
            expected_delta=case.expected_delta,
            actual_delta=actual_delta,
            baseline_result=out.baseline_outcome,
            gateway_result=out.gateway_outcome,
            classification=classification.classification,
            root_cause=classification.root_cause,
            proposed_action=classification.proposed_action,
            label_change_proposed=(
                classification.label_change_proposed
            ),
            tool_request_policy_change_proposed=(
                classification.tool_request_policy_change_proposed
            ),
            prompt_change_proposed=(
                classification.prompt_change_proposed
            ),
        ),
    )

    return out


def _summarise_outcome(report: object) -> str:
    """Compress an aggregation report to a one-line label."""
    accepted = getattr(report, "accepted_claims", ())
    rejected = getattr(report, "rejected_claims", ())
    unsupported = getattr(report, "unsupported_claims", ())
    status = getattr(report, "status", "?")
    return (
        f"status={status} "
        f"accepted={len(accepted)} "
        f"rejected={len(rejected)} "
        f"unsupported={len(unsupported)}"
    )


def _has_official_leak(report: object) -> bool:
    """Phase 5.4 — assert an emitted report does NOT mention
    forbidden official phrases. The aggregator already rejects
    these at construction time; this is a belt-and-braces
    check on the dumped JSON."""
    forbidden = (
        "total_v_net",
        "debt_final",
        "corrupt_success",
        "official_v_net",
        "merge_safe",
        "production_safe",
        "bug_free",
        "security_verified",
    )
    body = json.dumps(
        getattr(report, "model_dump", lambda: {})(), default=str,
    ).lower()
    return any(token in body for token in forbidden)


def _update_metrics(
    metrics: _PerModeMetrics,
    *,
    actual: object,
    expected: object,
    required_tool_refs: tuple[str, ...],
    official_leak: bool,
    enriched_evidence_refs: tuple[str, ...] = (),
) -> None:
    metrics.cases_evaluated += 1
    if official_leak:
        metrics.official_field_leak_count += 1

    expected_accepted = set(
        getattr(expected, "accepted_claim_ids", ()),
    )
    expected_unsupported = set(
        getattr(expected, "unsupported_claim_ids", ()),
    )
    expected_rejected = set(
        getattr(expected, "rejected_claim_ids", ()),
    )

    actual_accepted_claims = list(
        getattr(actual, "accepted_claims", ()),
    )
    actual_unsupported_claims = list(
        getattr(actual, "unsupported_claims", ()),
    )
    actual_rejected_claims = list(
        getattr(actual, "rejected_claims", ()),
    )
    actual_accepted = {c.claim_id for c in actual_accepted_claims}
    actual_unsupported = {
        c.claim_id for c in actual_unsupported_claims
    }
    actual_rejected = {c.claim_id for c in actual_rejected_claims}

    # Phase 5.5 — explicit per-class confusion counters. For
    # class C: TP = expected_C ∩ actual_C, FP = actual_C only,
    # FN = expected_C only. The earlier symmetric-difference
    # form was numerically equivalent to FP + FN (so the proxy
    # F1 matched the true F1) but did not surface precision
    # and recall separately.
    metrics.accepted.tp += len(expected_accepted & actual_accepted)
    metrics.accepted.fp += len(actual_accepted - expected_accepted)
    metrics.accepted.fn += len(expected_accepted - actual_accepted)
    metrics.unsupported.tp += len(
        expected_unsupported & actual_unsupported,
    )
    metrics.unsupported.fp += len(
        actual_unsupported - expected_unsupported,
    )
    metrics.unsupported.fn += len(
        expected_unsupported - actual_unsupported,
    )
    metrics.rejected.tp += len(expected_rejected & actual_rejected)
    metrics.rejected.fp += len(actual_rejected - expected_rejected)
    metrics.rejected.fn += len(expected_rejected - actual_rejected)

    metrics.accepted_claims_total += len(actual_accepted_claims)
    enriched_set = set(enriched_evidence_refs)
    for claim in actual_accepted_claims:
        refs = set(getattr(claim, "evidence_refs", ()))
        if enriched_set & refs:
            metrics.fresh_tool_ref_citations += 1

    # Tool-contradiction rejection accounting: when the case
    # documents required_tool_evidence_refs, the gateway is
    # expected to either cite them OR reject claims that
    # contradicted them.
    if required_tool_refs:
        metrics.tool_contradiction_opportunities += 1
        if expected_rejected and (
            expected_rejected & actual_rejected
        ):
            metrics.tool_contradiction_rejections += 1

    # Evidence-ref precision/recall accounting against the
    # case-level required_tool_evidence_refs target.
    cited_refs: set[str] = set()
    for claim in actual_accepted_claims:
        cited_refs.update(getattr(claim, "evidence_refs", ()))
    metrics.evidence_refs_cited += len(cited_refs)
    metrics.evidence_refs_required += len(required_tool_refs)
    metrics.evidence_refs_required_satisfied += len(
        cited_refs & set(required_tool_refs),
    )


def _classify_actual_delta(
    *, baseline_outcome: str, gateway_outcome: str,
) -> str:
    if baseline_outcome == gateway_outcome:
        return "same"
    # Heuristic: if gateway has FEWER accepted claims than
    # baseline OR a stricter status, the delta direction is
    # "stricter" (which can be either improves or worse_expected
    # depending on the case label).
    return "different"


@dataclass
class _ClassificationResult:
    """Phase 5.5 — bundle returned by :func:`_classify_case`.

    Carries the four classification fields plus the three
    proposal booleans. ``label_change_proposed`` /
    ``tool_request_policy_change_proposed`` /
    ``prompt_change_proposed`` are HINTS only; the runner
    NEVER mutates labels, policy, or prompts."""

    classification: str
    root_cause: str
    proposed_action: str
    label_change_proposed: bool = False
    tool_request_policy_change_proposed: bool = False
    prompt_change_proposed: bool = False


def _classify_case(
    *,
    expected: object,
    actual_baseline: object,
    actual_gateway: object,
    expected_delta: str,
    actual_delta: str,
    gateway_tool_results: tuple[object, ...] = (),
    pass1_requested_tools_count: int = 0,
) -> _ClassificationResult:
    """Return a :class:`_ClassificationResult` describing what
    the actual baseline + gateway outcomes say about the case.

    Phase 5.5 — when both modes match expected, the classifier
    can still UPGRADE the row to ``uncertainty_preserved`` (a
    tool_missing or timeout was correctly absorbed as
    uncertainty rather than rejected as code failure) or
    ``tool_budget_gap`` (the gateway loop's budget cap fired
    on a duplicate / wasteful request stream). These two
    classifications are documented in the legend AND actually
    emitted by the runner when the corresponding code paths
    were exercised."""

    expected_baseline_accepted = set(
        getattr(getattr(expected, "expected_baseline", None),
                "accepted_claim_ids", ()),
    )
    expected_gateway_accepted = set(
        getattr(getattr(expected, "expected_gateway", None),
                "accepted_claim_ids", ()),
    )
    actual_baseline_accepted = {
        c.claim_id for c in getattr(actual_baseline, "accepted_claims", ())
    }
    actual_gateway_accepted = {
        c.claim_id for c in getattr(actual_gateway, "accepted_claims", ())
    }

    baseline_match = (
        actual_baseline_accepted == expected_baseline_accepted
    )
    gateway_match = (
        actual_gateway_accepted == expected_gateway_accepted
    )

    # Phase 5.5 — detect uncertainty_preserved AND tool_budget_gap
    # signals BEFORE falling back to expected_behavior_changed.
    has_uncertainty_status = any(
        getattr(r, "status", None) in ("tool_missing", "timeout")
        for r in gateway_tool_results
    )
    budget_capped = (
        pass1_requested_tools_count > 0
        and len(gateway_tool_results) < pass1_requested_tools_count
    )

    if baseline_match and gateway_match:
        if has_uncertainty_status:
            return _ClassificationResult(
                classification="uncertainty_preserved",
                root_cause=(
                    "gateway encountered a tool_missing or "
                    "timeout result; Phase 5.2.1-B enforcer "
                    "demoted the requested-but-uncited claim "
                    "to unsupported (uncertainty preserved, "
                    "NOT rejected as code failure)"
                ),
                proposed_action=(
                    "no action required; case demonstrates "
                    "correct uncertainty handling"
                ),
            )
        if budget_capped:
            return _ClassificationResult(
                classification="tool_budget_gap",
                root_cause=(
                    f"forward requested {pass1_requested_tools_count} "
                    f"tool calls but the gateway loop ran "
                    f"{len(gateway_tool_results)} (budget cap "
                    "via tool_policy.max_tool_calls)"
                ),
                proposed_action=(
                    "no action required; case demonstrates "
                    "the cap fires and audit log is bounded"
                ),
            )
        return _ClassificationResult(
            classification="expected_behavior_changed",
            root_cause="actual outcomes match expected on both modes",
            proposed_action=(
                "no action required; case demonstrates the "
                "expected behaviour"
            ),
        )

    # Only baseline diverges → the LLM-replay layer is at
    # fault, not the gateway.
    if not baseline_match and gateway_match:
        return _ClassificationResult(
            classification="aggregator_bug",
            root_cause=(
                "baseline mode produced a different verdict than "
                "the operator labelled; the gateway side matches "
                "— investigate the no-gateway aggregator path"
            ),
            proposed_action=(
                "review run_verifier replay handling for this case"
            ),
            prompt_change_proposed=True,
        )

    # Only gateway diverges → either the gateway loop, the
    # tool adapter, or the citation rule produced an
    # unexpected result.
    if baseline_match and not gateway_match:
        return _ClassificationResult(
            classification="gateway_bug",
            root_cause=(
                "gateway mode produced a different verdict than "
                "the operator labelled; the baseline side matches"
            ),
            proposed_action=(
                "review run_gateway_grounded_verifier flow "
                "(admission, fingerprint, citation rule, "
                "requested-tool-evidence enforcer)"
            ),
            tool_request_policy_change_proposed=True,
        )

    # Both diverge → the labels themselves may be miscalibrated.
    return _ClassificationResult(
        classification="label_too_strict",
        root_cause=(
            "both modes diverged from expected; investigate label"
        ),
        proposed_action=(
            "review the operator-supplied expected.json; if the "
            "labels turn out to be too strict, propose a label "
            "change but DO NOT mutate it automatically"
        ),
        label_change_proposed=True,
    )


def _emit_failure_analysis(
    rows: list[_CaseClassification], path: Path,
) -> None:
    """Phase 5.5 — Markdown failure-analysis table.

    Phase 5.5 (QA/A32 §5.5-D) extends the Phase 5.4 table with
    two more proposal columns
    (``tool_request_policy_change_proposed``,
    ``prompt_change_proposed``) plus two new classification
    rows in the legend (``tool_budget_gap``,
    ``uncertainty_preserved``)."""
    legend_lines = [
        "| Classification | Meaning |",
        "|---|---|",
        (
            "| `label_too_strict` | Operator label rejected an "
            "outcome that turned out to be sound on inspection |"
        ),
        (
            "| `gateway_bug` | Gateway routing or admission "
            "behaviour diverged from spec |"
        ),
        (
            "| `tool_adapter_bug` | A specific deterministic "
            "tool adapter produced wrong evidence |"
        ),
        (
            "| `aggregator_bug` | The verifier aggregator's "
            "rule fired in an unintended way |"
        ),
        (
            "| `citation_gap` | Pass-2 forward failed to cite "
            "available tool refs (anti-injection or prompt "
            "design issue) |"
        ),
        (
            "| `tool_request_policy_gap` | Forward asked for a "
            "tool that was unavailable, blocked, or produced no "
            "citable evidence |"
        ),
        (
            "| `insufficient_fixture` | The replay fixture was "
            "underspecified relative to the label |"
        ),
        (
            "| `expected_behavior_changed` | The product "
            "intentionally changed; label needs operator update "
            "(propose, never auto-mutate) |"
        ),
        (
            "| `tool_budget_gap` | Pass-1 requested a duplicate "
            "or wasteful tool call; the budget cap fired and "
            "audit log is clear |"
        ),
        (
            "| `uncertainty_preserved` | Tool missing or timed "
            "out; gateway preserved the uncertainty (claim "
            "remains unsupported, NOT rejected as code failure) |"
        ),
    ]

    table_header = (
        "| case_id | family | expected_delta | actual_delta "
        "| baseline_result | gateway_result | classification "
        "| root_cause | proposed_action | label_change_proposed "
        "| tool_request_policy_change_proposed "
        "| prompt_change_proposed |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    table_rows = [
        (
            f"| `{r.case_id}` | {r.family} | {r.expected_delta} "
            f"| {r.actual_delta} | {r.baseline_result} "
            f"| {r.gateway_result} | `{r.classification}` "
            f"| {r.root_cause} | {r.proposed_action} "
            f"| {str(r.label_change_proposed).lower()} "
            f"| {str(r.tool_request_policy_change_proposed).lower()} "
            f"| {str(r.prompt_change_proposed).lower()} |"
        )
        for r in rows
    ]

    body = "\n".join([
        "# Phase 5.3 / 5.4 / 5.5 — gateway calibration failure analysis",
        "",
        "Per QA/A30 §5.3-E + QA/A31 §5.4-D + QA/A32 §5.5-D.",
        "Every row is a per-case PROPOSAL. Labels, tool-request",
        "policies, and prompts are NEVER mutated automatically;",
        "any change MUST be a human review followed by an",
        "explicit commit. The three `*_change_proposed` booleans",
        "are hints, not instructions.",
        "",
        "## Classification legend",
        "",
        *legend_lines,
        "",
        "## Per-case rows",
        "",
        table_header,
        *(table_rows or [
            "| _no rows_ | — | — | — | — | — | — | — | — | — | — | — |",
        ]),
        "",
    ])
    path.write_text(body, encoding="utf-8")


def _decide_recommendation(
    *,
    cases_runnable: int,
    cases_insufficient_fixture: int,
    official_leak_count: int,
    gateway_delta_macro_f1: float,
    gateway_delta_tool_contradiction: float,
    gateway_delta_evidence_precision: float,
    has_critical_gateway_bug: bool,
) -> str:
    """Phase 5.5 (QA/A32 §5.5-C) decision rules.

    Order matches the QA/A32 specification:

    1. ``official_field_leak_count > 0`` → ``revise_tool_policy``.
    2. ``cases_runnable < 12`` → ``insufficient_data``.
    3. macro-F1 positive AND tool-contradiction non-negative
       AND evidence-ref precision non-negative AND no critical
       gateway bug → ``integrate_opt_in_candidate``.
    4. macro-F1 negative → ``revise_labels``.
    5. otherwise → ``revise_prompts``.

    The macro-F1 delta is the TRUE per-class F1 from
    :class:`_PerClassConfusion`, not the Phase 5.4 symmetric
    proxy (the values are numerically equal in expectation;
    the change is structural — see :class:`_PerClassConfusion`
    docstring).

    These rules are operator hints — they choose the next
    phase, NOT a production threshold."""
    if official_leak_count > 0:
        return "revise_tool_policy"
    if cases_runnable < _RUNNABLE_THRESHOLD:
        return "insufficient_data"
    if (
        gateway_delta_macro_f1 > _DELTA_POSITIVE_THRESHOLD
        and gateway_delta_tool_contradiction >= 0
        and gateway_delta_evidence_precision >= 0
        and not has_critical_gateway_bug
    ):
        return "integrate_opt_in_candidate"
    if gateway_delta_macro_f1 < _DELTA_NEGATIVE_THRESHOLD:
        return "revise_labels"
    return "revise_prompts"


def _emit_decision_summary(
    *,
    out_dir: Path,
    cases_runnable: int,
    cases_insufficient_fixture: int,
    baseline_metrics: _PerModeMetrics,
    gateway_metrics: _PerModeMetrics,
    case_classifications: list[_CaseClassification],
) -> None:
    """Write ``decision_summary.json`` per QA/A31 §5.4-C."""
    baseline_payload = baseline_metrics.to_json()
    gateway_payload = gateway_metrics.to_json()

    delta_accept_acc = (
        gateway_payload["claim_accept_accuracy"]
        - baseline_payload["claim_accept_accuracy"]
    )
    delta_macro_f1 = (
        gateway_payload["claim_macro_f1"]
        - baseline_payload["claim_macro_f1"]
    )
    delta_evidence_precision = (
        gateway_payload["evidence_ref_precision"]
        - baseline_payload["evidence_ref_precision"]
    )
    delta_evidence_recall = (
        gateway_payload["evidence_ref_recall"]
        - baseline_payload["evidence_ref_recall"]
    )
    delta_contradiction = (
        gateway_payload["tool_contradiction_rejection_rate"]
        - baseline_payload["tool_contradiction_rejection_rate"]
    )

    leak_count = (
        baseline_metrics.official_field_leak_count
        + gateway_metrics.official_field_leak_count
    )

    improves = sum(
        1 for c in case_classifications
        if c.expected_delta == "improves"
        and c.actual_delta != "not_run"
    )
    same = sum(
        1 for c in case_classifications
        if c.expected_delta == "same"
        and c.actual_delta != "not_run"
    )
    worse = sum(
        1 for c in case_classifications
        if c.expected_delta == "worse_expected"
        and c.actual_delta != "not_run"
    )

    has_critical_gateway_bug = any(
        c.classification == "gateway_bug"
        for c in case_classifications
    )
    recommendation = _decide_recommendation(
        cases_runnable=cases_runnable,
        cases_insufficient_fixture=cases_insufficient_fixture,
        official_leak_count=leak_count,
        gateway_delta_macro_f1=delta_macro_f1,
        gateway_delta_tool_contradiction=delta_contradiction,
        gateway_delta_evidence_precision=delta_evidence_precision,
        has_critical_gateway_bug=has_critical_gateway_bug,
    )

    payload = {
        "cases_runnable": cases_runnable,
        "cases_insufficient_fixture": cases_insufficient_fixture,
        "gateway_improves_count": improves,
        "gateway_same_count": same,
        "gateway_worse_count": worse,
        "claim_accept_accuracy_delta": round(delta_accept_acc, 4),
        "claim_macro_f1_delta": round(delta_macro_f1, 4),
        "evidence_ref_precision_delta": round(
            delta_evidence_precision, 4,
        ),
        "evidence_ref_recall_delta": round(
            delta_evidence_recall, 4,
        ),
        "tool_contradiction_rejection_rate_delta": round(
            delta_contradiction, 4,
        ),
        "fresh_tool_ref_citation_rate": gateway_payload[
            "fresh_tool_ref_citation_rate"
        ],
        "official_field_leak_count": leak_count,
        "recommendation": recommendation,
        "recommendation_diagnostic_only": True,
        # Phase 5.5 (QA/A32 §5.5.0-C + §5.5-C) — STRUCTURAL
        # pin. Hardcoded ``False`` regardless of recommendation.
        # Phase 5.5 decides the next phase, NOT the action's
        # default. Even if the recommendation is
        # ``integrate_opt_in_candidate``, integration must
        # happen in a SUBSEQUENT phase under explicit review.
        "promotion_allowed": False,
        "reserved": (
            "Phase 5.5 recommendations are operator-facing "
            "hints. They are NOT production thresholds and do "
            "NOT promote any score to official total_v_net / "
            "debt_final / corrupt_success. promotion_allowed "
            "is hardcoded False."
        ),
    }
    (out_dir / "decision_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _emit_artifact_manifest(out_dir: Path) -> None:
    """SHA256-hash every artifact except the manifest itself
    (chicken-and-egg)."""
    files: dict[str, dict[str, object]] = {}
    payload: dict[str, object] = {
        "phase": "5.4",
        "scheme": "calibration_v1.0",
        "files": files,
    }
    for entry in sorted(out_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name == "artifact_manifest.json":
            continue
        files[entry.name] = {
            "sha256": _sha256_path(entry),
            "size_bytes": entry.stat().st_size,
        }
    out = out_dir / "artifact_manifest.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_calibration(
    *,
    manifest_path: Path,
    out_dir: Path,
    mode: _ManifestMode = "replay",
) -> None:
    """Execute the gateway calibration.

    Phase 5.4 (ADR-39): the runner now actually executes
    each case's baseline and gateway modes when the case
    directory carries the full required-fixture set
    (:data:`_REQUIRED_GATEWAY_CASE_FILES`). Cases without the
    full set fall back to the `insufficient_fixture`
    classification so an example/private slate manifest still
    produces the five artifacts.
    """
    if mode != "replay":
        raise ValueError(
            "Phase 5.3/5.4 calibration runner only supports "
            f"mode='replay' (got {mode!r}). External providers "
            "stay opt-in via the existing Phase 4.4.1 binders "
            "and never reach this script."
        )

    manifest = load_manifest(manifest_path)
    dataset_root = manifest_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_dir_root = out_dir / "audit"

    baseline = _PerModeMetrics()
    gateway = _PerModeMetrics()
    classifications: list[_CaseClassification] = []
    cases_runnable = 0
    cases_insufficient_fixture = 0

    for case in manifest.cases:
        case_dir = dataset_root / case.directory
        case_result = _run_one_case(
            case,
            case_dir,
            baseline_metrics=baseline,
            gateway_metrics=gateway,
            audit_dir_root=audit_dir_root,
        )
        classifications.extend(case_result.classifications)
        if case_result.baseline_runnable and case_result.gateway_runnable:
            cases_runnable += 1
        else:
            cases_insufficient_fixture += 1

    baseline_payload = baseline.to_json()
    gateway_payload = gateway.to_json()
    delta_payload: dict[str, object] = {
        "manifest_version": manifest.manifest_version,
        "cases_in_manifest": len(manifest.cases),
        "cases_runnable": cases_runnable,
        "cases_insufficient_fixture": cases_insufficient_fixture,
        "delta_diagnostic_only": True,
        "headline_metrics_exclude": list(
            manifest.headline_metrics_exclude,
        ),
        "metrics": {
            key: {
                "baseline": baseline_payload.get(key),
                "gateway": gateway_payload.get(key),
                "delta": (
                    (gateway_payload.get(key) or 0)
                    - (baseline_payload.get(key) or 0)
                )
                if isinstance(
                    baseline_payload.get(key), int | float,
                ) and isinstance(
                    gateway_payload.get(key), int | float,
                ) else None,
            }
            for key in baseline_payload
        },
        "reserved": (
            "gateway_delta is diagnostic only — Phase 5.3/5.4 "
            "does NOT promote any score to official total_v_net "
            "/ debt_final / corrupt_success."
        ),
    }

    (out_dir / "baseline_metrics.json").write_text(
        json.dumps(baseline_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "gateway_metrics.json").write_text(
        json.dumps(gateway_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "delta_metrics.json").write_text(
        json.dumps(delta_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _emit_failure_analysis(
        classifications, out_dir / "failure_analysis.md",
    )
    _emit_decision_summary(
        out_dir=out_dir,
        cases_runnable=cases_runnable,
        cases_insufficient_fixture=cases_insufficient_fixture,
        baseline_metrics=baseline,
        gateway_metrics=gateway,
        case_classifications=classifications,
    )
    _emit_artifact_manifest(out_dir)


__all__ = [
    "FAILURE_CLASSIFICATIONS",
    "CalibrationCaseEntry",
    "GatewayCalibrationManifest",
    "load_manifest",
    "run_calibration",
]
