"""Phase 5.6 §5.6-B — gateway bundle validator.

When the composite GitHub Action runs with
``enable-tool-gateway: "true"``, the operator supplies a
``gateway-bundle-dir`` containing the eight files the
``oida-code verify-grounded`` CLI needs:

* ``packet.json``
* ``pass1_forward.json``
* ``pass1_backward.json``
* ``pass2_forward.json``
* ``pass2_backward.json``
* ``tool_policy.json``
* ``gateway_definitions.json``
* ``approved_tools.json``

Bundle directories are ALWAYS treated as untrusted data.
Validation enforces:

1. All eight required files exist and are regular files.
2. No path component traverses outside ``bundle_dir``
   (``..`` segments, absolute paths, or symlinks pointing
   out are rejected).
3. No secret-shaped filename surfaces in the bundle
   (``.env`` / ``*.pem`` / ``*.key`` / ``id_rsa`` / etc.).
4. No provider configuration leaks (``provider.yml`` /
   ``provider.json`` / ``api_key.json`` / ``credentials*``).
5. No MCP configuration leaks (``mcp.yml`` /
   ``mcp_server.json`` / ``modelcontextprotocol*``).

The validator NEVER executes anything in the bundle; it
only inspects the directory listing and validates the
required-file set.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_BUNDLE_FILES: tuple[str, ...] = (
    "packet.json",
    "pass1_forward.json",
    "pass1_backward.json",
    "pass2_forward.json",
    "pass2_backward.json",
    "tool_policy.json",
    "gateway_definitions.json",
    "approved_tools.json",
)
"""The eight files the action's verify-grounded invocation
needs.  The naming convention matches QA/A33 §5.6-B (no
``gateway_`` prefix on replays — the action.yml mapping
rebinds them to the CLI's ``--forward-replay-1`` etc."""


SECRET_FILENAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.token",
    "*secret*",
    "*credentials*",
    "*credential*",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*.p12",
    "*.pfx",
    "api_key*",
)


PROVIDER_CONFIG_PATTERNS: tuple[str, ...] = (
    "provider.yml",
    "provider.yaml",
    "provider.json",
    "providers.yml",
    "providers.yaml",
    "providers.json",
    "provider_config*",
    "openai.yml",
    "anthropic.yml",
    "deepseek.yml",
)


MCP_CONFIG_PATTERNS: tuple[str, ...] = (
    "mcp.yml",
    "mcp.yaml",
    "mcp.json",
    "mcp_server*",
    "mcp_client*",
    "modelcontextprotocol*",
)


@dataclass(frozen=True)
class GatewayBundleValidationError:
    """Single validation finding — one per offending file or
    missing required entry."""

    code: str
    message: str
    offender: str = ""


@dataclass
class GatewayBundleValidationResult:
    """Aggregated outcome of one bundle validation. The
    runner is responsible for translating
    ``len(errors) > 0`` into a non-zero exit / contract
    error in the action."""

    bundle_dir: Path
    errors: list[GatewayBundleValidationError] = field(
        default_factory=list,
    )

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(
        self, code: str, message: str, *, offender: str = "",
    ) -> None:
        self.errors.append(
            GatewayBundleValidationError(
                code=code, message=message, offender=offender,
            ),
        )


def _filename_matches_any(
    name: str, patterns: tuple[str, ...],
) -> bool:
    lowered = name.lower()
    return any(
        fnmatch.fnmatchcase(lowered, p.lower())
        for p in patterns
    )


def _is_under(root: Path, candidate: Path) -> bool:
    """Return True iff ``candidate`` (resolved) is the same
    path as or a descendant of ``root`` (resolved). The
    resolution dereferences symlinks, so a symlink inside the
    bundle pointing OUT of it fails this check."""
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def validate_gateway_bundle(
    bundle_dir: Path,
    *,
    workspace_root: Path | None = None,
) -> GatewayBundleValidationResult:
    """Validate the supplied gateway bundle.

    ``workspace_root`` is the GitHub Actions
    ``$GITHUB_WORKSPACE`` (or the repo root in tests). When
    provided, every entry in ``bundle_dir`` MUST resolve
    inside it; otherwise the validator rejects the bundle.
    The check is required (the action passes
    ``GITHUB_WORKSPACE``); we keep it optional only so unit
    tests can exercise the inner rules without needing a
    workspace fixture.
    """
    result = GatewayBundleValidationResult(bundle_dir=bundle_dir)

    if not bundle_dir.exists():
        result.add(
            "bundle_dir_missing",
            (
                f"gateway-bundle-dir {bundle_dir!s} does not "
                "exist"
            ),
            offender=str(bundle_dir),
        )
        return result
    if not bundle_dir.is_dir():
        result.add(
            "bundle_dir_not_a_directory",
            (
                f"gateway-bundle-dir {bundle_dir!s} is not a "
                "directory"
            ),
            offender=str(bundle_dir),
        )
        return result

    if workspace_root is not None and not _is_under(
        workspace_root, bundle_dir,
    ):
        result.add(
            "bundle_dir_outside_workspace",
            (
                f"gateway-bundle-dir {bundle_dir!s} is not "
                f"under workspace {workspace_root!s} "
                "(path-traversal guard)"
            ),
            offender=str(bundle_dir),
        )
        return result

    # Required-file presence + per-file traversal check.
    for required in REQUIRED_BUNDLE_FILES:
        candidate = bundle_dir / required
        if not candidate.exists():
            result.add(
                "required_file_missing",
                (
                    f"required bundle file missing: {required}"
                ),
                offender=required,
            )
            continue
        if not candidate.is_file():
            result.add(
                "required_file_not_regular",
                (
                    f"required bundle entry {required} is not "
                    "a regular file"
                ),
                offender=required,
            )
            continue
        # Resolved path must stay inside bundle_dir (symlinks
        # pointing out are rejected).
        if not _is_under(bundle_dir, candidate):
            result.add(
                "path_traversal",
                (
                    f"bundle entry {required} resolves outside "
                    "gateway-bundle-dir (symlink or .. traversal)"
                ),
                offender=required,
            )

    # Sweep every file in the bundle for forbidden filename
    # shapes. The required-file set is whitelisted; everything
    # else is checked against secret / provider / MCP patterns.
    required_set = set(REQUIRED_BUNDLE_FILES)
    for entry in sorted(bundle_dir.rglob("*")):
        if not entry.is_file():
            continue
        # Resolve to canonical form to catch symlinks pointing out.
        if not _is_under(bundle_dir, entry):
            result.add(
                "path_traversal",
                (
                    f"bundle entry {entry.name} resolves outside "
                    "gateway-bundle-dir"
                ),
                offender=entry.name,
            )
            continue
        if entry.name in required_set:
            continue
        if _filename_matches_any(entry.name, SECRET_FILENAME_PATTERNS):
            result.add(
                "secret_like_path",
                (
                    f"bundle entry {entry.name} matches a "
                    "secret-shaped filename pattern"
                ),
                offender=entry.name,
            )
            continue
        if _filename_matches_any(entry.name, PROVIDER_CONFIG_PATTERNS):
            result.add(
                "provider_config",
                (
                    f"bundle entry {entry.name} looks like a "
                    "provider config; bundles are replay-only"
                ),
                offender=entry.name,
            )
            continue
        if _filename_matches_any(entry.name, MCP_CONFIG_PATTERNS):
            result.add(
                "mcp_config",
                (
                    f"bundle entry {entry.name} looks like an "
                    "MCP config; MCP is not enabled (Phase 5.6)"
                ),
                offender=entry.name,
            )
            continue

    return result


__all__ = [
    "MCP_CONFIG_PATTERNS",
    "PROVIDER_CONFIG_PATTERNS",
    "REQUIRED_BUNDLE_FILES",
    "SECRET_FILENAME_PATTERNS",
    "GatewayBundleValidationError",
    "GatewayBundleValidationResult",
    "validate_gateway_bundle",
]
