"""Phase 4.7 (QA/A24.md, ADR-32) — provider regression baseline
structural tests.

The structural surface this commit ships:

* `.github/workflows/sarif-upload.yml` — bumped to
  `github/codeql-action/upload-sarif@v4` (3 SARIF v4 tests below).
* `.github/workflows/provider-baseline.yml` — workflow_dispatch
  ONLY, replay-first then optional external provider, secrets via
  `secrets.*` → `env:` map → `$VAR` in bash (validator §6 forbids
  `${{ secrets.* }}` inside `run:`), official-leak gate inherited
  from the CLI.
* No MCP code, no provider tool-calling — Phase 4.7 explicitly
  defers both.

The acceptance criterion 12 from QA/A24.md is honest: "If no API
budget, provider baseline remains not_run with explicit reason
and Phase 4.7 is NOT marked fully accepted." These tests cover the
structural surface; the empirical provider run is gated on the
operator allocating budget and firing the workflow manually.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_PROVIDER_BASELINE = _WORKFLOW_DIR / "provider-baseline.yml"
_SARIF_UPLOAD = _WORKFLOW_DIR / "sarif-upload.yml"


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
    """YAML 1.1 parses ``on:`` as boolean ``True``."""
    on = payload.get("on")
    if not isinstance(on, dict):
        on = payload.get(True)
    return on if isinstance(on, dict) else None


_PULL_REQUEST_TARGET_KEY = re.compile(
    r"^\s*pull_request_target\s*:", re.MULTILINE,
)


# ---------------------------------------------------------------------------
# 4.7.0 — SARIF upload bumped to v4
# ---------------------------------------------------------------------------


def test_sarif_upload_uses_codeql_action_v4(_yaml_required: None) -> None:
    """4.7.0: GitHub announced ``upload-sarif@v3`` deprecation for
    December 2026; ``v4`` ships with native Node 24 support. The
    SARIF workflow MUST pin v4 (or a documented fallback to v3 if
    v4 fails — but this commit lands v4 because it works)."""
    body = _SARIF_UPLOAD.read_text(encoding="utf-8")
    assert "github/codeql-action/upload-sarif@v4" in body, (
        "sarif-upload.yml must pin codeql-action/upload-sarif@v4 "
        "per QA/A24.md §4.7.0"
    )
    # Belt-and-suspenders: no @v3 left over from an incomplete bump.
    assert "github/codeql-action/upload-sarif@v3" not in body, (
        "sarif-upload.yml still pins @v3 somewhere — bump the rest "
        "or document the fallback explicitly"
    )


def test_sarif_upload_v4_job_still_scopes_security_events_write(
    _yaml_required: None,
) -> None:
    """4.7.0: bumping to v4 MUST preserve the ADR-30 invariant:
    ``security-events: write`` lives on the upload JOB only, never
    at workflow scope."""
    payload = _load(_SARIF_UPLOAD)
    workflow_perms = payload.get("permissions")
    assert isinstance(workflow_perms, dict)
    assert "security-events" not in workflow_perms, (
        "security-events must NOT be granted at workflow level "
        "(ADR-30); bump to v4 must not have re-introduced it"
    )
    jobs = payload.get("jobs") or {}
    granted = False
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        perms = job.get("permissions") or {}
        if isinstance(perms, dict) and perms.get("security-events") == "write":
            granted = True
    assert granted, (
        "no job in sarif-upload.yml grants `security-events: write` "
        "after the v4 bump"
    )


def test_sarif_upload_v4_no_external_provider(
    _yaml_required: None,
) -> None:
    """4.7.0: bumping to v4 MUST keep the SARIF smoke replay-only —
    no `openai-compatible`, no API-key env var, no provider profile.
    The SARIF workflow generates SARIF from the deterministic
    pipeline and uploads it; the LLM estimator does not enter."""
    body = _SARIF_UPLOAD.read_text(encoding="utf-8")
    assert "openai-compatible" not in body
    assert "DEEPSEEK_API_KEY" not in body
    assert "KIMI_API_KEY" not in body
    assert "MINIMAX_API_KEY" not in body


# ---------------------------------------------------------------------------
# 4.7.1 — provider-baseline workflow shape
# ---------------------------------------------------------------------------


def test_provider_baseline_workflow_exists(_yaml_required: None) -> None:
    """4.7.1: ``.github/workflows/provider-baseline.yml`` MUST exist."""
    assert _PROVIDER_BASELINE.is_file(), f"missing {_PROVIDER_BASELINE}"


def test_provider_baseline_is_workflow_dispatch_only(
    _yaml_required: None,
) -> None:
    """4.7.1 + ADR-32: external provider runs imply secrets and
    cost — the workflow MUST be ``workflow_dispatch`` only. No
    push, no pull_request, no schedule, no anything else."""
    payload = _load(_PROVIDER_BASELINE)
    on = _on_block(payload)
    assert on is not None, (
        "provider-baseline.yml `on:` must be a mapping with "
        "workflow_dispatch only"
    )
    assert "workflow_dispatch" in on
    forbidden = set(on.keys()) - {"workflow_dispatch"}
    assert not forbidden, (
        f"provider-baseline.yml triggers must be workflow_dispatch "
        f"only; got extras: {sorted(forbidden)}"
    )


def test_provider_baseline_permissions_read_only(
    _yaml_required: None,
) -> None:
    """ADR-30 §A + 4.7.1: workflow-level + job-level permissions
    MUST be ``contents: read``. No `security-events`, no
    `actions: write`, no `checks: write`, no `contents: write`."""
    payload = _load(_PROVIDER_BASELINE)
    workflow_perms = payload.get("permissions")
    assert isinstance(workflow_perms, dict)
    assert workflow_perms.get("contents") == "read"
    forbidden_scopes = {
        "security-events", "actions", "checks", "deployments",
        "id-token", "issues", "packages", "pages", "pull-requests",
        "repository-projects", "statuses",
    }
    assert not (set(workflow_perms.keys()) & forbidden_scopes), (
        f"provider-baseline.yml workflow perms grant non-read "
        f"scopes: {workflow_perms!r}"
    )
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
                "provider-baseline must stay read-only (ADR-32)"
            )


def test_provider_baseline_has_no_pull_request_target(
    _yaml_required: None,
) -> None:
    """ADR-30 + ADR-32: forbidden trigger. Match YAML key only."""
    body = _PROVIDER_BASELINE.read_text(encoding="utf-8")
    assert not _PULL_REQUEST_TARGET_KEY.search(body)


def test_provider_baseline_does_not_run_on_push_or_pr(
    _yaml_required: None,
) -> None:
    """4.7.1: the workflow MUST refuse to fire on push or
    pull_request — provider runs cost real money and burn real
    secret-scoped quota; an automatic trigger is unsafe."""
    payload = _load(_PROVIDER_BASELINE)
    on = _on_block(payload)
    assert on is not None
    assert "push" not in on, (
        "provider-baseline.yml MUST NOT fire on push (cost + secret risk)"
    )
    assert "pull_request" not in on, (
        "provider-baseline.yml MUST NOT fire on pull_request"
    )
    assert "schedule" not in on, (
        "provider-baseline.yml MUST NOT fire on schedule"
    )


def test_provider_baseline_requires_explicit_provider_profile(
    _yaml_required: None,
) -> None:
    """4.7.1: ``inputs.provider-profile`` MUST be required (no
    silent fallback) — the operator chooses which provider's
    secret to spend."""
    payload = _load(_PROVIDER_BASELINE)
    on = _on_block(payload)
    assert on is not None
    dispatch = on.get("workflow_dispatch")
    assert isinstance(dispatch, dict)
    inputs = dispatch.get("inputs")
    assert isinstance(inputs, dict)
    profile = inputs.get("provider-profile")
    assert isinstance(profile, dict)
    assert profile.get("required") is True, (
        "provider-profile input must be `required: true`"
    )


def test_provider_baseline_default_max_cases_is_small(
    _yaml_required: None,
) -> None:
    """4.7.1: the default ``max-provider-cases`` MUST be small
    enough that a first dry-run is cheap. QA/A24.md §4.7.2 names
    `4` as the recommended starting cap."""
    payload = _load(_PROVIDER_BASELINE)
    on = _on_block(payload)
    assert on is not None
    inputs = on["workflow_dispatch"]["inputs"]  # type: ignore[index]
    assert isinstance(inputs, dict)
    cap = inputs.get("max-provider-cases")
    assert isinstance(cap, dict)
    default = cap.get("default")
    # Allow string or int form; both can be parsed.
    try:
        cap_int = int(default)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pytest.fail(f"max-provider-cases default not int-coercible: {default!r}")
    assert 1 <= cap_int <= 8, (
        f"default max-provider-cases must be in [1, 8] for safe "
        f"first-run cost; got {cap_int}"
    )


def test_provider_baseline_uses_secrets_context_only(
    _yaml_required: None,
) -> None:
    """4.7.1 + ADR-30 §6: secret values travel via ``${{ secrets.X
    }}`` → workflow `env:` → bash `$VAR`. The workflow MUST never
    reference `${{ secrets.* }}` inside any `run:` block. Validator
    §6 enforces this for the whole repo; we re-assert here so a
    future split-step refactor of provider-baseline can't silently
    weaken it."""
    payload = _load(_PROVIDER_BASELINE)
    jobs = payload.get("jobs") or {}
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            run_body = step.get("run")
            if not isinstance(run_body, str):
                continue
            assert "${{ secrets." not in run_body, (
                f"job {job_name!r} step `{step.get('name', '?')}` "
                "references `${{ secrets.* }}` inside its run "
                "block; lift it into env: and use $VAR"
            )


def test_provider_baseline_does_not_echo_secret_values(
    _yaml_required: None,
) -> None:
    """4.7.1 + ADR-32: no ``echo "$DEEPSEEK_API_KEY"`` style
    invocation. We scan every run body for `echo "$X_API_KEY` or
    `printf "$X_API_KEY` or just bare references that pipe into
    a logger."""
    payload = _load(_PROVIDER_BASELINE)
    jobs = payload.get("jobs") or {}
    secret_var_re = re.compile(
        r"(echo|printf|cat|tee|>>|>|\|)\s+[^\n]*\$\{?(DEEPSEEK|KIMI|MINIMAX|"
        r"CUSTOM_OPENAI_COMPATIBLE)_API_KEY",
    )
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            run_body = step.get("run")
            if not isinstance(run_body, str):
                continue
            m = secret_var_re.search(run_body)
            assert m is None, (
                f"step `{step.get('name', '?')}` echoes / pipes a "
                f"`*_API_KEY` value: {m.group(0)!r}"
            )


def test_provider_baseline_runs_replay_before_external(
    _yaml_required: None,
) -> None:
    """4.7.3: ``replay`` baseline MUST come BEFORE the external
    provider step in the job's step order. Step-order matters
    because the report's contract-compliance comparison is
    `provider vs replay`; the replay run is the reference and
    must be captured first."""
    payload = _load(_PROVIDER_BASELINE)
    jobs = payload.get("jobs") or {}
    for _, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        replay_idx: int | None = None
        provider_idx: int | None = None
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            run_body = step.get("run")
            if not isinstance(run_body, str):
                continue
            if "--llm-provider replay" in run_body and replay_idx is None:
                replay_idx = i
            if (
                "--llm-provider openai-compatible" in run_body
                and provider_idx is None
            ):
                provider_idx = i
        assert replay_idx is not None, (
            "no replay step found in provider-baseline.yml"
        )
        assert provider_idx is not None, (
            "no openai-compatible step found in provider-baseline.yml"
        )
        assert replay_idx < provider_idx, (
            f"replay step ({replay_idx}) must come before provider "
            f"step ({provider_idx})"
        )


def test_provider_baseline_artifacts_do_not_include_raw_prompt_by_default(
    _yaml_required: None,
) -> None:
    """4.7.3: the workflow MUST NOT pass any flag that surfaces raw
    prompts or raw provider responses in artifacts. The CLI does
    not have such a flag today; if one is ever added (e.g.
    `--debug-redacted` per QA/A24.md §4.7.3), the workflow must
    not pass it."""
    body = _PROVIDER_BASELINE.read_text(encoding="utf-8")
    forbidden_flags = (
        "--debug-raw-prompt",
        "--debug-raw-response",
        "--debug-unredacted",
        "--dump-prompt",
        "--dump-response",
        "--store-raw",
    )
    for flag in forbidden_flags:
        assert flag not in body, (
            f"provider-baseline.yml passes `{flag}` — raw prompt "
            "/ response storage is forbidden by ADR-32"
        )


def test_provider_baseline_official_leak_count_failure_path(
    _yaml_required: None,
) -> None:
    """4.7.4 + 4.3.1-A: any ``official_field_leak_count > 0`` in
    the calibration metrics MUST fail the run. The CLI exits with
    code 3 when ``assert_no_official_field_leaks`` raises; the
    workflow's `set -euo pipefail` propagates that exit. We assert
    the CLI gate hasn't been disabled in this workflow."""
    body = _PROVIDER_BASELINE.read_text(encoding="utf-8")
    # The CLI's exit-3 gate fires when run with default flags. The
    # workflow MUST NOT pass any kind of `--allow-leaks` / `--no-
    # leak-gate` / `|| true` swallow.
    forbidden_swallows = (
        "--allow-leaks",
        "--no-leak-gate",
        "--ignore-leak-gate",
    )
    for flag in forbidden_swallows:
        assert flag not in body, (
            f"provider-baseline.yml passes `{flag}` — the CLI's "
            "official-leak gate must remain enforced (ADR-22 + "
            "ADR-32)"
        )
    # And no `|| true` on the calibration-eval lines (would swallow
    # the exit-3 gate).
    for line in body.splitlines():
        if "calibration-eval" in line and "||" in line:
            pytest.fail(
                f"provider-baseline.yml swallows calibration-eval "
                f"exit code: {line.strip()!r}"
            )


# ---------------------------------------------------------------------------
# 4.7 — no MCP, no provider tool-calling
# ---------------------------------------------------------------------------


def test_no_mcp_workflow_or_dependency_added(_yaml_required: None) -> None:
    """ADR-32: Phase 4.7 EXPLICITLY defers MCP. There must be NO
    MCP-named workflow, no `mcp` package in `pyproject.toml`'s
    dependencies, no `model-context-protocol` mention in the
    project root."""
    # Workflows
    for wf in _WORKFLOW_DIR.glob("*.yml"):
        body = wf.read_text(encoding="utf-8").lower()
        # `mcp` appears in many unrelated tokens; assert no full
        # `model-context-protocol` or `mcp-server` invocation is
        # configured, and no MCP-named workflow file exists.
        assert "model-context-protocol" not in body, (
            f"{wf.name} references model-context-protocol; "
            "Phase 4.7 forbids MCP wiring"
        )
        assert "mcp-server" not in body, (
            f"{wf.name} references mcp-server"
        )
    assert not (_WORKFLOW_DIR / "mcp.yml").exists(), "mcp.yml must not exist"
    assert not (_WORKFLOW_DIR / "mcp-baseline.yml").exists(), (
        "mcp-baseline.yml must not exist"
    )
    # pyproject.toml dependencies
    pyproject_body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # The `dependencies = [...]` and the dev extra block both must
    # not list any MCP package. A literal `"mcp"` quoted string in
    # either block would be the smoking gun.
    assert '"mcp"' not in pyproject_body, (
        "pyproject.toml lists `mcp` package; ADR-32 forbids MCP in "
        "Phase 4.7"
    )
    assert '"model-context-protocol"' not in pyproject_body
    assert '"mcp-server"' not in pyproject_body


def test_no_provider_tool_calling_enabled(_yaml_required: None) -> None:
    """ADR-29 + ADR-32: ProviderProfile.supports_tools MUST stay
    `False` everywhere. Phase 4.7 does NOT enable provider
    function-calling at the verifier layer."""
    profile_path = _REPO_ROOT / "src" / "oida_code" / "estimators" / (
        "provider_config.py"
    )
    body = profile_path.read_text(encoding="utf-8")
    # Neither the schema default nor any predefined profile may
    # set supports_tools=True.
    assert "supports_tools=True" not in body, (
        f"{profile_path.name} sets supports_tools=True somewhere; "
        "ADR-32 forbids provider tool-calling in Phase 4.7"
    )
