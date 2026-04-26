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
from typing import Annotated, Any, NoReturn

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
        from oida_code.estimators.readiness import assess_estimator_readiness
        from oida_code.score.experimental_shadow_fusion import (
            compute_experimental_shadow_fusion,
        )
        from oida_code.score.fusion_readiness import assess_fusion_readiness
        from oida_code.score.mapper import build_scoring_inputs

        # E3.0 (ADR-24): build_scoring_inputs exposes the dependency
        # graph's per-edge confidences so shadow fusion uses real
        # DependencyEdge.confidence values instead of the uniform 0.6
        # default. Tool evidence stays None at score-trace time — the
        # full audit pipeline runs the verifiers; score-trace only
        # consumes pre-collected facts. The estimator readiness
        # ladder (E3.4) sits beside the official readiness gate and
        # describes what the deterministic baseline can claim.
        inputs = build_scoring_inputs(
            obligations, request=request_obj, tool_evidence=None,
        )
        readiness = assess_fusion_readiness(
            inputs.scenario, tool_evidence=None, trajectory_metrics=metrics,
        )
        estimator_report = assess_estimator_readiness(
            inputs.scenario, inputs.evidence_view, request=request_obj,
        )
        shadow = compute_experimental_shadow_fusion(
            inputs.scenario,
            readiness,
            tool_evidence=None,
            trajectory_metrics=metrics,
            edge_confidences=inputs.edge_confidences,
        )
        payload["readiness"] = json.loads(readiness.model_dump_json())
        payload["estimator_readiness"] = json.loads(
            estimator_report.model_dump_json()
        )
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


@app.command("build-artifact-manifest")
def build_artifact_manifest_cmd(
    bundle_root: Annotated[
        Path,
        typer.Argument(
            help=(
                "Root directory containing the artifacts to "
                "manifest (e.g. `.oida` or `.oida/provider-baseline`). "
                "Files are discovered recursively; the manifest "
                "itself is excluded from its own hash list."
            ),
            exists=True, file_okay=False, dir_okay=True,
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help=(
                "Output path for the manifest. Default: "
                "<bundle_root>/artifacts/manifest.json"
            ),
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="Optional provider label to record in the manifest.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Optional model id to record in the manifest.",
        ),
    ] = None,
) -> None:
    """Phase 4.9-F (QA/A26.md, ADR-34): build the artifact bundle
    manifest.

    Walks ``<bundle_root>``, classifies each artifact by filename /
    parent-directory pattern, computes its SHA256, and writes an
    :class:`ArtifactBundleManifest` to
    ``<bundle_root>/artifacts/manifest.json`` (or the path passed
    via ``--out``).

    The manifest pins:

    * ``mode = "diagnostic_only"`` (Literal — unrepresentable
      otherwise)
    * ``official_fields_emitted = False`` (Literal)
    * ``contains_secrets = False`` per artifact (Literal)
    """
    from oida_code.models.artifact_manifest import (
        build_manifest,
        write_manifest,
    )
    if out is None:
        manifest_relative_path = "artifacts/manifest.json"
        path = write_manifest(
            bundle_root,
            provider=provider, model=model,
            manifest_relative_path=manifest_relative_path,
        )
    else:
        # When --out is absolute / outside bundle_root, build the
        # manifest in-memory and write it where the operator asked.
        manifest = build_manifest(
            bundle_root, provider=provider, model=model,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8",
        )
        path = out
    typer.echo(f"manifest={path}")


@app.command("render-artifacts")
def render_artifacts_cmd(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help=(
                "Directory containing calibration-eval / provider-baseline "
                "artifacts (metrics.json + optional per_case.json + "
                "redacted_io/ + stability_summary.json)."
            ),
            exists=True, file_okay=False, dir_okay=True,
        ),
    ],
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Output file path for the rendered diagnostic Markdown.",
        ),
    ] = Path(".oida/diagnostic.md"),
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            help=(
                "Output format. Phase 4.9-A only ships ``markdown``; "
                "future phases may add ``json`` / ``sarif``."
            ),
        ),
    ] = "markdown",
) -> None:
    """Phase 4.9-A (QA/A26.md, ADR-34): render diagnostic artifacts.

    Reads the artifacts under ``<input-dir>`` and produces a
    diagnostic-only Markdown report. The output ALWAYS:

    * Opens with the diagnostic banner ("Diagnostic only — not a
      merge verdict.").
    * Shows ``total_v_net`` / ``debt_final`` / ``corrupt_success``
      as ``blocked`` per ADR-22.
    * Contains no merge-safe / production-safe / bug-free claims.
    * References ``redacted_io/<file>.json`` paths but never the raw
      prompt body.
    """
    from oida_code.report.diagnostic_report import write_diagnostic_markdown

    if fmt != "markdown":
        _fail(
            f"render-artifacts: --format={fmt!r} is not supported. "
            "Phase 4.9-A only ships 'markdown'.",
        )
    written = write_diagnostic_markdown(input_dir, out)
    typer.echo(f"diagnostic-markdown={written}")


@app.command("estimate-llm")
def estimate_llm_cmd(
    packet_path: Annotated[
        Path,
        typer.Argument(
            help="Path to an LLMEvidencePacket JSON (Phase 4.0).",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    provider: Annotated[
        str,
        typer.Option(
            "--llm-provider",
            help=(
                "Provider name: 'replay' (default; reads "
                "--llm-response-fixture), 'fake', 'external' (Phase "
                "4.0 stub — no call), or 'openai-compatible' (Phase "
                "4.4 — real provider; requires --provider-profile + "
                "--api-key-env). No external API call by default."
            ),
        ),
    ] = "replay",
    response_fixture: Annotated[
        Path | None,
        typer.Option(
            "--llm-response-fixture",
            help="Path to a fixture JSON for --llm-provider replay.",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option(
            "--provider-profile",
            help=(
                "Phase 4.4 provider-profile name "
                "(deepseek / kimi / minimax / custom_openai_compatible). "
                "Required when --llm-provider=openai-compatible."
            ),
        ),
    ] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option(
            "--api-key-env",
            help=(
                "Phase 4.4: env var name carrying the API key. "
                "Overrides the profile's default api_key_env. The "
                "value itself is NEVER printed in logs / errors / "
                "reports."
            ),
        ),
    ] = None,
    model_override: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Phase 4.4: override the profile's default_model.",
        ),
    ] = None,
    base_url_override: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help=(
                "Phase 4.4: override the profile's base_url (only "
                "meaningful for custom_openai_compatible)."
            ),
        ),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Where to write the EstimatorReport JSON."),
    ] = None,
    timeout_s: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Per-call provider budget (seconds).",
            min=1, max=600,
        ),
    ] = 30,
) -> None:
    """Phase 4.0/4.4: run an LLM estimator on a frozen packet.

    Always emits an :class:`EstimatorReport` JSON. Failures (invalid
    response, schema violations, forbidden phrases) become blockers
    and the report falls back to the deterministic baseline embedded
    in the packet. **Never** emits official ``V_net`` / ``debt_final``
    / ``corrupt_success``; the readiness ladder caps at
    ``shadow_ready`` in production.

    Phase 4.4 — passing ``--llm-provider openai-compatible`` opts in
    to a real external call. The key is read from the env var named
    by ``--api-key-env`` (or the profile default); a missing var
    raises a clean error without echoing the env value. ADR-29.
    """
    from oida_code.estimators.llm_estimator import run_llm_estimator
    from oida_code.estimators.llm_prompt import LLMEvidencePacket
    from oida_code.estimators.llm_provider import (
        LLMProvider,
        LLMProviderUnavailable,
        build_provider,
    )

    packet = LLMEvidencePacket.model_validate_json(
        packet_path.read_text(encoding="utf-8")
    )
    try:
        backend: LLMProvider
        if provider == "openai-compatible":
            backend = _build_openai_compatible_provider(
                profile_name=profile_name,
                api_key_env=api_key_env,
                model_override=model_override,
                base_url_override=base_url_override,
                timeout_s=timeout_s,
            )
        else:
            backend = build_provider(provider, fixture_path=response_fixture)
    except LLMProviderUnavailable as exc:
        _fail(f"llm provider unavailable: {exc}")
    run = run_llm_estimator(packet, backend, timeout_s=timeout_s)
    text = run.report.model_dump_json(indent=2)
    if out is None:
        typer.echo(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def _build_openai_compatible_provider(
    *,
    profile_name: str | None,
    api_key_env: str | None,
    model_override: str | None,
    base_url_override: str | None,
    timeout_s: int,
    capture_redacted_io: bool = False,
) -> Any:  # the import is local; concrete type checked by tests
    """Construct an :class:`OpenAICompatibleChatProvider` from CLI flags.

    Phase 4.4 hard rule: the integrator MUST pass
    ``--provider-profile`` to opt in to a real call. Custom providers
    additionally need ``--api-key-env`` AND ``--base-url``.

    Phase 4.8-A: ``capture_redacted_io`` defaults to False; the CLI
    flag ``--store-redacted-provider-io`` flips it to True. The
    redaction happens inside the provider so the runner never holds
    the raw API key value.
    """
    from oida_code.estimators.llm_provider import LLMProviderUnavailable
    from oida_code.estimators.provider_config import (
        ProviderProfile,
        get_predefined_profile,
    )
    from oida_code.estimators.providers import OpenAICompatibleChatProvider

    if profile_name is None:
        raise LLMProviderUnavailable(
            "--llm-provider openai-compatible requires --provider-profile "
            "(deepseek / kimi / minimax / custom_openai_compatible)."
        )
    if profile_name == "custom_openai_compatible":
        if api_key_env is None or base_url_override is None or model_override is None:
            raise LLMProviderUnavailable(
                "custom_openai_compatible requires --api-key-env "
                "--base-url --model."
            )
        profile = ProviderProfile(
            name="custom_openai_compatible",
            base_url=base_url_override,
            api_key_env=api_key_env,
            default_model=model_override,
            timeout_s=timeout_s,
        )
    else:
        try:
            base = get_predefined_profile(profile_name)  # type: ignore[arg-type]
        except KeyError as exc:
            raise LLMProviderUnavailable(str(exc)) from None
        updates: dict[str, object] = {"timeout_s": timeout_s}
        if api_key_env is not None:
            updates["api_key_env"] = api_key_env
        if model_override is not None:
            updates["default_model"] = model_override
        if base_url_override is not None:
            updates["base_url"] = base_url_override
        profile = base.model_copy(update=updates)
    return OpenAICompatibleChatProvider(
        profile=profile, capture_redacted_io=capture_redacted_io,
    )


@app.command("verify-claims")
def verify_claims_cmd(
    packet_path: Annotated[
        Path,
        typer.Argument(
            help="Path to an LLMEvidencePacket JSON (Phase 4.0).",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    forward_replay: Annotated[
        Path,
        typer.Option(
            "--forward-replay",
            help="Path to a fixture JSON containing the forward verifier "
            "response. Phase 4.1 only supports replay; live providers "
            "land in Phase 4.2.",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    backward_replay: Annotated[
        Path,
        typer.Option(
            "--backward-replay",
            help="Path to a fixture JSON containing the backward verifier "
            "response.",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Where to write the VerifierAggregationReport JSON.",
        ),
    ] = None,
    timeout_s: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Per-call provider budget (seconds).",
            min=1, max=600,
        ),
    ] = 30,
) -> None:
    """Phase 4.1 (ADR-26): aggregate forward + backward verifier replays.

    Produces a :class:`VerifierAggregationReport` that combines the two
    replay responses against the packet's evidence. Even if every claim
    is accepted, the report is non-authoritative — ADR-22 + ADR-26 keep
    the official fusion gate closed.
    """
    from oida_code.estimators.llm_prompt import LLMEvidencePacket
    from oida_code.verifier.forward_backward import run_verifier
    from oida_code.verifier.replay import (
        FileReplayVerifierProvider,
    )

    packet = LLMEvidencePacket.model_validate_json(
        packet_path.read_text(encoding="utf-8")
    )
    forward = FileReplayVerifierProvider(fixture_path=forward_replay)
    backward = FileReplayVerifierProvider(fixture_path=backward_replay)
    run = run_verifier(packet, forward, backward, timeout_s=timeout_s)
    text = run.report.model_dump_json(indent=2)
    if out is None:
        typer.echo(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


@app.command("run-tools")
def run_tools_cmd(
    requests_path: Annotated[
        Path,
        typer.Argument(
            help="JSON list of VerifierToolRequest objects.",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    policy_path: Annotated[
        Path,
        typer.Option(
            "--policy",
            help="Path to a ToolPolicy JSON.",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help="Where to write the VerifierToolResult JSON list.",
        ),
    ] = None,
) -> None:
    """Phase 4.2 (ADR-27): execute a budgeted batch of tool requests.

    Reads a JSON list of :class:`VerifierToolRequest` objects and a
    :class:`ToolPolicy`, runs each request through its adapter
    (validated against the policy), and emits one
    :class:`VerifierToolResult` per request as JSON. Default uses
    :func:`subprocess.run` (no shell). Read-only by default; the
    policy MUST set ``allow_write=False`` and ``allow_network=False``
    in Phase 4.2.
    """
    from oida_code.verifier.tools import (
        ToolExecutionEngine,
        ToolPolicy,
        VerifierToolRequest,
    )

    raw = json.loads(requests_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        _fail("run-tools requests must be a JSON list of VerifierToolRequest")
    requests = tuple(VerifierToolRequest.model_validate(item) for item in raw)
    policy = ToolPolicy.model_validate_json(
        policy_path.read_text(encoding="utf-8")
    )
    engine = ToolExecutionEngine()
    results = engine.run(requests, policy)
    text = json.dumps(
        [r.model_dump(mode="json") for r in results], indent=2,
    )
    if out is None:
        typer.echo(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


@app.command("calibration-eval")
def calibration_eval_cmd(
    dataset_path: Annotated[
        Path,
        typer.Argument(
            help="Path to datasets/calibration_v1/ (manifest.json + cases/).",
            exists=True, file_okay=False, dir_okay=True,
        ),
    ],
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Output directory (metrics.json + report.md + per_case.json).",
        ),
    ] = Path(".oida/calibration_v1"),
    stability_report: Annotated[
        Path | None,
        typer.Option(
            "--stability-report",
            help=(
                "Optional path to stability_report.json from "
                "check_calibration_stability.py. When omitted, defaults to "
                "<--out>/stability_report.json if present; otherwise "
                "F2P/P2P metrics are emitted as null with "
                "code_outcome_status='not_computed'."
            ),
        ),
    ] = None,
    llm_provider: Annotated[
        str,
        typer.Option(
            "--llm-provider",
            help=(
                "Phase 4.4.1: provider used for the ``llm_estimator`` "
                "family. Default 'replay' (per-case fixture file). "
                "'fake' uses the deterministic fake. "
                "'openai-compatible' opts in to a real external "
                "provider — requires --provider-profile + the "
                "corresponding api_key_env."
            ),
        ),
    ] = "replay",
    provider_profile: Annotated[
        str | None,
        typer.Option(
            "--provider-profile",
            help=(
                "Phase 4.4.1: provider-profile name (deepseek / kimi / "
                "minimax / custom_openai_compatible). Required when "
                "--llm-provider=openai-compatible."
            ),
        ),
    ] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option(
            "--api-key-env",
            help=(
                "Phase 4.4.1: env var name carrying the API key. "
                "Overrides the profile's default api_key_env. The "
                "value itself is NEVER printed in logs / errors / "
                "reports."
            ),
        ),
    ] = None,
    model_override: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Phase 4.4.1: override the profile's default_model.",
        ),
    ] = None,
    base_url_override: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Phase 4.4.1: override the profile's base_url.",
        ),
    ] = None,
    max_provider_cases: Annotated[
        int,
        typer.Option(
            "--max-provider-cases",
            help=(
                "Phase 4.4.1: cap the number of llm_estimator cases "
                "that hit a non-replay provider. 0 means no cap. "
                "Excess cases are skipped (recorded as "
                "estimator_skipped=True with a clear reason)."
            ),
            min=0, max=10_000,
        ),
    ] = 0,
    timeout_s: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Phase 4.4.1: per-call provider timeout in seconds.",
            min=1, max=600,
        ),
    ] = 60,
    store_redacted_provider_io: Annotated[
        bool,
        typer.Option(
            "--store-redacted-provider-io",
            help=(
                "Phase 4.8-A (ADR-33): capture per-case redacted "
                "provider I/O under <out>/<provider>/redacted_io/. "
                "DISABLED BY DEFAULT — opt-in only. The redaction "
                "happens INSIDE the provider before anything reaches "
                "disk; the API key value never travels into the "
                "runner. Only meaningful when --llm-provider is "
                "openai-compatible (replay/fake providers have no "
                "real wire response to capture)."
            ),
        ),
    ] = False,
    repeat_provider_runs: Annotated[
        int,
        typer.Option(
            "--repeat-provider-runs",
            help=(
                "Phase 4.8-E (ADR-33): repeat the external provider "
                "loop N times to measure stability (mean + std). "
                "Hard cap = 3 to bound API spend; default 1 = single "
                "run (current behaviour). The replay path always "
                "runs once; this flag only affects the external "
                "provider loop. Stability metrics are written to "
                "<out>/stability_summary.json when N > 1."
            ),
            min=1, max=3,
        ),
    ] = 1,
) -> None:
    """Phase 4.3 + 4.4 + 4.4.1: run the calibration eval.

    Loads every case under ``<dataset>/cases/``, dispatches to its
    family evaluator, aggregates metrics, and emits ``metrics.json``,
    ``report.md``, and ``per_case.json`` under ``<out>``.

    Phase 4.4.1 — when ``--llm-provider openai-compatible`` is passed,
    ``llm_estimator`` family cases route to a real external provider
    (DeepSeek / Kimi / MiniMax / custom). Default ``replay`` keeps the
    pipeline hermetic. ``--max-provider-cases`` caps the external
    spend; cases beyond the cap are skipped with a clear reason.

    Exits with code 3 if **any** case reports an
    ``official_field_leak_count > 0`` (4.3.1-A runtime gate).
    """
    import json as _json

    from oida_code.calibration.metrics import (
        OfficialFieldLeakError,
        assert_no_official_field_leaks,
    )
    from oida_code.calibration.runner import (
        CaseResult,
        aggregate,
        load_case,
        run_case,
    )
    from oida_code.estimators.llm_provider import (
        FakeLLMProvider,
        LLMProvider,
        LLMProviderUnavailable,
    )

    cases_dir = dataset_path / "cases"
    if not cases_dir.is_dir():
        _fail(f"no cases dir at {cases_dir}; run build_calibration_dataset.py first")
    out.mkdir(parents=True, exist_ok=True)

    # Phase 4.4.1 — provider selection guards.
    is_external = llm_provider == "openai-compatible"
    shared_provider: LLMProvider | None = None
    redacted_io_dir: Path | None = None
    if is_external:
        try:
            shared_provider = _build_openai_compatible_provider(
                profile_name=provider_profile,
                api_key_env=api_key_env,
                model_override=model_override,
                base_url_override=base_url_override,
                timeout_s=timeout_s,
                capture_redacted_io=store_redacted_provider_io,
            )
        except LLMProviderUnavailable as exc:
            _fail(f"calibration-eval: external provider unavailable: {exc}")
        # Phase 4.8-A — redacted IO directory under
        # <out>/redacted_io/ when opted in. The workflow / operator
        # is responsible for the parent path (e.g.,
        # `.oida/provider-baseline/<provider>/`); the CLI just nests
        # one fixed `redacted_io/` directory inside <out>.
        if store_redacted_provider_io:
            redacted_io_dir = out / "redacted_io"
    elif llm_provider == "fake":
        shared_provider = FakeLLMProvider()
    elif llm_provider != "replay":
        _fail(
            "--llm-provider must be one of "
            "{replay, fake, openai-compatible}",
        )
    if store_redacted_provider_io and not is_external:
        # Honest behaviour: the flag is only meaningful for the
        # external provider path. Replay/fake paths have no wire
        # response to capture; we say so loudly rather than silently
        # writing nothing.
        typer.echo(
            "calibration-eval: --store-redacted-provider-io is a "
            "no-op for --llm-provider != openai-compatible; the "
            "replay/fake paths have no real wire response to "
            "capture.",
            err=True,
        )

    results: list[CaseResult] = []
    provider_calls = 0
    for case_dir in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        # Phase 4.4.1 — pick the provider for llm_estimator cases.
        case_provider: LLMProvider | None = None
        if case.family == "llm_estimator":
            if shared_provider is None:
                # Default replay path uses the per-case fixture.
                case_provider = None
            else:
                # External / fake — count toward the cap.
                if (
                    is_external
                    and max_provider_cases > 0
                    and provider_calls >= max_provider_cases
                ):
                    skipped_result = CaseResult(
                        case_id=case.case_id,
                        family=case.family,
                        contamination_risk=case.contamination_risk,
                    )
                    skipped_result.estimator_skipped = True
                    skipped_result.estimator_skipped_reason = (
                        f"max_provider_cases={max_provider_cases} cap "
                        "exhausted; case not sent to external provider"
                    )
                    skipped_result.notes.append(
                        skipped_result.estimator_skipped_reason
                    )
                    results.append(skipped_result)
                    continue
                case_provider = shared_provider
                if is_external:
                    provider_calls += 1
        results.append(
            run_case(
                case, case_dir,
                provider=case_provider,
                redacted_io_dir=redacted_io_dir,
            ),
        )

    stability_payload: list[dict[str, object]] | None = None
    candidate = stability_report or (out / "stability_report.json")
    if candidate.is_file():
        try:
            raw = _json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                stability_payload = [r for r in raw if isinstance(r, dict)]
        except (OSError, _json.JSONDecodeError):
            stability_payload = None

    metrics = aggregate(results, stability_report=stability_payload)
    (out / "metrics.json").write_text(
        metrics.model_dump_json(indent=2), encoding="utf-8",
    )
    # Phase 4.9-D (QA/A26.md, ADR-34) — emit a key=value file the
    # composite GitHub Action can append to `$GITHUB_OUTPUT`. The
    # `diagnostic-status` enum is constrained to four values
    # (`blocked` / `contract_failed` / `contract_clean` /
    # `diagnostic_only`); the FORBIDDEN values
    # (`merge_safe` / `production_safe` / `verified`) are unreachable
    # by static type — the Literal in `derive_diagnostic_status` would
    # reject them at construction time.
    from oida_code.report.diagnostic_report import derive_diagnostic_status
    diagnostic_status = derive_diagnostic_status(metrics)
    (out / "action_outputs.txt").write_text(
        (
            f"diagnostic-status={diagnostic_status}\n"
            f"official-field-leaks={metrics.official_field_leak_count}\n"
        ),
        encoding="utf-8",
    )
    typer.echo(
        f"cases_evaluated={metrics.cases_evaluated} "
        f"leaks={metrics.official_field_leak_count} "
        f"code_outcome_status={metrics.code_outcome_status} "
        f"estimator_evaluated={metrics.estimator_cases_evaluated} "
        f"estimator_skipped={metrics.estimator_cases_skipped} "
        f"diagnostic_status={diagnostic_status}"
    )
    try:
        assert_no_official_field_leaks(metrics)
    except OfficialFieldLeakError as exc:
        typer.echo(f"FAIL: {exc}", err=True)
        raise typer.Exit(code=3) from None

    # Phase 4.8-E (ADR-33): repeat the external-provider loop to
    # measure stability. Only fires when --llm-provider is
    # openai-compatible AND --repeat-provider-runs > 1. The first
    # run is the one already written above; we add (N-1) more runs
    # and write `<out>/stability_summary.json` with mean+std across
    # all N. Hard cap = 3 to bound API spend (enforced by Typer's
    # min/max on the option).
    if is_external and repeat_provider_runs > 1:
        from oida_code.calibration.metrics import CalibrationMetrics
        all_metrics: list[CalibrationMetrics] = [metrics]
        for repeat_idx in range(1, repeat_provider_runs):
            run_results: list[CaseResult] = []
            run_provider_calls = 0
            for case_dir in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
                case = load_case(case_dir)
                case_provider2: LLMProvider | None = None
                if case.family == "llm_estimator":
                    if shared_provider is None:
                        case_provider2 = None
                    else:
                        if (
                            max_provider_cases > 0
                            and run_provider_calls >= max_provider_cases
                        ):
                            sk = CaseResult(
                                case_id=case.case_id,
                                family=case.family,
                                contamination_risk=case.contamination_risk,
                            )
                            sk.estimator_skipped = True
                            sk.estimator_skipped_reason = (
                                f"repeat#{repeat_idx + 1}: "
                                f"max_provider_cases={max_provider_cases} "
                                "cap exhausted"
                            )
                            run_results.append(sk)
                            continue
                        case_provider2 = shared_provider
                        run_provider_calls += 1
                run_results.append(
                    run_case(
                        case, case_dir,
                        provider=case_provider2,
                        redacted_io_dir=None,  # only the first run captures
                    ),
                )
            run_metrics = aggregate(run_results, stability_report=stability_payload)
            all_metrics.append(run_metrics)
            try:
                assert_no_official_field_leaks(run_metrics)
            except OfficialFieldLeakError as exc:
                typer.echo(
                    f"FAIL repeat#{repeat_idx + 1}: {exc}", err=True,
                )
                raise typer.Exit(code=3) from None
        # Build the stability summary.
        import math
        def _mean_std(vals: list[float]) -> tuple[float, float]:
            if not vals:
                return (0.0, 0.0)
            mean = sum(vals) / len(vals)
            if len(vals) == 1:
                return (mean, 0.0)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            return (mean, math.sqrt(var))
        # Tracked metrics — Phase 4.8-E spec.
        def _series(attr: str) -> list[float]:
            out: list[float] = []
            for m in all_metrics:
                v = getattr(m, attr, None)
                if isinstance(v, (int, float)):
                    out.append(float(v))
            return out
        leak_max = max(
            (m.official_field_leak_count for m in all_metrics),
            default=0,
        )
        status_mean, status_std = _mean_std(_series("estimator_status_accuracy"))
        est_mean, est_std = _mean_std(_series("estimator_estimate_accuracy"))
        safety_mean, safety_std = _mean_std(_series("safety_block_rate"))
        fence_mean, fence_std = _mean_std(_series("fenced_injection_rate"))
        evid_mean, _ = _mean_std(_series("evidence_ref_precision"))
        stability_summary = {
            "n_runs": repeat_provider_runs,
            "official_field_leak_count_max": leak_max,
            "estimator_status_accuracy_mean": status_mean,
            "estimator_status_accuracy_std": status_std,
            "estimator_estimate_accuracy_mean": est_mean,
            "estimator_estimate_accuracy_std": est_std,
            "safety_block_rate_mean": safety_mean,
            "safety_block_rate_std": safety_std,
            "fenced_injection_rate_mean": fence_mean,
            "fenced_injection_rate_std": fence_std,
            "citation_precision_mean": evid_mean,
        }
        (out / "stability_summary.json").write_text(
            _json.dumps(stability_summary, indent=2),
            encoding="utf-8",
        )
        typer.echo(
            f"repeat_provider_runs={repeat_provider_runs} "
            f"status_acc={status_mean:.3f}±{status_std:.3f} "
            f"estimate_acc={est_mean:.3f}±{est_std:.3f} "
            f"leak_max={leak_max}"
        )
        # Phase 4.8-E hard rule: leak_max > 0 fails (already covered
        # by per-run assert above, but assert again on the max).
        if leak_max > 0:
            typer.echo(
                f"FAIL: official_field_leak_count_max={leak_max} > 0",
                err=True,
            )
            raise typer.Exit(code=3) from None


def main() -> None:  # pragma: no cover - entry-point thunk
    app(prog_name="oida-code")


if __name__ == "__main__":  # pragma: no cover
    main()
    sys.exit(0)
