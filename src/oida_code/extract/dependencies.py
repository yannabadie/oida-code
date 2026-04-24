"""Dependency-graph construction for OIDA ``constitutive_parents`` /
``supportive_parents`` edges (blueprint §5 B).

**Phase 2 status**: stub — returns empty edge sets. The Phase-2 mapper
emits events with empty ``constitutive_parents`` / ``supportive_parents``
lists (documented in :mod:`oida_code.score.mapper`'s default-origin table),
which degrades the vendored analyzer's propagation logic to a single-event
view. This is an explicit ADR-15 trade-off: shipping a wrong dependency
graph produces confidently-wrong V_net; shipping an empty one produces
honestly-incomplete V_net.

Real implementation (Phase 3+):

* parse imports and function calls across changed files
* mark causally-required edges as ``constitutive_parents``
* mark reused helpers / fixtures as ``supportive_parents``
"""

from __future__ import annotations

from pathlib import Path

from oida_code.models.obligation import Obligation


def build_dependency_graph(
    repo_path: Path | str,
    changed_files: list[str],
    obligations: list[Obligation],
) -> dict[str, dict[str, list[str]]]:
    """Return an empty dependency graph for Phase 2.

    Shape matches the Phase-3 target so callers can opt in without rewrite:
    ``{obligation_id: {"constitutive": [...], "supportive": [...]}}``.
    """
    del repo_path, changed_files  # unused in Phase 2
    return {ob.id: {"constitutive": [], "supportive": []} for ob in obligations}


__all__ = ["build_dependency_graph"]
