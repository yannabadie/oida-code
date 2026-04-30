"""G-6d.4 pre-freeze screening stop guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_PATH = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_REPORT_DIR = _REPO_ROOT / "reports" / "phase6_d_4_candidate_screening_stop"
_SCREENING_PATH = _REPORT_DIR / "screening.json"
_PROTOCOL_PATH = _REPO_ROOT / "docs" / "calibration_seed_expansion_protocol.md"
_AGENTS_PATH = _REPO_ROOT / "AGENTS.md"

_ACCEPTED_FOR_FUTURE = {
    "seed_074_simonw_sqlite_utils_658",
    "seed_159_hynek_structlog_759",
}
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


def _screening() -> dict[str, Any]:
    return _json(_SCREENING_PATH)


def test_g6d4_stop_does_not_advance_live_index() -> None:
    records = _json(_INDEX_PATH)
    pinned = [r for r in records if r.get("partition") in {"train", "holdout"}]
    train = [r for r in pinned if r.get("partition") == "train"]
    holdout = [r for r in pinned if r.get("partition") == "holdout"]
    index = {record["case_id"]: record for record in records}

    assert len(records) == 46
    assert len(pinned) == 14
    assert len(train) == 10
    assert len(holdout) == 4

    for case_id in _ACCEPTED_FOR_FUTURE:
        record = index[case_id]
        assert record["partition"] is None
        assert record["partition_pinned_at"] is None
        assert record["label_source"] == "unknown_not_for_metrics"
        assert record["llm_assist_used"] is False


def test_g6d4_screening_records_pre_freeze_stop_semantics() -> None:
    report = _screening()
    flags = report["decision_flags"]
    corpus = report["current_live_corpus"]
    partition_policy = report["partition_policy"]

    assert report["status"] == "stopped_before_freeze"
    assert flags["freeze_performed"] is False
    assert flags["live_index_changed"] is False
    assert flags["partial_freeze_allowed"] is False
    assert flags["exact_four_required"] is True
    assert flags["post_freeze_replacement_allowed"] is False
    assert flags["accepted_for_possible_freeze_count"] == 2
    assert corpus == {
        "total_records": 46,
        "pinned": 14,
        "train": 10,
        "holdout": 4,
        "unpinned": 32,
    }
    assert partition_policy == {
        "valid_tranche_size": 4,
        "valid_train_delta": 3,
        "valid_holdout_delta": 1,
        "fewer_than_four_clean_candidates": "stop_before_freeze",
        "partial_freeze": "forbidden",
    }


def test_g6d4_candidate_actions_keep_only_two_for_future_freeze() -> None:
    actions = {
        candidate["case_id"]: candidate["action"]
        for candidate in _screening()["candidate_actions"]
    }

    assert {
        case_id
        for case_id, action in actions.items()
        if action == "accept_for_possible_future_freeze"
    } == _ACCEPTED_FOR_FUTURE
    assert actions["seed_071_simonw_sqlite_utils_689"] == "needs_more_screening"
    assert actions["seed_058_pallets_itsdangerous_378"] == "defer"
    assert actions["seed_060_simonw_sqlite_utils_693"] == "reject"
    assert actions["seed_109_encode_httpx_3690"] == "reject"
    assert len(_ACCEPTED_FOR_FUTURE) < _screening()["partition_policy"][
        "valid_tranche_size"
    ]


def test_g6d4_stop_does_not_create_pinning_or_replay_outputs() -> None:
    scope = _screening()["scope"]

    assert not (_REPO_ROOT / "reports" / "phase6_d_4_pinning").exists()
    assert not (_REPORT_DIR / "round_trip_outputs").exists()
    assert scope["provider_api_calls"] == 0
    assert scope["pat_github_used"] is False
    assert scope["fresh_github_api_used"] is False
    assert scope["replay_outputs_created"] == 0
    assert scope["round_trip_outputs_created"] == 0
    assert scope["runtime_path_changed"] is False
    assert scope["clone_helper_flags_added"] == 0
    assert scope["requirements_file_support_added"] is False
    assert scope["github_action_changes_required"] is False


def test_g6d4_protocol_records_exact_four_rule_and_autonomous_protocol() -> None:
    protocol = _PROTOCOL_PATH.read_text(encoding="utf-8").lower()
    normalized_protocol = " ".join(protocol.split())
    agents = _AGENTS_PATH.read_text(encoding="utf-8").lower()

    assert "g-6d.4 exact-four pre-freeze stop rule" in protocol
    assert "exactly four clean candidates" in normalized_protocol
    assert "stop before freeze" in normalized_protocol
    assert "no partial freeze" in normalized_protocol
    assert "evidence-led autonomous block protocol" in agents
    assert "cgpro is the decision channel" in agents
    assert "codex is the local control plane" in agents


def test_g6d4_stop_artifacts_do_not_make_product_or_closure_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            _SCREENING_PATH,
            _REPORT_DIR / "screening.md",
            _REPO_ROOT / "QA" / "A57.md",
        )
    )

    assert "g-6d remains open" in combined
    assert "no live corpus advance" in combined
    for phrase in _FORBIDDEN_PRODUCT_VERDICT_PHRASES:
        assert phrase not in combined
