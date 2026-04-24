"""Run Semgrep SAST with a starter ruleset.

Semgrep is expected on PATH (not a pyproject dependency — 500 MB install).
Absent: ``ToolEvidence(status="tool_missing")`` — the CLI treats it
identically to any other missing tool.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from oida_code.models.evidence import Finding, Severity, ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_SEMGREP_TOOL = "semgrep"
_DEFAULT_CONFIG = "auto"  # Semgrep's built-in "p/ci" auto profile


def _severity_from_semgrep(raw: str | None) -> Severity:
    value = (raw or "").upper()
    if value in {"ERROR", "HIGH", "CRITICAL"}:
        return "error"
    if value in {"WARNING", "MEDIUM"}:
        return "warning"
    if value == "INFO":
        return "info"
    return "warning"


def _parse_semgrep(stdout: str) -> list[Finding]:
    if not stdout.strip():
        return []
    try:
        payload: Any = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return []
    findings: list[Finding] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("check_id") or "semgrep")
        path = str(item.get("path") or "")
        start = item.get("start") or {}
        line = int(start.get("line") or 0) if isinstance(start, dict) else 0
        column = int(start.get("col") or 0) if isinstance(start, dict) else 0
        extra = item.get("extra") or {}
        raw_severity = extra.get("severity") if isinstance(extra, dict) else None
        severity = _severity_from_semgrep(raw_severity)
        message = str(extra.get("message") or "") if isinstance(extra, dict) else ""
        findings.append(
            Finding(
                tool="semgrep",
                rule_id=check_id,
                severity=severity,
                path=path,
                line=line,
                column=column,
                message=message,
                evidence_kind="static",
            )
        )
    return findings


def _counts(findings: list[Finding]) -> dict[str, int]:
    counter: Counter[str] = Counter(f.severity for f in findings)
    return dict(counter)


def run_semgrep(
    repo_path: Path | str,
    *,
    budget_seconds: int = 120,
    config: str = _DEFAULT_CONFIG,
) -> ToolEvidence:
    """Run ``semgrep --config=<auto> --json`` at ``repo_path``."""
    argv = [
        "scan",
        f"--config={config}",
        "--json",
        "--quiet",
        "--error",
        ".",
    ]

    result: RunResult = run_tool(
        _SEMGREP_TOOL,
        argv,
        repo_path=Path(repo_path),
        budget_seconds=budget_seconds,
    )

    if result.status != "ok":
        return ToolEvidence(
            tool="semgrep",
            status=result.status,
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt(),
        )

    # Semgrep exits 1 when it finds issues with --error, 0 otherwise.
    if result.exit_code not in (0, 1, None):
        return ToolEvidence(
            tool="semgrep",
            status="error",
            duration_ms=result.duration_ms,
            stderr_excerpt=result.stderr_excerpt() or f"semgrep exit code {result.exit_code}",
        )

    findings = _parse_semgrep(result.stdout)
    return ToolEvidence(
        tool="semgrep",
        status="ok",
        duration_ms=result.duration_ms,
        findings=findings,
        counts=_counts(findings),
        tool_version=probe_version(_SEMGREP_TOOL),
    )


__all__ = ["run_semgrep"]
