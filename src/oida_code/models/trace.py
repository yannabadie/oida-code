"""Trace schema: agent-action events + progress/no-progress segments.

Phase 2 ships the shapes. Phase 3 ships the Explore/Exploit *classification*
logic that assigns ``exploration_error`` / ``exploitation_error`` / ``stale``
to :class:`NoProgressSegment` (per ADR-15, classification moved out of P2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TraceEventKind = Literal[
    "tool_call",
    "read",
    "grep",
    "edit",
    "write",
    "test_run",
    "llm_call",
    "prompt",
    "diff",
    "commit",
    "other",
]

ProgressKind = Literal[
    "property_proved",
    "bug_located",
    "mutant_killed",
    "counterexample_found",
    "obligation_closed",
]

NoProgressClassification = Literal[
    "exploration_error",
    "exploitation_error",
    "stale",
    "unclassified",
]
"""``unclassified`` is the Phase 2 default; Phase 3 populates the real label."""


class TraceEvent(BaseModel):
    """One normalized agent action in a trace."""

    model_config = ConfigDict(extra="forbid")

    t: int = Field(ge=0)
    kind: TraceEventKind
    tool: str | None = None
    scope: list[str] = Field(default_factory=list)
    intent: str | None = None
    result: str | None = None
    new_facts: list[str] = Field(default_factory=list)
    closed_obligations: list[str] = Field(default_factory=list)
    opened_obligations: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ProgressEvent(BaseModel):
    """A trace action that reduced uncertainty or closed an obligation."""

    model_config = ConfigDict(extra="forbid")

    t: int = Field(ge=0)
    kind: ProgressKind
    obligation_id: str | None = None
    description: str


class NoProgressSegment(BaseModel):
    """A contiguous trace window with no reduction in uncertainty / obligations.

    Phase 2 populates ``start_t``, ``end_t``, and structural counters. The
    ``classification`` defaults to ``unclassified`` until Phase 3 wires the
    Explore/Exploit decision.
    """

    model_config = ConfigDict(extra="forbid")

    start_t: int = Field(ge=0)
    end_t: int = Field(ge=0)
    cycle_count: int = Field(default=0, ge=0)
    edge_reuse: int = Field(default=0, ge=0)
    node_reuse: int = Field(default=0, ge=0)
    classification: NoProgressClassification = "unclassified"


class Trace(BaseModel):
    """Top-level trace container for an audit run."""

    model_config = ConfigDict(extra="forbid")

    events: list[TraceEvent] = Field(default_factory=list)
    progress: list[ProgressEvent] = Field(default_factory=list)
    no_progress_segments: list[NoProgressSegment] = Field(default_factory=list)


__all__ = [
    "NoProgressClassification",
    "NoProgressSegment",
    "ProgressEvent",
    "ProgressKind",
    "Trace",
    "TraceEvent",
    "TraceEventKind",
]
