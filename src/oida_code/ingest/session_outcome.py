"""Compute an outcome label for a Claude Code session from git state.

Phase-3 validation needs an **independent** signal to correlate
trajectory scores against — otherwise measuring rho (Spearman) between
LLM labels and LLM-scored formulas is circular (advisor stress-test
2026-04-24).

Outcome signal: "did the session produce tangible forward progress in
the repo?" Derived from git, not from the trace itself:

* ``success``  — at least one commit authored during the session window,
  reachable from HEAD (i.e. not rebased away).
* ``failure``  — no commits during the session window; working tree may
  still be dirty, but nothing was captured.
* ``partial``  — commits exist but are not reachable from HEAD (e.g.
  rebased, dropped, abandoned branch).

The session window is extracted from the transcript's first and last
timestamps. Timestamps are ISO 8601 strings in the JSONL records.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Outcome = Literal["success", "failure", "partial", "unknown"]


@dataclass(frozen=True, slots=True)
class SessionOutcome:
    outcome: Outcome
    commits_in_window: int
    reachable_from_head: int
    start_ts: datetime | None
    end_ts: datetime | None


def _transcript_window(path: Path) -> tuple[datetime | None, datetime | None]:
    """Return (first_ts, last_ts) from a Claude Code JSONL transcript."""
    first: datetime | None = None
    last: datetime | None = None
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ts_str = rec.get("timestamp") if isinstance(rec, dict) else None
            if not isinstance(ts_str, str):
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if first is None or ts < first:
                first = ts
            if last is None or ts > last:
                last = ts
    return first, last


def _git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _commits_in_window(
    repo: Path, start: datetime, end: datetime, *, reachable_from_head: bool = False
) -> list[str]:
    args = [
        "log",
        "--pretty=%H",
        f"--since={start.isoformat()}",
        f"--until={end.isoformat()}",
    ]
    if reachable_from_head:
        args.append("HEAD")
    else:
        args.append("--all")
    out = _git(repo, *args)
    return [line.strip() for line in out.splitlines() if line.strip()]


def compute_session_outcome(
    transcript: Path | str, repo: Path | str
) -> SessionOutcome:
    """Compute :class:`SessionOutcome` for one transcript in ``repo``.

    When the repo path is not a git work tree or the transcript has no
    timestamps, returns ``outcome="unknown"`` with zeroed counts.
    """
    transcript_path = Path(transcript)
    repo_path = Path(repo)

    start, end = _transcript_window(transcript_path)
    if start is None or end is None:
        return SessionOutcome(
            outcome="unknown",
            commits_in_window=0,
            reachable_from_head=0,
            start_ts=start,
            end_ts=end,
        )

    is_repo = _git(repo_path, "rev-parse", "--is-inside-work-tree").strip()
    if is_repo != "true":
        return SessionOutcome(
            outcome="unknown",
            commits_in_window=0,
            reachable_from_head=0,
            start_ts=start,
            end_ts=end,
        )

    all_in_window = _commits_in_window(repo_path, start, end, reachable_from_head=False)
    reachable = _commits_in_window(repo_path, start, end, reachable_from_head=True)

    if not all_in_window:
        outcome: Outcome = "failure"
    elif reachable:
        outcome = "success"
    else:
        outcome = "partial"

    return SessionOutcome(
        outcome=outcome,
        commits_in_window=len(all_in_window),
        reachable_from_head=len(reachable),
        start_ts=start,
        end_ts=end,
    )


__all__ = ["Outcome", "SessionOutcome", "compute_session_outcome"]
