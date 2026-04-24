# OIDA Framework

**OIDA** = **Operational Integrity and Debt Analysis** for tool-using AI agents.

This reference implementation accompanies the working-paper draft
*Operational Debt in Tool-Using AI Agents: A Trace-Based Model of Corrupt Success, Systemic Harm, and Dependency-Aware Recovery*.

It is **not** a production safety system. It is a small, testable research artifact
that demonstrates four ideas:

1. outcome success is not enough;
2. low-grounding, low-reversibility patterns can accumulate **operational debt**;
3. traces can be converted into a **dependency graph** for repair planning;
4. invalidating a governing pattern should trigger **double-loop** remediation, not only local rollback.

## What the framework computes

For each event in a scenario trace, OIDA computes:

- `grounding`: weighted proportion of critical preconditions verified from the live environment;
- `q_obs`: visible / local success (completion, tests, operator acceptance);
- `mu`: autonomous execution compatibility, here instantiated as `sqrt(reversibility * observability)`;
- `lambda_bias`: risk that a reused action pattern becomes biased pseudo-knowledge;
- `pattern_state`: one of `H`, `C+`, `E`, or `B`;
- `v_dur`: durable value;
- `h_sys`: systemic harm;
- `v_net`: net value;
- cumulative `n_stock`, `b_load`, `n_eff`, and `debt`.

It also builds:

- a constitutive DAG;
- a supportive DAG;
- a dominance-based repair plan for double-loop remediation.

## Scenario format

Each scenario is a JSON file with:

- scenario metadata;
- optional configuration;
- a list of events.

Each event contains:
- `id`
- `pattern_id`
- `task`
- `capability`
- `reversibility`
- `observability`
- `blast_radius`
- `completion`
- `tests_pass`
- `operator_accept`
- `benefit`
- `preconditions`
- optional `constitutive_parents`
- optional `supportive_parents`
- optional `invalidates_pattern`

Example:

```json
{
  "id": "e2",
  "pattern_id": "p_delete_recreate",
  "task": "delete_and_recreate_database",
  "capability": 0.96,
  "reversibility": 0.05,
  "observability": 0.15,
  "blast_radius": 0.98,
  "completion": 1.0,
  "tests_pass": 0.90,
  "operator_accept": 0.85,
  "benefit": 0.35,
  "preconditions": [
    {"name": "snapshot exists", "weight": 3, "verified": false}
  ],
  "constitutive_parents": ["e1"]
}
```

## Install

### Minimal local install

```bash
python -m pip install -r requirements.txt
```

### Editable install

```bash
python -m pip install -e .
```

## Run the demos

### Analyze a scenario

```bash
python -m oida.cli analyze examples/destructive_db_recreate.json --pretty
python -m oida.cli analyze examples/safe_online_migration.json --pretty
python -m oida.cli analyze examples/repeated_low_grounding_cost_optimization.json --pretty
```

### Save JSON output

```bash
python -m oida.cli analyze examples/destructive_db_recreate.json --out results/destructive_db_recreate_report.json --pretty
```

### Generate a double-loop repair plan

```bash
python -m oida.cli repair examples/destructive_db_recreate.json e1 --pretty
```

### Run the included smoke script

```bash
python run_demo.py
```

### Run tests

```bash
python -m unittest discover -s tests -v
```

## Included scenarios

- `safe_online_migration.json`
  - high grounding, reversible or observable steps, zero debt in the reference run.
- `destructive_db_recreate.json`
  - a Replit/Kiro-like class of scenario: high visible success, high systemic harm, positive debt.
- `repeated_low_grounding_cost_optimization.json`
  - repeated reuse of a weakly grounded pattern until debt turns positive.

## Interpretation guidelines

This artifact is intentionally conservative in what it claims.

### What it does show

- A concrete implementation of the **stock–flow** idea:
  visible success can remain high while debt and systemic harm grow.
- A way to formalize **corrupt success** at runtime.
- A dominance-based distinction between:
  - descendants that must be reopened (`reopen`);
  - descendants that should be audited (`audit`).

### What it does not show

- It does **not** solve pattern extraction from raw traces.
  Here, `pattern_id` is provided in the input.
- It does **not** provide calibrated coefficients for real deployments.
- It does **not** replace runtime guardrails, policy engines, IAM, backup discipline, or human approval.
- It is **not** a claim of state-of-the-art incident prevention.

## Suggested next steps before public release

1. Replace hand-assigned `pattern_id` with clustering or rule extraction from traces.
2. Export OIDA metrics as OpenTelemetry-compatible attributes.
3. Calibrate `alpha_B`, thresholds, and harm weights on real coding/CloudOps traces.
4. Add benchmark tasks with explicit irreversible actions.
5. Publish the artifact with a clear license and a Zenodo DOI.

## Folder structure

```text
oida_framework/
├── README.md
├── pyproject.toml
├── requirements.txt
├── LICENSE_NOTE.md
├── run_demo.py
├── examples/
├── oida/
│   ├── __init__.py
│   ├── __main__.py
│   ├── analyzer.py
│   ├── cli.py
│   ├── io.py
│   └── models.py
├── results/
└── tests/
```
