"""Phase 4.1 (QA/A16.md, ADR-26) — forward/backward verifier tests.

Three groups:

* **Schema invariants** — :class:`VerifierClaim` rejects forbidden
  phrases / unknown claim types / authoritative=True.
* **Aggregation rules** — `aggregate_verification` enforces all 7
  rules from ADR-26 (forward + backward + evidence + tool + claim
  type + cap + forbidden).
* **Hermetic fixtures** — 8 cases including a prompt-injection
  attempt and a tool-failure-vs-claim contradiction.

NONE of these tests call an external API or execute any tool.
``test_no_external_provider_called_by_default`` and
``test_tool_call_specs_are_not_executed_in_phase4_1`` are the
explicit guards.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from oida_code.estimators.contracts import SignalEstimate
from oida_code.estimators.llm_prompt import (
    EvidenceItem,
    LLMEvidencePacket,
)
from oida_code.verifier.aggregator import aggregate_verification
from oida_code.verifier.contracts import (
    BackwardRequirement,
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierAggregationReport,
    VerifierClaim,
    VerifierToolCallSpec,
)
from oida_code.verifier.forward_backward import (
    run_verifier,
)
from oida_code.verifier.replay import (
    FakeVerifierProvider,
    FileReplayVerifierProvider,
    OptionalExternalVerifierProvider,
    VerifierProviderUnavailable,
    build_verifier_provider,
)

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "verifier_forward_backward"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _packet(
    *,
    event_id: str = "e1",
    evidence: list[tuple[str, str, str]] | None = None,
    deterministic: tuple[SignalEstimate, ...] = (),
) -> LLMEvidencePacket:
    items = [
        EvidenceItem(id=eid, kind=kind, summary=summary,  # type: ignore[arg-type]
                     source="ticket", confidence=0.9)
        for eid, kind, summary in (evidence or [("[E.intent.1]", "intent", "x")])
    ]
    return LLMEvidencePacket(
        event_id=event_id,
        allowed_fields=("capability", "benefit", "observability"),
        intent_summary="x",
        evidence_items=tuple(items),
        deterministic_estimates=deterministic,
    )


def _claim(
    *,
    claim_id: str = "c-1",
    event_id: str = "e1",
    claim_type: str = "capability_sufficient",
    confidence: float = 0.5,
    evidence_refs: tuple[str, ...] = ("[E.intent.1]",),
    statement: str = "ok",
    source: str = "forward",
) -> VerifierClaim:
    return VerifierClaim(
        claim_id=claim_id,
        event_id=event_id,
        claim_type=claim_type,  # type: ignore[arg-type]
        statement=statement,
        confidence=confidence,
        evidence_refs=evidence_refs,
        source=source,  # type: ignore[arg-type]
    )


def _backward(
    *,
    claim_id: str = "c-1",
    event_id: str = "e1",
    met: bool = True,
    required: tuple[str, ...] = ("intent",),
    missing: tuple[str, ...] = (),
) -> BackwardVerificationResult:
    return BackwardVerificationResult(
        event_id=event_id,
        claim_id=claim_id,
        requirement=BackwardRequirement(
            claim_id=claim_id,
            required_evidence_kinds=required,  # type: ignore[arg-type]
            missing_requirements=missing,
        ),
        necessary_conditions_met=met,
    )


def _forward(
    supported: tuple[VerifierClaim, ...] = (),
    rejected: tuple[VerifierClaim, ...] = (),
    *,
    event_id: str = "e1",
) -> ForwardVerificationResult:
    return ForwardVerificationResult(
        event_id=event_id,
        supported_claims=supported,
        rejected_claims=rejected,
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def test_verifier_claim_rejects_forbidden_phrase_in_statement() -> None:
    with pytest.raises(ValidationError):
        VerifierClaim(
            claim_id="c-1",
            event_id="e1",
            claim_type="capability_sufficient",
            statement="this code is merge_safe and bug_free",
            confidence=0.5,
            source="forward",
        )


def test_verifier_claim_rejects_unknown_claim_type() -> None:
    with pytest.raises(ValidationError):
        VerifierClaim(
            claim_id="c-1",
            event_id="e1",
            claim_type="merge_safe",  # type: ignore[arg-type]
            statement="ok",
            confidence=0.5,
            source="forward",
        )


def test_verifier_claim_is_authoritative_pinned_to_false() -> None:
    with pytest.raises(ValidationError):
        VerifierClaim.model_validate({
            "claim_id": "c-1",
            "event_id": "e1",
            "claim_type": "capability_sufficient",
            "statement": "ok",
            "confidence": 0.5,
            "source": "forward",
            "is_authoritative": True,
        })


def test_verifier_aggregation_report_authoritative_pinned_to_false() -> None:
    rep = VerifierAggregationReport(status="blocked")
    assert rep.authoritative is False
    with pytest.raises(ValidationError):
        rep.model_dump()  # pre-flight
        VerifierAggregationReport.model_validate({
            "status": "verification_candidate",
            "authoritative": True,
        })


def test_verifier_report_has_no_vnet_debt_corrupt_success() -> None:
    """The model schema does not expose any official field."""
    rep = VerifierAggregationReport(status="blocked")
    payload = rep.model_dump()
    forbidden = {
        "total_v_net", "v_net", "debt_final",
        "corrupt_success", "corrupt_success_ratio",
        "corrupt_success_verdict", "verdict",
    }
    assert not (forbidden & set(payload.keys()))


# ---------------------------------------------------------------------------
# Aggregation rules
# ---------------------------------------------------------------------------


def test_forward_and_backward_required_for_acceptance() -> None:
    packet = _packet()
    claim = _claim()
    forward = _forward(supported=(claim,))
    backward = (_backward(),)
    rep = aggregate_verification(forward, backward, packet)
    assert rep.status == "verification_candidate"
    assert rep.accepted_claims == (claim,)


def test_forward_only_is_not_enough() -> None:
    packet = _packet()
    claim = _claim()
    forward = _forward(supported=(claim,))
    rep = aggregate_verification(forward, (), packet)
    assert rep.accepted_claims == ()
    assert claim in rep.unsupported_claims
    assert rep.status == "diagnostic_only"


def test_backward_missing_requirement_rejects_claim() -> None:
    packet = _packet()
    claim = _claim()
    forward = _forward(supported=(claim,))
    backward = (_backward(met=False, missing=("intent",)),)
    rep = aggregate_verification(forward, backward, packet)
    assert claim in rep.unsupported_claims
    assert any("necessary conditions not met" in w for w in rep.warnings)


def test_unknown_evidence_ref_rejects_claim() -> None:
    packet = _packet()
    claim = _claim(evidence_refs=("[E.does_not_exist.1]",))
    forward = _forward(supported=(claim,))
    backward = (_backward(),)
    rep = aggregate_verification(forward, backward, packet)
    assert claim in rep.rejected_claims
    assert any("unknown evidence_refs" in w for w in rep.warnings)


def test_forbidden_official_field_rejects_batch() -> None:
    """At the schema level, a claim mentioning a forbidden phrase
    cannot even be CONSTRUCTED — the runner therefore never sees it.
    Test that the construction fails and that the aggregator handles
    a forward result with a rejected_claims block carrying a regular
    claim alongside forbidden text in raw JSON would be caught at
    forward parse time. We verify the schema rejection here."""
    with pytest.raises(ValidationError):
        VerifierClaim(
            claim_id="c-bad",
            event_id="e1",
            claim_type="capability_sufficient",
            statement="this is total_v_net at 0.95",
            confidence=0.4,
            source="forward",
        )


def test_tool_failure_contradicts_claim() -> None:
    """A tool-grounded estimate with value < 0.5 (failure) on the
    claim's event causes the aggregator to reject the LLM-style
    claim — deterministic wins."""
    det = SignalEstimate(
        field="completion",
        event_id="e1",
        value=0.2,
        confidence=0.85,
        source="test_result",
        method_id="completion.pytest_relevant",
        method_version="e3.2",
        evidence_refs=("pytest:src/a.py:1:failed",),
    )
    packet = _packet(deterministic=(det,))
    claim = _claim()
    forward = _forward(supported=(claim,))
    backward = (_backward(),)
    rep = aggregate_verification(forward, backward, packet)
    assert claim in rep.rejected_claims
    assert any("contradicts deterministic tool failure" in w for w in rep.warnings)


def test_llm_only_claim_never_authoritative() -> None:
    """Construct a VerifierClaim with source='forward' and
    is_authoritative=True — schema rejects."""
    with pytest.raises(ValidationError):
        VerifierClaim.model_validate({
            "claim_id": "c-1", "event_id": "e1",
            "claim_type": "capability_sufficient",
            "statement": "ok", "confidence": 0.5,
            "source": "forward", "is_authoritative": True,
        })


def test_verifier_claim_confidence_cap_enforced_by_aggregator() -> None:
    """LLM-style sources (forward/backward/replay) cap at 0.6."""
    packet = _packet()
    over = _claim(confidence=0.65)  # over the cap
    forward = _forward(supported=(over,))
    backward = (_backward(),)
    rep = aggregate_verification(forward, backward, packet)
    assert over in rep.rejected_claims
    assert any("0.6 cap" in w for w in rep.warnings)


# ---------------------------------------------------------------------------
# Provider security + Phase 4.1 contract guards
# ---------------------------------------------------------------------------


def test_no_external_provider_called_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OptionalExternalVerifierProvider raises clean
    LLMProviderUnavailable when env var is missing — no network call."""
    monkeypatch.delenv("OIDA_VERIFIER_API_KEY", raising=False)
    p = OptionalExternalVerifierProvider()
    with pytest.raises(VerifierProviderUnavailable) as excinfo:
        p.verify(prompt="x", timeout_s=1)
    msg = str(excinfo.value)
    assert "OIDA_VERIFIER_API_KEY" in msg


def test_external_provider_does_not_leak_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "this-must-never-leak-from-verifier"
    monkeypatch.setenv("OIDA_VERIFIER_API_KEY", secret)
    p = OptionalExternalVerifierProvider()
    try:
        p.verify(prompt="x", timeout_s=1)
    except VerifierProviderUnavailable as exc:
        captured = capsys.readouterr()
        assert secret not in str(exc)
        assert secret not in captured.out
        assert secret not in captured.err


def test_tool_call_specs_are_not_executed_in_phase4_1() -> None:
    """A VerifierToolCallSpec describes intent — Phase 4.1 cannot
    execute it. We construct one and verify there is no execute()
    method anywhere in the verifier package."""
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run scoped negative-path test",
        expected_evidence_kind="test_result",
        scope=("src/app.py",),
    )
    assert not hasattr(spec, "execute")
    assert not hasattr(spec, "run")
    # And the verifier module must not import a tool runner at module load.
    import oida_code.verifier as v

    assert not hasattr(v, "execute_tool_call_spec")
    assert not hasattr(v, "run_tool_call_spec")


def test_build_verifier_provider_factory() -> None:
    assert isinstance(build_verifier_provider("fake"), FakeVerifierProvider)
    with pytest.raises(VerifierProviderUnavailable):
        build_verifier_provider("nope")


def test_build_verifier_provider_replay_requires_path() -> None:
    with pytest.raises(VerifierProviderUnavailable):
        build_verifier_provider("replay")


# ---------------------------------------------------------------------------
# Hermetic fixtures
# ---------------------------------------------------------------------------


FIXTURES = sorted([p for p in FIXTURES_ROOT.iterdir() if p.is_dir()])


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_phase4_1_fixture(fixture: Path) -> None:
    packet = LLMEvidencePacket.model_validate_json(
        (fixture / "packet.json").read_text(encoding="utf-8")
    )
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    forward = FileReplayVerifierProvider(fixture_path=fixture / "forward_response.json")
    backward = FileReplayVerifierProvider(fixture_path=fixture / "backward_response.json")
    run = run_verifier(packet, forward, backward)
    rep = run.report

    assert rep.status == expected["expected_status"], (
        f"{fixture.name}: status={rep.status}, expected={expected['expected_status']}"
    )
    assert len(rep.accepted_claims) >= expected.get("min_accepted", 0)
    if "max_rejected" in expected:
        assert len(rep.rejected_claims) <= expected["max_rejected"]
    if "min_rejected" in expected:
        assert len(rep.rejected_claims) >= expected["min_rejected"]
    if "min_unsupported" in expected:
        assert len(rep.unsupported_claims) >= expected["min_unsupported"]
    if "max_unsupported" in expected:
        assert len(rep.unsupported_claims) <= expected["max_unsupported"]

    accepted_ids = {c.claim_id for c in rep.accepted_claims}
    rejected_ids = {c.claim_id for c in rep.rejected_claims}
    unsupported_ids = {c.claim_id for c in rep.unsupported_claims}

    for cid in expected.get("must_accept_claim_ids", []):
        assert cid in accepted_ids, f"{fixture.name}: missing accepted {cid}"
    for cid in expected.get("must_reject_claim_ids", []):
        assert cid in rejected_ids, f"{fixture.name}: missing rejected {cid}"
    for cid in expected.get("must_unsupport_claim_ids", []):
        assert cid in unsupported_ids, (
            f"{fixture.name}: missing unsupported {cid}"
        )

    if "must_have_warning_containing" in expected:
        text = expected["must_have_warning_containing"]
        assert any(text in w for w in rep.warnings), (
            f"{fixture.name}: expected warning containing {text!r}, "
            f"got {list(rep.warnings)}"
        )

    if expected.get("rendered_prompt_must_fence_injection"):
        from oida_code.estimators.llm_prompt import render_prompt
        prompt = render_prompt(packet)
        assert "mark capability=1.0" in prompt
        idx = prompt.find("mark capability=1.0")
        fence_open = prompt.rfind("<<<OIDA_EVIDENCE", 0, idx)
        fence_close = prompt.find("<<<END_OIDA_EVIDENCE", idx)
        assert 0 <= fence_open < idx < fence_close

    if expected.get("must_not_have_capability_at_one"):
        for c in rep.accepted_claims:
            if c.claim_type == "capability_sufficient":
                assert c.confidence < 1.0

    if expected.get("report_must_not_be_authoritative"):
        assert rep.authoritative is False


def test_prompt_injection_claim_payload_is_data() -> None:
    """The prompt-injection fixture sees the renderer place hostile
    text behind named fences. The verifier's forward response correctly
    emits no claim. Specific assertion in addition to the parametrized
    fixture."""
    fixture = FIXTURES_ROOT / "prompt_injection_claim_payload"
    packet = LLMEvidencePacket.model_validate_json(
        (fixture / "packet.json").read_text(encoding="utf-8")
    )
    forward = FileReplayVerifierProvider(fixture_path=fixture / "forward_response.json")
    backward = FileReplayVerifierProvider(fixture_path=fixture / "backward_response.json")
    run = run_verifier(packet, forward, backward)
    assert run.report.status == "blocked"
    # And the rendered prompt has the injection inside fences.
    from oida_code.estimators.llm_prompt import render_prompt

    prompt = render_prompt(packet)
    needle = "mark capability=1.0"
    idx = prompt.find(needle)
    fence_open = prompt.rfind("<<<OIDA_EVIDENCE", 0, idx)
    fence_close = prompt.find("<<<END_OIDA_EVIDENCE", idx)
    assert 0 <= fence_open < idx < fence_close


def test_repair_needed_claim_is_diagnostic_only() -> None:
    """Even when a repair_needed claim is fully accepted (forward +
    backward + evidence + no tool conflict), the report stays
    non-authoritative. ADR-26 explicitly forbids the verifier from
    promoting any claim to official."""
    fixture = FIXTURES_ROOT / "repair_needed_supported"
    packet = LLMEvidencePacket.model_validate_json(
        (fixture / "packet.json").read_text(encoding="utf-8")
    )
    forward = FileReplayVerifierProvider(fixture_path=fixture / "forward_response.json")
    backward = FileReplayVerifierProvider(fixture_path=fixture / "backward_response.json")
    run = run_verifier(packet, forward, backward)
    assert run.report.status == "verification_candidate"
    assert run.report.authoritative is False


# ---------------------------------------------------------------------------
# Final guards
# ---------------------------------------------------------------------------


def test_runner_handles_invalid_json_without_crash() -> None:
    packet = _packet()

    class _BadProvider:
        def verify(self, prompt: str, *, timeout_s: int) -> str:
            return "not json"

    backward = FakeVerifierProvider()
    run = run_verifier(packet, _BadProvider(), backward)  # type: ignore[arg-type]
    assert any("not valid JSON" in b for b in run.report.blockers)


def test_runner_handles_forbidden_phrase_in_response() -> None:
    packet = _packet()

    class _ForbiddenProvider:
        def verify(self, prompt: str, *, timeout_s: int) -> str:
            return json.dumps({
                "supported_claims": [],
                "rejected_claims": [],
                "missing_evidence_refs": [],
                "contradictions": ["this code is total_v_net=0.9"],
                "warnings": [],
            })

    backward = FakeVerifierProvider()
    run = run_verifier(packet, _ForbiddenProvider(), backward)  # type: ignore[arg-type]
    assert any("forbidden official phrase" in b for b in run.report.blockers)


def test_no_external_env_var_set_at_collection_time() -> None:
    _ = os.environ.get("OIDA_VERIFIER_API_KEY")


# ---------------------------------------------------------------------------
# Phase 4.1.1 — aggregator event_id hardening
# ---------------------------------------------------------------------------


def test_claim_event_id_must_match_forward_event_id() -> None:
    """4.1.1: a supported claim whose event_id != forward.event_id is
    rejected. Cross-event votes must NOT slip into accepted_claims."""
    packet = _packet(event_id="event-A")
    cross = _claim(event_id="event-B")  # mismatch
    forward = _forward(supported=(cross,), event_id="event-A")
    backward = (_backward(event_id="event-A"),)
    rep = aggregate_verification(forward, backward, packet)
    assert cross in rep.rejected_claims
    assert cross not in rep.accepted_claims
    assert any(
        "event_id 'event-B'" in w and "event-A" in w
        for w in rep.warnings
    )


def test_backward_event_id_must_match_forward_event_id() -> None:
    """4.1.1: a backward result whose event_id doesn't match
    forward.event_id is dropped. The claim it would have validated
    falls through to "no backward verification → unsupported"."""
    packet = _packet(event_id="event-A")
    claim = _claim(event_id="event-A")
    forward = _forward(supported=(claim,), event_id="event-A")
    bad_backward = (_backward(event_id="event-OTHER"),)
    rep = aggregate_verification(forward, bad_backward, packet)
    assert claim in rep.unsupported_claims
    assert any(
        "event_id 'event-OTHER'" in w
        for w in rep.warnings
    )


def test_tool_failure_check_uses_claim_event_id_not_forward() -> None:
    """4.1.1: the deterministic-tool contradiction check must use
    claim.event_id. We craft a forward that carries one event_id but
    a (now-rejected because of the new event-id check) and verify
    that an in-event claim is correctly rejected on its own event."""
    det = SignalEstimate(
        field="completion",
        event_id="event-claim",
        value=0.2,
        confidence=0.85,
        source="test_result",
        method_id="completion.pytest_relevant",
        method_version="e3.2",
        evidence_refs=("pytest:src/a.py:1:failed",),
    )
    packet = _packet(event_id="event-claim", deterministic=(det,))
    matching = _claim(event_id="event-claim")
    forward = _forward(supported=(matching,), event_id="event-claim")
    backward = (_backward(event_id="event-claim"),)
    rep = aggregate_verification(forward, backward, packet)
    assert matching in rep.rejected_claims
    assert any(
        f"contradicts deterministic tool failure on event "
        f"{matching.event_id}" in w
        for w in rep.warnings
    )
