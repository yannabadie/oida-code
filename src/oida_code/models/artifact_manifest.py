"""Phase 4.9-F (QA/A26.md, ADR-34) — artifact bundle manifest.

Frozen Pydantic shapes describing the bundle of outputs an
``oida-code`` action / CLI run produces. The manifest is written
to ``.oida/artifacts/manifest.json`` and lists every artifact
along with:

* a SHA256 of the file as it sits on disk (so downstream
  consumers can detect tampering between when the manifest was
  written and when they read the artifact);
* the ``kind`` enum (json_report / markdown_report / sarif /
  calibration_metrics / redacted_io / label_audit / step_summary);
* hard-pinned safety flags that the renderer is statically
  prevented from violating: ``contains_secrets: Literal[False]``,
  ``official_fields_emitted: Literal[False]``,
  ``mode: Literal["diagnostic_only"]``.

The two ``Literal[False]`` fields use the same trick as ADR-22's
shadow-fusion ``authoritative`` field — the type system rejects
any attempt to construct a manifest with them set to True. A
schema migration is the only way to relax that, and any such
migration would require an ADR.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactKind = Literal[
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
]
"""The closed set of artifact kinds Phase 4.9-F can describe.
QA/A26 line 376-384 prescribes the first seven; we extend with
``diagnostic_markdown`` (Phase 4.9-A) + ``action_outputs`` (Phase
4.9-D) + ``stability_summary`` (Phase 4.8-E) so the manifest
covers every file the action actually produces."""


class ArtifactRef(BaseModel):
    """One artifact in the bundle. The ``contains_secrets`` field
    is pinned to ``Literal[False]`` so a manifest with secrets-
    bearing artifacts is unrepresentable; if a future artifact
    type would carry secrets, an ADR + schema bump is required."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    kind: ArtifactKind
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    contains_secrets: Literal[False] = False
    contains_raw_prompt: bool = False
    contains_raw_response: bool = False


class ArtifactBundleManifest(BaseModel):
    """The manifest itself. ``mode`` is pinned to
    ``"diagnostic_only"`` and ``official_fields_emitted`` to
    ``False`` — both via Literal so ``model_validate`` rejects any
    other value at runtime, locking the ADR-22 hard wall into the
    manifest schema as well as the audit/calibration outputs."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    schema_version: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    mode: Literal["diagnostic_only"] = "diagnostic_only"
    official_fields_emitted: Literal[False] = False
    files: tuple[ArtifactRef, ...] = Field(default_factory=tuple)
    provider: str | None = None
    model: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)


# Map filename / suffix patterns to their ``kind``. The first match
# wins. Generic patterns last.
_KIND_PATTERNS: tuple[tuple[str, ArtifactKind], ...] = (
    ("action_outputs.txt", "action_outputs"),
    ("stability_summary.json", "stability_summary"),
    ("metrics.json", "calibration_metrics"),
    ("diagnostic.md", "diagnostic_markdown"),
    ("step_summary.md", "step_summary"),
    ("provider_label_audit", "label_audit"),
    ("report.json", "json_report"),
    ("report.md", "markdown_report"),
    ("report.sarif", "sarif"),
    (".sarif", "sarif"),
)


def _classify_filename(name: str) -> ArtifactKind | None:
    """Return the kind that best matches ``name``. ``redacted_io``
    is detected by the parent directory in :func:`build_manifest`,
    not by filename alone, so it is not in the patterns list."""
    lower = name.lower()
    for pattern, kind in _KIND_PATTERNS:
        if pattern in lower:
            return kind
    return None


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA256 of ``path``. Reads in
    chunks so a large SARIF file does not balloon RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with the trailing ``Z`` suffix.
    Used as ``generated_at``; tests assert the suffix to lock the
    timezone (no naive timestamps in artifacts)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(
    bundle_root: Path,
    *,
    schema_version: str = "1.0.0",
    provider: str | None = None,
    model: str | None = None,
    warnings: tuple[str, ...] = (),
    manifest_relative_path: str = "artifacts/manifest.json",
) -> ArtifactBundleManifest:
    """Walk ``bundle_root`` and build a manifest covering every
    artifact under it (recursively). The manifest file ITSELF is
    excluded from the file list — otherwise the manifest's hash
    would have to include its own hash (a chicken-and-egg).

    ``redacted_io`` files are classified by their parent directory
    name being ``redacted_io``. All other files are classified by
    :func:`_classify_filename`; unknown files are silently skipped
    so that auxiliary artifacts (e.g., per-case logs the operator
    drops in) do not blow up the manifest build.
    """
    manifest_path = (bundle_root / manifest_relative_path).resolve()
    files: list[ArtifactRef] = []
    for path in sorted(bundle_root.rglob("*")):
        if not path.is_file():
            continue
        # Exclude the manifest itself + any .git / __pycache__ noise.
        resolved = path.resolve()
        if resolved == manifest_path:
            continue
        rel_parts = path.relative_to(bundle_root).parts
        if any(part in (".git", "__pycache__") for part in rel_parts):
            continue
        # redacted_io classification — parent dir wins.
        if "redacted_io" in rel_parts:
            kind: ArtifactKind = "redacted_io"
        else:
            classified = _classify_filename(path.name)
            if classified is None:
                continue
            kind = classified
        files.append(
            ArtifactRef(
                kind=kind,
                path=path.relative_to(bundle_root).as_posix(),
                sha256=sha256_of_file(path),
                contains_raw_prompt=False,
                contains_raw_response=False,
            ),
        )
    return ArtifactBundleManifest(
        schema_version=schema_version,
        generated_at=_utc_now_iso(),
        files=tuple(files),
        provider=provider,
        model=model,
        warnings=warnings,
    )


def write_manifest(
    bundle_root: Path,
    *,
    schema_version: str = "1.0.0",
    provider: str | None = None,
    model: str | None = None,
    warnings: tuple[str, ...] = (),
    manifest_relative_path: str = "artifacts/manifest.json",
) -> Path:
    """Build the manifest, write it under
    ``<bundle_root>/<manifest_relative_path>`` (default
    ``.oida/artifacts/manifest.json`` when ``bundle_root=.oida``),
    and return the resulting path. The function creates parent
    directories as needed; the manifest file overwrites any
    previous one."""
    manifest = build_manifest(
        bundle_root,
        schema_version=schema_version,
        provider=provider,
        model=model,
        warnings=warnings,
        manifest_relative_path=manifest_relative_path,
    )
    out_path = bundle_root / manifest_relative_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8",
    )
    return out_path


__all__ = [
    "ArtifactBundleManifest",
    "ArtifactKind",
    "ArtifactRef",
    "build_manifest",
    "sha256_of_file",
    "write_manifest",
]
