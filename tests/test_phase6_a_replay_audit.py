"""Phase 6.a / G-6a static replay-content audit tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "audit_llm_replays.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_audit_llm_replays_for_tests",
        _SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_record() -> dict[str, Any]:
    return {
        "case_id": "seed_test_owner_repo_42",
        "claim_id": "C.fixture_surface.repair_needed",
        "claim_type": "repair_needed",
        "claim_text": (
            "After PR #42 the CLI accepts -x as alias for --xtra, "
            "and the scoped pytest test proves the repair."
        ),
        "test_scope": "tests/test_cli.py::test_xtra_alias",
        "evidence_items": [
            {
                "id": "[E.event.1]",
                "kind": "event",
                "summary": "PR #42 adds -x alias to CLI parser.",
                "source": "git",
                "confidence": 0.9,
            },
            {
                "id": "[E.test_result.1]",
                "kind": "test_result",
                "summary": "Scoped pytest covers the -x alias.",
                "source": "ticket",
                "confidence": 0.85,
            },
        ],
    }


def _case_files() -> dict[str, Any]:
    case_id = "seed_test_owner_repo_42"
    event_id = f"evt-{case_id}"
    claim_id = "C.fixture_surface.repair_needed"
    return {
        "packet.json": {
            "event_id": event_id,
            "allowed_fields": ["capability", "tests_pass", "operator_accept"],
            "intent_summary": "fixture packet",
            "evidence_items": _seed_record()["evidence_items"],
            "deterministic_estimates": [],
        },
        "pass1_forward.json": {
            "event_id": event_id,
            "supported_claims": [],
            "rejected_claims": [],
            "missing_evidence_refs": [],
            "contradictions": [],
            "warnings": [],
            "requested_tools": [
                {
                    "tool": "pytest",
                    "purpose": "Run scoped pytest for the fixture claim.",
                    "expected_evidence_kind": "test_result",
                    "scope": ["tests/test_cli.py::test_xtra_alias"],
                },
            ],
        },
        "pass1_backward.json": [],
        "pass2_forward.json": {
            "event_id": event_id,
            "supported_claims": [
                {
                    "claim_id": claim_id,
                    "event_id": event_id,
                    "claim_type": "repair_needed",
                    "statement": "The CLI -x alias repair is covered by the scoped pytest test.",
                    "confidence": 0.55,
                    "evidence_refs": ["[E.event.1]", "[E.tool.pytest.0]"],
                    "source": "forward",
                },
            ],
            "rejected_claims": [],
            "missing_evidence_refs": [],
            "contradictions": [],
            "warnings": [],
            "requested_tools": [],
        },
        "pass2_backward.json": [
            {
                "event_id": event_id,
                "claim_id": claim_id,
                "requirement": {
                    "claim_id": claim_id,
                    "required_evidence_kinds": ["test_result"],
                    "satisfied_evidence_refs": ["[E.tool.pytest.0]"],
                    "missing_requirements": [],
                },
                "necessary_conditions_met": True,
                "warnings": [],
            },
        ],
        "grounded_report.json": {
            "report": {
                "status": "verification_candidate",
                "accepted_claims": [
                    {
                        "claim_id": claim_id,
                        "event_id": event_id,
                        "claim_type": "repair_needed",
                        "statement": (
                            "The CLI -x alias repair is covered by the "
                            "scoped pytest test."
                        ),
                        "confidence": 0.55,
                        "evidence_refs": ["[E.event.1]", "[E.tool.pytest.0]"],
                        "source": "forward",
                        "is_authoritative": False,
                    },
                ],
                "rejected_claims": [],
                "unsupported_claims": [],
                "blockers": [],
                "warnings": [],
                "recommendation": "fixture",
                "authoritative": False,
            },
            "tool_results": [
                {
                    "tool": "pytest",
                    "status": "ok",
                    "evidence_items": [
                        {
                            "id": "[E.tool.pytest.0]",
                            "kind": "test_result",
                            "summary": "pytest passed scoped to fixture.",
                            "source": "pytest",
                            "confidence": 0.85,
                        },
                    ],
                },
            ],
            "enriched_evidence_refs": ["[E.tool.pytest.0]"],
        },
    }


def _write_fixture(
    tmp_path: Path,
    *,
    mutator: Any | None = None,
    case_id: str = "seed_test_owner_repo_42",
) -> tuple[Path, Path]:
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps([_seed_record()], indent=2) + "\n",
        encoding="utf-8",
    )
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    files = copy.deepcopy(_case_files())
    if mutator is not None:
        mutator(files)
    for name, body in files.items():
        (case_dir / name).write_text(
            json.dumps(body, indent=2) + "\n",
            encoding="utf-8",
        )
    return index_path, case_dir


def _audit(tmp_path: Path, mutator: Any | None = None) -> dict[str, Any]:
    mod = _load_script()
    index_path, case_dir = _write_fixture(tmp_path, mutator=mutator)
    return mod.audit_round_trip_dirs([case_dir], index_path=index_path)


def _assert_error(report: dict[str, Any], invariant_id: str) -> None:
    findings = report["cases"][0]["findings"]
    assert any(
        f["severity"] == "error" and f["invariant_id"] == invariant_id
        for f in findings
    ), findings


def test_static_replay_audit_passes_clean_fixture(tmp_path: Path) -> None:
    report = _audit(tmp_path)
    assert report["semantic_truth_validated"] is False
    assert report["summary"]["passed"] == 1
    assert report["summary"]["error_count"] == 0
    assert report["cases"][0]["status"] == "pass"


def test_static_replay_audit_fails_unknown_case_id(tmp_path: Path) -> None:
    mod = _load_script()
    index_path, case_dir = _write_fixture(
        tmp_path,
        case_id="seed_missing_owner_repo_99",
    )
    report = mod.audit_round_trip_dirs([case_dir], index_path=index_path)
    _assert_error(report, "SEED-MISSING")


def test_static_replay_audit_fails_claim_id_mismatch(tmp_path: Path) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["pass2_forward.json"]["supported_claims"][0]["claim_id"] = (
            "C.other_surface.repair_needed"
        )

    report = _audit(tmp_path, mutate)
    _assert_error(report, "CLAIM-ID")


def test_static_replay_audit_fails_pytest_scope_mismatch(tmp_path: Path) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["pass1_forward.json"]["requested_tools"][0]["scope"] = [
            "tests/test_other.py::test_other",
        ]

    report = _audit(tmp_path, mutate)
    _assert_error(report, "PASS1-SCOPE")


def test_static_replay_audit_fails_unknown_evidence_ref(tmp_path: Path) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["pass2_forward.json"]["supported_claims"][0][
            "evidence_refs"
        ].append("[E.unknown.99]")

    report = _audit(tmp_path, mutate)
    _assert_error(report, "REF-UNKNOWN")


def test_static_replay_audit_fails_missing_tool_evidence(tmp_path: Path) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["pass2_forward.json"]["supported_claims"][0]["evidence_refs"] = [
            "[E.event.1]",
        ]

    report = _audit(tmp_path, mutate)
    _assert_error(report, "CLAIM-TOOL-EVIDENCE")


def test_static_replay_audit_fails_missing_backward_test_requirement(
    tmp_path: Path,
) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["pass2_backward.json"][0]["requirement"][
            "required_evidence_kinds"
        ] = ["event"]

    report = _audit(tmp_path, mutate)
    _assert_error(report, "BACKWARD-TEST-REQUIREMENT")


def test_static_replay_audit_fails_grounded_report_extra_accepted_claim(
    tmp_path: Path,
) -> None:
    def mutate(files: dict[str, Any]) -> None:
        files["grounded_report.json"]["report"]["accepted_claims"][0][
            "claim_id"
        ] = "C.absent_surface.repair_needed"

    report = _audit(tmp_path, mutate)
    _assert_error(report, "REPORT-ACCEPTED-SUBSET")
