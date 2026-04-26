# Phase 4.6 — Real-runner / operator smoke

**Date**: 2026-04-29.
**Scope**: QA/A23.md — close the three operational gaps the
Phase 4.5 report flagged: (1) composite action never invoked from
a real consumer workflow, (2) fork-PR fence asserted by string
match only, (3) SARIF upload step never exercised against GitHub
Code Scanning ingestion. Plus Node 24 compatibility (GitHub
default switch 2026-06-02).
**Authority**: ADR-31 (Real-runner / operator smoke before MCP /
tool-calling).
**Reproduce**:

```bash
python scripts/validate_github_workflows.py
python -m pytest tests/test_phase4_5_ci_github_action.py \
                  tests/test_phase4_6_real_runner_smoke.py -v

# On GitHub-hosted runner:
gh workflow run sarif-upload.yml      # manual SARIF smoke
gh workflow run action-smoke.yml      # consumer smoke
```

**Verdict (TL;DR)**: three new workflows landed and went green on
real GitHub-hosted runners. The composite action's first real
invocation surfaced a latent bug
(`${{ github.workspace }}` inside `inputs.repo-path.description`,
rejected by GitHub's manifest loader); fixed and locked behind a
regression test before declaring done. SARIF upload confirmed
visible in GitHub Code Scanning via the `code-scanning/analyses`
API. Fork-PR fence smoke and provider regression baseline are
explicitly **not_run** with reasons (no fork exists; no API
budget allocated) — Phase 4.6 ships as "operationally validated
on the surfaces we own; partially open on the surfaces we don't".

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-31 | +110 |
| `.github/workflows/ci.yml` | Adds `node24-compat` job (FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true at job scope; runs validator + Phase 4.5 + Phase 4.6 tests under Node 24) | +30 |
| `.github/workflows/action-smoke.yml` | NEW — composite-action consumer smoke (`uses: ./`, replay-only, no SARIF, fetch-depth:2) | +60 |
| `.github/workflows/sarif-upload.yml` | NEW — manual workflow_dispatch only; `security-events: write` job-scoped; uses `codeql-action/upload-sarif@v3` | +75 |
| `action.yml` | Fix latent bug — `inputs.repo-path.description` had `${{ github.workspace }}` which GitHub's manifest loader rejects | ~5 |
| `tests/test_phase4_6_real_runner_smoke.py` | NEW — 15 invariants: 4 node24-compat job, 5 action-smoke workflow, 5 sarif-upload workflow, 1 action-input-description regression | +290 |
| `reports/phase4_6_real_runner_operator_smoke.md` | this report | — |

**Gates**: ruff clean, mypy clean (84 src files), **541 passed +
4 skipped**, validator OK, three real-runner runs green
(detailed in §3–6 below).

---

## 2. ADR-31 excerpt

> Phase 4.5 was accepted end-to-end on commit f625b1c. The Phase
> 4.5 report explicitly listed three operational gaps that
> remained structural-only [...]. QA/A23.md requires Phase 4.6 to
> close those operational gaps before opening the MCP /
> tool-calling chantier.

Decision (full text in `memory-bank/decisionLog.md` §[2026-04-29
03:00:00]):

* Node 24 compat job at job scope, runs validator + Phase
  4.5/4.6 invariants
* composite-action consumer smoke via `uses: ./`, replay-only
* SARIF upload via `workflow_dispatch` only, `security-events:
  write` job-scoped
* fork-PR fence + provider regression baseline = `not_run` with
  explicit reasons; do not fake.

---

## 3. Node 24 compatibility

**Why now**: GitHub announced runners default to Node 24 from
2026-06-02. Node 20 actions still work via opt-in
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`; testing it today
catches any vendor-incompatibility before it becomes a hard
blocker.

**Implementation** (`ci.yml` `node24-compat` job):

```yaml
node24-compat:
  name: Node 24 compatibility
  runs-on: ubuntu-latest
  permissions:
    contents: read
  env:
    FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - run: python scripts/validate_github_workflows.py
    - run: python -m pytest tests/test_phase4_5_ci_github_action.py -q
    - run: python -m pytest tests/test_phase4_6_real_runner_smoke.py -q
```

**Real-runner result** (run id `24948296296`, commit `a9de514`):

```yaml
node24_compat:
  status: pass
  run_id: 24948296296
  commit: a9de5141aa32afd1d9da644a4ce03711c36a5e69
  duration_s: 33      # observed
  jobs_green:
    - ruff
    - mypy
    - pytest
    - calibration-eval (replay)
    - workflow security smoke
    - Node 24 compatibility
```

**Tests** (`test_phase4_6_real_runner_smoke.py`):

* `test_ci_has_node24_compat_job`
* `test_node24_job_sets_force_javascript_actions_to_node24`
* `test_node24_job_does_not_use_external_provider`
* `test_node24_job_permissions_read_only`

---

## 4. Composite action consumer smoke

**Why now**: Phase 4.5 tests parsed `action.yml` structurally
but never EXECUTED it. The first real invocation surfaced one
latent bug (§4.2).

**Implementation** (`.github/workflows/action-smoke.yml`):

```yaml
name: action-smoke

on:
  workflow_dispatch: {}
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  consumer-smoke:
    name: composite action smoke
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2          # for `base-ref: HEAD~1`
          persist-credentials: false
      - uses: ./
        with:
          repo-path: "."
          base-ref: "HEAD~1"
          output-dir: ".oida/action-smoke"
          upload-sarif: "false"
          fail-on: "none"
          surface: "impact"
          enable-shadow: "false"
          llm-provider: "replay"
          max-provider-cases: "0"
```

### 4.1 Real-runner result

```yaml
composite_action_smoke:
  status: pass
  run_id: 24948296297
  commit: a9de5141aa32afd1d9da644a4ce03711c36a5e69
  duration_s: 51
  artifact: oida-code-audit
  step_summary_present: true
  permissions_observed:
    contents: read
  external_http_calls: 0
  secrets_used: none
```

### 4.2 Latent bug surfaced and fixed

The first action-smoke run on commit `d32fc1f` (id 24948235707)
failed with:

```
##[error]/home/runner/.../action.yml (Line: 19, Col: 18):
Unrecognized named-value: 'github'.
Located at position 1 within expression: github.workspace
```

`inputs.repo-path.description` in `action.yml` was:

```yaml
repo-path:
  description: Path to the repo to audit (relative to ${{ github.workspace }}).
```

GitHub's action manifest loader REJECTS `${{ ... }}` expressions
inside `inputs.<name>.description` — descriptions are static
metadata, parsed at action-load time, not runtime. Phase 4.5's
17 invariant tests parsed the YAML but never executed the
action, so the bug shipped silently.

**Fix** (commit `a9de514`):

1. `action.yml` — rewrite `inputs.repo-path.description` as
   plain text without expression interpolation.
2. `tests/test_phase4_6_real_runner_smoke.py` — new regression
   `test_action_inputs_descriptions_have_no_expression_interpolation`
   walks every `inputs.<name>.description` and rejects any
   `${{ ... }}` substring. Locks the surface so the same shape
   of bug never re-ships.

This is the kind of class of bug that only surfaces on real-
runner invocation; the regression test makes it catchable
locally going forward.

### 4.3 Tests

* `test_action_smoke_workflow_exists`
* `test_action_smoke_uses_local_action`
* `test_action_smoke_replay_only`
* `test_action_smoke_does_not_use_pull_request_target`
* `test_action_smoke_workflow_permissions_read_only`
* `test_action_inputs_descriptions_have_no_expression_interpolation`

---

## 5. Fork PR fence smoke

```yaml
manual_fork_pr_smoke:
  status: not_run
  pr_url: ~
  run_id: ~
  observed_behavior: ~
  reason: |
    No fork of yannabadie/oida-code exists at commit a9de514. The
    fence is asserted structurally by Phase 4.5 test
    `test_action_blocks_external_provider_on_pull_request_forks`
    (walks `runs.steps[*].if` and confirms `openai-compatible`,
    `head.repo.full_name`, and `github.repository` all sit inside
    the same `if:` clause). The structural test guarantees the
    surface stays clean against future refactors. The empirical
    fork-PR run is deferred to the first operator-driven fork PR.
  next_step: |
    When the first fork PR opens against this repo, this section
    becomes:
      status: pass | failed
      pr_url: <url>
      run_id: <id>
      observed_behavior: |
        - external provider blocked before any HTTP call
        - no secret accessed
        - no env-var leak
        - official fields absent
```

QA/A23.md is explicit: "ne fake pas le résultat. Marque not_run
et garde Phase 4.6 partiellement ouverte." This block stays open.

---

## 6. SARIF ingestion smoke

**Implementation** (`.github/workflows/sarif-upload.yml`):

```yaml
on:
  workflow_dispatch:
    inputs:
      base-ref:
        default: "HEAD~1"

permissions:
  contents: read

jobs:
  upload:
    permissions:
      contents: read
      security-events: write   # JOB-scoped, never workflow-scoped
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - env:
          BASE_REF: ${{ inputs.base-ref }}
        run: |
          python -m oida_code.cli audit . \
            --base "$BASE_REF" \
            --format sarif \
            --out .oida/report.sarif \
            --fail-on none
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: .oida/report.sarif
          category: oida-code
```

### 6.1 Real-runner result

```yaml
sarif_upload:
  status: pass
  run_id: 24948316005
  commit: a9de5141aa32afd1d9da644a4ce03711c36a5e69
  triggered_by: workflow_dispatch
  permissions_observed:
    workflow_level:
      contents: read
    upload_job:
      contents: read
      security-events: write
  code_scanning_visible: true
  ingested_analyses:
    sarif_id: 3f40cd46-4129-11f1-90ee-8add715f88c8
    category: oida-code
    tools:
      - { name: ruff,        results: 125, rules: 14 }
      - { name: mypy,        results: 215, rules: 12 }
      - { name: pytest,      results: 0,   rules: 0 }
      - { name: hypothesis,  results: 0,   rules: 0 }
      - { name: semgrep,     results: 0,   rules: 0 }
      - { name: CodeQL,      results: 0,   rules: 0 }
  query_used: gh api repos/yannabadie/oida-code/code-scanning/analyses
```

`code_scanning_visible: true` is confirmed via the
`/code-scanning/analyses` API endpoint — six analyses ingested
at `2026-04-26T04:34:44Z`, all tied to the upload run's commit
SHA. The `oida-code` category attribution is preserved
end-to-end, so a future PR diff will be able to surface deltas
inline.

### 6.2 Tests

* `test_sarif_upload_workflow_exists`
* `test_sarif_upload_workflow_dispatch_only`
* `test_sarif_upload_security_events_write_scoped_to_upload_job`
* `test_sarif_upload_uses_codeql_action`
* `test_sarif_upload_no_external_provider`

---

## 7. Optional provider regression baseline

```yaml
provider_regression_baseline:
  status: not_run
  run_id: ~
  reason: |
    No API budget allocated for this commit window. The
    workflow_dispatch entrypoint exists today via
      oida-code calibration-eval datasets/calibration_v1 \
        --llm-provider openai-compatible \
        --provider-profile deepseek \
        --api-key-env DEEPSEEK_API_KEY \
        --max-provider-cases 4
    A separate workflow file is intentionally NOT shipped in
    Phase 4.6 — adding one before allocating budget creates a
    one-click foot-gun. When budget is allocated, Phase 4.7 will
    add `.github/workflows/provider-baseline.yml` with
    workflow_dispatch only, secrets context only, ::add-mask:: on
    any dynamic sensitive value, and the headline metrics output
    as a build artifact (NOT a public benchmark).
```

QA/A23.md §4.6-E explicitly marks this block optional and
deferrable. We defer.

---

## 8. Secrets / permissions review

| Surface | Workflow perms | Job perms | Secrets | External provider |
|---|---|---|---|---|
| `ci.yml` | `contents: read` | per-job `contents: read` | none | replay only |
| `ci.yml` `node24-compat` | inherits | `contents: read` (explicit) | none | replay only |
| `action-smoke.yml` | `contents: read` | `contents: read` (explicit) | none | replay only |
| `sarif-upload.yml` | `contents: read` | `contents: read` + `security-events: write` (UPLOAD JOB ONLY) | none | replay only |
| `action.yml` runtime | inherits caller | inherits caller | none in body — `secrets.*` never referenced | default `replay`; fork-PR `openai-compatible` blocked structurally |

* No workflow uses `pull_request_target` (validator §2 enforces;
  Phase 4.5/4.6 tests assert).
* No workflow grants `security-events: write` at workflow scope
  (Phase 4.5 §A enforces; new Phase 4.6 sarif-upload test
  re-checks).
* No `${{ secrets.* }}` reference in any `run:` block (validator
  §5; new sarif-upload workflow honors this even though it could
  technically read GitHub-provided `GITHUB_TOKEN` — we don't).
* No PR-controlled `${{ inputs.* / github.head_ref / … }}` in
  any `run:` block (validator §6, Phase 4.5.1 hardening).
* No `${{ ... }}` expression in any input description (Phase 4.6
  regression test, after action-smoke surfaced the bug).

---

## 9. Known limitations

1. **Fork-PR fence not exercised on a real fork.** §5 captures
   this with `status: not_run` and the structural guarantee from
   Phase 4.5. The first operator-driven fork PR closes this gap.
2. **Provider regression baseline deferred to Phase 4.7.** §7.
3. **Node 20 deprecation annotations remain.** GitHub still flags
   `actions/checkout@v4`, `actions/setup-python@v5`,
   `actions/upload-artifact@v4`, and
   `github/codeql-action/upload-sarif@v3` as Node-20-bound. The
   Node 24 compat job proves we run cleanly under Node 24 via
   the opt-in env var; the action-vendor releases that drop the
   Node 20 dependency entirely are out of our hands. Action:
   bump pins as soon as the vendors ship Node-24-only releases.
4. **`codeql-action/upload-sarif@v3` deprecation** — GitHub
   announced v3 sunset in December 2026 (annotation observed on
   sarif-upload run `24948316005`). Bump to v4 when released; if
   v4 ships before December 2026 we move; otherwise stay on v3
   until the last possible moment. Tracked as Phase 4.7 work.
5. **No SARIF code-scanning UI screenshot in this report.** §6.1
   confirms ingestion via API; the visual UI surface is a
   subjective check that an operator can perform via
   `https://github.com/yannabadie/oida-code/security/code-scanning`.
6. **The `action.yml` smoke audits the repo against itself.**
   ADR-16 self-audit fork guard ensures the spawned pytest
   doesn't recursively re-invoke the CLI; this works on Linux
   too (verified by green run id 24948296297). A heterogeneous
   target repo would exercise a different code path; that's
   Phase 4.7+ scope.

---

## 10. Recommendation for Phase 4.7

Three candidates, ranked by what closes the remaining "promised
but not validated" claims fastest:

1. **Phase 4.7 — provider regression baseline on calibration_v1.**
   Allocate API budget (DeepSeek + 1-2 alternatives via
   `--max-provider-cases 4`); add
   `.github/workflows/provider-baseline.yml` with
   `workflow_dispatch` only; capture metrics as artifact.
   Output: `reports/phase4_7_provider_regression_baseline.md` —
   contract compliance only, no production claim.
2. **Phase 4.8 — MCP / provider tool-calling design ADR.**
   Design-only; no code. Forces the explicit ADR before
   committing to MCP machinery.
3. **Phase 4.9 — artifact UX polish.** Markdown report rendering
   (drop the 80-line head-cut for full-section navigation),
   SARIF category disambiguation, step summary prettification.
   Lower stakes; can be punted.

QA/A23.md's "Après Phase 4.6" block lists these in the same
order. I'd keep that order.

---

## 11. Gates

| Gate | Status | Notes |
|---|---|---|
| Ruff | green | `src/ tests/ scripts/...` |
| Mypy | green | 84 source files clean |
| Pytest | 541 passed, 4 skipped | All 4 skips documented in earlier reports |
| `validate_github_workflows.py` | OK | "workflow + action invariants hold" on shipped tree |
| ADR-22 hard wall | held | Action outputs name-checked vs forbidden phrase set |
| ADR-29 (provider opt-in) | held | replay default, fork fence, env-var-name only |
| ADR-30 (Phase 4.5 surface) | held | least-privilege, no `pull_request_target`, fork fence inside single `if:` |
| ADR-31 (this commit) | written | `decisionLog.md` §[2026-04-29 03:00:00] |
| Real-runner ci | green | run 24948296296 — all 6 jobs incl. Node 24 compat |
| Real-runner action-smoke | green | run 24948296297 — composite action smoke 51s |
| Real-runner sarif-upload | green + ingested | run 24948316005 — 6 analyses visible in code-scanning API |
| Fork-PR fence smoke | not_run | §5 — explicit reason, structural guarantee from Phase 4.5 |
| Provider regression baseline | not_run | §7 — deferred to Phase 4.7 |

---

## Honesty statement

Phase 4.6 validates operator-facing GitHub Actions behavior on
real GitHub-hosted runners.

It does **NOT** add MCP or provider tool-calling.

It does **NOT** validate production predictive performance.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-25..30 + ADR-31 hold.

It does **NOT** create a GitHub App or custom Checks API
integration.

It does **NOT** prove the fork-PR fence works against a real
fork PR — the structural guarantee from Phase 4.5 stands; the
empirical run is deferred to the first operator-driven fork PR
(§5).

It does **NOT** run any provider regression baseline — that's
deferred to Phase 4.7 once API budget is allocated (§7).

It does **NOT** modify the vendored OIDA core (ADR-02 holds).
