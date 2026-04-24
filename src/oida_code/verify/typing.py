"""Run the configured static type checker (default: ``mypy``).

Callers that need the stdlib ``typing`` module must import it directly (the
module docstring is a reminder that this file shadows ``typing`` by name).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from oida_code.models.evidence import Finding, Severity, ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_MYPY_TOOL = "mypy"
_MYPY_ARGS = [
    ".",
    "--no-error-summary",
    "--hide-error-context",
    "--show-absolute-path",
    "--show-column-numbers",
]

# mypy default message format:
#   path/to/file.py:12:5: error: Incompatible types  [assignment]
_MYPY_LINE_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+):\s*"
    r"(?P<sev>error|warning|note):\s*(?P<msg>.+?)"
    r"(?:\s+\[(?P<code>[a-zA-Z0-9_-]+)\])?$"
)


def _parse_mypy(stdout: str) -> list[Finding]:
    findings: list[Finding] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _MYPY_LINE_RE.match(line)
        if match is None:
            continue
        if match["sev"] == "note":
            continue  # notes are informational follow-ups, skip for now
        severity: Severity = "error" if match["sev"] == "error" else "warning"
        code = match["code"] or "mypy"
        findings.append(
            Finding(
                tool="mypy",
                rule_id=code,
                severity=severity,
                path=match["path"],
                line=int(match["line"]),
                column=int(match["col"]),
                message=match["msg"],
                evidence_kind="static",
            )
        )
    return findings


def _counts(findings: list[Finding]) -> dict[str, int]:
    counter: Counter[str] = Counter(f.severity for f in findings)
    return dict(counter)


def run_type_check(repo_path: Path | str, *, budget_seconds: int = 60) -> ToolEvidence:
    """Run ``mypy .`` at ``repo_path`` with column + absolute-path flags."""
    result: RunResult = run_tool(
        _MYPY_TOOL,
        _MYPY_ARGS,
        repo_path=Path(repo_path),
        budget_seconds=budget_seconds,
    )

    if result.status != "ok":
        return ToolEvidence(
            tool="mypy",
            status=result.status,
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt(),
        )

    # mypy exit codes: 0 = clean, 1 = issues, 2 = fatal internal error.
    if result.exit_code not in (0, 1, None):
        return ToolEvidence(
            tool="mypy",
            status="error",
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt() or f"mypy exit code {result.exit_code}",
        )

    findings = _parse_mypy(result.stdout)
    return ToolEvidence(
        tool="mypy",
        status="ok",
        duration_ms=result.duration_ms,
        findings=findings,
        counts=_counts(findings),
        tool_version=probe_version(_MYPY_TOOL),
    )


__all__ = ["run_type_check"]
