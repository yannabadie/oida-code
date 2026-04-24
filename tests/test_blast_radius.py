"""Tests for :mod:`oida_code.extract.blast_radius`."""

from __future__ import annotations

import pytest

from oida_code.extract.blast_radius import estimate_blast_radius


def test_empty_diff_is_zero() -> None:
    assert estimate_blast_radius([]) == 0.0


def test_small_pure_code_change_is_low() -> None:
    score = estimate_blast_radius(["src/utils/helpers.py"])
    assert 0.0 < score < 0.2


def test_api_path_bumps_score() -> None:
    api = estimate_blast_radius(["src/api/signup.py"])
    non_api = estimate_blast_radius(["src/utils/helpers.py"])
    assert api > non_api


def test_migration_dominates() -> None:
    migration = estimate_blast_radius(["migrations/0001_init.sql"])
    pure_code = estimate_blast_radius(["src/utils/helpers.py"])
    assert migration > pure_code + 0.1


def test_infra_change_is_significant() -> None:
    score = estimate_blast_radius([".github/workflows/deploy.yml"])
    assert score >= 0.15


def test_score_is_bounded() -> None:
    # Pile on everything → must stay ≤ 1.0.
    score = estimate_blast_radius(
        [f"migrations/{i:04d}.sql" for i in range(20)]
        + [f".github/workflows/deploy-{i}.yml" for i in range(10)]
        + [f"src/api/{i}.py" for i in range(10)]
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.parametrize(
    "path,expected_min",
    [
        ("migrations/0001_add_user.sql", 0.15),
        ("src/models/user.py", 0.15),
        ("Dockerfile", 0.15),
        (".github/workflows/ci.yml", 0.15),
    ],
)
def test_high_risk_paths_above_threshold(path: str, expected_min: float) -> None:
    assert estimate_blast_radius([path]) >= expected_min
