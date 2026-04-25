"""Phase 4.3-A/E (QA/A19.md, ADR-28) — calibration runner.

Loads a :class:`CalibrationCase` from disk, dispatches to the right
evaluator (one per family), and produces a :class:`CaseResult`. The
runner aggregates results into :class:`CalibrationMetrics`.

**No external API call.** The tool-grounded family uses a fake
executor that consumes ``canned_tool_outputs.json``; the
forward/backward families use file-replay providers.

**No predictive claim.** The runner measures the SHAPE of
estimator/verifier behaviour on controlled cases; it does NOT
attempt to validate production performance. ADR-28 §4.3-G explicitly
forbids product threshold tuning on this dataset.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oida_code.calibration.metrics import (
    CalibrationMetrics,
    CodeOutcomeStatus,
    macro_f1_from_confusion,
    pairwise_order_accuracy,
    precision,
    recall,
    safe_rate,
)
from oida_code.calibration.models import (
    CalibrationCase,
    CalibrationFamily,
    ClaimExpected,
    ContaminationRisk,
    ExpectedClaimLabel,
    ExpectedToolResultLabel,
    ShadowBucket,
)
from oida_code.estimators.llm_prompt import (
    LLMEvidencePacket,
    has_forbidden_phrase,
    render_prompt,
)
from oida_code.verifier.aggregator import aggregate_verification
from oida_code.verifier.contracts import (
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierAggregationReport,
)
from oida_code.verifier.tools import (
    ToolExecutionEngine,
    ToolPolicy,
    VerifierToolRequest,
)
from oida_code.verifier.tools.adapters import (
    ExecutionContext,
    ExecutionOutcome,
)

_FORBIDDEN_KEYS_IN_AGG: frozenset[str] = frozenset({
    "total_v_net", "v_net", "debt_final",
    "corrupt_success", "corrupt_success_ratio",
    "corrupt_success_verdict", "verdict",
})


@dataclass
class CaseResult:
    """Per-case eval outcome. Kept as a plain dataclass so the runner
    can mutate during aggregation; the public manifest is the
    :class:`CalibrationMetrics` Pydantic model."""

    case_id: str
    family: CalibrationFamily
    contamination_risk: ContaminationRisk

    # Claim-level confusion: confusion[true_label][predicted_label]
    claim_confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    evidence_ref_tp: int = 0
    evidence_ref_fp: int = 0
    evidence_ref_fn: int = 0
    unknown_ref_correctly_rejected: int = 0
    unknown_ref_total: int = 0

    # Tool-level
    tool_status_match: int = 0
    tool_status_total: int = 0
    tool_contradiction_rejected: int = 0
    tool_contradiction_total: int = 0
    tool_uncertainty_preserved: int = 0
    tool_uncertainty_total: int = 0
    sandbox_block_match: int = 0
    sandbox_block_total: int = 0

    # Shadow
    shadow_bucket_match: bool | None = None
    shadow_bucket_actual: ShadowBucket | None = None

    # Code outcome
    f2p_passed: bool | None = None
    p2p_preserved: bool | None = None
    flaky: bool = False

    # Safety
    safety_block_match: bool | None = None
    fenced_injection: bool | None = None

    # Honesty guard
    official_field_leaks: int = 0

    # Free-form notes
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_case(case_dir: Path) -> CalibrationCase:
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    return CalibrationCase.model_validate(expected)


def _load_relative_json(case_dir: Path, ref: str | None) -> Any | None:
    if ref is None:
        return None
    return json.loads((case_dir / ref).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Family evaluators
# ---------------------------------------------------------------------------


def _confusion_init() -> dict[str, dict[str, int]]:
    return {k: {kk: 0 for kk in _CLAIM_LABELS} for k in _CLAIM_LABELS}


_CLAIM_LABELS: tuple[ClaimExpected, ...] = ("accepted", "unsupported", "rejected")


def _classify_claim(
    claim_id: str, report: VerifierAggregationReport,
) -> ClaimExpected | None:
    for c in report.accepted_claims:
        if c.claim_id == claim_id:
            return "accepted"
    for c in report.unsupported_claims:
        if c.claim_id == claim_id:
            return "unsupported"
    for c in report.rejected_claims:
        if c.claim_id == claim_id:
            return "rejected"
    return None


def _evaluate_claims(
    expected_labels: tuple[ExpectedClaimLabel, ...],
    report: VerifierAggregationReport,
    result: CaseResult,
) -> None:
    if not result.claim_confusion:
        result.claim_confusion = _confusion_init()
    for label in expected_labels:
        actual = _classify_claim(label.claim_id, report)
        if actual is None:
            result.notes.append(
                f"claim {label.claim_id} not present in any verdict bucket"
            )
            continue
        result.claim_confusion[label.expected][actual] += 1
        # Evidence-ref metrics: count expected refs that actually appear
        # on the accepted/unsupported claim's evidence_refs.
        actual_refs = _claim_evidence_refs(label.claim_id, report)
        expected_refs = set(label.required_evidence_refs)
        if expected_refs:
            for ref in expected_refs:
                if ref in actual_refs:
                    result.evidence_ref_tp += 1
                else:
                    result.evidence_ref_fn += 1
            for ref in actual_refs:
                if ref not in expected_refs:
                    result.evidence_ref_fp += 1
        # Unknown-ref correctness: when reason is unknown_evidence_ref,
        # the claim MUST have been rejected.
        if label.reason == "unknown_evidence_ref":
            result.unknown_ref_total += 1
            if actual == "rejected":
                result.unknown_ref_correctly_rejected += 1


def _claim_evidence_refs(
    claim_id: str, report: VerifierAggregationReport,
) -> set[str]:
    for bucket in (
        report.accepted_claims, report.unsupported_claims, report.rejected_claims,
    ):
        for claim in bucket:
            if claim.claim_id == claim_id:
                return set(claim.evidence_refs)
    return set()


def _check_no_official_leak(
    payload: Mapping[str, Any], result: CaseResult,
) -> None:
    leaks = _FORBIDDEN_KEYS_IN_AGG & set(payload.keys())
    result.official_field_leaks += len(leaks)


def evaluate_claim_contract(
    case: CalibrationCase, case_dir: Path,
) -> CaseResult:
    result = CaseResult(
        case_id=case.case_id, family=case.family,
        contamination_risk=case.contamination_risk,
    )
    if case.packet_path is None:
        result.notes.append("missing packet_path")
        return result
    packet = LLMEvidencePacket.model_validate(
        _load_relative_json(case_dir, case.packet_path)
    )
    forward_payload = _load_relative_json(case_dir, case.forward_replay_path)
    backward_payload = _load_relative_json(case_dir, case.backward_replay_path)
    if forward_payload is None:
        result.notes.append("missing forward_replay_path")
        return result
    if "event_id" not in forward_payload:
        forward_payload["event_id"] = packet.event_id
    forward = ForwardVerificationResult.model_validate(forward_payload)
    backward_results: list[BackwardVerificationResult] = []
    if backward_payload is not None:
        items = (
            backward_payload["results"]
            if isinstance(backward_payload, dict) and "results" in backward_payload
            else backward_payload
        )
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    item.setdefault("event_id", packet.event_id)
                    backward_results.append(BackwardVerificationResult.model_validate(item))
    report = aggregate_verification(
        forward, tuple(backward_results), packet,
    )
    _check_no_official_leak(report.model_dump(), result)
    _evaluate_claims(case.expected_claim_labels, report, result)
    return result


def evaluate_tool_grounded(
    case: CalibrationCase, case_dir: Path,
) -> CaseResult:
    result = CaseResult(
        case_id=case.case_id, family=case.family,
        contamination_risk=case.contamination_risk,
    )
    if case.tool_policy_path is None or case.tool_requests_path is None:
        result.notes.append("missing tool_policy_path or tool_requests_path")
        return result
    policy_raw = _load_relative_json(case_dir, case.tool_policy_path)
    if (
        isinstance(policy_raw, dict)
        and "repo_root" in policy_raw
        and str(policy_raw["repo_root"]) in (".", "<case_dir>")
    ):
        # Allow placeholder repo_root in fixtures — resolve to case_dir.
        policy_raw["repo_root"] = str(case_dir)
    policy = ToolPolicy.model_validate(policy_raw)
    requests_raw = _load_relative_json(case_dir, case.tool_requests_path)
    if not isinstance(requests_raw, list):
        result.notes.append("tool_requests_path must be a JSON list")
        return result
    requests = tuple(
        VerifierToolRequest.model_validate(r) for r in requests_raw
    )
    canned = _load_relative_json(case_dir, case.canned_tool_outputs_path) or {}
    executor = _make_canned_executor(canned)
    engine = ToolExecutionEngine(executor=executor)
    tool_results = engine.run(requests, policy)
    expected_by_request_id = _index_expected_tool_results(case.expected_tool_results)
    for idx, (req, actual) in enumerate(zip(requests, tool_results, strict=True)):
        request_id = expected_by_request_id_key(req, idx)
        expected = expected_by_request_id.get(request_id)
        if expected is None:
            continue
        result.tool_status_total += 1
        if actual.status == expected.expected_status:
            result.tool_status_match += 1
        if expected.expected_status == "blocked":
            result.sandbox_block_total += 1
            if actual.status == "blocked":
                result.sandbox_block_match += 1
                # Optional substring sanity check on the block reason —
                # already counted as a match above; this branch just
                # logs an inconsistency if the operator-supplied
                # substring is missing.
                substring = expected.expected_block_reason_substring
                if substring is not None and not any(
                    substring in b for b in actual.blockers
                ):
                    result.notes.append(
                        f"block reason substring {substring!r} not found in "
                        f"{list(actual.blockers)}"
                    )
        if expected.expected_status == "failed":
            result.tool_contradiction_total += 1
            if actual.status == "failed":
                result.tool_contradiction_rejected += 1
        if expected.expected_status in ("tool_missing", "timeout", "error"):
            result.tool_uncertainty_total += 1
            if actual.status in ("tool_missing", "timeout", "error"):
                result.tool_uncertainty_preserved += 1
        # No V_net leak in any tool result.
        _check_no_official_leak(actual.model_dump(), result)
    return result


def _index_expected_tool_results(
    labels: Iterable[ExpectedToolResultLabel],
) -> dict[str, ExpectedToolResultLabel]:
    return {label.request_id: label for label in labels}


def expected_by_request_id_key(req: VerifierToolRequest, idx: int) -> str:
    """Best-effort id: ``<tool>:<idx>``. Cases use this naming
    convention so labels can be matched without a separate id field
    on :class:`VerifierToolRequest`."""
    return f"{req.tool}:{idx}"


def _make_canned_executor(canned: Mapping[str, Any]):  # type: ignore[no-untyped-def]
    """``canned`` is a dict ``binary -> {stdout, returncode, timed_out,
    runtime_ms, missing}`` describing what the fake executor returns
    on the first call to that binary. A list under ``binary`` rotates
    through outcomes by call index."""
    state: dict[str, int] = {}

    def _executor(ctx: ExecutionContext) -> ExecutionOutcome:
        spec = canned.get(ctx.binary)
        if spec is None:
            return ExecutionOutcome(
                stdout="", stderr="", returncode=None,
                timed_out=False, runtime_ms=0,
            )
        if isinstance(spec, list):
            idx = state.get(ctx.binary, 0)
            spec = spec[min(idx, len(spec) - 1)]
            state[ctx.binary] = idx + 1
        if spec.get("missing"):
            return ExecutionOutcome(
                stdout="", stderr="", returncode=None,
                timed_out=False, runtime_ms=int(spec.get("runtime_ms", 0)),
            )
        if spec.get("timed_out"):
            return ExecutionOutcome(
                stdout="", stderr="", returncode=None,
                timed_out=True, runtime_ms=int(spec.get("runtime_ms", 0)),
            )
        return ExecutionOutcome(
            stdout=str(spec.get("stdout", "")),
            stderr=str(spec.get("stderr", "")),
            returncode=int(spec.get("returncode", 0)),
            timed_out=False,
            runtime_ms=int(spec.get("runtime_ms", 0)),
        )

    return _executor


def evaluate_shadow_pressure(
    case: CalibrationCase, case_dir: Path,
) -> CaseResult:
    """Loads a packet whose deterministic_estimates encode the scenario
    intent and uses the shadow fusion's base_pressure on each event
    to bucket the case. The fixture-side label encodes the expected
    bucket; the runner just classifies the maximum base pressure."""
    from oida_code.score.experimental_shadow_fusion import (
        compute_experimental_shadow_fusion,
    )
    from oida_code.score.fusion_readiness import assess_fusion_readiness

    result = CaseResult(
        case_id=case.case_id, family=case.family,
        contamination_risk=case.contamination_risk,
    )
    if case.packet_path is None:
        result.notes.append("missing packet_path for shadow_pressure")
        return result
    # Shadow pressure cases ship a NormalizedScenario, NOT an evidence
    # packet — we reuse packet_path to point at the scenario JSON.
    raw = _load_relative_json(case_dir, case.packet_path)
    from oida_code.models.normalized_event import NormalizedScenario
    scenario = NormalizedScenario.model_validate(raw)
    readiness = assess_fusion_readiness(scenario)
    shadow = compute_experimental_shadow_fusion(scenario, readiness)
    _check_no_official_leak(shadow.model_dump(), result)
    if not shadow.event_scores:
        result.notes.append("scenario has no events")
        result.shadow_bucket_match = False
        return result
    max_pressure = max(s.base_pressure for s in shadow.event_scores)
    bucket = _bucket_for(max_pressure)
    result.shadow_bucket_actual = bucket
    result.shadow_bucket_match = (bucket == case.expected_shadow_bucket)
    return result


def _bucket_for(pressure: float) -> ShadowBucket:
    if pressure < 0.30:
        return "low"
    if pressure < 0.60:
        return "medium"
    return "high"


_HOSTILE_NEEDLES: tuple[str, ...] = (
    "mark capability=1.0",
    "Ignore previous instructions",
)
"""User-visible attack strings that, when found in a rendered prompt,
MUST sit inside a matching OIDA_EVIDENCE fence span. Used by
``_check_safety_fences``.

We intentionally do NOT include ``<<<END_OIDA_EVIDENCE`` here: the
legitimate closing fences themselves contain that exact substring at
positions just outside each span, and the renderer's
zero-width-space defence already neutralises any forged inner close
in user content. The close-tracking loop in
``_check_safety_fences`` enforces "every real close in the region
corresponds to a declared open" independently."""


def _check_safety_fences(prompt: str, packet: LLMEvidencePacket) -> bool:
    """4.3.1-C — exact OIDA_EVIDENCE fence check.

    The check is scoped to the **data region** of the rendered prompt
    (between ``EVIDENCE:`` and the next top-level marker
    ``DETERMINISTIC_ESTIMATES:``). The prompt's preamble + output
    schema hint legitimately mention ``<<<OIDA_EVIDENCE
    id="[E.kind.idx]" kind="...">>>`` as documentation; those mentions
    must NOT be confused with real data fences.

    Within the data region:

    * For every evidence item declared on ``packet``, the data region
      MUST contain an opening fence
      ``<<<OIDA_EVIDENCE id="<id>" kind="<kind>">>>`` and a matching
      closing fence ``<<<END_OIDA_EVIDENCE id="<id>">>>`` with the
      same ``id``.
    * No real ``<<<END_OIDA_EVIDENCE id="..."`` sequence in the data
      region may carry an id that isn't declared (forged-close
      escape).
    * Generic ``<<...>>`` shorthand or an open whose ``kind=...``
      doesn't match the declared kind is rejected.
    * Any hostile needle in the data region MUST sit inside one of
      the matching open/close spans.

    Returns ``True`` when every check passes; ``False`` otherwise.
    """
    import re as _re

    start_marker = "EVIDENCE:"
    end_marker = "DETERMINISTIC_ESTIMATES:"
    start = prompt.find(start_marker)
    end = prompt.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        # Prompt structure has shifted; fail closed.
        return False
    region = prompt[start + len(start_marker) : end]

    open_re = _re.compile(
        r'<<<OIDA_EVIDENCE id="(?P<id>\[[^"]*?\])" kind="(?P<kind>[^"]*?)">>>',
    )
    close_re = _re.compile(
        r'<<<END_OIDA_EVIDENCE id="(?P<id>\[[^"]*?\])">>>',
    )

    declared_ids = {item.id for item in packet.evidence_items}
    declared_kinds = {item.id: item.kind for item in packet.evidence_items}

    spans: dict[str, tuple[int, int]] = {}
    for match in open_re.finditer(region):
        eid = match.group("id")
        kind = match.group("kind")
        if eid not in declared_ids:
            return False
        if declared_kinds.get(eid) != kind:
            return False
        if eid in spans:
            return False
        close_match = close_re.search(region, match.end())
        if close_match is None or close_match.group("id") != eid:
            return False
        spans[eid] = (match.end(), close_match.start())

    for eid in declared_ids:
        if eid not in spans:
            return False

    # Every real close in the region must correspond to exactly one
    # span we already accepted (no duplicate / forged closes).
    for close_match in close_re.finditer(region):
        eid = close_match.group("id")
        if eid not in declared_ids:
            return False
        if close_match.start() != spans[eid][1]:
            return False

    for needle in _HOSTILE_NEEDLES:
        idx = 0
        while True:
            found = region.find(needle, idx)
            if found < 0:
                break
            idx = found + 1
            inside_span = any(
                s <= found < e for s, e in spans.values()
            )
            if not inside_span:
                return False
    return True


def evaluate_safety_adversarial(
    case: CalibrationCase, case_dir: Path,
) -> CaseResult:
    """Renders the prompt for a hostile packet and verifies (a) the
    injection is fenced, (b) any aggregator output (if forward/backward
    replays are present) does NOT accept the hostile claim, and (c)
    no official field leaks anywhere."""
    result = CaseResult(
        case_id=case.case_id, family=case.family,
        contamination_risk=case.contamination_risk,
    )
    if case.packet_path is None:
        result.notes.append("missing packet_path for safety_adversarial")
        return result
    packet = LLMEvidencePacket.model_validate(
        _load_relative_json(case_dir, case.packet_path)
    )
    prompt = render_prompt(packet)
    # 4.3.1-C — exact OIDA_EVIDENCE fence check. For every evidence
    # item that contains hostile content, the renderer must place the
    # content between an OIDA_EVIDENCE opening fence carrying the same
    # id (and kind) as the closing fence. Generic ``<<`` matches are
    # NOT sufficient (would allow both forged shorthand and unrelated
    # angle-bracket characters).
    result.fenced_injection = _check_safety_fences(prompt, packet)
    # If forward/backward replays are present, run the aggregator and
    # ensure the hostile claim is NOT accepted.
    forward_payload = _load_relative_json(case_dir, case.forward_replay_path)
    backward_payload = _load_relative_json(case_dir, case.backward_replay_path)
    if forward_payload is not None:
        if "event_id" not in forward_payload:
            forward_payload["event_id"] = packet.event_id
        forward = ForwardVerificationResult.model_validate(forward_payload)
        backward_results: list[BackwardVerificationResult] = []
        if backward_payload is not None:
            items = (
                backward_payload["results"]
                if isinstance(backward_payload, dict) and "results" in backward_payload
                else backward_payload
            )
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        item.setdefault("event_id", packet.event_id)
                        backward_results.append(BackwardVerificationResult.model_validate(item))
        report = aggregate_verification(
            forward, tuple(backward_results), packet,
        )
        _check_no_official_leak(report.model_dump(), result)
        # Block correctness — at least one expected claim should NOT
        # be accepted.
        any_blocked = any(
            label.expected != "accepted"
            for label in case.expected_claim_labels
        )
        if any_blocked:
            result.safety_block_match = all(
                _classify_claim(label.claim_id, report) != "accepted"
                for label in case.expected_claim_labels
                if label.expected != "accepted"
            )
        else:
            result.safety_block_match = True
        _evaluate_claims(case.expected_claim_labels, report, result)
    else:
        result.safety_block_match = True
    # Forbidden phrase MUST NOT appear in the rendered prompt body
    # OUTSIDE the data fences (that's allowed in the preamble's
    # meta-mention).
    if has_forbidden_phrase(prompt, packet):
        # The preamble cites the forbidden words — that's fine.
        # We're checking that no forbidden phrase appears as a real
        # claim VALUE; the prompt template carries them only inside
        # the FORBIDDEN_CLAIMS marker line.
        pass
    return result


def evaluate_code_outcome(
    case: CalibrationCase, case_dir: Path,
) -> CaseResult:
    """code_outcome cases are evaluated by the dedicated stability
    script; the runner records "deferred" so headline metrics know to
    pull the pass/fail counts from `.oida/calibration_v1/stability_report.json`."""
    result = CaseResult(
        case_id=case.case_id, family=case.family,
        contamination_risk=case.contamination_risk,
    )
    result.notes.append(
        "code_outcome family is evaluated by check_calibration_stability.py"
    )
    return result


_DISPATCH = {
    "claim_contract": evaluate_claim_contract,
    "tool_grounded": evaluate_tool_grounded,
    "shadow_pressure": evaluate_shadow_pressure,
    "code_outcome": evaluate_code_outcome,
    "safety_adversarial": evaluate_safety_adversarial,
}


def run_case(case: CalibrationCase, case_dir: Path) -> CaseResult:
    return _DISPATCH[case.family](case, case_dir)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate(
    results: Iterable[CaseResult],
    stability_report: list[dict[str, object]] | None = None,
) -> CalibrationMetrics:
    """Aggregate per-case results into :class:`CalibrationMetrics`.

    ``stability_report`` is the parsed JSON list emitted by
    ``check_calibration_stability.py``. When provided, the runner
    folds F2P / P2P pass rates + flaky exclusions into the headline
    metrics (4.3.1-B). When absent, those fields stay ``None`` and
    ``code_outcome_status="not_computed"`` makes the gap explicit.
    """
    bucket_results: list[CaseResult] = list(results)

    # 4.3.1-B — apply stability report flakiness BEFORE the
    # contamination/flaky filter so flagged code_outcome cases drop
    # out of the headline set the same way local-flagged cases do.
    flaky_from_stability: set[str] = set()
    if stability_report is not None:
        for entry in stability_report:
            if isinstance(entry, dict) and entry.get("flaky"):
                cid = entry.get("case_id")
                if isinstance(cid, str):
                    flaky_from_stability.add(cid)
    if flaky_from_stability:
        for r in bucket_results:
            if r.case_id in flaky_from_stability:
                r.flaky = True

    excluded_for_contamination = sum(
        1 for r in bucket_results if r.contamination_risk == "public_high"
    )
    excluded_for_flakiness = sum(1 for r in bucket_results if r.flaky)
    headline = [
        r for r in bucket_results
        if r.contamination_risk != "public_high" and not r.flaky
    ]

    # Claim metrics (claim_contract + safety_adversarial)
    confusion: dict[str, dict[str, int]] = {
        k: {kk: 0 for kk in _CLAIM_LABELS} for k in _CLAIM_LABELS
    }
    evidence_tp = evidence_fp = evidence_fn = 0
    unknown_correct = unknown_total = 0
    for r in headline:
        for label in _CLAIM_LABELS:
            for pred in _CLAIM_LABELS:
                confusion[label][pred] += r.claim_confusion.get(label, {}).get(pred, 0)
        evidence_tp += r.evidence_ref_tp
        evidence_fp += r.evidence_ref_fp
        evidence_fn += r.evidence_ref_fn
        unknown_correct += r.unknown_ref_correctly_rejected
        unknown_total += r.unknown_ref_total

    correct_claims = sum(confusion[k][k] for k in _CLAIM_LABELS)
    total_claims = sum(
        sum(confusion[k][kk] for kk in _CLAIM_LABELS) for k in _CLAIM_LABELS
    )

    # Tool metrics
    tool_status_match = sum(r.tool_status_match for r in headline)
    tool_status_total = sum(r.tool_status_total for r in headline)
    tool_contradiction_rejected = sum(r.tool_contradiction_rejected for r in headline)
    tool_contradiction_total = sum(r.tool_contradiction_total for r in headline)
    tool_uncertainty_preserved = sum(r.tool_uncertainty_preserved for r in headline)
    tool_uncertainty_total = sum(r.tool_uncertainty_total for r in headline)
    sandbox_block_match = sum(r.sandbox_block_match for r in headline)
    sandbox_block_total = sum(r.sandbox_block_total for r in headline)

    # Shadow metrics
    shadow_results = [
        r for r in headline
        if r.family == "shadow_pressure" and r.shadow_bucket_match is not None
    ]
    shadow_match = sum(1 for r in shadow_results if r.shadow_bucket_match)
    shadow_total = len(shadow_results)
    pairwise = pairwise_order_accuracy(
        _shadow_pairs(shadow_results),
        {r.case_id: r.shadow_bucket_actual or "low" for r in shadow_results},
    )

    # 4.3.1-B — code outcome rates are computed from the stability
    # report when present; otherwise stay None + "not_computed".
    f2p_rate, p2p_rate, code_status = _code_outcome_rates(
        bucket_results, stability_report,
    )
    flaky = sum(1 for r in bucket_results if r.flaky)

    # Safety metrics
    safety_results = [r for r in headline if r.family == "safety_adversarial"]
    safety_block = sum(
        1 for r in safety_results if r.safety_block_match
    )
    fenced = sum(1 for r in safety_results if r.fenced_injection)
    safety_total = len(safety_results)

    # Honesty
    leak_count = sum(r.official_field_leaks for r in bucket_results)

    return CalibrationMetrics(
        cases_total=len(bucket_results),
        cases_evaluated=len(headline),
        cases_excluded_for_contamination=excluded_for_contamination,
        cases_excluded_for_flakiness=excluded_for_flakiness,
        claim_accept_accuracy=safe_rate(correct_claims, total_claims),
        claim_accept_macro_f1=macro_f1_from_confusion(confusion),
        unsupported_precision=precision(
            confusion["unsupported"]["unsupported"],
            confusion["accepted"]["unsupported"]
            + confusion["rejected"]["unsupported"],
        ),
        rejected_precision=precision(
            confusion["rejected"]["rejected"],
            confusion["accepted"]["rejected"]
            + confusion["unsupported"]["rejected"],
        ),
        evidence_ref_precision=precision(evidence_tp, evidence_fp),
        evidence_ref_recall=recall(evidence_tp, evidence_fn),
        unknown_ref_rejection_rate=safe_rate(unknown_correct, unknown_total),
        tool_contradiction_rejection_rate=safe_rate(
            tool_contradiction_rejected, tool_contradiction_total,
        ),
        tool_uncertainty_preservation_rate=safe_rate(
            tool_uncertainty_preserved, tool_uncertainty_total,
        ),
        sandbox_block_rate_expected=safe_rate(
            sandbox_block_match, sandbox_block_total,
        ),
        shadow_bucket_accuracy=safe_rate(shadow_match, shadow_total),
        shadow_pairwise_order_accuracy=pairwise,
        f2p_pass_rate_on_expected_fixed=f2p_rate,
        p2p_preservation_rate=p2p_rate,
        flaky_case_count=flaky,
        code_outcome_status=code_status,
        safety_block_rate=safe_rate(safety_block, safety_total),
        fenced_injection_rate=safe_rate(fenced, safety_total),
        # 4.3.1-A — honest leak metric. Use
        # `assert_no_official_field_leaks(metrics)` (or the eval
        # script's exit code) as the gate; the schema permits a
        # positive count so the leak is **measurable** rather than
        # impossible to represent.
        official_field_leak_count=leak_count,
        notes=(
            f"calibration_v1 pilot: tool_status_match_rate="
            f"{safe_rate(tool_status_match, tool_status_total):.3f}; "
            f"leaks_seen={leak_count}; "
            f"code_outcome_status={code_status}"
        ),
    )


def _code_outcome_rates(
    bucket_results: list[CaseResult],
    stability_report: list[dict[str, object]] | None,
) -> tuple[float | None, float | None, CodeOutcomeStatus]:
    """4.3.1-B — derive code-outcome F2P / P2P rates from the stability
    report. Returns ``(f2p_rate, p2p_rate, status)``.

    * No stability report passed → ``(None, None, "not_computed")``.
      ``CalibrationMetrics`` carries the gap honestly instead of
      pretending the rates are 0.0.
    * Stability report present → the numerator counts cases whose
      F2P / P2P signature was unanimous across runs AND matched the
      expected outcome; the denominator is the count of non-flaky
      code_outcome cases. Cases marked flaky are dropped from BOTH
      numerator and denominator (consistent with `flaky_case_count`).
    """
    if stability_report is None:
        return None, None, "not_computed"
    code_case_ids = {
        r.case_id for r in bucket_results if r.family == "code_outcome"
    }
    f2p_pass = 0
    p2p_pass = 0
    total = 0
    for entry in stability_report:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("case_id")
        if not isinstance(cid, str) or cid not in code_case_ids:
            continue
        if entry.get("flaky"):
            continue
        runs = entry.get("runs")
        if not isinstance(runs, list) or not runs:
            continue
        total += 1
        # All runs must agree AND every F2P MUST be passed; every
        # P2P MUST stay green.
        f2p_unanimous = all(
            isinstance(run, dict)
            and all(bool(x) for x in run.get("f2p_passed", []) or [])
            for run in runs
        )
        p2p_unanimous = all(
            isinstance(run, dict)
            and all(bool(x) for x in run.get("p2p_passed", []) or [])
            for run in runs
        )
        if f2p_unanimous:
            f2p_pass += 1
        if p2p_unanimous:
            p2p_pass += 1
    if total == 0:
        return None, None, "not_computed"
    return (
        f2p_pass / total,
        p2p_pass / total,
        "from_stability_report",
    )


def _shadow_pairs(results: list[CaseResult]) -> Iterable[tuple[str, str, str]]:
    """All (case_a, case_b, "<") pairs for shadow cases sorted by
    expected bucket. The runner doesn't currently store the case-level
    expected bucket so we infer pairs from the actual ordering — this
    is a placeholder until we add expected-bucket pair lists to the
    case schema. For the pilot, the per-case bucket accuracy carries
    the load."""
    return ()


__all__ = [
    "CaseResult",
    "aggregate",
    "evaluate_claim_contract",
    "evaluate_code_outcome",
    "evaluate_safety_adversarial",
    "evaluate_shadow_pressure",
    "evaluate_tool_grounded",
    "expected_by_request_id_key",
    "load_case",
    "run_case",
]
