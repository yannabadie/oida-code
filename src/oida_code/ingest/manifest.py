"""Detect project manifests and derive verification commands.

Phase 1 scope: look at ``pyproject.toml`` (TOML), ``setup.cfg`` (INI),
and a handful of well-known marker files. Python-only. The detector never
raises on malformed TOML/INI — it falls back to
:func:`default_python_commands` defaults for anything it can't read.
"""

from __future__ import annotations

import configparser
import contextlib
import tomllib
from pathlib import Path
from typing import Any

from oida_code.models.audit_request import CommandsSpec


def default_python_commands() -> CommandsSpec:
    """Stock Python verification commands for v0 (blueprint §4)."""
    return CommandsSpec(
        lint="ruff check .",
        types="mypy .",
        tests="pytest -q",
    )


def _read_pyproject(repo_path: Path) -> dict[str, Any]:
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    try:
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _read_setup_cfg(repo_path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    setup_cfg = repo_path / "setup.cfg"
    if not setup_cfg.is_file():
        return parser
    with contextlib.suppress(OSError, configparser.Error):
        parser.read(setup_cfg, encoding="utf-8")
    return parser


def _has_tool_section(pyproject: dict[str, Any], name: str) -> bool:
    tool = pyproject.get("tool")
    return isinstance(tool, dict) and name in tool


def _detect_lint(
    pyproject: dict[str, Any],
    setup_cfg: configparser.ConfigParser,
    repo_path: Path,
) -> str:
    if _has_tool_section(pyproject, "ruff"):
        return "ruff check ."
    if (repo_path / ".ruff.toml").is_file() or (repo_path / "ruff.toml").is_file():
        return "ruff check ."
    if setup_cfg.has_section("flake8"):
        return "flake8 ."
    if (repo_path / ".flake8").is_file():
        return "flake8 ."
    if (repo_path / ".pylintrc").is_file():
        return "pylint $(git ls-files '*.py')"
    return "ruff check ."


def _detect_types(
    pyproject: dict[str, Any],
    setup_cfg: configparser.ConfigParser,
    repo_path: Path,
) -> str:
    if _has_tool_section(pyproject, "mypy"):
        return "mypy ."
    if (repo_path / "mypy.ini").is_file() or (repo_path / ".mypy.ini").is_file():
        return "mypy ."
    if setup_cfg.has_section("mypy"):
        return "mypy ."
    if (repo_path / "pyrightconfig.json").is_file():
        return "pyright"
    if (repo_path / "pyrefly.toml").is_file():
        return "pyrefly check"
    return "mypy ."


def _detect_tests(
    pyproject: dict[str, Any],
    setup_cfg: configparser.ConfigParser,
    repo_path: Path,
) -> str:
    if _has_tool_section(pyproject, "pytest"):
        return "pytest -q"
    if (repo_path / "pytest.ini").is_file() or (repo_path / "conftest.py").is_file():
        return "pytest -q"
    if setup_cfg.has_section("tool:pytest"):
        return "pytest -q"
    if (repo_path / "tox.ini").is_file():
        return "pytest -q"
    for candidate in ("tests", "test"):
        if (repo_path / candidate).is_dir():
            return "pytest -q"
    return "pytest -q"


def detect_commands(repo_path: Path | str) -> CommandsSpec:
    """Auto-detect verification commands from ``repo_path``.

    Defaults to Python tooling (``ruff`` / ``mypy`` / ``pytest``) unless a
    marker file indicates otherwise. Never raises on unreadable manifests.
    """
    root = Path(repo_path)
    pyproject = _read_pyproject(root)
    setup_cfg = _read_setup_cfg(root)
    return CommandsSpec(
        lint=_detect_lint(pyproject, setup_cfg, root),
        types=_detect_types(pyproject, setup_cfg, root),
        tests=_detect_tests(pyproject, setup_cfg, root),
    )


__all__ = ["default_python_commands", "detect_commands"]
