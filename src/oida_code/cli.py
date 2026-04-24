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
from oida_code.extract.obligations import extract_obligations
from oida_code.ingest.diff_parser import changed_files
from oida_code.ingest.git_repo import GitRepoError, inspect_repo
from oida_code.ingest.manifest import detect_commands
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
    enable_property: bool = False,
    enable_mutation: bool = False,
) -> list[ToolEvidence]:
    """Run every deterministic verifier against ``request.repo.path``.

    Default pipeline (5 tools): lint, types, semgrep, codeql, pytest.

    Phase 2 runners (hypothesis, mutmut) are **opt-in** behind flags. They
    each spawn an additional ``pytest`` subprocess (hypothesis) or an
    N-mutant subprocess tree (mutmut). On Windows / Cygwin-fork hosts, the
    multiplicative subprocess cost can exhaust handles when auditing repos
    whose tests themselves invoke the CLI. See PHASE2_AUDIT_REPORT §7.
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
            "--enable-property",
            help="Run Hypothesis property-based tests (Phase 2, opt-in).",
        ),
    ] = False,
    enable_mutation: Annotated[
        bool,
        typer.Option(
            "--enable-mutation",
            help="Run mutmut mutation testing (Phase 2, opt-in; can be slow).",
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
            "--enable-property",
            help="Run Hypothesis property-based tests (Phase 2, opt-in).",
        ),
    ] = False,
    enable_mutation: Annotated[
        bool,
        typer.Option(
            "--enable-mutation",
            help="Run mutmut mutation testing (Phase 2, opt-in; can be slow).",
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
) -> None:
    """Map an ``AuditRequest`` into a ``NormalizedScenario`` (Phase 2).

    Extracts obligations from the request's changed_files, synthesizes a
    scenario via the mapper, and emits it as JSON. Does **not** run the
    vendored analyzer or the deterministic verifiers — use ``verify`` /
    ``audit`` for that.
    """
    request = _load_request(request_path)
    obligations = extract_obligations(
        Path(request.repo.path), list(request.scope.changed_files)
    )
    scenario = obligations_to_scenario(
        obligations,
        request=request,
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
