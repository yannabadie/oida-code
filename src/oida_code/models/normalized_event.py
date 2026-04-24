"""Pydantic v2 model for the normalized OIDA event scenario (blueprint §5 B).

Mirrors the dataclass schema consumed by the vendored ``OIDAAnalyzer`` at
``oida_code._vendor.oida_framework.analyzer``. The mapper
(:mod:`oida_code.score.mapper`, phase 2) converts between this Pydantic surface
and the vendored dataclass surface.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PreconditionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    weight: float = Field(gt=0.0)
    verified: bool


class NormalizedEvent(BaseModel):
    """One event in the deterministic-scorer input trace.

    All unit-interval fields are bounded to ``[0, 1]`` to match the vendored
    ``Event.from_dict`` validation.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    pattern_id: str
    task: str
    capability: float = Field(ge=0.0, le=1.0)
    reversibility: float = Field(ge=0.0, le=1.0)
    observability: float = Field(ge=0.0, le=1.0)
    blast_radius: float = Field(ge=0.0, le=1.0)
    completion: float = Field(ge=0.0, le=1.0)
    tests_pass: float = Field(ge=0.0, le=1.0)
    operator_accept: float = Field(ge=0.0, le=1.0)
    benefit: float = Field(ge=0.0, le=1.0)
    preconditions: list[PreconditionSpec]
    constitutive_parents: list[str] = Field(default_factory=list)
    supportive_parents: list[str] = Field(default_factory=list)
    invalidates_pattern: bool = False


class ScenarioConfig(BaseModel):
    """Optional per-scenario overrides for :class:`AnalyzerConfig` defaults."""

    model_config = ConfigDict(extra="allow")

    alpha_b: float | None = None
    confirm_threshold: float | None = None
    bias_threshold: float | None = None
    tau_ref: float | None = None


class NormalizedScenario(BaseModel):
    """Top-level input consumed by the deterministic OIDA scorer."""

    model_config = ConfigDict(extra="forbid")

    name: str = "unnamed_scenario"
    description: str = ""
    config: ScenarioConfig = Field(default_factory=ScenarioConfig)
    events: list[NormalizedEvent]


__all__ = [
    "NormalizedEvent",
    "NormalizedScenario",
    "PreconditionSpec",
    "ScenarioConfig",
]
