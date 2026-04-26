"""Phase 5.0 (QA/A27.md, ADR-35) — design-only invariants.

Phase 5.0 is design-only: no MCP code, no provider
tool-calling, no removal of the existing anti-MCP locks. This
test file:

1. Asserts every Phase 5.0 design document exists at the
   prescribed path with the prescribed content keywords.
2. Re-affirms the Phase 4.7 anti-MCP / anti-tool-calling
   locks via SCOPED checks (pyproject.toml +
   .github/workflows/ + src/oida_code/ only — NOT
   docs/ or reports/, which intentionally contain the
   protected words).
3. Asserts the existing Phase 4.7 lock-tests remain defined
   as callable functions (catches silent removal of the
   locks).

Per QA/A27.md lines 929-930: tests MUST NOT block MCP /
tool-calling words in `docs/` and `reports/`. Scope every
negative check accordingly.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_SECURITY_DIR = _REPO_ROOT / "docs" / "security"


# ---------------------------------------------------------------------------
# Design-document existence (criterion 1 + 2-8 from QA/A27 §critères)
# ---------------------------------------------------------------------------


def test_phase5_design_docs_exist() -> None:
    """The seven Phase 5.0 design files MUST exist at the
    prescribed paths (QA/A27.md §5.0-A through §5.0-G + report)."""
    expected = (
        _SECURITY_DIR / "mcp_threat_model.md",
        _SECURITY_DIR / "mcp_admission_policy.md",
        _SECURITY_DIR / "tool_schema_pinning.md",
        _SECURITY_DIR / "tool_call_execution_model.md",
        _SECURITY_DIR / "mcp_audit_log_schema.md",
        _SECURITY_DIR / "mcp_unlock_criteria.md",
        _REPO_ROOT / "experiments" / "pydantic_ai_spike"
        / "phase5_assessment.md",
        _REPO_ROOT / "reports" / "phase5_0_mcp_tool_calling_design.md",
    )
    missing = [str(p.relative_to(_REPO_ROOT)) for p in expected if not p.is_file()]
    assert not missing, f"Phase 5.0 design docs missing: {missing!r}"


def test_adr35_logged() -> None:
    """ADR-35 MUST be appended to memory-bank/decisionLog.md."""
    log = (_REPO_ROOT / "memory-bank" / "decisionLog.md").read_text(
        encoding="utf-8",
    )
    assert "ADR-35" in log, "ADR-35 missing from decisionLog.md"
    # The ADR's signature one-liner.
    assert (
        "MCP and provider tool-calling design before implementation"
        in log
    ), "ADR-35 entry missing prescribed title"


# ---------------------------------------------------------------------------
# Threat model content (criteria 2-3-4 from QA/A27 §tests)
# ---------------------------------------------------------------------------


def test_mcp_threat_model_mentions_tool_poisoning() -> None:
    body = (_SECURITY_DIR / "mcp_threat_model.md").read_text(
        encoding="utf-8",
    ).lower()
    assert "tool poisoning" in body, (
        "mcp_threat_model.md must name the tool-poisoning class "
        "(OWASP MCP03)"
    )


def test_mcp_threat_model_mentions_rug_pull() -> None:
    body = (_SECURITY_DIR / "mcp_threat_model.md").read_text(
        encoding="utf-8",
    ).lower()
    # Accept either spelling.
    assert "rug-pull" in body or "rug pull" in body, (
        "mcp_threat_model.md must name the rug-pull class"
    )


def test_mcp_threat_model_mentions_confused_deputy() -> None:
    body = (_SECURITY_DIR / "mcp_threat_model.md").read_text(
        encoding="utf-8",
    ).lower()
    assert "confused deputy" in body, (
        "mcp_threat_model.md must name the confused-deputy "
        "authorization risk"
    )


# ---------------------------------------------------------------------------
# Admission policy + unlock criteria content
# ---------------------------------------------------------------------------


def test_mcp_admission_policy_requires_schema_hash() -> None:
    body = (_SECURITY_DIR / "mcp_admission_policy.md").read_text(
        encoding="utf-8",
    )
    # The 12-item checklist MUST include schema-hash pinning.
    assert "schema_sha256" in body or "schema hash" in body.lower(), (
        "mcp_admission_policy.md must require schema hash pinning"
    )


def test_mcp_unlock_criteria_keeps_locks_active() -> None:
    """The unlock criteria document MUST state the lock-stays
    phrase verbatim (QA/A27.md lines 808-810)."""
    body = (_SECURITY_DIR / "mcp_unlock_criteria.md").read_text(
        encoding="utf-8",
    )
    expected = (
        "Anti-MCP and anti-tool-calling tests remain active after "
        "Phase 5.0."
    )
    assert expected in body, (
        f"mcp_unlock_criteria.md missing the prescribed phrase: "
        f"{expected!r}"
    )


# ---------------------------------------------------------------------------
# SCOPED negative tests — pyproject.toml / workflows / src/ only.
# These DO NOT scan docs/ or reports/ (which intentionally contain
# the words the tests reject).
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added() -> None:
    """pyproject.toml MUST NOT list any MCP package. Phase 5.0
    re-affirms the Phase 4.7 lock with the same scoping."""
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        '"mcp"',
        '"model-context-protocol"',
        '"mcp-server"',
        '"pydantic-ai"',  # Phase 5.0 design rejects Pydantic-AI as runtime
    )
    for token in forbidden:
        assert token not in body, (
            f"pyproject.toml lists forbidden package {token!r}; "
            "Phase 5.0 + ADR-35 forbid MCP / Pydantic-AI runtime"
        )


def test_no_mcp_workflow_added() -> None:
    """No `.github/workflows/<mcp*>.yml` file may exist; no
    `mcp-server` / `model-context-protocol` invocation in any
    workflow YAML."""
    workflow_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return  # Nothing to check.
    forbidden_filenames = ("mcp.yml", "mcp-baseline.yml", "mcp-smoke.yml")
    for name in forbidden_filenames:
        assert not (workflow_dir / name).exists(), (
            f"{name} must not exist; Phase 5.0 forbids MCP workflows"
        )
    for wf in workflow_dir.glob("*.yml"):
        body = wf.read_text(encoding="utf-8").lower()
        assert "model-context-protocol" not in body, (
            f"{wf.name} references model-context-protocol; "
            "Phase 5.0 forbids MCP wiring"
        )
        assert "mcp-server" not in body, (
            f"{wf.name} references mcp-server"
        )


def test_no_provider_tool_calling_enabled() -> None:
    """provider_config.py MUST keep `supports_tools=False`
    everywhere. Re-affirms Phase 4.7
    test_no_provider_tool_calling_enabled with the same scoping."""
    body = (
        _REPO_ROOT / "src" / "oida_code" / "estimators"
        / "provider_config.py"
    ).read_text(encoding="utf-8")
    assert "supports_tools=True" not in body, (
        "provider_config.py sets supports_tools=True somewhere; "
        "Phase 5.0 + ADR-35 forbid provider tool-calling"
    )


def test_no_supports_tools_true() -> None:
    """Repeats the supports_tools=True check across every Python
    file under src/oida_code/ — broader than Phase 4.7 which
    only checked provider_config.py. Phase 5.0 adds this for
    defence-in-depth."""
    src_root = _REPO_ROOT / "src" / "oida_code"
    for py in src_root.rglob("*.py"):
        # The vendored OIDA core is excluded — see ADR-02; we
        # never scan the vendored tree for these style checks.
        if "_vendor" in py.parts:
            continue
        body = py.read_text(encoding="utf-8")
        assert "supports_tools=True" not in body, (
            f"{py.relative_to(_REPO_ROOT)} sets supports_tools=True; "
            "Phase 5.0 forbids provider tool-calling"
        )


def test_no_mcp_runtime_import_in_src() -> None:
    """No `import mcp` / `from mcp ...` / `from pydantic_ai ...`
    in any file under `src/oida_code/`. The MCP / Pydantic-AI
    surface lives only in docs/ and experiments/."""
    src_root = _REPO_ROOT / "src" / "oida_code"
    forbidden_imports = (
        re.compile(r"^\s*import\s+mcp(\s|$|\.)", re.MULTILINE),
        re.compile(r"^\s*from\s+mcp(\s|\.)", re.MULTILINE),
        re.compile(r"^\s*import\s+pydantic_ai(\s|$|\.)", re.MULTILINE),
        re.compile(r"^\s*from\s+pydantic_ai(\s|\.)", re.MULTILINE),
    )
    for py in src_root.rglob("*.py"):
        if "_vendor" in py.parts:
            continue
        body = py.read_text(encoding="utf-8")
        for pattern in forbidden_imports:
            match = pattern.search(body)
            assert not match, (
                f"{py.relative_to(_REPO_ROOT)} imports forbidden "
                f"runtime module: {match.group(0)!r}"
            )


def test_anti_mcp_locks_still_active() -> None:
    """The two Phase 4.7 lock-tests
    (`test_no_mcp_workflow_or_dependency_added` and
    `test_no_provider_tool_calling_enabled`) MUST still be
    defined as callable functions in
    tests/test_phase4_7_provider_baseline.py. This catches
    silent removal of the locks."""
    test_file = (
        _REPO_ROOT / "tests" / "test_phase4_7_provider_baseline.py"
    )
    assert test_file.is_file(), (
        f"{test_file.name} missing — anti-MCP locks gone"
    )
    spec = importlib.util.spec_from_file_location(
        "phase4_7_lock_check", test_file,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # Module may have collection-level imports we don't carry
        # (e.g. a yaml fixture). Fall back to text inspection,
        # which is sufficient to detect silent removal.
        body = test_file.read_text(encoding="utf-8")
        assert (
            "def test_no_mcp_workflow_or_dependency_added"
            in body
        ), (
            f"test_no_mcp_workflow_or_dependency_added missing "
            f"from {test_file.name} (module load: {exc})"
        )
        assert (
            "def test_no_provider_tool_calling_enabled" in body
        ), (
            f"test_no_provider_tool_calling_enabled missing "
            f"from {test_file.name} (module load: {exc})"
        )
        return
    # Module loaded cleanly — assert both functions exist + callable.
    assert callable(
        getattr(module, "test_no_mcp_workflow_or_dependency_added", None),
    ), (
        "test_no_mcp_workflow_or_dependency_added removed or renamed"
    )
    assert callable(
        getattr(module, "test_no_provider_tool_calling_enabled", None),
    ), (
        "test_no_provider_tool_calling_enabled removed or renamed"
    )


# ---------------------------------------------------------------------------
# Official-fields hard wall (ADR-22) — Phase 5.0 re-affirmation
# ---------------------------------------------------------------------------


def test_no_official_fields_emitted() -> None:
    """No production code path may emit `total_v_net` /
    `debt_final` / `corrupt_success` as a non-blocked, non-null
    value. Phase 5.0 re-affirms ADR-22 by scanning every
    Pydantic schema under src/oida_code/ — the field NAMES may
    appear (e.g., in markdown_report.py's optional renderer for
    the legacy AuditReport), but no field DEFAULT or model
    validator may set them to a numeric value."""
    src_root = _REPO_ROOT / "src" / "oida_code"
    forbidden_assignments = (
        re.compile(r"total_v_net\s*=\s*[0-9]"),
        re.compile(r"debt_final\s*=\s*[0-9]"),
        re.compile(r"corrupt_success\s*=\s*[0-9]"),
        re.compile(r"corrupt_success_ratio\s*=\s*[0-9]"),
    )
    for py in src_root.rglob("*.py"):
        if "_vendor" in py.parts:
            continue
        body = py.read_text(encoding="utf-8")
        for pattern in forbidden_assignments:
            match = pattern.search(body)
            assert not match, (
                f"{py.relative_to(_REPO_ROOT)} assigns a numeric "
                f"value to a forbidden official field: "
                f"{match.group(0)!r}"
            )


# ---------------------------------------------------------------------------
# Honesty statement lock (criterion 16 — report produced)
# ---------------------------------------------------------------------------


def test_phase5_report_honesty_statement() -> None:
    """The Phase 5.0 report MUST carry the eight-line honesty
    statement from QA/A27.md lines 899-908 verbatim."""
    body = (
        _REPO_ROOT / "reports" / "phase5_0_mcp_tool_calling_design.md"
    ).read_text(encoding="utf-8")
    expected_lines = (
        "Phase 5.0 is design-only.",
        "It does not add MCP runtime integration.",
        "It does not enable provider tool-calling.",
        "It does not execute MCP tools.",
        "It does not remove anti-MCP or anti-tool-calling locks.",
        "It does not validate production predictive performance.",
        "It does not emit official `total_v_net`, `debt_final`, or",
        "It does not modify the vendored OIDA core.",
    )
    for line in expected_lines:
        assert line in body, (
            f"Phase 5.0 report missing honesty-statement line: "
            f"{line!r}"
        )


def test_phase5_report_declares_no_code_mcp() -> None:
    """The report MUST explicitly state that no MCP runtime code
    is shipped in this phase."""
    body = (
        _REPO_ROOT / "reports" / "phase5_0_mcp_tool_calling_design.md"
    ).read_text(encoding="utf-8").lower()
    assert (
        "design-only" in body
        or "design only" in body
    ), "Phase 5.0 report does not declare itself as design-only"
    # Must explicitly note no MCP runtime code in src/.
    assert (
        "zero new code under" in body
        or "zero lines under" in body
        or "no mcp code" in body
        or "ships no mcp" in body
        or "no mcp runtime code" in body
    ), (
        "Phase 5.0 report does not state the no-runtime-code "
        "invariant"
    )
