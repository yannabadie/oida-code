"""Phase 6.1'e step 3 + Phase 6.1'f (per QA/A45) — manual-lane
target-checkout helper for the calibration_seed lane.

Shallow-fetches a public GitHub repo at a specific commit SHA
into a temp workspace, creates a venv, and installs the target
in editable mode. The resulting venv has the target package at
the head_sha so that `oida-code verify-grounded` (run from that
venv) invokes the head_sha version of any tool the bundle
requests (e.g. pytest).

NOT in CI. NOT in the runtime path of ``oida-code``.
``MANUAL_EGRESS_SCRIPT = True`` per ADR-53. Refuses without
``--manual-egress-ok``.

Idempotent: keyed on (repo_url, head_sha). Re-running on the
same SHA reuses the existing clone and venv. Outputs the path
to the venv's Python interpreter on stdout (the operator pipes
into the verify-grounded run).

**Install order (Phase 6.1'f / ADR-60):** when
``--install-oida-code`` is set, the local oida-code package is
installed FIRST and the cloned target is installed editable
LAST. The hypothesis (from Phase 6.1'e step 4
``target_bootstrap_gap`` failures on sqlite-utils + structlog):
pip's editable-install dependency resolution can remove the
target's editable link if a later install re-resolves shared
dependencies. Installing the target last makes its editable
link the final state.

**Post-install importability smoke (Phase 6.1'f / ADR-60):**
``--import-smoke PACKAGE`` (repeatable) runs the venv's Python
as ``python -c "import PACKAGE"`` after all installs and fails
fast with a ``target_bootstrap_gap`` banner if any import
fails. Use this for any target whose pytest tests load the
package via a ``tests/conftest.py`` import (most non-pytest
projects).

Usage::

    export PAT_GITHUB=...   # public repos do not strictly need
                            # this, but auth raises rate limit
    python scripts/clone_target_at_sha.py \\
        --repo pytest-dev/pytest \\
        --head-sha 480809ae02a97344e68e52eb015e68b840f2e05c \\
        --manual-egress-ok \\
        --install-oida-code \\
        --import-smoke _pytest

    # For non-pytest targets:
    python scripts/clone_target_at_sha.py \\
        --repo simonw/sqlite-utils \\
        --head-sha e7ecb0ffdfcb15a879e0da202a00966623f1e79c \\
        --manual-egress-ok \\
        --install-oida-code \\
        --import-smoke sqlite_utils

The ``--install-oida-code`` flag pip-installs the local
oida-code package into the venv so a subsequent
``<venv>/bin/oida-code verify-grounded ...`` call has both the
target package AND the verifier available in one venv.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MANUAL_EGRESS_SCRIPT = True

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLONES_DIR = _REPO_ROOT / ".tmp" / "clones"


def _slug(s: str) -> str:
    return s.replace("/", "_").replace("-", "_").lower()


def _run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capturing stdout/stderr. ``check=True``
    raises on non-zero exit."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _shallow_fetch(
    repo: str, head_sha: str, target_dir: Path,
) -> None:
    """Initialize a git repo at ``target_dir``, add the remote,
    and shallow-fetch the specific SHA. Idempotent: re-running
    is a no-op if the SHA is already checked out."""
    if (target_dir / ".git").is_dir():
        # Already a repo — verify HEAD matches
        rev = _run(
            ["git", "rev-parse", "HEAD"], cwd=target_dir, check=False,
        )
        if (
            rev.returncode == 0
            and rev.stdout.strip() == head_sha
        ):
            return
    target_dir.mkdir(parents=True, exist_ok=True)
    if not (target_dir / ".git").is_dir():
        _run(["git", "init", "-q"], cwd=target_dir)
    # Set / reset origin
    remote = f"https://github.com/{repo}.git"
    _run(
        ["git", "remote", "remove", "origin"],
        cwd=target_dir, check=False,
    )
    _run(["git", "remote", "add", "origin", remote], cwd=target_dir)
    print(
        f"shallow-fetching {repo}@{head_sha[:8]} ...",
        file=sys.stderr,
    )
    _run(
        ["git", "fetch", "--depth", "1", "origin", head_sha],
        cwd=target_dir,
    )
    _run(["git", "checkout", "FETCH_HEAD"], cwd=target_dir)


def _venv_python(venv_dir: Path) -> Path:
    """Return the path to the venv's python interpreter."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _create_venv(target_dir: Path) -> Path:
    venv = target_dir / ".venv"
    if not _venv_python(venv).is_file():
        print(
            f"creating venv at {venv} ...",
            file=sys.stderr,
        )
        _run([sys.executable, "-m", "venv", str(venv)])
    return venv


def _import_smoke_check(
    venv_python: Path, packages: list[str],
) -> None:
    """Phase 6.1'f (ADR-60) — post-install importability smoke.

    Runs ``<venv>/python -c "import <pkg>"`` for each package
    in ``packages``. Fails fast on the first failure with a
    clear ``target_bootstrap_gap`` banner naming the failing
    package. The check exists because ``pip install -e
    <clone>`` reports success but does not guarantee the
    package is on the venv's import path at runtime; the
    Phase 6.1'e step 4 holdouts (sqlite-utils, structlog)
    both passed pip but failed pytest's conftest import.
    """
    for pkg in packages:
        print(
            f"import-smoke: verifying `import {pkg}` in venv ...",
            file=sys.stderr,
        )
        res = subprocess.run(
            [str(venv_python), "-c", f"import {pkg}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(
                f"target_bootstrap_gap: import-smoke for "
                f"`import {pkg}` FAILED (rc={res.returncode}); "
                "the package is not on the venv's import path "
                "after install. The clone helper will not return "
                "success in this state. stderr tail:",
                file=sys.stderr,
            )
            for line in res.stderr.splitlines()[-10:]:
                print(f"  {line}", file=sys.stderr)
            raise SystemExit(2)
        print(
            f"import-smoke: `import {pkg}` OK",
            file=sys.stderr,
        )


def _pip_install_editable(
    venv_python: Path,
    src_dir: Path,
    label: str,
    extra_env: dict[str, str] | None = None,
) -> None:
    print(
        f"pip install -e {label} into venv ...",
        file=sys.stderr,
    )
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    res = subprocess.run(
        [
            str(venv_python), "-m", "pip", "install", "-e",
            str(src_dir),
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(
            f"pip install -e {label} failed (rc="
            f"{res.returncode}); stderr tail:",
            file=sys.stderr,
        )
        for line in res.stderr.splitlines()[-15:]:
            print(f"  {line}", file=sys.stderr)
        raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Manual lane: shallow-clone a public GitHub repo "
            "at a specific SHA, create a venv, and install "
            "the target. ADR-53 + QA/A45."
        ),
    )
    parser.add_argument(
        "--repo", required=True,
        help="owner/name of the public repo, e.g. pytest-dev/pytest",
    )
    parser.add_argument(
        "--head-sha", required=True,
        help="40-char SHA to check out",
    )
    parser.add_argument(
        "--manual-egress-ok", action="store_true", default=False,
    )
    parser.add_argument(
        "--install-oida-code", action="store_true", default=False,
        help=(
            "Also pip-install the local oida-code package into the venv "
            "so verify-grounded is available alongside the target."
        ),
    )
    parser.add_argument(
        "--clones-dir", type=Path, default=_CLONES_DIR,
    )
    parser.add_argument(
        "--scm-pretend-version",
        action="append", default=[],
        metavar="PACKAGE=VERSION",
        help=(
            "Set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PACKAGE> "
            "during the editable install. Use when the shallow "
            "clone lacks the tag history setuptools_scm needs. "
            "Repeatable: --scm-pretend-version pytest=9.0.0 "
            "--scm-pretend-version other=1.2.3"
        ),
    )
    parser.add_argument(
        "--import-smoke",
        action="append", default=[],
        metavar="PACKAGE",
        help=(
            "After all installs, run the venv's Python as "
            '`python -c "import PACKAGE"` to verify the package is '
            "importable. Fails fast with a clear "
            "target_bootstrap_gap message if the import fails. "
            "Repeatable: --import-smoke sqlite_utils "
            "--import-smoke structlog. Phase 6.1'f (ADR-60) "
            "introduced this flag in response to the holdout "
            "bootstrap gap surfaced in Phase 6.1'e step 4."
        ),
    )
    args = parser.parse_args()
    scm_env: dict[str, str] = {}
    for entry in args.scm_pretend_version:
        if "=" not in entry:
            print(
                f"--scm-pretend-version expects PACKAGE=VERSION; "
                f"got {entry!r}",
                file=sys.stderr,
            )
            return 2
        pkg, ver = entry.split("=", 1)
        scm_env[
            f"SETUPTOOLS_SCM_PRETEND_VERSION_FOR_{pkg.upper()}"
        ] = ver

    if not args.manual_egress_ok:
        print(
            "refusing: --manual-egress-ok required (ADR-53 "
            "frontière rule 4)",
            file=sys.stderr,
        )
        return 2

    if len(args.head_sha) != 40 or any(
        c not in "0123456789abcdef" for c in args.head_sha
    ):
        print(
            f"invalid head-sha (must be 40-char lowercase hex): "
            f"{args.head_sha!r}",
            file=sys.stderr,
        )
        return 2

    if "/" not in args.repo:
        print(
            f"invalid repo (must be owner/name): {args.repo!r}",
            file=sys.stderr,
        )
        return 2

    target_name = f"{_slug(args.repo)}_{args.head_sha[:8]}"
    target_dir = args.clones_dir / target_name
    args.clones_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: shallow-fetch
    _shallow_fetch(args.repo, args.head_sha, target_dir)

    # Step 2: create venv
    venv = _create_venv(target_dir)
    venv_python = _venv_python(venv)

    # Phase 6.1'f (ADR-60): install order matters.
    # When --install-oida-code is set, install oida-code FIRST so
    # the LAST install is the target's editable. Pip's
    # editable-install dependency resolution can otherwise
    # remove the target's editable link if a later install
    # re-resolves shared dependencies (the dominant failure shape
    # observed on sqlite-utils + structlog in Phase 6.1'e step 4).

    if args.install_oida_code:
        # Step 3a: install oida-code FIRST.
        _pip_install_editable(
            venv_python, _REPO_ROOT, "oida-code (local)",
        )

    # Step 3b (or step 3 if no oida-code): install target editable LAST.
    _pip_install_editable(
        venv_python, target_dir, args.repo, extra_env=scm_env,
    )

    # Step 4: post-install importability smoke (Phase 6.1'f).
    if args.import_smoke:
        _import_smoke_check(venv_python, args.import_smoke)

    print()
    print(f"target: {args.repo}@{args.head_sha}")
    print(f"clone:  {target_dir}")
    print(f"venv:   {venv}")
    print(f"python: {venv_python}")
    if args.install_oida_code:
        oida_cli = (
            venv / "Scripts" / "oida-code.exe"
            if sys.platform == "win32"
            else venv / "bin" / "oida-code"
        )
        print(f"oida-code CLI: {oida_cli}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
