# Pydantic-AI assessment — Phase 5.0 (ADR-35)

**Authority**: ADR-35, QA/A27.md §5.0-E.
**Status**: assessment only. Phase 5.0 does NOT migrate the
runtime to Pydantic-AI; it does NOT add Pydantic-AI to the
project's dependencies; it does NOT enable provider tool-
calling. This document extends `experiments/pydantic_ai_spike/
README.md` with seven Phase-5-specific evaluation questions
and records the recommendation.

## 1. Phase 4.8-F context recap

The Pydantic-AI spike was created as a Phase 4.8-F documentary
artifact (ADR-33). The constraints encoded there:

* Stays OUTSIDE `src/oida_code/`.
* NOT installed by `pip install -e ".[dev]"`.
* NOT covered by ruff / mypy in the project's gates.
* `adapter_sketch.py` documents the migration shape but does
  NOT execute (requires the operator's local
  `pip install pydantic-ai`).

ADR-32's reconciliation requirements that any future
Pydantic-AI adapter MUST preserve:

* Same `LLMEstimatorOutput` schema (frozen, `extra="forbid"`).
* Same forbidden-phrase rejection set.
* Same confidence caps (LLM-only ≤ 0.6, hybrid ≤ 0.8).
* Same evidence-ref citation rule.
* ZERO tool calling enabled (`tools=[]`).
* ZERO "authoritative" output (`is_authoritative: Literal[False]`).

## 2. The seven Phase 5 evaluation questions

Per QA/A27.md §5.0-E lines 762-768, the assessment must answer:

### Q1 — Can Pydantic-AI produce the same `LLMEstimatorOutput`?

**Yes**, via `Agent(result_type=LLMEstimatorOutput)`.
Pydantic-AI's structured output uses the same Pydantic v2
infrastructure OIDA-code already depends on; the
`extra="forbid"` config and field validators carry through.

The schema comes from `src/oida_code/estimators/llm_contract.py`
where `LLMEstimatorOutput` is defined as a frozen Pydantic
model. Pydantic-AI consumes it directly without translation.

### Q2 — Can it preserve `evidence_refs`?

**Yes, with caveats**. Pydantic-AI's structured output preserves
field shapes including the `evidence_refs: tuple[str, ...]`
field on each `SignalEstimate`. The caveats:

* Pydantic-AI's `Agent` may, under some provider configurations,
  RETRY a response that fails Pydantic validation; this can
  mask the original schema-violation count which Phase 4.7's
  metrics depend on. Disabling retries (`retries=0`) is a
  Pydantic-AI configuration option that the adapter MUST set.
* The citation cross-check (each `evidence_refs` entry MUST be
  in the packet's `evidence_ids`) is a domain rule, not a
  shape rule. Pydantic-AI's validation does NOT enforce this;
  the existing `_validate_citations` post-validator must still
  run.

### Q3 — Can it forbid `authoritative=True`?

**Yes, structurally**. The `LLMEstimatorOutput` schema already
pins `is_authoritative: Literal[False]` (per ADR-22 / ADR-24).
Pydantic-AI's structured output respects the Literal, rejecting
any provider response that attempts `True`. No additional
Pydantic-AI configuration is needed to enforce this.

### Q4 — Can it keep tool-calling disabled?

**Yes — but the surface is the entire reason for caution**.
Pydantic-AI's `Agent` accepts a `tools=[]` parameter to disable
function tools. Setting `tools=[]` AT CONSTRUCTION suffices; the
Pydantic-AI documentation confirms function tools are off by
default unless explicitly added.

The risk: Pydantic-AI's `Toolset` API allows tools to be:

* registered at startup
* registered dynamically at runtime (e.g., from MCP)
* composed across servers
* overridden contextually (e.g., per-request)

This is exactly the surface that Phase 4.7 + Phase 5.0 design
explicitly avoid. An adapter MUST:

1. Construct `Agent` with `tools=[]`.
2. NEVER invoke any of Pydantic-AI's `Toolset` registration
   methods.
3. NOT consume Pydantic-AI's `MCPServerStdio` /
   `MCPServerSSE` / `MCPServerStreamableHTTP` toolset classes.
4. NOT set `pydantic_ai.Agent.system_prompt_to_request_message`
   to anything that delegates to a tool.

A test invariant would lock that the adapter never imports
`pydantic_ai.tools.*` or `pydantic_ai.mcp.*`. This is the
analogue of the existing `test_no_provider_tool_calling_enabled`
extended to Pydantic-AI's surface.

### Q5 — Can it run replay-only?

**Yes**, but it requires a custom `Model` adapter. Pydantic-AI
uses pluggable model backends (`openai:`, `anthropic:`, etc.).
A replay-only adapter would implement a custom backend reading
from `case.llm_response_path` and returning the canned response.

The current `FileReplayLLMProvider` (in
`src/oida_code/estimators/llm_provider.py`) does this directly;
re-implementing it via Pydantic-AI's plugin surface is more
verbose, not less. **Not a clear win for replay paths.**

### Q6 — Can it avoid MCP dynamic toolsets?

**Yes**, by NOT importing the MCP toolset module. Pydantic-AI's
MCP integration ships as separate import paths
(`pydantic_ai.mcp`); not importing them keeps the agent's
toolset closed.

A static check (e.g., a `test_no_pydantic_ai_mcp_import`) on
any future adapter under `src/oida_code/` enforces this. The
import would be the smoking-gun signal that someone tried to
re-introduce MCP via Pydantic-AI.

### Q7 — Can it preserve OIDA-code's `ToolPolicy`?

**Mostly yes**, with one architectural caveat.

OIDA-code's `ToolPolicy` (in `src/oida_code/verifier/tools/`)
is the host-side authority that decides which deterministic
tools are callable. Pydantic-AI's `tools=[]` configuration
keeps the LLM out of tool execution entirely; in that
configuration, `ToolPolicy` is uninvolved (no LLM-issued tool
calls means no tool requests to validate).

If a future Phase 5.x ADR enabled provider tool-calling
through Pydantic-AI, the policy boundary would have to be
preserved by:

* mapping every Pydantic-AI `Tool` definition to a
  `ToolSchemaFingerprint` (cf. `tool_schema_pinning.md`)
* running every `tools/call` through OIDA-code's `ToolPolicy`
  BEFORE Pydantic-AI dispatches the call to the underlying
  function
* writing the `MCPAuditEvent` (cf.
  `mcp_audit_log_schema.md`) before dispatch

The architecture caveat: Pydantic-AI's tool dispatch happens
INSIDE its agent loop, not at a clean boundary the host can
intercept. An adapter that needs to enforce `ToolPolicy` would
have to either:

* register every "tool" as a Pydantic-AI tool whose
  implementation FIRST runs the policy check (clean, but
  every tool wraps two layers)
* or fork Pydantic-AI's agent loop (avoid).

**Phase 5.0 recommendation**: tool-calling stays disabled, so
`ToolPolicy` integration with Pydantic-AI is a Phase 5.x ADR
question, not a Phase 5.0 blocker.

## 3. Final recommendation

> **`pydantic_ai_adapter_experiment`** — keep the spike alive
> as a documentary experiment; do NOT migrate the runtime in
> Phase 5.0; do NOT add Pydantic-AI to `pyproject.toml`.

### Rationale

* The seven evaluation questions all admit "yes, with
  configuration" answers. None of them surfaces a hard
  blocker.
* But the SAME questions surface that Pydantic-AI's value-add
  (structured output, retries, instrumentation) is partial —
  OIDA-code already has the structured-output schema; retries
  would mask schema-violation counts the existing metrics
  depend on; instrumentation would require additional
  `redact_secret` plumbing.
* The migration's ONE concrete win is reducing the size of
  `OpenAICompatibleChatProvider` (~395 LOC) by delegating
  HTTP / JSON / retry handling to Pydantic-AI. That win does
  NOT justify (a) adding a dependency that brings tool-calling
  surface; (b) re-validating 26+ provider tests after the
  swap; (c) re-running the Phase 4.8 multi-provider matrix
  (V4 Pro 8×2 + V4 Flash 8×1) under the new adapter.
* Phase 4.7-4.9 has stabilised the contract surface. Changing
  the runtime now would introduce a confounding variable in
  every measurement.

### What stays the same

* `OpenAICompatibleChatProvider` remains the production path.
* `experiments/pydantic_ai_spike/` remains documentary; no
  new code is added to it in Phase 5.0 beyond this assessment.
* Pydantic-AI is NOT added to `pyproject.toml` (any extra,
  including dev).
* `provider_config.py` keeps `supports_tools=False` for every
  profile.

### What would change later (Phase 5.x — IF an ADR proposes it)

* Vendor a thin Pydantic-AI adapter under `src/oida_code/
  estimators/providers/pydantic_ai_adapter.py` that:
  * Constructs `Agent(tools=[], result_type=LLMEstimatorOutput,
    retries=0)`.
  * Wraps every call in `redact_secret(body, key)` for the
    redacted-I/O hook (Phase 4.8-A schema unchanged).
  * Maps Pydantic-AI exceptions to the existing
    `LLMProvider*` exception family.
  * NEVER imports `pydantic_ai.tools.*` or
    `pydantic_ai.mcp.*`.
* Add a "blessed adapter" test that locks the `tools=[]`
  configuration AND the import-allowlist (no
  `pydantic_ai.tools` / `pydantic_ai.mcp` imports anywhere
  under `src/`).
* Extend the multi-provider matrix to compare
  `OpenAICompatibleChatProvider` (current) vs
  `PydanticAIChatProvider` (new) on the same 8 cases × 2
  repeats — same accuracy, same redaction posture, same
  exception mapping.
* Only AFTER the matrix converges, evaluate cutting over.

## 4. Cross-references

| Document | Anchor | Relevance |
|---|---|---|
| `experiments/pydantic_ai_spike/README.md` | full | Phase 4.8-F context |
| `experiments/pydantic_ai_spike/adapter_sketch.py` | SKETCH_NOTES | Adapter signature design |
| `docs/security/tool_call_execution_model.md` | §5 | "Provider tool-calling forbidden by default" — same logic applies to Pydantic-AI's tool surface |
| `docs/security/mcp_threat_model.md` | §8 open question 5 | "Does Pydantic-AI's MCPServerStdio satisfy our admission policy out-of-the-box?" |
| ADR-32 (memory-bank/decisionLog.md) | full | Locks Pydantic-AI as spike, not migration |
| ADR-33 (memory-bank/decisionLog.md) | spike entry | Phase 4.8-F creation rationale |

---

**Honesty statement**: this assessment recommends a
`pydantic_ai_adapter_experiment`-class follow-on as documented
research, NOT a Phase 5.x migration. Pydantic-AI is not added
to OIDA-code's dependencies in Phase 5.0; the existing
`OpenAICompatibleChatProvider` remains the production path; the
anti-tool-calling and anti-MCP locks remain active.
