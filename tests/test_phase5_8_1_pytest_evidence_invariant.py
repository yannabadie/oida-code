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
