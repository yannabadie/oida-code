"""Run the configured static type checker (default ``mypy``). Phase 2.

The module name intentionally mirrors blueprint §7; callers must use the
absolute ``oida_code.verify.typing`` path to avoid shadowing stdlib ``typing``.
"""

from __future__ import annotations


def run_type_check(request: object) -> object:  # pragma: no cover - phase 2
    raise NotImplementedError("verify.typing: blueprint §3 Pass 1 (mypy/pyright).")


__all__ = ["run_type_check"]
