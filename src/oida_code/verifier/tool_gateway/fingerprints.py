"""Phase 5.1-B (QA/A28.md, ADR-36) — tool schema fingerprinting.

Computes deterministic SHA256 hashes over a
:class:`GatewayToolDefinition` so the gateway can detect
post-approval drift (the rug-pull vector from the Phase 5.0
threat model).

The canonical-JSON serialiser used here is a **JCS approximation**
(sorted keys + minimal separators + UTF-8 + ``ensure_ascii=False``).
It is sufficient for the local-adapter use-case because the
inputs are author-controlled Python dicts that already pass
Pydantic validation. A future MCP integration that consumes
third-party schemas SHOULD swap to strict JCS (RFC 8785) — see
`docs/security/tool_schema_pinning.md` §3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolSchemaFingerprint,
)


def _canonical_dumps(value: Any) -> str:
    """JCS-approximation: sorted keys, no insignificant
    whitespace, UTF-8, ``ensure_ascii=False`` so Unicode strings
    survive the round-trip without ``\\uXXXX`` escapes.

    This is NOT strict RFC 8785 JCS. The corner cases JCS
    handles that this approximation does not:

    * Number canonical form (IEEE 754 shortest round-trip).
    * Unicode normalisation (NFC).
    * ``\\uD800`` surrogate handling.

    For local adapters (Phase 5.1 scope) the inputs are bounded
    (the tool definitions live in vendored Python code), so the
    corner cases do not apply. A future MCP integration must
    upgrade to strict JCS before relying on this hashing layer.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_json_sha256(value: Mapping[str, Any] | str) -> str:
    """Return the lowercase-hex SHA256 of ``value`` after
    canonical-JSON serialisation (for mappings) or after UTF-8
    encoding (for plain strings — used for the ``description``
    field which is not a JSON object)."""
    payload = (
        value if isinstance(value, str) else _canonical_dumps(dict(value))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_tool_definition(
    definition: GatewayToolDefinition,
) -> ToolSchemaFingerprint:
    """Compute the four SHA256 fingerprints from the
    ``description`` / ``input_schema`` / ``output_schema``
    fields of ``definition``.

    The ``combined_sha256`` is the SHA256 of the three
    individual hex digests concatenated in a canonical order
    (description → input → output). It serves as a single
    field a downstream consumer can compare without unpacking
    the triplet.
    """
    description_sha = canonical_json_sha256(definition.description)
    input_sha = canonical_json_sha256(definition.input_schema)
    output_sha = canonical_json_sha256(definition.output_schema)
    combined_input = (
        f"description:{description_sha}|"
        f"input:{input_sha}|"
        f"output:{output_sha}"
    )
    combined_sha = hashlib.sha256(
        combined_input.encode("utf-8"),
    ).hexdigest()
    return ToolSchemaFingerprint(
        tool_id=definition.tool_id,
        tool_name=definition.tool_name,
        adapter_version=definition.adapter_version,
        description_sha256=description_sha,
        input_schema_sha256=input_sha,
        output_schema_sha256=output_sha,
        combined_sha256=combined_sha,
    )


def compare_fingerprints(
    expected: ToolSchemaFingerprint,
    observed: ToolSchemaFingerprint,
) -> Literal["match", "drift"]:
    """Return ``"match"`` iff every hash in the triplet AND
    ``combined_sha256`` matches between ``expected`` and
    ``observed``. A divergence on ANY of the four → ``"drift"``,
    which the admission layer translates to ``quarantined``.

    The ``tool_id`` is also checked: a fingerprint computed for
    a different tool cannot match an expected fingerprint, even
    if every hash happens to align.
    """
    if expected.tool_id != observed.tool_id:
        return "drift"
    if expected.description_sha256 != observed.description_sha256:
        return "drift"
    if expected.input_schema_sha256 != observed.input_schema_sha256:
        return "drift"
    if expected.output_schema_sha256 != observed.output_schema_sha256:
        return "drift"
    if expected.combined_sha256 != observed.combined_sha256:
        return "drift"
    return "match"


__all__ = [
    "canonical_json_sha256",
    "compare_fingerprints",
    "fingerprint_tool_definition",
]
