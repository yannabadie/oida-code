"""``oida-code`` CLI entry point (blueprint §8 + PLAN.md §11).

Subcommand status after Phase 1:

* ``inspect``   — Phase 0 (shipped).
* ``verify``    — Phase 1 deterministic path.
* ``audit``     — Phase 1 deterministic path (inspect → verify → report).
* ``normalize`` — Phase 2 (NotImplementedError — needs obligation graph).
* ``repair``    — Phase 3+ (NotImplementedError).
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from oida_code import __version__
from oida_code.extract.dependencies import derive_audit_surface
from oida_code.extract.obligations import extract_obligations
from oida_code.ingest.claude_code_trace import parse_claude_code_transcript
from oida_code.ingest.diff_parser import changed_files
from oida_code.ingest.git_repo import GitRepoError, inspect_repo
from oida_code.ingest.manifest import detect_commands
from oida_code.ingest.session_outcome import compute_session_outcome
from oida_code.models.audit_report import (
    AuditReport,
    RepairPlan,
    ReportSummary,
)
from oida_code.models.audit_request import (
    AuditRequest,
    IntentSpec,
    PolicySpec,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.evidence import ToolBudgets, ToolEvidence
from oida_code.report.json_report import write_json_report
from oida_code.report.markdown_report import write_markdown_report
from oida_code.report.sarif_export import export_sarif
from oida_code.score.mapper import obligations_to_scenario
from oida_code.score.trajectory import score_trajectory
from oida_code.score.verdict import VerdictResolution, resolve_verdict
from oida_code.verify.codeql_scan import run_codeql
from oida_code.verify.hypothesis_runner import run_hypothesis
from oida_code.verify.lint import run_lint
from oida_code.verify.mutmut_runner import run_mutmut
from oida_code.verify.pytest_runner import run_pytest
from oida_code.verify.semgrep_scan import run_semgrep
from oida_code.verify.typing import run_type_check


class OutputFormat(StrEnum):
    json = "json"
    sarif = "sarif"
    markdown = "markdown"


class FailOn(StrEnum):
    any_critical = "any_critical"
    corrupt = "corrupt"
    none = "none"


app = typer.Typer(
    name="oida-code",
    help="AI code verifier — measure the gap between apparent and guaranteed behavior.",
    no_args_is_help=True,
    add_completion=False,
)


def _fail(msg: str, code: int = 2) -> NoReturn:
    typer.echo(f"oida-code: {msg}", err=True)
    raise typer.Exit(code=code)


def _read_intent(path: Path | None) -> IntentSpec:
    if path is None:
        return IntentSpec()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fail(f"cannot read --intent file: {exc}")
    summary = content.strip().splitlines()[0][:240] if content.strip() else ""
    return IntentSpec(summary=summary, sources=[str(path)])


def _load_request(request_path: Path) -> AuditRequest:
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot load AuditRequest from {request_path}: {exc}")
    try:
        return AuditRequest.model_validate(payload)
    except Exception as exc:
        _fail(f"invalid AuditRequest: {exc}")


def _build_request(
    repo_path: Path,
    base: str,
    intent: Path | None,
) -> AuditRequest:
    try:
        git_state = inspect_repo(repo_path, base=base)
    except GitRepoError as exc:
        _fail(str(exc))
    files = changed_files(git_state.path, git_state.base_revision, git_state.revision)
    return AuditRequest(
        repo=RepoSpec(
            path=str(git_state.path),
            revision=git_state.revision,
            base_revision=git_state.base_revision,
        ),
        intent=_read_intent(intent),
        scope=ScopeSpec(changed_files=files, language="python"),
        commands=detect_commands(git_state.path),
        policy=PolicySpec(),
        budgets=ToolBudgets(),
    )


def _run_deterministic_pipeline(
    request: AuditRequest,
    *,
    enable_property: bool = True,
    enable_mutation: bool = False,
) -> list[ToolEvidence]:
    """Run every deterministic verifier against ``request.repo.path``.

    Default pipeline (6 tools): lint, types, semgrep, codeql, pytest,
    hypothesis. ``mutmut`` stays opt-in because a full ``mutmut run`` can
    cost >10 minutes even on small repos.

    The self-audit fork guard (ADR-16, :func:`oida_code.ingest.manifest.is_self_audit`)
    protects ``pytest`` from recursive subprocess explosion when the audited
    tree is the oida-code repo itself; the other runners are idempotent.
    """
    repo_path = Path(request.repo.path)
    budgets = request.budgets
    evidence: list[ToolEvidence] = [
        run_lint(repo_path, budget_seconds=budgets.lint),
        run_type_check(repo_path, budget_seconds=budgets.types),
        run_semgrep(repo_path, budget_seconds=budgets.semgrep),
        run_codeql(repo_path, budget_seconds=budgets.codeql),
        run_pytest(repo_path, budget_seconds=budgets.tests),
    ]
    if enable_property:
        evidence.append(run_hypothesis(repo_path, budget_seconds=budgets.hypothesis))
    if enable_mutation:
        evidence.append(run_mutmut(repo_path, budget_seconds=budgets.mutmut))
    return evidence


def _build_report(
    request: AuditRequest,
    evidence: list[ToolEvidence],
    resolution: VerdictResolution,
) -> AuditReport:
    del request  # unused for now; Phase 5 fuses it with OIDA scorer.
    return AuditReport(
        summary=ReportSummary(
            verdict=resolution.label,
            # mean_q_obs / grounding / V_net / debt / corrupt_success_ratio
            # require the OIDA fusion (Phase 5). They stay None in Phase 1.
        ),
        critical_findings=resolution.critical_findings,
        repair=RepairPlan(next_prompts=resolution.rationale),
        tool_evidence=evidence,
    )


def _write_report(report: AuditReport, out: Path | None, fmt: OutputFormat) -> None:
    if out is None:
        if fmt is OutputFormat.json:
            typer.echo(report.model_dump_json(indent=2))
            return
        if fmt is OutputFormat.markdown:
            from oida_code.report.markdown_report import render_markdown

            typer.echo(render_markdown(report))
            return
        from oida_code.report.sarif_export import render_sarif

        typer.echo(render_sarif(report))
        return

    if fmt is OutputFormat.json:
        write_json_report(report, out)
    elif fmt is OutputFormat.markdown:
        write_markdown_report(report, out)
    else:
        export_sarif(report, out)
    typer.echo(f"wrote {out}", err=True)


def _resolve_fail_on(report: AuditReport, fail_on: FailOn) -> int:
    if fail_on is FailOn.none:
        return 0
    if fail_on is FailOn.any_critical and report.critical_findings:
        return 3
    if fail_on is FailOn.corrupt and report.summary.verdict == "corrupt_success":
        return 3
    return 0


@app.callback(invoke_without_command=True)
def _main_callback(
    version: Annotated[
        bool,
        typer.Option("--version", help="Print version and exit."),
    ] = False,
) -> None:
    if version:
        typer.echo(f"oida-code {__version__}")
        raise typer.Exit(code=0)


@app.command("inspect")
def inspect_cmd(
    repo_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Path to the target git work tree.",
        ),
    ],
    base: Annotated[
        str,
        typer.Option("--base", help="Base revision to diff HEAD against."),
    ] = "HEAD",
    intent: Annotated[
        Path | None,
        typer.Option("--intent", help="Ticket / prompt file to summarise as intent."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Write AuditRequest here; else print to stdout.",
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Collect Pass-1 facts and emit an ``AuditRequest`` JSON."""
    request = _build_request(repo_path, base, intent)
    payload = request.model_dump_json(indent=2)
    if out is None:
        typer.echo(payload)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}", err=True)


@app.command("verify")
def verify_cmd(
    request_path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    out: Annotated[Path | None, typer.Option("--out")] = None,
    format_: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.json,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Non-zero exit trigger."),
    ] = FailOn.none,
    enable_property: Annotated[
        bool,
        typer.Option(
            "--enable-property/--no-property",
            help="Run Hypothesis property-based tests (default: on).",
        ),
    ] = True,
    enable_mutation: Annotated[
        bool,
        typer.Option(
            "--enable-mutation/--no-mutation",
            help="Run mutmut mutation testing (default: off; can be slow).",
        ),
    ] = False,
) -> None:
    """Run the deterministic verifiers against an existing ``AuditRequest``."""
    request = _load_request(request_path)
    evidence = _run_deterministic_pipeline(
        request,
        enable_property=enable_property,
        enable_mutation=enable_mutation,
    )
    resolution = resolve_verdict(evidence, request.policy)
    report = _build_report(request, evidence, resolution)
    _write_report(report, out, format_)
    exit_code = _resolve_fail_on(report, fail_on)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("audit")
def audit_cmd(
    repo_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Repo path to audit end-to-end.",
        ),
    ],
    base: Annotated[str, typer.Option("--base")] = "HEAD",
    intent: Annotated[Path | None, typer.Option("--intent")] = None,
    out: Annotated[Path | None, typer.Option("--out")] = None,
    format_: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.json,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Non-zero exit trigger."),
    ] = FailOn.none,
    enable_property: Annotated[
        bool,
        typer.Option(
            "--enable-property/--no-property",
            help="Run Hypothesis property-based tests (default: on).",
        ),
    ] = True,
    enable_mutation: Annotated[
        bool,
        typer.Option(
            "--enable-mutation/--no-mutation",
            help="Run mutmut mutation testing (default: off; can be slow).",
        ),
    ] = False,
) -> None:
    """End-to-end deterministic audit: inspect → verify → report (Phase 1 path)."""
    request = _build_request(repo_path, base, intent)
    evidence = _run_deterministic_pipeline(
        request,
        enable_property=enable_property,
        enable_mutation=enable_mutation,
    )
    resolution = resolve_verdict(evidence, request.policy)
    report = _build_report(request, evidence, resolution)
    _write_report(report, out, format_)
    exit_code = _resolve_fail_on(report, fail_on)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("normalize")
def normalize_cmd(
    request_path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    out: Annotated[Path | None, typer.Option("--out")] = None,
    surface_mode: Annotated[
        str,
        typer.Option(
            "--surface",
            help="Audit surface derivation: 'impact' (default) or 'changed' (legacy).",
        ),
    ] = "impact",
    max_surface_files: Annotated[
        int,
        typer.Option(
            "--max-surface-files",
            help="Cap on the audit surface size (default 50).",
            min=1,
            max=500,
        ),
    ] = 50,
) -> None:
    """Map an ``AuditRequest`` into a ``NormalizedScenario`` (Phase 2 / D0).

    Extracts obligations from the **audit surface** — ``changed_files``
    PLUS the bounded impact cone (direct imports / importers / related
    tests / config / migration) when ``--surface=impact``. Use
    ``--surface=changed`` to restrict extraction to the raw diff only.
    Does not run the vendored analyzer or the deterministic verifiers
    — use ``verify`` / ``audit`` for that.

    The emitted ``AuditRequest`` on scenario is the original — the
    surface derivation does NOT mutate ``request.scope.changed_files``.
    """
    if surface_mode not in ("impact", "changed"):
        _fail(f"--surface must be 'impact' or 'changed', got {surface_mode!r}")
    request = _load_request(request_path)
    surface = derive_audit_surface(
        Path(request.repo.path),
        list(request.scope.changed_files),
        mode=surface_mode,  # type: ignore[arg-type]
        max_files=max_surface_files,
    )
    obligations = extract_obligations(Path(request.repo.path), surface)
    # D0.1: obligations_to_scenario feeds changed_files into
    # build_dependency_graph. Pass a shallow-copy of the request with
    # the derived surface so the graph scans the full audit surface —
    # otherwise the ``imported_by_changed`` branch (reverse direction:
    # dependency changed, importers reached via impact cone) produces
    # obligations without the corresponding direct_import edges. The
    # PUBLIC request is preserved on disk so downstream readers still
    # see the raw diff in ``scope.changed_files``.
    surface_request = request.model_copy(
        update={
            "scope": request.scope.model_copy(
                update={"changed_files": surface}
            )
        }
    )
    scenario = obligations_to_scenario(
        obligations,
        request=surface_request,
        tool_evidence=None,
        name=request.intent.summary[:80] if request.intent.summary else None,
    )
    payload = scenario.model_dump_json(indent=2)
    if out is None:
        typer.echo(payload)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}", err=True)


@app.command("score-trace")
def score_trace_cmd(
    transcript: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Claude Code JSONL transcript to score.",
        ),
    ],
    request_path: Annotated[
        Path | None,
        typer.Option(
            "--request",
            help="Optional AuditRequest JSON to bound U(t) via changed_files.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            help="Optional repo path for outcome labeling (git log window).",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out")] = None,
    surface_mode: Annotated[
        str,
        typer.Option(
            "--surface",
            help="Audit surface derivation when --request is given: "
            "'impact' (default) or 'changed' (raw diff only).",
        ),
    ] = "impact",
    max_surface_files: Annotated[
        int,
        typer.Option(
            "--max-surface-files",
            help="Cap on the audit surface size (default 50).",
            min=1,
            max=500,
        ),
    ] = 50,
    experimental_shadow_fusion: Annotated[
        bool,
        typer.Option(
            "--experimental-shadow-fusion",
            help="Compute non-authoritative shadow fusion diagnostics (E1, "
            "ADR-22). NEVER unlocks official V_net/debt_final.",
        ),
    ] = False,
) -> None:
    """Score a Claude Code transcript — emit :class:`TrajectoryMetrics` JSON.

    With ``--repo``, appends a ``session_outcome`` block (git-derived
    non-circular validation signal, ADR-18).
    """
    from oida_code.models.obligation import Obligation as _Obligation

    if surface_mode not in ("impact", "changed"):
        _fail(f"--surface must be 'impact' or 'changed', got {surface_mode!r}")

    trace = parse_claude_code_transcript(transcript)
    obligations: list[_Obligation] = []
    request_obj = None
    if request_path is not None:
        raw_request = _load_request(request_path)
        repo_path = Path(raw_request.repo.path)
        raw_changed = list(raw_request.scope.changed_files)
        # D0/D0.1: obligation extraction and U(t) bounding both use the
        # impact surface (or raw diff under --surface=changed). The
        # public request's changed_files is preserved on disk; we only
        # swap the scope of a shallow-copy passed downstream.
        surface = derive_audit_surface(
            repo_path,
            raw_changed,
            mode=surface_mode,  # type: ignore[arg-type]
            max_files=max_surface_files,
        )
        obligations = extract_obligations(repo_path, surface)
        request_obj = raw_request.model_copy(
            update={
                "scope": raw_request.scope.model_copy(
                    update={"changed_files": surface}
                )
            }
        )
    metrics = score_trajectory(trace, obligations=obligations, request=request_obj)
    payload: dict[str, object] = json.loads(
        metrics.model_dump_json(exclude={"timesteps"})
    )
    if experimental_shadow_fusion and request_obj is not None:
        from oida_code.score.experimental_shadow_fusion import (
            compute_experimental_shadow_fusion,
        )
        from oida_code.score.fusion_readiness import assess_fusion_readiness
        from oida_code.score.mapper import obligations_to_scenario

        scenario = obligations_to_scenario(
            obligations, request=request_obj, tool_evidence=None
        )
        readiness = assess_fusion_readiness(
            scenario, tool_evidence=None, trajectory_metrics=metrics
        )
        shadow = compute_experimental_shadow_fusion(
            scenario,
            readiness,
            tool_evidence=None,
            trajectory_metrics=metrics,
        )
        payload["readiness"] = json.loads(readiness.model_dump_json())
        payload["experimental_shadow_fusion"] = json.loads(
            shadow.model_dump_json()
        )
    if repo is not None:
        outcome = compute_session_outcome(transcript, repo)
        payload["session_outcome"] = {
            "outcome": outcome.outcome,
            "commits_in_window": outcome.commits_in_window,
            "reachable_from_head": outcome.reachable_from_head,
            "start_ts": outcome.start_ts.isoformat() if outcome.start_ts else None,
            "end_ts": outcome.end_ts.isoformat() if outcome.end_ts else None,
        }
    text = json.dumps(payload, indent=2)
    if out is None:
        typer.echo(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}", err=True)


@app.command("repair")
def repair_cmd(
    report_path: Annotated[Path, typer.Argument(help="AuditReport JSON to repair.")],
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Emit a double-loop repair plan with targeted prompts (Phase 5)."""
    del report_path, out
    raise NotImplementedError(
        "repair: Phase 5 — wires double-loop dominance + LLM repair prompts."
    )


def main() -> None:  # pragma: no cover - entry-point thunk
    app(prog_name="oida-code")


if __name__ == "__main__":  # pragma: no cover
    main()
    sys.exit(0)
