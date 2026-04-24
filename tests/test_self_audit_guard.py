"""ADR-16 — self-audit fork guard.

When oida-code audits its own repository, pytest's collection would pick
up tests that themselves invoke the CLI via :class:`typer.testing.CliRunner`,
which then runs the full audit pipeline, which runs pytest, which...
On Windows/Cygwin fork emulation, this explodes into a fork bomb.

Guard rule: when ``pyproject.toml[project].name == "oida-code"`` in the
audited tree, :func:`oida_code.verify.pytest_runner.run_pytest` appends
``--ignore=<recursive-test>`` for each known reentering test file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from oida_code.ingest.manifest import is_self_audit, project_name
from oida_code.verify import pytest_runner


def _write_pyproject(root: Path, name: str) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\n', encoding="utf-8"
    )


def test_project_name_reads_toml(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "oida-code")
    assert project_name(tmp_path) == "oida-code"


def test_project_name_returns_none_when_missing(tmp_path: Path) -> None:
    assert project_name(tmp_path) is None


def test_is_self_audit_true_on_oida_code(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "oida-code")
    assert is_self_audit(tmp_path) is True


def test_is_self_audit_false_on_other_projects(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "attrs")
    assert is_self_audit(tmp_path) is False


def test_pytest_runner_adds_ignore_flags_on_self_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When is_self_audit is True, pytest argv gains --ignore entries."""
    _write_pyproject(tmp_path, "oida-code")
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=5, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(pytest_runner, "probe_version", lambda _b: None)

    pytest_runner.run_pytest(tmp_path, budget_seconds=5)

    assert captured, "subprocess.run never invoked"
    flat = " ".join(captured[0])
    for ignore in pytest_runner._SELF_AUDIT_IGNORES:
        assert ignore.replace("/", "\\") in flat or ignore in flat, (
            f"missing self-audit ignore for {ignore} in {flat}"
        )


def test_pytest_runner_does_not_add_ignore_flags_on_regular_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A normal target (non-oida-code pyproject) gets the plain argv."""
    _write_pyproject(tmp_path, "some-other-project")
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=5, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(pytest_runner, "probe_version", lambda _b: None)

    pytest_runner.run_pytest(tmp_path, budget_seconds=5)

    assert captured
    flat = " ".join(captured[0])
    assert "--ignore=" not in flat, (
        f"non-self-audit pipeline should not inject ignores: {flat}"
    )
