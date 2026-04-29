"""Phase 6.1'e (per QA/A45 step 1) — runtime-loader acceptance guard.

The Phase 6.1'b acceptance criterion was ``validate_gateway_bundle ok``,
which is a file-presence + filename-pattern check. Phase 6.1'd
surfaced three runtime-shape bugs (approved_tools.json shape,
pass*_backward.json list-shape, fingerprint drift) that the
file-presence validator could not catch.

cgpro QA/A45 verdict_q1 corrective: future 6.1'b-style
acceptance must also load each generated file through its target
Pydantic contract. This test enforces that contract for ANY
bundle the generator emits today, so a future skeleton change
cannot reintroduce the same class of bug.

Per ADR-57 retraction of ADR-55: "validate_gateway_bundle ok"
remains a meaningful file-presence check, but bundle acceptance
is now `validate_gateway_bundle ok AND runtime-loader smoke ok`.
This module is the runtime-loader smoke.
"""

from __future__ import annotations

import json
from pathlib import Path

from oida_code.bundle import generate_bundle
from oida_code.estimators.llm_prompt import LLMEvidencePacket
from oida_code.verifier.contracts import (
    BackwardVerificationResult,
    ForwardVerificationResult,
)
from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tools.contracts import ToolPolicy

_FIXTURE_RECORD: dict[str, object] = {
    "case_id": "seed_test_runtime_owner_repo_42",
    "repo_url": "https://github.com/owner/repo",
    "pr_number": 42,
    "title": "Fix CLI flag handling",
    "base_sha": "0" * 40,
    "head_sha": "1" * 40,
    "changed_files_list": [
        "src/pkg/cli.py",
        "tests/test_cli.py",
    ],
    "labels_observed": [],
    "merge_status": "merged",
    "candidate_reason": "fixture for runtime-loader test",
    "claim_id": "C.fixture_surface.repair_needed",
    "claim_text": (
        "After PR #42 the CLI accepts -x as alias for --xtra."
    ),
    "claim_type": "repair_needed",
    "evidence_items": [
        {
            "id": "[E.event.1]",
            "kind": "event",
            "summary": (
                "PR #42 adds -x alias to CLI parser; 8 lines."
            ),
            "source": "git",
            "confidence": 0.9,
        },
        {
            "id": "[E.event.2]",
            "kind": "event",
            "summary": (
                "Test test_xtra_alias asserts -x produces same "
                "exit code as --xtra."
            ),
            "source": "ticket",
            "confidence": 0.85,
        },
    ],
    "test_scope": "tests/test_cli.py::test_xtra_alias",
    "expected_grounding_outcome": "evidence_present",
    "label_source": "yann_manual_review",
    "selection_source": "manual",
    "llm_assist_used": False,
    "human_review_required": False,
    "collected_at": "2026-04-29T12:00:00Z",
    "script_version": "phase6_1_c_v1",
    "public_only": True,
    "partition": "train",
    "partition_pinned_at": "2026-04-29T12:00:00Z",
}


def test_packet_loads_as_llm_evidence_packet(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "packet.json").read_text(encoding="utf-8"),
    )
    packet = LLMEvidencePacket.model_validate(body)
    assert packet.event_id, "packet event_id must be non-empty"
    assert len(packet.evidence_items) >= 1


def test_tool_policy_loads_as_tool_policy(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "tool_policy.json").read_text(encoding="utf-8"),
    )
    policy = ToolPolicy.model_validate(body)
    assert policy.allow_network is False, (
        "bundle policy must default allow_network=false"
    )
    assert policy.allow_write is False, (
        "bundle policy must default allow_write=false"
    )
    assert "pytest" in policy.allowed_tools


def test_gateway_definitions_load_per_tool(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "gateway_definitions.json").read_text(
            encoding="utf-8",
        ),
    )
    assert isinstance(body, dict)
    for name, payload in body.items():
        defn = GatewayToolDefinition.model_validate(payload)
        assert defn.tool_name == name
        assert defn.requires_network is False
        assert defn.allows_write is False


def test_approved_tools_loads_as_admission_registry(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "approved_tools.json").read_text(encoding="utf-8"),
    )
    registry = ToolAdmissionRegistry.model_validate(body)
    assert len(registry.approved) >= 1
    for decision in registry.approved:
        assert decision.status == "approved_read_only"
        assert len(decision.fingerprint.combined_sha256) == 64


def test_pass1_forward_loads_as_forward_result(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "pass1_forward.json").read_text(encoding="utf-8"),
    )
    result = ForwardVerificationResult.model_validate(body)
    assert result.event_id
    # pass1 must request pytest on the test_scope.
    assert len(result.requested_tools) == 1
    assert result.requested_tools[0].tool == "pytest"


def test_pass1_backward_loads_as_list_of_backward_results(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "pass1_backward.json").read_text(
            encoding="utf-8",
        ),
    )
    assert isinstance(body, list), (
        "pass1_backward.json must be a JSON list per ADR-57"
    )
    # Empty list is allowed (the keystone shape).
    for entry in body:
        BackwardVerificationResult.model_validate(entry)


def test_pass2_forward_loads_as_forward_result(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "pass2_forward.json").read_text(encoding="utf-8"),
    )
    result = ForwardVerificationResult.model_validate(body)
    assert result.event_id


def test_pass2_backward_loads_as_list_of_backward_results(
    tmp_path: Path,
) -> None:
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    body = json.loads(
        (out / "pass2_backward.json").read_text(
            encoding="utf-8",
        ),
    )
    assert isinstance(body, list), (
        "pass2_backward.json must be a JSON list per ADR-57"
    )
    assert len(body) >= 1, (
        "pass2_backward.json must carry at least one "
        "BackwardVerificationResult entry per claim"
    )
    for entry in body:
        result = BackwardVerificationResult.model_validate(entry)
        assert result.claim_id == _FIXTURE_RECORD["claim_id"]


def test_all_eight_files_runtime_load(tmp_path: Path) -> None:
    """End-to-end smoke: every required bundle file loads
    through its target Pydantic contract without failure.

    This is the consolidated guard cgpro QA/A45 step 1
    requested. The individual per-file tests above let the
    failure mode point at the broken file; this aggregate
    test ensures all-or-nothing acceptance.
    """
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)

    LLMEvidencePacket.model_validate(
        json.loads((out / "packet.json").read_text(encoding="utf-8")),
    )
    ToolPolicy.model_validate(
        json.loads((out / "tool_policy.json").read_text(encoding="utf-8")),
    )
    defs = json.loads(
        (out / "gateway_definitions.json").read_text(encoding="utf-8"),
    )
    for payload in defs.values():
        GatewayToolDefinition.model_validate(payload)
    ToolAdmissionRegistry.model_validate(
        json.loads(
            (out / "approved_tools.json").read_text(encoding="utf-8"),
        ),
    )
    ForwardVerificationResult.model_validate(
        json.loads(
            (out / "pass1_forward.json").read_text(encoding="utf-8"),
        ),
    )
    p1b = json.loads(
        (out / "pass1_backward.json").read_text(encoding="utf-8"),
    )
    assert isinstance(p1b, list)
    for entry in p1b:
        BackwardVerificationResult.model_validate(entry)
    ForwardVerificationResult.model_validate(
        json.loads(
            (out / "pass2_forward.json").read_text(encoding="utf-8"),
        ),
    )
    p2b = json.loads(
        (out / "pass2_backward.json").read_text(encoding="utf-8"),
    )
    assert isinstance(p2b, list) and len(p2b) >= 1
    for entry in p2b:
        BackwardVerificationResult.model_validate(entry)
