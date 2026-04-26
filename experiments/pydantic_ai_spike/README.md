# Pydantic-AI spike (Phase 4.8-F)

**Authority**: ADR-33, QA/A25.md §4.8-F.
**Status**: spike, NOT a migration. The current
`OpenAICompatibleChatProvider` (Phase 4.4, ADR-29) and its 26+
existing tests stay the production path.

## Why a spike

QA/A25.md §4.8-F: "évaluer si Pydantic-AI peut remplacer ou
simplifier une partie du provider layer sans changer le
comportement". The user (operator) recommended Pydantic-AI as a
candidate during the Phase 4.7 session; this spike answers
whether a future migration would gain anything.

## Why NOT a migration today

Phase 4.7 just shipped the contract-compliant external provider
end-to-end (DeepSeek V4 Pro, run id 24953163352). Switching the
provider layer mid-Phase-4.8 would:

* invalidate the 26 existing Phase 4.4 provider tests
* change the surface ADR-29 froze
* re-introduce a class of risks Pydantic-AI's `Tools` /
  `Toolsets` exposes (tool-calling) that ADR-32 + the Phase 4.7
  anti-tool-calling tests explicitly lock out
* delay the empirical regression deepening that is the actual
  Phase 4.8 goal

The spike's job is to PRODUCE the data that justifies (or
contradicts) a future migration ADR.

## Out of `src/`

This directory is at repo root, NOT under `src/oida_code/`. The
project's `pip install -e ".[dev]"` does NOT pull pydantic-ai;
running the spike requires a separate `pip install pydantic-ai`
in the operator's local environment.

mypy and ruff DO NOT scan this directory in the project's gates
(see `pyproject.toml` `mypy.exclude`). Phase 4.8 deliberately
keeps the spike at sketch-quality; Phase 5.0 design ADR is where
spike outcomes get formalised.

## What the spike compares

| Surface | Current | Pydantic-AI candidate |
|---|---|---|
| HTTP transport | `urllib.request` + `http_post` injectable for tests | `httpx.AsyncClient` (pydantic-ai default) |
| Schema validation | `LLMEstimatorOutput.model_validate(json.loads(content))` | Native `result_type=LLMEstimatorOutput` agent param |
| Forbidden phrase fence | `_check_forbidden_phrases(raw)` runs after parse | Same — would still need to run after agent.run() returns |
| Citation rules | `_validate_citations(packet, parsed)` | Same — domain-specific, not framework-provided |
| Confidence cap (LLM-only ≤0.6) | `_apply_confidence_cap(parsed)` | Same — domain-specific |
| Redacted IO capture (Phase 4.8-A) | Provider-side, key in scope only there | Pydantic-AI runs the HTTP call internally; redaction would need a `Logfire`-style instrumentation hook |
| Secret redaction in errors | `redact_secret(text, key)` | Pydantic-AI raises typed exceptions; would need an exception filter wrapper |
| Tool calling | EXPLICITLY DISABLED (`supports_tools=False`) | Pydantic-AI `Agent(tools=[...])` is the framework's default — needs an empty list to match |

## Hard constraints from ADR-32 the spike MUST honour

1. Same `LLMEstimatorOutput` schema (`extra="forbid"`, frozen).
2. Same forbidden-phrase rejection set
   (`V_net` / `debt_final` / `corrupt_success` / `verdict` /
   `merge_safe` / `production_safe` / `bug_free` /
   `security_verified` / `official_*`).
3. Same confidence caps (LLM-only ≤0.6, hybrid ≤0.8).
4. Same evidence-ref citation rule.
5. Zero tool calling enabled.
6. Zero "authoritative" output.

## Spike outcome (TBD — populated after sketch is run)

```yaml
spike_status: not_run
reason: |
  Phase 4.8 ships the spike directory + the comparison checklist
  + the constraint articulation. An operator who chooses to
  install pydantic-ai locally can populate `adapter_sketch.py`
  and report against the table above. Until then the spike is
  documentation-only.
```

See `adapter_sketch.py` for the empty skeleton.
