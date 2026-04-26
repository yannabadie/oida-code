"""Phase 5.1 (QA/A28.md, ADR-36) — local deterministic tool gateway.

Wraps OIDA-code's existing tool adapters
(``src/oida_code/verifier/tools/``) behind an admission +
fingerprinting + audit-log layer. NOT MCP. NOT a JSON-RPC
server. The gateway speaks Python objects (Pydantic models)
and reuses the existing ``ToolPolicy`` / ``validate_request`` /
adapter machinery unchanged.
"""

from oida_code.verifier.tool_gateway.contracts import (
    AdmissionStatus,
    GatewayRiskLevel,
    GatewayToolDefinition,
    PolicyDecision,
    RequestedBy,
    ToolAdmissionDecision,
    ToolAdmissionRegistry,
    ToolGatewayAuditEvent,
    ToolSchemaFingerprint,
)

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
