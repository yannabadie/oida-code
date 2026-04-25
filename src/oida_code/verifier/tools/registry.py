"""Phase 4.2-A (QA/A18.md, ADR-27) — adapter registry."""

from __future__ import annotations

from oida_code.verifier.tools.adapters import (
    MypyAdapter,
    PytestAdapter,
    RuffAdapter,
    ToolAdapter,
)
from oida_code.verifier.tools.contracts import ToolName

_REGISTRY: dict[ToolName, type[ToolAdapter]] = {
    "ruff": RuffAdapter,
    "mypy": MypyAdapter,
    "pytest": PytestAdapter,
}


def get_adapter(name: ToolName) -> ToolAdapter:
    """Return a fresh adapter for ``name``. Phase 4.2 only ships
    ruff / mypy / pytest; semgrep / codeql adapters land in 4.2.x."""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"no adapter registered for tool {name!r}")
    return cls()


def supported_tools() -> tuple[ToolName, ...]:
    return tuple(_REGISTRY.keys())


__all__ = ["get_adapter", "supported_tools"]
