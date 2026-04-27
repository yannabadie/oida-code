"""Phase 5.2 (QA/A29.md, ADR-37) — gateway-grounded verifier loop.

The Phase 4.1 verifier produces forward/backward claims but never
executes any tool. Phase 4.2 introduced the deterministic tool
adapters (ruff/mypy/pytest/semgrep/codeql); Phase 5.1 wrapped them
in :class:`LocalDeterministicToolGateway` with admission +
fingerprinting + audit-log layers. Phase 5.2 wires those two
layers together with a strict two-pass loop:

#. Pass 1 — forward + backward verifier replay/providers run on
   the original :class:`LLMEvidencePacket`. Forward result may
   include a tuple of :class:`VerifierToolCallSpec` declaring
   which tools the verifier WOULD ask.
#. Tool phase — each spec is mapped to a
   :class:`VerifierToolRequest` via :func:`tool_request_from_spec`
   (no argv from the LLM, scope copied verbatim) and executed
   through :class:`LocalDeterministicToolGateway`. Tool
   :class:`EvidenceItem`\\s are appended to a NEW packet, and
   ``failed`` results produce a deterministic
   :class:`SignalEstimate` so the aggregator's existing
   tool-grounded contradiction rule can still reject any LLM
   claim that contradicts the tool.
#. Pass 2 — forward + backward verifier replay/providers run
   AGAIN on the enriched packet; the aggregator decides.

Hard rules (ADR-37 §Rejected):

* No MCP runtime, no JSON-RPC, no dynamic tool discovery, no
  remote tool dispatch primitives.
* No remote tools, no provider tool-calling.
* No write tools, no network egress.
* No unbounded multi-turn loops — the budget is two passes and at
  most ``max_tool_calls`` tool invocations.
* No official ``total_v_net`` / ``debt_final`` / ``corrupt_success``.

The runner is deterministic-by-default (replay providers only).
External providers stay opt-in via the existing optional binders
in :mod:`oida_code.verifier.replay_external` — Phase 5.2 does NOT
turn them on automatically.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from oida_code.estimators.contracts import SignalEstimate
from oida_code.estimators.llm_prompt import (
    EvidenceItem,
    LLMEvidencePacket,
)
from oida_code.verifier.contracts import (
    VerifierAggregationReport,
    VerifierToolCallSpec,
)
from oida_code.verifier.forward_backward import VerifierRun, run_verifier
from oida_code.verifier.replay import VerifierProvider
from oida_code.verifier.tool_gateway.audit_log import audit_log_path
from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tool_gateway.gateway import (
    LocalDeterministicToolGateway,
)
from oida_code.verifier.tools.contracts import (
    ToolName,
    ToolPolicy,
    VerifierToolRequest,
    VerifierToolResult,
)

_DEFAULT_RUNTIME_S = 10
_DEFAULT_MAX_OUTPUT_CHARS = 8000
_DEFAULT_MAX_TOOL_CALLS = 5

# Phase 5.2 maps tool kinds to deterministic SignalEstimate fields
# the aggregator's tool-grounded rule already understands. ruff,
# mypy, semgrep, codeql produce static-analysis style operator-
# accept signals; pytest produces a tests_pass signal.
_TOOL_TO_FIELD: dict[ToolName, Literal["operator_accept", "tests_pass"]] = {
    "ruff": "operator_accept",
    "mypy": "operator_accept",
    "semgrep": "operator_accept",
    "codeql": "operator_accept",
    "pytest": "tests_pass",
}


# ---------------------------------------------------------------------------
# 5.2-B — VerifierToolCallSpec → VerifierToolRequest mapping
# ---------------------------------------------------------------------------


def tool_request_from_spec(
    spec: VerifierToolCallSpec,
    *,
    default_runtime_s: int = _DEFAULT_RUNTIME_S,
    max_output_chars: int = _DEFAULT_MAX_OUTPUT_CHARS,
    requested_by_claim_id: str | None = None,
) -> VerifierToolRequest:
    """Convert a forward-verifier spec into a deterministic tool
    request.

    ADR-37 invariants enforced here:

    * ``tool`` MUST stay inside the
      :data:`oida_code.verifier.tools.contracts.ToolName` Literal —
      the schema rejects anything else, but we keep the mapping
      explicit so future tool additions show up in test diffs.
    * ``purpose`` is copied verbatim, then **truncated** at the
      schema's 200-char limit so a verbose spec can't blow up the
      request.
    * ``scope`` is copied exactly. No expansion, no normalisation —
      the existing sandbox is the path-traversal guard.
    * No ``argv`` / ``shell_command`` field exists on either
      schema; the adapter builds the argv itself from
      ``request.tool`` and the policy's ``repo_root``.
    """
    truncated_purpose = spec.purpose[:200] if spec.purpose else "tool re-run"
    # Phase 5.3 (ADR-38): ``VerifierToolCallSpec.requested_by_claim_id``
    # is now optional on the spec itself. The explicit kwarg still
    # wins (operator override); otherwise the spec's own attribution
    # flows through.
    resolved_claim_id = (
        requested_by_claim_id
        if requested_by_claim_id is not None
        else spec.requested_by_claim_id
    )
    return VerifierToolRequest(
        tool=spec.tool,
        purpose=truncated_purpose,
        scope=tuple(spec.scope),
        max_runtime_s=default_runtime_s,
        max_output_chars=max_output_chars,
        requested_by_claim_id=resolved_claim_id,
    )


# ---------------------------------------------------------------------------
# 5.2-D — VerifierToolResult → SignalEstimate mapping
# ---------------------------------------------------------------------------


def deterministic_estimates_from_tool_result(
    result: VerifierToolResult,
    *,
    event_id: str,
) -> tuple[SignalEstimate, ...]:
    """Translate a tool result into deterministic signal estimates.

    Phase 5.2-D contract:

    * ``failed``  → ONE negative tool estimate (value=0.0,
      confidence=0.8, source="tool"). The aggregator's existing
      tool-grounded contradiction rule then rejects any LLM claim
      on the same event.
    * ``ok``      → no estimate (deliberate; weak positive signals
      should not push the aggregator into "verification_candidate"
      without backward corroboration).
    * ``error`` / ``timeout`` / ``tool_missing`` / ``blocked`` →
      no estimate. These are uncertainties surfaced as warnings or
      blockers on the run, NOT proofs that the code is broken.

    The tool's ``evidence_items`` are wired into the
    :class:`SignalEstimate.evidence_refs` so the aggregator's rule
    can cite them.
    """
    if result.status != "failed":
        return ()
    field = _TOOL_TO_FIELD.get(result.tool)
    if field is None:
        return ()
    refs = tuple(item.id for item in result.evidence_items)
    return (
        SignalEstimate(
            field=field,
            event_id=event_id,
            value=0.0,
            confidence=0.8,
            source="tool",
            method_id=f"{result.tool}_runner",
            method_version="0.4.0",
            evidence_refs=refs,
        ),
    )


# ---------------------------------------------------------------------------
# 5.2-C — gateway-grounded run model + runner
# ---------------------------------------------------------------------------


class GatewayGroundedVerifierRun(BaseModel):
    """Aggregated output of one two-pass gateway-grounded run.

    The model is frozen to keep the runner immutable from the
    integrator's point of view (no field on this model can be
    mutated to slip through a forbidden official phrase).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    report: VerifierAggregationReport
    first_pass_report: VerifierAggregationReport | None = None
    tool_results: tuple[VerifierToolResult, ...] = ()
    audit_log_paths: tuple[str, ...] = ()
    enriched_evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass
class _ToolPhaseOutput:
    tool_results: tuple[VerifierToolResult, ...]
    # Phase 5.8.1-B (QA/A39 §4 invariant): every tool result emits at
    # least one citable EvidenceItem (clean-pass / failed-with-findings
    # via ``parse_outcome``; tool_missing/timeout/error/no-findings via
    # the adapter's ``_diagnostic_evidence`` synthesiser). All such items
    # are appended here so the enriched packet's ``evidence_items``
    # always resolves a claim's ``[E.tool.<binary>.0]`` ref (aggregator
    # rule 3 stops rejecting on missing-ref).
    new_evidence: tuple[EvidenceItem, ...]
    # Phase 5.8.1-B safety split: ``new_evidence`` is "citable but not
    # necessarily promoting". ``actionable_evidence`` is the strict
    # subset whose source result has ``status in {"ok", "failed"}`` —
    # i.e. the tool actually ran and reported a meaningful signal. The
    # ``error`` / ``timeout`` / ``tool_missing`` / ``blocked`` paths emit
    # diagnostics into ``new_evidence`` but NOT into
    # ``actionable_evidence``; ``_enforce_requested_tool_evidence`` and
    # ``_enforce_pass2_tool_citation`` consume the actionable subset so
    # an error-path diagnostic cannot promote a pass-2 claim from
    # rejected/unsupported to accepted.
    actionable_evidence: tuple[EvidenceItem, ...]
    new_estimates: tuple[SignalEstimate, ...]
    audit_paths: tuple[Path, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    # Phase 5.3 / 5.2.1-B accounting (QA/A30 §5.2.1-B): the
    # post-pass-2 enforcer needs to know whether forward asked
    # for tools at all, and which specs missed a gateway
    # definition (audit-only — never an exception path).
    requested_count: int = 0
    missing_definition_tools: tuple[str, ...] = ()


def _run_tool_phase(
    specs: Iterable[VerifierToolCallSpec],
    *,
    gateway: LocalDeterministicToolGateway,
    tool_policy: ToolPolicy,
    admission_registry: ToolAdmissionRegistry,
    gateway_definitions: Mapping[ToolName, GatewayToolDefinition],
    audit_log_dir: Path,
    event_id: str,
    max_tool_calls: int,
) -> _ToolPhaseOutput:
    """Execute up to ``max_tool_calls`` specs through the gateway.

    The function never raises — admission failures, missing
    definitions, and adapter errors all surface as warnings or
    blockers + a ``status="blocked"`` result.
    """
    tool_results: list[VerifierToolResult] = []
    new_evidence: list[EvidenceItem] = []
    actionable_evidence: list[EvidenceItem] = []
    new_estimates: list[SignalEstimate] = []
    warnings: list[str] = []
    blockers: list[str] = []
    audit_paths: list[Path] = []
    missing_definition_tools: list[str] = []

    bounded_specs = tuple(specs)[:max_tool_calls]
    for spec in bounded_specs:
        definition = gateway_definitions.get(spec.tool)
        if definition is None:
            # Phase 5.2.1-B: missing definition is a real
            # blocker, not a soft warning. The post-pass-2
            # enforcer demotes any claim that depended on the
            # tool's evidence.
            blockers.append(
                f"requested tool {spec.tool!r} had no approved "
                "gateway definition; skipping (Phase 5.2.1-B)"
            )
            missing_definition_tools.append(spec.tool)
            continue
        request = tool_request_from_spec(spec)
        result = gateway.run(
            request,
            policy=tool_policy,
            admission_registry=admission_registry,
            audit_log_dir=audit_log_dir,
            gateway_definition=definition,
        )
        tool_results.append(result)
        audit_paths.append(audit_log_path(audit_log_dir, spec.tool))
        if result.evidence_items:
            new_evidence.extend(result.evidence_items)
            # Phase 5.8.1-B: only items from results whose tool actually
            # produced a meaningful signal (status="ok" or "failed") are
            # actionable. Diagnostic items synthesised by the adapter on
            # tool_missing/timeout/error paths land in ``new_evidence``
            # (so the aggregator's ref-existence rule passes) but NOT in
            # ``actionable_evidence`` (so they cannot promote a claim).
            if result.status in ("ok", "failed"):
                actionable_evidence.extend(result.evidence_items)
        new_estimates.extend(
            deterministic_estimates_from_tool_result(
                result, event_id=event_id,
            ),
        )
        if result.blockers:
            blockers.extend(result.blockers)
        if result.warnings:
            warnings.extend(result.warnings)
    return _ToolPhaseOutput(
        tool_results=tuple(tool_results),
        new_evidence=tuple(new_evidence),
        actionable_evidence=tuple(actionable_evidence),
        new_estimates=tuple(new_estimates),
        audit_paths=tuple(audit_paths),
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        requested_count=len(bounded_specs),
        missing_definition_tools=tuple(missing_definition_tools),
    )


def _enrich_packet(
    packet: LLMEvidencePacket,
    new_evidence: tuple[EvidenceItem, ...],
    new_estimates: tuple[SignalEstimate, ...],
) -> LLMEvidencePacket:
    """Return a NEW frozen packet with appended evidence + estimates.

    :class:`LLMEvidencePacket` is frozen, so ``model_copy(update=...)``
    is the only legal mutation path.
    """
    return packet.model_copy(update={
        "evidence_items": packet.evidence_items + new_evidence,
        "deterministic_estimates": (
            packet.deterministic_estimates + new_estimates
        ),
    })


def run_gateway_grounded_verifier(
    packet: LLMEvidencePacket,
    *,
    forward_pass1: VerifierProvider,
    backward_pass1: VerifierProvider,
    forward_pass2: VerifierProvider,
    backward_pass2: VerifierProvider,
    gateway: LocalDeterministicToolGateway,
    tool_policy: ToolPolicy,
    admission_registry: ToolAdmissionRegistry,
    gateway_definitions: Mapping[ToolName, GatewayToolDefinition],
    audit_log_dir: Path,
    max_tool_calls: int = _DEFAULT_MAX_TOOL_CALLS,
) -> GatewayGroundedVerifierRun:
    """Run the two-pass gateway-grounded verifier loop.

    Flow:

    #. Pass-1 forward + backward providers receive the original
       packet via :func:`run_verifier`. Both replays may carry
       arbitrary canned JSON; the runner is responsible for
       schema validation.
    #. The forward result's ``requested_tools`` is mapped to
       :class:`VerifierToolRequest`\\s and executed through the
       gateway. ``failed`` tool results yield deterministic
       :class:`SignalEstimate`\\s; ``error`` / ``timeout`` /
       ``tool_missing`` / ``blocked`` produce warnings + blockers.
    #. The packet is rebuilt with the new evidence + estimates.
    #. Pass-2 forward + backward providers receive the enriched
       packet; the aggregator decides.

    ``max_tool_calls`` defaults to 5 — the same budget as the
    existing :class:`ToolPolicy.max_tool_calls`. There is no
    retry loop and no third pass.
    """
    pass1 = run_verifier(
        packet, forward_pass1, backward_pass1,
    )
    requested_tools = _extract_requested_tools(pass1)
    tool_phase = _run_tool_phase(
        requested_tools,
        gateway=gateway,
        tool_policy=tool_policy,
        admission_registry=admission_registry,
        gateway_definitions=gateway_definitions,
        audit_log_dir=audit_log_dir,
        event_id=packet.event_id,
        max_tool_calls=max_tool_calls,
    )
    enriched_packet = _enrich_packet(
        packet,
        tool_phase.new_evidence,
        tool_phase.new_estimates,
    )

    pass2 = run_verifier(
        enriched_packet, forward_pass2, backward_pass2,
    )

    aggregated_warnings = (
        tuple(pass2.report.warnings) + tool_phase.warnings
    )
    aggregated_blockers = (
        tuple(pass2.report.blockers) + tool_phase.blockers
    )
    # Phase 5.8.1-B: the citation rule consumes only **actionable**
    # refs (items from results with status in {"ok", "failed"}).
    # Diagnostic items synthesised on error/timeout/tool_missing
    # paths are still in the enriched packet but cannot satisfy
    # the citation requirement — otherwise a tool that crashed
    # would silently certify a pass-2 claim that cited it.
    enriched_refs = tuple(
        ev.id for ev in tool_phase.actionable_evidence
    )

    # Phase 5.2.1-B: forward asked for tools but no [E.tool_output.*]
    # was produced (missing definition / all calls blocked /
    # adapter emitted nothing). Run BEFORE the citation rule so
    # the demotion is unambiguous and the report's status is
    # downgraded if needed.
    requested_evidence_enforced = _enforce_requested_tool_evidence(
        pass2.report,
        tool_phase=tool_phase,
        warnings=aggregated_warnings,
        blockers=aggregated_blockers,
    )

    citation_enforced = _enforce_pass2_tool_citation(
        requested_evidence_enforced,
        enriched_refs=enriched_refs,
        warnings=tuple(requested_evidence_enforced.warnings),
        blockers=tuple(requested_evidence_enforced.blockers),
    )

    return GatewayGroundedVerifierRun(
        report=citation_enforced,
        first_pass_report=pass1.report,
        tool_results=tool_phase.tool_results,
        audit_log_paths=tuple(str(p) for p in tool_phase.audit_paths),
        enriched_evidence_refs=enriched_refs,
        warnings=tool_phase.warnings,
        blockers=tool_phase.blockers,
    )


def _enforce_requested_tool_evidence(
    pass2: VerifierAggregationReport,
    *,
    tool_phase: _ToolPhaseOutput,
    warnings: tuple[str, ...],
    blockers: tuple[str, ...],
) -> VerifierAggregationReport:
    """Enforce QA/A30 §5.2.1-B.

    When forward requested at least one tool BUT no
    ``[E.tool_output.*]`` evidence ended up in the enriched
    packet, the loop must:

    1. Surface a specific blocker explaining the citation gap
       (sub-cases: missing definition, all calls blocked,
       gateway ran with no findings).
    2. Demote every pass-2 ``accepted_claim`` to
       ``unsupported_claims`` — even claims whose
       ``evidence_refs`` happen to look complete on their own.
    3. Force the report status away from
       ``verification_candidate`` (the loop's MEASURE rule:
       you cannot promote a claim to the highest status if the
       tool you asked for never spoke).

    The function is a NO-OP when:

    * forward did not request any tool (``requested_count==0``),
      or
    * tools ran AND produced at least one **actionable**
      EvidenceItem (``tool_phase.actionable_evidence`` non-empty)
      — in that case :func:`_enforce_pass2_tool_citation` is the
      right rule.

    Phase 5.8.1-B: the guard switched from ``new_evidence`` to
    ``actionable_evidence``. Diagnostic items synthesised on
    error/timeout/tool_missing paths populate ``new_evidence``
    (so aggregator rule 3 stops rejecting on missing-ref) but
    NOT ``actionable_evidence`` — so a tool that failed cannot
    silently promote a pass-2 claim.
    """
    if tool_phase.requested_count == 0 or tool_phase.actionable_evidence:
        return pass2.model_copy(update={
            "warnings": warnings,
            "blockers": blockers,
        })

    new_blockers = list(blockers)
    new_warnings = list(warnings)

    # Sub-case 1: at least one spec had no gateway definition.
    if tool_phase.missing_definition_tools:
        new_blockers.append(
            "requested tool evidence unavailable: missing gateway "
            "definition for "
            f"{sorted(set(tool_phase.missing_definition_tools))} "
            "(Phase 5.2.1-B)"
        )

    # Sub-case 2: every gateway call returned status=blocked.
    if (
        tool_phase.tool_results
        and all(
            r.status == "blocked" for r in tool_phase.tool_results
        )
    ):
        new_blockers.append(
            "requested tool evidence unavailable: gateway blocked "
            "all calls (Phase 5.2.1-B)"
        )
    # Sub-case 3: gateway ran but produced no **actionable** evidence.
    # Phase 5.8.1-B: covers two flavours -
    #   - tool ran cleanly but emitted nothing citable (legacy: ruff
    #     with no findings + no synth pass item),
    #   - tool errored / timed out / was missing, so the only items
    #     in ``new_evidence`` are adapter-synthesised diagnostics.
    # Either way, no pass-2 claim can be promoted.
    elif (
        tool_phase.tool_results
        and not tool_phase.actionable_evidence
    ):
        if any(
            r.status in ("error", "timeout", "tool_missing")
            for r in tool_phase.tool_results
        ):
            new_blockers.append(
                "requested tool produced only diagnostic evidence "
                "(adapter status in error/timeout/tool_missing); "
                "cannot promote pass-2 claims (Phase 5.8.1-B)"
            )
        else:
            new_blockers.append(
                "requested tool ran but emitted no citable evidence; "
                "cannot promote pass-2 claims (Phase 5.2.1-B)"
            )

    # Demote every accepted_claim to unsupported.
    new_unsupported = list(pass2.unsupported_claims)
    for claim in pass2.accepted_claims:
        new_warnings.append(
            f"claim {claim.claim_id} demoted: forward requested "
            "tool evidence but the loop produced no "
            "[E.tool_output.*] ref (Phase 5.2.1-B)"
        )
        new_unsupported.append(claim)

    # Force status off verification_candidate.
    new_status = pass2.status
    if new_status == "verification_candidate":
        new_status = "diagnostic_only"

    # Phase 5.8.1-B: regenerate the recommendation string after the
    # demotion so it reflects the post-enforcer counts. Otherwise the
    # report.recommendation lies (e.g. "accepted=1 rejected=0
    # unsupported=0" when accepted_claims was just emptied), which
    # confuses operator-readable summaries.
    from oida_code.verifier.aggregator import _recommendation_for

    new_recommendation = _recommendation_for(
        new_status,
        0,  # accepted is now empty
        len(pass2.rejected_claims),
        len(new_unsupported),
    )

    return pass2.model_copy(update={
        "accepted_claims": (),
        "unsupported_claims": tuple(new_unsupported),
        "status": new_status,
        "warnings": tuple(new_warnings),
        "blockers": tuple(new_blockers),
        "recommendation": new_recommendation,
    })


def _enforce_pass2_tool_citation(
    pass2: VerifierAggregationReport,
    *,
    enriched_refs: tuple[str, ...],
    warnings: tuple[str, ...],
    blockers: tuple[str, ...],
) -> VerifierAggregationReport:
    """Apply the Phase 5.2 citation rule.

    QA/A29 §5.2-C criterion #10 — *"Second-pass claims must cite
    tool evidence when tool was needed"*.

    When the loop ran tools (i.e. ``enriched_refs`` is non-empty),
    any pass-2 ``accepted_claim`` that does NOT cite at least one
    of those refs is demoted to ``unsupported_claims`` and a
    warning is recorded. The claim is not "rejected" because the
    LLM-side reasoning may still be coherent — it merely failed
    to incorporate the deterministic evidence the loop just
    surfaced.

    If no tools ran, the rule is a no-op (legitimate — pass-1
    asked for nothing).
    """
    if not enriched_refs:
        return pass2.model_copy(update={
            "warnings": warnings,
            "blockers": blockers,
        })
    from oida_code.verifier.contracts import VerifierClaim

    enriched_set = set(enriched_refs)
    new_accepted: list[VerifierClaim] = []
    new_unsupported: list[VerifierClaim] = list(pass2.unsupported_claims)
    new_warnings = list(warnings)
    for claim in pass2.accepted_claims:
        if not enriched_set.intersection(claim.evidence_refs):
            new_warnings.append(
                f"claim {claim.claim_id} accepted by pass-2 "
                "verifier but does not cite any tool evidence "
                f"({sorted(enriched_set)}); demoting to "
                "unsupported (Phase 5.2 §5.2-C citation rule)"
            )
            new_unsupported.append(claim)
            continue
        new_accepted.append(claim)
    # Phase 5.8.1-B: regenerate the recommendation string when the
    # demotion changed counts — otherwise the report.recommendation
    # carries stale numbers from before the citation rule fired.
    update: dict[str, object] = {
        "accepted_claims": tuple(new_accepted),
        "unsupported_claims": tuple(new_unsupported),
        "warnings": tuple(new_warnings),
        "blockers": blockers,
    }
    if len(new_accepted) != len(pass2.accepted_claims):
        from oida_code.verifier.aggregator import _recommendation_for
        update["recommendation"] = _recommendation_for(
            pass2.status,
            len(new_accepted),
            len(pass2.rejected_claims),
            len(new_unsupported),
        )
    return pass2.model_copy(update=update)


def _extract_requested_tools(
    pass1: VerifierRun,
) -> tuple[VerifierToolCallSpec, ...]:
    """Pass-1 stores the forward-side raw response separately;
    we only have the parsed report. Re-parse the forward replay
    to extract ``requested_tools``. If the replay was malformed,
    return the empty tuple — the loop simply skips the tool
    phase.
    """
    raw = pass1.forward_raw
    if raw is None:
        return ()
    import json as _json

    try:
        decoded = _json.loads(raw)
    except _json.JSONDecodeError:
        return ()
    if not isinstance(decoded, dict):
        return ()
    raw_specs = decoded.get("requested_tools", ())
    if not isinstance(raw_specs, list):
        return ()
    out: list[VerifierToolCallSpec] = []
    for entry in raw_specs:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(VerifierToolCallSpec.model_validate(entry))
        except Exception:
            continue
    return tuple(out)


__all__ = [
    "GatewayGroundedVerifierRun",
    "deterministic_estimates_from_tool_result",
    "run_gateway_grounded_verifier",
    "tool_request_from_spec",
]
