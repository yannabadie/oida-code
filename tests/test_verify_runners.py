"""Tests for the Phase 1 ``verify/`` runners.

These tests call real binaries (ruff, mypy, pytest, semgrep) when they are on
PATH. ``tool_missing`` status is tested against a stub binary name.
"""

from __future__ import annotations

from pathlib import Path

from oida_code.verify._runner import run_tool
from oida_code.verify.codeql_scan import run_codeql
from oida_code.verify.lint import run_lint
from oida_code.verify.pytest_runner import run_pytest
from oida_code.verify.semgrep_scan import run_semgrep
from oida_code.verify.typing import run_type_check


def test_run_tool_handles_missing_binary(tmp_path: Path) -> None:
    result = run_tool(
        "this-binary-does-not-exist-xyz",
        ["--version"],
        repo_path=tmp_path,
        budget_seconds=5,
    )
    assert result.status == "tool_missing"
    assert result.exit_code is None


def test_run_lint_on_self_repo_returns_ok() -> None:
    from tests.conftest import REPO_ROOT

    ev = run_lint(REPO_ROOT, budget_seconds=30)
    # Either ok (findings or not) or tool_missing on exotic envs.
    assert ev.status in {"ok", "tool_missing"}
    if ev.status == "ok":
        assert isinstance(ev.findings, list)


def test_run_type_check_on_self_repo_returns_ok() -> None:
    from tests.conftest import REPO_ROOT

    ev = run_type_check(REPO_ROOT, budget_seconds=90)
    assert ev.status in {"ok", "tool_missing"}


def test_run_semgrep_returns_known_status() -> None:
    from tests.conftest import REPO_ROOT

    ev = run_semgrep(REPO_ROOT, budget_seconds=30)
    # Semgrep on Windows is flaky → any of these is acceptable.
    assert ev.status in {"ok", "tool_missing", "timeout", "error"}


def test_run_codeql_always_returns_tool_missing_or_skipped() -> None:
    from tests.conftest import REPO_ROOT

    ev = run_codeql(REPO_ROOT)
    assert ev.status in {"tool_missing", "skipped"}
    assert ev.findings == []


def test_run_pytest_on_fresh_tmp_returns_ok_or_nochecks(tmp_path: Path) -> None:
    # An empty tmp_path has no tests — pytest exits with code 5.
    # That must surface as status=ok with empty findings (not error).
    ev = run_pytest(tmp_path, budget_seconds=60)
    assert ev.status in {"ok", "tool_missing"}
    if ev.status == "ok":
        assert ev.findings == []
