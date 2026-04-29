"""Phase 6.d.0 corpus-expansion planning for the calibration_seed lane.

This script is deliberately planning-only. It reads the existing
``reports/calibration_seed/index.json`` corpus, computes the current pinned
state, and emits a deterministic plan for the next empirical G-6d tranche.

It does not add seed records, change partitions, call providers, call GitHub,
create replay bundles, or touch runtime code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "phase6_d_0_corpus_expansion_plan_v1"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INDEX = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_DEFAULT_OUT_DIR = _REPO_ROOT / "reports" / "phase6_d_corpus_expansion_plan"

_EXPECTED_CURRENT_PINNED = 6
_EXPECTED_CURRENT_HOLDOUT = 2
_TARGET_MIN_PINNED = 20
_FIRST_TRANCHE_TOTAL = 4
_FIRST_TRANCHE_TRAIN = 3
_FIRST_TRANCHE_HOLDOUT = 1
_FULL_TARGET_TRAIN_ADDITIONS = 10
_FULL_TARGET_HOLDOUT_ADDITIONS = 4
_RATIO_MIN = 0.20
_RATIO_MAX = 0.40


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_index(index_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"{_rel(index_path)} must be a JSON array")
    records: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise SystemExit(f"{_rel(index_path)} entry {idx} must be an object")
        if not isinstance(entry.get("case_id"), str):
            raise SystemExit(f"{_rel(index_path)} entry {idx} missing case_id")
        records.append(entry)
    return records


def _count_partitions(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"train": 0, "holdout": 0, "unpinned": 0}
    for record in records:
        partition = record.get("partition")
        if partition == "train":
            counts["train"] += 1
        elif partition == "holdout":
            counts["holdout"] += 1
        elif partition is None:
            counts["unpinned"] += 1
        else:
            case_id = record["case_id"]
            raise SystemExit(f"{case_id}: unsupported partition {partition!r}")
    return counts


def _ratio(holdout_count: int, pinned_count: int) -> float:
    if pinned_count == 0:
        return 0.0
    return round(holdout_count / pinned_count, 2)


def build_plan(records: list[dict[str, Any]], *, index_path: Path) -> dict[str, Any]:
    counts = _count_partitions(records)
    train_count = counts["train"]
    holdout_count = counts["holdout"]
    pinned_count = train_count + holdout_count
    unpinned_count = counts["unpinned"]

    if pinned_count != _EXPECTED_CURRENT_PINNED or holdout_count != _EXPECTED_CURRENT_HOLDOUT:
        raise SystemExit(
            "G-6d.0 plan is stale: expected current pinned=6 and holdout=2, "
            f"got pinned={pinned_count} holdout={holdout_count}",
        )

    additions_required = _TARGET_MIN_PINNED - pinned_count
    first_result_pinned = pinned_count + _FIRST_TRANCHE_TOTAL
    first_result_train = train_count + _FIRST_TRANCHE_TRAIN
    first_result_holdout = holdout_count + _FIRST_TRANCHE_HOLDOUT
    full_result_train = train_count + _FULL_TARGET_TRAIN_ADDITIONS
    full_result_holdout = holdout_count + _FULL_TARGET_HOLDOUT_ADDITIONS
    full_result_pinned = full_result_train + full_result_holdout

    return {
        "plan_id": "phase6_d_0_corpus_expansion_plan",
        "script_version": SCRIPT_VERSION,
        "planning_date": "2026-04-29",
        "source_index": _rel(index_path),
        "scope": {
            "phase": "G-6d.0",
            "kind": "planning_and_instrumentation_only",
            "pins_added": 0,
            "partition_changes": 0,
            "new_replay_sets": 0,
            "round_trip_outputs_created": 0,
            "requires_provider_calls": False,
            "requires_pat_github": False,
            "runtime_path_changed": False,
        },
        "current_corpus": {
            "candidate_pool_count": len(records),
            "pinned_count": pinned_count,
            "train_count": train_count,
            "holdout_count": holdout_count,
            "unpinned_count": unpinned_count,
            "holdout_ratio": _ratio(holdout_count, pinned_count),
            "pinned_case_ids": [
                record["case_id"]
                for record in records
                if record.get("partition") in {"train", "holdout"}
            ],
        },
        "target": {
            "minimum_pinned_count": _TARGET_MIN_PINNED,
            "additions_required": additions_required,
            "allowed_holdout_ratio": {
                "min": _RATIO_MIN,
                "max": _RATIO_MAX,
            },
            "recommended_full_additions": {
                "total": additions_required,
                "train": _FULL_TARGET_TRAIN_ADDITIONS,
                "holdout": _FULL_TARGET_HOLDOUT_ADDITIONS,
                "resulting_pinned_count": full_result_pinned,
                "resulting_train_count": full_result_train,
                "resulting_holdout_count": full_result_holdout,
                "resulting_holdout_ratio": _ratio(full_result_holdout, full_result_pinned),
            },
        },
        "next_empirical_tranche": {
            "phase": "G-6d.1",
            "description": (
                "Pin four new cases from the existing 46-case index before "
                "any replay authoring."
            ),
            "total": _FIRST_TRANCHE_TOTAL,
            "train": _FIRST_TRANCHE_TRAIN,
            "holdout": _FIRST_TRANCHE_HOLDOUT,
            "resulting_pinned_count": first_result_pinned,
            "resulting_train_count": first_result_train,
            "resulting_holdout_count": first_result_holdout,
            "resulting_holdout_ratio": _ratio(first_result_holdout, first_result_pinned),
        },
        "candidate_policy": {
            "primary_pool": "reports/calibration_seed/index.json existing 46 inclusions",
            "fresh_github_harvesting": "defer_to_separate_block_if_needed",
            "accept_only_if": [
                "public_only is true",
                "merge_status is merged",
                "repo_url, pr_number, base_sha, and head_sha are non-null",
                "diff is inspectable without private data",
                "test_scope is narrow and runnable in the target checkout",
                "claim_id, claim_text, and claim_type are clear and non-verdict-like",
                "evidence_items include a diff or implementation fact",
                "evidence_items include a test result or runnable-scope fact",
                "partition is frozen before outcome inspection",
            ],
            "reject_or_defer_if": [
                "release-prep only",
                "dependency-only",
                "formatting-only",
                "generated-heavy",
                "non-Python-adapter-dependent",
                "over-broad test scope",
                "PR-comment-dependent",
                "requires clone-helper carve-out widening",
            ],
            "diversity_preference": (
                "Prefer repo and claim-type diversity only after evidence quality "
                "and runnable-scope quality are satisfied."
            ),
        },
        "seed_authoring_checklist": {
            "g6c_folded_into_g6d": True,
            "completion_required_before_future_pin": True,
            "checklist_path": "docs/calibration_seed_authoring_checklist.md",
            "protocol_path": "docs/calibration_seed_expansion_protocol.md",
        },
        "future_replay_review": {
            "inherits_adr68_static_audit": True,
            "inherits_adr69_manual_semantic_review": True,
            "provider_output_is_not_non_llm_evidence": True,
        },
        "backlog_status_after_success": {
            "g6d": "open",
            "g6d_0": "complete_after_this_plan_only",
            "g6c": "partially_addressed_until_checklist_is_exercised",
            "next_block": (
                "G-6d.1 pin 4 new cases from existing index, split 3 train / "
                "1 holdout, then clone and scoped-pytest feasibility."
            ),
        },
        "stop_conditions": [
            "implementation starts pinning cases",
            "implementation changes any partition",
            "implementation generates replays or round_trip_outputs",
            "index parse/count mismatch from pinned=6 holdout=2",
            "candidate policy uses provider judgment as evidence",
            "candidate policy uses post-outcome convenience",
            "candidate requires clone-helper carve-out widening",
            "plan implies G-6d is closed",
            "plan implies G-6c is closed by documentation alone",
            "plan claims broad generalisation or product safety",
            "fresh GitHub harvesting becomes required",
        ],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    current = plan["current_corpus"]
    target = plan["target"]
    tranche = plan["next_empirical_tranche"]
    scope = plan["scope"]
    status = plan["backlog_status_after_success"]

    lines = [
        "# Phase 6.d.0 corpus expansion plan",
        "",
        "This is a planning and instrumentation artifact only. It does not add",
        "new pinned cases, change train/holdout partitions, generate replay",
        "sets, call providers, call GitHub, or touch the runtime path.",
        "",
        "## Scope",
        "",
        f"- Phase: `{scope['phase']}`",
        f"- Pins added: `{scope['pins_added']}`",
        f"- Partition changes: `{scope['partition_changes']}`",
        f"- Provider calls required: `{scope['requires_provider_calls']}`",
        f"- PAT_GITHUB required: `{scope['requires_pat_github']}`",
        f"- Runtime path changed: `{scope['runtime_path_changed']}`",
        "",
        "## Current corpus",
        "",
        f"- Source index: `{plan['source_index']}`",
        f"- Candidate pool count: `{current['candidate_pool_count']}`",
        f"- Pinned count: `{current['pinned_count']}`",
        f"- Train count: `{current['train_count']}`",
        f"- Holdout count: `{current['holdout_count']}`",
        f"- Unpinned count: `{current['unpinned_count']}`",
        f"- Holdout ratio: `{current['holdout_ratio']:.2f}`",
        "",
        "## Target",
        "",
        f"- Minimum pinned count before larger-N claims: `{target['minimum_pinned_count']}`",
        f"- Required additions from current state: `{target['additions_required']}`",
        "- Allowed holdout ratio: "
        f"`{target['allowed_holdout_ratio']['min']:.2f}` to "
        f"`{target['allowed_holdout_ratio']['max']:.2f}`",
        "- Full target recommendation: "
        f"`+{target['recommended_full_additions']['train']}` train / "
        f"`+{target['recommended_full_additions']['holdout']}` holdout, "
        f"ending at `{target['recommended_full_additions']['resulting_pinned_count']}` "
        "pinned cases and "
        f"`{target['recommended_full_additions']['resulting_holdout_ratio']:.2f}` "
        "holdout ratio.",
        "",
        "## Next empirical tranche",
        "",
        f"- Phase: `{tranche['phase']}`",
        f"- New pins: `{tranche['total']}`",
        f"- Split: `{tranche['train']}` train / `{tranche['holdout']}` holdout",
        f"- Resulting pinned count: `{tranche['resulting_pinned_count']}`",
        f"- Resulting holdout ratio: `{tranche['resulting_holdout_ratio']:.2f}`",
        "",
        "## Candidate policy",
        "",
        f"- Primary pool: `{plan['candidate_policy']['primary_pool']}`",
        "- Fresh GitHub harvesting: "
        f"`{plan['candidate_policy']['fresh_github_harvesting']}`",
        "- Candidate diversity is secondary to evidence quality and scoped-test quality.",
        "- See `docs/calibration_seed_expansion_protocol.md` and",
        "  `docs/calibration_seed_authoring_checklist.md` before any future pin.",
        "",
        "## Backlog status",
        "",
        f"- G-6d after this plan: `{status['g6d']}`",
        f"- G-6d.0 after this plan: `{status['g6d_0']}`",
        f"- G-6c after this plan: `{status['g6c']}`",
        f"- Next block: {status['next_block']}",
        "",
        "Future LLM-authored replay sets inherit ADR-68 static audit and",
        "ADR-69 manual semantic review before replay content carries",
        "claim-supporting weight. Provider output is not non-LLM evidence.",
        "",
        "G-6d remains open after G-6d.0; this artifact only closes the",
        "planning/instrumentation sub-block.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(plan: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "plan.md").write_text(render_markdown(plan), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the Phase 6.d.0 calibration_seed expansion plan.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=_DEFAULT_INDEX,
        help="Path to reports/calibration_seed/index.json.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help="Directory where plan.json and plan.md are written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_index(args.index)
    plan = build_plan(records, index_path=args.index)
    write_outputs(plan, args.out_dir)
    print(f"wrote {_rel(args.out_dir / 'plan.json')}")
    print(f"wrote {_rel(args.out_dir / 'plan.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
