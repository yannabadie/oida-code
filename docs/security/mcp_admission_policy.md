# MCP admission policy — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-B.
**Status**: design only. No MCP server is admitted, executed,
or even instantiated in Phase 5.0. This document defines the
conditions a future MCP integration would have to satisfy.

This policy answers a single question:

> Under what conditions is a candidate MCP server eligible for
> execution by OIDA-code?

The answer is *almost never*. The default state for every MCP
server (real or hypothetical) is `proposed` — not approved,
not running. Approval is operator-driven, time-bounded, and
schema-pinned.

## 1. Server status enum

```python
from typing import Literal

MCPServerStatus = Literal[
    "proposed",            # Default. Server is registered but cannot run.
    "quarantined",         # Hash mismatch, schema drift, or anomaly. Cannot run.
    "approved_read_only",  # Operator approved for read-only tools (mode 2).
    "approved_tooling",    # Reserved (Phase 5.x). Tooling beyond read-only.
    "rejected",            # Permanent denial. Re-proposal requires new server_id.
    "revoked",             # Was approved; revoked due to policy breach.
]
```

Default: every newly-registered server starts at `proposed`. A
server in `proposed` MAY be inspected (`tools/list`,
`resources/list`) to compute its schema fingerprints, but it
MUST NOT be invoked (`tools/call` is forbidden on `proposed`).

## 2. Approval conditions (12-item checklist)

A server transitions from `proposed` → `approved_read_only`
ONLY when ALL twelve conditions are met. Operator signs the
approval in `mcp_servers.json` (Phase 5.1+ artifact, NOT
shipped in Phase 5.0).

1. **Server identity known**. `server_id` is a
   stable string; the package / binary backing it is
   identified by name + version + cryptographic hash of the
   distribution tarball / executable. No identity drift.
2. **Source / package provenance known**. The package's
   origin is recorded (PyPI / npm / GitHub release URL +
   commit SHA + sigstore attestation when available). An
   anonymous tarball is rejected.
3. **Version pinned**. The approval references a specific
   `server_version`. A "pin to latest" specification is
   automatically rejected.
4. **Tool schema hash pinned**. Every tool the server exposes
   is recorded with its `description_sha256`,
   `input_schema_sha256`, and `output_schema_sha256` (see
   `tool_schema_pinning.md`).
5. **Tool descriptions scanned**. Each `description` field
   passes the same forbidden-phrase scan that runs on LLM
   responses (Phase 4.0 / ADR-25). No tool whose description
   contains any of the forbidden phrases is approved.
6. **No hidden prompt-injection pattern**. Each `description`
   is additionally scanned for known injection patterns:
   * "ignore previous instructions"
   * "system:" / "developer:" tags
   * encoded directives (base64, ROT13, zero-width chars)
   * inner copies of `<<<OIDA_EVIDENCE` / `<<<END_OIDA_EVIDENCE`
     fence markers
7. **No write access by default**. Only tools whose
   `input_schema` describes pure-read operations on the local
   filesystem (no `mode="w"`, no `path` outside an explicit
   read-allowlist) are eligible for the read-only tier.
8. **No network egress by default**. The server's manifest /
   capability declaration MUST state "no outbound network".
   Servers requesting outbound network on approval are
   automatically rejected; outbound network MAY be requested
   in Phase 5.x with a separate ADR.
9. **No secret access**. The approved server's process
   environment is computed from a small allowlist; the host's
   `os.environ` is NOT inherited. Any tool whose
   `input_schema` accepts a "credential" / "api_key" /
   "token" parameter is automatically rejected.
10. **No broad OAuth scopes**. If the server uses OAuth, its
    requested scopes are listed at approval. The MCP spec
    forbids token passthrough; this policy enforces it
    structurally — a single OAuth token is never reused
    across servers, and a scope addition triggers
    quarantine + re-approval.
11. **Tool outputs treated as data**. The host wraps every
    tool output in an evidence fence (Phase 4.0.1 / ADR-26)
    and runs forbidden-phrase scan + schema validation
    against the pinned `output_schema_sha256`.
12. **Audit log enabled**. Every `tools/call` against an
    approved server emits an `MCPAuditEvent`
    (`mcp_audit_log_schema.md`). A server that cannot be
    audited (e.g., refuses to run with audit enabled) is
    rejected.

A 13th condition is required for any non-read-only mode (see
`tool_call_execution_model.md`): explicit human approval per
write-class call. Phase 5.0 design explicitly does not
authorize that mode.

## 3. Auto-rejection list

A candidate server is rejected immediately (no operator
review) if ANY of the following hold:

* **Dynamic tool definitions without pinning**. The server
  emits `tools/list_changed` notifications without the host
  having a fingerprint of every reachable tool variant.
* **Tool schema changed after approval**. The
  `description_sha256`, `input_schema_sha256`, or
  `output_schema_sha256` differs from the approved fingerprint.
* **Broad filesystem access**. A tool's `input_schema`
  accepts an arbitrary `path` parameter without an explicit
  allowlist; OR a tool's declared capability includes
  "filesystem write" / "filesystem delete" / "execute".
* **Shell execution exposed**. A tool whose name, description,
  or input schema implies arbitrary shell / subprocess
  invocation (`shell`, `exec`, `system`, `cmd`, "run command").
* **OAuth broad scopes**. Any of `*`, `repo:write`,
  `admin:org`, `delete_repo`, `secrets:write`, or an
  unconstrained scope wildcard.
* **Unknown package source**. The server's distribution
  origin is not in the approved allowlist (PyPI / npm with
  signed package, GitHub release with attestation, or local
  vendored copy with SHA recorded).
* **Dependency unpinned**. The server's own dependency
  manifest contains floating versions (`>=`, `^`, `~`)
  without a lockfile.
* **Tool description contains instruction to ignore
  policy**. Pattern match on "ignore (the )?(previous|above|
  system|developer) (instruction|policy|prompt|rule)" — case
  insensitive, matched within the description text.
* **Server requests secrets**. The server's
  `inputSchema` for any tool accepts a property whose name
  matches `(api_)?key|token|credential|password|secret|
  bearer` — case insensitive — without an explicit annotation
  marking it as a non-secret label.
* **Server attempts outbound network not declared**. At
  runtime, a Phase 5.1+ implementation MUST detect outbound
  network attempts (via OS-level netfilter / sandbox-exec /
  similar) and quarantine on first hit. Phase 5.0 design
  notes: this requires a non-trivial sandbox primitive; see
  `mcp_threat_model.md` §8 open questions.

## 4. Quarantine semantics

`quarantined` is a one-way street within an approval cycle: a
quarantined server stops being callable, the operator is
notified (via `MCPAuditEvent` with `policy_decision="quarantine"`
and a non-empty `reason`), and the server stays quarantined
until the operator either:

* **Approves the new fingerprint** (a fresh
  `approved_at` timestamp + new `description_sha256` etc.),
  effectively re-issuing the approval with the new schema,
  OR
* **Marks the server `revoked`** (permanent block within this
  approval cycle).

A `revoked` server cannot be re-proposed under the same
`server_id` — operator MUST register a new identity. This
prevents an attacker who compromised an approved server from
"resetting" its status by causing a benign-looking
re-proposal.

## 5. Authorization (token / OAuth) policy

The MCP Security Best Practices document forbids **token
passthrough**: a server MUST NOT accept tokens that were not
explicitly issued for it. Phase 5.0 admission policy enforces
this structurally:

1. **One-token-per-server**. The host issues OAuth tokens
   per `server_id`. A token issued for `server_A` is never
   visible to `server_B`. Storage is per-server (e.g., a
   keychain entry per server, or a per-server env var that
   only that subprocess sees).
2. **No GITHUB_TOKEN passthrough**. The runner's
   `GITHUB_TOKEN` is NEVER passed to an MCP subprocess. If a
   future MCP server needs GitHub access, it negotiates its
   own token via the GitHub App / OAuth flow (and that token
   is scoped to its own identity, not the runner's).
3. **Confused-deputy guard**. When the host calls a tool that
   in turn requests another tool's invocation (or another
   server's resource), the host re-validates the second
   call's authorization against the FIRST server's policy.
   The deputy chain does not inherit privilege.
4. **Redirect URI strict match**. For any OAuth flow, the
   redirect URI MUST be a literal-match against the value
   recorded at server registration. Wildcard redirects are
   rejected.
5. **Consent per client**. Per MCP spec: each client MUST
   give explicit consent to call each tool. The host's
   policy treats "consent" as the operator-signed approval
   from §2; an LLM cannot grant consent on the operator's
   behalf.

## 6. Data flow controls

* **Inputs to MCP tools**: validated against the locally
  pinned `input_schema_sha256` BEFORE the request leaves the
  host. A server that responds to inputs the host did not
  validate (because the local schema rejected them) cannot
  execute the tool — the host short-circuits.
* **Outputs from MCP tools**: validated against the locally
  pinned `output_schema_sha256` AFTER the response arrives.
  A response that fails validation → `policy_decision="block"`
  in the audit event; the output never reaches the LLM.
* **Resources read**: every byte returned by `resources/read`
  is wrapped in an evidence fence. The fence's neutralisation
  rule (Phase 4.0.1, ADR-26) ensures inner forged closes
  cannot break out.
* **Prompts get**: forbidden in Phase 5.0 design. The host
  does not consume server-supplied prompt templates.

## 7. Observability requirements

Every approved server MUST be auditable end-to-end:

* Every `tools/call` produces one `MCPAuditEvent` (see
  `mcp_audit_log_schema.md`).
* Every notification (`tools/list_changed`,
  `resources/list_changed`) produces an audit entry.
* Every authorization decision (approve / quarantine /
  revoke) produces an audit entry with the operator's
  identity and timestamp.
* The audit log is append-only. A future Phase 5.x design
  may add SHA-chained entries for tamper-evidence, similar to
  the artifact manifest's hashing approach (Phase 4.9-F).

## 8. Operator workflow (design only)

```
operator runs:
  oida-code mcp register <server_id> --package <url> --version <v>
    → status=proposed, fingerprints computed
operator runs:
  oida-code mcp inspect <server_id>
    → list tools + their hashes + their descriptions
operator reviews:
  read tool descriptions, check for prompt injection
  read input/output schemas, check for filesystem / shell / network capabilities
operator runs:
  oida-code mcp approve <server_id> --tier read_only --signed-by <op>
    → status=approved_read_only
when calling:
  every tools/call writes an MCPAuditEvent
on hash drift:
  status → quarantined automatically (no operator action needed)
on policy breach:
  operator runs `oida-code mcp revoke <server_id>` → status=revoked
```

**This entire workflow is design-only.** Phase 5.0 ships no
`oida-code mcp` subcommands. The pseudocode is the contract a
future Phase 5.1+ implementation must satisfy.

## 9. Failure modes and rollback

* **Hash drift detected mid-call**: the in-flight request
  completes, the response is dropped (treated as data not
  reaching the LLM), and the server is quarantined.
* **Forbidden-phrase hit in tool description**: server is
  rejected immediately on registration; if discovered
  post-approval (because a notification updated the
  description), server is quarantined and the call is dropped.
* **Tool output schema violation**: response is dropped, audit
  event with `policy_decision="block"` and
  `reason="output_schema_violation"`. The aggregator NEVER
  sees this output.
* **Server crash or hang**: subprocess killed after the
  per-tool timeout (mirroring `OpenAICompatibleChatProvider`'s
  timeout handling); audit event with
  `policy_decision="block"` and `reason="timeout"` or
  `reason="crash"`.
* **Audit log write failure**: the call is rejected. No
  trace, no execution. This is intentional — silent execution
  is the worst failure mode.

---

**Honesty statement**: this admission policy is a design
document. No MCP server is admitted, executed, or
instantiated in Phase 5.0. The
`test_no_mcp_workflow_or_dependency_added` and
`test_no_provider_tool_calling_enabled` invariants from Phase
4.7 remain active. Removal of those locks requires a separate
ADR and is out of scope for Phase 5.0.
