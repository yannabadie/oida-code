"""Phase 5.1-D (QA/A28.md, ADR-36) — tool gateway audit log.

Append-only JSONL writer for
:class:`ToolGatewayAuditEvent`. Storage layout:

    .oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl

One line per Stage-2 decision: allow / block / quarantine /
reject all produce events. The audit file is opened with
``mode="a"``; existing entries are NEVER mutated.

Redaction rules: the writer NEVER emits the API key, the
GITHUB_TOKEN, the raw prompt, the raw provider response, or
the raw tool stdout. Audit events carry only the
``request_summary`` (short, human-readable, redacted upstream
by the caller) and the ``evidence_refs`` IDs that point at
the aggregator's evidence records.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from oida_code.verifier.tool_gateway.contracts import (
    PolicyDecision,
    RequestedBy,
    ToolGatewayAuditEvent,
    ToolSchemaFingerprint,
)


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with the trailing ``Z`` suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_today_dir() -> str:
    """Directory name for today's audit folder
    (``YYYY-MM-DD`` per QA/A28 line 274)."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _new_event_id() -> str:
    """Random 16-byte token. Not a ULID/UUIDv7 (would add a
    dependency); good enough for forensic linkage within a
    single audit cycle."""
    return secrets.token_hex(16)


def build_audit_event(
    *,
    tool_id: str,
    tool_name: str,
    fingerprint: ToolSchemaFingerprint,
    requested_by: RequestedBy,
    request_summary: str,
    allowed: bool,
    policy_decision: PolicyDecision,
    reason: str,
    case_id: str | None = None,
    evidence_refs: Iterable[str] = (),
    secret_access_attempted: bool = False,
    network_access_attempted: bool = False,
    write_access_attempted: bool = False,
) -> ToolGatewayAuditEvent:
    """Construct a :class:`ToolGatewayAuditEvent` with a fresh
    ``event_id`` and current UTC timestamp. The fingerprint's
    ``combined_sha256`` is what gets recorded in
    ``tool_schema_hash`` — the single field a forensic operator
    cross-references against the approved registry."""
    return ToolGatewayAuditEvent(
        event_id=_new_event_id(),
        timestamp=_utc_now_iso(),
        tool_id=tool_id,
        tool_name=tool_name,
        tool_schema_hash=fingerprint.combined_sha256,
        requested_by=requested_by,
        case_id=case_id,
        request_summary=request_summary,
        allowed=allowed,
        policy_decision=policy_decision,
        reason=reason,
        evidence_refs=tuple(evidence_refs),
        secret_access_attempted=secret_access_attempted,
        network_access_attempted=network_access_attempted,
        write_access_attempted=write_access_attempted,
    )


def audit_log_path(audit_log_dir: Path, tool_name: str) -> Path:
    """Return the JSONL file path for ``tool_name`` under
    ``audit_log_dir``: ``<dir>/<yyyy-mm-dd>/<tool_name>.jsonl``."""
    today = _utc_today_dir()
    return audit_log_dir / today / f"{tool_name}.jsonl"


def append_audit_event(
    event: ToolGatewayAuditEvent,
    audit_log_dir: Path,
) -> Path:
    """Append ``event`` to the per-day per-tool JSONL file.
    Creates parent directories as needed. Returns the path
    written to.

    The file is opened with ``mode="a"`` so existing entries
    are preserved. Each line is a complete JSON object
    terminated by ``\\n``.
    """
    out_path = audit_log_path(audit_log_dir, event.tool_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(event.model_dump_json())
        fh.write("\n")
    return out_path


def read_audit_events(
    audit_log_dir: Path,
    tool_name: str,
    *,
    date: str | None = None,
) -> list[ToolGatewayAuditEvent]:
    """Read every audit event for ``tool_name`` from the
    per-day file. ``date`` defaults to today's UTC date. Returns
    a list of parsed events; lines that fail to parse are
    silently skipped (the audit log is presentation, not
    validation — corruption surfaces via re-run)."""
    if date is None:
        date = _utc_today_dir()
    path = audit_log_dir / date / f"{tool_name}.jsonl"
    if not path.is_file():
        return []
    out: list[ToolGatewayAuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(ToolGatewayAuditEvent.model_validate_json(line))
        except Exception:
            continue
    return out


__all__ = [
    "append_audit_event",
    "audit_log_path",
    "build_audit_event",
    "read_audit_events",
]
