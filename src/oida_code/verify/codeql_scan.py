"""CodeQL scanner — Phase 1 stub, real integration deferred.

The CodeQL CLI is a multi-hundred-MB install with a steep setup cost
(database creation, query pack resolution, cache management). Per the
advisor's scope-realism note, Phase 1 ships a uniform ``tool_missing`` stub:
the contract is preserved, the CLI + report layers treat CodeQL exactly like
any other absent tool. Full integration lands in Phase 2 after the
deterministic pipeline is stable on real repos.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from oida_code.models.evidence import ToolEvidence


def run_codeql(repo_path: Path | str, *, budget_seconds: int = 900) -> ToolEvidence:
    """Return ``ToolEvidence(status="tool_missing" | "skipped")`` — Phase 1 stub.

    ``budget_seconds`` and ``repo_path`` are accepted for signature symmetry
    with the other runners; they are not used yet.
    """
    del repo_path, budget_seconds
    if shutil.which("codeql") is None:
        return ToolEvidence(
            tool="codeql",
            status="tool_missing",
        )
    return ToolEvidence(
        tool="codeql",
        status="skipped",
        stderr_excerpt="CodeQL CLI detected but integration is a Phase 2 task (PLAN.md §10).",
    )


__all__ = ["run_codeql"]
