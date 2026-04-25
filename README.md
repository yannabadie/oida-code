# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

**Phase 3.5 complete (v0.4.2) — structural measurement pipeline validated.**

Shipped: deterministic verifiers (ruff/mypy/pytest/semgrep/codeql/hypothesis/mutmut),
AST-based obligation extractor with 1..N PreconditionSpec expansion (ADR-20),
bounded dependency graph for repair propagation (ADR-21), Explore/Exploit
trajectory scorer faithful to paper 2604.13151 (ADR-18/19), audit-surface
derivation (impact cone), and E0 fusion-readiness layer (ADR-22).

Validation: D1 paper sanity all 10 aspects PASS; D2 10 hermetic
code-domain traces (71 parametrized tests) PASS; D3 real-repo
structural smoke PASS on 2 repos; 225/225 unit tests green.

**Fusion fields remain blocked / null pending E1 / Phase 4** —
`capability` / `benefit` / `observability` are structural defaults
until the LLM intent estimator lands. The fusion-readiness layer
classifies inputs and explicitly declines to emit `total_v_net` /
`debt_final` / `corrupt_success` while these inputs are defaults.

**Not production-ready.** See `memory-bank/progress.md`,
`reports/block_d_validation.md`, `reports/e0_fusion_readiness.md`.

## Install (dev)

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

```bash
# Collect Pass-1 facts
oida-code inspect ./path/to/repo --base origin/main --out .oida/request.json

# End-to-end deterministic audit (Phase 1 path)
oida-code audit ./path/to/repo --base origin/main --intent ticket.md --format markdown --out .oida/report.md
```

### Environment note

`oida-code audit` shells out to `ruff`, `mypy`, `pytest`, `semgrep`, `codeql`.
Each is resolved via `shutil.which()`. **Run `oida-code` from inside the
target repo's virtual environment** so `pytest` and `mypy` pick up the
target's installed packages. Missing tools are handled gracefully — the
report carries `status="tool_missing"` rather than crashing — so you can
safely omit any of them on minimal environments.

## License

MIT — see `LICENSE`.
