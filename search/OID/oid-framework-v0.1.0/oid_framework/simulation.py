"""
Simulation engine for OID Framework.

Runs multi-step agent trajectories with stochastic dynamics.
Supports multiple agent profiles and task portfolios.
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Optional

from .core import (
    ActionPattern,
    AgentProfile,
    OperationalEpisode,
    PatternState,
    TaskDescriptor,
)
from .dynamics import DependencyDAG, IntegrityDynamics
from .scorer import IntegrityScore, IntegrityScorer


@dataclass
class SimulationConfig:
    """Configuration for OID simulation."""
    n_steps: int = 100
    seed: int = 42
    # Dynamics parameters
    alpha_b: float = 0.15
    delta: float = 0.05
    tau_ref: float = 10.0
    # Scorer parameters
    gamma_c: float = 0.3
    # Episode generation
    episodes_per_step: int = 1
    confirmation_rate: float = 0.3  # base rate for H → C+
    # Grounding
    s_d: float = 5.0


@dataclass
class TrajectoryPoint:
    """Single point in an agent's trajectory."""
    T: int
    score: IntegrityScore
    n_patterns: int
    n_biased: int
    n_confirmed: int
    n_active: int


class OIDSimulation:
    """
    Simulation engine.

    Creates agent profiles, runs them through a sequence of
    operational episodes, and tracks integrity metrics over time.
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self.rng = random.Random(self.config.seed)
        self.dynamics = IntegrityDynamics(
            alpha_b=self.config.alpha_b,
            delta=self.config.delta,
            tau_ref=self.config.tau_ref,
        )
        self.scorer = IntegrityScorer(
            dynamics=self.dynamics,
            gamma_c=self.config.gamma_c,
        )

    @staticmethod
    def make_agent(
        agent_id: str,
        capability: float = 0.8,
        mastery: float = 0.7,
    ) -> AgentProfile:
        """Create a fresh agent profile."""
        return AgentProfile(
            agent_id=agent_id,
            capability=capability,
            mastery=mastery,
        )

    @staticmethod
    def make_task_portfolio() -> list:
        """
        Create the standard task portfolio for simulation.
        Implements the 'jagged frontier' — some tasks reversible,
        others irreversible.
        """
        return [
            TaskDescriptor("code_generation", mu=0.85, psi=0.5, n_min=2.0, exposure_weight=3.0),
            TaskDescriptor("code_review", mu=0.6, psi=1.0, n_min=4.0, exposure_weight=2.0),
            TaskDescriptor("db_migration", mu=0.15, psi=5.0, n_min=8.0, exposure_weight=1.0),
            TaskDescriptor("config_change", mu=0.3, psi=3.0, n_min=5.0, exposure_weight=2.0),
            TaskDescriptor("incident_response", mu=0.2, psi=4.0, n_min=7.0, exposure_weight=1.0),
            TaskDescriptor("documentation", mu=0.9, psi=0.2, n_min=1.0, exposure_weight=2.0),
        ]

    def run_trajectory(
        self,
        agent: AgentProfile,
        tasks: list,
        dag: Optional[DependencyDAG] = None,
    ) -> list:
        """
        Run a full trajectory for one agent.

        Returns list of TrajectoryPoint objects.
        """
        if dag is None:
            dag = DependencyDAG()

        trajectory = []

        for T in range(1, self.config.n_steps + 1):
            # 1. Decay all H-state patterns
            self.dynamics.apply_decay(agent, T)

            # 2. Generate new episodes
            for _ in range(self.config.episodes_per_step):
                task = self.rng.choice(tasks)
                self._generate_episode(agent, task, dag, T)

            # 3. Attempt H → B transitions
            g_d_cache = {}
            for p in list(agent.patterns.values()):
                if p.state == PatternState.H and p.task_id:
                    task_match = next(
                        (t for t in tasks if t.task_id == p.task_id), None
                    )
                    if task_match:
                        if task_match.task_id not in g_d_cache:
                            g_d_cache[task_match.task_id] = self.dynamics.grounding(
                                agent, task_match, T, s_d=self.config.s_d
                            )
                        self.dynamics.attempt_h_to_b(
                            p, agent, task_match,
                            g_d_cache[task_match.task_id],
                            T, self.rng,
                        )

            # 4. Stochastic H → C+ confirmations
            for p in list(agent.patterns.values()):
                if p.state == PatternState.H:
                    # Higher confirmation rate if reused and value still high
                    rate = self.config.confirmation_rate * p.value * (
                        1 + 0.1 * p.usage_count
                    )
                    if self.rng.random() < rate:
                        p.state = PatternState.CP
                        p.value = 1.0

            # 5. Score on a representative task (db_migration for critical path)
            critical_task = next(
                (t for t in tasks if t.task_id == "db_migration"), tasks[0]
            )
            score = self.scorer.score(agent, critical_task, T)

            # 6. Record trajectory point
            patterns_list = list(agent.patterns.values())
            trajectory.append(TrajectoryPoint(
                T=T,
                score=score,
                n_patterns=len(patterns_list),
                n_biased=sum(1 for p in patterns_list if p.state == PatternState.B),
                n_confirmed=sum(1 for p in patterns_list if p.state == PatternState.CP),
                n_active=sum(1 for p in patterns_list if p.state == PatternState.H),
            ))

        return trajectory

    def _generate_episode(
        self,
        agent: AgentProfile,
        task: TaskDescriptor,
        dag: DependencyDAG,
        T: int,
    ) -> None:
        """Generate a new operational episode."""
        pid = f"p_{agent.agent_id}_{T}_{self.rng.randint(0, 9999)}"

        # Determine parent patterns (reuse existing)
        parents = {}
        existing = [
            p for p in agent.patterns.values()
            if p.task_id == task.task_id and p.state in (PatternState.H, PatternState.CP)
        ]
        if existing:
            parent = self.rng.choice(existing)
            parent.usage_count += 1
            parent.last_used = T
            etype = "constitutive" if self.rng.random() < 0.4 else "supportive"
            parents[parent.pattern_id] = etype

        # Create new pattern
        pattern = ActionPattern(
            pattern_id=pid,
            state=PatternState.H,
            value=0.3 + 0.5 * self.rng.random(),
            created_at=T,
            last_used=T,
            usage_count=1,
            task_id=task.task_id,
            domains={task.task_id},
        )

        agent.patterns[pid] = pattern
        dag.add_pattern(pid, parents if parents else None)

        episode = OperationalEpisode(
            episode_id=f"ep_{pid}",
            timestep=T,
            task_id=task.task_id,
            pattern=pattern,
            parent_episodes=[],
            edge_types=parents,
            domains_mobilised={task.task_id},
        )
        agent.episodes.append(episode)

    def seed_agent(
        self,
        agent: AgentProfile,
        n_confirmed: int,
        task_id: str,
        dag: DependencyDAG,
    ) -> None:
        """Pre-seed an agent with confirmed patterns (prior grounding)."""
        for i in range(n_confirmed):
            pid = f"seed_{agent.agent_id}_{i}"
            pattern = ActionPattern(
                pattern_id=pid,
                state=PatternState.CP,
                value=1.0,
                created_at=0,
                last_used=0,
                usage_count=3,
                task_id=task_id,
                domains={task_id},
            )
            agent.patterns[pid] = pattern
            dag.add_pattern(pid)

    def run_comparative(
        self,
        profiles: dict,
        tasks: Optional[list] = None,
        seeds: Optional[dict] = None,
    ) -> dict:
        """
        Run trajectories for multiple agent profiles.

        Args:
            profiles: dict of {name: (capability, mastery)}
            tasks: optional task portfolio
            seeds: optional {name: {task_id: n_confirmed}}

        Returns:
            dict of {name: trajectory}
        """
        if tasks is None:
            tasks = self.make_task_portfolio()
        if seeds is None:
            seeds = {}

        results = {}
        for name, (cap, mast) in profiles.items():
            agent = self.make_agent(name, capability=cap, mastery=mast)
            dag = DependencyDAG()
            # Pre-seed if specified
            for task_id, n in seeds.get(name, {}).items():
                self.seed_agent(agent, n, task_id, dag)
            trajectory = self.run_trajectory(agent, tasks, dag)
            results[name] = trajectory

        return results


def run_database_deletion_scenario() -> dict:
    """
    Reproduce the 'agents deleted a user database' scenario.

    An agent with high capability but low grounding on db_migration
    tasks accumulates biased patterns, producing high Q_obs but
    catastrophic H_sys.
    """
    config = SimulationConfig(
        n_steps=50,
        alpha_b=0.25,    # higher bias transition rate
        delta=0.02,       # slow decay
        confirmation_rate=0.1,  # low confirmation (no proper testing)
        seed=42,
    )

    sim = OIDSimulation(config)

    # Agent: capable but not grounded in production ops
    agent = sim.make_agent("reckless_agent", capability=0.9, mastery=0.85)

    # Task: database migration — irreversible, high impact
    tasks = [
        TaskDescriptor("db_migration", mu=0.1, psi=8.0, n_min=10.0, exposure_weight=1.0),
    ]

    trajectory = sim.run_trajectory(agent, tasks)

    # Find the "disaster point": when V_net goes negative
    disaster_t = None
    for tp in trajectory:
        if tp.score.v_net < 0 and disaster_t is None:
            disaster_t = tp.T

    return {
        "trajectory": trajectory,
        "disaster_timestep": disaster_t,
        "final_score": trajectory[-1].score if trajectory else None,
    }
