# OID Framework — Operational Integrity Dynamics for Autonomous AI Agents

A formal model of competence degradation and systemic harm in autonomous AI agents.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from oid_framework import OIDSimulation, SimulationConfig
from oid_framework.simulation import run_database_deletion_scenario

# Run the database deletion scenario
result = run_database_deletion_scenario()
print(f"V_net at disaster: {result['final_score'].v_net:.3f}")
print(f"Profile type: {result['final_score'].profile_type}")
```

## Run Full Simulation Suite

```bash
python -m oid_framework.examples.run_all
```

## Core Concepts

- **PatternState {H, C+, E, B}**: State machine for action patterns
- **ActionPattern**: Learned heuristic with state, value, audit flag
- **DependencyDAG**: Constitutive/supportive action dependencies
- **IntegrityScorer**: Computes Q_obs, V_IA, H_sys, V_net
- **OIDSimulation**: Multi-step trajectory simulation engine

## Citation

```
Abadie, Y. (2026). Operational Integrity Dynamics for Autonomous AI Agents:
A Formal Model of Competence Degradation and Systemic Harm.
```

## License

MIT
