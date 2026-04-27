"""Phase 5.8.1-C — verify-grounded ``--repo-root`` runtime override.

Background: case_001 / workflow run 25021820479 confirmed the
verifier's safety contract holds (Phase 5.8.1-B), but pytest still
errors out at runtime because the bundle's
``tool_policy.repo_root = "."`` resolves to ``$GITHUB_WORKSPACE`` —
not the audit-subject checkout the workflow already provides via
``inputs.repo-path``. Phase 5.8.1-C adds a CLI override so the
workflow's already-known audit-subject path can rebind the bundle's
repo_root at runtime without touching the bundle on disk. The
bundle's ``"."`` value remains a legal default (preserves
self-audit semantics) — only when the override is set does it kick
in.

These tests pin the override's end-to-end effect at the unit level
(``run_gateway_grounded_verifier`` consumes the rebuilt
``ToolPolicy``) and at the CLI level (``--repo-root`` reaches the
policy and survives ``model_copy``).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.estimators.llm_prompt import EvidenceItem, LLMEvidencePacket
from oida_code.verifier.contracts import VerifierToolCallSpec
from oida_code.verifier.gateway_loop import _run_tool_phase
from oida_code.verifier.tool_gateway.contracts import (
    GatewayToolDefinition,
    ToolAdmissionDecision,
    ToolAdmissionRegistry,
)
from oida_code.verifier.tool_gateway.fingerprints import (
    fingerprint_tool_definition,
)
from oida_code.verifier.tool_gateway.gateway import (
    LocalDeterministicToolGateway,
)
from oida_code.verifier.tools.adapters import (
    ExecutionContext,
    ExecutionOutcome,
)
from oida_code.verifier.tools.contracts import ToolPolicy

_RUNNER = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _pytest_def() -> GatewayToolDefinition:
    return GatewayToolDefinition(
        tool_id="oida-code/pytest",
        tool_name="pytest",
        adapter_version="0.4.0",
        description="Run pytest (read-only).",
        input_schema={
            "type": "object",
            "properties": {"scope": {"type": "array"}},
        },
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
        risk_level="read_only",
        allowed_scopes=("repo:read",),
    )


def _registry(*defs: GatewayToolDefinition) -> ToolAdmissionRegistry:
    return ToolAdmissionRegistry(approved=tuple(
        ToolAdmissionDecision(
            tool_id=d.tool_id,
            status="approved_read_only",
            reason="phase 5.8.1-C test",
            fingerprint=fingerprint_tool_definition(d),
        )
        for d in defs
    ))


def _policy(repo_root: Path | str) -> ToolPolicy:
    return ToolPolicy(
        allowed_tools=("pytest",),
        repo_root=Path(repo_root) if isinstance(repo_root, str) else repo_root,
        allow_network=False,
        allow_write=False,
    )


def _packet() -> LLMEvidencePacket:
    return LLMEvidencePacket(
        event_id="evt-repo-root-test",
        allowed_fields=("capability",),
        intent_summary="Phase 5.8.1-C repo-root override test",
        evidence_items=(
            EvidenceItem(
                id="[E.event.1]", kind="event", summary="x",
                source="ticket", confidence=0.9,
            ),
        ),
        deterministic_estimates=(),
    )


def test_run_tool_phase_executes_tool_with_policy_repo_root(
    tmp_path: Path,
) -> None:
    """The deepest unit-level guard: ``_run_tool_phase`` passes
    ``policy.repo_root`` to the gateway, which passes it to the
    adapter's executor as ``ctx.cwd``. With Phase 5.8.1-C, the
    CLI rebinds ``policy.repo_root`` to the override before this
    function ever sees the policy — so this is the contract that
    locks the override's end-to-end effect.
    """
    captured_cwds: list[Path] = []

    def _capturing_executor(ctx: ExecutionContext) -> ExecutionOutcome:
        captured_cwds.append(ctx.cwd)
        return ExecutionOutcome(
            stdout="0 passed",
            stderr="",
            returncode=0,
            timed_out=False,
            runtime_ms=1,
        )

    pytest_def = _pytest_def()
    audit_subject = tmp_path / "subject"
    audit_subject.mkdir()
    (audit_subject / "tests").mkdir()

    gateway = LocalDeterministicToolGateway(executor=_capturing_executor)
    spec = VerifierToolCallSpec(
        tool="pytest",
        purpose="verify cwd",
        expected_evidence_kind="test_result",
        scope=("tests/",),
    )
    out = _run_tool_phase(
        [spec],
        gateway=gateway,
        tool_policy=_policy(audit_subject),
        admission_registry=_registry(pytest_def),
        gateway_definitions={"pytest": pytest_def},
        audit_log_dir=tmp_path / "audit",
        event_id="evt-x",
        max_tool_calls=5,
    )
    assert len(out.tool_results) == 1
    assert captured_cwds == [audit_subject], (
        f"Phase 5.8.1-C contract: pytest cwd must equal "
        f"policy.repo_root ({audit_subject!r}); got {captured_cwds!r}"
    )


def _build_bundle(bundle_dir: Path, *, bundle_repo_root: str = ".") -> None:
    """Write a complete 8-file gateway bundle for the CLI tests."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "packet.json").write_text(json.dumps({
        "event_id": "evt-repo-root-cli",
        "allowed_fields": ["capability"],
        "intent_summary": "Phase 5.8.1-C CLI test",
        "evidence_items": [{
            "id": "[E.event.1]",
            "kind": "event",
            "summary": "x",
            "source": "ticket",
            "confidence": 0.9,
        }],
        "deterministic_estimates": [],
    }), encoding="utf-8")
    (bundle_dir / "pass1_forward.json").write_text(json.dumps({
        "event_id": "evt-repo-root-cli",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [{
            "tool": "pytest",
            "purpose": "scope-relative tool execution test",
            "expected_evidence_kind": "test_result",
            "scope": ["tests/"],
        }],
    }), encoding="utf-8")
    (bundle_dir / "pass1_backward.json").write_text("[]", encoding="utf-8")
    (bundle_dir / "pass2_forward.json").write_text(json.dumps({
        "event_id": "evt-repo-root-cli",
        "supported_claims": [],
        "rejected_claims": [],
        "requested_tools": [],
    }), encoding="utf-8")
    (bundle_dir / "pass2_backward.json").write_text("[]", encoding="utf-8")
    (bundle_dir / "tool_policy.json").write_text(json.dumps({
        "allowed_tools": ["pytest"],
        "repo_root": bundle_repo_root,
        "allowed_paths": [],
        "deny_patterns": [],
        "allow_network": False,
        "allow_write": False,
        "max_tool_calls": 5,
        "max_total_runtime_s": 60,
        "max_output_chars_per_tool": 8000,
    }), encoding="utf-8")
    pytest_def_obj = _pytest_def()
    (bundle_dir / "gateway_definitions.json").write_text(json.dumps({
        "pytest": pytest_def_obj.model_dump(mode="json"),
    }), encoding="utf-8")
    fp = fingerprint_tool_definition(pytest_def_obj)
    (bundle_dir / "approved_tools.json").write_text(json.dumps({
        "approved": [{
            "tool_id": "oida-code/pytest",
            "status": "approved_read_only",
            "reason": "Phase 5.8.1-C test",
            "fingerprint": fp.model_dump(mode="json"),
        }],
        "quarantined": [],
        "rejected": [],
    }), encoding="utf-8")


def test_cli_repo_root_option_propagates_to_pytest_invocation(
    tmp_path: Path,
) -> None:
    """End-to-end CLI test: the override surfaces in the audit-log
    ``request_summary`` (which embeds the resolved scope path) and
    in pytest's working directory by way of the actual subprocess
    invocation.

    The bundle ships ``repo_root="."``. Without override, scope
    ``tests/`` would resolve relative to the CLI's cwd (the test
    harness's tmp scratch). With ``--repo-root <audit_subject>``,
    the resolved scope is ``<audit_subject>/tests``.
    """
    bundle = tmp_path / "bundle"
    _build_bundle(bundle, bundle_repo_root=".")

    audit_subject = tmp_path / "audit-subject"
    audit_subject.mkdir()
    (audit_subject / "tests").mkdir()
    (audit_subject / "tests" / "test_marker.py").write_text(
        "def test_x():\n    assert True\n",
        encoding="utf-8",
    )

    audit_dir = tmp_path / "audit"
    out = tmp_path / "grounded_report.json"

    result = _RUNNER.invoke(
        app,
        [
            "verify-grounded",
            str(bundle / "packet.json"),
            "--forward-replay-1", str(bundle / "pass1_forward.json"),
            "--backward-replay-1", str(bundle / "pass1_backward.json"),
            "--forward-replay-2", str(bundle / "pass2_forward.json"),
            "--backward-replay-2", str(bundle / "pass2_backward.json"),
            "--tool-policy", str(bundle / "tool_policy.json"),
            "--approved-tools", str(bundle / "approved_tools.json"),
            "--gateway-definitions",
            str(bundle / "gateway_definitions.json"),
            "--audit-log-dir", str(audit_dir),
            "--out", str(out),
            "--repo-root", str(audit_subject),
        ],
    )
    assert result.exit_code == 0, (
        f"verify-grounded failed:\nstdout={result.stdout}\n"
        f"exception={result.exception}"
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    tool_results = report["tool_results"]
    assert len(tool_results) == 1
    assert tool_results[0]["tool"] == "pytest"
    # status=ok proves pytest actually found the test under
    # <audit_subject>/tests/. Without the override, the resolved
    # scope path would have been the CLI's cwd or "." which has no
    # tests/ subdir — pytest would have exited rc=4 with status=error.
    assert tool_results[0]["status"] == "ok", (
        f"Phase 5.8.1-C: with --repo-root pointing at the audit "
        f"subject, pytest must find the tests/ subdir there and "
        f"return status=ok. Got status={tool_results[0]['status']!r}, "
        f"summary={tool_results[0]['evidence_items']!r}"
    )


def test_cli_no_repo_root_falls_back_to_bundle_value(
    tmp_path: Path,
) -> None:
    """Regression guard — without ``--repo-root``, the bundle's
    ``tool_policy.repo_root`` survives unchanged. Self-audit
    bundles that ship ``repo_root="."`` and run from inside the
    target tree must keep working as before Phase 5.8.1-C.
    """
    bundle = tmp_path / "bundle"
    audit_subject = tmp_path / "audit-subject"
    audit_subject.mkdir()
    (audit_subject / "tests").mkdir()
    (audit_subject / "tests" / "test_marker.py").write_text(
        "def test_x():\n    assert True\n",
        encoding="utf-8",
    )
    # Bundle's repo_root pinned to the audit-subject absolute path
    # so the no-override path still finds tests/.
    _build_bundle(bundle, bundle_repo_root=str(audit_subject.resolve()))

    audit_dir = tmp_path / "audit"
    out = tmp_path / "grounded_report.json"

    result = _RUNNER.invoke(
        app,
        [
            "verify-grounded",
            str(bundle / "packet.json"),
            "--forward-replay-1", str(bundle / "pass1_forward.json"),
            "--backward-replay-1", str(bundle / "pass1_backward.json"),
            "--forward-replay-2", str(bundle / "pass2_forward.json"),
            "--backward-replay-2", str(bundle / "pass2_backward.json"),
            "--tool-policy", str(bundle / "tool_policy.json"),
            "--approved-tools", str(bundle / "approved_tools.json"),
            "--gateway-definitions",
            str(bundle / "gateway_definitions.json"),
            "--audit-log-dir", str(audit_dir),
            "--out", str(out),
            # No --repo-root — falls back to bundle value.
        ],
    )
    assert result.exit_code == 0, (
        f"verify-grounded failed:\nstdout={result.stdout}\n"
        f"exception={result.exception}"
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["tool_results"][0]["status"] == "ok"
