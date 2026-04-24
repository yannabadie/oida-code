"""``oida-code`` CLI entry point (blueprint §8).

Subcommand status in phase 1:

* ``inspect``   — implemented. Produces an :class:`AuditRequest` JSON.
* ``normalize`` — declared, ``NotImplementedError`` (phase 2, blueprint days 7-8).
* ``verify``    — declared, ``NotImplementedError`` (phase 2, blueprint days 5-6).
* ``audit``     — declared, ``NotImplementedError`` (phase 3).
* ``repair``    — declared, ``NotImplementedError`` (phase 3).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from oida_code import __version__
from oida_code.ingest.diff_parser import changed_files
from oida_code.ingest.git_repo import GitRepoError, inspect_repo
from oida_code.ingest.manifest import default_python_commands
from oida_code.models.audit_request import (
    AuditRequest,
    IntentSpec,
    PolicySpec,
    RepoSpec,
    ScopeSpec,
)

app = typer.Typer(
    name="oida-code",
    help="AI code verifier — measure the gap between apparent and guaranteed behavior.",
    no_args_is_help=True,
    add_completion=False,
)


def _fail(msg: str, code: int = 2) -> NoReturn:
    typer.echo(f"oida-code: {msg}", err=True)
    raise typer.Exit(code=code)


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
        typer.Option(
            "--base",
            help="Base revision to diff HEAD against (default: HEAD, yields an empty diff).",
        ),
    ] = "HEAD",
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Write the AuditRequest JSON here; otherwise print to stdout.",
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Collect Pass-1 deterministic facts and emit an ``AuditRequest`` JSON."""
    try:
        git_state = inspect_repo(repo_path, base=base)
    except GitRepoError as exc:
        _fail(str(exc))

    files = changed_files(git_state.path, git_state.base_revision, git_state.revision)
    request = AuditRequest(
        repo=RepoSpec(
            path=str(git_state.path),
            revision=git_state.revision,
            base_revision=git_state.base_revision,
        ),
        intent=IntentSpec(),
        scope=ScopeSpec(changed_files=files, language="python"),
        commands=default_python_commands(),
        policy=PolicySpec(),
    )
    payload = request.model_dump_json(indent=2)

    if out is None:
        typer.echo(payload)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}", err=True)


@app.command("normalize")
def normalize_cmd(
    request_path: Annotated[Path, typer.Argument(help="AuditRequest JSON to normalize.")],
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Map an ``AuditRequest`` into a ``NormalizedScenario`` (phase 2)."""
    del request_path, out
    raise NotImplementedError(
        "normalize: phase 2 — blueprint §13 days 7-8 (raw facts → normalized OIDA events)."
    )


@app.command("verify")
def verify_cmd(
    scenario_path: Annotated[Path, typer.Argument(help="NormalizedScenario JSON to verify.")],
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Run the behavioral verification pass (phase 2)."""
    del scenario_path, out
    raise NotImplementedError(
        "verify: phase 2 — blueprint §13 days 5-6 (Semgrep, Hypothesis, mutmut)."
    )


@app.command("audit")
def audit_cmd(
    repo_path: Annotated[Path, typer.Argument(help="Repo path to audit end-to-end.")],
    base: Annotated[str, typer.Option("--base")] = "HEAD",
    intent: Annotated[Path | None, typer.Option("--intent")] = None,
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Full pipeline: inspect → normalize → verify → report (phase 3)."""
    del repo_path, base, intent, out
    raise NotImplementedError(
        "audit: phase 3 — wires Pass 1/2/3 with the LLM verifier (blueprint §13 day 9)."
    )


@app.command("repair")
def repair_cmd(
    report_path: Annotated[Path, typer.Argument(help="AuditReport JSON to repair.")],
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Emit a double-loop repair plan with targeted prompts (phase 3)."""
    del report_path, out
    raise NotImplementedError(
        "repair: phase 3 — uses vendored double_loop_repair + LLM prompt synthesis."
    )


def main() -> None:  # pragma: no cover - entry-point thunk
    """Setuptools console-script thunk for ``oida-code``."""
    app(prog_name="oida-code")


if __name__ == "__main__":  # pragma: no cover
    main()
    sys.exit(0)
