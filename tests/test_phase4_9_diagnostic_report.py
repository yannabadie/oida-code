"""Phase 4.9-A (QA/A26.md, ADR-34) — diagnostic Markdown report tests.

Five mandatory tests from QA/A26 §4.9-A plus a small set of
backstops against future regressions (forbidden status enum
values, missing-metrics handling, on-disk write).

The diagnostic report is a presentation layer over the existing
``CalibrationMetrics`` + ``ProviderRedactedIO`` artifacts. It MUST:

* Open with the diagnostic banner.
* Show ``total_v_net`` / ``debt_final`` / ``corrupt_success`` as
  ``blocked`` (ADR-22).
* NEVER contain the words ``merge_safe`` / ``production_safe`` /
  ``bug_free`` / ``bug-free`` / ``production-safe`` / ``merge-safe``
  (criterion #6).
* Reference ``redacted_io/<file>.json`` paths but never the raw
  prompt body (sentinel in fixture confirms).
* Render the provider matrix as a readable Markdown table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oida_code.calibration.metrics import CalibrationMetrics
from oida_code.report.diagnostic_report import (
    _FORBIDDEN_DIAGNOSTIC_STATUSES,
    _FORBIDDEN_PRODUCT_CLAIMS,
    DiagnosticStatus,
    derive_diagnostic_status,
    render_diagnostic_markdown_from_dir,
    write_diagnostic_markdown,
)

_PROMPT_SENTINEL = (
    "OIDA-DIAGNOSTIC-REPORT-RAW-PROMPT-SENTINEL-Z9KF1L-DO-NOT-LEAK"
)


def _clean_metrics(**overrides: object) -> CalibrationMetrics:
    """Build a CalibrationMetrics with all rates at 1.0 (clean run)
    by default. Overrides let individual tests flip a single field
    without restating the whole dict."""
    base: dict[str, object] = {
        "cases_total": 8,
        "cases_evaluated": 8,
        "cases_excluded_for_contamination": 0,
        "cases_excluded_for_flakiness": 0,
        "claim_accept_accuracy": 1.0,
        "claim_accept_macro_f1": 1.0,
        "unsupported_precision": 1.0,
        "rejected_precision": 1.0,
        "evidence_ref_precision": 1.0,
        "evidence_ref_recall": 1.0,
        "unknown_ref_rejection_rate": 1.0,
        "tool_contradiction_rejection_rate": 1.0,
        "tool_uncertainty_preservation_rate": 1.0,
        "sandbox_block_rate_expected": 1.0,
        "shadow_bucket_accuracy": 1.0,
        "shadow_pairwise_order_accuracy": 1.0,
        "f2p_pass_rate_on_expected_fixed": None,
        "p2p_preservation_rate": None,
        "flaky_case_count": 0,
        "code_outcome_status": "not_computed",
        "safety_block_rate": 1.0,
        "fenced_injection_rate": 1.0,
        "estimator_status_accuracy": 0.625,
        "estimator_estimate_accuracy": 1.0,
        "estimator_cases_evaluated": 8,
        "estimator_cases_skipped": 0,
        "official_field_leak_count": 0,
        "notes": "phase4.9-a fixture",
    }
    base.update(overrides)
    return CalibrationMetrics.model_validate(base)


def _seed_input_dir(
    tmp_path: Path,
    *,
    metrics: CalibrationMetrics | None = None,
    per_case: list[dict[str, object]] | None = None,
    redacted_io: list[dict[str, object]] | None = None,
    stability: dict[str, object] | None = None,
) -> Path:
    """Materialise a synthetic <input-dir> on disk."""
    input_dir = tmp_path / "calibration"
    input_dir.mkdir()
    (input_dir / "metrics.json").write_text(
        (metrics or _clean_metrics()).model_dump_json(indent=2),
        encoding="utf-8",
    )
    if per_case is not None:
        (input_dir / "per_case.json").write_text(
            json.dumps(per_case, indent=2), encoding="utf-8",
        )
    if redacted_io is not None:
        (input_dir / "redacted_io").mkdir()
        for entry in redacted_io:
            case_id = entry.get("case_id") or "anon"
            (input_dir / "redacted_io" / f"{case_id}.json").write_text(
                json.dumps(entry, indent=2), encoding="utf-8",
            )
    if stability is not None:
        (input_dir / "stability_summary.json").write_text(
            json.dumps(stability, indent=2), encoding="utf-8",
        )
    return input_dir


# ---------------------------------------------------------------------------
# Five mandatory tests (QA/A26 §4.9-A)
# ---------------------------------------------------------------------------


def test_markdown_report_has_diagnostic_only_banner(tmp_path: Path) -> None:
    """Criterion #4: every output starts with the diagnostic banner."""
    input_dir = _seed_input_dir(tmp_path)
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    assert "Diagnostic only — not a merge verdict." in rendered, (
        "banner missing — Phase 4.9-A criterion #4 violated"
    )
    # Banner must be near the top of the document, not buried at the
    # end. Anything past line 10 means a reader scrolling a PR comment
    # might miss it.
    head = "\n".join(rendered.splitlines()[:10])
    assert "Diagnostic only — not a merge verdict." in head, (
        "banner present but buried below the first 10 lines"
    )


def test_markdown_report_has_official_fields_blocked_section(
    tmp_path: Path,
) -> None:
    """Criterion #5: status card shows total_v_net / debt_final /
    corrupt_success as `blocked` per ADR-22."""
    input_dir = _seed_input_dir(tmp_path)
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    assert "total_v_net`: **blocked**" in rendered
    assert "debt_final`: **blocked**" in rendered
    assert "corrupt_success`: **blocked**" in rendered
    assert "ADR-22" in rendered, (
        "the blocked status MUST cite ADR-22 so a reader can trace "
        "WHY those fields are unavailable"
    )


def test_markdown_report_does_not_contain_merge_safe(
    tmp_path: Path,
) -> None:
    """Criterion #6: forbidden product-claim words MUST NEVER appear.
    Locked over EVERY variant in `_FORBIDDEN_PRODUCT_CLAIMS`."""
    input_dir = _seed_input_dir(tmp_path)
    rendered = render_diagnostic_markdown_from_dir(input_dir).lower()
    for forbidden in _FORBIDDEN_PRODUCT_CLAIMS:
        assert forbidden.lower() not in rendered, (
            f"diagnostic report contains forbidden product claim "
            f"{forbidden!r} — Phase 4.9-A criterion #6 violated"
        )


def test_markdown_report_links_redacted_io_without_raw_prompt(
    tmp_path: Path,
) -> None:
    """The provider matrix MUST link to redacted_io files but the
    raw prompt sentinel MUST NEVER appear in the rendered output."""
    redacted_io = [
        {
            "case_id": "L001",
            "prompt_sha256": "0" * 64,
            "redacted_response_body": (
                '{"choices":[{"message":{"content":"ok"}}]}'
            ),
            "redacted_error": None,
            "failure_kind": "success",
            "model": "deepseek-v4-flash",
            "http_status": 200,
            "wall_clock_ms": 412,
            "response_id": "chatcmpl-1",
            "finish_reason": "stop",
            "usage_prompt_tokens": 200,
            "usage_completion_tokens": 50,
        },
        {
            "case_id": "L002",
            "prompt_sha256": "1" * 64,
            "redacted_response_body": (
                '{"id":"chatcmpl-bad","object":"chat.completion"}'
            ),
            "redacted_error": "response has no 'choices' array",
            "failure_kind": "invalid_shape",
            "model": "deepseek-v4-pro",
            "http_status": 200,
            "wall_clock_ms": 873,
        },
    ]
    input_dir = _seed_input_dir(tmp_path, redacted_io=redacted_io)
    # The raw prompt sentinel is NEVER passed to the renderer (only
    # the SHA256 lives in the captured payload). If it shows up in
    # the rendered output, something has slipped.
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    assert _PROMPT_SENTINEL not in rendered
    # Linked filenames present so the operator can navigate.
    assert "redacted_io/L001.json" in rendered
    assert "redacted_io/L002.json" in rendered
    # `failure_kind` makes the V4 Pro 6/8 invalid_shape gap visible.
    assert "invalid_shape" in rendered
    assert "success" in rendered


def test_markdown_report_provider_matrix_is_readable(
    tmp_path: Path,
) -> None:
    """The provider matrix MUST render as a Markdown table (column
    headers + separator row + data rows)."""
    redacted_io = [
        {
            "case_id": "L00X",
            "prompt_sha256": "a" * 64,
            "redacted_response_body": "{}",
            "failure_kind": "success",
            "model": "deepseek-v4-flash",
            "http_status": 200,
            "wall_clock_ms": 100,
        },
    ]
    input_dir = _seed_input_dir(tmp_path, redacted_io=redacted_io)
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    # Column headers.
    assert "| File | `failure_kind` | `http_status` | `model` | `wall_clock_ms` |" in rendered
    # Markdown table separator row.
    assert "|---|---|---|---|---|" in rendered
    # At least one data row referencing the captured file.
    assert "| `redacted_io/L00X.json` |" in rendered


# ---------------------------------------------------------------------------
# Backstops
# ---------------------------------------------------------------------------


def test_diagnostic_status_clean_run_is_contract_clean(tmp_path: Path) -> None:
    """All contract metrics at 1.0 → status=`contract_clean`."""
    metrics = _clean_metrics()
    assert derive_diagnostic_status(metrics) == "contract_clean"


def test_diagnostic_status_leak_is_blocked() -> None:
    """A positive leak count MUST flip status to `blocked` regardless
    of every other metric. ADR-22 has precedence."""
    metrics = _clean_metrics(official_field_leak_count=1)
    assert derive_diagnostic_status(metrics) == "blocked"


def test_diagnostic_status_low_citation_precision_is_contract_failed() -> None:
    """Citation precision below 1.0 → `contract_failed` (the LLM
    cited evidence the packet did not carry)."""
    metrics = _clean_metrics(evidence_ref_precision=0.5)
    assert derive_diagnostic_status(metrics) == "contract_failed"


def test_diagnostic_status_enum_excludes_forbidden_values() -> None:
    """The DiagnosticStatus Literal MUST NOT include any forbidden
    enum value (Phase 4.9-D criterion #12)."""
    import typing
    allowed = set(typing.get_args(DiagnosticStatus))
    for forbidden in _FORBIDDEN_DIAGNOSTIC_STATUSES:
        assert forbidden not in allowed, (
            f"DiagnosticStatus enum includes forbidden value "
            f"{forbidden!r} — Phase 4.9-D criterion #12 violated"
        )
    # Spot-check that the four allowed values are present.
    expected = {"blocked", "contract_failed", "contract_clean", "diagnostic_only"}
    assert allowed == expected


def test_diagnostic_report_missing_metrics_raises(tmp_path: Path) -> None:
    """A missing metrics.json is a hard error — the diagnostic
    report needs the metrics as the canonical source of truth."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        render_diagnostic_markdown_from_dir(empty_dir)


def test_write_diagnostic_markdown_persists_to_disk(tmp_path: Path) -> None:
    """`write_diagnostic_markdown` should land bytes on disk and
    return the resolved path."""
    input_dir = _seed_input_dir(tmp_path)
    out_path = tmp_path / "out" / "diagnostic.md"
    written = write_diagnostic_markdown(input_dir, out_path)
    assert written == out_path
    assert out_path.is_file()
    body = out_path.read_text(encoding="utf-8")
    assert "Diagnostic only — not a merge verdict." in body
    assert body.startswith("# OIDA-code Diagnostic Report")


def test_diagnostic_report_renders_stability_summary_when_present(
    tmp_path: Path,
) -> None:
    """When `stability_summary.json` is present, render it as a JSON
    code block under section 6."""
    stability = {
        "n_runs": 2,
        "official_field_leak_count_max": 0,
        "estimator_status_accuracy_mean": 0.625,
        "estimator_status_accuracy_std": 0.0,
    }
    input_dir = _seed_input_dir(tmp_path, stability=stability)
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    assert "## 6. Stability across repeat runs" in rendered
    assert "estimator_status_accuracy_mean" in rendered
    assert '"n_runs": 2' in rendered


def test_diagnostic_report_handles_missing_per_case(tmp_path: Path) -> None:
    """A missing per_case.json should not crash; the families row
    should fall back to a placeholder."""
    input_dir = _seed_input_dir(tmp_path)  # no per_case
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    assert "per-case breakdown not present" in rendered
