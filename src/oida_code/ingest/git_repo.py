"""Read-only git repo introspection for Pass 1 fact collection.

Responsibilities (phase 1):

* resolve an absolute repo path and confirm it is inside a git work tree;
* resolve ``HEAD`` and a user-supplied base revision to short SHAs;
* expose a thin ``git`` runner that refuses shell interpolation.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 30


class GitRepoError(RuntimeError):
    """Raised when a git invocation fails or the path is not a work tree."""


@dataclass(frozen=True, slots=True)
class GitRepoState:
    """Deterministic snapshot of the repo at inspection time."""

    path: Path
    revision: str
    base_revision: str


def _git_binary() -> str:
    binary = shutil.which("git")
    if binary is None:
        raise GitRepoError("git executable not found on PATH")
    return binary


def run_git(repo_path: Path, *args: str) -> str:
    """Run ``git`` at ``repo_path`` and return stripped stdout.

    No shell. Raises :class:`GitRepoError` on non-zero exit.
    """
    cmd = [_git_binary(), "-C", str(repo_path), *args]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitRepoError(f"git command timed out: {' '.join(args)}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise GitRepoError(f"git {args[0] if args else ''} failed: {stderr}")
    return completed.stdout.strip()


def assert_is_git_repo(repo_path: Path) -> None:
    """Raise :class:`GitRepoError` if ``repo_path`` is not a git work tree."""
    output = run_git(repo_path, "rev-parse", "--is-inside-work-tree")
    if output != "true":
        raise GitRepoError(f"{repo_path} is not a git work tree")


def resolve_revision(repo_path: Path, revision: str) -> str:
    """Resolve ``revision`` (e.g. ``HEAD``, ``origin/main``) to a full SHA."""
    return run_git(repo_path, "rev-parse", revision)


def inspect_repo(repo_path: Path | str, base: str = "HEAD") -> GitRepoState:
    """Collect the deterministic git facts for Pass 1.

    Parameters
    ----------
    repo_path:
        Path to a git work tree. Resolved to absolute.
    base:
        Base revision to compare ``HEAD`` against. Defaults to ``HEAD`` itself,
        which yields an empty diff — useful for smoke-testing or for inspecting
        an unmodified tree.
    """
    path = Path(repo_path).resolve()
    if not path.is_dir():
        raise GitRepoError(f"{path} is not a directory")
    assert_is_git_repo(path)
    revision = resolve_revision(path, "HEAD")
    base_revision = resolve_revision(path, base)
    return GitRepoState(path=path, revision=revision, base_revision=base_revision)


__all__ = [
    "GitRepoError",
    "GitRepoState",
    "assert_is_git_repo",
    "inspect_repo",
    "resolve_revision",
    "run_git",
]
