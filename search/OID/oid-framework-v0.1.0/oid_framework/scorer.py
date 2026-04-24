"""
Integrity scorer: computes the triple output + net value.

    Q_obs  — observable quality (what benchmarks see)
    V_IA   — durable productive value
    H_sys  — systemic harm
    V_net  — net value = V_IA - H_sys
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .core import AgentProfile, TaskDescriptor
from .dynamics import IntegrityDynamics


@dataclass
class IntegrityScore:
    """Result of scoring an agent on a task at time T."""
    agent_id: str
    task_id: str
    T: int
    q_obs: float      # observable quality ∈ [0, 1]
    v_ia: float        # durable value ≥ 0
    h_sys: float       # systemic harm ≥ 0
    v_net: float       # net value ∈ ℝ
    grounding: float   # operational grounding ∈ [0, 1]
    n_eff: float       # effective stock ∈ ℝ
    debt: float        # learning debt ≥ 0
    bias_load: float   # accumulated bias load
    transition_risk: float  # current H → B risk

    @property
    def is_atrophied(self) -> bool:
        """Agent atrophié: high Q_obs, negative V_net."""
        return self.q_obs > 0.6 and self.v_net < 0

    @property
    def profile_type(self) -> str:
        """Classify agent profile."""
        if self.is_atrophied:
            return "atrophied"
        if self.grounding > 0.7 and self.v_net > 0.5:
            return "grounded_expert"
        if self.grounding < 0.3 and self.q_obs > 0.5:
            return "novice_assisted"
        if self.debt > 0:
            return "indebted"
        return "operational"


class IntegrityScorer:
    """
    Computes the four outputs of the OID model.

    Q_obs(I,τ,T) = S_eff + (1 - S_eff) · G_D
    V_IA(I,τ,T)  = G_D · [1 + μ · S_eff] · g(C_stock, T)
    H_sys(I,τ,T) = ψ · (1-μ) · S_eff · B̃ · Q_obs
    V_net(I,τ,T) = V_IA - H_sys
    """

    def __init__(
        self,
        dynamics: IntegrityDynamics,
        gamma_c: float = 0.3,   # cross-domain acceleration factor
    ):
        self.dynamics = dynamics
        self.gamma_c = gamma_c

    def score(
        self,
        agent: AgentProfile,
        task: TaskDescriptor,
        T: int,
        c_stock: float = 0.0,
        adjacent_contribution: float = 0.0,
    ) -> IntegrityScore:
        """Score an agent on a specific task at time T."""

        # Grounding
        g_d = self.dynamics.grounding(agent, task, T, adjacent_contribution)

        # Effective AI capability
        s_eff = agent.s_ia_eff(T)

        # Q_obs: what benchmarks and observers see
        q_obs = s_eff + (1 - s_eff) * g_d

        # Cross-domain acceleration
        g_accel = 1 + self.gamma_c * c_stock * math.log(1 + T)

        # V_IA: durable productive value
        v_ia = g_d * (1 + task.mu * s_eff) * g_accel

        # Bias tilde: saturating function of bias load
        b_load = agent.bias_load(T)
        b_tilde = 1 - math.exp(-b_load)

        # H_sys: systemic harm
        h_sys = task.psi * (1 - task.mu) * s_eff * b_tilde * q_obs

        # V_net
        v_net = v_ia - h_sys

        # Transition risk for the most-used H-state pattern
        h_patterns = [
            p for p in agent.patterns.values()
            if p.state.value == "H"
        ]
        max_risk = 0.0
        for p in h_patterns:
            risk = self.dynamics.transition_risk_h_to_b(
                p, agent, task, g_d, T
            )
            max_risk = max(max_risk, risk)

        return IntegrityScore(
            agent_id=agent.agent_id,
            task_id=task.task_id,
            T=T,
            q_obs=q_obs,
            v_ia=v_ia,
            h_sys=h_sys,
            v_net=v_net,
            grounding=g_d,
            n_eff=agent.n_eff(T),
            debt=agent.debt(T),
            bias_load=b_load,
            transition_risk=max_risk,
        )

    def score_aggregate(
        self,
        agent: AgentProfile,
        tasks: list,
        T: int,
        c_stock: float = 0.0,
    ) -> dict:
        """Score agent across all tasks, weighted by exposure."""
        scores = []
        total_weight = sum(t.exposure_weight for t in tasks)
        agg = {"q_obs": 0, "v_ia": 0, "h_sys": 0, "v_net": 0}

        for task in tasks:
            s = self.score(agent, task, T, c_stock)
            w = task.exposure_weight / total_weight
            agg["q_obs"] += w * s.q_obs
            agg["v_ia"] += w * s.v_ia
            agg["h_sys"] += w * s.h_sys
            agg["v_net"] += w * s.v_net
            scores.append(s)

        return {"aggregate": agg, "per_task": scores}
