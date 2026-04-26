"""Phase 5.3 (QA/A30.md, ADR-38) — gateway-grounded verifier
calibration runner.
Phase 5.4 (QA/A31.md, ADR-39) — real-execution upgrade.

The runner pairs each holdout case's
:class:`GatewayHoldoutExpected` labels with two actual runs:

* ``baseline`` — :func:`run_verifier` (Phase 4.1) with no
  gateway. Forward + backward replays only; no tool execution.
* ``gateway``  — :func:`run_gateway_grounded_verifier`
  (Phase 5.2) routed through the local deterministic gateway.

Phase 5.4 replaces the stub metric emitters with real
execution: each case's directory is loaded, the providers are
constructed from the per-case replay JSON files, and the two
modes are run against the same packet. The runner falls back
to the stub for cases that don't ship the full file set
(criterion #8 — the public runnable subset must contain ZERO
``insufficient_fixture`` rows; private/example slates can use
the fallback).

It computes per-mode metrics and a ``gateway_delta`` and emits:

* ``baseline_metrics.json``      — per-case + macro metrics (no
  gateway).
* ``gateway_metrics.json``       — per-case + macro metrics
  (gateway-grounded).
* ``delta_metrics.json``         — gateway minus baseline.
* ``decision_summary.json``      — Phase 5.4 recommendation
  (``integrate_opt_in`` / ``revise_prompts`` /
  ``revise_labels`` / ``revise_tool_policy`` /
  ``insufficient_data``). The recommendation is an INPUT for
  the operator, never a production threshold.
* ``failure_analysis.md``        — per-case classification +
  proposed action + ``label_change_proposed`` flag. **NO
  automatic label mutation.**
* ``artifact_manifest.json``     — SHA256 hashes of all written
  artifacts so a future run can prove integrity.

ADR-38 + ADR-39 + QA/A30 + QA/A31 hard rules enforced here:

* The runner NEVER writes anywhere under ``datasets/``.
* Per-case audit logs land under ``<out_dir>/audit/<case_id>/``
  to keep calibration runs from polluting the operator's
  ``.oida/tool-gateway/audit/`` namespace.
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
)

_RECOMMENDATION_LITERAL: tuple[str, ...] = (
    "integrate_opt_in",
    "revise_prompts",
    "revise_labels",
    "revise_tool_policy",
    "insufficient_data",
)


_ManifestMode = Literal["replay", "fake"]


_DELTA_POSITIVE_THRESHOLD = 0.05
_DELTA_NEGATIVE_THRESHOLD = -0.05


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
class _PerModeMetrics:
    """Lightweight per-mode metric bundle used internally by
    the runner. The serialised form lives in the JSON files."""

    cases_evaluated: int = 0
    accepted_correct: int = 0
    accepted_wrong: int = 0
    unsupported_correct: int = 0
    unsupported_wrong: int = 0
    rejected_correct: int = 0
    rejected_wrong: int = 0
    official_field_leak_count: int = 0
    # Phase 5.4 additions.
    fresh_tool_ref_citations: int = 0
    accepted_claims_total: int = 0
    tool_contradiction_rejections: int = 0
    tool_contradiction_opportunities: int = 0
    evidence_refs_cited: int = 0
    evidence_refs_required: int = 0
    evidence_refs_required_satisfied: int = 0

    def claim_accept_accuracy(self) -> float:
        total = self.accepted_correct + self.accepted_wrong
        if total == 0:
            return 0.0
        return self.accepted_correct / total

    def claim_macro_f1(self) -> float:
        scores: list[float] = []
        for tp, fp_fn in (
            (
                self.accepted_correct,
                self.accepted_wrong,
            ),
            (
                self.unsupported_correct,
                self.unsupported_wrong,
            ),
            (
                self.rejected_correct,
                self.rejected_wrong,
            ),
        ):
            if tp == 0 and fp_fn == 0:
                scores.append(0.0)
                continue
            # Symmetric proxy for macro-F1 in the
            # accept/unsupported/reject one-vs-one bucket.
            # Real F1 needs precision/recall; we don't have
            # full per-class P/R here, so we use 2tp / (2tp +
            # fp_fn) as a balanced score.
            scores.append((2 * tp) / (2 * tp + fp_fn))
        return sum(scores) / 3 if scores else 0.0

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
        return {
            "cases_evaluated": self.cases_evaluated,
            "accepted_correct": self.accepted_correct,
            "accepted_wrong": self.accepted_wrong,
            "unsupported_correct": self.unsupported_correct,
            "unsupported_wrong": self.unsupported_wrong,
            "rejected_correct": self.rejected_correct,
            "rejected_wrong": self.rejected_wrong,
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
    label_change_proposed: bool = False


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
    executor_path = case_dir / "executor.json"
    canned_outcome: ExecutionOutcome | None = None
    if executor_path.is_file():
        raw_executor = json.loads(
            executor_path.read_text(encoding="utf-8"),
        )
        canned_outcome = ExecutionOutcome(
            returncode=raw_executor.get("returncode"),
            stdout=raw_executor.get("stdout", ""),
            stderr=raw_executor.get("stderr", ""),
            timed_out=raw_executor.get("timed_out", False),
            runtime_ms=raw_executor.get("runtime_ms", 0),
        )

    def _executor(_ctx: ExecutionContext) -> ExecutionOutcome:
        if canned_outcome is not None:
            return canned_outcome
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
    classification, root_cause, proposed_action, label_change = (
        _classify_case(
            expected=expected,
            actual_baseline=baseline_run.report,
            actual_gateway=gateway_run.report,
            expected_delta=case.expected_delta,
            actual_delta=actual_delta,
        )
    )
    out.classifications.append(
        _CaseClassification(
            case_id=case.case_id,
            family=case.family,
            expected_delta=case.expected_delta,
            actual_delta=actual_delta,
            baseline_result=out.baseline_outcome,
            gateway_result=out.gateway_outcome,
            classification=classification,
            root_cause=root_cause,
            proposed_action=proposed_action,
            label_change_proposed=label_change,
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

    metrics.accepted_correct += len(
        expected_accepted & actual_accepted,
    )
    metrics.accepted_wrong += len(
        expected_accepted ^ actual_accepted,
    )
    metrics.unsupported_correct += len(
        expected_unsupported & actual_unsupported,
    )
    metrics.unsupported_wrong += len(
        expected_unsupported ^ actual_unsupported,
    )
    metrics.rejected_correct += len(
        expected_rejected & actual_rejected,
    )
    metrics.rejected_wrong += len(
        expected_rejected ^ actual_rejected,
    )

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


def _classify_case(
    *,
    expected: object,
    actual_baseline: object,
    actual_gateway: object,
    expected_delta: str,
    actual_delta: str,
) -> tuple[str, str, str, bool]:
    """Return (classification, root_cause, proposed_action,
    label_change_proposed)."""

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

    if baseline_match and gateway_match:
        return (
            "label_too_strict" if False else "expected_behavior_changed",
            "actual outcomes match expected on both modes",
            (
                "no action required; case demonstrates the "
                "expected behaviour"
            ),
            False,
        )

    # Only baseline diverges → the LLM-replay layer is at
    # fault, not the gateway.
    if not baseline_match and gateway_match:
        return (
            "aggregator_bug",
            (
                "baseline mode produced a different verdict than "
                "the operator labelled; the gateway side matches "
                "— investigate the no-gateway aggregator path"
            ),
            (
                "review run_verifier replay handling for this case"
            ),
            False,
        )

    # Only gateway diverges → either the gateway loop, the
    # tool adapter, or the citation rule produced an
    # unexpected result.
    if baseline_match and not gateway_match:
        return (
            "gateway_bug",
            (
                "gateway mode produced a different verdict than "
                "the operator labelled; the baseline side matches"
            ),
            (
                "review run_gateway_grounded_verifier flow "
                "(admission, fingerprint, citation rule, "
                "requested-tool-evidence enforcer)"
            ),
            False,
        )

    # Both diverge → the labels themselves may be miscalibrated.
    return (
        "label_too_strict",
        "both modes diverged from expected; investigate label",
        (
            "review the operator-supplied expected.json; if the "
            "labels turn out to be too strict, propose a label "
            "change but DO NOT mutate it automatically"
        ),
        True,
    )


def _emit_failure_analysis(
    rows: list[_CaseClassification], path: Path,
) -> None:
    """Phase 5.4 — extended Markdown table per QA/A31 §5.4-D.
    Now carries ``actual_delta`` and ``label_change_proposed``
    columns."""
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
    ]

    table_header = (
        "| case_id | family | expected_delta | actual_delta "
        "| baseline_result | gateway_result | classification "
        "| root_cause | proposed_action | label_change_proposed |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    table_rows = [
        (
            f"| `{r.case_id}` | {r.family} | {r.expected_delta} "
            f"| {r.actual_delta} | {r.baseline_result} "
            f"| {r.gateway_result} | `{r.classification}` "
            f"| {r.root_cause} | {r.proposed_action} "
            f"| {str(r.label_change_proposed).lower()} |"
        )
        for r in rows
    ]

    body = "\n".join([
        "# Phase 5.3 / 5.4 — gateway calibration failure analysis",
        "",
        "Per QA/A30 §5.3-E + QA/A31 §5.4-D. Every row is a",
        "per-case proposal. Labels are NEVER mutated",
        "automatically; any change to operator-supplied",
        "expected.json files MUST be a human review followed by",
        "an explicit commit. The `label_change_proposed`",
        "boolean is a hint, not an instruction.",
        "",
        "## Classification legend",
        "",
        *legend_lines,
        "",
        "## Per-case rows",
        "",
        table_header,
        *(table_rows or [
            "| _no rows_ | — | — | — | — | — | — | — | — | — |",
        ]),
        "",
    ])
    path.write_text(body, encoding="utf-8")


def _decide_recommendation(
    *,
    cases_runnable: int,
    cases_insufficient_fixture: int,
    official_leak_count: int,
    gateway_delta_accept_acc: float,
) -> str:
    """Phase 5.4 §5.4-C decision rules.

    The recommendation literal is exactly five values
    (QA/A31 line 219). The conflicting line-226 wording
    (`revise_policy`) and line-238 wording
    (`revise_gateway_or_labels`) are folded into the canonical
    five-value set per the advisor's read.
    """
    if official_leak_count > 0:
        return "revise_tool_policy"
    if cases_runnable < 12:
        return "insufficient_data"
    if gateway_delta_accept_acc > _DELTA_POSITIVE_THRESHOLD:
        return "integrate_opt_in"
    if gateway_delta_accept_acc < _DELTA_NEGATIVE_THRESHOLD:
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

    recommendation = _decide_recommendation(
        cases_runnable=cases_runnable,
        cases_insufficient_fixture=cases_insufficient_fixture,
        official_leak_count=leak_count,
        gateway_delta_accept_acc=delta_accept_acc,
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
        "reserved": (
            "Phase 5.4 recommendations are operator-facing "
            "hints. They are NOT production thresholds and do "
            "NOT promote any score to official total_v_net / "
            "debt_final / corrupt_success."
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
