"""Phase 4.8-F (QA/A25.md, ADR-33) — Pydantic-AI adapter SKETCH.

NOT a production module. NOT installed by ``pip install -e .[dev]``.
NOT covered by mypy or ruff in the project's gates (see
`pyproject.toml` exclude list — this file lives outside `src/`
specifically to stay out of the install surface).

The sketch outlines what an `oida-code` provider built on
`pydantic-ai` WOULD look like if a future ADR decides to migrate.
The actual code is a stub — running it requires `pip install
pydantic-ai` in the operator's local environment, which Phase 4.8
deliberately does NOT add.

Hard constraints from ADR-32 the spike MUST preserve:

* same `LLMEstimatorOutput` schema (frozen + ``extra="forbid"``)
* same forbidden-phrase rejection set
* same confidence caps (LLM-only ≤0.6, hybrid ≤0.8)
* same evidence-ref citation rule
* ZERO tool calling enabled (`tools=[]`)
* ZERO "authoritative" output
"""

# ruff: noqa: F401, E501 — sketch only; real adoption goes through ADR

from __future__ import annotations

# When pydantic-ai is installed locally:
#
#     pip install pydantic-ai
#
# the sketch becomes runnable. The skeleton below shows the
# adapter signature. Filling it out is a follow-up exercise an
# operator runs locally and reports against `experiments/
# pydantic_ai_spike/README.md`'s comparison table.

SKETCH_NOTES = """
1. Construct the agent with NO tools and a typed result model:

       from pydantic_ai import Agent
       from oida_code.estimators.llm_contract import LLMEstimatorOutput

       agent = Agent(
           model="openai:deepseek-v4-pro",          # via OPENAI_API_BASE
           result_type=LLMEstimatorOutput,
           tools=[],                                  # ADR-32: forbidden
           system_prompt="...",                       # same as render_prompt
       )

2. Run synchronously (the existing CLI is sync):

       result = agent.run_sync(user_prompt)
       parsed: LLMEstimatorOutput = result.data

3. Apply the existing post-validators ON TOP — pydantic-ai validates
   the SHAPE; our forbidden-phrase fence + citation + confidence-cap
   logic must still run (these are domain rules, not type rules):

       _check_forbidden_phrases(json.dumps(parsed.model_dump()))
       _validate_citations(packet, parsed)
       _apply_confidence_cap(parsed)

4. Capture redacted IO via a logfire-style instrumentation hook:

       # pseudocode — pydantic-ai uses logfire for tracing; the
       # operator's adapter would intercept the HTTP call's response
       # body, run redact_secret(body, api_key), then stash a
       # ProviderRedactedIO matching the existing schema.

5. Map exceptions to the existing taxonomy
   (LLMProviderUnavailable / LLMProviderTimeout /
   LLMProviderInvalidResponse / LLMProviderError) so the runner
   doesn't need to learn pydantic-ai's exception shape.
"""


def adapter_sketch_signature() -> str:
    """Document — for the spike — what the migration adapter
    boundary would look like. Returns the SKETCH_NOTES so the
    spike script (run locally) can print them."""
    return SKETCH_NOTES


if __name__ == "__main__":  # pragma: no cover — sketch
    print(adapter_sketch_signature())
