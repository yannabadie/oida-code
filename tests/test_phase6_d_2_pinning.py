"""Phase 6.d.2 corpus pinning guards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_PATH = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_ADR70_PLAN_PATH = (
    _REPO_ROOT / "reports" / "phase6_d_corpus_expansion_plan" / "plan.json"
)
_G6D1_SELECTION_PATH = (
    _REPO_ROOT / "reports" / "phase6_d_1_pinning" / "selection.json"
)
_REPORT_DIR = _REPO_ROOT / "reports" / "phase6_d_2_pinning"
_SELECTION_PATH = _REPORT_DIR / "selection.json"
_FEASIBILITY_PATH = _REPORT_DIR / "feasibility.json"

_G6D2_CASE_IDS = {
    "seed_037_tiangolo_typer_1695",
    "seed_075_simonw_sqlite_utils_653",
    "seed_161_hynek_structlog_757",
    "seed_162_hynek_structlog_756",
}
_FREEZE_AT = "2026-04-30T07:18:00Z"
_AI_AUTHORED_LABEL = "ai_authored_public_diff_review"
_FORBIDDEN_PRODUCT_VERDICT_PHRASES = (
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
    "product-safe",
    "broadly generalizes",
    "future replay correctness is validated",
    "g-6d is closed",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_records() -> list[dict[str, Any]]:
    return _json(_INDEX_PATH)


def _selection() -> dict[str, Any]:
    return _json(_SELECTION_PATH)


def _feasibility() -> dict[str, Any]:
    return _json(_FEASIBILITY_PATH)


def _index_by_case_id() -> dict[str, dict[str, Any]]:
    return {record["case_id"]: record for record in _index_records()}


def _adr71_pinned_baseline() -> set[str]:
    adr70_ids = set(_json(_ADR70_PLAN_PATH)["current_corpus"]["pinned_case_ids"])
    g6d1_ids = {
        case["case_id"]
        for case in _json(_G6D1_SELECTION_PATH)["selected_cases"]
    }
    return adr70_ids | g6d1_ids


def test_live_index_counts_after_g6d2() -> None:
    records = _index_records()
    pinned = [r for r in records if r.get("partition") in {"train", "holdout"}]
    train = [r for r in pinned if r.get("partition") == "train"]
    holdout = [r for r in pinned if r.get("partition") == "holdout"]

    assert len(records) == 46
    assert len(pinned) == 14
    assert len(train) == 10
    assert len(holdout) == 4
    assert len(holdout) / len(pinned) == 4 / 14


def test_g6d2_selected_cases_are_exact_new_pins() -> None:
    adr71_pinned_ids = _adr71_pinned_baseline()
    selection_cases = _selection()["selected_cases"]
    selected_ids = {case["case_id"] for case in selection_cases}

    assert len(adr71_pinned_ids) == 10
    assert selected_ids == _G6D2_CASE_IDS
    assert selected_ids.isdisjoint(adr71_pinned_ids)

    selected_partitions = {case["case_id"]: case["partition"] for case in selection_cases}
    assert sum(1 for v in selected_partitions.values() if v == "train") == 3
    assert sum(1 for v in selected_partitions.values() if v == "holdout") == 1

    index = _index_by_case_id()
    for case_id, partition in selected_partitions.items():
        assert index[case_id]["partition"] == partition
        assert index[case_id]["partition_pinned_at"] == _FREEZE_AT


def test_selected_records_keep_ai_authored_open_review_provenance() -> None:
    index = _index_by_case_id()
    for case_id in _G6D2_CASE_IDS:
        record = index[case_id]
        assert record["label_source"] == _AI_AUTHORED_LABEL
        assert record["human_review_required"] is True
        assert record["llm_assist_used"] is True
        assert record["expected_grounding_outcome"] == "evidence_present"
        assert record["partition_pinned_at"] == _FREEZE_AT
        for field in (
            "claim_id",
            "claim_type",
            "claim_text",
            "test_scope",
            "candidate_reason",
        ):
            assert isinstance(record.get(field), str) and record[field]
        assert isinstance(record.get("evidence_items"), list)
        assert len(record["evidence_items"]) >= 2


def test_deterministic_holdout_rule_selects_seed_161() -> None:
    selected_ids = sorted(case["case_id"] for case in _selection()["selected_cases"])
    expected_hashes = {
        case_id: hashlib.sha256(f"g6d2-holdout:{case_id}".encode()).hexdigest()
        for case_id in selected_ids
    }
    rule = _selection()["deterministic_partition_rule"]

    assert rule["hashes"] == expected_hashes
    assert min(expected_hashes, key=expected_hashes.__getitem__) == (
        "seed_161_hynek_structlog_757"
    )
    assert rule["holdout_case_id"] == "seed_161_hynek_structlog_757"


def test_selection_artifact_records_pre_outcome_boundaries() -> None:
    selection = _selection()
    scope = selection["scope"]
    provenance = selection["authoring_provenance"]

    assert selection["partition_freeze_at"] == _FREEZE_AT
    assert selection["pre_outcome_screened_at"] < selection["partition_freeze_at"]
    assert scope["provider_calls"] == 0
    assert scope["pat_github_used"] is False
    assert scope["fresh_github_api_used"] is False
    assert scope["replay_outputs_created"] == 0
    assert scope["pytest_outcome_inspected_before_freeze"] is False
    assert provenance["label_source"] == _AI_AUTHORED_LABEL
    assert provenance["human_review_required"] is True
    assert provenance["llm_assist_used"] is True

    for case in selection["selected_cases"]:
        checklist = case["checklist"]
        assert checklist["diff_inspected_before_freeze"] is True
        assert checklist["narrow_claim"] is True
        assert checklist["narrow_test_scope"] is True
        assert checklist["implementation_or_diff_evidence"] is True
        assert checklist["test_or_runnable_scope_evidence"] is True
        assert checklist["provider_output_used_as_evidence"] is False
        assert checklist["partition_frozen_before_pytest"] is True


def test_feasibility_artifact_is_post_freeze_and_all_green() -> None:
    feasibility = _feasibility()
    results = feasibility["results"]

    assert feasibility["partition_freeze_at"] == _FREEZE_AT
    assert feasibility["post_freeze_started_at"] > _FREEZE_AT
    assert feasibility["aggregate"] == {
        "cases": 4,
        "passed": 4,
        "failed": 0,
        "flaky": 0,
    }
    assert {result["case_id"] for result in results} == _G6D2_CASE_IDS

    for result in results:
        assert result["clone_started_at"] > _FREEZE_AT
        assert result["pytest_completed_at"] >= result["clone_started_at"]
        assert result["pytest_exit_code"] == 0
        assert "clone_target_at_sha.py" in result["clone_command"]
        assert " -m pytest " in result["pytest_command"]
        assert "passed" in result["pytest_summary"]
        assert result["base_sha"]
        assert result["head_sha"]


def test_g6d2_artifacts_do_not_create_replay_outputs_or_product_claims() -> None:
    assert not (_REPORT_DIR / "round_trip_outputs").exists()

    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            _REPORT_DIR / "selection.json",
            _REPORT_DIR / "selection.md",
            _REPORT_DIR / "feasibility.json",
            _REPORT_DIR / "feasibility.md",
        )
    )
    assert "provider output is not non-llm evidence" in combined
    assert "g-6d remains open" in combined
    for phrase in _FORBIDDEN_PRODUCT_VERDICT_PHRASES:
        assert phrase not in combined


def test_adr70_and_adr71_artifacts_stay_historical_after_g6d2() -> None:
    assert _json(_ADR70_PLAN_PATH)["current_corpus"]["pinned_count"] == 6
    assert len(_json(_G6D1_SELECTION_PATH)["selected_cases"]) == 4
    assert len(_selection()["selected_cases"]) == 4
