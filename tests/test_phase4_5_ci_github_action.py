"""Phase 4.5 (QA/A21.md, ADR-30) — CI workflow + composite action tests.

The mandatory invariants from QA/A21.md:

* `action.yml` exists at the repo root with `runs.using: composite`.
* `.github/workflows/ci.yml` exists.
* Workflow-level `permissions:` defaults to ``contents: read``.
* No `pull_request_target` anywhere in the workflows.
* The SARIF upload step is the ONLY thing that can require
  `security-events: write` (the action makes this clear by gating
  the SARIF upload on `inputs.upload-sarif == 'true'`).
* `action.yml` defaults `llm-provider` to ``replay``.
* `action.yml` blocks external providers on PRs from forks.
* `action.yml` declares the artifact paths described in QA/A21.md.
* No raw API key value appears in any workflow or action file.
* `validate_github_workflows.py` exits 0 on the shipped tree.

These tests exercise the YAML files directly — they don't need a
running runner.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_CI_WORKFLOW = _WORKFLOW_DIR / "ci.yml"
_ACTION = _REPO_ROOT / "action.yml"
_VALIDATOR_SCRIPT = _REPO_ROOT / "scripts" / "validate_github_workflows.py"


@pytest.fixture(scope="module")
def _yaml_required() -> None:
    if yaml is None:
        pytest.skip("PyYAML required to parse workflow YAML")


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------


def test_action_yaml_exists() -> None:
    """4.5-B: ``action.yml`` MUST exist at the repo root."""
    assert _ACTION.is_file(), f"missing {_ACTION}"


def test_ci_workflow_exists() -> None:
    """4.5-A: ``.github/workflows/ci.yml`` MUST exist."""
    assert _CI_WORKFLOW.is_file(), f"missing {_CI_WORKFLOW}"


def test_validator_script_exists() -> None:
    """The workflow validator script ships with the repo."""
    assert _VALIDATOR_SCRIPT.is_file()


# ---------------------------------------------------------------------------
# Permissions / triggers
# ---------------------------------------------------------------------------


def test_ci_workflow_permissions_are_read_only_by_default(
    _yaml_required: None,
) -> None:
    """4.5-A + ADR-30: top-level ``permissions:`` MUST be present
    and ``contents: read`` (no escalation by default)."""
    assert yaml is not None
    payload = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    perms = payload.get("permissions")
    assert isinstance(perms, dict), "missing top-level permissions:"
    assert perms.get("contents") == "read"


def test_ci_workflow_does_not_use_pull_request_target(
    _yaml_required: None,
) -> None:
    """ADR-30: ``pull_request_target`` is FORBIDDEN — it would let
    untrusted PR contents read repo secrets."""
    body = _CI_WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"^\s*pull_request_target\s*:", body, re.MULTILINE)


def test_sarif_job_has_security_events_write_only_if_upload_enabled(
    _yaml_required: None,
) -> None:
    """ADR-30: ``security-events: write`` may only appear in a job
    whose purpose is the SARIF upload. The CI workflow's jobs run
    under ``contents: read``; the SARIF upload happens through the
    composite action, which scopes the permission to its own step.

    We assert: no job in the CI workflow sets
    ``security-events: write``."""
    assert yaml is not None
    payload = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    for job_name, job in (payload.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        perms = job.get("permissions")
        if not isinstance(perms, dict):
            continue
        for scope, value in perms.items():
            if scope == "security-events" and value == "write":
                pytest.fail(
                    f"job {job_name!r} grants security-events: write — "
                    "should live in a separate SARIF-upload job only"
                )


# ---------------------------------------------------------------------------
# action.yml defaults
# ---------------------------------------------------------------------------


def test_action_uses_composite_runs(_yaml_required: None) -> None:
    """ADR-30: the action MUST be a composite action so the operator
    can include it in their workflow without needing a custom runner."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runs = payload.get("runs")
    assert isinstance(runs, dict)
    assert runs.get("using") == "composite"


def test_action_defaults_to_replay_provider(
    _yaml_required: None,
) -> None:
    """ADR-30: ``inputs.llm-provider.default`` MUST be ``replay`` so
    a workflow that includes the action without flags never makes
    a real external API call."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    inputs = payload.get("inputs") or {}
    llm_provider = inputs.get("llm-provider")
    assert isinstance(llm_provider, dict), "missing llm-provider input"
    assert llm_provider.get("default") == "replay"


def test_action_does_not_reference_api_key_by_value(
    _yaml_required: None,
) -> None:
    """ADR-30: no raw API key value may appear in the action body —
    only env-var **names** (``api-key-env``)."""
    body = _ACTION.read_text(encoding="utf-8")
    # Common API-key prefixes; the validator catches more forms.
    pattern = re.compile(
        r"\b(sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}"
        r"|xoxb-[A-Za-z0-9\-]+)",
    )
    assert not pattern.search(body)


def test_action_blocks_external_provider_on_pull_request_forks(
    _yaml_required: None,
) -> None:
    """ADR-30: the action MUST refuse to run an external provider on
    PR events from forks (anti-secret-exfil guard).

    The check is structural: a step's `if:` clause MUST contain BOTH
    the `openai-compatible` literal AND the
    `head.repo.full_name != github.repository` fork-detection
    expression. A future refactor that splits them into separate
    steps would silently weaken the guard, so we assert both literals
    appear in the same `if:` value."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runs = payload.get("runs")
    assert isinstance(runs, dict)
    steps = runs.get("steps")
    assert isinstance(steps, list)
    matches = [
        step for step in steps
        if isinstance(step, dict)
        and isinstance(step.get("if"), str)
        and "openai-compatible" in step["if"]
        and "head.repo.full_name" in step["if"]
        and "github.repository" in step["if"]
    ]
    assert matches, (
        "no step.if combines `openai-compatible` with the fork-PR "
        "detection (`head.repo.full_name != github.repository`); "
        "the anti-secret-exfil guard must live in a single `if:`"
    )


def test_action_does_not_inline_pr_controlled_expr_in_run_blocks(
    _yaml_required: None,
) -> None:
    """ADR-30 + Phase 4.5.1 hardening: PR-controlled values
    (`inputs.X`, `github.head_ref`, `github.actor`,
    `github.event.pull_request.*`, `github.event.head_commit.message`)
    MUST be lifted into the step's `env:` map before being
    referenced inside a `run:` block. Inline `${{ inputs.X }}` in a
    bash heredoc lets a malicious branch name break out of quoting
    and run arbitrary commands on the runner."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runs = payload.get("runs")
    assert isinstance(runs, dict)
    steps = runs.get("steps")
    assert isinstance(steps, list)
    bad_pattern = re.compile(
        r"\$\{\{\s*("
        r"inputs\."
        r"|github\.head_ref"
        r"|github\.actor"
        r"|github\.triggering_actor"
        r"|github\.event\.(pull_request|issue|comment|review|"
        r"discussion|workflow_run|push|head_commit)"
        r")",
    )
    for step in steps:
        if not isinstance(step, dict):
            continue
        run_body = step.get("run")
        if not isinstance(run_body, str):
            continue
        m = bad_pattern.search(run_body)
        assert m is None, (
            f"step `{step.get('name', '?')}` interpolates a "
            f"PR-controlled expression `{m.group(0)}` inside its "
            "`run:` block; lift it into env: and use $VAR"
        )


def test_action_writes_expected_artifact_paths(
    _yaml_required: None,
) -> None:
    """QA/A21.md §4.5-B: the action MUST emit JSON / Markdown / SARIF
    + calibration metrics.json."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    outputs = payload.get("outputs") or {}
    for expected in (
        "report-json", "report-markdown", "report-sarif",
        "calibration-metrics",
    ):
        assert expected in outputs, f"missing output {expected!r}"


def test_action_summary_redacts_provider_key_names_or_values(
    _yaml_required: None,
) -> None:
    """ADR-30: the action's step summary MUST NOT echo any
    ``${{ secrets.* }}`` content. We assert the action body never
    references ``secrets.*`` in a ``run:`` block — secrets travel
    via ``env:`` only.

    Note: the action takes an ``api-key-env`` input (the env var
    NAME, not value) and passes it to ``oida-code calibration-eval``
    as a CLI flag. That's safe — the value lives only in the env."""
    body = _ACTION.read_text(encoding="utf-8")
    # ${{ secrets.X }} should never appear — operator wires secrets
    # in the WORKFLOW that calls the action, not inside the action.
    assert "secrets." not in body, (
        "action.yml must not reference ${{ secrets.* }} directly; "
        "secrets belong in the calling workflow's env: map"
    )


# ---------------------------------------------------------------------------
# Outputs from CLI calibration-eval are leak-free
# ---------------------------------------------------------------------------


def test_no_official_fields_in_action_outputs(
    _yaml_required: None,
) -> None:
    """ADR-22 + ADR-30: the action MUST NOT promise official OIDA
    fusion fields in any output. We assert by name-checking the
    declared outputs against the forbidden phrase set."""
    assert yaml is not None
    payload = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    outputs = payload.get("outputs") or {}
    forbidden = {
        "total_v_net", "v_net", "debt_final",
        "corrupt_success", "corrupt_success_ratio",
        "corrupt_success_verdict", "verdict", "merge_safe",
        "production_safe", "bug_free", "security_verified",
    }
    for output_name in outputs:
        assert output_name.lower() not in forbidden


# ---------------------------------------------------------------------------
# validator script as a sanity gate
# ---------------------------------------------------------------------------


def test_validate_github_workflows_script_passes(
    _yaml_required: None,
) -> None:
    """The script ships green on the shipped tree."""
    proc = subprocess.run(
        [sys.executable, str(_VALIDATOR_SCRIPT)],
        capture_output=True, text=True, check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"validate_github_workflows.py failed:\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )


def test_validate_github_workflows_script_detects_pull_request_target(
    tmp_path: Path, _yaml_required: None,
) -> None:
    """The script MUST flag a workflow that uses the forbidden
    ``pull_request_target`` trigger."""
    bad_wf = tmp_path / ".github" / "workflows"
    bad_wf.mkdir(parents=True)
    (bad_wf / "danger.yml").write_text(
        "name: danger\n"
        "on:\n"
        "  pull_request_target:\n"
        "    branches: [main]\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  ok:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo hi\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable, str(_VALIDATOR_SCRIPT),
            "--workflows-dir", str(bad_wf),
            "--action-file", str(_ACTION),
        ],
        capture_output=True, text=True, check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "pull_request_target" in combined


def test_validate_github_workflows_script_detects_inputs_in_run(
    tmp_path: Path, _yaml_required: None,
) -> None:
    """The script MUST flag a workflow that interpolates a
    PR-controlled `${{ inputs.X }}` straight into a `run:` block —
    the documented shell-injection anti-pattern that ADR-30 §6
    forbids."""
    bad_wf = tmp_path / ".github" / "workflows"
    bad_wf.mkdir(parents=True)
    (bad_wf / "shellinj.yml").write_text(
        "name: shellinj\n"
        "on:\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  bad:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: vulnerable\n"
        "        run: echo \"${{ github.head_ref }}\"\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable, str(_VALIDATOR_SCRIPT),
            "--workflows-dir", str(bad_wf),
            "--action-file", str(_ACTION),
        ],
        capture_output=True, text=True, check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "PR-controlled expression" in combined
