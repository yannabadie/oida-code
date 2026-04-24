#!/usr/bin/env python3
"""
OID Framework — Example: Run all scenarios and generate figures.

This script demonstrates:
1. The database deletion scenario (atrophied agent)
2. Comparative trajectories (grounded vs novice vs reckless)
3. H→B transition risk surface
4. Full simulation with standard task portfolio
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oid_framework.core import TaskDescriptor
from oid_framework.simulation import OIDSimulation, SimulationConfig, run_database_deletion_scenario
from oid_framework.viz import (
    plot_trajectory,
    plot_comparative,
    plot_database_scenario,
    plot_transition_risk_surface,
)


def main():
    out_dir = "/home/claude/figures"
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("OID Framework v0.1.0 — Simulation Suite")
    print("=" * 60)

    # 1. Database deletion scenario
    print("\n[1/4] Running database deletion scenario...")
    result = run_database_deletion_scenario()
    traj = result["trajectory"]
    disaster_t = result["disaster_timestep"]
    final = result["final_score"]

    print(f"  Disaster timestep (V_net < 0): T={disaster_t}")
    print(f"  Final Q_obs: {final.q_obs:.3f}")
    print(f"  Final V_net: {final.v_net:.3f}")
    print(f"  Final H_sys: {final.h_sys:.3f}")
    print(f"  Final debt:  {final.debt:.3f}")
    print(f"  Profile:     {final.profile_type}")

    plot_database_scenario(traj, disaster_t, f"{out_dir}/fig1_database_scenario.png")
    print(f"  → Saved fig1_database_scenario.png")

    # 2. Comparative trajectories
    print("\n[2/4] Running comparative trajectories...")
    config = SimulationConfig(n_steps=80, seed=42, alpha_b=0.12)
    sim = OIDSimulation(config)

    profiles = {
        "grounded_expert":     (0.75, 0.9),   # moderate capability, high mastery
        "novice_high_cap":     (0.95, 0.5),   # high capability, low mastery
        "balanced_adjacent":   (0.80, 0.75),  # moderate both
        "reckless_autonomous": (0.95, 0.85),  # high both, no prior grounding
    }

    # Pre-seed: grounded expert has prior experience on critical tasks
    seeds = {
        "grounded_expert":   {"db_migration": 8, "config_change": 5, "incident_response": 6},
        "novice_high_cap":   {},
        "balanced_adjacent": {"code_review": 4, "config_change": 3, "db_migration": 3},
        "reckless_autonomous": {},
    }

    tasks = sim.make_task_portfolio()
    results = sim.run_comparative(profiles, tasks, seeds)

    for name, traj in results.items():
        final = traj[-1].score
        print(f"  {name:25s}: Q_obs={final.q_obs:.3f}  V_net={final.v_net:.3f}  H_sys={final.h_sys:.3f}  type={final.profile_type}")

    plot_comparative(results, "v_net",
                     title="Net Value ($V_{net}$) — Comparative Trajectories",
                     savepath=f"{out_dir}/fig2_comparative_vnet.png")
    plot_comparative(results, "q_obs",
                     title="Observable Quality ($Q_{obs}$) — Comparative Trajectories",
                     savepath=f"{out_dir}/fig3_comparative_qobs.png")
    print(f"  → Saved fig2, fig3")

    # 3. Individual trajectory for grounded expert
    print("\n[3/4] Generating detailed trajectory plot...")
    plot_trajectory(results["grounded_expert"],
                    title="Trajectory: Grounded Expert Agent",
                    savepath=f"{out_dir}/fig4_trajectory_expert.png")
    plot_trajectory(results["reckless_autonomous"],
                    title="Trajectory: Reckless Autonomous Agent",
                    savepath=f"{out_dir}/fig5_trajectory_reckless.png")
    print(f"  → Saved fig4, fig5")

    # 4. Risk surface
    print("\n[4/4] Generating H→B risk surface...")
    plot_transition_risk_surface(f"{out_dir}/fig6_risk_surface.png")
    print(f"  → Saved fig6_risk_surface.png")

    print("\n" + "=" * 60)
    print("All figures generated in /home/claude/figures/")
    print("=" * 60)


if __name__ == "__main__":
    main()
