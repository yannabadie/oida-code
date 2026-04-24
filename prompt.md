# Mission — OIDA Code Audit MVP (phase 1 bootstrap)

You are operating inside `C:\Code\unslop.ai` with filesystem, git, shell, MCP, and web access.
Your mission is to bootstrap a defensible v0.1 of the project described in the workspace — NOT to generate a finished SaaS, NOT to "autonomously work until perfect". Ship a minimal correct foundation, stop at the first gate I define below, wait for my review.

You have access to the following environment variables in `.env` (OpenAI / Anthropic / other API keys). Use them only when explicitly needed for Pass 3 (LLM verification) or when invoking advisor/codex. Never print keys in logs, reports, commits, or memory-bank files.

-----------------------------------------------------------
## Step 0 — Context ingestion (mandatory, in this order)

Read the following files before writing ANY code. Do not skim. Take notes in `memory-bank/activeContext.md` as you go.

1. `oida-code-mvp-blueprint.md`        ← authoritative blueprint, this is the spec
2. `brainstorm2_improved.md`           ← refined reasoning, overrides brainstorm2
3. `last.md`                           ← final prioritization of the 3 research sources
4. `infos.md`                          ← name collision check + hardware constraints
5. `brainstorm2.md`                    ← original draft, keep for historical context only
6. `oida-code-audit-request.example.json` and `oida-code-audit-report.example.json`   ← I/O contracts
7. `search/OIDA/oida_framework/README.md` and `search/OIDA/oida_framework/oida/analyzer.py`  ← existing deterministic OIDA core (reuse, do not rewrite)
8. `search/OID/oid-framework-v0.1.0/README.md` and `oid_framework/*.py`                     ← research/simulation package (reuse for scorer math only)
9. `search/OIDA/OID_Paper_Abadie_2026.pdf`  ← formal OIDA v4.2 model (grounding, Q_obs, mu, lambda_bias, V_net formulas are authoritative here)
10. `.github/*.chatmode.md`           ← memory-bank protocol you MUST follow

When documents contradict each other, the authoritative order is:
`oida-code-mvp-blueprint.md` > `brainstorm2_improved.md` > `last.md` > `infos.md` > `brainstorm2.md`

Produce a structured summary in `memory-bank/activeContext.md` under section "Phase 1 bootstrap — context digest" covering:
- the product wedge (one sentence),
- the three research sources and their exact role in the MVP,
- the 4 verdict buckets,
- the honesty rules from blueprint §12,
- every contradiction you found between documents and how you resolved it.

-----------------------------------------------------------
## Step 1 — Naming and repo creation (explicit checkpoint)

DO NOT name the repo `unslop.ai`. The blueprint §1 and `infos.md` both forbid it (name collision with github.com/mshumer/unslop, unslop.xyz, unslop.design; also the anti-slop framing contradicts the OIDA positioning).

Working name for the package, CLI and repo: **`oida-code`**.
Public GitHub repo: **`oida-code`** under the user's account (check `git config user.name` first; if ambiguous, ASK me before creating).

Before creating the GitHub repo:
- run `git init` inside `C:\Code\unslop.ai` if not already a git repo,
- write a proper `.gitignore` (Python, venv, .env, memory-bank/*.tmp, __pycache__, .pytest_cache, .mypy_cache, dist, build, *.egg-info, *.pyc, .oida/, search/**/__pycache__),
- commit all existing content as `chore: initial brainstorm and research snapshot`,
- ONLY THEN propose the repo name to me and wait for confirmation before `gh repo create`.

Do not push to GitHub without my explicit "go" in chat. Staying local is acceptable until I confirm.

-----------------------------------------------------------
## Step 2 — Skeleton only (blueprint §7)

Create the `src/oida_code/` tree EXACTLY as specified in blueprint §7. Every file should exist with:
- a minimal docstring describing its responsibility,
- correct imports so the package is importable,
- NotImplementedError for methods you cannot yet ground in a test.

Do NOT fill in logic you cannot verify in this phase. Empty scaffolds are honest; speculative code is slop. This project measures slop — do not produce it.

Files to actually implement in phase 1:
- `pyproject.toml` (Python 3.11+, package name `oida-code`, CLI entry point `oida-code`)
- `src/oida_code/__init__.py` with version string
- `src/oida_code/models/audit_request.py`, `models/normalized_event.py`, `models/audit_report.py` — Pydantic v2 models matching the two example JSONs exactly (validate by loading the example files in tests)
- `src/oida_code/cli.py` with only the `inspect` subcommand implemented (Typer or Click), others declared but raising NotImplementedError with a clear message
- `src/oida_code/ingest/git_repo.py` + `ingest/diff_parser.py` — read repo path, base revision, produce the raw fact block for `inspect`
- `src/oida_code/score/analyzer.py` — thin wrapper importing and re-exporting from the existing `search/OIDA/oida_framework/oida/analyzer.py` (vendor it as an internal dependency, do NOT reimplement the formulas)
- `tests/` — at minimum: round-trip test for each Pydantic model against its example JSON, smoke test for `oida-code inspect --help`, smoke test for the vendored analyzer on `search/OIDA/oida_framework/examples/safe_online_migration.json`.

-----------------------------------------------------------
## Step 3 — Quality gates (must pass before you declare phase 1 done)

Run locally and include outputs in the final report:
1. `ruff check src/ tests/` — must pass
2. `mypy src/oida_code` with strict mode — must pass on the code you wrote (ignore vendored code if needed, but document it in `pyproject.toml`)
3. `pytest -q` — must pass, minimum tests listed in Step 2
4. `oida-code inspect ./search/OIDA/oida_framework --base HEAD` must produce a valid `AuditRequest` JSON on stdout that deserializes cleanly

If ANY gate fails, fix it before stopping. If you cannot fix it within 3 attempts, stop, write the failure diagnostic to `memory-bank/activeContext.md`, and ask me.

-----------------------------------------------------------
## Step 4 — Memory bank synchronization (follow .github/*.chatmode.md protocol)

At the end of phase 1, update:
- `memory-bank/projectBrief.md` — fill with real content from blueprint §1 (not the template)
- `memory-bank/productContext.md` — product wedge, core features, tech stack
- `memory-bank/systemPatterns.md` — the 3-pass pipeline (deterministic / behavioral / agentic), the 4 verdict buckets, the honesty rules from blueprint §12
- `memory-bank/decisionLog.md` — ADRs for: (a) rejecting `unslop.ai` name, (b) reusing existing OIDA core verbatim, (c) Python-only v0, (d) Qwen3.6-35B-A3B as default local model, (e) CLI-first before GitHub Action
- `memory-bank/progress.md` — phase 1 done items, phase 2 next items (blueprint days 3-4)
- `memory-bank/activeContext.md` — final state after phase 1, open questions for my review

Format every memory-bank entry with `[YYYY-MM-DD HH:MM:SS] - [Summary]` as required by the chatmode spec.

-----------------------------------------------------------
## Step 5 — Stop and report

Write `PHASE1_REPORT.md` at repo root containing:
1. Exact list of files created with SHA256
2. Output of each quality gate (copy-paste, not a summary)
3. Coverage % from pytest-cov
4. Every decision you made that was NOT in the blueprint, with rationale
5. Every contradiction you found in the input documents and how you resolved it
6. Open questions for me, ranked by blocking / nice-to-have
7. A honest self-critique: what in what you produced is actually defensible vs. placeholder?

Then STOP. Do not start phase 2 (Semgrep, Hypothesis, LLM verifier) without my explicit "go phase 2" in chat.

-----------------------------------------------------------
## Operating rules (non-negotiable)

- **Honesty over progress**: if a piece of logic cannot be tested, leave it as `NotImplementedError` with a TODO referencing blueprint §. Placeholder code is debt — this project measures debt.
- **Reuse over rewrite**: the OIDA core under `search/OIDA/oida_framework/` is already shipped. Vendor it, do not reimplement grounding/Q_obs/mu/lambda_bias/V_net formulas.
- **Scope discipline**: phase 1 is CLI skeleton + ingest + vendored scorer + one working subcommand. Nothing else. No Semgrep, no LLM, no GitHub Action, no mutation testing. Those are phases 2-4 of blueprint §13.
- **When to escalate**: if you hit a design question not answered in `oida-code-mvp-blueprint.md`, STOP and ask me in chat. Do not invoke advisor/codex unless I explicitly say "use codex". Those tools are for phase 2+ deep dives on static analysis and property testing integration, not for phase 1 skeleton decisions.
- **Secrets**: never commit `.env`, never echo keys, never include keys in memory-bank or reports.
- **Commits**: conventional commits (`feat:`, `chore:`, `test:`, `docs:`), one logical change per commit, no 500-line mega commits.
- **No dead code, no stub tests that always pass, no `# type: ignore` without a reason in the comment**.

-----------------------------------------------------------
## What "done" looks like for phase 1

- `oida-code inspect` works end-to-end on the repo itself
- Pydantic models round-trip the two example JSONs byte-for-byte when re-serialized with `model_dump_json(indent=2)`
- `pytest -q` green, coverage > 70% on code you wrote
- memory-bank files reflect the real project, not the templates
- PHASE1_REPORT.md answers every question in Step 5
- repo is clean (`git status` shows nothing), all commits signed-off

Start by reading the files listed in Step 0. Do not write a single line of code before you have produced the context digest in `memory-bank/activeContext.md` and I can review it. Ping me in chat when the digest is ready.