"""Phase 4.9-F (QA/A26.md, ADR-34) — artifact bundle manifest tests.

Hard invariants:

* The manifest pins ``mode = "diagnostic_only"`` and
  ``official_fields_emitted = False`` via Literal — any other
  value is rejected at construction time.
* Every ``ArtifactRef`` pins ``contains_secrets = False`` via
  Literal.
* The manifest lists every artifact under the bundle root,
  excluding the manifest file itself (chicken-and-egg).
* The recorded SHA256 matches the file's actual hash on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from oida_code.models.artifact_manifest import (
    ArtifactBundleManifest,
    ArtifactRef,
    build_manifest,
    sha256_of_file,
    write_manifest,
)


def _seed_bundle(tmp_path: Path) -> Path:
    """Materialise a synthetic .oida bundle on disk."""
    bundle = tmp_path / ".oida"
    bundle.mkdir()
    (bundle / "report.json").write_text('{"audit": "stub"}', encoding="utf-8")
    (bundle / "report.md").write_text("# stub", encoding="utf-8")
    (bundle / "report.sarif").write_text('{"version":"2.1.0"}', encoding="utf-8")
    (bundle / "diagnostic.md").write_text(
        "# OIDA-code Diagnostic Report\nDiagnostic only — not a merge verdict.\n",
        encoding="utf-8",
    )
    cal = bundle / "calibration"
    cal.mkdir()
    (cal / "metrics.json").write_text(
        '{"cases_total": 8, "official_field_leak_count": 0}',
        encoding="utf-8",
    )
    (cal / "action_outputs.txt").write_text(
        "diagnostic-status=contract_clean\nofficial-field-leaks=0\n",
        encoding="utf-8",
    )
    (cal / "stability_summary.json").write_text(
        '{"n_runs": 2}', encoding="utf-8",
    )
    redacted_io = cal / "redacted_io"
    redacted_io.mkdir()
    (redacted_io / "L001.json").write_text(
        '{"prompt_sha256": "0", "failure_kind": "success"}',
        encoding="utf-8",
    )
    (redacted_io / "L002.json").write_text(
        '{"prompt_sha256": "1", "failure_kind": "invalid_shape"}',
        encoding="utf-8",
    )
    return bundle


# ---------------------------------------------------------------------------
# QA/A26 §4.9-F mandatory tests
# ---------------------------------------------------------------------------


def test_artifact_manifest_lists_all_outputs(tmp_path: Path) -> None:
    """Every artifact under the bundle root must appear in the
    manifest (modulo the manifest file itself + classification-
    excluded files like .git noise)."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    paths = {ref.path for ref in manifest.files}
    expected_paths = {
        "report.json",
        "report.md",
        "report.sarif",
        "diagnostic.md",
        "calibration/metrics.json",
        "calibration/action_outputs.txt",
        "calibration/stability_summary.json",
        "calibration/redacted_io/L001.json",
        "calibration/redacted_io/L002.json",
    }
    missing = expected_paths - paths
    assert not missing, (
        f"manifest is missing artifacts: {missing!r}; got {paths!r}"
    )


def test_artifact_manifest_hashes_existing_files(tmp_path: Path) -> None:
    """Each ArtifactRef's sha256 MUST match the actual file hash."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    for ref in manifest.files:
        actual = sha256_of_file(bundle / ref.path)
        assert ref.sha256 == actual, (
            f"manifest hash mismatch for {ref.path}: "
            f"manifest={ref.sha256}, actual={actual}"
        )
        assert len(ref.sha256) == 64
        # All-lowercase hex.
        assert ref.sha256 == ref.sha256.lower()


def test_artifact_manifest_contains_secrets_false(tmp_path: Path) -> None:
    """Every ArtifactRef MUST have contains_secrets=False, AND the
    schema MUST reject any attempt to construct it with True."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    for ref in manifest.files:
        assert ref.contains_secrets is False
    # The Literal[False] pin REJECTS True at construction.
    with pytest.raises(ValidationError):
        ArtifactRef(
            kind="json_report",
            path="x.json",
            sha256="0" * 64,
            contains_secrets=True,  # type: ignore[arg-type]
        )


def test_artifact_manifest_official_fields_false(tmp_path: Path) -> None:
    """The manifest MUST have official_fields_emitted=False AND
    mode='diagnostic_only', both as Literal pins."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    assert manifest.official_fields_emitted is False
    assert manifest.mode == "diagnostic_only"

    # The Literal[False] pin REJECTS True at construction.
    with pytest.raises(ValidationError):
        ArtifactBundleManifest(
            schema_version="1.0.0",
            generated_at="2026-04-26T00:00:00Z",
            official_fields_emitted=True,  # type: ignore[arg-type]
        )
    # Mode pin: "diagnostic_only" is the only allowed value.
    with pytest.raises(ValidationError):
        ArtifactBundleManifest(
            schema_version="1.0.0",
            generated_at="2026-04-26T00:00:00Z",
            mode="merge_safe",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Backstops
# ---------------------------------------------------------------------------


def test_manifest_excludes_itself(tmp_path: Path) -> None:
    """Writing the manifest at its default path MUST NOT include
    the manifest in its own file list (chicken-and-egg)."""
    bundle = _seed_bundle(tmp_path)
    manifest_path = write_manifest(bundle)
    assert manifest_path == bundle / "artifacts" / "manifest.json"
    assert manifest_path.is_file()
    # Re-read and parse.
    parsed = ArtifactBundleManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8"),
    )
    paths = {ref.path for ref in parsed.files}
    assert "artifacts/manifest.json" not in paths, (
        "manifest file lists itself — chicken-and-egg hash problem"
    )


def test_manifest_classifies_redacted_io_by_parent_dir(
    tmp_path: Path,
) -> None:
    """Files under any `redacted_io/` directory MUST be classified
    as `redacted_io` regardless of their filename."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    redacted_refs = [
        ref for ref in manifest.files
        if "redacted_io" in ref.path
    ]
    assert len(redacted_refs) == 2
    for ref in redacted_refs:
        assert ref.kind == "redacted_io"


def test_manifest_classifies_known_kinds(tmp_path: Path) -> None:
    """Each known artifact type maps to the expected kind."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    by_path = {ref.path: ref for ref in manifest.files}
    assert by_path["report.json"].kind == "json_report"
    assert by_path["report.md"].kind == "markdown_report"
    assert by_path["report.sarif"].kind == "sarif"
    assert by_path["diagnostic.md"].kind == "diagnostic_markdown"
    assert by_path["calibration/metrics.json"].kind == "calibration_metrics"
    assert by_path["calibration/action_outputs.txt"].kind == "action_outputs"
    assert by_path["calibration/stability_summary.json"].kind == "stability_summary"


def test_manifest_generated_at_is_utc_iso(tmp_path: Path) -> None:
    """The generated_at field MUST end in `Z` (UTC) so consumers
    can parse it without guessing the timezone."""
    bundle = _seed_bundle(tmp_path)
    manifest = build_manifest(bundle)
    assert manifest.generated_at.endswith("Z")
    # Parseable as ISO-8601.
    from datetime import datetime
    datetime.strptime(manifest.generated_at, "%Y-%m-%dT%H:%M:%SZ")


def test_cli_build_artifact_manifest_writes_file(tmp_path: Path) -> None:
    """`oida-code build-artifact-manifest <bundle>` MUST land a
    valid manifest at the default path."""
    from typer.testing import CliRunner

    from oida_code.cli import app

    bundle = _seed_bundle(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "build-artifact-manifest", str(bundle),
            "--provider", "deepseek-v4-flash",
            "--model", "deepseek-v4-flash",
        ],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    manifest_path = bundle / "artifacts" / "manifest.json"
    assert manifest_path.is_file()
    parsed = ArtifactBundleManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8"),
    )
    assert parsed.provider == "deepseek-v4-flash"
    assert parsed.model == "deepseek-v4-flash"
    assert parsed.mode == "diagnostic_only"
    assert parsed.official_fields_emitted is False


def test_manifest_skips_unknown_artifact_kinds(tmp_path: Path) -> None:
    """Files that do not match any known classification pattern
    MUST be silently skipped — not crash the manifest build."""
    bundle = tmp_path / ".oida"
    bundle.mkdir()
    (bundle / "report.json").write_text('{}', encoding="utf-8")
    (bundle / "random_log.txt").write_text("noise", encoding="utf-8")
    manifest = build_manifest(bundle)
    paths = {ref.path for ref in manifest.files}
    assert "report.json" in paths
    assert "random_log.txt" not in paths


def test_artifact_kind_enum_is_closed() -> None:
    """The ArtifactKind Literal MUST contain exactly the documented
    set; adding a new kind requires touching this test."""
    import typing

    from oida_code.models.artifact_manifest import ArtifactKind
    assert set(typing.get_args(ArtifactKind)) == {
        "json_report",
        "markdown_report",
        "sarif",
        "calibration_metrics",
        "redacted_io",
        "label_audit",
        "step_summary",
        "diagnostic_markdown",
        "action_outputs",
        "stability_summary",
    }
