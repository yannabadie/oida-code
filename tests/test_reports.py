"""Tests for :mod:`oida_code.report` writers."""

from __future__ import annotations

import json
from pathlib import Path

from oida_code.models.audit_report import (
    AuditReport,
    CriticalFinding,
    RepairPlan,
    ReportSummary,
)
from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.report.json_report import render_json, write_json_report
from oida_code.report.markdown_report import render_markdown, write_markdown_report
from oida_code.report.sarif_export import export_sarif, render_sarif


def _sample_report() -> AuditReport:
    findings = [
        Finding(
            tool="ruff",
            rule_id="E501",
            severity="warning",
            path="src/foo.py",
            line=10,
            column=1,
            message="line too long",
            evidence_kind="static",
        ),
        Finding(
            tool="mypy",
            rule_id="assignment",
            severity="error",
            path="src/bar.py",
            line=5,
            message="Incompatible types",
            evidence_kind="static",
        ),
    ]
    return AuditReport(
        summary=ReportSummary(verdict="counterexample_found"),
        critical_findings=[
            CriticalFinding(
                id="f1",
                title="Incompatible types in bar.py",
                kind="mypy.assignment",
                evidence=["static", "mypy"],
                path="src/bar.py",
                line=5,
            )
        ],
        repair=RepairPlan(reopen=["e2"], next_prompts=["Fix the type."]),
        tool_evidence=[
            ToolEvidence(tool="ruff", status="ok", findings=[findings[0]], counts={"warning": 1}),
            ToolEvidence(tool="mypy", status="ok", findings=[findings[1]], counts={"error": 1}),
        ],
    )


def test_render_json_roundtrip() -> None:
    report = _sample_report()
    rendered = render_json(report)
    assert json.loads(rendered)["summary"]["verdict"] == "counterexample_found"
    # Idempotent.
    again = render_json(AuditReport.model_validate_json(rendered))
    assert again == rendered


def test_write_json_report_creates_file(tmp_path: Path) -> None:
    report = _sample_report()
    out = tmp_path / "sub" / "report.json"
    result = write_json_report(report, out)
    assert result == out
    assert out.read_text(encoding="utf-8").strip().startswith("{")


def test_render_markdown_is_diagnostic_only_and_contains_table() -> None:
    md = render_markdown(_sample_report())
    assert md.startswith("# OIDA Code Diagnostic Report")
    assert "Diagnostic only - not a merge decision" in md
    assert "**Verdict:**" not in md
    assert "Contradicted by deterministic evidence" in md
    assert "| Tool | Status |" in md
    assert "`ruff`" in md
    assert "Incompatible types in bar.py" in md
    assert "## Human follow-up checklist" in md
    assert "## Repair plan" not in md


def test_write_markdown_report_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = write_markdown_report(_sample_report(), out)
    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# OIDA Code Diagnostic Report")
    assert text.endswith("\n")


def test_render_sarif_has_required_fields() -> None:
    doc = json.loads(render_sarif(_sample_report()))
    assert doc["version"] == "2.1.0"
    assert doc["$schema"].endswith("sarif-schema-2.1.0.json")
    assert isinstance(doc["runs"], list) and doc["runs"]
    first = doc["runs"][0]
    assert "tool" in first and "driver" in first["tool"]
    assert "results" in first


def test_sarif_emits_result_per_finding() -> None:
    report = _sample_report()
    doc = json.loads(render_sarif(report))
    # One run per tool (mypy + ruff), each with one result.
    total_results = sum(len(run["results"]) for run in doc["runs"])
    assert total_results == sum(len(ev.findings) for ev in report.tool_evidence)


def test_export_sarif_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "report.sarif"
    result = export_sarif(_sample_report(), out)
    assert result == out
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_empty_report_still_produces_valid_sarif() -> None:
    report = AuditReport(summary=ReportSummary(verdict="insufficient_evidence"))
    doc = json.loads(render_sarif(report))
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "oida-code"
    assert doc["runs"][0]["results"] == []
