"""Shared pytest fixtures and path constants."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
VENDORED_EXAMPLES_DIR = (
    REPO_ROOT / "search" / "OIDA" / "oida_framework" / "examples"
)


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    return EXAMPLES_DIR


@pytest.fixture(scope="session")
def vendored_examples_dir() -> Path:
    return VENDORED_EXAMPLES_DIR
