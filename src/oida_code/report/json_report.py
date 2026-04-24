"""Serialize an :class:`AuditReport` as canonical JSON."""

from __future__ import annotations

from pathlib import Path

from oida_code.models.audit_report import AuditReport


def render_json(report: AuditReport) -> str:
    """Return the deterministic ``indent=2`` JSON form of the report."""
    return report.model_dump_json(indent=2)


def write_json_report(report: AuditReport, path: Path | str) -> Path:
    """Write the report JSON to ``path`` (UTF-8, trailing newline)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_json(report) + "\n", encoding="utf-8")
    return target


__all__ = ["render_json", "write_json_report"]
