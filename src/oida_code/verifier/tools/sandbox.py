"""Phase 4.2-B (QA/A18.md, ADR-27) — sandbox helpers.

Path validation, deny-pattern matching, output truncation + hashing.
Pure functions; never raise vendor exceptions.
"""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

from oida_code.verifier.tools.contracts import ToolPolicy, VerifierToolRequest


class SandboxViolation(Exception):
    """Raised by ``validate_request`` when a request fails policy."""


def _normalise(p: str) -> str:
    """Forward-slash + strip a leading ``./`` (NOT ``.``) prefix.

    Critical: do NOT use :meth:`str.lstrip` — that would strip every
    leading ``.`` / ``/`` character set, turning ``.env`` into ``env``
    and defeating the deny-pattern check for dotfiles.
    """
    forward = p.replace("\\", "/")
    while forward.startswith("./"):
        forward = forward[2:]
    return forward


def _is_under(root: Path, candidate: Path) -> bool:
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return False
    try:
        resolved.relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _matches_any_deny(rel_path: str, deny_patterns: tuple[str, ...]) -> str | None:
    """Return the matching pattern (or None) — kept lazy so we can
    log which rule blocked the request."""
    norm = _normalise(rel_path)
    name = norm.rsplit("/", 1)[-1]
    for pattern in deny_patterns:
        # Match against the basename AND the full relative path.
        if fnmatch.fnmatch(name, pattern):
            return pattern
        if fnmatch.fnmatch(norm, pattern):
            return pattern
    return None


def _matches_any_allow(rel_path: str, allowed_paths: tuple[str, ...]) -> bool:
    """Empty allowlist means "everything under repo_root is allowed"
    (the path-traversal check still runs separately)."""
    if not allowed_paths:
        return True
    norm = _normalise(rel_path)
    for pattern in allowed_paths:
        norm_p = _normalise(pattern)
        if norm == norm_p:
            return True
        if fnmatch.fnmatch(norm, norm_p):
            return True
        if norm.startswith(norm_p.rstrip("/") + "/"):
            return True
    return False


def validate_request(
    request: VerifierToolRequest,
    policy: ToolPolicy,
) -> None:
    """Raise :class:`SandboxViolation` if ``request`` fails policy.

    Checked in order:

    1. tool is in ``policy.allowed_tools``
    2. write/network defaults
    3. every path in ``scope`` resolves under ``policy.repo_root``
       (no path traversal)
    4. every path passes deny-pattern checks
    5. every path passes allowed-paths check
    """
    if request.tool not in policy.allowed_tools:
        raise SandboxViolation(
            f"tool {request.tool!r} not in policy.allowed_tools "
            f"{list(policy.allowed_tools)}"
        )
    if policy.allow_write:
        raise SandboxViolation(
            "policy.allow_write must be False in Phase 4.2 (read-only)"
        )
    if policy.allow_network:
        raise SandboxViolation(
            "policy.allow_network must be False in Phase 4.2"
        )
    repo_root = policy.repo_root
    for raw in request.scope:
        # Detect absolute paths BEFORE normalising — `_normalise`
        # strips leading `/` and `.` so the absolute check has to look
        # at the raw input. Handles POSIX `/etc/...` and Windows `C:\...`.
        raw_str = str(raw)
        forwarded = raw_str.replace("\\", "/")
        if (
            raw_str.startswith("/")
            or raw_str.startswith("\\")
            or Path(forwarded).is_absolute()
        ):
            raise SandboxViolation(
                f"absolute scope entry not allowed: {raw!r}"
            )
        rel = _normalise(raw_str)
        if not rel:
            raise SandboxViolation("empty scope entry")
        if ".." in Path(rel).parts:
            raise SandboxViolation(
                f"scope entry contains path traversal: {raw!r}"
            )
        candidate = repo_root / rel
        if not _is_under(repo_root, candidate):
            raise SandboxViolation(
                f"scope entry resolves outside repo_root: {raw!r}"
            )
        denied = _matches_any_deny(rel, policy.deny_patterns)
        if denied is not None:
            raise SandboxViolation(
                f"scope entry {raw!r} matches deny pattern {denied!r}"
            )
        if not _matches_any_allow(rel, policy.allowed_paths):
            raise SandboxViolation(
                f"scope entry {raw!r} not in policy.allowed_paths"
            )


def truncate_and_hash(
    output: str, max_chars: int,
) -> tuple[str, bool, str]:
    """Truncate ``output`` to ``max_chars`` and return SHA256 of the
    full original payload. Returns ``(truncated_text, was_truncated,
    sha256_hex)``. Hash is computed on the FULL payload so a downstream
    integrator can detect tampering."""
    full = output if isinstance(output, str) else str(output)
    digest = hashlib.sha256(full.encode("utf-8", errors="replace")).hexdigest()
    if len(full) <= max_chars:
        return full, False, digest
    truncated = full[:max_chars] + "\n... [truncated]"
    return truncated, True, digest


__all__ = [
    "SandboxViolation",
    "truncate_and_hash",
    "validate_request",
]
