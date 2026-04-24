"""Tests for :mod:`oida_code.ingest.manifest`."""

from __future__ import annotations

from pathlib import Path

from oida_code.ingest.manifest import default_python_commands, detect_commands


def test_default_python_commands() -> None:
    commands = default_python_commands()
    assert commands.lint == "ruff check ."
    assert commands.types == "mypy ."
    assert commands.tests == "pytest -q"


def test_detect_empty_dir_falls_back_to_defaults(tmp_path: Path) -> None:
    commands = detect_commands(tmp_path)
    assert commands.lint == "ruff check ."
    assert commands.types == "mypy ."
    assert commands.tests == "pytest -q"


def test_detect_ruff_in_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 120\n",
        encoding="utf-8",
    )
    assert detect_commands(tmp_path).lint == "ruff check ."


def test_detect_flake8_over_ruff(tmp_path: Path) -> None:
    (tmp_path / "setup.cfg").write_text(
        "[flake8]\nmax-line-length = 100\n",
        encoding="utf-8",
    )
    assert detect_commands(tmp_path).lint == "flake8 ."


def test_detect_pyright(tmp_path: Path) -> None:
    (tmp_path / "pyrightconfig.json").write_text("{}", encoding="utf-8")
    assert detect_commands(tmp_path).types == "pyright"


def test_detect_tests_via_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert detect_commands(tmp_path).tests == "pytest -q"


def test_detect_malformed_pyproject_falls_back(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("not = [valid toml", encoding="utf-8")
    commands = detect_commands(tmp_path)
    # Should NOT crash, just return defaults.
    assert commands.lint == "ruff check ."


def test_detect_on_self_repo() -> None:
    # Sanity check on the real repo we live in.
    from tests.conftest import REPO_ROOT

    commands = detect_commands(REPO_ROOT)
    assert commands.lint == "ruff check ."
    assert commands.types == "mypy ."
    assert commands.tests == "pytest -q"
