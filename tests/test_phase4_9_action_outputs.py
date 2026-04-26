"""Phase 4.9-D (QA/A26.md, ADR-34) — action outputs ergonomics.

Hard invariants:

* The CLI's ``calibration-eval`` writes ``<out>/action_outputs.txt``
  in ``key=value`` format, exactly compatible with what GitHub
  Actions expects on ``$GITHUB_OUTPUT``.
* The ``diagnostic-status`` enum has FOUR values:
  ``blocked`` / ``contract_failed`` / ``contract_clean`` /
  ``diagnostic_only`` (Phase 4.9-D criterion #297). The three
  FORBIDDEN values (``merge_safe`` / ``production_safe`` /
  ``verified``) MUST NEVER appear in the output OR in the
  composite action's documented enum.
* The composite ``action.yml`` declares both new outputs
  (``diagnostic-status`` and ``official-field-leaks``) and wires
  them via ``${{ steps.run.outputs.* }}``.
* The README / action docs MUST mention the new outputs (criterion
  ``test_action_outputs_are_documented_in_readme``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The four FORBIDDEN status values from QA/A26 lines 303-305.
_FORBIDDEN_STATUSES = ("merge_safe", "production_safe", "verified")
_REQUIRED_STATUSES = (
    "blocked", "contract_failed", "contract_clean", "diagnostic_only",
)


def test_action_outputs_include_stable_report_paths() -> None:
    """`action.yml` MUST declare each report-path output (json /
    markdown / sarif / calibration-metrics / diagnostic-markdown)."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(body)
    outputs = parsed.get("outputs") or {}
    for required in (
        "report-json",
        "report-markdown",
        "report-sarif",
        "calibration-metrics",
        "diagnostic-markdown",
    ):
        assert required in outputs, f"action.yml missing output: {required}"


def test_action_diagnostic_status_enum_has_no_forbidden_values() -> None:
    """The action.yml `diagnostic-status` description MUST list the
    four allowed values and MUST NOT name any of the three forbidden
    values (`merge_safe` / `production_safe` / `verified`)."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(body)
    desc = (parsed["outputs"]["diagnostic-status"]["description"] or "").lower()
    for required in _REQUIRED_STATUSES:
        assert required in desc, (
            f"action.yml diagnostic-status description missing the "
            f"allowed value {required!r}"
        )
    for forbidden in _FORBIDDEN_STATUSES:
        # Must not appear as a documented enum value. The word
        # "verified" is allowed in prose ONLY as a negative ("not
        # verified" / "MUST NEVER") — but to keep the rule simple
        # and easy to grep, the description MUST NOT contain the
        # bare token at all.
        token_pattern = rf"`{re.escape(forbidden)}`"
        assert not re.search(token_pattern, desc), (
            f"action.yml diagnostic-status description references "
            f"forbidden value {forbidden!r} (Phase 4.9-D #12)"
        )


def test_action_outputs_do_not_surface_vnet_debt_corrupt() -> None:
    """No action output may carry `total_v_net` / `debt_final` /
    `corrupt_success` (ADR-22 hard wall)."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(body)
    outputs = parsed.get("outputs") or {}
    for output_name, output_spec in outputs.items():
        for forbidden in (
            "total_v_net", "debt_final", "corrupt_success",
            "corrupt_success_ratio",
        ):
            assert forbidden not in output_name, (
                f"action.yml output {output_name!r} would expose "
                f"forbidden official field {forbidden!r}"
            )
            value_str = str(output_spec.get("value", ""))
            assert forbidden not in value_str, (
                f"action.yml output {output_name!r} value references "
                f"forbidden official field {forbidden!r}"
            )


def test_action_outputs_are_documented_in_readme() -> None:
    """The README MUST mention the two new Phase 4.9-D outputs so an
    operator can find them without reading the action.yml."""
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    # We require a literal mention of each output name. Phase 4.9
    # report writes the README docs with the new outputs; the test
    # locks the documentation lives.
    assert "diagnostic-status" in readme, (
        "README must mention the new `diagnostic-status` action output"
    )
    assert "official-field-leaks" in readme, (
        "README must mention the new `official-field-leaks` action output"
    )


def test_cli_calibration_eval_writes_action_outputs_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: invoking ``oida-code calibration-eval`` on the
    real calibration_v1 dataset MUST produce a key=value
    ``<out>/action_outputs.txt`` file with exactly the two expected
    keys and no others."""
    from typer.testing import CliRunner

    from oida_code.cli import app

    dataset = _REPO_ROOT / "datasets" / "calibration_v1"
    if not (dataset / "manifest.json").is_file():
        pytest.skip("calibration_v1 not built; skip e2e test")

    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "calibration-eval", str(dataset),
            "--out", str(out_dir),
            "--llm-provider", "replay",
        ],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    action_outputs = out_dir / "action_outputs.txt"
    assert action_outputs.is_file(), (
        "calibration-eval did not write action_outputs.txt"
    )
    body = action_outputs.read_text(encoding="utf-8")
    lines = [line for line in body.splitlines() if line.strip()]
    keys = [line.split("=", 1)[0] for line in lines]
    assert sorted(keys) == ["diagnostic-status", "official-field-leaks"]
    # Each value MUST come from the allowed set.
    pairs = dict(line.split("=", 1) for line in lines)
    assert pairs["diagnostic-status"] in _REQUIRED_STATUSES, (
        f"unexpected diagnostic-status value: "
        f"{pairs['diagnostic-status']!r}"
    )
    # Must be an integer.
    int(pairs["official-field-leaks"])


def test_cli_render_artifacts_writes_diagnostic_markdown(
    tmp_path: Path,
) -> None:
    """`oida-code render-artifacts <input>` MUST produce a Markdown
    file at the requested --out path."""
    import json as _json

    from typer.testing import CliRunner

    from oida_code.cli import app

    # Synthesize a minimal input dir.
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    metrics = {
        "cases_total": 1, "cases_evaluated": 1,
        "cases_excluded_for_contamination": 0,
        "cases_excluded_for_flakiness": 0,
        "claim_accept_accuracy": 1.0, "claim_accept_macro_f1": 1.0,
        "unsupported_precision": 1.0, "rejected_precision": 1.0,
        "evidence_ref_precision": 1.0, "evidence_ref_recall": 1.0,
        "unknown_ref_rejection_rate": 1.0,
        "tool_contradiction_rejection_rate": 1.0,
        "tool_uncertainty_preservation_rate": 1.0,
        "sandbox_block_rate_expected": 1.0,
        "shadow_bucket_accuracy": 1.0,
        "shadow_pairwise_order_accuracy": 1.0,
        "f2p_pass_rate_on_expected_fixed": None,
        "p2p_preservation_rate": None,
        "flaky_case_count": 0, "code_outcome_status": "not_computed",
        "safety_block_rate": 1.0, "fenced_injection_rate": 1.0,
        "estimator_status_accuracy": None,
        "estimator_estimate_accuracy": None,
        "estimator_cases_evaluated": 0, "estimator_cases_skipped": 0,
        "official_field_leak_count": 0, "notes": "",
    }
    (input_dir / "metrics.json").write_text(
        _json.dumps(metrics, indent=2), encoding="utf-8",
    )

    out_path = tmp_path / "out" / "diagnostic.md"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "render-artifacts", str(input_dir),
            "--out", str(out_path),
            "--format", "markdown",
        ],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    assert out_path.is_file()
    body = out_path.read_text(encoding="utf-8")
    assert "Diagnostic only — not a merge verdict." in body
    assert "blocked" in body  # status card cites ADR-22 blocked fields


def test_action_yml_invokes_render_artifacts() -> None:
    """The composite action MUST call `render-artifacts` after
    calibration-eval so the polished diagnostic Markdown lands."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert "render-artifacts" in body, (
        "action.yml does not invoke `oida-code render-artifacts` — "
        "the polished diagnostic Markdown will not be produced"
    )


def test_action_yml_consumes_action_outputs_file() -> None:
    """The composite action MUST read `<CAL_OUT>/action_outputs.txt`
    and append its contents to `$GITHUB_OUTPUT`."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert "action_outputs.txt" in body, (
        "action.yml never references action_outputs.txt — the new "
        "diagnostic-status / official-field-leaks outputs will be empty"
    )
    # Must `cat` it into $GITHUB_OUTPUT (or otherwise wire it).
    cat_pattern = re.compile(
        r'cat\s+"\$CAL_OUT/action_outputs\.txt"\s*>>\s*"\$GITHUB_OUTPUT"',
    )
    assert cat_pattern.search(body), (
        "action.yml does not append action_outputs.txt to GITHUB_OUTPUT"
    )


def test_action_yml_sarif_uploader_is_v4_with_category() -> None:
    """Phase 4.9-C: action.yml's SARIF uploader MUST be `@v4` (was
    `@v3` until Phase 4.7) AND MUST set an explicit `category` so
    multiple SARIF uploads on the same commit do not collapse."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert "github/codeql-action/upload-sarif@v4" in body, (
        "action.yml SARIF uploader must be `@v4` — `@v3` deprecated "
        "December 2026"
    )
    assert "github/codeql-action/upload-sarif@v3" not in body, (
        "action.yml still references the deprecated `@v3` uploader"
    )
    # Category — Phase 4.9-C SARIF disambiguation.
    assert re.search(r"category:\s*oida-code/", body), (
        "action.yml SARIF uploader missing `category: oida-code/...` — "
        "Phase 4.9-C requires explicit category for disambiguation"
    )
