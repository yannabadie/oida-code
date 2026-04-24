"""Phase 2 end-to-end smoke test.

Flow: synthetic repo → extract obligations → synthesize scenario with evidence
→ vendored OIDAAnalyzer → non-zero grounding and well-formed summary.

The synthetic repo is generated inside ``tmp_path`` so the test is hermetic.
"""

from __future__ import annotations

from pathlib import Path

from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer
from oida_code.extract.obligations import extract_obligations
from oida_code.models.audit_request import (
    AuditRequest,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.evidence import ToolEvidence
from oida_code.score.mapper import obligations_to_scenario, pydantic_to_vendored


def _write_green_repo(root: Path) -> list[str]:
    (root / "src").mkdir()
    (root / "src" / "service.py").write_text(
        'def pay(amount: int) -> int:\n'
        '    assert amount > 0, "amount must be positive"\n'
        '    if amount > 10_000:\n'
        '        raise ValueError("too large")\n'
        '    return amount * 2\n',
        encoding="utf-8",
    )
    (root / "src" / "routes.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/health')\n"
        "def health():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    return ["src/service.py", "src/routes.py"]


def test_phase2_pipeline_produces_grounded_scenario(tmp_path: Path) -> None:
    changed = _write_green_repo(tmp_path)

    obligations = extract_obligations(tmp_path, changed)
    # service.py → 2 preconditions (assert + guard); routes.py → 1 api_contract.
    assert len(obligations) >= 3
    kinds = {o.kind for o in obligations}
    assert "precondition" in kinds
    assert "api_contract" in kinds

    evidence = [
        ToolEvidence(
            tool="pytest",
            status="ok",
            duration_ms=10,
            counts={"total": 12, "failure": 0, "error": 0},
        ),
        ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={}),
        ToolEvidence(tool="mypy", status="ok", duration_ms=5, findings=[], counts={}),
    ]
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=changed),
    )

    scenario = obligations_to_scenario(obligations, request=request, tool_evidence=evidence)
    assert len(scenario.events) == len(obligations)

    # Evidence linker should have closed at least one precondition and the
    # api_contract → at least one event now carries a verified precondition.
    verified_events = [
        e for e in scenario.events if any(p.verified for p in e.preconditions)
    ]
    assert verified_events, "evidence linker did not close any obligations"

    report = OIDAAnalyzer(pydantic_to_vendored(scenario)).analyze()
    summary = report["summary"]
    assert summary["event_count"] == len(scenario.events)
    assert summary["mean_grounding"] > 0.0, "grounding should be non-zero with green evidence"
    # Sanity: analyzer produces all the downstream fields reports depend on.
    for key in ("mean_q_obs", "total_v_net"):
        assert key in summary
