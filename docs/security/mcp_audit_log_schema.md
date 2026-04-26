# MCP audit log schema — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-G.
**Status**: design only. No audit log is written in Phase 5.0
(no MCP execution → nothing to audit). This document specifies
the schema a future Phase 5.x implementation must satisfy.

> **Three-line principle**:
> No tool without a trace.
> No trace without a reason.
> No reason without a policy.

OWASP MCP Top 10 lists **MCP08 — lack of audit and telemetry**
as one of the dominant risks. Phase 5.0 design assumes the
audit log is a hard prerequisite for any MCP integration; a
server that cannot be audited cannot be admitted (cf.
`mcp_admission_policy.md` §2 condition 12).

## 1. Event schema

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


PolicyDecision = Literal[
    "allow",         # Stage 2 passed, tool was invoked
    "block",         # Stage 2 rejected (schema, allowlist, budget, scope)
    "quarantine",    # Schema hash drift, server marked quarantined
    "human_review",  # Pending operator decision (Phase 5.x mode 4)
]


RequestedBy = Literal[
    "llm",           # The LLM-estimator emitted the request
    "operator",      # Human-issued via CLI / workflow input
    "workflow",      # Internal trigger (e.g., scheduled audit job)
]


class MCPAuditEvent(BaseModel):
    """One event per (Stage 2 decision, Stage 3 invocation
    attempt). The aggregator NEVER consumes audit events as
    evidence — they are operator-facing telemetry.
    """
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    # Identity
    event_id: str = Field(min_length=1)        # ULID / UUIDv7 (sortable)
    timestamp: str = Field(min_length=1)        # ISO-8601 UTC w/ "Z"

    # What
    server_id: str = Field(min_length=1)
    server_version: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_schema_hash: str = Field(min_length=64, max_length=64)
    # ^ The fingerprint USED for this call (post-canonicalisation).
    #   On a quarantine event, this is the OBSERVED hash that
    #   diverged from the approved one.

    # Who / why
    requested_by: RequestedBy
    case_id: str | None = None
    # ^ When the request comes from a calibration-eval / audit run.

    request_summary: str = Field(min_length=1)
    # ^ Short, human-readable. The full arguments are NEVER logged
    #   here (see §3 redaction). Example: "ruff check src/" or
    #   "github.read_pr(pr_number=123)".

    # Policy
    allowed: bool
    policy_decision: PolicyDecision
    reason: str = Field(min_length=1)
    # ^ Free-form short string. For block: "schema_violation" /
    #   "allowlist_miss" / "budget_exceeded" / "scope_creep".
    #   For quarantine: "description_hash_drift" /
    #   "input_schema_hash_drift" / "output_schema_hash_drift" /
    #   "package_hash_mismatch_at_start".

    # Evidence linkage
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    # ^ When the call produced an EvidenceItem, list its IDs so
    #   an operator can navigate from audit → evidence in the
    #   aggregator report.

    # Capability flags (sentinel-style — these MUST be False for
    # admitted servers; True is a red flag)
    secret_access_attempted: bool = False
    network_access_attempted: bool = False
    write_access_attempted: bool = False
```

## 2. Field semantics

### 2.1 `event_id`

Recommend ULID or UUIDv7 (time-sortable). Never a sequential
integer (an attacker who tampers with one event could re-number
the rest to hide the gap). The ID lookup must work even if
events are appended out-of-order across multiple processes.

### 2.2 `timestamp`

ISO-8601 UTC with the trailing `Z`. Phase 4.9-F's
`generated_at` field uses the same format; consistency matters
because an operator may correlate a manifest's timestamp with
audit events.

### 2.3 `tool_schema_hash`

The 64-char SHA256 of the canonicalised
`description + input_schema + output_schema` triplet AS
OBSERVED at this call (not the approved fingerprint). This is
the field that makes hash-drift detection auditable: when
`policy_decision="quarantine"` and `reason` is a
hash-drift class, this field shows the OBSERVED hash; cross-
referencing against the approved fingerprint's stored hashes
reveals the exact tool that drifted.

### 2.4 `request_summary`

A short, human-readable summary. Phase 5.0 design rule: this
field MUST NOT contain:

* the raw `arguments` dict (could include user-supplied
  paths / query strings)
* any value matching the secret-detection patterns from
  Phase 4.8-A's `redact_secret`
* the full prompt that produced the LLM's request

The summary is meant to let a human glance the audit log and
understand "what was attempted". For forensic detail, the
operator cross-references with the `evidence_refs` IDs in the
aggregator report.

Example summaries (acceptable):
* `"ruff check src/oida_code/cli.py"`
* `"github.read_pr(pr_number=123)"`  (PR number is operational,
  not secret)
* `"mcp.unknown_tool — admission policy denied"`

Example summaries (FORBIDDEN — would leak):
* `"github.read_pr(token=ghp_***...)"`
* `"raw arguments: {...20 KB of repo content...}"`

### 2.5 `policy_decision` × `allowed`

These two fields are correlated but not redundant:

| `allowed` | `policy_decision` | Meaning |
|---|---|---|
| `True` | `"allow"` | Stage 2 passed; Stage 3 invoked |
| `False` | `"block"` | Stage 2 rejected; Stage 3 NOT invoked |
| `False` | `"quarantine"` | Hash drift / policy breach; server now quarantined |
| `False` | `"human_review"` | Awaiting operator decision (Phase 5.x mode 4) |

Any other combination is invalid. A future schema validator
SHOULD enforce this with a model-validator.

### 2.6 `evidence_refs`

For successful invocations (`allowed=True`), this lists the
`EvidenceItem` IDs the call produced. For blocks /
quarantines, this is empty (the block fired before evidence
emission). Empty is meaningful — an operator running a query
"show me audit events for case X with no evidence" gets all
the blocked attempts back.

### 2.7 Capability sentinel flags

`secret_access_attempted`, `network_access_attempted`,
`write_access_attempted` default to `False`. They're set to
`True` only when the runtime detects the tool ACTUALLY tried
the action (via sandbox / namespace / netfilter). For an
admitted read-only server, all three must stay `False` over
the entire audit log; ANY `True` is a red flag and should
trigger:

1. The server is quarantined immediately.
2. An operator notification.
3. The current call is dropped (response NOT delivered to
   the LLM-estimator).

These three flags are why Phase 5.x requires a real sandbox
primitive (cf. `mcp_threat_model.md` §8 open question 6). The
flags being all-`False` for an unaudited server tells you
nothing; their meaning depends on actually being able to
detect the attempt.

## 3. Redaction rules

Audit events MUST NEVER carry:

* the API key value (none of the existing
  `api_key_env` / Bearer tokens)
* the GitHub `GITHUB_TOKEN` or any OAuth bearer
* the raw prompt that produced the request
* the raw provider response
* the raw tool output content (only `evidence_refs` pointing
  to it)
* any user-supplied repo content beyond what's needed to
  identify the case

The same `redact_secret` family of functions used for
provider I/O (Phase 4.8-A) MUST run on every field of an
`MCPAuditEvent` before it is written to disk. A future Phase
5.x implementation extends `redact_secret` to take a
multi-secret list and run over every observed env var
matching the secret patterns.

## 4. Storage layout (design)

```
.oida/mcp/audit/<YYYY>/<MM>/<DD>/<server_id>.jsonl
```

* Per-day, per-server JSONL files.
* Append-only: opened with `mode="a"`. A future Phase 5.x ADR
  may add SHA-chained entries (each line carries a hash of
  the previous) for tamper-evidence.
* No size cap during a single run; daily rotation + operator-
  driven archival is the intended lifecycle.

## 5. Append rules

* **One event per Stage 2 decision**. A single `tools/call`
  attempt produces ONE event whose `policy_decision` reflects
  the Stage 2 outcome. Subsequent runtime detection (e.g., a
  capability sentinel firing during execution) updates the
  event by emitting a SECOND event (referencing the first via
  `event_id`) — never mutates the first.
* **Best-effort durability**. The audit write happens BEFORE
  the tool's result is delivered to Stage 4. If the audit
  write fails (disk full, permissions), the call is rejected
  (cf. `mcp_admission_policy.md` §9). Silent execution is
  worse than failure.
* **No auto-purge**. Audit events are NEVER deleted by the
  host. Operator-driven archival is allowed; programmatic
  deletion is not.

## 6. Cross-references with other Phase 5.0 documents

| Document | Section | Audit linkage |
|---|---|---|
| `mcp_threat_model.md` | §6 control 8 | "Audit log per call" |
| `mcp_admission_policy.md` | §2 condition 12 | "Audit log enabled" required for approval |
| `mcp_admission_policy.md` | §7 | Observability requirements |
| `tool_schema_pinning.md` | §4 | Hash drift triggers `policy_decision="quarantine"` event |
| `tool_call_execution_model.md` | §7 | "Every Stage 3 invocation produces exactly one MCPAuditEvent" |
| `mcp_unlock_criteria.md` | criterion 6 | Audit log schema accepted |

## 7. Test invariants (Phase 5.0)

The schema lives in this document only — no Pydantic class is
materialised in `src/oida_code/` in Phase 5.0. The Phase 5.0
test set includes:

* `test_mcp_audit_log_schema_documents_policy_decisions` —
  this doc names all four `PolicyDecision` enum values.
* `test_mcp_audit_log_schema_documents_capability_sentinels` —
  this doc names `secret_access_attempted`,
  `network_access_attempted`, `write_access_attempted`.
* `test_mcp_audit_log_schema_documents_redaction_rules` — this
  doc states "MUST NEVER carry API key" and similar redactions.

The runtime invariant (no MCP audit log code in `src/oida_code/`)
is locked by the existing
`test_no_mcp_workflow_or_dependency_added` from Phase 4.7.

---

**Honesty statement**: this document specifies an audit log
schema for an integration that does not exist. No audit log
is written in Phase 5.0; no `MCPAuditEvent` Pydantic class is
created in `src/oida_code/`; no `.oida/mcp/audit/` directory
is touched. The locks preventing MCP code from landing remain
active.
