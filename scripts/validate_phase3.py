"""Phase-3 validation run (ADR-17 + ADR-18).

Picks N real Claude Code transcripts from ~/.claude/projects/, scores
them with the Phase-3 trajectory scorer, labels each with its git-derived
outcome (success/failure/partial), and computes Spearman ρ between
log(exploration_error + eps) and outcome_success to test paper
2604.13151 Figure 1a's main finding (low exploration error → success).

Exit criterion: ρ ≤ -0.3 on ≥ 20 transcripts with usable outcome labels.

Usage:
    python scripts/validate_phase3.py [--n 20] [--out .oida/phase3_validation.json]

Bounded U(t) proxy: for each transcript we derive changed_files from the
first 15 distinct scope paths the agent touched. This is a heuristic, not
a ground-truth audit surface — documented as a Phase-3 limitation in the
report (a proper ingest would use the `inspect` snapshot captured at
session start).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import correlation

from oida_code.ingest.claude_code_trace import parse_claude_code_transcript
from oida_code.ingest.session_outcome import compute_session_outcome
from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.score.trajectory import score_trajectory

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _derive_changed_files(trace_events: list, limit: int = 15) -> list[str]:
    """First N distinct scope paths as the bounded U(t) surface."""
    seen: list[str] = []
    for ev in trace_events:
        for p in ev.scope:
            if p and p not in seen:
                seen.append(p)
                if len(seen) >= limit:
                    return seen
    return seen


def _project_repo_path(transcript: Path) -> Path | None:
    """Extract ``cwd`` from the transcript's first records — the real repo path.

    Claude Code writes ``{"cwd": "C:\\\\Code\\\\Unslop.ai", ...}`` in
    every assistant/user record, so we read the first one that has the
    field. Avoids fragile slug-decoding (``C--Code-Unslop-ai`` → ???).
    """
    try:
        with transcript.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                cwd = rec.get("cwd") if isinstance(rec, dict) else None
                if isinstance(cwd, str) and cwd.strip():
                    p = Path(cwd)
                    if p.is_dir():
                        return p
                    return None
    except OSError:
        return None
    return None


def collect_transcripts(n: int) -> list[tuple[Path, Path]]:
    """Return up to ``n`` (transcript, repo_path) pairs, one per project
    first so the sample spans as many repos as possible."""
    pairs: list[tuple[Path, Path]] = []
    by_project: dict[str, list[Path]] = {}
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        transcripts = sorted(project_dir.glob("*.jsonl"))
        if transcripts:
            by_project[project_dir.name] = transcripts

    # Round-robin: first transcript from each project, then second, etc.
    # This oversamples diverse projects over multi-session single projects.
    max_depth = max((len(v) for v in by_project.values()), default=0)
    for depth in range(max_depth):
        for project_name in sorted(by_project):
            transcripts = by_project[project_name]
            if depth >= len(transcripts):
                continue
            transcript = transcripts[depth]
            repo_path = _project_repo_path(transcript)
            if repo_path is None:
                continue
            pairs.append((transcript, repo_path))
            if len(pairs) >= n:
                return pairs
    return pairs


def score_one(transcript: Path, repo: Path) -> dict:
    trace = parse_claude_code_transcript(transcript)
    if not trace.events:
        return {"transcript": str(transcript), "skipped": "empty trace"}
    changed = _derive_changed_files(trace.events)
    req = AuditRequest(
        repo=RepoSpec(path=str(repo), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=changed),
    )
    metrics = score_trajectory(trace, obligations=[], request=req)
    outcome = compute_session_outcome(transcript, repo)
    return {
        "transcript": str(transcript),
        "repo": str(repo),
        "total_steps": metrics.total_steps,
        "exploration_error": metrics.exploration_error,
        "exploitation_error": metrics.exploitation_error,
        "stale_score": metrics.stale_score,
        "no_progress_rate": metrics.no_progress_rate,
        "progress_events": metrics.progress_events_count,
        "outcome": outcome.outcome,
        "commits_in_window": outcome.commits_in_window,
        "reachable_from_head": outcome.reachable_from_head,
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    try:
        return correlation(xs, ys, method="ranked")
    except (ValueError, ZeroDivisionError):
        return None


def compute_spearman(results: list[dict], min_steps: int = 50) -> dict:
    """Compute the Phase-3 validation correlations.

    We report four rhos:

    * ``rho_exploration`` / ``rho_exploitation`` — paper's raw metrics on
      log-scale against outcome. Included for reproducibility; length
      confound makes them unreliable without further normalization.
    * ``rho_progress_rate`` — ``progress_events / total_steps``, the
      length-normalized analogue. **Primary gate signal** per
      PHASE3_AUDIT_REPORT §7.
    * ``rho_no_progress_rate`` — direct no-progress fraction.

    Filtering: sessions shorter than ``min_steps`` are dropped because
    the scorer's Case assignment is dominated by noise on short traces.
    """
    usable = [
        r
        for r in results
        if "exploration_error" in r
        and r.get("outcome") in ("success", "failure", "partial")
        and r["total_steps"] >= min_steps
    ]
    if len(usable) < 3:
        return {
            "n": len(usable),
            "min_steps_filter": min_steps,
            "rho_exploration": None,
            "rho_exploitation": None,
            "rho_progress_rate": None,
            "rho_no_progress_rate": None,
        }

    eps = 1e-6
    log_expl = [math.log(r["exploration_error"] + eps) for r in usable]
    log_expt = [math.log(r["exploitation_error"] + eps) for r in usable]
    progress_rate = [
        r["progress_events"] / max(r["total_steps"], 1) for r in usable
    ]
    np_rate = [r["no_progress_rate"] for r in usable]
    outcome_score = [
        {"success": 1.0, "partial": 0.5, "failure": 0.0}[r["outcome"]]
        for r in usable
    ]

    return {
        "n": len(usable),
        "min_steps_filter": min_steps,
        "rho_exploration": _spearman(log_expl, outcome_score),
        "rho_exploitation": _spearman(log_expt, outcome_score),
        "rho_progress_rate": _spearman(progress_rate, outcome_score),
        "rho_no_progress_rate": _spearman(np_rate, outcome_score),
        "outcome_counts": {
            "success": sum(1 for r in usable if r["outcome"] == "success"),
            "partial": sum(1 for r in usable if r["outcome"] == "partial"),
            "failure": sum(1 for r in usable if r["outcome"] == "failure"),
        },
    }


def main() -> int:
    n = 20
    out_path = Path(".oida/phase3_validation.json")
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--n":
            n = int(args[i + 1])
            i += 2
        elif args[i] == "--out":
            out_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    pairs = collect_transcripts(n)
    print(f"collected {len(pairs)} transcripts", file=sys.stderr)

    results: list[dict] = []
    for j, (transcript, repo) in enumerate(pairs, 1):
        print(f"[{j}/{len(pairs)}] {transcript.name} @ {repo.name}", file=sys.stderr)
        try:
            row = score_one(transcript, repo)
        except Exception as e:  # noqa: BLE001 — collect failures, keep going
            row = {"transcript": str(transcript), "error": str(e)}
        results.append(row)

    stats = compute_spearman(results)
    summary = {
        "config": {"n_requested": n, "n_collected": len(pairs)},
        "spearman": stats,
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)

    # Console summary
    print("\n=== Phase 3 validation ===")
    print(f"n = {stats['n']} (after min_steps={stats.get('min_steps_filter')} filter)")
    print(f"rho(log exploration_error, outcome)  = {stats['rho_exploration']}")
    print(f"rho(log exploitation_error, outcome) = {stats['rho_exploitation']}")
    print(f"rho(progress_rate, outcome)          = {stats['rho_progress_rate']} <-- PRIMARY GATE")
    print(f"rho(no_progress_rate, outcome)       = {stats['rho_no_progress_rate']}")
    print(f"outcome counts: {stats.get('outcome_counts')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
