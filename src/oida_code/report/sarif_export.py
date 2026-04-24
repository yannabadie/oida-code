"""Export critical findings as SARIF for IDE/GitHub code-scanning. Phase 2+."""

from __future__ import annotations


def export_sarif(report: object, path: object) -> None:  # pragma: no cover - phase 2
    raise NotImplementedError("report.sarif_export: SARIF 2.1.0 for GitHub code-scanning.")


__all__ = ["export_sarif"]
