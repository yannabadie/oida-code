"""Phase 6.1'b (ADR-55) — gateway bundle skeleton generator tests.

The generator turns a Tier-3-complete calibration_seed record
into an 8-file gateway bundle directory + a README. These
tests verify:

1. Generator emits 9 files for a complete record.
2. Output passes ``validate_gateway_bundle`` (structural
   correctness against the verifier's required-file set).
3. ``packet.json`` is Pydantic-valid against
   ``LLMEvidencePacket`` and carries the seed record's
   evidence_items verbatim.
4. The four ``pass*_*.json`` stubs are Pydantic-valid
   against ``ForwardVerificationResult`` /
   ``BackwardVerificationResult`` AND each carries the
   skeleton note in their ``warnings`` array.
5. Generator refuses if any Tier-3 field is missing/null
   (claim_id, claim_type, claim_text, test_scope,
   evidence_items).
6. Generator refuses if ``human_review_required`` is true.
7. Generator refuses if ``expected_grounding_outcome`` is
   ``"not_run"`` (a partial-record sentinel).
8. Generator never imports a network client / provider /
   MCP module (static check on the module's source).
9. Forbidden phrases (V_net / merge-safe / etc.) in the
   seed record are caught by the generator's pre-check.
10. Idempotence: regenerating into the same dir overwrites
    cleanly without orphans.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from oida_code.action_gateway.bundle import (
    REQUIRED_BUNDLE_FILES,
    validate_gateway_bundle,
)
from oida_code.bundle import (
    REQUIRED_TIER_3_FIELDS,
    BundleGenerationError,
    generate_bundle,
)
from oida_code.estimators.llm_prompt import LLMEvidencePacket
from oida_code.verifier.contracts import (
    BackwardVerificationResult,
    ForwardVerificationResult,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent

# A Tier-3-complete seed record matching seed_008's shape.
_FIXTURE_RECORD: dict[str, object] = {
    "case_id": "seed_test_owner_repo_42",
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
    "candidate_reason": "fixture for unit test",
    "claim_id": "C.fixture_surface.repair_needed",
    "claim_text": "After PR #42 the CLI accepts -x as alias for --xtra.",
    "claim_type": "repair_needed",
    "evidence_items": [
        {
            "id": "[E.event.1]",
            "kind": "event",
            "summary": "PR #42 adds -x alias to CLI parser; 8 lines.",
            "source": "git",
            "confidence": 0.9,
        },
        {
            "id": "[E.event.2]",
            "kind": "event",
            "summary": "Test test_xtra_alias asserts -x produces same exit code as --xtra.",
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
    "collected_at": "2026-04-28T12:00:00Z",
    "script_version": "phase6_1_a_pre_v1",
    "public_only": True,
}


def test_generator_emits_9_files(tmp_path: Path) -> None:
    """Generator produces 8 verifier-required files plus a
    README.md (per ADR-55)."""
    out = tmp_path / "bundle"
    bundle = generate_bundle(_FIXTURE_RECORD, out)
    assert len(bundle.files) == 9
    names = {p.name for p in bundle.files}
    expected = set(REQUIRED_BUNDLE_FILES) | {"README.md"}
    assert names == expected


def test_generator_passes_validate_gateway_bundle(
    tmp_path: Path,
) -> None:
    """The ADR-55 acceptance criterion: the generated bundle
    passes the existing structural validator."""
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    result = validate_gateway_bundle(out)
    assert result.ok, [
        f"{e.code}: {e.message}" for e in result.errors
    ]


def test_packet_is_pydantic_valid_with_evidence_items(
    tmp_path: Path,
) -> None:
    """packet.json validates against LLMEvidencePacket and
    carries the seed's evidence_items verbatim."""
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    packet_data = json.loads(
        (out / "packet.json").read_text(encoding="utf-8"),
    )
    packet = LLMEvidencePacket.model_validate(packet_data)
    assert len(packet.evidence_items) == 2
    ids = [e.id for e in packet.evidence_items]
    assert ids == ["[E.event.1]", "[E.event.2]"]
    assert packet.event_id == (
        "evt-seed_test_owner_repo_42"
    )


def test_pass_stubs_pydantic_valid_with_skeleton_warning(
    tmp_path: Path,
) -> None:
    """All four pass*_*.json stubs validate against the
    contract models AND carry the skeleton note in
    warnings[]."""
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)

    fwd1 = ForwardVerificationResult.model_validate(
        json.loads(
            (out / "pass1_forward.json").read_text(encoding="utf-8"),
        ),
    )
    bwd1 = BackwardVerificationResult.model_validate(
        json.loads(
            (out / "pass1_backward.json").read_text(encoding="utf-8"),
        ),
    )
    fwd2 = ForwardVerificationResult.model_validate(
        json.loads(
            (out / "pass2_forward.json").read_text(encoding="utf-8"),
        ),
    )
    bwd2 = BackwardVerificationResult.model_validate(
        json.loads(
            (out / "pass2_backward.json").read_text(encoding="utf-8"),
        ),
    )
    for replies, label in (
        (fwd1, "pass1_forward"),
        (bwd1, "pass1_backward"),
        (fwd2, "pass2_forward"),
        (bwd2, "pass2_backward"),
    ):
        warnings = list(replies.warnings)
        assert any("skeleton" in w.lower() for w in warnings), (
            f"{label} stub missing skeleton note in warnings: "
            f"{warnings}"
        )

    # pass1_forward must request pytest on the test_scope.
    assert len(fwd1.requested_tools) == 1
    spec = fwd1.requested_tools[0]
    assert spec.tool == "pytest"
    assert spec.scope == ("tests/test_cli.py::test_xtra_alias",)
    assert spec.expected_evidence_kind == "test_result"


def test_no_secrets_in_packet(tmp_path: Path) -> None:
    """The packet must not carry any secret-shaped value."""
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    raw = (out / "packet.json").read_text(encoding="utf-8").lower()
    forbidden = (
        "ghp_", "ghs_", "github_pat_", "sk-",  # API tokens
        "begin private key",
        "begin rsa private key",
    )
    for needle in forbidden:
        assert needle not in raw, (
            f"packet.json appears to carry secret: {needle}"
        )


@pytest.mark.parametrize("missing", REQUIRED_TIER_3_FIELDS)
def test_refuses_when_tier3_field_missing(
    tmp_path: Path, missing: str,
) -> None:
    """Generator refuses if any Tier-3 field is None or empty."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    if missing == "evidence_items":
        record[missing] = []
    else:
        record[missing] = None
    with pytest.raises(BundleGenerationError, match="Tier-3"):
        generate_bundle(record, tmp_path / "bundle")


def test_refuses_when_human_review_still_required(
    tmp_path: Path,
) -> None:
    """Generator refuses if human_review_required is true."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    record["human_review_required"] = True
    with pytest.raises(
        BundleGenerationError, match="human_review_required",
    ):
        generate_bundle(record, tmp_path / "bundle")


def test_refuses_when_expected_grounding_is_not_run(
    tmp_path: Path,
) -> None:
    """A seed record with expected_grounding_outcome='not_run'
    is a partial-record sentinel; the generator refuses."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    record["expected_grounding_outcome"] = "not_run"
    with pytest.raises(BundleGenerationError, match="not_run"):
        generate_bundle(record, tmp_path / "bundle")


def test_refuses_invalid_evidence_kind(tmp_path: Path) -> None:
    """Each evidence item's kind must be in the allowed
    Literal allowlist."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    record["evidence_items"][0]["kind"] = "unknown_kind"
    with pytest.raises(BundleGenerationError, match="kind"):
        generate_bundle(record, tmp_path / "bundle")


def test_refuses_confidence_out_of_range(tmp_path: Path) -> None:
    """confidence must lie in [0.0, 1.0]."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    record["evidence_items"][0]["confidence"] = 1.5
    with pytest.raises(BundleGenerationError, match="confidence"):
        generate_bundle(record, tmp_path / "bundle")


def test_refuses_forbidden_phrase_in_record(tmp_path: Path) -> None:
    """A seed record carrying any ADR-22/24/25/26 forbidden
    phrase is rejected before any file is written."""
    record = copy.deepcopy(_FIXTURE_RECORD)
    record["claim_text"] = (
        record["claim_text"] + " (production-safe per scope)"
    )
    with pytest.raises(BundleGenerationError, match="forbidden"):
        generate_bundle(record, tmp_path / "bundle")


def test_idempotent_regenerate(tmp_path: Path) -> None:
    """Re-running the generator into the same dir overwrites
    files cleanly without crashing or leaving orphans."""
    out = tmp_path / "bundle"
    generate_bundle(_FIXTURE_RECORD, out)
    first_listing = sorted(p.name for p in out.iterdir())
    generate_bundle(_FIXTURE_RECORD, out)
    second_listing = sorted(p.name for p in out.iterdir())
    assert first_listing == second_listing


# ---------------------------------------------------------------------------
# Static contract: the generator imports nothing forbidden.
# ---------------------------------------------------------------------------


_GENERATOR_PATH = (
    _REPO_ROOT / "src" / "oida_code" / "bundle" / "generator.py"
)


def test_generator_does_not_import_network_clients() -> None:
    """The generator must not import requests / httpx /
    huggingface_hub / urllib.request — it is local
    composition only."""
    body = _GENERATOR_PATH.read_text(encoding="utf-8")
    forbidden = (
        re.compile(r"^\s*import\s+requests\b", re.MULTILINE),
        re.compile(r"^\s*from\s+requests(\.|\s+)", re.MULTILINE),
        re.compile(r"^\s*import\s+httpx\b", re.MULTILINE),
        re.compile(r"^\s*from\s+httpx(\.|\s+)", re.MULTILINE),
        re.compile(
            r"^\s*import\s+huggingface_hub\b", re.MULTILINE,
        ),
        re.compile(
            r"^\s*from\s+huggingface_hub(\.|\s+)", re.MULTILINE,
        ),
        re.compile(
            r"^\s*import\s+urllib\.request\b", re.MULTILINE,
        ),
        re.compile(
            r"^\s*from\s+urllib\.request(\.|\s+)", re.MULTILINE,
        ),
    )
    for pat in forbidden:
        m = pat.search(body)
        assert m is None, (
            f"generator imports a forbidden network client: "
            f"{m.group(0).strip() if m else ''}"
        )


def test_generator_does_not_import_provider_modules() -> None:
    """The generator must not import any provider/MCP module."""
    body = _GENERATOR_PATH.read_text(encoding="utf-8")
    forbidden_substrings = (
        "from oida_code.providers",
        "import oida_code.providers",
        "modelcontextprotocol",
        "openai",
        "anthropic",
        "from .providers",
        "OptionalExternalLLMProvider",
        "OptionalExternalVerifierProvider",
    )
    for sub in forbidden_substrings:
        assert sub not in body, (
            f"generator references forbidden module/symbol: {sub!r}"
        )


def test_generator_carries_no_manual_egress_marker() -> None:
    """ADR-53 invariant 1: ``MANUAL_EGRESS_SCRIPT = True``
    is the marker for manual data-acquisition scripts under
    ``scripts/``. The bundle generator MUST NOT carry it; it
    is local composition only."""
    body = _GENERATOR_PATH.read_text(encoding="utf-8")
    assert not re.search(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b",
        body,
        re.MULTILINE,
    ), (
        "src/oida_code/bundle/generator.py must not set "
        "MANUAL_EGRESS_SCRIPT — that marker is reserved for "
        "scripts/ files (per ADR-53)."
    )
