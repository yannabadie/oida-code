"""E2 (QA/A13.md, ADR-23) — real-repo shadow smoke.

Runs the experimental shadow fusion (E1/E1.1) against:

* ``oida-code`` self
* ``attrs`` (``.oida/validation-external/attrs/``) — already cloned
* optional third repo via ``--extra``

For each target we record **structural** properties only:

* shadow fusion runs without crashing
* official summary fields stay null (we never call the vendored fuse path)
* ShadowFusionReport's payload carries no ``total_v_net`` / ``debt_final``
  / ``corrupt_success_*`` keys
* graph_summary surfaces propagation_iterations + converged
* warnings list (missing grounding count, "no graph edges" if applicable)
* max debt/integrity pressure on the scenario
* ``readiness_status == "blocked"`` because v0.4.x runs default
  capability/benefit/observability — by ADR-22 we MUST stay blocked

This is **NOT** a statistical validation. There is no Spearman, no
correlation, no outcome label. The shadow report's authoritative bit
remains ``False`` regardless of repo.

Usage:

    python scripts/real_repo_shadow_smoke.py
    python scripts/real_repo_shadow_smoke.py --extra path/to/repo
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from oida_code.extract.dependencies import derive_audit_surface
from oida_code.extract.obligations import extract_obligations
from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.score.experimental_shadow_fusion import (
    compute_experimental_shadow_fusion,
)
from oida_code.score.fusion_readiness import assess_fusion_readiness
from oida_code.score.mapper import build_scoring_inputs


@dataclass
class ShadowSmokeResult:
    name: str
    path: str
    obligations_count: int
    constitutive_edges: int
    supportive_edges: int
    n_events: int
    propagation_iterations: int
    propagation_converged: bool
    max_base_pressure: float
    max_shadow_debt_pressure: float
    max_shadow_integrity_pressure: float
    missing_grounding_count: int
    no_graph_edges_warning: bool
    has_forbidden_summary_keys: bool
    readiness_status: str
    shadow_status: str
    authoritative: bool
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


_FORBIDDEN_KEYS = {
    "total_v_net",
    "debt_final",
    "corrupt_success",
    "corrupt_success_ratio",
    "corrupt_success_verdict",
    "mean_q_obs",
    "mean_lambda_bias",
}


def _git_changed_files(repo: Path, n_commits: int = 5) -> list[str]:
    try:
        proc = subprocess.run(
            [
                "git", "-C", str(repo), "diff", "--name-only",
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


def _sample_repo_python_files(repo: Path, max_files: int = 12) -> list[str]:
    """Fallback when git history is too shallow (e.g. snapshot clones):
    sample a few ``.py`` files under ``src/`` (or the repo root if no
    src/) so the shadow smoke has something non-trivial to chew on."""
    candidates = sorted(
        p for p in (repo / "src").rglob("*.py")
        if "__pycache__" not in p.parts
    ) if (repo / "src").is_dir() else sorted(
        p for p in repo.rglob("*.py")
        if "__pycache__" not in p.parts
    )
    out: list[str] = []
    for p in candidates[:max_files]:
        try:
            rel = p.relative_to(repo)
        except ValueError:
            continue
        out.append(str(rel).replace("\\", "/"))
    return out


def _smoke_one(name: str, repo: Path, *, n_commits: int = 5) -> ShadowSmokeResult:
    try:
        changed = _git_changed_files(repo, n_commits=n_commits)
        if not changed:
            # Snapshot clones / shallow histories: sample real source so
            # the smoke isn't trivially empty.
            changed = _sample_repo_python_files(repo)
        surface = derive_audit_surface(repo, changed, mode="impact", max_files=50)
        obligations = extract_obligations(repo, surface)
        request = AuditRequest(
            repo=RepoSpec(
                path=str(repo), revision="HEAD", base_revision="HEAD^",
            ),
            scope=ScopeSpec(changed_files=surface, language="python"),
        )
        # E3.0 (ADR-24) — single pass: scenario + dependency graph
        # + per-event evidence view + edge_confidences.
        inputs = build_scoring_inputs(obligations, request=request)
        scenario = inputs.scenario
        graph = inputs.graph
        readiness = assess_fusion_readiness(scenario)
        shadow = compute_experimental_shadow_fusion(
            scenario, readiness,
            edge_confidences=inputs.edge_confidences,
        )
    except Exception as exc:  # defensive: report and move on
        return ShadowSmokeResult(
            name=name,
            path=str(repo),
            obligations_count=0,
            constitutive_edges=0,
            supportive_edges=0,
            n_events=0,
            propagation_iterations=0,
            propagation_converged=False,
            max_base_pressure=0.0,
            max_shadow_debt_pressure=0.0,
            max_shadow_integrity_pressure=0.0,
            missing_grounding_count=0,
            no_graph_edges_warning=False,
            has_forbidden_summary_keys=False,
            readiness_status="error",
            shadow_status="error",
            authoritative=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    payload = shadow.model_dump()
    forbidden = bool(_FORBIDDEN_KEYS & set(payload.keys()))
    missing = [
        w for w in shadow.warnings
        if "missing grounding model" in w.lower()
    ]
    no_edges = any(
        "no graph edges" in w.lower() for w in shadow.warnings
    )
    base_max = max(
        (s.base_pressure for s in shadow.event_scores), default=0.0,
    )
    debt_max = max(
        (s.shadow_debt_pressure for s in shadow.event_scores), default=0.0,
    )
    int_max = max(
        (s.shadow_integrity_pressure for s in shadow.event_scores), default=0.0,
    )
    # Extract per-event missing count from the warning if present.
    missing_count = 0
    for w in missing:
        # Format: "missing grounding model on N event(s); ..."
        head = w.split("on ", 1)[1] if "on " in w else ""
        try:
            missing_count = int(head.split(" ", 1)[0])
        except (IndexError, ValueError):
            missing_count = 0

    return ShadowSmokeResult(
        name=name,
        path=str(repo),
        obligations_count=len(obligations),
        constitutive_edges=len(graph.constitutive_edges),
        supportive_edges=len(graph.supportive_edges),
        n_events=len(scenario.events),
        propagation_iterations=shadow.graph_summary.propagation_iterations,
        propagation_converged=shadow.graph_summary.propagation_converged,
        max_base_pressure=round(base_max, 6),
        max_shadow_debt_pressure=round(debt_max, 6),
        max_shadow_integrity_pressure=round(int_max, 6),
        missing_grounding_count=missing_count,
        no_graph_edges_warning=no_edges,
        has_forbidden_summary_keys=forbidden,
        readiness_status=shadow.readiness_status,
        shadow_status=shadow.status,
        authoritative=shadow.authoritative,
        warnings=list(shadow.warnings),
    )


def _print_table(rows: list[ShadowSmokeResult]) -> None:
    header = (
        f"{'name':<20} {'obs':>4} {'con':>4} {'sup':>4} "
        f"{'iter':>4} {'conv':>5} "
        f"{'base':>7} {'debt':>7} {'integ':>7} "
        f"{'miss':>4} {'no_edge':>7} {'forbid':>6} "
        f"{'auth':>4} {'rdy':>10}"
    )
    print(f"\n{header}")
    print("-" * len(header))
    for r in rows:
        print(
            f"{r.name:<20} {r.obligations_count:>4} "
            f"{r.constitutive_edges:>4} {r.supportive_edges:>4} "
            f"{r.propagation_iterations:>4} "
            f"{'Y' if r.propagation_converged else 'N':>5} "
            f"{r.max_base_pressure:>7.4f} {r.max_shadow_debt_pressure:>7.4f} "
            f"{r.max_shadow_integrity_pressure:>7.4f} "
            f"{r.missing_grounding_count:>4} "
            f"{'Y' if r.no_graph_edges_warning else 'N':>7} "
            f"{'Y' if r.has_forbidden_summary_keys else 'N':>6} "
            f"{'Y' if r.authoritative else 'N':>4} "
            f"{r.readiness_status:>10}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra", type=Path, default=None)
    parser.add_argument("--n-commits", type=int, default=5)
    parser.add_argument(
        "--out", type=Path,
        default=Path(".oida/e2/shadow_smoke.json"),
    )
    args = parser.parse_args()

    targets: list[tuple[str, Path]] = [("oida-code (self)", Path("."))]
    attrs_path = Path(".oida/validation-external/attrs")
    if attrs_path.is_dir():
        targets.append(("attrs", attrs_path))
    if args.extra is not None and args.extra.is_dir():
        targets.append((args.extra.name, args.extra))

    results: list[ShadowSmokeResult] = []
    for name, path in targets:
        print(f"[shadow-smoke] {name} @ {path}", file=sys.stderr)
        results.append(_smoke_one(name, path, n_commits=args.n_commits))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps([r.__dict__ for r in results], indent=2), encoding="utf-8",
    )
    _print_table(results)

    # E2 acceptance: shadow runs, no forbidden keys, never authoritative.
    all_ok = all(
        r.error is None
        and not r.has_forbidden_summary_keys
        and not r.authoritative
        for r in results
    )
    print()
    print(
        f"E2 shadow-smoke invariants: "
        f"{'PASS' if all_ok else 'FAIL'}"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
