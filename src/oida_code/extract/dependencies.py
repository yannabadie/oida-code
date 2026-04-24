"""Minimal bounded dependency graph between :class:`Obligation` objects.

Block C (ADR-21) deliverable. The graph answers exactly one question:

    If this obligation is invalidated, which events must be reopened,
    and which must only be audited?

Four edge rules, all bounded (``max_depth=1``, ``max_files=50``),
deterministic, and explainable (every edge carries ``reason`` + ``source``
+ ``confidence``). Direction convention: ``A → B`` means "B depends on A"
— so if ``src/service.py`` imports ``src/db.py``, the edge is
``db_event → service_event``, matching the dominator semantics in the
vendored :func:`double_loop_repair`.

**Not in scope** (ADR-21):

* No claim of graph-aware ``V_net``. The vendored ``OIDAAnalyzer.analyze()``
  does not consume edges in its per-event fusion.
* No exhaustive call graph.
* No edges without ``reason`` / ``source`` / ``confidence``.
* External / stdlib / site-packages imports are ignored; unresolved
  imports are RECORDED, not guessed.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from oida_code.models.obligation import Obligation

EdgeKind = Literal["constitutive", "supportive"]
ImpactReason = Literal[
    "changed",
    "imports_changed",
    "imported_by_changed",
    "related_test",
    "config",
    "migration",
]

_CONFIG_FILENAMES = frozenset(
    {"pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini", "setup.py"}
)
_MIGRATION_MARKERS = (
    "migrations/",
    "migration/",
    "alembic/",
    "/migrations/",
    "/migration/",
    "/alembic/",
)


# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """One directed edge between obligations. Always carries provenance."""

    parent_id: str
    child_id: str
    kind: EdgeKind
    reason: str
    confidence: float
    source: str


@dataclass(frozen=True, slots=True)
class DependencyGraphResult:
    """Output of :func:`build_dependency_graph`."""

    obligations: list[Obligation]
    constitutive_edges: list[DependencyEdge]
    supportive_edges: list[DependencyEdge]
    unresolved_imports: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    max_depth: int = 1
    max_files: int = 50

    def parents_of(
        self, child_id: str, kind: EdgeKind
    ) -> list[str]:
        """Return sorted list of ``parent_id``s for ``child_id`` by edge kind."""
        edges = (
            self.constitutive_edges if kind == "constitutive" else self.supportive_edges
        )
        return sorted({e.parent_id for e in edges if e.child_id == child_id})


@dataclass(frozen=True, slots=True)
class ImpactConeEntry:
    """One file in the bounded impact cone, with a provenance tag."""

    path: str
    reason: ImpactReason


# ---------------------------------------------------------------------------
# Path + scope helpers
# ---------------------------------------------------------------------------


def _normalize(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _obligation_file(ob: Obligation) -> str:
    return _normalize(ob.scope.split("::", 1)[0])


def _obligation_symbol(ob: Obligation) -> str | None:
    parts = ob.scope.split("::", 1)
    return parts[1] if len(parts) == 2 and parts[1] else None


def _is_config(path: str) -> bool:
    norm = _normalize(path)
    return Path(norm).name in _CONFIG_FILENAMES


def _is_migration(path: str) -> bool:
    norm = _normalize(path).lower()
    return any(m in norm for m in _MIGRATION_MARKERS) or norm.endswith(".sql")


def _is_test_file(path: str) -> bool:
    norm = _normalize(path)
    name = Path(norm).name
    return norm.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py")


def _related_source_for_test(test_path: str) -> str | None:
    """``tests/test_foo.py`` → ``src/foo.py`` or ``foo.py``. Best-effort."""
    norm = _normalize(test_path)
    name = Path(norm).name
    if name.startswith("test_") and name.endswith(".py"):
        stem = name[len("test_") : -len(".py")]
        return f"src/{stem}.py"
    if name.endswith("_test.py"):
        stem = name[: -len("_test.py")]
        return f"src/{stem}.py"
    return None


# ---------------------------------------------------------------------------
# Rule 2 — direct imports via AST
# ---------------------------------------------------------------------------


def _read_source(repo: Path, rel: str) -> str | None:
    try:
        return (repo / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _module_to_candidate_files(module: str) -> list[str]:
    """Return repo-local candidate paths for ``module`` (dotted name).

    E.g. ``oida_code.score.mapper`` → ``["oida_code/score/mapper.py",
    "oida_code/score/mapper/__init__.py", "src/oida_code/score/mapper.py",
    "src/oida_code/score/mapper/__init__.py"]``.
    """
    base = module.replace(".", "/")
    return [
        f"{base}.py",
        f"{base}/__init__.py",
        f"src/{base}.py",
        f"src/{base}/__init__.py",
    ]


def _resolve_module(module: str, repo: Path) -> str | None:
    """Return the first candidate that exists in ``repo``, else ``None``.

    Stdlib / site-packages / external modules are filtered out because
    the candidate paths only reference repo-local layouts. This is the
    "unresolved imports ignored" behaviour from ADR-21.
    """
    if not module:
        return None
    # Cheap stdlib filter — avoids walking the filesystem for hot hits.
    head = module.split(".", 1)[0]
    if head in sys.stdlib_module_names:
        return None
    for cand in _module_to_candidate_files(module):
        if (repo / cand).is_file():
            return _normalize(cand)
    return None


def _extract_imports(source: str) -> list[str]:
    """Return the list of dotted module names imported by ``source``.

    For ``import a.b`` we emit ``"a.b"``. For ``from a import b`` we emit
    BOTH ``"a.b"`` (if ``b`` is itself a module) and ``"a"`` (the package),
    so the resolver can try both candidates.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    out.append(alias.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
        ):
            # Try each imported name as a sub-module first, fall back to
            # the package itself. This covers ``from pkg import module``.
            for alias in node.names:
                if alias.name and alias.name != "*":
                    out.append(f"{node.module}.{alias.name}")
            out.append(node.module)
    return out


# ---------------------------------------------------------------------------
# Rule 1 — same-scope kind hierarchy
# ---------------------------------------------------------------------------


def _same_scope_edges(obligations: list[Obligation]) -> list[DependencyEdge]:
    """Rule 1: within the same (file, symbol), non-contract obligations
    edge into the api_contract obligation.

    Constitutive: precondition / invariant / security_rule → api_contract
    Supportive: migration / observability → api_contract
    """
    edges: list[DependencyEdge] = []
    by_key: dict[tuple[str, str | None], list[Obligation]] = {}
    for ob in obligations:
        key = (_obligation_file(ob), _obligation_symbol(ob))
        by_key.setdefault(key, []).append(ob)

    for (file_path, symbol), group in by_key.items():
        api_contracts = [o for o in group if o.kind == "api_contract"]
        if not api_contracts:
            continue
        for api in api_contracts:
            for ob in group:
                if ob.id == api.id:
                    continue
                if ob.kind in {"precondition", "invariant", "security_rule"}:
                    edges.append(
                        DependencyEdge(
                            parent_id=ob.id,
                            child_id=api.id,
                            kind="constitutive",
                            reason=f"same_symbol_{ob.kind}_supports_contract",
                            confidence=0.9,
                            source=f"rule1:same_scope:{file_path}"
                            + (f"::{symbol}" if symbol else ""),
                        )
                    )
                elif ob.kind in {"migration", "observability"}:
                    edges.append(
                        DependencyEdge(
                            parent_id=ob.id,
                            child_id=api.id,
                            kind="supportive",
                            reason=f"same_symbol_{ob.kind}_audits_contract",
                            confidence=0.7,
                            source=f"rule1:same_scope:{file_path}"
                            + (f"::{symbol}" if symbol else ""),
                        )
                    )
    return edges


# ---------------------------------------------------------------------------
# Rule 2 — direct imports
# ---------------------------------------------------------------------------


def _import_edges(
    obligations: list[Obligation],
    repo: Path,
    scanned_files: list[str],
    unresolved: list[str],
) -> list[DependencyEdge]:
    """For each changed Python file, parse imports. An obligation on the
    imported file → obligation(s) on the importing file = supportive.
    """
    by_file: dict[str, list[Obligation]] = {}
    for ob in obligations:
        by_file.setdefault(_obligation_file(ob), []).append(ob)

    edges: list[DependencyEdge] = []
    for importer_rel in scanned_files:
        if not importer_rel.endswith(".py"):
            continue
        source = _read_source(repo, importer_rel)
        if source is None:
            continue
        importing_obs = by_file.get(_normalize(importer_rel), [])
        if not importing_obs:
            # Still scan so unresolved imports accumulate for diagnostics.
            for module in _extract_imports(source):
                if _resolve_module(module, repo) is None:
                    unresolved.append(f"{importer_rel} -> {module}")
            continue

        for module in _extract_imports(source):
            imported_rel = _resolve_module(module, repo)
            if imported_rel is None:
                unresolved.append(f"{importer_rel} -> {module}")
                continue
            imported_obs = by_file.get(imported_rel, [])
            if not imported_obs:
                continue
            for parent in imported_obs:
                for child in importing_obs:
                    if parent.id == child.id:
                        continue
                    edges.append(
                        DependencyEdge(
                            parent_id=parent.id,
                            child_id=child.id,
                            kind="supportive",
                            reason="direct_import",
                            confidence=0.6,
                            source=f"rule2:import:{importer_rel}->{imported_rel}",
                        )
                    )
    return edges


# ---------------------------------------------------------------------------
# Rule 3 — related tests (test → source supportive)
# ---------------------------------------------------------------------------


def _test_edges(obligations: list[Obligation]) -> list[DependencyEdge]:
    edges: list[DependencyEdge] = []
    by_file: dict[str, list[Obligation]] = {}
    for ob in obligations:
        by_file.setdefault(_obligation_file(ob), []).append(ob)

    for test_path, test_obs in by_file.items():
        if not _is_test_file(test_path):
            continue
        source_path = _related_source_for_test(test_path)
        if source_path is None:
            continue
        # Match by direct relative path OR by basename.
        source_obs: list[Obligation] = []
        for candidate, candidates_obs in by_file.items():
            if candidate == source_path or Path(candidate).name == Path(source_path).name:
                source_obs.extend(candidates_obs)
        for t_ob in test_obs:
            for s_ob in source_obs:
                if t_ob.id == s_ob.id:
                    continue
                edges.append(
                    DependencyEdge(
                        parent_id=t_ob.id,
                        child_id=s_ob.id,
                        kind="supportive",
                        reason="related_test_audits_source",
                        confidence=0.5,
                        source=f"rule3:test:{test_path}->{_obligation_file(s_ob)}",
                    )
                )
    return edges


# ---------------------------------------------------------------------------
# Rule 4 — config + migration
# ---------------------------------------------------------------------------


def _config_migration_edges(
    obligations: list[Obligation],
) -> list[DependencyEdge]:
    edges: list[DependencyEdge] = []
    config_obs = [o for o in obligations if _is_config(_obligation_file(o))]
    migration_obs = [o for o in obligations if _is_migration(_obligation_file(o))]
    python_obs = [
        o
        for o in obligations
        if _obligation_file(o).endswith(".py")
        and not _is_config(_obligation_file(o))
    ]

    for cfg in config_obs:
        for py in python_obs:
            edges.append(
                DependencyEdge(
                    parent_id=cfg.id,
                    child_id=py.id,
                    kind="supportive",
                    reason="config_audits_python_obligation",
                    confidence=0.4,
                    source=f"rule4:config:{_obligation_file(cfg)}",
                )
            )

    for mig in migration_obs:
        for other in obligations:
            if other.id == mig.id:
                continue
            other_file = _obligation_file(other)
            if other.kind == "migration" and _is_migration(other_file):
                # Same migration scope already covered by rule 1 on pattern_id.
                # Cross-migration constitutive edge only fires when scope paths
                # overlap (same migration dir).
                if _same_migration_scope(_obligation_file(mig), other_file):
                    edges.append(
                        DependencyEdge(
                            parent_id=mig.id,
                            child_id=other.id,
                            kind="constitutive",
                            reason="same_migration_scope",
                            confidence=0.8,
                            source=f"rule4:migration:{_obligation_file(mig)}->{other_file}",
                        )
                    )
            elif other.kind in {"api_contract", "precondition"}:
                edges.append(
                    DependencyEdge(
                        parent_id=mig.id,
                        child_id=other.id,
                        kind="supportive",
                        reason="migration_audits_data_api_path",
                        confidence=0.5,
                        source=f"rule4:migration:{_obligation_file(mig)}->{other_file}",
                    )
                )
    return edges


def _same_migration_scope(a: str, b: str) -> bool:
    if a == b:
        return True
    a_dir = str(Path(a).parent)
    b_dir = str(Path(b).parent)
    return a_dir == b_dir and any(m.rstrip("/") in a for m in _MIGRATION_MARKERS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _dedup(edges: list[DependencyEdge]) -> list[DependencyEdge]:
    """Stable dedup on ``(parent_id, child_id, kind)`` — keeps first reason."""
    seen: set[tuple[str, str, str]] = set()
    out: list[DependencyEdge] = []
    for e in edges:
        key = (e.parent_id, e.child_id, e.kind)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _drop_self_and_unknown(
    edges: list[DependencyEdge], known_ids: set[str]
) -> list[DependencyEdge]:
    return [
        e
        for e in edges
        if e.parent_id != e.child_id
        and e.parent_id in known_ids
        and e.child_id in known_ids
    ]


def build_dependency_graph(
    obligations: list[Obligation],
    repo_path: Path | str,
    changed_files: list[str],
    *,
    max_depth: int = 1,
    max_files: int = 50,
) -> DependencyGraphResult:
    """Return a bounded dependency graph over ``obligations``.

    ADR-21 bounds: ``max_depth=1`` means we only scan the directly-
    changed files for imports; we do not recurse into their imports'
    imports. ``max_files`` caps how many files we parse; excess are
    recorded in ``skipped_files``.
    """
    del max_depth  # Block-C default; wider depth is Phase-4 work.
    repo = Path(repo_path)
    known_ids = {o.id for o in obligations}

    # Bound the set of files we actually parse.
    scanned = [_normalize(f) for f in changed_files[:max_files] if f.endswith(".py")]
    skipped = [
        _normalize(f)
        for f in changed_files[max_files:]
        if f.endswith(".py")
    ]

    unresolved: list[str] = []

    edges: list[DependencyEdge] = []
    edges.extend(_same_scope_edges(obligations))
    edges.extend(_import_edges(obligations, repo, scanned, unresolved))
    edges.extend(_test_edges(obligations))
    edges.extend(_config_migration_edges(obligations))

    edges = _drop_self_and_unknown(edges, known_ids)
    edges = _dedup(edges)
    edges.sort(key=lambda e: (e.kind, e.parent_id, e.child_id))

    constitutive = [e for e in edges if e.kind == "constitutive"]
    supportive = [e for e in edges if e.kind == "supportive"]

    return DependencyGraphResult(
        obligations=list(obligations),
        constitutive_edges=constitutive,
        supportive_edges=supportive,
        unresolved_imports=sorted(set(unresolved)),
        skipped_files=sorted(set(skipped)),
        max_depth=1,
        max_files=max_files,
    )


# ---------------------------------------------------------------------------
# Impact cone — changed_files + bounded neighborhood with reason tags
# ---------------------------------------------------------------------------


def build_impact_cone(
    repo_path: Path | str,
    changed_files: list[str],
    *,
    max_files: int = 50,
) -> list[ImpactConeEntry]:
    """Return the bounded impact cone around ``changed_files``.

    Every entry carries a ``reason`` tag: ``changed`` / ``imports_changed``
    / ``imported_by_changed`` / ``related_test`` / ``config`` / ``migration``.
    Bounded at ``max_files`` total entries; external imports and stdlib
    are excluded.
    """
    repo = Path(repo_path)
    changed_norm = [_normalize(f) for f in changed_files]
    entries: list[ImpactConeEntry] = []
    seen: set[str] = set()

    def _add(path: str, reason: ImpactReason) -> None:
        norm = _normalize(path)
        if norm in seen:
            return
        seen.add(norm)
        entries.append(ImpactConeEntry(path=norm, reason=reason))

    for cf in changed_norm:
        _add(cf, "changed")

    # Direct imports of changed Python files.
    for cf in changed_norm:
        if not cf.endswith(".py"):
            continue
        if len(entries) >= max_files:
            break
        source = _read_source(repo, cf)
        if source is None:
            continue
        for module in _extract_imports(source):
            resolved = _resolve_module(module, repo)
            if resolved is None or resolved in seen:
                continue
            if len(entries) >= max_files:
                break
            _add(resolved, "imports_changed")

    # Importers of changed files (cheap scan): look only at *.py in repo
    # root + src/ (do not walk the whole repo).
    candidate_roots = [repo, repo / "src"]
    scanned = 0
    changed_modules: set[str] = set()
    for cf in changed_norm:
        if not cf.endswith(".py"):
            continue
        module_full = cf.removesuffix(".py").replace("/", ".")
        changed_modules.add(module_full)
        # Also add the src-stripped spelling so importers that write
        # ``from src.pkg import mod`` (emitting ``src.pkg.mod``) AND
        # importers that write ``import pkg.mod`` (no ``src.``) both
        # resolve to the same changed file.
        if module_full.startswith("src."):
            changed_modules.add(module_full[len("src.") :])

    for root in candidate_roots:
        if len(entries) >= max_files:
            break
        if not root.is_dir():
            continue
        for py_path in sorted(root.rglob("*.py")):
            if len(entries) >= max_files:
                break
            scanned += 1
            if scanned > max_files * 4:  # hard stop on giant repos
                break
            rel = _normalize(str(py_path.relative_to(repo)))
            if rel in seen:
                continue
            source = _read_source(repo, rel)
            if source is None:
                continue
            imports = _extract_imports(source)
            prefixes = tuple(m + "." for m in changed_modules)
            if any(
                mod in changed_modules or mod.startswith(prefixes)
                for mod in imports
            ):
                _add(rel, "imported_by_changed")

    # Related tests for changed source files.
    for cf in list(changed_norm):
        if len(entries) >= max_files:
            break
        if cf.endswith(".py") and not _is_test_file(cf):
            stem = Path(cf).stem
            for test_candidate in (f"tests/test_{stem}.py", f"tests/{stem}_test.py"):
                if test_candidate in seen:
                    continue
                if (repo / test_candidate).is_file():
                    _add(test_candidate, "related_test")

    # Config files in the repo root (supportive surface).
    for cfg_name in _CONFIG_FILENAMES:
        if len(entries) >= max_files:
            break
        if (repo / cfg_name).is_file():
            _add(cfg_name, "config")

    # Migration files touched elsewhere in changed set already tagged as changed;
    # if a changed file sits in a migrations/alembic dir, re-tag its kind.
    # (Non-mutating: the original "changed" entry stays; we add the kind hint
    # only when the path isn't already in the cone.)
    for cf in changed_norm:
        if _is_migration(cf) and cf not in seen:
            if len(entries) >= max_files:
                break
            _add(cf, "migration")

    return entries[:max_files]


# ---------------------------------------------------------------------------
# D0 integration helper — derive the audit surface from a diff
# ---------------------------------------------------------------------------


def derive_audit_surface(
    repo_path: Path | str,
    changed_files: list[str],
    *,
    mode: Literal["changed", "impact"] = "impact",
    max_files: int = 50,
) -> list[str]:
    """Return the surface the audit pipeline should operate on.

    ADR-21 / Block D0: the raw diff (``AuditRequest.scope.changed_files``)
    and the audit-surface are two different things. The diff is what the
    commit touched; the surface is diff PLUS the bounded impact cone
    (direct imports / importers / related tests / config / migration).
    Callers that extract obligations or bound U(t) should use the
    surface, not the raw diff.

    * ``mode="changed"``: pass-through; returns the raw diff deduplicated
      and normalized. Used by callers that explicitly want legacy
      behaviour (``normalize --mode=changed``).
    * ``mode="impact"``: returns ``[entry.path for entry in
      build_impact_cone(...)]`` capped at ``max_files``. Default.

    Does NOT mutate the input list. Does NOT modify
    ``AuditRequest.scope.changed_files`` — that stays the raw diff so
    downstream readers know what actually changed.
    """
    if mode == "changed":
        seen: list[str] = []
        for f in changed_files:
            norm = _normalize(f)
            if norm and norm not in seen:
                seen.append(norm)
                if len(seen) >= max_files:
                    break
        return seen
    # mode == "impact"
    cone = build_impact_cone(repo_path, changed_files, max_files=max_files)
    return [entry.path for entry in cone]


__all__ = [
    "DependencyEdge",
    "DependencyGraphResult",
    "ImpactConeEntry",
    "build_dependency_graph",
    "build_impact_cone",
    "derive_audit_surface",
]
