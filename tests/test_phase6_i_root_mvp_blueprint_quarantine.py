"""Phase 6.i root MVP blueprint diagnostic quarantine guards."""

from __future__ import annotations

import json
import re

from tests.conftest import REPO_ROOT

_BLUEPRINT_MD = REPO_ROOT / "oida-code-mvp-blueprint.md"
_REPORT_JSON = (
    REPO_ROOT
    / "reports"
    / "phase6_i_root_mvp_blueprint_quarantine"
    / "report.json"
)

_HISTORICAL_MARKERS = (
    "historical",
    "Historical",
    "obsolete",
    "Obsolete",
    "pre-ADR-",
    "pre-Phase-",
    "no longer used",
    "no longer the active",
    "not an active",
    "not active",
    "not a current",
    "NOT an active",
    "NOT a current",
    "not public outputs",
    "not emitted",
    "blocked by",
    "ARCHIVAL",
    "historicization",
    "supersede",
    "Supersede",
)

_FORBIDDEN_ACTIVE_CLAIMS = (
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
)

_DANGEROUS_PHRASES = (
    "AI code verifier",
    "actually guarantees",
    "proved enough for merge",
    "Final verdict buckets",
    "repair planner",
    "GitHub App later",
    "verdict merge",
)


def _context_around(
    lines: list[str], idx: int, window: int = 30
) -> str:
    start = max(0, idx - window)
    end = min(len(lines), idx + window + 1)
    return "\n".join(lines[start:end])


def _compact(text: str) -> str:
    return re.sub(r"\s+(?:>\s+)?", " ", text)


def test_blueprint_starts_with_archival_banner() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")
    head = "\n".join(body.splitlines()[:35])
    head_compact = _compact(head)

    assert "ARCHIVAL" in head
    assert "READ THIS FIRST" in head
    assert "Phase 6.i" in head
    assert "ADR-81" in head
    assert "Do not quote sentences from this file" in head_compact
    assert "docs/product_strategy.md" in head
    assert "docs/project_status.md" in head


def test_blueprint_archival_banner_lists_blocked_fields() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")
    head = "\n".join(body.splitlines()[:35])

    for blocked in (
        "total_v_net",
        "debt_final",
        "corrupt_success",
        "corrupt_success_ratio",
        "verdict",
        "V_net",
        "Debt",
    ):
        assert blocked in head, f"banner must reference blocked field {blocked}"
    assert "ADR-22" in head
    assert "Literal[False]" in head


def test_blueprint_dangerous_phrases_only_in_historical_context() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")
    lines = body.splitlines()

    for phrase in _DANGEROUS_PHRASES:
        for idx, line in enumerate(lines):
            if phrase in line:
                context = _context_around(lines, idx)
                assert any(
                    marker in context for marker in _HISTORICAL_MARKERS
                ), (
                    f"oida-code-mvp-blueprint.md:{idx + 1} mentions "
                    f"{phrase!r} without a historical marker within "
                    f"+/-30 surrounding lines: {line!r}"
                )


def test_blueprint_section_headers_marked_historical() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")

    expected_historical_headers = (
        "## 1. Positioning",
        "### Pass 3 — Agentic verification",
        "### Deployment modes",
        "## 9. Report contract",
        "## 10. LLM choice for the MVP",
        "## 11. First 10 implementation days",
        "## 12. Hard rules for honesty",
        "## 13. Best wedge",
    )
    for header in expected_historical_headers:
        idx = body.find(header)
        assert idx != -1, f"missing header {header!r}"
        header_line_end = body.find("\n", idx)
        next_lines = body[header_line_end:header_line_end + 800]
        assert any(
            marker in next_lines for marker in _HISTORICAL_MARKERS
        ), f"header {header!r} must be followed by a historical marker"


def test_blueprint_report_contract_has_hard_wall_reminder() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")

    idx = body.find("## 9. Report contract")
    assert idx != -1
    end = body.find("## 10.", idx)
    assert end != -1
    section = body[idx:end]

    assert "Hard-wall reminder" in section
    assert "ADR-22" in section
    assert "ADR-24" in section
    assert "Literal[False]" in section
    assert "not emitted" in section
    assert "AuditReport" in section
    assert "src/oida_code/models/audit_report.py" in section


def test_blueprint_no_unframed_active_product_verdict_claims() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")

    for phrase in _FORBIDDEN_ACTIVE_CLAIMS:
        assert phrase not in body, phrase


def test_blueprint_preserves_historical_oida_vocabulary() -> None:
    body = _BLUEPRINT_MD.read_text(encoding="utf-8")

    for token in (
        "v_net",
        "debt",
        "grounding",
        "double_loop_repair",
        "Q_obs",
    ):
        assert token in body, (
            f"blueprint must preserve historical OIDA vocabulary "
            f"token {token!r} (don't delete content, only quarantine)"
        )


def test_phase6i_report_records_scope_flags() -> None:
    report = json.loads(_REPORT_JSON.read_text(encoding="utf-8"))

    assert report["root_blueprint_historicized"] is True
    assert report["runtime_changed"] is False
    assert report["json_schema_changed"] is False
    assert report["sarif_schema_changed"] is False
    assert report["action_yml_changed"] is False
    assert report["workflow_changed"] is False
    assert report["source_code_changed"] is False
    assert report["clone_helper_changed"] is False
    assert report["corpus_index_changed"] is False
    assert report["provider_call_used"] is False
    assert report["direct_provider_call"] is False
    assert report["runtime_gateway_default_changed"] is False
    assert report["mcp_runtime_changed"] is False
    assert report["plan_md_changed"] is False
