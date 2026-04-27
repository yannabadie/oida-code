# Operator Soak Cases (Phase 5.7)

This directory holds the **controlled operator-soak fiches** for Phase 5.7 of
oida-code. Each subdirectory `case_<id>_<slug>/` is one controlled case the
opt-in gateway-grounded action path was (or will be) run against.

## Why this exists

ADR-41 (Phase 5.6) shipped an opt-in `enable-tool-gateway: "true"` path on the
composite Action with bundle validation, fork/PR guards, and a Literal-pinned
`gateway-status`. Before any wider adoption we need real operator labels —
**not LLM labels** — measuring whether the artefact bundle is actually useful
on real repos.

ADR-42 (Phase 5.7, this directory) defines the soak protocol: 3–5 controlled
repos / PRs, human-only labels, FP/FN counts, UX qualitative scores, and an
explicit decision rule (`continue_soak` until ≥3 completed cases).

## Directory layout

```
operator_soak_cases/
├── README.md                              ← this file (protocol overview)
└── case_<id>_<slug>/
    ├── README.md                          ← human-readable fiche
    ├── fiche.json                         ← machine-readable fiche metadata
    ├── label.json                         ← operator label (human-written only)
    └── ux_score.json                      ← operator UX scores (human-written only)
```

The JSON sidecars are what `scripts/run_operator_soak_eval.py` parses. The
README is what an operator reads when triaging the case.

## File contracts

### `fiche.json` — case metadata (operator authors / edits manually)

Required keys (see `src/oida_code/operator_soak/models.py` :: `OperatorSoakFiche`):

- `case_id` (string, matches dir name)
- `repo` (string, e.g. `yannabadie/oida-code`)
- `branch` (string)
- `commit` (string, full SHA)
- `operator` (string, GitHub handle)
- `intent` (string, plain-text summary of what the change does)
- `expected_risk` (`low` | `medium` | `high` | `unknown`)
- `gateway_bundle` (string, path to bundle dir, e.g. `tests/fixtures/...`)
- `workflow_run_id` (string or null until the action ran)
- `artifact_url` (string or null)
- `notes` (string)
- `status` (`awaiting_operator` | `awaiting_run` | `awaiting_label` | `complete` | `blocked`)

### `label.json` — operator label (rule: NO LLM may write this)

- `operator_label` ∈ {
    `useful_true_positive`, `useful_true_negative`,
    `false_positive`, `false_negative`,
    `unclear`, `insufficient_fixture`
  }
- `operator_rationale` (3–10 lines of plain text)
- `labeled_by` (GitHub handle)
- `labeled_at` (ISO-8601 UTC)

### `ux_score.json` — operator UX scores (rule: NO LLM may write this)

Each score ∈ {0, 1, 2}:

- `summary_readability` — Q1: GitHub Step Summary suffices to understand the result?
- `evidence_traceability` — Q2: `summary.md` clearly explains proven / not proven?
- `actionability` — Q3: `grounded_report.json` has enough to audit?
- `no_false_verdict` — Q4: report proposes useful action without faking a product verdict?
- `scored_by` (GitHub handle)
- `scored_at` (ISO-8601 UTC)

## Scoping rules (QA/A34 §5.7-A)

Use only:

1. oida-code self with a controlled minor change
2. small hermetic Python repo with a simple bug + test
3. simple real Python repo with import/test changes
4. repo with migration / config change
5. repo with explicit fail-to-pass / pass-to-pass

**Do not** use: massive monorepos, repos without tests, repos with heavy deps,
private repos with secrets, fork PRs, uncontrolled PRs.

## What is forbidden

Per QA/A34 §5.7-C:

- no `pull_request_target`
- no fork PR
- no external provider call (`llm-provider: "replay"` only)
- no secrets in artefacts
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-generated labels
- no auto-labelling from `gateway-status`

## Status of cases

This directory ships with `case_001_oida_code_self/` **scaffolded** but
deliberately **not labelled**: there is no controlled-change branch on this
repo today, so the case sits in `awaiting_run` and the aggregator will
correctly classify the soak as `cases_completed=0` →
`recommendation=continue_soak` per QA/A34 §5.7-F rule 1.

Adding a case is a four-step manual operator workflow:

1. Copy `case_001_oida_code_self/` → `case_<id>_<slug>/`, edit the JSON sidecars.
2. Run the action with `enable-tool-gateway: "true"` and the case bundle.
3. Operator triages artefacts and writes `label.json` + `ux_score.json` by hand.
4. Re-run `scripts/run_operator_soak_eval.py` to refresh `reports/operator_soak/aggregate.md`.
