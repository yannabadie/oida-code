# Beta known limits

This document lists what `oida-code` does **not** do, what its
controlled-beta operators should not expect, and which signals are
diagnostic only. It is the leaf document of `docs/beta/` — every
other beta doc references this one. Read this before you read the
quickstart.

> `oida-code` does not say "this PR is safe". It shows which claims
> are supported by which evidence, which evidence is missing, and
> why official fields stay blocked.

## What stays blocked during the beta

These fields are pinned as null / not-emitted across every artefact
the beta produces. The pin is structural (Pydantic schemas, runner
forbidden-phrase scan, action manifest) and is not relaxed in beta:

* `total_v_net`
* `debt_final`
* `corrupt_success`
* `corrupt_success_ratio`
* `verdict`

If you see any of these as a non-null value in a beta artefact,
that is a contract violation. Report it via the feedback form
(`beta_feedback_form.md`); it is a project bug, not a beta result.

## Phrases the beta will never produce

The runners reject any response that contains any of these phrases.
The rejection is at the raw-bytes layer — it does not depend on
whether the LLM agreed to comply:

* `merge-safe`
* `production-safe`
* `bug-free`
* `verified` (as a product verdict)
* `security-verified`

If you see any of these in a beta report, that is a contract
violation. Report it.

## Default settings the beta does not change

* `enable-tool-gateway` stays **false** by default. The composite
  Action input does not change in Phase 6.0 even if the recommendation
  flips.
* No external provider is wired in by default. The beta uses replay
  fixtures or an explicit opt-in operator-controlled provider.
* No write tools, no network egress, no MCP, no provider tool-calling.
* `contents: read` permissions; no `pull_request_target`; no
  fork-PR execution of the gateway path.

## What the beta cannot tell you

* It cannot tell you a PR is safe to merge.
* It cannot tell you a codebase is bug-free.
* It cannot tell you a security review is complete.
* It cannot tell you the LLM judgement is correct — the report is a
  diagnostic of which claims are grounded in tool output.
* It cannot tell you the gateway path generalises to your full
  codebase. The beta is **scoped to a named claim with a named
  pytest target**.
* It cannot tell you predictive performance numbers — there is no
  large-scale validation dataset.

## What `verification_candidate` means in beta

`verification_candidate: true` means: a claim has at least one
evidence item that the gateway-grounded verifier loop accepted as
relevant. It does **not** mean:

* the claim has been verified end-to-end
* the underlying code is correct
* the underlying code is safe to merge
* an external reviewer would accept the claim
* official fusion fields would have non-null values if they existed

This is exactly the "diagnostic-only" frame the security policy
documents (`docs/security/no_product_verdict_policy.md`).

## What the five completed Tier-5 cases actually proved

The five operator-soak cases (`operator_soak_cases/case_001..005`)
demonstrated that:

* the gateway opt-in path can run on real targets with real
  pytest scopes,
* artefacts are reproducible and human-readable,
* the contract walls hold (zero official-field leaks across all five),
* a single human (`cgpro`) can label each case useful in a
  controlled context.

They did **not** demonstrate:

* that someone other than the project authors can run and read the
  artefacts,
* that the bundle authoring is feasible without the runbook open,
* that the gateway path scales to non-Python targets,
* that the gateway path scales to fork-PR targets,
* anything about predictive performance.

That is exactly what the controlled beta is for.

## Limits inherited from the underlying tooling

* `pytest_summary_line` is captured from the terminal summary line
  produced by pytest. If the target neutralises summary output by
  some mechanism the adapter does not yet handle, the line will be
  null and the evidence falls back to the parser-only signals. The
  Phase 5.9 fix (`-o addopts=`) handles the most common case
  (target `addopts` collapsing verbosity), but is not exhaustive.
* `mypy` runs in the target's venv. If the target does not type-check
  cleanly even on `main`, the report shows the pre-existing failures
  unchanged — `oida-code` does not silently fix them.
* `ruff` and `semgrep` outputs depend on the target's configuration.
  The report shows what the configured tools say.
* `codeql` is opt-in and slow. The default beta configuration does
  not run `codeql`.
* No language other than Python is currently supported. JavaScript /
  TypeScript / Go / Rust targets are out of scope for the beta.

## Limits inherited from the bundle format

The bundle is currently 8 files (`packet.json`, four pass JSONs,
`tool_policy.json`, `gateway_definitions.json`, `approved_tools.json`).
Authoring it by hand is non-trivial and the beta is the first
external test of "is this feasible". One of the open beta questions
is precisely "should there be a `prepare-gateway-bundle` generator?"
— Phase 6.0 will gather signal but does not commit to the answer.

## Limits inherited from the workflow

* The composite Action does not run on `pull_request_target`.
* The composite Action does not run on fork PRs.
* The composite Action does not have write permissions.
* The composite Action does not call out to external networks
  (other than the explicit `actions/checkout` clone of the target).

These are not configurable in the beta. They are the security
defaults documented in the [no-product-verdict policy](../../docs/security/no_product_verdict_policy.md).

## What beta operators may NOT do

* Re-label `cgpro` outputs. Operator labels are operator-only;
  `cgpro` is treated as a separate human-operator channel.
* Edit `aggregate.json` by hand. Use the runner script.
* Add a claim outside the `LLMEvidencePacket.allowed_fields`
  Literal allowlist (the schema rejects this anyway, but don't
  try to work around it).
* Author an evidence item with a summary longer than 400 chars.
* Author a `VerifierToolCallSpec.purpose` longer than 200 chars.

## What beta operators may freely do

* Pick the target repo and PR.
* Pick the named claim. (Pick one. The beta is per-claim, not
  per-PR.)
* Pick the pytest scope.
* Author the bundle by hand or by adapting an existing case.
* Run the workflow with `enable-tool-gateway=true` for the duration
  of the beta — this is opt-in by the operator, not a default change.
* Submit feedback via the feedback form (`beta_feedback_form.md`).
* Walk away. The beta is not a contract; if a target turns out to
  be unsuitable (large monorepo, secrets, etc.), document the reason
  and skip.

## Cross-references

* Status: see [`docs/project_status.md`](../project_status.md).
* Plain-language overview: see
  [`docs/concepts/oida_code_plain_language.md`](../concepts/oida_code_plain_language.md).
* No-product-verdict policy: see
  [`docs/security/no_product_verdict_policy.md`](../security/no_product_verdict_policy.md).
* Gateway opt-in usage: see
  [`docs/gateway_opt_in_usage.md`](../gateway_opt_in_usage.md).
* Interpretation guide: see
  [`docs/interpreting_gateway_reports.md`](../interpreting_gateway_reports.md).
* Operator soak runbook: see
  [`docs/operator_soak_runbook.md`](../operator_soak_runbook.md).
