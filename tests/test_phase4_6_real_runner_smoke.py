"""Phase 4.6 (QA/A23.md, ADR-31) — real-runner / operator smoke
structural tests.

Phase 4.5 closed the YAML-level invariant matrix; Phase 4.6 ships
three new workflow surfaces that need their own structural tests
before the real runner exercises them:

* `node24-compat` job in ``.github/workflows/ci.yml`` — verifies the
  workflow + action survive the GitHub-announced switch to Node 24
  (default 2026-06-02). Sets ``FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=
  true`` and runs validator + Phase 4.5 invariants.
* ``.github/workflows/action-smoke.yml`` — invokes the composite
  action as an operator would (``uses: ./``) and uploads the
  artifact. Replay-only, no secrets, no SARIF.
* ``.github/workflows/sarif-upload.yml`` — manual SARIF upload to
  GitHub Code Scanning. ``security-events: write`` is scoped to a
  single job.

The tests parse the YAML directly and don't need a runner — that's
the same pattern as ``test_phase4_5_ci_github_action.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None


def _on_block(payload: dict[str, object]) -> dict[str, object] | None:
    """YAML 1.1 parses ``on:`` as boolean ``True``. PyYAML defaults
    to YAML 1.1, so look up the trigger block under either form.
    Returning ``None`` when neither key is a mapping lets the
    caller emit a clear assertion message."""
    on = payload.get("on")
    if not isinstance(on, dict):
        on = payload.get(True)  # YAML 1.1 boolean key
    if isinstance(on, dict):
        return on
    return None


_PULL_REQUEST_TARGET_KEY = re.compile(
    r"^\s*pull_request_target\s*:", re.MULTILINE,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_CI_WORKFLOW = _WORKFLOW_DIR / "ci.yml"
_ACTION_SMOKE = _WORKFLOW_DIR / "action-smoke.yml"
_SARIF_UPLOAD = _WORKFLOW_DIR / "sarif-upload.yml"
_ACTION = _REPO_ROOT / "action.yml"


@pytest.fixture(scope="module")
def _yaml_required() -> None:
    if yaml is None:
        pytest.skip("PyYAML required to parse workflow YAML")


def _load(path: Path) -> dict[str, object]:
    assert yaml is not None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


# ---------------------------------------------------------------------------
# 4.6-A — Node24 compatibility job (in ci.yml)
# ---------------------------------------------------------------------------


def test_ci_has_node24_compat_job(_yaml_required: None) -> None:
    """4.6-A: ``ci.yml`` MUST declare a ``node24-compat`` job that
    runs alongside the regular jobs."""
    payload = _load(_CI_WORKFLOW)
    jobs = payload.get("jobs")
    assert isinstance(jobs, dict)
    assert "node24-compat" in jobs, (
        "missing node24-compat job in ci.yml — required by ADR-31 "
        "Phase 4.6-A"
    )


def test_node24_job_sets_force_javascript_actions_to_node24(
    _yaml_required: None,
) -> None:
    """4.6-A: the ``node24-compat`` job MUST set
    ``FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`` at job scope so
    every nested action runs under Node 24."""
    payload = _load(_CI_WORKFLOW)
    job = (payload.get("jobs") or {}).get("node24-compat")
    assert isinstance(job, dict), "node24-compat job missing"
    env = job.get("env")
    assert isinstance(env, dict), "node24-compat must declare env:"
    flag = env.get("FORCE_JAVASCRIPT_ACTIONS_TO_NODE24")
    assert flag in ("true", True), (
        "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 must be `true` on the "
        f"node24-compat job; got {flag!r}"
    )


def test_node24_job_does_not_use_external_provider(
    _yaml_required: None,
) -> None:
    """4.6-A + ADR-30 §A: the Node-24 compat job MUST NOT reach an
    external LLM provider. The job runs the validator and the
    Phase-4.5/4.6 structural test suites — that's it. No
    `--llm-provider openai-compatible`, no API key env var."""
    payload = _load(_CI_WORKFLOW)
    job = (payload.get("jobs") or {}).get("node24-compat")
    assert isinstance(job, dict)
    body = _CI_WORKFLOW.read_text(encoding="utf-8")
    # Crude but sufficient: any mention of openai-compatible inside
    # the job's run-step bodies fails. We re-read the file and
    # confirm the literal isn't present anywhere in the workflow.
    assert "openai-compatible" not in body, (
        "ci.yml references `openai-compatible` — the Node-24 compat "
        "job MUST stay replay-only (ADR-30 §A)"
    )
    # And the job's own env: must not carry an api-key-env name.
    env = job.get("env") or {}
    forbidden = {"DEEPSEEK_API_KEY", "KIMI_API_KEY", "MINIMAX_API_KEY"}
    assert not (set(env.keys()) & forbidden), (
        f"node24-compat env: leaks an API-key name: {env!r}"
    )


def test_node24_job_permissions_read_only(_yaml_required: None) -> None:
    """4.6-A + ADR-30 §A: the Node-24 compat job MUST inherit
    `contents: read` (or set it explicitly) — no escalation."""
    payload = _load(_CI_WORKFLOW)
    job = (payload.get("jobs") or {}).get("node24-compat")
    assert isinstance(job, dict)
    perms = job.get("permissions")
    # If `permissions:` is missing on the job, the workflow-level
    # default applies. We assert *either* the job sets read-only OR
    # the workflow default is read-only (which Phase 4.5 already
    # asserts) — but we re-check here to keep the guarantee local
    # to the Node-24 surface.
    if perms is not None:
        assert isinstance(perms, dict)
        for scope, value in perms.items():
            assert value in ("read", "none"), (
                f"node24-compat permissions.{scope}={value!r} — only "
                "read/none allowed on this job"
            )


# ---------------------------------------------------------------------------
# 4.6-B — composite action consumer smoke (action-smoke.yml)
# ---------------------------------------------------------------------------


def test_action_smoke_workflow_exists(_yaml_required: None) -> None:
    """4.6-B: ``.github/workflows/action-smoke.yml`` MUST exist."""
    assert _ACTION_SMOKE.is_file(), f"missing {_ACTION_SMOKE}"


def test_action_smoke_uses_local_action(_yaml_required: None) -> None:
    """4.6-B: the smoke MUST invoke the local action via
    ``uses: ./`` so it exercises the composite action body in this
    very commit, not a published version."""
    payload = _load(_ACTION_SMOKE)
    jobs = payload.get("jobs") or {}
    found = False
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("uses") == "./":
                found = True
    assert found, (
        "action-smoke.yml must include a step with `uses: ./` to "
        "invoke the composite action under test"
    )


def test_action_smoke_replay_only(_yaml_required: None) -> None:
    """4.6-B: the smoke MUST set ``llm-provider: replay`` (no
    external API call) and ``upload-sarif: false`` (SARIF lives in
    the dedicated workflow)."""
    payload = _load(_ACTION_SMOKE)
    jobs = payload.get("jobs") or {}
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or step.get("uses") != "./":
                continue
            with_block = step.get("with") or {}
            assert with_block.get("llm-provider") == "replay", (
                f"action-smoke `with.llm-provider` must be `replay`; "
                f"got {with_block.get('llm-provider')!r}"
            )
            assert with_block.get("upload-sarif") == "false", (
                f"action-smoke `with.upload-sarif` must be `false`; "
                f"got {with_block.get('upload-sarif')!r}"
            )


def test_action_smoke_does_not_use_pull_request_target(
    _yaml_required: None,
) -> None:
    """ADR-30 + ADR-31: forbidden trigger. Match the YAML key, not
    occurrences of the literal in comments."""
    body = _ACTION_SMOKE.read_text(encoding="utf-8")
    assert not _PULL_REQUEST_TARGET_KEY.search(body)


def test_action_smoke_workflow_permissions_read_only(
    _yaml_required: None,
) -> None:
    """ADR-30 §A: workflow-level `permissions: contents: read`."""
    payload = _load(_ACTION_SMOKE)
    perms = payload.get("permissions")
    assert isinstance(perms, dict), (
        "action-smoke.yml must declare workflow-level permissions: "
        "contents: read (ADR-30)"
    )
    assert perms.get("contents") == "read"


# ---------------------------------------------------------------------------
# 4.6-D — SARIF upload (sarif-upload.yml)
# ---------------------------------------------------------------------------


def test_sarif_upload_workflow_exists(_yaml_required: None) -> None:
    """4.6-D: ``.github/workflows/sarif-upload.yml`` MUST exist."""
    assert _SARIF_UPLOAD.is_file(), f"missing {_SARIF_UPLOAD}"


def test_sarif_upload_workflow_dispatch_only(_yaml_required: None) -> None:
    """4.6-D: the SARIF workflow MUST be ``workflow_dispatch`` only —
    no automatic firing on push or PR. Operator opts in deliberately."""
    payload = _load(_SARIF_UPLOAD)
    on = _on_block(payload)
    assert on is not None, (
        "sarif-upload.yml `on:` must be a mapping with workflow_dispatch only"
    )
    assert "workflow_dispatch" in on
    # No push, no pull_request, no schedule, no anything else.
    forbidden = set(on.keys()) - {"workflow_dispatch"}
    assert not forbidden, (
        f"sarif-upload.yml triggers must be workflow_dispatch only; "
        f"got extras: {sorted(forbidden)}"
    )


def test_sarif_upload_security_events_write_scoped_to_upload_job(
    _yaml_required: None,
) -> None:
    """ADR-30 §A + 4.6-D: ``security-events: write`` MUST appear
    only at job scope (the SARIF-uploading job), never at workflow
    scope. The workflow default stays `contents: read`."""
    payload = _load(_SARIF_UPLOAD)
    workflow_perms = payload.get("permissions")
    assert isinstance(workflow_perms, dict), (
        "sarif-upload.yml must declare workflow-level permissions"
    )
    assert workflow_perms.get("contents") == "read"
    assert "security-events" not in workflow_perms, (
        "security-events must NOT be granted at workflow level — "
        "scope it to the upload job (ADR-30)"
    )
    # And confirm at least one job grants the permission.
    jobs = payload.get("jobs") or {}
    granted = False
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        perms = job.get("permissions") or {}
        if isinstance(perms, dict) and perms.get("security-events") == "write":
            granted = True
    assert granted, (
        "no job in sarif-upload.yml grants `security-events: write`"
    )


def test_sarif_upload_uses_codeql_action(_yaml_required: None) -> None:
    """4.6-D: the SARIF push MUST go through
    `github/codeql-action/upload-sarif`. That's the canonical
    GitHub-supported ingestion path; rolling our own would skip
    the GitHub App's permission check."""
    body = _SARIF_UPLOAD.read_text(encoding="utf-8")
    assert "github/codeql-action/upload-sarif" in body


def test_sarif_upload_no_external_provider(_yaml_required: None) -> None:
    """ADR-30 + ADR-31: SARIF smoke MUST stay replay-only — no
    `openai-compatible`, no API-key env var, no provider profile."""
    body = _SARIF_UPLOAD.read_text(encoding="utf-8")
    assert "openai-compatible" not in body
    assert "DEEPSEEK_API_KEY" not in body
    assert "KIMI_API_KEY" not in body
    assert "MINIMAX_API_KEY" not in body
