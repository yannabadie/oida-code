"""Phase 5.3 (QA/A30.md, ADR-38) — gateway verifier calibration
tests.

Sub-blocks covered:

* 5.2.1-A — fence wording in the Phase 5.2 report stays in
  sync with the actual ``FENCE_NAME`` constant.
* 5.2.1-B — gateway loop surfaces blockers (and demotes pass-2
  accepted claims) when forward requested tools but no
  ``[E.tool_output.*]`` evidence was produced. Three failure
  modes: missing definition, all calls blocked, gateway ran
  but emitted nothing.
* 5.2.1-C — ``VerifierToolCallSpec`` carries an optional
  ``requested_by_claim_id`` field.
* 5.3-A / 5.3-F — private holdout v2 dataset README + manifest
  example + contamination policy.
* 5.3-C — ``GatewayHoldoutExpected`` + ``ExpectedVerifierOutcome``
  schemas under :mod:`oida_code.calibration.gateway_holdout`.
* 5.3-D — ``scripts/run_gateway_calibration.py`` runner.
* 5.3-E — failure analysis Markdown table emitted by the runner.
* 5.3-G — anti-MCP regression locks remain active.
* 5.3-H — replay-only ``gateway-calibration.yml`` workflow.

Negative checks scan ``pyproject.toml`` +
``.github/workflows/`` + ``src/oida_code/`` only — never
``docs/`` or ``reports/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from oida_code.estimators.llm_prompt import FENCE_NAME

_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# 5.2.1-A — fence wording canary
# ---------------------------------------------------------------------------


def test_phase5_2_report_uses_current_fence_constant() -> None:
    """The Phase 5.2 report MUST reference the live
    ``FENCE_NAME`` constant. If the prompt module renames the
    fence, this canary catches the docs drift."""
    report = (
        _REPO_ROOT / "reports"
        / "phase5_2_gateway_grounded_verifier_loop.md"
    ).read_text(encoding="utf-8")
    # The actual prompt fence has named attributes — the report
    # MUST mention the open-with-id form, not the bare prefix.
    assert FENCE_NAME == "OIDA_EVIDENCE", (
        "Test assumption: FENCE_NAME=='OIDA_EVIDENCE'. If you "
        "renamed the constant, update this canary too."
    )
    assert f'<<<{FENCE_NAME} id=' in report, (
        "Phase 5.2 report must reference the named per-item "
        f"open fence {FENCE_NAME!r} including the id attribute"
    )
    assert f'<<<END_{FENCE_NAME} id=' in report, (
        "Phase 5.2 report must reference the named per-item "
        f"close fence END_{FENCE_NAME} including the id attribute"
    )
    # Cross-link: the report must point at the FENCE_NAME
    # constant so a future reader can follow the wire.
    assert "FENCE_NAME" in report, (
        "Phase 5.2 report must mention FENCE_NAME so the docs "
        "stay anchored to the source constant"
    )


# ---------------------------------------------------------------------------
# 5.2.1-B — requested-tool-without-evidence blockers
# ---------------------------------------------------------------------------


def _baseline_packet():
    from oida_code.estimators.llm_prompt import (
        EvidenceItem,
        LLMEvidencePacket,
    )
    return LLMEvidencePacket(
        event_id="evt-loop",
        allowed_fields=("capability",),
        intent_summary="ship feature",
        evidence_items=(
            EvidenceItem(
                id="[E.event.1]", kind="event", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )


class _ScriptedProvider:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    def verify(self, prompt: str, *, timeout_s: int) -> str:
        del prompt, timeout_s
        if not self._replies:
            raise AssertionError("scripted provider exhausted")
        return self._replies.pop(0)


def _ruff_definition():
    from oida_code.verifier.tool_gateway.contracts import (
        GatewayToolDefinition,
    )
    return GatewayToolDefinition(
        tool_id="oida-code/ruff",
        tool_name="ruff",
        adapter_version="0.4.0",
        description="Run ruff check (read-only).",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_level="read_only",
        allowed_scopes=("repo:read",),
    )


def _pytest_definition():
    from oida_code.verifier.tool_gateway.contracts import (
        GatewayToolDefinition,
    )
    return GatewayToolDefinition(
        tool_id="oida-code/pytest",
        tool_name="pytest",
        adapter_version="0.4.0",
        description="Run pytest (read-only).",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_level="read_only",
        allowed_scopes=("repo:read",),
    )


def _registry_with(*defs):
    from oida_code.verifier.tool_gateway.contracts import (
        ToolAdmissionDecision,
        ToolAdmissionRegistry,
    )
    from oida_code.verifier.tool_gateway.fingerprints import (
        fingerprint_tool_definition,
    )
    decisions = tuple(
        ToolAdmissionDecision(
            tool_id=d.tool_id,
            status="approved_read_only",
            reason="test fixture approval",
            fingerprint=fingerprint_tool_definition(d),
        )
        for d in defs
    )
    return ToolAdmissionRegistry(approved=decisions)


def _policy(repo_root: Path):
    from oida_code.verifier.tools.contracts import ToolPolicy
    return ToolPolicy(
        allowed_tools=("ruff", "mypy", "pytest"),
        repo_root=repo_root,
        allow_network=False,
        allow_write=False,
    )


def _ok_executor():
    from oida_code.verifier.tools.adapters import (
        ExecutionContext,
        ExecutionOutcome,
    )

    def _exec(_ctx: ExecutionContext) -> ExecutionOutcome:
        # ruff returncode=0 with empty JSON list ⇒ status=ok but
        # the adapter emits NO evidence_items because there are
        # no findings.
        return ExecutionOutcome(
            returncode=0, stdout="[]", stderr="",
            timed_out=False, runtime_ms=1,
        )
    return _exec


def test_requested_tool_missing_definition_blocks_claim_acceptance(
    tmp_path: Path,
) -> None:
    """Forward requested pytest, but the operator-supplied
    ``gateway_definitions`` map has no entry for it. The loop
    must surface a blocker AND prevent any pass-2 claim from
    being accepted."""
    from oida_code.verifier.gateway_loop import (
        run_gateway_grounded_verifier,
    )
    from oida_code.verifier.tool_gateway.gateway import (
        LocalDeterministicToolGateway,
    )

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    # Pass-2 forward asserts a claim that doesn't cite tool refs.
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [{
            "claim_id": "C.tests_pass",
            "event_id": "evt-loop",
            "claim_type": "capability_sufficient",
            "statement": "tests pass",
            "confidence": 0.55,
            "evidence_refs": ["[E.event.1]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward = json.dumps([{
        "event_id": "evt-loop",
        "claim_id": "C.tests_pass",
        "requirement": {
            "claim_id": "C.tests_pass",
            "required_evidence_kinds": ["event"],
            "satisfied_evidence_refs": ["[E.event.1]"],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }])

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(executor=_ok_executor())
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=_registry_with(_pytest_definition()),
        gateway_definitions={},  # NO definition for pytest
        audit_log_dir=audit_dir,
    )
    # No tool ran; no evidence; pass-2 claim must NOT be accepted.
    accepted = {c.claim_id for c in run.report.accepted_claims}
    assert "C.tests_pass" not in accepted
    # A blocker must explain why.
    blockers_text = " ".join(run.report.blockers).lower()
    assert (
        "no approved gateway definition" in blockers_text
        or "missing gateway definition" in blockers_text
        or "had no" in blockers_text
    ), f"expected missing-definition blocker; got {run.report.blockers}"


def test_requested_tool_blocked_without_evidence_demotes_pass2_claim(
    tmp_path: Path,
) -> None:
    """Forward requested pytest; the gateway has the definition
    but the admission registry is empty so the call is blocked
    with no evidence produced. Pass-2 claim that doesn't cite
    tool refs must be demoted from accepted_claims."""
    from oida_code.verifier.gateway_loop import (
        run_gateway_grounded_verifier,
    )
    from oida_code.verifier.tool_gateway.contracts import (
        ToolAdmissionRegistry,
    )
    from oida_code.verifier.tool_gateway.gateway import (
        LocalDeterministicToolGateway,
    )

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "re-run pytest",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    })
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [{
            "claim_id": "C.tests_pass",
            "event_id": "evt-loop",
            "claim_type": "capability_sufficient",
            "statement": "tests pass",
            "confidence": 0.55,
            "evidence_refs": ["[E.event.1]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward = json.dumps([{
        "event_id": "evt-loop",
        "claim_id": "C.tests_pass",
        "requirement": {
            "claim_id": "C.tests_pass",
            "required_evidence_kinds": ["event"],
            "satisfied_evidence_refs": ["[E.event.1]"],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }])
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(executor=_ok_executor())
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=ToolAdmissionRegistry(),  # empty
        gateway_definitions={"pytest": _pytest_definition()},
        audit_log_dir=audit_dir,
    )
    # Tool was called but blocked; no evidence; claim demoted.
    accepted = {c.claim_id for c in run.report.accepted_claims}
    unsupported = {
        c.claim_id for c in run.report.unsupported_claims
    }
    assert "C.tests_pass" not in accepted
    assert "C.tests_pass" in unsupported
    assert any(r.status == "blocked" for r in run.tool_results)


def test_requested_tool_no_new_evidence_adds_blocker(
    tmp_path: Path,
) -> None:
    """Gateway runs ok but the adapter emits no
    ``[E.tool_output.*]`` evidence (e.g. ruff with empty
    findings list, no positive item). The run must record a
    blocker explaining the citation gap."""
    from oida_code.verifier.gateway_loop import (
        run_gateway_grounded_verifier,
    )
    from oida_code.verifier.tool_gateway.gateway import (
        LocalDeterministicToolGateway,
    )

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "ruff",
            "purpose": "re-run ruff",
            "expected_evidence_kind": "tool_finding",
            "scope": ["src/"],
        }],
    })
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    })
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(executor=_ok_executor())
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider(["[]"]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=_registry_with(_ruff_definition()),
        gateway_definitions={"ruff": _ruff_definition()},
        audit_log_dir=audit_dir,
    )
    assert run.enriched_evidence_refs == ()
    blockers_text = " ".join(run.report.blockers).lower()
    assert (
        "no citable evidence" in blockers_text
        or "emitted no" in blockers_text
        or "no new" in blockers_text
    ), f"expected no-evidence blocker; got {run.report.blockers}"


def test_tool_requested_but_no_evidence_cannot_be_verification_candidate(
    tmp_path: Path,
) -> None:
    """When tools were requested but no evidence was produced,
    the report MUST NOT be ``verification_candidate`` (the
    highest status), even if the LLM-only chain would otherwise
    accept a claim."""
    from oida_code.verifier.gateway_loop import (
        run_gateway_grounded_verifier,
    )
    from oida_code.verifier.tool_gateway.gateway import (
        LocalDeterministicToolGateway,
    )

    pass1_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "ruff",
            "purpose": "re-run ruff",
            "expected_evidence_kind": "tool_finding",
            "scope": ["src/"],
        }],
    })
    pass2_forward = json.dumps({
        "event_id": "evt-loop",
        "supported_claims": [{
            "claim_id": "C.cap",
            "event_id": "evt-loop",
            "claim_type": "capability_sufficient",
            "statement": "ok",
            "confidence": 0.55,
            "evidence_refs": ["[E.event.1]"],
            "source": "forward",
        }],
        "rejected_claims": [],
        "requested_tools": [],
    })
    pass2_backward = json.dumps([{
        "event_id": "evt-loop",
        "claim_id": "C.cap",
        "requirement": {
            "claim_id": "C.cap",
            "required_evidence_kinds": ["event"],
            "satisfied_evidence_refs": ["[E.event.1]"],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }])
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    audit_dir = tmp_path / "audit"
    gateway = LocalDeterministicToolGateway(executor=_ok_executor())
    run = run_gateway_grounded_verifier(
        _baseline_packet(),
        forward_pass1=_ScriptedProvider([pass1_forward]),
        backward_pass1=_ScriptedProvider(["[]"]),
        forward_pass2=_ScriptedProvider([pass2_forward]),
        backward_pass2=_ScriptedProvider([pass2_backward]),
        gateway=gateway,
        tool_policy=_policy(repo_root),
        admission_registry=_registry_with(_ruff_definition()),
        gateway_definitions={"ruff": _ruff_definition()},
        audit_log_dir=audit_dir,
    )
    assert run.report.status != "verification_candidate"


# ---------------------------------------------------------------------------
# 5.2.1-C — VerifierToolCallSpec.requested_by_claim_id
# ---------------------------------------------------------------------------


def test_verifier_tool_call_spec_accepts_requested_by_claim_id() -> None:
    from oida_code.verifier.contracts import VerifierToolCallSpec
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run pytest",
        expected_evidence_kind="test_result",
        scope=("tests/",),
        requested_by_claim_id="C.42",
    )
    assert spec.requested_by_claim_id == "C.42"


def test_verifier_tool_call_spec_default_requested_by_claim_id_is_none() -> None:
    from oida_code.verifier.contracts import VerifierToolCallSpec
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run pytest",
        expected_evidence_kind="test_result",
        scope=("tests/",),
    )
    assert spec.requested_by_claim_id is None


def test_verifier_tool_call_spec_legacy_replay_still_validates() -> None:
    """Legacy fixtures (Phase 4.1 + Phase 5.2) that don't carry
    ``requested_by_claim_id`` MUST still parse via
    ``model_validate``."""
    from oida_code.verifier.contracts import VerifierToolCallSpec
    legacy = {
        "tool": "ruff",
        "purpose": "re-run ruff",
        "expected_evidence_kind": "tool_finding",
        "scope": ["src/app.py"],
    }
    parsed = VerifierToolCallSpec.model_validate(legacy)
    assert parsed.requested_by_claim_id is None


def test_tool_request_from_spec_propagates_claim_id() -> None:
    """The mapper plumbs ``spec.requested_by_claim_id`` into
    the resulting ``VerifierToolRequest`` (the field already
    exists on the request schema)."""
    from oida_code.verifier.contracts import VerifierToolCallSpec
    from oida_code.verifier.gateway_loop import tool_request_from_spec
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="re-run pytest",
        expected_evidence_kind="test_result",
        scope=("tests/",),
        requested_by_claim_id="C.42",
    )
    request = tool_request_from_spec(spec)
    assert request.requested_by_claim_id == "C.42"


# ---------------------------------------------------------------------------
# 5.3-C — GatewayHoldoutExpected schemas
# ---------------------------------------------------------------------------


def test_expected_verifier_outcome_defaults_are_empty() -> None:
    from oida_code.calibration.gateway_holdout import (
        ExpectedVerifierOutcome,
    )
    o = ExpectedVerifierOutcome()
    assert o.accepted_claim_ids == ()
    assert o.unsupported_claim_ids == ()
    assert o.rejected_claim_ids == ()
    assert o.blockers_expected == ()
    assert o.warnings_expected == ()


def test_gateway_holdout_expected_required_fields() -> None:
    from oida_code.calibration.gateway_holdout import (
        ExpectedVerifierOutcome,
        GatewayHoldoutExpected,
    )
    expected = GatewayHoldoutExpected(
        case_id="case-1",
        expected_baseline=ExpectedVerifierOutcome(
            accepted_claim_ids=("C.1",),
        ),
        expected_gateway=ExpectedVerifierOutcome(
            unsupported_claim_ids=("C.1",),
        ),
        expected_delta="improves",
    )
    assert expected.expected_delta == "improves"
    assert expected.required_tool_evidence_refs == ()
    assert expected.forbidden_acceptance_reasons == ()


def test_gateway_holdout_expected_delta_literal_rejects_garbage() -> None:
    from oida_code.calibration.gateway_holdout import (
        ExpectedVerifierOutcome,
        GatewayHoldoutExpected,
    )
    with pytest.raises(ValidationError):
        GatewayHoldoutExpected(
            case_id="case-1",
            expected_baseline=ExpectedVerifierOutcome(),
            expected_gateway=ExpectedVerifierOutcome(),
            expected_delta="totally_amazing",  # type: ignore[arg-type]
        )


def test_gateway_holdout_expected_is_frozen() -> None:
    from oida_code.calibration.gateway_holdout import (
        ExpectedVerifierOutcome,
        GatewayHoldoutExpected,
    )
    expected = GatewayHoldoutExpected(
        case_id="case-1",
        expected_baseline=ExpectedVerifierOutcome(),
        expected_gateway=ExpectedVerifierOutcome(),
        expected_delta="not_applicable",
    )
    with pytest.raises(ValidationError):
        expected.case_id = "case-2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 5.3-A / 5.3-F — private_holdout_v2 dataset
# ---------------------------------------------------------------------------


_HOLDOUT_DIR = _REPO_ROOT / "datasets" / "private_holdout_v2"


def test_private_holdout_v2_readme_exists() -> None:
    assert (_HOLDOUT_DIR / "README.md").is_file()


def test_private_holdout_v2_manifest_example_is_valid_json() -> None:
    payload = json.loads(
        (_HOLDOUT_DIR / "manifest.example.json").read_text(
            encoding="utf-8",
        ),
    )
    assert isinstance(payload, dict)
    assert "cases" in payload
    assert isinstance(payload["cases"], list)


def test_private_holdout_v2_readme_documents_contamination_policy() -> None:
    body = (_HOLDOUT_DIR / "README.md").read_text(encoding="utf-8")
    for keyword in ("synthetic", "private", "public_low", "public_high"):
        assert keyword in body, (
            f"README must document contamination tier {keyword!r}"
        )


def test_private_holdout_v2_readme_cross_links_v1() -> None:
    body = (_HOLDOUT_DIR / "README.md").read_text(encoding="utf-8")
    assert "private_holdout_v1" in body, (
        "v2 README must cross-link the existing v1 holdout"
    )


# ---------------------------------------------------------------------------
# 5.3-D / 5.3-E — calibration runner + failure analysis
# ---------------------------------------------------------------------------


_CALIBRATION_SCRIPT = (
    _REPO_ROOT / "scripts" / "run_gateway_calibration.py"
)


def test_calibration_script_exists() -> None:
    assert _CALIBRATION_SCRIPT.is_file()


def test_calibration_script_supports_replay_mode() -> None:
    body = _CALIBRATION_SCRIPT.read_text(encoding="utf-8")
    assert "--mode" in body
    assert '"replay"' in body or "'replay'" in body


def test_calibration_runner_outputs_delta_metrics(tmp_path: Path) -> None:
    """Smoke test: invoke the runner against the committed
    public/synthetic subset of the v2 holdout (or a tiny
    in-test manifest) and verify it produces the expected JSON
    artifacts."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )

    out_dir = tmp_path / "calibration"
    manifest = _HOLDOUT_DIR / "manifest.example.json"
    if not manifest.is_file():
        pytest.skip("v2 manifest example not present yet")
    run_calibration(
        manifest_path=manifest, out_dir=out_dir, mode="replay",
    )
    for name in (
        "baseline_metrics.json",
        "gateway_metrics.json",
        "delta_metrics.json",
        "failure_analysis.md",
        "artifact_manifest.json",
    ):
        assert (out_dir / name).is_file(), f"missing {name}"


def test_calibration_runner_does_not_mutate_dataset(
    tmp_path: Path,
) -> None:
    """Criterion #17 — labels are never mutated automatically.
    The runner MUST NOT modify any file under ``datasets/``
    while running."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )

    manifest = _HOLDOUT_DIR / "manifest.example.json"
    if not manifest.is_file():
        pytest.skip("v2 manifest example not present yet")

    # Snapshot dataset mtimes BEFORE.
    before = {
        p: p.stat().st_mtime_ns
        for p in _HOLDOUT_DIR.rglob("*")
        if p.is_file()
    }
    out_dir = tmp_path / "calibration"
    run_calibration(
        manifest_path=manifest, out_dir=out_dir, mode="replay",
    )
    after = {
        p: p.stat().st_mtime_ns
        for p in _HOLDOUT_DIR.rglob("*")
        if p.is_file()
    }
    assert before == after, "calibration runner mutated dataset files"


def test_failure_analysis_md_lists_required_columns(tmp_path: Path) -> None:
    """The Markdown table emitted by the runner MUST include
    the canonical columns from QA/A30 §5.3-E + QA/A31 §5.4-D
    extensions (Phase 5.4 added ``actual_delta`` +
    ``label_change_proposed``)."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )

    manifest = _HOLDOUT_DIR / "manifest.example.json"
    if not manifest.is_file():
        pytest.skip("v2 manifest example not present yet")
    out_dir = tmp_path / "calibration"
    run_calibration(
        manifest_path=manifest, out_dir=out_dir, mode="replay",
    )
    body = (out_dir / "failure_analysis.md").read_text(
        encoding="utf-8",
    )
    for column in (
        "case_id", "expected_delta", "actual_delta",
        "baseline_result", "gateway_result",
        "classification", "root_cause", "proposed_action",
        "label_change_proposed",
    ):
        assert column in body, f"failure_analysis.md missing column {column!r}"


def test_calibration_failure_classifications_are_documented(
    tmp_path: Path,
) -> None:
    """The seven QA/A30 §5.3-E classifications + the Phase 5.4
    addition (``tool_request_policy_gap``) MUST be documented
    in the runner's classification vocabulary."""
    from oida_code.calibration.gateway_calibration import (
        FAILURE_CLASSIFICATIONS,
    )
    expected = {
        "label_too_strict",
        "gateway_bug",
        "tool_adapter_bug",
        "aggregator_bug",
        "citation_gap",
        "tool_request_policy_gap",
        "insufficient_fixture",
        "expected_behavior_changed",
    }
    assert set(FAILURE_CLASSIFICATIONS) == expected


# ---------------------------------------------------------------------------
# 5.3-G — anti-MCP regression locks
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added() -> None:
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        "modelcontextprotocol",
        "@modelcontextprotocol",
        "mcp-server",
        "mcp_server",
    )
    for token in forbidden:
        assert token not in body, (
            f"pyproject.toml must not depend on {token!r}"
        )


def test_no_mcp_workflow_added() -> None:
    workflow_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return
    for wf in workflow_dir.glob("*.yml"):
        body = wf.read_text(encoding="utf-8")
        assert "tools/list" not in body, f"{wf.name} mentions tools/list"
        assert "tools/call" not in body, f"{wf.name} mentions tools/call"
        assert "mcp-server" not in body.lower(), (
            f"{wf.name} mentions mcp-server"
        )


def test_no_jsonrpc_runtime_in_calibration_script() -> None:
    body = _CALIBRATION_SCRIPT.read_text(encoding="utf-8")
    for token in (
        "modelcontextprotocol",
        "mcp.server",
        "stdio_server",
        "jsonrpc",
        "json-rpc",
    ):
        assert token not in body.lower(), (
            f"calibration script mentions {token!r}"
        )


def test_no_provider_tool_calling_enabled_in_phase5_3() -> None:
    """Phase 5.3 must not introduce provider-side tool-calling
    in any new source file."""
    src = _REPO_ROOT / "src" / "oida_code"
    forbidden_re = re.compile(
        r"(?:client\.responses\.create|client\.messages\.create|"
        r"client\.chat\.completions\.create)[^)]*\btools\s*=",
        re.MULTILINE | re.DOTALL,
    )
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        assert not forbidden_re.search(body), (
            f"{py} appears to enable provider tool-calling"
        )


# ---------------------------------------------------------------------------
# 5.3-H — gateway-calibration.yml workflow
# ---------------------------------------------------------------------------


_CALIBRATION_WORKFLOW = (
    _REPO_ROOT / ".github" / "workflows" / "gateway-calibration.yml"
)


def test_gateway_calibration_workflow_exists() -> None:
    assert _CALIBRATION_WORKFLOW.is_file()


def test_gateway_calibration_workflow_replay_only() -> None:
    body = _CALIBRATION_WORKFLOW.read_text(encoding="utf-8")
    triggers = body.split("on:", 1)[1].split("jobs:", 1)[0]
    assert "workflow_dispatch" in triggers
    forbidden = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OIDA_LLM_PROVIDER",
        "real provider",
    )
    for token in forbidden:
        assert token not in body, (
            f"gateway-calibration must not reference {token!r}"
        )


def test_gateway_calibration_workflow_permissions_read_only() -> None:
    body = _CALIBRATION_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:" in body
    assert "contents: read" in body
    write_lines = [
        ln for ln in body.splitlines()
        if ":" in ln and "write" in ln.lower()
    ]
    for line in write_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert (
            stripped.endswith(": read") or stripped.endswith(": none")
        ), f"non-read permission detected: {stripped}"


def test_gateway_calibration_workflow_no_external_provider() -> None:
    body = _CALIBRATION_WORKFLOW.read_text(encoding="utf-8")
    # Only the default GITHUB_TOKEN is allowed; nothing else.
    assert "secrets." not in body or "secrets.GITHUB_TOKEN" in body, (
        "gateway-calibration must not consume non-default secrets"
    )


def test_gateway_calibration_workflow_no_mcp() -> None:
    body = _CALIBRATION_WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "@modelcontextprotocol",
        "mcp-server",
        "stdio_server",
        "tools/list",
        "tools/call",
    )
    for token in forbidden:
        assert token not in body


def test_gateway_calibration_workflow_no_sarif_upload() -> None:
    """QA/A30 §5.3-H explicitly forbids SARIF upload from the
    calibration workflow (the calibration is measurement, not
    a code-scanning run)."""
    body = _CALIBRATION_WORKFLOW.read_text(encoding="utf-8")
    for token in ("upload-sarif", "codeql-action/upload-sarif"):
        assert token not in body, (
            f"gateway-calibration must not perform SARIF upload "
            f"({token!r} found)"
        )
