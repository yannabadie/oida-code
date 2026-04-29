"""Phase 6.a.1 / ADR-69 review artifact guards.

These tests validate the shape and hard-wall wording of the manual
semantic review artifact. They do not validate semantics; the semantics
come from the recorded human review against non-LLM evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPORT_DIR = _REPO_ROOT / "reports" / "phase6_a_semantic_replay_review"
_JSON_PATH = _REPORT_DIR / "review.json"
_MD_PATH = _REPORT_DIR / "review.md"

_EXPECTED_CASES = {
    "seed_008_pytest_dev_pytest_14407",
    "seed_065_simonw_sqlite_utils_680",
    "seed_018_python_attrs_attrs_1529",
}

_ALLOWED_OUTCOMES = {
    "manual_semantic_pass",
    "manual_semantic_fail",
    "ambiguous_insufficient_evidence",
}

_FORBIDDEN_PRODUCT_VERDICT_PHRASES = (
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
    "product-safe",
    "broadly generalizes",
    "future replay correctness is validated",
)


def _review() -> dict[str, Any]:
    return json.loads(_JSON_PATH.read_text(encoding="utf-8"))


def test_review_artifact_has_epistemic_boundary() -> None:
    review = _review()
    assert review["review_scope"] == "manual_archived_replay_semantic_alignment"
    assert review["semantic_replay_alignment_validated"] is True
    assert review["product_safety_validated"] is False
    assert review["predictive_validity_validated"] is False
    assert review["future_replay_correctness_validated"] is False


def test_review_artifact_covers_exact_three_load_bearing_cases() -> None:
    review = _review()
    cases = review["cases"]
    assert {case["case_id"] for case in cases} == _EXPECTED_CASES
    assert review["summary"] == {
        "case_count": 3,
        "manual_semantic_pass": 3,
        "manual_semantic_fail": 0,
        "ambiguous_insufficient_evidence": 0,
    }


def test_each_case_records_non_llm_evidence_chain() -> None:
    for case in _review()["cases"]:
        assert case["outcome"] in _ALLOWED_OUTCOMES
        assert case["seed_claim_id"].startswith("C.")
        assert case["seed_claim_text"]
        assert case["replay_dir"].startswith("reports/")
        assert set(case["reviewed_replay_files"]) == {
            "packet.json",
            "pass1_forward.json",
            "pass2_forward.json",
            "pass2_backward.json",
            "grounded_report.json",
        }
        assert len(case["non_llm_evidence_checked"]) >= 3

        upstream = case["upstream_evidence"]
        assert upstream["repo_url"].startswith("https://github.com/")
        assert isinstance(upstream["pr_number"], int)
        assert len(upstream["base_sha"]) == 40
        assert len(upstream["head_sha"]) == 40
        assert upstream["diff_summary"]
        assert "pytest" in upstream["pytest_rerun_command"]
        assert upstream["pytest_rerun_exit_code"] == 0
        assert "passed" in upstream["pytest_rerun_summary"]

        checks = case["semantic_checks"]
        assert checks
        assert all(value is True for value in checks.values())


def test_markdown_preserves_manual_review_boundary() -> None:
    body = _MD_PATH.read_text(encoding="utf-8").lower()
    normalized = " ".join(body.split())
    assert "manual_archived_replay_semantic_alignment" in body
    assert "does not validate product safety" in body
    assert "future llm-authored replay sets must inherit" in normalized
    for phrase in _FORBIDDEN_PRODUCT_VERDICT_PHRASES:
        assert phrase not in body
