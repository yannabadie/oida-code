"""Phase 4.2 (QA/A18.md, ADR-27) — bounded tool-grounded verifier loop.

Sub-modules:

* :mod:`oida_code.verifier.tools.contracts` — frozen Pydantic schemas
  ``VerifierToolRequest`` / ``VerifierToolResult`` / ``ToolPolicy``.
* :mod:`oida_code.verifier.tools.sandbox` — path validation, deny
  patterns, output truncation + SHA256.
* :mod:`oida_code.verifier.tools.adapters` — deterministic per-tool
  adapters (ruff / mypy / pytest at minimum). Each builds its own
  argv; **no shell passthrough**.
* :mod:`oida_code.verifier.tools.registry` — adapter lookup.
* The :class:`ToolExecutionEngine` defined here drives a list of
  requests through policy validation + adapter execution + budget
  enforcement, returning one :class:`VerifierToolResult` per request.

ADR-27 hard rules:

* read-only by default (`allow_write=False`, `allow_network=False`)
* allowlist-only tools
* per-tool timeout + per-engine total runtime + per-tool output cap
* no shell passthrough; argv is built by the adapter itself
* tool output is truncated + hashed; raw bytes never reach the LLM
* missing tool → uncertainty, never code-failure
* no MCP integration in Phase 4.2
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from oida_code.verifier.tools.adapters import (
    Executor,
    default_subprocess_executor,
)
from oida_code.verifier.tools.contracts import (
    ToolName,
    ToolPolicy,
    VerifierToolRequest,
    VerifierToolResult,
)
from oida_code.verifier.tools.registry import get_adapter, supported_tools
from oida_code.verifier.tools.sandbox import (
    SandboxViolation,
    truncate_and_hash,
    validate_request,
)


@dataclass
class ToolExecutionEngine:
    """Runs a budgeted batch of tool requests through allowlisted adapters.

    The engine is the ONLY path that calls an executor in production.
    Tests inject a fake :class:`Executor` so no subprocess is spawned.
    """

    executor: Executor | None = None

    def run(
        self,
        requests: Sequence[VerifierToolRequest],
        policy: ToolPolicy,
    ) -> tuple[VerifierToolResult, ...]:
        from oida_code.verifier.tools import adapters as _adapters

        # ``executor`` is resolved at call time so a test that
        # monkey-patches ``adapters.default_subprocess_executor`` is
        # picked up here. The dataclass default-value approach would
        # capture the original function reference at class-creation
        # time and bypass monkey-patching.
        executor = self.executor or _adapters.default_subprocess_executor

        # Guard: too many requests → process the first N normally, then
        # append blocked entries for the remainder so the result list
        # mirrors the request order.
        extras: tuple[VerifierToolRequest, ...] = ()
        if len(requests) > policy.max_tool_calls:
            extras = tuple(requests[policy.max_tool_calls:])
            requests = requests[: policy.max_tool_calls]

        results: list[VerifierToolResult] = []
        total_runtime_ms = 0
        budget_ms = policy.max_total_runtime_s * 1000
        for request in requests:
            # 4.2.1 — clamp the per-tool timeout to the remaining
            # global budget BEFORE invoking the executor, so a single
            # slow tool can't push past the engine-level budget. If
            # there's no budget left at all, block without any
            # subprocess call.
            remaining_ms = budget_ms - total_runtime_ms
            if remaining_ms <= 0:
                results.append(VerifierToolResult(
                    tool=request.tool,
                    status="blocked",
                    blockers=(
                        f"max_total_runtime_s={policy.max_total_runtime_s} "
                        f"exhausted before request {request.tool}/"
                        f"{request.purpose!r}; executor not invoked",
                    ),
                ))
                continue
            try:
                validate_request(request, policy)
            except SandboxViolation as exc:
                results.append(VerifierToolResult(
                    tool=request.tool,
                    status="blocked",
                    blockers=(str(exc),),
                ))
                continue
            try:
                adapter = get_adapter(request.tool)
            except KeyError as exc:
                results.append(VerifierToolResult(
                    tool=request.tool,
                    status="blocked",
                    blockers=(str(exc),),
                ))
                continue
            # Effective per-call timeout — the smaller of the request's
            # own budget and what's left of the engine-level budget.
            effective_timeout_s = max(
                1, min(request.max_runtime_s, max(1, remaining_ms // 1000)),
            )
            clamped_request = request.model_copy(
                update={"max_runtime_s": effective_timeout_s},
            )
            start = time.monotonic()
            outcome = adapter.run(
                clamped_request,
                repo_root=policy.repo_root,
                executor=executor,
                max_output_chars=policy.max_output_chars_per_tool,
            )
            # 4.2.1 — honor the larger of wall-clock and executor-
            # reported runtime so a fake/replay executor reporting a
            # synthetic runtime still consumes the engine's budget.
            wall_ms = int((time.monotonic() - start) * 1000)
            total_runtime_ms += max(wall_ms, outcome.runtime_ms)
            results.append(outcome)

        # Append the over-budget extras, preserving request order.
        for extra in extras:
            results.append(VerifierToolResult(
                tool=extra.tool,
                status="blocked",
                blockers=(
                    f"max_tool_calls={policy.max_tool_calls} exceeded; "
                    f"request {extra.tool}/{extra.purpose!r} skipped",
                ),
            ))
        return tuple(results)


__all__ = [
    "Executor",
    "SandboxViolation",
    "ToolExecutionEngine",
    "ToolName",
    "ToolPolicy",
    "VerifierToolRequest",
    "VerifierToolResult",
    "default_subprocess_executor",
    "get_adapter",
    "supported_tools",
    "truncate_and_hash",
    "validate_request",
]
