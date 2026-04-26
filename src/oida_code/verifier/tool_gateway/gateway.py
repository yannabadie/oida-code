"""Phase 5.1-E (QA/A28.md, ADR-36) — gateway execution wrapper.

:class:`LocalDeterministicToolGateway` wraps the existing
deterministic tool engine
(``src/oida_code/verifier/tools/``) with admission +
fingerprinting + audit-log layers. The gateway:

1. Loads a :class:`GatewayToolDefinition` for the requested
   tool.
2. Re-fingerprints the observed definition.
3. Compares against the locally-stored expected fingerprint
   (:class:`ToolAdmissionRegistry`).
4. Validates the request through the existing
   :class:`ToolPolicy` (path traversal + secret-path deny
   patterns + allowlist + budget).
5. Invokes the existing adapter via
   :func:`oida_code.verifier.tools.registry.get_adapter`.
6. Writes one :class:`ToolGatewayAuditEvent` per decision.
7. Returns the existing :class:`VerifierToolResult` shape —
   the gateway is a wrapper, NOT a new pipeline stage from
   the aggregator's perspective.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oida_code.verifier.tool_gateway.audit_log import (
    append_audit_event,
    build_audit_event,
)
from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    RequestedBy,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tool_gateway.fingerprints import (
    fingerprint_tool_definition,
)
from oida_code.verifier.tools.adapters import (
    Executor,
    default_subprocess_executor,
)
from oida_code.verifier.tools.contracts import (
    ToolPolicy,
    VerifierToolRequest,
    VerifierToolResult,
)
from oida_code.verifier.tools.registry import get_adapter
from oida_code.verifier.tools.sandbox import (
    SandboxViolation,
    validate_request,
)


def _summarise_request(request: VerifierToolRequest) -> str:
    """Short, human-readable summary for the audit log. NEVER
    contains raw arguments / paths beyond the per-tool scope
    list, NEVER contains secret-like values (the existing
    sandbox already rejects scopes that match deny patterns)."""
    scope_label = ", ".join(request.scope) or "(no scope)"
    return f"{request.tool} on [{scope_label}] (purpose: {request.purpose})"


@dataclass
class LocalDeterministicToolGateway:
    """Runtime gateway wrapping the existing tool adapters.

    ``executor`` is the same ``Executor`` callable the existing
    :class:`ToolExecutionEngine` uses. Tests inject a fake
    executor to avoid spawning subprocesses; production uses
    :func:`default_subprocess_executor`.

    Phase 5.1 design rule: this gateway returns
    :class:`VerifierToolResult` exactly — the same type the
    existing engine returns. No new wrapper type. The audit
    log is a side effect; the aggregator is unaware of it.
    """

    executor: Executor = field(default=default_subprocess_executor)

    def run(
        self,
        request: VerifierToolRequest,
        *,
        policy: ToolPolicy,
        admission_registry: ToolAdmissionRegistry,
        audit_log_dir: Path,
        gateway_definition: GatewayToolDefinition,
        case_id: str | None = None,
        requested_by: RequestedBy = "verifier",
    ) -> VerifierToolResult:
        """Drive one tool request through the gateway.

        ``gateway_definition`` is the AS-OBSERVED definition of
        the tool the caller is about to invoke; the gateway
        re-fingerprints it and compares against
        ``admission_registry.approved`` to decide whether to
        execute.

        Failure modes (each emits one audit event):

        * No approved decision for ``tool_id`` → block (status
          ``blocked``).
        * Hash drift vs. approved fingerprint → quarantine
          (status ``blocked``).
        * Sandbox / policy violation → block (status
          ``blocked``).
        * Definition itself rejected (write / network /
          suspicious description) → reject (status
          ``blocked``). *(Cannot occur via this method because
          the registry is consulted upstream; included for
          completeness.)*
        """
        observed = fingerprint_tool_definition(gateway_definition)

        # Stage 1: registry lookup.
        approved = self._lookup_approved(
            admission_registry, gateway_definition.tool_id,
        )
        if approved is None:
            event = build_audit_event(
                tool_id=gateway_definition.tool_id,
                tool_name=gateway_definition.tool_name,
                fingerprint=observed,
                requested_by=requested_by,
                request_summary=_summarise_request(request),
                allowed=False,
                policy_decision="block",
                reason=(
                    f"tool_id {gateway_definition.tool_id!r} has "
                    "no `approved_read_only` decision in the "
                    "admission registry"
                ),
                case_id=case_id,
            )
            append_audit_event(event, audit_log_dir)
            return self._blocked_result(request, event.reason)

        # Stage 2: hash drift check.
        if observed.combined_sha256 != approved.fingerprint.combined_sha256:
            event = build_audit_event(
                tool_id=gateway_definition.tool_id,
                tool_name=gateway_definition.tool_name,
                fingerprint=observed,
                requested_by=requested_by,
                request_summary=_summarise_request(request),
                allowed=False,
                policy_decision="quarantine",
                reason=(
                    "fingerprint drift — observed combined_sha256 "
                    "does not match the approved fingerprint"
                ),
                case_id=case_id,
            )
            append_audit_event(event, audit_log_dir)
            return self._blocked_result(request, event.reason)

        # Stage 3: existing ToolPolicy / sandbox validation.
        try:
            validate_request(request, policy)
        except SandboxViolation as exc:
            event = build_audit_event(
                tool_id=gateway_definition.tool_id,
                tool_name=gateway_definition.tool_name,
                fingerprint=observed,
                requested_by=requested_by,
                request_summary=_summarise_request(request),
                allowed=False,
                policy_decision="block",
                reason=f"sandbox violation: {exc}",
                case_id=case_id,
            )
            append_audit_event(event, audit_log_dir)
            return self._blocked_result(request, event.reason)

        # Stage 4: invoke the existing adapter.
        adapter = get_adapter(request.tool)
        t_start = time.perf_counter()
        try:
            result = adapter.run(
                request,
                repo_root=policy.repo_root,
                executor=self.executor,
                max_output_chars=policy.max_output_chars_per_tool,
            )
        except Exception as exc:
            wall_clock_ms = int(
                (time.perf_counter() - t_start) * 1000,
            )
            event = build_audit_event(
                tool_id=gateway_definition.tool_id,
                tool_name=gateway_definition.tool_name,
                fingerprint=observed,
                requested_by=requested_by,
                request_summary=_summarise_request(request),
                allowed=False,
                policy_decision="block",
                reason=(
                    f"adapter execution raised "
                    f"{type(exc).__name__}: {exc}"
                ),
                case_id=case_id,
            )
            append_audit_event(event, audit_log_dir)
            return self._blocked_result(
                request,
                f"adapter error: {type(exc).__name__}",
                runtime_ms=wall_clock_ms,
            )

        # Stage 5: success path — emit the allow event.
        event = build_audit_event(
            tool_id=gateway_definition.tool_id,
            tool_name=gateway_definition.tool_name,
            fingerprint=observed,
            requested_by=requested_by,
            request_summary=_summarise_request(request),
            allowed=True,
            policy_decision="allow",
            reason=f"adapter completed with status={result.status}",
            case_id=case_id,
            evidence_refs=tuple(
                ev.id for ev in result.evidence_items
            ),
        )
        append_audit_event(event, audit_log_dir)
        return result

    def _lookup_approved(
        self,
        registry: ToolAdmissionRegistry,
        tool_id: str,
    ) -> Any:
        for decision in registry.approved:
            if decision.tool_id == tool_id:
                return decision
        return None

    def _blocked_result(
        self,
        request: VerifierToolRequest,
        reason: str,
        *,
        runtime_ms: int = 0,
    ) -> VerifierToolResult:
        return VerifierToolResult(
            tool=request.tool,
            status="blocked",
            warnings=(reason,),
            runtime_ms=runtime_ms,
        )


__all__ = [
    "LocalDeterministicToolGateway",
]
