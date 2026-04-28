"""Phase 6.0.y' (ADR-52, QA/A43) — cross-lane structural isolation tests.

Four tests enforce the three-lane architecture defined by ADR-52:

* Lane 1 — `reports/beta/` + `feedback_channel: human_beta`
  (external operators only).
* Lane 2 — `reports/ai_adversarial/` + `agent_label`
  (cold-reader critique, downgraded evidence).
* Lane 3 — `reports/yann_solo/` + `feedback_channel:
  yann_solo_dogfood` + `operator_role: project_author` (project
  author dogfood, internal only).

Cross-lane contamination is forbidden. The schema pins
(`feedback_channel`) and path-isolation guards (in
`scripts/run_beta_feedback_eval.py:_iter_feedback_files`) are the
runtime defences. These four tests are the structural defence:
they fail loudly the moment a lane label leaks into the wrong
directory or schema combination.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# `reports/beta/ai_adversarial/` and `reports/beta/yann_solo/` are
# explicitly excluded from the human-beta scan because per the
# Phase 6.0.x path-isolation guard the aggregator already skips
# them. Any subdirectory whose name is in this set is scanned
# under its own lane's tests, not the human-beta lane test.
_HUMAN_BETA_LANE_EXCLUDED_SUBTREES: frozenset[str] = frozenset(
    {"ai_adversarial", "yann_solo", "legacy"},
)


def _scan_text_files(root: Path) -> list[Path]:
    """Return all .md / .yaml / .yml / .json files under root."""
    if not root.exists():
        return []
    out: list[Path] = []
    for pattern in ("**/*.md", "**/*.yaml", "**/*.yml", "**/*.json"):
        out.extend(root.glob(pattern))
    return sorted(set(out))


def _files_in_human_beta_lane(root: Path) -> list[Path]:
    """Return text files under `reports/beta/` excluding isolated
    subtrees per the Phase 6.0.x path-isolation guard.
    """
    out: list[Path] = []
    for path in _scan_text_files(root):
        if any(
            seg in _HUMAN_BETA_LANE_EXCLUDED_SUBTREES
            for seg in path.parts
        ):
            continue
        out.append(path)
    return out


def test_no_agent_label_in_reports_beta() -> None:
    """ADR-52 lane 1 isolation: ``agent_label`` (the AI-tier
    discriminator) must NOT appear in the human-beta lane.

    A leak would mean an AI critique landed in
    ``reports/beta/`` and could pollute future aggregations or
    confuse a reader. The schema pin in the aggregator catches
    this at runtime; this test catches it at commit time.
    """
    beta_root = _REPO_ROOT / "reports" / "beta"
    files = _files_in_human_beta_lane(beta_root)
    leaks: list[str] = []
    for path in files:
        body = path.read_text(encoding="utf-8")
        # Only flag the LITERAL field-name token; mentions in
        # narrative text (e.g. the aggregate.md zero-feedback
        # frame document) are filtered by requiring the YAML/JSON
        # field shape ``agent_label:`` or `"agent_label":`.
        if re.search(r"^\s*agent_label\s*:", body, re.MULTILINE):
            leaks.append(str(path.relative_to(_REPO_ROOT)))
        if re.search(r'"agent_label"\s*:', body):
            leaks.append(str(path.relative_to(_REPO_ROOT)))
    assert not leaks, (
        "Lane 1 contamination — `agent_label` field appeared in "
        "reports/beta/ outside excluded subtrees:\n  "
        + "\n  ".join(leaks)
    )


def test_no_human_beta_channel_in_reports_ai_adversarial() -> None:
    """ADR-52 lane 2 isolation: ``feedback_channel: human_beta``
    must NOT appear in the AI-tier lane.

    A leak would mean an AI critique pretended to be human
    feedback. The aggregator's schema pin rejects this at
    ingestion; this test catches the structural shape at commit
    time so it never gets ingested in the first place.
    """
    ai_root = _REPO_ROOT / "reports" / "ai_adversarial"
    if not ai_root.is_dir():
        return
    leaks: list[str] = []
    for path in _scan_text_files(ai_root):
        body = path.read_text(encoding="utf-8")
        if re.search(
            r"^\s*feedback_channel\s*:\s*['\"]?human_beta['\"]?\s*$",
            body,
            re.MULTILINE,
        ):
            leaks.append(str(path.relative_to(_REPO_ROOT)))
        if re.search(
            r'"feedback_channel"\s*:\s*"human_beta"',
            body,
        ):
            leaks.append(str(path.relative_to(_REPO_ROOT)))
    assert not leaks, (
        "Lane 2 contamination — `feedback_channel: human_beta` "
        "appeared in reports/ai_adversarial/:\n  "
        + "\n  ".join(leaks)
    )


def test_no_human_beta_channel_with_project_author_role() -> None:
    """ADR-52 cross-lane bias guard: a single file MUST NOT
    combine ``feedback_channel: human_beta`` with
    ``operator_role: project_author``.

    QA/A43 §"Yann-solo policy": Yann is the project author and
    co-author of every doc; his runs are real human runs but
    they are NOT external. Combining ``project_author`` role with
    ``human_beta`` channel would let project-author dogfood count
    as external-human signal, which is exactly the contamination
    QA/A41 §6.0-A protected against ("usage par quelqu'un hors
    Yann / Claude / cgpro").
    """
    leaks: list[str] = []
    for root_name in ("reports", "docs"):
        root = _REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in _scan_text_files(root):
            body = path.read_text(encoding="utf-8")
            has_human_beta = bool(
                re.search(
                    r"^\s*feedback_channel\s*:\s*['\"]?human_beta['\"]?\s*$",
                    body,
                    re.MULTILINE,
                )
                or re.search(
                    r'"feedback_channel"\s*:\s*"human_beta"', body,
                ),
            )
            has_project_author = bool(
                re.search(
                    r"^\s*operator_role\s*:\s*['\"]?project_author['\"]?\s*$",
                    body,
                    re.MULTILINE,
                )
                or re.search(
                    r'"operator_role"\s*:\s*"project_author"', body,
                ),
            )
            if has_human_beta and has_project_author:
                leaks.append(str(path.relative_to(_REPO_ROOT)))
    assert not leaks, (
        "Cross-lane bias guard — file combines "
        "`feedback_channel: human_beta` with `operator_role: "
        "project_author`:\n  "
        + "\n  ".join(leaks)
    )


def test_project_status_distinguishes_three_lanes() -> None:
    """ADR-52 public-status integrity: ``docs/project_status.md``
    MUST contain literal mentions of each of the three lane
    labels so a reader sees them spelled out and cannot mistake
    AI-tier or Yann-solo for the absent external-human beta.

    Per QA/A43 piège 15 ("contamination par vocabulaire"): the
    risk is discursive, not just technical. A public summary
    that says "beta feedback" while meaning "AI-tier critique"
    leaks the wrong claim. The three lane labels in
    project_status.md are the canonical anti-confusion surface.
    """
    body = (
        _REPO_ROOT / "docs" / "project_status.md"
    ).read_text(encoding="utf-8")
    required_labels = (
        "external-human beta",
        "AI-tier",
        "Yann-solo",
    )
    missing: list[str] = []
    for label in required_labels:
        if label not in body:
            missing.append(label)
    assert not missing, (
        f"docs/project_status.md must contain literal lane "
        f"labels {required_labels}; missing: {missing}"
    )
