# `docs/legacy/` — moved files mapping

This file records files that lived at the **repository root** before
the `chore(repo): tidy root` cleanup and that now live elsewhere.
Use it as a redirect table when a memory-bank journal entry, an
older ADR, or an external link references a file by its old root
basename.

The cleanup is a **rename / move**, not a content change. Each
moved file's contents are byte-identical to the pre-cleanup
version (preserved by `git mv` so the move shows as a rename in
`git log --follow`).

## Mapping table

| Old path (root) | New path | Reason |
|---|---|---|
| `PHASE1_REPORT.md` | `reports/legacy/PHASE1_REPORT.md` | Phase 0 bootstrap report; `PLAN.md` §14 takes precedence |
| `PHASE1_AUDIT_REPORT.md` | `reports/legacy/PHASE1_AUDIT_REPORT.md` | Phase 1 audit report; superseded by `reports/block_d_validation.md` and the per-block reports |
| `PHASE2_AUDIT_REPORT.md` | `reports/legacy/PHASE2_AUDIT_REPORT.md` | Phase 2 audit report; superseded by the per-block reports |
| `PHASE3_AUDIT_REPORT.md` | `reports/legacy/PHASE3_AUDIT_REPORT.md` | Phase 3 audit report; the §3 length-confound caveat is referenced by `reports/e1_shadow_fusion.md`, `scripts/validate_phase3.py`, and `src/oida_code/score/experimental_shadow_fusion.py` |
| `prompt.md` | `docs/legacy/prompt.md` | Original Step 5 questions; superseded by `PLAN.md` and `BACKLOG.md` |
| `infos.md` | `docs/legacy/infos.md` | §1 unslop name-collision rationale, §3 storage prerequisite — kept for ADR-01 historical context |
| `roadmap.md` | `docs/legacy/roadmap.md` | Subsumed by `PLAN.md` per ADR-10; kept for change-log traceability |
| `last.md` | `docs/legacy/last.md` | Pre-merge scratch; kept for memory-bank narrative integrity |
| `oida-code-audit-report.example.json` | `examples/audit-report.example.json` | Example artefacts belong under `examples/` |
| `oida-code-audit-request.example.json` | `examples/audit-request.example.json` | Same |

## Files removed entirely (no replacement)

The following root files were removed during the cleanup. They had
no inbound active-code references; their only mentions were in
memory-bank journal narrative. The journal entries describe what
was read at the time and remain verbatim — the files themselves
are not preserved because they had no further use.

* `1.png`, `2.png`, `3.png` — ad-hoc screenshots
* `brainstorm2.md`, `brainstorm2_improved.md` — pre-merge scratch
* `CONSULTATION_OIDA.md`, `CONSULTATION_OIDA_RESPONSE.md` —
  one-off consultation dump (the **decision** that came out of the
  consultation is in `memory-bank/decisionLog.md` ADR-15 and is
  preserved)

## How to find content from a removed file

* If the content was a **decision**, look in `memory-bank/decisionLog.md`.
* If the content was a **report**, look in `reports/`.
* If the content was a **specification**, look in
  `oida-code-mvp-blueprint.md` or `PLAN.md`.
* If the content was a **roadmap**, look in `BACKLOG.md` or
  `docs/project_status.md`.
* If the content was an **audit report on Phase 1/2/3**, look in
  `reports/legacy/`.

## What this file is NOT

* Not a versioned redirect (no `301` / no symlink).
* Not a public surface — it's an internal record so future
  developers don't waste time looking for moved files.
* Not a place to add new redirects automatically — every entry
  here corresponds to an explicit `git mv` in the cleanup commit.
