"""Translate between Pydantic ``NormalizedScenario`` and vendored ``Scenario``.

Phase 2 deliverable. Two responsibilities:

1. **Round-trip**: ``pydantic_to_vendored`` / ``vendored_to_pydantic`` so the
   public Pydantic surface and the vendored dataclass core agree byte-for-byte
   on the OIDA event schema.
2. **Synthesis**: ``obligations_to_scenario`` turns a list of
   :class:`Obligation` + Phase-1 :class:`ToolEvidence` into a
   :class:`NormalizedScenario` ready to feed :class:`OIDAAnalyzer`.

Advisor-mandated transparency: which OIDA event fields are derived from
real signal vs. held at a fixed default until later phases.

+------------------------+--------------------------------------------------+
| Field                  | Phase 2 source                                   |
+========================+==================================================+
| ``pattern_id``         | synthesized from ``obligation.kind`` + scope hash |
| ``task``               | ``obligation.description`` (truncated)           |
| ``capability``         | **default 0.5** (Phase 4 LLM fills from intent)  |
| ``reversibility``      | heuristic ``1 − data_signal(scope)``             |
| ``observability``      | **default 0.5** (Phase 4 uses test-file presence)|
| ``blast_radius``       | Phase 1 :func:`estimate_blast_radius`            |
| ``completion``         | pytest pass-ratio from evidence, default 0.5     |
| ``tests_pass``         | ``0.50·regression + 0.25·property + 0.25·mutation`` |
| ``operator_accept``    | lint + types green from evidence                 |
| ``benefit``            | **default 0.5** (Phase 4 LLM from intent)        |
| ``preconditions``      | from obligation graph (one ``PreconditionSpec``  |
|                        | per Obligation)                                  |
| ``constitutive_parents`` | empty in P2 (dependency extractor is P2 too,   |
|                        | but graph topology becomes real in Phase 3)      |
+------------------------+--------------------------------------------------+

The cells marked **default** are load-bearing for the ADR-13 decision to
emit ``null`` instead of ``0.0`` on fusion fields: downstream readers of a
Phase-2 report must understand that e.g. a ``V_net`` computed with
``capability=0.5`` everywhere is structurally incomplete, not a real signal.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from oida_code._vendor.oida_framework.models import (
    Event as VendoredEvent,
)
from oida_code._vendor.oida_framework.models import (
    Precondition as VendoredPrecondition,
)
from oida_code._vendor.oida_framework.models import (
    Scenario as VendoredScenario,
)
from oida_code.extract.blast_radius import estimate_blast_radius
from oida_code.models.audit_request import AuditRequest
from oida_code.models.evidence import ToolEvidence
from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
    ScenarioConfig,
)
from oida_code.models.obligation import Obligation

_PATTERN_ID_CLEAN = re.compile(r"[^a-zA-Z0-9_]+")


# ---------------------------------------------------------------------------
# Round-trip: Pydantic <-> vendored dataclass
# ---------------------------------------------------------------------------


def _precondition_to_vendored(pre: PreconditionSpec) -> VendoredPrecondition:
    return VendoredPrecondition(name=pre.name, weight=float(pre.weight), verified=pre.verified)


def _precondition_from_vendored(pre: VendoredPrecondition) -> PreconditionSpec:
    return PreconditionSpec(name=pre.name, weight=pre.weight, verified=pre.verified)


def _event_to_vendored(ev: NormalizedEvent) -> VendoredEvent:
    return VendoredEvent(
        id=ev.id,
        pattern_id=ev.pattern_id,
        task=ev.task,
        capability=ev.capability,
        reversibility=ev.reversibility,
        observability=ev.observability,
        blast_radius=ev.blast_radius,
        completion=ev.completion,
        tests_pass=ev.tests_pass,
        operator_accept=ev.operator_accept,
        benefit=ev.benefit,
        preconditions=[_precondition_to_vendored(p) for p in ev.preconditions],
        constitutive_parents=list(ev.constitutive_parents),
        supportive_parents=list(ev.supportive_parents),
        invalidates_pattern=ev.invalidates_pattern,
    )


def _event_from_vendored(ev: VendoredEvent) -> NormalizedEvent:
    return NormalizedEvent(
        id=ev.id,
        pattern_id=ev.pattern_id,
        task=ev.task,
        capability=ev.capability,
        reversibility=ev.reversibility,
        observability=ev.observability,
        blast_radius=ev.blast_radius,
        completion=ev.completion,
        tests_pass=ev.tests_pass,
        operator_accept=ev.operator_accept,
        benefit=ev.benefit,
        preconditions=[_precondition_from_vendored(p) for p in ev.preconditions],
        constitutive_parents=list(ev.constitutive_parents),
        supportive_parents=list(ev.supportive_parents),
        invalidates_pattern=ev.invalidates_pattern,
    )


def pydantic_to_vendored(scenario: NormalizedScenario) -> VendoredScenario:
    """Convert a Pydantic :class:`NormalizedScenario` to the vendored form."""
    config_dict: dict[str, float] = {}
    raw = scenario.config.model_dump(exclude_none=True)
    for key, value in raw.items():
        if isinstance(value, (int, float)):
            config_dict[key] = float(value)
    return VendoredScenario(
        name=scenario.name,
        description=scenario.description,
        config=config_dict,
        events=[_event_to_vendored(ev) for ev in scenario.events],
    )


def vendored_to_pydantic(scenario: VendoredScenario) -> NormalizedScenario:
    """Convert a vendored dataclass :class:`Scenario` back to Pydantic."""
    return NormalizedScenario(
        name=scenario.name,
        description=scenario.description,
        config=ScenarioConfig(**{k: v for k, v in scenario.config.items()}),
        events=[_event_from_vendored(ev) for ev in scenario.events],
    )


# ---------------------------------------------------------------------------
# Synthesis: Obligations + evidence -> NormalizedScenario
# ---------------------------------------------------------------------------


def _pattern_id_for(obligation: Obligation) -> str:
    slug = _PATTERN_ID_CLEAN.sub("_", obligation.scope)[:40].strip("_").lower()
    digest = hashlib.sha1(obligation.scope.encode("utf-8")).hexdigest()[:6]
    return f"p_{obligation.kind}_{slug}_{digest}"


def _data_signal_for_scope(scope: str) -> float:
    """Reuse the Phase 1 blast-radius signal to estimate scope-specific data risk."""
    return estimate_blast_radius([scope])


def _find_evidence(tool_evidence: list[ToolEvidence] | None, tool: str) -> ToolEvidence | None:
    if not tool_evidence:
        return None
    for ev in tool_evidence:
        if ev.tool == tool:
            return ev
    return None


def _completion_from_evidence(tool_evidence: list[ToolEvidence] | None) -> float:
    pytest_ev = _find_evidence(tool_evidence, "pytest")
    if pytest_ev is None or pytest_ev.status != "ok":
        return 0.5
    counts = pytest_ev.counts
    total = int(counts.get("total", 0))
    failures = int(counts.get("failure", 0)) + int(counts.get("error", 0))
    if total <= 0:
        # No tests collected ⇒ cannot measure completion; use the neutral default.
        return 0.5
    passed = max(0, total - failures)
    return round(passed / total, 6)


def _tests_pass_from_evidence(tool_evidence: list[ToolEvidence] | None) -> float:
    # Weighted: 0.50·regression + 0.25·property + 0.25·mutation. Property +
    # mutation ship in Phase 2 runners that may also report tool_missing, in
    # which case their weight collapses to 0 and the regression term normalises.
    regression = _completion_from_evidence(tool_evidence)
    property_score = 0.5  # TODO(phase2): wire hypothesis_runner counts
    mutation_score = 0.5  # TODO(phase2): wire mutmut_runner counts
    return round(
        0.50 * regression + 0.25 * property_score + 0.25 * mutation_score, 6
    )


def _operator_accept_from_evidence(tool_evidence: list[ToolEvidence] | None) -> float:
    # Crude but transparent: fraction of (ruff, mypy) that are ok + zero errors.
    if not tool_evidence:
        return 0.5
    score = 0.0
    checked = 0
    for tool in ("ruff", "mypy"):
        ev = _find_evidence(tool_evidence, tool)
        if ev is None or ev.status != "ok":
            continue
        checked += 1
        errors = int(ev.counts.get("error", 0))
        score += 1.0 if errors == 0 else max(0.0, 1.0 - min(1.0, errors / 50.0))
    if checked == 0:
        return 0.5
    return round(score / checked, 6)


def _preconditions_for(obligation: Obligation) -> list[PreconditionSpec]:
    return [
        PreconditionSpec(
            name=obligation.description[:120] or f"{obligation.kind}:{obligation.scope}",
            weight=float(obligation.weight),
            verified=obligation.status == "closed",
        )
    ]


# ---------------------------------------------------------------------------
# Evidence linker (ADR-13 / Phase-2 grounding bootstrap)
# ---------------------------------------------------------------------------


def _scope_matches_file(scope: str, file_path: str) -> bool:
    """Loose match: scope equals the path, is a suffix of it, or shares its stem.

    Obligation scopes are free-form strings (``module::function`` or a path or a
    glob-ish marker). For linking we only need a conservative overlap — exact
    path, trailing-component match, or same basename.
    """
    if not scope or not file_path:
        return False
    scope_norm = scope.replace("\\", "/").lstrip("./")
    file_norm = file_path.replace("\\", "/").lstrip("./")
    if scope_norm == file_norm:
        return True
    if file_norm.endswith("/" + scope_norm) or scope_norm.endswith("/" + file_norm):
        return True
    # module::symbol form — take the left half as the path hint.
    left = scope_norm.split("::", 1)[0]
    if left and (file_norm.endswith("/" + left) or left == file_norm):
        return True
    return False


def _pytest_is_green(ev: ToolEvidence | None) -> bool:
    if ev is None or ev.status != "ok":
        return False
    counts = ev.counts
    if int(counts.get("total", 0)) <= 0:
        return False
    return int(counts.get("failure", 0)) == 0 and int(counts.get("error", 0)) == 0


def _files_with_findings(ev: ToolEvidence | None) -> set[str]:
    if ev is None or ev.status != "ok":
        return set()
    return {
        f.path.replace("\\", "/").lstrip("./")
        for f in ev.findings
        if f.severity == "error"
    }


def _link_evidence_to_obligations(
    obligations: list[Obligation],
    tool_evidence: list[ToolEvidence] | None,
    changed_files: list[str] | None,
) -> list[Obligation]:
    """Close obligations whose required evidence is green in ``tool_evidence``.

    Rules (advisor-approved, deliberately crude in Phase 2):

    * ``precondition`` — closed when pytest is fully green AND the scope
      matches at least one ``changed_file``. Rationale: a green pytest run
      over the changed surface is the strongest automatic evidence we have
      for preconditions without per-obligation test mapping.
    * ``api_contract`` — closed when both ruff and mypy ran green for the
      scope's file (no error-severity findings on that path).

    Obligations already ``closed`` or ``violated`` are left untouched; the
    linker only upgrades ``open`` → ``closed``. It never downgrades, because
    a human may have marked an obligation violated manually and we must
    preserve that signal. The linker returns a new list; inputs are not
    mutated.
    """
    if not obligations:
        return []
    pytest_ev = _find_evidence(tool_evidence, "pytest")
    ruff_ev = _find_evidence(tool_evidence, "ruff")
    mypy_ev = _find_evidence(tool_evidence, "mypy")

    pytest_green = _pytest_is_green(pytest_ev)
    ruff_ran = ruff_ev is not None and ruff_ev.status == "ok"
    mypy_ran = mypy_ev is not None and mypy_ev.status == "ok"
    ruff_error_files = _files_with_findings(ruff_ev)
    mypy_error_files = _files_with_findings(mypy_ev)

    changed = [f.replace("\\", "/").lstrip("./") for f in (changed_files or [])]

    linked: list[Obligation] = []
    for ob in obligations:
        if ob.status != "open":
            linked.append(ob)
            continue

        closed = False
        if ob.kind == "precondition" and pytest_green and changed:
            if any(_scope_matches_file(ob.scope, cf) for cf in changed):
                closed = True
        elif ob.kind == "api_contract" and ruff_ran and mypy_ran:
            # Find the file this obligation is scoped to; green = no error
            # findings for that path in either tool.
            candidates = changed if changed else [ob.scope]
            hit = next(
                (cf for cf in candidates if _scope_matches_file(ob.scope, cf)),
                None,
            )
            if hit is not None:
                hit_norm = hit.replace("\\", "/").lstrip("./")
                if hit_norm not in ruff_error_files and hit_norm not in mypy_error_files:
                    closed = True

        if closed:
            linked.append(ob.model_copy(update={"status": "closed"}))
        else:
            linked.append(ob)
    return linked


def _event_id_for(index: int, obligation: Obligation) -> str:
    # Use obligation ID stripped of the "o-" prefix so the OIDA event ID
    # stays compact (vendored analyzer requires uniqueness only).
    suffix = obligation.id.removeprefix("o-") or f"{index:03d}"
    return f"e{index + 1}_{suffix[:16]}"


def _task_summary(obligation: Obligation) -> str:
    return obligation.description.strip()[:140] or f"{obligation.kind} @ {obligation.scope}"


def obligations_to_scenario(
    obligations: list[Obligation],
    request: AuditRequest | None = None,
    tool_evidence: list[ToolEvidence] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> NormalizedScenario:
    """Synthesize a :class:`NormalizedScenario` from obligations + evidence.

    See the module docstring for the default-origin table. This function is
    deliberately pure; it never hits the filesystem or subprocess.
    """
    if not obligations:
        return NormalizedScenario(
            name=name or (request.intent.summary[:80] if request else "empty"),
            description=description or "No obligations extracted.",
            events=[],
        )

    tests_pass_value = _tests_pass_from_evidence(tool_evidence)
    completion_value = _completion_from_evidence(tool_evidence)
    operator_value = _operator_accept_from_evidence(tool_evidence)

    changed_files = list(request.scope.changed_files) if request else []
    linked_obligations = _link_evidence_to_obligations(
        obligations, tool_evidence, changed_files
    )

    events: list[NormalizedEvent] = []
    for idx, ob in enumerate(linked_obligations):
        data_signal = _data_signal_for_scope(ob.scope)
        reversibility = round(max(0.0, min(1.0, 1.0 - data_signal)), 6)
        blast = round(data_signal, 6)  # scope-local blast; aggregate is elsewhere.
        events.append(
            NormalizedEvent(
                id=_event_id_for(idx, ob),
                pattern_id=_pattern_id_for(ob),
                task=_task_summary(ob),
                capability=0.5,  # default — Phase 4 LLM
                reversibility=reversibility,
                observability=0.5,  # default — Phase 4 uses test-file presence
                blast_radius=blast,
                completion=completion_value,
                tests_pass=tests_pass_value,
                operator_accept=operator_value,
                benefit=0.5,  # default — Phase 4 LLM from intent
                preconditions=_preconditions_for(ob),
                constitutive_parents=[],
                supportive_parents=[],
                invalidates_pattern=False,
            )
        )

    scenario_name = name or (
        request.intent.summary[:80] if request and request.intent.summary else "oida-code-audit"
    )
    scenario_desc = description or (
        f"Synthesized scenario for {len(obligations)} obligation(s)"
    )
    return NormalizedScenario(
        name=scenario_name,
        description=scenario_desc,
        events=events,
    )


def analyze_scenario(scenario: NormalizedScenario) -> dict[str, Any]:
    """Run the vendored :class:`OIDAAnalyzer` against a Pydantic scenario.

    Convenience wrapper used by ``cli.normalize`` and the downstream phases.
    Pydantic → vendored → analyzer → dict report.
    """
    from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer

    vendored = pydantic_to_vendored(scenario)
    analyzer = OIDAAnalyzer(vendored)
    return analyzer.analyze()


__all__ = [
    "analyze_scenario",
    "obligations_to_scenario",
    "pydantic_to_vendored",
    "vendored_to_pydantic",
]
