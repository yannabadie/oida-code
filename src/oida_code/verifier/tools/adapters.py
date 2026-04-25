"""Phase 4.2-A/D (QA/A18.md, ADR-27) — deterministic tool adapters.

Each adapter:

* knows how to build its OWN argv from a :class:`VerifierToolRequest`
  (the LLM never composes argv — ADR-27 §accepted #2);
* knows how to parse the tool's stdout into deterministic
  :class:`EvidenceItem` + :class:`Finding` instances (no raw stdout
  reaches the LLM);
* runs through an injected ``executor`` callable so tests can replay
  canned output without invoking the real binary (and so the same
  adapter works in production with :func:`subprocess.run`).

ADR-27 hard rules:

* ``shell=False`` everywhere — the executor receives an argv list.
* ``capture_output=True`` + ``timeout`` enforced.
* missing binary → ``status="tool_missing"`` (uncertainty), not crash.
* timeout → ``status="timeout"``, not crash.
* non-zero exit with no parsed findings → ``status="error"``
  (uncertainty); non-zero exit WITH findings is the normal "the tool
  ran ok and reported issues" case → ``status="failed"``.
"""

from __future__ import annotations

import abc
import json
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oida_code.estimators.llm_prompt import EvidenceItem
from oida_code.models.evidence import Finding
from oida_code.verifier.tools.contracts import (
    ToolName,
    VerifierToolRequest,
    VerifierToolResult,
)
from oida_code.verifier.tools.sandbox import truncate_and_hash


@dataclass(frozen=True)
class ExecutionContext:
    """Inputs an :class:`Executor` needs.

    Carries argv + cwd + timeout + budget. The adapter constructs this
    from the request; the executor only consumes it.
    """

    argv: tuple[str, ...]
    cwd: Path
    timeout_s: int
    binary: str


@dataclass(frozen=True)
class ExecutionOutcome:
    """Output of an :class:`Executor`. ``stdout`` is whatever the tool
    wrote to standard output. ``returncode=None`` means the binary was
    missing; any failure beyond that becomes a non-None returncode."""

    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool
    runtime_ms: int


Executor = Callable[[ExecutionContext], ExecutionOutcome]
"""Single-shot tool executor signature."""


def default_subprocess_executor(ctx: ExecutionContext) -> ExecutionOutcome:
    """Default :class:`Executor` used by the production engine."""
    binary = shutil.which(ctx.binary)
    if binary is None:
        return ExecutionOutcome(
            stdout="", stderr="", returncode=None, timed_out=False,
            runtime_ms=0,
        )
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [binary, *ctx.argv[1:]],
            cwd=str(ctx.cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ctx.timeout_s,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return ExecutionOutcome(
            stdout="", stderr="", returncode=None, timed_out=True,
            runtime_ms=int((time.monotonic() - start) * 1000),
        )
    runtime_ms = int((time.monotonic() - start) * 1000)
    return ExecutionOutcome(
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        timed_out=False,
        runtime_ms=runtime_ms,
    )


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class ToolAdapter(abc.ABC):
    """One adapter per tool. Subclasses implement :meth:`build_argv`
    and :meth:`parse_outcome`. The base class composes them into a
    :class:`VerifierToolResult`, applies the per-tool output cap, and
    handles missing-binary / timeout / error consistently."""

    name: ToolName
    binary: str

    def run(
        self,
        request: VerifierToolRequest,
        *,
        repo_root: Path,
        executor: Executor,
        max_output_chars: int,
    ) -> VerifierToolResult:
        argv = self.build_argv(request, repo_root=repo_root)
        ctx = ExecutionContext(
            argv=argv,
            cwd=repo_root,
            timeout_s=request.max_runtime_s,
            binary=self.binary,
        )
        outcome = executor(ctx)
        if outcome.returncode is None and not outcome.timed_out:
            return VerifierToolResult(
                tool=self.name,
                status="tool_missing",
                warnings=(f"{self.binary} not on PATH",),
                runtime_ms=outcome.runtime_ms,
            )
        if outcome.timed_out:
            return VerifierToolResult(
                tool=self.name,
                status="timeout",
                warnings=(f"{self.binary} exceeded budget {request.max_runtime_s}s",),
                runtime_ms=outcome.runtime_ms,
            )
        truncated_stdout, was_truncated, digest = truncate_and_hash(
            outcome.stdout, max_output_chars,
        )
        try:
            evidence_items, findings, parse_warnings = self.parse_outcome(
                request, truncated_stdout, outcome.stderr,
                outcome.returncode or 0,
            )
        except Exception as exc:  # defensive — never crash the engine
            return VerifierToolResult(
                tool=self.name,
                status="error",
                warnings=(f"{self.binary} output unparseable: {type(exc).__name__}",),
                runtime_ms=outcome.runtime_ms,
                output_truncated=was_truncated,
                output_sha256=digest,
            )
        # Status: failed if findings exist; ok otherwise; error if rc!=0
        # but no findings parsed (likely a tool-level crash).
        rc = outcome.returncode or 0
        if findings:
            status: str = "failed"
        elif rc != 0:
            status = "error"
        else:
            status = "ok"
        return VerifierToolResult(
            tool=self.name,
            status=status,  # type: ignore[arg-type]
            evidence_items=tuple(evidence_items),
            findings=tuple(findings),
            warnings=tuple(parse_warnings),
            runtime_ms=outcome.runtime_ms,
            output_truncated=was_truncated,
            output_sha256=digest,
        )

    @abc.abstractmethod
    def build_argv(
        self, request: VerifierToolRequest, *, repo_root: Path,
    ) -> tuple[str, ...]:
        ...

    @abc.abstractmethod
    def parse_outcome(
        self,
        request: VerifierToolRequest,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> tuple[list[EvidenceItem], list[Finding], list[str]]:
        ...


# ---------------------------------------------------------------------------
# ruff
# ---------------------------------------------------------------------------


def _scope_paths(request: VerifierToolRequest, repo_root: Path) -> list[str]:
    return [str((repo_root / s).as_posix()) for s in request.scope]


def _evidence_id(tool: ToolName, idx: int) -> str:
    return f"[E.tool.{tool}.{idx}]"


class RuffAdapter(ToolAdapter):
    name: ToolName = "ruff"
    binary: str = "ruff"

    def build_argv(
        self, request: VerifierToolRequest, *, repo_root: Path,
    ) -> tuple[str, ...]:
        paths = _scope_paths(request, repo_root) or [str(repo_root)]
        return ("ruff", "check", "--output-format=json", "--no-fix", *paths)

    def parse_outcome(
        self,
        request: VerifierToolRequest,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> tuple[list[EvidenceItem], list[Finding], list[str]]:
        warnings: list[str] = []
        decoded: Any
        try:
            decoded = json.loads(stdout) if stdout.strip() else []
        except json.JSONDecodeError:
            warnings.append("ruff: stdout not valid JSON")
            return [], [], warnings
        if not isinstance(decoded, list):
            warnings.append("ruff: stdout JSON is not a list")
            return [], [], warnings
        items: list[EvidenceItem] = []
        findings: list[Finding] = []
        for idx, raw in enumerate(decoded):
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("filename", "unknown"))
            line = int((raw.get("location") or {}).get("row", 0)) or 0
            code = str(raw.get("code", "?"))
            message = str(raw.get("message", ""))[:200]
            findings.append(Finding(
                tool="ruff",
                rule_id=code,
                severity="error",
                path=path,
                line=line,
                column=int((raw.get("location") or {}).get("column", 0)) or 0,
                message=message,
                evidence_kind="static",
            ))
            items.append(EvidenceItem(
                id=_evidence_id("ruff", idx + 1),
                kind="tool_finding",
                summary=f"ruff {code} at {path}:{line}: {message}"[:400],
                source="ruff",
                confidence=1.0,
            ))
        return items, findings, warnings


# ---------------------------------------------------------------------------
# mypy
# ---------------------------------------------------------------------------


class MypyAdapter(ToolAdapter):
    name: ToolName = "mypy"
    binary: str = "mypy"

    def build_argv(
        self, request: VerifierToolRequest, *, repo_root: Path,
    ) -> tuple[str, ...]:
        paths = _scope_paths(request, repo_root) or [str(repo_root)]
        return ("mypy", "--no-color-output", "--no-error-summary", *paths)

    def parse_outcome(
        self,
        request: VerifierToolRequest,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> tuple[list[EvidenceItem], list[Finding], list[str]]:
        items: list[EvidenceItem] = []
        findings: list[Finding] = []
        warnings: list[str] = []
        for idx, line in enumerate(stdout.splitlines()):
            stripped = line.strip()
            if not stripped or ": error:" not in stripped:
                continue
            head, _, rest = stripped.partition(": error:")
            path_part, _, line_part = head.partition(":")
            try:
                line_no = int(line_part) if line_part else 0
            except ValueError:
                line_no = 0
            message = rest.strip()[:200]
            findings.append(Finding(
                tool="mypy",
                rule_id="mypy-error",
                severity="error",
                path=path_part,
                line=line_no,
                column=0,
                message=message,
                evidence_kind="static",
            ))
            items.append(EvidenceItem(
                id=_evidence_id("mypy", idx + 1),
                kind="tool_finding",
                summary=f"mypy at {path_part}:{line_no}: {message}"[:400],
                source="mypy",
                confidence=1.0,
            ))
        return items, findings, warnings


# ---------------------------------------------------------------------------
# pytest (scoped, --no-header, -q)
# ---------------------------------------------------------------------------


class PytestAdapter(ToolAdapter):
    name: ToolName = "pytest"
    binary: str = "pytest"

    def build_argv(
        self, request: VerifierToolRequest, *, repo_root: Path,
    ) -> tuple[str, ...]:
        paths = _scope_paths(request, repo_root)
        if not paths:
            return ("pytest", "-q", "--no-header", "--maxfail=20")
        return ("pytest", "-q", "--no-header", "--maxfail=20", *paths)

    def parse_outcome(
        self,
        request: VerifierToolRequest,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> tuple[list[EvidenceItem], list[Finding], list[str]]:
        items: list[EvidenceItem] = []
        findings: list[Finding] = []
        warnings: list[str] = []
        # pytest reports failures as lines starting "FAILED <path>::<test>".
        for idx, raw_line in enumerate(stdout.splitlines()):
            line = raw_line.strip()
            if not line.startswith("FAILED "):
                continue
            target = line[len("FAILED "):].split(" ")[0]
            path = target.split("::", 1)[0]
            findings.append(Finding(
                tool="pytest",
                rule_id="pytest-failure",
                severity="error",
                path=path,
                line=0,
                column=0,
                message=target[:200],
                evidence_kind="regression",
            ))
            items.append(EvidenceItem(
                id=_evidence_id("pytest", idx + 1),
                kind="test_result",
                summary=f"pytest FAILED: {target}"[:400],
                source="pytest",
                confidence=1.0,
            ))
        # If pytest passed cleanly, surface a positive evidence item so
        # the LLM can cite it (otherwise an OK run produces no refs).
        if returncode == 0 and not findings and stdout.strip():
            items.append(EvidenceItem(
                id=_evidence_id("pytest", 0),
                kind="test_result",
                summary=(
                    f"pytest passed scoped to {list(request.scope) or ['<all>']} "
                    "with no failures"
                )[:400],
                source="pytest",
                confidence=0.85,
            ))
        return items, findings, warnings


__all__ = [
    "ExecutionContext",
    "ExecutionOutcome",
    "Executor",
    "MypyAdapter",
    "PytestAdapter",
    "RuffAdapter",
    "ToolAdapter",
    "default_subprocess_executor",
]
