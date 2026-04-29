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
import re
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

    def extract_summary_line(self, stdout: str) -> str | None:
        """Phase 5.8.x / ADR-47 — pytest-shaped hook for tools whose stdout
        carries a single terminal summary line worth surfacing on
        :attr:`VerifierToolResult.pytest_summary_line`.

        Default implementation returns ``None``; only :class:`PytestAdapter`
        overrides. The base must NOT know about pytest specifically — this
        keeps adapter responsibilities narrow.
        """
        return None

    def _diagnostic_evidence(
        self, *, summary: str, confidence: float = 0.5,
    ) -> tuple[EvidenceItem, ...]:
        """QA/A39 §4 invariant — every requested tool produces at least
        one citable evidence item, even when the tool failed. The
        synthesised item uses ``id=[E.tool.<binary>.0]`` (same idx the
        clean-pass branch uses), ``kind="tool_finding"``, and the given
        diagnostic summary so callers citing ``[E.tool.<binary>.0]`` in
        a claim's ``evidence_refs`` always resolve to *something*. The
        verifier's downstream contradiction enforcer is responsible for
        deciding whether the diagnostic actually supports the claim.
        """
        return (
            EvidenceItem(
                id=_evidence_id(self.name, 0),
                kind="tool_finding",
                summary=summary[:400],
                source=self.binary,
                confidence=confidence,
            ),
        )

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
            warning = f"{self.binary} not on PATH"
            return VerifierToolResult(
                tool=self.name,
                status="tool_missing",
                evidence_items=self._diagnostic_evidence(
                    summary=(
                        f"{self.binary} could not be invoked: not on PATH "
                        f"(scope={list(request.scope) or ['<all>']})"
                    ),
                ),
                warnings=(warning,),
                runtime_ms=outcome.runtime_ms,
            )
        if outcome.timed_out:
            warning = (
                f"{self.binary} exceeded budget {request.max_runtime_s}s"
            )
            return VerifierToolResult(
                tool=self.name,
                status="timeout",
                evidence_items=self._diagnostic_evidence(
                    summary=(
                        f"{self.binary} exceeded the per-tool runtime budget "
                        f"of {request.max_runtime_s}s "
                        f"(scope={list(request.scope) or ['<all>']})"
                    ),
                ),
                warnings=(warning,),
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
                evidence_items=self._diagnostic_evidence(
                    summary=(
                        f"{self.binary} output unparseable "
                        f"({type(exc).__name__}); rc={outcome.returncode}"
                    ),
                ),
                warnings=(
                    f"{self.binary} output unparseable: {type(exc).__name__}",
                ),
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
        # Phase 5.8.1 / QA/A39 §4 invariant — when the tool ran but
        # produced nothing citable AND status is "error", synthesise a
        # diagnostic evidence item so a downstream claim citing
        # [E.tool.<binary>.0] can resolve. The "ok" / "failed" branches
        # already emit citable items via parse_outcome.
        if status == "error" and not evidence_items:
            stderr_excerpt = (outcome.stderr or "").strip()[:200]
            stdout_excerpt = (truncated_stdout or "").strip()[:200]
            tail = stderr_excerpt or stdout_excerpt or "(no output)"
            evidence_items = list(self._diagnostic_evidence(
                summary=(
                    f"{self.binary} exited rc={rc} with no parseable "
                    f"findings; output excerpt: {tail}"
                ),
            ))
        # Phase 5.8.x / ADR-47 — surface a structured terminal summary line
        # alongside the citable evidence chain (default None for tools that
        # don't override the hook).
        summary_line = self.extract_summary_line(truncated_stdout)
        return VerifierToolResult(
            tool=self.name,
            status=status,  # type: ignore[arg-type]
            evidence_items=tuple(evidence_items),
            findings=tuple(findings),
            warnings=tuple(parse_warnings),
            runtime_ms=outcome.runtime_ms,
            output_truncated=was_truncated,
            output_sha256=digest,
            pytest_summary_line=summary_line,
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


def _extract_pytest_plugin_args(repo_root: Path) -> tuple[str, ...]:
    """Phase 6.1'e fix (ADR-58 step 3): scan the target's
    ``pyproject.toml`` for ``[tool.pytest].addopts`` (or
    ``[tool.pytest.ini_options].addopts``) and extract any
    ``-p <plugin>`` pair (or ``--plugins=<plugin>``-style flag).

    Returns a flat tuple of args to insert into the verifier's
    pytest argv. The ``-o addopts=`` neutralisation in
    :class:`PytestAdapter` would otherwise strip these and turn
    plugin-registered options (e.g. ``pytester_example_dir``)
    into "Unknown config option" errors, killing the run.

    Returns an empty tuple if:

    * the target has no ``pyproject.toml``,
    * the file fails to parse as TOML,
    * neither ``[tool.pytest]`` nor ``[tool.pytest.ini_options]``
      defines an ``addopts`` entry,
    * ``addopts`` contains no ``-p`` directive.

    Reads only — no side effects on the target tree.
    """
    try:
        import tomllib
    except ImportError:  # pragma: no cover  — Python < 3.11
        return ()
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return ()
    try:
        data = tomllib.loads(
            pyproject.read_text(encoding="utf-8"),
        )
    except Exception:  # pragma: no cover  — defensive parsing
        return ()
    tool = data.get("tool", {})
    candidates: list[Any] = []
    pytest_section = tool.get("pytest")
    if isinstance(pytest_section, dict):
        if "addopts" in pytest_section:
            candidates.append(pytest_section["addopts"])
        ini_options = pytest_section.get("ini_options")
        if isinstance(ini_options, dict) and "addopts" in ini_options:
            candidates.append(ini_options["addopts"])
    out: list[str] = []
    for raw in candidates:
        tokens: list[str] = []
        if isinstance(raw, list):
            tokens = [str(x) for x in raw]
        elif isinstance(raw, str):
            tokens = raw.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "-p" and i + 1 < len(tokens):
                out.append("-p")
                out.append(tokens[i + 1])
                i += 2
                continue
            i += 1
    return tuple(out)


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


_PYTEST_SUMMARY_LINE_RE = re.compile(
    # optional '=' decoration + count-verb terms (passed / failed / skipped /
    # error[s] / xfailed / xpassed / warning[s] / deselected) joined by commas,
    # then "in N.NNs" wall-clock segment, optional decoration. The capture
    # group strips both decorations so the surfaced string is the canonical
    # "29 passed, 0 skipped in 0.21s" core line.
    r"^=*\s*"
    r"(\d+\s+(?:passed|failed|skipped|errors?|xfailed|xpassed|warnings?|deselected)"
    r"\b.*\bin\s+[\d.]+s)"
    r"\s*=*\s*$"
)

# CSI / SGR ANSI escapes — projects that pin ``addopts = "--color=yes"`` in
# pyproject.toml (e.g. python-slugify) emit colored output even when stdout
# is a pipe, so the summary parser must strip the codes before applying the
# canonical regex. Matches CSI introducer + parameter bytes + final byte
# (covers SGR colors and the broader CSI grammar without over-matching).
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class PytestAdapter(ToolAdapter):
    name: ToolName = "pytest"
    binary: str = "pytest"

    def build_argv(
        self, request: VerifierToolRequest, *, repo_root: Path,
    ) -> tuple[str, ...]:
        # Phase 5.9 / ADR-49 sub-decision — neutralise the target's
        # pyproject.toml ``addopts`` so gateway behavior is independent
        # of target-side pytest config. Without this, a target pinning
        # ``addopts = "-q ..."`` plus our own ``-q`` collapses to ``-qq``
        # which suppresses the terminal summary line and breaks
        # pytest_summary_line. ``-o addopts=`` overrides any ini setting
        # for that key with an empty string.
        #
        # Phase 6.1'e fix (ADR-58 step 3): when the target's addopts
        # include ``-p <plugin>`` directives (pre-loading plugins like
        # ``pytester``), the neutralization above also strips those.
        # Plugins registered options (e.g. ``pytester_example_dir``)
        # then become "Unknown config option" errors, killing the run.
        # Preserve any ``-p <plugin>`` pairs from the target's
        # ``[tool.pytest].addopts`` (or ``[tool.pytest.ini_options]``)
        # so plugin-registered options remain known.
        paths = _scope_paths(request, repo_root)
        plugin_args = _extract_pytest_plugin_args(repo_root)
        base: tuple[str, ...] = (
            "pytest", "-o", "addopts=",
            *plugin_args,
            "-q", "--no-header", "--maxfail=20",
        )
        if not paths:
            return base
        return (*base, *paths)

    def extract_summary_line(self, stdout: str) -> str | None:
        """Phase 5.8.x / ADR-47 — return pytest's canonical terminal
        summary ("29 passed, 0 skipped in 0.21s") so the result carries
        passed/skipped/failed counts as a structured field.

        Scans stdout from bottom to top so the LAST summary-shaped line
        wins (pytest may emit a stale line earlier in noisy plugins). A
        line with no terminal summary returns ``None`` — never fabricate
        counts when the run didn't surface them.

        ANSI escape codes are stripped before matching because some
        projects pin ``addopts = "--color=yes"`` in pyproject.toml,
        which forces colored output even when stdout is a pipe.
        """
        for raw_line in reversed(stdout.splitlines()):
            cleaned = _ANSI_ESCAPE_RE.sub("", raw_line).strip()
            match = _PYTEST_SUMMARY_LINE_RE.match(cleaned)
            if match:
                return match.group(1).strip()
        return None

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
            # Phase 5.8.x / ADR-47 — fold the canonical terminal summary
            # ("29 passed, 0 skipped in 0.21s") into the operator-facing
            # evidence summary so cgpro / human reviewers see counts even
            # if their renderer only consumes evidence_items[*].summary.
            summary_line = self.extract_summary_line(stdout)
            scope = list(request.scope) or ["<all>"]
            if summary_line is not None:
                summary = (
                    f"pytest passed scoped to {scope} "
                    f"with no failures ({summary_line})"
                )
            else:
                summary = (
                    f"pytest passed scoped to {scope} with no failures"
                )
            items.append(EvidenceItem(
                id=_evidence_id("pytest", 0),
                kind="test_result",
                summary=summary[:400],
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
