"""Smoke tests for the ``oida-code`` Typer CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.models import AuditRequest

runner = CliRunner()


def test_inspect_help_shows() -> None:
    result = runner.invoke(app, ["inspect", "--help"])
    assert result.exit_code == 0, result.output
    assert "inspect" in result.output.lower()
    assert "--base" in result.output


def test_top_level_help_shows() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "inspect" in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert "oida-code" in result.output


def test_inspect_emits_valid_audit_request(tmp_path_factory: object) -> None:
    # The project itself is a git repo; run inspect against its root.
    from tests.conftest import REPO_ROOT

    result = runner.invoke(
        app,
        ["inspect", str(REPO_ROOT), "--base", "HEAD"],
    )
    assert result.exit_code == 0, result.output

    # Typer's CliRunner may prefix with ANSI; locate the JSON object.
    start = result.output.find("{")
    end = result.output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {result.output!r}"
    payload = result.output[start : end + 1]

    parsed = json.loads(payload)
    request = AuditRequest.model_validate(parsed)
    assert request.repo.revision, "revision must be resolved"
    assert request.repo.base_revision == request.repo.revision, (
        "--base HEAD yields an empty diff on a single-branch HEAD"
    )
    assert request.scope.language == "python"
    # changed_files is empty when base == head, which is expected.
    assert request.scope.changed_files == []


def test_phase2_subcommands_raise() -> None:
    for sub in ("normalize", "verify", "audit", "repair"):
        result = runner.invoke(app, [sub, "."])
        # Typer surfaces the raised NotImplementedError as a non-zero exit.
        assert result.exit_code != 0, f"{sub} should not succeed in phase 1"
