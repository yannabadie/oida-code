"""Phase 4.9-B + 4.9-C (QA/A26.md, ADR-34) — GitHub Step Summary
polish + SARIF category disambiguation tests.

4.9-B invariants:

* The composite action.yml MUST cat the polished diagnostic
  Markdown into ``$GITHUB_STEP_SUMMARY`` when it exists.
* The step summary MUST NOT carry raw provider responses, raw
  prompts, or API keys (these are already redacted upstream; this
  test locks the action.yml's `head -n` quoting and ordering).
* The step summary MUST NOT contain forbidden product claims
  (``merge_safe`` / ``production_safe`` / ``bug_free`` etc.) —
  the underlying diagnostic_report renderer enforces this; here
  we only check the action.yml never re-introduces them via
  echo/printf.

4.9-C invariants:

* The SARIF uploader in ``action.yml`` is ``@v4`` (was ``@v3``
  until Phase 4.7) and sets an explicit ``category`` so multiple
  SARIF uploads on the same commit do not collide in Code Scanning.
* The dedicated ``sarif-upload.yml`` workflow already pins ``@v4``
  (Phase 4.7) — this file additionally locks it for the action.
* Categories use the ``oida-code/`` prefix (criterion
  ``test_sarif_category_uses_oida_prefix``).
* Report rendering documents the category strategy.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 4.9-B — GitHub Step Summary polish
# ---------------------------------------------------------------------------


def test_step_summary_contains_diagnostic_only() -> None:
    """The action.yml step summary path MUST end up containing the
    diagnostic banner — either by piping the polished diagnostic
    Markdown (which carries the banner) into $GITHUB_STEP_SUMMARY,
    or by writing the banner directly. We assert via static check
    that the action.yml routes through the diagnostic Markdown."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    # The polished diagnostic file MUST flow into $GITHUB_STEP_SUMMARY.
    assert re.search(
        r'cat\s+"\$DIAGNOSTIC_MD"\s*>>\s*"\$GITHUB_STEP_SUMMARY"',
        body,
    ), (
        "action.yml does not cat the polished diagnostic markdown "
        "into $GITHUB_STEP_SUMMARY — Phase 4.9-B violated"
    )


def test_step_summary_contains_artifact_paths() -> None:
    """The step summary MUST surface the artifact paths (or at least
    list them as outputs). We check that the action.yml emits
    `report-json`, `report-markdown`, `report-sarif`,
    `calibration-metrics`, and `diagnostic-markdown` to
    $GITHUB_OUTPUT — those are picked up by the consumer workflow
    and surfaced in the run UI."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    for name in (
        "report-json",
        "report-markdown",
        "report-sarif",
        "calibration-metrics",
        "diagnostic-markdown",
    ):
        # Each name must appear in a `>> "$GITHUB_OUTPUT"` line.
        pattern = re.compile(
            rf'echo\s+"{re.escape(name)}=.+?"\s*>>\s*"\$GITHUB_OUTPUT"',
        )
        assert pattern.search(body), (
            f"action.yml never emits `{name}=...` to $GITHUB_OUTPUT — "
            "the consumer workflow cannot surface this artifact"
        )


def test_step_summary_does_not_contain_secret_like_values() -> None:
    """The action.yml MUST NEVER reference `${{ secrets.* }}` from
    inside a `run:` block (Phase 4.5.1 hardening + Phase 4.9-B
    re-affirmation). Secrets flow strictly via env: → $VAR."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    # Find the bash heredoc that builds $GITHUB_STEP_SUMMARY.
    # Anywhere in the action.yml run block must not interpolate
    # secrets directly.
    secret_in_run = re.compile(r"\$\{\{\s*secrets\.[A-Z_]+\s*\}\}")
    assert not secret_in_run.search(body), (
        "action.yml references ${{ secrets.* }} in a `run:` block — "
        "Phase 4.5.1 + 4.9-B forbid this; use env: → $VAR instead"
    )


def test_step_summary_does_not_contain_forbidden_product_claims() -> None:
    """The action.yml MUST NOT echo/printf the forbidden product
    claims into $GITHUB_STEP_SUMMARY directly. The underlying
    diagnostic_report renderer rejects them at render time; this
    test guards against a stale shell template re-introducing them."""
    body = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    # Find the lines that flow into GITHUB_STEP_SUMMARY.
    summary_section = re.findall(
        r"GITHUB_STEP_SUMMARY[^\n]*\n(.*?)(?=\n[a-zA-Z_]|\Z)",
        body, flags=re.DOTALL,
    )
    summary_text = "\n".join(summary_section).lower()
    for forbidden in (
        "merge_safe", "merge-safe",
        "production_safe", "production-safe",
        "bug_free", "bug-free",
    ):
        assert forbidden not in summary_text, (
            f"action.yml step summary echoes forbidden product claim "
            f"{forbidden!r}"
        )


# ---------------------------------------------------------------------------
# 4.9-C — SARIF category disambiguation
# ---------------------------------------------------------------------------


def test_sarif_upload_category_is_explicit() -> None:
    """Both the action.yml composite step AND the dedicated
    sarif-upload.yml workflow MUST set an explicit `category:` on
    the upload-sarif step."""
    for relative in (
        "action.yml",
        ".github/workflows/sarif-upload.yml",
    ):
        body = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        # Only check files that actually invoke upload-sarif.
        if "github/codeql-action/upload-sarif" not in body:
            continue
        assert re.search(
            r"category:\s*oida-code/", body,
        ), f"{relative} upload-sarif step missing `category:` line"


def test_sarif_category_uses_oida_prefix() -> None:
    """All SARIF categories used by this repo MUST start with the
    `oida-code/` prefix so Code Scanning groups them correctly and
    a future addition (e.g., a separate ruff-only upload) can
    coexist without overwriting the others."""
    for relative in (
        "action.yml",
        ".github/workflows/sarif-upload.yml",
    ):
        body = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        if "github/codeql-action/upload-sarif" not in body:
            continue
        for match in re.finditer(r"category:\s*(\S+)", body):
            category = match.group(1)
            assert category.startswith("oida-code/"), (
                f"{relative} uses SARIF category {category!r} not "
                "starting with `oida-code/` — Phase 4.9-C violated"
            )


def test_sarif_multiple_categories_do_not_collide() -> None:
    """If multiple SARIF uploads exist anywhere in the repo, each
    MUST use a DIFFERENT category. Two uploads with the same
    category overwrite each other in Code Scanning."""
    seen: dict[str, str] = {}
    for path in _REPO_ROOT.rglob("*.yml"):
        if "node_modules" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        if "github/codeql-action/upload-sarif" not in body:
            continue
        for match in re.finditer(r"category:\s*(\S+)", body):
            category = match.group(1)
            relative = str(path.relative_to(_REPO_ROOT))
            if category in seen and seen[category] != relative:
                # Two DIFFERENT files using the same category — this
                # is the collision we guard against.
                raise AssertionError(
                    f"SARIF category {category!r} used by both "
                    f"{seen[category]} and {relative} — they will "
                    "collide in Code Scanning",
                )
            seen[category] = relative


def test_sarif_report_documents_category_strategy() -> None:
    """The Phase 4.9 report MUST document the SARIF category
    strategy so an operator can discover why the categories use
    the `oida-code/` prefix."""
    report_path = _REPO_ROOT / "reports" / "phase4_9_artifact_ux_polish.md"
    if not report_path.is_file():
        # Report is added at end of Phase 4.9; skip when absent so
        # we can land tests block-by-block.
        import pytest
        pytest.skip("Phase 4.9 report not yet present")
    body = report_path.read_text(encoding="utf-8")
    assert "SARIF category" in body or "sarif category" in body.lower(), (
        "Phase 4.9 report does not document the SARIF category strategy"
    )
