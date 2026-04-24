"""Programmatic builders for the 10 Block-D2 hermetic trace fixtures.

Each scenario is a single :class:`TraceSpec` that materializes into the
A9.md-compliant directory layout:

    <fixture_root>/<name>/
        repo/           (Python sources)
        request.json
        trace.jsonl
        expected.json
        README.md

We materialize on-demand (tmp_path in tests) rather than checking 10*5=50
files into the repo — the spec is the single source of truth, and the
materializer is the only place that can drift. Checksums for expected
outputs are computed by running the real scorer the first time; tests
then assert against ``expected.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class TraceEventSpec:
    """Minimal JSONL record for a Claude Code transcript."""

    kind: Literal[
        "read", "grep", "edit", "write", "test_run", "tool_call", "commit", "other"
    ]
    scope: tuple[str, ...]
    intent: str = ""
    tool_result: str = "ok"

    _TOOL_NAME: dict[str, str] = field(  # type: ignore[misc]
        default_factory=lambda: {
            "read": "Read",
            "grep": "Grep",
            "edit": "Edit",
            "write": "Write",
            "test_run": "Bash",
            "tool_call": "Bash",
            "commit": "Bash",
            "other": "Bash",
        }
    )


@dataclass(frozen=True, slots=True)
class ExpectedSurface:
    changed: tuple[str, ...]
    impact: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedMetrics:
    progress_events_min: int = 0
    progress_events_max: int | None = None
    dominant_case: Literal[
        "exploration", "exploit_goal", "exploit_other", "either", "terminal", "mixed"
    ] | None = None
    exploration_error_min: float | None = None
    exploration_error_max: float | None = None
    exploitation_error_min: float | None = None
    exploitation_error_max: float | None = None
    stale_score_min: int = 0


@dataclass(frozen=True, slots=True)
class ExpectedGraph:
    supportive_edges_count_min: int = 0
    constitutive_edges_count_min: int = 0
    has_db_to_app_edge: bool = False


@dataclass(frozen=True, slots=True)
class TraceSpec:
    """One hermetic D2 scenario."""

    name: str
    description: str
    files: dict[str, str]  # relpath → contents
    changed_files: tuple[str, ...]
    events: tuple[TraceEventSpec, ...]
    surface: ExpectedSurface
    metrics: ExpectedMetrics
    graph: ExpectedGraph
    ablation_compare: bool = False  # compare --surface changed vs impact


def _make_assistant(use_id: str, name: str, input_dict: dict[str, Any]) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": use_id,
                    "name": name,
                    "input": input_dict,
                }
            ]
        },
    }


def _make_user_result(use_id: str, text: str) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": use_id,
                    "content": [{"type": "text", "text": text}],
                }
            ]
        },
    }


_KIND_TO_TOOL: dict[str, str] = {
    "read": "Read",
    "grep": "Grep",
    "edit": "Edit",
    "write": "Write",
    "test_run": "Bash",
    "tool_call": "Bash",
    "commit": "Bash",
    "other": "Bash",
}


def _build_trace_records(events: tuple[TraceEventSpec, ...]) -> list[dict]:
    out: list[dict] = []
    for i, ev in enumerate(events):
        use_id = f"u{i}"
        name = _KIND_TO_TOOL[ev.kind]
        if name in ("Read", "Edit", "Write"):
            inp = {"file_path": ev.scope[0] if ev.scope else ""}
        elif name == "Grep":
            inp = {"path": ev.scope[0] if ev.scope else "", "pattern": "foo"}
        elif name == "Bash":
            if ev.kind == "test_run":
                inp = {"command": f"pytest {ev.scope[0] if ev.scope else ''}",
                       "description": ev.intent}
            elif ev.kind == "commit":
                inp = {"command": "git commit -m 'msg'", "description": ev.intent}
            else:
                inp = {"command": ev.intent or "echo", "description": ev.intent}
        else:
            inp = {}
        out.append(_make_assistant(use_id, name, inp))
        out.append(_make_user_result(use_id, ev.tool_result))
    return out


def materialize(spec: TraceSpec, root: Path) -> Path:
    """Write the A9.md directory for ``spec`` under ``root/spec.name/``."""
    fixture_dir = root / spec.name
    repo = fixture_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    # repo/ sources.
    for rel, contents in spec.files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")

    # request.json (raw diff).
    request = {
        "repo": {
            "path": str(repo),
            "revision": "HEAD",
            "base_revision": "HEAD^",
        },
        "intent": {"summary": spec.description[:80], "sources": []},
        "scope": {
            "changed_files": list(spec.changed_files),
            "language": "python",
        },
        "commands": {"lint": "", "types": "", "tests": ""},
        "policy": {
            "max_critical_findings": 0,
            "min_mutation_score": 0.0,
            "min_property_checks": 0,
        },
        "budgets": {
            "lint": 30, "types": 60, "tests": 600,
            "semgrep": 120, "codeql": 900,
            "hypothesis": 300, "mutmut": 600,
        },
    }
    (fixture_dir / "request.json").write_text(
        json.dumps(request, indent=2), encoding="utf-8"
    )

    # trace.jsonl.
    records = _build_trace_records(spec.events)
    (fixture_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )

    # expected.json.
    expected = {
        "name": spec.name,
        "description": spec.description,
        "expected_surface": {
            "changed": list(spec.surface.changed),
            "impact": list(spec.surface.impact),
        },
        "expected_metrics": {
            k: v
            for k, v in {
                "progress_events_min": spec.metrics.progress_events_min,
                "progress_events_max": spec.metrics.progress_events_max,
                "dominant_case": spec.metrics.dominant_case,
                "exploration_error_min": spec.metrics.exploration_error_min,
                "exploration_error_max": spec.metrics.exploration_error_max,
                "exploitation_error_min": spec.metrics.exploitation_error_min,
                "exploitation_error_max": spec.metrics.exploitation_error_max,
                "stale_score_min": spec.metrics.stale_score_min,
            }.items()
            if v is not None
        },
        "expected_graph": {
            "supportive_edges_min": spec.graph.supportive_edges_count_min,
            "constitutive_edges_min": spec.graph.constitutive_edges_count_min,
            "has_db_to_app_edge": spec.graph.has_db_to_app_edge,
        },
        "ablation_compare_changed_vs_impact": spec.ablation_compare,
    }
    (fixture_dir / "expected.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )

    # README.md (human-readable scenario note).
    readme = f"# {spec.name}\n\n{spec.description}\n"
    (fixture_dir / "README.md").write_text(readme, encoding="utf-8")

    return fixture_dir


# ---------------------------------------------------------------------------
# The 10 scenarios
# ---------------------------------------------------------------------------


def _minimal_repo_with_db_and_app() -> dict[str, str]:
    return {
        "src/__init__.py": "",
        "src/db.py": (
            "def get_conn(host):\n"
            "    assert host, 'host required'\n"
            "    return host\n"
        ),
        "src/app.py": (
            "from src import db\n"
            "def create_user(name):\n"
            "    assert name, 'name required'\n"
            "    return db.get_conn('postgres://x'), name\n"
        ),
        "tests/test_app.py": "def test_create(): pass\n",
        "tests/__init__.py": "",
    }


SCENARIOS: list[TraceSpec] = [
    # 1. Clean success — read target, read tests, edit, run tests, commit.
    TraceSpec(
        name="01_clean_success",
        description="Read target + tests, make an edit, run tests, commit. "
                    "Low exploration error, bounded exploitation error.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="read", scope=("src/app.py",), intent="discover target"),
            TraceEventSpec(kind="read", scope=("tests/test_app.py",), intent="read tests"),
            TraceEventSpec(kind="edit", scope=("src/app.py",), intent="patch"),
            TraceEventSpec(kind="test_run", scope=("tests/test_app.py",), intent="verify"),
            TraceEventSpec(kind="commit", scope=("src/app.py",), intent="ship"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(
            progress_events_min=1, exploration_error_max=0.5,
        ),
        graph=ExpectedGraph(supportive_edges_count_min=1),
    ),

    # 2. Exploration miss — never reads the target file in U(t).
    TraceSpec(
        name="02_exploration_miss",
        description="Agent greps unrelated docs and never reads the changed file. "
                    "High exploration error, U(t) stays full.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="grep", scope=("README.md",), intent="search docs"),
            TraceEventSpec(kind="grep", scope=("CHANGELOG.md",), intent="search changelog"),
            TraceEventSpec(kind="grep", scope=("README.md",), intent="re-search docs"),
            TraceEventSpec(kind="grep", scope=("CHANGELOG.md",), intent="re-search"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(
            progress_events_max=0, exploration_error_min=0.5,
        ),
        graph=ExpectedGraph(),
    ),

    # 3. Exploitation miss — reads everything then edits unrelated file without closing.
    TraceSpec(
        name="03_exploitation_miss",
        description="Agent reads the target, sees all the info, but edits an unrelated file. "
                    "Exploitation error is non-trivial; no obligation closed.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="read", scope=("src/app.py",), intent="read target"),
            TraceEventSpec(kind="edit", scope=("README.md",), intent="edit docs"),
            TraceEventSpec(kind="edit", scope=("README.md",), intent="edit docs again"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(
            progress_events_min=1,
            # at least one exploitation-regime step errors out
            exploitation_error_min=0.2,
        ),
        graph=ExpectedGraph(),
    ),

    # 4. Stale cycling — alternating grep on non-surface paths.
    # README/CHANGELOG are outside the impact cone so they never enter
    # U(t); no progress fires; the no-progress segment grows and
    # node/edge reuse accumulates under the undirected-budget rule.
    TraceSpec(
        name="04_stale_cycling",
        description="Agent alternates grep between README.md and CHANGELOG.md "
                    "(both outside the impact surface). No action hits U(t); "
                    "stale counter rises via node_reuse + edge_reuse.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="grep", scope=("README.md",), intent="search docs"),
            TraceEventSpec(kind="grep", scope=("CHANGELOG.md",), intent="search changelog"),
            TraceEventSpec(kind="grep", scope=("README.md",), intent="re-search docs"),
            TraceEventSpec(kind="grep", scope=("CHANGELOG.md",), intent="re-search changelog"),
            TraceEventSpec(kind="grep", scope=("README.md",), intent="third doc search"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(stale_score_min=1),
        graph=ExpectedGraph(),
    ),

    # 5. Blind edit, no observation — Edit on src/app.py without reading it.
    TraceSpec(
        name="05_blind_edit_no_observation",
        description="Agent edits src/app.py with no prior Read. "
                    "Per A2.5, edit without observation must NOT fire progress.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="edit", scope=("src/app.py",), intent="blind edit"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(progress_events_max=0),
        graph=ExpectedGraph(),
    ),

    # 6. Repeated edit error — read then edit twice, no close.
    TraceSpec(
        name="06_repeated_edit_error",
        description="Read then two identical Edits without closing an obligation. "
                    "Second edit must NOT retrigger paper_gain (A2.4 repetition bound).",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="read", scope=("src/app.py",)),
            TraceEventSpec(kind="edit", scope=("src/app.py",), intent="first edit"),
            TraceEventSpec(kind="edit", scope=("src/app.py",), intent="same edit repeat"),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(
            progress_events_min=1, exploitation_error_min=0.2,
        ),
        graph=ExpectedGraph(),
    ),

    # 7. Import dependency missed — changed=db.py, importer=app.py;
    #    --surface=changed misses app, --surface=impact captures it.
    TraceSpec(
        name="07_import_dependency_missed",
        description="src/db.py changed; src/app.py imports src.db. "
                    "Ablation: --surface=changed sees only db; --surface=impact "
                    "sees both files AND the db→app supportive edge.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/db.py",),
        events=(
            TraceEventSpec(kind="read", scope=("src/db.py",)),
            TraceEventSpec(kind="read", scope=("src/app.py",)),
        ),
        surface=ExpectedSurface(
            changed=("src/db.py",),
            # `tests/test_db.py` doesn't exist, so related-test detection
            # does not add anything beyond the importer + db itself.
            impact=("src/db.py", "src/app.py"),
        ),
        metrics=ExpectedMetrics(progress_events_min=1),
        graph=ExpectedGraph(supportive_edges_count_min=1, has_db_to_app_edge=True),
        ablation_compare=True,
    ),

    # 8. Supportive test audit — test obligation supports source; repair on
    #    test root should AUDIT source, not reopen.
    TraceSpec(
        name="08_supportive_test_audit",
        description="tests/test_app.py obligation ↔ src/app.py obligation is "
                    "supportive only. double_loop_repair from the test event "
                    "lists the source event in 'audit', not 'reopen'.",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py", "tests/test_app.py"),
        events=(
            TraceEventSpec(kind="read", scope=("src/app.py",)),
            TraceEventSpec(kind="read", scope=("tests/test_app.py",)),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py", "tests/test_app.py"),
            impact=("src/app.py", "tests/test_app.py", "src/db.py", "src/__init__.py"),
        ),
        metrics=ExpectedMetrics(progress_events_min=1),
        graph=ExpectedGraph(supportive_edges_count_min=1),
    ),

    # 9. Migration without rollback — migration obligation expands to 4 children;
    #    only marker + migration_test_evidence verified, rollback unverified.
    TraceSpec(
        name="09_migration_without_rollback",
        description="migrations/001_init.sql changed + pytest green. Migration "
                    "obligation expands to 4 sub-preconditions; only 2 auto-verified. "
                    "Grounding partial (strictly between 0 and 1).",
        files={
            "migrations/001_init.sql": "-- CREATE TABLE users ...",
            "src/__init__.py": "",
            "tests/test_migrations.py": "def test_m(): pass\n",
        },
        changed_files=("migrations/001_init.sql",),
        events=(
            TraceEventSpec(kind="read", scope=("migrations/001_init.sql",)),
            TraceEventSpec(kind="test_run", scope=("tests/test_migrations.py",)),
        ),
        surface=ExpectedSurface(
            changed=("migrations/001_init.sql",),
            impact=("migrations/001_init.sql",),
        ),
        metrics=ExpectedMetrics(progress_events_min=1),
        graph=ExpectedGraph(),
    ),

    # 10. Corrupt plausible success — high apparent completion but a
    #     precondition obligation is never verified. grounding < 1.0.
    TraceSpec(
        name="10_corrupt_plausible_success",
        description="Agent reads target, test_run passes, commits. But the "
                    "precondition 'negative_path_tested' is NEVER verified by "
                    "Phase-3.5 evidence (needs LLM). Grounding partial; no "
                    "global 'corrupt_success' emitted (gate per A5.md).",
        files=_minimal_repo_with_db_and_app(),
        changed_files=("src/app.py",),
        events=(
            TraceEventSpec(kind="read", scope=("src/app.py",)),
            TraceEventSpec(kind="edit", scope=("src/app.py",)),
            TraceEventSpec(kind="test_run", scope=("tests/test_app.py",)),
            TraceEventSpec(kind="commit", scope=("src/app.py",)),
        ),
        surface=ExpectedSurface(
            changed=("src/app.py",),
            impact=("src/app.py", "src/db.py", "src/__init__.py", "tests/test_app.py"),
        ),
        metrics=ExpectedMetrics(progress_events_min=1),
        graph=ExpectedGraph(),
    ),
]


__all__ = [
    "SCENARIOS",
    "ExpectedGraph",
    "ExpectedMetrics",
    "ExpectedSurface",
    "TraceEventSpec",
    "TraceSpec",
    "materialize",
]
