# System Patterns

## Architectural Patterns

### The 3-pass pipeline (blueprint §3)

1. **Pass 1 — Deterministic facts.** Read-only. Inputs: repo path / diff / ticket. Outputs: machine facts only (lint, types, Semgrep/CodeQL, unit tests, git diff hunks, manifests).
2. **Pass 2 — Behavioral verification.** Property-based tests (Hypothesis), mutation testing (mutmut), adversarial regressions. Evidence that a claim survives non-happy-path execution.
3. **Pass 3 — Agentic verification.** LLM as verifier/planner only, never final judge. Sub-agents: *forward verifier* (premises → sufficient?), *backward verifier* (outcome → missing premises?), *repair planner*.

### The 4 verdict buckets (blueprint §3, §12)

1. **proved enough for merge** — formal proof of an explicit property OR tests+mutations green above thresholds.
2. **counterexample found** — execution produced a failing case.
3. **insufficient evidence** — cannot confirm nor refute.
4. **high apparent quality / negative net value** — *corrupt success*: `Q_obs ≥ 0.80` with `V_net < 0`.

### OIDA v4.2 scoring core (paper §4, vendored `analyzer.py`)

Formulas reused verbatim — do NOT reimplement:

- `grounding = Σ w_k · 1[verified_k] / Σ w_k`
- `Q_obs = 0.40·completion + 0.40·tests_pass + 0.20·operator_accept`
- `μ = sqrt(reversibility · observability)`
- `λ_{H→B} = α_B · cap · (1−μ) · (1−g) · ρ(reuse) · Q_obs`
- `N_eff = N_stock − B_load`; `Debt = max(0, −N_eff)`
- `V_dur = benefit · g · (1 + μ·cap) · (1 − Debt̃_{t−1})`
- `H_sys = ψ · (1−μ) · cap · B̃ · Q_obs`
- `V_net = V_dur − H_sys`
- pattern state machine `{H, C+, E, B}` + dominance-based double-loop repair

### Vendoring discipline

- Frozen copies under `src/oida_code/_vendor/<pkg>/`.
- `VENDORED_FROM.txt` records the upstream path + SHA256 of each file at vendoring time.
- `ruff` and `mypy --strict` EXCLUDE `_vendor/**` (see `pyproject.toml`). Touching vendored code would diverge from upstream.
- To refresh a vendor: re-copy, re-compute SHA256, bump `VENDORED_FROM.txt`.

## Design Patterns

### Honesty over progress (blueprint §12)

Unimplemented logic is `NotImplementedError` with a phase pointer, never a placeholder that silently succeeds or returns mock data.

### Pydantic boundary, dataclass core

- Public surface (`oida_code.models`) = Pydantic v2 `BaseModel` with `ConfigDict(extra="forbid")`.
- Internal math (vendored) = `@dataclass(slots=True)`.
- A `score/mapper.py` translator sits between them (phase 2).

### Subprocess safety

All external-tool invocations (`git`, later `ruff`, `mypy`, `semgrep`, `pytest`, `mutmut`, `hypothesis`) use:

- argv form (no `shell=True`);
- `shutil.which` lookup of the binary;
- `subprocess.run` with an explicit timeout;
- typed error translation (`GitRepoError`, …).

## Common Idioms

- Module docstrings cite the blueprint section(s) the file implements.
- `from __future__ import annotations` at the top of every `.py` (Python 3.11+ best practice with mypy strict).
- `__all__` in every public module.
- Absolute imports only (no relative imports into `_vendor`).
- For `verify/typing.py` (shadows stdlib), callers must use the full `oida_code.verify.typing` path.

---
[2026-04-24 07:04:50] - Initial system patterns documented from blueprint §3, §6, §12 + paper §4.
