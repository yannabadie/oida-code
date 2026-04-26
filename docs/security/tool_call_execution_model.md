# Tool-call execution model — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-D.
**Status**: design only. Phase 5.0 ships zero tool-execution
code beyond the existing Phase 4.2 deterministic adapters
(`src/oida_code/verifier/tools/`). This document specifies the
contract any future MCP / provider-tool-calling integration
must satisfy.

## 1. Core principle

The LLM **proposes**, OIDA-code **executes**. This separation
predates Phase 5.0 — it has been the architecture since Phase
4.0 (ADR-25) and Phase 4.2 (tool-grounded verifier loop). MCP
and provider tool-calling, when (and IF) they ever land, must
slot into the existing pipeline:

```
LLM proposes
  → policy validates
    → adapter executes
      → parser emits EvidenceItem
        → forward/backward verifier
          → aggregator decides
```

What is **forbidden** at every layer:

* the LLM picking a raw shell command and the host running it
* the LLM bypassing the policy (e.g., by inserting arguments
  the policy did not validate)
* the LLM seeing the API key, GITHUB_TOKEN, or any other
  credential directly
* the LLM writing `is_authoritative=True` on any claim
* the LLM writing or influencing `total_v_net` /
  `debt_final` / `corrupt_success` (ADR-22 hard wall)
* a provider returning an opaque "tool call" structure that
  bypasses the host's policy validation

## 2. Pipeline contract

Every external information source — provider, MCP tool, file
read, CLI execution — flows through this five-stage pipeline:

### Stage 1 — `request`

The LLM (or an internal trigger) emits a structured request:

```python
class VerifierToolRequest(BaseModel):
    tool_name: str            # MUST be in the local registry
    arguments: dict[str, Any]  # validated against locally-pinned schema
    proposed_by: Literal["llm", "operator", "deterministic"]
    case_id: str | None
```

For LLM-issued requests, the contract is: the LLM names a tool
and supplies arguments. It NEVER ships a shell command, a
function pointer, or an executable. This contract already
exists in `src/oida_code/verifier/tools/` for the Phase 4.2
deterministic adapters; MCP / provider-tool-calling MUST use
the same shape.

### Stage 2 — `policy`

`ToolPolicy` (existing, in `src/oida_code/verifier/tools/`) is
the only authority that decides "is this tool callable?". The
policy validates:

1. `tool_name` is in the allowlist for the current execution
   mode (see §3 below).
2. `arguments` validates against the locally-pinned
   `input_schema_sha256` (when MCP) or against the adapter's
   declared schema (when local-deterministic).
3. The execution would not exceed budget (timeout, memory,
   call count).
4. The execution does not require a credential the host
   has decided not to issue (no GITHUB_TOKEN passthrough, no
   broad OAuth scopes).
5. The execution context allows it (see §4 — no execution on
   fork PRs, etc.).

A failure at Stage 2 emits an `MCPAuditEvent` with
`policy_decision="block"` (or `"quarantine"` for hash drift)
and short-circuits — the tool is not invoked.

### Stage 3 — `adapter`

If Stage 2 passes, the tool is invoked through a deterministic
**adapter**. For local tools (`ruff`, `mypy`, `pytest`,
`semgrep`, `codeql`, `hypothesis`, `mutmut`), the adapter is
the existing `src/oida_code/verify/<tool>_runner.py`. For
MCP-sourced tools (Phase 5.x), the adapter is a new
`src/oida_code/mcp/adapters/<tool_name>.py` that:

* establishes the stdio subprocess (no network)
* sends the JSON-RPC `tools/call` with the
  Stage-2-validated arguments
* parses the response against the locally-pinned
  `output_schema_sha256`
* enforces the per-call timeout (subprocess kill on
  timeout)
* writes the `MCPAuditEvent`

The adapter is the **only** code path that knows about MCP /
JSON-RPC. Everything above (policy, request shape) and below
(evidence, aggregator) is unaware of the transport.

### Stage 4 — `parser` → `EvidenceItem`

The validated tool output is wrapped in an `EvidenceItem`
carrying:

* `kind="tool_output"` (or `kind="mcp_tool_output"` if a
  future schema bump distinguishes)
* `tool_name`
* `case_id`
* the output content (post-canonicalisation, post-redaction)

Output content is fenced via the existing prompt-injection
defence (Phase 4.0.1, ADR-26): every byte is wrapped in
`<<<OIDA_EVIDENCE id="..." kind="tool_output">>> ...
<<<END_OIDA_EVIDENCE id="...">>>`, with `_neutralise_fence_close`
applied so a tool output that ECHOES the close marker cannot
truncate the fence. Forbidden-phrase scan runs on every
output.

### Stage 5 — `aggregator`

The `EvidenceItem` is fed to the existing forward/backward
verifier (`src/oida_code/verifier/`). The aggregator
(`VerifierAggregationReport`) remains the sole source of truth.
Its `is_authoritative` field stays `Literal[False]` — no MCP
output, no provider tool-call output, can flip it.

## 3. Five execution modes

Every tool source (deterministic local, MCP, provider-issued)
operates in one of five modes. Phase 5.0 only authorises modes
0 and 1 (in design). Phase 5.x designs may unlock 2 with
explicit ADR; modes 3 and 4 are deferred indefinitely.

### Mode 0 — `disabled`

Default. Tool source is registered but cannot be invoked. The
admission policy may compute fingerprints and run static
inspections, but `tools/call` is not issued. Phase 5.0
production: every MCP server is mode 0.

### Mode 1 — `schema-discovery only`

The host MAY issue `tools/list`, `resources/list`, and
`prompts/list` to compute fingerprints and prepare an
admission decision. NO `tools/call`, NO `resources/read`, NO
`prompts/get`. This is the mode under which an operator
inspects a candidate server before approval.

Phase 5.0 design recognises this mode but does NOT ship
runtime support. The `oida-code mcp inspect` pseudocode
described in `mcp_admission_policy.md` §8 implements this
mode.

### Mode 2 — `read-only deterministic tools`

After admission with `risk_level="read_only"`, tools that the
admission policy classified as read-only (no filesystem write,
no shell execution, no network egress, no credential access)
become invocable. Each call still goes through Stages 1-5.

Phase 5.0 design ONLY: this mode is the recommended ceiling
for any first Phase 5.1 prototype. The unlock criteria
document (`mcp_unlock_criteria.md`) lists what must hold
before mode 2 ships.

### Mode 3 — `approved deterministic tools`

Tools that may have side-effects beyond read-only (e.g.,
writing to a scratch directory, creating a temp file) but
whose adapter is fully deterministic and bounded. Reserved
for future ADR; explicitly out of scope for Phase 5.x near-
term roadmap.

### Mode 4 — `human-approved write tools`

Write / destructive operations: create PR, modify branch,
close issue, trigger deployment. Each call requires a fresh
human approval (operator presses "approve" per call, not just
per server). Reserved indefinitely; this is the mode where an
unbounded autonomous loop becomes possible, and OIDA-code's
mission (verification, not action) does not require it.

## 4. Context restrictions

Even in modes 1 / 2, MCP tool execution is forbidden in the
following contexts. These mirror the existing fork-PR fence
(Phase 4.5, ADR-30) and extend it.

| Context | MCP / tool-calling allowed? |
|---|---|
| `pull_request` from a fork | **forbidden** |
| `pull_request_target` | **forbidden** |
| `push` (default branch or otherwise), no operator opt-in | **forbidden** |
| `action-smoke.yml` default path | **forbidden** |
| `workflow_dispatch` with explicit `mcp-enable=true` input | allowed (Phase 5.x) |
| Local CLI invoked by the operator with explicit `--mcp` flag | allowed (Phase 5.x) |
| Protected branch with read-only permissions | allowed (Phase 5.x) |

The reason: GitHub Actions' `pull_request_target` event runs
in the context of the base repository with full secret
access. Combining that with MCP execution would give a fork
PR's author an indirect path to influence host-side tool
calls, which is exactly the **confused deputy** class.

## 5. Provider tool-calling

DeepSeek V4 Pro / V4 Flash, OpenAI-compatible providers
generally, and most modern LLMs ship native function-calling
support. Pydantic-AI in particular makes function tools the
canonical surface. Phase 5.0 design forbids enabling that
surface in OIDA-code:

```yaml
# Phase 5.0 design rule (locked by tests)
ProviderProfile.supports_tools: False  # all profiles, all configs
```

The reason: a provider's tool-call surface comes with TWO
properties OIDA-code does not want:

1. **Provider-defined tools**. Some providers ship "browse",
   "code interpreter", or "file search" tools as built-ins.
   Enabling tool-calling implicitly enables these unless the
   API request strips them. Per provider, the strip-list is
   inconsistent.
2. **Provider-issued command strings**. The model's tool-call
   payload is opaque from the host's perspective unless the
   host strictly validates `function_name` against a local
   allowlist AND `arguments` against a local schema. The
   host code path that validates tool calls IS a fresh attack
   surface that did not previously exist.

If provider tool-calling ever ships in Phase 5.x, the contract
is the same as MCP:

* `function_name` MUST be in a local allowlist with the same
  per-tool fingerprint pinning as MCP.
* `arguments` MUST validate against a locally-pinned schema.
* The host's adapter executes — never the provider's tool
  registry.
* The aggregator still decides; the provider's tool call is
  just one `EvidenceItem`.

A provider returning a tool-call request the host does not
recognise → block, audit event with `reason="unknown
function_name"`, NEVER auto-allow.

## 6. What the LLM is forbidden to say

The host's prompt template (Phase 4.0.1, ADR-26) already
fences the LLM into a constrained output shape
(`LLMEstimatorOutput` Pydantic model). For MCP / tool-calling
purposes, the additional forbidden phrases (locked by the
existing `forbidden_claims` list) include:

* `run this shell command`
* `call this MCP server`
* `write this file`
* `upload this artifact`
* `mark this PR safe`
* `merge_safe`, `production_safe`, `bug_free`,
  `security_verified`
* `verified` (as a status word, not as part of "I can
  verify that...")

A response containing any of these is rejected by the
existing strict runner (Phase 4.0.1).

## 7. Audit-log linkage

Every Stage 3 invocation produces exactly one
`MCPAuditEvent` (`mcp_audit_log_schema.md`). Stage 2 blocks
also produce events (with `policy_decision="block"` or
`"quarantine"`). Stages 1 / 4 / 5 do NOT produce MCP-specific
audit events — Stage 1's request is recorded in the
`EstimatorRun` / `VerifierRun` traces, Stages 4 / 5 in the
existing aggregator's records.

This means: every byte that crosses an MCP / tool-call
boundary is auditable. No invisible execution.

## 8. Concrete deferral list

What Phase 5.0 design EXPLICITLY does not include:

* No subprocess spawn
* No JSON-RPC parser
* No `oida-code mcp` CLI subcommands
* No `src/oida_code/mcp/` package
* No `src/oida_code/verifier/tools/mcp_adapter.py`
* No new dependency in `pyproject.toml`
* No new workflow under `.github/workflows/`
* No test that EXECUTES an MCP tool (even a mock)
* No `supports_tools=True` on any `ProviderProfile`

The existing locks
(`test_no_mcp_workflow_or_dependency_added`,
`test_no_provider_tool_calling_enabled`) remain ACTIVE and
will be extended in Phase 5.0's test set
(`tests/test_phase5_0_design.py`) to cover the new design
docs.

---

**Honesty statement**: this document is a contract for future
implementations, not an implementation. The aggregator
remains the only authority for OIDA-code conclusions; MCP and
provider tool-calling, when (and IF) they ever ship, do not
elevate any external party above that authority. The
`is_authoritative: Literal[False]` pin on
`VerifierAggregationReport` is unchanged.
