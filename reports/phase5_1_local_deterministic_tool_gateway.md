# Phase 5.1 — Local deterministic tool gateway (ADR-36)

QA/A28.md scope. Phase 5.1 implements a runtime tool gateway
that wraps OIDA-code's existing deterministic adapters
(`ruff` / `mypy` / `pytest`) behind admission, schema-
fingerprinting, and audit-log layers. **It does not implement
MCP.** It transforms Phase 5.0's design documents into runtime
guard-rails on tools the project already trusts.

---

## Honesty statement (locked by QA/A28 lines 449-458)

* Phase 5.1 implements a local deterministic tool gateway for
  existing tools.
* It does not implement MCP.
* It does not enable provider tool-calling.
* It does not execute remote tools.
* It does not allow write tools or network egress.
* It does not validate production predictive performance.
* It does not emit official `total_v_net`, `debt_final`, or
  `corrupt_success`.
* It does not modify the vendored OIDA core.

---

## 1. Diff summary

| Area | File | Change | Lines |
|---|---|---|---|
| 5.1.0-A doc sync | `reports/phase5_0_mcp_tool_calling_design.md` | `~13 tests` → `16 tests`; §10 enumerated list updated to cover all 16 actual tests | ~+10/-3 |
| 5.1-A contracts | `src/oida_code/verifier/tool_gateway/contracts.py` | NEW — `GatewayToolDefinition` + `ToolSchemaFingerprint` (runtime variant) + `ToolAdmissionDecision` + `ToolAdmissionRegistry` + `ToolGatewayAuditEvent` | ~+220 |
| 5.1-B fingerprints | `src/oida_code/verifier/tool_gateway/fingerprints.py` | NEW — `canonical_json_sha256`, `fingerprint_tool_definition`, `compare_fingerprints` | ~+125 |
| 5.1-C admission | `src/oida_code/verifier/tool_gateway/admission.py` | NEW — `admit_tool_definition` with 7 rules in QA-prescribed order; suspicious-pattern detection | ~+150 |
| 5.1-D audit log | `src/oida_code/verifier/tool_gateway/audit_log.py` | NEW — `build_audit_event`, `append_audit_event`, `read_audit_events`, `audit_log_path` | ~+135 |
| 5.1-E gateway | `src/oida_code/verifier/tool_gateway/gateway.py` | NEW — `LocalDeterministicToolGateway.run()` returning `VerifierToolResult` | ~+225 |
| Package | `src/oida_code/verifier/tool_gateway/__init__.py` | NEW — re-exports | ~+25 |
| 5.1-F CLI | `src/oida_code/cli.py` | NEW Typer sub-app `tool-gateway` with `fingerprint` + `run` subcommands; new `_builtin_gateway_definitions` helper | ~+265 |
| Tests | `tests/test_phase5_1_tool_gateway.py` | NEW — 40 tests covering all 8 sub-blocks | ~+910 |
| ADR-36 | `memory-bank/decisionLog.md` | Appended | ~+95 |
| Phase 5.1 report | `reports/phase5_1_local_deterministic_tool_gateway.md` | THIS file | ~+450 |
| Docs | `README.md` + `memory-bank/progress.md` | Phase 5.1 status entries | ~+30 |

Net: ~+2640 lines added across 11 files.

---

## 2. 5.1.0 doc sync

### 5.1.0-A — audit log path

QA/A28 §5.1.0-A flagged the Phase 5.0 report's audit log path
as malformed (`.oida/mcp/audit///    /.jsonl`). The actual file
is correct — the path lives inside backticks and the angle-
bracket placeholders survive Markdown rendering. The "malformed"
appearance comes from a renderer that strips HTML-tag-shaped
tokens from inside code spans. The fix:

* Phase 5.1's runtime path uses a different namespace:
  `.oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl`
  (NOT `.oida/mcp/audit/...`). QA/A28 line 92 explicit:
  "car ce n'est pas MCP".
* `test_phase5_report_audit_log_path_is_not_malformed` asserts
  no `///` pattern in the Phase 5.0 report — the renderer-
  induced corruption signature.
* `test_audit_log_path_namespace_is_tool_gateway` asserts the
  runtime path lives under `tool-gateway/`, not `mcp/`.

### 5.1.0-B — test count sync

The Phase 5.0 report claimed `~13 tests`; the actual
`tests/test_phase5_0_design.py` has 16 tests. Fixed: both
occurrences (lines 361 + 378) now say `16 tests`; §10's
enumerated list expanded from 13 to 16 entries (added
`test_no_mcp_runtime_import_in_src`,
`test_no_official_fields_emitted`,
`test_phase5_report_declares_no_code_mcp`).
`test_phase5_report_test_count_matches_test_file` is a
regression check that re-counts the test file and compares.

---

## 3. ADR-36 excerpt

See `memory-bank/decisionLog.md` for the full ADR. Decision
summary:

> Phase 5.1 implements a local deterministic tool gateway
> around OIDA-code's existing tool adapters. It applies Phase
> 5.0's admission, schema pinning and audit-log designs
> without adding MCP runtime, remote servers, or provider
> tool-calling.

Accepted: local tools only; ruff/mypy/pytest at minimum;
semgrep/codeql optional via existing `get_adapter()`; tool
schema fingerprints; admission registry; hash drift
quarantine; audit log per tool decision; reuse existing
`ToolPolicy`; evidence item outputs only; no MCP protocol.

Rejected: MCP SDK dependency; JSON-RPC `tools/list` /
`tools/call`; remote MCP servers; provider tool-calling;
write tools; network egress; official `total_v_net` /
`debt_final` / `corrupt_success`.

---

## 4. Gateway contracts (5.1-A)

The runtime contracts module (`contracts.py`) defines five
Pydantic shapes. All are frozen with `extra="forbid"`.

### 4.1 `GatewayToolDefinition`

The static identity of a tool. Two `Literal[False]` pins make
write/network-class definitions structurally
unrepresentable:

```python
class GatewayToolDefinition(BaseModel):
    tool_id: str
    tool_name: ToolName  # Phase 4.2 allowlist: ruff/mypy/pytest/semgrep/codeql
    adapter_version: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: GatewayRiskLevel  # read_only | sensitive_read | write_forbidden
    allowed_scopes: tuple[str, ...]
    requires_network: Literal[False] = False
    allows_write: Literal[False] = False
```

### 4.2 `ToolSchemaFingerprint` (runtime variant)

Distinct from the design-only `ToolSchemaFingerprint` in
`docs/security/tool_schema_pinning.md` (which describes MCP-
shape fingerprints with `server_id` / OAuth scopes etc.). The
runtime variant adds a `combined_sha256` computed over the
three individual hashes:

```python
class ToolSchemaFingerprint(BaseModel):
    tool_id: str
    tool_name: str
    adapter_version: str
    description_sha256: str        # 64-char hex
    input_schema_sha256: str       # 64-char hex
    output_schema_sha256: str      # 64-char hex
    combined_sha256: str           # SHA256("description:H1|input:H2|output:H3")
```

A future reader who finds both schemas must understand the
distinction: the design-only one is for hypothetical MCP
servers; the runtime one is for local adapters. The module
docstring documents this.

### 4.3 `ToolAdmissionDecision`

The outcome of admission for a single (tool, fingerprint) pair.
`status` is restricted to `Literal["approved_read_only" |
"quarantined" | "rejected"]` — Mode 3 (deterministic with
side-effects) and Mode 4 (write) tier upgrades require a
schema bump and a new ADR.

### 4.4 `ToolAdmissionRegistry`

The set of decisions the gateway loads at startup. Three
parallel tuples (`approved` / `quarantined` / `rejected`) keep
the JSON file human-readable.

### 4.5 `ToolGatewayAuditEvent`

One event per Stage-2 decision. The schema deliberately has no
`request_arguments` / `raw_stdout` / `api_key` fields —
inviting secret leakage by design is exactly what Phase 5.0
rejected. `request_summary` is short, human-readable;
`evidence_refs` carry only `EvidenceItem.id` strings.

---

## 5. Fingerprinting / schema pinning (5.1-B)

The fingerprinting module uses a **JCS-approximation**:

```python
def _canonical_dumps(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
```

This is **not** strict RFC 8785 JCS. The corner cases JCS
handles that this approximation does not:

* IEEE 754 number canonical form (shortest round-trip).
* Unicode NFC normalisation.
* `\uD800` surrogate handling.

For local adapters (Phase 5.1 scope), the inputs are bounded
— tool definitions live in vendored Python code that already
passes Pydantic validation. The corner cases do not apply.
**A future MCP integration that ingests third-party schemas
MUST swap to strict JCS** before relying on this hashing
layer; the module docstring is explicit about this.

`compare_fingerprints` returns `Literal["match", "drift"]`. Any
divergence on `tool_id`, `description_sha256`,
`input_schema_sha256`, `output_schema_sha256`, OR
`combined_sha256` produces `"drift"`; the admission layer
translates that to `quarantined`.

---

## 6. Admission registry (5.1-C)

`admit_tool_definition` runs the seven rules in QA/A28
§5.1-C lines 222-228 verbatim. Rule order matters: rule 7
(suspicious description) precedes rule 1 (missing fingerprint)
because a poisoned description must be REJECTED outright, not
quarantined for operator review.

Rule sequence:

1. Suspicious description match → **rejected** (precedence
   over fingerprint logic).
2. `risk_level != "read_only"` → **rejected**.
3. `requires_network=True` → **rejected** *(unreachable;
   pinned `Literal[False]` at the schema level — kept
   defensively)*.
4. `allows_write=True` → **rejected** *(same)*.
5. `expected_fingerprint is None` → **quarantined**.
6. fingerprint match → **approved_read_only**.
7. fingerprint drift → **quarantined**.

### Suspicious-pattern detection

```python
_SUSPICIOUS_PATTERNS = (
    re.compile(r"ignore\s+(the\s+)?(previous|above|system|developer)\s+"
               r"(instruction|policy|prompt|rule)", re.IGNORECASE),
    re.compile(r"override\s+policy", re.IGNORECASE),
    re.compile(r"send\s+secrets", re.IGNORECASE),
    re.compile(r"\bexfiltrate\b", re.IGNORECASE),
    re.compile(r"execute\s+shell", re.IGNORECASE),
    re.compile(r"(^|\s)write\s+file(\s|$|\.|,)", re.IGNORECASE),
    re.compile(r"<<<(OIDA_EVIDENCE|END_OIDA_EVIDENCE)"),
)
```

The last pattern catches inner copies of the OIDA evidence
fence — a tool description that includes those tokens would
truncate the LLM's prompt context if it ever reached the
prompt template (Phase 4.0.1, ADR-26).

---

## 7. Audit log runtime (5.1-D)

```
.oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl
```

Storage: per-day per-tool JSONL append-only files. One line
per Stage-2 decision (allow / block / quarantine / reject).
The runtime path is intentionally distinct from the
hypothetical `.oida/mcp/audit/...` namespace from the Phase
5.0 design — Phase 5.1 is NOT MCP.

### Redaction posture

The schema has no field that could legitimately carry a
secret:

* `request_summary`: short, human-readable, redacted UPSTREAM
  by the caller (Phase 5.1's `_summarise_request` includes
  only `tool` + `scope` + `purpose`, NEVER raw arguments).
* `tool_schema_hash`: 64-char SHA256 — not a secret.
* `evidence_refs`: tuple of `EvidenceItem.id` strings — IDs
  only, no payload.
* `reason`: short class-name string ("sandbox violation:
  ...", "fingerprint drift — ...").

The schema has NO `request_arguments`, `raw_stdout`, or
`api_key` field, asserted by
`test_audit_event_contains_no_secret_like_values`.

### JSONL round-trip

`read_audit_events` is the read side. Lines that fail to
parse are silently skipped (the audit log is presentation, not
validation — corruption surfaces via re-run). Multiple events
appended to the same per-day file round-trip cleanly, locked
by `test_audit_log_jsonl_roundtrip`.

---

## 8. Execution wrapper (5.1-E)

`LocalDeterministicToolGateway.run()` returns
`VerifierToolResult` exactly. **No new wrapper type.** The
gateway is a wrapper around the existing engine; from the
aggregator's perspective, nothing changed.

### Five-stage pipeline

```
VerifierToolRequest
  → Stage 1: registry lookup (find approved decision for tool_id)
    → Stage 2: hash drift check (observed vs approved fingerprint)
      → Stage 3: existing validate_request (sandbox)
        → Stage 4: existing get_adapter().run() (existing adapter)
          → Stage 5: emit audit event + return VerifierToolResult
```

Each failure mode is testable independently:

| Failure | Stage | Test |
|---|---|---|
| No approved decision | 1 | `test_gateway_blocks_unapproved_tool` |
| Hash drift | 2 | `test_gateway_quarantines_hash_drift` |
| Path traversal | 3 | `test_gateway_reuses_existing_tool_policy_path_traversal_block` |
| Secret-path scope | 3 | `test_gateway_reuses_existing_tool_policy_secret_path_block` |
| Adapter exception | 4 | (defensive — unhandled exception → block) |
| `tool_missing` (uncertainty, NOT failure) | 4 | `test_gateway_tool_missing_is_uncertainty` |
| Success path | 5 | `test_gateway_runs_approved_ruff_tool` |

### Sandbox reuse

The gateway calls `validate_request` from
`src/oida_code/verifier/tools/sandbox.py` rather than re-
implementing path traversal / secret-path checks. This means
a future fix to a deny pattern propagates automatically; no
code drift between the verifier-engine and the gateway.

### `shell=True` lock

`test_gateway_never_uses_shell_true` greps every Python file
under the gateway package for `shell=True`. The existing
adapters compose argv as tuples; nothing in the gateway can
introduce a shell passthrough without breaking this test.

---

## 9. CLI usage (5.1-F)

Two subcommands under a Typer sub-app:

### `oida-code tool-gateway fingerprint`

```bash
oida-code tool-gateway fingerprint \
  --out .oida/tool-gateway/fingerprints.json
```

Computes the four-hash fingerprint for each builtin tool
definition (ruff / mypy / pytest). Operator reviews the JSON
output, approves selected fingerprints into the registry, then
invokes `run`.

### `oida-code tool-gateway run`

```bash
oida-code tool-gateway run requests.json \
  --policy tool_policy.json \
  --approved-tools .oida/tool-gateway/approved_tools.json \
  --audit-log-dir .oida/tool-gateway/audit \
  --out .oida/tool-gateway/results.json
```

Drives a list of `VerifierToolRequest` objects through the
gateway. Each request is admitted against `--approved-tools`,
sandbox-validated against `--policy`, and dispatched to the
existing adapter. One audit event per decision lands under
`--audit-log-dir`. Results write to `--out` as JSON.

### Why two subcommands

The split makes visible the difference between:

* **observed**: the tool definitions as the gateway sees them
  right now (`fingerprint`'s output).
* **approved**: the operator-signed subset the gateway is
  allowed to invoke (`--approved-tools` input).
* **executed**: the actual calls the gateway dispatched
  (audit log + `--out` results).

A single subcommand that did both would conflate "what's
available" with "what's authorized".

---

## 10. No-MCP regression locks (5.1-G)

Six new tests assert the gateway is NOT MCP:

* `test_tool_gateway_is_not_mcp_server` — no `mcp_server` /
  `model-context-protocol` strings in the gateway code.
* `test_tool_gateway_does_not_import_mcp` — no `import mcp`
  / `from mcp ...` / `import pydantic_ai` /
  `from pydantic_ai ...` under the gateway package.
* `test_tool_gateway_has_no_tools_list_jsonrpc` — no
  `"tools/list"` JSON-RPC method binding.
* `test_tool_gateway_has_no_tools_call_jsonrpc` — no
  `"tools/call"` JSON-RPC method binding.
* `test_tool_gateway_has_no_remote_transport` — no `urllib`
  / `http` / `httpx` / `requests` / `websockets` / `aiohttp`
  imports under the gateway package.
* `test_tool_gateway_has_no_provider_tool_calling` — re-
  affirms `supports_tools=True` is absent from
  `provider_config.py`.

These complement (do NOT replace) the existing Phase 4.7 +
Phase 5.0 anti-MCP locks. Removal of any lock requires a
named ADR + the corresponding criterion from
`docs/security/mcp_unlock_criteria.md`.

---

## 11. Security review

### What this phase changed

* Added `src/oida_code/verifier/tool_gateway/` (~1200 LOC).
  Every module is local-only: no network imports, no
  subprocess primitives beyond what the existing adapters
  already use, no environment-variable reads.
* Added two CLI subcommands (`tool-gateway fingerprint` /
  `tool-gateway run`). Both are operator-driven; neither
  triggers automatically on `push` or `pull_request`.
* Added `.oida/tool-gateway/audit/` as the audit log
  directory. JSONL files are append-only; existing entries
  are never mutated.

### What this phase did NOT change

* No new dependency in `pyproject.toml`.
* No new workflow under `.github/workflows/`.
* No external network call.
* No change to `provider_config.py` (`supports_tools` stays
  `False`).
* No change to existing `ToolPolicy` / `validate_request` /
  adapter behaviour.
* No change to ADR-22 hard wall (`total_v_net` /
  `debt_final` / `corrupt_success` remain blocked).
* No change to Phase 4.5 fork-PR fence.

### Tests asserting the security envelope

* `test_gateway_never_uses_shell_true`
* `test_gateway_reuses_existing_tool_policy_path_traversal_block`
* `test_gateway_reuses_existing_tool_policy_secret_path_block`
* `test_audit_event_contains_no_secret_like_values`
* `test_tool_gateway_run_cli_no_official_fields`
* `test_tool_gateway_does_not_import_mcp`
* `test_tool_gateway_has_no_remote_transport`

---

## 12. What this still does NOT implement

(In addition to the §honesty statement.)

* **No MCP runtime**. The gateway is NOT an MCP server / NOT
  an MCP client / does NOT speak JSON-RPC. The Phase 5.0
  designs (`docs/security/mcp_threat_model.md` etc.) describe
  MCP; Phase 5.1 implements local deterministic guard-rails
  on tools the project already calls.
* **No verifier-loop integration**. Phase 5.1 ships the
  gateway as a library + CLI. The existing
  `ToolExecutionEngine` (in
  `src/oida_code/verifier/tools/__init__.py`) still
  invokes adapters directly. Phase 5.2 (per QA/A28 line 511)
  routes verifier requests through the gateway.
* **No write / network capability**. Modes 3 and 4 from the
  Phase 5.0 execution model
  (`docs/security/tool_call_execution_model.md` §3) are NOT
  authorised. Mode 1 (schema-discovery) is implemented via
  the `tool-gateway fingerprint` subcommand; mode 2
  (read-only) is the only invocation tier.
* **No sandbox primitive enforcement**. The
  `secret_access_attempted` / `network_access_attempted` /
  `write_access_attempted` capability sentinels in the audit
  event default to `False`; a future Phase 5.x sandbox
  primitive (Linux namespaces / macOS sandbox-exec /
  similar) MUST set them to `True` when the runtime detects
  the attempt. Phase 5.1 audit events have these flags
  always-`False` because the gateway uses the existing
  subprocess executor without sandbox-level instrumentation.
* **No tamper-evident audit log**. The audit JSONL is
  append-only at the filesystem level; a compromised host
  process could replace a line. Phase 5.x may add SHA-chained
  entries.

---

## 13. Recommendation for Phase 5.2

Per QA/A28 line 511-518, the next phase is:

> Phase 5.2 — gateway integration into verifier loop
>
> Objectif: run verifier tool requests through the gateway,
> not directly through the old engine.
>
> Toujours pas MCP.

Concretely:

1. Add a `use_gateway: bool = False` flag to the existing
   `ToolExecutionEngine` (or a similar opt-in path).
2. When the flag is set, route each request through
   `LocalDeterministicToolGateway.run()` instead of the
   direct `adapter.run()` call.
3. Confirm the existing aggregator continues to consume the
   `VerifierToolResult` unchanged (the gateway returns the
   same type — locked by Phase 5.1 tests).
4. Run the calibration-eval matrix with the gateway path
   enabled to confirm metrics are unchanged (the gateway
   adds admission + audit, not measurement changes).
5. Once the gateway path is operationally green for at least
   one CI cycle, flip `use_gateway` default to `True`.
6. Phase 5.2 is still NOT MCP — `test_no_mcp_workflow_or_dependency_added`
   stays active throughout.

After Phase 5.2 lands, the unlock criteria from
`docs/security/mcp_unlock_criteria.md` will have demonstrably
been satisfied for criteria 6 (audit log schema accepted), 7
(allowlist-only tool registry accepted), and 9 (failure mode
tests specified). At that point, a Phase 5.3 ADR could
propose an MCP sandbox proof-of-concept (Option B from
QA/A27 line 985) — but only with a separate ADR explicitly
removing the relevant locks.

---

## 14. Gates

| Criterion (QA/A28 lines 459-489) | Status |
|---|---|
| 1. 5.1.0 doc sync done | yes — Phase 5.0 report `~13 → 16`; enumerated test list expanded; runtime path is `tool-gateway/`, not `mcp/` |
| 2. ADR-36 written | yes — `memory-bank/decisionLog.md` |
| 3. `GatewayToolDefinition` schema added | yes — `contracts.py` |
| 4. `ToolSchemaFingerprint` runtime impl added | yes — `contracts.py` + `fingerprints.py` |
| 5. Fingerprints stable under key order changes | yes — `test_fingerprint_is_stable_across_key_order` |
| 6. Fingerprint drift quarantines tool | yes — `test_hash_drift_quarantines_tool` + `test_gateway_quarantines_hash_drift` |
| 7. `ToolAdmissionDecision` / registry added | yes — `contracts.py` |
| 8. Write tools rejected | yes — `Literal[False]` pin + `test_write_tool_rejected` |
| 9. Network tools rejected | yes — `Literal[False]` pin + `test_network_tool_rejected` |
| 10. Prompt-injection description rejected/quarantined | yes — `test_prompt_injection_in_tool_description_rejected` |
| 11. `ToolGatewayAuditEvent` schema added | yes — `contracts.py` |
| 12. Audit log JSONL emitted for allowed tools | yes — `test_audit_event_written_for_allowed_tool` |
| 13. Audit log JSONL emitted for blocked/quarantined tools | yes — `test_audit_event_written_for_blocked_tool` + `test_gateway_quarantines_hash_drift` |
| 14. Audit log contains no secret-like values | yes — `test_audit_event_contains_no_secret_like_values` |
| 15. `LocalDeterministicToolGateway` added | yes — `gateway.py` |
| 16. Gateway reuses existing `ToolPolicy` blocks | yes — `test_gateway_reuses_existing_tool_policy_path_traversal_block` + `_secret_path_block` |
| 17. Gateway executes ruff/mypy/pytest through existing adapters | yes — `test_gateway_runs_approved_ruff_tool` (other adapters use the same `get_adapter()` registry, no per-tool gateway code) |
| 18. Gateway output is `EvidenceItem` / `VerifierToolResult` only | yes — `test_gateway_runs_approved_ruff_tool` asserts `isinstance(result, VerifierToolResult)` |
| 19. CLI fingerprint command added | yes — `test_tool_gateway_fingerprint_cli_outputs_hashes` |
| 20. CLI run command added | yes — `test_tool_gateway_run_cli_requires_approved_tools` + `_writes_audit_log` |
| 21. No MCP dependency added | yes — Phase 5.0 + 5.1 lock tests |
| 22. No MCP workflow added | yes — Phase 5.0 + 5.1 lock tests |
| 23. No provider tool-calling enabled | yes — `test_tool_gateway_has_no_provider_tool_calling` |
| 24. No JSON-RPC tools/list or tools/call runtime | yes — `test_tool_gateway_has_no_tools_list_jsonrpc` + `_call_jsonrpc` |
| 25. No official `total_v_net` / `debt_final` / `corrupt_success` emitted | yes — `test_tool_gateway_run_cli_no_official_fields` + Phase 5.0's `test_no_official_fields_emitted` |
| 26. Report produced | yes — THIS file |
| 27. ruff clean | yes — full curated CI scope |
| 28. mypy clean | yes — 88 source files |
| 29. pytest full green, skips documented | yes — 685 passed, 4 skipped (V2 placeholder + 2 Phase-4 observability markers + 1 optional external-provider smoke) |
| 30. At least one GitHub-hosted CI / action-smoke run green after Phase 5.1 | pending — operator triggers post-merge |

### Skip inventory (4 — unchanged from Phase 5.0)

1. V2 placeholder skip (Phase 0).
2. Phase-4 observability marker #1.
3. Phase-4 observability marker #2.
4. Optional external-provider smoke (no DEEPSEEK_API_KEY in CI by default).
