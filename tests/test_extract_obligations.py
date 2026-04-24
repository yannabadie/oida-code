"""Tests for :mod:`oida_code.extract.obligations` (Phase 2)."""

from __future__ import annotations

from pathlib import Path

from oida_code.extract.obligations import extract_obligations


def test_assert_becomes_precondition(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text(
        "def f(x):\n"
        "    assert x > 0, 'x must be positive'\n"
        "    return x * 2\n",
        encoding="utf-8",
    )
    obs = extract_obligations(tmp_path, ["mod.py"])
    assert len(obs) == 1
    assert obs[0].kind == "precondition"
    assert obs[0].scope == "mod.py::f"


def test_if_not_raise_guard_becomes_precondition(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text(
        "def f(x):\n"
        "    if x < 0:\n"
        "        raise ValueError('bad x')\n"
        "    return x\n",
        encoding="utf-8",
    )
    obs = extract_obligations(tmp_path, ["mod.py"])
    kinds = [o.kind for o in obs]
    assert "precondition" in kinds


def test_route_decorator_becomes_api_contract(tmp_path: Path) -> None:
    src = tmp_path / "app.py"
    src.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/items')\n"
        "def list_items():\n"
        "    return []\n",
        encoding="utf-8",
    )
    obs = extract_obligations(tmp_path, ["app.py"])
    api_obs = [o for o in obs if o.kind == "api_contract"]
    assert len(api_obs) == 1
    assert api_obs[0].scope == "app.py::list_items"


def test_field_validator_becomes_precondition(tmp_path: Path) -> None:
    src = tmp_path / "schemas.py"
    src.write_text(
        "from pydantic import BaseModel, field_validator\n"
        "class S(BaseModel):\n"
        "    x: int\n"
        "    @field_validator('x')\n"
        "    @classmethod\n"
        "    def check_x(cls, v):\n"
        "        return v\n",
        encoding="utf-8",
    )
    obs = extract_obligations(tmp_path, ["schemas.py"])
    pre = [o for o in obs if o.kind == "precondition"]
    assert any("check_x" in o.scope for o in pre)


def test_migration_path_becomes_migration_obligation(tmp_path: Path) -> None:
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "001_init.sql").write_text("-- noop", encoding="utf-8")
    obs = extract_obligations(tmp_path, ["migrations/001_init.sql"])
    assert len(obs) == 1
    assert obs[0].kind == "migration"


def test_non_python_non_migration_files_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    assert extract_obligations(tmp_path, ["README.md"]) == []


def test_syntax_error_yields_empty_without_crashing(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def f(: broken\n", encoding="utf-8")
    assert extract_obligations(tmp_path, ["broken.py"]) == []


def test_missing_file_is_skipped(tmp_path: Path) -> None:
    assert extract_obligations(tmp_path, ["does_not_exist.py"]) == []


def test_extraction_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text(
        "def f(x):\n"
        "    assert x > 0\n"
        "    if x > 100:\n"
        "        raise ValueError()\n",
        encoding="utf-8",
    )
    first = extract_obligations(tmp_path, ["mod.py"])
    second = extract_obligations(tmp_path, ["mod.py"])
    assert [o.id for o in first] == [o.id for o in second]


def test_obligation_ids_conform_to_regex(tmp_path: Path) -> None:
    import re

    (tmp_path / "mod.py").write_text(
        "def f(x):\n    assert x > 0\n", encoding="utf-8"
    )
    pattern = re.compile(r"^o-[0-9A-Za-z_-]+$")
    for ob in extract_obligations(tmp_path, ["mod.py"]):
        assert pattern.match(ob.id), ob.id
