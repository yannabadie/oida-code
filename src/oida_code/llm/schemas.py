"""Structured-output schemas for the LLM verifier. Phase 3."""

from __future__ import annotations


def forward_verifier_schema() -> object:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.schemas.forward: blueprint §3 Pass 3.")


def backward_verifier_schema() -> object:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.schemas.backward: blueprint §3 Pass 3.")


__all__ = ["backward_verifier_schema", "forward_verifier_schema"]
