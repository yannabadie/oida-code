"""Phase 6.1' commit-2 (per cgpro QA/A47 + ADR-65 + ADR-66) —
structural test for the predeclared env-bootstrap flag list on
``scripts/clone_target_at_sha.py``.

cgpro QA/A47 verdict_q1 carve-out language: predeclared
environment bootstrap flags derived from target metadata are
NOT tooling edits. The Phase 6.2 audit (ADR-63 G-6b) sharpened
this with: "the carve-out should be explicitly bounded: only
flags that existed BEFORE the holdout pass was designed, not
flags added in response to holdout failures." Without a
structural test, "predeclared" is just rhetorical — anyone can
add a new flag and call it predeclared. This test pins the
list operationally:

* The clone helper's argparse flag set MUST equal a known
  predeclared list (this module's ``_PREDECLARED_BOOTSTRAP_FLAGS``).
* Adding a new flag REQUIRES updating this list AND citing an
  explicit ADR rationale in the same commit.
* Removing a flag also requires test update + ADR.

This is the structural counterpart to the documentation
discipline. The test fails noisily so a reviewer cannot miss
it.

Per cgpro QA/A47 hard rule: this is test infrastructure, NOT a
runtime-path edit. The clone helper itself is unchanged in this
commit; only the test that pins its flag surface is added.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = (
    _REPO_ROOT / "scripts" / "clone_target_at_sha.py"
)


# The audit-bounded predeclared flag list (per ADR-66 +
# QA/A45 follow-up verdict_q1). Each flag MUST be justified
# as "predeclared environment bootstrap derived from target
# metadata", NOT as a tooling edit added in response to a
# specific holdout failure.
_PREDECLARED_BOOTSTRAP_FLAGS: frozenset[str] = frozenset(
    {
        # Required positional-style options.
        "--repo",
        "--head-sha",
        # Refusal mode (cgpro mandate, ADR-53 frontière rule 4).
        "--manual-egress-ok",
        # Operator-controlled directory placement.
        "--clones-dir",
        # Co-installs the local oida-code package so the venv
        # has both target + verifier (ADR-58, Phase 6.1'e).
        "--install-oida-code",
        # ADR-58: SCM_PRETEND_VERSION env-var pretend bypass
        # for shallow clones whose tag history setuptools_scm
        # needs (e.g. pytest 9.0.0).
        "--scm-pretend-version",
        # ADR-60: post-install importability smoke. Closes the
        # "package not importable from venv at pytest time"
        # bootstrap class.
        "--import-smoke",
        # ADR-61: PEP 621 [project.optional-dependencies] for
        # projects whose pytest comes from an extras (e.g.
        # sqlite-utils [test]).
        "--install-extras",
        # ADR-61: PEP 735 [dependency-groups] for projects
        # whose pytest comes from a group (e.g. structlog
        # [tests], attrs [tests]).
        "--install-group",
    },
)


def _import_clone_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_clone_for_predeclared_test", _SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _discover_argparse_flags() -> set[str]:
    """Discover the set of long-form flags defined by the
    script's argparse parser. Read the script's source and
    grep for ``parser.add_argument("--<flag>"`` — we don't
    need to invoke the parser to enumerate its flag set, and
    grepping keeps the test hermetic (no module-level
    side-effects on import)."""
    body = _SCRIPT_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r'parser\.add_argument\(\s*"(--[a-z][a-z0-9-]*)"',
    )
    return set(pattern.findall(body))


def test_predeclared_bootstrap_flag_set_is_pinned() -> None:
    """Phase 6.1' G-6b structural guard.

    The clone helper's argparse flag set MUST equal the
    audit-bounded predeclared list. Adding a new flag without
    updating ``_PREDECLARED_BOOTSTRAP_FLAGS`` (and citing an
    ADR) is a freeze-rule carve-out widening — exactly what
    the Phase 6.2 audit G-6b warned against.

    This test fails by listing both directions of the diff:
    flags in the script that are NOT in the predeclared list
    (carve-out widening — needs ADR), and flags in the
    predeclared list that are NOT in the script (test stale
    — needs cleanup).
    """
    discovered = _discover_argparse_flags()
    extra_in_script = discovered - _PREDECLARED_BOOTSTRAP_FLAGS
    missing_in_script = _PREDECLARED_BOOTSTRAP_FLAGS - discovered

    issues: list[str] = []
    if extra_in_script:
        issues.append(
            "Flags found in scripts/clone_target_at_sha.py that "
            "are NOT in the predeclared list: "
            f"{sorted(extra_in_script)}. Adding a new flag is "
            "a freeze-rule CARVE-OUT WIDENING per Phase 6.2 "
            "audit G-6b. Update tests/"
            "test_phase6_1_i_predeclared_bootstrap.py::"
            "_PREDECLARED_BOOTSTRAP_FLAGS in the SAME commit "
            "AND cite an explicit ADR justifying the new flag "
            "as predeclared environment bootstrap (NOT a "
            "tooling edit added in response to a specific "
            "holdout failure)."
        )
    if missing_in_script:
        issues.append(
            "Flags in the predeclared list that are NOT in the "
            "script: "
            f"{sorted(missing_in_script)}. The test is stale; "
            "either restore the flag in the script OR remove "
            "the entry from _PREDECLARED_BOOTSTRAP_FLAGS in "
            "the same commit."
        )
    assert not issues, "\n".join(issues)


def test_clone_module_carries_egress_marker() -> None:
    """Sanity check: the clone helper must continue to carry
    the MANUAL_EGRESS_SCRIPT marker (ADR-53). Pinning the flag
    set without preserving the marker would defeat the
    structural lane separation."""
    mod = _import_clone_module()
    assert getattr(mod, "MANUAL_EGRESS_SCRIPT", False) is True


def test_predeclared_list_size_matches_audit_count() -> None:
    """The audit (G-6b) named exactly 9 flags as the
    predeclared bootstrap surface as of ADR-66:
    --repo, --head-sha, --manual-egress-ok, --install-oida-code,
    --clones-dir, --scm-pretend-version, --import-smoke,
    --install-extras, --install-group.

    A future commit adding a 10th flag must (a) update this
    expected count, (b) update _PREDECLARED_BOOTSTRAP_FLAGS,
    (c) cite an ADR explaining why the new flag qualifies as
    predeclared. This double-binding test makes the "10 flags
    moment" structurally noisy."""
    assert len(_PREDECLARED_BOOTSTRAP_FLAGS) == 9, (
        f"Expected 9 predeclared bootstrap flags per audit "
        f"G-6b; got {len(_PREDECLARED_BOOTSTRAP_FLAGS)}: "
        f"{sorted(_PREDECLARED_BOOTSTRAP_FLAGS)}. If you "
        "intentionally added a 10th flag, update both this "
        "expected count AND the predeclared list above, and "
        "cite the ADR in the commit message."
    )
