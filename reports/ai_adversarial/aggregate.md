# AI adversarial review — aggregate (Phase 6.0.y, ADR-51)

**Status:** 3 of 4 attempted providers produced critiques. This
aggregate is **hand-summarized convergence/divergence**, NOT a
programmatic aggregate. There is no score, no usefulness rate, no
recommendation key. The friction surfaced here is for the project
team to act on (or defer); it is **NOT** a Phase 6.1 scope decision —
that decision still requires human-beta feedback per QA/A42
§"Phase 6.1 préfiguration".

## Per QA/A41 + QA/A42 + ADR-51 — what this aggregate is and is not

* It is a **first-opinion friction surface** from cold readers (3 LLMs from 3 independent provider families) before external human operators arrive.
* It is **NOT** operator feedback. The 3 critiques never land in `reports/beta/beta_feedback_aggregate.md`. The path-isolation guard in `_iter_feedback_files` (Phase 6.0.x) and the schema pin `feedback_channel: human_beta` (Phase 6.0.x) make this structural, not just convention.
* It is **NOT** a Phase 6.1 scope decision. AI agents cannot choose Phase 6.1 in place of human operators. The convergence/divergence below informs which questions to ask human operators FIRST; it does NOT resolve them.
* It is **NOT** a contract on the docs. Some agent suggestions (e.g. "remove the 400-char EvidenceItem.summary cap") directly contradict ADR-22+ structural pins and must be rejected without further consideration. The project team filters before acting.

## Run record

| Provider | Model | Status | Output |
|---|---|---|---|
| DeepSeek | `deepseek-v4-pro` | success | `critique_deepseek.md` |
| xAI Grok | `grok-4.20-reasoning` | success | `critique_grok.md` |
| Moonshot Kimi | `kimi-k2.6` | HTTP 401 (auth failed; fallback `moonshot-v1-128k` also 401) | `critique_kimi.md` (failure record) |
| MiniMax | `MiniMax-Text-01` | success (substitute for Kimi) | `critique_minimax.md` |

3 successful critiques + 1 documented failure. Pin date 2026-04-28; future operators MUST re-verify the model IDs before re-running.

## Convergence (≥2 reviewers agree)

### C1 — Bundle authoring is the dominant friction. Cited by: **DeepSeek, Grok, MiniMax** (3/3).

The 8-file bundle (`packet.json`, `pass1_forward.json`, `pass1_backward.json`, `pass2_forward.json`, `pass2_backward.json`, `tool_policy.json`, `gateway_definitions.json`, `approved_tools.json`) has no schema documentation, no per-file walkthrough, no worked non-self-audit example, and no generator. The closest guidance is the keystone self-audit example in `examples/gateway_opt_in/`, which a cold reader has to reverse-engineer.

DeepSeek's exact framing: *"No specification of the eight bundle files. `beta_case_template.md` says 'Author the bundle under reports/beta/beta_case_<n>/bundle/' but never describes what packet.json [etc.] must contain. The closest guidance is the quickstart's smoke-test command that references the keystone example, but that only shows the example, not how to derive your own."*

Grok's exact framing: *"a cold reader cannot know what legal values belong in `allowed_fields`, `VerifierToolCallSpec.purpose`, or the four pass JSONs without reading vendored code."*

MiniMax's exact framing: *"The complexity and manual nature of bundle authoring are likely to be a significant blocker for new users. The documentation acknowledges this but does not provide a clear solution or tool to simplify the process."*

**Project-team interpretation:** this matches QA/A41 §6.0-F's prediction ("Phase 6.1 devra créer `oida-code prepare-gateway-bundle`"). The 3-of-3 convergence among cold readers is a strong pre-beta signal that bundle authoring will dominate `setup_friction` scores once human operators arrive. **It does NOT yet justify launching Phase 6.1 — the rule is still "first measure with humans, then build"** per QA/A41 §6.0-F: "Mais ne pas le coder en Phase 6.0. D'abord mesurer." The convergence makes the bundle-generator hypothesis (QA/A42 Phase 6.1 hypothesis A) the prior with the strongest evidence among the three; humans confirm or refute.

### C2 — `verification_candidate: true` "strongest positive signal" wording risks verdict-leak. Cited by: **DeepSeek, Grok, MiniMax** (3/3).

The phrase in `docs/concepts/oida_code_plain_language.md` reading *"`verification_candidate: true` is the **strongest positive signal** the project emits"* is brittle. The bolded "strongest positive signal" phrasing invites a relative-safety reading, especially because the disclaimers below it ("does NOT mean…") sit AFTER the eye-catching claim.

DeepSeek's framing: *"The bolded phrase invites a product-like reading (`strongest positive` implies relative safety/reliability) despite the immediately following disclaimers. A hurried cold reader could easily land on `strongest positive signal` and conclude the claim is good enough to merge, leaking a pseudo-verdict."*

Grok's framing: *"this sits one paragraph above the pinned `Literal[False]` explanation and could be misread as the closest thing the project offers to a positive verdict, despite the explicit no-product-verdict policy."*

MiniMax's framing: *"could be misread as an endorsement or a form of verification, especially since it is described as the 'strongest positive signal'."*

**Project-team interpretation:** this is actionable in a Phase 6.0.z documentation polish patch (NOT Phase 6.1, since it's wording not architecture). Candidate revision: lead with the diagnostic frame ("`verification_candidate: true` is the **strongest diagnostic positive signal** the project emits — it is NOT a merge gate, NOT a safety claim, NOT an endorsement of the underlying code") so the disclaimer arrives BEFORE the eye-catching phrase. The doc-guard regex `_FORBIDDEN_VERDICT_CLAIM_PATTERNS` does NOT currently flag this phrasing because no forbidden token appears literally; the friction is reader-cognition, not token leak.

### C3 — Contradiction between "30-60 min" quickstart and "non-trivial / first external test" known_limits. Cited by: **DeepSeek, Grok** (2/3).

`docs/beta/beta_operator_quickstart.md` says *"Authoring the bundle takes ~30–60 minutes for an experienced Python developer reading the runbook for the first time."*

`docs/beta/beta_known_limits.md` says *"Authoring it by hand is non-trivial and the beta is the first external test of 'is this feasible'."*

Grok's framing: *"the quickstart minimises the cost while the known-limits file treats it as an open research question, leaving the cold reader unsure which to believe."*

**Project-team interpretation:** the inconsistency is real. The quickstart's 30-60 min estimate was author intuition, not measurement. Either:
- (a) drop the time estimate from the quickstart and replace with "we don't know yet — measuring this is exactly what the beta tests";
- (b) keep the estimate as an upper bound ("plan for up to 60 min on first attempt") with the explicit acknowledgement that this is unmeasured.

This is a one-line fix; defer to Phase 6.0.z documentation polish.

### C4 — "Gateway-grounded verifier loop" is load-bearing jargon used before definition. Cited by: **DeepSeek, Grok, MiniMax** (3/3).

The term appears in `beta_known_limits.md` and `beta_operator_quickstart.md` before any operational definition. The plain-language doc gives a property-based-test analogue but doesn't explain what the loop *does* on the bundle JSON files.

**Project-team interpretation:** this is a real gap. Phase 6.0.z documentation polish should add a `## What the verifier loop does` section to `oida_code_plain_language.md` with a concrete walkthrough: "given packet + 4 pass JSONs + tool_policy, the loop runs `pytest <scope>`, checks the response against the policy, accepts evidence items the policy permits, and either marks `verification_candidate: true` (one or more grounded evidence items) or `false` (zero grounded evidence items)."

### C5 — `C.<surface>.<claim>` claim format and `LLMEvidencePacket.allowed_fields` Literal allowlist undocumented for cold readers. Cited by: **DeepSeek, Grok** (2/3).

`<surface>` is never defined; the allowlist values (`capability_sufficient`, `benefit_aligned`, `observability_sufficient`, `precondition_supported`, `negative_path_covered`, `repair_needed`, `shadow_pressure_explained`) are listed but not exemplified.

Grok's "Honest uncertainty" item: *"Whether 'surface' in `C.<surface>.<claim>` is a file, a module, a class, or something else — none of the docs define it."*

**Project-team interpretation:** Phase 6.0.z documentation polish — add a dedicated "How to write a `C.<surface>.<claim>` identifier" section to `beta_case_template.md` with 5 concrete examples spanning the 7 allowed_fields types. This was implicit in the template's prose but never spelled out.

## Divergence (1 reviewer disagrees or is alone)

### D1 — Grok proposes removing the 400/200-char hard caps and the `LLMEvidencePacket.allowed_fields` Literal allowlist.

Grok's exact ask: *"Removal of the 400/200 character hard caps and the `LLMEvidencePacket.allowed_fields` Literal straitjacket so the tool could be used on real engineering claims instead of the seven enumerated shapes."*

**Project-team interpretation:** **REJECTED without further consideration.** The 400-char `EvidenceItem.summary` cap and the 200-char `VerifierToolCallSpec.purpose` cap are part of the prompt-injection defence per Phase 4.0.1 hardening (CLAUDE.md). The Literal allowlist is the structural backbone of the verifier contract per ADR-22+. Removing them would re-open the prompt-injection attack surface and break the no-product-verdict guarantees. This is exactly the QA/A42 piège 5 case ("la lane adversarial IA peut informer les fixtures et les garde-fous, mais elle ne doit pas choisir Phase 6.1 à la place des opérateurs humains") — agents propose architectural changes that violate the project's load-bearing contracts; project team filters.

### D2 — MiniMax flags `useful_true_positive` operator label as verdict-leak risk.

MiniMax's exact framing: *"The label 'useful_true_positive' — This label implies a verdict-like classification, which could be misinterpreted as a product verdict despite the policy against such claims."*

**Project-team interpretation:** **partially valid.** The label name is internal-clinic terminology (true positive / true negative / false positive / false negative — standard binary-classifier framing). For the operator-soak case readers it's clear; for a cold beta operator it could read as endorsement. **Defer:** rename is a breaking change touching aggregator + tests + 5 Tier-5 operator-soak case READMEs; not justified by 1-of-3 reviewers. Re-evaluate if a human operator independently flags the same friction.

### D3 — DeepSeek-only weak verdict-leak concern on `gateway_status: diagnostic_only` "stop and report".

DeepSeek noted that the framing in `beta_operator_quickstart.md` ("If the gateway status is anything other than `diagnostic_only`, that is a project bug. Stop and report it.") could be over-read as "the project guarantees the block is absolute and therefore the artifact is 'safe'." Self-rated as a "weaker leak."

**Project-team interpretation:** **defer.** The "stop and report" framing is correct (a non-`diagnostic_only` status IS a project bug). The over-read is theoretical. No revision.

## What this aggregate does NOT find

- **No `merge-safe` / `production-safe` / `bug-free` / `verified` / `security-verified` token leak in any doc.** All 3 reviewers were specifically primed to look for this; none found a literal occurrence outside the explicit forbidden-token enumeration in `docs/security/no_product_verdict_policy.md`. The verdict-leak risks identified are all reader-cognition (wording invites misreading) not token leak.
- **No contradiction between the action default (`enable-tool-gateway: false`) statement across docs.** The default-false invariant is consistent across all 8 reviewed files.
- **No reviewer suggested flipping `enable-tool-gateway` to default-true.** The system prompt forbade this; all 3 reviewers respected the constraint.
- **No reviewer suggested emitting `total_v_net` / `debt_final` / `corrupt_success`.** Same.

## What follows from this aggregate

1. **Phase 6.0.z documentation polish patch** addressing C2 (verification_candidate wording), C3 (30-60 min vs non-trivial inconsistency), C4 (verifier loop walkthrough), C5 (C.<surface>.<claim> examples). Estimated 4 small doc edits + 0 schema changes + 0 new tests. Not a phase boundary; lands as a single `chore(docs): address ai_adversarial findings C2-C5` commit.
2. **Phase 6.1 bundle-generator hypothesis (per QA/A42 hypothesis A) gains pre-beta evidence weight from C1.** Still does NOT trigger Phase 6.1 — the rule "first measure with humans, then build" stands. The convergence makes hypothesis A the prior with strongest pre-beta evidence; human operators confirm or refute.
3. **D1 (cap removal) explicitly rejected and recorded.** Future reviewers should not re-litigate this.
4. **D2 (operator label rename) parked.** Re-evaluate if a human operator independently flags it.
5. **Kimi 401 needs investigation before any future re-run.** Either the `KIMI_API_KEY` is for a different endpoint (e.g., the Kimi Open Platform vs the Moonshot Open Platform), or the key is expired. Out-of-scope for Phase 6.0.y; recorded for future operators.

## Honesty statement

Phase 6.0.y is a friction-surface tool for the project team. It does NOT replace human-beta feedback; it informs which questions to ask human operators first. AI agents cannot choose Phase 6.1; AI agents cannot label cases; AI agents cannot fill the human feedback form (path-isolation + schema pin both block this structurally). The 3 critiques here are first opinions from cold readers, not verdicts. The Phase 4.7 + 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 + 5.7 + 5.8 + 5.8.x + 5.9 + 6.0 + 6.0.x anti-MCP locks remain ACTIVE.

## Cross-references

* ADR-51: `memory-bank/decisionLog.md`
* QA/A42: `QA/A42.md` (the verdict that scoped this lane)
* Per-provider critiques: `critique_deepseek.md`, `critique_grok.md`, `critique_kimi.md` (failure record), `critique_minimax.md`
* Script: `scripts/run_ai_adversarial_review.py`
* Path-isolation + schema pin (Phase 6.0.x): `scripts/run_beta_feedback_eval.py`
