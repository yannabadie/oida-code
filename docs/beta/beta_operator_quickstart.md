# Beta operator quickstart (10-minute read)

This guide is for `oida-code` controlled-beta operators. It assumes
you are not the project author. It assumes you are a Python
developer comfortable with GitHub PRs, `pytest`, `mypy`, and
`ruff`. It assumes you have read
[`beta_known_limits.md`](beta_known_limits.md) — read that first
if you have not.

The 10-minute promise:
* 1 minute — what `oida-code` does and does not do.
* 1 minute — how it differs from a linter / a code review bot / a
  copilot.
* 3 minutes — how to launch a beta run.
* 3 minutes — how to read the artefacts.
* 2 minutes — how to fill the feedback form.

## 1. What `oida-code` does

`oida-code` reads a **bundle** describing a single named claim
about a target codebase, runs deterministic tools (`pytest`,
`mypy`, `ruff`, `semgrep`) scoped to that claim, and produces a
**diagnostic report** showing whether the bundle's claim is
**grounded** in the tool output.

The report names the claim, the evidence items, and the link
between them. It does **not** name a verdict. The defining phrase:

> `oida-code` does not say "this PR is safe". It shows which claims
> are supported by which evidence, which evidence is missing, and
> why official fields stay blocked.

## 2. How it differs from existing tools

| Tool category | What it gives you | What `oida-code` gives you |
|---|---|---|
| Linter (ruff, eslint) | Style and correctness alerts on the entire file. | Whether a **named claim** is supported by a **scoped pytest run**. |
| PR review bot | English-language review comments, often free of evidence. | Each claim **linked to a tool result**; English without evidence is rejected by the runners. |
| Copilot / refactor agent | A diff suggestion. | No diff. A diagnostic about what the existing diff already implies and whether the implication is grounded. |
| LLM-as-judge | A pass/fail with no audit trail. | The **audit trail itself** plus the rejection of any `merge-safe` / `production-safe` / `bug-free` / `verified` token. |
| GitHub App / Checks | A green / red check that gates merge. | An artefact + Step Summary. The composite Action is opt-in and the gateway path is opt-in inside that. No merge gate. |

If you have not used a "verifier loop" before: the closest
analogue is "a property-based test plus a structured argument
tracing the test back to a named property". `oida-code` makes the
named property explicit and rejects responses that claim the
property without naming the test that demonstrates it.

## 3. How to launch a beta run

There are three launch options; pick whichever matches your
context.

### Option A — local CLI (fastest, no GitHub run)

```bash
git clone https://github.com/yannabadie/oida-code.git
cd oida-code
python -m pip install -e ".[dev]"
python -m oida_code verify-grounded \
    --packet examples/gateway_opt_in/packet.json \
    --pass1-forward examples/gateway_opt_in/pass1_forward.json \
    --pass1-backward examples/gateway_opt_in/pass1_backward.json \
    --pass2-forward examples/gateway_opt_in/pass2_forward.json \
    --pass2-backward examples/gateway_opt_in/pass2_backward.json \
    --tool-policy examples/gateway_opt_in/tool_policy.json \
    --gateway-definitions examples/gateway_opt_in/gateway_definitions.json \
    --approved-tools examples/gateway_opt_in/approved_tools.json \
    --repo-root . \
    --out-dir .oida/quickstart
```

Result: `.oida/quickstart/grounded_report.json` and
`.oida/quickstart/summary.md`. This runs the keystone example
shipped with the repo (a self-audit on `oida-code` itself). It
proves your environment can run the tool. It is **not** a beta
case yet — it's the smoke test.

### Option B — workflow_dispatch on a target repo

Pick a target repo of yours (small, Python, simple build, no
secrets). Author a bundle (use
[`beta_case_template.md`](beta_case_template.md)). Then:

```bash
gh workflow run operator-soak \
  -f target_repo=<owner/name> \
  -f target_ref=<sha> \
  -f bundle_dir=beta_cases/beta_case_<n>/bundle \
  -f enable_tool_gateway=true \
  -f target_install=<auto-detect|none|pip-e|pip-deps>
gh run watch
```

Result: a GitHub Actions run with artefacts (`grounded_report.json`,
`summary.md`, `audit.log`, `manifest.json`). The run id and
artifact url go into your beta case file.

### Option C — composite Action input on your repo's CI

Add the composite Action to a workflow in your repo:

```yaml
- name: oida-code grounded verifier (opt-in beta)
  uses: yannabadie/oida-code@<sha>
  with:
    enable-tool-gateway: 'true'
    bundle-dir: '.oida/bundle'
    target-install: 'auto-detect'
```

The default of `enable-tool-gateway` is `false`. You set it to
`true` per workflow run, not project-wide. The action does not
have write permissions; it does not reach external networks
(other than the explicit `actions/checkout` clone of the target).

## 4. How to read the artefacts (3 minutes)

Read them in this order. Each artefact has a specific job; if you
read them out of order the diagnostic will look ambiguous.

### 4.1 — GitHub Step Summary (10 seconds)

Top of the run page. One paragraph, three bullets:

* **Claim:** `C.<surface>.<claim>`
* **Verification candidate:** `true` or `false`
* **Gateway status:** `diagnostic_only`

If the gateway status is anything other than `diagnostic_only`,
that is a project bug. Stop and report it.

### 4.2 — `summary.md` (1 minute)

Markdown report. Read it top-to-bottom. Look for:

* The named claim repeated verbatim from your packet.
* The evidence items listed with their summary (≤ 400 chars).
* The grounded / not-grounded sentence per claim.
* The honesty footer ("does not say ‘this PR is safe' …").

If `summary.md` claims a product verdict (`merge-safe`, etc.),
that is a contract violation. Stop and report it.

### 4.3 — `grounded_report.json` (1 minute)

The structured form. Open it; verify:

* `gateway_status: "diagnostic_only"`
* `official_fields_emitted: false`
* `total_v_net`, `debt_final`, `corrupt_success` — all null or
  absent.
* `verification_candidate: true|false` — matches the Step Summary.

If any official field has a non-null value, that is a contract
violation. Stop and report it.

### 4.4 — `audit.log` (30 seconds first / last)

Per-tool-call narrative. Read the first 20 lines and the last
20 lines. The first 20 should show the bundle being loaded and
the policy being applied; the last 20 should show the verifier
loop closing. If the last 20 lines show a partial pass or an
unhandled exception, the run is broken — report it.

### 4.5 — `manifest.json` (10 seconds)

Lists every artefact written, with byte sizes. Skim it. If a
file is `0 bytes`, the run is broken — report it.

## 5. How to fill the feedback form (2 minutes)

Open [`beta_feedback_form.md`](beta_feedback_form.md). Copy the
**Form (one per run)** YAML block. Fill the placeholders. Be
honest about scores — a form full of `2`s without reasons is less
useful than mixed scores with specific complaints.

Submit it via the path described in the form (case directory or
tracking issue).

## What you should NOT do

* Do not edit the public surface of the schemas.
* Do not author a bundle that adds claims outside the
  `LLMEvidencePacket.allowed_fields` Literal allowlist.
* Do not try to flip `enable-tool-gateway` to default-true.
* Do not run on a target with secrets, on a fork PR, or on a
  monorepo larger than ~20k Python LoC. The beta does not
  support those.
* Do not ask an LLM to fill the feedback form for you.
* Do not interpret a `verification_candidate: true` as "merge it".
  See [`beta_known_limits.md`](beta_known_limits.md).

## What you should expect

* **Bundle authoring time is unmeasured.** Earlier drafts of this
  doc estimated "30-60 minutes for an experienced Python
  developer"; that estimate was author intuition, not measurement,
  and the AI-tier cold-reader review found the estimate
  inconsistent with `beta_known_limits.md` calling the same
  process "non-trivial / first external test of feasibility". The
  honest answer is: **plan for as long as it takes**, record what
  you observe in `setup_friction`. Measuring the actual time is
  exactly what the controlled beta tests.
* The first run is the slow one. Subsequent runs on the same
  bundle are fast.
* Some runs will return `verification_candidate: false`. That is
  not a bug; it is a real diagnostic outcome. Report what you
  observed.

## Cross-references

* Known limits: [`beta_known_limits.md`](beta_known_limits.md).
* Feedback form: [`beta_feedback_form.md`](beta_feedback_form.md).
* Case template: [`beta_case_template.md`](beta_case_template.md).
* Gateway opt-in usage: [`docs/gateway_opt_in_usage.md`](../gateway_opt_in_usage.md).
* Interpretation guide: [`docs/interpreting_gateway_reports.md`](../interpreting_gateway_reports.md).
* Operator soak runbook (the deeper doc): [`docs/operator_soak_runbook.md`](../operator_soak_runbook.md).
* Plain-language overview: [`docs/concepts/oida_code_plain_language.md`](../concepts/oida_code_plain_language.md).
