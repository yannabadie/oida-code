"""Run existing Hypothesis property-based tests and count outcomes.

Phase 2 scope (PLAN.md §14): this runner does **not** synthesize new
property-based tests (Phase 3+). It runs ``pytest`` with a marker filter so
only tests explicitly tagged with ``@pytest.mark.hypothesis`` run, then
reports counts. The mapper reuses those counts to replace its default 0.5
placeholder on the ``tests_pass`` term.

If the Hypothesis library is not importable in the current interpreter, the
runner returns ``status="tool_missing"`` and the mapper's default remains in
place — exactly the advisor-approved behavior for Phase 2 transparency.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from oida_code.models.evidence import ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_HYPOTHESIS_MARKER = "hypothesis"


def _count_from_junit(xml_path: Path) -> dict[str, int]:
    try:
        tree = ET.parse(xml_path)
    except (ET.ParseError, OSError):
        return {}
    root = tree.getroot()
    counts: dict[str, int] = {"total": 0, "failure": 0, "error": 0, "skipped": 0}
    for case in root.iter("testcase"):
        counts["total"] += 1
        for child in case:
            tag = child.tag.lower()
            if tag in {"failure", "error", "skipped"}:
                counts[tag] += 1
    return counts


def run_hypothesis(repo_path: Path | str, *, budget_seconds: int = 300) -> ToolEvidence:
    """Run ``pytest -m hypothesis --junit-xml=...`` at ``repo_path``.

    Exit-code semantics match :mod:`oida_code.verify.pytest_runner` (0/1/5
    are ``ok``).
    """
    root = Path(repo_path)
    with tempfile.TemporaryDirectory(prefix="oida-hypothesis-") as tmpdir:
        xml_path = Path(tmpdir) / "junit.xml"
        argv = [
            f"--rootdir={root}",
            f"--junit-xml={xml_path}",
            "-m",
            _HYPOTHESIS_MARKER,
            "-q",
            "--no-header",
            "--disable-warnings",
        ]
        result: RunResult = run_tool(
            "pytest",
            argv,
            repo_path=root,
            budget_seconds=budget_seconds,
            python_module="pytest",
        )

        if result.status != "ok":
            return ToolEvidence(
                tool="hypothesis",
                status=result.status,
                duration_ms=result.duration_ms,
                stderr_excerpt=result.stderr_excerpt(),
            )

        # Exit 5 = "no tests collected" → count as ok with total=0.
        acceptable = {0, 1, 5}
        if result.exit_code is not None and result.exit_code not in acceptable:
            return ToolEvidence(
                tool="hypothesis",
                status="error",
                duration_ms=result.duration_ms,
                stderr_excerpt=(
                    result.stderr_excerpt() or f"pytest exit code {result.exit_code}"
                ),
            )

        counts = _count_from_junit(xml_path) if xml_path.is_file() else {}

    return ToolEvidence(
        tool="hypothesis",
        status="ok",
        duration_ms=result.duration_ms,
        counts=counts,
        tool_version=probe_version("hypothesis") or probe_version("pytest"),
    )


__all__ = ["run_hypothesis"]
