"""Phase 6.g Step Summary fallback diagnostic quarantine guards."""

from __future__ import annotations

import json
import re

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from tests.conftest import REPO_ROOT

_ACTION_YML = REPO_ROOT / "action.yml"
_REPORT_JSON = (
    REPO_ROOT
    / "reports"
    / "phase6_g_action_step_summary_diagnostic_fallback"
    / "report.json"
)

_FORBIDDEN_PUBLIC_PHRASES = (
    "AI code verifier",
    "actually guarantees",
    "guaranteed behavior",
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
)

_DIAGNOSTIC_HEADER = '## OIDA-code diagnostic evidence'
_DIAGNOSTIC_NON_CLAIM = (
    "Diagnostic only — not a merge decision or "
    "production-readiness assessment."
)
_LEGACY_TITLE = '## OIDA-code audit'
_LEGACY_COMMENT_PHRASE = "legacy audit report excerpt"


@pytest.fixture(scope="module")
def _action_payload() -> dict[str, object]:
    if yaml is None:
        pytest.skip("PyYAML required to parse action.yml")
    payload = yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _input(payload: dict[str, object], name: str) -> dict[str, object]:
    inputs = payload.get("inputs")
    assert isinstance(inputs, dict)
    item = inputs.get(name)
    assert isinstance(item, dict), f"missing input {name!r}"
    return item


def test_step_summary_fallback_uses_diagnostic_title() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    assert f'echo "{_LEGACY_TITLE}"' not in body
    assert f'echo "{_DIAGNOSTIC_HEADER}"' in body
    assert f'echo "{_DIAGNOSTIC_NON_CLAIM}"' in body


def test_step_summary_fallback_emits_non_claim_disclaimer() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    diagnostic_index = body.find(f'echo "{_DIAGNOSTIC_HEADER}"')
    non_claim_index = body.find(f'echo "{_DIAGNOSTIC_NON_CLAIM}"')
    head_index = body.find('head -n 80 "$OUTPUT_DIR/report.md"')

    assert diagnostic_index != -1
    assert non_claim_index != -1
    assert head_index != -1
    assert diagnostic_index < non_claim_index < head_index


def test_action_yml_has_no_legacy_audit_excerpt_phrase() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    assert _LEGACY_COMMENT_PHRASE not in body
    assert _LEGACY_TITLE not in body


def test_step_summary_fallback_preserves_calibration_block() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    assert 'echo "## Calibration metrics"' in body
    assert 'head -n 30 "$CAL_OUT/metrics.json"' in body


def test_action_yml_no_public_product_verdict_claims() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    for phrase in _FORBIDDEN_PUBLIC_PHRASES:
        assert phrase not in body, phrase

    for line in body.splitlines():
        if re.search(r"\bverified\b", line):
            assert (
                "product verdicts" in line
                or "verification labels are NOT emitted" in line
                or "unverified PR contributions" in line
            ), line


def test_action_safe_defaults_remain_pinned(
    _action_payload: dict[str, object],
) -> None:
    assert _input(_action_payload, "enable-tool-gateway")["default"] == "false"
    assert _input(_action_payload, "upload-sarif")["default"] == "false"
    assert _input(_action_payload, "fail-on")["default"] == "none"
    assert _input(_action_payload, "llm-provider")["default"] == "replay"
    assert (
        _input(_action_payload, "gateway-fail-on-contract")["default"]
        == "false"
    )


def test_action_runs_steps_and_commands_preserved(
    _action_payload: dict[str, object],
) -> None:
    runs = _action_payload.get("runs")
    assert isinstance(runs, dict)
    assert runs.get("using") == "composite"

    steps = runs.get("steps")
    assert isinstance(steps, list)
    step_names = {
        step.get("name")
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("name"), str)
    }
    assert "Set up Python" in step_names
    assert "Install oida-code" in step_names
    assert "Run audit" in step_names
    assert "Upload artifacts" in step_names
    assert "Upload SARIF (optional)" in step_names
    assert "Phase 5.6 — gateway-grounded verifier (opt-in)" in step_names
    assert "Phase 5.6 — upload gateway artifacts" in step_names

    body = _ACTION_YML.read_text(encoding="utf-8")
    for command_token in (
        "python -m oida_code.cli inspect",
        "python -m oida_code.cli audit",
        "python -m oida_code.cli render-artifacts",
        "python -m oida_code.cli build-artifact-manifest",
        "python -m oida_code.cli verify-grounded",
        "python -m oida_code.cli render-gateway-summary",
        "python -m oida_code.cli emit-gateway-status",
        "python -m oida_code.cli validate-gateway-bundle",
    ):
        assert command_token in body, command_token

    # calibration-eval is invoked via the CAL_ARGS bash array
    # (`python -m oida_code.cli "${CAL_ARGS[@]}"`), so it does not
    # appear as a literal `python -m oida_code.cli calibration-eval`
    # token. Verify the array form + the subcommand string instead.
    assert 'python -m oida_code.cli "${CAL_ARGS[@]}"' in body
    assert '"calibration-eval"' in body


def test_action_outputs_unchanged(_action_payload: dict[str, object]) -> None:
    outputs = _action_payload.get("outputs")
    assert isinstance(outputs, dict)
    for expected in (
        "report-json",
        "report-markdown",
        "report-sarif",
        "calibration-metrics",
        "diagnostic-markdown",
        "diagnostic-status",
        "official-field-leaks",
        "artifact-manifest",
        "gateway-report-json",
        "gateway-summary-md",
        "gateway-audit-log-dir",
        "gateway-status",
        "gateway-official-field-leak-count",
    ):
        assert expected in outputs, expected


def test_phase6g_report_records_scope_flags() -> None:
    report = json.loads(_REPORT_JSON.read_text(encoding="utf-8"))

    assert report["action_runtime_behavior_changed"] is False
    assert report["step_summary_fallback_text_changed"] is True
    assert report["inputs_defaults_changed"] is False
    assert report["provider_call_used"] is False
    assert report["direct_provider_call"] is False
    assert report["corpus_index_changed"] is False
    assert report["workflow_changed"] is False
    assert report["source_code_changed"] is False
    assert report["clone_helper_changed"] is False
    assert report["runtime_gateway_default_changed"] is False
    assert report["mcp_runtime_changed"] is False
    assert report["sarif_upload_behavior_changed"] is False
    assert report["forbidden_public_phrases_removed"] == list(
        _FORBIDDEN_PUBLIC_PHRASES
    )
