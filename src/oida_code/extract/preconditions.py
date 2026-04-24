"""Precondition extraction (blueprint §6).

**Phase 2 status**: subsumed by :mod:`oida_code.extract.obligations`. The
``precondition`` kind of :class:`~oida_code.models.obligation.Obligation`
is produced by the AST walks for ``assert``, ``if+raise`` guards, and
validator decorators. This module re-exports a filtered view so callers
that want *only* preconditions have a stable entry point.
"""

from __future__ import annotations

from pathlib import Path

from oida_code.extract.obligations import extract_obligations
from oida_code.models.obligation import Obligation


def extract_preconditions(repo_path: Path | str, changed_files: list[str]) -> list[Obligation]:
    """Return only the ``precondition``-kind obligations for ``changed_files``."""
    return [o for o in extract_obligations(repo_path, changed_files) if o.kind == "precondition"]


__all__ = ["extract_preconditions"]
