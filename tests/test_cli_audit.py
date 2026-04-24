"""End-to-end CLI tests for the Phase 1 ``verify`` and ``audit`` commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.models import AuditReport, AuditRequest

runner = CliRunner()


def test_verify_command_reads_request_and_emits_report(tmp_path: Path) -> None:
    from tests.conftest import REPO_ROOT

    # First generate an AuditRequest via inspect.
    request_path = tmp_path / "request.json"
    result = runner.invoke(
        app,
        ["inspect", str(REPO_ROOT), "--base", "HEAD", "--out", str(request_path)],
    )
    assert result.exit_code == 0, result.output
    assert request_path.is_file()

    # Now run verify.
    report_path = tmp_path / "report.json"
    result = runner.invoke(
        app,
        ["verify", str(request_path), "--out", str(report_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    report = AuditReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert report.summary.verdict in {
        "verified",
        "counterexample_found",
        "insufficient_evidence",
    }
    # Phase-1 summary fields stay None (not computed without full OIDA fusion).
    assert report.summary.mean_q_obs is None
    # We expect tool_evidence for every runner we invoke.
    tools = {ev.tool for ev in report.tool_evidence}
    assert tools >= {"ruff", "mypy", "codeql"}


def test_audit_command_end_to_end_json(tmp_path: Path) -> None:
    from tests.conftest import REPO_ROOT

    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "audit",
            str(REPO_ROOT),
            "--base",
            "HEAD",
            "--out",
            str(out),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    report = AuditReport.model_validate_json(out.read_text(encoding="utf-8"))
    assert report.summary.verdict in {
        "verified",
        "counterexample_found",
        "insufficient_evidence",
    }


def test_audit_command_markdown_format(tmp_path: Path) -> None:
    from tests.conftest import REPO_ROOT

    out = tmp_path / "report.md"
    result = runner.invoke(
        app,
        [
            "audit",
            str(REPO_ROOT),
            "--base",
            "HEAD",
            "--out",
            str(out),
            "--format",
            "markdown",
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "# OIDA Code Audit" in text


def test_audit_command_sarif_format(tmp_path: Path) -> None:
    from tests.conftest import REPO_ROOT

    out = tmp_path / "report.sarif"
    result = runner.invoke(
        app,
        [
            "audit",
            str(REPO_ROOT),
            "--base",
            "HEAD",
            "--out",
            str(out),
            "--format",
            "sarif",
        ],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["version"] == "2.1.0"


def test_inspect_still_works_with_intent_flag(tmp_path: Path) -> None:
    from tests.conftest import REPO_ROOT

    intent = tmp_path / "ticket.md"
    intent.write_text("Add email validation\nDetails here\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["inspect", str(REPO_ROOT), "--intent", str(intent)],
    )
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    request = AuditRequest.model_validate(json.loads(result.output[start : end + 1]))
    assert request.intent.summary.startswith("Add email validation")
    assert str(intent) in request.intent.sources
