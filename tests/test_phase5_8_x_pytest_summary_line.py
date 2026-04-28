"""Phase 5.8.x — pytest_summary_line adapter follow-up.

cgpro flagged on case_003 (markupsafe, run 25045245609) that the
gateway adapter's clean-pass synthesis emits "pytest passed scoped to
... with no failures" but does NOT include the explicit pytest
terminal summary line ("29 passed, 0 skipped" vs "24 passed, 5
skipped" was the dual-backend trap signal). cgpro labelled
case_003 useful_true_positive UX 2/1/2/2 — evidence_traceability
scored 1 (not 2) for that gap.

This phase adds a `pytest_summary_line: str | None = None` field to
:class:`VerifierToolResult` (frozen Pydantic, default None preserves
backward compat for non-pytest tools), and wires
:class:`PytestAdapter` to extract the standard pytest terminal line
from stdout. The clean-pass evidence summary is also enriched so the
operator-facing surface (which only reads ``evidence_items[*].summary``)
exposes the counts.

ADR-47 governs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from oida_code.verifier.tools import (
    ToolPolicy,
    VerifierToolRequest,
    VerifierToolResult,
)
from oida_code.verifier.tools.adapters import (
    ExecutionContext,
    ExecutionOutcome,
    PytestAdapter,
    RuffAdapter,
)


def _ok(stdout: str = "", stderr: str = "", returncode: int = 0,
        runtime_ms: int = 12) -> ExecutionOutcome:
    return ExecutionOutcome(
        stdout=stdout, stderr=stderr, returncode=returncode,
        timed_out=False, runtime_ms=runtime_ms,
    )


class _FakeExecutor:
    def __init__(self, outcomes: Mapping[str, ExecutionOutcome] | None = None) -> None:
        self.outcomes: dict[str, ExecutionOutcome] = dict(outcomes or {})
        self.calls: list[ExecutionContext] = []

    def __call__(self, ctx: ExecutionContext) -> ExecutionOutcome:
        self.calls.append(ctx)
        return self.outcomes.get(
            ctx.binary,
            ExecutionOutcome(
                stdout="", stderr="", returncode=None, timed_out=False,
                runtime_ms=0,
            ),
        )


def _request(tool: str = "pytest", scope: tuple[str, ...] = ("tests/test_a.py",),
             max_runtime_s: int = 10) -> VerifierToolRequest:
    return VerifierToolRequest(
        tool=tool,  # type: ignore[arg-type]
        purpose=f"check {tool}",
        scope=scope,
        max_runtime_s=max_runtime_s,
        max_output_chars=8000,
    )


def _policy(tmp_path: Path) -> ToolPolicy:
    return ToolPolicy(
        allowed_tools=("pytest", "ruff"),
        repo_root=tmp_path,
        allowed_paths=("tests", "src"),
    )


# ---------------------------------------------------------------------------
# Schema invariant — new field defaults to None, preserves frozen contract
# ---------------------------------------------------------------------------


def test_verifier_tool_result_pytest_summary_line_defaults_to_none() -> None:
    """The new field is opt-in and Optional; non-pytest results never set it."""
    result = VerifierToolResult(tool="ruff", status="ok")
    assert result.pytest_summary_line is None


def test_verifier_tool_result_pytest_summary_line_round_trip() -> None:
    """The field accepts a string and is preserved through model_dump."""
    result = VerifierToolResult(
        tool="pytest",
        status="ok",
        pytest_summary_line="29 passed in 0.21s",
    )
    assert result.pytest_summary_line == "29 passed in 0.21s"
    dumped = result.model_dump()
    assert dumped["pytest_summary_line"] == "29 passed in 0.21s"


# ---------------------------------------------------------------------------
# Parser unit tests — variant coverage
# ---------------------------------------------------------------------------


def test_pytest_extract_summary_passed_only() -> None:
    """Most common case: '29 passed in 0.21s'."""
    adapter = PytestAdapter()
    line = adapter.extract_summary_line("..\n29 passed in 0.21s\n")
    assert line == "29 passed in 0.21s"


def test_pytest_extract_summary_passed_and_skipped() -> None:
    """The dual-backend trap signal — '5 skipped' appearing means
    parametrized cases silently skipped."""
    adapter = PytestAdapter()
    line = adapter.extract_summary_line("..\n24 passed, 5 skipped in 1.23s\n")
    assert line == "24 passed, 5 skipped in 1.23s"


def test_pytest_extract_summary_failed_and_passed() -> None:
    """Failure case still parseable so red runs surface counts."""
    adapter = PytestAdapter()
    line = adapter.extract_summary_line(
        "FAILED tests/test_a.py::test_x - assert 0\n"
        "1 failed, 2 passed in 0.30s\n"
    )
    assert line == "1 failed, 2 passed in 0.30s"


def test_pytest_extract_summary_decorated_equals_line() -> None:
    """Pytest commonly decorates the summary with '=' bars."""
    adapter = PytestAdapter()
    line = adapter.extract_summary_line(
        "..\n=================== 29 passed in 0.21s ===================\n"
    )
    assert line == "29 passed in 0.21s"


def test_pytest_extract_summary_error_only() -> None:
    """Collection errors emit '1 error' summaries."""
    adapter = PytestAdapter()
    line = adapter.extract_summary_line("===== 1 error in 0.10s =====\n")
    assert line == "1 error in 0.10s"


def test_pytest_extract_summary_no_summary_returns_none() -> None:
    """Pre-summary or fully empty stdout → None (don't fabricate counts)."""
    adapter = PytestAdapter()
    assert adapter.extract_summary_line("") is None
    assert adapter.extract_summary_line(
        "collected 0 items / 1 deselected\n"
    ) is None


def test_pytest_extract_summary_picks_last_summary_line() -> None:
    """When multiple candidate lines exist, prefer the LAST (true terminal)."""
    adapter = PytestAdapter()
    out = (
        "===== test session starts =====\n"
        "(stale 1 passed in 99.0s line that should be ignored)\n"
        "..\n"
        "29 passed in 0.21s\n"
    )
    assert adapter.extract_summary_line(out) == "29 passed in 0.21s"


def test_ruff_adapter_does_not_implement_summary_line() -> None:
    """Other adapters keep returning None — the hook is pytest-shaped only."""
    adapter = RuffAdapter()
    assert adapter.extract_summary_line("..\n5 passed in 1.0s\n") is None


# ---------------------------------------------------------------------------
# Adapter integration — VerifierToolResult.pytest_summary_line populated
# ---------------------------------------------------------------------------


def test_pytest_clean_pass_populates_pytest_summary_line(tmp_path: Path) -> None:
    """End-to-end: PytestAdapter.run() exposes the line on the result."""
    adapter = PytestAdapter()
    fake = _FakeExecutor({
        "pytest": _ok(stdout="..\n29 passed in 0.21s\n"),
    })
    result = adapter.run(
        _request(tool="pytest"),
        repo_root=tmp_path,
        executor=fake,
        max_output_chars=8000,
    )
    assert result.status == "ok"
    assert result.pytest_summary_line == "29 passed in 0.21s"


def test_pytest_clean_pass_evidence_summary_now_includes_counts(tmp_path: Path) -> None:
    """The user-facing surface (evidence_items[*].summary) carries the line.

    Without this, the schema field exists but cgpro/operators reading
    the audit packet's evidence chain still don't see passed/skipped
    counts — the case_003 evidence_traceability=1 trap.
    """
    adapter = PytestAdapter()
    fake = _FakeExecutor({
        "pytest": _ok(stdout="..\n24 passed, 5 skipped in 1.23s\n"),
    })
    result = adapter.run(
        _request(tool="pytest"),
        repo_root=tmp_path,
        executor=fake,
        max_output_chars=8000,
    )
    assert result.status == "ok"
    assert len(result.evidence_items) == 1
    summary = result.evidence_items[0].summary
    assert "24 passed, 5 skipped" in summary, summary


def test_pytest_failed_run_populates_summary_line(tmp_path: Path) -> None:
    """Even on red runs the parser surfaces the count."""
    adapter = PytestAdapter()
    out = (
        "FAILED tests/test_a.py::test_x - assert 0\n"
        "1 failed, 2 passed in 0.30s\n"
    )
    fake = _FakeExecutor({
        "pytest": _ok(stdout=out, returncode=1),
    })
    result = adapter.run(
        _request(tool="pytest"),
        repo_root=tmp_path,
        executor=fake,
        max_output_chars=8000,
    )
    assert result.status == "failed"
    assert result.pytest_summary_line == "1 failed, 2 passed in 0.30s"


def test_pytest_tool_missing_leaves_summary_line_none(tmp_path: Path) -> None:
    """When pytest binary is missing, the field stays None — uncertainty,
    not a fabricated summary."""
    adapter = PytestAdapter()
    fake = _FakeExecutor()  # no canned outcome ⇒ tool_missing
    result = adapter.run(
        _request(tool="pytest"),
        repo_root=tmp_path,
        executor=fake,
        max_output_chars=8000,
    )
    assert result.status == "tool_missing"
    assert result.pytest_summary_line is None


def test_ruff_run_keeps_pytest_summary_line_none(tmp_path: Path) -> None:
    """Non-pytest adapters never populate the field even if their stdout
    contains a string that looks summary-shaped."""
    adapter = RuffAdapter()
    fake = _FakeExecutor({
        "ruff": _ok(stdout="[]"),  # ruff outputs JSON when --output-format=json
    })
    result = adapter.run(
        _request(tool="ruff"),
        repo_root=tmp_path,
        executor=fake,
        max_output_chars=8000,
    )
    assert result.tool == "ruff"
    assert result.pytest_summary_line is None
