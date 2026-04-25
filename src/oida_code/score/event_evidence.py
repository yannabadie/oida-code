"""E3.0 (QA/A14.md, ADR-24) — per-event deterministic evidence view.

Bridges :class:`~oida_code.models.evidence.ToolEvidence` (scenario-wide
runner outputs) into per-event signals so that
:class:`~oida_code.models.normalized_event.NormalizedEvent` can carry
**differentiated** ``completion`` / ``tests_pass`` / ``operator_accept``
values, not the uniform scenario-average that the v0.4.x baseline
emitted everywhere.

This module is **deterministic and side-effect free**. It does NOT call
an LLM, does NOT modify the vendored core, and does NOT promote any
field to authoritative. It is the foundation E3.1+ builds on.

Honesty rules (ADR-13 + ADR-22 + ADR-24):

* ``pytest`` global green is a **weak** positive — it does NOT
  auto-close obligation sub-preconditions like ``negative_path_tested``
  or ``rollback_or_idempotency_checked``. Block B (ADR-20) avoided that
  collapse and we don't recreate it here.
* Missing tool (``status="tool_missing"``) is **missing**, not failure.
* Tool error (``status="error"``) raises a per-event uncertainty
  warning; it does not punish the event.
* An event with NO scope match in any tool view falls under
  ``source="missing"`` — it does NOT inherit a fake-green signal from
  unrelated test runs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.models.normalized_event import NormalizedEvent, NormalizedScenario

EvidenceSource = Literal["tool", "heuristic", "missing"]


class EventEvidenceView(BaseModel):
    """Per-event slice of deterministic tool evidence.

    Frozen + extra=forbid so a downstream estimator cannot mutate it
    after the linker has produced it.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    event_id: str
    scope: tuple[str, ...]

    ruff_findings: tuple[Finding, ...] = ()
    mypy_findings: tuple[Finding, ...] = ()
    semgrep_findings: tuple[Finding, ...] = ()
    codeql_findings: tuple[Finding, ...] = ()

    pytest_relevant: bool = Field(
        default=False,
        description=(
            "True when at least one test path in the audit surface "
            "matches this event's scope (basename / suffix match)."
        ),
    )
    pytest_passed: bool | None = Field(
        default=None,
        description=(
            "Result of the relevant tests (None = no relevant test "
            "found; True = the relevant test passed; False = it failed)."
        ),
    )
    pytest_global_passed: bool | None = Field(
        default=None,
        description=(
            "True if pytest ran globally with zero failures+errors. "
            "Used as a WEAK positive only."
        ),
    )

    ruff_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"
    mypy_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"
    pytest_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"

    source: EvidenceSource = "missing"
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Scope match — same heuristic as `_scope_matches_file` in mapper.py but
# kept private here so module is self-contained.
# ---------------------------------------------------------------------------


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _scope_matches_path(event_scope: tuple[str, ...], path: str) -> bool:
    """Loose match between an event's scope tuple and a file path.

    Returns True when any scope entry equals the path, is a trailing
    component of it, or shares the same basename. Mirrors the
    ``_scope_matches_file`` logic in :mod:`oida_code.score.mapper`.
    """
    file_norm = _normalize_path(path)
    if not file_norm:
        return False
    for scope in event_scope:
        scope_norm = _normalize_path(scope)
        if not scope_norm:
            continue
        if scope_norm == file_norm:
            return True
        if file_norm.endswith("/" + scope_norm):
            return True
        if scope_norm.endswith("/" + file_norm):
            return True
        # ``module::symbol`` form — left half is the path hint.
        left = scope_norm.split("::", 1)[0]
        if left and (file_norm.endswith("/" + left) or left == file_norm):
            return True
    return False


def _findings_for_event(
    evidence: ToolEvidence | None,
    event_scope: tuple[str, ...],
) -> tuple[Finding, ...]:
    if evidence is None or evidence.status != "ok":
        return ()
    return tuple(
        f for f in evidence.findings
        if _scope_matches_path(event_scope, f.path)
    )


def _find_evidence(
    tool_evidence: list[ToolEvidence] | None,
    name: str,
) -> ToolEvidence | None:
    if not tool_evidence:
        return None
    for ev in tool_evidence:
        if ev.tool == name:
            return ev
    return None


def _tool_status(
    evidence: ToolEvidence | None,
) -> Literal["ok", "tool_missing", "error", "skipped"]:
    if evidence is None or evidence.status == "tool_missing":
        return "tool_missing"
    if evidence.status == "ok":
        return "ok"
    if evidence.status == "skipped":
        return "skipped"
    # timeout / error → unified "error" for view-level reasoning.
    return "error"


def _scope_for_event(event: NormalizedEvent) -> tuple[str, ...]:
    """Best-effort scope tuple for an event.

    The ``NormalizedEvent`` doesn't store scope explicitly; we use the
    event's ``task`` and ``pattern_id`` heuristically. The mapper's
    callers should pass an explicit scope override when available
    (E3.0 — the scoring driver knows the obligation that produced the
    event).
    """
    parts: list[str] = []
    if event.task:
        # Tasks often start with "<file>: <message>"
        head = event.task.split(":", 1)[0].strip()
        if head:
            parts.append(head)
    return tuple(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_event_evidence_view(
    scenario: NormalizedScenario,
    tool_evidence: list[ToolEvidence] | None,
    *,
    event_scopes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, EventEvidenceView]:
    """Return one :class:`EventEvidenceView` per event in ``scenario``.

    ``event_scopes`` overrides the inferred scope per event id — the
    scoring driver (mapper) supplies the obligation's scope here so the
    scope match is exact rather than parsed from ``task``.
    """
    ruff_ev = _find_evidence(tool_evidence, "ruff")
    mypy_ev = _find_evidence(tool_evidence, "mypy")
    pytest_ev = _find_evidence(tool_evidence, "pytest")
    semgrep_ev = _find_evidence(tool_evidence, "semgrep")
    codeql_ev = _find_evidence(tool_evidence, "codeql")

    pytest_global = _pytest_global_passed(pytest_ev)

    out: dict[str, EventEvidenceView] = {}
    for event in scenario.events:
        scope = (event_scopes or {}).get(event.id) or _scope_for_event(event)
        ruff_findings = _findings_for_event(ruff_ev, scope)
        mypy_findings = _findings_for_event(mypy_ev, scope)
        semgrep_findings = _findings_for_event(semgrep_ev, scope)
        codeql_findings = _findings_for_event(codeql_ev, scope)

        # pytest_relevant: at least one finding/path in pytest evidence
        # touches this event's scope. We don't (yet) know test paths
        # without test discovery — Phase 4 will improve this. For now
        # we treat the pytest evidence's finding list (which carries the
        # failing test paths if any) and any global pytest counts as
        # the only signals.
        pytest_relevant_findings = _findings_for_event(pytest_ev, scope)
        pytest_relevant = bool(pytest_relevant_findings)
        pytest_passed: bool | None
        if pytest_relevant:
            # If a relevant pytest finding exists and is an error/regression,
            # the relevant test failed.
            pytest_passed = not any(
                f.severity in ("error", "warning") for f in pytest_relevant_findings
            )
        else:
            pytest_passed = None

        warnings: list[str] = []
        if ruff_ev is not None and ruff_ev.status not in ("ok", "tool_missing"):
            warnings.append(f"ruff status={ruff_ev.status}: uncertainty added")
        if mypy_ev is not None and mypy_ev.status not in ("ok", "tool_missing"):
            warnings.append(f"mypy status={mypy_ev.status}: uncertainty added")
        if pytest_ev is not None and pytest_ev.status not in ("ok", "tool_missing"):
            warnings.append(f"pytest status={pytest_ev.status}: uncertainty added")

        # Source classification:
        # * "tool"      — at least one tool returned status=ok and the event's
        #                 scope intersected its findings (ruff/mypy/semgrep/codeql)
        #                 OR pytest is relevant
        # * "heuristic" — at least one tool ran ok globally but no finding/test
        #                 touched this event's scope
        # * "missing"   — every tool we asked is tool_missing or no tool_evidence
        any_tool_ok = any(
            ev is not None and ev.status == "ok"
            for ev in (ruff_ev, mypy_ev, pytest_ev, semgrep_ev, codeql_ev)
        )
        any_finding_for_event = bool(
            ruff_findings or mypy_findings or semgrep_findings
            or codeql_findings or pytest_relevant
        )
        source: EvidenceSource
        if any_finding_for_event:
            source = "tool"
        elif any_tool_ok:
            source = "heuristic"
        else:
            source = "missing"

        out[event.id] = EventEvidenceView(
            event_id=event.id,
            scope=scope,
            ruff_findings=ruff_findings,
            mypy_findings=mypy_findings,
            semgrep_findings=semgrep_findings,
            codeql_findings=codeql_findings,
            pytest_relevant=pytest_relevant,
            pytest_passed=pytest_passed,
            pytest_global_passed=pytest_global,
            ruff_status=_tool_status(ruff_ev),
            mypy_status=_tool_status(mypy_ev),
            pytest_status=_tool_status(pytest_ev),
            source=source,
            warnings=tuple(warnings),
        )
    return out


def _pytest_global_passed(ev: ToolEvidence | None) -> bool | None:
    if ev is None or ev.status != "ok":
        return None
    counts = ev.counts
    total = int(counts.get("total", 0))
    if total <= 0:
        return None
    failures = int(counts.get("failure", 0)) + int(counts.get("error", 0))
    return failures == 0


# ---------------------------------------------------------------------------
# Per-event signal helpers — derived directly from EventEvidenceView
# ---------------------------------------------------------------------------


def event_operator_accept_from_view(view: EventEvidenceView) -> float:
    """Ruff + mypy mapped to ``operator_accept`` for one event.

    Findings on the event's scope reduce ``operator_accept`` linearly
    (fraction of error severities, capped at 50 errors → 0.0). Missing
    tools return the neutral ``0.5`` so we never punish an event for
    something we couldn't measure.
    """
    statuses = (view.ruff_status, view.mypy_status)
    if all(s == "tool_missing" for s in statuses):
        return 0.5
    if all(s != "ok" for s in statuses):
        # Both tools either errored or were skipped — uncertainty.
        return 0.5
    score = 0.0
    counted = 0
    for status, findings in (
        (view.ruff_status, view.ruff_findings),
        (view.mypy_status, view.mypy_findings),
    ):
        if status != "ok":
            continue
        counted += 1
        errors = sum(1 for f in findings if f.severity == "error")
        if errors == 0:
            score += 1.0
        else:
            score += max(0.0, 1.0 - min(1.0, errors / 50.0))
    if counted == 0:
        return 0.5
    return round(score / counted, 6)


def event_completion_from_view(view: EventEvidenceView) -> float:
    """pytest evidence mapped to ``completion`` for one event.

    Tiered:

    * relevant test that failed → 0.2 (real negative signal)
    * relevant test that passed → 0.95 (strong positive)
    * no relevant test, pytest global green → 0.8 (weak positive)
    * no relevant test, pytest global failed → 0.5 + warning (uncertainty
      — this event isn't covered by the failing tests but we shouldn't
      claim completion either)
    * pytest tool_missing → 0.5 (missing, neutral)
    """
    if view.pytest_status == "tool_missing":
        return 0.5
    if view.pytest_status != "ok":
        return 0.5  # error/skipped → neutral with warning recorded
    if view.pytest_relevant:
        return 0.95 if view.pytest_passed else 0.2
    if view.pytest_global_passed is True:
        return 0.8
    if view.pytest_global_passed is False:
        return 0.5
    return 0.5


def event_tests_pass_from_view(view: EventEvidenceView) -> float:
    """Weighted blend of completion + property/mutation placeholders.

    Phase-2 runners (hypothesis, mutmut) ship as placeholders here per
    the existing scenario-level helper. When their per-event wiring
    arrives, this function gains those terms.
    """
    regression = event_completion_from_view(view)
    property_score = 0.5  # TODO(phase2): per-event hypothesis counts
    mutation_score = 0.5  # TODO(phase2): per-event mutmut counts
    return round(
        0.50 * regression + 0.25 * property_score + 0.25 * mutation_score, 6
    )


__all__ = [
    "EventEvidenceView",
    "EvidenceSource",
    "build_event_evidence_view",
    "event_completion_from_view",
    "event_operator_accept_from_view",
    "event_tests_pass_from_view",
]
