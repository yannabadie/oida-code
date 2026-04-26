"""Phase 5.6 §5.6-E — gateway-status enum.

The composite GitHub Action emits a ``gateway-status``
output that takes one of EXACTLY five values:

* ``disabled`` — ``enable-tool-gateway`` was false (default
  path).
* ``diagnostic_only`` — gateway ran; no contract violations
  detected; findings are diagnostic only (this is the
  expected value when the bundle is well-formed and the
  gateway produces a normal report).
* ``contract_clean`` — contract checks passed (used when the
  caller wants an explicit "contracts held" signal; in
  Phase 5.6 the action usually returns ``diagnostic_only``).
* ``contract_failed`` — at least one contract violation
  surfaced (e.g. official-field leak count > 0; bundle
  validation failed; PR-context guard tripped).
* ``blocked`` — the gateway path was requested but blocked
  before execution (PR/fork guard, bundle validator
  rejection).

The vocabulary is a :class:`Literal[...]` — the forbidden
product verdicts (``merge_safe`` / ``verified`` /
``production_safe`` / ``bug_free``) are STRUCTURALLY
unrepresentable: the ``derive_gateway_status`` function
returns a ``GatewayStatus``, which the type checker pins
to the five-value Literal.
"""

from __future__ import annotations

from typing import Literal

GatewayStatus = Literal[
    "disabled",
    "diagnostic_only",
    "contract_clean",
    "contract_failed",
    "blocked",
]
"""Five-value enum of gateway-status outputs."""


GATEWAY_STATUS_VALUES: tuple[GatewayStatus, ...] = (
    "disabled",
    "diagnostic_only",
    "contract_clean",
    "contract_failed",
    "blocked",
)


# Forbidden product-verdict tokens that must NEVER appear
# anywhere in the gateway action surface (status enum,
# step summary, action outputs, audit logs).
FORBIDDEN_VERDICT_TOKENS: tuple[str, ...] = (
    "merge_safe",
    "merge-safe",
    "production_safe",
    "production-safe",
    "verified",
    "bug_free",
    "bug-free",
    "security_verified",
    "security-verified",
    "official_v_net",
    "total_v_net",
    "debt_final",
    "corrupt_success",
)


def derive_gateway_status(
    *,
    enabled: bool,
    blocked_pre_execution: bool,
    bundle_valid: bool,
    official_field_leak_count: int,
) -> GatewayStatus:
    """Map a tuple of (enabled, blocked, bundle_valid,
    leak_count) inputs to the canonical Literal status.

    The function does NOT consume the gateway report's
    findings/blockers — those are diagnostic only and never
    promote a contract failure on their own. Contract
    failure is reserved for:

    * ``official_field_leak_count > 0`` — ADR-22 hard-wall
      breach.
    * ``not bundle_valid`` — the operator-supplied bundle
      did not pass :func:`validate_gateway_bundle`.

    PR/fork guard tripping → ``blocked``. Default disabled
    path → ``disabled``. Otherwise the gateway runs and the
    status is ``diagnostic_only``.
    """
    if not enabled:
        return "disabled"
    if blocked_pre_execution:
        return "blocked"
    if official_field_leak_count > 0:
        return "contract_failed"
    if not bundle_valid:
        return "contract_failed"
    return "diagnostic_only"


__all__ = [
    "FORBIDDEN_VERDICT_TOKENS",
    "GATEWAY_STATUS_VALUES",
    "GatewayStatus",
    "derive_gateway_status",
]
