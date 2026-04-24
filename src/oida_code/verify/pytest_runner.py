"""Invoke ``pytest`` and surface per-test outcomes via JUnit XML.

JUnit XML is zero-dep and stable across pytest versions (advisor choice). The
runner writes the XML to a temp file, parses it, and converts each failure /
error into a :class:`Finding` with ``evidence_kind="regression"``.
"""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_PYTEST_TOOL = "pytest"


def _parse_junit(xml_path: Path) -> tuple[list[Finding], dict[str, int]]:
    """Return (findings, counts) from a pytest JUnit-XML file."""
    try:
        tree = ET.parse(xml_path)
    except (ET.ParseError, OSError):
        return [], {}

    root = tree.getroot()
    findings: list[Finding] = []
    counts = Counter[str]()

    # JUnit XML can have root = <testsuite> or <testsuites> depending on plugins.
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    for suite in suites:
        for case in suite.iter("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            file_path = case.get("file") or classname.replace(".", "/") + ".py"
            line = int(case.get("line") or 0)
            for child in case:
                tag = child.tag.lower()
                if tag in {"failure", "error"}:
                    counts[tag] += 1
                    message = child.get("message") or child.text or tag
                    findings.append(
                        Finding(
                            tool="pytest",
                            rule_id=f"{classname}::{name}" if classname else name,
                            severity="error",
                            path=file_path,
                            line=line,
                            column=0,
                            message=str(message).strip()[:500],
                            evidence_kind="regression",
                        )
                    )
                elif tag == "skipped":
                    counts["skipped"] += 1

    counts["total"] = sum(1 for _ in root.iter("testcase"))
    counts.setdefault("failure", counts.get("failure", 0))
    counts.setdefault("error", counts.get("error", 0))
    return findings, dict(counts)


def run_pytest(repo_path: Path | str, *, budget_seconds: int = 600) -> ToolEvidence:
    """Run ``pytest --junit-xml=...`` at ``repo_path``.

    Exit code semantics (pytest 8.x):
        0  all tests passed
        1  tests were collected and run but some failed
        2  execution interrupted by the user
        3  internal pytest error
        4  pytest command-line usage error
        5  no tests were collected
    We treat ``0``, ``1``, and ``5`` as ``ok`` (the runner ran). Everything
    else is ``error``.
    """
    root = Path(repo_path)
    with tempfile.TemporaryDirectory(prefix="oida-pytest-") as tmpdir:
        xml_path = Path(tmpdir) / "junit.xml"
        argv = [
            f"--rootdir={root}",
            f"--junit-xml={xml_path}",
            "-q",
            "--maxfail=50",
            "--no-header",
            "--disable-warnings",
        ]
        result: RunResult = run_tool(
            _PYTEST_TOOL,
            argv,
            repo_path=root,
            budget_seconds=budget_seconds,
            python_module="pytest",
        )

        if result.status != "ok":
            return ToolEvidence(
                tool="pytest",
                status=result.status,
                duration_ms=result.duration_ms,
                stderr_excerpt=result.stderr_excerpt(),
            )

        acceptable_exits = {0, 1, 5}
        if result.exit_code is not None and result.exit_code not in acceptable_exits:
            # pytest writes collection errors to stdout, not stderr —
            # fall back to stdout excerpt so the user sees the cause.
            excerpt = result.stderr_excerpt()
            if not excerpt and result.stdout.strip():
                stdout_tail = result.stdout.strip()
                if len(stdout_tail) > 2000:
                    stdout_tail = stdout_tail[-2000:] + "\n… (truncated start)"
                excerpt = stdout_tail
            return ToolEvidence(
                tool="pytest",
                status="error",
                duration_ms=result.duration_ms,
                stderr_excerpt=excerpt or f"pytest exit code {result.exit_code}",
            )

        findings, counts = _parse_junit(xml_path) if xml_path.is_file() else ([], {})

    return ToolEvidence(
        tool="pytest",
        status="ok",
        duration_ms=result.duration_ms,
        findings=findings,
        counts=counts,
        tool_version=probe_version(_PYTEST_TOOL),
    )


__all__ = ["run_pytest"]
