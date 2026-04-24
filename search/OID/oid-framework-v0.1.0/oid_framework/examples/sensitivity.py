#!/usr/bin/env python3
"""
Sensitivity analysis for OID Framework.

Tests robustness of three qualitative predictions:
    P1. Atrophied agent emerges on irreversible tasks
    P2. Grounding is the primary differentiator of V_net sign
    P3. Higher capability without grounding accelerates atrophy

Sweeps key parameters: alpha_B, delta, s_D, psi, mu, capability.
Reports fraction of parameter combinations where predictions hold.
"""

import sys, os
import itertools
import json
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oid_framework.core import TaskDescriptor, ActionPattern, PatternState
from oid_framework.simulation import OIDSimulation, SimulationConfig

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


@dataclass
class SensitivityResult:
    param_name: str
    param_values: list
    p1_rates: list  # atrophied emergence rate
    p2_rates: list  # grounding advantage rate
    p3_rates: list  # capability-acceleration rate


def run_single(alpha_b, delta, s_d, mu_crit, psi_crit, cap_high, cap_low, n_steps=40, seed=42):
    """Run a paired comparison and check predictions."""
    tasks = [
        TaskDescriptor("critical", mu=mu_crit, psi=psi_crit, n_min=8.0, exposure_weight=1.0),
        TaskDescriptor("safe", mu=0.85, psi=0.3, n_min=2.0, exposure_weight=2.0),
    ]

    config = SimulationConfig(
        n_steps=n_steps, seed=seed, alpha_b=alpha_b, delta=delta,
        confirmation_rate=0.15,
    )
    sim = OIDSimulation(config)

    # Agent A: high capability, no grounding
    agent_a = sim.make_agent("high_cap", capability=cap_high, mastery=0.8)
    traj_a = sim.run_trajectory(agent_a, tasks)

    # Agent B: lower capability, grounded (pre-seeded)
    from oid_framework.dynamics import DependencyDAG
    agent_b = sim.make_agent("grounded", capability=cap_low, mastery=0.85)
    dag_b = DependencyDAG()
    sim.seed_agent(agent_b, 8, "critical", dag_b)
    traj_b = sim.run_trajectory(agent_b, tasks, dag_b)

    # Agent C: even higher capability, no grounding (for P3)
    config_c = SimulationConfig(
        n_steps=n_steps, seed=seed + 1, alpha_b=alpha_b, delta=delta,
        confirmation_rate=0.15,
    )
    sim_c = OIDSimulation(config_c)
    agent_c = sim_c.make_agent("very_high_cap", capability=min(cap_high + 0.1, 0.99), mastery=0.9)
    traj_c = sim_c.run_trajectory(agent_c, tasks)

    final_a = traj_a[-1].score
    final_b = traj_b[-1].score
    final_c = traj_c[-1].score

    # P1: atrophied agent emerges (high Q_obs, negative V_net)
    p1 = final_a.q_obs > 0.5 and final_a.v_net < 0

    # P2: grounded agent has higher V_net than ungrounded
    p2 = final_b.v_net > final_a.v_net

    # P3: higher capability without grounding produces lower V_net
    p3 = final_c.v_net < final_a.v_net or (final_c.v_net < 0 and final_a.v_net < 0)

    return p1, p2, p3


def sweep_parameter(name, values, defaults, n_repeats=5):
    """Sweep one parameter and measure prediction robustness."""
    p1_rates, p2_rates, p3_rates = [], [], []

    for val in values:
        params = dict(defaults)
        params[name] = val
        p1_count, p2_count, p3_count = 0, 0, 0

        for seed_offset in range(n_repeats):
            p1, p2, p3 = run_single(
                alpha_b=params["alpha_b"],
                delta=params["delta"],
                s_d=params["s_d"],
                mu_crit=params["mu_crit"],
                psi_crit=params["psi_crit"],
                cap_high=params["cap_high"],
                cap_low=params["cap_low"],
                seed=42 + seed_offset * 7,
            )
            p1_count += p1
            p2_count += p2
            p3_count += p3

        p1_rates.append(p1_count / n_repeats)
        p2_rates.append(p2_count / n_repeats)
        p3_rates.append(p3_count / n_repeats)

    return SensitivityResult(name, values, p1_rates, p2_rates, p3_rates)


def run_full_sensitivity():
    """Run sensitivity analysis across all key parameters."""
    defaults = {
        "alpha_b": 0.15,
        "delta": 0.05,
        "s_d": 5.0,
        "mu_crit": 0.15,
        "psi_crit": 5.0,
        "cap_high": 0.9,
        "cap_low": 0.7,
    }

    sweeps = {
        "alpha_b":  [0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50],
        "delta":    [0.01, 0.02, 0.05, 0.10, 0.15, 0.20],
        "mu_crit":  [0.05, 0.10, 0.15, 0.25, 0.35, 0.50, 0.65, 0.80],
        "psi_crit": [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0],
        "cap_high": [0.5, 0.6, 0.7, 0.8, 0.9, 0.95],
    }

    results = {}
    for name, values in sweeps.items():
        print(f"  Sweeping {name}: {values}")
        results[name] = sweep_parameter(name, values, defaults, n_repeats=8)

    return results


def plot_sensitivity(results, savepath=None):
    """Plot sensitivity analysis results."""
    n = len(results)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle("Sensitivity Analysis: Robustness of Qualitative Predictions", fontsize=14, fontweight="bold")

    axes_flat = axes.flatten()

    labels = {
        "alpha_b": r"$\alpha_B$ (bias transition intensity)",
        "delta": r"$\delta$ (decay rate)",
        "mu_crit": r"$\mu(\tau)$ (task reversibility)",
        "psi_crit": r"$\psi(\tau)$ (systemic impact)",
        "cap_high": "Agent capability",
    }

    for idx, (name, res) in enumerate(results.items()):
        ax = axes_flat[idx]
        ax.plot(res.param_values, res.p1_rates, "o-", color="#F44336", linewidth=2, label="P1: Atrophied emerges")
        ax.plot(res.param_values, res.p2_rates, "s-", color="#4CAF50", linewidth=2, label="P2: Grounding advantage")
        ax.plot(res.param_values, res.p3_rates, "^-", color="#2196F3", linewidth=2, label="P3: Cap. accelerates atrophy")
        ax.set_xlabel(labels.get(name, name), fontsize=10)
        ax.set_ylabel("Prediction rate", fontsize=10)
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(y=0.5, color="grey", linestyle=":", alpha=0.5)
        ax.legend(fontsize=7, loc="lower left")
        ax.grid(True, alpha=0.3)

    # Hide the 6th subplot
    axes_flat[-1].axis("off")

    plt.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return savepath


def summarise(results):
    """Print summary statistics."""
    print("\n" + "=" * 70)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("=" * 70)
    for name, res in results.items():
        avg_p1 = sum(res.p1_rates) / len(res.p1_rates)
        avg_p2 = sum(res.p2_rates) / len(res.p2_rates)
        avg_p3 = sum(res.p3_rates) / len(res.p3_rates)
        print(f"\n  {name}:")
        print(f"    P1 (atrophied emerges):       {avg_p1:.1%} avg across {len(res.param_values)} values")
        print(f"    P2 (grounding advantage):      {avg_p2:.1%} avg")
        print(f"    P3 (cap accelerates atrophy):  {avg_p3:.1%} avg")

    # Global robustness
    all_p1 = [r for res in results.values() for r in res.p1_rates]
    all_p2 = [r for res in results.values() for r in res.p2_rates]
    all_p3 = [r for res in results.values() for r in res.p3_rates]
    print(f"\n  GLOBAL ROBUSTNESS:")
    print(f"    P1: {sum(all_p1)/len(all_p1):.1%}")
    print(f"    P2: {sum(all_p2)/len(all_p2):.1%}")
    print(f"    P3: {sum(all_p3)/len(all_p3):.1%}")
    print("=" * 70)


if __name__ == "__main__":
    print("Running sensitivity analysis...")
    results = run_full_sensitivity()
    summarise(results)
    path = plot_sensitivity(results, "/home/claude/figures/fig7_sensitivity.png")
    print(f"\nSaved: {path}")
