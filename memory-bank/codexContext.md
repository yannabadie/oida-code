# Codex Project Memory - Unslop.ai / oida-code

Date captured: 2026-04-29.
Working tree at capture: `main...origin/main`, with pre-existing
untracked `.tmp/`.

## Current override (2026-04-30)

This file began as a 2026-04-29 Claude/Codex handoff. Its original
"current" sections below are historical where they conflict with the
repo after ADR-75.

Current head before the ADR-75 policy block is `e5022d6`
(`docs(product): reset diagnostic-first product strategy`). ADR-73
stopped G-6d.3 without advancing the live corpus; ADR-74 reset the
diagnostic-first product strategy; ADR-75 records the dependency
policy for the next G-6d.4 candidate-selection block. The live
`reports/calibration_seed/index.json` remains at the ADR-72 state:
46 records, 14 pinned, 10 train, 4 holdout.

G-6a is closed for the current archived load-bearing replay set by
ADR-68 plus ADR-69. G-6d remains open toward N>=20, but cgpro review
`repo-product-vision-review` (`69f329be-0dd4-838f-8687-d68190f21e7d`)
recommended pausing new corpus pinning until product strategy, docs,
agent handoff, CLI UX, and the dependency-install policy were reset.
ADR-75 chooses a policy-only response: for G-6d.4, candidates that
need `requirements/*.txt`, tox `deps = -r ...`, manual `pip install -r
...`, or a new requirements-file clone-helper flag are rejected or
deferred before partition freeze. Do not add a clone-helper flag,
corpus record, runtime path, or claim-surface unlock for that case.

Use `docs/product_strategy.md`, `docs/project_status.md`, and
`AGENTS.md` as the live orientation surfaces before relying on the
historical capture below.

## Why this file exists

The user asked Codex to recover the project memory and Claude Code
conversations dedicated to this project, then integrate the useful
state into a Codex-readable project memory. This file is the curated
handoff. It does not replace the raw transcripts or canonical repo
docs.

## Anthropic / Claude Code facts verified from official docs

- Claude Code project instructions live in `./CLAUDE.md` or
  `./.claude/CLAUDE.md`; user instructions live in `~/.claude/CLAUDE.md`.
  Claude reads these at the start of sessions as context, not enforced
  configuration.
- Claude Code sessions are stored locally by project directory and can
  be resumed with `claude --continue` or `claude --resume`.
- Claude Code hooks expose `transcript_path`, with examples under
  `~/.claude/projects/.../*.jsonl`.

Docs consulted:

- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/fr/common-workflows
- https://code.claude.com/docs/fr/cli-reference
- https://code.claude.com/docs/fr/hooks

## Local Claude Code corpus recovered

Project directory:

`C:\Users\yann.abadie\.claude\projects\C--Code-Unslop-ai`

Recovered files:

- Main transcript:
  `5cc25491-da19-440d-b737-d5cd118a09c5.jsonl`
  - Size: about 78 MB.
  - Parsed lines: 19,413.
  - Parse errors: 0.
  - Time span: 2026-04-23T19:43:47Z to 2026-04-29T16:55:03Z.
  - Main cwd: `C:\Code\Unslop.ai`.
  - Branches observed: `main`, `HEAD`,
    `operator-soak/case-001-docstring`,
    `operator-soak/case-001-docstring-v2`.
- Auto-memory files:
  - `memory/MEMORY.md`
  - `memory/feedback_autonomous_with_ai_consultation.md`
  - `memory/feedback_no_schedule_for_observation_phases.md`
  - `memory/feedback_pipeline_wiring.md`
  - `memory/feedback_windows_fork_pressure.md`
- Tool results and subagents under:
  `5cc25491-da19-440d-b737-d5cd118a09c5\tool-results\`
  and `...\subagents\`.

The broader Claude Desktop export was searched for `Unslop` and did
not contain direct hits. The dedicated Claude Code transcript above is
the relevant project-specific source.

## Claude Code auto-memory to preserve

- Windows fork pressure:
  never run `python -m pytest` in background on this repo. Foreground
  and focused pytest is safer on this Windows/Cygwin host because the
  self-audit tests invoke the CLI and spawn subprocess verifier tools.
- Audit pipeline wiring:
  `_run_deterministic_pipeline` in `src/oida_code/cli.py` defaults to
  the 5 Phase-1 tools. Hypothesis and mutmut exist but remain opt-in
  behind `--enable-property` and `--enable-mutation` until the
  self-audit fork guard lands.
- No schedule for observation phases:
  do not pitch `/schedule` at the close of soak/telemetry phases before
  real telemetry exists. For this repo, no scheduled reminder until
  real operator-soak labels exist in `reports/operator_soak/`.
- Autonomous work with AI consultation:
  default to autonomous execution on approved phase work, while
  consulting cgpro / Codex CLI / Gemini / advisor at substantive
  inflection points. Plan mode is not default unless Yann asks for it.

## Current canonical repo state

Verified from repo files and git log on 2026-04-29:

- Current HEAD: `e0b7c33`
  `docs(consolidation-v2): align canonical state with ADR-65/66; G-6b/f CLOSED; natural pause point (ADR-67)`.
- Latest relevant chain:
  - `af87f75` Phase 6.1'a first calibration seed collection.
  - `4f3b7f9` Phase 6.1'b bundle generator.
  - `1def23a` Phase 6.1'c corpus expansion N=46 + partition discipline.
  - `bfb63ca` Phase 6.1'd LLM-author replays.
  - `f27e40c` Phase 6.1'e train pins + first verification_candidate.
  - `97f27cc` Phase 6.1'e holdouts, 0/2 candidate due bootstrap gaps.
  - `0e0864f` Phase 6.1'f minimal clone helper bootstrap fix.
  - `de26bce` Phase 6.1'g extras/groups/pytest-smoke fix.
  - `e57d2cc` Phase 6.1'h fresh freeze-rule holdout pass.
  - `101e633` Phase 6.2 AI-tier cold-reader audit.
  - `e742867` methodology consolidation v1.
  - `71df92e` corpus-quality v1: seed_157 demoted, seed_018 pinned.
  - `97fe278` G-6b structural test and SARIF `.tmp/` skip fix.
  - `2f86e77` QA/A48 cgpro recommendation.
  - `e0b7c33` consolidation v2 and natural pause point.

Canonical status sentence from `reports/phase6_1_close_out_v2.md`:

> Phase 6.1' plus corpus-quality v1 produced two holdout
> claim-supporting round-trips, one entangled and one independent, and
> bounded the bootstrap carve-out; replay-content audit and larger-N
> validation remain open.

## What is usable now

Use `docs/project_status.md` as canonical, but the high-level state is:

- Deterministic audit pipeline: `oida-code audit`, `oida-code inspect`.
- Trajectory scorer: `oida-code score-trace`.
- LLM estimator dry-run: `oida-code estimate-llm --llm-provider replay`.
- Forward/backward replay verifier: `oida-code verify-claims`.
- Gateway-grounded verifier opt-in:
  `oida-code verify-grounded`; GitHub Action input
  `enable-tool-gateway` remains default false.
- Bundle generator:
  `oida-code prepare-gateway-bundle --case-id <id> --out <dir>`.
- Calibration seed corpus:
  46 inclusions, 6 pinned cases, 4 train + 2 holdout.
- Manual-lane scripts:
  `scripts/build_calibration_seed_index.py`,
  `scripts/llm_author_replays.py`,
  `scripts/clone_target_at_sha.py`.

## Hard walls still active

- No MCP runtime.
- No provider tool-calling in runtime path.
- No GitHub App / Checks API custom annotations.
- `enable-tool-gateway` default false.
- No non-Python ecosystem adapters.
- No public benchmark claim.
- No PyPI stable release.
- No public beta reopened by Phase 6.1' / Phase 6.2.
- Official fields stay blocked/null:
  `total_v_net`, `debt_final`, `corrupt_success`,
  `corrupt_success_ratio`, `verdict`,
  `is_authoritative` pinned false for LLM source.
- Do not use product-verdict language such as merge-safe,
  production-safe, bug-free, verified, or security-verified as an
  output claim.

## Natural pause point

The last recovered Claude Code state says the project reached a
natural pause point after consolidation v2 at `e0b7c33`, per cgpro
QA/A48 verdict_q2.

Do not start more implementation solely from the prior transcript's
"Continue from where you left off" message. The transcript itself says
that the correct action after that message was to wait for explicit
direction.

If the user explicitly asks to resume implementation, the next
recommended empirical priority is:

1. G-6a: replay-content audit.
   Build a `scripts/audit_llm_replays.py` path that either:
   - re-authors via a second provider and diffs,
   - statically checks LLM `evidence_refs` against packet evidence IDs,
   - or performs a hand-review path against upstream PR test outputs.
2. G-6d: corpus expansion after G-6a closes, toward N >= 20 pinned
   cases.

Other deferred priorities (Phase 7 research moat, official fusion
fields revisit, public benchmark) remain off the critical path.

## Current open G-6 status

From `BACKLOG.md` and `reports/phase6_1_close_out_v2.md`:

- G-6a LLM-replay-audit gap: OPEN, next empirical priority.
- G-6b freeze-rule carve-out scope: CLOSED by ADR-66.
- G-6c seed authoring quality: PARTIALLY ADDRESSED.
- G-6d N statistically thin: OPEN.
- G-6e ADR-56 spirit-tension on seed_065: PARTIALLY ADDRESSED.
- G-6f seed_157 demotion-and-replace: CLOSED by ADR-65.

## Commands and checks

Use the commands in `CLAUDE.md` as the source of truth. Important
local reminders:

- Install dev: `python -m pip install -e ".[dev]"`.
- Main gates:
  - `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
  - `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
  - `python -m pytest -q`
- On this machine, prefer focused pytest invocations and keep pytest in
  foreground.

## How to use this memory

Before changing code:

1. Check `git status --short --branch`.
2. Read `docs/project_status.md`, `BACKLOG.md`, and the target files.
3. Treat transcript-derived facts as prior context only. Re-verify
   current code, tests, and docs before acting.
4. Keep changes scoped. The current project state is mostly a
   research/protocol discipline surface; do not convert unresolved
   caveats into product claims.
