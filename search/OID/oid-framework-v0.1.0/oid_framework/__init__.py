"""
OID Framework — Operational Integrity Dynamics for Autonomous AI Agents
========================================================================

A formal model of competence degradation and systemic harm in autonomous
AI agents, adapted from the V4.2 professional-competence model
(Abadie, 2026).

Core concepts:
    - ActionPattern: a learned heuristic with state {H, C+, E, B}
    - OperationalEpisode: a non-trivial adaptation event
    - DependencyDAG: constitutive/supportive action dependencies
    - IntegrityScorer: computes Q_obs, V_IA, H_sys, V_net

License: MIT
"""

__version__ = "0.1.0"
__author__ = "Yann Abadie"

from .core import (
    PatternState,
    ActionPattern,
    OperationalEpisode,
    AgentProfile,
    TaskDescriptor,
)
from .dynamics import IntegrityDynamics
from .scorer import IntegrityScorer
from .simulation import OIDSimulation
