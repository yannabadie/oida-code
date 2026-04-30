"""Phase 6.f action.yml metadata diagnostic quarantine guards."""

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
    / "phase6_f_action_metadata_diagnostic_quarantine"
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


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


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


def test_action_public_description_is_diagnostic_only(
    _action_payload: dict[str, object],
) -> None:
    description = _action_payload.get("description")
    assert isinstance(description, str)
    compact = _compact(description)

    assert "Diagnostic evidence for AI-authored Python diffs" in compact
    assert "Not a merge or production-readiness decision" in compact
    assert "Reports stay diagnostic only" in compact
    for phrase in _FORBIDDEN_PUBLIC_PHRASES:
        assert phrase not in description


def test_action_yml_has_no_stale_public_product_claim_phrases() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")

    for phrase in _FORBIDDEN_PUBLIC_PHRASES:
        assert phrase not in body

    # ``verified`` may appear only as a quoted/internal token in a
    # negative product-verdict list, never as a public promise.
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


def test_gateway_input_description_remains_opt_in_not_mcp_or_provider(
    _action_payload: dict[str, object],
) -> None:
    description = _input(
        _action_payload, "enable-tool-gateway",
    ).get("description")
    assert isinstance(description, str)
    lowered = _compact(description.lower().replace("`", ""))

    assert 'default stays "false"' in lowered
    assert "gateway path is not the default audit path" in lowered
    assert "no mcp" in lowered
    assert "no provider tool-calling" in lowered
    assert "no write or network tools" in lowered


def test_action_runs_shape_and_core_outputs_still_exist(
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
    assert "Run audit" in step_names
    assert "Upload SARIF (optional)" in step_names
    assert "Phase 5.6 \u2014 gateway-grounded verifier (opt-in)" in step_names

    outputs = _action_payload.get("outputs")
    assert isinstance(outputs, dict)
    for expected in (
        "report-json",
        "report-markdown",
        "report-sarif",
        "diagnostic-status",
        "artifact-manifest",
        "gateway-status",
    ):
        assert expected in outputs


def test_phase6f_report_records_scope_flags() -> None:
    report = json.loads(_REPORT_JSON.read_text(encoding="utf-8"))

    assert report["action_metadata_changed"] is True
    assert report["action_runs_changed"] is False
    assert report["action_defaults_changed"] is False
    assert report["workflow_changed"] is False
    assert report["source_code_changed"] is False
    assert report["provider_call_used"] is False
    assert report["direct_provider_call"] is False
    assert report["runtime_gateway_default_changed"] is False
    assert report["mcp_runtime_changed"] is False
    assert report["corpus_index_changed"] is False
    assert report["forbidden_public_phrases_removed"] == list(
        _FORBIDDEN_PUBLIC_PHRASES
    )
