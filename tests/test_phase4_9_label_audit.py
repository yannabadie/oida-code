"""Phase 4.9-E (QA/A26.md, ADR-34) — provider label audit UX tests.

Hard invariants from QA/A26 §4.9-E lines 350-353:

* The audit Markdown table standardises columns: case_id / field /
  expected / provider_value / classification / evidence_refs /
  action.
* The script NEVER mutates ``datasets/calibration_v1/cases/<id>/
  expected.json`` — it is a read-only diagnosis.
* Every label change is marked as a PROPOSAL with a recommended
  action, NOT auto-applied.
* The classification list now includes ``missing_capture`` so
  a Phase 4.8 V4 Pro 6/8 row remains visible after the Phase 4.9.0
  failure-path stash lands.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure scripts/ is on sys.path so we can import the audit script.
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


@pytest.fixture
def audit_module() -> Any:
    """Reload the script module fresh for each test (it has
    module-level state via argparse defaults that we never touch
    here, but the reload keeps tests independent)."""
    if "audit_provider_estimator_labels" in sys.modules:
        del sys.modules["audit_provider_estimator_labels"]
    return importlib.import_module("audit_provider_estimator_labels")


def _seed_dataset(
    tmp_path: Path,
    case_id: str = "L0XX",
    expected_estimates: list[dict[str, Any]] | None = None,
) -> Path:
    """Materialise a single-case dataset matching the script's
    expected layout."""
    dataset = tmp_path / "dataset"
    case_dir = dataset / "cases" / case_id
    case_dir.mkdir(parents=True)
    expected = {
        "family": "llm_estimator",
        "case_id": case_id,
        "expected_estimator_status": "shadow_ready",
        "expected_estimates": expected_estimates or [
            {
                "field": "capability",
                "expected_status": "accepted",
                "min_value": 0.4,
                "max_value": 0.8,
                "required_evidence_refs": ["E.event.1"],
            },
        ],
    }
    (case_dir / "expected.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8",
    )
    return dataset


def _seed_redacted_io(
    tmp_path: Path,
    case_id: str,
    *,
    failure_kind: str = "success",
    response_content: dict[str, Any] | None = None,
) -> Path:
    """Materialise a synthetic redacted_io directory."""
    redacted_io_dir = tmp_path / "redacted_io"
    redacted_io_dir.mkdir(exist_ok=True)
    if failure_kind == "success" and response_content is not None:
        body = json.dumps({
            "id": "chatcmpl-x",
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(response_content),
                    },
                    "finish_reason": "stop",
                },
            ],
        })
    else:
        body = ""
    payload = {
        "case_id": case_id,
        "prompt_sha256": "0" * 64,
        "redacted_response_body": body if body else None,
        "redacted_error": (
            None if failure_kind == "success"
            else f"synthetic {failure_kind}"
        ),
        "failure_kind": failure_kind,
        "model": "deepseek-v4-pro",
        "http_status": 200 if failure_kind == "success" else None,
        "wall_clock_ms": 100,
    }
    (redacted_io_dir / f"{case_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    return redacted_io_dir


# ---------------------------------------------------------------------------
# QA/A26 §4.9-E mandatory tests
# ---------------------------------------------------------------------------


def test_label_audit_markdown_has_classification_table(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """The rendered Markdown MUST include a table with the
    standardised columns: case_id / field / expected / provider_value
    / classification / evidence_refs (called required_refs in our
    table) / action."""
    dataset = _seed_dataset(tmp_path)
    redacted_io = _seed_redacted_io(
        tmp_path, "L0XX",
        response_content={
            "estimates": [
                {
                    "field": "capability",
                    "value": 0.6,
                    "confidence": 0.7,
                    "evidence_refs": ["E.event.1"],
                    "source": "llm",
                    "is_default": False,
                },
            ],
            "cited_evidence_refs": ["E.event.1"],
            "unsupported_claims": [],
        },
    )
    out_path = tmp_path / "audit.md"
    rows: list[dict[str, Any]] = []
    for case_dir in sorted((dataset / "cases").iterdir()):
        rows.extend(
            audit_module._audit_case(
                case_dir.name, case_dir, redacted_io,
            ),
        )
    audit_module._render_report(
        rows, provider_label="test-provider", out_path=out_path,
    )
    body = out_path.read_text(encoding="utf-8")
    # Standardised columns from QA/A26 line 319-326.
    for column in (
        "case_id", "field", "expected", "provider_value",
        "classification", "action",
    ):
        assert column in body, (
            f"audit Markdown table missing required column {column!r}"
        )
    # The action column carries the recommendation for the row.
    assert "no action — the provider matches the label" in body, (
        "the action column does not carry the recommendation text"
    )


def test_label_audit_never_changes_expected_labels_automatically(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """Running the audit on a case with a strict label MUST NOT
    rewrite ``expected.json`` even when the row is classified as
    ``label_too_strict``. The expected.json on disk is read-only
    from the script's perspective."""
    dataset = _seed_dataset(tmp_path)
    expected_path = dataset / "cases" / "L0XX" / "expected.json"
    expected_before = expected_path.read_text(encoding="utf-8")
    expected_mtime_before = expected_path.stat().st_mtime
    redacted_io = _seed_redacted_io(
        tmp_path, "L0XX",
        response_content={
            "estimates": [
                {
                    "field": "capability",
                    "value": 0.95,  # OUTSIDE [0.4, 0.8] → label_too_strict
                    "confidence": 0.7,
                    "evidence_refs": ["E.event.1"],
                    "source": "llm",
                    "is_default": False,
                },
            ],
            "cited_evidence_refs": ["E.event.1"],
            "unsupported_claims": [],
        },
    )
    out_path = tmp_path / "audit.md"
    rows = audit_module._audit_case(
        "L0XX", dataset / "cases" / "L0XX", redacted_io,
    )
    audit_module._render_report(
        rows, provider_label="test-provider", out_path=out_path,
    )

    # Expected.json MUST be byte-identical and untouched.
    expected_after = expected_path.read_text(encoding="utf-8")
    assert expected_after == expected_before, (
        "the audit script mutated expected.json — Phase 4.9-E "
        "criterion 'never changes labels automatically' violated"
    )
    expected_mtime_after = expected_path.stat().st_mtime
    assert expected_mtime_after == expected_mtime_before, (
        "expected.json mtime changed — the audit script wrote "
        "to it (a re-write with same content)"
    )

    # Verify the row WAS classified as label_too_strict (so the
    # test is exercising the meaningful path).
    assert any(r["classification"] == "label_too_strict" for r in rows), (
        "fixture did not produce a label_too_strict classification — "
        "test setup error, not a script bug"
    )


def test_label_audit_marks_label_changes_as_proposals(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """The rendered report MUST mark any suggested label change as
    a PROPOSAL — explicitly, in prose. The reader must NEVER walk
    away thinking the labels were modified."""
    dataset = _seed_dataset(tmp_path)
    redacted_io = _seed_redacted_io(
        tmp_path, "L0XX",
        response_content={
            "estimates": [
                {
                    "field": "capability",
                    "value": 0.95,  # → label_too_strict
                    "confidence": 0.7,
                    "evidence_refs": ["E.event.1"],
                    "source": "llm",
                    "is_default": False,
                },
            ],
            "cited_evidence_refs": ["E.event.1"],
            "unsupported_claims": [],
        },
    )
    out_path = tmp_path / "audit.md"
    rows = audit_module._audit_case(
        "L0XX", dataset / "cases" / "L0XX", redacted_io,
    )
    audit_module._render_report(
        rows, provider_label="test-provider", out_path=out_path,
    )
    body = out_path.read_text(encoding="utf-8")
    # The script must say so explicitly.
    assert "do not apply automatically" in body or "PROPOSAL" in body, (
        "audit report does not mark label changes as proposals — "
        "Phase 4.9-E criterion violated"
    )
    # And it must say it never writes back to expected.json.
    assert "never writes back to" in body or "Read-only diagnosis" in body, (
        "audit report does not state the read-only invariant"
    )


# ---------------------------------------------------------------------------
# Backstops
# ---------------------------------------------------------------------------


def test_label_audit_classifies_missing_capture(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """A case whose redacted_io is absent MUST get classification =
    `missing_capture` and an action recommending re-run with
    Phase 4.9.0 failure-path capture."""
    dataset = _seed_dataset(tmp_path)
    # Redacted_io directory exists but is EMPTY (the case_id file
    # is not there).
    redacted_io_dir = tmp_path / "empty_io"
    redacted_io_dir.mkdir()
    rows = audit_module._audit_case(
        "L0XX", dataset / "cases" / "L0XX", redacted_io_dir,
    )
    assert all(r["classification"] == "missing_capture" for r in rows), (
        f"missing redacted_io did NOT classify as missing_capture: "
        f"{[r['classification'] for r in rows]!r}"
    )
    assert all("Phase 4.9.0" in r["action"] for r in rows), (
        "missing_capture action does not point at Phase 4.9.0 fix"
    )


def test_label_audit_classifies_failed_capture(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """Phase 4.9.0 + 4.9-E: a captured file with
    ``failure_kind=invalid_shape`` (the V4 Pro 6/8 case) MUST get
    ``missing_capture`` classification with an action that names
    the failure_kind so the operator can act on it."""
    dataset = _seed_dataset(tmp_path)
    redacted_io = _seed_redacted_io(
        tmp_path, "L0XX", failure_kind="invalid_shape",
    )
    rows = audit_module._audit_case(
        "L0XX", dataset / "cases" / "L0XX", redacted_io,
    )
    assert all(r["classification"] == "missing_capture" for r in rows)
    # The observed text MUST point at the invalid_shape failure
    # so the operator can navigate to the file.
    assert all("invalid_shape" in r["observed"] for r in rows), (
        f"invalid_shape failure not surfaced in observed: "
        f"{[r['observed'] for r in rows]!r}"
    )


def test_label_audit_action_recommendations_are_documented(
    audit_module: Any,
) -> None:
    """The script's _ACTION_RECOMMENDATIONS map MUST cover every
    classification value the renderer can produce."""
    expected_classifications = {
        "match", "label_too_strict", "provider_wrong",
        "contract_gap", "mapping_ambiguous", "missing_capture",
    }
    actual = set(audit_module._ACTION_RECOMMENDATIONS.keys())
    assert expected_classifications == actual, (
        f"_ACTION_RECOMMENDATIONS map mismatch: "
        f"missing {expected_classifications - actual!r}; "
        f"extra {actual - expected_classifications!r}"
    )


def test_label_audit_provider_value_column_renders(
    tmp_path: Path,
    audit_module: Any,
) -> None:
    """The provider_value column MUST render even when no estimate
    was emitted (showing '(no estimate emitted)' rather than a
    crash or blank cell)."""
    dataset = _seed_dataset(tmp_path)
    # Provider returned valid response with NO estimate for the field.
    redacted_io = _seed_redacted_io(
        tmp_path, "L0XX",
        response_content={
            "estimates": [],  # empty
            "cited_evidence_refs": [],
            "unsupported_claims": [],
        },
    )
    out_path = tmp_path / "audit.md"
    rows = audit_module._audit_case(
        "L0XX", dataset / "cases" / "L0XX", redacted_io,
    )
    audit_module._render_report(
        rows, provider_label="test-provider", out_path=out_path,
    )
    body = out_path.read_text(encoding="utf-8")
    assert "(no estimate emitted)" in body
