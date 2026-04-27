# Case 003 — markupsafe `soft_unicode` removal (simple Python import-contract change)

## Status

`awaiting_real_audit_packet_decision` — `cgpro` selected the upstream
repo / commit in session `phase58-soak`, but **this case is scaffolded
only**.

> This case is scaffolded only.
> The committed bundle is **not** yet a real audit packet.
> Human/cgpro decision required:
> - generate real audit packet for `pallets/markupsafe@7856c3d`,
> - replace this case with a different upstream,
> - or mark `insufficient_fixture` after operator review.

Per QA/A38 §3, only `case_001` gets a real audit packet during 5.8-prep
(it is the only case currently feasible without external setup). For
this case to advance, the operator must decide on the bundle strategy —
the seeded bundle does NOT describe the real `markupsafe` change and
dispatching as-is would produce a contaminated soak signal.

Selected upstream:

- repo: `pallets/markupsafe`
- branch: `main`
- commit: `7856c3d945a969bc94a19989dda61c3d50ac2adb`
- PR: `https://github.com/pallets/markupsafe/pull/261`
- commit URL: `https://github.com/pallets/markupsafe/commit/7856c3d945a969bc94a19989dda61c3d50ac2adb`
- operator-channel rationale: removes the deprecated top-level
  `markupsafe.soft_unicode` export from `__init__.py` / `_native.py` /
  `_speedups.c` and updates `tests/test_markupsafe.py` + `tests/conftest.py`
  in the same PR. Consumers must switch to `soft_str` — a missed downstream
  import is a legitimate `false_negative` candidate for the gateway.
- independent verification: `gh api repos/pallets/markupsafe/commits/<sha>`
  confirmed the commit exists, author David Lord, files match the rationale.

## Recommended shape (per QA/A34 §5.7-A item 3 + QA/A35 §5.8-A case 003)

A **simple real Python repo** where the controlled change touches an
import or a small public-API contract:

- module `pkg.utils` previously re-exported `def parse(s)`; PR removes the
  re-export and points consumers at `pkg.parse_strict`.
- a regression test imports the symbol via the old path and is updated to
  the new path in the same PR.

The operator (here, `cgpro` per QA/A37) picks the upstream + commit.
Claude must not pick on the operator's behalf for this case to count as
a real soak.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`
- no monorepo (per QA/A34 §5.7-A "éviter pour cette phase")
- no repo containing secrets or private logs

## Workflow (operator action — see `../RUNBOOK.md`)

This case is **blocked on the bundle decision** described above. Once
the operator picks a path:

1. (decision path A) Generate a real audit packet for
   `pallets/markupsafe@7856c3d` — clone locally, run `oida-code audit`
   against the upstream commit, capture the 8 bundle files, replace
   `bundle/` content. Note that `markupsafe` has a C extension
   (`_speedups.c`); building it requires a C toolchain. Then move to
   step 4.
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

The expected_risk for an import-contract change is `medium` rather than
`low`: a missed downstream import becomes a true `false_negative` if the
gateway stays silent on an actual breakage.
