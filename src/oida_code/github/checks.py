"""Post OIDA verdicts as GitHub Check Runs. Phase 2+."""

from __future__ import annotations


def post_check(report: object) -> None:  # pragma: no cover - phase 2
    raise NotImplementedError("github.checks: blueprint §4 deployment mode 2.")


__all__ = ["post_check"]
