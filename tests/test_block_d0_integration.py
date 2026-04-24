"""Block D0 (QA/A7.md) — integration guards: derive_audit_surface must
actually flow through normalize / score-trace in the real CLI paths.

Without these tests, Block C primitives and Block D validation would be
exercised only on hand-injected obligations, not on the surface the
pipeline itself extracts. These guards catch the case where a code
change touches ``src/app.py`` which imports ``src/db.py``: the scenario
must contain obligations from BOTH files, and the Block-C graph must
carry ``db → app`` supportive edges.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.extract.dependencies import (
    build_impact_cone,
    derive_audit_surface,
)
from oida_code.models.audit_request import (
    AuditRequest,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.normalized_event import NormalizedScenario

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixture helper — the canonical A7.md mini-repo
# ---------------------------------------------------------------------------


def _build_mini_repo(tmp: Path) -> None:
    """src/app.py changed; src/app.py imports src.db; src/db.py has
    a guard-style precondition; tests/test_app.py exists."""
    (tmp / "src").mkdir()
    (tmp / "tests").mkdir()
    (tmp / "src" / "__init__.py").write_text("", encoding="utf-8")
    (tmp / "src" / "db.py").write_text(
        "def get_conn(host):\n"
        "    assert host, 'host required'\n"
        "    if not host.startswith('postgres'):\n"
        "        raise ValueError('unsupported db')\n"
        "    return host\n",
        encoding="utf-8",
    )
    (tmp / "src" / "app.py").write_text(
        "from src import db\n"
        "\n"
        "def create_user(host, name):\n"
        "    assert name, 'name required'\n"
        "    return db.get_conn(host), name\n",
        encoding="utf-8",
    )
    (tmp / "tests" / "test_app.py").write_text(
        "def test_create_user():\n    assert True\n",
        encoding="utf-8",
    )


def _write_request(tmp: Path, *, changed: list[str]) -> Path:
    req = AuditRequest(
        repo=RepoSpec(
            path=str(tmp), revision="HEAD", base_revision="HEAD^"
        ),
        scope=ScopeSpec(changed_files=changed, language="python"),
    )
    req_path = tmp / "audit_request.json"
    req_path.write_text(req.model_dump_json(indent=2), encoding="utf-8")
    return req_path


# ---------------------------------------------------------------------------
# D0 test 1 — normalize uses impact cone for obligation extraction
# ---------------------------------------------------------------------------


def _scope_files(scenario: NormalizedScenario) -> set[str]:
    """Extract the file-half of each event's pattern_id slug.

    pattern_id format is ``p_{kind}_{sluggified_scope}_{digest}`` where
    the slug replaces ``.``, ``:``, and ``/`` with ``_``. We recover
    candidate file paths by finding the ``_py`` marker and reconstructing.
    """
    files: set[str] = set()
    for ev in scenario.events:
        slug = ev.pattern_id
        # Look for a contiguous "...foo_py..." substring and reconstruct.
        # Slug tokens: kind/scope/digest separated by `_`; the scope
        # contains tokens like `src_app_py_f`. We keep the check loose.
        if "_py_" in slug or slug.endswith("_py"):
            # approximate: split on `_py`, first segment back to the
            # file name; flatten "src_app" → "src/app.py".
            head = slug.split("_py", 1)[0]
            # head looks like "p_precondition_src_app"; drop the first
            # two tokens (prefix + kind).
            parts = head.split("_", 2)
            if len(parts) >= 3:
                dir_and_file = parts[2].replace("_", "/")
                files.add(f"{dir_and_file}.py")
    return files


def test_normalize_uses_impact_cone_for_obligation_extraction(
    tmp_path: Path,
) -> None:
    """Changing only ``src/app.py`` must still extract obligations from
    ``src/db.py`` (reached via direct import). Pre-D0, extraction was
    limited to changed_files."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/app.py"])

    result = runner.invoke(app, ["normalize", str(req_path)])
    assert result.exit_code == 0, result.output

    start = result.output.find("{")
    end = result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(result.output[start : end + 1])
    files = _scope_files(scenario)
    assert "src/app.py" in files, (
        f"expected src/app.py obligation; recovered files: {files}"
    )
    assert "src/db.py" in files, (
        f"D0 violated: src/db.py not in extraction surface though "
        f"src/app.py imports it. recovered files: {files}"
    )


# ---------------------------------------------------------------------------
# D0 test 2 — end-to-end: imported file gets obligations + supportive edge
# ---------------------------------------------------------------------------


def test_changed_app_imports_db_creates_db_obligation_and_supportive_edge(
    tmp_path: Path,
) -> None:
    """The canonical A7.md crown-jewel test: after normalize, the
    scenario must contain BOTH app and db obligations, AND the graph
    must carry ``db_event → app_event`` supportive edges
    (direct_import)."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/app.py"])
    result = runner.invoke(app, ["normalize", str(req_path)])
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(result.output[start : end + 1])

    app_events = [e for e in scenario.events if "app" in e.pattern_id]
    db_events = [e for e in scenario.events if "db" in e.pattern_id]
    assert app_events, "no obligations extracted from src/app.py"
    assert db_events, "no obligations extracted from src/db.py via impact cone"

    # The supportive edges must include at least one db → app link.
    app_event_ids = {e.id for e in app_events}
    db_event_ids = {e.id for e in db_events}
    has_support_edge = any(
        parent in db_event_ids and ev.id in app_event_ids
        for ev in scenario.events
        for parent in ev.supportive_parents
    )
    assert has_support_edge, (
        "D0 violated: no supportive edge from db_event to app_event; "
        f"app_events={app_event_ids} db_events={db_event_ids}"
    )


# ---------------------------------------------------------------------------
# D0 test 3 — --surface=changed preserves legacy behavior
# ---------------------------------------------------------------------------


def test_changed_mode_preserves_previous_changed_files_only_behavior(
    tmp_path: Path,
) -> None:
    """``--surface=changed`` must NOT expand into imports/tests. This is
    the regression guard for the legacy flow — users who want the exact
    diff surface must still have it."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/app.py"])

    result = runner.invoke(
        app, ["normalize", str(req_path), "--surface", "changed"]
    )
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(result.output[start : end + 1])
    files = _scope_files(scenario)
    assert "src/app.py" in files
    assert "src/db.py" not in files, (
        f"--surface=changed must NOT expand into imports; got {files}"
    )


# ---------------------------------------------------------------------------
# D0 test 4 — score-trace --request uses impact surface, not a heuristic
# ---------------------------------------------------------------------------


def test_score_trace_request_uses_impact_surface_not_first_15_paths(
    tmp_path: Path,
) -> None:
    """When ``score-trace`` is given ``--request``, the trajectory U(t)
    must be bounded by the impact surface derived from the request's
    changed_files, not by the first 15 paths in the transcript or the
    raw changed_files alone."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/app.py"])

    # Minimal Claude Code transcript that reads both app.py and db.py.
    transcript_records = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "u1",
                        "name": "Read",
                        "input": {"file_path": "src/app.py"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "u1",
                        "content": "file contents",
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "u2",
                        "name": "Read",
                        "input": {"file_path": "src/db.py"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "u2",
                        "content": "db file contents",
                    }
                ]
            },
        },
    ]
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text(
        "\n".join(json.dumps(r) for r in transcript_records) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["score-trace", str(transcript_path), "--request", str(req_path)],
    )
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    payload = json.loads(result.output[start : end + 1])
    # With impact surface, both Reads hit paths in U(t) → both are
    # progress events.
    assert payload["progress_events_count"] >= 2, (
        f"expected ≥2 progress events via impact surface; "
        f"progress_events={payload.get('progress_events_count')}"
    )
    # total_steps matches the transcript.
    assert payload["total_steps"] == 2


# ---------------------------------------------------------------------------
# D0 test 5 — derive_audit_surface is bounded and reasoned
# ---------------------------------------------------------------------------


def test_impact_surface_is_bounded_and_reasoned(tmp_path: Path) -> None:
    """``derive_audit_surface(mode='impact')`` must return a bounded
    list of paths whose underlying impact cone tags every entry with
    a valid reason."""
    _build_mini_repo(tmp_path)

    surface = derive_audit_surface(
        tmp_path, ["src/app.py"], mode="impact", max_files=50
    )
    assert len(surface) <= 50
    # Must contain the changed file itself and the imported module.
    assert "src/app.py" in surface
    assert "src/db.py" in surface

    # max_files cap honored.
    capped = derive_audit_surface(
        tmp_path, ["src/app.py"], mode="impact", max_files=2
    )
    assert len(capped) == 2

    # Every entry carries a valid reason per build_impact_cone.
    cone = build_impact_cone(tmp_path, ["src/app.py"])
    valid_reasons = {
        "changed",
        "imports_changed",
        "imported_by_changed",
        "related_test",
        "config",
        "migration",
    }
    for entry in cone:
        assert entry.reason in valid_reasons
    # And mode="changed" is pass-through, no expansion.
    changed_only = derive_audit_surface(
        tmp_path, ["src/app.py"], mode="changed"
    )
    assert changed_only == ["src/app.py"]


# ---------------------------------------------------------------------------
# D0.1 — reverse direction: dependency changed, importer reached via cone
# ---------------------------------------------------------------------------


def test_changed_dependency_imported_by_app_creates_importer_surface(
    tmp_path: Path,
) -> None:
    """A7.md reverse case: when ``src/db.py`` is the changed file and
    ``src/app.py`` imports it, the impact surface must include app.py
    as ``imported_by_changed``."""
    _build_mini_repo(tmp_path)
    cone = build_impact_cone(tmp_path, ["src/db.py"])
    by_path = {e.path: e.reason for e in cone}
    assert by_path.get("src/db.py") == "changed"
    assert by_path.get("src/app.py") == "imported_by_changed", (
        f"expected src/app.py as imported_by_changed; cone={by_path}"
    )


def test_normalize_graph_uses_impact_surface_for_importer_edges(
    tmp_path: Path,
) -> None:
    """D0.1 crown jewel: when ``src/db.py`` is the changed file and
    ``src/app.py`` imports it, the scenario must have a supportive
    edge ``db_event → app_event`` with reason=direct_import. Pre-D0.1,
    build_dependency_graph was called with the raw diff so it only
    scanned db.py (which has no outgoing imports) and missed app.py
    entirely — even though the extractor had already picked up
    obligations on app.py via the impact surface."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/db.py"])

    result = runner.invoke(app, ["normalize", str(req_path)])
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(result.output[start : end + 1])

    app_events = [e for e in scenario.events if "app" in e.pattern_id]
    db_events = [e for e in scenario.events if "db" in e.pattern_id]
    assert app_events, "D0 failure: no obligations extracted from src/app.py"
    assert db_events, "no obligations extracted from src/db.py"

    # The supportive edge must exist: db_event → app_event.
    app_ids = {e.id for e in app_events}
    db_ids = {e.id for e in db_events}
    has_db_to_app_edge = any(
        parent in db_ids and ev.id in app_ids
        for ev in scenario.events
        for parent in ev.supportive_parents
    )
    assert has_db_to_app_edge, (
        "D0.1 violated: reverse-direction edge db → app missing. "
        "build_dependency_graph must scan the impact surface, not the "
        "raw changed_files."
    )


def test_normalize_changed_mode_does_not_create_importer_edge(
    tmp_path: Path,
) -> None:
    """``--surface=changed`` must preserve the legacy behavior: when
    only ``src/db.py`` is in the raw diff, no ``src/app.py`` obligation
    is extracted and no importer edge is created."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/db.py"])

    result = runner.invoke(
        app, ["normalize", str(req_path), "--surface", "changed"]
    )
    assert result.exit_code == 0, result.output
    start = result.output.find("{")
    end = result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(result.output[start : end + 1])

    files = _scope_files(scenario)
    assert "src/db.py" in files
    assert "src/app.py" not in files, (
        f"--surface=changed must NOT expand to importers; got {files}"
    )
    # No supportive edges from any db event to any app event
    # (app events don't even exist in this mode).
    for ev in scenario.events:
        for parent in ev.supportive_parents:
            assert parent in {e.id for e in scenario.events}, (
                "every parent id must reference an existing event"
            )


def test_score_trace_surface_flag_accepts_both_modes(tmp_path: Path) -> None:
    """D0.1: ``score-trace --surface {impact,changed}`` must both be
    accepted and produce different U(t) bounds."""
    _build_mini_repo(tmp_path)
    req_path = _write_request(tmp_path, changed=["src/db.py"])
    transcript = tmp_path / "t.jsonl"
    # Minimal 1-event transcript touching src/app.py (which is in
    # impact surface but NOT in changed diff).
    records = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "u1",
                        "name": "Read",
                        "input": {"file_path": "src/app.py"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "u1",
                        "content": "ok",
                    }
                ]
            },
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )

    # impact mode: src/app.py IS in U(t) → progress
    impact_res = runner.invoke(
        app,
        [
            "score-trace",
            str(transcript),
            "--request",
            str(req_path),
            "--surface",
            "impact",
        ],
    )
    assert impact_res.exit_code == 0, impact_res.output
    impact_payload = json.loads(
        impact_res.output[impact_res.output.find("{") : impact_res.output.rfind("}") + 1]
    )
    assert impact_payload["progress_events_count"] >= 1, (
        "impact surface must include src/app.py so Read of it registers as progress"
    )

    # changed mode: src/app.py NOT in U(t) → no progress from reading it
    changed_res = runner.invoke(
        app,
        [
            "score-trace",
            str(transcript),
            "--request",
            str(req_path),
            "--surface",
            "changed",
        ],
    )
    assert changed_res.exit_code == 0, changed_res.output
    changed_payload = json.loads(
        changed_res.output[changed_res.output.find("{") : changed_res.output.rfind("}") + 1]
    )
    assert changed_payload["progress_events_count"] == 0, (
        "changed mode bounds U(t) to raw diff; reading src/app.py "
        "(outside the diff) must NOT register as progress"
    )
