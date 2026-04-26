# MCP unlock criteria — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-F.
**Status**: design only. The anti-MCP locks
(`test_no_mcp_workflow_or_dependency_added`,
`test_no_provider_tool_calling_enabled`) **remain active**
after Phase 5.0. This document defines what would have to be
in place BEFORE a future ADR may remove them.

> **Important**: Phase 5.0 writes the criteria for unlocking
> MCP and provider tool-calling. Phase 5.0 does NOT unlock
> them. The locks are guardrails preventing design from
> becoming accidental implementation; their removal requires
> a separate, deliberate decision.

## 1. The 10 unlock criteria

Every item below MUST be satisfied before the next phase may
remove either of the two anti-MCP locks. Partial satisfaction
is not enough — the criteria are jointly sufficient AND
individually necessary.

### Criterion 1 — MCP threat model complete

The threat model document (`mcp_threat_model.md`) MUST cover:

* All 10 OWASP MCP Top 10 risks, named and mapped to
  controls (MCP01-MCP10).
* The MCP-spec specific **confused deputy** and **token
  passthrough** risks from MCP Security Best Practices.
* Explicit assets, trust boundaries, actors, abuse cases.
* The 12-item `Required controls` checklist.
* An open-questions section listing what the design
  deliberately defers.

**Phase 5.0 status**: ✅ done — `mcp_threat_model.md` ships
in this phase.

### Criterion 2 — MCP admission policy complete

The admission policy (`mcp_admission_policy.md`) MUST cover:

* Server status enum (proposed / quarantined /
  approved_read_only / approved_tooling / rejected /
  revoked).
* 12-item approval checklist.
* Auto-rejection list with explicit triggers.
* Quarantine semantics (one-way within an approval cycle).
* Authorization policy enforcing one-token-per-server,
  no GITHUB_TOKEN passthrough, confused-deputy guard,
  redirect-URI strict match, and consent-per-client.
* Operator workflow pseudocode (register / inspect /
  approve / revoke).

**Phase 5.0 status**: ✅ done — `mcp_admission_policy.md`
ships in this phase.

### Criterion 3 — Schema pinning design reviewed

The pinning design (`tool_schema_pinning.md`) MUST cover:

* `ToolSchemaFingerprint` Pydantic schema with
  `description_sha256` / `input_schema_sha256` /
  `output_schema_sha256` (all 64-char lowercase hex).
* Canonicalisation specification (JCS RFC 8785).
* Rug-pull detection rule (any hash drift → quarantine
  the entire server).
* Per-notification behaviour (`tools/list_changed`,
  `resources/list_changed`, `prompts/list_changed`).
* Storage layout (design pseudocode, no on-disk presence in
  Phase 5.0).
* Per-capability scope pinning (`allowed_scopes`).

**Phase 5.0 status**: ✅ done — `tool_schema_pinning.md`
ships in this phase.

### Criterion 4 — No dynamic tool install

The design MUST forbid runtime tool installation:

* No `pip install <mcp-package>` triggered by an LLM
  request.
* No `npm install` from a server response.
* No tool fetched at runtime from a URL.
* No package manager invocation behind any LLM-influenced
  decision.

The first acceptable Phase 5.x prototype is **vendored or
explicitly declared** in `pyproject.toml` (or its
equivalent), pinned to a specific version + SHA, and
audited as a normal dependency. `mcp_admission_policy.md`
§3 enforces this via "dependency unpinned → auto-reject".

**Phase 5.0 status**: ✅ encoded in admission policy.

### Criterion 5 — Local-only sandbox design accepted

The first MCP prototype MUST be local-stdio only:

* No HTTP transport.
* No DNS resolution.
* No outbound network from the MCP subprocess.
* The host enforces this via OS-level sandbox primitives
  (Linux namespaces / cgroups; macOS sandbox-exec; Windows
  Job Objects). The selection is per-platform; the design
  document for Phase 5.x must spell out the chosen
  primitive on each.

`mcp_threat_model.md` §8 Open question 6 captures the
remaining sandbox decision; it must be answered (with a
concrete primitive per supported OS) before the locks lift.

**Phase 5.0 status**: design recorded; concrete primitive
selection deferred to Phase 5.x ADR.

### Criterion 6 — Audit log schema accepted

The audit log schema (`mcp_audit_log_schema.md`) MUST cover:

* `MCPAuditEvent` Pydantic schema with the 4-value
  `PolicyDecision` enum, the 3 capability sentinel flags,
  and explicit redaction rules.
* Storage layout (per-day, per-server JSONL append-only).
* Append rules (one event per Stage 2 decision, best-effort
  durability with execution-on-failure).
* Cross-references with the other Phase 5.0 docs.

**Phase 5.0 status**: ✅ done — `mcp_audit_log_schema.md`
ships in this phase.

### Criterion 7 — Allowlist-only tool registry accepted

The runtime MUST resolve tool calls against a LOCALLY-DEFINED
allowlist, NOT against the server's `tools/list`:

* The host's tool registry holds the approved fingerprints
  (`ApprovedMCPServer.fingerprints`).
* A `tools/call` for a `tool_name` not in the local registry
  is rejected, even if the server claims the tool exists.
* New tools added to the server (without operator
  re-approval) → not callable.

This is enforced by `mcp_admission_policy.md` §3 (auto-reject
on dynamic tool definitions without pinning) and by
`tool_schema_pinning.md` §4 (rug-pull rule).

**Phase 5.0 status**: ✅ encoded in admission policy +
pinning design.

### Criterion 8 — Human approval protocol accepted for writes

Before mode 4 (write tools) is even DESIGNED, a human approval
protocol MUST be specified. Phase 5.0 design says: mode 4 is
NOT in scope; the criteria for mode 4 must include a per-call
human approval step (operator presses "approve" before the
write is executed). No automatic approval, no batch approval.

**Phase 5.0 status**: deferred indefinitely. Reaching mode 4
is not a near-term roadmap item. Even read-only / mode-2
unlock does not require this criterion to be satisfied; this
criterion is a hard prerequisite ONLY for mode 4.

### Criterion 9 — Failure mode tests specified

The Phase 5.x ADR that proposes lock removal MUST also
specify the test set that exercises every failure mode in
`mcp_admission_policy.md` §9:

* Hash drift mid-call → server quarantined, response dropped.
* Forbidden-phrase hit in tool description → server rejected
  on registration, OR quarantined post-approval.
* Tool output schema violation → response dropped, audit
  event with `policy_decision="block"`.
* Server crash / hang → subprocess killed, audit event with
  `reason="timeout"` or `reason="crash"`.
* Audit log write failure → call rejected.

Each failure mode MUST have at least one regression test that
runs in the standard pytest suite. The test names should be
prefixed `test_mcp_failure_*`.

**Phase 5.0 status**: not yet — this is the bulk of the
Phase 5.x implementation work.

### Criterion 10 — Rollback plan defined

The Phase 5.x ADR MUST specify a rollback plan:

* How to disable MCP execution at runtime (env var?
  config flag? CLI argument?).
* What happens to in-flight calls when MCP is disabled.
* What the operator sees when an MCP-using workflow is
  re-run after disable.
* How approved server records are preserved (so re-enable
  doesn't require re-approval).

**Phase 5.0 status**: design pseudocode TBD in Phase 5.x.

## 2. The locks remain ACTIVE after Phase 5.0

> **Anti-MCP and anti-tool-calling tests remain active after Phase 5.0.** They are not a blocker to this design phase; they are the guardrail that prevents design from becoming accidental implementation.

The two locks are:

1. **`test_no_mcp_workflow_or_dependency_added`** (in
   `tests/test_phase4_7_provider_baseline.py:427`). Asserts:
   * No `mcp.yml` / `mcp-baseline.yml` workflow.
   * No `"mcp"` / `"model-context-protocol"` /
     `"mcp-server"` package in `pyproject.toml`.
   * No `mcp-server` invocation in any workflow YAML.
2. **`test_no_provider_tool_calling_enabled`** (in
   `tests/test_phase4_7_provider_baseline.py:462`). Asserts:
   * `supports_tools=True` is not present anywhere in
     `src/oida_code/estimators/provider_config.py`.

Phase 5.0 ADDS to these locks (cf.
`tests/test_phase5_0_design.py`):

* `test_anti_mcp_locks_still_active` — imports the two
  existing test functions and asserts they are present and
  callable. This catches a future commit that silently
  deletes the function (vs. legitimately removing it via an
  ADR).
* `test_no_supports_tools_true` — repeats the
  `supports_tools=True` check explicitly so the assertion
  lives in the Phase 5.0 test file too.
* `test_no_mcp_dependency_added` — `pyproject.toml` MCP
  package check, again explicitly in Phase 5.0 test file.
* `test_no_mcp_workflow_added` — workflow-directory MCP
  check, again explicitly.
* `test_no_official_fields_emitted` — extends the existing
  ADR-22 hard-wall checks to cover the design docs (the
  docs MUST NOT include `total_v_net=...` / `debt_final=...`
  / `corrupt_success=...` as anything other than blocked
  references).

These additional Phase 5.0 tests are EXPLICITLY scoped:

* They check `pyproject.toml` (no MCP package).
* They check `.github/workflows/` (no MCP workflow).
* They check `src/oida_code/` (no MCP runtime imports, no
  `supports_tools=True`).
* They DO NOT check `docs/` or `reports/` (those files
  intentionally contain the words "MCP" / "tool-calling" /
  "supports_tools" — the test scoping prevents false
  positives on the design content itself).

## 3. The unlock procedure (design only)

When (and IF) all 10 criteria are satisfied:

1. A new ADR (call it ADR-N for now; it's not numbered until
   the moment arrives) is written, explicitly removing one
   or both locks.
2. The ADR cites which criteria are met and how.
3. A new phase (Phase 5.x) lands the implementation in a
   single commit:
   * Adds the dependency / vendored package / both.
   * Adds the runtime code under `src/oida_code/mcp/` (or
     similar).
   * Modifies the existing locks INTENTIONALLY (e.g.,
     `test_no_mcp_workflow_or_dependency_added` becomes
     `test_only_pinned_mcp_dependency_present`).
   * Adds the failure-mode tests from criterion 9.
   * Adds the rollback toggle from criterion 10.

The "intentional modification" point matters: a silent
removal of the lock test (e.g., `git rm` without ADR) is the
attack vector this design protects against. The
`test_anti_mcp_locks_still_active` Phase 5.0 test catches
silent removal; intentional removal accompanies the ADR and
its replacement test.

## 4. What stays locked even after MCP unlock

Even if Phase 5.x removes the two anti-MCP locks, several
locks remain in place INDEFINITELY (until a separate, named
ADR removes each):

* **ADR-22 hard wall**: no `total_v_net` / `debt_final` /
  `corrupt_success` emission. Independent of MCP / tool-
  calling.
* **`is_authoritative: Literal[False]`** on shadow / verifier
  reports. The aggregator's authority is structurally pinned
  via Pydantic Literal — MCP / tool-calling do not change
  that.
* **No raw prompt / raw response in artifacts**. Phase 4.8-A
  redaction layer + Phase 4.9-F manifest pin
  (`contains_secrets: Literal[False]`) hold.
* **No `pull_request_target` triggers anywhere**. The
  fork-PR fence (Phase 4.5) is broader than MCP and stays.
* **No GitHub App / custom Checks API integration**. Out of
  scope at every phase.
* **No PyPI stable release** while the official fields
  remain blocked.

## 5. Cross-references

| Document | Anchor | Relevance to unlock |
|---|---|---|
| `mcp_threat_model.md` | §6 controls | Implementation guidance for criteria 1-7 |
| `mcp_admission_policy.md` | §2 conditions | Criterion 1 + 2 + 7 |
| `tool_schema_pinning.md` | §4 rug-pull rule | Criterion 3 |
| `tool_call_execution_model.md` | §3 modes | Criteria 4 + 5 |
| `mcp_audit_log_schema.md` | §1 event schema | Criterion 6 |
| ADR-22 (memory-bank/decisionLog.md) | hard wall | Stays even if MCP unlocks |
| ADR-29 / ADR-32 (decisionLog.md) | provider-tool-calling locks | Same logic as MCP locks |

---

**Honesty statement**: this document writes the criteria for
removing the anti-MCP locks. It does NOT remove them. After
Phase 5.0 ships, the locks are still active; any future
implementation phase that removes them must do so via a
named ADR that cites which criteria are met. The
`test_anti_mcp_locks_still_active` test added in Phase 5.0
catches accidental or silent removal.
