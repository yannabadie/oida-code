"""Extract :class:`Obligation` objects from source files (Phase 2, PLAN.md §8).

Three extractor-backed kinds ship in Phase 2 (ADR-15 locks the scope):

* ``precondition`` — AST detects:
  - top-level ``assert`` inside a function
  - ``if <cond>: raise`` guards
  - methods decorated with ``@field_validator`` / ``@validates`` (pydantic + SQLAlchemy)
* ``api_contract`` — AST detects functions decorated with route-family decorators:
  ``@app.route``, ``@app.get``, ``@router.(get|post|put|patch|delete)``,
  ``@blueprint.route``, ``@api.route`` (Flask + FastAPI + Starlette-style).
* ``migration`` — path-marker scan reusing
  :mod:`oida_code.extract.blast_radius`'s ``_DATA_MARKERS`` (migration dirs,
  ``.sql`` files, alembic, schema, db, models).

The extractor is **syntactic**: it does not resolve imports or run code. It
returns stable-sorted :class:`Obligation` instances with deterministic IDs.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from oida_code.extract.blast_radius import _DATA_MARKERS
from oida_code.models.obligation import EvidenceRequirement, Obligation

_ROUTE_ATTRS = frozenset(
    {"route", "get", "post", "put", "patch", "delete", "head", "options"}
)
_ROUTE_OBJECTS = frozenset({"app", "router", "blueprint", "api", "bp"})
_VALIDATOR_NAMES = frozenset({"field_validator", "validator", "validates", "model_validator"})


def _oid(kind: str, scope: str, marker: str) -> str:
    """Deterministic obligation ID. Safe for the ``^o-[0-9A-Za-z_-]+$`` regex."""
    raw = f"{kind}|{scope}|{marker}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:10]
    return f"o-{kind[:3]}-{digest}"


def _decorator_name(dec: ast.expr) -> tuple[str | None, str | None]:
    """Return (object, attr) for ``@obj.attr(...)``; (None, name) for ``@name(...)``."""
    # strip call -> decorator target
    target: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Attribute):
        value = target.value
        obj_name = value.id if isinstance(value, ast.Name) else None
        return obj_name, target.attr
    if isinstance(target, ast.Name):
        return None, target.id
    return None, None


def _is_route_decorator(dec: ast.expr) -> bool:
    obj, attr = _decorator_name(dec)
    if attr is None:
        return False
    if obj in _ROUTE_OBJECTS and attr in _ROUTE_ATTRS:
        return True
    # Also accept bare `@route(...)` when imported directly.
    return obj is None and attr == "route"


def _is_validator_decorator(dec: ast.expr) -> bool:
    _, attr = _decorator_name(dec)
    return attr in _VALIDATOR_NAMES


def _extract_from_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, file_path: str
) -> list[Obligation]:
    out: list[Obligation] = []

    for dec in func.decorator_list:
        if _is_route_decorator(dec):
            marker = f"{file_path}:{func.name}:{func.lineno}"
            out.append(
                Obligation(
                    id=_oid("api_contract", file_path, marker),
                    kind="api_contract",
                    scope=f"{file_path}::{func.name}",
                    description=f"HTTP route handler {func.name} must honor declared contract",
                    evidence_required=[
                        EvidenceRequirement(
                            kind="regression",
                            description="Integration test hits the route and asserts status + shape",
                        )
                    ],
                    source="extracted",
                )
            )
            break  # one api_contract obligation per routed function is enough

        if _is_validator_decorator(dec):
            marker = f"{file_path}:{func.name}:{func.lineno}:validator"
            out.append(
                Obligation(
                    id=_oid("precondition", file_path, marker),
                    kind="precondition",
                    scope=f"{file_path}::{func.name}",
                    description=f"Validator {func.name} enforces input constraint",
                    evidence_required=[
                        EvidenceRequirement(
                            kind="regression",
                            description="Test rejects invalid input and accepts valid input",
                        )
                    ],
                    source="extracted",
                )
            )

    for node in ast.walk(func):
        # `assert cond[, msg]` inside the body
        if isinstance(node, ast.Assert):
            marker = f"{file_path}:{func.name}:{node.lineno}:assert"
            out.append(
                Obligation(
                    id=_oid("precondition", file_path, marker),
                    kind="precondition",
                    scope=f"{file_path}::{func.name}",
                    description=f"Assertion at line {node.lineno} must hold",
                    evidence_required=[
                        EvidenceRequirement(
                            kind="regression",
                            description="A test exercises this path without triggering AssertionError",
                        )
                    ],
                    source="extracted",
                )
            )
        # `if <cond>: raise ...` guard
        elif isinstance(node, ast.If):
            if any(isinstance(child, ast.Raise) for child in node.body):
                marker = f"{file_path}:{func.name}:{node.lineno}:guard"
                out.append(
                    Obligation(
                        id=_oid("precondition", file_path, marker),
                        kind="precondition",
                        scope=f"{file_path}::{func.name}",
                        description=f"Guard at line {node.lineno} raises on invalid input",
                        evidence_required=[
                            EvidenceRequirement(
                                kind="regression",
                                description="Test triggers and avoids the raise branch",
                            )
                        ],
                        source="extracted",
                    )
                )
    return out


def _extract_from_source(source: str, rel_path: str) -> list[Obligation]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    obligations: list[Obligation] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            obligations.extend(_extract_from_function(node, rel_path))
    return obligations


def _migration_obligations(changed_files: list[str]) -> list[Obligation]:
    out: list[Obligation] = []
    for p in changed_files:
        path_norm = p.replace("\\", "/")
        if any(pattern.search(path_norm) for pattern in _DATA_MARKERS):
            out.append(
                Obligation(
                    id=_oid("migration", path_norm, path_norm),
                    kind="migration",
                    scope=path_norm,
                    description=f"Data-layer change in {path_norm} requires reversibility evidence",
                    evidence_required=[
                        EvidenceRequirement(
                            kind="regression",
                            description="Migration up/down round-trip; backup + restore proof",
                        )
                    ],
                    source="extracted",
                )
            )
    return out


def extract_obligations(
    repo_path: Path | str,
    changed_files: list[str],
) -> list[Obligation]:
    """Return extracted obligations for the files in ``changed_files``.

    Arguments:
        repo_path: Absolute path to the repo root. AST reads resolve relative
            to this.
        changed_files: Forward-slash POSIX paths relative to ``repo_path``.
            (Blueprint §5 A; produced by :func:`detect_commands` + git diff.)

    The returned list is deterministic: sorted by ``(kind, scope, id)``.
    """
    root = Path(repo_path)
    obligations: list[Obligation] = []

    for rel in changed_files:
        if not rel.endswith(".py"):
            continue
        full = root / rel
        try:
            source = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        obligations.extend(_extract_from_source(source, rel.replace("\\", "/")))

    obligations.extend(_migration_obligations(changed_files))

    obligations.sort(key=lambda o: (o.kind, o.scope, o.id))
    return obligations


__all__ = ["extract_obligations"]
