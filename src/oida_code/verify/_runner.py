"""Shared subprocess helper for every verifier runner.

Contract (advisor-mandated, PLAN.md §14 Phase 1):

* Never raise on missing binary, timeout, or non-zero exit.
* Return a :class:`RunResult` dataclass every time.
* Caller converts :class:`RunResult` → :class:`ToolEvidence` per tool semantics
  (e.g. ruff exit=1 means "findings", pytest exit=1 means "tests failed").
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from oida_code.models.evidence import ToolStatus

_RunStatus = Literal["ok", "tool_missing", "timeout", "error"]
_STDERR_EXCERPT_LIMIT = 2000


@dataclass(frozen=True, slots=True)
class RunResult:
    """Raw outcome of invoking an external tool."""

    status: _RunStatus
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    exit_code: int | None = None
    cmd: list[str] = field(default_factory=list)

    def stderr_excerpt(self) -> str | None:
        if not self.stderr.strip():
            return None
        text = self.stderr.strip()
        if len(text) > _STDERR_EXCERPT_LIMIT:
            text = text[:_STDERR_EXCERPT_LIMIT] + "\n… (truncated)"
        return text


def run_tool(
    binary: str,
    argv: list[str],
    *,
    repo_path: Path,
    budget_seconds: int,
) -> RunResult:
    """Invoke ``binary argv*`` at ``repo_path`` with a wall-clock budget.

    ``status`` semantics::

        "ok"            binary ran to completion (any exit code)
        "tool_missing"  ``shutil.which(binary)`` returned ``None``
        "timeout"       exceeded ``budget_seconds``
        "error"         OSError / permission denied / other subprocess failure

    The caller is responsible for interpreting ``exit_code`` per tool contract.
    """
    resolved = shutil.which(binary)
    if resolved is None:
        return RunResult(status="tool_missing", cmd=[binary, *argv])

    cmd = [resolved, *argv]
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=budget_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return RunResult(
            status="timeout",
            stdout="",
            stderr=stderr,
            duration_ms=duration_ms,
            cmd=cmd,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return RunResult(
            status="error",
            stdout="",
            stderr=str(exc),
            duration_ms=duration_ms,
            cmd=cmd,
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    return RunResult(
        status="ok",
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_ms=duration_ms,
        exit_code=proc.returncode,
        cmd=cmd,
    )


def tool_status_from_run(result: RunResult) -> ToolStatus:
    """Map a :class:`RunResult` to the public :data:`ToolStatus` literal."""
    # The literals happen to overlap, but this keeps the mapping explicit.
    return result.status


def probe_version(binary: str, *, arg: str = "--version") -> str | None:
    """Return the first line of ``binary --version`` stdout, or ``None``.

    Cheap best-effort probe: never raises, 5-second timeout, falls back to
    the first line of stderr when a tool prints its version there.
    """
    resolved = shutil.which(binary)
    if resolved is None:
        return None
    try:
        proc = subprocess.run(
            [resolved, arg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    for stream in (proc.stdout, proc.stderr):
        stripped = (stream or "").strip()
        if stripped:
            return stripped.splitlines()[0][:120]
    return None


__all__ = ["RunResult", "probe_version", "run_tool", "tool_status_from_run"]
