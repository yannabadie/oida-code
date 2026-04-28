"""Phase 5.7 (QA/A34.md, ADR-42) — operator soak protocol tests.

Sub-blocks covered:

* 5.7-A — controlled case selection (operator_soak_cases dir +
  case_001 scaffolded).
* 5.7-B — operator fiche / label / ux_score schemas.
* 5.7-D — artefact contract (no forbidden filenames in repo
  scaffolding).
* 5.7-E — aggregator counts + recommendation Literal.
* 5.7-F — decision rule precedence.
* 5.7-G — UX qualitative score schema.
* 5.7-I — anti-MCP / anti-provider locks extended.

These tests are hermetic: they build temporary case directories
under ``tmp_path`` rather than touching the committed
``operator_soak_cases/`` (which carries the awaiting-run scaffold).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from oida_code.operator_soak import (
    EXPECTED_RISK_VALUES,
    OPERATOR_LABEL_VALUES,
    RECOMMENDATION_VALUES,
    SOAK_STATUS_VALUES,
    AggregateReport,
    OperatorLabelEntry,
    OperatorSoakFiche,
    OperatorUxScore,
)
from oida_code.operator_soak.aggregate import (
    aggregate_cases,
    compute_recommendation,
    render_aggregate_markdown,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CASES_DIR = _REPO_ROOT / "operator_soak_cases"
_PACKAGE_DIR = _REPO_ROOT / "src" / "oida_code" / "operator_soak"
_DECISION_LOG = _REPO_ROOT / "memory-bank" / "decisionLog.md"
_PHASE_REPORT = _REPO_ROOT / "reports" / "phase5_7_operator_soak.md"
_EVAL_SCRIPT = _REPO_ROOT / "scripts" / "run_operator_soak_eval.py"
_ACTION_YML = _REPO_ROOT / "action.yml"


# ---------------------------------------------------------------------------
# Helpers — build a fully-populated case directory under tmp_path.
# ---------------------------------------------------------------------------


def _write_fiche(
    case_dir: Path,
    *,
    case_id: str,
    status: str = "complete",
    expected_risk: str = "low",
    workflow_run_id: str | None = "1234567890",
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "repo": "yannabadie/oida-code",
        "branch": "main",
        "commit": "deadbeef",
        "operator": "yannabadie",
        "intent": "Controlled minor change",
        "expected_risk": expected_risk,
        "gateway_bundle": "tests/fixtures/action_gateway_bundle/tool_needed_then_supported",
        "workflow_run_id": workflow_run_id,
        "artifact_url": None,
        "notes": "",
        "status": status,
    }
    (case_dir / "fiche.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )


def _write_label(case_dir: Path, *, label: str) -> None:
    payload = {
        "operator_label": label,
        "operator_rationale": (
            "Line one of rationale.\n"
            "Line two of rationale.\n"
            "Line three of rationale."
        ),
        "labeled_by": "yannabadie",
        "labeled_at": "2026-04-27T12:00:00Z",
    }
    (case_dir / "label.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )


def _write_ux(case_dir: Path) -> None:
    payload = {
        "summary_readability": 2,
        "evidence_traceability": 1,
        "actionability": 2,
        "no_false_verdict": 2,
        "scored_by": "yannabadie",
        "scored_at": "2026-04-27T12:00:00Z",
    }
    (case_dir / "ux_score.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )


def _build_complete_case(
    cases_root: Path,
    case_id: str,
    *,
    label: str,
) -> None:
    case_dir = cases_root / case_id
    _write_fiche(case_dir, case_id=case_id, status="complete")
    _write_label(case_dir, label=label)
    _write_ux(case_dir)


# ---------------------------------------------------------------------------
# 5.7-A / 5.7-B — directory + fiche scaffolding committed
# ---------------------------------------------------------------------------


def test_operator_soak_cases_dir_exists() -> None:
    assert _CASES_DIR.is_dir()


def test_operator_soak_cases_root_readme_exists() -> None:
    assert (_CASES_DIR / "README.md").is_file()


def test_case_001_scaffold_exists() -> None:
    case_dir = _CASES_DIR / "case_001_oida_code_self"
    assert case_dir.is_dir()
    assert (case_dir / "README.md").is_file()
    assert (case_dir / "fiche.json").is_file()


def test_case_001_fiche_validates_against_schema() -> None:
    case_dir = _CASES_DIR / "case_001_oida_code_self"
    payload = json.loads((case_dir / "fiche.json").read_text(encoding="utf-8"))
    fiche = OperatorSoakFiche.model_validate(payload)
    # Phase 5.8.1-C (QA/A39 follow-up): case_001 was redispatched on
    # commit da9623a as workflow run 25022965745 after the verify-grounded
    # --repo-root runtime override + cherry-picked
    # operator-soak/case-001-docstring-v2 branch fixed the dual-checkout
    # pytest cwd bug. The verifier-grounded happy path now ends with
    # status=verification_candidate accepted=1 (the docstring claim is
    # genuinely true and pytest now actually executes against the
    # audit-subject's tests/). cgpro session unslop-md labelled this
    # rerun ``useful_true_positive``. The case is still ``complete``
    # and still does NOT count toward ``document_opt_in_path`` (1 < 3;
    # recommendation stays ``continue_soak`` per QA/A34 §5.7-F rule 1).
    assert fiche.status == "complete"
    assert fiche.workflow_run_id == "25022965745"
    assert fiche.artifact_url == (
        "https://github.com/yannabadie/oida-code/actions/runs/25022965745"
    )
    assert fiche.commit and fiche.commit.startswith("ddf302a")
    assert fiche.branch == "operator-soak/case-001-docstring-v2"


def test_case_001_has_cgpro_label_and_ux_score() -> None:
    """Phase 5.8 (QA/A37 + QA/A38) + Phase 5.8.1-C rerun: case_001
    carries operator-written label.json + ux_score.json from cgpro.
    Claude is NOT allowed to write these files itself; the schema
    validates the structural shape and the ``labelled_by`` /
    ``scored_by`` fields cite the cgpro session explicitly.

    The Phase 5.8.1-C rerun (workflow run 25022965745 on commit
    da9623a, target-ref operator-soak/case-001-docstring-v2)
    upgraded the label from ``useful_true_negative`` (Phase 5.8.1-B
    rerun on the original branch) to ``useful_true_positive`` after
    the verify-grounded --repo-root override + cherry-picked v2
    branch fixed the dual-checkout pytest cwd bug. The verifier
    now accepts the C.docstring.no_behavior_delta claim with full
    actionable [E.tool.pytest.0] (kind=test_result) corroboration.
    UX score also bumps to 2/2/2/2 (actionability was 1 in the
    Phase 5.8.1-B run because pytest didn't actually execute the
    audit-subject's tests).
    """
    case_dir = _CASES_DIR / "case_001_oida_code_self"
    label_payload = json.loads(
        (case_dir / "label.json").read_text(encoding="utf-8"),
    )
    label = OperatorLabelEntry.model_validate(label_payload)
    assert label.operator_label == "useful_true_positive"
    assert label.labeled_by is not None
    assert "cgpro session unslop-md" in label.labeled_by
    # Rationale must be the canonical 3-10 line range.
    assert 3 <= len(label.operator_rationale) <= 10

    ux_payload = json.loads(
        (case_dir / "ux_score.json").read_text(encoding="utf-8"),
    )
    ux = OperatorUxScore.model_validate(ux_payload)
    # Phase 5.8.1-C unlocked perfect 2/2/2/2 — the topology fix
    # made pytest actually run, so actionability bumped from 1 to 2.
    assert ux.summary_readability == 2
    assert ux.evidence_traceability == 2
    assert ux.actionability == 2
    assert ux.no_false_verdict == 2  # gateway preserved ADR-22 hard wall
    assert ux.scored_by is not None
    assert "cgpro session unslop-md" in ux.scored_by


# ---------------------------------------------------------------------------
# Phase 5.8-prep (QA/A36) — case_002 + case_003 + RUNBOOK
# ---------------------------------------------------------------------------


_REQUIRED_BUNDLE_FILES = (
    "approved_tools.json",
    "gateway_definitions.json",
    "packet.json",
    "pass1_backward.json",
    "pass1_forward.json",
    "pass2_backward.json",
    "pass2_forward.json",
    "tool_policy.json",
)


@pytest.mark.parametrize(
    "case_id",
    ("case_002_python_semver", "case_003_markupsafe"),
)
def test_phase58_prep_scaffolded_case_dirs_exist(case_id: str) -> None:
    case_dir = _CASES_DIR / case_id
    assert case_dir.is_dir()
    assert (case_dir / "README.md").is_file()
    assert (case_dir / "fiche.json").is_file()
    assert (case_dir / "bundle").is_dir()


def test_phase58_case002_cgpro_selected_upstream_and_dispatched() -> None:
    """QA/A37 + QA/A38 + Phase 5.8.1-D: case_002 selection came from
    cgpro and Phase 5.8.1-D's new ``inputs.target-repo`` enabled the
    cross-repo dispatch on workflow run 25040744063. The case is now
    ``complete`` with cgpro session unslop-md-2 having labelled it
    ``useful_true_positive`` (after a truncated-prompt round-trip
    surfaced via QA/Q3.md). The bundle is no longer scaffolded — it
    is the real audit packet for python-semver/python-semver@0309c63
    PR #292 ('Fix #291: Disallow negative numbers in VersionInfo').
    """
    case_id = "case_002_python_semver"
    payload = json.loads(
        (_CASES_DIR / case_id / "fiche.json").read_text(encoding="utf-8"),
    )
    fiche = OperatorSoakFiche.model_validate(payload)
    assert fiche.case_id == "case_002_python_semver"
    assert fiche.status == "complete"
    assert fiche.repo == "python-semver/python-semver"
    assert fiche.branch == "master"
    assert fiche.commit == "0309c63ce834b7d35aa3e29b8d5bb0357532b016"
    # Notes record the full cgpro session history (initial selection
    # in phase58-soak, dispatch + relabelling in unslop-md-2).
    assert "cgpro session" in fiche.notes
    # Notes must reference the upstream identity in some form -- the
    # commit SHA (full or short) or the python-semver repo path.
    assert "python-semver/python-semver" in fiche.notes
    assert fiche.workflow_run_id == "25040744063"
    assert fiche.artifact_url == (
        "https://github.com/yannabadie/oida-code/actions/runs/25040744063"
    )


def test_phase58_case003_cgpro_selected_upstream_and_dispatched() -> None:
    """QA/A37 + QA/A38 + Phase 5.8.1-E + Phase 5.8.x: case_003 selection
    came from cgpro and Phase 5.8.1-E's ``inputs.target-install`` enabled
    the editable-install path required for markupsafe's C extension.
    Originally dispatched as workflow run 25045245609 (commit 469de38)
    against pallets/markupsafe@7856c3d, then re-dispatched as workflow
    run 25047711777 (commit 93c7581 — Phase 5.8.x / ADR-47
    pytest_summary_line) to upgrade UX evidence_traceability from 1 to
    2 once the gateway adapter started folding pytest's terminal summary
    line into [E.tool.pytest.0]. The case is ``complete`` with cgpro
    session phase58-soak (relabel) confirming useful_true_positive
    UX 2/2/2/2 — original cgpro session unslop-md-2 (labelling) referenced
    in the fiche history.
    """
    case_id = "case_003_markupsafe"
    payload = json.loads(
        (_CASES_DIR / case_id / "fiche.json").read_text(encoding="utf-8"),
    )
    fiche = OperatorSoakFiche.model_validate(payload)
    assert fiche.case_id == "case_003_markupsafe"
    assert fiche.status == "complete"
    assert fiche.repo == "pallets/markupsafe"
    assert fiche.branch == "main"
    assert fiche.commit == "7856c3d945a969bc94a19989dda61c3d50ac2adb"
    assert fiche.expected_risk == "medium"
    # Notes record the cgpro session history (both labelling and relabel).
    assert "cgpro session" in fiche.notes
    assert "pallets/markupsafe" in fiche.notes
    # The fiche must reference both the original run and the Phase 5.8.x
    # re-dispatch run so the audit trail is complete.
    assert "25045245609" in fiche.notes
    assert "25047711777" in fiche.notes
    # workflow_run_id points at the latest (Phase 5.8.x) re-dispatch.
    assert fiche.workflow_run_id == "25047711777"
    assert fiche.artifact_url == (
        "https://github.com/yannabadie/oida-code/actions/runs/25047711777"
    )


@pytest.mark.parametrize(
    "case_id",
    (
        "case_001_oida_code_self",
        "case_002_python_semver",
        "case_003_markupsafe",
    ),
)
def test_phase58_prep_bundle_carries_8_required_files(case_id: str) -> None:
    bundle_dir = _CASES_DIR / case_id / "bundle"
    for filename in _REQUIRED_BUNDLE_FILES:
        assert (bundle_dir / filename).is_file(), (
            f"missing {filename!r} from {case_id} bundle"
        )


def test_phase58_all_three_cases_carry_cgpro_authored_label_and_ux() -> None:
    """All three Phase 5.8 cases (001, 002, 003) have now been
    dispatched and labelled by cgpro. The earlier ``no_label_or_ux_yet``
    structural lock no longer applies — every committed case_*/ dir
    MUST carry label.json + ux_score.json, and the labeled_by /
    scored_by fields MUST cite a cgpro session (NOT Claude).

    Phase 5.8.1-C closed case_001 (workflow run 25022965745, label
    useful_true_positive). Phase 5.8.1-D closed case_002 (run
    25040744063, label useful_true_positive). Phase 5.8.1-E closed
    case_003 (run 25045245609, label useful_true_positive); Phase 5.8.x
    re-dispatched case_003 as run 25047711777 with the new
    pytest_summary_line evidence shape and cgpro relabelled UX
    2/1/2/2 → 2/2/2/2 (label still useful_true_positive). With
    cases_completed=3 the aggregator's rule 2 short-circuit
    (cases_completed<3 → continue_soak) no longer fires; the next
    rule that could flip the recommendation off continue_soak is
    rule 5 (cases_completed>=5 with usefulness_rate>=0.6), which
    requires scaffolding case_004 + case_005.
    """
    for case_id in (
        "case_001_oida_code_self",
        "case_002_python_semver",
        "case_003_markupsafe",
    ):
        case_dir = _CASES_DIR / case_id
        label_path = case_dir / "label.json"
        ux_path = case_dir / "ux_score.json"
        assert label_path.is_file(), (
            f"{case_id} missing label.json (Tier 3 baseline expects all "
            f"three cases dispatched + labelled)"
        )
        assert ux_path.is_file(), (
            f"{case_id} missing ux_score.json"
        )
        # Schema check + cgpro provenance.
        label = OperatorLabelEntry.model_validate(
            json.loads(label_path.read_text(encoding="utf-8")),
        )
        assert label.labeled_by is not None
        assert "cgpro session" in label.labeled_by, (
            f"{case_id} label.json labeled_by must cite a cgpro session, "
            f"got {label.labeled_by!r}"
        )
        ux = OperatorUxScore.model_validate(
            json.loads(ux_path.read_text(encoding="utf-8")),
        )
        assert ux.scored_by is not None
        assert "cgpro session" in ux.scored_by, (
            f"{case_id} ux_score.json scored_by must cite a cgpro session, "
            f"got {ux.scored_by!r}"
        )


def test_phase58_prep_runbook_exists_with_required_sections() -> None:
    runbook = _CASES_DIR / "RUNBOOK.md"
    assert runbook.is_file()
    body = runbook.read_text(encoding="utf-8")
    # Step headers per QA/A36 §4.
    for header in (
        "Step 1",
        "Step 2",
        "Step 3",
        "Step 4",
        "Step 5",
        "Step 6",
        "Step 7",
        "Step 8",
    ):
        assert header in body, f"RUNBOOK missing {header!r}"
    # Operator-only rule must be restated.
    assert "operator-only" in body.lower() or "operator only" in body.lower()
    # Forbidden tokens must NOT appear in the runbook itself.
    for forbidden in (
        "merge_safe", "production_safe", "bug_free",
        "security_verified", "total_v_net", "debt_final", "corrupt_success",
    ):
        assert forbidden not in body, f"RUNBOOK leaked forbidden token {forbidden!r}"


def test_phase58_aggregate_tier4_four_cases_complete() -> None:
    """Tier 4 — case_004 added on top of the Tier 3 baseline. case_001
    (Phase 5.8.1-C run 25022965745), case_002 (Phase 5.8.1-D run
    25040744063), case_003 (Phase 5.8.1-E run 25045245609 → Phase 5.8.x
    re-dispatch run 25047711777), and case_004 (Phase 5.8 cgpro pre-pick
    un33k/python-slugify@7edf477, run 25050370380) have all been
    dispatched + labelled ``useful_true_positive`` by cgpro. The
    aggregator's rule 5 (cases_completed>=5 with usefulness_rate>=0.6)
    has NOT fired yet — promotion off continue_soak still requires
    case_005. Rule 2 short-circuit (cases_completed<3 → continue_soak)
    no longer fires; rules 3-4 require false_* counts >=2 (we have 0).

    Phase 5.8.x evidence-shape upgrade (commits 93c7581, c7734b3 — the
    pytest_summary_line schema field plus the ANSI-strip fix surfaced
    on case_004) means every UX axis now scores 2 on every case from
    case_004 onward; case_003 was relabelled from 2/1/2/2 to 2/2/2/2
    in the same cycle, so all four UX averages are 2.000.
    """
    payload = json.loads(
        (_REPO_ROOT / "reports" / "operator_soak" / "aggregate.json")
        .read_text(encoding="utf-8"),
    )
    assert payload["recommendation"] == "continue_soak"
    assert payload["cases_completed"] == 4
    # All four cases useful_true_positive (perfect Tier 4 outcome).
    assert payload["useful_true_positive_count"] == 4
    assert payload["useful_true_negative_count"] == 0
    assert payload["insufficient_fixture_count"] == 0
    assert payload["false_positive_count"] == 0
    assert payload["false_negative_count"] == 0
    assert payload["official_field_leak_count"] == 0
    # Usefulness rate at the rule-5 threshold (0.6); only the
    # cases_completed<5 gate keeps continue_soak active.
    assert payload["operator_usefulness_rate"] >= 0.6
    # Phase 5.8.x evidence shape — UX averages all hold at 2.0.
    assert payload["summary_readability_avg"] == 2.0
    assert payload["evidence_traceability_avg"] == 2.0
    assert payload["actionability_avg"] == 2.0
    assert payload["no_false_verdict_avg"] == 2.0


# ---------------------------------------------------------------------------
# 5.7-B — schema invariants
# ---------------------------------------------------------------------------


def test_fiche_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        OperatorSoakFiche.model_validate(
            {
                "case_id": "x",
                "repo": "x/y",
                "branch": "main",
                "commit": "abc",
                "operator": "op",
                "intent": "test",
                "expected_risk": "low",
                "gateway_bundle": "tests/fixtures/action_gateway_bundle/x",
                "status": "complete",
                "extra_key": "should be rejected",
            },
        )


def test_fiche_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        OperatorSoakFiche.model_validate(
            {
                "case_id": "x",
                "repo": "x/y",
                "branch": "main",
                "commit": "abc",
                "operator": "op",
                "intent": "test",
                "expected_risk": "low",
                "gateway_bundle": "tests/fixtures/action_gateway_bundle/x",
                "status": "merge_safe",
            },
        )


def test_fiche_is_frozen() -> None:
    fiche = OperatorSoakFiche.model_validate(
        {
            "case_id": "x",
            "repo": "x/y",
            "branch": "main",
            "commit": "abc",
            "operator": "op",
            "intent": "test",
            "expected_risk": "low",
            "gateway_bundle": "tests/fixtures/action_gateway_bundle/x",
            "status": "complete",
        },
    )
    with pytest.raises(ValidationError):
        fiche.status = "blocked"  # type: ignore[misc]


def test_label_rejects_forbidden_verdict_strings() -> None:
    """A forged label.json with merge_safe / production_safe is
    rejected at the schema layer because operator_label is a Literal.
    """
    for forbidden in ("merge_safe", "production_safe", "verified", "bug_free"):
        with pytest.raises(ValidationError):
            OperatorLabelEntry.model_validate(
                {
                    "operator_label": forbidden,
                    "operator_rationale": "a\nb\nc",
                    "labeled_by": "op",
                    "labeled_at": "2026-04-27T12:00:00Z",
                },
            )


def test_label_rationale_must_have_at_least_three_lines() -> None:
    with pytest.raises(ValidationError):
        OperatorLabelEntry.model_validate(
            {
                "operator_label": "false_positive",
                "operator_rationale": "single line",
                "labeled_by": "op",
                "labeled_at": "2026-04-27T12:00:00Z",
            },
        )


def test_label_rationale_capped_at_ten_lines() -> None:
    with pytest.raises(ValidationError):
        OperatorLabelEntry.model_validate(
            {
                "operator_label": "false_positive",
                "operator_rationale": "\n".join(f"line {i}" for i in range(11)),
                "labeled_by": "op",
                "labeled_at": "2026-04-27T12:00:00Z",
            },
        )


def test_ux_score_rejects_out_of_range() -> None:
    for bad in (-1, 3, 99):
        with pytest.raises(ValidationError):
            OperatorUxScore.model_validate(
                {
                    "summary_readability": bad,
                    "evidence_traceability": 1,
                    "actionability": 1,
                    "no_false_verdict": 1,
                    "scored_by": "op",
                    "scored_at": "2026-04-27T12:00:00Z",
                },
            )


# ---------------------------------------------------------------------------
# 5.7-E / 5.7-F — aggregator + decision rules
# ---------------------------------------------------------------------------


def test_aggregate_empty_dir_returns_continue_soak(tmp_path: Path) -> None:
    """QA/A34 §5.7-F rule 1: cases_completed < 3 -> continue_soak.

    Zero cases is the baseline state until operators run real cases;
    the aggregator must return continue_soak without crashing.
    """
    cases_root = tmp_path / "operator_soak_cases"
    cases_root.mkdir()

    report = aggregate_cases(cases_root)

    assert report.cases_total == 0
    assert report.cases_completed == 0
    assert report.recommendation == "continue_soak"
    assert report.is_authoritative is False


def test_aggregate_missing_dir_returns_continue_soak(tmp_path: Path) -> None:
    """The aggregator must be safe to call before the directory exists."""
    cases_root = tmp_path / "does_not_exist"
    report = aggregate_cases(cases_root)
    assert report.cases_total == 0
    assert report.recommendation == "continue_soak"


def test_aggregate_two_complete_cases_still_continue_soak(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _build_complete_case(cases_root, "case_001", label="useful_true_positive")
    _build_complete_case(cases_root, "case_002", label="useful_true_negative")
    report = aggregate_cases(cases_root)
    assert report.cases_completed == 2
    assert report.recommendation == "continue_soak"


def test_leak_count_overrides_under_three_completed(tmp_path: Path) -> None:
    """5.7-F: leak count > 0 must beat every other rule, including
    the cases_completed < 3 short-circuit. ADR-22 hard wall.
    """
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    report = aggregate_cases(cases_root, official_field_leak_count=1)
    assert report.recommendation == "fix_contract_leak"


def test_two_false_negatives_with_three_completed_revise_policy(
    tmp_path: Path,
) -> None:
    cases_root = tmp_path / "cases"
    _build_complete_case(cases_root, "case_001", label="false_negative")
    _build_complete_case(cases_root, "case_002", label="false_negative")
    _build_complete_case(cases_root, "case_003", label="useful_true_positive")
    report = aggregate_cases(cases_root)
    assert report.recommendation == "revise_gateway_policy_or_prompts"


def test_two_false_positives_with_three_completed_revise_ux(
    tmp_path: Path,
) -> None:
    cases_root = tmp_path / "cases"
    _build_complete_case(cases_root, "case_001", label="false_positive")
    _build_complete_case(cases_root, "case_002", label="false_positive")
    _build_complete_case(cases_root, "case_003", label="useful_true_positive")
    report = aggregate_cases(cases_root)
    assert report.recommendation == "revise_report_ux_or_labels"


def test_document_opt_in_path_only_with_five_complete(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    for i in range(1, 6):
        _build_complete_case(
            cases_root, f"case_{i:03d}", label="useful_true_positive",
        )
    report = aggregate_cases(cases_root)
    assert report.cases_completed == 5
    assert report.operator_usefulness_rate == pytest.approx(1.0)
    assert report.recommendation == "document_opt_in_path"


def test_four_useful_cases_still_continue_soak(tmp_path: Path) -> None:
    """Even a 100% useful 4-case slate stays in continue_soak —
    document_opt_in_path requires >=5 completed cases.
    """
    cases_root = tmp_path / "cases"
    for i in range(1, 5):
        _build_complete_case(
            cases_root, f"case_{i:03d}", label="useful_true_positive",
        )
    report = aggregate_cases(cases_root)
    assert report.cases_completed == 4
    assert report.recommendation == "continue_soak"


def test_document_opt_in_threshold_is_not_met_under_zero_six(tmp_path: Path) -> None:
    """Five completed cases with 2/5 useful (0.4 < 0.6) -> continue_soak."""
    cases_root = tmp_path / "cases"
    _build_complete_case(cases_root, "case_001", label="useful_true_positive")
    _build_complete_case(cases_root, "case_002", label="useful_true_positive")
    _build_complete_case(cases_root, "case_003", label="unclear")
    _build_complete_case(cases_root, "case_004", label="unclear")
    _build_complete_case(cases_root, "case_005", label="insufficient_fixture")
    report = aggregate_cases(cases_root)
    assert report.recommendation == "continue_soak"


def test_compute_recommendation_precedence_pure() -> None:
    # leak overrides under-three.
    assert (
        compute_recommendation(
            cases_completed=0,
            official_field_leak_count=1,
            false_negative_count=0,
            false_positive_count=0,
            useful_true_positive_count=0,
            useful_true_negative_count=0,
        )
        == "fix_contract_leak"
    )
    # leak overrides false_negative threshold too.
    assert (
        compute_recommendation(
            cases_completed=10,
            official_field_leak_count=1,
            false_negative_count=10,
            false_positive_count=0,
            useful_true_positive_count=0,
            useful_true_negative_count=0,
        )
        == "fix_contract_leak"
    )
    # FN beats FP when both >=2.
    assert (
        compute_recommendation(
            cases_completed=10,
            official_field_leak_count=0,
            false_negative_count=2,
            false_positive_count=2,
            useful_true_positive_count=6,
            useful_true_negative_count=0,
        )
        == "revise_gateway_policy_or_prompts"
    )


# ---------------------------------------------------------------------------
# Aggregate report invariants
# ---------------------------------------------------------------------------


def test_aggregate_report_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        AggregateReport.model_validate(
            {
                "cases_total": 0,
                "cases_completed": 0,
                "useful_true_positive_count": 0,
                "useful_true_negative_count": 0,
                "false_positive_count": 0,
                "false_negative_count": 0,
                "unclear_count": 0,
                "insufficient_fixture_count": 0,
                "contract_violation_count": 0,
                "official_field_leak_count": 0,
                "operator_usefulness_rate": 0.0,
                "summary_readability_avg": 0.0,
                "evidence_traceability_avg": 0.0,
                "actionability_avg": 0.0,
                "no_false_verdict_avg": 0.0,
                "recommendation": "continue_soak",
                "total_v_net": 0.5,
            },
        )


def test_aggregate_report_is_authoritative_pinned_false(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    report = aggregate_cases(cases_root)
    with pytest.raises(ValidationError):
        AggregateReport.model_validate(
            {**report.model_dump(), "is_authoritative": True},
        )


def test_aggregate_report_rejects_invalid_recommendation() -> None:
    with pytest.raises(ValidationError):
        AggregateReport.model_validate(
            {
                "cases_total": 0,
                "cases_completed": 0,
                "useful_true_positive_count": 0,
                "useful_true_negative_count": 0,
                "false_positive_count": 0,
                "false_negative_count": 0,
                "unclear_count": 0,
                "insufficient_fixture_count": 0,
                "contract_violation_count": 0,
                "official_field_leak_count": 0,
                "operator_usefulness_rate": 0.0,
                "summary_readability_avg": 0.0,
                "evidence_traceability_avg": 0.0,
                "actionability_avg": 0.0,
                "no_false_verdict_avg": 0.0,
                "recommendation": "merge_safe",
            },
        )


def test_render_aggregate_markdown_no_forbidden_phrases(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _build_complete_case(cases_root, "case_001", label="useful_true_positive")
    _build_complete_case(cases_root, "case_002", label="useful_true_negative")
    _build_complete_case(cases_root, "case_003", label="false_positive")
    rendered = render_aggregate_markdown(
        aggregate_cases(
            cases_root,
            gateway_status_distribution={"diagnostic_only": 3},
        ),
    )
    forbidden = (
        "merge_safe", "merge-safe",
        "production_safe", "production-safe",
        "bug_free", "bug-free",
        "security_verified", "total_v_net",
        "debt_final", "corrupt_success",
        # "verified" appears legitimately as a substring of words like
        # "diagnostic"; we only check the token form here.
    )
    for tok in forbidden:
        assert tok not in rendered, f"forbidden token {tok!r} leaked"
    # "Diagnostic-only" honesty wording present.
    assert "Diagnostic-only" in rendered or "diagnostic-only" in rendered.lower()


def test_aggregate_distribution_is_sorted_tuple(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    report = aggregate_cases(
        cases_root,
        gateway_status_distribution={"diagnostic_only": 2, "blocked": 1},
    )
    assert report.gateway_status_distribution == (
        ("blocked", 1), ("diagnostic_only", 2),
    )


# ---------------------------------------------------------------------------
# Eval script CLI smoke
# ---------------------------------------------------------------------------


def test_eval_script_runs_against_empty_dir(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    out_dir = tmp_path / "reports"
    proc = subprocess.run(
        [
            sys.executable, str(_EVAL_SCRIPT),
            "--cases-root", str(cases_root),
            "--out-dir", str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "continue_soak" in proc.stdout
    payload = json.loads((out_dir / "aggregate.json").read_text(encoding="utf-8"))
    assert payload["recommendation"] == "continue_soak"
    md = (out_dir / "aggregate.md").read_text(encoding="utf-8")
    assert "continue_soak" in md


def test_eval_script_parses_gateway_status_flag(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    out_dir = tmp_path / "reports"
    proc = subprocess.run(
        [
            sys.executable, str(_EVAL_SCRIPT),
            "--cases-root", str(cases_root),
            "--out-dir", str(out_dir),
            "--gateway-status", "diagnostic_only=2",
            "--gateway-status", "blocked=1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads((out_dir / "aggregate.json").read_text(encoding="utf-8"))
    distribution = {k: v for k, v in payload["gateway_status_distribution"]}
    assert distribution == {"blocked": 1, "diagnostic_only": 2}


# ---------------------------------------------------------------------------
# 5.7-I — anti-MCP / anti-provider locks extended
# ---------------------------------------------------------------------------


def test_operator_soak_package_does_not_import_mcp_runtime() -> None:
    forbidden_runtime_tokens = (
        "mcp.client", "mcp.server", "mcp_session", "json_rpc_dispatch",
        "tool_calling", "websocket",
    )
    for path in _PACKAGE_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        # AST walk: no import statement may name MCP runtime modules.
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "mcp" not in alias.name.split(".")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "mcp" not in module.split(".")
        # Strip docstrings before token scan so legitimate explanatory
        # mentions in module docstrings (e.g. "no MCP") do not trip the
        # runtime lock.
        sanitised = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        sanitised = re.sub(r"'''.*?'''", "", sanitised, flags=re.DOTALL)
        sanitised = re.sub(r"#.*", "", sanitised)
        lower = sanitised.lower()
        for tok in forbidden_runtime_tokens:
            assert tok not in lower, (
                f"runtime token {tok!r} appeared in {path.name}"
            )


def test_no_provider_external_call_in_eval_script() -> None:
    body = _EVAL_SCRIPT.read_text(encoding="utf-8")
    for tok in ("openai", "anthropic", "modelcontextprotocol", "requests.post"):
        assert tok.lower() not in body.lower()


def test_no_pull_request_target_in_phase_5_7_files() -> None:
    """Phase 5.7 must not introduce any pull_request_target reference."""
    for path in (_EVAL_SCRIPT, *_PACKAGE_DIR.rglob("*.py")):
        body = path.read_text(encoding="utf-8")
        assert "pull_request_target" not in body


def test_action_yml_default_enable_tool_gateway_still_false() -> None:
    """Phase 5.7 must NOT flip enable-tool-gateway to default true."""
    body = _ACTION_YML.read_text(encoding="utf-8")
    after = body.split("enable-tool-gateway:", 1)[1]
    next_input = re.search(r"\n  [a-z][a-z0-9-]*:\n", after)
    block = after[: next_input.start()] if next_input else after
    match = re.search(r'default:\s*"([^"]*)"', block)
    assert match is not None
    assert match.group(1) == "false"


# ---------------------------------------------------------------------------
# Phase 5.7 docs locks: ADR-42 + report present
# ---------------------------------------------------------------------------


def test_adr_42_present_in_decision_log() -> None:
    body = _DECISION_LOG.read_text(encoding="utf-8")
    assert "ADR-42" in body
    # ADR-42 must mention the fork-PR block disposition.
    assert "Operator soak" in body or "operator soak" in body


def test_phase_5_7_report_present_with_honesty_statement() -> None:
    assert _PHASE_REPORT.is_file()
    body = _PHASE_REPORT.read_text(encoding="utf-8")
    # QA/A34 mandates this exact wording.
    required = (
        "Phase 5.7 evaluates the opt-in gateway-grounded action path",
        "It does not make the gateway default",
        "It does not run on fork PRs",
        "It does not implement MCP",
        "It does not enable provider tool-calling",
        "It does not validate production predictive performance",
        "It does not emit official total_v_net, debt_final, or corrupt_success",
        "It does not modify the vendored OIDA core",
    )
    for fragment in required:
        assert fragment in body, f"missing honesty fragment: {fragment!r}"


def test_phase_5_7_report_carries_split_acceptance_table() -> None:
    body = _PHASE_REPORT.read_text(encoding="utf-8")
    # Split AC table: shipped vs scaffolded-blocked-on-operator.
    assert "shipped" in body.lower()
    assert "scaffolded" in body.lower() or "awaiting" in body.lower()


def test_phase_5_7_report_does_not_emit_official_fields() -> None:
    body = _PHASE_REPORT.read_text(encoding="utf-8").lower()
    forbidden = (
        "merge_safe", "merge-safe",
        "production_safe", "production-safe",
        "bug_free", "bug-free",
        "security_verified",
    )
    for tok in forbidden:
        assert tok not in body, f"phase 5.7 report leaked {tok!r}"


# ---------------------------------------------------------------------------
# Enum invariants
# ---------------------------------------------------------------------------


def test_recommendation_enum_does_not_contain_product_verdicts() -> None:
    for forbidden in (
        "merge_safe", "production_safe", "verified", "bug_free",
    ):
        assert forbidden not in RECOMMENDATION_VALUES


def test_operator_label_enum_has_six_buckets() -> None:
    assert len(OPERATOR_LABEL_VALUES) == 6
    assert "useful_true_positive" in OPERATOR_LABEL_VALUES
    assert "false_negative" in OPERATOR_LABEL_VALUES
    assert "insufficient_fixture" in OPERATOR_LABEL_VALUES


def test_status_enum_has_nine_buckets() -> None:
    """Phase 5.8-prep status taxonomy:

    * QA/A36 added ``awaiting_case_selection`` and ``awaiting_operator_run``
    * QA/A38 added ``awaiting_operator_dispatch`` (real packet ready, awaiting
      cgpro+Yann double-gate to dispatch) and
      ``awaiting_real_audit_packet_decision`` (upstream selected by cgpro
      but bundle still seeded — operator must decide on real packet vs
      replace vs insufficient_fixture).
    """
    assert set(SOAK_STATUS_VALUES) == {
        "awaiting_case_selection",
        "awaiting_operator",
        "awaiting_operator_run",
        "awaiting_operator_dispatch",
        "awaiting_real_audit_packet_decision",
        "awaiting_run",
        "awaiting_label",
        "complete",
        "blocked",
    }


def test_expected_risk_enum_has_four_buckets() -> None:
    assert set(EXPECTED_RISK_VALUES) == {"low", "medium", "high", "unknown"}
