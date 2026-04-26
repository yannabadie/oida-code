# Tool schema pinning & rug-pull detection — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-C.
**Status**: design only. No pinning code is implemented in
Phase 5.0; this document specifies the contract a future Phase
5.1+ implementation must satisfy.

## 1. Goal

Prevent a server that was approved today from silently changing
its tool definitions tomorrow. The MCP spec allows servers to
push `tools/list_changed` notifications and to update tool
descriptions / schemas on the fly. Without cryptographic pinning
of the approved fingerprint, an attacker (or a benign upstream
update) can rug-pull a tool's behaviour after approval.

OWASP MCP Top 10 explicitly lists this as **MCP03 tool
poisoning**: "Tool definitions / descriptions are loaded
dynamically and can be altered post-approval by a compromised
or malicious server. Treat the entirety of a tool's schema as
prompt-injection surface; pin definitions by cryptographic
hash, alert on changes."

## 2. Schema fingerprint

The unit of pinning is the per-tool **fingerprint**, not the
whole server's tool list. Each tool gets its own fingerprint
so a server that updates one tool does not invalidate the
others.

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ServerOrigin = Literal["local_stdio", "local_http", "remote_http"]
RiskLevel = Literal[
    "schema_discovery",  # mode 1 — server is queryable, tools not callable
    "read_only",         # mode 2 — read-only deterministic tools
    "deterministic",     # mode 3 — approved deterministic tools (Phase 5.x)
    "human_approved_write",  # mode 4 — write tools, per-call human approval
]


class ToolSchemaFingerprint(BaseModel):
    """One fingerprint per (server_id, server_version, tool_name).
    All three SHA256 fields are 64-char lowercase hex; any drift
    triggers automatic quarantine of the parent server.
    """
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    server_id: str = Field(min_length=1)
    server_version: str = Field(min_length=1)
    server_origin: ServerOrigin
    tool_name: str = Field(min_length=1)

    description_sha256: str = Field(min_length=64, max_length=64)
    input_schema_sha256: str = Field(min_length=64, max_length=64)
    output_schema_sha256: str = Field(min_length=64, max_length=64)

    risk_level: RiskLevel
    allowed_scopes: tuple[str, ...] = Field(default_factory=tuple)

    approved_by: str = Field(min_length=1)   # operator identity
    approved_at: str = Field(min_length=1)   # ISO-8601 UTC w/ "Z"
```

The companion record at the server level binds the fingerprint
set:

```python
class ApprovedMCPServer(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )
    server_id: str = Field(min_length=1)
    server_version: str = Field(min_length=1)
    server_origin: ServerOrigin
    package_sha256: str = Field(min_length=64, max_length=64)  # binary / tarball
    package_provenance: str  # PyPI / npm URL + commit / tag
    fingerprints: tuple[ToolSchemaFingerprint, ...]
    approved_by: str = Field(min_length=1)
    approved_at: str = Field(min_length=1)
```

## 3. Canonicalisation

JSON Schema is not canonical: key order, whitespace, optional
fields, default values all create equally-valid representations
of the same schema. Hashing the raw bytes produces brittle
fingerprints (a trivial pretty-print breaks the hash).

**Phase 5.0 specification**: every schema/description is
canonicalised before hashing using **JCS (RFC 8785)**. The
operations performed before SHA256:

1. UTF-8 encode strings, NFC normalisation.
2. Object keys sorted lexicographically (UCS-2 order).
3. No insignificant whitespace.
4. Numbers in JCS canonical form (shortest IEEE 754 round-trip).
5. The `description` text is hashed AFTER trimming trailing
   whitespace per line and normalising newlines to `\n`.

This is the only normalisation. We deliberately do NOT
semantically rewrite the schema (e.g., "remove default values
for required fields") because that would mask intent changes.

## 4. Rug-pull detection rule

```
on every tools/list response:
    for each tool in response:
        compute (description_sha256, input_schema_sha256, output_schema_sha256)
        approved = lookup_fingerprint(server_id, tool_name)
        if approved is None:
            policy_decision = "block"
            reason = "tool not in approved fingerprint set"
            emit MCPAuditEvent(policy_decision, reason)
            continue
        if (description_sha256, input_schema_sha256, output_schema_sha256)
           != (approved.description_sha256, approved.input_schema_sha256,
               approved.output_schema_sha256):
            mark server quarantined
            policy_decision = "quarantine"
            reason = "schema hash drift detected"
            emit MCPAuditEvent(policy_decision, reason)
            HALT — no further calls to this server until operator re-approves
```

The rule is enforced **before** any `tools/call`. A drift
detected mid-session quarantines the server and refuses the
subsequent call. The host MUST NOT auto-recover.

## 5. Behaviour on each MCP notification

| Notification | Behaviour |
|---|---|
| `tools/list_changed` | Re-fetch `tools/list`, recompute every fingerprint, run §4 rule. ANY hash change → quarantine. |
| `resources/list_changed` | Resources are not pinned per-resource (their content is per-call); but the resource *manifest* is pinned and any drift quarantines. |
| `prompts/list_changed` | Server-supplied prompts are forbidden in Phase 5.0. The notification is logged but ignored. |

## 6. Storage layout (design)

A future Phase 5.1+ implementation stores the approved
fingerprint set at:

```
.oida/mcp/approved_servers.json    # ApprovedMCPServer[] — operator-signed
.oida/mcp/audit/<YYYY>/<MM>/<DD>/  # MCPAuditEvent JSONL files
```

**Phase 5.0 ships neither path.** The CLI subcommand
`oida-code mcp register / inspect / approve / revoke` is
design-pseudocode only; no Typer command is added in this
phase.

## 7. Hash domain rules

* `package_sha256` covers the WHOLE distribution artifact
  (the wheel / tarball / executable). For npm packages, this
  is the published tarball; for GitHub releases, the release
  asset; for vendored copies, the vendored tree's combined
  SHA256.
* `description_sha256` covers the canonicalised
  `description` string only. Trailing newlines stripped;
  internal whitespace preserved so semantically-distinct
  variants ("read file" vs "read       file") hash
  differently.
* `input_schema_sha256` covers the canonicalised JSON Schema
  object. `$schema` URI is preserved (its change matters);
  `examples` and `default` are preserved (their change
  matters).
* `output_schema_sha256` covers the canonicalised output
  schema when the server provides one. If no `outputSchema`
  is declared, the field is set to the SHA256 of the literal
  string `"<no-output-schema>"` so it stays a 64-char hex —
  this prevents a server from later ADDING an output schema
  silently.

## 8. Allowed-scopes pinning

`allowed_scopes` on `ToolSchemaFingerprint` enumerates the
authorisation scopes a tool is permitted to use. For local
read-only tools, this is typically `("repo:read",)`. The host
enforces:

1. The tool's runtime credentials are scoped to AT MOST
   `allowed_scopes` (the host issues no broader token).
2. If the server requests a scope outside `allowed_scopes`
   (e.g., via OAuth refresh), the host blocks the request
   AND quarantines the server.
3. A scope addition to an approved fingerprint requires a
   fresh approval cycle (new `approved_at`).

## 9. Failure modes

| Failure | Detection | Response |
|---|---|---|
| Tool name not in approved set | `tools/list` lookup miss | Block this tool's invocation; server stays approved (other tools OK) |
| Description hash drift | §4 rule | Quarantine entire server |
| Input schema hash drift | §4 rule | Quarantine entire server |
| Output schema hash drift | §4 rule | Quarantine entire server |
| Package hash drift on restart | `package_sha256` mismatch at process start | Refuse to start the subprocess; status → revoked (binary substitution) |
| Provenance URL changes | Operator-visible audit | Operator decides; not auto-quarantined (the URL change might be benign — e.g., mirror) |

## 10. Test invariants (Phase 5.0)

These tests are part of `tests/test_phase5_0_design.py` and lock
the design intent without executing pinning code:

* `test_mcp_threat_model_mentions_rug_pull` — this document
  AND `mcp_threat_model.md` mention "rug pull" / "rug-pull".
* `test_tool_schema_pinning_uses_sha256` — the doc names
  `description_sha256` / `input_schema_sha256` /
  `output_schema_sha256`.
* `test_tool_schema_pinning_canonicalises_via_jcs` — the doc
  references RFC 8785 / JCS.

The runtime invariant (no actual pinning code) is locked by
the existing `test_no_mcp_workflow_or_dependency_added` from
Phase 4.7.

## 11. Recommended Phase 5.1+ implementation order

Not part of Phase 5.0 acceptance, recorded here as the
follow-on path:

1. Implement `ToolSchemaFingerprint` + `ApprovedMCPServer`
   Pydantic models in a new `src/oida_code/mcp/schemas.py`
   (gated by an explicit ADR removing the anti-MCP locks).
2. Implement JCS canonicalisation as a small library
   (probably depending on a vetted JCS Python package, or
   ~100 LOC of in-tree code).
3. Implement `oida-code mcp register / inspect` — these are
   safe (read-only) operations that do not run any tool.
4. Implement `oida-code mcp approve / revoke` — operator
   tooling, no auto-execution.
5. Only AFTER 1-4 ship and have tests, build the
   stdio-only mock MCP server prototype that exercises the
   rug-pull rule end-to-end.

---

**Honesty statement**: this document specifies a pinning
design that has zero runtime presence in Phase 5.0. The locks
preventing MCP code (`test_no_mcp_workflow_or_dependency_added`
/ `test_no_provider_tool_calling_enabled`) remain active. No
hash is computed, no server is registered, no tool is
approved, no fingerprint is stored.
