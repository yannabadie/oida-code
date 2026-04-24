"""Run the configured linter (default: ``ruff``).

Phase 1: hard-wired to ruff JSON output. Other linters (flake8, pylint) are
detected by :mod:`oida_code.ingest.manifest` but not executed here yet —
extending the runner is a phase-2 polish job.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from oida_code.models.evidence import Finding, Severity, ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_RUFF_TOOL = "ruff"
_RUFF_ARGS = ["check", ".", "--output-format=json", "--no-fix", "--exit-zero"]


def _ruff_findings(stdout: str) -> list[Finding]:
    if not stdout.strip():
        return []
    try:
        payload: Any = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    findings: list[Finding] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "ruff")
        filename = str(item.get("filename") or "")
        location = item.get("location") or {}
        row = int(location.get("row") or 0) if isinstance(location, dict) else 0
        column = int(location.get("column") or 0) if isinstance(location, dict) else 0
        message = str(item.get("message") or "")
        findings.append(
            Finding(
                tool="ruff",
                rule_id=code,
                severity=_ruff_severity(code),
                path=filename,
                line=row,
                column=column,
                message=message,
                evidence_kind="static",
            )
        )
    return findings


def _ruff_severity(code: str) -> Severity:
    # Ruff maps to pycodestyle / pyflakes / pylint rule prefixes. Treat
    # E, F, SIM, B, S (security) as errors; the rest as warnings.
    if not code:
        return "warning"
    prefix = code[0].upper()
    if prefix in {"E", "F", "S", "B"}:
        return "error"
    return "warning"


def _counts(findings: list[Finding]) -> dict[str, int]:
    counter: Counter[str] = Counter(f.severity for f in findings)
    return dict(counter)


def run_lint(repo_path: Path | str, *, budget_seconds: int = 30) -> ToolEvidence:
    """Run ``ruff check . --output-format=json`` at ``repo_path``."""
    result: RunResult = run_tool(
        _RUFF_TOOL,
        _RUFF_ARGS,
        repo_path=Path(repo_path),
        budget_seconds=budget_seconds,
    )

    if result.status != "ok":
        return ToolEvidence(
            tool="ruff",
            status=result.status,
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt(),
        )

    # ``--exit-zero`` forces ruff to return 0 even with findings; a non-zero
    # exit therefore signals an internal ruff error.
    if result.exit_code not in (0, None):
        return ToolEvidence(
            tool="ruff",
            status="error",
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt() or f"ruff exit code {result.exit_code}",
        )

    findings = _ruff_findings(result.stdout)
    return ToolEvidence(
        tool="ruff",
        status="ok",
        duration_ms=result.duration_ms,
        findings=findings,
        counts=_counts(findings),
        tool_version=probe_version(_RUFF_TOOL),
    )


__all__ = ["run_lint"]
