# Codex Instructions for Unslop.ai / oida-code

This file is for Codex agents working in `C:\Code\Unslop.ai`.
Read it before making changes. Treat imported memory as directional
context, not as a replacement for checking the current repo state.

## Required Read Order

1. `memory-bank/codexContext.md` - Codex handoff from Claude Code
   project transcripts and auto-memory.
2. `CLAUDE.md` - project commands, quality gates, and Claude Code
   operational rules.
3. `docs/product_strategy.md` - active product direction and
   diagnostic-only scope.
4. `docs/project_status.md` - canonical current project status.
5. `BACKLOG.md` - acknowledged gaps and current G-6 status.
6. `reports/phase6_1_close_out_v2.md` - historical Phase 6.1'
   close-out.

## Current Handoff State

- Claude Code project transcript recovered from
  `C:\Users\yann.abadie\.claude\projects\C--Code-Unslop-ai\5cc25491-da19-440d-b737-d5cd118a09c5.jsonl`.
- The recovered session spans 2026-04-23 to 2026-04-29 and ended at a
  documented natural pause point after commit `e0b7c33`. That is now
  historical context, not the current head state.
- Current head after the latest pushed block is `b8bc2ad`
  (`chore(phase6.d): record g6d3 stop`). ADR-73 stopped G-6d.3
  honestly after a post-freeze dependency-boundary failure; the live
  corpus remains N=14 (10 train, 4 holdout).
- G-6a is CLOSED for the current archived load-bearing replay set by
  ADR-68 static audit plus ADR-69 manual semantic review. Do not restart
  G-6a unless a future block creates new LLM-authored replay content
  that needs the same audit discipline.
- Per cgpro review `repo-product-vision-review`
  (`69f329be-0dd4-838f-8687-d68190f21e7d`), the immediate priority is
  product-strategy / docs / CLI UX reset before any new G-6d pinning.
  G-6d remains OPEN toward N>=20, but the next G-6d block must first
  record a pre-freeze dependency-install policy for historical
  `requirements/*.txt` / `tox.ini` test-dependency patterns.

## cgpro Project Continuity

- This repo is linked in `cgpro` to the ChatGPT Project `unslop`
  (`g-p-69ed965308088191a3f20cfba999c589`), linked to
  `github.com/yannabadie/oida-code`. Keep `workdir` at
  `C:\Code\Unslop.ai` for `cgpro` calls so project routing applies.
- Before any substantive `cgpro` consultation, run `cgpro status`. If
  it reports `Not signed in`, `Cloudflare challenge`, `Selector broken`,
  or another unhealthy state, stop and surface that exact blocker.
- If `cgpro` is otherwise unavailable because the browser/session is
  already being used elsewhere, wait about 10 minutes and retry before
  treating it as a blocker. Do not downgrade to an unreviewed local
  decision just because `cgpro` is temporarily busy.
- Existing continuity thread for the latest chain:
  `phase61-review`, ChatGPT conversation
  `69f1bde2-70c0-8387-9c89-743f8780cb14`
  (`Phase 6.1 Chain Review`). Resume it for follow-up decisions about
  the already-closed Phase 6.1' / 6.2 / consolidation-v2 chain.
- Existing G-6d / replay-audit thread:
  `phase6a-replay-audit`, ChatGPT conversation
  `69f25185-5f94-8394-ad11-627a00d1741b` (`Replay Audit Strategy`).
  It currently includes ADR-68 through ADR-73 decisions.
- Product reset thread:
  `repo-product-vision-review`, ChatGPT conversation
  `69f329be-0dd4-838f-8687-d68190f21e7d`. Use it for follow-up
  decisions about product vision, front-door docs, CLI UX, or whether to
  resume G-6d.
- Use parseable, non-streaming calls for project decisions:

```powershell
cgpro ask --json --no-stream --timeout 600 --resume phase61-review @'
<prompt>
'@
```

For a new block:

```powershell
cgpro ask --json --no-stream --timeout 600 --new-session --save <stable-thread-name> @'
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

## Autonomous Development Provider Protocol

- The local `.env` may expose provider credentials. Inspect only env var
  names, never values. As of 2026-04-29, observed names are
  `DEEPSEEK_API_KEY`, `GROK_API_KEY`, `KIMI_API_KEY`,
  `MINIMAX_API_KEY`, `HF_TOKEN`, and `PAT_GITHUB`.
- Before selecting or invoking any provider model, refresh current
  official provider documentation or live model-list output. Do not rely
  on stale comments, old ADR pins, or historical defaults.
- Prefer the newest/highest-capability model available for the task
  unless the block explicitly optimizes for cost, latency, or replay
  comparability. Record the model id, provider, date, and verification
  source in the QA/ADR/report trail when a provider call matters.
- Current local high-capability tools include `cgpro` with GPT-5.5 Pro,
  `codex` CLI logged in through ChatGPT (use GPT-5.5 with xhigh
  reasoning for hard code/research planning), and `gemini` CLI
  (Gemini 3.1 Pro when available). Verify CLI model availability before
  relying on a specific id.
- For project decisions, consult `cgpro` at every substantive step. Use
  Codex CLI, Gemini CLI, or direct provider API calls as secondary
  research/critique channels only when the current block benefits from
  independent analysis; never let an AI answer replace non-LLM evidence
  when the block is explicitly about semantic or upstream truth.
- Available data is not limited to this repo. If the block needs more
  evidence, search the user's local project folders and the user's
  GitHub repositories, but keep private/local data out of public reports
  unless explicitly approved and relevant.
- API keys are the practical substitute for unavailable hired external
  developers, but they do not relax the trust boundary: runtime remains
  locked down, provider/tool-calling stays opt-in and non-authoritative,
  and all claims must stay tied to evidence, tests, docs, or explicit
  downgraded AI-tier critique.

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
