"""Phase 4.8 (QA/A25.md, ADR-33) — workflow + docs invariants.

Two surfaces:

* `.github/workflows/provider-baseline-node24-smoke.yml` — replay-
  only smoke that pins `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`
  to prove the provider-baseline surface survives the GitHub
  Node 24 default switch (2026-06-02).
* README.md — Phase 4.6 paragraph used to claim
  `upload-sarif@v3` and `provider baseline not_run`; both are now
  stale post-Phase 4.7. Tests lock the cleanup so a future
  contributor can't silently re-introduce a contradiction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_NODE24_SMOKE = _WORKFLOW_DIR / "provider-baseline-node24-smoke.yml"
_PROVIDER_BASELINE = _WORKFLOW_DIR / "provider-baseline.yml"
_README = _REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def _yaml_required() -> None:
    if yaml is None:
        pytest.skip("PyYAML required to parse workflow YAML")


def _load(path: Path) -> dict[str, object]:
    assert yaml is not None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _on_block(payload: dict[str, object]) -> dict[str, object] | None:
    on = payload.get("on")
    if not isinstance(on, dict):
        on = payload.get(True)
    return on if isinstance(on, dict) else None


# ---------------------------------------------------------------------------
# 4.8.0-A — README contradiction cleanup
# ---------------------------------------------------------------------------


def test_readme_phase47_does_not_contain_stale_sarif_v3_claim() -> None:
    """4.8.0-A: the README's Phase 4.6 paragraph used to assert
    that `sarif-upload.yml` uploads via `upload-sarif@v3`. Phase
    4.7.0 bumped to `@v4`; the README must not re-introduce the
    stale `@v3` claim. Historical mentions in the changelog/ADR
    excerpts are fine — what we forbid is the README ASSERTING
    that the live workflow uses v3."""
    body = _README.read_text(encoding="utf-8")
    # Allow the substring in contexts that explicitly mark it as
    # historical (e.g., "bumped from @v3 to @v4"); reject the
    # standalone present-tense claim.
    forbidden_phrases = (
        "uploads via `github/codeql-action/upload-sarif@v3`",
        "uses `github/codeql-action/upload-sarif@v3`",
        "uses github/codeql-action/upload-sarif@v3",
    )
    for phrase in forbidden_phrases:
        assert phrase not in body, (
            f"README still asserts upload-sarif@v3 via phrase: {phrase!r}; "
            "Phase 4.7.0 bumped to @v4"
        )


def test_readme_phase47_does_not_say_provider_baseline_not_run() -> None:
    """4.8.0-A: the README's Phase 4.6 paragraph used to mark the
    provider regression baseline as `not_run`; Phase 4.7 ran it
    end-to-end on commit c1a39b8. The README must not still claim
    it's `not_run`."""
    body = _README.read_text(encoding="utf-8")
    forbidden_substrings = (
        "provider regression baseline marked\n`not_run`",
        "provider regression baseline marked `not_run`",
        "provider baseline marked `not_run`",
    )
    for sub in forbidden_substrings:
        assert sub not in body, (
            f"README still claims provider baseline not_run via: {sub!r}"
        )


# ---------------------------------------------------------------------------
# 4.8.0-B — provider-baseline Node 24 replay smoke
# ---------------------------------------------------------------------------


def test_provider_baseline_has_node24_replay_smoke(
    _yaml_required: None,
) -> None:
    """4.8.0-B: a separate workflow MUST exercise the provider-
    baseline surface under `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=
    true` so the 2026-06-02 default switch doesn't silently break
    operator runs."""
    assert _NODE24_SMOKE.is_file(), f"missing {_NODE24_SMOKE}"
    payload = _load(_NODE24_SMOKE)
    jobs = payload.get("jobs") or {}
    found = False
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        env = job.get("env")
        if isinstance(env, dict) and env.get(
            "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24",
        ) in ("true", True):
            found = True
    assert found, (
        "no job in provider-baseline-node24-smoke.yml sets "
        "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true"
    )


def test_provider_baseline_node24_smoke_no_external_provider(
    _yaml_required: None,
) -> None:
    """4.8.0-B: the Node 24 smoke MUST stay replay-only — the
    surface under test is "does this workflow file run cleanly on
    a Node-24-defaulted runner", NOT "does DeepSeek charge me
    again". No `openai-compatible`, no `*_API_KEY` reference."""
    body = _NODE24_SMOKE.read_text(encoding="utf-8")
    assert "openai-compatible" not in body
    for k in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MINIMAX_API_KEY"):
        assert k not in body, (
            f"provider-baseline-node24-smoke.yml references {k}; "
            "Phase 4.8.0-B requires it to stay replay-only"
        )


def test_provider_baseline_node24_permissions_read_only(
    _yaml_required: None,
) -> None:
    """4.8.0-B + ADR-30 §A: workflow + every job MUST be
    `contents: read` only. No security-events / actions / checks /
    contents:write."""
    payload = _load(_NODE24_SMOKE)
    workflow_perms = payload.get("permissions")
    assert isinstance(workflow_perms, dict)
    assert workflow_perms.get("contents") == "read"
    forbidden = {
        "security-events", "actions", "checks", "deployments",
        "id-token", "issues", "packages", "pages", "pull-requests",
        "repository-projects", "statuses",
    }
    assert not (set(workflow_perms.keys()) & forbidden)
    jobs = payload.get("jobs") or {}
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        perms = job.get("permissions")
        if perms is None:
            continue
        assert isinstance(perms, dict)
        for scope, value in perms.items():
            assert value in ("read", "none"), (
                f"job {job_name!r} perms.{scope}={value!r} — "
                "Node 24 smoke must stay read-only"
            )


# ---------------------------------------------------------------------------
# 4.8 provider-baseline workflow gains store-redacted-provider-io
# ---------------------------------------------------------------------------


def test_provider_baseline_exposes_store_redacted_io_input(
    _yaml_required: None,
) -> None:
    """4.8-A: provider-baseline.yml MUST expose
    `store-redacted-provider-io` as a workflow_dispatch input,
    default `false`. An operator opts in deliberately."""
    payload = _load(_PROVIDER_BASELINE)
    on = _on_block(payload)
    assert on is not None
    inputs = on["workflow_dispatch"]["inputs"]  # type: ignore[index]
    assert isinstance(inputs, dict)
    flag = inputs.get("store-redacted-provider-io")
    assert isinstance(flag, dict), (
        "provider-baseline.yml must declare the "
        "store-redacted-provider-io workflow_dispatch input"
    )
    assert flag.get("default") in ("false", False)


def test_provider_baseline_passes_store_redacted_io_to_cli(
    _yaml_required: None,
) -> None:
    """4.8-A: the workflow MUST conditionally append
    `--store-redacted-provider-io` to the CLI invocation when
    the input is `"true"`. We grep the run-step body for the
    flag literal."""
    body = _PROVIDER_BASELINE.read_text(encoding="utf-8")
    assert "--store-redacted-provider-io" in body, (
        "provider-baseline.yml does not pass "
        "--store-redacted-provider-io to the CLI"
    )
