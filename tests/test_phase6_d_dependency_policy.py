"""ADR-75 dependency-policy guards for future G-6d pinning."""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROTOCOL = _REPO_ROOT / "docs" / "calibration_seed_expansion_protocol.md"
_POLICY_REPORT = _REPO_ROOT / "reports" / "phase6_d_dependency_policy" / "adr75_policy.md"
_CLONE_HELPER = _REPO_ROOT / "scripts" / "clone_target_at_sha.py"
_INDEX = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_adr75_requires_pre_freeze_reject_or_defer_for_requirements_files() -> None:
    protocol = _read(_PROTOCOL)
    report = _read(_POLICY_REPORT)
    combined = f"{protocol}\n{report}".lower()
    normalized = " ".join(combined.split())

    assert "adr-75" in combined
    assert "rejected or deferred before partition freeze" in normalized
    assert "requirements/*.txt" in combined
    assert "tox.ini" in combined
    assert "deps = -r" in combined
    assert "pip install -r" in combined
    assert "post-freeze rescue" in combined or "rescued after" in combined


def test_adr75_does_not_add_requirements_file_clone_helper_capability() -> None:
    helper = _read(_CLONE_HELPER)
    protocol = _read(_PROTOCOL)
    report = _read(_POLICY_REPORT)

    assert "--install-requirements-file" not in helper
    assert "install_requirements_file" not in helper
    assert "pip install -r" not in helper
    assert "--install-requirements-file" in protocol
    assert "--install-requirements-file" in report
    assert "does not add a new clone-helper flag" in report


def test_adr75_is_policy_only_and_does_not_advance_live_index() -> None:
    records = json.loads(_INDEX.read_text(encoding="utf-8"))
    pinned = [r for r in records if r.get("partition") in {"train", "holdout"}]
    train = [r for r in pinned if r.get("partition") == "train"]
    holdout = [r for r in pinned if r.get("partition") == "holdout"]

    assert len(records) == 46
    assert len(pinned) == 14
    assert len(train) == 10
    assert len(holdout) == 4
    assert not (_REPO_ROOT / "reports" / "phase6_d_4_pinning").exists()


def test_adr75_keeps_runtime_and_product_boundaries_closed() -> None:
    report = _read(_POLICY_REPORT).lower()

    assert "no runtime/provider/mcp/default-gateway change" in report
    assert "no official oida fusion-field unlock" in report
    assert "no corpus advance" in report
    assert "no product or merge-readiness verdict" in report
