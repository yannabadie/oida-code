"""Phase 6.1'a-pre (ADR-53, QA/A44) — calibration seed corpus indexer.

Manual-invocation script. NOT in CI. NOT in the runtime path of
``oida-code``. Reads PAT_GITHUB if set; falls back to
unauthenticated public API (rate-limited) if not.

Per QA/A44 §"Frontière manual-vs-runtime" rule 4: refuses to run
without ``--manual-egress-ok`` AND ``--public-only`` flags.
``--dry-run`` is the default. Per ADR-53 §"Outcome": the first
version is metadata-only — no raw diff, no raw source, no provider
call, no HF call.

Usage::

    # Dry-run (default — no network call)
    python scripts/build_calibration_seed_index.py --repo pallets/click --max-prs 5

    # Real collection (operator-confirmed)
    export PAT_GITHUB=<your_pat>
    python scripts/build_calibration_seed_index.py \\
        --repo pallets/click \\
        --max-prs 5 \\
        --manual-egress-ok \\
        --public-only \\
        --output reports/calibration_seed/index.json

The script never modifies any target repo, never pushes, never
opens issues, and never calls a provider. Output is JSON
manifest-only under ``reports/calibration_seed/``.

Per ADR-53 the script carries a module-level ``MANUAL_EGRESS_SCRIPT
= True`` marker. The structural test
``test_no_manual_egress_marker_in_src`` enforces that no module
under ``src/oida_code/`` ever sets this marker.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Module-level marker — see ADR-53. Tests under
# tests/test_phase6_1_manual_data_lane_isolation.py enforce that
# this marker NEVER appears in src/oida_code/.
MANUAL_EGRESS_SCRIPT = True

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_VERSION = "phase6_1_a_pre_v1"
_GITHUB_API = "https://api.github.com"

_VALID_EXCLUSION_REASONS: frozenset[str] = frozenset(
    {
        "private_repo_refused",
        "pr_too_large",
        "pr_too_trivial",
        "non_python_change",
        "archived_repo",
        "flaky_test_suspected",
        "dependency_failure",
        "claim_too_vague",
        "fork_pr_refused",
        "licence_unclear",
        "secret_observed",
        "other",
    },
)


@dataclass(frozen=True)
class CollectionConfig:
    """Resolved configuration for a single collection run."""

    repo: str
    max_prs: int
    output_path: Path
    exclusions_path: Path
    manual_egress_ok: bool
    public_only: bool
    dry_run: bool
    pr_state: str  # "all" | "merged" | "closed" | "open"
    max_files_per_pr: int
    max_lines_per_pr: int


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str) -> str:
    """Slugify a repo name for use in case_id."""
    return s.replace("/", "_").replace("-", "_").lower()


def _github_get(url: str, pat: str | None) -> Any:
    """One unauthenticated-or-authenticated GET to the GitHub REST API.

    Returns the parsed JSON. Raises RuntimeError on HTTP errors with
    enough context to record an exclusion.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "oida-code-calibration-seed-indexer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if pat:
        headers["Authorization"] = f"Bearer {pat}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            err_body = "<no body>"
        raise RuntimeError(
            f"GitHub HTTP {exc.code}: {err_body[:300]}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub URL error: {exc}") from exc


def _check_repo_visibility(
    repo: str, pat: str | None,
) -> tuple[str, bool]:
    """Return ``(visibility, is_archived)`` for ``repo`` (e.g.
    ``"pallets/click"``). Raises RuntimeError on unreachable repos.
    """
    data = _github_get(f"{_GITHUB_API}/repos/{repo}", pat)
    visibility = str(data.get("visibility") or "unknown")
    is_archived = bool(data.get("archived", False))
    return visibility, is_archived


def _list_prs(
    repo: str, pat: str | None, max_prs: int, state: str,
) -> list[dict[str, Any]]:
    """List up to ``max_prs`` PRs of repo in the given state."""
    state_param = "closed" if state in ("merged", "closed") else state
    url = (
        f"{_GITHUB_API}/repos/{repo}/pulls"
        f"?state={state_param}&per_page={min(max_prs, 100)}&sort=updated"
        f"&direction=desc"
    )
    data = _github_get(url, pat)
    if not isinstance(data, list):
        raise RuntimeError(
            f"GitHub /pulls returned non-array: {type(data).__name__}",
        )
    if state == "merged":
        data = [pr for pr in data if pr.get("merged_at")]
    return data[:max_prs]


def _list_pr_files(
    repo: str, pr_number: int, pat: str | None,
) -> list[dict[str, Any]]:
    url = (
        f"{_GITHUB_API}/repos/{repo}/pulls/{pr_number}/files?per_page=100"
    )
    data = _github_get(url, pat)
    if not isinstance(data, list):
        raise RuntimeError(
            f"GitHub /pulls/{pr_number}/files returned non-array",
        )
    return data


def _classify_pr(
    pr: dict[str, Any], files: list[dict[str, Any]], cfg: CollectionConfig,
) -> tuple[bool, str | None]:
    """Return ``(include, exclusion_reason_or_None)``.

    Applies the structural exclusion rules: too-large, too-trivial,
    non-Python, fork PR. Operator-driven reasons (claim_too_vague,
    flaky_test_suspected, etc.) are NOT applied here — those require
    human review and are handled in a later manual triage step.
    """
    if pr.get("head", {}).get("repo", {}).get("fork", False):
        return False, "fork_pr_refused"
    file_count = len(files)
    if file_count > cfg.max_files_per_pr:
        return False, "pr_too_large"
    total_lines = sum(int(f.get("changes", 0)) for f in files)
    if total_lines > cfg.max_lines_per_pr:
        return False, "pr_too_large"
    if total_lines < 3 and file_count <= 1:
        return False, "pr_too_trivial"
    py_files = [
        f for f in files
        if str(f.get("filename", "")).endswith(".py")
    ]
    if not py_files:
        return False, "non_python_change"
    return True, None


def _build_inclusion_record(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    cfg: CollectionConfig,
    seq: int,
) -> dict[str, Any]:
    pr_number = int(pr["number"])
    repo_slug = _slug(cfg.repo)
    case_id = f"seed_{seq:03d}_{repo_slug}_{pr_number}"
    merge_status = "merged" if pr.get("merged_at") else (
        "closed" if pr.get("closed_at") else "open"
    )
    return {
        "case_id": case_id,
        "repo_url": f"https://github.com/{cfg.repo}",
        "pr_number": pr_number,
        "title": str(pr.get("title", ""))[:200],
        "base_sha": str(pr.get("base", {}).get("sha", "")),
        "head_sha": str(pr.get("head", {}).get("sha", "")),
        "changed_files_list": [
            str(f.get("filename", "")) for f in files
        ],
        "labels_observed": [
            str(label.get("name", ""))
            for label in (pr.get("labels") or [])
        ],
        "merge_status": merge_status,
        "candidate_reason": (
            f"automated initial selection: {len(files)} files changed, "
            f"{sum(int(f.get('changes', 0)) for f in files)} lines, "
            f"merge_status={merge_status}; awaits manual claim assignment"
        ),
        "claim_id": None,
        "claim_type": None,
        "claim_text": None,
        "test_scope": None,
        "expected_grounding_outcome": "not_run",
        "label_source": "unknown_not_for_metrics",
        "selection_source": "manual",
        "llm_assist_used": False,
        "human_review_required": True,
        "collected_at": _now_iso(),
        "script_version": _SCRIPT_VERSION,
        "public_only": True,
    }


def _build_exclusion_record(
    pr: dict[str, Any], reason: str, notes: str | None, repo: str,
) -> dict[str, Any]:
    if reason not in _VALID_EXCLUSION_REASONS:
        raise ValueError(
            f"unknown exclusion_reason {reason!r}; allowed: "
            f"{sorted(_VALID_EXCLUSION_REASONS)}",
        )
    return {
        "repo_url": f"https://github.com/{repo}",
        "pr_number": int(pr["number"]),
        "exclusion_reason": reason,
        "notes": notes,
        "collected_at": _now_iso(),
        "script_version": _SCRIPT_VERSION,
    }


def _load_existing_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"existing file {path} is not valid JSON: {exc}",
        ) from exc
    if not isinstance(data, list):
        raise RuntimeError(
            f"existing file {path} top-level is not a JSON array",
        )
    return data


def _save_json_array(
    path: Path, records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _merge_records(
    existing: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Idempotent merge: existing records are preserved; new records
    are added if their key tuple is not already present.
    """
    seen = {tuple(r.get(k) for k in key_fields) for r in existing}
    out = list(existing)
    for r in new_records:
        k = tuple(r.get(field) for field in key_fields)
        if k not in seen:
            out.append(r)
            seen.add(k)
    return out


def _print_dry_run_plan(cfg: CollectionConfig) -> None:
    """Print what the script would do. No network call."""
    print(f"calibration seed indexer — DRY-RUN ({_SCRIPT_VERSION})")
    print(f"  repo: {cfg.repo}")
    print(f"  max_prs: {cfg.max_prs}")
    print(f"  pr_state: {cfg.pr_state}")
    print(f"  max_files_per_pr: {cfg.max_files_per_pr}")
    print(f"  max_lines_per_pr: {cfg.max_lines_per_pr}")
    print(f"  output: {cfg.output_path}")
    print(f"  exclusions: {cfg.exclusions_path}")
    print(f"  manual_egress_ok: {cfg.manual_egress_ok}")
    print(f"  public_only: {cfg.public_only}")
    print()
    print("In real-collection mode, this run would:")
    print(f"  1. Verify {cfg.repo} is public (refuse if not).")
    print(f"  2. Fetch up to {cfg.max_prs} PRs from {cfg.repo}.")
    print("  3. For each PR, fetch its file list via the API.")
    print("  4. Apply structural exclusion rules (size, language, fork).")
    print("  5. Emit metadata-only inclusion / exclusion records.")
    print()
    print("Re-run with `--manual-egress-ok --public-only` to actually collect.")


def _resolve_config(args: argparse.Namespace) -> CollectionConfig:
    return CollectionConfig(
        repo=args.repo,
        max_prs=args.max_prs,
        output_path=args.output,
        exclusions_path=args.exclusions,
        manual_egress_ok=args.manual_egress_ok,
        public_only=args.public_only,
        dry_run=args.dry_run,
        pr_state=args.pr_state,
        max_files_per_pr=args.max_files_per_pr,
        max_lines_per_pr=args.max_lines_per_pr,
    )


def _real_collection(cfg: CollectionConfig) -> int:
    pat = os.environ.get("PAT_GITHUB")
    if not pat:
        print(
            "warning: PAT_GITHUB not set; falling back to "
            "unauthenticated GitHub API (low rate-limit)",
            file=sys.stderr,
        )

    visibility, is_archived = _check_repo_visibility(cfg.repo, pat)
    if visibility != "public":
        print(
            f"refusing: repo {cfg.repo} visibility={visibility!r} "
            f"(must be 'public')",
            file=sys.stderr,
        )
        return 2
    if is_archived:
        print(
            f"warning: repo {cfg.repo} is archived; recording all PRs "
            f"as exclusion archived_repo",
            file=sys.stderr,
        )

    prs = _list_prs(cfg.repo, pat, cfg.max_prs, cfg.pr_state)
    print(f"fetched {len(prs)} PRs from {cfg.repo}")

    inclusions: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    existing_inclusions = _load_existing_json_array(cfg.output_path)
    existing_exclusions = _load_existing_json_array(cfg.exclusions_path)
    seq_start = 1 + max(
        (
            int(r["case_id"].split("_")[1])
            for r in existing_inclusions
            if str(r.get("case_id", "")).startswith("seed_")
            and r["case_id"].split("_")[1].isdigit()
        ),
        default=0,
    )

    for offset, pr in enumerate(prs):
        if is_archived:
            exclusions.append(
                _build_exclusion_record(
                    pr, "archived_repo", "repo flagged archived", cfg.repo,
                ),
            )
            continue
        try:
            files = _list_pr_files(cfg.repo, int(pr["number"]), pat)
        except RuntimeError as exc:
            exclusions.append(
                _build_exclusion_record(
                    pr,
                    "other",
                    f"file listing failed: {exc}",
                    cfg.repo,
                ),
            )
            continue
        include, reason = _classify_pr(pr, files, cfg)
        if include:
            inclusions.append(
                _build_inclusion_record(pr, files, cfg, seq_start + offset),
            )
        else:
            exclusions.append(
                _build_exclusion_record(
                    pr, reason or "other", None, cfg.repo,
                ),
            )

    merged_inclusions = _merge_records(
        existing_inclusions, inclusions, ("repo_url", "pr_number"),
    )
    merged_exclusions = _merge_records(
        existing_exclusions, exclusions, ("repo_url", "pr_number"),
    )
    merged_inclusions.sort(key=lambda r: str(r.get("case_id", "")))
    merged_exclusions.sort(
        key=lambda r: (
            str(r.get("repo_url", "")), int(r.get("pr_number", 0)),
        ),
    )
    _save_json_array(cfg.output_path, merged_inclusions)
    _save_json_array(cfg.exclusions_path, merged_exclusions)
    print(
        f"wrote {len(inclusions)} new inclusions "
        f"(total {len(merged_inclusions)}) -> {cfg.output_path}",
    )
    print(
        f"wrote {len(exclusions)} new exclusions "
        f"(total {len(merged_exclusions)}) -> {cfg.exclusions_path}",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Manual data acquisition: build a calibration seed corpus "
            "of public Python PRs for Phase 6.1' bundle authoring "
            "stress-test. NOT in CI. NOT in the runtime path. Per "
            "ADR-53 / QA/A44 §'Frontière manual-vs-runtime'."
        ),
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help='Public GitHub repo, e.g. "pallets/click".',
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=5,
        help="Maximum number of PRs to fetch (default: 5).",
    )
    parser.add_argument(
        "--pr-state",
        type=str,
        default="merged",
        choices=("merged", "closed", "open", "all"),
        help="PR state filter (default: merged).",
    )
    parser.add_argument(
        "--max-files-per-pr",
        type=int,
        default=30,
        help="Reject PRs touching more files than this.",
    )
    parser.add_argument(
        "--max-lines-per-pr",
        type=int,
        default=1000,
        help="Reject PRs with more changed lines than this.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "reports" / "calibration_seed" / "index.json",
        help="Inclusions output path.",
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=_REPO_ROOT / "reports" / "calibration_seed" / "exclusions.json",
        help="Exclusions output path.",
    )
    parser.add_argument(
        "--manual-egress-ok",
        action="store_true",
        default=False,
        help="Required to leave dry-run mode (frontière rule 4).",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        default=False,
        help=(
            "Required acknowledgement that this script is public-only "
            "and refuses any private repo (per QA/A44 §'Calibration "
            "dataset boundaries')."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Force dry-run mode (no network call). Default is True "
            "unless --manual-egress-ok and --public-only are both set."
        ),
    )
    args = parser.parse_args()
    cfg = _resolve_config(args)

    # Default mode = dry-run. Without --manual-egress-ok the script
    # never makes a network call; it prints the plan and exits 0.
    if not args.manual_egress_ok:
        _print_dry_run_plan(cfg)
        return 0

    # --manual-egress-ok is set. We need --public-only too, otherwise
    # refuse with a clear message and exit 2 (per ADR-53 frontière
    # rule 4 + QA/A44 §"Calibration dataset boundaries").
    if not args.public_only:
        print(
            "refusing: --manual-egress-ok requires --public-only "
            "to leave dry-run mode (per ADR-53 frontière rule 4 + "
            "QA/A44 §'Calibration dataset boundaries').",
            file=sys.stderr,
        )
        print(file=sys.stderr)
        _print_dry_run_plan(cfg)
        return 2

    # Both safety flags are set. If --dry-run is also set, still
    # dry-run (operator override). Otherwise, real collection.
    if args.dry_run:
        _print_dry_run_plan(cfg)
        return 0

    return _real_collection(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
