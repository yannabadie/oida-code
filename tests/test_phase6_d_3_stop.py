"""Phase 6.d.3 stop-condition guards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_PATH = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_REPORT_DIR = _REPO_ROOT / "reports" / "phase6_d_3_pinning"
_SELECTION_PATH = _REPORT_DIR / "selection.json"
_STOP_PATH = _REPORT_DIR / "stop.json"

_G6D3_CASE_IDS = {
    "seed_058_pallets_itsdangerous_378",
    "seed_071_simonw_sqlite_utils_689",
    "seed_074_simonw_sqlite_utils_658",
    "seed_159_hynek_structlog_759",
}
_FREEZE_AT = "2026-04-30T09:18:00Z"
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


def _index_by_case_id() -> dict[str, dict[str, Any]]:
    return {record["case_id"]: record for record in _index_records()}


def _selection() -> dict[str, Any]:
    return _json(_SELECTION_PATH)


def _stop() -> dict[str, Any]:
    return _json(_STOP_PATH)


def test_g6d3_stop_does_not_advance_live_index() -> None:
    records = _index_records()
    pinned = [r for r in records if r.get("partition") in {"train", "holdout"}]
    train = [r for r in pinned if r.get("partition") == "train"]
    holdout = [r for r in pinned if r.get("partition") == "holdout"]

    assert len(records) == 46
    assert len(pinned) == 14
    assert len(train) == 10
    assert len(holdout) == 4

    index = _index_by_case_id()
    for case_id in _G6D3_CASE_IDS:
        record = index[case_id]
        assert record["partition"] is None
        assert record["partition_pinned_at"] is None
        assert record["label_source"] == "unknown_not_for_metrics"
        assert record["llm_assist_used"] is False


def test_g6d3_selection_is_frozen_attempt_not_successful_pin() -> None:
    selection = _selection()
    selected_cases = selection["selected_cases"]
    selected_ids = {case["case_id"] for case in selected_cases}

    assert selection["status"] == "stopped_after_freeze_before_successful_pinning"
    assert selection["live_index_update_committed"] is False
    assert selection["partition_freeze_at"] == _FREEZE_AT
    assert selected_ids == _G6D3_CASE_IDS
    assert sum(1 for case in selected_cases if case["partition"] == "train") == 3
    assert sum(1 for case in selected_cases if case["partition"] == "holdout") == 1


def test_g6d3_holdout_rule_remains_auditable_after_stop() -> None:
    selected_ids = sorted(case["case_id"] for case in _selection()["selected_cases"])
    expected_hashes = {
        case_id: hashlib.sha256(f"g6d3-holdout:{case_id}".encode()).hexdigest()
        for case_id in selected_ids
    }
    rule = _selection()["deterministic_partition_rule"]

    assert rule["hashes"] == expected_hashes
    assert min(expected_hashes, key=expected_hashes.__getitem__) == (
        "seed_159_hynek_structlog_759"
    )
    assert rule["holdout_case_id"] == "seed_159_hynek_structlog_759"


def test_g6d3_stop_artifact_records_bootstrap_failure_before_pytest() -> None:
    stop = _stop()
    failure = stop["failure"]

    assert stop["success"] is False
    assert stop["continue_current_block"] is False
    assert stop["failure_stage"] == "post_freeze_bootstrap_before_pytest"
    assert stop["partition_freeze_at"] == _FREEZE_AT
    assert stop["post_freeze_started_at"] > _FREEZE_AT
    assert stop["live_corpus_after_stop"] == {
        "source": "reports/calibration_seed/index.json",
        "total_records": 46,
        "pinned": 14,
        "train": 10,
        "holdout": 4,
        "note": (
            "ADR-73 did not commit a live index advance. "
            "These are the ADR-72 live counts."
        ),
    }

    assert failure["case_id"] == "seed_058_pallets_itsdangerous_378"
    assert failure["clone_exit_code"] == 1
    assert "clone_target_at_sha.py" in failure["clone_command"]
    assert "--install-group tests" in failure["clone_command"]
    assert failure["scoped_pytest_outcome_reached"] is False
    assert failure["diagnostic_pytest_attempt"]["exit_code"] == 1
    assert "No module named pytest" in failure["diagnostic_pytest_attempt"]["summary"]
    assert "requirements/tests.txt" in failure["target_dependency_evidence"]["tox_ini"]
    assert "pytest==8.1.1" in failure["target_dependency_evidence"][
        "requirements_tests_contains"
    ]


def test_g6d3_stop_forbids_rescue_or_replacement_after_freeze() -> None:
    decision = _stop()["cgpro_stop_decision"]

    assert decision == {
        "manual_requirements_install_allowed": False,
        "replacement_allowed_after_freeze": False,
        "successful_g6d3_commit_allowed": False,
        "reason": (
            "seed_058 had already been documented as the older "
            "requirements-pattern risk; rescuing it post-freeze would widen "
            "the dependency-install boundary inside ADR-73."
        ),
    }


def test_g6d3_stop_does_not_create_success_feasibility_or_replay_outputs() -> None:
    assert not (_REPORT_DIR / "feasibility.json").exists()
    assert not (_REPORT_DIR / "feasibility.md").exists()
    assert not (_REPORT_DIR / "round_trip_outputs").exists()

    scope = _stop()["scope"]
    assert scope["provider_calls_as_evidence"] == 0
    assert scope["pat_github_used"] is False
    assert scope["fresh_github_api_used"] is False
    assert scope["replay_outputs_created"] == 0
    assert scope["round_trip_outputs_created"] == 0
    assert scope["runtime_path_changed"] is False
    assert scope["clone_helper_flags_added"] == 0
    assert scope["src_changes_required"] is False
    assert scope["github_action_changes_required"] is False


def test_g6d3_stop_artifacts_do_not_make_product_or_closure_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            _REPORT_DIR / "selection.json",
            _REPORT_DIR / "selection.md",
            _REPORT_DIR / "stop.json",
            _REPORT_DIR / "stop.md",
        )
    )
    assert "provider output is not non-llm evidence" in combined
    assert "g-6d remains open" in combined
    assert "live corpus remains at the adr-72 state" in combined
    for phrase in _FORBIDDEN_PRODUCT_VERDICT_PHRASES:
        assert phrase not in combined
