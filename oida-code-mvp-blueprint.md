# OIDA Code Audit — MVP Blueprint (historical 2026-04-23)

> **ARCHIVAL — READ THIS FIRST (Phase 6.i / ADR-81, 2026-05-04).**
> This file is the **2026-04-23 historical MVP blueprint**. It is **not**
> the active product spec, **not** a roadmap, and **not** a source of
> current product claims. **Do not quote sentences from this file as
> current product claims.** The active product positioning is
> diagnostic-only; the canonical surfaces are
> `docs/product_strategy.md` (active direction),
> `docs/project_status.md` (verified current repo state), and
> `PLAN.md` §0 (authority hierarchy). Specifically, the fields
> `total_v_net`, `debt_final`, `corrupt_success`,
> `corrupt_success_ratio`, `verdict`, `V_net`, and `Debt` shown anywhere
> in this file are **not public outputs**; they remain blocked by the
> ADR-22 / ADR-24 / ADR-25 / ADR-26 hard wall, the Pydantic schemas pin
> them with `Literal[False]` flags, and runner guards reject them in raw
> responses. Phrases such as "AI code verifier", "actually guarantees",
> "Final verdict buckets", "proved enough for merge", "repair planner",
> "GitHub App later", and "SaaS" describe the 2026-04-23 blueprint
> shape, **not** the 2026-05-04 product. Per ADR-78 / Phase 6.f, the
> active reusable Action describes itself as "Diagnostic evidence for
> AI-authored Python diffs", not an "AI code verifier". Per ADR-77 /
> Phase 6.e, the active CLI Markdown front door reframes legacy verdict
> tokens as diagnostic reviewer text. Per ADR-80 / Phase 6.h, the
> companion `PLAN.md` document carries the same archival framing.

## 1. Positioning (historical 2026-04-23, NOT an active product positioning)

> **Historical (pre-ADR-74).** The "AI code verifier" framing below is
> obsolete pre-ADR-74 wording. The active 2026-05-04 positioning is
> "Diagnostic evidence for AI-authored Python diffs" per
> `docs/product_strategy.md` and ADR-78 / Phase 6.f. The "GitHub PR
> check" / "SaaS" / "GitHub App" trajectory is **not** an active
> product roadmap; the active integration is the reusable composite
> Action (`action.yml`).

**Do not ship this as “unslop”.** Ship it as an **AI code verifier**. *(historical 2026-04-23 framing — obsolete; the active product is diagnostic-only per ADR-74 / ADR-78.)*

Working names:
- OIDA Code Audit
- OIDA Verify
- OIDA PR Guard

Core promise (historical 2026-04-23, NOT an active product claim):

> Measure the gap between what AI-written code appears to do and what it actually guarantees.

The MVP is a **CLI first**, then a **GitHub PR check**, then optionally a SaaS. *(historical 2026-04-23 trajectory — the SaaS / GitHub App path is not an active roadmap.)*

## 2. Reuse from the current project

Keep the current OIDA core almost intact.

Already present in your code:
- `grounding(event)` from weighted verified preconditions
- `q_obs(event)` from completion / tests / operator acceptance
- `mu(event) = sqrt(reversibility * observability)`
- `lambda_bias(...)`
- stock / bias / debt accumulation
- `v_net = v_dur - h_sys`
- `double_loop_repair(root_event)` on constitutive/supportive graphs

Interpretation:
- `oid-framework` stays the **research / simulation** package
- `oida_framework_package` becomes the **deterministic scoring engine**
- new `oida-code` layer becomes the **repo/diff extractor + verifier + report generator**

## 3. MVP architecture

### Pass 1 — Deterministic facts
Input:
- repo path OR git diff OR PR checkout
- optional ticket / prompt / spec file

Collect:
- changed files
- language(s)
- dependency manifests
- test command(s)
- git diff hunks
- existing CI config

Run:
- format/lint
- type checks
- Semgrep
- CodeQL (when language supported)
- unit/integration tests

Output:
- machine facts only

### Pass 2 — Behavioral verification
Generate or run:
- property-based tests for critical pure functions
- mutation testing on changed code
- adversarial regression cases for changed public behaviors

Output:
- evidence that a claim survives non-happy-path execution

### Pass 3 — Agentic verification (historical 2026-04-23, NOT an active product surface)

> **Historical (pre-ADR-22 hard wall enforcement / pre-ADR-77).** The
> "Final verdict buckets" listed below are the 2026-04-23 internal
> label vocabulary. The "proved enough for merge" bucket and the
> "repair planner" sub-agent are obsolete pre-ADR-74 wording and are
> **not** active product outputs. Per ADR-77 / Phase 6.e, the active
> CLI Markdown front door reframes the legacy verdict tokens as
> diagnostic reviewer text (e.g. legacy `verified` → "No
> contradiction observed by configured deterministic checks
> (diagnostic only; not proof of correctness)"). Per the Phase 6.e
> CLI quarantine, the `repair` command is shipped only as a
> compatibility stub that does **not** modify code.

Use the LLM only as a **verifier/planner**, not as the final judge.

Sub-agents:
- **forward verifier**: from code + tests + spec → what is actually sufficient?
- **backward verifier**: from expected outcome → which premises are missing?
- **repair planner**: if verdict is red/yellow, generate precise repair tasks and targeted prompts *(historical 2026-04-23 — obsolete; the active `repair` CLI is a compatibility stub that does not modify code.)*

Final verdict buckets *(historical 2026-04-23 — obsolete; not active product labels)*:
- **proved enough for merge** *(obsolete pre-ADR-74 wording — not an active product label)*
- **counterexample found**
- **insufficient evidence**
- **high apparent quality / negative net value**

## 4. MVP scope

### Languages
Start with **Python only** for v0.

Reason:
- your current codebase is Python
- Hypothesis + mutmut give a strong verification wedge quickly
- Semgrep and CodeQL both work here

### Deployment modes (historical 2026-04-23)

> **Historical (pre-ADR-74).** Mode 3 (GitHub App / SaaS) is **not**
> an active product roadmap. The active integration is the reusable
> composite Action (`action.yml`); the GitHub App / Check Run path is
> deferred research per ADR-30 / ADR-78.

1. `oida-code audit ./repo`
2. GitHub Action (local/self-hosted)
3. GitHub App later for rich annotations and external SaaS *(historical 2026-04-23 — obsolete; the GitHub App / SaaS trajectory is not an active roadmap.)*

## 5. Normalized audit model

Use two layers.

### A. Raw audit request
This is produced from the repo / diff / ticket.

```json
{
  "repo": {
    "path": "/workspace/repo",
    "revision": "HEAD",
    "base_revision": "origin/main"
  },
  "intent": {
    "summary": "Add email validation to signup endpoint",
    "sources": ["ticket.md", "prompt.txt"]
  },
  "scope": {
    "changed_files": [
      "app/api/signup.py",
      "app/validators.py",
      "tests/test_signup.py"
    ],
    "language": "python"
  },
  "commands": {
    "lint": "ruff check .",
    "types": "mypy app",
    "tests": "pytest -q"
  },
  "policy": {
    "max_critical_findings": 0,
    "min_mutation_score": 0.65,
    "min_property_checks": 50
  }
}
```

### B. Normalized OIDA event scenario
This is the deterministic input to the scoring engine.

```json
{
  "name": "signup_email_validation_pr_42",
  "description": "Validation change on public signup path",
  "config": {
    "alpha_b": 1.15,
    "confirm_threshold": 0.80,
    "bias_threshold": 0.45,
    "tau_ref": 3.0
  },
  "events": [
    {
      "id": "e1",
      "pattern_id": "p_input_normalization",
      "task": "normalize_email_input",
      "capability": 0.74,
      "reversibility": 0.95,
      "observability": 0.70,
      "blast_radius": 0.25,
      "completion": 0.90,
      "tests_pass": 0.81,
      "operator_accept": 0.88,
      "benefit": 0.65,
      "preconditions": [
        {"name": "None input rejected", "weight": 2, "verified": true},
        {"name": "whitespace-only rejected", "weight": 2, "verified": true},
        {"name": "unicode normalization defined", "weight": 1, "verified": false}
      ]
    },
    {
      "id": "e2",
      "pattern_id": "p_signup_contract_update",
      "task": "enforce_validation_in_api_path",
      "capability": 0.69,
      "reversibility": 0.90,
      "observability": 0.65,
      "blast_radius": 0.40,
      "completion": 0.78,
      "tests_pass": 0.72,
      "operator_accept": 0.70,
      "benefit": 0.80,
      "preconditions": [
        {"name": "all callers use validator", "weight": 3, "verified": false},
        {"name": "400 response contract documented", "weight": 1, "verified": true}
      ],
      "constitutive_parents": ["e1"]
    }
  ]
}
```

## 6. How to derive the OIDA variables from code

### Grounding
`grounding = verified_precondition_weight / total_precondition_weight`

Sources of verification:
- static proof from AST / call graph / type checker
- dynamic proof from tests / property tests
- explicit human or policy confirmation

### Q_obs
Keep the existing formula:

`q_obs = 0.40 * completion + 0.40 * tests_pass + 0.20 * operator_accept`

#### completion
How much of the intended change is visibly implemented?
Examples:
- function exists
- call sites updated
- migration added
- API contract wired
- docs/schema updated when required

#### tests_pass
Composite score for behavioral evidence, for example:

`tests_pass = 0.50 * regression + 0.25 * property + 0.25 * mutation`

#### operator_accept
Merge readiness proxy:
- no critical blocker
- lint/types green
- no critical Semgrep/CodeQL alert in changed lines

### Capability
For code, interpret `capability` as **difficulty-fit** rather than model self-confidence.

Suggested formula:

`capability = 1 - difficulty_mismatch`

Where mismatch grows when the change touches:
- DB migrations
- concurrency
- auth/security paths
- public APIs
- multi-module refactors
- cross-service behavior

### Mu
Keep:

`mu = sqrt(reversibility * observability)`

#### reversibility
High when:
- change is isolated
- rollback is trivial
- no irreversible data migration
- feature flag exists

Low when:
- schema/data mutation
- destructive writes
- one-way migrations

#### observability
High when:
- assertions
- logs/metrics
- invariant checks
- contract tests
- business-level validations

### Blast radius
Estimate from:
- number of changed modules
- public API exposure
- dependency fan-out
- data-layer criticality

## 7. Suggested repository structure

```text
oida-code/
├── pyproject.toml
├── README.md
├── src/
│   └── oida_code/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models/
│       │   ├── audit_request.py
│       │   ├── normalized_event.py
│       │   └── audit_report.py
│       ├── ingest/
│       │   ├── git_repo.py
│       │   ├── diff_parser.py
│       │   └── manifest.py
│       ├── extract/
│       │   ├── claims.py
│       │   ├── preconditions.py
│       │   ├── blast_radius.py
│       │   └── dependencies.py
│       ├── verify/
│       │   ├── lint.py
│       │   ├── typing.py
│       │   ├── semgrep_scan.py
│       │   ├── codeql_scan.py
│       │   ├── pytest_runner.py
│       │   ├── hypothesis_runner.py
│       │   └── mutmut_runner.py
│       ├── llm/
│       │   ├── client.py
│       │   ├── schemas.py
│       │   ├── forward_verifier.py
│       │   ├── backward_verifier.py
│       │   └── repair_prompts.py
│       ├── score/
│       │   ├── mapper.py
│       │   ├── analyzer.py
│       │   └── verdict.py
│       ├── report/
│       │   ├── json_report.py
│       │   ├── markdown_report.py
│       │   └── sarif_export.py
│       └── github/
│           ├── checks.py
│           └── annotations.py
├── examples/
│   ├── audit_request.json
│   ├── normalized_scenario.json
│   └── audit_report.json
└── tests/
```

## 8. CLI contract

```bash
oida-code inspect ./repo --base origin/main --out .oida/request.json
oida-code normalize .oida/request.json --out .oida/scenario.json
oida-code verify .oida/scenario.json --out .oida/evidence.json
oida-code audit ./repo --base origin/main --intent ticket.md --format markdown --out .oida/report.md
oida-code repair .oida/report.json --out .oida/repair.md
```

Recommended user-facing shortcut:

```bash
oida-code audit ./repo --base origin/main --intent ticket.md
```

## 9. Report contract (historical 2026-04-23, NOT an active schema)

> **Historical (pre-ADR-22 hard wall enforcement).** The JSON snippet
> below is the 2026-04-23 aspirational shape. **None of the
> highlighted official fusion fields are public outputs in the
> current product.** The active report contract is the diagnostic-only
> `AuditReport` Pydantic model in
> `src/oida_code/models/audit_report.py`; its summary excludes
> `total_v_net`, `debt_final`, `corrupt_success_ratio`, and the active
> Markdown front door reframes `verdict` per ADR-77 / Phase 6.e.

Minimum JSON report:

```json
{
  "summary": {
    "verdict": "yellow",
    "mean_q_obs": 0.83,
    "mean_grounding": 0.58,
    "total_v_net": -0.21,
    "debt_final": 0.63,
    "corrupt_success_ratio": 0.5
  },
  "critical_findings": [
    {
      "id": "f1",
      "title": "Validator exists but one API path bypasses it",
      "kind": "missing_precondition",
      "evidence": ["call graph", "tests", "forward verifier"],
      "path": "app/api/admin_signup.py",
      "line": 44
    }
  ],
  "repair": {
    "reopen": ["e2"],
    "audit": [],
    "next_prompts": [
      "Update every signup entrypoint so email normalization is applied before persistence. Return a unified 400 contract and add regression tests for bypass paths.",
      "Write Hypothesis tests for empty, whitespace-only, Unicode-normalized, and mixed-case emails."
    ]
  }
}
```

> **Hard-wall reminder (post-ADR-22 / ADR-24 / ADR-25 / ADR-26).** The
> `verdict`, `total_v_net`, `debt_final`, `corrupt_success_ratio`, and
> related official fusion fields shown above are **not emitted** as
> public outputs. The Pydantic schemas pin them with `Literal[False]`
> flags, runner guards reject the tokens in raw responses, and the
> action manifest does not expose them as outputs. The JSON snippet
> above is the 2026-04-23 historical shape; the active diagnostic-only
> `AuditReport` schema lives in `src/oida_code/models/audit_report.py`
> and excludes every field listed above.

## 10. LLM choice for the MVP (historical 2026-04-23)

> **Historical (pre-ADR-30 / pre-ADR-78).** The local-Qwen / cloud-LLM
> trajectory below is the 2026-04-23 development plan. The active
> product is replay-by-default; opt-in external providers are gated by
> ADR-30 anti-secret-exfil + Phase 4.7 provider-baseline workflow + the
> Phase 5.6 anti-MCP locks. The active reusable Action describes itself
> as "Diagnostic evidence for AI-authored Python diffs" per
> ADR-78 / Phase 6.f.

### Local default
Use **Qwen3.6-35B-A3B** as the main verifier/planner when local inference is acceptable.

Why:
- open-weight
- official support for `transformers serve`
- official support for `llama.cpp` GGUF local inference
- designed for agentic coding and repository-level reasoning

### Local fallback
If latency or VRAM is too tight, keep a smaller fallback model for extraction/classification tasks.

Pattern:
- small model → extraction / summarization / cheap classification
- 35B-A3B → final forward/backward verification and repair planning

## 11. First 10 implementation days (historical 2026-04-23)

> **Historical (pre-Phase-1 implementation).** This 10-day plan was
> the 2026-04-23 implementation intent. It is **not** an active
> roadmap; the actual shipped trajectory diverged through Phase 0 →
> Phase 1 → … → Phase 6.h. See `memory-bank/progress.md` for the
> verified actual timeline. Day 9's "forward/backward verdict merge"
> is obsolete pre-ADR-77 framing and is **not** an active product
> output.

### Day 1–2
- unify naming: `oida-code`
- import the current analyzer as `score/analyzer.py`
- define `AuditRequest`, `NormalizedScenario`, `AuditReport`

### Day 3–4
- implement `inspect` for Python repos
- detect changed files and commands
- collect raw facts from lint/types/tests

### Day 5–6
- add Semgrep + pytest
- add Hypothesis generation for selected changed functions
- compute `tests_pass` composite

### Day 7–8
- map raw facts → normalized OIDA events
- reuse existing `double_loop_repair`
- emit JSON + Markdown report

### Day 9
- add local Qwen verifier with structured JSON output
- implement forward/backward verdict merge

### Day 10
- demo on 10 intentionally sloppy PRs
- record false positives / false negatives
- tune thresholds only after this evaluation

## 12. Hard rules for honesty (historical 2026-04-23 wording, conceptually preserved)

> **Historical wording (pre-ADR-22 / pre-ADR-77).** The four claim
> categories below describe the intended honesty boundary. The active
> 2026-05-04 honesty boundary is enforced **structurally**: ADR-22
> hard wall (no `total_v_net` / `debt_final` / `corrupt_success` /
> `verdict` emitted), Phase 4.7+ anti-MCP locks, Phase 6.e/6.f/6.g/6.h
> diagnostic-only front-door quarantines, and Phase 4.0.1
> prompt-injection fences. The intent of the four categories below
> remains directly applicable; the wording references obsolete labels
> only.

Do not claim “mathematical proof” for arbitrary code.

Claim only one of these:
- **formal proof for an explicit property**
- **counterexample found by execution**
- **static evidence of rule violation**
- **insufficient evidence**

That keeps the product defensible.

## 13. Best wedge (historical 2026-04-23 framing)

> **Historical (pre-ADR-74).** The "wedge" framing is a 2026-04-23
> internal positioning paragraph. The active 2026-05-04 product
> positioning is **diagnostic evidence for AI-authored Python diffs**
> per `docs/product_strategy.md`, not an operational-debt verdict.
> The internal scorer still computes the OIDA quantities; the
> corresponding fusion fields (`V_net`, `Debt`, etc.) remain blocked
> by the ADR-22 hard wall.

The wedge is not “clean code”.

The wedge is:

> High apparent success, low grounding, hidden operational debt.

That is exactly what your existing OIDA core already measures.
