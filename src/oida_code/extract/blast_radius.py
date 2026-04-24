"""Estimate blast radius from module fan-out + data-layer criticality. Phase 2."""

from __future__ import annotations


def estimate_blast_radius(request: object) -> float:  # pragma: no cover - phase 2
    raise NotImplementedError("extract.blast_radius: blueprint §6 blast radius.")


__all__ = ["estimate_blast_radius"]
