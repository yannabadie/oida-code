"""Generate targeted repair prompts from a red/yellow verdict. Phase 3."""

from __future__ import annotations


def generate_repair_prompts(report: object) -> list[str]:  # pragma: no cover - phase 3
    raise NotImplementedError("llm.repair_prompts: blueprint §9 repair.next_prompts.")


__all__ = ["generate_repair_prompts"]
