"""Phase 6.h root historical PLAN.md diagnostic quarantine guards."""

from __future__ import annotations

import json
import re

from tests.conftest import REPO_ROOT

_PLAN_MD = REPO_ROOT / "PLAN.md"
_REPORT_JSON = (
    REPO_ROOT
    / "reports"
    / "phase6_h_root_historical_plan_quarantine"
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


def _is_historical_line(line: str) -> bool:
    return any(marker in line for marker in _HISTORICAL_MARKERS)


def _context_around(
    lines: list[str], idx: int, window: int = 30
) -> str:
    """Return ``±window`` lines around ``idx``.

    Used to widen the historical-marker check so a phrase living
    inside a markdown table inherits the historical block-quote
    that immediately precedes the section header.
    """

    start = max(0, idx - window)
    end = min(len(lines), idx + window + 1)
    return "\n".join(lines[start:end])


def _compact(text: str) -> str:
    return re.sub(r"\s+(?:>\s+)?", " ", text)


def test_plan_md_starts_with_archival_banner() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")
    head = "\n".join(body.splitlines()[:60])
    head_compact = _compact(head)

    assert "ARCHIVAL" in head
    assert "READ THIS FIRST" in head
    assert "Phase 6.h" in head
    assert "ADR-80" in head
    assert "Do not quote sentences from this file" in head_compact
    assert "docs/product_strategy.md" in head
    assert "docs/project_status.md" in head


def test_plan_md_archival_banner_lists_blocked_fields() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")
    head = "\n".join(body.splitlines()[:60])

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


def test_plan_md_proved_enough_to_merge_only_in_obsolete_context() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")
    lines = body.splitlines()

    for idx, line in enumerate(lines):
        if "Proved enough to merge" in line:
            context = _context_around(lines, idx)
            assert any(
                marker in context for marker in _HISTORICAL_MARKERS
            ), (
                f"PLAN.md:{idx + 1} mentions 'Proved enough to merge' "
                f"without a historical/obsolete marker within +/-30 "
                f"surrounding lines: {line!r}"
            )


def test_plan_md_section_headers_are_marked_historical() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")

    expected_historical_headers = (
        "## 6. Verdict taxonomy",
        "## 7. OIDA scoring core",
        "## 11. CLI contract",
        "## 12. Report contract",
        "## 14. Phased roadmap",
        "## 15. Honesty rules",
        "## 16. Wedge",
    )
    for header in expected_historical_headers:
        idx = body.find(header)
        assert idx != -1, f"missing header {header!r}"
        header_line_end = body.find("\n", idx)
        next_lines = body[header_line_end:header_line_end + 600]
        assert any(
            marker in next_lines for marker in _HISTORICAL_MARKERS
        ), f"header {header!r} must be followed by a historical marker"


def test_plan_md_section_3_pipeline_has_historical_marker() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")

    idx = body.find("## 3. Pipeline architecture")
    assert idx != -1
    next_lines = body[idx:idx + 800]

    assert "Verdict resolver" in next_lines
    assert any(marker in next_lines for marker in _HISTORICAL_MARKERS)


def test_plan_md_report_contract_has_hard_wall_reminder() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")

    idx = body.find("## 12. Report contract")
    assert idx != -1
    next_lines = body[idx:idx + 3000]

    assert "Hard-wall reminder" in next_lines
    assert "ADR-22" in next_lines
    assert "ADR-24" in next_lines
    assert "Literal[False]" in next_lines
    assert "not emitted" in next_lines


def test_plan_md_active_authority_pointer_preserved() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")

    assert "# OIDA Code Audit" in body
    assert "Historical Plan" in body
    assert "no longer the active source of truth" in body
    assert "docs/product_strategy.md" in body
    assert "docs/project_status.md" in body
    assert "Older statements in this file about GitHub App" in body
    assert "wins on conflicts" not in body


def test_plan_md_no_unframed_active_product_verdict_claims() -> None:
    body = _PLAN_MD.read_text(encoding="utf-8")
    lines = body.splitlines()

    for phrase in _FORBIDDEN_ACTIVE_CLAIMS:
        assert phrase not in body, phrase

    for idx, line in enumerate(lines):
        if re.search(r"\buseful verdict\b", line):
            context = _context_around(lines, idx)
            assert any(
                marker in context for marker in _HISTORICAL_MARKERS
            ), (
                f"PLAN.md:{idx + 1} mentions 'useful verdict' "
                f"without a historical marker within +/-30 "
                f"surrounding lines: {line!r}"
            )


def test_phase6h_report_records_scope_flags() -> None:
    report = json.loads(_REPORT_JSON.read_text(encoding="utf-8"))

    assert report["plan_historicized"] is True
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
