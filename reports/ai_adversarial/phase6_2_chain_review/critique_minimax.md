<!-- ai_adversarial lane (ADR-51). Provider: minimax / model: MiniMax-Text-01. Pin date: 2026-04-28. NOT operator feedback. NEVER ingested by the human-beta aggregator. -->

# Methodology critique by <PROVIDER>/<MODEL>

## Summary
The Phase 6.1' methodology for "oida-code" is meticulous in its adherence to a no-product-verdict policy and in its structural separation of lanes. However, it exhibits significant ambiguity in terminology, struggles with the practical implications of its holdout discipline, and risks overstating partial generalization due to a narrow and biased corpus.

## Confusion points (jargon, undefined terms)
- `<reports/calibration_seed/README.md>`: "structural sampling of public Python PRs" — unclear what "structural" means in this context; it is not defined against "behavioral" or other sampling strategies.
- `<reports/calibration_seed/schema.md>`: "expected_grounding_outcome" — while the schema defines allowed values (e.g., `evidence_present`), it does not define what "grounding" means in the context of the verifier's operation.
- `<reports/calibration_seed/schema.md>`: "claim_id" uses the pattern `C.<surface>.<claim>`, but "surface" is not defined, making it unclear how to categorize or interpret these IDs.
- `<reports/phase6_1_d_round_trip.md>`: "diagnostic_only" — the term implies a specific meaning, but without a clear definition, it is unclear if this is a technical term or a colloquial description.
- `<reports/phase6_1_h_freeze_pass.md>`: "partial holdout generalisation" — the term suggests a broader claim about the tool's capabilities, but the methodology does not define the boundaries of "partial" or what constitutes "generalisation" in this context.

## Contradictions / inconsistencies across phase reports
- `<reports/calibration_seed/README.md>` vs. `<reports/phase6_1_h_freeze_pass.md>`: The README states that "The generator's holdout-set performance is the only honest signal that the helper generalises beyond its training corpus," but the freeze-pass report claims "partial holdout generalisation" based on a single successful holdout case out of two. This is inconsistent because the README implies a need for a more robust demonstration of generalisation.
- `<reports/phase6_1_e_step_4_holdouts.md>` vs. `<reports/phase6_1_h_freeze_pass.md>`: The step-4 report categorizes `seed_157` as `diagnostic_only` due to a "target_bootstrap_gap," while the freeze-pass report reclassifies it as an "honest claim-level negative" due to an "over-broad test_scope." This reclassification is inconsistent and suggests a shift in interpretation rather than a clear methodological justification.
- `<reports/phase6_1_c_corpus_expansion.md>` vs. `<reports/phase6_1_h_freeze_pass.md>`: The corpus expansion report acknowledges a "selection-effect caveat" that biases the corpus toward maintainer-authored work, but the freeze-pass report claims "partial holdout generalisation" without addressing whether this bias undermines the claim.

## Verdict-leak risk
- `<reports/phase6_1_h_freeze_pass.md>`: "The chain CAN now honestly claim partial holdout generalisation" — this statement could be misread as a product verdict because it implies a level of confidence in the tool's capabilities that goes beyond the empirical evidence of a single successful holdout case.
- `<reports/phase6_1_h_freeze_pass.md>`: "The remaining 1/2 negative is a documented seed-record authoring quality issue, not a generator/verifier failure" — this statement could be misread as a product verdict because it suggests that the tool would have succeeded if not for the quality of the seed record, which is an assumption not supported by the evidence.

## Discipline / Goodhart risks
- **Holdout discipline**: The current holdout ratio guard (20%-40%) is too loose at very small N (e.g., N=5), as acknowledged in the schema. This raises concerns about the reliability of the holdout discipline in detecting overfitting.
- **Seed authoring quality**: The `seed_157` case highlights a defect in seed authoring, where the test_scope was over-broad. This suggests that the discipline for authoring seed records may need to be more rigorous to prevent similar issues.
- **Freeze rule carve-outs**: The use of the carve-out for "predeclared env bootstrap" in the freeze rule for `seed_157` raises questions about the consistency of its application. The distinction between "predeclared env bootstrap" and "tooling edits" is not clearly defined, which could lead to inconsistent application of the freeze rule.

## Are the success claims actually supported?
- **seed_008 verification_candidate**: The evidence cited in `<reports/phase6_1_e_steps_1_3.md>` supports the claim that the verifier accepted the claim and that pytest passed the test. However, the evidence does not address whether the test_scope is representative of the broader claim or whether the test is sufficient to support the claim.
- **seed_065 verification_candidate**: The evidence cited in `<reports/phase6_1_h_freeze_pass.md>` supports the claim that the verifier accepted the claim and that pytest passed the test. However, the evidence does not address whether the test_scope is representative of the broader claim or whether the test is sufficient to support the claim.
- **seed_157 diagnostic_only**: The evidence cited in `<reports/phase6_1_h_freeze_pass.md>` supports the claim that the verifier did not accept the claim and that pytest failed the test. However, the evidence suggests that the failure was due to an over-broad test_scope rather than a failure of the tool itself.

## What would make you doubt the chain's "partial generalisation" claim
1. The current corpus is heavily biased toward maintainer-authored work and lacks diversity in terms of project size, complexity, and authorship. This bias undermines the claim of generalisation.
2. The successful holdout case (`seed_065`) is still pytest-shaped, which means the tool has not demonstrated generalisation to non-pytest-shaped targets.
3. The freeze rule carve-outs, particularly the "predeclared env bootstrap" carve-out, introduce a level of flexibility that could be exploited to tune the tool to the holdout cases without violating the letter of the rule.

## Honest uncertainty
1. The distinction between "predeclared env bootstrap" and "tooling edits" is unclear. It is uncertain whether the use of `--scm-pretend-version`, `--install-extras`, `--install-group`, and `--import-smoke` in the freeze rule pass constitutes a tooling edit.
2. The schema defines "diagnostic_only" but does not define what "diagnostic evidence" means. It is uncertain whether the evidence produced by the verifier in the `seed_157` case qualifies as "diagnostic evidence."
3. The schema defines "claim_id" but does not define what "surface" means. It is uncertain how to interpret the claim_id "C.cli_version_flag.repair_needed" or how to categorize it.
