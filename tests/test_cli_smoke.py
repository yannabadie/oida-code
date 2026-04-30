"""Smoke tests for the ``oida-code`` Typer CLI."""

from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.models import AuditRequest

# Phase 4.5.2 real-runner fix: pin a wide terminal so Rich panels
# never wrap option names. `COLUMNS=200` is read by Rich's
# `shutil.get_terminal_size()` fallback when the captured pipe
# isn't a TTY. We do NOT rely on NO_COLOR alone — Rich still emits
# bold/dim ANSI codes under NO_COLOR, and typer's
# `OptionHighlighter` styles the leading dashes and the name
# separately, producing e.g. `\x1b[1m--\x1b[0mbase` where `--base`
# is no longer a contiguous substring. The robust fix is to strip
# ANSI escape sequences from `result.output` before any substring
# check.
runner = CliRunner(env={"COLUMNS": "200"})

# ANSI CSI sequence: ESC [ <params> <final-byte (0x40-0x7E)>. Covers
# bold/dim/colour/reset and the wider SGR family. Conservative
# enough that we don't accidentally chew through real text.
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(text: str) -> str:
    """Return ``text`` with ANSI CSI escape sequences removed.

    Used to make help-text substring assertions robust against
    Rich's per-segment styling on the GHA Linux runner."""
    return _ANSI_CSI_RE.sub("", text)


def test_inspect_help_shows() -> None:
    result = runner.invoke(app, ["inspect", "--help"])
    assert result.exit_code == 0, result.output
    plain = _plain(result.output)
    assert "inspect" in plain.lower()
    assert "--base" in plain


def test_top_level_help_shows() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    plain = _plain(result.output)
    assert "inspect" in plain
    assert "Diagnostic evidence for Python code reviewers" in plain
    assert "AI code verifier" not in plain
    assert "guaranteed behavior" not in plain


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert "oida-code" in result.output


def test_inspect_emits_valid_audit_request(tmp_path_factory: object) -> None:
    # The project itself is a git repo; run inspect against its root.
    from tests.conftest import REPO_ROOT

    result = runner.invoke(
        app,
        ["inspect", str(REPO_ROOT), "--base", "HEAD"],
    )
    assert result.exit_code == 0, result.output

    # Typer's CliRunner may prefix with ANSI; locate the JSON object.
    start = result.output.find("{")
    end = result.output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {result.output!r}"
    payload = result.output[start : end + 1]

    parsed = json.loads(payload)
    request = AuditRequest.model_validate(parsed)
    assert request.repo.revision, "revision must be resolved"
    assert request.repo.base_revision == request.repo.revision, (
        "--base HEAD yields an empty diff on a single-branch HEAD"
    )
    assert request.scope.language == "python"
    # changed_files is empty when base == head, which is expected.
    assert request.scope.changed_files == []


def test_unimplemented_phase5_subcommand_raises() -> None:
    """``repair`` remains Phase 5 work; only it should still error out."""
    result = runner.invoke(app, ["repair", "."])
    assert result.exit_code != 0
    assert result.exception is not None
    assert "compatibility stub only" in str(result.exception)


def test_normalize_emits_valid_scenario(tmp_path, tmp_path_factory: object) -> None:
    """``normalize`` consumes an AuditRequest and emits a NormalizedScenario."""
    from oida_code.models.normalized_event import NormalizedScenario
    from tests.conftest import REPO_ROOT

    # Produce a request against the self-repo (base=HEAD yields empty diff,
    # so the scenario will have zero events — that's a valid shape).
    inspect_result = runner.invoke(
        app, ["inspect", str(REPO_ROOT), "--base", "HEAD"]
    )
    assert inspect_result.exit_code == 0, inspect_result.output
    req_path = tmp_path / "req.json"
    start = inspect_result.output.find("{")
    end = inspect_result.output.rfind("}")
    req_path.write_text(inspect_result.output[start : end + 1], encoding="utf-8")

    norm_result = runner.invoke(app, ["normalize", str(req_path)])
    assert norm_result.exit_code == 0, norm_result.output

    start = norm_result.output.find("{")
    end = norm_result.output.rfind("}")
    scenario = NormalizedScenario.model_validate_json(
        norm_result.output[start : end + 1]
    )
    # base=HEAD ⇒ empty diff ⇒ no obligations ⇒ 0 events (valid shape).
    assert scenario.events == []
