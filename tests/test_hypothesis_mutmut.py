"""Phase-2 unit tests for the hypothesis and mutmut runners.

Both are shell-out-and-parse wrappers (PLAN.md §14): tests mock the
underlying ``subprocess.run`` and ``shutil.which`` so they never spawn the
real tools.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from oida_code.verify import _runner as runner_mod
from oida_code.verify import hypothesis_runner as hypo_mod
from oida_code.verify import mutmut_runner as mut_mod

# ---------------------------------------------------------------------------
# hypothesis_runner
# ---------------------------------------------------------------------------


def test_hypothesis_parses_junit_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    junit_written: list[Path] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        # Locate `--junit-xml=<path>` in argv and write a stub.
        xml_path: Path | None = None
        for arg in cmd:
            if isinstance(arg, str) and arg.startswith("--junit-xml="):
                xml_path = Path(arg.split("=", 1)[1])
                break
        assert xml_path is not None
        xml_path.write_text(
            '<?xml version="1.0"?>'
            "<testsuite>"
            '<testcase classname="t" name="t1"/>'
            '<testcase classname="t" name="t2"><failure/></testcase>'
            '<testcase classname="t" name="t3"/>'
            "</testsuite>",
            encoding="utf-8",
        )
        junit_written.append(xml_path)
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    # Skip the version probe.
    monkeypatch.setattr(hypo_mod, "probe_version", lambda _binary: None)

    ev = hypo_mod.run_hypothesis(tmp_path, budget_seconds=10)
    assert ev.status == "ok"
    assert ev.counts.get("total") == 3
    assert ev.counts.get("failure") == 1


def test_hypothesis_handles_no_tests_collected_exit_5(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """pytest exit 5 = no tests matched; runner must report ok with total=0."""

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=cmd, returncode=5, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hypo_mod, "probe_version", lambda _binary: None)

    ev = hypo_mod.run_hypothesis(tmp_path, budget_seconds=10)
    assert ev.status == "ok"
    # No junit file was written, so counts stays empty — that's fine.
    assert ev.counts.get("total", 0) == 0


def test_hypothesis_reports_tool_missing_when_pytest_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner_mod, "_module_importable", lambda _m: False)
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _b: None)

    ev = hypo_mod.run_hypothesis(tmp_path, budget_seconds=10)
    assert ev.status == "tool_missing"


# ---------------------------------------------------------------------------
# mutmut_runner
# ---------------------------------------------------------------------------


def test_mutmut_parses_results_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Pretend cache exists to skip the `mutmut run` step.
    (tmp_path / ".mutmut-cache").mkdir()

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        # Only `mutmut results` should be invoked; emit the summary text.
        assert "results" in cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="Killed 8 out of 10 mutants\nSurvived: 2\nTimeout: 0\n",
            stderr="",
        )

    # Pretend mutmut is importable so run_tool doesn't short-circuit to
    # tool_missing in environments that don't actually have it installed.
    monkeypatch.setattr(runner_mod, "_module_importable", lambda _m: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(mut_mod, "probe_version", lambda _binary: None)

    ev = mut_mod.run_mutmut(tmp_path, budget_seconds=10)
    assert ev.status == "ok"
    assert ev.counts.get("killed") == 8
    assert ev.counts.get("total") == 10
    assert ev.counts.get("survived") == 2


def test_mutmut_tool_missing_when_not_importable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner_mod, "_module_importable", lambda _m: False)
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _b: None)

    ev = mut_mod.run_mutmut(tmp_path, budget_seconds=10)
    assert ev.status == "tool_missing"


def test_mutmut_regex_handles_case_and_whitespace() -> None:
    sample = "KILLED 17  out  of  20  mutants\nsurvived:   3\nTIMEOUT: 0\nSuspicious: 1"
    counts = mut_mod._parse_mutmut_results(sample)
    assert counts == {
        "killed": 17,
        "total": 20,
        "survived": 3,
        "timeout": 0,
        "suspicious": 1,
    }
