"""Extract changed files between two revisions.

Phase 1 produces only the flat list of changed file paths needed to populate
``AuditRequest.scope.changed_files``. Hunk-level parsing (for ``extract/`` and
``verify/``) is phase 2.
"""

from __future__ import annotations

from pathlib import Path

from oida_code.ingest.git_repo import run_git


def changed_files(repo_path: Path, base_revision: str, head_revision: str) -> list[str]:
    """Return the list of files that differ between ``base`` and ``head``.

    When ``base == head`` (e.g. inspecting a single-commit repo with
    ``--base HEAD``), the list is empty.
    """
    if base_revision == head_revision:
        return []
    raw = run_git(
        repo_path,
        "diff",
        "--name-only",
        f"{base_revision}..{head_revision}",
    )
    return [line for line in raw.splitlines() if line]


__all__ = ["changed_files"]
