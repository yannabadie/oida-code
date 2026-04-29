"""Phase 6.1'g (ADR-61) — clone helper extras + groups tests.

Phase 6.1'f closed the "package not importable" bootstrap class
via install-order flip + ``--import-smoke``. Phase 6.1'g closes
the second-order class — non-pytest targets where pytest lives
behind an extras/group declaration:

* ``--install-extras EXTRAS`` (PEP 621) — append-style flag
  that turns the target install into
  ``pip install -e <clone>[EXTRAS]``.
* ``--install-group GROUP`` (PEP 735) — append-style flag that
  runs ``pip install --group <pyproject>:GROUP`` after the
  editable install.
* Whenever EITHER extras OR groups are requested, an
  auto-pytest-smoke runs after all installs. Failure yields a
  clear ``target_bootstrap_gap`` banner naming pytest.

These tests are hermetic — no real ``pip``, ``git``, or
external network. The script's internal functions are imported
and exercised under ``monkeypatch``.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = (
    _REPO_ROOT / "scripts" / "clone_target_at_sha.py"
)


def _import_clone_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_clone_target_at_sha_for_g", _SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pip_install_editable_extras_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_pip_install_editable(extras=("test","docs"))``
    constructs `<src>[test,docs]` as the pip argument."""
    mod = _import_clone_module()
    captured: list[list[str]] = []

    class _OkResult:
        returncode = 0
        stderr = ""

    def fake_run(
        argv: list[str],
        env: dict[str, str] | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> _OkResult:
        captured.append(argv)
        return _OkResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    venv_py = Path("/fake/venv/python")
    src = Path("/fake/clone")
    mod._pip_install_editable(
        venv_py, src, "fake/repo", extras=("test", "docs"),
    )
    assert len(captured) == 1
    argv = captured[0]
    assert argv[-1] == f"{src}[test,docs]", (
        "extras must be appended in `[a,b]` syntax to the path "
        f"argument; got {argv[-1]!r}"
    )


def test_pip_install_editable_no_extras_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without extras, the path argument is the bare path."""
    mod = _import_clone_module()
    captured: list[list[str]] = []

    class _OkResult:
        returncode = 0
        stderr = ""

    def fake_run(
        argv: list[str],
        env: dict[str, str] | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> _OkResult:
        captured.append(argv)
        return _OkResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    venv_py = Path("/fake/venv/python")
    src = Path("/fake/clone")
    mod._pip_install_editable(venv_py, src, "fake/repo")
    assert captured[0][-1] == str(src)


def test_pip_install_groups_per_group_invocation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``_pip_install_groups(groups=("a","b"))`` invokes pip
    once per group, each as
    ``pip install --group <pyproject>:<group>``."""
    mod = _import_clone_module()
    target = tmp_path / "target"
    target.mkdir()
    (target / "pyproject.toml").write_text("# placeholder\n")

    captured: list[list[str]] = []

    class _OkResult:
        returncode = 0
        stderr = ""

    def fake_run(
        argv: list[str],
        env: dict[str, str] | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> _OkResult:
        captured.append(argv)
        return _OkResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    venv_py = Path("/fake/venv/python")
    mod._pip_install_groups(
        venv_py, target, ("tests", "typing"),
    )
    assert len(captured) == 2
    assert captured[0][1:5] == [
        "-m", "pip", "install", "--group",
    ]
    assert captured[0][5].endswith(":tests")
    assert captured[1][5].endswith(":typing")


def test_pytest_version_smoke_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Smoke succeeds when pytest --version exits 0."""
    mod = _import_clone_module()

    class _OkResult:
        returncode = 0
        stdout = "pytest 9.0.3\n"
        stderr = ""

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, check=False, capture_output=False, text=False:
            _OkResult(),
    )
    mod._pytest_version_smoke(Path("/fake/venv/python"))
    err = capsys.readouterr().err
    assert "pytest 9.0.3" in err
    assert "target_bootstrap_gap" not in err


def test_pytest_version_smoke_failure_banner(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Smoke failure raises SystemExit(2) and emits a
    ``target_bootstrap_gap`` banner naming pytest."""
    mod = _import_clone_module()

    class _FailResult:
        returncode = 1
        stdout = ""
        stderr = "No module named pytest\n"

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, check=False, capture_output=False, text=False:
            _FailResult(),
    )
    with pytest.raises(SystemExit) as exc_info:
        mod._pytest_version_smoke(Path("/fake/venv/python"))
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "target_bootstrap_gap" in err
    assert "pytest" in err.lower()


def test_main_runs_pytest_smoke_when_extras_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """main() with --install-extras MUST trigger
    _pytest_version_smoke after the install."""
    mod = _import_clone_module()
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )
    monkeypatch.setattr(
        mod, "_pip_install_editable",
        lambda venv_python, src_dir, label, extra_env=None,
        extras=(): None,
    )
    monkeypatch.setattr(
        mod, "_pip_install_groups",
        lambda venv_python, target_dir, groups, extra_env=None: None,
    )
    smoke_count = {"n": 0}
    monkeypatch.setattr(
        mod, "_pytest_version_smoke",
        lambda venv_python: smoke_count.__setitem__(
            "n", smoke_count["n"] + 1,
        ),
    )
    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--install-extras", "test",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert smoke_count["n"] == 1, (
        "extras-install MUST trigger pytest smoke once"
    )


def test_main_runs_pytest_smoke_when_groups_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """main() with --install-group also triggers pytest smoke."""
    mod = _import_clone_module()
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )
    monkeypatch.setattr(
        mod, "_pip_install_editable",
        lambda venv_python, src_dir, label, extra_env=None,
        extras=(): None,
    )
    group_calls: list[tuple[str, ...]] = []

    def fake_groups(
        venv_python: Path,
        target_dir: Path,
        groups: tuple[str, ...],
        extra_env: dict[str, str] | None = None,
    ) -> None:
        group_calls.append(groups)

    monkeypatch.setattr(
        mod, "_pip_install_groups", fake_groups,
    )
    smoke_count = {"n": 0}
    monkeypatch.setattr(
        mod, "_pytest_version_smoke",
        lambda venv_python: smoke_count.__setitem__(
            "n", smoke_count["n"] + 1,
        ),
    )
    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--install-group", "tests",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert group_calls == [("tests",)]
    assert smoke_count["n"] == 1


def test_main_no_pytest_smoke_when_neither_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Backward compat: no extras AND no groups → no pytest
    smoke (pytest may legitimately not be expected)."""
    mod = _import_clone_module()
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )
    monkeypatch.setattr(
        mod, "_pip_install_editable",
        lambda venv_python, src_dir, label, extra_env=None,
        extras=(): None,
    )
    monkeypatch.setattr(
        mod, "_pip_install_groups",
        lambda venv_python, target_dir, groups, extra_env=None: None,
    )
    smoke_count = {"n": 0}
    monkeypatch.setattr(
        mod, "_pytest_version_smoke",
        lambda venv_python: smoke_count.__setitem__(
            "n", smoke_count["n"] + 1,
        ),
    )
    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert smoke_count["n"] == 0


def test_main_passes_extras_through_to_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end: --install-extras X --install-extras Y →
    _pip_install_editable receives extras=("X","Y")."""
    mod = _import_clone_module()
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )
    monkeypatch.setattr(
        mod, "_pip_install_groups",
        lambda venv_python, target_dir, groups, extra_env=None: None,
    )
    monkeypatch.setattr(
        mod, "_pytest_version_smoke",
        lambda venv_python: None,
    )
    capture: list[tuple[str, ...]] = []

    def fake_install(
        venv_python: Path,
        src_dir: Path,
        label: str,
        extra_env: dict[str, str] | None = None,
        extras: tuple[str, ...] = (),
    ) -> None:
        capture.append(extras)

    monkeypatch.setattr(
        mod, "_pip_install_editable", fake_install,
    )
    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--install-extras", "test",
            "--install-extras", "docs",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert capture == [("test", "docs")]
