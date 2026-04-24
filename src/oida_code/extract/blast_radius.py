"""Minimal blast-radius heuristic (blueprint §6, Phase 1).

Real dependency fan-out (call graphs, import closures) is a Phase 2 concern;
this module only uses changed-path signals. Output is ``float`` in ``[0, 1]``.

Four weighted signals, transparent and calibratable:

* ``modules_signal``   — breadth of the change across distinct top-level modules.
* ``api_signal``       — fraction of changes touching public API surfaces.
* ``data_signal``      — presence of data-layer / migration markers.
* ``infra_signal``     — presence of infrastructure / CI markers.

The weights match the advisor note: data + infra weighted highest because
those are the cases where corrupt_success costs the most.
"""

from __future__ import annotations

import math
import re
from pathlib import PurePosixPath

_DATA_MARKERS = (
    re.compile(r"(^|/)migrations?($|/)"),
    re.compile(r"\.sql$"),
    re.compile(r"(^|/)schema($|/|\.)"),
    re.compile(r"(^|/)alembic($|/)"),
    re.compile(r"(^|/)models?($|/)"),
    re.compile(r"(^|/)db($|/)"),
)
_INFRA_MARKERS = (
    re.compile(r"^dockerfile", re.IGNORECASE),
    re.compile(r"^docker-compose", re.IGNORECASE),
    re.compile(r"^\.github/workflows/"),
    re.compile(r"(^|/)terraform($|/)"),
    re.compile(r"(^|/)helm($|/)"),
    re.compile(r"(^|/)k8s($|/)|(^|/)kubernetes($|/)"),
    re.compile(r"(^|/)pulumi($|/)"),
)
_API_MARKERS = (
    re.compile(r"(^|/)api($|/)"),
    re.compile(r"(^|/)routes?($|/)"),
    re.compile(r"(^|/)endpoints?($|/)"),
    re.compile(r"(^|/)public($|/)"),
    re.compile(r"(^|/)__init__\.py$"),
)
_CONFIG_MARKERS = (
    re.compile(r"(^|/)settings\.py$"),
    re.compile(r"(^|/)config\.(py|toml|yaml|yml|json)$"),
    re.compile(r"(^|/)\.env($|\.)"),
)


def _top_module(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts:
        return ""
    return parts[0]


def _count_matches(path: str, markers: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in markers if pattern.search(path))


def _modules_signal(changed_files: list[str]) -> float:
    if not changed_files:
        return 0.0
    modules = {_top_module(p) for p in changed_files if p}
    # 1 module ≈ 0.35; 3 ≈ 0.68; 5 ≈ 0.83; 10+ saturates near 0.95.
    return 1.0 - math.exp(-0.35 * len(modules))


def _api_signal(changed_files: list[str]) -> float:
    if not changed_files:
        return 0.0
    hits = sum(1 for p in changed_files if _count_matches(p, _API_MARKERS) > 0)
    return min(1.0, hits / max(1, len(changed_files)))


def _data_signal(changed_files: list[str]) -> float:
    if not changed_files:
        return 0.0
    matched = sum(1 for p in changed_files if _count_matches(p, _DATA_MARKERS) > 0)
    if matched == 0:
        return 0.0
    # Any single data-layer hit is already serious; saturate quickly.
    return min(1.0, 0.5 + 0.15 * (matched - 1))


def _infra_signal(changed_files: list[str]) -> float:
    if not changed_files:
        return 0.0
    matched = sum(1 for p in changed_files if _count_matches(p, _INFRA_MARKERS) > 0)
    config_hits = sum(1 for p in changed_files if _count_matches(p, _CONFIG_MARKERS) > 0)
    score = 0.0
    if matched:
        score = max(score, 0.6 + 0.1 * (matched - 1))
    if config_hits:
        score = max(score, 0.3 + 0.1 * (config_hits - 1))
    return min(1.0, score)


def estimate_blast_radius(changed_files: list[str]) -> float:
    """Return a calibratable blast-radius score in ``[0, 1]`` from the diff.

    Weights (sum = 1.0): modules 0.20, api 0.20, data 0.35, infra 0.25.
    The data + infra axes dominate because they match the OIDA paper's
    motivating incidents (Replit DB wipe, Kiro delete-and-recreate).
    """
    if not changed_files:
        return 0.0
    score = (
        0.20 * _modules_signal(changed_files)
        + 0.20 * _api_signal(changed_files)
        + 0.35 * _data_signal(changed_files)
        + 0.25 * _infra_signal(changed_files)
    )
    return max(0.0, min(1.0, score))


__all__ = ["estimate_blast_radius"]
