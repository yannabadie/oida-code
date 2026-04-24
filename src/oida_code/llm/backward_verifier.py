"""Backward verifier: outcome → missing premises? (AgentV-RL style). Phase 3."""

from __future__ import annotations


def verify_backward(context: object) -> object:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.backward_verifier: blueprint §3 Pass 3 backward.")


__all__ = ["verify_backward"]
