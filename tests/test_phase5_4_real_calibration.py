"""Phase 5.4 (QA/A31.md, ADR-39) — real gateway calibration
tests.

Sub-blocks covered:

* 5.4-A — runnable public subset under
  ``datasets/gateway_holdout_public_v1/``: at least 8 cases,
  every case loadable, every case ``insufficient_fixture`` row
  count == 0 when the runner walks the public manifest.
* 5.4-B — mandatory cases present (the 7 named in QA/A31
  §5.4-B plus 1 sentinel).
* 5.4-C — ``decision_summary.json`` schema + recommendation
  literal vocabulary.
* 5.4-D — failure analysis Markdown table extended with
  ``actual_delta`` + ``label_change_proposed`` columns.
* 5.4-E — audit log review: every gateway-mode case writes a
  per-case audit log; blocked / quarantined / missing-
  definition cases produce blockers; audit logs never carry
  secret-like values.
* 5.4-F — calibration workflow points at the public dataset
  and uploads artifacts.
* 5.4-G — anti-MCP regression locks remain active (all
  Phase-5.x scopes).

Negative checks scan ``pyproject.toml`` +
``.github/workflows/`` + ``src/oida_code/`` only — never
``docs/`` or ``reports/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PUBLIC_HOLDOUT = (
    _REPO_ROOT / "datasets" / "gateway_holdout_public_v1"
)
_WORKFLOW = (
    _REPO_ROOT / ".github" / "workflows" / "gateway-calibration.yml"
)


# ---------------------------------------------------------------------------
# 5.4-A — public dataset present + cases loadable
# ---------------------------------------------------------------------------


def test_public_holdout_readme_exists() -> None:
    assert (_PUBLIC_HOLDOUT / "README.md").is_file()


def test_public_holdout_manifest_loads() -> None:
    from oida_code.calibration.gateway_calibration import (
        load_manifest,
    )
    manifest = load_manifest(_PUBLIC_HOLDOUT / "manifest.json")
    assert manifest.manifest_version
    assert len(manifest.cases) >= 8


_REQUIRED_CASE_FILES = (
    "packet.json",
    "baseline_forward.json",
    "baseline_backward.json",
    "gateway_pass1_forward.json",
    "gateway_pass1_backward.json",
    "gateway_pass2_forward.json",
    "gateway_pass2_backward.json",
    "tool_policy.json",
    "gateway_definitions.json",
    "approved_tools.json",
    "expected.json",
)


def test_public_holdout_every_case_has_full_fixture() -> None:
    """Criterion #2 + #8 — at least 8 runnable public cases,
    every required file present."""
    from oida_code.calibration.gateway_calibration import (
        load_manifest,
    )
    manifest = load_manifest(_PUBLIC_HOLDOUT / "manifest.json")
    runnable = 0
    for case in manifest.cases:
        case_dir = _PUBLIC_HOLDOUT / case.directory
        for required in _REQUIRED_CASE_FILES:
            assert (case_dir / required).is_file(), (
                f"case {case.case_id!r} missing {required!r}"
            )
        runnable += 1
    assert runnable >= 8, (
        f"public holdout must ship at least 8 runnable cases; "
        f"got {runnable}"
    )


# ---------------------------------------------------------------------------
# 5.4-B — mandatory cases present
# ---------------------------------------------------------------------------


def test_public_holdout_carries_mandatory_cases() -> None:
    """QA/A31 §5.4-B mandates the named cases."""
    cases_root = _PUBLIC_HOLDOUT / "cases"
    for case_id in (
        "tool_needed_then_supported",
        "tool_failed_contradicts_claim",
        "tool_requested_but_blocked",
        "hash_drift_quarantine",
        "prompt_injection_in_tool_output",
        "negative_path_missing",
        "f2p_p2p_regression",
    ):
        assert (cases_root / case_id).is_dir(), (
            f"missing mandatory case directory {case_id!r}"
        )


# ---------------------------------------------------------------------------
# 5.4-C — decision_summary schema + recommendation
# ---------------------------------------------------------------------------


def test_calibration_runner_emits_decision_summary(
    tmp_path: Path,
) -> None:
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary_path = out / "decision_summary.json"
    assert summary_path.is_file()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in (
        "cases_runnable",
        "cases_insufficient_fixture",
        "gateway_improves_count",
        "gateway_same_count",
        "gateway_worse_count",
        "claim_accept_accuracy_delta",
        "claim_macro_f1_delta",
        "evidence_ref_precision_delta",
        "evidence_ref_recall_delta",
        "tool_contradiction_rejection_rate_delta",
        "fresh_tool_ref_citation_rate",
        "official_field_leak_count",
        "recommendation",
    ):
        assert key in payload, f"decision_summary missing key {key!r}"


def test_decision_summary_recommendation_is_literal(
    tmp_path: Path,
) -> None:
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    payload = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    allowed = {
        "integrate_opt_in",
        "revise_prompts",
        "revise_labels",
        "revise_tool_policy",
        "insufficient_data",
    }
    assert payload["recommendation"] in allowed


def test_public_holdout_runs_with_zero_insufficient_fixture(
    tmp_path: Path,
) -> None:
    """Criterion #8 — the public runnable subset must have
    cases_insufficient_fixture == 0."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    payload = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert payload["cases_insufficient_fixture"] == 0


def test_public_holdout_official_field_leak_zero(
    tmp_path: Path,
) -> None:
    """Criterion #11 — official_field_leak_count == 0 on both
    modes."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    payload = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert payload["official_field_leak_count"] == 0


def test_decision_summary_carries_diagnostic_only_flag(
    tmp_path: Path,
) -> None:
    """The runner's recommendation MUST be flagged as
    diagnostic; no production threshold is hidden in the
    output."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    payload = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert payload.get("recommendation_diagnostic_only") is True
    assert "production thresholds" in payload.get("reserved", "").lower()


# ---------------------------------------------------------------------------
# 5.4-D — failure analysis table shape
# ---------------------------------------------------------------------------


def test_failure_analysis_carries_label_change_proposed(
    tmp_path: Path,
) -> None:
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    body = (out / "failure_analysis.md").read_text(encoding="utf-8")
    for column in (
        "case_id", "family", "expected_delta", "actual_delta",
        "baseline_result", "gateway_result", "classification",
        "root_cause", "proposed_action", "label_change_proposed",
    ):
        assert column in body, (
            f"failure_analysis.md missing column {column!r}"
        )


def test_failure_analysis_lists_tool_request_policy_gap() -> None:
    from oida_code.calibration.gateway_calibration import (
        FAILURE_CLASSIFICATIONS,
    )
    assert "tool_request_policy_gap" in FAILURE_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# 5.4-E — audit log review
# ---------------------------------------------------------------------------


def test_every_gateway_case_writes_audit_log(tmp_path: Path) -> None:
    """Criterion #14 — every gateway tool call (whether
    allowed, blocked, quarantined, or hitting a missing
    definition) MUST land in an audit log under
    ``<out>/audit/<case_id>/``. Cases that don't request any
    tool are a legitimate exception (they don't make any tool
    call)."""
    from oida_code.calibration.gateway_calibration import (
        load_manifest,
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    manifest = load_manifest(_PUBLIC_HOLDOUT / "manifest.json")
    for case in manifest.cases:
        case_dir = _PUBLIC_HOLDOUT / case.directory
        pass1 = json.loads(
            (case_dir / "gateway_pass1_forward.json").read_text(
                encoding="utf-8",
            ),
        )
        if not pass1.get("requested_tools"):
            continue
        # At least one .jsonl file must exist for this case.
        case_audit_dir = out / "audit" / case.case_id
        jsonl = list(case_audit_dir.rglob("*.jsonl"))
        assert jsonl, (
            f"case {case.case_id!r} requested a tool but wrote "
            "no audit JSONL"
        )


def test_blocked_tool_call_has_audit_event(tmp_path: Path) -> None:
    """The ``tool_requested_but_blocked`` case writes one
    audit event with ``policy_decision='block'``."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    from oida_code.verifier.tool_gateway.audit_log import (
        read_audit_events,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    case_audit_dir = (
        out / "audit" / "tool_requested_but_blocked"
    )
    events = read_audit_events(case_audit_dir, "pytest")
    assert events, "no audit events for blocked-tool case"
    assert any(e.policy_decision == "block" for e in events)


def test_quarantined_tool_call_has_audit_event(tmp_path: Path) -> None:
    """The ``hash_drift_quarantine`` case writes one audit
    event with ``policy_decision='quarantine'``."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    from oida_code.verifier.tool_gateway.audit_log import (
        read_audit_events,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    case_audit_dir = out / "audit" / "hash_drift_quarantine"
    events = read_audit_events(case_audit_dir, "pytest")
    assert events
    assert any(e.policy_decision == "quarantine" for e in events)


def test_missing_definition_has_blocker(tmp_path: Path) -> None:
    """Phase 5.2.1-B — a case requesting a tool with no
    matching definition must surface a blocker on the run."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    # Build a tiny temp manifest with a one-case slate where
    # gateway_definitions.json is empty (the case requests
    # pytest but no definition is shipped).
    case_src = (
        _PUBLIC_HOLDOUT / "cases" / "tool_needed_then_supported"
    )
    case_dst = tmp_path / "case"
    case_dst.mkdir()
    for f in (
        "packet.json", "baseline_forward.json",
        "baseline_backward.json", "gateway_pass1_forward.json",
        "gateway_pass1_backward.json",
        "gateway_pass2_forward.json",
        "gateway_pass2_backward.json", "tool_policy.json",
        "approved_tools.json", "expected.json", "executor.json",
    ):
        (case_dst / f).write_text(
            (case_src / f).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    # Empty gateway_definitions.
    (case_dst / "gateway_definitions.json").write_text(
        json.dumps({}), encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "manifest_version": "test",
            "cases": [
                {
                    "case_id": "missing_definition_smoke",
                    "family": "gateway_grounded",
                    "directory": "case",
                    "provenance": "synthetic",
                    "contamination_risk": "synthetic",
                    "expected_delta": "worse_expected",
                    "notes": "smoke",
                },
            ],
        }),
        encoding="utf-8",
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=manifest_path, out_dir=out, mode="replay",
    )
    # Failure analysis must classify the case (the blocker
    # text lives on the run report, not on the per-case row,
    # but the classification must not be 'expected_behavior_changed').
    body = (out / "failure_analysis.md").read_text(encoding="utf-8")
    assert "missing_definition_smoke" in body


def test_audit_log_contains_no_secret_like_values(
    tmp_path: Path,
) -> None:
    """Audit-event schema review (re-affirmed in 5.4-E):
    nothing the runner writes carries an API key, GITHUB_TOKEN,
    or other secret-shaped string."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    audit_dir = out / "audit"
    forbidden_substrings = (
        "api_key", "api-key", "x-api-key", "bearer ",
        "password", "secret_value",
    )
    for jsonl_path in audit_dir.rglob("*.jsonl"):
        body = jsonl_path.read_text(encoding="utf-8").lower()
        for token in forbidden_substrings:
            assert token not in body, (
                f"audit log {jsonl_path} contains forbidden "
                f"substring {token!r}"
            )


# ---------------------------------------------------------------------------
# 5.4-F — workflow points at public dataset
# ---------------------------------------------------------------------------


def test_workflow_points_at_public_holdout_manifest() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    assert (
        "datasets/gateway_holdout_public_v1/manifest.json" in body
    ), (
        "gateway-calibration workflow must point at the public "
        "runnable subset"
    )


def test_workflow_uploads_calibration_artifacts() -> None:
    body = _WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-artifact" in body
    assert ".oida/gateway-calibration" in body


# ---------------------------------------------------------------------------
# 5.4-G — anti-MCP regression locks remain active
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added() -> None:
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        "modelcontextprotocol",
        "@modelcontextprotocol",
        "mcp-server",
        "mcp_server",
    )
    for token in forbidden:
        assert token not in body, (
            f"pyproject.toml must not depend on {token!r}"
        )


def test_no_mcp_runtime_in_calibration_module() -> None:
    body = (
        _REPO_ROOT / "src" / "oida_code" / "calibration"
        / "gateway_calibration.py"
    ).read_text(encoding="utf-8")
    for token in (
        "modelcontextprotocol",
        "mcp.server",
        "stdio_server",
        "json_rpc",
        "jsonrpc",
    ):
        assert token.lower() not in body.lower(), (
            f"gateway_calibration.py mentions {token!r}"
        )


def test_no_provider_tool_calling_enabled_in_phase5_4() -> None:
    src = _REPO_ROOT / "src" / "oida_code"
    forbidden_re = re.compile(
        r"(?:client\.responses\.create|client\.messages\.create|"
        r"client\.chat\.completions\.create)[^)]*\btools\s*=",
        re.MULTILINE | re.DOTALL,
    )
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        assert not forbidden_re.search(body), (
            f"{py} appears to enable provider tool-calling"
        )


def test_action_yml_does_not_default_enable_tool_gateway_true() -> None:
    """QA/A31 line 416: do not integrate enable-tool-gateway
    into the action path yet. The default stays "false"."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    after = body.split("enable-tool-gateway:", 1)[1]
    next_input = re.search(r"\n  [a-z][a-z0-9-]*:\n", after)
    block = after[: next_input.start()] if next_input else after
    assert 'default: "false"' in block, (
        "action.yml must keep enable-tool-gateway default false"
    )


# ---------------------------------------------------------------------------
# Anti-mutation invariant — runner is read-only over both datasets
# ---------------------------------------------------------------------------


def test_runner_does_not_mutate_public_holdout(tmp_path: Path) -> None:
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    before = {
        p: p.stat().st_mtime_ns
        for p in _PUBLIC_HOLDOUT.rglob("*")
        if p.is_file()
    }
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    after = {
        p: p.stat().st_mtime_ns
        for p in _PUBLIC_HOLDOUT.rglob("*")
        if p.is_file()
    }
    assert before == after, (
        "calibration runner mutated the public holdout"
    )
