"""Phase 5.8.1 (QA/A39) — pytest evidence invariant under operator-soak.

These tests pin the QA/A39 §4 rule:

> Every requested tool produces at least one citable EvidenceItem
> (with id ``[E.tool.<binary>.0]``) OR an explicit blocker. A
> tool requested by the verifier must NEVER silently emit
> ``status="error" + evidence_items=()``, which is what made
> case_001 (operator-soak run 24995045522) reject its only
> claim with "claim cites unknown evidence_refs ['[E.tool.pytest.0]']".

The invariant is enforced inside ``ToolAdapter.run`` (base class
in ``src/oida_code/verifier/tools/adapters.py``). It applies to
every adapter (ruff, mypy, pytest) — these tests use pytest as
the canonical case but the helper covers all three.

Diagnosis report: ``reports/operator_soak/case_001_pytest_evidence_diagnosis.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from oida_code.verifier.tools.adapters import (
    ExecutionContext,
    ExecutionOutcome,
    MypyAdapter,
    PytestAdapter,
    RuffAdapter,
)
from oida_code.verifier.tools.contracts import (
    VerifierToolRequest,
    VerifierToolResult,
)


@dataclass
class _StubExecutor:
    """Drop-in for ``Executor`` that returns one canned outcome.

    Mirrors the testing pattern in
    ``tests/test_phase4_2_tool_grounded_verifier.py`` but kept
    private to this Phase 5.8.1 test module so the invariant locks
    even if the legacy fake is later refactored.
    """

    outcome: ExecutionOutcome
    captured: list[ExecutionContext]

    def __init__(self, outcome: ExecutionOutcome) -> None:
        self.outcome = outcome
        self.captured = []

    def __call__(self, ctx: ExecutionContext) -> ExecutionOutcome:
        self.captured.append(ctx)
        return self.outcome


def _request(
    tool: str = "pytest",
    scope: tuple[str, ...] = ("tests/test_phase5_7_operator_soak.py",),
    max_runtime_s: int = 5,
) -> VerifierToolRequest:
    return VerifierToolRequest(
        tool=tool,  # type: ignore[arg-type]
        purpose=(
            "Phase 5.8.1 invariant test — pytest evidence must always "
            "produce a citable EvidenceItem or an explicit blocker."
        ),
        scope=scope,
        max_runtime_s=max_runtime_s,
        max_output_chars=8000,
    )


def _adapter_factories() -> list[Callable[[], Any]]:
    return [PytestAdapter, RuffAdapter, MypyAdapter]


# ---------------------------------------------------------------------------
# Primary invariant — pytest status=error case_001 reproduction
# ---------------------------------------------------------------------------


def test_pytest_error_still_emits_citable_tool_evidence_or_blocker(
    tmp_path: Path,
) -> None:
    """case_001 / run 24995045522 reproduction.

    pytest exits non-zero (rc=4 — file not found) at ~193 ms,
    emits no FAILED lines on stdout, no parseable findings.
    Pre-fix, ``ToolAdapter.run`` returned
    ``status="error", evidence_items=()`` and the verifier
    rejected any claim citing ``[E.tool.pytest.0]``.

    Post-fix, ``ToolAdapter.run`` synthesises a diagnostic
    EvidenceItem with that exact id so the claim resolves.
    """
    outcome = ExecutionOutcome(
        stdout="",
        stderr=(
            "ERROR: file or directory not found: "
            "tests/test_phase5_7_operator_soak.py"
        ),
        returncode=4,
        timed_out=False,
        runtime_ms=193,
    )
    adapter = PytestAdapter()
    result = adapter.run(
        _request(),
        repo_root=tmp_path,
        executor=_StubExecutor(outcome),
        max_output_chars=8000,
    )
    assert result.status == "error"
    assert result.evidence_items, (
        "QA/A39 invariant: pytest status=error must still emit at "
        "least one citable EvidenceItem (run 24995045522 reproduced "
        "case_001's silent failure here pre-fix)"
    )
    only = result.evidence_items[0]
    assert only.id == "[E.tool.pytest.0]"
    assert only.kind == "tool_finding"
    assert only.source == "pytest"
    assert "rc=4" in only.summary
    assert "no parseable findings" in only.summary


def test_pytest_tool_missing_emits_citable_tool_finding(
    tmp_path: Path,
) -> None:
    """A missing binary must still produce ``[E.tool.pytest.0]``.

    Without this, a verifier claim that grounded itself on pytest
    would silently fail to resolve when the runner image lacks
    pytest entirely.
    """
    missing = ExecutionOutcome(
        stdout="", stderr="", returncode=None, timed_out=False, runtime_ms=0,
    )
    adapter = PytestAdapter()
    result = adapter.run(
        _request(),
        repo_root=tmp_path,
        executor=_StubExecutor(missing),
        max_output_chars=8000,
    )
    assert result.status == "tool_missing"
    assert result.evidence_items
    only = result.evidence_items[0]
    assert only.id == "[E.tool.pytest.0]"
    assert only.kind == "tool_finding"
    assert "not on PATH" in only.summary


def test_pytest_timeout_emits_citable_tool_finding(tmp_path: Path) -> None:
    """A timeout must still produce ``[E.tool.pytest.0]`` so the
    operator can see *why* no test result was captured.
    """
    timed_out = ExecutionOutcome(
        stdout="", stderr="", returncode=None, timed_out=True, runtime_ms=5000,
    )
    adapter = PytestAdapter()
    result = adapter.run(
        _request(max_runtime_s=2),
        repo_root=tmp_path,
        executor=_StubExecutor(timed_out),
        max_output_chars=8000,
    )
    assert result.status == "timeout"
    assert result.evidence_items
    only = result.evidence_items[0]
    assert only.id == "[E.tool.pytest.0]"
    assert only.kind == "tool_finding"
    assert "exceeded the per-tool runtime budget" in only.summary


def test_pytest_parse_exception_emits_citable_tool_finding(
    tmp_path: Path,
) -> None:
    """If ``parse_outcome`` raises (unexpected stdout shape, etc.),
    the adapter must still emit a citable evidence item that names
    the exception class — never a silent ``evidence_items=()``.
    """

    class _ExplodingPytestAdapter(PytestAdapter):
        def parse_outcome(
            self,
            request: VerifierToolRequest,
            stdout: str,
            stderr: str,
            returncode: int,
        ) -> tuple[list[Any], list[Any], list[str]]:
            raise RuntimeError("synthetic parse_outcome explosion")

    outcome = ExecutionOutcome(
        stdout="something garbled",
        stderr="",
        returncode=1,
        timed_out=False,
        runtime_ms=42,
    )
    adapter = _ExplodingPytestAdapter()
    result = adapter.run(
        _request(),
        repo_root=tmp_path,
        executor=_StubExecutor(outcome),
        max_output_chars=8000,
    )
    assert result.status == "error"
    assert result.evidence_items
    only = result.evidence_items[0]
    assert only.id == "[E.tool.pytest.0]"
    assert only.kind == "tool_finding"
    assert "RuntimeError" in only.summary


def test_pytest_clean_pass_still_emits_citable_evidence(tmp_path: Path) -> None:
    """Regression guard — the existing clean-pass branch (rc=0,
    pytest stdout present, no findings) must keep emitting
    ``[E.tool.pytest.0]`` exactly as before. The invariant patch
    must not regress the success path.
    """
    outcome = ExecutionOutcome(
        stdout="3 passed in 0.05s\n",
        stderr="",
        returncode=0,
        timed_out=False,
        runtime_ms=120,
    )
    adapter = PytestAdapter()
    result = adapter.run(
        _request(),
        repo_root=tmp_path,
        executor=_StubExecutor(outcome),
        max_output_chars=8000,
    )
    assert result.status == "ok"
    assert result.evidence_items
    only = result.evidence_items[0]
    assert only.id == "[E.tool.pytest.0]"
    # Clean-pass branch uses kind="test_result" (it IS a real test
    # outcome); the invariant patch ONLY adds diagnostic items on
    # the error/missing/timeout paths — it must NOT shadow the
    # clean-pass branch's stronger semantic.
    assert only.kind == "test_result"
    assert "passed scoped to" in only.summary


# ---------------------------------------------------------------------------
# Cross-adapter invariant — same rule applies to ruff and mypy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "adapter_factory",
    _adapter_factories(),
    ids=["pytest", "ruff", "mypy"],
)
def test_every_adapter_error_emits_citable_diagnostic(
    adapter_factory: Callable[[], Any],
    tmp_path: Path,
) -> None:
    """The invariant lives in the shared ``ToolAdapter.run`` base
    class, so it must apply to every concrete adapter — not just
    the pytest path that case_001 tripped on.
    """
    adapter = adapter_factory()
    request = _request(tool=adapter.name)
    outcome = ExecutionOutcome(
        stdout="",
        stderr="some unparseable garbage",
        returncode=2,
        timed_out=False,
        runtime_ms=50,
    )
    result: VerifierToolResult = adapter.run(
        request,
        repo_root=tmp_path,
        executor=_StubExecutor(outcome),
        max_output_chars=8000,
    )
    assert result.status == "error", (
        f"{adapter.name}: rc=2 with empty stdout should map to error, "
        f"got {result.status!r}"
    )
    assert result.evidence_items, (
        f"{adapter.name}: error path must emit a citable diagnostic"
    )
    only = result.evidence_items[0]
    assert only.id == f"[E.tool.{adapter.name}.0]"
    assert only.kind == "tool_finding"


@pytest.mark.parametrize(
    "adapter_factory",
    _adapter_factories(),
    ids=["pytest", "ruff", "mypy"],
)
def test_every_adapter_tool_missing_emits_citable_diagnostic(
    adapter_factory: Callable[[], Any],
    tmp_path: Path,
) -> None:
    adapter = adapter_factory()
    missing = ExecutionOutcome(
        stdout="", stderr="", returncode=None, timed_out=False, runtime_ms=0,
    )
    result = adapter.run(
        _request(tool=adapter.name),
        repo_root=tmp_path,
        executor=_StubExecutor(missing),
        max_output_chars=8000,
    )
    assert result.status == "tool_missing"
    assert result.evidence_items
    assert result.evidence_items[0].id == f"[E.tool.{adapter.name}.0]"
    assert result.evidence_items[0].kind == "tool_finding"


# ---------------------------------------------------------------------------
# Phase 5.8.1 forbidden-token guard
# ---------------------------------------------------------------------------


def test_diagnostic_summaries_never_emit_forbidden_tokens(
    tmp_path: Path,
) -> None:
    """The diagnostic EvidenceItem summary must not contain any
    product-verdict token (ADR-22 hard wall). The patch built the
    summaries from binary name + scope + stderr/stdout excerpts;
    this test reproduces a stderr that *contains* a forbidden token
    and verifies the truncated excerpt never makes it into the
    EvidenceItem summary verbatim. The invariant is "the diagnostic
    is operator-readable but never claims a product verdict on its
    own"."""
    forbidden = (
        "merge_safe", "merge-safe", "production_safe", "production-safe",
        "bug_free", "bug-free", "verified", "security_verified",
        "total_v_net", "debt_final", "corrupt_success",
    )
    # Stderr happens to contain a forbidden token (e.g. an upstream
    # error message). The diagnostic excerpt may copy 200 chars of
    # stderr; we only require the *summary's verdict-claim shape* to
    # never use those tokens. Concretely: the framing words around
    # the excerpt ("exited rc=…", "no parseable findings") must not
    # be product-verdict claims.
    poisoned_stderr = "the merge_safe shim crashed on startup"
    outcome = ExecutionOutcome(
        stdout="",
        stderr=poisoned_stderr,
        returncode=2,
        timed_out=False,
        runtime_ms=10,
    )
    adapter = PytestAdapter()
    result = adapter.run(
        _request(),
        repo_root=tmp_path,
        executor=_StubExecutor(outcome),
        max_output_chars=8000,
    )
    assert result.status == "error"
    assert result.evidence_items
    summary = result.evidence_items[0].summary
    # The framing of the diagnostic must NOT itself claim a product
    # verdict. The stderr quote may surface a forbidden token from
    # upstream, but the summary's structural framing ("rc=…", "no
    # parseable findings") must be neutral.
    framing = summary.replace(poisoned_stderr, "")
    for token in forbidden:
        assert token not in framing, (
            f"diagnostic framing leaked forbidden token {token!r}: {framing}"
        )


# ---------------------------------------------------------------------------
# Phase 5.8.1-B verifier-level safety regression
# ---------------------------------------------------------------------------
#
# The Phase 5.8.1 invariant patch (every error path must emit a citable
# diagnostic ``[E.tool.<binary>.0]``) accidentally promoted case_001's
# false claim from ``rejected`` to ``accepted`` when the diagnostic
# satisfied aggregator rule 3 + ``_enforce_pass2_tool_citation``'s
# intersection check + ``_enforce_requested_tool_evidence``'s
# new_evidence-non-empty guard.
#
# Phase 5.8.1-B fixes this by splitting "diagnostic evidence" (citable
# but non-promoting) from "actionable evidence" (citable AND promoting).
# These tests reproduce case_001's exact bundle shape at the verifier
# level and assert the safe outcome: the claim ends up in
# ``unsupported_claims`` (NOT ``accepted_claims``), and the report
# status is ``diagnostic_only`` (NOT ``verification_candidate``).
#
# These are the regression guards for the regression we found.

import json  # noqa: E402

from oida_code.estimators.llm_prompt import (  # noqa: E402
    EvidenceItem as _EvidenceItem,
)
from oida_code.estimators.llm_prompt import (  # noqa: E402
    LLMEvidencePacket,
)
from oida_code.verifier.gateway_loop import (  # noqa: E402
    _run_tool_phase,
    run_gateway_grounded_verifier,
)
from oida_code.verifier.replay import (  # noqa: E402
    VerifierProvider as _VerifierProvider,
)
from oida_code.verifier.tool_gateway.contracts import (  # noqa: E402
    GatewayToolDefinition,
    ToolAdmissionDecision,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tool_gateway.fingerprints import (  # noqa: E402
    fingerprint_tool_definition,
)
from oida_code.verifier.tool_gateway.gateway import (  # noqa: E402
    LocalDeterministicToolGateway,
)
from oida_code.verifier.tools.contracts import ToolPolicy  # noqa: E402


class _ScriptedProvider(_VerifierProvider):
    """Replay-style provider returning a queue of canned JSON replies."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        if not self._replies:
            raise AssertionError(
                "scripted provider exhausted (test queued too few replies)"
            )
        return self._replies.pop(0)


def _pytest_definition() -> GatewayToolDefinition:
    return GatewayToolDefinition(
        tool_id="oida-code/pytest",
        tool_name="pytest",
        adapter_version="0.4.0",
        description="Run pytest (read-only).",
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


def _registry_with(*defs: GatewayToolDefinition) -> ToolAdmissionRegistry:
    return ToolAdmissionRegistry(approved=tuple(
        ToolAdmissionDecision(
            tool_id=d.tool_id,
            status="approved_read_only",
            reason="phase 5.8.1-B safety test",
            fingerprint=fingerprint_tool_definition(d),
        )
        for d in defs
    ))


def _policy(repo_root: Path) -> ToolPolicy:
    return ToolPolicy(
        allowed_tools=("pytest",),
        repo_root=repo_root,
        allow_network=False,
        allow_write=False,
    )


def _case001_packet() -> LLMEvidencePacket:
    """Reproduces case_001 / run 24995045522's actual packet exactly."""
    return LLMEvidencePacket(
        event_id="evt-case-001-docstring",
        allowed_fields=("capability", "benefit", "observability"),
        intent_summary=(
            "Phase 5.8 case_001: align rule-5 docstring in "
            "src/oida_code/operator_soak/aggregate.py"
        ),
        evidence_items=(
            _EvidenceItem(
                id="[E.event.1]",
                kind="event",
                summary="docstring-only single-commit change.",
                source="git",
                confidence=0.95,
            ),
            _EvidenceItem(
                id="[E.event.2]",
                kind="event",
                summary="operator intent recorded in case README.",
                source="ticket",
                confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )


def _case001_pass1_forward() -> str:
    return json.dumps({
        "event_id": "evt-case-001-docstring",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": (
                "Confirm tests/test_phase5_7_operator_soak.py still passes "
                "with the docstring change."
            ),
            "expected_evidence_kind": "test_result",
            "scope": ["tests/test_phase5_7_operator_soak.py"],
        }],
    })


def _case001_pass2_forward() -> str:
    """The pass-2 forward replay verbatim from case_001's bundle."""
    return json.dumps({
        "event_id": "evt-case-001-docstring",
        "supported_claims": [{
            "claim_id": "C.docstring.no_behavior_delta",
            "event_id": "evt-case-001-docstring",
            "claim_type": "capability_sufficient",
            "statement": (
                "The case_001 docstring update preserves aggregator behavior; "
                "pytest evidence confirms tests still pass."
            ),
            "confidence": 0.6,
            "evidence_refs": ["[E.event.1]", "[E.event.2]", "[E.tool.pytest.0]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })


def _case001_pass2_backward() -> str:
    return json.dumps([{
        "event_id": "evt-case-001-docstring",
        "claim_id": "C.docstring.no_behavior_delta",
        "requirement": {
            "claim_id": "C.docstring.no_behavior_delta",
            "required_evidence_kinds": ["event", "test_result"],
            "satisfied_evidence_refs": [
                "[E.event.1]", "[E.event.2]", "[E.tool.pytest.0]",
            ],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }])


def _pytest_error_executor(_ctx: ExecutionContext) -> ExecutionOutcome:
    """Reproduces case_001's actual pytest run: rc=4, no output."""
    return ExecutionOutcome(
        stdout="",
        stderr="ERROR: file or directory not found: tests/...",
        returncode=4,
        timed_out=False,
        runtime_ms=193,
    )


def test_case001_pytest_error_does_not_promote_claim_post_patch(
    tmp_path: Path,
) -> None:
    """REGRESSION GUARD for the bug found by post-patch verify-claims:

    Pre-patch: pytest emitted ``evidence_items=()`` on rc!=0; the
    aggregator rejected the claim citing ``[E.tool.pytest.0]`` with
    "claim cites unknown evidence_refs" → status=diagnostic_only,
    accepted=0, rejected=1. Safe.

    With Phase 5.8.1 patch (B) alone: pytest emits
    ``[E.tool.pytest.0]`` diagnostic → ref resolves → aggregator
    rule 3 passes → ``_enforce_pass2_tool_citation`` intersection
    finds the ref → ``_enforce_requested_tool_evidence`` is no-op
    because ``new_evidence`` non-empty → status=verification_candidate,
    accepted=1. UNSAFE — false claim promoted.

    With Phase 5.8.1-B (this fix): the diagnostic is in
    ``new_evidence`` (so rule 3 still passes) but NOT in
    ``actionable_evidence``. Both enforcers consume actionable;
    ``_enforce_requested_tool_evidence`` fires and demotes the
    accepted claim to unsupported. Safe again — but this time the
    claim is properly resolved at rule 3 instead of silently
    rejected.
    """
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(
        executor=_pytest_error_executor,
    )
    run = run_gateway_grounded_verifier(
        _case001_packet(),
        forward_pass1=_ScriptedProvider([_case001_pass1_forward()]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([_case001_pass2_forward()]),
        backward_pass2=_ScriptedProvider([_case001_pass2_backward()]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    # The claim must NOT be accepted post-patch — its only "tool"
    # corroboration is a diagnostic that says pytest crashed.
    accepted_ids = {c.claim_id for c in run.report.accepted_claims}
    unsupported_ids = {c.claim_id for c in run.report.unsupported_claims}
    assert "C.docstring.no_behavior_delta" not in accepted_ids, (
        "Phase 5.8.1-B SAFETY REGRESSION: case_001's claim was promoted to "
        "accepted by the diagnostic [E.tool.pytest.0]. The diagnostic must "
        "satisfy rule 3 (ref exists) but MUST NOT count as actionable tool "
        "evidence."
    )
    assert "C.docstring.no_behavior_delta" in unsupported_ids, (
        "Phase 5.8.1-B: a claim citing [E.tool.pytest.0] when pytest errored "
        "must be demoted to unsupported (not silently rejected, not "
        "accepted). Got accepted="
        f"{accepted_ids}, unsupported={unsupported_ids}, "
        f"rejected={[c.claim_id for c in run.report.rejected_claims]}"
    )
    assert run.report.status != "verification_candidate", (
        f"Phase 5.8.1-B: status must be downgraded from "
        f"verification_candidate when the requested tool only produced "
        f"diagnostic (non-actionable) evidence. Got {run.report.status!r}."
    )
    # Additionally: the loop must have surfaced a Phase 5.8.1-B
    # blocker explaining why the claim was demoted.
    assert any(
        "Phase 5.8.1-B" in b for b in run.report.blockers
    ), (
        f"Phase 5.8.1-B: report must surface a blocker explaining the "
        f"diagnostic-only demotion. Got blockers={list(run.report.blockers)!r}"
    )


def test_case001_pytest_clean_pass_still_promotes_claim(
    tmp_path: Path,
) -> None:
    """Happy-path regression guard for the diagnostic/actionable split.

    When pytest actually runs cleanly (rc=0, ``5 passed``), the
    adapter emits a ``test_result``-kind item. That item IS
    actionable, so the claim citing it must still be accepted.
    The split must not break the success path.
    """
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    def _clean_executor(_ctx: ExecutionContext) -> ExecutionOutcome:
        return ExecutionOutcome(
            stdout="===== 5 passed in 0.4s =====",
            stderr="",
            returncode=0,
            timed_out=False,
            runtime_ms=400,
        )

    gateway = LocalDeterministicToolGateway(executor=_clean_executor)
    run = run_gateway_grounded_verifier(
        _case001_packet(),
        forward_pass1=_ScriptedProvider([_case001_pass1_forward()]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([_case001_pass2_forward()]),
        backward_pass2=_ScriptedProvider([_case001_pass2_backward()]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
    )
    accepted_ids = {c.claim_id for c in run.report.accepted_claims}
    assert "C.docstring.no_behavior_delta" in accepted_ids, (
        "Phase 5.8.1-B regression: clean pytest pass must still allow the "
        "pass-2 claim to be accepted. The split must not break the success "
        "path. Got accepted="
        f"{accepted_ids}, "
        f"unsupported={[c.claim_id for c in run.report.unsupported_claims]}, "
        f"rejected={[c.claim_id for c in run.report.rejected_claims]}, "
        f"status={run.report.status!r}"
    )


def test_run_tool_phase_splits_diagnostic_from_actionable(
    tmp_path: Path,
) -> None:
    """Direct unit test for the split inside ``_run_tool_phase``.

    pytest errors (rc=4) → adapter emits one diagnostic item. That
    item lands in ``new_evidence`` but NOT in ``actionable_evidence``.
    """
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(executor=_pytest_error_executor)

    from oida_code.verifier.contracts import VerifierToolCallSpec

    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="reproduce case_001 error",
        expected_evidence_kind="test_result",
        scope=("tests/",),
    )
    out = _run_tool_phase(
        [spec],
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
        event_id="evt-case-001",
        max_tool_calls=5,
    )
    assert len(out.tool_results) == 1
    assert out.tool_results[0].status == "error"
    assert out.new_evidence, (
        "diagnostic evidence (citable) must exist in new_evidence so "
        "aggregator rule 3 stops rejecting on missing-ref"
    )
    assert out.new_evidence[0].id == "[E.tool.pytest.0]"
    assert out.actionable_evidence == (), (
        "Phase 5.8.1-B: diagnostic items from status=error must NOT enter "
        "actionable_evidence. Got "
        f"{[e.id for e in out.actionable_evidence]!r}"
    )


def test_run_tool_phase_clean_pass_evidence_is_actionable(
    tmp_path: Path,
) -> None:
    """Regression guard: a clean pytest pass produces a
    ``test_result`` item that IS actionable."""
    pytest_def = _pytest_definition()
    registry = _registry_with(pytest_def)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"

    def _clean_executor(_ctx: ExecutionContext) -> ExecutionOutcome:
        return ExecutionOutcome(
            stdout="===== 5 passed in 0.4s =====",
            stderr="",
            returncode=0,
            timed_out=False,
            runtime_ms=400,
        )

    gateway = LocalDeterministicToolGateway(executor=_clean_executor)

    from oida_code.verifier.contracts import VerifierToolCallSpec
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="happy path",
        expected_evidence_kind="test_result",
        scope=("tests/",),
    )
    out = _run_tool_phase(
        [spec],
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=registry,
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=audit_dir,
        event_id="evt-happy-path",
        max_tool_calls=5,
    )
    assert out.tool_results[0].status == "ok"
    assert out.new_evidence
    assert out.actionable_evidence, (
        "happy-path tool result must produce actionable evidence so "
        "claims citing it can be accepted"
    )
    assert out.new_evidence == out.actionable_evidence, (
        "for status=ok, every new_evidence item is actionable"
    )
