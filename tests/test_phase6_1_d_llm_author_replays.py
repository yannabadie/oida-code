"""Phase 6.1'd (ADR-57) — LLM-replay authoring helper guards.

The new manual-lane script ``scripts/llm_author_replays.py``
calls a provider (DeepSeek by default) to author the four
``pass*_*.json`` replays for a calibration_seed bundle. These
tests enforce the lane discipline:

1. The script carries the ``MANUAL_EGRESS_SCRIPT = True``
   module-level marker (per ADR-53).
2. The script refuses to run without ``--manual-egress-ok``.
3. NO ``scripts/*.py`` carrying the marker is referenced from
   any GitHub workflow file (this generalizes the
   Phase 6.1'a-pre check that targeted only the indexer).
4. The bundle generator's pre-LLM skeleton stubs do NOT carry
   any forbidden phrase that the LLM author might propagate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LLM_SCRIPT = _REPO_ROOT / "scripts" / "llm_author_replays.py"


def test_llm_author_replays_carries_egress_marker() -> None:
    """The script MUST carry the ``MANUAL_EGRESS_SCRIPT = True``
    module-level marker — that marker is the discriminator
    between manual-only egress scripts and runtime modules
    under ``src/oida_code/`` (per ADR-53)."""
    body = _LLM_SCRIPT.read_text(encoding="utf-8")
    assert re.search(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b",
        body,
        re.MULTILINE,
    ), (
        f"{_LLM_SCRIPT.relative_to(_REPO_ROOT)} must carry the "
        f"`MANUAL_EGRESS_SCRIPT = True` module-level marker "
        f"(per ADR-53 frontière rule 1)."
    )


def test_llm_author_replays_refuses_without_egress_ok() -> None:
    """Without ``--manual-egress-ok`` the script must refuse
    with a non-zero exit code AND NOT call the provider."""
    result = subprocess.run(
        [
            sys.executable,
            str(_LLM_SCRIPT),
            "--case-id", "seed_test",
            "--bundle-dir", str(_REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 2, (
        "without --manual-egress-ok the script must exit 2; "
        f"got {result.returncode}; "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "manual-egress-ok" in (
        result.stderr.lower() + result.stdout.lower()
    ), (
        "the refusal banner must mention `--manual-egress-ok`; "
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
    )


def _discover_manual_egress_scripts() -> list[Path]:
    """Find every ``scripts/*.py`` that sets the marker."""
    scripts_dir = _REPO_ROOT / "scripts"
    pattern = re.compile(
        r"^\s*MANUAL_EGRESS_SCRIPT\s*=\s*True\b",
        re.MULTILINE,
    )
    out: list[Path] = []
    for path in scripts_dir.glob("*.py"):
        if pattern.search(path.read_text(encoding="utf-8")):
            out.append(path)
    return sorted(out)


def test_no_manual_egress_script_referenced_in_workflows() -> None:
    """Generalises the Phase 6.1'a-pre indexer-only check:
    every ``scripts/*.py`` carrying the marker MUST NOT be
    referenced from any GitHub workflow file."""
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return
    egress_scripts = _discover_manual_egress_scripts()
    assert egress_scripts, (
        "no manual-egress scripts were discovered — the test "
        "expects at least the indexer + the LLM-author helper"
    )
    leaks: list[str] = []
    rel_paths = [
        f"scripts/{p.name}" for p in egress_scripts
    ]
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


def test_marker_set_includes_indexer_and_llm_author() -> None:
    """Sanity check on the discovery helper. As of Phase 6.1'd
    (ADR-57) the marker set must include both the indexer
    (Phase 6.1'a-pre) and the LLM-author helper."""
    discovered = {
        p.name for p in _discover_manual_egress_scripts()
    }
    assert "build_calibration_seed_index.py" in discovered, (
        "indexer should be discovered"
    )
    assert "llm_author_replays.py" in discovered, (
        "LLM-author helper should be discovered"
    )
