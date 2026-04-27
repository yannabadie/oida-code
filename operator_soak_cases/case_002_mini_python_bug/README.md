# Case 002 — mini hermetic Python bug

## Status

`awaiting_case_selection` — the directory + replay bundle structure are
ready, but the operator has not yet picked a real upstream repo / commit
for this case.

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

1. Pick a small hermetic Python repo + a controlled commit.
2. Update `fiche.json` (`repo`, `branch`, `commit`, `intent`,
   `expected_risk`, `gateway_bundle`).
3. Replace the seed bundle in `bundle/` with a real audit packet for the
   selected commit (or accept the seed as a placeholder and label the
   case `insufficient_fixture` honestly).
4. Trigger `workflow_dispatch` with the bundle.
5. Capture `workflow_run_id` + `artifact_url` into `fiche.json`.
6. Triage artefacts. Write `label.json` (one of six labels + 3–10 line
   rationale).
7. Write `ux_score.json` (four 0/1/2 scores).
8. Re-run `python scripts/run_operator_soak_eval.py` from the repo root.
