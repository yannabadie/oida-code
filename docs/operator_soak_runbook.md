# Operator soak runbook (public)

This runbook lets an external operator reproduce a controlled
gateway-grounded audit case end-to-end:

1. Pick a target.
2. Author a bundle.
3. Dispatch the workflow.
4. Triage the artefacts.
5. Write `label.json` + `ux_score.json` (operator-authored).
6. Refresh the aggregate.

It is the **public** runbook. The internal protocol document at
[`../operator_soak_cases/RUNBOOK.md`](../operator_soak_cases/RUNBOOK.md)
covers the project-internal cgpro orchestration; this file
documents what the operator role actually does, in the
operator's own voice.

> **Hard rules — non-negotiable.** No MCP. No provider
> tool-calling. No `pull_request_target`. No fork PR. No
> LLM-written `label.json` / `ux_score.json` (the schema can't
> enforce author identity, so the rule lives in policy and
> human discipline). No `total_v_net` / `debt_final` /
> `corrupt_success` emission. `enable-tool-gateway` stays
> default false at every layer.

## Step 1 — pick a target

A good soak target is:

- A public commit on a public Python repo. Pin the **full 40-char
  SHA**; never floating branch heads.
- A scoped change with a clear, named property: a CLI bug fix, a
  precondition, a new public-API capability, a deprecation
  removal, an observability claim with a regression test.
- Small enough that pytest on the relevant test file runs in
  under 30s on a stock Linux runner.
- Not one of the blacklisted high-traffic repos
  (numpy / django / fastapi / requests / pydantic / sqlalchemy /
  pytest itself / pallets/* if already covered).
- Not a monorepo, not a repo requiring a database, not a repo
  requiring non-trivial network calls during pytest.

Verify the SHA exists on the upstream:

```bash
gh api repos/<owner>/<name>/commits/<full-sha> --jq '{sha, message: .commit.message, author: .commit.author.name}'
```

## Step 2 — author the bundle

A bundle is 8 files in `operator_soak_cases/case_NNN_<short>/bundle/`:

```
approved_tools.json
gateway_definitions.json
packet.json
pass1_backward.json
pass1_forward.json
pass2_backward.json
pass2_forward.json
tool_policy.json
```

The fastest way to get started is to copy
`examples/gateway_opt_in/` and adapt:

```bash
cp -r examples/gateway_opt_in operator_soak_cases/case_006_<short>/bundle
```

Then edit:

- **`packet.json`** — change `event_id`, `intent_summary`
  (≤ 400 chars), the two `evidence_items` (≤ 400 chars each).
  Keep `allowed_fields` as `["capability", "tests_pass",
  "operator_accept"]` unless your claim type needs different
  Literal values.
- **`pass1_forward.json`** — change `event_id`, the `purpose`
  field on `requested_tools[0]` (≤ 200 chars), the `scope` to
  point at the test file(s) on the target repo.
- **`pass2_forward.json`** — change `event_id`, `claim_id`
  (use dotted form `C.<repo>.<short>`), `claim_type` (must be in
  the Literal allowlist: `capability_sufficient`,
  `benefit_aligned`, `observability_sufficient`,
  `precondition_supported`, `negative_path_covered`,
  `repair_needed`, `shadow_pressure_explained`), `statement`,
  `evidence_refs`.
- **`pass2_backward.json`** — change `event_id`, `claim_id`,
  `satisfied_evidence_refs`. Keep `necessary_conditions_met=true`.
- **`tool_policy.json`**, **`gateway_definitions.json`**,
  **`approved_tools.json`** — usually identical to the example.

### Pre-dispatch local gate (mandatory)

Always run the local gate before dispatching to GitHub Actions.
This catches bundle errors and adapter behavior issues an order of
magnitude faster than CI:

```bash
# Clone the target locally
git clone https://github.com/<owner>/<name> /tmp/<short>
cd /tmp/<short>
git checkout <full-sha>

# If the target needs an editable install (C extensions, console_scripts):
pip install -e .

# Verify pytest passes on the bundled scope
pytest <bundled-scope-from-pass1_forward.json> -v

# Run the verifier-grounded gate
cd <oida-code-repo>
BUNDLE=operator_soak_cases/case_NNN_<short>/bundle
python -m oida_code.cli verify-grounded \
  $BUNDLE/packet.json \
  --forward-replay-1 $BUNDLE/pass1_forward.json \
  --backward-replay-1 $BUNDLE/pass1_backward.json \
  --forward-replay-2 $BUNDLE/pass2_forward.json \
  --backward-replay-2 $BUNDLE/pass2_backward.json \
  --tool-policy $BUNDLE/tool_policy.json \
  --approved-tools $BUNDLE/approved_tools.json \
  --gateway-definitions $BUNDLE/gateway_definitions.json \
  --audit-log-dir .tmp/local_audit \
  --out .tmp/local_grounded_report.json \
  --repo-root /tmp/<short>
```

Expected output: `status=verification_candidate`,
`accepted_claims=[<your claim id>]`, `pytest_summary_line`
populated. If `status=blocked` or the claim is rejected /
unsupported, the bundle is wrong — fix it before proceeding.

## Step 3 — dispatch the workflow

Use the `operator-soak.yml` workflow_dispatch:

```bash
gh workflow run operator-soak.yml --ref main \
  -f case-id=case_NNN_<short> \
  -f target-repo=<owner>/<name> \
  -f target-ref=<full-sha> \
  -f target-install=<true|false> \
  -f bundle-dir=operator_soak_cases/case_NNN_<short>/bundle
```

`target-install: true` runs `pip install -e .` inside
`oida-target/` before the gateway step. Required for any target
whose tests need the package importable (C extensions, console
scripts, modules with relative imports beyond the source tree).

The workflow also accepts `output-dir` (default
`.oida/operator-soak`); leave at default for consistency with the
five existing cases.

Wait for the run to finish (~1-2 minutes typical), capture the
run ID, and verify success:

```bash
gh run list --branch main --limit 5 --workflow operator-soak.yml
gh run view <run-id> --json status,conclusion
```

## Step 4 — triage the artefacts

Download the artefact bundle:

```bash
mkdir -p .tmp/run_<run-id>
gh run download <run-id> -D .tmp/run_<run-id>
ls .tmp/run_<run-id>/oida-code-gateway/
# action_outputs.txt
# artifacts/
# audit/
# grounded_report.json
# summary.md
```

Read in this order:

1. `action_outputs.txt` — `gateway-status`, `leak-count`, paths.
2. `summary.md` — human-readable run summary.
3. `grounded_report.json` — authoritative structured output
   (overall status, accepted/rejected/unsupported claims,
   `tool_results[*].pytest_summary_line`,
   `enriched_evidence_refs`, etc.).
4. `audit/<yyyy-mm-dd>/<tool>.jsonl` — policy decisions, tool
   fingerprints, evidence refs.
5. `artifacts/manifest.json` — SHA-256 manifest with three
   Literal pins (`mode`, `official_fields_emitted: false`,
   `contains_secrets: false`).

Cross-check: forbidden-token scan over all artefacts must return
zero hits.

```bash
# Quick sanity scan — no forbidden product-verdict tokens
grep -rE "merge.safe|production.safe|bug.free|security.verified|total_v_net|debt_final|corrupt_success" .tmp/run_<run-id>/ || echo "clean"
```

See [`interpreting_gateway_reports.md`](interpreting_gateway_reports.md)
for the full set of "what each signal means / does NOT mean"
tables.

## Step 5 — write `label.json` + `ux_score.json` (operator-authored)

These two files are the **operator's verdict on the run's
diagnostic usefulness**. They cannot be authored by an LLM. The
schema cannot enforce author identity; the policy lives in writing
in this runbook, in `operator_soak_cases/README.md`, and in
ADR-42.

### `operator_soak_cases/case_NNN_<short>/label.json`

```json
{
  "operator_label": "useful_true_positive | useful_true_negative | false_positive | false_negative | unclear | insufficient_fixture",
  "operator_rationale": [
    "3 to 10 lines as an array of strings.",
    "First line says what was accepted/rejected and why.",
    "Following lines explain why the label fits.",
    "Last line names the concrete caveat operators should know."
  ],
  "labeled_by": "<who> — <when, in operator's own words>",
  "labeled_at": "<ISO-8601 timestamp>"
}
```

### `operator_soak_cases/case_NNN_<short>/ux_score.json`

```json
{
  "summary_readability": 0,
  "evidence_traceability": 0,
  "actionability": 0,
  "no_false_verdict": 0,
  "notes": "1-4 lines explaining each axis score. Score 0/1/2 each.",
  "scored_by": "<same as labeled_by>",
  "scored_at": "<ISO-8601 timestamp>"
}
```

The four UX axes:

- **summary_readability** (0/1/2) — was the run outcome clear from
  the summary alone, or did you need to dig into the JSON?
- **evidence_traceability** (0/1/2) — could you trace the cited
  evidence (event refs + tool result refs) back to concrete
  artefacts?
- **actionability** (0/1/2) — did the report give you enough to
  decide on a label without external context?
- **no_false_verdict** (0/1/2) — did the report avoid
  product-verdict framing
  ([`security/no_product_verdict_policy.md`](security/no_product_verdict_policy.md))?

## Step 6 — refresh the aggregate

```bash
python scripts/run_operator_soak_eval.py \
  --cases-root operator_soak_cases \
  --out-dir reports/operator_soak \
  --official-field-leaks 0 \
  --gateway-status verification_candidate=<count>
```

Inspect the regenerated `reports/operator_soak/aggregate.md`. The
recommendation Literal will reflect rule precedence:

```
leak>0                                    → fix_contract_leak
cases_completed<3                         → continue_soak
false_negative_count>=2                   → revise_gateway_policy_or_prompts
false_positive_count>=2                   → revise_report_ux_or_labels
cases_completed>=5 AND useful_rate>=0.6  → document_opt_in_path
otherwise                                 → continue_soak
```

`document_opt_in_path` (the current state) does NOT flip the
action default. `enable-tool-gateway` stays `"false"` regardless.

## Five completed reference cases

The five cgpro-labelled cases under
[`../operator_soak_cases/`](../operator_soak_cases/) span four
distinct VerifierClaimType Literal values and three install
strategies. New operators can read these end-to-end as worked
examples:

| Case | Target | Claim type | Strategy | Outcome |
|---|---|---|---|---|
| case_001_oida_code_self | yannabadie/oida-code self-audit | negative_path_covered | repo_root="." | useful_true_positive UX 2/2/2/2 |
| case_002_python_semver | python-semver/python-semver@0309c63 | negative_path_covered | cross-repo no-install | useful_true_positive UX 2/2/2/2 |
| case_003_markupsafe | pallets/markupsafe@7856c3d | observability_sufficient | cross-repo C-extension install | useful_true_positive UX 2/2/2/2 |
| case_004_python_slugify | un33k/python-slugify@7edf477 | precondition_supported | cross-repo CLI-precondition install | useful_true_positive UX 2/2/2/2 |
| case_005_voluptuous | alecthomas/voluptuous@4cef6ce | capability_sufficient | cross-repo capability install | useful_true_positive UX 2/2/2/2 |

## Troubleshooting

**`status=blocked` after dispatch.** Open `grounded_report.json`,
check `report.blockers` and `report.warnings`. Common causes:

- Schema validation error in `pass1_forward.json` (often the
  `purpose` field exceeded 200 chars, or `claim_type` is not in
  the Literal allowlist).
- Pytest emitted no evidence because the scope path is wrong on
  the target — re-verify `pass1_forward.requested_tools[0].scope`
  matches a file that actually exists at the pinned SHA.
- Pytest's terminal summary suppressed by `-q -q` collapse from
  target-side `addopts` (the adapter mitigates this with
  `-o addopts=` since Phase 5.9; if you see it on an older
  bundle, regenerate).

**`pytest_summary_line: null` despite `status=ok`.** Pytest didn't
emit a parseable terminal summary line. With the Phase 5.9 adapter
the most common cause is an unusual `addopts` config (e.g. `-rN
--no-summary`). Diagnostic — not blocking, but evidence_traceability
will be lower until the line surfaces.

**`gateway-official-field-leak-count != 0`.** Critical. Stop and
investigate. Some forbidden token leaked into a packet, evidence
item, or rendering. The aggregator's rule 1 fires
(`fix_contract_leak`); recommendation flips off `continue_soak`
to that.

**Workflow failed before the gateway step.** Read the workflow
run log step-by-step. The composite action's `Verify bundle
directory exists` step rejects path traversal, secret-shaped
filenames, and provider/MCP config in the bundle.
