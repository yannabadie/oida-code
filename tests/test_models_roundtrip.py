"""Round-trip tests for the three Pydantic I/O models (blueprint §5).

Guarantees:

* Example JSONs validate into their Pydantic models without loss.
* ``model_dump_json(indent=2)`` is deterministic (dump ↔ dump is byte-identical).
* Serialized output is semantically equal to the original JSON dict.
"""

from __future__ import annotations

import json
from pathlib import Path

from oida_code.models import (
    AuditReport,
    AuditRequest,
    NormalizedScenario,
)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_audit_request_roundtrip(examples_dir: Path) -> None:
    path = examples_dir / "audit_request.json"
    original = _read_json(path)

    model1 = AuditRequest.model_validate(original)
    dumped1 = model1.model_dump_json(indent=2)
    model2 = AuditRequest.model_validate_json(dumped1)
    dumped2 = model2.model_dump_json(indent=2)

    assert dumped1 == dumped2, "model_dump_json(indent=2) must be deterministic"
    assert json.loads(dumped1) == original, "no data lost during round-trip"


def test_audit_report_roundtrip(examples_dir: Path) -> None:
    path = examples_dir / "audit_report.json"
    original = _read_json(path)

    model1 = AuditReport.model_validate(original)
    dumped1 = model1.model_dump_json(indent=2)
    model2 = AuditReport.model_validate_json(dumped1)
    dumped2 = model2.model_dump_json(indent=2)

    assert dumped1 == dumped2, "model_dump_json(indent=2) must be deterministic"
    assert json.loads(dumped1) == original, "no data lost during round-trip"


def test_normalized_scenario_loads(examples_dir: Path) -> None:
    """Scenario example validates against the Pydantic schema.

    The source scenario uses int ``weight`` values and omits the optional
    ``config`` block, so strict byte-for-byte equivalence is not asserted; the
    mapper (phase 2) is responsible for that translation.
    """
    path = examples_dir / "normalized_scenario.json"
    data = _read_json(path)

    scenario = NormalizedScenario.model_validate(data)
    assert scenario.name == "safe_online_migration"
    assert len(scenario.events) == 3
    assert all(event.id for event in scenario.events)

    # Serialization is still idempotent even if the source form differs.
    dumped1 = scenario.model_dump_json(indent=2)
    scenario2 = NormalizedScenario.model_validate_json(dumped1)
    assert dumped1 == scenario2.model_dump_json(indent=2)
