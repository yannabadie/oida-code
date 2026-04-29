"""Phase 6.1'f (ADR-60) — clone helper bootstrap fix tests.

Phase 6.1'e step 4 surfaced `target_bootstrap_gap` for both
holdouts (seed_065 sqlite-utils + seed_157 structlog): the
target package was not importable from the clone-venv at
pytest time despite ``pip install -e <clone>`` reporting
success. Per cgpro QA/A45 follow-up step_4_recommendation +
verdict_q3 (minimal_first), Phase 6.1'f delivers two changes:

1. **Install order:** when ``--install-oida-code`` is set, the
   local oida-code package is installed FIRST and the cloned
   target is installed editable LAST.
2. **`--import-smoke PACKAGE`** (repeatable): after all
   installs, ``<venv>/python -c "import PACKAGE"`` is run for
   each smoke value; failure is `target_bootstrap_gap` with a
   clear banner.

These tests are hermetic — no real `git`, `pip`, or
`subprocess` against an external repo. The script's internal
functions are imported and exercised under `monkeypatch`.
"""

from __future__ import annotations

import importlib.util
import re
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
    """Import ``scripts/clone_target_at_sha.py`` as a module
    so its private functions are exercisable in tests. The
    script is intentionally not a package, so we use
    importlib's spec-from-file approach."""
    spec = importlib.util.spec_from_file_location(
        "_clone_target_at_sha_for_tests", _SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_clone_module_carries_egress_marker() -> None:
    """ADR-53: the script MUST carry MANUAL_EGRESS_SCRIPT=True."""
    mod = _import_clone_module()
    assert getattr(mod, "MANUAL_EGRESS_SCRIPT", False) is True


def test_install_order_oida_code_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 6.1'f core invariant: when --install-oida-code is
    set, the local oida-code package is installed BEFORE the
    target. Captures the order of _pip_install_editable calls
    via a monkeypatched recorder.
    """
    mod = _import_clone_module()

    # Stub git fetch + venv creation so we don't hit the
    # network or actually create a venv.
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )

    calls: list[tuple[str, Path]] = []

    def recorder(
        venv_python: Path,
        src_dir: Path,
        label: str,
        extra_env: dict[str, str] | None = None,
        extras: tuple[str, ...] = (),
    ) -> None:
        calls.append((label, src_dir))

    monkeypatch.setattr(
        mod, "_pip_install_editable", recorder,
    )
    # No import-smoke — keep the test focused on order.
    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--install-oida-code",
            "--clones-dir", str(tmp_path),
        ],
    )

    rc = mod.main()
    assert rc == 0, "main() should exit 0 on the happy path"
    assert len(calls) == 2, (
        "expected 2 install calls (oida-code + target); "
        f"got {len(calls)}: {calls}"
    )
    first_label, _ = calls[0]
    second_label, _ = calls[1]
    assert "oida-code" in first_label.lower(), (
        "Phase 6.1'f: oida-code MUST be installed first when "
        "--install-oida-code is set; got first call labelled "
        f"{first_label!r}"
    )
    assert "owner/repo" in second_label.lower(), (
        "target MUST be installed last; got second call "
        f"labelled {second_label!r}"
    )


def test_install_order_target_only_when_no_oida_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without --install-oida-code only the target is installed."""
    mod = _import_clone_module()
    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )

    calls: list[str] = []

    def recorder(
        venv_python: Path,
        src_dir: Path,
        label: str,
        extra_env: dict[str, str] | None = None,
        extras: tuple[str, ...] = (),
    ) -> None:
        calls.append(label)

    monkeypatch.setattr(
        mod, "_pip_install_editable", recorder,
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
    assert len(calls) == 1, (
        f"expected 1 install call (target only); got {calls}"
    )
    assert "owner/repo" in calls[0].lower()


def test_import_smoke_command_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_import_smoke_check` runs <venv>/python -c "import X"
    for each PACKAGE; happy path returns silently."""
    mod = _import_clone_module()
    venv_py = Path("/fake/venv/python")

    captured_argvs: list[list[str]] = []

    class _OkResult:
        returncode = 0
        stderr = ""

    def fake_run(
        argv: list[str],
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> _OkResult:
        captured_argvs.append(argv)
        return _OkResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    mod._import_smoke_check(venv_py, ["sqlite_utils", "json"])

    assert len(captured_argvs) == 2, (
        "expected 2 import-smoke invocations; got "
        f"{len(captured_argvs)}"
    )
    for argv, pkg in zip(
        captured_argvs, ["sqlite_utils", "json"], strict=True,
    ):
        assert argv[0] == str(venv_py)
        assert argv[1] == "-c"
        assert argv[2] == f"import {pkg}", (
            f"expected `import {pkg}`; got {argv[2]!r}"
        )
        assert len(argv) == 3


def test_import_smoke_failure_reporting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Failed import emits a `target_bootstrap_gap` banner
    naming the failing package and raises SystemExit(2)."""
    mod = _import_clone_module()
    venv_py = Path("/fake/venv/python")

    class _FailResult:
        returncode = 1
        stderr = (
            "Traceback (most recent call last):\n"
            "  File \"<string>\", line 1, in <module>\n"
            "ModuleNotFoundError: No module named 'broken_pkg'\n"
        )

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, check=False, capture_output=False, text=False:
            _FailResult(),
    )

    with pytest.raises(SystemExit) as exc_info:
        mod._import_smoke_check(venv_py, ["broken_pkg"])
    assert exc_info.value.code == 2

    out = capsys.readouterr().err
    assert "target_bootstrap_gap" in out, (
        "failure banner must include 'target_bootstrap_gap'; "
        f"got stderr:\n{out}"
    )
    assert "broken_pkg" in out, (
        "failure banner must name the failing package; "
        f"got stderr:\n{out}"
    )


def test_main_invokes_import_smoke_after_installs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Sanity: main() calls _import_smoke_check exactly once
    when --import-smoke is provided, AFTER the install calls."""
    mod = _import_clone_module()

    monkeypatch.setattr(
        mod, "_shallow_fetch", lambda repo, sha, target: None,
    )
    monkeypatch.setattr(
        mod, "_create_venv", lambda target: tmp_path / ".venv",
    )
    install_count = {"n": 0}
    smoke_count = {"n": 0}
    smoke_after_installs = {"ok": False}

    def fake_install(
        venv_python: Path,
        src_dir: Path,
        label: str,
        extra_env: dict[str, str] | None = None,
        extras: tuple[str, ...] = (),
    ) -> None:
        install_count["n"] += 1

    def fake_smoke(
        venv_python: Path, packages: list[str],
    ) -> None:
        smoke_count["n"] += 1
        if install_count["n"] >= 1:
            smoke_after_installs["ok"] = True

    monkeypatch.setattr(
        mod, "_pip_install_editable", fake_install,
    )
    monkeypatch.setattr(
        mod, "_import_smoke_check", fake_smoke,
    )

    monkeypatch.setattr(
        sys, "argv",
        [
            "clone_target_at_sha.py",
            "--repo", "owner/repo",
            "--head-sha", "0" * 40,
            "--manual-egress-ok",
            "--install-oida-code",
            "--import-smoke", "owner_repo",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert smoke_count["n"] == 1
    assert install_count["n"] == 2
    assert smoke_after_installs["ok"], (
        "smoke check must run AFTER all installs"
    )


def test_no_import_smoke_skips_smoke_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without --import-smoke, no smoke check runs (back-compat)."""
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
    smoke_count = {"n": 0}
    monkeypatch.setattr(
        mod, "_import_smoke_check",
        lambda v, p: smoke_count.__setitem__(
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
            "--install-oida-code",
            "--clones-dir", str(tmp_path),
        ],
    )
    rc = mod.main()
    assert rc == 0
    assert smoke_count["n"] == 0, (
        "no --import-smoke means no smoke call"
    )


def test_workflow_non_reference_test_still_passes() -> None:
    """The existing dynamic-discovery test in
    `tests/test_phase6_1_d_llm_author_replays.py::test_no_manual_egress_script_referenced_in_workflows`
    auto-discovers all `scripts/*.py` carrying the marker. The
    Phase 6.1'f script change preserves the marker; no
    workflow file references the script. We re-run the
    discovery here as a Phase 6.1'f-local check.
    """
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return
    pattern = re.compile(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b",
        re.MULTILINE,
    )
    egress_scripts: list[Path] = []
    for path in (_REPO_ROOT / "scripts").glob("*.py"):
        if pattern.search(path.read_text(encoding="utf-8")):
            egress_scripts.append(path)
    assert (
        _SCRIPT_PATH in egress_scripts
    ), (
        "Phase 6.1'f's clone helper should still carry the "
        "MANUAL_EGRESS_SCRIPT marker"
    )
    rel_paths = [f"scripts/{p.name}" for p in egress_scripts]
    leaks: list[str] = []
    for yml_path in workflows_dir.rglob("*.yml"):
        body = yml_path.read_text(encoding="utf-8")
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for rel in rel_paths:
                if rel in stripped:
                    leaks.append(
                        f"{yml_path.relative_to(_REPO_ROOT)}: "
                        f"{stripped}",
                    )
                    break
    assert not leaks, (
        "manual-egress scripts must not be referenced from "
        "GitHub workflows. Violations:\n  "
        + "\n  ".join(leaks)
    )
