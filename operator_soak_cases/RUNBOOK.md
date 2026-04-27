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
| `case_001_oida_code_self/` | low | `awaiting_operator_dispatch` (branch + commit + REAL audit packet ready) |
| `case_002_python_semver/` | low | `awaiting_real_audit_packet_decision` (`cgpro` selected `python-semver/python-semver` PR #292 / commit `0309c63`; bundle still seeded) |
| `case_003_markupsafe/` | medium | `awaiting_real_audit_packet_decision` (`cgpro` selected `pallets/markupsafe` PR #261 / commit `7856c3d`; bundle still seeded) |

For `case_002` and `case_003`, the seeded `bundle/` does NOT describe
the real upstream change. Decide: generate a real audit packet,
replace the case, or label `insufficient_fixture` honestly. Per
QA/A38, only `case_001` has a real audit packet during 5.8-prep.

## Step 2 — Verify the branch / commit

For `case_001`:

```bash
git fetch origin operator-soak/case-001-docstring
git log -1 6585dd4d56613119b929924292f2d0367504d6bb
gh api repos/yannabadie/oida-code/commits/6585dd4d56613119b929924292f2d0367504d6bb \
  --jq '.commit.message,.commit.author.name'
```

For `case_002`:

```bash
gh api repos/python-semver/python-semver/commits/0309c63ce834b7d35aa3e29b8d5bb0357532b016 \
  --jq '.sha,.commit.message'
gh api repos/python-semver/python-semver/commits/0309c63ce834b7d35aa3e29b8d5bb0357532b016/pulls \
  -H 'Accept: application/vnd.github+json' \
  --jq '.[].html_url'
```

For `case_003` (`pallets/markupsafe` PR #261):

```bash
gh api repos/pallets/markupsafe/commits/7856c3d945a969bc94a19989dda61c3d50ac2adb \
  --jq '.sha,.commit.message'
gh api repos/pallets/markupsafe/commits/7856c3d945a969bc94a19989dda61c3d50ac2adb/pulls \
  -H 'Accept: application/vnd.github+json' \
  --jq '.[].html_url'
```

Don't trust a commit that doesn't verify cleanly.

## Step 3 — Trigger the workflow manually

GitHub allows manual `workflow_dispatch` from the API, the CLI, or the
Actions UI. Use any of the three; **do not** use `pull_request_target`,
**do not** dispatch from a fork, and **do not** schedule the run.

The dedicated workflow for operator soak is
**`.github/workflows/operator-soak.yml`** — distinct from
`action-gateway-smoke.yml` (which stays a stable CI smoke against the
fixed Phase 5.6 fixture). Soak runs are **manual, parametric, and
expected to vary per case**; mixing them with the smoke would make
both signals harder to read.

### 3.A — gh CLI (recommended)

For `case_001`:

```bash
gh workflow run operator-soak.yml --ref main \
  -f case-id=case_001_oida_code_self \
  -f target-ref=operator-soak/case-001-docstring \
  -f bundle-dir=operator_soak_cases/case_001_oida_code_self/bundle \
  -f output-dir=.oida/operator-soak/case_001_oida_code_self
```

The `--ref main` flag tells GitHub to **run the workflow YAML from
`main`** — that's where `operator-soak.yml` is committed. The
`target-ref` input is the branch the workflow checks out as the audit
subject.

### 3.B — Actions tab UI

1. Open the repo's *Actions* tab.
2. Pick the `operator-soak` workflow.
3. Click *Run workflow*.
4. Leave the branch dropdown on `main` (the workflow itself runs from
   main; the audit target is the `target-ref` input).
5. Fill in the four inputs (`case-id`, `target-ref`, `bundle-dir`,
   `output-dir`) and dispatch.

### 3.C — REST API

```bash
gh api repos/yannabadie/oida-code/actions/workflows/operator-soak.yml/dispatches \
  --method POST \
  -f ref=main \
  -f 'inputs[case-id]=case_001_oida_code_self' \
  -f 'inputs[target-ref]=operator-soak/case-001-docstring' \
  -f 'inputs[bundle-dir]=operator_soak_cases/case_001_oida_code_self/bundle' \
  -f 'inputs[output-dir]=.oida/operator-soak/case_001_oida_code_self'
```

The workflow always invokes the composite action with
`enable-tool-gateway: "true"` and `gateway-fail-on-contract: "false"`
internally (per QA/A38 §1) — operators don't flip those per dispatch.

### 3.D — guard rails

The `operator-soak.yml` workflow only triggers on `workflow_dispatch`
(no `push`, no `pull_request*`, no `schedule`). The composite action's
Phase 5.6 fork/PR guard (`block-gateway-on-pr`) is also still active
defence-in-depth — if a future workflow file accidentally adds a
PR-context trigger, the guard exits with `::error::`. Don't try to
work around it; fix the workflow.

## Step 4 — Capture the run identifiers

```bash
RUN_ID=$(gh run list --workflow operator-soak.yml --limit 1 --json databaseId --jq '.[0].databaseId')
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

Create `operator_soak_cases/<case>/label.json`. The QA/A38 §5 minimal
template is:

```json
{
  "operator_label": "useful_true_positive",
  "operator_rationale": [
    "Line 1: what the gateway surfaced.",
    "Line 2: why it was or was not useful.",
    "Line 3: what action the operator would take."
  ]
}
```

Replace the `useful_true_positive` literal with one of the six allowed
labels (see the rubric below). `operator_rationale` must have **3 to
10 entries**. Provenance fields are optional but recommended:

```json
{
  "operator_label": "...",
  "operator_rationale": [...],
  "labeled_by": "<your-github-handle>",
  "labeled_at": "<ISO-8601 UTC>"
}
```

(The schema also accepts a single string with `\n` separators in
`operator_rationale` for backwards compatibility — pick whichever
ergonomy suits you. The aggregator validates 3–10 lines either way.)

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

Create `operator_soak_cases/<case>/ux_score.json`. Each score is 0, 1,
or 2. The QA/A38 §5 minimal template is:

```json
{
  "summary_readability": 0,
  "evidence_traceability": 0,
  "actionability": 0,
  "no_false_verdict": 0,
  "notes": ""
}
```

Provenance fields (`scored_by` / `scored_at`) are optional but
recommended:

```json
{
  "summary_readability": 0,
  "evidence_traceability": 0,
  "actionability": 0,
  "no_false_verdict": 0,
  "notes": "<free-text qualitative comment>",
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
