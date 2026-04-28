"""Phase 6.0 (QA/A41, ADR-50) — controlled beta doc-guard tests.

QA/A41 acceptance criteria #1-#28 land here as structural locks. The
overarching rule is **scoped enforcement** — these tests must NOT
scan files that legitimately reproduce the forbidden product-verdict
tokens in their forbidden role (security policy doc, ADRs that quote
the wall, reports' honesty statements, BACKLOG.md). The Phase 5.0 /
ADR-35 SCOPED-checks precedent applies; Phase 5.9 already established
the three-heuristic negation detector for inline mentions.

The Phase 6.0 user-facing scope splits into two layers:

* ``_ALL_PHASE6_DOCS`` — every Phase 6.0 deliverable file. The
  **no-product-verdict** test runs over this entire set.
* ``_GATEWAY_EXPLAINER_DOCS`` — the subset that explains the gateway
  path operationally. The **default-false / official-fields-blocked /
  diagnostic-only** assertions only run over this subset (templates,
  the feedback form, and BACKLOG.md are intentionally narrower).

Out-of-scope for the verdict-token scan (these intentionally
reproduce the tokens to forbid them):

* docs/security/no_product_verdict_policy.md
* memory-bank/decisionLog.md (ADRs)
* reports/*.md (honesty statements, including reports/beta/*.md)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Phase 6.0 user-facing files — the scoped sets
# ---------------------------------------------------------------------------


_ALL_PHASE6_DOCS: tuple[Path, ...] = (
    _REPO_ROOT / "BACKLOG.md",
    _REPO_ROOT / "docs" / "project_status.md",
    _REPO_ROOT / "docs" / "concepts" / "oida_code_plain_language.md",
    _REPO_ROOT / "docs" / "beta" / "README.md",
    _REPO_ROOT / "docs" / "beta" / "beta_known_limits.md",
    _REPO_ROOT / "docs" / "beta" / "beta_operator_quickstart.md",
    _REPO_ROOT / "docs" / "beta" / "beta_case_template.md",
    _REPO_ROOT / "docs" / "beta" / "beta_feedback_form.md",
)


_GATEWAY_EXPLAINER_DOCS: tuple[Path, ...] = (
    _REPO_ROOT / "docs" / "project_status.md",
    _REPO_ROOT / "docs" / "concepts" / "oida_code_plain_language.md",
    _REPO_ROOT / "docs" / "beta" / "README.md",
    _REPO_ROOT / "docs" / "beta" / "beta_known_limits.md",
    _REPO_ROOT / "docs" / "beta" / "beta_operator_quickstart.md",
)


def _doc_id(path: Path) -> str:
    """Pytest parametrize id helper — keeps decorator lines short."""
    return path.relative_to(_REPO_ROOT).as_posix()


_VERDICT_TOKENS = (
    r"merge-safe|production-safe|bug-free|verified|security-verified"
)
_OFFICIAL_TOKENS = (
    r"total_v_net|debt_final|corrupt_success|corrupt_success_ratio"
)
_FORBIDDEN_VERDICT_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bthe\s+code\s+is\s+(?:{_VERDICT_TOKENS})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bthis\s+(?:PR|change|code)\s+is\s+(?:{_VERDICT_TOKENS})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:{_VERDICT_TOKENS}):\s*true\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:{_OFFICIAL_TOKENS}):\s*\d",
        re.IGNORECASE,
    ),
    re.compile(r"\bofficial_fields_emitted:\s*true\b", re.IGNORECASE),
    re.compile(r"\bauthoritative:\s*true\b", re.IGNORECASE),
    re.compile(
        r"\benable-tool-gateway\s*:\s*['\"]?true['\"]?\s+by\s+default\b",
        re.IGNORECASE,
    ),
)


_NEGATION_CONTEXT_RE = re.compile(
    r"(?:does\s+NOT|do\s+not|don't|NEVER|must\s+not|is\s+NOT|are\s+NOT|"
    r"NOT\s+mean|forbidden|forbids|reject|banned|misreading|"
    r"NOT\s+a\s+claim|cautionary|do\s+NOT\s+read|wrong\s+by\s+design|"
    r"does\s+not\s+mean|read\s+it\s+as|stays?\s+blocked|stay\s+blocked|"
    r"remain\s+blocked|stays?\s+null|remains?\s+null|"
    r"refuses?\s+to\s+emit|reject\w*\s+any\s+response|"
    r"runners?\s+(?:reject|refuse)|cannot\s+tell\s+you|"
    r"will\s+never\s+produce)",
    re.IGNORECASE,
)


def _is_negated_context(body: str, match: re.Match[str]) -> bool:
    """Return True if a forbidden token match sits inside a negating
    sentence/table cell — i.e. it's documenting the forbidden shape,
    not asserting it. Three heuristics, any one being enough.
    """
    surroundings = body[
        max(0, match.start() - 2) : min(len(body), match.end() + 2)
    ]
    if (surroundings.startswith('"') and '"' in surroundings[1:]) or (
        surroundings.startswith("'") and "'" in surroundings[1:]
    ):
        return True
    window_start = max(0, match.start() - 500)
    if (
        _NEGATION_CONTEXT_RE.search(body[window_start : match.start()])
        is not None
    ):
        return True
    line_start = body.rfind("\n", 0, match.start()) + 1
    table_header_search_start = max(0, line_start - 4000)
    table_segment = body[table_header_search_start:line_start]
    for header_match in re.finditer(
        r"^(\|[^\n]+)\n\|[\s\-|:]+\|\s*$",
        table_segment,
        re.MULTILINE,
    ):
        header = header_match.group(1)
        if "NOT" in header.upper():
            return True
    return False


@pytest.mark.parametrize("doc_path", _ALL_PHASE6_DOCS, ids=_doc_id)
def test_phase6_0_user_facing_doc_exists(doc_path: Path) -> None:
    """Acceptance #2-#6: each Phase 6.0 user-facing doc must exist."""
    assert doc_path.is_file(), f"Phase 6.0 doc missing: {doc_path}"


@pytest.mark.parametrize("doc_path", _ALL_PHASE6_DOCS, ids=_doc_id)
def test_phase6_0_user_facing_doc_no_product_verdict_claim(
    doc_path: Path,
) -> None:
    """Acceptance #23: no false product verdict in any Phase 6.0
    user-facing doc. The negation detector lets cautionary mentions
    pass; only the abusive claim shapes fail the test.
    """
    body = doc_path.read_text(encoding="utf-8")
    abusive_hits: list[str] = []
    for pattern in _FORBIDDEN_VERDICT_CLAIM_PATTERNS:
        for match in pattern.finditer(body):
            if _is_negated_context(body, match):
                continue
            abusive_hits.append(
                f"{pattern.pattern!r}: {match.group(0)!r} "
                f"at offset {match.start()}",
            )
    assert not abusive_hits, (
        f"{doc_path.relative_to(_REPO_ROOT)} contains product-verdict "
        f"claim(s) outside of a negating context:\n  "
        + "\n  ".join(abusive_hits)
    )


@pytest.mark.parametrize(
    "doc_path", _GATEWAY_EXPLAINER_DOCS, ids=_doc_id,
)
def test_phase6_0_gateway_explainer_mentions_default_false(
    doc_path: Path,
) -> None:
    """Acceptance #16: each gateway-explainer doc must explain that
    enable-tool-gateway stays false by default. Accepts any of the
    canonical phrasings.
    """
    body = doc_path.read_text(encoding="utf-8")
    enable_proximity = re.compile(
        r"enable-tool-gateway[\s\S]{0,200}?(?:false|default|stays?|off)|"
        r"(?:false|default|stays?|off)[\s\S]{0,200}?enable-tool-gateway",
        re.IGNORECASE,
    )
    explicit_default = re.compile(
        r"(?:default\s+(?:false|`?\"?false\"?`?)|"
        r"defaults?\s+to\s+(?:false|`?\"?false\"?`?)|"
        r"stays\s+default\s+false|"
        r"stays\s+(?:false|`?\"?false\"?`?)|"
        r"off\s+by\s+default|"
        r"default\s+stays\s+(?:false|`?\"?false\"?`?))",
        re.IGNORECASE,
    )
    assert (
        enable_proximity.search(body) is not None
        or explicit_default.search(body) is not None
    ), (
        f"{doc_path.relative_to(_REPO_ROOT)} must mention that "
        f"enable-tool-gateway stays false by default"
    )


@pytest.mark.parametrize(
    "doc_path", _GATEWAY_EXPLAINER_DOCS, ids=_doc_id,
)
def test_phase6_0_gateway_explainer_mentions_official_fields_blocked(
    doc_path: Path,
) -> None:
    """Acceptance #15: each gateway-explainer doc must explain that
    official fields stay blocked / null / not emitted.
    """
    body = doc_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?:official\s+fields?\s+(?:stay|are|remain)\s+(?:blocked|null|unreachable|"
        r"not[\s-]?emitted|pinned)|"
        r"official\s+\w+\s+stay(?:s)?\s+null|"
        r"officially\s+(?:blocked|unreachable)|"
        r"`?total_v_net`?[^.\n]{0,400}?(?:null|unreachable|blocked|not[\s-]?emitted|pinned)|"
        r"ADR-22[^.\n]{0,200}?(?:wall|blocks|preserved)|"
        r"hard\s+wall(?:\s+preserved)?|"
        r"official_fields_emitted:\s*false|"
        r"no\s+`?total_v_net`?\s*[/\\,]|"
        r"no\s+(?:`?V_net`?|`?debt_final`?|`?corrupt_success`?)|"
        r"does\s+NOT\s+emit\s+(?:any|the)\s+(?:official|`?total_v_net`?)|"
        r"structurally\s+blocked|"
        r"pinned\s+as\s+null)",
        re.IGNORECASE | re.DOTALL,
    )
    assert pattern.search(body) is not None, (
        f"{doc_path.relative_to(_REPO_ROOT)} must explain that official "
        f"fields stay blocked / null / not emitted"
    )


@pytest.mark.parametrize(
    "doc_path", _GATEWAY_EXPLAINER_DOCS, ids=_doc_id,
)
def test_phase6_0_gateway_explainer_mentions_diagnostic_only(
    doc_path: Path,
) -> None:
    """Acceptance #17: each gateway-explainer doc must clarify that
    the gateway-grounded report is diagnostic, NOT a product verdict.
    Token "diagnostic" or "verification_candidate" must appear at
    least once.
    """
    body = doc_path.read_text(encoding="utf-8")
    assert (
        ("diagnostic" in body.lower())
        or ("verification_candidate" in body)
    ), (
        f"{doc_path.relative_to(_REPO_ROOT)} must clarify the "
        f"diagnostic-only nature of the report"
    )


# ---------------------------------------------------------------------------
# Cross-link integrity for the new docs
# ---------------------------------------------------------------------------


_MD_LINK_RE = re.compile(
    r"\[[^\]]+\]\(((?!https?://|mailto:|#)[^)]+)\)",
)


@pytest.mark.parametrize("doc_path", _ALL_PHASE6_DOCS, ids=_doc_id)
def test_phase6_0_user_facing_doc_relative_links_resolve(
    doc_path: Path,
) -> None:
    """All relative markdown links from Phase 6.0 docs must resolve."""
    body = doc_path.read_text(encoding="utf-8")
    base = doc_path.parent
    broken: list[str] = []
    for match in _MD_LINK_RE.finditer(body):
        target = match.group(1).split("#", 1)[0]
        if not target:
            continue
        resolved = (base / target).resolve()
        if not resolved.exists():
            broken.append(f"{match.group(0)} → {resolved}")
    assert not broken, (
        f"{doc_path.relative_to(_REPO_ROOT)} has broken relative links:\n  "
        + "\n  ".join(broken)
    )


# ---------------------------------------------------------------------------
# Beta feedback aggregator: zero-feedback case handled cleanly (#9-#11)
# ---------------------------------------------------------------------------


_BETA_FEEDBACK_AGGREGATE_JSON = (
    _REPO_ROOT / "reports" / "beta" / "beta_feedback_aggregate.json"
)
_BETA_FEEDBACK_AGGREGATE_MD = (
    _REPO_ROOT / "reports" / "beta" / "beta_feedback_aggregate.md"
)
_BETA_CASES_REGISTRY = _REPO_ROOT / "reports" / "beta" / "beta_cases.md"
_BETA_FEEDBACK_SCRIPT = (
    _REPO_ROOT / "scripts" / "run_beta_feedback_eval.py"
)


def test_phase6_0_beta_feedback_script_exists() -> None:
    """Acceptance #11-#14: the metric script must be present."""
    assert _BETA_FEEDBACK_SCRIPT.is_file(), (
        f"missing {_BETA_FEEDBACK_SCRIPT}"
    )


def test_phase6_0_beta_feedback_aggregate_json_present() -> None:
    """Acceptance #11: the aggregate JSON must exist (initial state
    is the zero-feedback empty aggregate)."""
    assert _BETA_FEEDBACK_AGGREGATE_JSON.is_file(), (
        f"missing {_BETA_FEEDBACK_AGGREGATE_JSON}"
    )


def test_phase6_0_beta_feedback_aggregate_md_present() -> None:
    """Acceptance #11: the aggregate Markdown must exist."""
    assert _BETA_FEEDBACK_AGGREGATE_MD.is_file(), (
        f"missing {_BETA_FEEDBACK_AGGREGATE_MD}"
    )


def test_phase6_0_beta_cases_registry_present() -> None:
    """Acceptance #1-#6: the cases registry must exist."""
    assert _BETA_CASES_REGISTRY.is_file(), (
        f"missing {_BETA_CASES_REGISTRY}"
    )


def test_phase6_0_beta_feedback_aggregate_carries_diagnostic_only() -> None:
    """Acceptance #16-#23: the aggregate must carry
    `gateway_status: diagnostic_only` and
    `official_fields_emitted: false` even in the zero-feedback case.
    """
    data = json.loads(
        _BETA_FEEDBACK_AGGREGATE_JSON.read_text(encoding="utf-8"),
    )
    assert data["gateway_status"] == "diagnostic_only"
    assert data["official_fields_emitted"] is False
    assert data["official_field_leak_count"] == 0


def test_phase6_0_beta_feedback_aggregate_carries_17_metrics() -> None:
    """Acceptance #11-#14: the aggregate must carry every metric
    listed in QA/A41 §6.0-E. Missing keys would mean the script
    silently dropped a metric.
    """
    data = json.loads(
        _BETA_FEEDBACK_AGGREGATE_JSON.read_text(encoding="utf-8"),
    )
    required = (
        "beta_cases_total",
        "beta_cases_completed",
        "operators_total",
        "operator_usefulness_rate",
        "summary_readability_avg",
        "evidence_traceability_avg",
        "actionability_avg",
        "no_false_verdict_avg",
        "setup_friction_avg",
        "would_use_again_yes_count",
        "would_use_again_maybe_count",
        "would_use_again_no_count",
        "official_field_leak_count",
        "false_positive_count",
        "false_negative_count",
        "unclear_count",
        "insufficient_fixture_count",
    )
    missing = [key for key in required if key not in data]
    assert not missing, (
        f"beta_feedback_aggregate.json missing keys: {missing}"
    )


def test_phase6_0_beta_feedback_aggregate_zero_feedback_state() -> None:
    """The initial Phase 6.0 state is zero feedback. The aggregate
    must reflect this cleanly with `recommendation: continue_beta`
    and `beta_cases_total: 0`. This is the QA/A41 partial-completion
    authorization (criteria #7-#10) frozen as a structural test.
    """
    data = json.loads(
        _BETA_FEEDBACK_AGGREGATE_JSON.read_text(encoding="utf-8"),
    )
    if data["beta_cases_total"] == 0:
        assert data["recommendation"] == "continue_beta", (
            f"zero-feedback recommendation must be continue_beta, "
            f"got {data['recommendation']!r}"
        )
        assert data["operator_usefulness_rate"] == 0.0


# ---------------------------------------------------------------------------
# Anti-MCP / no-default-flip locks for Phase 6.0 (#16-#22)
# ---------------------------------------------------------------------------


def test_phase6_0_action_yml_keeps_enable_tool_gateway_default_false() -> None:
    """Acceptance #16: Phase 6.0 must NOT flip the action default."""
    action_yml = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    pattern = re.compile(
        r"enable-tool-gateway:\s*\n\s*description:[\s\S]+?default:\s*\"false\"",
    )
    assert pattern.search(action_yml) is not None, (
        "action.yml must keep enable-tool-gateway default at \"false\""
    )


def test_phase6_0_no_mcp_runtime_added() -> None:
    """Acceptance #18-#20: Phase 6.0 must NOT add MCP / JSON-RPC
    runtime code anywhere in src/.
    """
    src_root = _REPO_ROOT / "src" / "oida_code"
    forbidden_imports = (
        "import mcp",
        "from mcp ",
        "import jsonrpc",
        "from jsonrpc ",
    )
    hits: list[str] = []
    for py_path in src_root.rglob("*.py"):
        if "_vendor" in py_path.parts:
            continue
        body = py_path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            if forbidden in body:
                hits.append(
                    f"{py_path.relative_to(_REPO_ROOT)}: {forbidden}",
                )
    assert not hits, (
        "Phase 6.0 must not add MCP / JSON-RPC runtime imports:\n  "
        + "\n  ".join(hits)
    )


def test_phase6_0_no_mcp_workflow_added() -> None:
    """Acceptance #19: Phase 6.0 must NOT add an MCP workflow file.
    Searches for any workflow whose name or run-name mentions MCP.
    """
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return
    hits: list[str] = []
    for yml_path in workflows_dir.rglob("*.yml"):
        body = yml_path.read_text(encoding="utf-8")
        if re.search(r"\bmcp\b", body, re.IGNORECASE) and (
            "name:" in body or "uses:" in body
        ):
            # Only flag if the MCP token appears in a workflow
            # field, not in a comment forbidding it.
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\bmcp\b", stripped, re.IGNORECASE):
                    hits.append(
                        f"{yml_path.relative_to(_REPO_ROOT)}: {stripped}",
                    )
                    break
    assert not hits, (
        "Phase 6.0 must not add MCP workflows:\n  " + "\n  ".join(hits)
    )


def test_phase6_0_phase5_locks_preserved() -> None:
    """Anti-regression: the Phase 5.x locks remain ACTIVE.
    Specifically: the no-product-verdict policy doc still exists
    and still enumerates the forbidden tokens.
    """
    policy = (
        _REPO_ROOT
        / "docs"
        / "security"
        / "no_product_verdict_policy.md"
    )
    assert policy.is_file(), (
        f"{policy} must exist (Phase 5.9 lock)"
    )
    body = policy.read_text(encoding="utf-8")
    for token in (
        "merge-safe",
        "production-safe",
        "bug-free",
        "total_v_net",
        "debt_final",
        "corrupt_success",
    ):
        assert token in body, (
            f"no_product_verdict_policy.md missing token {token!r}"
        )


# ---------------------------------------------------------------------------
# BACKLOG.md is a record, NOT a roadmap (#part of acceptance #1 expanded)
# ---------------------------------------------------------------------------


def test_phase6_0_backlog_md_present_and_disclaims_roadmap() -> None:
    """The BACKLOG.md file must exist and explicitly state it is NOT
    a roadmap. This is the QA/A41 addendum directive: 'Record
    Grok-style long-term gaps as backlog, not as Phase 6.0 scope.'
    """
    backlog = _REPO_ROOT / "BACKLOG.md"
    assert backlog.is_file(), f"missing {backlog}"
    body = backlog.read_text(encoding="utf-8")
    # Must contain a disclaimer that this is not a phase commitment
    # / not a roadmap. Accepts several phrasings.
    pattern = re.compile(
        r"(?:not\s+a\s+roadmap|"
        r"not\s+a\s+phase\s+commitment|"
        r"not\s+(?:a\s+)?phase\s+scope|"
        r"explicitly\s+not\s+(?:a|in)\s+(?:roadmap|phase\s+scope|scope))",
        re.IGNORECASE,
    )
    assert pattern.search(body) is not None, (
        "BACKLOG.md must explicitly disclaim being a roadmap / phase "
        "commitment per QA/A41 addendum"
    )


# ---------------------------------------------------------------------------
# docs/beta/ directory index points at every leaf doc
# ---------------------------------------------------------------------------


def test_phase6_0_beta_index_links_to_every_leaf_doc() -> None:
    """`docs/beta/README.md` must link to every leaf doc in the pack."""
    index = (_REPO_ROOT / "docs" / "beta" / "README.md").read_text(
        encoding="utf-8",
    )
    expected_leafs = (
        "beta_known_limits.md",
        "beta_operator_quickstart.md",
        "beta_case_template.md",
        "beta_feedback_form.md",
    )
    for leaf in expected_leafs:
        assert leaf in index, (
            f"docs/beta/README.md must link to {leaf!r}"
        )


# ---------------------------------------------------------------------------
# project_status.md carries the four required sections (per addendum)
# ---------------------------------------------------------------------------


def test_phase6_0_project_status_carries_four_sections() -> None:
    """QA/A41 addendum §2: docs/project_status.md must carry sections
    for: usable now, blocked fields, out-of-scope, current roadmap.
    """
    body = (_REPO_ROOT / "docs" / "project_status.md").read_text(
        encoding="utf-8",
    )
    required_sections = (
        re.compile(r"^##\s.*usable\s+now", re.IGNORECASE | re.MULTILINE),
        re.compile(
            r"^##\s.*blocked", re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^##\s.*out\s+of\s+scope", re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^##\s.*roadmap", re.IGNORECASE | re.MULTILINE,
        ),
    )
    missing: list[str] = []
    for pattern in required_sections:
        if pattern.search(body) is None:
            missing.append(pattern.pattern)
    assert not missing, (
        f"docs/project_status.md missing required sections: {missing}"
    )
