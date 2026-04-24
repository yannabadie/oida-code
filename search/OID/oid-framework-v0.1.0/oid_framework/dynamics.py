"""
Dynamics module: state transitions, dependency DAG, and correction operators.

Implements:
    - H → B transition risk (λ_{H→B})
    - Single-loop correction (local fix)
    - Double-loop correction (propagation via dominance)
    - Dependency DAG with constitutive/supportive edges
    - Dominance relation
"""

from __future__ import annotations

import math
from typing import Optional

import networkx as nx

from .core import (
    ActionPattern,
    AgentProfile,
    PatternState,
    TaskDescriptor,
)


class DependencyDAG:
    """
    DAG of action pattern dependencies: G^D_N(T).

    Two edge types:
        - constitutive: N_i is necessary to the structure of N_j
        - supportive: N_i aided N_j without being its sole foundation

    Dominance is computed on the constitutive sub-graph only.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._super_root = "__ROOT__"
        self.graph.add_node(self._super_root)

    def add_pattern(
        self,
        pattern_id: str,
        parents: Optional[dict] = None,
    ) -> None:
        """
        Add a pattern node. parents = {parent_id: "constitutive"|"supportive"}.
        """
        self.graph.add_node(pattern_id)
        if parents:
            for pid, etype in parents.items():
                self.graph.add_edge(pid, pattern_id, edge_type=etype)
        else:
            self.graph.add_edge(self._super_root, pattern_id, edge_type="constitutive")

    def constitutive_subgraph(self) -> nx.DiGraph:
        """Extract the constitutive sub-graph G^D_c."""
        edges = [
            (u, v) for u, v, d in self.graph.edges(data=True)
            if d.get("edge_type") == "constitutive"
        ]
        G_c = nx.DiGraph()
        G_c.add_nodes_from(self.graph.nodes())
        G_c.add_edges_from(edges)
        return G_c

    def dominators(self) -> dict:
        """
        Compute immediate dominators on the constitutive sub-graph.
        dom_D(i, j) = 1 iff i dominates j in (G^D_c, r_D).
        """
        G_c = self.constitutive_subgraph()
        try:
            return nx.immediate_dominators(G_c, self._super_root)
        except nx.NetworkXError:
            return {}

    def dominated_by(self, node_id: str) -> set:
        """Return all nodes dominated by node_id (descendants via dominance)."""
        idom = self.dominators()
        dominated = set()
        for node, dom in idom.items():
            if dom == node_id and node != node_id:
                dominated.add(node)
                # Recursively find nodes dominated by this one
                dominated |= self._recursive_dominated(node, idom)
        return dominated

    def _recursive_dominated(self, node_id: str, idom: dict) -> set:
        result = set()
        for node, dom in idom.items():
            if dom == node_id and node != node_id:
                result.add(node)
                result |= self._recursive_dominated(node, idom)
        return result

    def descendants(self, node_id: str) -> set:
        """All descendants (any path) in the full graph."""
        if node_id not in self.graph:
            return set()
        return nx.descendants(self.graph, node_id)


class IntegrityDynamics:
    """
    Transition operators for action pattern states.

    Implements:
        - H → B transition risk
        - Single-loop correction
        - Double-loop correction with dominance propagation
    """

    def __init__(
        self,
        alpha_b: float = 0.15,
        delta: float = 0.05,
        tau_ref: float = 10.0,
    ):
        """
        Args:
            alpha_b: base intensity of H → B transition
            delta:   natural decay rate for H patterns
            tau_ref: temporal inertia of damage
        """
        self.alpha_b = alpha_b
        self.delta = delta
        self.tau_ref = tau_ref

    def transition_risk_h_to_b(
        self,
        pattern: ActionPattern,
        agent: AgentProfile,
        task: TaskDescriptor,
        grounding: float,
        T: int,
    ) -> float:
        """
        Compute λ_{H→B,i}(T).

        λ = α_B · S_{IA_eff} · (1 - μ(τ)) · (1 - G_D) · usage_i

        A pattern becomes biased when:
            - agent is highly capable (convincing outputs)
            - task is irreversible / opaque (low μ)
            - grounding is weak (low G_D)
            - pattern has been reused many times
        """
        if pattern.state != PatternState.H:
            return 0.0

        s_eff = agent.s_ia_eff(T)
        return (
            self.alpha_b
            * s_eff
            * (1 - task.mu)
            * (1 - grounding)
            * pattern.usage_count
        )

    def apply_decay(self, agent: AgentProfile, T: int) -> None:
        """Apply natural decay to all H-state patterns."""
        for p in agent.patterns.values():
            p.decay(T, self.delta)

    def attempt_h_to_b(
        self,
        pattern: ActionPattern,
        agent: AgentProfile,
        task: TaskDescriptor,
        grounding: float,
        T: int,
        rng=None,
    ) -> bool:
        """
        Stochastic H → B transition.
        Returns True if transition occurred.
        """
        if pattern.state != PatternState.H:
            return False
        risk = self.transition_risk_h_to_b(pattern, agent, task, grounding, T)
        prob = 1 - math.exp(-risk)
        if rng is None:
            import random
            rng = random
        if rng.random() < prob:
            pattern.state = PatternState.B
            pattern.bias_onset = T
            return True
        return False

    def single_loop_correct(self, pattern: ActionPattern) -> None:
        """
        Single-loop correction: fix a local response.
        The corrected pattern can go H → E or stay H.
        No propagation through the DAG.
        """
        if pattern.state in (PatternState.H, PatternState.B):
            pattern.state = PatternState.E
            pattern.value = 0.0

    def double_loop_correct(
        self,
        governing_id: str,
        agent: AgentProfile,
        dag: DependencyDAG,
    ) -> dict:
        """
        Double-loop correction on a governing node.

        1. Eliminate the governing pattern.
        2. Dominated descendants: reopen to H, set audit_flag.
        3. Non-dominated descendants: set audit_flag only.

        Returns: dict of {pattern_id: action_taken}
        """
        result = {}
        gov = agent.patterns.get(governing_id)
        if gov is None:
            return result

        # Step 1: eliminate the governing pattern
        gov.state = PatternState.E
        gov.value = 0.0
        result[governing_id] = "eliminated"

        # Step 2: find dominated descendants
        dominated = dag.dominated_by(governing_id)
        all_desc = dag.descendants(governing_id)
        non_dominated = all_desc - dominated - {governing_id}

        for pid in dominated:
            p = agent.patterns.get(pid)
            if p is not None:
                p.state = PatternState.H
                p.audit_flag = 1
                result[pid] = "reopened_and_flagged"

        for pid in non_dominated:
            p = agent.patterns.get(pid)
            if p is not None:
                p.audit_flag = 1
                result[pid] = "flagged_for_review"

        return result

    def grounding(
        self,
        agent: AgentProfile,
        task: TaskDescriptor,
        T: int,
        adjacent_contribution: float = 0.0,
        s_d: float = 5.0,
    ) -> float:
        """
        Compute operational grounding G_D(I, τ, T).

        G_D = σ((N_eff + adj - N_min(τ)) / s_D)

        Grounding = proportion of environment the agent has
        verified by direct observation (not inference).
        """
        n_eff = agent.n_eff(T)
        z = (n_eff + adjacent_contribution - task.n_min) / s_d
        return 1.0 / (1.0 + math.exp(-z))
