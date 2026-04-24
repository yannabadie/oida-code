"""
Visualization module for OID framework.

Generates publication-quality figures for:
    - Agent trajectories (Q_obs, V_IA, H_sys, V_net over time)
    - Comparative profiles
    - The database deletion scenario
    - Pattern state distribution over time
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


COLORS = {
    "q_obs": "#2196F3",
    "v_ia": "#4CAF50",
    "h_sys": "#F44336",
    "v_net": "#9C27B0",
    "biased": "#FF5722",
    "confirmed": "#009688",
    "active": "#FFC107",
}


def plot_trajectory(trajectory, title="Agent Trajectory", savepath=None):
    """Plot Q_obs, V_IA, H_sys, V_net over time."""
    T = [tp.T for tp in trajectory]
    q = [tp.score.q_obs for tp in trajectory]
    v = [tp.score.v_ia for tp in trajectory]
    h = [tp.score.h_sys for tp in trajectory]
    n = [tp.score.v_net for tp in trajectory]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle(title, fontsize=14, fontweight="bold")

    ax1.plot(T, q, color=COLORS["q_obs"], linewidth=2, label="$Q_{obs}$ (observable quality)")
    ax1.plot(T, v, color=COLORS["v_ia"], linewidth=2, label="$V_{IA}$ (durable value)")
    ax1.plot(T, h, color=COLORS["h_sys"], linewidth=2, label="$H_{sys}$ (systemic harm)")
    ax1.plot(T, n, color=COLORS["v_net"], linewidth=2, linestyle="--", label="$V_{net}$ (net value)")
    ax1.axhline(y=0, color="gray", linewidth=0.5, linestyle=":")
    ax1.set_ylabel("Score")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Pattern state counts
    nb = [tp.n_biased for tp in trajectory]
    nc = [tp.n_confirmed for tp in trajectory]
    na = [tp.n_active for tp in trajectory]

    ax2.stackplot(
        T, nb, nc, na,
        labels=["Biased (B)", "Confirmed (C+)", "Active (H)"],
        colors=[COLORS["biased"], COLORS["confirmed"], COLORS["active"]],
        alpha=0.8,
    )
    ax2.set_xlabel("Timestep")
    ax2.set_ylabel("Pattern count")
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return savepath


def plot_comparative(results, metric="v_net", title=None, savepath=None):
    """Plot a single metric across multiple agent profiles."""
    fig, ax = plt.subplots(figsize=(10, 5))
    if title is None:
        title = f"Comparative: {metric}"
    ax.set_title(title, fontsize=13, fontweight="bold")

    for name, traj in results.items():
        T = [tp.T for tp in traj]
        vals = [getattr(tp.score, metric) for tp in traj]
        ax.plot(T, vals, linewidth=2, label=name)

    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle=":")
    ax.set_xlabel("Timestep")
    ax.set_ylabel(metric)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return savepath


def plot_database_scenario(trajectory, disaster_t=None, savepath=None):
    """
    Plot the database deletion scenario.
    Highlights the divergence between Q_obs and V_net.
    """
    T = [tp.T for tp in trajectory]
    q = [tp.score.q_obs for tp in trajectory]
    v = [tp.score.v_net for tp in trajectory]
    h = [tp.score.h_sys for tp in trajectory]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title(
        "Database Deletion Scenario: The Atrophied Agent",
        fontsize=13, fontweight="bold",
    )

    ax.plot(T, q, color=COLORS["q_obs"], linewidth=2.5, label="$Q_{obs}$ (benchmarks see this)")
    ax.plot(T, v, color=COLORS["v_net"], linewidth=2.5, linestyle="--", label="$V_{net}$ (actual net value)")
    ax.fill_between(T, 0, h, color=COLORS["h_sys"], alpha=0.2, label="$H_{sys}$ (systemic harm)")

    if disaster_t is not None:
        ax.axvline(x=disaster_t, color="red", linewidth=1.5, linestyle=":",
                   label=f"$V_{{net}} < 0$ at T={disaster_t}")

    ax.axhline(y=0, color="gray", linewidth=0.8)
    ax.set_xlabel("Timestep")
    ax.set_ylabel("Score")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Annotation
    if disaster_t:
        ax.annotate(
            "Agent becomes\nnet-destructive",
            xy=(disaster_t, 0), xytext=(disaster_t + 5, -0.3),
            fontsize=10, color="red",
            arrowprops=dict(arrowstyle="->", color="red"),
        )

    plt.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return savepath


def plot_transition_risk_surface(savepath=None):
    """
    Plot the H→B transition risk as a function of μ and grounding.
    Shows why irreversible tasks with low grounding are dangerous.
    """
    mu_vals = np.linspace(0, 1, 100)
    g_vals = np.linspace(0, 1, 100)
    MU, G = np.meshgrid(mu_vals, g_vals)

    alpha_b = 0.15
    s_eff = 0.7
    usage = 5
    RISK = alpha_b * s_eff * (1 - MU) * (1 - G) * usage

    fig, ax = plt.subplots(figsize=(8, 6))
    c = ax.contourf(MU, G, RISK, levels=20, cmap="RdYlGn_r")
    fig.colorbar(c, ax=ax, label="$\\lambda_{H \\to B}$ (transition risk)")
    ax.set_xlabel("$\\mu(\\tau)$ — Reversibility × Observability", fontsize=11)
    ax.set_ylabel("$G_D$ — Operational Grounding", fontsize=11)
    ax.set_title("H → B Transition Risk Surface", fontsize=13, fontweight="bold")

    # Annotate zones
    ax.annotate("DANGER ZONE\n(db deletion, config change)",
                xy=(0.1, 0.1), fontsize=10, color="white", fontweight="bold",
                ha="center")
    ax.annotate("SAFE ZONE\n(code gen, docs)",
                xy=(0.85, 0.85), fontsize=10, color="darkgreen", fontweight="bold",
                ha="center")

    plt.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return savepath
