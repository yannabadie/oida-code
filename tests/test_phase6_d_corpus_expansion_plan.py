"""Phase 6.d.0 / G-6d corpus-expansion planning guards."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "plan_g6d_corpus_expansion.py"
_INDEX_PATH = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_REPORT_DIR = _REPO_ROOT / "reports" / "phase6_d_corpus_expansion_plan"
_PLAN_JSON_PATH = _REPORT_DIR / "plan.json"
_PLAN_MD_PATH = _REPORT_DIR / "plan.md"
_PROTOCOL_PATH = _REPO_ROOT / "docs" / "calibration_seed_expansion_protocol.md"
_CHECKLIST_PATH = _REPO_ROOT / "docs" / "calibration_seed_authoring_checklist.md"

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


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_plan_g6d_corpus_expansion_for_tests",
        _SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _index() -> list[dict[str, Any]]:
    return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))


def _plan() -> dict[str, Any]:
    return json.loads(_PLAN_JSON_PATH.read_text(encoding="utf-8"))


def test_script_computes_current_index_counts() -> None:
    mod = _load_script()
    plan = mod.build_plan(_index(), index_path=_INDEX_PATH)

    assert plan["current_corpus"]["candidate_pool_count"] == 46
    assert plan["current_corpus"]["pinned_count"] == 6
    assert plan["current_corpus"]["train_count"] == 4
    assert plan["current_corpus"]["holdout_count"] == 2
    assert plan["current_corpus"]["unpinned_count"] == 40
    assert plan["current_corpus"]["holdout_ratio"] == 0.33


def test_checked_in_plan_matches_script_output() -> None:
    mod = _load_script()
    expected = mod.build_plan(_index(), index_path=_INDEX_PATH)
    assert _plan() == expected


def test_plan_is_planning_only_and_requires_no_external_calls() -> None:
    scope = _plan()["scope"]
    assert scope == {
        "phase": "G-6d.0",
        "kind": "planning_and_instrumentation_only",
        "pins_added": 0,
        "partition_changes": 0,
        "new_replay_sets": 0,
        "round_trip_outputs_created": 0,
        "requires_provider_calls": False,
        "requires_pat_github": False,
        "runtime_path_changed": False,
    }


def test_next_tranche_and_full_target_are_pinned() -> None:
    plan = _plan()
    tranche = plan["next_empirical_tranche"]
    assert tranche["phase"] == "G-6d.1"
    assert tranche["total"] == 4
    assert tranche["train"] == 3
    assert tranche["holdout"] == 1
    assert tranche["resulting_pinned_count"] == 10
    assert tranche["resulting_train_count"] == 7
    assert tranche["resulting_holdout_count"] == 3
    assert tranche["resulting_holdout_ratio"] == 0.3

    target = plan["target"]
    assert target["minimum_pinned_count"] == 20
    assert target["additions_required"] == 14
    assert target["allowed_holdout_ratio"] == {"min": 0.2, "max": 0.4}
    assert target["recommended_full_additions"] == {
        "total": 14,
        "train": 10,
        "holdout": 4,
        "resulting_pinned_count": 20,
        "resulting_train_count": 14,
        "resulting_holdout_count": 6,
        "resulting_holdout_ratio": 0.3,
    }


def test_g6c_checklist_is_required_but_not_claimed_closed() -> None:
    checklist = _plan()["seed_authoring_checklist"]
    assert checklist["g6c_folded_into_g6d"] is True
    assert checklist["completion_required_before_future_pin"] is True
    assert checklist["checklist_path"] == "docs/calibration_seed_authoring_checklist.md"
    assert checklist["protocol_path"] == "docs/calibration_seed_expansion_protocol.md"

    status = _plan()["backlog_status_after_success"]
    assert status["g6d"] == "open"
    assert status["g6d_0"] == "complete_after_this_plan_only"
    assert status["g6c"] == "partially_addressed_until_checklist_is_exercised"


def test_candidate_policy_rejects_known_bad_case_classes() -> None:
    policy = _plan()["candidate_policy"]
    reject = set(policy["reject_or_defer_if"])
    assert "release-prep only" in reject
    assert "dependency-only" in reject
    assert "formatting-only" in reject
    assert "generated-heavy" in reject
    assert "non-Python-adapter-dependent" in reject
    assert "over-broad test scope" in reject
    assert "PR-comment-dependent" in reject
    assert "requires clone-helper carve-out widening" in reject
    assert policy["fresh_github_harvesting"] == "defer_to_separate_block_if_needed"


def test_future_replay_sets_inherit_adr68_and_adr69() -> None:
    review = _plan()["future_replay_review"]
    assert review["inherits_adr68_static_audit"] is True
    assert review["inherits_adr69_manual_semantic_review"] is True
    assert review["provider_output_is_not_non_llm_evidence"] is True


def test_docs_and_report_preserve_hard_wall_wording() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (_PLAN_MD_PATH, _PROTOCOL_PATH, _CHECKLIST_PATH)
    )
    normalized = " ".join(combined.split())
    assert "planning and instrumentation" in normalized
    assert "does not add new pinned cases" in normalized
    assert "provider output is not non-llm evidence" in normalized
    assert "g-6d remains open" in normalized
    assert "g-6c" in normalized and "checklist" in normalized
    for phrase in _FORBIDDEN_PRODUCT_VERDICT_PHRASES:
        assert phrase not in combined


def test_index_state_remains_current_planning_baseline() -> None:
    records = _index()
    pinned = [r for r in records if r.get("partition") in {"train", "holdout"}]
    holdout = [r for r in pinned if r.get("partition") == "holdout"]
    train = [r for r in pinned if r.get("partition") == "train"]

    assert len(records) == 46
    assert len(pinned) == 6
    assert len(train) == 4
    assert len(holdout) == 2
    assert not (_REPORT_DIR / "round_trip_outputs").exists()
