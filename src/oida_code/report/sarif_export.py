"""Export tool evidence as a SARIF 2.1.0 document.

We emit the minimum set of fields GitHub code-scanning accepts:
``version``, ``$schema``, ``runs[].tool.driver.{name,version,rules}``, and
``runs[].results[]``. Full SARIF compliance (threadFlows, codeFlows, taxonomies)
is a Phase 7 polish task.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from oida_code import __version__
from oida_code.models.audit_report import AuditReport
from oida_code.models.evidence import Finding, Severity, ToolEvidence

_SARIF_VERSION = "2.1.0"
_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)


def _sarif_level(severity: Severity) -> str:
    # SARIF levels: "error" | "warning" | "note" | "none".
    if severity == "error":
        return "error"
    if severity == "warning":
        return "warning"
    return "note"


def _location(finding: Finding) -> dict[str, Any]:
    region: dict[str, Any] = {}
    if finding.line:
        region["startLine"] = finding.line
    if finding.column:
        region["startColumn"] = finding.column
    physical: dict[str, Any] = {
        "artifactLocation": {"uri": finding.path or ""},
    }
    if region:
        physical["region"] = region
    return {"physicalLocation": physical}


def _rules_for_tool(findings: list[Finding]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for f in findings:
        if f.rule_id in seen:
            continue
        seen[f.rule_id] = {
            "id": f.rule_id,
            "name": f.rule_id,
            "shortDescription": {"text": f.rule_id},
            "defaultConfiguration": {"level": _sarif_level(f.severity)},
        }
    return list(seen.values())


def _run_for_tool(tool: str, evidence_list: list[ToolEvidence]) -> dict[str, Any]:
    all_findings: list[Finding] = []
    versions: set[str] = set()
    for ev in evidence_list:
        all_findings.extend(ev.findings)
        if ev.tool_version:
            versions.add(ev.tool_version)
    driver: dict[str, Any] = {
        "name": tool,
        "informationUri": "https://github.com/yannabadie/oida-code",
        "rules": _rules_for_tool(all_findings),
    }
    if versions:
        driver["version"] = sorted(versions)[0]
    results = [
        {
            "ruleId": f.rule_id,
            "level": _sarif_level(f.severity),
            "message": {"text": f.message or f.rule_id},
            "locations": [_location(f)],
        }
        for f in all_findings
    ]
    return {"tool": {"driver": driver}, "results": results}


def render_sarif(report: AuditReport) -> str:
    """Return the SARIF 2.1.0 JSON string for ``report``."""
    per_tool: dict[str, list[ToolEvidence]] = defaultdict(list)
    for ev in report.tool_evidence:
        per_tool[ev.tool].append(ev)

    runs = [_run_for_tool(tool, evs) for tool, evs in sorted(per_tool.items())]
    if not runs:
        # Keep SARIF structurally valid even without evidence.
        runs = [
            {
                "tool": {"driver": {"name": "oida-code", "version": __version__, "rules": []}},
                "results": [],
            }
        ]

    doc = {
        "version": _SARIF_VERSION,
        "$schema": _SARIF_SCHEMA,
        "runs": runs,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


def export_sarif(report: AuditReport, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_sarif(report) + "\n", encoding="utf-8")
    return target


__all__ = ["export_sarif", "render_sarif"]
