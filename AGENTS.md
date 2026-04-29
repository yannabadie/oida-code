# Codex Instructions for Unslop.ai / oida-code

This file is for Codex agents working in `C:\Code\Unslop.ai`.
Read it before making changes. Treat imported memory as directional
context, not as a replacement for checking the current repo state.

## Required Read Order

1. `memory-bank/codexContext.md` - Codex handoff from Claude Code
   project transcripts and auto-memory.
2. `CLAUDE.md` - project commands, quality gates, and Claude Code
   operational rules.
3. `docs/project_status.md` - canonical current project status.
4. `BACKLOG.md` - acknowledged gaps and current G-6 status.
5. `reports/phase6_1_close_out_v2.md` - current Phase 6.1' close-out.

## Current Handoff State

- Claude Code project transcript recovered from
  `C:\Users\yann.abadie\.claude\projects\C--Code-Unslop-ai\5cc25491-da19-440d-b737-d5cd118a09c5.jsonl`.
- The recovered session spans 2026-04-23 to 2026-04-29 and ended at a
  documented natural pause point after commit `e0b7c33`.
- Do not start G-6a just because the prior transcript ended with
  "Continue from where you left off." The recovered Claude summary says
  the correct behavior was to wait for explicit user direction after the
  natural pause point.
- If the user explicitly resumes implementation, the cgpro-recommended
  next empirical priority is G-6a: replay-content audit before corpus
  expansion G-6d.

## cgpro Project Continuity

- This repo is linked in `cgpro` to the ChatGPT Project `unslop`
  (`g-p-69ed965308088191a3f20cfba999c589`), linked to
  `github.com/yannabadie/oida-code`. Keep `workdir` at
  `C:\Code\Unslop.ai` for `cgpro` calls so project routing applies.
- Before any substantive `cgpro` consultation, run `cgpro status`. If
  it reports `Not signed in`, `Cloudflare challenge`, `Selector broken`,
  or another unhealthy state, stop and surface that exact blocker.
- Existing continuity thread for the latest chain:
  `phase61-review`, ChatGPT conversation
  `69f1bde2-70c0-8387-9c89-743f8780cb14`
  (`Phase 6.1 Chain Review`). Resume it for follow-up decisions about
  the already-closed Phase 6.1' / 6.2 / consolidation-v2 chain.
- For a new G-6a implementation block, create a separate saved thread
  such as `phase6a-replay-audit` with `--new-session --save` on the
  first prompt, then use `--resume phase6a-replay-audit` for all
  follow-up decisions in that block.
- Use parseable, non-streaming calls for project decisions:

```powershell
cgpro ask --json --no-stream --timeout 600 --resume phase61-review @'
<prompt>
'@
```

For a new block:

```powershell
cgpro ask --json --no-stream --timeout 600 --new-session --save phase6a-replay-audit @'
<prompt>
'@
```

- Prompts to `cgpro` must lead with the canonical repo URL
  `https://github.com/yannabadie/oida-code`, the current local commit
  SHA, what shipped, what is stuck, and 2-3 specific questions. When the
  response feeds repo state, require a single JSON object and forbid
  prose outside it.
- `cgpro` is a decision channel only. It cannot modify files, verify
  the worktree, dispatch workflows, or run tests. After each `cgpro`
  answer, Codex must parse and validate it, verify concrete refs
  locally, implement changes itself, run relevant checks, and persist the
  decision trail in `QA/Axx.md`, ADRs, reports, or backlog entries as
  appropriate.
- Never invent or infer missing `cgpro` decisions. If the reply is
  empty, ambiguous, malformed, or outside the allowed response shape,
  keep the case pending and ask `cgpro` for clarification.

## Operating Rules

- Default language with Yann is French, but keep repo docs in the
  existing project style unless asked otherwise.
- Be direct and evidence-grounded. Separate verified repo state from
  transcript-derived context and inference.
- Work autonomously on approved project tasks, but consult cgpro/Codex
  CLI/Gemini/advisor at substantive inflection points when the project
  workflow calls for it.
- For this repo, run pytest in the foreground and prefer focused tests.
  Do not background pytest or long pytest monitors on this Windows host.
- Preserve the hard walls: no MCP runtime, no product-verdict language,
  `enable-tool-gateway` default false, lane separation, partition
  discipline, freeze-rule discipline, and audit-as-block.
- Before declaring completion, verify with the smallest relevant tests
  and report any checks that were not run.
