# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

- Canonical public repo: `https://github.com/yannabadie/oida-code`.
- When asking an external operator, ChatGPT Pro, or `cgpro` to inspect this project, include that URL explicitly in the prompt so the operator can verify the current public surface.

## Human Operator Channel (`cgpro`)

For Phase 5.8 and any later operator-soak work, `cgpro` is the authorized human-operator channel. Treat `cgpro` answers as Yann's human judgement only after they are explicitly returned by the tool; never invent, simulate, or pre-fill human labels, UX scores, workflow run IDs, artifact URLs, or operator rationales.

Before using it, run `cgpro status` and stop if the session is not healthy. For the first prompt in a decision thread, start a fresh session and save it under a stable name, for example:

```bash
cgpro ask --web --new-session --save phase58-soak "<prompt including https://github.com/yannabadie/oida-code>"
```

For follow-up decisions in the same operator flow, resume the saved session instead of starting a new one:

```bash
cgpro ask --web --resume phase58-soak "<follow-up prompt>"
```

This preserves continuity for repo/PR selection, workflow-dispatch approvals, labels, UX scores, and clarification loops. If a `cgpro` response is missing, empty, ambiguous, or not one of the allowed answers, keep the case in an awaiting-human state and ask `cgpro` for clarification; do not infer the missing decision locally.

Operationally, `cgpro` is a decision/answer channel only. It cannot modify files, run `gh`, dispatch workflows, update reports, or verify the local worktree; Claude/Codex remains at the controls. After every `cgpro` answer, the agent must parse and validate the response, verify concrete URLs/SHAs/run IDs locally, make any file edits itself, run the relevant checks, and explain the result to Yann in enough detail to preserve the reasoning trail.

### `cgpro` invocation hygiene

The polished invocation pattern is:

```bash
cgpro ask --json --no-stream --timeout 600 --resume phase58-soak <<'EOF'
<long prompt — heredoc avoids shell-quoting bugs>
EOF
```

- **`--json`** emits NDJSON events instead of the human-formatted stream, which makes downstream parsing reliable. Without it, ANSI codes and partial-token streaming mangle the response.
- **`--no-stream`** buffers the full reply before printing — pair it with `--json` so the agent can parse one complete JSON document instead of stitching event deltas.
- **`--timeout 600`** caps wait time per turn. Without it, a stalled chatgpt.com UI hangs the call indefinitely.
- **stdin via heredoc** sidesteps the shell quoting cliff (backticks, dollar signs, multi-line JSON examples in the prompt). The `prompt` positional reads piped stdin per `cgpro ask --help`.
- **`--web` is policy-on**: pass it for explicitness or omit it; `--no-web` is ignored. Verifying claims against live source is mandatory for any "pick a real repo / commit" question.
- **`--resume <name>`** continues an existing decision thread (e.g. `phase58-soak`); use `--new-session --save <name>` only for the first prompt in a flow.

### `cgpro` prompt hygiene

- **Lead with the canonical repo URL** (`https://github.com/yannabadie/oida-code`) and, when relevant, the commit SHA being discussed. cgpro pulls live source via web search and the URL anchors the answer to the right artefact.
- **Structure the framing**: a short "what shipped / what's stuck / what I'm about to do" header before the question. cgpro is slow and analytic; without scoping, it wanders.
- **Split the ask into 2–3 specific questions**, typically along the axes "verdict on what I did / what should I do next / what trap am I missing". One open-ended "thoughts?" wastes a Pro turn.
- **Constrain the response shape** when the answer feeds a parser (e.g. `OperatorSoakFiche` field). Demand a single JSON object with named keys; explicitly forbid prose around it.
- **Pre-emptively blacklist undesired picks** in case-selection prompts (e.g. "do not pick numpy / django / fastapi"). cgpro will otherwise default to high-profile repos.

### When `cgpro` is the right tool

- Holistic review of a substantial cycle (5+ commits or a phase boundary).
- Strategy critique before committing to an approach.
- Finding non-obvious bugs across files (cgpro saw real prod bugs that local-only inspection missed).
- Operator-channel decisions per QA/A37 (label / UX-score / case selection / dispatch approval).
- Methodology audit before a release.

### When `cgpro` is the wrong tool

- Quick syntax lookups (use Context7 docs or local reading).
- One-line refactors / well-known API explanations.
- Anything Claude can answer from local files in seconds (don't waste Pro turns).
- Decisions where Yann explicitly asked Claude for Claude's own answer.

### Background-task gotcha

`run_in_background: true` on the Bash tool spawns a sub-shell with a stripped PATH that does NOT include `/c/Program Files/nodejs/`, so `cgpro` resolves to "command not found" (exit 127). Two workarounds:

1. Run `cgpro` calls in the foreground (default Bash invocation) — the harness auto-backgrounds long calls anyway when the timeout exceeds the inline budget, but PATH is preserved.
2. If a background invocation is genuinely required, prefix with the absolute path: `"/c/Program Files/nodejs/cgpro" ask ...`.

Always check with `which cgpro` and `cgpro status` before a long batch of calls; a "Cloudflare challenge" or "Not signed in" needs Yann to run `cgpro login` (interactive) or `cgpro adopt`, and Claude must surface the error rather than retry.

## Commands

Install (dev): `python -m pip install -e ".[dev]"`

Quality gates (run all three before claiming a block complete — the QA review checks all of them):

```bash
python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py
python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py
python -m pytest -q
```

Run one test file or a single test:

```bash
python -m pytest tests/test_phase4_1_verifier_contract.py -v
python -m pytest tests/test_phase4_1_verifier_contract.py::test_forward_only_is_not_enough -v
```

CLI subcommands (defined in `src/oida_code/cli.py`):

| Command | Purpose |
|---|---|
| `oida-code inspect <repo> --base <rev> --out request.json` | Pass-1 deterministic facts collector |
| `oida-code audit <repo> --base <rev> --intent ticket.md --format markdown --out report.md` | Full deterministic audit (Phase 1 path) |
| `oida-code normalize <request.json> --surface impact\|changed` | Build NormalizedScenario from request |
| `oida-code score-trace <trace.jsonl> --request <r> --surface impact [--experimental-shadow-fusion]` | Trajectory scorer + opt-in shadow fusion |
| `oida-code estimate-llm <packet.json> --llm-provider replay --llm-response-fixture <reply.json>` | Phase 4.0 LLM estimator dry-run |
| `oida-code verify-claims <packet.json> --forward-replay <r> --backward-replay <r>` | Phase 4.1 forward/backward verifier |

Standalone evaluation scripts:

```bash
python scripts/evaluate_shadow_formula.py        # E2 sensitivity sweep + graph ablation; writes .oida/e2/
python scripts/real_repo_shadow_smoke.py         # E2 shadow smoke on oida-code self + attrs
python scripts/real_repo_smoke.py                # D3 structural smoke
python scripts/paper_sanity_check.py             # D1 paper-conformance checks
```

`oida-code audit` shells out to `ruff` / `mypy` / `pytest` / `semgrep` / `codeql` via `shutil.which`. Run it from inside the **target** repo's venv so `pytest` and `mypy` see the target's installed packages. Missing tools become `status="tool_missing"` in the report — never a crash.

**Windows note**: `pytest` invocations must run in the foreground. There is a per-repo memory feedback (`feedback_windows_fork_pressure.md`) that running pytest with `run_in_background` triggers exponential Cygwin fork costs through self-audit tests that re-invoke the CLI.

## Architecture

### The hard wall: official fusion fields stay null

**ADR-22, ADR-24, ADR-25, ADR-26 are non-negotiable.** No code path may emit `total_v_net`, `debt_final`, `corrupt_success`, `corrupt_success_ratio`, or `verdict` in a Pydantic model dump. Enforcement is layered:

1. The schemas don't expose those fields (e.g. `ShadowFusionReport`, `EstimatorReport`, `VerifierAggregationReport`).
2. `authoritative` is pinned to `Literal[False]` on shadow + verifier reports — not just defaulted, **pinned**, so any attempt to set `True` fails Pydantic validation.
3. Runners check raw response bodies for forbidden phrases (V_net / debt_final / corrupt_success / verdict / merge_safe / production_safe / bug_free / security_verified / official_*) and reject the entire response if any appears.
4. Tests (`test_*_no_official_fields`, `test_official_summary_fields_still_null_in_e3`, `test_official_ready_candidate_is_unreachable_at_v0_4_x`) parametrize over every fixture and assert no leakage.

When adding a new schema or runner, add it to the forbidden-phrase chain — never just trust the default.

### The three architecture rules (PLAN.md §4)

1. **Truth does not come from the LLM.** Evidence flows from tools, tests, counter-examples, proven properties, static alerts. The LLM plans / explains / proposes — it never replaces a passing test, and `is_authoritative=True` is rejected for `source="llm"` at the model level.
2. LongCoT and Simula are Phase 7 research moat — off the critical path.
3. No "mathematical proof of arbitrary code" claim, ever.

### Vendored OIDA core (ADR-02)

`src/oida_code/_vendor/oida_framework/` is a frozen copy of the OIDA v4.2 reference implementation. SHA256-pinned in `VENDORED_FROM.txt`. Reuse, do not rewrite. ruff and mypy explicitly **exclude** `_vendor/` (see `pyproject.toml`); modifying it would diverge from upstream. Refresh = re-copy + recompute SHA + bump `VENDORED_FROM.txt`.

The translator between Pydantic public surface and the vendored dataclass core lives in `src/oida_code/score/mapper.py` (`pydantic_to_vendored`, `vendored_to_pydantic`).

### Module layout

```
src/oida_code/
├── _vendor/oida_framework/    OIDA v4.2 core (verbatim; do not edit)
├── models/                    Pydantic v2 public surface (extra="forbid")
├── extract/                   Obligation extractor + dependency graph + audit-surface derivation
├── verify/                    Deterministic runners (ruff, mypy, pytest, semgrep, codeql, hypothesis, mutmut)
├── score/                     Trajectory scorer, fusion readiness, shadow fusion, mapper, event_evidence
├── estimators/                Phase 4.0 — frozen estimate contracts + deterministic baselines + LLM dry-run
├── verifier/                  Phase 4.1 — forward/backward verifier contracts + aggregator + replay providers
├── report/                    Markdown / JSON report rendering
├── github/                    GitHub Action + Checks API integration (Phase 6)
├── ingest/                    Trace parsers (Claude Code transcripts, etc.)
└── cli.py                     Typer entry point
```

### Block / phase cadence

The project ships in named blocks driven by external review files in `QA/A*.md`. Each block:

1. Receives a directive in `QA/A<n>.md` listing acceptance criteria, forbidden actions, expected tests, and the report filename.
2. Lands as one commit with `feat(phase<n>-<block>):` or `feat(phase<n>):`, an ADR appended to `memory-bank/decisionLog.md` (timestamped), a report under `reports/<block>.md`, and tests covering every listed criterion.
3. Updates README + `memory-bank/progress.md` with the new test count and status line.
4. Validates via the next `QA/A<n+1>.md` review file before the next block starts.

Current blocks: **Phase 3.5** (A→D structural pipeline) → **E0–E3** (fusion readiness, shadow fusion, formula decision, estimator contracts) → **Phase 4.0** (LLM estimator dry-run) → **4.0.1** (fence hardening) → **Phase 4.1** (forward/backward verifier contract). Reports for each block under `reports/`.

### ADR discipline

Every architectural decision lives in `memory-bank/decisionLog.md` as a timestamped block:

```
[YYYY-MM-DD HH:MM:SS] - **ADR-NN: <one-line decision>.**
**Why:** ...
**Decision:** ...
**Accepted:** ...
**Rejected:** ...
**Outcome:** ...
```

Append, never overwrite. When code references an ADR (e.g. `# ADR-22 §5 Option B`), search `decisionLog.md` for the full text — code comments only carry the pointer, not the rationale.

### Forbidden in any commit

- Modifying `src/oida_code/_vendor/**` (ADR-02).
- Calling an external LLM API by default. The opt-in providers (`OptionalExternalLLMProvider`, `OptionalExternalVerifierProvider`) are stubs that raise `*ProviderUnavailable` whether the env var is set or not — Phase 4.2 will introduce real bindings under a follow-up ADR.
- Echoing env-var values in logs, exceptions, reports, or commits. There are explicit `test_*_does_not_leak_secrets` guards.
- Bumping the PyPI version to a non-alpha tag while official fields are still blocked.
- Adding tests that claim predictive validation (Spearman, commits>0 correlation, etc.). Phase 3 already tripped on a length-confound proxy; Phase 3.5+ enforces "structural validation only".

### Pydantic patterns specific to this repo

- `ConfigDict(extra="forbid", frozen=True, validate_assignment=True)` on every report-shaped model. Frozen prevents post-construction mutation; `validate_assignment` rejects re-validation attempts.
- `Literal[False]` pin (instead of `bool = False`) for any field that must never become `True` in production.
- Public collections are `tuple[...]`, not `list[...]` — list mutators (`append`, `extend`, slice assignment) are unavailable on the public surface.
- Model-level `@model_validator(mode="after")` for cross-field invariants (e.g. `source="default"` ⇒ `confidence=0.0` ⇒ `is_default=True`).

### Prompt-injection defence (4.0.1 hardening)

User-supplied evidence text in `LLMEvidencePacket.evidence_items[*].summary` is wrapped in named per-item fences:

```
<<<OIDA_EVIDENCE id="[E.event.1]" kind="event">>>
...untrusted data...
<<<END_OIDA_EVIDENCE id="[E.event.1]">>>
```

`_neutralise_fence_close` inserts a zero-width space inside any literal `<<<END_OIDA_EVIDENCE` or `<<<OIDA_EVIDENCE` in user content so a forged inner close cannot truncate the block. The fence is one defence layer — runners additionally enforce forbidden-phrase rejection, schema validation, and citation rules independently. Don't rely on the fence alone.

### Memory bank protocol (.github/*.chatmode.md)

`memory-bank/` carries the long-running project context: `productContext.md`, `activeContext.md`, `systemPatterns.md`, `decisionLog.md`, `progress.md`, `architect.md`. Append timestamped entries; never overwrite. The "UMB" / "Update Memory Bank" command in chatmode files refreshes all five at once.

## Important docs to read before non-trivial changes

- `oida-code-mvp-blueprint.md` — authoritative spec.
- `PLAN.md` — phase decomposition (§14 Phase 0-7).
- `memory-bank/systemPatterns.md` — 3-pass pipeline, 4-bucket verdict, OIDA scoring formulas, vendoring discipline.
- `memory-bank/decisionLog.md` — full ADR history (ADR-01 … ADR-26).
- The relevant `reports/<block>.md` for whichever block you're touching.
- The latest `QA/A<n>.md` directive (currently QA/A16.md — Phase 4.1 validation + Phase 4.2 plan).
