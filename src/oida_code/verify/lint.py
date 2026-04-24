"""Run the configured linter (default ``ruff``). Phase 2."""

from __future__ import annotations


def run_lint(request: object) -> object:  # pragma: no cover - phase 2
    raise NotImplementedError("verify.lint: blueprint §3 Pass 1 (ruff/pylint/flake8).")


__all__ = ["run_lint"]
