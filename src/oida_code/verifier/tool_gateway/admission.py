"""Phase 5.1-C (QA/A28.md, ADR-36) — admission policy runtime.

Decides ``approved_read_only`` / ``quarantined`` / ``rejected``
for a candidate :class:`GatewayToolDefinition` against a
locally-stored ``expected_fingerprint``.

Rule order (matches QA/A28 §5.1-C lines 222-228 verbatim):

1. ``expected_fingerprint is None`` → ``quarantined``
2. fingerprint match → ``approved_read_only``
3. fingerprint drift → ``quarantined``
4. ``risk_level != "read_only"`` → ``rejected``
5. ``requires_network=True`` → ``rejected``  *(unreachable;
   pinned ``Literal[False]`` at the schema level — kept here
   defensively)*
6. ``allows_write=True`` → ``rejected``  *(same)*
7. suspicious description → ``rejected`` (or ``quarantined``
   for borderline cases — see ``_SUSPICIOUS_PATTERNS``)
"""

from __future__ import annotations

import re

from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolAdmissionDecision,
    ToolSchemaFingerprint,
)
from oida_code.verifier.tool_gateway.fingerprints import (
    compare_fingerprints,
    fingerprint_tool_definition,
)

# Patterns that, when present in a tool description, indicate
# the tool is trying to subvert host-side policy (or its
# upstream documentation has been poisoned). Each match → reject.
# The regex is case-insensitive; we match anywhere in the
# description.
_SUSPICIOUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(the\s+)?(previous|above|system|developer)\s+"
        r"(instruction|policy|prompt|rule)",
        re.IGNORECASE,
    ),
    re.compile(r"override\s+policy", re.IGNORECASE),
    re.compile(r"send\s+secrets", re.IGNORECASE),
    re.compile(r"\bexfiltrate\b", re.IGNORECASE),
    re.compile(r"execute\s+shell", re.IGNORECASE),
    re.compile(
        # "write file" only when surrounded by space-or-anchors,
        # so it doesn't match e.g. "rewrite filename".
        r"(^|\s)write\s+file(\s|$|\.|,)",
        re.IGNORECASE,
    ),
    re.compile(
        # Inner copies of the OIDA evidence fence — would
        # truncate the context if the description ever lands
        # in the LLM's prompt.
        r"<<<(OIDA_EVIDENCE|END_OIDA_EVIDENCE)",
    ),
)


def _detect_suspicious(description: str) -> str | None:
    """Return the matched pattern (rendered as a short string)
    when ``description`` contains one of the suspicious
    patterns; ``None`` otherwise. The returned string is used
    as the rejection reason."""
    for pattern in _SUSPICIOUS_PATTERNS:
        match = pattern.search(description)
        if match is not None:
            return f"suspicious description matched {pattern.pattern!r}"
    return None


def admit_tool_definition(
    definition: GatewayToolDefinition,
    *,
    expected_fingerprint: ToolSchemaFingerprint | None,
) -> ToolAdmissionDecision:
    """Decide whether ``definition`` may be invoked.

    The seven rules from QA/A28.md §5.1-C run in declared order;
    the first rule that triggers wins. The Pydantic-level
    Literal pins on ``requires_network`` and ``allows_write``
    make rules 5 and 6 unreachable in practice (any attempt to
    construct a definition with either flag set to ``True``
    fails at validation time), but the rules are kept here so
    a future schema bump that loosens the pins still has a
    backstop.

    Returns the :class:`ToolAdmissionDecision`. The caller
    indexes the decision into a :class:`ToolAdmissionRegistry`.
    """
    observed = fingerprint_tool_definition(definition)

    # Rule 7 (suspicious description) takes precedence over rule
    # 1 — a tool with a malicious description must be rejected
    # outright, not "quarantined pending operator approval".
    suspicion = _detect_suspicious(definition.description)
    if suspicion is not None:
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="rejected",
            reason=suspicion,
            fingerprint=observed,
        )

    # Rule 4 — risk_level is the second-most-discriminating field.
    if definition.risk_level != "read_only":
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="rejected",
            reason=(
                f"risk_level {definition.risk_level!r} not "
                "approved in Phase 5.1 (only `read_only` is)"
            ),
            fingerprint=observed,
        )

    # Rules 5 + 6 (defensive — Literal[False] pin should make
    # these unreachable, but keep the rules so a future
    # un-pinning still has a backstop).
    if bool(definition.requires_network):
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="rejected",
            reason="requires_network=True forbidden in Phase 5.1",
            fingerprint=observed,
        )
    if bool(definition.allows_write):
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="rejected",
            reason="allows_write=True forbidden in Phase 5.1",
            fingerprint=observed,
        )

    # Rule 1 — no expected fingerprint = no prior approval.
    if expected_fingerprint is None:
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="quarantined",
            reason=(
                "no expected fingerprint — operator approval "
                "required before this tool can be invoked"
            ),
            fingerprint=observed,
        )

    # Rules 2 + 3 — fingerprint match wins; drift quarantines.
    comparison = compare_fingerprints(expected_fingerprint, observed)
    if comparison == "match":
        return ToolAdmissionDecision(
            tool_id=definition.tool_id,
            status="approved_read_only",
            reason="fingerprint match against expected approval",
            fingerprint=observed,
        )
    return ToolAdmissionDecision(
        tool_id=definition.tool_id,
        status="quarantined",
        reason=(
            "fingerprint drift — observed hashes do not match "
            "the approved fingerprint; operator review required"
        ),
        fingerprint=observed,
    )


__all__ = [
    "admit_tool_definition",
]
