# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

**Phase 3.5 + E1 complete — structural measurement pipeline validated;
opt-in experimental shadow fusion shipped non-authoritative.**

Shipped: deterministic verifiers (ruff/mypy/pytest/semgrep/codeql/hypothesis/mutmut),
AST-based obligation extractor with 1..N PreconditionSpec expansion (ADR-20),
bounded dependency graph for repair propagation (ADR-21), Explore/Exploit
trajectory scorer faithful to paper 2604.13151 (ADR-18/19), audit-surface
derivation (impact cone), E0 fusion-readiness layer (ADR-22), and E1
experimental shadow fusion as opt-in CLI flag (`--experimental-shadow-fusion`).

Validation: D1 paper sanity all 10 aspects PASS; D2 10 hermetic
code-domain traces (71 parametrized tests) PASS; D3 real-repo
structural smoke PASS on 2 repos; **250/250 unit tests green**.

**Official `total_v_net` / `debt_final` / `corrupt_success` remain
blocked / null** — `capability` / `benefit` / `observability` are
structural defaults until the Phase-4 LLM intent estimator. The
fusion-readiness layer classifies inputs and explicitly declines
official emission. The shadow fusion is diagnostic-only,
non-authoritative by type (`Literal[False]` + frozen Pydantic model),
and lives in a separate output block.

**E2 formula decision and E3 estimator contracts pending.**
**Not production-ready.** See `memory-bank/progress.md`,
`reports/block_d_validation.md`, `reports/e0_fusion_readiness.md`,
`reports/e1_shadow_fusion.md`.

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
