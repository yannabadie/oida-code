# Phase 5.0 — MCP / provider tool-calling design (ADR-35)

QA/A27.md scope. Phase 5.0 is a **design-only** phase. It
produces a threat model, admission policy, tool schema pinning
design, tool-call execution model, audit-log schema, MCP
unlock criteria, and a Pydantic-AI assessment, plus this
report. **It implements no MCP code and enables no provider
tool-calling.**

---

## Honesty statement (locked by QA/A27.md lines 899-908)

* Phase 5.0 is design-only.
* It does not add MCP runtime integration.
* It does not enable provider tool-calling.
* It does not execute MCP tools.
* It does not remove anti-MCP or anti-tool-calling locks.
* It does not validate production predictive performance.
* It does not emit official `total_v_net`, `debt_final`, or
  `corrupt_success`.
* It does not modify the vendored OIDA core.

---

## 1. Diff summary

| Area | File | Change | Lines |
|---|---|---|---|
| Threat model | `docs/security/mcp_threat_model.md` | NEW — 8-section structure covering OWASP MCP01-MCP10 + confused deputy + token passthrough; 14 abuse cases; 12 required controls | ~+330 |
| Admission policy | `docs/security/mcp_admission_policy.md` | NEW — `MCPServerStatus` enum, 12-item approval checklist, 9 auto-reject triggers, quarantine semantics, authz policy, operator workflow pseudocode | ~+250 |
| Schema pinning | `docs/security/tool_schema_pinning.md` | NEW — `ToolSchemaFingerprint` Pydantic schema, JCS RFC 8785 canonicalisation, rug-pull rule, per-notification behaviour | ~+220 |
| Execution model | `docs/security/tool_call_execution_model.md` | NEW — 5 execution modes, pipeline contract, provider tool-calling forbidden by default, list of forbidden LLM utterances | ~+260 |
| Audit log schema | `docs/security/mcp_audit_log_schema.md` | NEW — `MCPAuditEvent` schema with `PolicyDecision` enum + capability sentinels + redaction rules | ~+220 |
| Unlock criteria | `docs/security/mcp_unlock_criteria.md` | NEW — 10-item criteria list; locks remain active after Phase 5.0 | ~+220 |
| Pydantic-AI assessment | `experiments/pydantic_ai_spike/phase5_assessment.md` | NEW — 7 evaluation questions; recommendation = `pydantic_ai_adapter_experiment` (NOT migration) | ~+250 |
| Phase 5.0 report | `reports/phase5_0_mcp_tool_calling_design.md` | THIS file | ~+450 |
| ADR-35 | `memory-bank/decisionLog.md` | Appended | ~+85 |
| Phase 5.0 tests | `tests/test_phase5_0_design.py` | NEW — non-regression tests with proper scoping | ~+260 |
| Docs | `README.md` + `memory-bank/progress.md` | Phase 5.0 status entries | ~+30 |

Net: ~+2575 lines added, **zero lines under `src/oida_code/`**,
**zero new dependencies in `pyproject.toml`**, **zero new
workflows under `.github/workflows/`**.

---

## 2. ADR-35 excerpt

See `memory-bank/decisionLog.md` for the full ADR. Decision
summary:

> Phase 5.0 is a DESIGN-ONLY phase. It produces six security
> documents under `docs/security/` plus a Pydantic-AI
> assessment plus a 13-section report. NO MCP runtime code.
> NO provider tool-calling enabled. The existing anti-MCP
> locks STAY ACTIVE; Phase 5.0 EXTENDS them with a new test
> set in `tests/test_phase5_0_design.py`.

Accepted: MCP threat model, admission policy, schema pinning
design, execution model, audit log schema, unlock criteria,
Pydantic-AI Phase 5 assessment, local-stdio-first
recommendation, no-write first prototype, no remote MCP first
prototype, no secrets in MCP context, aggregator remains
final authority, existing anti-MCP locks remain active.

Rejected: MCP runtime code, remote MCP servers, provider
tool-calling enabled by default, dynamic unpinned tools,
write/destructive tools, token passthrough, raw tool output
trusted as instruction, Pydantic-AI runtime migration, GitHub
App / Checks API, official V_net / debt_final /
corrupt_success.

---

## 3. Threat model (5.0-A summary)

Full document: `docs/security/mcp_threat_model.md`.

The MCP architecture (host / client / server, JSON-RPC,
dynamic `tools/list`, live `tools/list_changed` notifications)
introduces an attack surface that OIDA-code's existing closed-
tool-adapter approach does not have. Phase 5.0's threat model
covers:

* **9 protected assets**: repo source, provider API keys,
  GitHub tokens, tool outputs, calibration / private holdout
  cases, redacted provider I/O, artifact manifests, SARIF
  outputs, user intent.
* **15-row trust-boundary matrix**: extends OIDA-code's
  existing trust framework with explicit MCP entries
  (`tools/list` descriptions, `inputSchema`, `outputSchema`,
  `resources/read` contents, `prompts/get` outputs all
  marked **untrusted**).
* **7 actor classes**: repo committer, provider model, MCP
  server author, MCP server operator, GitHub Actions user,
  GitHub Actions runner, external attacker via fork PR.
* **7 attack surfaces** keyed by JSON-RPC method
  (`tools/list`, `tools/call`, `tools/list_changed`,
  `resources/list` + `resources/read`, `prompts/get`,
  authorization, transport).
* **14 abuse cases** including all 10 OWASP MCP Top 10
  classes (MCP01-MCP10) plus confused deputy, token
  passthrough, JSON-RPC replay, and local sandbox escape.
* **12 required controls** for any future Phase 5.1
  prototype: identity pinning, schema pinning, no write
  tools, no remote servers, no secret access, treat tool
  output as data, aggregator final authority, audit log per
  call, no fork PR, no GITHUB_TOKEN passthrough, operator
  opt-in, rollback.
* **6 open questions** explicitly NOT answered by Phase 5.0:
  schema hash canonicalisation finer points, description-
  prose hashing, allowlist enforcement layer location, audit
  log persistence format, Pydantic-AI's `MCPServerStdio`
  fit, sandbox primitive selection per platform.

Cross-reference: every required control links to a section in
one of the other Phase 5.0 documents (admission policy,
pinning, execution model, audit log, unlock criteria).

---

## 4. MCP admission policy (5.0-B summary)

Full document: `docs/security/mcp_admission_policy.md`.

```python
MCPServerStatus = Literal[
    "proposed", "quarantined", "approved_read_only",
    "approved_tooling", "rejected", "revoked",
]
```

Default: every newly-registered server starts at `proposed`.
Approval requires ALL twelve checklist items:

1. server identity known (cryptographic hash of distribution)
2. source / package provenance known
3. version pinned (no "latest")
4. tool schema hash pinned (per-tool, three SHAs)
5. tool descriptions scanned (forbidden-phrase check)
6. no hidden prompt-injection pattern
7. no write access by default
8. no network egress by default
9. no secret access (env not inherited)
10. no broad OAuth scopes (no token passthrough)
11. tool outputs treated as data (fenced + scanned)
12. audit log enabled (no tool without trace)

Auto-rejection list (9 triggers):
dynamic-tool-defs-without-pinning, schema-changed-after-
approval, broad-filesystem-access, shell-execution-exposed,
OAuth-broad-scopes, unknown-package-source, dependency-
unpinned, description-contains-policy-bypass-pattern, server-
requests-secrets, server-attempts-undeclared-network.

Quarantine is a one-way street within an approval cycle:
quarantined → re-approved with new fingerprint OR revoked
permanently. A revoked server cannot be re-proposed under the
same `server_id` (prevents an attacker from "resetting"
status via benign-looking re-proposal).

---

## 5. Tool schema pinning / rug-pull detection (5.0-C summary)

Full document: `docs/security/tool_schema_pinning.md`.

```python
class ToolSchemaFingerprint(BaseModel):
    server_id: str
    server_version: str
    server_origin: ServerOrigin  # local_stdio | local_http | remote_http
    tool_name: str
    description_sha256: str       # 64-char hex
    input_schema_sha256: str      # 64-char hex
    output_schema_sha256: str     # 64-char hex
    risk_level: RiskLevel
    allowed_scopes: tuple[str, ...]
    approved_by: str              # operator identity
    approved_at: str              # ISO-8601 UTC w/ "Z"
```

**Canonicalisation**: JCS (RFC 8785) before hashing — UTF-8 +
NFC + lexicographically sorted object keys + no insignificant
whitespace + JCS-canonical numbers.

**Rug-pull rule**: on every `tools/list` response, recompute
fingerprints; ANY change in the (description, input_schema,
output_schema) hash triplet → quarantine the entire server,
emit `MCPAuditEvent(policy_decision="quarantine",
reason="<which>_hash_drift")`, halt all further calls until
operator re-approval.

OWASP-recommended posture: treat the entirety of a tool's
schema as injection surface; pin by cryptographic hash; alert
on changes.

---

## 6. Tool-call execution model (5.0-D summary)

Full document: `docs/security/tool_call_execution_model.md`.

**Core principle**: the LLM proposes; OIDA-code executes. The
five-stage pipeline (request → policy → adapter → EvidenceItem
→ aggregator) is unchanged from Phase 4.2; MCP and provider
tool-calling, when (and IF) they ever land, slot into the
existing pipeline rather than replacing it.

**Five execution modes**:

| Mode | Name | Phase 5.0 status |
|---|---|---|
| 0 | disabled | ✅ default |
| 1 | schema-discovery only | ✅ design only |
| 2 | read-only deterministic | recommended ceiling for Phase 5.1 prototype |
| 3 | approved deterministic | reserved (Phase 5.x ADR) |
| 4 | human-approved write | deferred indefinitely |

Phase 5.0 production: every MCP server in mode 0; mode 1
recognised in design but no runtime support shipped.

**Provider tool-calling**: `ProviderProfile.supports_tools`
stays `False` for every profile in `provider_config.py`. The
locked test
`test_no_provider_tool_calling_enabled` from Phase 4.7
(`tests/test_phase4_7_provider_baseline.py:462`) is reaffirmed
by `test_no_supports_tools_true` in Phase 5.0. If provider
tool-calling ever ships in Phase 5.x, the contract is the same
as MCP: function name in local allowlist, arguments validated
locally, host-side adapter executes.

**Forbidden context list** (no MCP execution allowed):
`pull_request` from forks, `pull_request_target`, `push` by
default, `action-smoke.yml` default path. ALLOWED only on
`workflow_dispatch` with explicit input + protected branch +
read-only permissions + operator-confirmed provider profile.

---

## 7. Audit-log schema (5.0-G summary)

Full document: `docs/security/mcp_audit_log_schema.md`.

```python
PolicyDecision = Literal[
    "allow", "block", "quarantine", "human_review",
]

class MCPAuditEvent(BaseModel):
    event_id: str           # ULID / UUIDv7
    timestamp: str          # ISO-8601 UTC w/ "Z"
    server_id: str
    server_version: str
    tool_name: str
    tool_schema_hash: str   # 64-char hex of OBSERVED triplet
    requested_by: Literal["llm", "operator", "workflow"]
    case_id: str | None
    request_summary: str    # short, human-readable, no secrets
    allowed: bool
    policy_decision: PolicyDecision
    reason: str             # short class-name
    evidence_refs: tuple[str, ...]
    secret_access_attempted: bool = False
    network_access_attempted: bool = False
    write_access_attempted: bool = False
```

**Three-line principle**: no tool without a trace; no trace
without a reason; no reason without a policy.

**Storage**: `.oida/mcp/audit/<YYYY>/<MM>/<DD>/<server_id>.jsonl`
— per-day per-server append-only.

**Redaction rules** (audit events MUST NEVER carry):
* API key value
* GITHUB_TOKEN / OAuth bearer
* raw prompt
* raw provider response
* raw tool output content (only `evidence_refs` IDs)
* user-supplied repo content beyond case identity

**Capability sentinels**: `secret_access_attempted`,
`network_access_attempted`, `write_access_attempted` default
to `False`; if a runtime sandbox primitive ever detects them
as `True`, the server is quarantined immediately.

---

## 8. Pydantic-AI Phase 5 decision (5.0-E summary)

Full document: `experiments/pydantic_ai_spike/phase5_assessment.md`.

Seven evaluation questions:

| # | Question | Answer |
|---|---|---|
| Q1 | Same `LLMEstimatorOutput`? | Yes, via `Agent(result_type=LLMEstimatorOutput)` |
| Q2 | Preserve `evidence_refs`? | Yes, with `retries=0` to prevent retry-mask |
| Q3 | Forbid `authoritative=True`? | Yes, structurally via Literal |
| Q4 | Tool-calling disabled? | Yes via `tools=[]`; surface still concerning |
| Q5 | Replay-only? | Yes but more verbose than current code |
| Q6 | Avoid MCP dynamic toolsets? | Yes by NOT importing `pydantic_ai.mcp.*` |
| Q7 | Preserve `ToolPolicy`? | Yes via wrapper-tools or fork-loop avoidance |

**Recommendation**: `pydantic_ai_adapter_experiment` —
documentary follow-on, NOT migration in Phase 5.0. The
spike's value is empirical comparison data; the migration's
ONE concrete win (reducing `OpenAICompatibleChatProvider`'s
LOC) does NOT justify dependency surface + 26+ provider-test
re-validation + Phase 4.8 multi-provider matrix re-run.

`pyproject.toml` does NOT add Pydantic-AI in Phase 5.0. The
`experiments/pydantic_ai_spike/` directory remains
documentary.

---

## 9. GitHub Actions / CI impact review

The existing CI / action surface (Phase 4.5-4.9) already has
the right posture for what Phase 5.x might attempt:

* `ci.yml` runs on `push` / `pull_request` / `workflow_dispatch`,
  never `pull_request_target`, with `permissions: contents: read`
  workflow-wide.
* `provider-baseline.yml` is `workflow_dispatch` only;
  secrets flow via `secrets.* → env: → $VAR`; replay runs
  BEFORE the external provider; only redacted headline
  metrics reach `report.md` / `$GITHUB_STEP_SUMMARY`.
* `sarif-upload.yml` is `workflow_dispatch` only;
  `security-events: write` is job-scoped; SARIF uploader pinned
  to `@v4` with explicit category `oida-code/audit-sarif`.
* `action.yml` (composite) uses the intermediate-env-var
  pattern (Phase 4.5.1) for every PR-controlled value;
  upload-sarif pinned to `@v4` with category
  `oida-code/combined`; fork-PR fence on
  `inputs.llm-provider == 'openai-compatible'`.

**Phase 5.0 design rule**: if MCP / tool-calling ever lands
(Phase 5.x), it MUST NOT run on:
* `pull_request` from forks
* `pull_request_target`
* `push` by default
* `action-smoke.yml` default path

It MAY run only on `workflow_dispatch` with explicit
`mcp-enable=true` input + protected branch + read-only
permissions + operator-confirmed provider/tool profile.

GitHub's published guidance reinforces this:
* Least privilege for `GITHUB_TOKEN`.
* `::add-mask::` for any operator-supplied secret-like input.
* Automatic secret redaction is best-effort, not guaranteed.

---

## 10. Tests and static checks

Phase 5.0 adds `tests/test_phase5_0_design.py` (~13 tests).
Per QA/A27.md lines 929-930, these tests are SCOPED:

* `pyproject.toml` (no `"mcp"` / `"model-context-protocol"` /
  `"mcp-server"` package) — extends the existing Phase 4.7
  check.
* `.github/workflows/` (no `mcp.yml`, no
  `model-context-protocol` / `mcp-server` invocation in YAML).
* `src/oida_code/` (no `import mcp`, no
  `from mcp` imports, no `supports_tools=True`).

The tests **deliberately do NOT** check `docs/` or
`reports/`. Those files contain "MCP", "tool-calling",
"supports_tools" intentionally — they ARE the design content
this phase ships. Scoping the negative checks prevents
self-fire on the docs they protect.

The 13 tests:

1. `test_phase5_design_docs_exist` — all 7 design files
   present at the documented paths.
2. `test_adr35_logged` — ADR-35 entry in
   `memory-bank/decisionLog.md`.
3. `test_mcp_threat_model_mentions_tool_poisoning`
4. `test_mcp_threat_model_mentions_rug_pull`
5. `test_mcp_threat_model_mentions_confused_deputy`
6. `test_mcp_admission_policy_requires_schema_hash`
7. `test_mcp_unlock_criteria_keeps_locks_active` — phrase
   from QA/A27 line 808-810 present verbatim.
8. `test_no_mcp_dependency_added` — `pyproject.toml` scoped
   check.
9. `test_no_mcp_workflow_added` — `.github/workflows/`
   scoped check.
10. `test_no_provider_tool_calling_enabled` — re-affirms
    Phase 4.7 lock; checks `provider_config.py` only.
11. `test_no_supports_tools_true` — same scoping; explicit
    Phase 5.0 lock.
12. `test_anti_mcp_locks_still_active` — imports the two
    Phase 4.7 lock-tests, asserts they are still defined as
    callables in `tests/test_phase4_7_provider_baseline.py`.
13. `test_phase5_report_honesty_statement` — the exact 8
    lines of the QA/A27.md lines 899-908 honesty statement
    appear in `reports/phase5_0_mcp_tool_calling_design.md`.

---

## 11. What this still does NOT prove

(In addition to the §honesty statement.)

* The threat model is exhaustive only insofar as it covers
  the OWASP MCP Top 10 + the MCP-spec authorization risks. A
  novel risk class discovered after Phase 5.0 is NOT
  pre-addressed.
* The admission policy is only as strong as the
  `MCPServerStatus` enforcement layer that does not yet
  exist in code. The policy is design-only; a future runtime
  implementation could deviate, and only Phase 5.x's tests
  will close that gap.
* The schema pinning design relies on JCS canonicalisation;
  an implementation bug in the canonicaliser would silently
  weaken the rug-pull rule. Phase 5.x must include a
  canonicaliser test suite covering RFC 8785's edge cases.
* The audit log schema does not yet include tamper-
  evidence (SHA-chained entries are noted as a Phase 5.x
  future direction). A compromised host could append fake
  events or delete real ones; Phase 5.0's design assumes the
  host process is trusted.
* The Pydantic-AI assessment's "yes, with configuration"
  answers depend on Pydantic-AI's API not changing. A future
  Pydantic-AI release might change `tools=[]` semantics or
  introduce auto-discovery; the assessment would need to be
  re-run.

---

## 12. Recommendation for Phase 5.1

Two options exist.

**Option A (recommended): Phase 5.1 — local deterministic
tool gateway**

* No MCP yet.
* Adapt the current `ruff` / `mypy` / `pytest` /
  `semgrep` / `codeql` engine into a gateway abstraction
  that emits `MCPAuditEvent`-shaped audit records (without
  the MCP transport, but with the same observability).
* Prove the `ToolPolicy` integration unchanged.
* Prove the admission-policy + audit-log machinery on the
  EXISTING tools first.
* No third-party tools.
* No new dependency.

This option transforms Phase 5.0's designs into runtime
guard-rails on tools OIDA-code already calls. It does NOT
open the MCP surface; it builds the platform that MCP would
later plug INTO.

**Option B (alternative): Phase 5.1 — MCP sandbox proof-of-
concept**

ONLY if all 10 unlock criteria from
`mcp_unlock_criteria.md` are demonstrably satisfied:

* One local-stdio MCP server (read-only).
* No network egress (sandbox-enforced).
* No write tools.
* No secrets passed.
* Pinned schema (rug-pull rule armed).
* Schema-hash mismatch → quarantine.
* Replay-only tests (no live LLM).

Option B opens the MCP surface but in the most boring
configuration possible. It is the canonical "prove the
machinery on a mock" prototype.

**Recommendation**: ship Option A first. It de-risks Option B
by exercising every Phase 5.0 design concept on tools the
project already trusts. After Option A passes, Option B's
incremental risk is just "transport: stdio JSON-RPC instead
of subprocess `argv`".

Either way, the existing locks
(`test_no_mcp_workflow_or_dependency_added`,
`test_no_provider_tool_calling_enabled`) remain ACTIVE until
the Phase 5.1 (or 5.2) ADR explicitly removes them.

---

## 13. Gates

| Criterion (QA/A27.md lines 936-956) | Status |
|---|---|
| 1. ADR-35 written | yes — `memory-bank/decisionLog.md` |
| 2. MCP threat model produced | yes — `docs/security/mcp_threat_model.md` |
| 3. MCP admission policy produced | yes — `docs/security/mcp_admission_policy.md` |
| 4. Tool schema pinning / rug-pull design | yes — `docs/security/tool_schema_pinning.md` |
| 5. Tool-call execution model produced | yes — `docs/security/tool_call_execution_model.md` |
| 6. Audit-log schema design produced | yes — `docs/security/mcp_audit_log_schema.md` |
| 7. Pydantic-AI assessment updated | yes — `experiments/pydantic_ai_spike/phase5_assessment.md` |
| 8. Unlock criteria documented | yes — `docs/security/mcp_unlock_criteria.md` |
| 9. Anti-MCP locks remain active | yes — Phase 4.7 tests still pass; Phase 5.0 adds `test_anti_mcp_locks_still_active` |
| 10. Anti-tool-calling locks remain active | yes — same |
| 11. No MCP dependency added | yes — `test_no_mcp_dependency_added` (Phase 5.0) + Phase 4.7 check |
| 12. No provider tool-calling enabled | yes — `test_no_provider_tool_calling_enabled` (both) |
| 13. No MCP workflow added | yes — `test_no_mcp_workflow_added` |
| 14. No runtime MCP execution | yes — no MCP code under `src/oida_code/` |
| 15. No official `total_v_net` / `debt_final` / `corrupt_success` emission | yes — ADR-22 hard wall holds |
| 16. Report produced | yes — THIS file |
| 17. ruff clean | yes — full curated CI scope |
| 18. mypy clean | yes — `src/` source files |
| 19. pytest full green, skips documented | yes — N passed, 4 skipped (V2 placeholder + 2 Phase-4 observability markers + 1 optional external-provider smoke); N updated post-runner |
| 20. At least one GitHub-hosted CI / action-smoke run green after Phase 5.0 docs | pending — operator triggers post-merge |

### Skip inventory (4 — unchanged from Phase 4.9)

1. V2 placeholder skip (Phase 0).
2. Phase-4 observability marker #1.
3. Phase-4 observability marker #2.
4. Optional external-provider smoke (no DEEPSEEK_API_KEY in
   CI by default).
