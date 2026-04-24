from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

import networkx as nx

from .models import Event, Scenario


@dataclass(slots=True)
class PatternLedger:
    pattern_id: str
    state: str = "H"
    value: float = 0.0
    reuse_count: int = 0
    damage: float = 0.0
    b_age: int = 0


@dataclass(slots=True)
class AnalyzerConfig:
    alpha_b: float = 1.15
    confirm_threshold: float = 0.80
    bias_threshold: float = 0.45
    tau_ref: float = 3.0
    weight_completion: float = 0.40
    weight_tests: float = 0.40
    weight_accept: float = 0.20
    corrupt_success_q_threshold: float = 0.80

    @staticmethod
    def from_scenario(scenario: Scenario) -> "AnalyzerConfig":
        cfg = AnalyzerConfig()
        for key, value in scenario.config.items():
            if hasattr(cfg, key):
                setattr(cfg, key, float(value))
        return cfg


class OIDAAnalyzer:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.config = AnalyzerConfig.from_scenario(scenario)
        self.patterns: Dict[str, PatternLedger] = {}
        self.event_results: List[Dict[str, Any]] = []
        self.g_constitutive = nx.DiGraph()
        self.g_supportive = nx.DiGraph()
        self._validated_ids = False

    def _validate_ids(self) -> None:
        if self._validated_ids:
            return
        known_ids = {event.id for event in self.scenario.events}
        if len(known_ids) != len(self.scenario.events):
            raise ValueError("Event IDs must be unique.")
        for event in self.scenario.events:
            for parent in event.constitutive_parents + event.supportive_parents:
                if parent not in known_ids:
                    raise ValueError(f"Unknown parent '{parent}' referenced by event '{event.id}'.")
        self._validated_ids = True

    def grounding(self, event: Event) -> float:
        total_weight = sum(item.weight for item in event.preconditions)
        if total_weight <= 0:
            return 0.0
        verified = sum(item.weight for item in event.preconditions if item.verified)
        return verified / total_weight

    def q_obs(self, event: Event) -> float:
        c = self.config
        return (
            c.weight_completion * event.completion
            + c.weight_tests * event.tests_pass
            + c.weight_accept * event.operator_accept
        )

    def mu(self, event: Event) -> float:
        return math.sqrt(max(0.0, event.reversibility) * max(0.0, event.observability))

    @staticmethod
    def _reuse_norm(count: int) -> float:
        return min(1.0, math.log1p(count) / math.log(6.0))

    def lambda_bias(self, event: Event, reuse_count: int) -> float:
        g = self.grounding(event)
        q = self.q_obs(event)
        m = self.mu(event)
        value = (
            self.config.alpha_b
            * event.capability
            * (1.0 - m)
            * (1.0 - g)
            * (0.5 + 0.5 * self._reuse_norm(reuse_count))
            * q
        )
        return min(1.5, value)

    def _next_pattern_state(self, event: Event, ledger: PatternLedger, g: float, q: float, lam: float) -> None:
        if event.invalidates_pattern:
            ledger.state = "E"
            ledger.value = 0.0
            return

        if g >= self.config.confirm_threshold and q >= 0.60:
            ledger.state = "C+"
            ledger.value = max(1.0, q * g)
            return

        if lam >= self.config.bias_threshold and g < 0.60 and q >= 0.70:
            ledger.state = "B"
            ledger.value = -(q - g)
            ledger.b_age += 1
            return

        ledger.state = "H"
        ledger.value = max(0.05, q * g * (1.0 - math.exp(-ledger.reuse_count / 3.0)))

    def _update_damage(self, event: Event, ledger: PatternLedger) -> None:
        if ledger.state != "B":
            return
        incremental = (
            abs(ledger.value)
            * (1.0 + ledger.reuse_count)
            * math.log1p(1.0 + ledger.b_age / self.config.tau_ref)
            * event.blast_radius
            * (1.0 - event.reversibility)
        )
        ledger.damage += incremental

    def _n_stock(self) -> float:
        confirmed = sum(1.0 for ledger in self.patterns.values() if ledger.state == "C+")
        active = sum(ledger.value for ledger in self.patterns.values() if ledger.state == "H")
        return confirmed + active

    def _b_load(self) -> float:
        return sum(ledger.damage for ledger in self.patterns.values())

    def _pattern_snapshot(self) -> Dict[str, Dict[str, float | int | str]]:
        snapshot: Dict[str, Dict[str, float | int | str]] = {}
        for pattern_id, ledger in sorted(self.patterns.items()):
            snapshot[pattern_id] = {
                "state": ledger.state,
                "value": round(ledger.value, 6),
                "reuse_count": ledger.reuse_count,
                "damage": round(ledger.damage, 6),
                "b_age": ledger.b_age,
            }
        return snapshot

    def analyze(self) -> Dict[str, Any]:
        self._validate_ids()
        self.patterns.clear()
        self.event_results.clear()
        self.g_constitutive.clear()
        self.g_supportive.clear()

        for tick, event in enumerate(self.scenario.events, start=1):
            self.g_constitutive.add_node(event.id)
            self.g_supportive.add_node(event.id)
            for parent in event.constitutive_parents:
                self.g_constitutive.add_edge(parent, event.id)
            for parent in event.supportive_parents:
                self.g_supportive.add_edge(parent, event.id)

            ledger = self.patterns.setdefault(event.pattern_id, PatternLedger(pattern_id=event.pattern_id))
            ledger.reuse_count += 1

            g = self.grounding(event)
            q = self.q_obs(event)
            m = self.mu(event)
            lam = self.lambda_bias(event, ledger.reuse_count)

            self._next_pattern_state(event, ledger, g, q, lam)
            self._update_damage(event, ledger)

            n_stock = self._n_stock()
            b_load = self._b_load()
            n_eff = n_stock - b_load
            debt = max(0.0, -n_eff)
            debt_norm = 1.0 - math.exp(-debt) if debt > 0 else 0.0
            b_tilde = 1.0 - math.exp(-(b_load + max(0.0, lam if ledger.state == "B" else 0.0)))

            v_dur = event.benefit * g * (1.0 + m * event.capability) * (1.0 - debt_norm)
            h_sys = event.blast_radius * (1.0 - m) * event.capability * b_tilde * q
            v_net = v_dur - h_sys
            corrupt_success = q >= self.config.corrupt_success_q_threshold and v_net < 0.0

            self.event_results.append(
                {
                    "tick": tick,
                    "event": event.id,
                    "task": event.task,
                    "pattern": event.pattern_id,
                    "grounding": round(g, 6),
                    "q_obs": round(q, 6),
                    "mu": round(m, 6),
                    "lambda_bias": round(lam, 6),
                    "pattern_state": ledger.state,
                    "n_stock": round(n_stock, 6),
                    "b_load": round(b_load, 6),
                    "n_eff": round(n_eff, 6),
                    "debt": round(debt, 6),
                    "v_dur": round(v_dur, 6),
                    "h_sys": round(h_sys, 6),
                    "v_net": round(v_net, 6),
                    "corrupt_success": corrupt_success,
                }
            )

        report = {
            "scenario": self.scenario.name,
            "description": self.scenario.description,
            "config": {
                "alpha_b": self.config.alpha_b,
                "confirm_threshold": self.config.confirm_threshold,
                "bias_threshold": self.config.bias_threshold,
                "tau_ref": self.config.tau_ref,
                "weight_completion": self.config.weight_completion,
                "weight_tests": self.config.weight_tests,
                "weight_accept": self.config.weight_accept,
                "corrupt_success_q_threshold": self.config.corrupt_success_q_threshold,
            },
            "summary": self.summary(),
            "patterns": self._pattern_snapshot(),
            "events": self.event_results,
        }
        return report

    def summary(self) -> Dict[str, Any]:
        if not self.event_results:
            return {
                "event_count": 0,
                "mean_q_obs": 0.0,
                "mean_grounding": 0.0,
                "total_v_net": 0.0,
                "max_h_sys": 0.0,
                "debt_final": 0.0,
                "corrupt_success_ratio": 0.0,
                "bias_pattern_count": 0,
                "bias_patterns": [],
            }

        mean_q_obs = sum(item["q_obs"] for item in self.event_results) / len(self.event_results)
        mean_grounding = sum(item["grounding"] for item in self.event_results) / len(self.event_results)
        total_v_net = sum(item["v_net"] for item in self.event_results)
        max_h_sys = max(item["h_sys"] for item in self.event_results)
        debt_final = self.event_results[-1]["debt"]
        corrupt_success_ratio = (
            sum(1 for item in self.event_results if item["corrupt_success"]) / len(self.event_results)
        )
        bias_patterns = sorted(
            pattern_id for pattern_id, ledger in self.patterns.items() if ledger.state == "B"
        )

        return {
            "event_count": len(self.event_results),
            "mean_q_obs": round(mean_q_obs, 6),
            "mean_grounding": round(mean_grounding, 6),
            "total_v_net": round(total_v_net, 6),
            "max_h_sys": round(max_h_sys, 6),
            "debt_final": round(debt_final, 6),
            "corrupt_success_ratio": round(corrupt_success_ratio, 6),
            "bias_pattern_count": len(bias_patterns),
            "bias_patterns": bias_patterns,
        }

    def double_loop_repair(self, root_event_id: str) -> Dict[str, Any]:
        self._validate_ids()
        if root_event_id not in self.g_constitutive and root_event_id not in {e.id for e in self.scenario.events}:
            raise KeyError(f"Unknown root_event_id '{root_event_id}'.")

        # Ensure graphs are populated even if analyze() was not called.
        if self.g_constitutive.number_of_nodes() == 0 and self.g_supportive.number_of_nodes() == 0:
            self.analyze()

        g_c = self.g_constitutive.copy()
        g_all = nx.compose(self.g_constitutive, self.g_supportive)
        synthetic_root = "__root__"
        g_c.add_node(synthetic_root)

        for node in list(g_c.nodes()):
            if node == synthetic_root:
                continue
            if g_c.in_degree(node) == 0:
                g_c.add_edge(synthetic_root, node)

        immediate = nx.algorithms.dominance.immediate_dominators(g_c, synthetic_root)

        dominated_descendants: List[str] = []
        for node in g_c.nodes():
            if node in {synthetic_root, root_event_id}:
                continue
            cursor = node
            while cursor != synthetic_root:
                if cursor == root_event_id:
                    dominated_descendants.append(node)
                    break
                cursor = immediate[cursor]

        all_descendants = nx.descendants(g_all, root_event_id)
        audit_only = sorted(all_descendants - set(dominated_descendants))

        return {
            "root_event": root_event_id,
            "reopen": sorted(dominated_descendants),
            "audit": audit_only,
        }
