# `reports/calibration_seed/` — manual data acquisition lane charter

This directory holds the **calibration seed corpus**: a bounded
collection of public Python PR candidates used to stress-test
the Phase 6.1' bundle authoring helper. The lane is established
per ADR-53 / QA/A44 §"Frontière manual-vs-runtime".

> **This is NOT a calibration dataset for predictive validation.**
> This is **NOT** G-3 closure. This is **NOT** operator feedback.
> This is **NOT** a benchmark of "user usefulness". The lane is a
> **structural sampling of public Python PRs**, manually curated
> and labelled, used solely to stress-test bundle authoring and
> measure friction reduction across Phase 6.1' iterations.

## What this lane is for

Phase 6.1' Option Y (per QA/A44 §"Phase 6.1' option choice")
delivers a minimal bundle-authoring helper tested against a
bounded adversarial corpus. The corpus comes from this lane:
20-50 public Python PR cases, manually selected, with structural
expectations documented per case.

The lane exists because:

- Phase 6.0.y AI-tier critique (3/3 convergence on C1) flagged
  the keystone example (`examples/gateway_opt_in/`) as
  auto-referential — bundle authoring guidance derives from
  reverse-engineering one self-audit example.
- A non-self-audit corpus reduces auto-reference and gives the
  Phase 6.1'b generator real cases to stress-test against.
- The corpus is **structural**, not behavioural — it measures
  whether the helper can produce a valid bundle skeleton, NOT
  whether external operators find the result useful (that
  remains the external-human beta lane's job, which is
  `not_run` per QA/A43).

## The 12 frontier rules (verbatim from QA/A44 §"Frontière manual-vs-runtime")

These rules are the **lane charter**. Every script that touches
this lane must comply:

1. Les scripts avec egress vivent dans `scripts/` ou `tools/manual/`, jamais dans `src/oida_code/`.
2. Ils sont invoqués manuellement, jamais par défaut en CI.
3. Ils exigent une variable d'environnement explicite.
4. Ils refusent de tourner sans flag d'intention, par exemple `--manual-egress-ok`.
5. Ils produisent des artefacts sous `reports/`, `datasets/`, ou `calibration/`, jamais dans le runtime path.
6. Ils n'ajoutent aucune dépendance runtime.
7. Ils n'importent pas le verifier runtime dans un mode qui déclenche réseau.
8. Ils ne modifient jamais un repo cible.
9. Ils ne poussent jamais de branche.
10. Ils ne créent jamais de PR.
11. Ils n'appellent jamais une API provider depuis `verify-grounded`.
12. Ils n'appellent jamais GitHub ou HF depuis `verify-grounded`.

ADR-53 enshrines the binding sentence:

> **Manual data acquisition may use network credentials. The
> verifier runtime may not. Manual scripts can collect candidate
> evidence; they cannot produce human feedback, cannot produce
> runtime decisions, and cannot relax structural pins.**

## What PAT_GITHUB may / may not do

**May:** list public repos, list PRs, list commits in a PR, list
files touched, clone read-only, fetch public metadata, build a
manifest of candidates.

**May not:** merge, comment, review, push, modify issue/PR, open
checks, write to target repos, access private repos without an
ADR-specific exception.

## What HF_TOKEN may / may not do (in this lane)

**May:** download a public dataset for survey purposes (read-only,
documented).

**May not:** upload anything, publish anything, sync raw corpus
output by default.

The first version of this lane does **not** use HF_TOKEN at all
(per QA/A44 §"HuggingFace usage policy" deferral); it is
mentioned here as forward guidance.

## What provider API keys may / may not do (in this lane)

**May:** propose candidate PRs (LLM-assisted suggestion of which
PRs to look at), summarise a public diff to help Yann triage, suggest a
`claim_id`, critique a case description.

**May not:** fill `operator_label`, vote on whether a case is
useful, decide a label of truth, write to the human-beta
aggregate, replace human review.

## Schema overview

See [`schema.md`](schema.md) for field-by-field definitions of
`index.json` and `exclusions.json`.

Quick reference:

* **`index.json`** — array of inclusion records. One per
  candidate PR that will be turned into a bundle.
* **`exclusions.json`** — array of exclusion records. PRs the
  operator considered but rejected, with `exclusion_reason`.
  The exclusions are signal too — they document why the corpus
  is not larger.

## Naming policy

Per QA/A44 §"Naming policy":

* The dataset is called `calibration_seed` or
  `structural_grounding_corpus`.
* It is **not** called `human_beta`, `operator_feedback`, or
  `validation_dataset`.
* Public release would require a separate ADR (data card,
  license, attribution, opt-out, secret scan, PII minimization).
  Phase 6.1'a-pre does **not** release publicly; the manifest
  stays local.

## Refusal modes (the script's two safety layers)

`scripts/build_calibration_seed_index.py` has two refusal layers
on top of the `--dry-run` default:

1. **`--manual-egress-ok` is required** to exit dry-run mode. If
   absent, the script prints the planned operation, lists the
   repos that would be queried, and exits 0 without any network
   call.
2. **`--public-only` is required** to bypass the safety check. If
   absent (even with `--manual-egress-ok`), the script refuses
   with a non-zero exit and a clear message.

A run that escaped both refusals AND tries to access a private
repo will get a third refusal: the script checks
`repo.visibility == "public"` via the GitHub REST API before any
clone or fetch, and records `exclusion_reason: private_repo_refused`
on any private repo encountered.

## What this lane records

For each **inclusion**:

* `case_id` — stable id, e.g. `seed_001_<repo>_<pr>`.
* `repo_url`, `pr_number`, `title`, `base_sha`, `head_sha`.
* `changed_files_list` (paths only).
* `labels_observed` (GitHub labels visible publicly).
* `merge_status` (merged / closed / open at collection time).
* `candidate_reason` — one sentence on why this PR was selected.
* `claim_id`, `claim_type`, `claim_text` — populated MANUALLY
  by Yann after reviewing each case (or LLM-assisted-then-confirmed).
* `test_scope` — pytest target.
* `expected_grounding_outcome` — structural expectation, not
  product verdict.
* `label_source` — strict allowlist (see [`schema.md`](schema.md)).
* `selection_source` — strict allowlist (manual / llm_assist /
  random_sample / curated).
* `llm_assist_used` — boolean.
* `human_review_required` — boolean.
* `collected_at` — ISO 8601 timestamp.
* `script_version`, `public_only: true`.

For each **exclusion**:

* `repo_url`, `pr_number`, `exclusion_reason`, `collected_at`.

## What this lane does NOT record

* Raw diffs.
* Raw source code.
* Provider transcripts.
* Comments / reviews / discussion threads from the PR.
* Author identity (only public PR number + repo URL).
* Anything from private repos.

The first iteration is **manifest-only**. If a future ADR
authorizes richer storage, the schema is extended explicitly,
not implicitly.

## How to run the script (operator-facing)

Dry-run preview (default):

```bash
python scripts/build_calibration_seed_index.py \
    --repo pallets/click \
    --max-prs 5
```

Output: prints the plan, exits 0, no network call.

Real collection (operator-confirmed):

```bash
export PAT_GITHUB=<your_pat>
python scripts/build_calibration_seed_index.py \
    --repo pallets/click \
    --max-prs 5 \
    --manual-egress-ok \
    --public-only \
    --output reports/calibration_seed/index.json
```

Output: appends inclusion records to `index.json` and any
exclusions to `exclusions.json`. Idempotent: re-running with the
same flags does not duplicate records (keyed by
`(repo_url, pr_number)`).

## What Phase 6.1'a-pre delivers (this commit)

* The lane charter (this README).
* The schema documentation ([`schema.md`](schema.md)).
* The script in dry-run mode (no real collection happens).
* 7 structural tests in
  `tests/test_phase6_1_manual_data_lane_isolation.py`.
* The `manual_data_acquisition` lane row in
  `docs/project_status.md`.
* The ADR-53 entry in `memory-bank/decisionLog.md`.

What Phase 6.1'a-pre does NOT deliver:

* Actual collected data. The first 5-10 cases land in a later
  Phase 6.1'a commit AFTER Yann manually reviews the contract
  and runs the script with the explicit flags.
* The bundle generator. That is Phase 6.1'b.
* Public release. That is deferred indefinitely per
  QA/A44 §"HuggingFace usage policy".

## Cross-references

* ADR-53: `memory-bank/decisionLog.md`
* QA/A44: `QA/A44.md`
* Schema: [`schema.md`](schema.md)
* Script: `scripts/build_calibration_seed_index.py`
* Tests: `tests/test_phase6_1_manual_data_lane_isolation.py`
* Project status: `docs/project_status.md`
* Backlog G-3: `BACKLOG.md`
