"""Block D3 (QA/A9.md) — structural smoke on real repos.

Runs ``normalize`` on each target repo and records structural
properties — **no Spearman, no correlation, no outcome prediction**
(A9.md §D3 constraint: "Block D validates structural measurement, not
statistical outcome prediction").

Targets (in order):

1. ``oida-code`` self (``.``)                — the current repo
2. ``attrs`` (``.oida/validation-external/attrs/``) — already cloned
3. optional third small Python repo if a path is passed via --extra

For each target we collect:

* does ``normalize`` exit 0?
* impact surface size + whether it strictly extends the raw diff
* obligation count
* graph edge counts (constitutive / supportive)
* any unknown parent ID? (would fail the vendored analyzer's _validate_ids)
* any self-edge?
* ``double_loop_repair`` demonstration on a chosen root

Output: ``.oida/block_d/real_repo_smoke.json`` (machine) +
markdown snippet embedded in ``reports/block_d_validation.md`` (human).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer
from oida_code.extract.dependencies import (
    build_dependency_graph,
    derive_audit_surface,
)
from oida_code.extract.obligations import extract_obligations
from oida_code.score.mapper import obligations_to_scenario, pydantic_to_vendored


@dataclass
class SmokeResult:
    name: str
    path: str
    normalize_exit_code: int
    changed_files_count: int
    impact_surface_count: int
    impact_extends_changed: bool
    obligations_count: int
    constitutive_edges: int
    supportive_edges: int
    has_unknown_parent_ids: bool
    has_self_edges: bool
    repair_reopen_count: int = 0
    repair_audit_count: int = 0
    repair_demo_root: str | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def _git_changed_files(repo: Path, n_commits: int = 5) -> list[str]:
    """Return files changed in the last ``n_commits`` commits of ``repo``."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "diff",
                "--name-only",
                f"HEAD~{n_commits}..HEAD",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip().endswith(".py")
    ][:20]


def _smoke_one(name: str, repo: Path, *, n_commits: int = 5) -> SmokeResult:
    changed = _git_changed_files(repo, n_commits=n_commits)
    surface = derive_audit_surface(repo, changed, mode="impact", max_files=50)
    impact_extends = len(surface) > len(changed)

    try:
        obligations = extract_obligations(repo, surface)
    except Exception as exc:  # defensive; extract_obligations should not raise
        return SmokeResult(
            name=name,
            path=str(repo),
            normalize_exit_code=-1,
            changed_files_count=len(changed),
            impact_surface_count=len(surface),
            impact_extends_changed=impact_extends,
            obligations_count=0,
            constitutive_edges=0,
            supportive_edges=0,
            has_unknown_parent_ids=False,
            has_self_edges=False,
            error=f"extract_obligations: {exc}",
        )

    graph = build_dependency_graph(obligations, repo, surface)

    # Build a NormalizedScenario and run the vendored analyzer to
    # validate IDs + exercise double_loop_repair.
    from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
    raw_request = AuditRequest(
        repo=RepoSpec(
            path=str(repo), revision="HEAD", base_revision="HEAD^",
        ),
        scope=ScopeSpec(changed_files=surface, language="python"),
    )
    try:
        scenario = obligations_to_scenario(obligations, request=raw_request)
    except Exception as exc:
        return SmokeResult(
            name=name,
            path=str(repo),
            normalize_exit_code=-1,
            changed_files_count=len(changed),
            impact_surface_count=len(surface),
            impact_extends_changed=impact_extends,
            obligations_count=len(obligations),
            constitutive_edges=len(graph.constitutive_edges),
            supportive_edges=len(graph.supportive_edges),
            has_unknown_parent_ids=False,
            has_self_edges=False,
            error=f"obligations_to_scenario: {exc}",
        )

    known = {ev.id for ev in scenario.events}
    has_unknown = any(
        p not in known
        for ev in scenario.events
        for p in ev.constitutive_parents + ev.supportive_parents
    )
    has_self = any(
        ev.id in ev.constitutive_parents + ev.supportive_parents
        for ev in scenario.events
    )

    reopen_count = 0
    audit_count = 0
    repair_root = None
    # Pick a root that has at least one constitutive child, if any.
    if graph.constitutive_edges and scenario.events:
        # Translate obligation IDs to event IDs.
        ob_to_ev = {
            ob.id: ev.id
            for ob, ev in zip(obligations, scenario.events, strict=False)
        }
        parent_id = graph.constitutive_edges[0].parent_id
        repair_root = ob_to_ev.get(parent_id)
        if repair_root:
            try:
                analyzer = OIDAAnalyzer(pydantic_to_vendored(scenario))
                result = analyzer.double_loop_repair(repair_root)
                reopen_count = len(result["reopen"])
                audit_count = len(result["audit"])
            except Exception as exc:  # defensive — log + continue
                return SmokeResult(
                    name=name,
                    path=str(repo),
                    normalize_exit_code=-1,
                    changed_files_count=len(changed),
                    impact_surface_count=len(surface),
                    impact_extends_changed=impact_extends,
                    obligations_count=len(obligations),
                    constitutive_edges=len(graph.constitutive_edges),
                    supportive_edges=len(graph.supportive_edges),
                    has_unknown_parent_ids=has_unknown,
                    has_self_edges=has_self,
                    error=f"double_loop_repair: {exc}",
                )

    return SmokeResult(
        name=name,
        path=str(repo),
        normalize_exit_code=0,
        changed_files_count=len(changed),
        impact_surface_count=len(surface),
        impact_extends_changed=impact_extends,
        obligations_count=len(obligations),
        constitutive_edges=len(graph.constitutive_edges),
        supportive_edges=len(graph.supportive_edges),
        has_unknown_parent_ids=has_unknown,
        has_self_edges=has_self,
        repair_reopen_count=reopen_count,
        repair_audit_count=audit_count,
        repair_demo_root=repair_root,
    )


def _print_table(rows: list[SmokeResult]) -> None:
    print(
        f"\n{'name':<20} {'changed':>7} {'surface':>7} "
        f"{'obs':>5} {'con':>4} {'sup':>4} {'reopen':>6} {'audit':>5} "
        f"{'unk':>3} {'self':>4}"
    )
    print("-" * 80)
    for r in rows:
        print(
            f"{r.name:<20} {r.changed_files_count:>7} {r.impact_surface_count:>7} "
            f"{r.obligations_count:>5} {r.constitutive_edges:>4} "
            f"{r.supportive_edges:>4} {r.repair_reopen_count:>6} "
            f"{r.repair_audit_count:>5} "
            f"{'Y' if r.has_unknown_parent_ids else 'N':>3} "
            f"{'Y' if r.has_self_edges else 'N':>4}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Block D3 real-repo structural smoke")
    parser.add_argument(
        "--extra",
        type=Path,
        default=None,
        help="Optional third repo path (Python).",
    )
    parser.add_argument(
        "--n-commits",
        type=int,
        default=5,
        help="How many recent commits to treat as the changed set (default 5).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".oida/block_d/real_repo_smoke.json"),
    )
    args = parser.parse_args()

    targets: list[tuple[str, Path]] = [("oida-code (self)", Path("."))]
    attrs_path = Path(".oida/validation-external/attrs")
    if attrs_path.is_dir():
        targets.append(("attrs", attrs_path))
    if args.extra is not None and args.extra.is_dir():
        targets.append((args.extra.name, args.extra))

    results: list[SmokeResult] = []
    for name, path in targets:
        print(f"[smoke] {name} @ {path}", file=sys.stderr)
        results.append(_smoke_one(name, path, n_commits=args.n_commits))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps([r.__dict__ for r in results], indent=2), encoding="utf-8"
    )
    _print_table(results)

    # Structural assertions (A9.md §D3 acceptance criteria).
    all_structural_ok = all(
        r.error is None
        and not r.has_unknown_parent_ids
        and not r.has_self_edges
        for r in results
    )
    print()
    print(
        f"Structural invariants: "
        f"{'PASS' if all_structural_ok else 'FAIL'}"
    )
    return 0 if all_structural_ok else 1


if __name__ == "__main__":
    sys.exit(main())
