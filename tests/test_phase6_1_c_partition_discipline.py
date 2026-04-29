"""Phase 6.1'c (ADR-56) — partition discipline structural tests.

Per QA/A44 §"Pièges" item 46 + ADR-54 §"Holdout discipline":
the calibration_seed corpus must split into ``train`` / ``holdout``
partitions to prevent the bundle generator from being tuned
against its own evaluation set. These tests enforce the
discipline structurally:

1. Every record carries ``partition`` and
   ``partition_pinned_at`` fields (may both be null for
   partial records).
2. ``partition`` ∈ {``"train"``, ``"holdout"``, None} only.
3. ``partition`` non-null  ⇔  ``partition_pinned_at`` non-null.
4. Pinned (non-null partition) cases must be Tier-3-complete
   (claim_id, claim_type, claim_text, evidence_items,
   test_scope all set).
5. Pinned cases must have ``human_review_required=false``,
   ``expected_grounding_outcome`` ≠ ``"not_run"``,
   ``label_source`` ≠ ``"unknown_not_for_metrics"``.
6. Holdout fraction of (train + holdout) pool ∈ [0.20, 0.40]
   when ``N_pinned ≥ 5`` (warning-only at smaller N — the
   guard is documented but not asserted at very small N).
7. ``partition_pinned_at`` is a valid ISO 8601 UTC
   timestamp (``YYYY-MM-DDTHH:MM:SSZ``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_PATH = (
    _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
)

_ISO8601_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
)

_ALLOWED_PARTITIONS = (None, "train", "holdout")

_TIER_3_FIELDS: tuple[str, ...] = (
    "claim_id",
    "claim_type",
    "claim_text",
    "evidence_items",
    "test_scope",
)


def _load_index() -> list[dict[str, object]]:
    return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))


def test_index_has_partition_and_partition_pinned_at_fields() -> None:
    """Every inclusion record must carry both
    ``partition`` and ``partition_pinned_at`` keys (may be
    null)."""
    records = _load_index()
    assert records, "index.json must contain at least one record"
    missing: list[str] = []
    for r in records:
        cid = str(r.get("case_id", "<no case_id>"))
        if "partition" not in r:
            missing.append(f"{cid}: missing 'partition'")
        if "partition_pinned_at" not in r:
            missing.append(
                f"{cid}: missing 'partition_pinned_at'",
            )
    assert not missing, (
        "Phase 6.1'c (ADR-56) requires every record to carry "
        "partition + partition_pinned_at. Violations:\n  "
        + "\n  ".join(missing)
    )


def test_partition_value_is_in_allowlist() -> None:
    """partition ∈ {null, 'train', 'holdout'}."""
    bad: list[str] = []
    for r in _load_index():
        v = r.get("partition")
        if v not in _ALLOWED_PARTITIONS:
            bad.append(f"{r['case_id']}: partition={v!r}")
    assert not bad, (
        "partition must be one of {None, 'train', 'holdout'}. "
        "Violations:\n  " + "\n  ".join(bad)
    )


def test_partition_iff_pinned_at() -> None:
    """``partition`` is non-null  ⇔  ``partition_pinned_at``
    is non-null. Mismatched state is a discipline violation."""
    bad: list[str] = []
    for r in _load_index():
        p = r.get("partition")
        ts = r.get("partition_pinned_at")
        if (p is None) != (ts is None):
            bad.append(
                f"{r['case_id']}: partition={p!r} "
                f"partition_pinned_at={ts!r}",
            )
    assert not bad, (
        "partition and partition_pinned_at must both be set "
        "or both be null. Violations:\n  "
        + "\n  ".join(bad)
    )


def test_partition_pinned_at_is_iso8601_utc() -> None:
    """``partition_pinned_at`` (when set) must be ISO 8601
    UTC."""
    bad: list[str] = []
    for r in _load_index():
        ts = r.get("partition_pinned_at")
        if ts is None:
            continue
        if not isinstance(ts, str) or not _ISO8601_UTC_RE.match(
            ts,
        ):
            bad.append(f"{r['case_id']}: {ts!r}")
    assert not bad, (
        "partition_pinned_at must be ISO 8601 UTC "
        "(YYYY-MM-DDTHH:MM:SSZ). Violations:\n  "
        + "\n  ".join(bad)
    )


def test_pinned_records_are_tier3_complete() -> None:
    """A pinned case (non-null partition) must have all
    Tier-3 fields populated. Per ADR-54 + ADR-56."""
    bad: list[str] = []
    for r in _load_index():
        if r.get("partition") is None:
            continue
        for field_ in _TIER_3_FIELDS:
            v = r.get(field_)
            if v is None or (isinstance(v, list) and not v):
                bad.append(
                    f"{r['case_id']}: pinned but Tier-3 "
                    f"field {field_!r} is missing/empty",
                )
    assert not bad, (
        "pinned cases must be Tier-3-complete. Violations:"
        "\n  " + "\n  ".join(bad)
    )


def test_pinned_records_pass_hygiene_invariants() -> None:
    """Pinned cases must pass the hygiene invariants:
    human_review_required=false, expected_grounding_outcome
    ≠ 'not_run', label_source ≠ 'unknown_not_for_metrics'."""
    bad: list[str] = []
    for r in _load_index():
        if r.get("partition") is None:
            continue
        cid = r["case_id"]
        if r.get("human_review_required") is True:
            bad.append(
                f"{cid}: pinned but human_review_required=true",
            )
        if r.get("expected_grounding_outcome") == "not_run":
            bad.append(
                f"{cid}: pinned but "
                "expected_grounding_outcome='not_run'",
            )
        if r.get("label_source") == "unknown_not_for_metrics":
            bad.append(
                f"{cid}: pinned but "
                "label_source='unknown_not_for_metrics'",
            )
    assert not bad, (
        "pinned cases must pass hygiene invariants. "
        "Violations:\n  " + "\n  ".join(bad)
    )


def test_holdout_ratio_in_band_when_pool_large() -> None:
    """When N_pinned ≥ 5, the holdout fraction of the
    (train + holdout) pool must lie in [0.20, 0.40]. Below
    N_pinned=5 the test is informational only."""
    records = _load_index()
    pinned = [
        r for r in records if r.get("partition") is not None
    ]
    n = len(pinned)
    if n < 5:
        # informational — emit no failure but ensure ratio is
        # at least defined (no zero-division crash later)
        return
    holdout_n = sum(
        1 for r in pinned if r["partition"] == "holdout"
    )
    train_n = sum(
        1 for r in pinned if r["partition"] == "train"
    )
    pool = holdout_n + train_n
    assert pool == n, (
        "all pinned records must be 'train' or 'holdout' "
        "(no other label allowed once partition is set)"
    )
    ratio = holdout_n / pool
    assert 0.20 <= ratio <= 0.40, (
        f"holdout fraction {ratio:.2f} outside [0.20, 0.40] "
        f"(holdout={holdout_n} train={train_n})"
    )


def test_train_test_id_disjoint() -> None:
    """A given case_id must not appear in both partitions
    (vacuous in JSON-array shape — case_id is unique by
    construction — but kept as an explicit invariant for
    future schema migrations)."""
    records = _load_index()
    train_ids = {
        r["case_id"]
        for r in records
        if r.get("partition") == "train"
    }
    holdout_ids = {
        r["case_id"]
        for r in records
        if r.get("partition") == "holdout"
    }
    overlap = train_ids & holdout_ids
    assert not overlap, (
        "case_ids must not appear in both train and "
        f"holdout: {sorted(overlap)}"
    )


def test_seed_008_pinned_as_train() -> None:
    """seed_008 is the Phase 6.1'a worked example used to
    inform the bundle generator design. ADR-54 + ADR-56:
    seed_008 must be ``partition=train``."""
    records = _load_index()
    matches = [
        r
        for r in records
        if r.get("case_id") == "seed_008_pytest_dev_pytest_14407"
    ]
    assert len(matches) == 1, (
        "seed_008_pytest_dev_pytest_14407 must exist exactly "
        "once in index.json"
    )
    rec = matches[0]
    assert rec["partition"] == "train", (
        "seed_008 informed the generator's design and MUST "
        f"be partition='train' (got {rec['partition']!r})"
    )


def test_at_least_one_holdout_case_pinned() -> None:
    """Phase 6.1'c lands at least one holdout case so the
    discipline is non-vacuous from day 1."""
    records = _load_index()
    holdout_n = sum(
        1 for r in records if r.get("partition") == "holdout"
    )
    assert holdout_n >= 1, (
        "Phase 6.1'c must pin at least one HOLDOUT case so "
        "the discipline test is non-vacuous"
    )
