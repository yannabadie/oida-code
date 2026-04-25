"""Phase 4.2-A/B (QA/A18.md, ADR-27) — tool registry contracts.

Frozen Pydantic schemas for the bounded, tool-grounded verifier loop.
ADR-27 hard rules are enforced at the model level + by the policy
validator + by the execution engine. **No shell passthrough.** **No
LLM-chosen argv.** Each adapter builds its own argv from the request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.estimators.llm_prompt import EvidenceItem
from oida_code.models.evidence import Finding

ToolName = Literal[
    "ruff",
    "mypy",
    "pytest",
    "semgrep",
    "codeql",
]
"""Phase 4.2 allowlist. Anything outside this Literal cannot reach
the registry, the engine, or the policy."""


_ToolStatus = Literal["ok", "failed", "error", "timeout", "tool_missing", "blocked"]


class VerifierToolRequest(BaseModel):
    """A request for a single tool invocation.

    Built from a :class:`VerifierToolCallSpec` + audit context. The
    LLM may propose specs, but it does NOT compose the argv. The
    adapter receives this request, validates it against the policy,
    and constructs the argv itself.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool: ToolName
    purpose: str = Field(min_length=1, max_length=200)
    scope: tuple[str, ...] = ()
    max_runtime_s: int = Field(default=10, ge=1, le=600)
    max_output_chars: int = Field(default=8000, ge=128, le=64000)
    requested_by_claim_id: str | None = None


class VerifierToolResult(BaseModel):
    """Result of one tool invocation.

    The runner converts ``status="error"`` / ``timeout`` /
    ``tool_missing`` into UNCERTAINTY (warnings/blockers), never into
    "code is broken". ``status="failed"`` means the tool ran ok and
    found problems — that's a real negative signal.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool: ToolName
    status: _ToolStatus
    evidence_items: tuple[EvidenceItem, ...] = ()
    findings: tuple[Finding, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    runtime_ms: int = Field(default=0, ge=0)
    output_truncated: bool = False
    output_sha256: str | None = None


class ToolPolicy(BaseModel):
    """Policy bounding what tools can run, where, with what budget.

    `allowed_paths` is checked against every path in the request's
    scope; `deny_patterns` block known sensitive files
    (.env, *.key, *.pem, *secret*, .git/config, ...) and any pattern
    the operator adds. `allow_network` / `allow_write` are False by
    default — Phase 4.2 is read-only.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    allowed_tools: tuple[ToolName, ...]
    repo_root: Path
    allowed_paths: tuple[str, ...] = ()
    deny_patterns: tuple[str, ...] = (
        ".env",
        ".env.*",
        "*.key",
        "*.pem",
        "*secret*",
        "*.token",
        ".git/config",
        ".git/hooks/*",
        "id_rsa",
        "id_ed25519",
    )
    allow_network: bool = False
    allow_write: bool = False
    max_tool_calls: int = Field(default=5, ge=1, le=50)
    max_total_runtime_s: int = Field(default=60, ge=1, le=600)
    max_output_chars_per_tool: int = Field(default=8000, ge=128, le=64000)


__all__ = [
    "ToolName",
    "ToolPolicy",
    "VerifierToolRequest",
    "VerifierToolResult",
]
