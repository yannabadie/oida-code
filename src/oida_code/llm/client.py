"""Local + remote LLM client (default: Qwen3.6-35B-A3B via llama.cpp). Phase 3."""

from __future__ import annotations


def get_client() -> object:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.client: blueprint §10 (local default Qwen3.6-35B-A3B).")


__all__ = ["get_client"]
