"""Phase 6.e front-door diagnostic CLI and Markdown guards."""

from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.models.audit_report import (
    AuditReport,
    RepairPlan,
    ReportSummary,
    VerdictLabel,
)
from oida_code.report.markdown_report import render_markdown
from tests.conftest import REPO_ROOT

runner = CliRunner(env={"COLUMNS": "200"})
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

_MAPPING: dict[VerdictLabel, str] = {
    "verified": "No contradiction observed by configured deterministic checks",
    "counterexample_found": "Contradicted by deterministic evidence",
    "insufficient_evidence": "Evidence gap remains",
    "corrupt_success": "Success evidence conflicts with critical findings",
}
_RAW_LEGACY_LABELS = (
    "verified",
    "counterexample_found",
    "insufficient_evidence",
    "corrupt_success",
)
_FORBIDDEN_HUMAN_OUTPUT = (
    "**Verdict:**",
    "# OIDA Code Audit",
    "## Repair plan",
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
)


def _plain(text: str) -> str:
    return _ANSI_CSI_RE.sub("", text)


def _report(verdict: VerdictLabel) -> AuditReport:
    return AuditReport(
        summary=ReportSummary(verdict=verdict),
        repair=RepairPlan(
            reopen=["E.old"],
            audit=["E.tool"],
            next_prompts=["Inspect the cited tool output before deciding."],
        ),
    )


def test_front_door_markdown_maps_legacy_verdicts_without_raw_status_labels() -> None:
    for verdict, expected in _MAPPING.items():
        rendered = render_markdown(_report(verdict))
        status_section = rendered.split("## Summary", maxsplit=1)[0]

        assert rendered.startswith("# OIDA Code Diagnostic Report")
        assert "Diagnostic only - not a merge decision" in rendered
        assert expected in rendered
        assert "## Human follow-up checklist" in rendered
        for forbidden in _FORBIDDEN_HUMAN_OUTPUT:
            assert forbidden not in rendered
        for raw in _RAW_LEGACY_LABELS:
            assert raw not in status_section


def test_front_door_json_still_preserves_legacy_schema_values() -> None:
    report = _report("verified")
    payload = json.loads(report.model_dump_json())

    assert payload["summary"]["verdict"] == "verified"
    assert "No contradiction observed" not in report.model_dump_json()


def test_top_level_help_is_diagnostic_not_product_verdict_language() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    plain = _plain(result.output)
    assert "Diagnostic evidence for Python code reviewers" in plain
    assert "not a merge decision" in plain
    assert "AI code verifier" not in plain
    assert "guaranteed behavior" not in plain


def test_audit_help_pins_markdown_as_diagnostic_only() -> None:
    result = runner.invoke(app, ["audit", "--help"])

    assert result.exit_code == 0, result.output
    plain = _plain(result.output)
    assert "deterministic diagnostic review" in plain
    assert "Diagnostic only" in plain
    assert "markdown is diagnostic-only" in plain
    assert "JSON preserves the legacy schema" in plain
    assert "not a merge decision" in plain


def test_repair_help_is_visible_but_quarantined_as_compatibility_stub() -> None:
    result = runner.invoke(app, ["repair", "--help"])

    assert result.exit_code == 0, result.output
    plain = _plain(result.output)
    assert "Compatibility stub for legacy follow-up records" in plain
    assert "Not a front-door path" in plain
    assert "does not modify code" in plain
    assert "double-loop" not in plain.lower()
    assert "LLM repair prompts" not in plain


def test_phase6e_report_records_scope_flags() -> None:
    report = json.loads(
        (
            REPO_ROOT
            / "reports"
            / "phase6_e_front_door_diagnostic_cli"
            / "report.json"
        ).read_text(encoding="utf-8")
    )

    assert report["front_door_renderer_changed"] is True
    assert report["json_schema_changed"] is False
    assert report["sarif_schema_changed"] is False
    assert report["alias_added"] is False
    assert report["provider_call_used"] is False
    assert report["direct_provider_call"] is False
    assert report["corpus_index_changed"] is False
    assert report["runtime_gateway_default_changed"] is False
    assert report["mcp_runtime_changed"] is False
    assert report["clone_helper_changed"] is False
    assert report["github_action_changed"] is False
    assert report["markdown_mapping"] == {
        "verified": (
            "No contradiction observed by configured deterministic checks "
            "(diagnostic only; not proof of correctness)"
        ),
        "counterexample_found": (
            "Contradicted by deterministic evidence (human review required)"
        ),
        "insufficient_evidence": "Evidence gap remains (human review required)",
        "corrupt_success": (
            "Success evidence conflicts with critical findings "
            "(human review required)"
        ),
    }
