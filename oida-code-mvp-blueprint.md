# OIDA Code Audit — MVP Blueprint

## 1. Positioning

**Do not ship this as “unslop”.** Ship it as an **AI code verifier**.

Working names:
- OIDA Code Audit
- OIDA Verify
- OIDA PR Guard

Core promise:

> Measure the gap between what AI-written code appears to do and what it actually guarantees.

The MVP is a **CLI first**, then a **GitHub PR check**, then optionally a SaaS.

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

### Pass 3 — Agentic verification
Use the LLM only as a **verifier/planner**, not as the final judge.

Sub-agents:
- **forward verifier**: from code + tests + spec → what is actually sufficient?
- **backward verifier**: from expected outcome → which premises are missing?
- **repair planner**: if verdict is red/yellow, generate precise repair tasks and targeted prompts

Final verdict buckets:
- **proved enough for merge**
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

### Deployment modes
1. `oida-code audit ./repo`
2. GitHub Action (local/self-hosted)
3. GitHub App later for rich annotations and external SaaS

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

## 9. Report contract

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

## 10. LLM choice for the MVP

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

## 11. First 10 implementation days

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

## 12. Hard rules for honesty

Do not claim “mathematical proof” for arbitrary code.

Claim only one of these:
- **formal proof for an explicit property**
- **counterexample found by execution**
- **static evidence of rule violation**
- **insufficient evidence**

That keeps the product defensible.

## 13. Best wedge

The wedge is not “clean code”.

The wedge is:

> High apparent success, low grounding, hidden operational debt.

That is exactly what your existing OIDA core already measures.
