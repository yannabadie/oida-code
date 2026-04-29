# Calibration seed authoring checklist

This checklist is mandatory before any future calibration seed pin. It folds
G-6c into G-6d by making the human Tier-3 authoring step explicit and
reviewable before a case receives `partition=train` or `partition=holdout`.

## Candidate identity

- Public repo only.
- Merged PR only.
- `repo_url`, `pr_number`, `base_sha`, and `head_sha` are present.
- Diff boundary is inspectable and matches the seed record.
- No private data, PR-comment-only rationale, or unavailable upstream evidence
  is required to understand the claim.

## Claim quality

- `claim_id` starts with `C.` and names the behavior, not the verdict.
- `claim_type` is one of the allowed verifier claim types.
- `claim_text` is concise, code/test-grounded, and does not contain product
  verdict wording.
- The claim describes one behavior change or capability, not a broad release.
- The claim can be checked through source diff plus scoped test evidence.

## Evidence quality

- `evidence_items` include at least one implementation or diff fact.
- `evidence_items` include at least one test-result or runnable-scope fact.
- Evidence summaries cite concrete files, symbols, tests, or behavior.
- Provider output is never used as non-LLM evidence.
- Ambiguous, inferred, or reviewer-intent claims are rejected or deferred.

## Test scope quality

- `test_scope` names the narrowest runnable pytest scope that exercises the
  claim.
- The scope is not a whole class or directory when a specific test is enough.
- The scope is feasible for `scripts/clone_target_at_sha.py` without adding a
  new carve-out flag.
- The base/head checkout path and dependency mode are understood before
  replay authoring starts.

## Partition discipline

- Partition is assigned before outcome inspection.
- Train cases may inform authoring/tooling.
- Holdout cases must not be used to tune the generator or helper code.
- Demotion or replacement of a defective holdout must preserve the historical
  reason instead of rewriting the trajectory.

## Before replay authoring

- The seed passes the schema and partition-discipline tests.
- The scoped pytest command has been identified for the target checkout.
- No clone-helper widening is required.
- The case has a clear reason for inclusion and a clear reason it is not
  release-prep, dependency-only, formatting-only, or generated-heavy.
- Future LLM-authored replay outputs are marked for ADR-68 static audit and
  ADR-69 manual semantic review before they carry claim-supporting weight.
