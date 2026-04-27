# Case 002 — python-semver negative-version reject (mini hermetic Python bug)

## Status

`awaiting_real_audit_packet_decision` — `cgpro` selected the upstream
repo / commit in session `phase58-soak`, but **this case is scaffolded
only**.

> This case is scaffolded only.
> The committed bundle is **not** yet a real audit packet.
> Human/cgpro decision required:
> - generate real audit packet for `python-semver/python-semver@0309c63`,
> - replace this case with a different upstream,
> - or mark `insufficient_fixture` after operator review.

Per QA/A38 §3, only `case_001` gets a real audit packet during 5.8-prep
(it is the only case currently feasible without external setup). For
this case to advance, the operator must decide on the bundle strategy —
the seeded bundle does NOT describe the real `python-semver` change and
dispatching as-is would produce a contaminated soak signal.

Selected upstream:

- repo: `python-semver/python-semver`
- branch: `master`
- commit: `0309c63ce834b7d35aa3e29b8d5bb0357532b016`
- PR: `https://github.com/python-semver/python-semver/pull/292`
- commit URL: `https://github.com/python-semver/python-semver/commit/0309c63ce834b7d35aa3e29b8d5bb0357532b016`
- operator-channel rationale: negative `VersionInfo` constructor inputs are
  rejected and pinned by regression coverage in `test_semver.py`.

## Recommended shape (per QA/A34 §5.7-A item 2 + QA/A35 §5.8-A case 002)

A **small hermetic Python repo** with:

- one function with a clear, narrow contract (e.g. `validate_email(s: str) -> bool`)
- a known bug on a negative case (e.g. accepts `"a@b"` even though it should require a TLD)
- a regression test that pins the bug as fail-to-pass

Examples the operator could pick:

* a tiny standalone repo authored for the soak (~50 LOC)
* a one-PR fork of a small public Python repo with a known bug
* a synthetic case derived from the existing
  `datasets/calibration_v1/` cases (operator-only — Claude must not
  generate the synthetic on the operator's behalf for this case to count
  as a real soak)

**Why the operator must select**: the soak measures whether the gateway's
report is *useful* on a case whose risk profile the operator already
understands. If Claude picks the case, the soak measures Claude's
confidence in its own audit, not the operator's reading.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`
- no large dependency (heavy frameworks blow up the soak signal)
- no repo without tests (the gateway has nothing to ground against)

## Workflow (operator action — see `../RUNBOOK.md` for the step-by-step)

This case is **blocked on the bundle decision** described above. Once
the operator picks a path:

1. (decision path A) Generate a real audit packet for
   `python-semver/python-semver@0309c63` — clone locally, run
   `oida-code audit` against the upstream commit, capture the 8 bundle
   files, replace `bundle/` content. Then move to step 4.
2. (decision path B) Replace this case with a different upstream that's
   easier to audit. Update `fiche.json` and re-anchor the case.
3. (decision path C) Accept the seeded bundle and prepare to label the
   case `insufficient_fixture` honestly after dispatch.
4. Trigger `workflow_dispatch` with the bundle.
5. Capture `workflow_run_id` + `artifact_url` into `fiche.json`.
6. Triage artefacts. Write `label.json` (one of six labels + 3–10 line
   rationale).
7. Write `ux_score.json` (four 0/1/2 scores).
8. Re-run `python scripts/run_operator_soak_eval.py` from the repo root.
