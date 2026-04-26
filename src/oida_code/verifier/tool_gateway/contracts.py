"""Phase 5.1-A (QA/A28.md, ADR-36) — local deterministic tool
gateway contracts.

Frozen Pydantic shapes for the runtime tool-gateway. This is the
**runtime** counterpart to the Phase 5.0 design documents under
``docs/security/`` (`tool_schema_pinning.md`,
`mcp_audit_log_schema.md`, `mcp_admission_policy.md`). Same
*concepts* (admission, fingerprinting, audit log) but applied
to the LOCAL tool adapters that already ship in
``src/oida_code/verifier/tools/`` — NOT to MCP.

Note for future readers: there are two ``ToolSchemaFingerprint``
schemas in this repo. The one in this module is the runtime
shape for local adapters (with ``combined_sha256``). The one
in ``docs/security/tool_schema_pinning.md`` is the
*design-only* shape for hypothetical MCP servers (extended
with ``server_id`` / ``server_origin`` / OAuth scopes). They
share intent but diverge in fields because their inputs
differ. Phase 5.1 ships only the runtime variant.

ADR-36 hard rules captured here:

* ``GatewayToolDefinition.requires_network`` and
  ``allows_write`` are pinned to ``Literal[False]`` — Pydantic
  rejects any attempt to construct a definition with either
  set to ``True``.
* ``ToolAdmissionDecision.status`` Literal excludes any
  ``approved_*`` value beyond ``approved_read_only``. Mode 3
  (deterministic) and mode 4 (write) tier upgrades require a
  schema bump and a new ADR.
* ``ToolGatewayAuditEvent.policy_decision`` is a 4-value
  Literal mirroring the Phase 5.0 design
  (``allow`` / ``block`` / ``quarantine`` / ``reject``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.verifier.tools.contracts import ToolName

# ---------------------------------------------------------------------------
# Tool definition (the static identity of a tool, before approval)
# ---------------------------------------------------------------------------

GatewayRiskLevel = Literal[
    "read_only",
    "sensitive_read",  # not yet authorized; reserved for Phase 5.x
    "write_forbidden",  # explicit "this tool is destructive — reject it"
]
"""Phase 5.1 only authorises ``read_only``. The other values
exist so an admission decision can carry a clear reason on
rejection without inventing strings ad-hoc."""


class GatewayToolDefinition(BaseModel):
    """Static description of one tool the gateway might admit.

    ``input_schema`` and ``output_schema`` are JSON Schema-shaped
    dicts (we use ``dict[str, Any]`` rather than a typed schema
    model because the adapters that consume these are
    deterministic and self-documenting; the schema is a
    machine-readable artifact for fingerprinting, not a
    validation contract for the adapter itself).

    The two ``Literal[False]`` pins (``requires_network``,
    ``allows_write``) are the structural floor: a definition
    that wants either capability cannot be constructed.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool_id: str = Field(min_length=1)
    tool_name: ToolName
    adapter_version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: GatewayRiskLevel
    allowed_scopes: tuple[str, ...] = Field(default_factory=tuple)
    requires_network: Literal[False] = False
    allows_write: Literal[False] = False


# ---------------------------------------------------------------------------
# Schema fingerprint (the dynamic identity, computed from the definition)
# ---------------------------------------------------------------------------


class ToolSchemaFingerprint(BaseModel):
    """SHA256 fingerprints of ``description`` / ``input_schema``
    / ``output_schema``, plus a ``combined_sha256`` over all
    three. Any drift on any field's hash → quarantine the
    tool (cf. ``compare_fingerprints``).

    All four hashes are 64-char lowercase hex.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    description_sha256: str = Field(min_length=64, max_length=64)
    input_schema_sha256: str = Field(min_length=64, max_length=64)
    output_schema_sha256: str = Field(min_length=64, max_length=64)
    combined_sha256: str = Field(min_length=64, max_length=64)


# ---------------------------------------------------------------------------
# Admission decision + registry
# ---------------------------------------------------------------------------

AdmissionStatus = Literal[
    "approved_read_only",
    "quarantined",
    "rejected",
]
"""Phase 5.1 supports only one tier — ``approved_read_only``.
Mode 3 (deterministic with side-effects) and mode 4 (write)
require an ADR-37+ unlock and are NOT in this Literal."""


class ToolAdmissionDecision(BaseModel):
    """One admission outcome for a (tool, fingerprint) pair.

    The gateway never invokes a tool whose decision is not
    ``approved_read_only``. Quarantined tools require operator
    re-approval (new fingerprint); rejected tools cannot be
    re-proposed under the same ``tool_id`` within the same
    approval cycle.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    tool_id: str = Field(min_length=1)
    status: AdmissionStatus
    reason: str = Field(min_length=1)
    fingerprint: ToolSchemaFingerprint
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class ToolAdmissionRegistry(BaseModel):
    """The set of decisions the gateway loads at startup. Three
    parallel tuples keep the JSON file human-readable: an
    operator can grep ``approved`` to see what's callable,
    ``quarantined`` for the V4 Pro 6/8-style follow-ups, and
    ``rejected`` for the auto-rejects."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    approved: tuple[ToolAdmissionDecision, ...] = Field(default_factory=tuple)
    quarantined: tuple[ToolAdmissionDecision, ...] = Field(default_factory=tuple)
    rejected: tuple[ToolAdmissionDecision, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Audit event (one per Stage-2 decision)
# ---------------------------------------------------------------------------

PolicyDecision = Literal[
    "allow",       # Stage 2 passed; tool was invoked
    "block",       # Stage 2 rejected (policy / schema)
    "quarantine",  # Hash drift; tool not invoked
    "reject",      # Definition itself rejected (write / network / etc.)
]


RequestedBy = Literal[
    "workflow",  # Internal trigger (CI / scheduled run)
    "operator",  # Human-issued via CLI
    "verifier",  # The verifier-aggregator loop requested this tool
]


class ToolGatewayAuditEvent(BaseModel):
    """One audit entry per Stage-2 decision. Written as JSONL
    under ``.oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl``.

    ``request_summary`` is a short human-readable string —
    NEVER the full arguments, NEVER a credential, NEVER raw
    repo content. The full evidence (when the tool ran) is
    referenced via ``evidence_refs`` IDs against the
    aggregator's record.

    The three capability sentinel flags
    (``secret_access_attempted`` / ``network_access_attempted``
    / ``write_access_attempted``) default to ``False``. They
    are set to ``True`` only when a future runtime sandbox
    primitive detects the attempt; their meaning depends on
    actually being able to detect the attempt (Phase 5.x sandbox
    selection, cf. ``mcp_threat_model.md`` open question 6).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    event_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)  # ISO-8601 UTC w/ "Z"
    tool_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_schema_hash: str = Field(min_length=64, max_length=64)
    requested_by: RequestedBy
    case_id: str | None = None
    request_summary: str = Field(min_length=1)
    allowed: bool
    policy_decision: PolicyDecision
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    secret_access_attempted: bool = False
    network_access_attempted: bool = False
    write_access_attempted: bool = False


__all__ = [
    "AdmissionStatus",
    "GatewayRiskLevel",
    "GatewayToolDefinition",
    "PolicyDecision",
    "RequestedBy",
    "ToolAdmissionDecision",
    "ToolAdmissionRegistry",
    "ToolGatewayAuditEvent",
    "ToolSchemaFingerprint",
]
