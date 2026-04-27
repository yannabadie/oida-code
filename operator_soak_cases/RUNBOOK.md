# Operator Runbook — Phase 5.8 soak execution

This runbook is the **operator-only** procedure for running the opt-in
gateway action against a controlled case and writing human labels. Claude
prepared the cases (Phase 5.8-prep, QA/A36) but **did not** trigger any
workflow, did not author any `label.json`, and did not author any
`ux_score.json`.

The hard rule per QA/A34 §5.7-B and QA/A35 §5.8-C:

> Aucun label ne doit être généré par LLM. Aucun label ne doit être déduit
> automatiquement du gateway-status.

If you (the operator) ask Claude to "just write the label for you", Claude
must refuse. The point of this protocol is operator labels.

---

## Step 1 — Pick the case

Open `operator_soak_cases/` and pick a case directory. The committed
candidates:

| dir | recommended risk | status today |
|---|---|---|
| `case_001_oida_code_self/` | low | `awaiting_operator_run` (branch + commit ready) |
| `case_002_mini_python_bug/` | low | `awaiting_case_selection` (no upstream picked) |
| `case_003_import_contract/` | medium | `awaiting_case_selection` (no upstream picked) |

For `case_002` and `case_003`: pick a real upstream Python repo + commit
yourself, edit `fiche.json` (`repo`, `branch`, `commit`, `intent`,
`expected_risk`), and (ideally) replace the seeded `bundle/` files with a
real audit packet for the picked commit. If you keep the seeded bundle as
a placeholder, you must label the case `insufficient_fixture` to be
honest about the soak signal.

## Step 2 — Verify the branch / commit

For `case_001`:

```bash
git fetch origin operator-soak/case-001-docstring
git log -1 6585dd4d56613119b929924292f2d0367504d6bb
gh api repos/yannabadie/oida-code/commits/6585dd4d56613119b929924292f2d0367504d6bb \
  --jq '.commit.message,.commit.author.name'
```

For `case_002` / `case_003`: equivalent commands against the upstream you
picked. Don't trust a commit that doesn't `git log` cleanly.

## Step 3 — Trigger the workflow manually

GitHub allows manual `workflow_dispatch` from the API, the CLI, or the
Actions UI. Use any of the three; **do not** use `pull_request_target`,
**do not** dispatch from a fork, and **do not** schedule the run.

### 3.A — gh CLI

```bash
gh workflow run action-gateway-smoke.yml \
  --ref operator-soak/case-001-docstring \
  -f bundle-dir=operator_soak_cases/case_001_oida_code_self/bundle \
  -f case-id=case_001_oida_code_self
```

(adapt `--ref`, `-f bundle-dir`, `-f case-id` to the case you picked).

### 3.B — Actions tab UI

1. Open the repo's *Actions* tab.
2. Pick the `action-gateway-smoke` workflow.
3. Click *Run workflow*.
4. Select the branch (e.g. `operator-soak/case-001-docstring`).
5. Fill in the `bundle-dir` input and dispatch.

### 3.C — REST API

```bash
gh api repos/yannabadie/oida-code/actions/workflows/action-gateway-smoke.yml/dispatches \
  --method POST \
  -f ref=operator-soak/case-001-docstring \
  -f 'inputs[bundle-dir]=operator_soak_cases/case_001_oida_code_self/bundle'
```

Whatever path you use, **`enable-tool-gateway` must be `"true"`** for the
case to actually exercise the gateway. The default stays `"false"`; you
flip it per-dispatch.

### 3.D — guard rails

Before the workflow starts, the action's Phase 5.6 guard step
(`block-gateway-on-pr`) re-checks the event context. If it sees
`pull_request` or `pull_request_target`, the gateway path exits with a
clear `::error::`. If you see that error, you dispatched from the wrong
event — fix and retry, do not work around it.

## Step 4 — Capture the run identifiers

```bash
RUN_ID=$(gh run list --workflow action-gateway-smoke.yml --limit 1 --json databaseId --jq '.[0].databaseId')
echo "$RUN_ID"
gh run view "$RUN_ID" --log >/dev/null   # confirm the run exists
```

Edit the case's `fiche.json`:

```json
{
  "workflow_run_id": "<RUN_ID>",
  "artifact_url": "https://github.com/yannabadie/oida-code/actions/runs/<RUN_ID>"
}
```

Don't forge these. If the workflow failed, write the failure into `notes`
instead and skip ahead to step 7 with a `blocked` status.

## Step 5 — Read the artefacts in this exact order

GitHub renders `$GITHUB_STEP_SUMMARY` directly on the run page; that is
the operator UX surface. Read top to bottom:

1. **GitHub Step Summary** — the diagnostic Markdown table the action
   appends.
2. **`summary.md`** — the rendered gateway summary, downloaded from the
   `gateway-summary` artifact.
3. **`grounded_report.json`** — the verifier's structured output. Look
   for `findings`, `blockers`, `tool_calls`, and the `gateway_status`
   key.
4. **`audit/`** — the per-tool JSONL audit log. Each line is one tool
   call with `request`, `response`, `runtime_ms`, and `gated`.
5. **`artifacts/manifest.json`** — SHA256 of every uploaded file.

If you skip ahead and label without reading these in order, you risk
labelling on the Step Summary alone — which usually shows a clean state
even when `audit/` flags suspicious behaviour.

## Step 6 — Write `label.json` (operator-only)

Create `operator_soak_cases/<case>/label.json`. Use the template:

```json
{
  "operator_label": "useful_true_positive | useful_true_negative | false_positive | false_negative | unclear | insufficient_fixture",
  "operator_rationale": [
    "ligne 1 (3 lignes minimum, 10 maximum)",
    "ligne 2",
    "ligne 3"
  ],
  "labeled_by": "<your-github-handle>",
  "labeled_at": "<ISO-8601 UTC>"
}
```

(The schema accepts a single string with `\n` separators too — pick
whichever ergonomy suits you. The aggregator validates 3–10 lines either
way.)

Label semantics (re-read before deciding):

| label | meaning |
|---|---|
| `useful_true_positive` | gateway flagged a real concern that was actionable |
| `useful_true_negative` | gateway correctly stayed quiet on a non-issue |
| `false_positive` | gateway raised a flag that was not actionable |
| `false_negative` | you found a real concern the gateway missed |
| `unclear` | artefacts insufficient to decide |
| `insufficient_fixture` | bundle / replay / policy not adapted to the case |

**Never** delete or edit a `label.json` Claude wrote. Claude does not
write `label.json`. If one appears with `labeled_by: claude` or no
`labeled_by` at all, that's a bug — flag it and stop.

## Step 7 — Write `ux_score.json` (operator-only)

Create `operator_soak_cases/<case>/ux_score.json`. Each score is 0, 1, or
2. Template:

```json
{
  "summary_readability": 0,
  "evidence_traceability": 0,
  "actionability": 0,
  "no_false_verdict": 0,
  "scored_by": "<your-github-handle>",
  "scored_at": "<ISO-8601 UTC>"
}
```

Scoring rubric (per QA/A34 §5.7-G):

* **`summary_readability`** — does the GitHub Step Summary alone tell you
  what happened?
  * 0: no, you needed `grounded_report.json` to even guess
  * 1: partly — gives the headline, hides the why
  * 2: yes — the Step Summary is sufficient
* **`evidence_traceability`** — does `summary.md` clearly state what is
  proven vs. not proven?
  * 0: no — claims float without evidence references
  * 1: partly — some claims have IDs, others don't
  * 2: yes — every claim resolves to an evidence ID
* **`actionability`** — is `grounded_report.json` audit-grade?
  * 0: no — too sparse to act
  * 1: partly — enough to ask follow-up questions
  * 2: yes — directly actionable
* **`no_false_verdict`** — does the report avoid product-verdict labels
  (merge-safe, production-safe, bug-free)?
  * 0: no — a forbidden token leaked somewhere
  * 1: partly — borderline phrasing
  * 2: yes — diagnostic only

## Step 8 — Refresh the aggregate

From the repo root, on `main`:

```bash
python scripts/run_operator_soak_eval.py \
  --cases-root operator_soak_cases \
  --out-dir reports/operator_soak \
  --gateway-status diagnostic_only=<n> \
  --gateway-status blocked=<m> \
  --official-field-leaks 0
```

(Adjust `--gateway-status` from what you observed across all completed
runs. `--official-field-leaks` MUST stay 0; if it's not, the
recommendation will lock to `fix_contract_leak` and the soak is over.)

This regenerates `reports/operator_soak/aggregate.{json,md}`. Commit
those files alongside the updated case fiches + new `label.json` /
`ux_score.json` files.

## Things you should NEVER do

* trigger the workflow on a fork PR
* trigger the workflow on `pull_request_target`
* dispatch with `enable-tool-gateway: "true"` on `main` directly (use a
  controlled branch like `operator-soak/case-NNN-…`)
* edit `aggregate.json` by hand to make the recommendation prettier
* delete a `false_negative` because it makes the slate look bad
* let an LLM write `label.json` or `ux_score.json`
* schedule an autonomous agent to audit the results
* claim `merge-safe` / `production-safe` / `bug-free` anywhere

If you catch yourself reaching for any of these, stop and revisit ADR-42
(`memory-bank/decisionLog.md`).

## After at least 3 cases are `complete`

The aggregator's `recommendation` becomes non-trivial. Possible outcomes:

| recommendation | meaning |
|---|---|
| `continue_soak` | not enough data yet |
| `fix_contract_leak` | hard wall breach (ADR-22); halt and patch |
| `revise_gateway_policy_or_prompts` | ≥2 false-negatives — the gateway missed real concerns |
| `revise_report_ux_or_labels` | ≥2 false-positives — the gateway over-flagged or the report is unreadable |
| `document_opt_in_path` | ≥5 cases, usefulness ≥0.6, FP<2, FN<2 — Phase 5.9 path |

Even `document_opt_in_path` does NOT flip `enable-tool-gateway` default.
That stays `"false"` until a separate ADR explicitly authorises it.
