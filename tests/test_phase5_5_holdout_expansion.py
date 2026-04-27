"""Phase 5.5 (QA/A32.md, ADR-40) — runnable holdout expansion
tests.

Sub-blocks covered:

* 5.5.0-A — Phase 5.4 audit-log wording canaries (live in
  ``tests/test_phase5_4_real_calibration.py`` so they sit
  alongside the Phase 5.4 report assertions).
* 5.5.0-B — true macro-F1 with per-class confusion matrix.
* 5.5.0-C — recommendation rename + ``promotion_allowed`` pin.
* 5.5-A — public runnable slate >= 12 cases including the
  four mandatory Phase 5.5 additions.
* 5.5-B — baseline vs gateway runs on the expanded slate.
* 5.5-C — recommendation rule order matches QA/A32 §5.5-C.
* 5.5-D — failure analysis carries the three proposal columns.
* 5.5-F — anti-MCP regression locks remain active (no new
  imports, no new workflows).

Negative checks scan ``pyproject.toml`` +
``.github/workflows/`` + ``src/oida_code/`` only — never
``docs/`` or ``reports/``.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PUBLIC_HOLDOUT = (
    _REPO_ROOT / "datasets" / "gateway_holdout_public_v1"
)
_WORKFLOW = (
    _REPO_ROOT / ".github" / "workflows" / "gateway-calibration.yml"
)


# ---------------------------------------------------------------------------
# 5.5.0-B — true macro-F1 with per-class confusion
# ---------------------------------------------------------------------------


def test_per_class_confusion_dataclass_exposes_tp_fp_fn() -> None:
    """The runner now keeps explicit ``tp`` / ``fp`` / ``fn``
    counters per class instead of a single ``correct`` /
    ``wrong`` pair."""
    from oida_code.calibration.gateway_calibration import (
        _PerClassConfusion,
    )
    c = _PerClassConfusion(tp=4, fp=1, fn=2)
    assert c.tp == 4
    assert c.fp == 1
    assert c.fn == 2
    # Phase 5.4 backward-compat aliases.
    assert c.correct == 4
    assert c.wrong == 3


def test_true_macro_f1_computes_per_class_precision_recall() -> None:
    """For a single class with TP=4, FP=1, FN=2: precision=0.8,
    recall=0.667, f1=0.727 (rounded)."""
    from oida_code.calibration.gateway_calibration import (
        _PerClassConfusion,
    )
    c = _PerClassConfusion(tp=4, fp=1, fn=2)
    assert round(c.precision(), 4) == 0.8
    assert round(c.recall(), 4) == 0.6667
    assert round(c.f1(), 4) == 0.7273


def test_true_macro_f1_handles_empty_class_without_div_zero() -> None:
    """An empty per-class counter (no expected and no actual
    members of that class) must return 0.0 from each of
    precision / recall / f1 — never raise."""
    from oida_code.calibration.gateway_calibration import (
        _PerClassConfusion,
    )
    c = _PerClassConfusion(tp=0, fp=0, fn=0)
    assert c.precision() == 0.0
    assert c.recall() == 0.0
    assert c.f1() == 0.0


def test_macro_f1_is_mean_of_three_per_class_f1(tmp_path: Path) -> None:
    """The runner's :meth:`_PerModeMetrics.claim_macro_f1` must
    be the mean of three per-class F1 values, not the symmetric
    proxy. On the 8-case Phase 5.4 slate every per-class
    confusion has zero FP/FN so each class with TP > 0 scores
    F1 = 1.0; classes with TP = 0 score F1 = 0.0. For the
    gateway mode all three classes have TP > 0 so macro-F1 must
    be exactly 1.0."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    gateway = json.loads(
        (out / "gateway_metrics.json").read_text(encoding="utf-8"),
    )
    expected_macro = (
        gateway["accepted_f1"]
        + gateway["unsupported_f1"]
        + gateway["rejected_f1"]
    ) / 3
    assert round(gateway["claim_macro_f1"], 4) == round(
        expected_macro, 4,
    )


def test_metrics_json_carries_per_class_precision_recall(
    tmp_path: Path,
) -> None:
    """Both baseline and gateway metric JSONs must expose
    precision and recall and F1 for each of the three classes."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    for name in ("baseline_metrics.json", "gateway_metrics.json"):
        payload = json.loads(
            (out / name).read_text(encoding="utf-8"),
        )
        for cls in ("accepted", "unsupported", "rejected"):
            for stat in ("tp", "fp", "fn",
                         "precision", "recall", "f1"):
                key = f"{cls}_{stat}"
                assert key in payload, (
                    f"{name} missing {key!r}"
                )


def test_macro_f1_delta_uses_true_macro_f1_not_proxy(
    tmp_path: Path,
) -> None:
    """The decision summary's ``claim_macro_f1_delta`` must be
    derived from the per-class F1 mean, NOT the legacy proxy.
    On the Phase 5.4 8-case slate the gateway side has perfect
    F1=1.0 in all three classes (8 TP across the slate, zero
    FP, zero FN); the baseline side has F1=1.0 only on
    ``accepted`` (8 TP) and 0.0 on the empty ``unsupported`` /
    ``rejected`` classes. Macro-F1: gateway=1.0,
    baseline=1/3≈0.3333. Delta ≈ 0.6667 — same value the proxy
    produced on the original slate."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    # Sanity: the delta is computed (not None) and is a number.
    assert isinstance(summary["claim_macro_f1_delta"], int | float)
    # Cross-check against the explicit per-class F1 in the per-
    # mode metrics — confirms the delta is wired through the
    # new structure.
    baseline = json.loads(
        (out / "baseline_metrics.json").read_text(encoding="utf-8"),
    )
    gateway = json.loads(
        (out / "gateway_metrics.json").read_text(encoding="utf-8"),
    )
    expected_delta = round(
        gateway["claim_macro_f1"] - baseline["claim_macro_f1"], 4,
    )
    assert summary["claim_macro_f1_delta"] == expected_delta


def test_legacy_proxy_not_used_in_decision_summary(
    tmp_path: Path,
) -> None:
    """The decision summary must NOT carry a key named
    ``legacy_claim_macro_f1_proxy`` or otherwise advertise a
    pre-Phase-5.5 metric in the canonical output."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert "legacy_claim_macro_f1_proxy" not in summary
    assert "proxy" not in summary.get("recommendation", "")


# ---------------------------------------------------------------------------
# 5.5.0-C — recommendation rename + promotion_allowed pin
# ---------------------------------------------------------------------------


def test_recommendation_literal_uses_integrate_opt_in_candidate() -> None:
    """The recommendation Literal must use
    ``integrate_opt_in_candidate``, not the Phase 5.4
    ``integrate_opt_in`` (the suffix `_candidate` is the explicit
    "Phase 5.5 picks the next phase, integration is a separate
    deliberate act" marker)."""
    from oida_code.calibration.gateway_calibration import (
        _RECOMMENDATION_LITERAL,
    )
    assert "integrate_opt_in_candidate" in _RECOMMENDATION_LITERAL
    assert "integrate_opt_in" not in _RECOMMENDATION_LITERAL


def test_decision_summary_carries_promotion_allowed_false(
    tmp_path: Path,
) -> None:
    """``promotion_allowed`` is a STRUCTURAL pin: hardcoded
    False in :func:`_emit_decision_summary` regardless of
    recommendation. Phase 5.5 may PROPOSE
    ``integrate_opt_in_candidate`` but does not enable any
    action path."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert "promotion_allowed" in summary
    assert summary["promotion_allowed"] is False


def test_decision_summary_recommendation_remains_diagnostic_only(
    tmp_path: Path,
) -> None:
    """``recommendation_diagnostic_only`` must remain True even
    when the recommendation lands on a non-``insufficient_data``
    value."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert summary["recommendation_diagnostic_only"] is True


# ---------------------------------------------------------------------------
# 5.5-A — runnable slate >= 12 cases including the four mandatory
# Phase 5.5 additions
# ---------------------------------------------------------------------------


_PHASE5_5_MANDATORY_CASES = (
    "tool_missing_uncertainty",
    "tool_timeout_uncertainty",
    "multi_tool_static_then_test",
    "duplicate_tool_request_budget",
)


def test_public_holdout_has_phase5_5_mandatory_cases() -> None:
    """QA/A32 §5.5-A — four new cases must be present alongside
    the original eight from Phase 5.4."""
    cases_root = _PUBLIC_HOLDOUT / "cases"
    for case_id in _PHASE5_5_MANDATORY_CASES:
        assert (cases_root / case_id).is_dir(), (
            f"Phase 5.5 mandatory case missing: {case_id!r}"
        )


def test_public_holdout_runnable_count_at_least_twelve(
    tmp_path: Path,
) -> None:
    """QA/A32 criterion #4 — public runnable holdout has at
    least 12 complete cases."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    summary = json.loads(
        (out / "decision_summary.json").read_text(encoding="utf-8"),
    )
    assert summary["cases_runnable"] >= 12, (
        f"Phase 5.5 needs >= 12 runnable cases; "
        f"got {summary['cases_runnable']}"
    )
    assert summary["cases_insufficient_fixture"] == 0


def test_public_holdout_manifest_lists_phase5_5_cases() -> None:
    """The manifest must enumerate the four Phase 5.5 mandatory
    cases alongside the Phase 5.4 set."""
    from oida_code.calibration.gateway_calibration import (
        load_manifest,
    )
    manifest = load_manifest(_PUBLIC_HOLDOUT / "manifest.json")
    case_ids = {c.case_id for c in manifest.cases}
    for case_id in _PHASE5_5_MANDATORY_CASES:
        assert case_id in case_ids, (
            f"manifest does not list {case_id!r}"
        )


def test_duplicate_tool_request_budget_cap_fires(tmp_path: Path) -> None:
    """The duplicate case requests pytest 3 times with
    ``max_tool_calls=2``; the audit log MUST contain at most 2
    events (the budget cap fires)."""
    from oida_code.calibration.gateway_calibration import (
        run_calibration,
    )
    out = tmp_path / "calibration"
    run_calibration(
        manifest_path=_PUBLIC_HOLDOUT / "manifest.json",
        out_dir=out,
        mode="replay",
    )
    case_audit = (
        out / "audit" / "duplicate_tool_request_budget"
    )
    jsonl_files = list(case_audit.rglob("*.jsonl"))
    assert jsonl_files, "duplicate-budget case wrote no audit log"
    total_events = sum(
        len(p.read_text(encoding="utf-8").splitlines())
        for p in jsonl_files
    )
    assert total_events <= 2, (
        f"max_tool_calls=2 cap not honoured; got {total_events} "
        "audit events"
    )


def test_tool_missing_uncertainty_demotes_claim(tmp_path: Path) -> None:
    """The ``tool_missing_uncertainty`` case must surface the
    Phase 5.2.1-B "no citable evidence" blocker AND demote the
    pass-2 claim to unsupported (NOT rejected)."""
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
    # Find the row for tool_missing_uncertainty.
    rows = [
        line for line in body.splitlines()
        if "tool_missing_uncertainty" in line
        and "expected_delta" not in line
    ]
    assert rows, "missing tool_missing_uncertainty row"
    row = rows[0]
    # Gateway side must show ``status=diagnostic_only`` AND
    # ``unsupported=1`` AND ``accepted=0``. Phase 5.8.1-B restored
    # the strict status anchor: the diagnostic/actionable split
    # ensures a tool_missing diagnostic stays non-promoting, so the
    # gateway-side status remains ``diagnostic_only`` (was briefly
    # weakened to ``unsupported=1`` only between Phase 5.8.1 and
    # 5.8.1-B while the safety regression was active).
    assert "unsupported=1" in row
    assert "accepted=0" in row.split("status=diagnostic_only", 1)[1]


def test_tool_timeout_uncertainty_demotes_claim(tmp_path: Path) -> None:
    """The ``tool_timeout_uncertainty`` case must surface the
    Phase 5.2.1-B "no citable evidence" blocker AND demote the
    pass-2 claim to unsupported (NOT rejected)."""
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
    rows = [
        line for line in body.splitlines()
        if "tool_timeout_uncertainty" in line
        and "expected_delta" not in line
    ]
    assert rows
    row = rows[0]
    # See test_tool_missing_uncertainty_demotes_claim — same anchor
    # restored by Phase 5.8.1-B (status=diagnostic_only on the
    # gateway side, AND accepted=0 + unsupported=1 demotion).
    assert "unsupported=1" in row
    assert "accepted=0" in row.split("status=diagnostic_only", 1)[1]


def test_multi_tool_static_then_test_rejects_fix(tmp_path: Path) -> None:
    """The multi-tool case requests ruff + mypy + pytest.
    Static checkers come back ok; pytest fails. The aggregator
    MUST reject the ``C.fix`` claim because the pytest negative
    estimate dominates."""
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
    rows = [
        line for line in body.splitlines()
        if "multi_tool_static_then_test" in line
        and "expected_delta" not in line
    ]
    assert rows
    row = rows[0]
    # Gateway side rejects the claim.
    assert "rejected=1" in row.split("| status=", 2)[2]


# ---------------------------------------------------------------------------
# 5.5-C — recommendation rule order
# ---------------------------------------------------------------------------


def test_decide_recommendation_leak_first() -> None:
    """Rule 1 — any official-field leak forces
    ``revise_tool_policy`` regardless of slate size or deltas."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=20,
        cases_insufficient_fixture=0,
        official_leak_count=1,
        gateway_delta_macro_f1=0.5,
        gateway_delta_tool_contradiction=0.4,
        gateway_delta_evidence_precision=0.3,
        has_critical_gateway_bug=False,
    ) == "revise_tool_policy"


def test_decide_recommendation_runnable_threshold() -> None:
    """Rule 2 — fewer than 12 runnable cases forces
    ``insufficient_data``."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=11,
        cases_insufficient_fixture=0,
        official_leak_count=0,
        gateway_delta_macro_f1=0.5,
        gateway_delta_tool_contradiction=0.4,
        gateway_delta_evidence_precision=0.3,
        has_critical_gateway_bug=False,
    ) == "insufficient_data"


def test_decide_recommendation_integrate_opt_in_candidate() -> None:
    """Rule 3 — at >= 12 runnable cases with positive macro-F1,
    non-negative tool-contradiction, non-negative evidence-ref
    precision, and no critical gateway bug, the recommendation
    is ``integrate_opt_in_candidate``."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=12,
        cases_insufficient_fixture=0,
        official_leak_count=0,
        gateway_delta_macro_f1=0.6,
        gateway_delta_tool_contradiction=0.4,
        gateway_delta_evidence_precision=0.3,
        has_critical_gateway_bug=False,
    ) == "integrate_opt_in_candidate"


def test_decide_recommendation_critical_gateway_bug_blocks_promotion() -> None:
    """A critical gateway_bug case prevents promotion even
    when the deltas are all positive."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=20,
        cases_insufficient_fixture=0,
        official_leak_count=0,
        gateway_delta_macro_f1=0.6,
        gateway_delta_tool_contradiction=0.4,
        gateway_delta_evidence_precision=0.3,
        has_critical_gateway_bug=True,
    ) != "integrate_opt_in_candidate"


def test_decide_recommendation_negative_macro_f1_revise_labels() -> None:
    """Rule 4 — strongly negative macro-F1 maps to
    ``revise_labels``."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=12,
        cases_insufficient_fixture=0,
        official_leak_count=0,
        gateway_delta_macro_f1=-0.2,
        gateway_delta_tool_contradiction=0.0,
        gateway_delta_evidence_precision=0.0,
        has_critical_gateway_bug=False,
    ) == "revise_labels"


def test_decide_recommendation_neutral_revise_prompts() -> None:
    """Rule 5 — small / neutral deltas with all guards
    satisfied default to ``revise_prompts``."""
    from oida_code.calibration.gateway_calibration import (
        _decide_recommendation,
    )
    assert _decide_recommendation(
        cases_runnable=12,
        cases_insufficient_fixture=0,
        official_leak_count=0,
        gateway_delta_macro_f1=0.01,
        gateway_delta_tool_contradiction=0.0,
        gateway_delta_evidence_precision=0.0,
        has_critical_gateway_bug=False,
    ) == "revise_prompts"


# ---------------------------------------------------------------------------
# 5.5-D — failure analysis carries the three proposal columns
# ---------------------------------------------------------------------------


def test_failure_analysis_has_three_proposal_columns(
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
        "label_change_proposed",
        "tool_request_policy_change_proposed",
        "prompt_change_proposed",
    ):
        assert column in body, (
            f"failure_analysis.md missing column {column!r}"
        )


def test_failure_classifications_include_phase5_5_additions() -> None:
    """``tool_budget_gap`` and ``uncertainty_preserved`` are
    legitimate Phase 5.5 additions because the new mandatory
    slate exercises both code paths."""
    from oida_code.calibration.gateway_calibration import (
        FAILURE_CLASSIFICATIONS,
    )
    assert "tool_budget_gap" in FAILURE_CLASSIFICATIONS
    assert "uncertainty_preserved" in FAILURE_CLASSIFICATIONS


def test_failure_analysis_legend_documents_phase5_5_additions(
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
    assert "tool_budget_gap" in body
    assert "uncertainty_preserved" in body


def test_uncertainty_preserved_actually_emitted_for_tool_missing(
    tmp_path: Path,
) -> None:
    """The classifier must emit ``uncertainty_preserved`` (not
    just ``expected_behavior_changed``) on the
    ``tool_missing_uncertainty`` case because the gateway
    actually exercised the tool_missing code path."""
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
    rows = [
        line for line in body.splitlines()
        if "tool_missing_uncertainty" in line
        and "expected_delta" not in line
    ]
    assert rows
    # The classification cell must contain `uncertainty_preserved`.
    assert "`uncertainty_preserved`" in rows[0]


def test_uncertainty_preserved_actually_emitted_for_timeout(
    tmp_path: Path,
) -> None:
    """Same for the ``tool_timeout_uncertainty`` case (timeout
    is the second tool status that maps to
    ``uncertainty_preserved``)."""
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
    rows = [
        line for line in body.splitlines()
        if "tool_timeout_uncertainty" in line
        and "expected_delta" not in line
    ]
    assert rows
    assert "`uncertainty_preserved`" in rows[0]


def test_tool_budget_gap_actually_emitted_for_duplicate_case(
    tmp_path: Path,
) -> None:
    """The ``duplicate_tool_request_budget`` case requests
    pytest 3 times with ``max_tool_calls=2``; the classifier
    must emit ``tool_budget_gap`` (not ``expected_behavior_changed``)
    because the gateway loop's budget cap fired."""
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
    rows = [
        line for line in body.splitlines()
        if "duplicate_tool_request_budget" in line
        and "expected_delta" not in line
    ]
    assert rows
    assert "`tool_budget_gap`" in rows[0]


# ---------------------------------------------------------------------------
# 5.5-F — anti-MCP regression locks remain active
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added_phase5_5() -> None:
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for token in (
        "modelcontextprotocol",
        "@modelcontextprotocol",
        "mcp-server",
        "mcp_server",
    ):
        assert token not in body


def test_no_mcp_workflow_added_phase5_5() -> None:
    workflows = _REPO_ROOT / ".github" / "workflows"
    for wf in workflows.glob("*.yml"):
        body = wf.read_text(encoding="utf-8").lower()
        assert "modelcontextprotocol" not in body
        assert "mcp.server" not in body


def test_no_jsonrpc_tools_list_or_tools_call_runtime_phase5_5() -> None:
    src = _REPO_ROOT / "src" / "oida_code"
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        # JSON-RPC verbs must not surface in the runtime; the
        # gateway dispatch is direct calls to the deterministic
        # adapters.
        assert '"tools/list"' not in body
        assert '"tools/call"' not in body


def test_no_provider_tool_calling_enabled_phase5_5() -> None:
    """Phase 5.5 (criterion #29) — no SDK call must enable
    ``tools=[...]`` at provider level."""
    import re
    src = _REPO_ROOT / "src" / "oida_code"
    forbidden_re = re.compile(
        r"(?:client\.responses\.create|client\.messages\.create|"
        r"client\.chat\.completions\.create)[^)]*\btools\s*=",
        re.MULTILINE | re.DOTALL,
    )
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        assert not forbidden_re.search(body)


def test_action_yml_does_not_default_enable_tool_gateway_true_phase5_5() -> (
    None
):
    """Criterion — Phase 5.5 must NOT promote
    ``enable-tool-gateway`` to default ``"true"`` in
    ``action.yml``. Promotion is explicitly deferred to a later
    phase under separate review."""
    import re
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    after = body.split("enable-tool-gateway:", 1)[1]
    next_input = re.search(r"\n  [a-z][a-z0-9-]*:\n", after)
    block = after[: next_input.start()] if next_input else after
    assert 'default: "false"' in block, (
        "action.yml must keep enable-tool-gateway default false"
    )


def test_calibration_module_does_not_import_mcp_runtime() -> None:
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
        assert token.lower() not in body.lower()


# ---------------------------------------------------------------------------
# Anti-mutation invariant — runner is read-only over expanded slate
# ---------------------------------------------------------------------------


def test_runner_does_not_mutate_phase5_5_holdout(tmp_path: Path) -> None:
    """The runner must remain read-only over the expanded
    public holdout (criterion held over from Phase 5.4)."""
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
    assert before == after
