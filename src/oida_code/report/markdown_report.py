"""Render the :class:`AuditReport` as Markdown for PR annotations. Phase 2."""

from __future__ import annotations


def render_markdown(report: object) -> str:  # pragma: no cover - phase 2
    raise NotImplementedError("report.markdown_report: blueprint §4 GitHub Action.")


__all__ = ["render_markdown"]
