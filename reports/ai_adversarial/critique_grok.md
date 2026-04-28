<!-- ai_adversarial lane (ADR-51). Provider: grok / model: grok-4.20-reasoning. Pin date: 2026-04-28. NOT operator feedback. NEVER ingested by the human-beta aggregator. -->

# Critique by adversarial-cold-reader/grok-4

## Summary
The single biggest friction is that bundle authoring is presented as a non-trivial 8-file hand-crafted JSON exercise whose value proposition (a diagnostic report that explicitly cannot say anything is safe/correct/mergeable) feels disproportionate; a cold reader finishes the quickstart convinced the setup cost will never pay for itself on a real PR. This is compounded by pervasive undefined jargon ("verifier loop", "gateway-grounded", "verification_candidate") that the plain-language doc only partially unpacks, leaving the first beta case impossible to launch without reverse-engineering the example files.

## Confusion points (jargon, undefined terms)
- `docs/concepts/oida_code_plain_language.md`: "`verification_candidate: true` is the **strongest positive signal** the project emits" — a cold reader has no prior definition of "signal" versus "verdict", especially when the next paragraph lists five things it does *not* mean.
- `docs/beta/beta_known_limits.md`: "`verification_candidate: true` means: a claim has at least one evidence item that the gateway-grounded verifier loop accepted as relevant" — "gateway-grounded verifier loop" is used as load-bearing jargon before any operational definition appears; the plain-language doc only gives a one-sentence analogy that does not tell you what the loop actually *does* on the eight JSON files.
- `docs/beta/beta_operator_quickstart.md`: "Author the bundle by hand or by adapting an existing case" — "bundle" is never defined in this file; the reader must jump to the 8-file list in `beta_known_limits.md` ("The bundle is currently 8 files (`packet.json`, four pass JSONs, `tool_policy.json`, `gateway_definitions.json`, `approved_tools.json`)") with no schema or example structure supplied in the quickstart.
- `docs/beta/beta_case_template.md`: "`Claim type:` <<<one of: capability_sufficient | benefit_aligned | …>>>" and "`Named claim:` <<<C.<surface>.<claim>>>" — "surface" and the exact Literal allowlist from `LLMEvidencePacket.allowed_fields` are never defined for a cold reader; the only mention is an opaque cross-reference to a vendored module.
- `docs/beta/beta_feedback_form.md`: "`evidence_traceability` — 0|1|2" and "`VerifierToolCallSpec.purpose` longer than 200 chars" — both assume the reader already knows what a VerifierToolCallSpec is and what an "evidence item" looks like inside the JSON bundle; no example is given.
- `docs/project_status.md`: "Gateway-grounded verifier opt-in path (`oida-code verify-grounded` + `enable-tool-gateway` Action input)" — "opt-in path" is used 20+ times across the pack without a concrete definition of what changes in the tool call surface when the flag flips.
- `BACKLOG.md`: "shadow fusion", "estimator", "LongCoT and Simula are Phase 7 research moat" — these terms appear without any definition or pointer, violating the plain-language doc's own promise to avoid OIDA jargon.

## Contradictions / inconsistencies
- `docs/concepts/oida_code_plain_language.md` vs `docs/beta/beta_known_limits.md`: "`verification_candidate: true` is the **strongest positive signal** the project emits" vs "It does **not** mean: the claim has been verified end-to-end … official fusion fields would have non-null values" — the first reads as positive endorsement while the second (and the no-product-verdict policy) insists it is purely diagnostic, creating tonal conflict.
- `docs/beta/beta_operator_quickstart.md` vs `docs/beta/beta_known_limits.md`: "Authoring the bundle takes ~30–60 minutes for an experienced Python developer" vs "Authoring it by hand is non-trivial and the beta is the first external test of 'is this feasible'" — the quickstart minimises the cost while the known-limits file treats it as an open research question, leaving the cold reader unsure which to believe.
- `docs/beta/README.md` vs `docs/beta/beta_case_template.md`: "the aggregator that turns submitted feedback forms into a single `beta_feedback_aggregate.md`" vs the template's instruction to run `python scripts/run_beta_feedback_eval.py --feedback-root reports/beta --out-dir reports/beta` which produces both `.md` *and* `.json` — the filenames and exact outputs are inconsistent across the two files.
- `docs/concepts/oida_code_plain_language.md` vs `docs/project_status.md`: both list the blocked official fields, but the plain-language version calls them "OIDA v4.2 fusion fields" while project_status calls them "official fusion fields" and adds a table with ADR citations; a cold reader cannot tell if these are the same concept.

## Verdict-leak risk
- `docs/concepts/oida_code_plain_language.md`: "`verification_candidate: true` is the **strongest positive signal** the project emits. It means: the gateway-grounded verifier loop accepted at least one evidence item as relevant" — this sits one paragraph above the pinned `Literal[False]` explanation and could be misread as the closest thing the project offers to a positive verdict, despite the explicit no-product-verdict policy in `docs/security/no_product_verdict_policy.md`.
- `docs/beta/beta_operator_quickstart.md`: "If the gateway status is anything other than `diagnostic_only`, that is a project bug" combined with the table that contrasts oida-code against tools that *do* gate merges — the repeated insistence that it is *not* a gate still leaves the reader wondering why the strongest signal is called "verification_candidate".
- `docs/beta/beta_known_limits.md`: "the five operator-soak cases … all `useful_true_positive`" — while the label itself is forbidden for beta operators, its presence in the known-limits doc leaks the flavour of a positive product judgement the policy forbids.

## Bundle authoring blockers
- "The bundle is currently 8 files (`packet.json`, four pass JSONs, `tool_policy.json`, `gateway_definitions.json`, `approved_tools.json`)" (in `beta_known_limits.md`) with no schema, no generator, and only a self-referential example in the repo root — a cold reader cannot know what legal values belong in `allowed_fields`, `VerifierToolCallSpec.purpose`, or the four pass JSONs without reading vendored code.
- The pre-dispatch local gate in `beta_case_template.md` requires running `python -m oida_code verify-grounded` with eight separate `--packet … --pass1-forward …` flags; a cold reader has no template for what those JSON files must contain to pass the "official_fields_emitted: false" check.
- `docs/beta/beta_operator_quickstart.md` says "use `beta_case_template.md`" but the template only gives the *Markdown* wrapper, not the eight JSON files, forcing the reader to hunt for `examples/gateway_opt_in/` and then figure out how to mutate them for a new claim.
- Bundle authoring notes section in the template asks for "hard-cap close calls (400-char EvidenceItem.summary, 200-char VerifierToolCallSpec.purpose)" but never explains where those limits are enforced or what a valid EvidenceItem looks like, making the first bundle impossible to write.
- The requirement to pick a "named claim" from an undocumented Literal allowlist (`LLMEvidencePacket.allowed_fields`) before you can even start the local gate blocks the very first beta case.

## What would stop you from running a beta case
- The complete absence of a worked example showing the *contents* of a non-self-audit `packet.json` + the four pass JSONs; adapting the shipped example feels like cargo-culting without understanding the verifier loop.
- The explicit warning that bundle authoring takes 30-60 minutes *plus* the local-gate must pass *plus* you must not trigger any forbidden phrases, with no forgiveness path if you get the JSON structure wrong.
- No clear definition of what "C.<surface>.<claim>" must look like or what the `<surface>` part refers to, making the mandatory header in `beta_case_template.md` impossible to fill honestly.

## What would make you actually use this on a real PR
- A `prepare-gateway-bundle` generator (mentioned but explicitly deferred in `beta_known_limits.md` and `project_status.md`) that took a pytest scope and a claim string and emitted the eight files.
- Concrete evidence that the diagnostic report tells you something beyond what `pytest -q --tb=no` + `mypy` + `ruff` already tell you; the current "strongest positive signal" still reads as a complicated way to say "the test passed".
- Removal of the 400/200 character hard caps and the `LLMEvidencePacket.allowed_fields` Literal straitjacket so the tool could be used on real engineering claims instead of the seven enumerated shapes.

## Honest uncertainty
- Whether "surface" in `C.<surface>.<claim>` is a file, a module, a class, or something else — none of the docs define it.
- Whether the four "pass" JSONs are supposed to be hand-written counterfactuals or are generated by the verifier loop; the quickstart command passes them *in* but never says where they come from.
- If the `verify-grounded` local gate is intended to run against the *target* repo or against the oida-code repo itself; the example uses `--repo-root .` while the beta instructions imply a separate target.
