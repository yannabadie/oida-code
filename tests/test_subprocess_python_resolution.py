"""Regression test for the Phase 1 carry-over bug (ADR-14 follow-up).

When ``shutil.which("pytest")`` resolves to a pytest bound to a different
Python than the one running ``oida-code``, target-repo package imports fail
in the subprocess with ``ModuleNotFoundError``. The fix is to prefer
``[sys.executable, "-m", "pytest", ...]`` whenever the ``pytest`` module is
importable in the current interpreter.

Mirror cases for ``mypy``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from oida_code.verify._runner import run_tool
from oida_code.verify.pytest_runner import run_pytest
from oida_code.verify.typing import run_type_check


def test_run_tool_uses_sys_executable_when_python_module_given(
    monkeypatch, tmp_path: Path
) -> None:
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_tool(
        "pytest",
        ["--version"],
        repo_path=tmp_path,
        budget_seconds=5,
        python_module="pytest",
    )
    assert captured, "subprocess.run was not invoked"
    cmd = captured[0]
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "pytest"]


def test_run_tool_falls_back_to_shutil_which_for_non_python_tools(
    monkeypatch, tmp_path: Path
) -> None:
    """When ``python_module`` is None, behavior is unchanged."""
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_tool("ruff", ["check"], repo_path=tmp_path, budget_seconds=5)
    assert captured, "subprocess.run was not invoked"
    cmd = captured[0]
    assert cmd[0] != sys.executable  # resolved via shutil.which


def test_run_pytest_uses_current_interpreter(tmp_path: Path) -> None:
    """Running pytest on a target that depends on ``oida_code`` must succeed.

    Before the fix, this was the exact failure mode: ``shutil.which("pytest")``
    could resolve to a pytest from a different Python where ``oida_code`` is
    not installed, making collection fail with ``ModuleNotFoundError``.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_oida_import.py").write_text(
        "import oida_code\n"
        "def test_oida_importable():\n"
        "    assert hasattr(oida_code, '__version__')\n",
        encoding="utf-8",
    )
    ev = run_pytest(tmp_path, budget_seconds=60)
    assert ev.status == "ok", f"unexpected status={ev.status}; stderr={ev.stderr_excerpt}"
    assert ev.counts.get("failure", 0) == 0
    assert ev.counts.get("error", 0) == 0


def test_run_type_check_uses_current_interpreter(tmp_path: Path) -> None:
    """Same guarantee for mypy."""
    (tmp_path / "x.py").write_text(
        "import oida_code\n"
        "_: str = oida_code.__version__\n",
        encoding="utf-8",
    )
    ev = run_type_check(tmp_path, budget_seconds=60)
    # Either ok (and zero errors since oida_code.__version__ is str) or
    # tool_missing (mypy not importable in current Python — shouldn't happen in our dev env).
    assert ev.status in {"ok", "tool_missing"}
    if ev.status == "ok":
        # The subprocess Python had to resolve oida_code to type-check. Any
        # "not found" / "module has no attribute" would indicate a wrong
        # interpreter. "import-untyped" is benign (missing py.typed marker).
        fatal = [
            f
            for f in ev.findings
            if any(needle in f.message for needle in ("has no attribute", "Cannot find"))
            and "oida_code" in f.message
        ]
        assert not fatal, f"mypy ran with the wrong Python: {fatal}"
