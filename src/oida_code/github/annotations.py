"""Convert critical findings into inline PR annotations. Phase 2+."""

from __future__ import annotations


def emit_annotations(report: object) -> list[object]:  # pragma: no cover - phase 2
    raise NotImplementedError("github.annotations: blueprint §9 critical_findings.")


__all__ = ["emit_annotations"]
