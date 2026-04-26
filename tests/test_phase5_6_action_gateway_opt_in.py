"""Phase 5.6 (QA/A33.md, ADR-41) — opt-in gateway-grounded
GitHub Action path tests.

Sub-blocks covered:

* 5.6-A — action.yml inputs (enable-tool-gateway,
  gateway-bundle-dir, gateway-output-dir,
  gateway-fail-on-contract).
* 5.6-B — bundle validator (8 required files, no path
  traversal, no secret-shaped paths, no provider/MCP config).
* 5.6-C — verify-grounded invocation with the QA-spec'd
  filenames.
* 5.6-D — Step Summary section + forbidden-phrase scan.
* 5.6-E — gateway action outputs + 5-value Literal enum.
* 5.6-F — `.github/workflows/action-gateway-smoke.yml`
  workflow + bundle fixture.
* 5.6-G — fork/PR guard.
* 5.6-H — shell-injection guard.

Negative checks scan ``pyproject.toml`` +
``.github/workflows/`` + ``src/oida_code/`` only — never
``docs/`` or ``reports/``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = (
    _REPO_ROOT / "tests" / "fixtures" / "action_gateway_bundle"
    / "tool_needed_then_supported"
)
_ACTION_YML = _REPO_ROOT / "action.yml"
_SMOKE_WORKFLOW = (
    _REPO_ROOT / ".github" / "workflows"
    / "action-gateway-smoke.yml"
)


# ---------------------------------------------------------------------------
# 5.6-A — action.yml inputs
# ---------------------------------------------------------------------------


def test_action_yml_carries_enable_tool_gateway_input() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    assert "enable-tool-gateway:" in body


def test_action_yml_default_enable_tool_gateway_is_false() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    after = body.split("enable-tool-gateway:", 1)[1]
    next_input = re.search(r"\n  [a-z][a-z0-9-]*:\n", after)
    block = after[: next_input.start()] if next_input else after
    assert 'default: "false"' in block


def test_action_yml_carries_gateway_bundle_dir_input() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    assert "gateway-bundle-dir:" in body


def test_action_yml_carries_gateway_output_dir_input() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    assert "gateway-output-dir:" in body


def test_action_yml_carries_gateway_fail_on_contract_input() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    assert "gateway-fail-on-contract:" in body


# ---------------------------------------------------------------------------
# 5.6-B — bundle validator
# ---------------------------------------------------------------------------


def test_bundle_fixture_exists_with_eight_required_files() -> None:
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
    )
    assert len(REQUIRED_BUNDLE_FILES) == 8
    for name in REQUIRED_BUNDLE_FILES:
        assert (_FIXTURE / name).is_file(), (
            f"fixture missing required file {name}"
        )


def test_validate_gateway_bundle_passes_on_fixture() -> None:
    from oida_code.action_gateway.bundle import (
        validate_gateway_bundle,
    )
    result = validate_gateway_bundle(_FIXTURE)
    assert result.ok, [
        f"{e.code}: {e.message}" for e in result.errors
    ]


def test_gateway_bundle_requires_all_files(
    tmp_path: Path,
) -> None:
    """5.6-B canary: dropping any required file fails
    validation."""
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
        validate_gateway_bundle,
    )
    # Build a near-complete bundle with one file missing.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in REQUIRED_BUNDLE_FILES[:-1]:
        (bundle / name).write_text("{}", encoding="utf-8")
    result = validate_gateway_bundle(bundle)
    assert not result.ok
    assert any(
        e.code == "required_file_missing"
        and e.offender == REQUIRED_BUNDLE_FILES[-1]
        for e in result.errors
    )


def test_gateway_bundle_rejects_missing_dir(
    tmp_path: Path,
) -> None:
    from oida_code.action_gateway.bundle import (
        validate_gateway_bundle,
    )
    result = validate_gateway_bundle(tmp_path / "nonexistent")
    assert not result.ok
    assert any(
        e.code == "bundle_dir_missing" for e in result.errors
    )


def test_gateway_bundle_workspace_root_traversal_blocked(
    tmp_path: Path,
) -> None:
    """5.6-B: bundle must resolve under workspace_root."""
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
        validate_gateway_bundle,
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bundle = tmp_path / "outside_workspace"
    bundle.mkdir()
    for name in REQUIRED_BUNDLE_FILES:
        (bundle / name).write_text("{}", encoding="utf-8")
    result = validate_gateway_bundle(
        bundle, workspace_root=workspace,
    )
    assert not result.ok
    assert any(
        e.code == "bundle_dir_outside_workspace"
        for e in result.errors
    )


def test_gateway_bundle_rejects_secret_like_paths(
    tmp_path: Path,
) -> None:
    """5.6-B: secret-shaped filenames inside the bundle fail
    validation."""
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
        validate_gateway_bundle,
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in REQUIRED_BUNDLE_FILES:
        (bundle / name).write_text("{}", encoding="utf-8")
    (bundle / ".env").write_text("API_KEY=x", encoding="utf-8")
    result = validate_gateway_bundle(bundle)
    assert not result.ok
    assert any(
        e.code == "secret_like_path" for e in result.errors
    )


def test_gateway_bundle_rejects_provider_config(
    tmp_path: Path,
) -> None:
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
        validate_gateway_bundle,
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in REQUIRED_BUNDLE_FILES:
        (bundle / name).write_text("{}", encoding="utf-8")
    (bundle / "provider.yml").write_text(
        "provider: openai", encoding="utf-8",
    )
    result = validate_gateway_bundle(bundle)
    assert not result.ok
    assert any(
        e.code == "provider_config" for e in result.errors
    )


def test_gateway_bundle_rejects_mcp_config(
    tmp_path: Path,
) -> None:
    from oida_code.action_gateway.bundle import (
        REQUIRED_BUNDLE_FILES,
        validate_gateway_bundle,
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in REQUIRED_BUNDLE_FILES:
        (bundle / name).write_text("{}", encoding="utf-8")
    (bundle / "mcp.yml").write_text(
        "mcp_server: x", encoding="utf-8",
    )
    result = validate_gateway_bundle(bundle)
    assert not result.ok
    assert any(
        e.code == "mcp_config" for e in result.errors
    )


# ---------------------------------------------------------------------------
# 5.6-D — gateway-status enum + summary forbidden-phrase scan
# ---------------------------------------------------------------------------


def test_gateway_status_enum_has_no_product_verdicts() -> None:
    """The 5-value enum must NOT contain any product verdict.
    The `Literal[...]` in `oida_code.action_gateway.status`
    pins this at the type level; the runtime check is a
    second layer."""
    from oida_code.action_gateway.status import (
        FORBIDDEN_VERDICT_TOKENS,
        GATEWAY_STATUS_VALUES,
    )
    assert len(GATEWAY_STATUS_VALUES) == 5
    assert set(GATEWAY_STATUS_VALUES) == {
        "disabled", "diagnostic_only", "contract_clean",
        "contract_failed", "blocked",
    }
    for token in FORBIDDEN_VERDICT_TOKENS:
        assert token not in GATEWAY_STATUS_VALUES


def test_derive_gateway_status_disabled_path() -> None:
    from oida_code.action_gateway.status import (
        derive_gateway_status,
    )
    assert derive_gateway_status(
        enabled=False,
        blocked_pre_execution=False,
        bundle_valid=True,
        official_field_leak_count=0,
    ) == "disabled"


def test_derive_gateway_status_blocked_path() -> None:
    from oida_code.action_gateway.status import (
        derive_gateway_status,
    )
    assert derive_gateway_status(
        enabled=True,
        blocked_pre_execution=True,
        bundle_valid=True,
        official_field_leak_count=0,
    ) == "blocked"


def test_derive_gateway_status_leak_path() -> None:
    from oida_code.action_gateway.status import (
        derive_gateway_status,
    )
    assert derive_gateway_status(
        enabled=True,
        blocked_pre_execution=False,
        bundle_valid=True,
        official_field_leak_count=1,
    ) == "contract_failed"


def test_derive_gateway_status_invalid_bundle_path() -> None:
    from oida_code.action_gateway.status import (
        derive_gateway_status,
    )
    assert derive_gateway_status(
        enabled=True,
        blocked_pre_execution=False,
        bundle_valid=False,
        official_field_leak_count=0,
    ) == "contract_failed"


def test_derive_gateway_status_default_diagnostic_only() -> None:
    from oida_code.action_gateway.status import (
        derive_gateway_status,
    )
    assert derive_gateway_status(
        enabled=True,
        blocked_pre_execution=False,
        bundle_valid=True,
        official_field_leak_count=0,
    ) == "diagnostic_only"


def test_render_gateway_summary_disabled_section() -> None:
    from oida_code.action_gateway.summary import (
        render_gateway_summary,
    )
    body = render_gateway_summary(
        enabled=False,
        status="disabled",
        grounded_report=None,
        audit_log_dir="",
    )
    assert "Gateway-grounded verifier" in body
    assert "disabled" in body
    # No forbidden tokens.
    for token in (
        "merge_safe", "production_safe", "bug_free", "verified",
    ):
        assert token not in body


def test_render_gateway_summary_absent_path() -> None:
    from oida_code.action_gateway.summary import (
        render_gateway_summary,
    )
    body = render_gateway_summary(
        enabled=True,
        status="blocked",
        grounded_report=None,
        audit_log_dir=".oida/x/audit",
    )
    assert "blocked before execution" in body
    assert "blocked" in body


def test_render_gateway_summary_normal_run() -> None:
    from oida_code.action_gateway.summary import (
        render_gateway_summary,
    )
    body = render_gateway_summary(
        enabled=True,
        status="diagnostic_only",
        grounded_report={
            "report": {
                "accepted_claims": [{"claim_id": "C.cap"}],
                "unsupported_claims": [],
                "rejected_claims": [],
            },
            "tool_results": [
                {"tool": "pytest", "status": "ok"},
            ],
        },
        audit_log_dir=".oida/x/audit",
        bundle_dir="tests/fixtures/action_gateway_bundle/x",
    )
    assert "diagnostic_only" in body
    assert "Tool calls | 1" in body
    assert "Accepted claims | 1" in body


def test_render_gateway_summary_rejects_injected_forbidden_phrase() -> (
    None
):
    """Synthesize a fake report whose claim statement contains
    `merge_safe`. The renderer's runtime forbidden-phrase scan
    must raise."""
    from oida_code.action_gateway.summary import (
        ForbiddenSummaryPhraseError,
        render_gateway_summary,
    )
    # The renderer doesn't echo claim statements directly into
    # the table — but if a future change ever adds them, we
    # want the scan to catch it. So we directly exercise the
    # scanner via an assembled body. Instead of relying on a
    # specific render path, force the issue by adding a
    # forbidden token to bundle_dir (which IS rendered).
    with pytest.raises(ForbiddenSummaryPhraseError):
        render_gateway_summary(
            enabled=True,
            status="diagnostic_only",
            grounded_report={"report": {}, "tool_results": []},
            audit_log_dir=".oida/audit",
            bundle_dir="bundles/merge_safe-fixture",
        )


# ---------------------------------------------------------------------------
# 5.6-E — emit-gateway-status CLI
# ---------------------------------------------------------------------------


def test_emit_gateway_status_writes_action_outputs_file(
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    from oida_code.cli import app

    runner = CliRunner()
    out = tmp_path / "outputs.txt"
    result = runner.invoke(
        app,
        [
            "emit-gateway-status",
            "--out", str(out),
            "--enabled", "--not-blocked", "--bundle-valid",
            "--report-json", "x.json",
            "--summary-md", "x.md",
            "--audit-log-dir", "x/audit",
        ],
    )
    assert result.exit_code == 0, result.output
    body = out.read_text(encoding="utf-8")
    for key in (
        "gateway-status=", "gateway-report-json=",
        "gateway-summary-md=", "gateway-audit-log-dir=",
        "gateway-official-field-leak-count=",
    ):
        assert key in body
    # Default = no leak, no block, valid bundle ⇒ diagnostic_only.
    assert "gateway-status=diagnostic_only" in body


def test_emit_gateway_status_blocked_path(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from oida_code.cli import app

    runner = CliRunner()
    out = tmp_path / "outputs.txt"
    result = runner.invoke(
        app,
        [
            "emit-gateway-status",
            "--out", str(out),
            "--enabled", "--blocked", "--bundle-valid",
        ],
    )
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert "gateway-status=blocked" in body


def test_emit_gateway_status_leak_detection_from_grounded_report(
    tmp_path: Path,
) -> None:
    """If the grounded_report file mentions a forbidden token,
    the leak count > 0 → contract_failed."""
    from typer.testing import CliRunner

    from oida_code.cli import app

    runner = CliRunner()
    out = tmp_path / "outputs.txt"
    fake_report = tmp_path / "fake.json"
    fake_report.write_text(
        '{"report":{"status":"merge_safe"}}',
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "emit-gateway-status",
            "--out", str(out),
            "--enabled", "--not-blocked", "--bundle-valid",
            "--grounded-report", str(fake_report),
        ],
    )
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert "gateway-status=contract_failed" in body
    assert "gateway-official-field-leak-count=" in body
    leak_line = next(
        line for line in body.splitlines()
        if line.startswith("gateway-official-field-leak-count=")
    )
    leak_count = int(leak_line.split("=", 1)[1])
    assert leak_count >= 1


# ---------------------------------------------------------------------------
# validate-gateway-bundle CLI
# ---------------------------------------------------------------------------


def test_validate_gateway_bundle_cli_exits_2_on_failure(
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    from oida_code.cli import app

    runner = CliRunner()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # No required files → validator fails.
    result = runner.invoke(
        app,
        ["validate-gateway-bundle", str(bundle)],
    )
    assert result.exit_code == 2


def test_validate_gateway_bundle_cli_succeeds_on_fixture() -> None:
    from typer.testing import CliRunner

    from oida_code.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["validate-gateway-bundle", str(_FIXTURE)],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 5.6-F — workflow + fixture
# ---------------------------------------------------------------------------


def test_action_gateway_smoke_workflow_exists() -> None:
    assert _SMOKE_WORKFLOW.is_file()


def test_action_gateway_smoke_workflow_uses_workflow_dispatch_and_push_main_only() -> (
    None
):
    body = _SMOKE_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in body
    assert "branches: [main]" in body


def test_action_gateway_smoke_workflow_permissions_contents_read() -> (
    None
):
    body = _SMOKE_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:" in body
    assert "contents: read" in body


def test_action_gateway_smoke_workflow_no_pull_request_target() -> (
    None
):
    body = _SMOKE_WORKFLOW.read_text(encoding="utf-8")
    # Strip header comments before checking. The comment block
    # at the top of the file legitimately discusses
    # `pull_request_target` to explain why it's NOT used as a
    # trigger; the actual `on:` block must not include it.
    code_lines = [
        line for line in body.splitlines()
        if not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)
    assert "pull_request_target" not in code
    assert "pull_request:" not in code


def test_action_gateway_smoke_workflow_calls_action_with_gateway_inputs() -> (
    None
):
    body = _SMOKE_WORKFLOW.read_text(encoding="utf-8")
    assert 'enable-tool-gateway: "true"' in body
    assert "gateway-bundle-dir:" in body
    assert "tool_needed_then_supported" in body


def test_action_gateway_smoke_workflow_no_secrets() -> None:
    body = _SMOKE_WORKFLOW.read_text(encoding="utf-8")
    # No `secrets.<NAME>` references AND no `env: NAME: ${{ secrets.X }}`.
    assert "secrets." not in body


# ---------------------------------------------------------------------------
# 5.6-G — fork/PR guard in action.yml
# ---------------------------------------------------------------------------


def test_action_gateway_blocks_pull_request_event() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    # The Phase 5.6 guard step must reference pull_request.
    assert "block gateway on PR / fork PR" in body
    assert "pull_request" in body


def test_action_gateway_blocks_pull_request_target_event() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    # The guard MUST also catch pull_request_target.
    assert "pull_request_target" in body


def test_action_gateway_does_not_access_secrets() -> None:
    """The Phase 5.6 gateway path must not consume any
    `secrets.*` value. Only the existing Phase 4.5 external
    LLM provider step is allowed to touch secrets."""
    body = _ACTION_YML.read_text(encoding="utf-8")
    # Find the Phase 5.6 block and verify it has no secrets.* reference.
    start = body.find("Phase 5.6 — gateway-grounded verifier")
    end = body.find("Phase 5.6 — upload gateway artifacts")
    assert start != -1 and end != -1
    block = body[start:end]
    assert "secrets." not in block


# ---------------------------------------------------------------------------
# 5.6-H — shell-injection guard
# ---------------------------------------------------------------------------


def test_action_gateway_inputs_lifted_to_env_not_inline() -> None:
    """Phase 4.5.1 + 5.6-H: `inputs.gateway-*` values must be
    lifted to `env:` and referenced as bash variables in
    `run:`. Direct `${{ inputs.gateway-X }}` interpolation
    inside a `run:` block is the documented shell-injection
    anti-pattern."""
    body = _ACTION_YML.read_text(encoding="utf-8")
    start = body.find("Phase 5.6 — gateway-grounded verifier")
    end = body.find("Phase 5.6 — upload gateway artifacts")
    block = body[start:end]
    # Find run: ... blocks and verify no ${{ inputs.gateway-X }}
    # appears inside any of them.
    in_run = False
    for line in block.splitlines():
        stripped = line.strip()
        if stripped == "run: |":
            in_run = True
            continue
        if in_run and stripped.startswith("- name:"):
            in_run = False
        if in_run and "${{ inputs.gateway-" in line:
            raise AssertionError(
                f"PR-controlled gateway input interpolated "
                f"inline in run block: {line!r}"
            )


def test_no_pr_controlled_expression_in_gateway_run_blocks() -> (
    None
):
    """Same rule: no `${{ github.event.pull_request.* }}`
    interpolation inside a gateway run: block."""
    body = _ACTION_YML.read_text(encoding="utf-8")
    start = body.find("Phase 5.6 — gateway-grounded verifier")
    end = body.find("Phase 5.6 — upload gateway artifacts")
    block = body[start:end]
    in_run = False
    for line in block.splitlines():
        stripped = line.strip()
        if stripped == "run: |":
            in_run = True
            continue
        if in_run and stripped.startswith("- name:"):
            in_run = False
        if (
            in_run
            and "${{ github.event.pull_request" in line
        ):
            raise AssertionError(
                f"PR-controlled github.event.* interpolated "
                f"inline in run block: {line!r}"
            )


def test_gateway_bundle_dir_not_interpolated_inline() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    # `${{ inputs.gateway-bundle-dir }}` is allowed in `env:`
    # mappings (its hosting env variable is expanded once,
    # safely) but never inside a `run: |` block.
    for match in re.finditer(
        r"\$\{\{\s*inputs\.gateway-bundle-dir\s*\}\}", body,
    ):
        # Walk up to find the surrounding `run:` or `env:` /
        # `with:` parent. If it's under `env:`, fine; under
        # `run:`, fail.
        prefix = body[: match.start()]
        # Find the most recent `run:` or `env:` token before
        # the match.
        last_run = prefix.rfind("\n      run: |\n")
        last_env = prefix.rfind("\n      env:\n")
        last_with = prefix.rfind("\n        with:\n")
        last_value = prefix.rfind("\n    value: ")
        last_step = prefix.rfind("\n    - name:")
        assert last_run < max(
            last_env, last_with, last_value, last_step,
        ), (
            "gateway-bundle-dir is interpolated inside a "
            "run block (shell-injection vector)"
        )


# ---------------------------------------------------------------------------
# 5.6-E — outputs surface
# ---------------------------------------------------------------------------


def test_action_gateway_outputs_exist() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    for key in (
        "gateway-report-json:",
        "gateway-summary-md:",
        "gateway-audit-log-dir:",
        "gateway-status:",
        "gateway-official-field-leak-count:",
    ):
        assert key in body


def test_gateway_outputs_do_not_surface_official_fields() -> None:
    body = _ACTION_YML.read_text(encoding="utf-8")
    # The action.yml MUST not place `total_v_net` etc. in
    # output names or default values.
    for token in (
        "total_v_net", "debt_final", "corrupt_success",
        "merge_safe", "production_safe", "bug_free",
    ):
        assert f"{token}:" not in body
        assert f"= {token}" not in body
        assert f"={token}" not in body


# ---------------------------------------------------------------------------
# Anti-MCP / anti-tool-calling regression locks
# ---------------------------------------------------------------------------


def test_no_mcp_dependency_added_phase5_6() -> None:
    body = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for token in (
        "modelcontextprotocol",
        "@modelcontextprotocol",
        "mcp-server",
        "mcp_server",
    ):
        assert token not in body


def test_no_mcp_workflow_added_phase5_6() -> None:
    workflows = _REPO_ROOT / ".github" / "workflows"
    for wf in workflows.glob("*.yml"):
        body = wf.read_text(encoding="utf-8").lower()
        assert "modelcontextprotocol" not in body
        assert "mcp.server" not in body


def test_no_provider_tool_calling_enabled_phase5_6() -> None:
    forbidden_re = re.compile(
        r"(?:client\.responses\.create|client\.messages\.create|"
        r"client\.chat\.completions\.create)[^)]*\btools\s*=",
        re.MULTILINE | re.DOTALL,
    )
    src = _REPO_ROOT / "src" / "oida_code"
    for py in src.rglob("*.py"):
        body = py.read_text(encoding="utf-8")
        assert not forbidden_re.search(body)


def test_action_gateway_module_does_not_import_mcp_runtime() -> None:
    """The action_gateway package must not IMPORT MCP runtime
    or JSON-RPC dispatch modules. The bundle validator's
    forbidden-pattern list legitimately mentions
    `modelcontextprotocol*` as a string pattern; the test
    strips Python docstrings + comments before scanning."""
    import ast
    pkg = _REPO_ROOT / "src" / "oida_code" / "action_gateway"
    for py in pkg.rglob("*.py"):
        source = py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Scan AST imports.
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.lower()
                    assert "mcp" not in name.split(".")
                    assert "modelcontextprotocol" not in name
            if isinstance(node, ast.ImportFrom):
                module = (node.module or "").lower()
                assert "mcp" not in module.split(".")
                assert "modelcontextprotocol" not in module
        # Strip docstrings + comments, then scan for runtime
        # tokens that would only appear if MCP/JSON-RPC code
        # were actually invoked.
        stripped_lines = []
        for line in source.splitlines():
            no_comment = re.sub(r"#.*$", "", line)
            stripped_lines.append(no_comment)
        no_docstrings = re.sub(
            r'"""[\s\S]*?"""', "", "\n".join(stripped_lines),
        ).lower()
        for token in (
            "stdio_server", "json_rpc", "jsonrpc",
        ):
            assert token not in no_docstrings, (
                f"{py.name} contains runtime token {token!r}"
            )


# ---------------------------------------------------------------------------
# End-to-end CLI flow against the fixture
# ---------------------------------------------------------------------------


def test_end_to_end_render_summary_against_fixture(
    tmp_path: Path,
) -> None:
    """Run the full validate → verify-grounded → render-summary
    → emit-status pipeline against the committed fixture and
    assert the artifacts are well-formed. The verify-grounded
    invocation may end with status=blocked due to the
    real-pytest timeout — that's fine, the gateway-status
    derivation handles it as diagnostic_only."""
    out = tmp_path / "out"
    out.mkdir()
    audit_dir = out / "audit"
    report_json = out / "grounded_report.json"
    summary_md = out / "summary.md"
    outputs_txt = out / "action_outputs.txt"

    py = sys.executable
    env = {**os.environ, "NO_COLOR": "1"}

    # 1. Validate.
    rc = subprocess.call(
        [
            py, "-m", "oida_code.cli", "validate-gateway-bundle",
            str(_FIXTURE),
        ],
        env=env,
    )
    assert rc == 0

    # 2. Verify-grounded — may exit 0 even when the report's
    # internal status is 'blocked' (timeout etc.).
    rc = subprocess.call(
        [
            py, "-m", "oida_code.cli", "verify-grounded",
            str(_FIXTURE / "packet.json"),
            "--forward-replay-1", str(_FIXTURE / "pass1_forward.json"),
            "--backward-replay-1", str(_FIXTURE / "pass1_backward.json"),
            "--forward-replay-2", str(_FIXTURE / "pass2_forward.json"),
            "--backward-replay-2", str(_FIXTURE / "pass2_backward.json"),
            "--tool-policy", str(_FIXTURE / "tool_policy.json"),
            "--approved-tools", str(_FIXTURE / "approved_tools.json"),
            "--gateway-definitions", str(
                _FIXTURE / "gateway_definitions.json",
            ),
            "--audit-log-dir", str(audit_dir),
            "--out", str(report_json),
        ],
        env=env,
    )
    assert rc == 0
    assert report_json.is_file()

    # 3. Emit gateway-status.
    rc = subprocess.call(
        [
            py, "-m", "oida_code.cli", "emit-gateway-status",
            "--out", str(outputs_txt),
            "--enabled", "--not-blocked", "--bundle-valid",
            "--grounded-report", str(report_json),
            "--report-json", str(report_json),
            "--summary-md", str(summary_md),
            "--audit-log-dir", str(audit_dir),
        ],
        env=env,
    )
    assert rc == 0
    body = outputs_txt.read_text(encoding="utf-8")
    assert "gateway-status=" in body
    leak_line = next(
        line for line in body.splitlines()
        if line.startswith("gateway-official-field-leak-count=")
    )
    assert int(leak_line.split("=", 1)[1]) == 0

    # 4. Render summary.
    rc = subprocess.call(
        [
            py, "-m", "oida_code.cli", "render-gateway-summary",
            str(report_json),
            "--out", str(summary_md),
            "--audit-log-dir", str(audit_dir),
            "--bundle-dir", str(_FIXTURE),
            "--status", "diagnostic_only",
        ],
        env=env,
    )
    assert rc == 0
    summary = summary_md.read_text(encoding="utf-8")
    assert "Gateway-grounded verifier" in summary
    # No forbidden token surfaced in the rendered summary.
    for token in (
        "merge_safe", "production_safe", "bug_free", "verified",
        "total_v_net", "debt_final", "corrupt_success",
    ):
        assert token not in summary


# ---------------------------------------------------------------------------
# Anti-mutation invariant
# ---------------------------------------------------------------------------


def test_runner_does_not_mutate_action_gateway_bundle_fixture(
    tmp_path: Path,
) -> None:
    """The CLI flow must be read-only over the committed
    fixture (criterion held over from Phases 5.4 / 5.5)."""
    before = {
        p: p.stat().st_mtime_ns
        for p in _FIXTURE.rglob("*")
        if p.is_file()
    }
    out = tmp_path / "out"
    out.mkdir()
    # Run validate-gateway-bundle (read-only).
    subprocess.call(
        [
            sys.executable, "-m", "oida_code.cli",
            "validate-gateway-bundle", str(_FIXTURE),
        ],
        env={**os.environ, "NO_COLOR": "1"},
    )
    after = {
        p: p.stat().st_mtime_ns
        for p in _FIXTURE.rglob("*")
        if p.is_file()
    }
    assert before == after
