# `oida-code` in plain language

This document explains what `oida-code` is, in plain language,
without project jargon. It is for readers — including
controlled-beta operators — who do not yet know what
"verifier loop", "gateway-grounded", or "OIDA" mean. Read this
before you read the runbook.

## The one-paragraph version

`oida-code` is a tool that takes a **claim about code** (e.g.
"this change adds a negative-path test for X") plus a
**named test scope**, runs deterministic Python tools (`pytest`,
`mypy`, `ruff`, `semgrep`) against that scope, and produces a
**diagnostic report** showing whether the claim is supported by
the tool output. The report does **not** declare the code safe,
correct, or merge-ready. It just shows the link from claim to
evidence — or the absence of that link.

## What it is, in one sentence each

* **Not a linter.** A linter flags style and correctness on the
  whole file. `oida-code` answers a single named question.
* **Not a code review bot.** A bot writes English comments.
  `oida-code` writes structured artefacts where every claim is
  linked to a tool result.
* **Not a copilot.** A copilot writes code for you. `oida-code`
  doesn't write any code; it reads code that already exists and
  asks "is the named claim about this code grounded in evidence?"
* **Not an LLM-as-judge.** An LLM-as-judge says "looks fine to
  me" or "looks broken". `oida-code` rejects unsupported English
  outright; the runners refuse any response containing
  `merge-safe`, `production-safe`, `bug-free`, `verified`, or
  `security-verified`.
* **Not a merge gate.** The default GitHub Action setting keeps
  the gateway path off; even when on, the action does not gate
  merge. The artefact is a diagnostic, not a check.

## Why this exists

LLMs are very good at producing **plausible** claims about code.
"This PR adds proper input validation" — sounds reasonable. The
problem is: how do you know? In a normal review, the answer is
"someone reads the diff and trusts the author". `oida-code` is
an experiment in making that trust explicit and traceable: the
claim must be named, the evidence must be named, the tool result
must be cited, and the report must not lie about the verdict.

The model behind it is **OIDA v4.2** — a formal framework for
auditing arguments about code. The vendored OIDA core lives at
`src/oida_code/_vendor/oida_framework/`. We don't modify it; we
wrap it in a Pydantic public surface.

## What "named claim" means

A claim is one of the following structured assertions about a
code change. The shape is fixed (`LLMEvidencePacket.allowed_fields`
is a Literal allowlist):

* `capability_sufficient` — "the change adds the named
  capability".
* `benefit_aligned` — "the change is aligned with a stated
  user-facing benefit".
* `observability_sufficient` — "the change adds enough logs /
  metrics / traces for an operator to detect it in production".
* `precondition_supported` — "the change preserves or
  strengthens a named precondition".
* `negative_path_covered` — "the change adds a test of an error
  path".
* `repair_needed` — "the change names a follow-up
  repair".
* `shadow_pressure_explained` — "the change explains a shadow
  pressure observation".

A claim is **per-PR scoped to one of these shapes**. Multi-claim
PRs run multiple cases. The point is to make the claim
**checkable**, not exhaustive.

## What "tool-grounded" means

A claim is "tool-grounded" if the report can point at a
specific tool result that the verifier loop accepted as
relevant. The relevant tools are:

* `pytest` — run scoped to the named test path.
* `mypy --strict` — run on the changed surface.
* `ruff check` — run on the changed surface.
* `semgrep` — opt-in, configured per-bundle.
* `codeql` — opt-in, slow, off by default.

The verifier loop reads the tool output and either accepts the
claim as supported, marks it `verification_candidate: true` (a
diagnostic, see below), or rejects it. It never declares
"merge-safe".

## What `verification_candidate` does and does not mean

`verification_candidate: true` is the **strongest positive
signal** the project emits. It means: the gateway-grounded
verifier loop accepted at least one evidence item as relevant
to the named claim, the official-field walls held, and the
runners did not reject the response.

It does **not** mean:

* the underlying code is correct,
* the underlying code is safe to merge,
* the LLM judgement was right,
* an external reviewer would accept the claim,
* official `total_v_net` / `debt_final` / `corrupt_success`
  fields would have non-null values if they existed.

`verification_candidate: false` means: at least one of the
walls did not clear. It does not mean the code is broken —
just that the claim/evidence/tool chain did not pass through
the loop.

## What "gateway opt-in path" means

The composite GitHub Action exposes an
`enable-tool-gateway` input. The default is **false**. When
false, the action runs in deterministic-only mode — no
LLM-grounded verifier loop, no gateway tool calls. When true,
the action enables the gateway-grounded path: the LLM is given
a controlled tool-call API (read-only, network-egress-blocked,
write-blocked), the verifier loop accepts evidence the
gateway actually grounded, and the report includes the
diagnostic.

The default stays **false** even if the recommendation in the
operator-soak aggregate flips to `document_opt_in_path`. The
recommendation is diagnostic; the action default does not
change.

## What "official fields blocked" means

The fields `total_v_net`, `debt_final`, `corrupt_success`,
`corrupt_success_ratio`, and `verdict` are the OIDA v4.2 fusion
fields. In the framework, they have semantic weight: they
encode a quantitative judgement of safety / correctness. In
this project, they are **structurally blocked** — the schemas
don't expose them as `True` fields, the runners refuse to emit
them, and the action manifest does not surface them as outputs.

The block exists because emitting them without rigorous
predictive validation would misrepresent the project's
predictive performance. Phase 3 already failed on a
length-confound proxy; Phase 3.5+ established the rule that
official fields stay null until predictive validation lands —
which is not currently scheduled.

## What "diagnostic only" means

Every report carries `gateway_status: diagnostic_only`. This
means:

* the report's purpose is to show evidence linkage, not to
  authorise a merge,
* no badge / status / check / output of the action implies a
  product verdict,
* the operator (a human) is the one who decides what to do with
  the report.

This is the project's defining frame. If you ever see a report
that does not have `diagnostic_only`, that is a project bug.

## What the project is for

* **Demonstrating** that the gateway-grounded verifier loop
  produces traceable diagnostics.
* **Documenting** how an external operator can use it without
  internal context.
* **Measuring** (via controlled beta) whether the diagnostic is
  understandable and actionable for a human reader.

## What the project is **not** for

* Not a compliance tool. Not a security verdict. Not a merge
  gate. Not an MCP server. Not a provider-tool-calling demo.
  Not a public benchmark. Not a PyPI-stable release.

## The five-minute summary

If you read nothing else: `oida-code` makes claims about code
**checkable** by linking each claim to a tool result. The
report says "this claim has this evidence" or "this claim has
no evidence". It does not say "this code is safe". It is opt-in.
It is diagnostic. The default GitHub Action setting keeps the
gateway path off. The five completed Tier-5 cases
(`operator_soak_cases/case_001..005`) demonstrate the path on
real targets but are not generalisable to a population of PRs
without further validation.

The controlled beta (Phase 6.0) is the first external test of
"is this understandable to a human who is not the project
author?".

## Cross-references

* Project status: [`docs/project_status.md`](../project_status.md).
* Beta operator quickstart:
  [`docs/beta/beta_operator_quickstart.md`](../beta/beta_operator_quickstart.md).
* Known limits:
  [`docs/beta/beta_known_limits.md`](../beta/beta_known_limits.md).
* Gateway opt-in usage:
  [`docs/gateway_opt_in_usage.md`](../gateway_opt_in_usage.md).
* No-product-verdict policy:
  [`docs/security/no_product_verdict_policy.md`](../security/no_product_verdict_policy.md).
* Long-term backlog: [`BACKLOG.md`](../../BACKLOG.md).
