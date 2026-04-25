# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

**Phase 3.5 + E1 + E2 + E3 + Phase 4.0 + Phase 4.1 complete — structural pipeline
validated; opt-in experimental shadow fusion shipped non-authoritative;
formula decision recorded (KEEP V1 per ADR-23); estimator contracts
defined per ADR-24; LLM estimator dry-run shipped per ADR-25 with
8 hermetic fixtures including a prompt-injection scenario.**

Shipped: deterministic verifiers (ruff/mypy/pytest/semgrep/codeql/hypothesis/mutmut),
AST-based obligation extractor with 1..N PreconditionSpec expansion (ADR-20),
bounded dependency graph for repair propagation (ADR-21), Explore/Exploit
trajectory scorer faithful to paper 2604.13151 (ADR-18/19), audit-surface
derivation (impact cone), E0 fusion-readiness layer (ADR-22), E1
experimental shadow fusion as opt-in CLI flag (`--experimental-shadow-fusion`),
E2 formula decision (ADR-23) with sensitivity sweep / graph ablation /
variant comparison / real-repo shadow smoke, E3 estimator contracts
(ADR-24) with `EventEvidenceView` per-event evidence plumbing,
`SignalEstimate` / `EstimatorReport` frozen schemas, deterministic
baselines for capability/benefit/observability + completion/
tests_pass/operator_accept, LLM input/output contracts, and
`assess_estimator_readiness` ladder, and Phase 4.0 LLM estimator
dry-run (ADR-25) with `LLMProvider` abstraction (Fake / FileReplay
/ OptionalExternal — no API call by default), citable
`LLMEvidencePacket` with data-fenced prompt template, strict runner
that rejects forbidden phrases / cap breaches / missing citations,
`oida-code estimate-llm` CLI subcommand, and 8 hermetic fixtures
including a prompt-injection attempt.

Validation: D1 paper sanity all 10 aspects PASS; D2 10 hermetic
code-domain traces (71 parametrized tests) PASS; D3 real-repo
structural smoke PASS on 2 repos; E2 sensitivity sweep 26/26
delta=0.0; E2 graph ablation 7/7 invariants hold; E2 real-repo
shadow smoke PASS on oida-code self + attrs; E3 differentiation
fixture proves shadow pressure now varies with evidence; Phase 4.0
8 hermetic LLM-estimator fixtures PASS including prompt-injection;
**400/403 unit tests green (3 skips = V2 placeholder + 2 Phase-4
observability markers)**.

**Official `total_v_net` / `debt_final` / `corrupt_success` remain
blocked / null** — `capability` / `benefit` / `observability` are
structural defaults until the Phase-4 LLM intent estimator. The
fusion-readiness layer classifies inputs and explicitly declines
official emission. The shadow fusion is diagnostic-only,
non-authoritative by type (`Literal[False]` + frozen Pydantic model),
and lives in a separate output block. The estimator readiness ladder
sits beside the official gate (`payload["estimator_readiness"]`)
and produces `status="blocked"` on real repos at v0.4.x. The LLM
estimator can lift this to `shadow_ready` only on controlled
fixtures where evidence is captured; **no external API is called
by default** and the `OptionalExternalLLMProvider` is a Phase 4.2+
contract stub.

**Phase 4.2 tool-grounded verifier loop pending.**
**Not production-ready.** See `memory-bank/progress.md`,
`reports/block_d_validation.md`, `reports/e0_fusion_readiness.md`,
`reports/e1_shadow_fusion.md`, `reports/e2_shadow_formula_decision.md`,
`reports/e3_estimator_contracts.md`,
`reports/phase4_0_llm_estimator_dryrun.md`,
`reports/phase4_1_forward_backward_contract.md`.

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
