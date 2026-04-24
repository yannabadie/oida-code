"""Invoke ``mutmut`` and parse survivor / killed counts.

Phase 2 scope (PLAN.md §14): shell-out + parse only. This runner does not
generate mutants on its own; it requires a ``setup.cfg`` / ``pyproject.toml``
section for mutmut or runs with defaults when absent.

If mutmut is not importable in the current interpreter, returns
``status="tool_missing"`` so the mapper keeps its default 0.5 on the
``tests_pass`` mutation term.
"""

from __future__ import annotations

import re
from pathlib import Path

from oida_code.models.evidence import ToolEvidence
from oida_code.verify._runner import RunResult, probe_version, run_tool

_MUTMUT_TOOL = "mutmut"

# mutmut's summary lines look like:
#   Killed 12 out of 17 mutants
#   Survived: 3
#   Skipped: 2
_KILLED_RE = re.compile(r"(?i)killed\s+(\d+)\s+out\s+of\s+(\d+)")
_SURVIVED_RE = re.compile(r"(?i)survived[:\s]+(\d+)")
_TIMEOUT_RE = re.compile(r"(?i)timeout[:\s]+(\d+)")
_SUSPICIOUS_RE = re.compile(r"(?i)suspicious[:\s]+(\d+)")


def _parse_mutmut_results(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if match := _KILLED_RE.search(text):
        counts["killed"] = int(match.group(1))
        counts["total"] = int(match.group(2))
    if match := _SURVIVED_RE.search(text):
        counts["survived"] = int(match.group(1))
    if match := _TIMEOUT_RE.search(text):
        counts["timeout"] = int(match.group(1))
    if match := _SUSPICIOUS_RE.search(text):
        counts["suspicious"] = int(match.group(1))
    return counts


def run_mutmut(repo_path: Path | str, *, budget_seconds: int = 600) -> ToolEvidence:
    """Run ``mutmut results`` after a ``mutmut run`` at ``repo_path``.

    Strategy: a full ``mutmut run`` can take >10 minutes; Phase 2 only needs
    the **last** run's summary. If ``.mutmut-cache`` exists (leftover from a
    prior run), we call ``mutmut results`` directly. Otherwise we attempt a
    budgeted ``mutmut run`` and then ``mutmut results``.
    """
    root = Path(repo_path)
    cache = root / ".mutmut-cache"

    if not cache.exists():
        run_result: RunResult = run_tool(
            _MUTMUT_TOOL,
            ["run"],
            repo_path=root,
            budget_seconds=budget_seconds,
            python_module="mutmut",
        )
        if run_result.status == "tool_missing":
            return ToolEvidence(tool="mutmut", status="tool_missing", duration_ms=0)
        if run_result.status == "timeout":
            # Partial run is still useful — fall through to results parsing.
            pass
        elif run_result.status != "ok":
            return ToolEvidence(
                tool="mutmut",
                status=run_result.status,
                duration_ms=run_result.duration_ms,
                stderr_excerpt=run_result.stderr_excerpt(),
            )

    # mutmut stores its summary in the cache; ``mutmut results`` prints it.
    results = run_tool(
        _MUTMUT_TOOL,
        ["results"],
        repo_path=root,
        budget_seconds=60,
        python_module="mutmut",
    )
    if results.status != "ok":
        return ToolEvidence(
            tool="mutmut",
            status=results.status,
            duration_ms=results.duration_ms,
            stderr_excerpt=results.stderr_excerpt(),
        )

    counts = _parse_mutmut_results(results.stdout)
    return ToolEvidence(
        tool="mutmut",
        status="ok",
        duration_ms=results.duration_ms,
        counts=counts,
        tool_version=probe_version(_MUTMUT_TOOL),
    )


__all__ = ["run_mutmut"]
