"""Phase 4.3 (QA/A19.md, ADR-28) — calibration framework tests.

Five groups:

* Schema invariants on :class:`CalibrationCase`,
  :class:`ExpectedClaimLabel`, :class:`ExpectedCodeOutcome`,
  :class:`CalibrationProvenance`, :class:`CalibrationMetrics`.
* Metric helpers (``macro_f1_from_confusion``, ``precision``,
  ``recall``, ``safe_rate``, ``pairwise_order_accuracy``).
* Per-family runner correctness on tiny synthetic cases (claim,
  tool, shadow, safety).
* End-to-end smoke of the pilot dataset under
  ``datasets/calibration_v1/`` — every case loads, dispatches, and
  produces a result with zero official-field leaks.
* Manifest + provenance invariants — ``official_vnet_allowed`` is
  pinned to ``False``; ``contamination_risk`` ladders correctly.

NONE of these tests run pytest as a subprocess; the stability
script's pytest-real-execution path is exercised manually by the
operator (Windows fork-pressure constraint per
``feedback_windows_fork_pressure.md``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oida_code.calibration.metrics import (
    CalibrationMetrics,
    macro_f1_from_confusion,
    pairwise_order_accuracy,
    precision,
    recall,
    safe_rate,
)
from oida_code.calibration.models import (
    CalibrationCase,
    CalibrationManifest,
    CalibrationProvenance,
    ExpectedClaimLabel,
    ExpectedCodeOutcome,
    ExpectedToolResultLabel,
)
from oida_code.calibration.runner import (
    aggregate,
    load_case,
    run_case,
)


_DATASET_ROOT = Path(__file__).parent.parent / "datasets" / "calibration_v1"


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def test_calibration_case_is_frozen() -> None:
    case = CalibrationCase(
        case_id="x",
        family="claim_contract",
        provenance=CalibrationProvenance(
            source="synthetic", created_by="script",
        ),
        contamination_risk="synthetic",
    )
    with pytest.raises(ValidationError):
        case.case_id = "y"  # type: ignore[misc]


def test_expected_code_outcome_requires_f2p() -> None:
    with pytest.raises(ValidationError, match="at least one F2P"):
        ExpectedCodeOutcome(f2p_tests=())


def test_calibration_case_code_outcome_requires_expected_code_outcome() -> None:
    with pytest.raises(
        ValidationError, match="family='code_outcome' requires",
    ):
        CalibrationCase(
            case_id="X",
            family="code_outcome",
            provenance=CalibrationProvenance(
                source="synthetic", created_by="script",
            ),
            contamination_risk="synthetic",
        )


def test_calibration_case_non_code_family_rejects_code_outcome() -> None:
    with pytest.raises(
        ValidationError, match="only family='code_outcome' may set",
    ):
        CalibrationCase(
            case_id="X",
            family="claim_contract",
            expected_code_outcome=ExpectedCodeOutcome(
                f2p_tests=("tests/test.py::test_x",),
            ),
            provenance=CalibrationProvenance(
                source="synthetic", created_by="script",
            ),
            contamination_risk="synthetic",
        )


def test_calibration_case_shadow_requires_bucket() -> None:
    with pytest.raises(ValidationError, match="expected_shadow_bucket"):
        CalibrationCase(
            case_id="X",
            family="shadow_pressure",
            provenance=CalibrationProvenance(
                source="synthetic", created_by="script",
            ),
            contamination_risk="synthetic",
        )


def test_calibration_case_tool_grounded_requires_results() -> None:
    with pytest.raises(ValidationError, match="expected_tool_results"):
        CalibrationCase(
            case_id="X",
            family="tool_grounded",
            provenance=CalibrationProvenance(
                source="synthetic", created_by="script",
            ),
            contamination_risk="synthetic",
        )


def test_manifest_official_vnet_allowed_pinned_false() -> None:
    """ADR-28: the manifest must NEVER claim official_vnet_allowed=True."""
    with pytest.raises(ValidationError):
        CalibrationManifest.model_validate({
            "dataset_id": "x", "version": "0.1.0",
            "created_at": "2026-04-26", "families": {},
            "case_count": 0, "official_vnet_allowed": True,
        })


def test_calibration_metrics_official_field_leak_count_pinned_zero() -> None:
    """Metric schema literally cannot carry a non-zero leak count."""
    base = {
        "cases_total": 0, "cases_evaluated": 0,
        "cases_excluded_for_contamination": 0,
        "cases_excluded_for_flakiness": 0,
        "claim_accept_accuracy": 0.0, "claim_accept_macro_f1": 0.0,
        "unsupported_precision": 0.0, "rejected_precision": 0.0,
        "evidence_ref_precision": 0.0, "evidence_ref_recall": 0.0,
        "unknown_ref_rejection_rate": 0.0,
        "tool_contradiction_rejection_rate": 0.0,
        "tool_uncertainty_preservation_rate": 0.0,
        "sandbox_block_rate_expected": 0.0,
        "shadow_bucket_accuracy": 0.0,
        "shadow_pairwise_order_accuracy": 0.0,
        "f2p_pass_rate_on_expected_fixed": 0.0,
        "p2p_preservation_rate": 0.0,
        "flaky_case_count": 0,
        "safety_block_rate": 0.0,
        "fenced_injection_rate": 0.0,
    }
    # Default 0 is fine.
    CalibrationMetrics.model_validate(base)
    # Trying to set 1 fails.
    with pytest.raises(ValidationError):
        CalibrationMetrics.model_validate({**base, "official_field_leak_count": 1})


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def test_macro_f1_balanced() -> None:
    confusion = {
        "accepted": {"accepted": 5, "unsupported": 0, "rejected": 0},
        "unsupported": {"accepted": 0, "unsupported": 5, "rejected": 0},
        "rejected": {"accepted": 0, "unsupported": 0, "rejected": 5},
    }
    assert macro_f1_from_confusion(confusion) == pytest.approx(1.0)


def test_macro_f1_imbalanced_skewed() -> None:
    confusion = {
        "accepted": {"accepted": 10, "unsupported": 0, "rejected": 0},
        "unsupported": {"accepted": 1, "unsupported": 0, "rejected": 0},
        "rejected": {"accepted": 1, "unsupported": 0, "rejected": 0},
    }
    f1 = macro_f1_from_confusion(confusion)
    # Macro-F1 weights each class equally → much lower than accuracy
    # would suggest. Accuracy here is 10/12 = 0.83; macro F1 must be
    # well below that because two classes have 0 recall.
    assert f1 < 0.5


def test_pairwise_order_accuracy_basic() -> None:
    rank = {"a": "low", "b": "medium", "c": "high"}
    pairs = [("a", "b", "<"), ("b", "c", "<"), ("c", "a", ">")]
    assert pairwise_order_accuracy(pairs, rank) == pytest.approx(1.0)


def test_safe_rate_zero_denominator() -> None:
    assert safe_rate(3, 0) == 0.0


def test_precision_recall() -> None:
    assert precision(3, 1) == 0.75
    assert recall(3, 2) == 0.6


# ---------------------------------------------------------------------------
# Per-family runner correctness — tiny synthetic in-memory cases
# ---------------------------------------------------------------------------


def _write_minimal_claim_case(tmp_path: Path) -> Path:
    case_dir = tmp_path / "C_test"
    case_dir.mkdir()
    packet = {
        "event_id": "e1",
        "allowed_fields": ["capability"],
        "intent_summary": "x",
        "evidence_items": [{
            "id": "[E.intent.1]", "kind": "intent", "summary": "x",
            "source": "ticket", "confidence": 0.9,
        }],
        "deterministic_estimates": [],
    }
    (case_dir / "packet.json").write_text(json.dumps(packet), encoding="utf-8")
    forward = {
        "event_id": "e1",
        "supported_claims": [{
            "claim_id": "c-1", "event_id": "e1",
            "claim_type": "capability_sufficient",
            "statement": "ok", "confidence": 0.5,
            "evidence_refs": ["[E.intent.1]"],
            "source": "forward", "is_authoritative": False,
        }],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [], "warnings": [],
    }
    (case_dir / "forward.json").write_text(json.dumps(forward), encoding="utf-8")
    backward = [{
        "event_id": "e1", "claim_id": "c-1",
        "requirement": {
            "claim_id": "c-1",
            "required_evidence_kinds": ["intent"],
            "satisfied_evidence_refs": ["[E.intent.1]"],
            "missing_requirements": [],
        },
        "necessary_conditions_met": True,
    }]
    (case_dir / "backward.json").write_text(json.dumps(backward), encoding="utf-8")
    case = CalibrationCase(
        case_id="C_test",
        family="claim_contract",
        packet_path="packet.json",
        forward_replay_path="forward.json",
        backward_replay_path="backward.json",
        expected_claim_labels=(
            ExpectedClaimLabel(
                claim_id="c-1", event_id="e1",
                expected="accepted",
                reason="supported_by_forward_backward",
                required_evidence_refs=("[E.intent.1]",),
            ),
        ),
        provenance=CalibrationProvenance(
            source="synthetic", created_by="script",
        ),
        contamination_risk="synthetic",
    )
    (case_dir / "expected.json").write_text(
        case.model_dump_json(), encoding="utf-8",
    )
    return case_dir


def test_runner_claim_contract_happy_path(tmp_path: Path) -> None:
    case_dir = _write_minimal_claim_case(tmp_path)
    case = load_case(case_dir)
    result = run_case(case, case_dir)
    # Confusion matrix should record one accepted-true-positive.
    assert result.claim_confusion["accepted"]["accepted"] == 1
    assert result.official_field_leaks == 0


def test_runner_shadow_pressure_low_bucket(tmp_path: Path) -> None:
    case_dir = tmp_path / "S_test"
    case_dir.mkdir()
    scenario = {
        "name": "S_test",
        "description": "low pressure",
        "events": [{
            "id": "e1",
            "pattern_id": "p_S_test",
            "task": "src/a.py: clean",
            "capability": 0.5,
            "reversibility": 0.5,
            "observability": 0.5,
            "blast_radius": 0.3,
            "completion": 0.95,
            "tests_pass": 0.95,
            "operator_accept": 0.95,
            "benefit": 0.5,
            "preconditions": [
                {"name": "x", "weight": 1.0, "verified": True},
            ],
            "constitutive_parents": [],
            "supportive_parents": [],
            "invalidates_pattern": False,
        }],
    }
    (case_dir / "packet.json").write_text(
        json.dumps(scenario), encoding="utf-8",
    )
    case = CalibrationCase(
        case_id="S_test",
        family="shadow_pressure",
        packet_path="packet.json",
        expected_shadow_bucket="low",
        provenance=CalibrationProvenance(
            source="synthetic", created_by="script",
        ),
        contamination_risk="synthetic",
    )
    (case_dir / "expected.json").write_text(
        case.model_dump_json(), encoding="utf-8",
    )
    case_loaded = load_case(case_dir)
    result = run_case(case_loaded, case_dir)
    assert result.shadow_bucket_actual == "low"
    assert result.shadow_bucket_match is True


def test_runner_aggregates_into_metrics() -> None:
    """A trivial aggregation with one accepted + one unsupported case
    produces sane per-class precision."""
    from oida_code.calibration.runner import CaseResult

    results = [
        CaseResult(
            case_id="A", family="claim_contract",
            contamination_risk="synthetic",
            claim_confusion={
                "accepted": {"accepted": 1, "unsupported": 0, "rejected": 0},
                "unsupported": {"accepted": 0, "unsupported": 0, "rejected": 0},
                "rejected": {"accepted": 0, "unsupported": 0, "rejected": 0},
            },
        ),
        CaseResult(
            case_id="B", family="claim_contract",
            contamination_risk="synthetic",
            claim_confusion={
                "accepted": {"accepted": 0, "unsupported": 0, "rejected": 0},
                "unsupported": {"accepted": 0, "unsupported": 1, "rejected": 0},
                "rejected": {"accepted": 0, "unsupported": 0, "rejected": 0},
            },
        ),
    ]
    metrics = aggregate(results)
    assert metrics.cases_evaluated == 2
    assert metrics.claim_accept_accuracy == pytest.approx(1.0)
    assert metrics.official_field_leak_count == 0


def test_aggregate_excludes_public_high_contamination() -> None:
    from oida_code.calibration.runner import CaseResult

    results = [
        CaseResult(
            case_id="P", family="claim_contract",
            contamination_risk="public_high",
            claim_confusion={
                "accepted": {"accepted": 1, "unsupported": 0, "rejected": 0},
                "unsupported": {"accepted": 0, "unsupported": 0, "rejected": 0},
                "rejected": {"accepted": 0, "unsupported": 0, "rejected": 0},
            },
        ),
        CaseResult(
            case_id="S", family="claim_contract",
            contamination_risk="synthetic",
            claim_confusion={
                "accepted": {"accepted": 1, "unsupported": 0, "rejected": 0},
                "unsupported": {"accepted": 0, "unsupported": 0, "rejected": 0},
                "rejected": {"accepted": 0, "unsupported": 0, "rejected": 0},
            },
        ),
    ]
    metrics = aggregate(results)
    assert metrics.cases_evaluated == 1
    assert metrics.cases_excluded_for_contamination == 1


# ---------------------------------------------------------------------------
# Pilot dataset smoke
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _DATASET_ROOT.is_dir(),
    reason="run scripts/build_calibration_dataset.py first",
)
def test_pilot_dataset_loads_and_runs_with_zero_leaks() -> None:
    cases_dir = _DATASET_ROOT / "cases"
    cases = sorted(p for p in cases_dir.iterdir() if p.is_dir())
    assert len(cases) >= 32, f"pilot dataset has {len(cases)} cases, expected >= 32"
    leaks_total = 0
    for case_dir in cases:
        case = load_case(case_dir)
        result = run_case(case, case_dir)
        leaks_total += result.official_field_leaks
    assert leaks_total == 0


@pytest.mark.skipif(
    not _DATASET_ROOT.is_dir(),
    reason="run scripts/build_calibration_dataset.py first",
)
def test_pilot_dataset_has_all_five_families() -> None:
    cases_dir = _DATASET_ROOT / "cases"
    families = {load_case(p).family for p in cases_dir.iterdir() if p.is_dir()}
    assert families == {
        "claim_contract", "tool_grounded", "shadow_pressure",
        "code_outcome", "safety_adversarial",
    }


@pytest.mark.skipif(
    not _DATASET_ROOT.is_dir(),
    reason="run scripts/build_calibration_dataset.py first",
)
def test_pilot_dataset_code_outcome_cases_have_f2p() -> None:
    cases_dir = _DATASET_ROOT / "cases"
    code_cases = [
        load_case(p) for p in cases_dir.iterdir() if p.is_dir()
        and load_case(p).family == "code_outcome"
    ]
    assert len(code_cases) >= 6
    for case in code_cases:
        assert case.expected_code_outcome is not None
        assert case.expected_code_outcome.f2p_tests


@pytest.mark.skipif(
    not _DATASET_ROOT.is_dir(),
    reason="run scripts/build_calibration_dataset.py first",
)
def test_pilot_manifest_official_vnet_disabled() -> None:
    manifest_path = _DATASET_ROOT / "manifest.json"
    manifest = CalibrationManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    assert manifest.official_vnet_allowed is False
    assert manifest.public_claims_allowed is False


# ---------------------------------------------------------------------------
# ExpectedToolResultLabel sanity
# ---------------------------------------------------------------------------


def test_expected_tool_result_label_round_trip() -> None:
    label = ExpectedToolResultLabel(
        request_id="ruff:0",
        tool="ruff",
        expected_status="failed",
        expected_findings_min=1,
    )
    assert label.tool == "ruff"
    assert label.expected_status == "failed"
