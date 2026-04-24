# Product Context

## Overview

`oida-code` is the AI-code-audit companion to the OIDA v4.2 trace-based stock-flow model.

**Product wedge:** measure the gap between apparent success (`Q_obs`) and durable value (`V_dur − H_sys`) on diff-scoped code changes, exposing *corrupt success* (high `Q_obs`, negative `V_net`) that ordinary test-pass metrics miss.

**Positioning:** this is NOT an "anti-slop" tool (blueprint §1 forbids that framing; `infos.md` confirms the name / concept collision with mshumer/unslop, unslop.xyz, unslop.design, etc.). It is "OIDA Code Audit".

## Core Features

### Phase 1 (shipped)

- **`oida-code inspect REPO --base REV --out FILE`** — collects Pass-1 deterministic facts (repo path, HEAD/base SHAs, changed files) and emits an `AuditRequest` JSON.
- **Pydantic v2 I/O schemas** — `AuditRequest`, `NormalizedScenario`, `AuditReport`. Deterministic round-trip.
- **Vendored OIDA scorer** — `OIDAAnalyzer`, `double_loop_repair`, pattern state machine `{H, C+, E, B}`, full `grounding / Q_obs / μ / λ_bias / V_net` chain.

### Phase 2 (planned, blueprint §13 days 3-8)

- `oida-code normalize`: raw facts → `NormalizedScenario`.
- `oida-code verify`: Semgrep + pytest + Hypothesis + mutmut; composite `tests_pass`.
- `oida-code audit`: full pipeline end-to-end → JSON + Markdown report.

### Phase 3 (planned, blueprint §13 day 9)

- LLM forward/backward verifier (AgentV-RL style) via Qwen3.6-35B-A3B local.
- `oida-code repair`: double-loop repair plan + targeted prompts.

### Phase 4 (planned)

- GitHub Action + Checks API for PR annotations.
- SARIF export for IDE / code-scanning integration.

## Tech Stack

- **Language:** Python >=3.11 (Python-only MVP; blueprint §4).
- **CLI:** Typer >=0.12.
- **Models:** Pydantic >=2.5.
- **Graph math:** NetworkX >=3.1 (via vendored OIDA core).
- **Packaging:** setuptools src-layout, console-script entry point `oida-code = oida_code.cli:app`.
- **Quality gates:** ruff, mypy --strict, pytest, pytest-cov (≥70%).
- **Planned (phase 2+):** semgrep, hypothesis, mutmut, codeql.
- **Planned LLM (phase 3):** Qwen3.6-35B-A3B via llama.cpp (local, Apache 2.0).

## Non-Goals

- Generic "clean code" AI assistant.
- Proving arbitrary semantic properties of arbitrary code (Rice).
- Replacing runtime guardrails, IAM, backups, or policy engines (paper §6 — OIDA is *complementary* accounting, not enforcement).

---
[2026-04-24 07:04:50] - Initial product context populated from blueprint §3-§10 after Step 0 ingestion.
