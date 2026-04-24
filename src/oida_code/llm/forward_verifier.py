"""Forward verifier: premises → sufficient? (AgentV-RL style). Phase 3."""

from __future__ import annotations


def verify_forward(context: object) -> object:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.forward_verifier: blueprint §3 Pass 3 forward.")


__all__ = ["verify_forward"]
