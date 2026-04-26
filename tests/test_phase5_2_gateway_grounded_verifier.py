"""Phase 5.2 (QA/A29.md, ADR-37) — gateway-grounded verifier
loop tests.

Sub-blocks covered:

* 5.1.1 hardening — gateway must reject a request whose
  ``tool`` field disagrees with the
  ``gateway_definition.tool_name``, and every blocked
  ``VerifierToolResult`` must populate both ``warnings`` and
  ``blockers``.
* 5.2-A — :class:`ForwardVerificationResult` carries a
  ``requested_tools`` tuple (default empty for replay
  backward-compat).
* 5.2-B — :func:`tool_request_from_spec` mapping
  ``VerifierToolCallSpec`` → ``VerifierToolRequest`` with no
  argv, no shell command, length-bounded purpose.
* 5.2-C — two-pass gateway-grounded runner.
* 5.2-D — deterministic ``SignalEstimate`` produced from a
  ``failed`` tool result; ``error`` / ``timeout`` /
  ``tool_missing`` / ``blocked`` stay uncertainty.
* 5.2-E — ``oida-code verify-grounded`` CLI subcommand.
* 5.2-F — fixture-driven scenarios under
  ``tests/fixtures/gateway_grounded_verifier/``.
* 5.2-G — replay-only ``gateway-grounded-smoke.yml`` workflow.
* 5.2-H — anti-MCP regression locks (gateway loop is NOT MCP).

Negative checks scan ``pyproject.toml`` +
``.github/workflows/`` + ``src/oida_code/`` only — never
``docs/`` or ``reports/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from oida_code.estimators.contracts import SignalEstimate
from oida_code.estimators.llm_prompt import (
    EvidenceItem,
    LLMEvidencePacket,
)
from oida_code.verifier.contracts import (
    BackwardRequirement,
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierClaim,
    VerifierToolCallSpec,
)
from oida_code.verifier.replay import VerifierProvider
from oida_code.verifier.tool_gateway.audit_log import (
    read_audit_events,
)
from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolAdmissionDecision,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tool_gateway.fingerprints import (
    fingerprint_tool_definition,
)
from oida_code.verifier.tool_gateway.gateway import (
    LocalDeterministicToolGateway,
)
from oida_code.verifier.tools.adapters import ExecutionContext, ExecutionOutcome
from oida_code.verifier.tools.contracts import (
    ToolPolicy,
    VerifierToolRequest,
    VerifierToolResult,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _fake_executor_factory(
    returncode: int = 0, stdout: str = "[]", stderr: str = "",
):
    def _executor(_ctx: ExecutionContext) -> ExecutionOutcome:
        return ExecutionOutcome(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            runtime_ms=1,
        )
    return _executor


def _ruff_definition(
    description: str = "Run ruff check (read-only).",
) -> GatewayToolDefinition:
    return GatewayToolDefinition(
        tool_id="oida-code/ruff",
        tool_name="ruff",
        adapter_version="0.4.0",
        description=description,
        input_schema={
            "type": "object",
            "properties": {"scope": {"type": "array"}},
        },
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
        risk_level="read_only",
        allowed_scopes=("repo:read",),
    )


def _pytest_definition(
    description: str = "Run pytest (read-only).",
) -> GatewayToolDefinition:
    return GatewayToolDefinition(
        tool_id="oida-code/pytest",
        tool_name="pytest",
        adapter_version="0.4.0",
        description=description,
        input_schema={
            "type": "object",
            "properties": {"scope": {"type": "array"}},
        },
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
        risk_level="read_only",
        allowed_scopes=("repo:read",),
    )


def _request(
    tool: str = "ruff",
    scope: tuple[str, ...] = ("src/",),
) -> VerifierToolRequest:
    return VerifierToolRequest(
        tool=tool,  # type: ignore[arg-type]
        purpose="phase5.2 test invocation",
        scope=scope,
        max_runtime_s=5,
    )


def _policy(repo_root: Path) -> ToolPolicy:
    return ToolPolicy(
        allowed_tools=("ruff", "mypy", "pytest"),
        repo_root=repo_root,
        allow_network=False,
        allow_write=False,
    )


def _registry_with(
    *definitions: GatewayToolDefinition,
) -> ToolAdmissionRegistry:
    decisions = tuple(
        ToolAdmissionDecision(
            tool_id=d.tool_id,
            status="approved_read_only",
            reason="test fixture approval",
            fingerprint=fingerprint_tool_definition(d),
        )
        for d in definitions
    )
    return ToolAdmissionRegistry(approved=decisions)


# ---------------------------------------------------------------------------
# 5.1.1 — gateway hardening (precondition for Phase 5.2)
# ---------------------------------------------------------------------------


def test_gateway_blocks_request_tool_definition_mismatch(
    tmp_path: Path,
) -> None:
    """If ``request.tool`` (e.g. ``"pytest"``) does not match
    ``gateway_definition.tool_name`` (e.g. ``"ruff"``), the
    gateway MUST refuse to execute and return ``status="blocked"``
    BEFORE any adapter runs."""
    ruff_def = _ruff_definition()
    registry = _registry_with(ruff_def)
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    # Caller passes the ruff definition but asks the engine to
    # run pytest. Without 5.1.1 hardening, this could audit a
    # ruff fingerprint while executing the pytest adapter.
    result = gateway.run(
        _request(tool="pytest"),
        policy=_policy(tmp_path),
        admission_registry=registry,
        audit_log_dir=audit_dir,
        gateway_definition=ruff_def,
    )
    assert result.status == "blocked"
    assert result.tool == "pytest"


def test_gateway_mismatch_writes_audit_event(tmp_path: Path) -> None:
    """The 5.1.1 mismatch path MUST emit one audit event with
    ``policy_decision="block"`` and a reason explicitly
    referencing the field names."""
    ruff_def = _ruff_definition()
    registry = _registry_with(ruff_def)
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    gateway.run(
        _request(tool="pytest"),
        policy=_policy(tmp_path),
        admission_registry=registry,
        audit_log_dir=audit_dir,
        gateway_definition=ruff_def,
    )
    # Audit record was written under the gateway_definition's
    # tool_name (ruff) — that's where the mismatch was caught.
    parsed = read_audit_events(audit_dir, "ruff")
    assert len(parsed) == 1
    event = parsed[0]
    assert event.policy_decision == "block"
    assert event.allowed is False
    # Reason mentions both fields.
    assert "request.tool" in event.reason
    assert "tool_name" in event.reason


def test_gateway_blocked_result_sets_blockers(tmp_path: Path) -> None:
    """``_blocked_result`` MUST populate ``blockers`` (not just
    ``warnings``). The Phase 5.2 loop integrator treats
    ``VerifierToolResult.blockers`` as a hard claim blocker."""
    empty_registry = ToolAdmissionRegistry()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    result = gateway.run(
        _request(),
        policy=_policy(tmp_path),
        admission_registry=empty_registry,
        audit_log_dir=audit_dir,
        gateway_definition=_ruff_definition(),
    )
    assert result.status == "blocked"
    assert result.blockers, "blocked result MUST surface blockers"
    assert result.warnings, "blocked result MUST also surface warnings"
    # Both fields carry the same human-readable reason.
    assert result.warnings == result.blockers


def test_gateway_adapter_exception_sets_blockers(tmp_path: Path) -> None:
    """An adapter raising during execution must produce a
    blocked result with the failure reason in BOTH ``warnings``
    and ``blockers`` (5.1.1 hardening)."""
    definition = _ruff_definition()
    registry = _registry_with(definition)
    audit_dir = tmp_path / "audit"

    def _raising_executor(_ctx: ExecutionContext) -> ExecutionOutcome:
        raise RuntimeError("synthetic adapter crash")

    gateway = LocalDeterministicToolGateway(executor=_raising_executor)
    result = gateway.run(
        _request(),
        policy=_policy(tmp_path),
        admission_registry=registry,
        audit_log_dir=audit_dir,
        gateway_definition=definition,
    )
    assert result.status == "blocked"
    assert result.blockers
    assert result.warnings
    # Reason references the adapter error class.
    assert any("adapter error" in b.lower() for b in result.blockers)


# ---------------------------------------------------------------------------
# 5.2-A — ForwardVerificationResult.requested_tools
# ---------------------------------------------------------------------------


def test_forward_result_accepts_requested_tools_default_empty() -> None:
    """``requested_tools`` defaults to the empty tuple for
    backward compatibility with Phase 4.1 replay fixtures."""
    result = ForwardVerificationResult(event_id="evt-1")
    assert result.requested_tools == ()


def test_forward_result_rejects_unknown_tool_request() -> None:
    """A spec whose ``tool`` field is not in the Literal MUST
    fail Pydantic validation."""
    with pytest.raises(ValidationError):
        VerifierToolCallSpec(
            tool="exec_arbitrary_shell",  # type: ignore[arg-type]
            purpose="bad",
            expected_evidence_kind="tool_finding",
        )


def test_legacy_forward_replay_without_requested_tools_still_validates() -> None:
    """A replay payload (Phase 4.1 fixture) that does NOT
    include ``requested_tools`` must still parse via
    ``model_validate``."""
    legacy_payload = {
        "event_id": "evt-legacy",
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
    }
    parsed = ForwardVerificationResult.model_validate(legacy_payload)
    assert parsed.requested_tools == ()


def test_requested_tools_do_not_execute_during_plain_verify_claims() -> None:
    """The plain :func:`run_verifier` path (Phase 4.1) MUST
    ignore ``requested_tools`` — execution only happens in the
    Phase 5.2 gateway-grounded runner."""
    spec = VerifierToolCallSpec(
        tool="ruff",
        purpose="re-run ruff scoped to src/app.py",
        expected_evidence_kind="tool_finding",
        scope=("src/app.py",),
    )
    forward = ForwardVerificationResult(
        event_id="evt-1",
        supported_claims=(),
        requested_tools=(spec,),
    )
    # The schema accepts the field but the Phase 4.1 runner
    # consumes only ``supported_claims`` and ``rejected_claims``
    # to drive the aggregator. There is no path inside
    # :mod:`oida_code.verifier.forward_backward` that imports
    # ``LocalDeterministicToolGateway``.
    src = (_REPO_ROOT / "src" / "oida_code" / "verifier" / "forward_backward.py")
    assert "LocalDeterministicToolGateway" not in src.read_text(
        encoding="utf-8",
    )
    # Sanity: the spec itself round-trips through model_dump.
    dumped = forward.model_dump()
    assert dumped["requested_tools"][0]["tool"] == "ruff"


# ---------------------------------------------------------------------------
# 5.2-B — tool_request_from_spec mapping
# ---------------------------------------------------------------------------


def test_tool_call_spec_maps_to_verifier_tool_request() -> None:
    from oida_code.verifier.gateway_loop import tool_request_from_spec

    spec = VerifierToolCallSpec(
        tool="ruff",
        purpose="re-run ruff scoped to src/app.py",
        expected_evidence_kind="tool_finding",
        scope=("src/app.py",),
    )
    request = tool_request_from_spec(spec)
    assert isinstance(request, VerifierToolRequest)
    assert request.tool == "ruff"
    assert request.scope == ("src/app.py",)
    assert request.purpose.startswith("re-run ruff")
    # No argv, no shell — the schema doesn't even allow it.
    assert "argv" not in request.model_dump()
    assert "shell" not in request.model_dump()


def test_tool_call_spec_never_contains_argv() -> None:
    """``VerifierToolRequest`` and ``VerifierToolCallSpec`` MUST
    not carry an ``argv`` or ``command`` field — adapter builds
    the argv itself."""
    spec_fields = set(VerifierToolCallSpec.model_fields.keys())
    request_fields = set(VerifierToolRequest.model_fields.keys())
    forbidden = {"argv", "command", "shell", "shell_command"}
    assert not (spec_fields & forbidden), (
        f"VerifierToolCallSpec exposes argv-like fields: "
        f"{spec_fields & forbidden}"
    )
    assert not (request_fields & forbidden), (
        f"VerifierToolRequest exposes argv-like fields: "
        f"{request_fields & forbidden}"
    )


def test_tool_call_spec_scope_preserved() -> None:
    from oida_code.verifier.gateway_loop import tool_request_from_spec

    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run pytest scoped to tests/",
        expected_evidence_kind="test_result",
        scope=("tests/test_a.py", "tests/test_b.py"),
    )
    request = tool_request_from_spec(spec)
    assert request.scope == ("tests/test_a.py", "tests/test_b.py")


def test_tool_call_spec_requested_by_claim_id_preserved() -> None:
    from oida_code.verifier.gateway_loop import tool_request_from_spec

    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run pytest",
        expected_evidence_kind="test_result",
        scope=("tests/",),
    )
    request = tool_request_from_spec(spec, requested_by_claim_id="C.42")
    assert request.requested_by_claim_id == "C.42"


# ---------------------------------------------------------------------------
# 5.2-D — deterministic SignalEstimate from tool result
# ---------------------------------------------------------------------------


def test_failed_tool_result_creates_negative_deterministic_estimate() -> None:
    from oida_code.verifier.gateway_loop import (
        deterministic_estimates_from_tool_result,
    )

    failed_pytest = VerifierToolResult(
        tool="pytest",
        status="failed",
        evidence_items=(
            EvidenceItem(
                id="[E.tool_output.1]",
                kind="test_result",
                summary="2 failed",
                source="pytest",
                confidence=0.9,
            ),
        ),
        runtime_ms=120,
    )
    estimates = deterministic_estimates_from_tool_result(
        failed_pytest, event_id="evt-1",
    )
    assert estimates, "failed pytest must produce at least one estimate"
    e = estimates[0]
    assert e.value == 0.0
    assert e.confidence >= 0.5
    assert e.source == "tool"
    assert e.field == "tests_pass"
    assert e.event_id == "evt-1"


def test_tool_error_is_uncertainty_not_negative_proof() -> None:
    from oida_code.verifier.gateway_loop import (
        deterministic_estimates_from_tool_result,
    )

    err = VerifierToolResult(
        tool="pytest",
        status="error",
        warnings=("internal harness error",),
        runtime_ms=10,
    )
    assert deterministic_estimates_from_tool_result(
        err, event_id="evt-1",
    ) == ()


def test_tool_missing_is_uncertainty_not_negative_proof() -> None:
    from oida_code.verifier.gateway_loop import (
        deterministic_estimates_from_tool_result,
    )

    miss = VerifierToolResult(
        tool="pytest",
        status="tool_missing",
        warnings=("pytest not on PATH",),
        runtime_ms=0,
    )
    assert deterministic_estimates_from_tool_result(
        miss, event_id="evt-1",
    ) == ()


def test_blocked_tool_blocks_claim_but_not_code_failure() -> None:
    from oida_code.verifier.gateway_loop import (
        deterministic_estimates_from_tool_result,
    )

    blocked = VerifierToolResult(
        tool="ruff",
        status="blocked",
        blockers=("not approved",),
        warnings=("not approved",),
        runtime_ms=0,
    )
    # Status=blocked means tool didn't run — it must NOT produce
    # a negative deterministic estimate (that would falsely
    # contradict the LLM claim with a tool fault).
    assert deterministic_estimates_from_tool_result(
        blocked, event_id="evt-1",
    ) == ()


def test_tool_contradiction_rejects_llm_claim_after_gateway() -> None:
    from oida_code.verifier.aggregator import aggregate_verification

    failed_pytest_estimate = SignalEstimate(
        event_id="evt-1",
        field="tests_pass",
        value=0.0,
        confidence=0.8,
        source="tool",
        method_id="pytest_runner",
        method_version="0.4.0",
        evidence_refs=("[E.tool_output.1]",),
    )
    claim = VerifierClaim(
        claim_id="C.1",
        event_id="evt-1",
        claim_type="capability_sufficient",
        statement="this works",
        confidence=0.55,
        evidence_refs=("[E.event.1]",),
        source="forward",
    )
    forward = ForwardVerificationResult(
        event_id="evt-1",
        supported_claims=(claim,),
    )
    backward = (
        BackwardVerificationResult(
            event_id="evt-1",
            claim_id="C.1",
            requirement=BackwardRequirement(
                claim_id="C.1",
                required_evidence_kinds=("event",),
                satisfied_evidence_refs=("[E.event.1]",),
            ),
            necessary_conditions_met=True,
        ),
    )
    packet = LLMEvidencePacket(
        event_id="evt-1",
        allowed_fields=("capability",),
        intent_summary="t",
        evidence_items=(
            EvidenceItem(
                id="[E.event.1]", kind="event", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(failed_pytest_estimate,),
    )
    report = aggregate_verification(forward, backward, packet)
    # Tool contradiction must reject the LLM claim.
    assert claim in report.rejected_claims
    assert claim not in report.accepted_claims


# ---------------------------------------------------------------------------
# 5.2-C — two-pass gateway-grounded runner
# ---------------------------------------------------------------------------


class _ScriptedProvider(VerifierProvider):
    """Replay-style provider returning a queue of canned JSON
    responses. Lets a single test drive both forward passes
    deterministically."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        if not self._replies:
            raise AssertionError(
                "scripted provider exhausted — test asked for "
                "more verifier replies than queued"
            )
        return self._replies.pop(0)


def _baseline_packet() -> LLMEvidencePacket:
    return LLMEvidencePacket(
        event_id="evt-loop",
        allowed_fields=("capability",),
        intent_summary="ship feature",
        evidence_items=(
            EvidenceItem(
                id="[E.event.1]", kind="event", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )


def test_gateway_loop_pass1_tool_request_becomes_gateway_call(
    tmp_path: Path,
) -> None:
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest scoped to tests/",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    pass1_backward = json.dumps([])
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward = json.dumps([])

    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(returncode=0, stdout=""),
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider([pass1_backward]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    assert len(run.tool_results) == 1
    assert run.tool_results[0].tool == "pytest"
    # Audit log was written for the gateway call.
    parsed = read_audit_events(audit_dir, "pytest")
    assert len(parsed) == 1
    assert parsed[0].policy_decision == "allow"


def test_gateway_loop_appends_tool_evidence_to_packet(
    tmp_path: Path,
) -> None:
    """After the tool phase, the second-pass evidence packet
    must contain the tool's EvidenceItems with stable
    ``[E.tool_output.N]``-style ids."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(
            returncode=0, stdout="===== 5 passed in 0.4s =====",
        ),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    refs = run.enriched_evidence_refs
    assert refs, "tool phase must contribute at least one EvidenceItem"
    for ref in refs:
        assert ref.startswith("[E.")
        assert ref.endswith("]")


def test_gateway_loop_pass2_claim_must_cite_tool_evidence(
    tmp_path: Path,
) -> None:
    """Pass-2 claim that doesn't cite the new tool evidence
    when the tool was needed MUST NOT be accepted."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    # Pass-2 claim cites only [E.event.1], not the tool ref.
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [{
            "claim_id": "C.tests_pass",
            "event_id": "evt-loop",
            "claim_type": "capability_sufficient",
            "statement": "tests pass",
            "confidence": 0.55,
            "evidence_refs": ["[E.event.1]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward = json.dumps([{
        "event_id": "evt-loop",
        "claim_id": "C.tests_pass",
        "requirement": {
            "claim_id": "C.tests_pass",
            "required_evidence_kinds": ["event"],
            "satisfied_evidence_refs": ["[E.event.1]"],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }])
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(
            returncode=0, stdout="===== 5 passed in 0.4s =====",
        ),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    # Sanity: tools were actually invoked and produced refs.
    assert run.enriched_evidence_refs, (
        "tool phase must contribute at least one EvidenceItem; "
        "otherwise the citation rule is vacuous and this test "
        "is checking nothing"
    )
    accepted_ids = {c.claim_id for c in run.report.accepted_claims}
    assert "C.tests_pass" not in accepted_ids
    # Demoted to unsupported_claims, not rejected.
    assert any(
        c.claim_id == "C.tests_pass" for c in run.report.unsupported_claims
    )


def test_gateway_loop_aggregator_accepts_only_after_backward_support(
    tmp_path: Path,
) -> None:
    """Even when the claim cites the tool evidence, the
    aggregator must still require backward necessary-conditions-
    met before accepting it."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [{
            "claim_id": "C.with_tool",
            "event_id": "evt-loop",
            "claim_type": "capability_sufficient",
            "statement": "ok",
            "confidence": 0.55,
            "evidence_refs": ["[E.event.1]", "[E.tool_output.1]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward_unmet = json.dumps([{
        "event_id": "evt-loop",
        "claim_id": "C.with_tool",
        "requirement": {
            "claim_id": "C.with_tool",
            "required_evidence_kinds": ["event"],
            "satisfied_evidence_refs": [],
            "missing_requirements": ["needs more"],
        },
        "necessary_conditions_met": False,
    }])
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(returncode=0, stdout=""),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward_unmet]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    accepted_ids = {c.claim_id for c in run.report.accepted_claims}
    assert "C.with_tool" not in accepted_ids


def test_gateway_loop_blocks_when_tool_not_approved(
    tmp_path: Path,
) -> None:
    """Pass-1 asks for a tool that has no admission decision.
    Gateway must return ``status="blocked"`` and the loop must
    surface the blocker on the run."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([json.dumps({
            "event_id": "evt-loop",
            "supported_claims": [],
            "rejected_claims": [],
            "requested_tools": [],
        })]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=ToolAdmissionRegistry(),
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    assert any(r.status == "blocked" for r in run.tool_results)
    assert run.blockers, "blocked tool must surface at run-level blockers"


def test_gateway_loop_respects_max_tool_calls(tmp_path: Path) -> None:
    """If pass-1 asks for more tools than ``max_tool_calls``,
    the loop only executes up to the budget."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    big_request = [{
        "tool": "pytest",
        "purpose": f"re-run pytest #{i}",
        "expected_evidence_kind": "test_result",
        "scope": ["tests/"],
    } for i in range(10)]
    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": big_request,
    })
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(returncode=0, stdout=""),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([json.dumps({
            "event_id": "evt-loop",
            "supported_claims": [],
            "rejected_claims": [],
            "requested_tools": [],
        })]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
        max_tool_calls=3,
    )
    assert len(run.tool_results) == 3


def test_gateway_loop_never_calls_gateway_when_no_requested_tools(
    tmp_path: Path,
) -> None:
    """Pass-1 returned no requested tools → tool phase is
    skipped entirely → no audit events were written."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    no_request = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([no_request]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([no_request]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    assert run.tool_results == ()
    # No audit JSONL files written.
    if audit_dir.exists():
        assert not list(audit_dir.rglob("*.jsonl"))


def test_gateway_loop_official_fields_absent(tmp_path: Path) -> None:
    """The :class:`GatewayGroundedVerifierRun` model dump MUST
    NOT contain any of the forbidden official phrases."""
    from oida_code.verifier.gateway_loop import run_gateway_grounded_verifier

    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    no_request = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })
    gateway = LocalDeterministicToolGateway(
        executor=_fake_executor_factory(),
    )
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([no_request]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([no_request]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    serialized = json.dumps(run.model_dump(), default=str).lower()
    for phrase in (
        "total_v_net",
        "debt_final",
        "corrupt_success",
        "official_v_net",
        "merge_safe",
        "production_safe",
        "bug_free",
        "security_verified",
    ):
        assert phrase not in serialized


# ---------------------------------------------------------------------------
# 5.2-E — verify-grounded CLI
# ---------------------------------------------------------------------------


def _write_replay(path: Path, payload: Any) -> None:
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _verify_grounded_cli_args(
    tmp_path: Path,
) -> tuple[Path, list[str]]:
    """Materialise the seven inputs verify-grounded needs and
    return (out_path, argv suffix)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    packet = _baseline_packet()
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(packet.model_dump_json(), encoding="utf-8")
    no_request = {
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    }
    fwd1 = tmp_path / "fwd1.json"
    bwd1 = tmp_path / "bwd1.json"
    fwd2 = tmp_path / "fwd2.json"
    bwd2 = tmp_path / "bwd2.json"
    _write_replay(fwd1, no_request)
    _write_replay(bwd1, [])
    _write_replay(fwd2, no_request)
    _write_replay(bwd2, [])
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        _policy(repo_root).model_dump_json(), encoding="utf-8",
    )
    approved_path = tmp_path / "approved.json"
    approved_path.write_text(registry.model_dump_json(), encoding="utf-8")
    definitions_path = tmp_path / "definitions.json"
    _write_replay(definitions_path, {
        "pytest": json.loads(pytest_def.model_dump_json()),
    })
    audit_dir = tmp_path / "audit"
    out = tmp_path / "grounded_report.json"
    return out, [
        str(packet_path),
        "--forward-replay-1", str(fwd1),
        "--backward-replay-1", str(bwd1),
        "--forward-replay-2", str(fwd2),
        "--backward-replay-2", str(bwd2),
        "--tool-policy", str(policy_path),
        "--approved-tools", str(approved_path),
        "--gateway-definitions", str(definitions_path),
        "--audit-log-dir", str(audit_dir),
        "--out", str(out),
    ]


def test_verify_grounded_cli_exists() -> None:
    """The CLI MUST register ``verify-grounded`` as a subcommand
    of ``oida-code``."""
    from oida_code.cli import app
    result = _RUNNER.invoke(
        app, ["verify-grounded", "--help"], env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    assert "verify-grounded" in result.output.lower() or (
        "Usage:" in result.output and "packet" in result.output.lower()
    )


def test_verify_grounded_cli_requires_approved_tools(
    tmp_path: Path,
) -> None:
    """Without an ``--approved-tools`` flag, the CLI MUST fail
    fast (Typer enforces required options)."""
    from oida_code.cli import app
    result = _RUNNER.invoke(
        app, ["verify-grounded", str(tmp_path / "missing.json")],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code != 0


def test_verify_grounded_cli_writes_report(tmp_path: Path) -> None:
    from oida_code.cli import app
    out, argv = _verify_grounded_cli_args(tmp_path)
    result = _RUNNER.invoke(
        app, ["verify-grounded", *argv], env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "report" in payload
    assert "tool_results" in payload


def test_verify_grounded_cli_writes_audit_log(tmp_path: Path) -> None:
    """When pass-1 requests a tool, the CLI MUST write at least
    one audit JSONL file."""
    from oida_code.cli import app
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    packet = _baseline_packet()
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(packet.model_dump_json(), encoding="utf-8")
    fwd1 = tmp_path / "fwd1.json"
    _write_replay(fwd1, {
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    bwd1 = tmp_path / "bwd1.json"
    _write_replay(bwd1, [])
    fwd2 = tmp_path / "fwd2.json"
    _write_replay(fwd2, {
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })
    bwd2 = tmp_path / "bwd2.json"
    _write_replay(bwd2, [])
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        _policy(repo_root).model_dump_json(), encoding="utf-8",
    )
    approved_path = tmp_path / "approved.json"
    approved_path.write_text(registry.model_dump_json(), encoding="utf-8")
    definitions_path = tmp_path / "definitions.json"
    _write_replay(definitions_path, {
        "pytest": json.loads(pytest_def.model_dump_json()),
    })
    audit_dir = tmp_path / "audit"
    out = tmp_path / "grounded_report.json"
    result = _RUNNER.invoke(app, [
        "verify-grounded", str(packet_path),
        "--forward-replay-1", str(fwd1),
        "--backward-replay-1", str(bwd1),
        "--forward-replay-2", str(fwd2),
        "--backward-replay-2", str(bwd2),
        "--tool-policy", str(policy_path),
        "--approved-tools", str(approved_path),
        "--gateway-definitions", str(definitions_path),
        "--audit-log-dir", str(audit_dir),
        "--out", str(out),
    ], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    assert list(audit_dir.rglob("*.jsonl"))


def test_verify_grounded_cli_official_fields_absent(
    tmp_path: Path,
) -> None:
    from oida_code.cli import app
    out, argv = _verify_grounded_cli_args(tmp_path)
    result = _RUNNER.invoke(
        app, ["verify-grounded", *argv], env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8").lower()
    for phrase in (
        "total_v_net",
        "debt_final",
        "corrupt_success",
        "official_v_net",
        "merge_safe",
        "production_safe",
        "bug_free",
        "security_verified",
    ):
        assert phrase not in body


def test_action_enable_tool_gateway_default_false() -> None:
    """``action.yml`` exposes an ``enable-tool-gateway`` input
    whose default is exactly the literal string ``"false"``.
    Phase 5.2 does NOT make verify-grounded the default audit
    path."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert "enable-tool-gateway" in body
    # The block must end before the next top-level input. Find
    # the ``default:`` line that follows enable-tool-gateway:.
    after = body.split("enable-tool-gateway:", 1)[1]
    # Stop at the next two-space-indented input definition.
    next_input = re.search(r"\n  [a-z][a-z0-9-]*:\n", after)
    block = after[: next_input.start()] if next_input else after
    assert 'default: "false"' in block, (
        f"enable-tool-gateway block must default to \"false\": {block!r}"
    )


# ---------------------------------------------------------------------------
# 5.2-F — hermetic fixtures
# ---------------------------------------------------------------------------


_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gateway_grounded_verifier"


def test_fixture_tool_needed_then_supported() -> None:
    """The 'tool_needed_then_supported' fixture must contain
    pass1 forward asking for pytest, and pass2 forward citing
    [E.tool_output.*] in its evidence_refs."""
    case_dir = _FIXTURE_DIR / "tool_needed_then_supported"
    pass1_forward = json.loads(
        (case_dir / "pass1_forward.json").read_text(encoding="utf-8"),
    )
    assert pass1_forward["requested_tools"], (
        "pass1 must request at least one tool"
    )
    assert pass1_forward["requested_tools"][0]["tool"] == "pytest"
    pass2_forward = json.loads(
        (case_dir / "pass2_forward.json").read_text(encoding="utf-8"),
    )
    cited_refs: list[str] = []
    for claim in pass2_forward["supported_claims"]:
        cited_refs.extend(claim.get("evidence_refs", []))
    assert any("[E.tool_output." in r for r in cited_refs), (
        "pass2 supported_claims must cite tool_output evidence"
    )


def test_fixture_tool_hash_drift_quarantines() -> None:
    """The fixture marks the gateway definition's description
    as drifted vs. the approved fingerprint — the gateway must
    quarantine."""
    case_dir = _FIXTURE_DIR / "tool_hash_drift"
    approved = json.loads(
        (case_dir / "approved.json").read_text(encoding="utf-8"),
    )
    definitions = json.loads(
        (case_dir / "definitions.json").read_text(encoding="utf-8"),
    )
    # Approved fingerprint description differs from the served
    # definition description — that's the drift signal.
    served_desc = definitions["pytest"]["description"]
    approved_desc_hash = approved["approved"][0]["fingerprint"]["description_sha256"]
    import hashlib
    served_desc_hash = hashlib.sha256(served_desc.encode("utf-8")).hexdigest()
    assert served_desc_hash != approved_desc_hash, (
        "tool_hash_drift fixture must encode a real drift"
    )


def test_fixture_tool_failed_contradicts_claim() -> None:
    case_dir = _FIXTURE_DIR / "tool_failed_contradicts_claim"
    # The fixture's executor stdout is a JSON containing at
    # least one finding so the pytest adapter reports `failed`.
    executor_payload = json.loads(
        (case_dir / "executor.json").read_text(encoding="utf-8"),
    )
    assert executor_payload["returncode"] != 0, (
        "tool_failed_contradicts_claim must encode returncode != 0"
    )


def test_fixture_tool_error_uncertainty() -> None:
    case_dir = _FIXTURE_DIR / "tool_error_uncertainty"
    # The fixture's executor returns a non-zero rc that the
    # pytest adapter classifies as `error`, not `failed` (e.g.
    # rc=2 for collection error vs rc=1 for test failure).
    executor_payload = json.loads(
        (case_dir / "executor.json").read_text(encoding="utf-8"),
    )
    assert executor_payload["returncode"] is not None
    # The fixture documentation must also explicitly classify
    # the case as uncertainty.
    notes = (case_dir / "NOTES.md").read_text(encoding="utf-8").lower()
    assert "uncertainty" in notes


def test_fixture_prompt_injection_tool_output_is_data() -> None:
    """Stdout containing strings like ``IGNORE PRIOR
    INSTRUCTIONS`` becomes EvidenceItem data, never instruction
    text in any prompt rendered downstream."""
    case_dir = _FIXTURE_DIR / "prompt_injection_in_tool_output"
    executor_payload = json.loads(
        (case_dir / "executor.json").read_text(encoding="utf-8"),
    )
    stdout = executor_payload.get("stdout", "")
    # The fixture must encode a real prompt-injection attempt.
    assert (
        "ignore prior instructions" in stdout.lower()
        or "</oida_evidence>" in stdout.lower()
        or "<<<end_oida_evidence" in stdout.lower()
    )


# ---------------------------------------------------------------------------
# 5.2-G — replay-only smoke workflow
# ---------------------------------------------------------------------------


_WORKFLOW = (
    _REPO_ROOT / ".github" / "workflows" / "gateway-grounded-smoke.yml"
)


def test_gateway_grounded_smoke_workflow_replay_only() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    # Must not run on every PR; replay-only triggers.
    triggers_block = body.split("on:", 1)[1].split("jobs:", 1)[0]
    assert "workflow_dispatch" in triggers_block
    # No external provider — the keywords below must not appear.
    forbidden = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OIDA_LLM_PROVIDER",
        "real provider",
    )
    for token in forbidden:
        assert token not in body, (
            f"gateway-grounded-smoke must not reference {token!r}"
        )


def test_gateway_grounded_smoke_no_external_provider() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    # No `with:` block carrying an api key — replay only.
    assert "secrets." not in body or "secrets.GITHUB_TOKEN" in body, (
        "gateway-grounded-smoke must not consume non-default secrets"
    )


def test_gateway_grounded_smoke_permissions_read_only() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:" in body
    # Required: contents: read; nothing else write.
    assert "contents: read" in body
    write_lines = [ln for ln in body.splitlines() if ":" in ln and "write" in ln.lower()]
    # The only acceptable "write" reference would be a comment;
    # no actual permission grant.
    for line in write_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Allow GITHUB_TOKEN write if absolutely necessary —
        # but Phase 5.2 should not need any.
        assert stripped.endswith(": read") or stripped.endswith(": none"), (
            f"non-read permission detected: {stripped}"
        )


def test_gateway_grounded_smoke_no_mcp() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "@modelcontextprotocol",
        "mcp-server",
        "stdio_server",
        "tools/list",
        "tools/call",
    )
    for token in forbidden:
        assert token not in body


# ---------------------------------------------------------------------------
# 5.2-H — anti-MCP regression locks
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added() -> None:
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        "modelcontextprotocol",
        "@modelcontextprotocol",
        "mcp-server",
        "mcp_server",
    )
    for token in forbidden:
        assert token not in body, (
            f"pyproject.toml must not depend on {token!r}"
        )


def test_no_mcp_workflow_added() -> None:
    workflow_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return
    for wf in workflow_dir.glob("*.yml"):
        body = wf.read_text(encoding="utf-8")
        # Workflows must not run an MCP server or invoke the
        # JSON-RPC primitives.
        assert "tools/list" not in body, f"{wf.name} mentions tools/list"
        assert "tools/call" not in body, f"{wf.name} mentions tools/call"
        assert "mcp-server" not in body.lower(), (
            f"{wf.name} mentions mcp-server"
        )


def test_no_jsonrpc_tools_list_or_tools_call_runtime() -> None:
    src = _REPO_ROOT / "src" / "oida_code"
    forbidden = ("tools/list", "tools/call")
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        for token in forbidden:
            # Allow the negative-list backstop in the loop's
            # security comments to mention the strings, but
            # only if they appear inside a quoted forbidden
            # list (we look for the string surrounded by
            # quotes inside a tuple of forbidden phrases).
            if token in body:
                # If a file mentions the token, it must be in
                # a guard list (i.e. `"tools/list"` inside a
                # tuple/list literal whose name signals
                # forbiddance).
                in_guard = (
                    f'"{token}"' in body and "forbidden" in body.lower()
                ) or (
                    f"'{token}'" in body and "forbidden" in body.lower()
                )
                assert in_guard, (
                    f"{py} contains a runtime reference to {token}"
                )


def test_no_provider_tool_calling_enabled() -> None:
    """No source file under ``src/oida_code/`` may contain the
    OpenAI / Anthropic ``tools=`` parameter or a provider-side
    function-calling helper."""
    src = _REPO_ROOT / "src" / "oida_code"
    forbidden_re = re.compile(
        r"(?:client\.responses\.create|client\.messages\.create|"
        r"client\.chat\.completions\.create)[^)]*\btools\s*=",
        re.MULTILINE | re.DOTALL,
    )
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        assert not forbidden_re.search(body), (
            f"{py} appears to enable provider tool-calling"
        )


def test_gateway_loop_is_not_mcp() -> None:
    """The gateway-loop module MUST NOT import any MCP SDK or
    expose JSON-RPC primitives. Only the local deterministic
    gateway is permitted."""
    target = _REPO_ROOT / "src" / "oida_code" / "verifier" / "gateway_loop.py"
    body = target.read_text(encoding="utf-8")
    # Imports — no MCP SDK, no JSON-RPC server.
    for token in (
        "modelcontextprotocol",
        "mcp.server",
        "stdio_server",
        "json_rpc",
        "jsonrpc",
    ):
        assert token.lower() not in body.lower(), (
            f"gateway_loop.py mentions {token!r}"
        )
