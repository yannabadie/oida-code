"""First-class :class:`Obligation` schema (PLAN.md §8, Phase 2 keystone).

An ``Obligation`` is a **testable commitment** the change MUST satisfy.
Phase 2 ships **three** extractor-backed kinds plus **three** stubs:

* ``precondition`` — AST-detected (``assert``, ``if not x: raise``,
  ``@field_validator``, ``@validates``).
* ``api_contract`` — AST-detected (``@app.route``, ``@router.(get|post|…)``).
* ``migration``    — path markers (reuses ``extract.blast_radius``'s
  ``_DATA_MARKERS``).
* ``invariant`` | ``security_rule`` | ``observability`` — schema only; the
  extractor emits nothing for them in Phase 2 (ADR-15). Real extraction
  is Phase 3+.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.models.evidence import EvidenceKind

ObligationKind = Literal[
    "precondition",
    "api_contract",
    "migration",
    "invariant",
    "security_rule",
    "observability",
]

ObligationStatus = Literal["open", "closed", "violated"]

ObligationSource = Literal["diff", "intent", "extracted", "synthetic"]


class EvidenceRequirement(BaseModel):
    """What kind of proof would satisfy an :class:`Obligation`."""

    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    description: str


class Obligation(BaseModel):
    """One testable commitment tied to the change under audit."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^o-[0-9A-Za-z_-]+$")
    kind: ObligationKind
    scope: str
    description: str
    evidence_required: list[EvidenceRequirement] = Field(default_factory=list)
    status: ObligationStatus = "open"
    source: ObligationSource = "extracted"
    weight: int = Field(default=1, ge=1)


__all__ = [
    "EvidenceRequirement",
    "Obligation",
    "ObligationKind",
    "ObligationSource",
    "ObligationStatus",
]
