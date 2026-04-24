"""Claim extraction (blueprint §3 Pass 2).

**Phase 2 status**: subsumed by :mod:`oida_code.extract.obligations`. Each
:class:`~oida_code.models.obligation.Obligation` produced by that extractor
is the Phase-2 representation of a claim: a testable commitment with an
``evidence_required`` list. The structural "claim vs precondition vs
invariant" tripartition from the blueprint becomes Phase 3 work when we add
the invariant + security_rule + observability extractors (ADR-15).

Keeping the module stub here preserves the blueprint's public API surface
for future phases without duplicating extraction logic in Phase 2.
"""

from __future__ import annotations

from pathlib import Path

from oida_code.extract.obligations import extract_obligations
from oida_code.models.obligation import Obligation


def extract_claims(repo_path: Path | str, changed_files: list[str]) -> list[Obligation]:
    """Delegate to :func:`extract_obligations` (Phase 2).

    Phase 3+ will split claims out as a distinct model with semantic anchors
    (intent parse, docstring NLI). For Phase 2 the extractor-produced
    obligations are the canonical claim set.
    """
    return extract_obligations(repo_path, changed_files)


__all__ = ["extract_claims"]
