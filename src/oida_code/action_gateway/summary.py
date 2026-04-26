"""Phase 5.6 §5.6-D — gateway step-summary renderer.

When the composite GitHub Action runs with
``enable-tool-gateway: "true"``, this module renders the
``summary.md`` artifact and the section appended to
``$GITHUB_STEP_SUMMARY``. The renderer:

1. Builds a small Markdown table from the gateway report
   (enabled / mode / official-fields-blocked / tool-call
   count / accepted / unsupported / rejected counts /
   audit-log path).
2. Scans the rendered text for forbidden product-verdict
   tokens (``merge_safe`` / ``production_safe`` / ``bug_free``
   / ``verified`` / ``official_v_net`` / ``total_v_net`` /
   ``debt_final`` / ``corrupt_success``) and raises if any
   surfaces. The Phase 4.7+ pattern is "schema pin AND
   runtime scan" — the schema rejects the strings at
   construction time, but the rendered text is plain-string
   Markdown, so a runtime scan is the second layer.
"""

from __future__ import annotations

from typing import Any

from oida_code.action_gateway.status import (
    FORBIDDEN_VERDICT_TOKENS,
    GatewayStatus,
)


class ForbiddenSummaryPhraseError(RuntimeError):
    """Raised when the rendered summary contains a forbidden
    product-verdict token. The Phase 5.6 contract is that
    the gateway section is diagnostic-only; promoting a
    finding to merge-safe / verified / etc. would breach
    ADR-22."""


def _scan_for_forbidden_phrases(rendered: str) -> None:
    lowered = rendered.lower()
    for token in FORBIDDEN_VERDICT_TOKENS:
        if token in lowered:
            raise ForbiddenSummaryPhraseError(
                f"forbidden product-verdict token {token!r} "
                "appeared in rendered gateway summary"
            )


def render_gateway_summary(
    *,
    enabled: bool,
    status: GatewayStatus,
    grounded_report: dict[str, Any] | None,
    audit_log_dir: str,
    bundle_dir: str = "",
) -> str:
    """Return the Markdown step-summary section for the
    gateway-grounded run. The output is plain-text Markdown
    suitable for both ``$GITHUB_STEP_SUMMARY`` and a
    standalone ``summary.md`` artifact.

    ``grounded_report`` is the parsed JSON of the
    ``GatewayGroundedVerifierRun`` written by
    :func:`oida_code.cli.verify_grounded_cmd`. It can be
    ``None`` when the gateway path was disabled or blocked
    pre-execution; in that case the renderer emits a
    short stub explaining the absence."""

    lines: list[str] = ["## Gateway-grounded verifier"]
    lines.append("")
    if not enabled:
        lines.extend([
            "_Gateway path disabled (`enable-tool-gateway: false`)._",
            "",
            "| Item | Status |",
            "|---|---|",
            "| Enabled | false |",
            "| Mode | replay-only |",
            "| Official fields | blocked/null |",
        ])
        rendered = "\n".join(lines) + "\n"
        _scan_for_forbidden_phrases(rendered)
        return rendered

    if grounded_report is None:
        lines.extend([
            (
                "_Gateway path was enabled but blocked before "
                "execution (PR/fork guard or bundle "
                "validation rejection)._"
            ),
            "",
            "| Item | Status |",
            "|---|---|",
            "| Enabled | true |",
            "| Mode | replay-only |",
            "| Official fields | blocked/null |",
            f"| Status | {status} |",
            "| Tool calls | 0 |",
            "| Audit log | (not produced; gateway blocked) |",
        ])
        rendered = "\n".join(lines) + "\n"
        _scan_for_forbidden_phrases(rendered)
        return rendered

    report = grounded_report.get("report") or {}
    accepted = len(report.get("accepted_claims", ()))
    unsupported = len(report.get("unsupported_claims", ()))
    rejected = len(report.get("rejected_claims", ()))
    tool_results = grounded_report.get("tool_results") or ()
    blocked_tools = sum(
        1 for r in tool_results
        if isinstance(r, dict) and r.get("status") == "blocked"
    )
    bundle_label = bundle_dir or "(unset)"

    lines.extend([
        "_Diagnostic only — see ADR-41. No product verdict._",
        "",
        "| Item | Status |",
        "|---|---|",
        "| Enabled | true |",
        "| Mode | replay-only |",
        "| Official fields | blocked/null |",
        f"| Status | {status} |",
        f"| Tool calls | {len(tool_results)} |",
        f"| Blocked tools | {blocked_tools} |",
        f"| Accepted claims | {accepted} |",
        f"| Unsupported claims | {unsupported} |",
        f"| Rejected claims | {rejected} |",
        f"| Bundle | {bundle_label} |",
        f"| Audit log | {audit_log_dir} |",
        "",
        (
            "Phase 5.6 (ADR-41) keeps the gateway path replay-"
            "only. No external provider, no MCP, no write or "
            "network tools. The official OIDA fusion fields "
            "remain null (ADR-22 hard wall)."
        ),
    ])
    rendered = "\n".join(lines) + "\n"
    _scan_for_forbidden_phrases(rendered)
    return rendered


__all__ = [
    "ForbiddenSummaryPhraseError",
    "render_gateway_summary",
]
