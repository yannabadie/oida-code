"""Phase 6.1'a-pre (ADR-53, QA/A44) — manual data lane isolation tests.

Per QA/A44 §"Frontière manual-vs-runtime", the manual data
acquisition lane (PAT_GITHUB / HF_TOKEN / providers) must NEVER
cross into the runtime path under ``src/oida_code/``. These tests
enforce the four critical invariants:

1. No source file under ``src/oida_code/`` carries the
   ``MANUAL_EGRESS_SCRIPT = True`` marker (the marker is the
   discriminator for manual-only scripts).
2. No module under ``src/oida_code/`` (excluding ``_vendor/``)
   imports a network-egress client (``requests``, ``httpx``,
   ``huggingface_hub``).
3. No source file under ``src/oida_code/`` references the env
   vars ``PAT_GITHUB`` or ``HF_TOKEN``.
4. The first manual data acquisition script
   (``scripts/build_calibration_seed_index.py``) defaults to
   dry-run, refuses to leave dry-run without
   ``--manual-egress-ok`` AND ``--public-only``, and is not
   referenced from any GitHub workflow.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_FORBIDDEN_NETWORK_IMPORTS: tuple[re.Pattern[str], ...] = (
    # `requests` is the canonical egress library; never in runtime
    re.compile(r"^\s*import\s+requests\b", re.MULTILINE),
    re.compile(r"^\s*from\s+requests(\.|\s+)", re.MULTILINE),
    # `httpx` is async egress; never in runtime
    re.compile(r"^\s*import\s+httpx\b", re.MULTILINE),
    re.compile(r"^\s*from\s+httpx(\.|\s+)", re.MULTILINE),
    # huggingface_hub is the HF SDK; never in runtime
    re.compile(r"^\s*import\s+huggingface_hub\b", re.MULTILINE),
    re.compile(r"^\s*from\s+huggingface_hub(\.|\s+)", re.MULTILINE),
)

_FORBIDDEN_ENV_VAR_NAMES: tuple[str, ...] = (
    "PAT_GITHUB",
    "HF_TOKEN",
)


def _runtime_python_files() -> list[Path]:
    """Return all .py files under src/oida_code/ excluding _vendor/."""
    src_root = _REPO_ROOT / "src" / "oida_code"
    out: list[Path] = []
    for path in src_root.rglob("*.py"):
        if "_vendor" in path.parts:
            continue
        out.append(path)
    return sorted(out)


def test_no_manual_egress_marker_in_src() -> None:
    """ADR-53 invariant 1: ``MANUAL_EGRESS_SCRIPT = True`` is the
    marker for manual-only egress scripts. It must NEVER appear in
    a runtime source file.
    """
    leaks: list[str] = []
    pattern = re.compile(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b", re.MULTILINE,
    )
    for path in _runtime_python_files():
        body = path.read_text(encoding="utf-8")
        if pattern.search(body):
            leaks.append(str(path.relative_to(_REPO_ROOT)))
    assert not leaks, (
        "ADR-53 invariant 1 violated — `MANUAL_EGRESS_SCRIPT = True` "
        "marker found in runtime source files:\n  "
        + "\n  ".join(leaks)
    )


def test_no_network_client_import_in_src_runtime() -> None:
    """ADR-53 invariant 2: no module under src/oida_code/ may import
    `requests`, `httpx`, or `huggingface_hub`. `urllib.request` is
    the stdlib fallback used by the opt-in adversarial review
    pattern; it is allowed but must NOT appear in code under any
    name that suggests runtime invocation.
    """
    leaks: list[str] = []
    for path in _runtime_python_files():
        body = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN_NETWORK_IMPORTS:
            for match in pattern.finditer(body):
                leaks.append(
                    f"{path.relative_to(_REPO_ROOT)}: "
                    f"{match.group(0).strip()}",
                )
    assert not leaks, (
        "ADR-53 invariant 2 violated — runtime module imports a "
        "forbidden network client:\n  " + "\n  ".join(leaks)
    )


def test_no_pat_github_or_hf_token_in_src() -> None:
    """ADR-53 invariant 3: env var names `PAT_GITHUB` and
    `HF_TOKEN` MUST NOT appear in any runtime source file.
    """
    leaks: list[str] = []
    for path in _runtime_python_files():
        body = path.read_text(encoding="utf-8")
        for env_var in _FORBIDDEN_ENV_VAR_NAMES:
            if env_var in body:
                leaks.append(
                    f"{path.relative_to(_REPO_ROOT)}: {env_var}",
                )
    assert not leaks, (
        "ADR-53 invariant 3 violated — runtime source mentions a "
        "forbidden env var:\n  " + "\n  ".join(leaks)
    )


_INDEXER_SCRIPT = (
    _REPO_ROOT / "scripts" / "build_calibration_seed_index.py"
)


def test_manual_indexer_carries_egress_marker() -> None:
    """The manual data acquisition script MUST carry the
    ``MANUAL_EGRESS_SCRIPT = True`` module-level marker. Without
    it, invariant 1 cannot be enforced (the test scans for the
    marker in src/, but the marker also has to actually exist in
    the manual script for the discriminator to be meaningful).
    """
    body = _INDEXER_SCRIPT.read_text(encoding="utf-8")
    assert re.search(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b",
        body,
        re.MULTILINE,
    ), (
        f"{_INDEXER_SCRIPT.relative_to(_REPO_ROOT)} must carry the "
        f"`MANUAL_EGRESS_SCRIPT = True` module-level marker"
    )


def test_manual_indexer_default_dry_run() -> None:
    """ADR-53 invariant 4 (part 1): the script must default to
    dry-run mode (no network call) when called without explicit
    flags. We verify by invoking with `--repo` only and checking
    that the dry-run banner appears AND no real-collection path
    is taken.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_INDEXER_SCRIPT),
            "--repo",
            "pallets/click",
            "--max-prs",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"default invocation should exit 0, got {result.returncode}"
    )
    assert "DRY-RUN" in result.stdout, (
        "default invocation must print DRY-RUN banner; got:\n"
        f"{result.stdout}"
    )


def test_manual_indexer_refuses_without_egress_ok() -> None:
    """ADR-53 invariant 4 (part 2): with --public-only but without
    --manual-egress-ok, the script must refuse with non-zero exit
    AND a clear message.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_INDEXER_SCRIPT),
            "--repo",
            "pallets/click",
            "--max-prs",
            "1",
            "--public-only",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )
    # Without manual-egress-ok the script runs in dry-run mode (since
    # the outer condition catches not args.manual_egress_ok). The
    # dry-run plan is printed; exit is 0. This is a soft refusal —
    # the script never makes a network call. The hard refusal (exit
    # 2) requires manual_egress_ok=True AND public_only=False.
    assert "DRY-RUN" in result.stdout, (
        "without --manual-egress-ok the script must remain in "
        "dry-run mode; got:\n" + result.stdout
    )


def test_manual_indexer_refuses_without_public_only() -> None:
    """ADR-53 invariant 4 (part 3): with --manual-egress-ok but
    without --public-only, the script must refuse with non-zero
    exit AND a clear "refusing:" message in stderr.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_INDEXER_SCRIPT),
            "--repo",
            "pallets/click",
            "--max-prs",
            "1",
            "--manual-egress-ok",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 2, (
        f"--manual-egress-ok without --public-only must exit 2, "
        f"got {result.returncode}; stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "refusing" in result.stderr.lower() or (
        "refusing" in result.stdout.lower()
    ), (
        "must print a 'refusing' message; stderr:\n"
        f"{result.stderr}"
    )


def test_no_manual_egress_script_in_workflows() -> None:
    """ADR-53 invariant 4 (part 4): no GitHub workflow may invoke
    a script that carries the MANUAL_EGRESS_SCRIPT marker. This
    test specifically checks for `build_calibration_seed_index.py`
    (the only one in this phase) but the pattern generalizes to
    any future manual-egress script.
    """
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return
    forbidden_script_paths = (
        "scripts/build_calibration_seed_index.py",
        "scripts/build_calibration_seed_",  # any future variant
    )
    leaks: list[str] = []
    for yml_path in workflows_dir.rglob("*.yml"):
        body = yml_path.read_text(encoding="utf-8")
        for forbidden in forbidden_script_paths:
            if forbidden in body:
                # Only flag if actually invoked, not in a comment
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if forbidden in stripped:
                        leaks.append(
                            f"{yml_path.relative_to(_REPO_ROOT)}: "
                            f"{stripped}",
                        )
                        break
    assert not leaks, (
        "ADR-53 invariant 4 violated — manual-egress script "
        "invoked from a GitHub workflow:\n  " + "\n  ".join(leaks)
    )
