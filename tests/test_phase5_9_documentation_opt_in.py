"""Phase 5.9 (QA/A40, ADR-49) — documentation opt-in path doc-guard tests.

QA/A40 acceptance criteria 1-10 land here as structural locks. The
overarching rule is **scoped enforcement** — these tests must NOT
scan files that legitimately reproduce the forbidden product-verdict
tokens in their forbidden role (security policy docs, ADRs that
quote the wall, reports' honesty statements). The Phase 5.0 / ADR-35
SCOPED-checks precedent is the model: scope = the new user-facing
files only.

The user-facing scope for Phase 5.9 is:

* docs/gateway_opt_in_usage.md
* docs/interpreting_gateway_reports.md
* docs/operator_soak_runbook.md
* examples/gateway_opt_in/README.md

Out-of-scope for the verdict-token scan (these intentionally
reproduce the tokens to forbid them):

* docs/security/no_product_verdict_policy.md
* memory-bank/decisionLog.md (ADRs)
* reports/*.md (honesty statements)

The five committed operator-soak case READMEs and the bundle JSONs
get their own structural checks below (status alignment with
aggregate, label/ux provenance).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Phase 5.9 user-facing files — the scoped set
# ---------------------------------------------------------------------------


_USER_FACING_DOCS: tuple[Path, ...] = (
    _REPO_ROOT / "docs" / "gateway_opt_in_usage.md",
    _REPO_ROOT / "docs" / "interpreting_gateway_reports.md",
    _REPO_ROOT / "docs" / "operator_soak_runbook.md",
    _REPO_ROOT / "examples" / "gateway_opt_in" / "README.md",
)


def _doc_id(path: Path) -> str:
    """Pytest parametrize id helper — keeps decorator lines short."""
    return path.relative_to(_REPO_ROOT).as_posix()


# Forbidden product-verdict tokens. The phrasing matches the
# no-product-verdict policy doc. The scoped scan asserts these do not
# appear AS PRODUCT CLAIMS in the user-facing file set.
#
# Detection strategy: regex with a sentence-claim shape, NOT a bare
# substring match. The user-facing docs MAY mention these tokens in
# warning rows ("does NOT mean: 'merge-safe'") — those mentions sit
# inside markdown table cells next to "does NOT mean" or under a
# "What this does NOT do" / "misreading" header. The regex anchors on
# claim shapes ("the code is", "this is", "is now") followed by a
# token, which is the abusive form we want to catch.
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


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_exists(doc_path: Path) -> None:
    """Acceptance #2-#5: each user-facing doc file must exist."""
    assert doc_path.is_file(), f"Phase 5.9 doc missing: {doc_path}"


_NEGATION_CONTEXT_RE = re.compile(
    # Negation cues that indicate the match is cautionary / forbidden,
    # not asserted. Window scanned ~120 chars before the match.
    r"(?:does\s+NOT|do\s+not|don't|NEVER|must\s+not|is\s+NOT|are\s+NOT|"
    r"NOT\s+mean|forbidden|forbids|reject|banned|misreading|"
    r"NOT\s+a\s+claim|cautionary|do\s+NOT\s+read|wrong\s+by\s+design|"
    r"does\s+not\s+mean|read\s+it\s+as)",
    re.IGNORECASE,
)


def _is_negated_context(body: str, match: re.Match[str]) -> bool:
    """Return True if a forbidden token match sits inside a negating
    sentence/table cell — i.e. it's documenting the forbidden shape,
    not asserting it.

    Three heuristics, any one being enough:

    1. The match is inside a quoted string (`"..."` or `'...'`),
       which signals a forbidden-phrase enumeration in a markdown
       table cell or a forbidden list.
    2. A negation cue (Do NOT, does NOT, NEVER, must not, ...)
       appears in the 500 characters before the match — markdown
       tables can have wide columns, so 120 chars is too narrow.
    3. The match sits in a markdown table whose header column
       includes "NOT" (e.g. "Do NOT read it as", "What it does
       NOT mean").
    """
    # Heuristic 1 — direct enclosing quotes around the match.
    surroundings = body[max(0, match.start() - 2) : min(len(body), match.end() + 2)]
    if (surroundings.startswith('"') and '"' in surroundings[1:]) or (
        surroundings.startswith("'") and "'" in surroundings[1:]
    ):
        return True

    # Heuristic 2 — wider negation cue window.
    window_start = max(0, match.start() - 500)
    if _NEGATION_CONTEXT_RE.search(body[window_start : match.start()]) is not None:
        return True

    # Heuristic 3 — markdown table column headed with "NOT".
    line_start = body.rfind("\n", 0, match.start()) + 1
    table_header_search_start = max(0, line_start - 4000)
    table_segment = body[table_header_search_start:line_start]
    # Find the most recent table header (line starting with `|`
    # whose next line is the separator `|---|`).
    for header_match in re.finditer(
        r"^(\|[^\n]+)\n\|[\s\-|:]+\|\s*$",
        table_segment,
        re.MULTILINE,
    ):
        header = header_match.group(1)
        if "NOT" in header.upper():
            return True
    return False


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_no_product_verdict_claim(doc_path: Path) -> None:
    """Acceptance #9: no false product verdict in the scoped user-facing
    docs. The regex catches the abusive claim shapes; mentions inside
    "does NOT mean" rows or "misreading" tables are fine because they
    are cautioning against the claim, not making it. The
    `_is_negated_context` helper distinguishes the two.
    """
    body = doc_path.read_text(encoding="utf-8")
    abusive_hits: list[str] = []
    for pattern in _FORBIDDEN_VERDICT_CLAIM_PATTERNS:
        for match in pattern.finditer(body):
            if _is_negated_context(body, match):
                continue
            abusive_hits.append(
                f"{pattern.pattern!r}: {match.group(0)!r} at offset {match.start()}"
            )
    assert not abusive_hits, (
        f"{doc_path.relative_to(_REPO_ROOT)} contains product-verdict "
        f"claim(s) outside of a negating context:\n  "
        + "\n  ".join(abusive_hits)
    )


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_mentions_default_false(doc_path: Path) -> None:
    """Acceptance #6: each user-facing doc must explain that
    enable-tool-gateway stays false by default. Accepts any of the
    canonical phrasings — "defaults to false", "default false", "stays
    default false", "stays false" near the gateway input name, etc.
    """
    body = doc_path.read_text(encoding="utf-8")
    # Either "enable-tool-gateway" mentioned within 80 chars of a
    # default-false phrase, OR a generic "default false" / "stays
    # default false" / "default `\"false\"`" phrase.
    enable_proximity = re.compile(
        r"enable-tool-gateway[\s\S]{0,80}?(?:false|default|stays?)|"
        r"(?:false|default|stays?)[\s\S]{0,80}?enable-tool-gateway",
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
    assert enable_proximity.search(body) is not None or explicit_default.search(body) is not None, (
        f"{doc_path.relative_to(_REPO_ROOT)} must mention that "
        f"enable-tool-gateway stays false by default"
    )


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_mentions_official_fields_blocked(doc_path: Path) -> None:
    """Acceptance #8: each user-facing doc must explain that official
    fields stay blocked / null / not emitted. Multiple acceptable
    phrasings — "official fields stay null", "ADR-22 hard wall",
    "No total_v_net ... emission", "official_fields_emitted: false",
    etc.
    """
    body = doc_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?:official\s+fields?\s+(?:stay|are|remain)\s+(?:blocked|null|unreachable)|"
        r"official\s+\w+\s+stay(?:s)?\s+null|"
        r"officially\s+(?:blocked|unreachable)|"
        r"`?total_v_net`?[^.\n]{0,400}?(?:null|unreachable|blocked)|"
        r"ADR-22[^.\n]{0,200}?(?:wall|blocks|preserved)|"
        r"hard\s+wall(?:\s+preserved)?|"
        r"official_fields_emitted:\s*false|"
        r"no\s+`?total_v_net`?\s*[/\\,]|"
        r"no\s+(?:`?V_net`?|`?debt_final`?|`?corrupt_success`?)|"
        r"does\s+NOT\s+emit\s+(?:any|the)\s+(?:official|`?total_v_net`?))",
        re.IGNORECASE | re.DOTALL,
    )
    assert pattern.search(body) is not None, (
        f"{doc_path.relative_to(_REPO_ROOT)} must explain that official "
        f"fields stay blocked / null / not emitted"
    )


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_mentions_diagnostic_only(doc_path: Path) -> None:
    """Acceptance #7: each user-facing doc must clarify that
    verification_candidate / diagnostic_only stays diagnostic, NOT a
    product verdict. Token "diagnostic" or "verification_candidate"
    must appear at least once.
    """
    body = doc_path.read_text(encoding="utf-8")
    assert ("diagnostic" in body.lower()) or ("verification_candidate" in body), (
        f"{doc_path.relative_to(_REPO_ROOT)} must clarify the "
        f"diagnostic-only nature of the report"
    )


# ---------------------------------------------------------------------------
# Cross-link integrity for the new docs
# ---------------------------------------------------------------------------


_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(((?!https?://|mailto:|#)[^)]+)\)")


@pytest.mark.parametrize("doc_path", _USER_FACING_DOCS, ids=_doc_id)
def test_phase5_9_user_facing_doc_relative_links_resolve(doc_path: Path) -> None:
    """All relative markdown links from the user-facing docs must
    resolve. Catches drift between the example, the docs, and the
    operator-soak case READMEs.
    """
    body = doc_path.read_text(encoding="utf-8")
    base = doc_path.parent
    broken: list[str] = []
    for match in _MD_LINK_RE.finditer(body):
        target = match.group(1).split("#", 1)[0]  # strip anchor
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
# Operator-soak case README alignment with aggregate (acceptance #1)
# ---------------------------------------------------------------------------


_AGGREGATE_PATH = _REPO_ROOT / "reports" / "operator_soak" / "aggregate.json"
_CASES_DIR = _REPO_ROOT / "operator_soak_cases"


def test_phase5_9_all_completed_cases_have_complete_status_in_readme() -> None:
    """Acceptance #1: no case README may say `awaiting_*` if the
    aggregate marks the case complete. This is the drift QA/A40
    flagged on case_002 specifically; the test enforces the
    invariant for all 5 cases.
    """
    aggregate = json.loads(_AGGREGATE_PATH.read_text(encoding="utf-8"))
    drifts: list[str] = []
    for case in aggregate.get("cases", []):
        case_id = case["case_id"]
        case_status = case["status"]
        readme_path = _CASES_DIR / case_id / "README.md"
        if not readme_path.is_file():
            continue
        body = readme_path.read_text(encoding="utf-8")
        if case_status == "complete":
            # Drift signature: README says `awaiting_run` or
            # `awaiting_real_audit_packet_decision` or
            # `awaiting_label` etc. but aggregate says complete.
            if re.search(r"`awaiting_[a-z_]+`", body):
                drifts.append(
                    f"{case_id}: README mentions `awaiting_*` but aggregate "
                    f"says complete"
                )
            # Status section must say complete somewhere.
            status_section = re.search(
                r"##\s*Status\b[\s\S]{0,500}",
                body,
            )
            if status_section is not None:
                section_text = status_section.group(0)
                if "complete" not in section_text.lower():
                    drifts.append(
                        f"{case_id}: ## Status section does not mention "
                        f"`complete`"
                    )
    assert not drifts, "Case README drift detected:\n  " + "\n  ".join(drifts)


def test_phase5_9_all_completed_cases_carry_run_id_in_readme() -> None:
    """Acceptance #10: each completed case README must carry the
    workflow_run_id matching its fiche.json. Catches drift after
    re-dispatches (e.g. case_003's run 25045245609 → 25047711777
    re-dispatch in Phase 5.8.x).
    """
    aggregate = json.loads(_AGGREGATE_PATH.read_text(encoding="utf-8"))
    drifts: list[str] = []
    for case in aggregate.get("cases", []):
        case_id = case["case_id"]
        if case["status"] != "complete":
            continue
        run_id = case.get("workflow_run_id")
        if not run_id:
            continue
        readme_path = _CASES_DIR / case_id / "README.md"
        if not readme_path.is_file():
            continue
        body = readme_path.read_text(encoding="utf-8")
        if run_id not in body:
            drifts.append(
                f"{case_id}: README does not contain workflow_run_id "
                f"{run_id!r}"
            )
    assert not drifts, "Case README run_id drift:\n  " + "\n  ".join(drifts)


# ---------------------------------------------------------------------------
# examples/gateway_opt_in/ bundle is structurally valid (acceptance #5)
# ---------------------------------------------------------------------------


_EXAMPLE_DIR = _REPO_ROOT / "examples" / "gateway_opt_in"
_REQUIRED_BUNDLE_FILES: tuple[str, ...] = (
    "approved_tools.json",
    "gateway_definitions.json",
    "packet.json",
    "pass1_backward.json",
    "pass1_forward.json",
    "pass2_backward.json",
    "pass2_forward.json",
    "tool_policy.json",
)


def test_phase5_9_example_bundle_carries_all_required_files() -> None:
    """The example bundle must carry all 8 required files."""
    for filename in _REQUIRED_BUNDLE_FILES:
        path = _EXAMPLE_DIR / filename
        assert path.is_file(), (
            f"examples/gateway_opt_in/ missing required {filename!r}"
        )


def test_phase5_9_example_bundle_validates_against_schemas() -> None:
    """The example bundle must validate against the Phase 5.2 / 5.8.x
    Pydantic schemas. Drift between the schema and the example would
    surface as a future operator getting a stale walkthrough.
    """
    from oida_code.estimators.llm_prompt import LLMEvidencePacket
    from oida_code.verifier.contracts import (
        BackwardVerificationResult,
        ForwardVerificationResult,
    )
    from oida_code.verifier.tool_gateway.contracts import (
        GatewayToolDefinition,
        ToolAdmissionRegistry,
    )
    from oida_code.verifier.tools import ToolPolicy

    packet_data = json.loads(
        (_EXAMPLE_DIR / "packet.json").read_text(encoding="utf-8"),
    )
    LLMEvidencePacket.model_validate(packet_data)

    for forward_name in ("pass1_forward.json", "pass2_forward.json"):
        ForwardVerificationResult.model_validate(
            json.loads((_EXAMPLE_DIR / forward_name).read_text(encoding="utf-8"))
        )

    for backward_name in ("pass1_backward.json", "pass2_backward.json"):
        backward_data = json.loads(
            (_EXAMPLE_DIR / backward_name).read_text(encoding="utf-8"),
        )
        if isinstance(backward_data, list):
            for item in backward_data:
                BackwardVerificationResult.model_validate(item)
        else:
            BackwardVerificationResult.model_validate(backward_data)

    ToolPolicy.model_validate(
        json.loads(
            (_EXAMPLE_DIR / "tool_policy.json").read_text(encoding="utf-8"),
        ),
    )
    gateway_defs = json.loads(
        (_EXAMPLE_DIR / "gateway_definitions.json").read_text(encoding="utf-8"),
    )
    for value in gateway_defs.values():
        GatewayToolDefinition.model_validate(value)
    ToolAdmissionRegistry.model_validate(
        json.loads(
            (_EXAMPLE_DIR / "approved_tools.json").read_text(encoding="utf-8"),
        ),
    )


def test_phase5_9_example_bundle_repo_root_is_dot() -> None:
    """The example must use `repo_root="."` (self-audit) so it can be
    reproduced in CI without any external clone or editable install.
    """
    policy = json.loads(
        (_EXAMPLE_DIR / "tool_policy.json").read_text(encoding="utf-8"),
    )
    assert policy["repo_root"] == ".", (
        f"example tool_policy.repo_root must be '.' for self-audit, "
        f"got {policy['repo_root']!r}"
    )


# ---------------------------------------------------------------------------
# Anti-MCP / no-default-flip locks for Phase 5.9 (additive)
# ---------------------------------------------------------------------------


def test_phase5_9_action_yml_keeps_enable_tool_gateway_default_false() -> None:
    """Phase 5.9 must NOT flip the action default. Anti-regression."""
    action_yml = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    pattern = re.compile(
        r"enable-tool-gateway:\s*\n\s*description:[\s\S]+?default:\s*\"false\"",
    )
    assert pattern.search(action_yml) is not None, (
        "action.yml must keep enable-tool-gateway default at \"false\""
    )


def test_phase5_9_no_mcp_runtime_added() -> None:
    """Phase 5.9 must NOT add MCP runtime code anywhere in src/."""
    src_root = _REPO_ROOT / "src" / "oida_code"
    forbidden_imports = (
        "import mcp",
        "from mcp ",
        "import jsonrpc",
        "from jsonrpc ",
    )
    hits: list[str] = []
    for py_path in src_root.rglob("*.py"):
        # Skip the vendored OIDA core.
        if "_vendor" in py_path.parts:
            continue
        body = py_path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            if forbidden in body:
                hits.append(f"{py_path.relative_to(_REPO_ROOT)}: {forbidden}")
    assert not hits, (
        "Phase 5.9 must not add MCP / JSON-RPC runtime imports:\n  "
        + "\n  ".join(hits)
    )


# ---------------------------------------------------------------------------
# Aggregate carries five cases summary (acceptance #10 finalisation)
# ---------------------------------------------------------------------------


def test_phase5_9_aggregate_carries_five_completed_cases() -> None:
    """Acceptance #10: the five cases are summarised in a clear table.
    The aggregate's table is regenerated by the eval script and is
    the source of truth.
    """
    aggregate_md = (_REPO_ROOT / "reports" / "operator_soak" / "aggregate.md").read_text(
        encoding="utf-8",
    )
    expected_case_ids = (
        "case_001_oida_code_self",
        "case_002_python_semver",
        "case_003_markupsafe",
        "case_004_python_slugify",
        "case_005_voluptuous",
    )
    for case_id in expected_case_ids:
        assert case_id in aggregate_md, (
            f"aggregate.md missing row for {case_id}"
        )
    aggregate_json = json.loads(_AGGREGATE_PATH.read_text(encoding="utf-8"))
    assert aggregate_json["cases_completed"] == 5
    assert aggregate_json["useful_true_positive_count"] == 5
    assert aggregate_json["recommendation"] == "document_opt_in_path"
